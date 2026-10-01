"""Frozen clean births; one current, source-bound contact measurement admission.

The certificate establishes measurement lineage, never fish identity. Contact
facts stay current and anonymous; they do not repair or extend past histories.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import math

from common import ROOT, HERE, read
from contact_measurement import validate_contact_certificate

CFG = read(HERE / 'CONFIG.json')
_spec = importlib.util.spec_from_file_location('ds12_frozen_clean_birth',
    ROOT / 'experiments/ds11_depth_birth_reconnect/reconnect.py')
_legacy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_legacy)
qualification = _legacy.qualification
geometry_forecast = _legacy.geometry_forecast
predict = _legacy.predict
_density = _legacy._density
_finite = _legacy._finite
log_t4 = _legacy.log_t4
_logaddexp = _legacy._logaddexp


def admission_hash(body):
    """Canonical metadata body, shared by selection and the real transaction."""
    content = {k:v for k,v in body.items() if k != 'body_sha256'}
    encoded = json.dumps(content, sort_keys=True, separators=(',', ':'),
                         allow_nan=False).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def _admission_body(query, certificate, mode, segment, measurement):
    valid = bool(certificate and validate_contact_certificate(certificate,
        native=query['source'], frame=query['frame'], mode=mode))
    expected_source = ('RAW_SENSOR_CONTACT_CORE' if mode == 'RAW_DEPTH'
                       else 'NATIVE_V2_RETAINED_CONTACT_CORE')
    if valid:
        valid = bool(certificate['segment'] == segment and certificate['time'] == query['time']
            and certificate['mask_area'] == query['area'] and certificate['source'] == expected_source
            and certificate['source_measurement_fact_id'] == measurement.get('fact_id')
            and certificate['no_future_frame_read'] and certificate['no_history_write'])
    # Caller quality, area and real contact classification are separate from
    # component depth quality. Neither is rewritten into a clean observation.
    current = bool(query.get('quality', False) and query.get('area', 0) >= CFG['birth_min_area']
                   and query.get('neighbors') and
                   query.get('observation_class') == 'BIRTH_UNASSIGNED')
    components = copy.deepcopy(certificate.get('qualified_components', [])) if valid else []
    return dict(schema='DS12_CURRENT_CONTACT_ADMISSION_V1', segment=segment, mode=mode,
        source=query['source'], frame=query['frame'], time=query['time'],
        source_measurement_fact_id=measurement.get('fact_id'),
        query=copy.deepcopy(query), certificate=copy.deepcopy(certificate),
        certificate_valid=valid, current_quality_eligible=current,
        qualified_components=components,
        admitted=bool(valid and current and components and mode != 'DEPTH_ZERO'),
        component_policy='PRE_FIXED_EQUAL_WEIGHT_QUERY_COMPONENTS_SHARED_BY_ALL_CANDIDATES',
        retains_actual_neighbors_and_class=True, current_contact_is_not_past_history=True,
        physical_surface_identity='UNKNOWN', physical_depth_accuracy_mm='UNKNOWN')


def validate_admission_body(body, *, query=None, mode=None, segment=None):
    """Recheck the actual body, not merely its externally supplied hash."""
    try:
        actual = body['query']
        if query is not None and actual != query:
            return False
        if mode is not None and body['mode'] != mode:
            return False
        if segment is not None and body['segment'] != segment:
            return False
        rebuilt = _admission_body(actual, body['certificate'], body['mode'], body['segment'],
            {'fact_id':body['source_measurement_fact_id']})
        rebuilt['selected_target'] = body['selected_target']
        rebuilt['body_sha256'] = admission_hash(rebuilt)
        return body == rebuilt and rebuilt['admitted']
    except (KeyError, TypeError, ValueError, OverflowError):
        return False


def _mixture(terms, components):
    """Normalized fixed query mixture; never average likelihood ratios."""
    result = None
    for term, component in zip(terms, components):
        weighted = math.log(component['weight']) + term
        result = weighted if result is None else _logaddexp(result, weighted)
    return result


def choose(query, candidates, measurements, full, mode, segment, contact_certificates=None):
    """Return an old public or None. Clean output is exactly frozen DS11."""
    if not query.get('neighbors'):
        return _legacy.choose(query, candidates, measurements, full, mode, segment)
    assert mode in ('RAW_DEPTH', 'RESTORED_DEPTH', 'DEPTH_ZERO') and CFG['student_df'] == 4
    source = query['source']
    assert _finite(query['time']) and len(query['center']) == 2
    assert all(_finite(x) for x in query['center'])
    certificate = (contact_certificates or {}).get(source)
    measurement = measurements[source]
    body = _admission_body(query, certificate, mode, segment, measurement)
    components = body['qualified_components']
    current_ok = body['current_quality_eligible']
    query_ok = body['admitted']
    background = _density._depth_background(measurements, full) if mode != 'DEPTH_ZERO' else None
    if background and background['method'] == 'NO_USABLE_DEPTH_BACKGROUND':
        background = None
    depth_ok = bool(query_ok and background)
    background_terms = ([_density._background_logdensity(background, c['median_mm'], c['scale_mm'])
                         for c in components] if depth_ok else [])
    depth_background = _mixture(background_terms, components) if depth_ok else 0.
    if depth_ok:
        background['query_specific_logdensity'][str(source)] = dict(
            assigned_depth_source=source, log_density=depth_background,
            components=[dict(component_id=c['component_id'], weight=c['weight'],
                observation_mm=c['median_mm'], query_sigma_mm=c['scale_mm'], log_density=b)
                for c, b in zip(components, background_terms)],
            mixture='EQUAL_WEIGHT_DENSITIES_BEFORE_SIGNAL_BACKGROUND_CONTRAST',
            all_candidates_share_this_source_density=True)
    geo_background = -math.log(CFG['geometry_background_area_px'])
    signal = CFG['signal_fraction']
    scored, unscored, duplicates, eligible_by_public = {}, [], [], {}
    for candidate in sorted(candidates, key=lambda c: (c['public'], c['source'])):
        reasons = qualification(candidate, query, segment)
        fact = copy.deepcopy(candidate)
        fact['selector_reasons'] = reasons
        if reasons:
            unscored.append(fact)
            continue
        public = candidate['public']
        if public in eligible_by_public:
            previous = eligible_by_public[public]
            if any(candidate[k] != previous[k] for k in
                   ('source', 'anchor', 'geometry_history', 'frozen_depth')):
                raise ValueError('conflicting qualified histories for the same old public')
            duplicates.append(fact)
            continue
        eligible_by_public[public] = candidate
    prior = -math.log(len(eligible_by_public)+1)
    scored['NEW'] = dict(public=source, mapping={source:source}, is_new=True,
        geometry_log_lr=0., depth_log_lr=0., log_prior=prior, log_score=prior,
        geometry=dict(used=False, raw_log_density=None, background_log_density=geo_background,
                      mixture_log_density=geo_background, log_lr=0.),
        depth=dict(used=False, raw_log_density=None, background_log_density=depth_background,
                   mixture_log_density=depth_background, log_lr=0., missing_model='COMMON_NEW_IDENTITY_NULL'))
    for public, candidate in eligible_by_public.items():
        geo = geometry_forecast(candidate['geometry_history'], query['time'], segment)
        raw_geo = _density.log_t4_2d(query['center'], geo['mu_px'], geo['shape_px2'])
        geo_lr = _logaddexp(math.log(signal)+raw_geo-geo_background, math.log(1.-signal))
        forecast = predict(copy.deepcopy(candidate['frozen_depth']), query['time'])
        used = bool(depth_ok and _finite(forecast['mu_mm']) and _finite(forecast['scale_mm'])
                    and forecast['scale_mm'] > 0)
        terms = ([log_t4(c['median_mm'], forecast['mu_mm'],
                        math.hypot(forecast['scale_mm'], c['scale_mm'])) for c in components]
                 if used else [])
        raw_depth = _mixture(terms, components) if used else None
        depth_lr = (_logaddexp(math.log(signal)+raw_depth-depth_background, math.log(1.-signal))
                    if used else 0.)
        scored[f'OLD:{public}'] = dict(public=public, source=candidate['source'],
            mapping={source:public}, is_new=False, qualification=copy.deepcopy(candidate),
            geometry_forecast=geo, depth_forecast=forecast,
            geometry_log_lr=geo_lr, depth_log_lr=depth_lr, log_prior=prior,
            log_score=prior+geo_lr+depth_lr,
            geometry=dict(used=True, raw_log_density=raw_geo, background_log_density=geo_background,
                mixture_log_density=geo_background+geo_lr, log_lr=geo_lr),
            depth=dict(used=used, raw_log_density=raw_depth, background_log_density=depth_background,
                mixture_log_density=depth_background+depth_lr, log_lr=depth_lr,
                components=[dict(component_id=c['component_id'], weight=c['weight'],
                    observation_mm=c['median_mm'], observation_scale_mm=c['scale_mm'],
                    combined_scale_mm=math.hypot(forecast['scale_mm'], c['scale_mm']),
                    raw_log_density=t) for c, t in zip(components, terms)],
                measurement_fact_id=certificate.get('fact_id') if certificate else None,
                assigned_depth_source=source,
                missing_model=None if used else 'COMMON_QUERY_DEPTH_UNINFORMATIVE'))
    ranked = sorted(scored, key=lambda k: (-scored[k]['log_score'], k != 'NEW', k))
    best, runner = ranked[0], ranked[1] if len(ranked) > 1 else None
    maximum = scored[best]['log_score']
    total = sum(math.exp(c['log_score']-maximum) for c in scored.values())
    for c in scored.values():
        c['posterior'] = math.exp(c['log_score']-maximum)/total
        c['log_joint_density'] = c['log_score']+geo_background+depth_background
    margin = maximum-scored[runner]['log_score'] if runner else None
    dummy_margin = maximum-scored['NEW']['log_score']
    threshold = math.log(CFG['minimum_joint_odds'])
    positive = scored[best]['depth_log_lr'] > 0 and scored[best]['depth']['used']
    accepted = bool(query['frame'] > 1 and current_ok and depth_ok and best != 'NEW'
                    and runner and margin >= threshold and dummy_margin >= threshold and positive)
    selected = best if accepted else 'NEW'
    body['selected_target'] = scored[best]['public'] if accepted else None
    body['body_sha256'] = admission_hash(body)
    reason = ('SEGMENT_INITIAL_FRAME_NOT_ASSOCIATED' if query['frame'] == 1 else
              'CURRENT_QUALITY_CONTACT_OR_CLASS_INELIGIBLE' if not current_ok else
              'CURRENT_CONTACT_CERTIFICATE_UNINFORMATIVE' if not depth_ok else
              'NEW_IDENTITY_BEST' if best == 'NEW' else
              'NONPOSITIVE_DEPTH_SUPPORT' if not positive else
              'INSUFFICIENT_JOINT_ODDS' if not accepted else 'DEPTH_SUPPORTED_BIRTH_ACCEPTED')
    return (scored[best]['public'] if accepted else None), dict(reason=reason,
        accepted=accepted, best=best, runner_up=runner, selected=selected,
        selected_mapping=scored[selected]['mapping'], baseline_mapping={source:source},
        candidates=scored, unscored_candidates=unscored,
        duplicate_public_facts_not_extra_prior_votes=duplicates,
        unique_physical_candidates=len(scored), log_prior=prior, margin=margin,
        best_vs_new_margin=dummy_margin, minimum_log_odds=threshold,
        positive_depth_lr_required=CFG['birth_positive_depth_lr_required'],
        current_quality_eligible=bool(current_ok), current_depth_usable=bool(query_ok),
        depth_used=depth_ok, all_candidate_query_depth_common_uninformative=not depth_ok,
        depth_assignment=dict(observation_source=source, assigned_depth_source=source,
            measurement_fact_id=certificate.get('fact_id') if certificate else None,
            source_measurement_fact_id=certificate.get('source_measurement_fact_id') if certificate else None,
            cohort=certificate.get('cohort') if certificate else None,
            components=copy.deepcopy(components), actual_state_source=source,
            actual_state_fact_id=measurement.get('fact_id')),
        background=dict(geometry_area_px=CFG['geometry_background_area_px'],
                        geometry_log_density=geo_background, depth=background),
        evidence_max_frame=query['frame'], past_depth_and_geometry_cutoff=query['frame']-1,
        query=copy.deepcopy(query), single_object_geometry=True,
        admission_body=body, admission_body_sha256=body['body_sha256'],
        joint_independence='CONDITIONAL_GEOMETRY_DEPTH_FACTORIZATION_ASSUMPTION',
        posterior_interpretation='NORMALIZED_PLUGIN_CONTRAST_NOT_CALIBRATED_IDENTITY_PROBABILITY',
        physical_surface_identity='UNKNOWN', physical_depth_accuracy_mm='UNKNOWN')
