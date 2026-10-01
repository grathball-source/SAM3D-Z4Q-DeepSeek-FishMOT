"""One-source birth association against distinct absent publics and NEW.

Selection is read-only. The caller and the real bridge recheck occupation,
first-ever birth, group reservation and the exact authoritative bank anchor.
"""
from __future__ import annotations

import copy
import importlib.util
import math
import numpy as np

from common import HERE, ROOT, read
from forecast import predict
from depth_measurement import usable
from depth_score import log_t4, _logaddexp
from merge_split_manager import velocity

CFG = read(HERE / 'CONFIG.json')
# Reuse the frozen normalized densities and current-object null, not its
# two-role predictor or identity decision. This dependency is in the freeze.
_spec = importlib.util.spec_from_file_location('ds10_birth_density_primitives',
    ROOT / 'experiments/ds10_depth_failure_repair/association.py')
_density = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_density)


def _finite(value):
    return isinstance(value, (int, float)) and math.isfinite(value)


def _version(item):
    return [item.get(k) for k in ('source', 'source_generation', 'public_id', 'public_epoch')]


def _fact(item, segment):
    return dict(fact_id=f"{segment}/F{item['frame']}/n:{item['source']}/geometry",
        frame=item['frame'], time=item['time'], source=item['source'],
        version=_version(item), center_px=list(item['center']), bbox=list(item['bbox']))


def qualification(candidate, query, segment):
    """Recheck the supplied certification without joining or repairing fragments."""
    reasons = list(candidate.get('reasons', []))
    if not candidate.get('eligible', False):
        return reasons or ['CALLER_INELIGIBLE']
    history = candidate.get('geometry_history', [])[-CFG['fit_observations']:]
    frozen = candidate.get('frozen_depth', {})
    samples = frozen.get('samples', [])[-CFG['fit_observations']:]
    minimum = CFG['birth_min_history_samples']
    if len(history) < minimum or len(samples) < minimum:
        reasons.append('TOO_FEW_CERTIFIED_PAST_SAMPLES')
        return reasons
    key = frozen.get('key')
    version = key if key and len(key)==5 else [None]*5
    source, public = candidate['source'], candidate['public']
    if (not key or len(key) != 5 or key[0] != segment or key[3] != public or
            frozen.get('source') != source or frozen.get('public') != public):
        reasons.append('DEPTH_VERSION_SOURCE_PUBLIC_MISMATCH')
    if any(_version(p) != _version(history[-1]) for p in history):
        reasons.append('GEOMETRY_VERSION_BREAK')
    if [(p['frame'],p['time']) for p in history] != [(p['frame'],p['time']) for p in samples]:
        reasons.append('GEOMETRY_RAW_CERTIFICATION_WINDOW_MISMATCH')
    if key and len(key) == 5 and _version(history[-1]) != [source, key[2], public, key[4]]:
        reasons.append('GEOMETRY_DEPTH_VERSION_MISMATCH')
    cutoff = frozen.get('cutoff_frame')
    if cutoff is None or cutoff >= query['frame']:
        reasons.append('INVALID_PAST_DEPTH_CUTOFF')
    for points, name in ((history, 'GEOMETRY'), (samples, 'DEPTH')):
        if any(not _finite(p.get('time')) or p['time'] >= query['time'] or
               p.get('frame', query['frame']) >= query['frame'] for p in points):
            reasons.append(f'{name}_NONCAUSAL_OR_NONFINITE')
        if any(b['frame'] != a['frame'] + 1 or b['time'] <= a['time']
               for a, b in zip(points, points[1:])):
            reasons.append(f'{name}_NONCONTIGUOUS_FRAGMENT')
    if any(p.get('source') != source or p.get('neighbors') or p.get('area', 0) < 64 or
           p.get('observation_class') not in ('SOURCE_OBSERVATION', 'RESTORED_POST') or
           not all(_finite(x) for x in p.get('center', []) + p.get('bbox', [])) or
           len(p.get('center', [])) != 2 or len(p.get('bbox', [])) != 4 for p in history):
        reasons.append('INVALID_CLEAN_GEOMETRY_FACT')
    if any(p.get('source') != 'RAW_SENSOR_ADAPTIVE' or p.get('version_key') != key or
           p['frame'] > (cutoff if cutoff is not None else -1) or
           not _finite(p.get('z_mm')) or p['z_mm'] <= 0 or
           not _finite(p.get('mad_mm')) or p['mad_mm'] < 0 or
           max(CFG['raw_scale_floor_mm'], 1.4826*p['mad_mm']) > CFG['max_raw_scale_mm']
           for p in samples):
        reasons.append('INVALID_RAW_CERTIFIED_DEPTH_FACT')
    reference = candidate.get('reference_anchor') or {}
    if (reference.get('native_id') != source or reference.get('canonical_id') != public or
            reference.get('source_generation') != version[2] or reference.get('public_epoch') != version[4] or
            reference.get('frame') != history[-1]['frame'] or
            reference.get('frame') != samples[-1]['frame'] or
            reference.get('time') != history[-1]['time'] or
            samples[-1]['time'] != history[-1]['time']):
        reasons.append('CLEAN_REFERENCE_GEOMETRY_DEPTH_ENDPOINT_MISMATCH')
    anchor = candidate.get('anchor') or {}
    if (anchor.get('native_id') != source or anchor.get('canonical_id') != public or
            anchor.get('frame',query['frame']) >= query['frame'] or
            candidate.get('bank_anchor_version') != key):
        reasons.append('PAST_AUTHORITATIVE_BANK_SOURCE_PUBLIC_VERSION_MISMATCH')
    gap = query['time'] - samples[-1]['time']
    if not 0 < gap <= CFG['birth_max_gap_seconds']:
        reasons.append('CERTIFIED_HISTORY_EXPIRED_OR_NONCAUSAL')
    risk = candidate.get('risk_interval') or {}
    if (risk.get('reference_frame') != history[-1]['frame'] or
            risk.get('reference_time') != history[-1]['time'] or
            risk.get('query_frame') != query['frame'] or risk.get('query_time') != query['time'] or
            not _finite(risk.get('full_gap_seconds')) or
            not math.isclose(risk.get('full_gap_seconds',0.),gap,rel_tol=1e-12,abs_tol=1e-12)):
        reasons.append('EXPLICIT_REFERENCE_TO_QUERY_INTERVAL_MISMATCH')
    for fact in candidate.get('anonymous_risk_observations',[]):
        if (fact.get('version_key') != key or fact.get('source_generation') != version[2] or
                fact.get('public_epoch') != version[4] or
                not _finite(fact.get('time')) or
                not history[-1]['time'] < fact['time'] < query['time'] or
                not history[-1]['frame'] < fact.get('frame',query['frame']) < query['frame']):
            reasons.append('ANONYMOUS_RISK_FACT_VERSION_OR_CAUSALITY_MISMATCH')
            break
    return list(dict.fromkeys(reasons))


