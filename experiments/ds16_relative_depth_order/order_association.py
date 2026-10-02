"""One causal paired-depth order factor, replacing absolute group depth scores."""
from __future__ import annotations

import importlib.util
import math
import statistics

from common import ROOT, HERE, read

CFG = read(HERE / 'CONFIG.json')
ROLES = ('A', 'B')
MODES = ('ORDER_OFF', 'ORDER', 'ORDER_PERMUTE')
_spec = importlib.util.spec_from_file_location(
    'ds16_isolated_geometry', ROOT / 'experiments/ds9_joint_h0_depth/association.py')
_geometry = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_geometry)


def t4_cdf(value):
    """Exact Student-t df=4 CDF; no new numerical dependency."""
    u = value / math.hypot(value, 2.)
    return max(0., min(1., .5 + .75 * u - .25 * u ** 3))


def _finite(value):
    return isinstance(value, (int, float)) and math.isfinite(value)


def _fact_matches(fact, segment, frame, native):
    return isinstance(fact, str) and fact.startswith(f'{segment}/F{frame}/n:{native}/')


def _quality(measurement):
    core = measurement.get('core') or {}
    return bool(measurement.get('core_usable') and
        all(_finite(core.get(k)) for k in ('median', 'mad', 'n', 'valid_fraction')) and
        core['median'] > 0 and core['mad'] >= 0 and
        core['n'] >= CFG['min_points'] and CFG['min_fraction'] <= core['valid_fraction'] <= 1. and
        max(CFG['raw_scale_floor_mm'], 1.4826 * core['mad']) <= CFG['max_raw_scale_mm'])


