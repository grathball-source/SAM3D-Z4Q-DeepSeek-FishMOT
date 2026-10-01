"""DS9 identity/geometry contract, with local-level depth and object-level null."""
from __future__ import annotations

import math
import numpy as np
from common import HERE, read
from forecast import predict
from depth_score import log_t4, _logaddexp
from merge_split_manager import choice_mapping, velocity

CFG = read(HERE / 'CONFIG.json')
ROLES = ('A', 'B')
MODES = ('GEOMETRY', 'RAW_DEPTH', 'RESTORED_DEPTH', 'DEPTH_ZERO', 'DEPTH_PERMUTE')


def log_t4_2d(point, mean, shape):
    """Normalized multivariate t, df=4; shape is covariance / 2."""
    delta = np.asarray(point, float) - np.asarray(mean, float)
    matrix = np.asarray(shape, float)
    sign, determinant = np.linalg.slogdet(matrix)
    assert matrix.shape == (2, 2) and sign > 0
    distance = float(delta @ np.linalg.solve(matrix, delta))
    return (math.lgamma(3.) - math.lgamma(2.) - math.log(4. * math.pi)
            - .5 * float(determinant) - 3. * math.log1p(distance / 4.))


def _version(item):
    return [item.get(k) for k in ('source', 'source_generation', 'public_id', 'public_epoch')]


def _fact(item, segment):
    return dict(fact_id=f"{segment}/F{item['frame']}/n:{item['source']}/geometry",
                frame=item['frame'], time=item['time'], source=item['source'],
                version=_version(item), center_px=list(item['center']), bbox=list(item['bbox']))


def _fragment(history, cutoff, query):
    """Use the existing last clean fragment; never join through risk/version gaps."""
    past = [p for p in history if p['frame'] <= cutoff and p['time'] < query][-30:]
    tail = []
    for p in reversed(past):
        if (p.get('observation_class', 'SOURCE_OBSERVATION') not in
                ('SOURCE_OBSERVATION', 'RESTORED_POST') or p.get('neighbors') or
                p.get('area', 64) < 64):
            break
        if tail and (tail[-1]['frame'] != p['frame'] + 1 or
                     tail[-1]['time'] <= p['time'] or _version(tail[-1]) != _version(p)):
            break
        tail.append(p)
    return list(reversed(tail))


def _mean(histories, role, query):
    """Exactly the old pair-level availability and capped-mean prediction."""
    fits = {r: velocity(histories[r]) for r in ROLES}
    both = all(fits[r]['status'] != 'UNKNOWN' for r in ROLES)
    last = histories[role][-1]
    gap = query - last['time']
    assert gap > 0
    horizon = min(gap, 1.)
    fit = fits[role]
    mean = ([fit['intercept_px'][i] + fit['px_per_second'][i] *
             (last['time'] + horizon - fit['time_origin']) for i in (0, 1)]
            if both else list(last['center']))
    return mean, both, gap, horizon, fits