def _mean(history, query_time):
    fit = velocity(history)
    last = history[-1]
    gap = query_time - last['time']
    cap = min(gap, 1.)
    estimated = fit['status'] != 'UNKNOWN'
    mean = ([fit['intercept_px'][i] + fit['px_per_second'][i] *
             (last['time'] + cap - fit['time_origin']) for i in (0, 1)]
            if estimated else list(last['center']))
    return mean, fit, gap, cap


def geometry_forecast(history, query_time, segment):
    """One actual <=10 observation prefix; no artificial second role."""
    window = history[-CFG['fit_observations']:]
    mean, fit, gap, cap = _mean(window, query_time)
    residuals = []
    for i, target in enumerate(window[1:], 1):
        prefix = window[:i]
        predicted, prior_fit, _, prior_cap = _mean(prefix, target['time'])
        residuals.append(dict(target=_fact(target, segment),
            predictor_facts=[_fact(p, segment) for p in prefix],
            predicted_center_px=predicted,
            residual_px=[target['center'][j]-predicted[j] for j in (0, 1)],
            mean_mode='OLS_LINEAR_EXTRAPOLATION' if prior_fit['status'] != 'UNKNOWN'
                      else 'LAST_MEASURED_POSITION_ONLY', capped_mean_gap_seconds=prior_cap))
    if len(residuals) >= CFG['geometry_residual_min']:
        errors = np.asarray([r['residual_px'] for r in residuals], float)
        moment = errors.T @ errors / len(errors)
        shrink = CFG['geometry_covariance_shrinkage']
        covariance = ((1.-shrink)*moment + shrink*np.diag(np.diag(moment)) +
                      CFG['geometry_covariance_floor_px2']*np.eye(2))
        calibration = dict(method='UNCENTERED_NEXT_POINT_RESIDUAL_SECOND_MOMENT',
            second_moment_px2=moment.tolist(), shrinkage=shrink,
            floor_px2=CFG['geometry_covariance_floor_px2'])
    else:
        box = window[-1]['bbox']
        sigma = max(CFG['geometry_fallback_sigma_px'],
                    CFG['geometry_fallback_bbox_fraction'] * math.hypot(box[2]-box[0], box[3]-box[1]))
        covariance = sigma*sigma*np.eye(2)
        calibration = dict(method='TOO_FEW_RESIDUALS_ISOTROPIC_BBOX', sigma_px=sigma)
    span = window[-1]['time']-window[0]['time']
    time_scale = max(span, 1./30.)
    growth = 1.+(gap/time_scale)**2
    inflated = covariance*growth
    calibration.update(residual_count=len(residuals), residuals=residuals,
        history_window='LATEST_AT_MOST_TEN_CERTIFIED_GEOMETRY_OBSERVATIONS',
        physical_accuracy_calibrated=False)
    return dict(available=True, mu_px=mean, shape_px2=(inflated/2.).tolist(),
        covariance_px2=covariance.tolist(), inflated_covariance_px2=inflated.tolist(),
        mean_mode='OLS_LINEAR_EXTRAPOLATION' if fit['status'] != 'UNKNOWN' else 'LAST_MEASURED_POSITION_ONLY',
        velocity_fit=fit, samples=len(window), pre_facts=[_fact(p, segment) for p in window],
        actual_gap_seconds=gap, capped_mean_gap_seconds=cap,
        real_pre_span_seconds=span, time_scale_seconds=time_scale, growth_factor=growth,
        calibration=calibration, post_velocity_status='UNKNOWN_AT_BIRTH')