def evidence(episode, frozen_depth, measurements, mode, segment):
    """Bind latest clean paired observations; never infer hidden individual depth."""
    assert mode in MODES
    sources = list(episode['post_roles'])
    query = episode['post_roles'][sources[0]][0]['time']
    cutoff = episode.get('suspect_frame', episode['q']) - 1
    base = dict(status='UNKNOWN', eligible=False, mode=mode, applied=mode != 'ORDER_OFF',
        query_frame=episode['q'], query_time=query, pre_cutoff_frame=cutoff,
        representative='EXCLUSIVE_CORE_MEDIAN_DEPTH_ORDER_NOT_LOCAL_OCCLUSION_TOPOLOGY',
        physical_identity='UNKNOWN_UNTIL_POSTSEAL_REFERENCE_AUDIT',
        confidence_interpretation='UNCALIBRATED_NOISE_AND_CONTINUITY_PROXY',
        invariance_scope='THIS_AUTOMATIC_TWO_MEMBER_EPISODE_ONLY',
        assumption='PRE_ORDER_PERSISTS_UNLESS_EVIDENCE_IS_UNKNOWN_OR_CONTRADICTORY',
        missing_policy='COMMON_NEUTRAL_FACTOR_AND_OWN_BRANCH_H0',
        hidden_individual_depth='NOT_OBSERVED_NOT_IMPUTED', pre_pairs=[], post_bindings={})

    def unknown(reason):
        return dict(base, reason=reason)

    if len(sources) != 2 or len(set(sources)) != 2 or len(episode.get('public_ids', [])) != 2:
        return unknown('NOT_TWO_DISTINCT_MEMBERS_AND_POST_SOURCES')
    if not _finite(query) or len(set(episode['public_ids'])) != 2:
        return unknown('INVALID_QUERY_OR_PROTECTED_IDENTITIES')
    samples = {}
    for role, native, public in zip(ROLES, episode['member_sources'], episode['public_ids']):
        frozen = frozen_depth.get(role, {})
        key = frozen.get('key')
        history = frozen.get('samples', [])[-CFG['history_frames']:]
        if (not key or len(key) != 5 or key[3] != public or
                frozen.get('public') != public or frozen.get('source') != native or not history):
            return unknown('MISSING_OR_MISMATCHED_PRE_VERSION')
        reference_cutoff = min(cutoff, frozen.get('cutoff_frame', cutoff))
        geometry = {p['frame']: p for p in episode['pre'].get(role, [])}
        bound = []
        for item in history:
            frame = item.get('frame')
            point = geometry.get(frame)
            if (not point or not all(_finite(item.get(k)) for k in ('time', 'z_mm', 'mad_mm')) or
                    frame > reference_cutoff or item['time'] >= query or item['z_mm'] <= 0 or
                    item['mad_mm'] < 0 or max(CFG['raw_scale_floor_mm'], 1.4826 * item['mad_mm']) > CFG['max_raw_scale_mm'] or
                    list(item.get('version_key', key)) != list(key) or
                    item.get('observation_class', 'SOURCE_OBSERVATION') not in ('SOURCE_OBSERVATION', 'RESTORED_POST') or
                    point.get('observation_class', 'SOURCE_OBSERVATION') not in ('SOURCE_OBSERVATION', 'RESTORED_POST') or
                    point.get('neighbors') or point.get('area', 0) < 64 or
                    point.get('source') != native or point.get('public_id') != public or
                    point.get('source_generation') != key[2] or point.get('public_epoch') != key[4] or
                    point.get('time') != item['time'] or
                    item.get('source_native') != native or not item.get('core_usable') or
                    not all(_finite(item.get(k)) for k in ('n', 'valid_fraction')) or
                    item['n'] < CFG['min_points'] or not CFG['min_fraction'] <= item['valid_fraction'] <= 1. or
                    not _fact_matches(item.get('fact_id'), segment, frame, native)):
                return unknown('INVALID_CAUSAL_CLEAN_PRE_SOURCE_BINDING')
            bound.append(dict(item, version_key=list(key), native=native, public=public,
                sigma_mm=max(CFG['raw_scale_floor_mm'], 1.4826 * item['mad_mm']),
                quality_source='ACTUAL_CURRENT_MEASUREMENT_RECORDED_WITH_SOURCE_FRAME_VERSION',
                measured_n=item['n'], measured_valid_fraction=item['valid_fraction']))
        if any(b['frame'] != a['frame'] + 1 or b['time'] <= a['time']
               for a, b in zip(bound, bound[1:])):
            return unknown('PRE_GAP_OR_NONMONOTONIC_TIME')
        samples[role] = {p['frame']: p for p in bound}

    frames = sorted(set(samples['A']) & set(samples['B']))[-CFG['fit_observations']:]
    if not frames:
        return unknown('NO_SAME_FRAME_PRE_PAIR')
    for frame in frames:
        a, b = samples['A'][frame], samples['B'][frame]
        if a['time'] != b['time']:
            return unknown('PRE_PAIR_TIME_MISMATCH')
        pair_scale = math.hypot(a['sigma_mm'], b['sigma_mm'])
        delta = b['z_mm'] - a['z_mm']
        base['pre_pairs'].append(dict(frame=frame, time=a['time'], A=a, B=b,
            delta_B_minus_A_mm=delta, pair_scale_mm=pair_scale,
            p_A_nearer=t4_cdf(delta / pair_scale)))
    pairs = base['pre_pairs']
    if any(b['frame'] != a['frame'] + 1 or b['time'] <= a['time']
           for a, b in zip(pairs, pairs[1:])):
        return unknown('PAIRED_PRE_FRAGMENT_GAP')
    odds = CFG['minimum_joint_odds']
    high, low = odds / (1. + odds), 1. / (1. + odds)
    if (any(p['p_A_nearer'] >= high for p in pairs) and
            any(p['p_A_nearer'] <= low for p in pairs)):
        return unknown('CONFIDENT_PRE_ORDER_REVERSAL')

    last = pairs[-1]
    gap = query - last['time']
    if not 0 < gap <= CFG['birth_max_gap_seconds']:
        return unknown('PRE_REFERENCE_EXPIRED_OR_NONCAUSAL')
    intervals = [b['time'] - a['time'] for a, b in zip(pairs, pairs[1:])]
    acquired = [frozen_depth[r].get('acquired_interval_seconds') for r in ROLES]
    acquired = [x for x in acquired if _finite(x) and x > 0]
    nominal = max(acquired) if acquired else 1. / 30.
    time_scale = max(last['time'] - pairs[0]['time'], statistics.median(intervals)) if intervals else nominal
    pair_floor2 = 2. * CFG['raw_scale_floor_mm'] ** 2
    original_process = pair_floor2 * (1. + (gap / time_scale) ** 2)
    increments = []
    for a, b in zip(pairs, pairs[1:]):
        dt = b['time'] - a['time']
        dz = b['delta_B_minus_A_mm'] - a['delta_B_minus_A_mm']
        excess = max(0., dz * dz - a['pair_scale_mm'] ** 2 - b['pair_scale_mm'] ** 2)
        increments.append(dict(first_frame=a['frame'], second_frame=b['frame'],
            first_fact_ids=[a[r]['fact_id'] for r in ROLES],
            second_fact_ids=[b[r]['fact_id'] for r in ROLES], dt_seconds=dt,
            delta_increment_mm=dz, excess_variance_mm2=excess,
            diffusion_rate_mm2_per_second=excess / dt))
    diffusion = (statistics.median(p['diffusion_rate_mm2_per_second'] for p in increments)
                 if len(increments) >= CFG['depth_diffusion_min_increments'] else None)
    process = max(original_process, diffusion * gap) if diffusion is not None else original_process
    propagated_scale = math.sqrt(last['pair_scale_mm'] ** 2 + process)
    p_pre = t4_cdf(last['delta_B_minus_A_mm'] / propagated_scale)

    for native in sources:
        post = episode['post_roles'][native]
        measurement = measurements.get(native, {})
        if (len(post) != 1 or post[0]['frame'] != episode['q'] or post[0]['time'] != query or
                post[0].get('source') != native or not _quality(measurement) or
                not _fact_matches(measurement.get('fact_id'), segment, episode['q'], native)):
            return unknown('INVALID_OR_MISSING_CURRENT_PAIRED_DEPTH')
    assigned = dict(zip(sources, sources[::-1] if mode == 'ORDER_PERMUTE' else sources))
    for native in sources:
        measurement = measurements[native]
        source = assigned[native]
        scored = measurements[source]
        base['post_bindings'][str(native)] = dict(observation_source=native,
            actual_state_source=native, actual_state_fact_id=measurement['fact_id'],
            assigned_depth_source=source, assigned_measurement_fact_id=scored['fact_id'],
            core=dict(scored['core']), actual_core=dict(measurement['core']),
            scoring_permutation_only=mode == 'ORDER_PERMUTE')
    return dict(base, status='MEASURED_PAIRED_ORDER', eligible=True,
        reason='VALID_SOFT_ORDER_EVIDENCE', p_A_nearer_at_q=p_pre,
        last_delta_B_minus_A_mm=last['delta_B_minus_A_mm'], pre_scale_at_q_mm=propagated_scale,
        calibration=dict(real_gap_seconds=gap, real_pre_span_seconds=last['time'] - pairs[0]['time'],
            time_scale_seconds=time_scale, single_pair_time_source='OBSERVED_ACQUISITION_INTERVAL' if acquired else 'NOMINAL_1_OVER_30_FALLBACK',
            original_process_variance_mm2=original_process, selected_process_variance_mm2=process,
            diffusion_rate_mm2_per_second=diffusion, increments=increments,
            temporal_evidence='LAST_SAME_FRAME_MEASURED_DELTA; NO_FRAME_VOTE_MULTIPLICATION',
            actual_mean='LAST_MEASURED_RELATIVE_DEPTH; NO_HIDDEN_DEPTH_OR_INVARIANCE_PROOF'))