def _geometry_forecast(histories, role, query, segment):
    history = histories[role]
    if not history:
        return dict(available=False, reason='NO_CLEAN_PRE_HISTORY', mu_px=None,
                    shape_px2=None, samples=0, pre_facts=[], calibration=dict(residual_count=0))
    mean, both, gap, horizon, fits = _mean(histories, role, query)
    residuals = []
    other = 'B' if role == 'A' else 'A'
    for index, target in enumerate(history[1:], 1):
        own = history[:index][-10:]
        previous_other = [p for p in histories[other] if
                          p['frame'] < target['frame'] and p['time'] < target['time']][-10:]
        prefixes = {role: own, other: previous_other}
        estimate, available, _, cap, _ = _mean(prefixes, role, target['time'])
        residual = [target['center'][i] - estimate[i] for i in (0, 1)]
        residuals.append(dict(target=_fact(target, segment),
            predictor_facts={r: [_fact(p, segment) for p in prefixes[r]] for r in ROLES},
            predicted_center_px=estimate, residual_px=residual,
            mean_mode='OLS_LINEAR_EXTRAPOLATION' if available else 'LAST_MEASURED_POSITION_ONLY',
            both_pre_velocity_available=available, capped_mean_gap_seconds=cap))
    if len(residuals) >= CFG['geometry_residual_min']:
        errors = np.asarray([r['residual_px'] for r in residuals], float)
        moment = errors.T @ errors / len(errors)
        shrink = CFG['geometry_covariance_shrinkage']
        covariance = ((1. - shrink) * moment + shrink * np.diag(np.diag(moment)) +
                      CFG['geometry_covariance_floor_px2'] * np.eye(2))
        calibration = dict(method='UNCENTERED_NEXT_POINT_RESIDUAL_SECOND_MOMENT',
                           second_moment_px2=moment.tolist(), shrinkage=shrink,
                           floor_px2=CFG['geometry_covariance_floor_px2'])
    else:
        box = history[-1]['bbox']
        sigma = max(CFG['geometry_fallback_sigma_px'], CFG['geometry_fallback_bbox_fraction'] *
                    math.hypot(box[2] - box[0], box[3] - box[1]))
        covariance = sigma * sigma * np.eye(2)
        calibration = dict(method='TOO_FEW_RESIDUALS_ISOTROPIC_BBOX', sigma_px=sigma)
    # Same latest <=10 window as old velocity; cap only the prediction mean.
    prediction_window = history[-10:]
    span = prediction_window[-1]['time'] - prediction_window[0]['time']
    time_scale = max(span, 1. / 30.)
    growth = 1. + (gap / time_scale) ** 2
    inflated = covariance * growth
    calibration.update(residual_count=len(residuals), residuals=residuals,
                       residuals_are_accuracy_proxy=True, physical_accuracy_calibrated=False)
    return dict(available=True, mu_px=mean, shape_px2=(inflated / 2.).tolist(),
        covariance_px2=covariance.tolist(), inflated_covariance_px2=inflated.tolist(),
        growth_factor=growth, actual_gap_seconds=gap, real_pre_span_seconds=span,
        real_pre_span_definition='LATEST_AT_MOST_TEN_PREDICTOR_OBSERVATIONS',
        time_scale_seconds=time_scale, capped_mean_gap_seconds=horizon,
        mean_mode='OLS_LINEAR_EXTRAPOLATION' if both else 'LAST_MEASURED_POSITION_ONLY',
        both_pre_velocity_available=both, velocity_fits=fits,
        samples=len(history), pre_facts=[_fact(p, segment) for p in history],
        calibration=calibration, post_velocity_status='UNKNOWN_AT_Q')


def _finite(value):
    return value is not None and math.isfinite(value)


def _measurement_ok(measurement):
    core = measurement['core']
    return bool(measurement['core_usable'] and _finite(core['median']) and core['median'] > 0
                and _finite(core['mad']) and core['mad'] >= 0)