def choose(query, candidates, measurements, full, mode, segment):
    """Return an old public or None (NEW); numerical choice never writes identity."""
    assert mode in ('RAW_DEPTH', 'RESTORED_DEPTH', 'DEPTH_ZERO') and CFG['student_df'] == 4
    source = query['source']
    assert _finite(query['time']) and all(_finite(x) for x in query['center'])
    assert len(query['center']) == 2
    current_ok = (query.get('quality', False) and query.get('area', 0) >= CFG['birth_min_area']
                  and not query.get('neighbors') and query.get('observation_class') == 'BIRTH_UNASSIGNED')
    measurement = measurements[source]
    admitted_source = (measurement.get('source') == 'RAW_SENSOR_ADAPTIVE' if mode == 'RAW_DEPTH'
        else measurement.get('cohort') == 'retained' and
             measurement.get('source') == 'RESTORED_V2_RETAINED' if mode == 'RESTORED_DEPTH' else False)
    query_ok = bool(current_ok and admitted_source and measurement['core_usable'] and
                    _finite(measurement['core']['median']) and usable(measurement['core']))
    background = _density._depth_background(measurements, full) if mode != 'DEPTH_ZERO' else None
    if background and background['method'] == 'NO_USABLE_DEPTH_BACKGROUND':
        background = None
    depth_ok = bool(query_ok and background)
    query_sigma = max(CFG['raw_scale_floor_mm'], 1.4826*measurement['core']['mad']) if depth_ok else None
    depth_background = (_density._background_logdensity(background, measurement['core']['median'], query_sigma)
                        if depth_ok else 0.)
    if depth_ok:
        background['query_specific_logdensity'][str(source)] = dict(
            observation_mm=measurement['core']['median'], query_sigma_mm=query_sigma,
            assigned_depth_source=source, log_density=depth_background,
            all_candidates_share_this_source_density=True)
    geo_background = -math.log(CFG['geometry_background_area_px'])
    signal = CFG['signal_fraction']
    scored, unscored, duplicates = {}, [], []
    eligible_by_public = {}
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
        combined = math.hypot(forecast['scale_mm'], query_sigma) if used else None
        raw_depth = log_t4(measurement['core']['median'], forecast['mu_mm'], combined) if used else None
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
                observation_scale_mm=query_sigma, combined_scale_mm=combined,
                measurement_fact_id=measurement.get('fact_id'), assigned_depth_source=source,
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
    reason = ('SEGMENT_INITIAL_FRAME_NOT_ASSOCIATED' if query['frame'] == 1 else
              'CURRENT_QUALITY_CONTACT_OR_CLASS_INELIGIBLE' if not current_ok else
              'CURRENT_RAW_OR_RETAINED_DEPTH_UNINFORMATIVE' if not depth_ok else
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
            measurement_fact_id=measurement.get('fact_id'), cohort=measurement.get('cohort', 'RAW'),
            observation_mm=measurement['core']['median'], observation_mad_mm=measurement['core']['mad'],
            actual_state_source=source, actual_state_fact_id=measurement.get('fact_id')),
        background=dict(geometry_area_px=CFG['geometry_background_area_px'],
                        geometry_log_density=geo_background, depth=background),
        evidence_max_frame=query['frame'], past_depth_and_geometry_cutoff=query['frame']-1,
        query=copy.deepcopy(query), single_object_geometry=True,
        joint_independence='CONDITIONAL_GEOMETRY_DEPTH_FACTORIZATION_ASSUMPTION',
        posterior_interpretation='NORMALIZED_PLUGIN_CONTRAST_NOT_CALIBRATED_IDENTITY_PROBABILITY',
        physical_surface_identity='UNKNOWN', physical_depth_accuracy_mm='UNKNOWN')