def choose(episode, frozen_depth, measurements, full, baseline_mapping, mode, segment):
    """Same candidate geometry and transactions, with one bounded ordinal factor."""
    assert mode in MODES
    _, detail = _geometry.choose(episode, frozen_depth, measurements, full,
                                 baseline_mapping, 'GEOMETRY', segment)
    order = evidence(episode, frozen_depth, measurements, mode, segment)
    signal = CFG['signal_fraction']
    public = dict(zip(ROLES, episode['public_ids']))
    for candidate in detail['candidates'].values():
        assigned = {role: next((n for n, k in candidate['mapping'].items() if k == public[role]), None)
                    for role in ROLES}
        ordinal = dict(used=False, log_lr=0., p_same_order=None,
            reason='COMMON_UNINFORMATIVE_NO_COMPLETE_OLD_PAIR', assigned_sources=assigned)
        if order['eligible'] and all(n is not None for n in assigned.values()):
            a, b = [order['post_bindings'][str(assigned[r])] for r in ROLES]
            delta = b['core']['median'] - a['core']['median']
            scale = math.hypot(*(max(CFG['raw_scale_floor_mm'], 1.4826 * p['core']['mad']) for p in (a, b)))
            p_post = t4_cdf(delta / scale)
            p_pre = order['p_A_nearer_at_q']
            compatibility = p_pre * p_post + (1. - p_pre) * (1. - p_post)
            mixture = (1. - signal) / 2. + signal * compatibility
            ordinal.update(used=mode != 'ORDER_OFF', log_lr=math.log(mixture / .5) if mode != 'ORDER_OFF' else 0.,
                p_same_order=compatibility, p_A_nearer_post=p_post, post_delta_B_minus_A_mm=delta,
                post_pair_scale_mm=scale, mixture_likelihood=mixture,
                measurement_fact_ids=[p['assigned_measurement_fact_id'] for p in (a, b)],
                reason='ORDINAL_FACTOR_DISABLED' if mode == 'ORDER_OFF' else 'ONE_PAIRED_ORDER_FACTOR')
        elif not order['eligible']:
            ordinal['reason'] = order['reason']
        candidate.update(order=ordinal, order_log_lr=ordinal['log_lr'], depth_log_lr=0.,
            log_score=candidate['log_prior'] + candidate['geometry_log_lr'] + ordinal['log_lr'])
        candidate['log_joint_density'] = (candidate['log_prior'] +
            candidate['geometry_log_likelihood'] + ordinal['log_lr'])
    ranked = sorted(detail['candidates'], key=lambda k: (-detail['candidates'][k]['log_score'], k != 'H0', k))
    best = ranked[0]
    runner = ranked[1] if len(ranked) > 1 else None
    maximum = detail['candidates'][best]['log_score']
    total = sum(math.exp(c['log_score'] - maximum) for c in detail['candidates'].values())
    for candidate in detail['candidates'].values():
        candidate['posterior'] = math.exp(candidate['log_score'] - maximum) / total
    margin = maximum - detail['candidates'][runner]['log_score'] if runner else None
    threshold = math.log(CFG['minimum_joint_odds'])
    selected_lr = detail['candidates'][best]['order_log_lr']
    baseline_lr = detail['candidates']['H0']['order_log_lr']
    admitted = bool(order['eligible'] and runner and best != 'H0' and margin >= threshold)
    if mode != 'ORDER_OFF':
        admitted = admitted and selected_lr > 0. and selected_lr > baseline_lr
    choice = best if admitted else 'H0'
    reason = (order['reason'] if not order['eligible'] else
        'ORDINAL_OR_GEOMETRY_ODDS_ACCEPTED' if admitted else 'H0_BEST' if best == 'H0' else
        'INSUFFICIENT_JOINT_ODDS' if not runner or margin < threshold else
        'NO_POSITIVE_ORDINAL_SUPPORT_OR_PREFERENCE')
    order.update(best_ordinal_log_lr=selected_lr, h0_ordinal_log_lr=baseline_lr,
        positive_order_admission_required=mode != 'ORDER_OFF', candidates_ranked=ranked)
    detail.update(reason=reason, accepted=admitted, selected_mapping=detail['candidates'][choice]['mapping'],
        best=best, runner_up=runner, margin=margin, minimum_log_odds=threshold,
        order_evidence=order, depth_enabled=False, order_enabled=mode != 'ORDER_OFF',
        post_pair_usable=order['eligible'], used_edges=0,
        joint_independence='GEOMETRY_AND_ONE_ORDINAL_FACTOR_ASSUMPTION; NO_ABSOLUTE_DEPTH_FACTOR')
    return choice, detail