def _depth_background(measurements, full):
    """One equal-weight component per current qualified observation, including query."""
    components=[]
    for native,measurement in sorted(measurements.items(),key=lambda pair:int(pair[0])):
        if not _measurement_ok(measurement):
            continue
        core=measurement['core']
        sigma=max(CFG['raw_scale_floor_mm'],1.4826*core['mad'])
        components.append(dict(source=int(native),fact_id=measurement['fact_id'],
            measurement_source=measurement.get('source'),cohort=measurement.get('cohort','RAW'),
            median_mm=core['median'],mad_mm=core['mad'],sigma_mm=sigma,
            base_scale_mm=math.hypot(sigma,CFG['depth_background_component_floor_mm'])))
    count=len(components)
    for component in components:
        component['weight']=1./count
    result=dict(component_count=count,min_components=CFG['depth_background_min_components'],
        components=components,query_included=True,leave_query_out=False,
        query_specific_logdensity={},physical_surface_identity='UNKNOWN',
        interpretation='CURRENT_OBSERVATION_FITTED_NORMALIZED_PLUGIN_CONTRAST_NOT_CALIBRATED_BAYES_POSTERIOR')
    if count>=CFG['depth_background_min_components']:
        return dict(result,method='EQUAL_CURRENT_QUALIFIED_OBJECT_T4_KDE',
                    reason='ALL_CURRENT_CORE_USABLE_FINITE_OBJECTS_ONE_COMPONENT_EACH')
    full_ok=full['n']>0 and _finite(full['median']) and _finite(full['mad']) and full['mad']>=0
    if full_ok:
        return dict(result,method='LEGACY_WHOLE_FRAME_T4_FALLBACK',
            reason='TOO_FEW_OBJECT_COMPONENTS_USE_ORIGINAL_WHOLE_FRAME_NULL',
            mu_mm=full['median'],scale_mm=max(60.,1.4826*full['mad']))
    return dict(result,method='NO_USABLE_DEPTH_BACKGROUND',
                reason='TOO_FEW_OBJECT_COMPONENTS_AND_NO_VALID_WHOLE_FRAME_NULL')


def _background_logdensity(background, observation, query_sigma):
    if background['method']=='EQUAL_CURRENT_QUALIFIED_OBJECT_T4_KDE':
        terms=[log_t4(observation,c['median_mm'],math.hypot(c['base_scale_mm'],query_sigma))
               for c in background['components']]
        total=terms[0]
        for term in terms[1:]:total=_logaddexp(total,term)
        return total-math.log(len(terms))
    return log_t4(observation,background['mu_mm'],background['scale_mm'])


def choose(episode, frozen_depth, measurements, full, baseline_mapping, mode, segment):
    """Score distinct physical mappings; insufficient odds always retain lawful H0."""
    assert mode in MODES and CFG['student_df'] == 4
    sources = list(episode['post_roles'])
    assert len(sources) == 2 and len(set(sources)) == 2
    posts = {n: episode['post_roles'][n][0] for n in sources}
    assert all(p['frame'] == episode['q'] for p in posts.values())
    query = posts[sources[0]]['time']
    assert all(p['time'] == query for p in posts.values())
    baseline = {n: baseline_mapping[n] for n in sources}
    assert len(set(baseline.values())) == 2
    cutoff = episode.get('suspect_frame', episode['q']) - 1
    histories = {r: _fragment(episode['pre'].get(r, []), cutoff, query) for r in ROLES}
    geometry = {r: _geometry_forecast(histories, r, query, segment) for r in ROLES}
    geometry_background = -math.log(CFG['geometry_background_area_px'])
    signal = CFG['signal_fraction']
    log_signal_weight, log_background_weight = math.log(signal), math.log(1. - signal)

    enabled = mode not in ('GEOMETRY', 'DEPTH_ZERO')
    assignment, forecasts, background = {}, {}, None
    post_ok = False
    if enabled:
        assigned = dict(zip(sources, reversed(sources))) if mode == 'DEPTH_PERMUTE' else dict(zip(sources, sources))
        for source in sources:
            measurement = measurements[assigned[source]]
            original = measurements[source]
            assignment[str(source)] = dict(observation_post_source=source,
                assigned_depth_source=assigned[source], measurement_fact_id=measurement['fact_id'],
                original_post_measurement_fact_id=original['fact_id'],
                cohort=measurement.get('cohort', 'RAW'), observation_mm=measurement['core']['median'],
                observation_mad_mm=measurement['core']['mad'], core_usable=bool(measurement['core_usable']),
                original_cohort=original.get('cohort', 'RAW'),
                actual_state_source=source, actual_state_fact_id=original['fact_id'])
        post_ok = all(_measurement_ok(measurements[n]) for n in sources)
        background = _depth_background(measurements,full)
        if background['method']=='NO_USABLE_DEPTH_BACKGROUND':
            background=None
        for role in ROLES:
            frozen = dict(frozen_depth.get(role, dict(samples=[])))
            depth_cutoff = min(cutoff, frozen.get('cutoff_frame', cutoff))
            frozen['samples'] = [p for p in frozen['samples'] if p['frame'] <= depth_cutoff and p['time'] < query]
            forecasts[role] = dict(predict(frozen, query), version_key=frozen.get('key'),
                                   cutoff_frame=depth_cutoff, source=frozen.get('source'),
                                   public=frozen.get('public'))
    else:
        # ZERO deliberately never inspects depth/state, ensuring exact J0 arithmetic.
        forecasts = {r: dict(status='DEPTH_MODALITY_DISABLED', mu_mm=None, scale_mm=None,
                             samples=0, sample_fact_ids=[]) for r in ROLES}

    edges, background_edges = {}, {}
    for source in sources:
        query_sigma=(max(CFG['raw_scale_floor_mm'],1.4826*assignment[str(source)]['observation_mad_mm'])
                     if enabled and post_ok else None)
        depth_bg=(_background_logdensity(background,assignment[str(source)]['observation_mm'],query_sigma)
                  if enabled and post_ok and background else 0.)
        if enabled and post_ok and background:
            background['query_specific_logdensity'][str(source)]=dict(
                observation_mm=assignment[str(source)]['observation_mm'],query_sigma_mm=query_sigma,
                assigned_depth_source=assignment[str(source)]['assigned_depth_source'],log_density=depth_bg,
                all_candidates_share_this_source_density=True)
        background_edges[str(source)] = dict(role=None, source=source, associated=False,
            geometry=dict(used=False, raw_log_density=None, background_log_density=geometry_background,
                          mixture_log_density=geometry_background, log_lr=0.),
            depth=dict(used=False, raw_log_density=None, background_log_density=depth_bg,
                       mixture_log_density=depth_bg, log_lr=0., missing_model='COMMON_BACKGROUND'))
        for role in ROLES:
            geo = geometry[role]
            raw_geo = log_t4_2d(posts[source]['center'], geo['mu_px'], geo['shape_px2']) if geo['available'] else None
            geo_lr = (_logaddexp(log_signal_weight + raw_geo - geometry_background, log_background_weight)
                      if raw_geo is not None else 0.)
            forecast = forecasts[role]
            depth_used = bool(enabled and post_ok and background and _finite(forecast['mu_mm']) and
                              _finite(forecast['scale_mm']) and forecast['scale_mm'] > 0)
            raw_depth, depth_lr, observation_scale, combined_scale = None, 0., None, None
            if depth_used:
                observed = assignment[str(source)]
                observation_scale = max(15., 1.4826 * observed['observation_mad_mm'])
                combined_scale = math.hypot(forecast['scale_mm'], observation_scale)
                raw_depth = log_t4(observed['observation_mm'], forecast['mu_mm'], combined_scale)
                depth_lr = _logaddexp(log_signal_weight + raw_depth - depth_bg, log_background_weight)
            edges[f'{role}:{source}'] = dict(role=role, source=source, associated=True,
                geometry=dict(used=geo['available'], observed_center_px=list(posts[source]['center']),
                    predicted_center_px=geo['mu_px'], raw_log_density=raw_geo,
                    background_log_density=geometry_background,
                    mixture_log_density=geometry_background + geo_lr, log_lr=geo_lr,
                    shape_px2=geo['shape_px2']),
                depth=dict(used=depth_used, raw_log_density=raw_depth, background_log_density=depth_bg,
                    mixture_log_density=depth_bg + depth_lr, log_lr=depth_lr,
                    observation_scale_mm=observation_scale, combined_scale_mm=combined_scale,
                    measurement_fact_id=assignment.get(str(source), {}).get('measurement_fact_id'),
                    assigned_depth_source=assignment.get(str(source), {}).get('assigned_depth_source'),
                    missing_model='COMMON_UNINFORMATIVE_ROLE_OR_PAIRED_MODALITY'))

    maps = {'H0': baseline}
    public_ids = episode.get('public_ids', [])
    if len(public_ids) == 2 and len(set(public_ids)) == 2:
        maps.update({label: choice_mapping(episode, label) for label in ('H1', 'H2')})
    hypotheses, candidates, canonical = {}, {}, {}
    for label, mapping in maps.items():
        key = tuple((n, mapping[n]) for n in sources)
        representative = canonical.setdefault(key, label)
        hypotheses[label] = dict(mapping=mapping, canonical=representative)
        if representative in candidates:
            candidates[representative]['labels'].append(label)
        else:
            candidates[representative] = dict(mapping=mapping, labels=[label])
    prior = -math.log(len(candidates))
    target_roles = dict(zip(public_ids, ROLES))
    for label, candidate in candidates.items():
        pairs = []
        for source in sources:
            role = target_roles.get(candidate['mapping'][source])
            pairs.append(edges[f'{role}:{source}'] if role in ROLES else background_edges[str(source)])
        geometry_lr = sum(p['geometry']['log_lr'] for p in pairs)
        depth_lr = sum(p['depth']['log_lr'] for p in pairs)
        geometry_ll = sum(p['geometry']['mixture_log_density'] for p in pairs)
        depth_ll = sum(p['depth']['mixture_log_density'] for p in pairs)
        candidate.update(pairs=pairs, log_prior=prior, geometry_log_lr=geometry_lr,
            depth_log_lr=depth_lr, geometry_log_likelihood=geometry_ll,
            depth_log_likelihood=depth_ll, log_joint_density=prior + geometry_ll + depth_ll,
            log_score=prior + geometry_lr + depth_lr)
    ranked = sorted(candidates, key=lambda label: (-candidates[label]['log_score'], label != 'H0', label))
    best = ranked[0]
    runner = ranked[1] if len(ranked) > 1 else None
    maximum = candidates[best]['log_score']
    total = sum(math.exp(c['log_score'] - maximum) for c in candidates.values())
    for candidate in candidates.values():
        candidate['posterior'] = math.exp(candidate['log_score'] - maximum) / total
    margin = maximum - candidates[runner]['log_score'] if runner else None
    threshold = math.log(CFG['minimum_joint_odds'])
    accepted = bool(runner and best != 'H0' and margin >= threshold)
    choice = best if accepted else 'H0'
    return choice, dict(reason='JOINT_ODDS_ACCEPTED' if accepted else
        'ONLY_LAWFUL_PHYSICAL_MAPPING' if runner is None else 'H0_BEST' if best == 'H0' else 'INSUFFICIENT_JOINT_ODDS',
        accepted=accepted, selected_mapping=candidates[choice]['mapping'], baseline_mapping=baseline,
        hypotheses=hypotheses, candidates=candidates, edges=edges,
        background_edges=background_edges, geometry_forecasts=geometry, depth_forecasts=forecasts,
        depth_assignment=assignment, background=dict(geometry_area_px=CFG['geometry_background_area_px'],
            geometry_log_density=geometry_background, depth=background),
        best=best, runner_up=runner, margin=margin, minimum_log_odds=threshold,
        used_edges=sum(e['depth']['used'] for e in edges.values()), post_pair_usable=post_ok,
        depth_enabled=enabled, unique_physical_candidates=len(candidates),
        joint_independence='CONDITIONAL_GEOMETRY_DEPTH_FACTORIZATION_ASSUMPTION',
        signal_fraction=signal, evidence_max_frame=episode['q'],
        geometry_pre_cutoff_frame=cutoff, physical_identity='UNKNOWN_UNTIL_POSTSEAL_REFERENCE_AUDIT')
