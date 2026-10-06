"""Versioned short endpoints and joint identity explanations; no state or pixel writes."""
from common import *
import copy
import math
import numpy as np

DEPTH = module('ds34_unchanged_ds31_depth', ROOT / 'experiments/ds31_persistent_identity_depth/depth.py')
ENDPOINT = module('ds34_unchanged_ds33_endpoint', ROOT / 'experiments/ds33_rgbd_fixed_lag/evidence.py')


def _native(sample):
    return sample['native'] if 'native' in sample else sample['source']


def _box(sample):
    return sample['box'] if 'box' in sample else sample['bbox']


def _center(sample):
    box = _box(sample)
    return [(box[0] + box[2]) / 2., (box[1] + box[3]) / 2.]


def _version(sample, pre):
    if pre: return sample.get('version')
    return [_native(sample), sample.get('source_generation'), sample.get('public_epoch')]


def _segment(samples, pre):
    """Never remove bad observations and join the surviving ends."""
    if not samples: return 'NO_PRE_HISTORY' if pre else 'NO_POST_HISTORY'
    if any(not isinstance(s.get('frame'), int) or not isinstance(s.get('time'), (int, float))
           or not math.isfinite(s['time']) for s in samples): return 'INVALID_FRAME_OR_TIME'
    if any(b['frame'] != a['frame'] + 1 or b['time'] <= a['time']
           for a, b in zip(samples, samples[1:])): return 'DISCONTINUOUS_ENDPOINT'
    versions = [_version(s, pre) for s in samples]
    if (any(v is None for v in versions) or any(v != versions[-1] for v in versions)
            or not pre and versions[-1][1] is None): return 'ENDPOINT_SOURCE_VERSION_CHANGED_OR_UNKNOWN'
    if any(_native(s) != _native(samples[-1]) for s in samples): return 'ENDPOINT_NATIVE_CHANGED'
    return None


def fit(samples):
    """Actual-time OLS, latest ten contiguous measurements, with residuals."""
    selected = list(samples)[-CFG['fit_observations']:]
    result = dict(status='UNKNOWN', model='OLS_INTERCEPT_LINEAR_REAL_TIME', samples=len(selected),
        sample_frames=[s['frame'] for s in selected], sample_times=[s['time'] for s in selected],
        velocity_px_s=None, center_at_last_time_px=None, residual_rms_px=None,
        measured_velocity_is_unknown=True, uncertainty='IN_SAMPLE_RESIDUAL_NOT_CALIBRATED_FORECAST')
    if len(selected) < 3: return dict(result, reason='FEWER_THAN_THREE_CONTINUOUS_OBSERVATIONS')
    times = np.asarray([s['time'] for s in selected], 'f8')
    values = np.asarray([_center(s) for s in selected], 'f8')
    if not np.isfinite(times).all() or not np.isfinite(values).all() or np.any(np.diff(times) <= 0):
        return dict(result, reason='INVALID_OBSERVATION_TIME_OR_POSITION')
    relative = times - times[-1]
    design = np.column_stack((np.ones(len(times)), relative))
    beta, _, rank, _ = np.linalg.lstsq(design, values, rcond=None)
    if rank != 2: return dict(result, reason='DEGENERATE_REAL_TIME_FIT')
    residual = values - design @ beta
    return dict(result, status='AVAILABLE_MEASURED_OLS', reason=None,
        velocity_px_s=beta[1].tolist(), center_at_last_time_px=beta[0].tolist(),
        time_origin=float(times[-1]), span_seconds=float(times[-1]-times[0]),
        residual_px=residual.tolist(), residual_rms_px_by_axis=np.sqrt(np.mean(residual**2, axis=0)).tolist(),
        residual_rms_px=float(np.sqrt(np.mean(np.sum(residual**2, axis=1)))),
        measured_velocity_is_unknown=False)


def _bind(sample, packet, clean):
    row = packet['row']; n = _native(sample)
    assert (sample['frame'], sample['time']) == (row['frame'], row['time']), 'Endpoint from another time'
    observations = [o for o in row['observations'] if o['id'] == n]
    assert len(observations) == 1, 'Endpoint source absent or duplicated'
    actual = observations[0]
    assert list(_box(sample)) == list(actual['box']) and sample['area'] == actual['area'], 'Changed endpoint geometry'
    if clean: assert not actual.get('neighbors'), 'Risk observation authenticated as clean endpoint'
    assignment = packet.get('assignment')
    if assignment is not None:
        assert (assignment['frame'], assignment['global_frame_id'], assignment['time']) == (
            row['frame'], row['global_frame'], row['time']), 'Wrong endpoint mask source'
    assert n in packet['masks'] and packet['masks'][n].dtype == np.dtype(bool)
    return dict(frame=row['frame'], global_frame=row['global_frame'], time=row['time'], native=n,
        mask=actual['mask'], current_mask_binding=array_hash(packet['masks'][n]),
        source_row_sha256=row_sha(row), assignment_row_sha256=row_sha(assignment) if assignment is not None else None,
        endpoint_version=copy.deepcopy(sample.get('version')),
        source_generation=sample.get('source_generation'), public_epoch=sample.get('public_epoch'),
        observation_is_actual=True, candidate_identity_is_not_certified=True)


def _extract(sample, packet):
    n = _native(sample)
    extracts = packet.get('extracts', {})
    extract = copy.deepcopy(extracts.get(n, extracts.get(str(n))) or {})
    usable = ENDPOINT.endpoint_depth_usable(extract, packet['row'], n)
    extract['usable'] = usable
    return extract, dict(usable=usable, quality=copy.deepcopy(extract.get('quality', {})),
        fact_binding=ENDPOINT.depth_fact_binding(extract))


def _dice(a, b):
    return float(2 * np.count_nonzero(a & b) / max(1, int(a.sum()) + int(b.sum())))


def _pair_contract(pair, previous, current):
    summary = pair.numeric_summary
    assert (summary['previous_frame'], summary['current_frame'], summary['maximum_read_global_frame']) == (
        previous['row']['global_frame'], current['row']['global_frame'], current['row']['global_frame'])
    for role, packet in (('previous', previous), ('current', current)):
        sensor = packet.get('sensor')
        if sensor is not None:
            assert summary[role + '_source_binding'] == sensor['binding'], 'Flow sensor differs from actual endpoint'
    return {key:copy.deepcopy(summary.get(key)) for key in ('schema', 'method', 'actual_DIS_parameters',
        'actual_quality_parameters', 'previous_frame', 'current_frame', 'maximum_read_global_frame',
        'previous_source_binding', 'current_source_binding', 'rgb_status', 'rgb_dt_s', 'depth_status',
        'depth_dt_s', 'depth_unknown_reasons', 'flow_forward', 'flow_backward',
        'forward_reliable', 'backward_reliable', 'physical_surface_identity')}


def _contour(pair, a, b):
    forward, backward = pair.warp_forward(a), pair.warp_backward(b)
    trusted_forward, trusted_backward = pair.warp_forward(a, quality=True), pair.warp_backward(b, quality=True)
    fractions = [int(trusted_forward.sum()) / max(1, int(forward.sum())),
        int(trusted_backward.sum()) / max(1, int(backward.sum()))]
    areas = [int(trusted_forward.sum()), int(trusted_backward.sum())]
    available = bool(pair.numeric_summary.get('rgb_status') == 'AVAILABLE'
        and min(fractions) >= CFG['min_reliable_contour_fraction']
        and min(areas) >= CFG['flow']['min_correspondences'])
    dice = [_dice(forward, b), _dice(backward, a)]
    return dict(available=available, status='AVAILABLE_CONDITIONAL_BIDIRECTIONAL_CONTOUR' if available else 'UNKNOWN',
        reason=None if available else 'INSUFFICIENT_ENDPOINT_FORWARD_BACKWARD_SUPPORT',
        forward_dice=dice[0], backward_dice=dice[1], symmetric_dice=float(np.mean(dice)),
        forward_reliable_fraction=fractions[0], backward_reliable_fraction=fractions[1],
        forward_reliable_area=areas[0], backward_reliable_area=areas[1],
        forward_mask_binding=array_hash(forward), backward_mask_binding=array_hash(backward),
        forward_trusted_binding=array_hash(trusted_forward), backward_trusted_binding=array_hash(trusted_backward),
        propagated_contours_are_hypotheses=True, physical_identity='UNKNOWN',
        no_long_anchor_chain=True, candidate_related_short_endpoint_comparison=True)


def _back_to_q(native, endpoint, q, packets, pair_at):
    """Post-source continuity at q is a reliability diagnostic, never an identity score."""
    mask = packets[endpoint['frame']]['masks'][native].copy(); trusted = mask.copy()
    links = []
    for frame in range(endpoint['frame'], q, -1):
        if frame not in packets or frame-1 not in packets:
            return dict(status='UNKNOWN', reason='MISSING_UNPUBLISHED_RAW_PACKET', links=links)
        old, current = packets[frame-1], packets[frame]
        if native not in old['masks'] or native not in current['masks']:
            return dict(status='UNKNOWN', reason='RAW_SOURCE_BROKEN_BEFORE_Q', links=links)
        pair = pair_at(frame-1, frame)
        if pair is None: return dict(status='UNKNOWN', reason='NO_ACTUAL_MOTION_PROVIDER', links=links)
        binding = _pair_contract(pair, old, current)
        mask = pair.warp_backward(mask); trusted = pair.warp_backward(trusted, quality=True)
        links.append(dict(previous_frame=frame-1, current_frame=frame, pair=binding))
    fraction = int(trusted.sum()) / max(1, int(mask.sum()))
    available = int(trusted.sum()) >= CFG['flow']['min_correspondences'] and fraction >= CFG['min_reliable_contour_fraction']
    return dict(status='AVAILABLE_POST_CONTINUITY_DIAGNOSTIC' if available else 'UNKNOWN',
        reason=None if available else 'INSUFFICIENT_POST_BACKWARD_SUPPORT', q=q, maximum_frame=endpoint['frame'],
        links=links, backprojected_binding=array_hash(mask), trusted_binding=array_hash(trusted),
        reliable_fraction=fraction, q_actual_mask_binding=array_hash(packets[q]['masks'][native]),
        q_actual_dice=_dice(mask, packets[q]['masks'][native]), used_for_identity_score=False,
        candidate_independent=True, propagated_contour_is_hypothesis=True)


def choose(episode, pre, packets, use_depth, motion_provider=None):
    """Choose H1/H2 once from fixed endpoints; DEFER never fabricates identity evidence."""
    roles = ('A', 'B'); sources = list(episode['post_roles']); q = episode['q']
    assert len(sources) == len(set(sources)) == len(episode['public_ids']) == len(set(episode['public_ids'])) == 2
    count = CFG['short_endpoint_frames']
    before = {role:list(pre.get(role, {}).get('samples', []))[-CFG['fit_observations']:] for role in roles}
    confirmed = episode.get('confirmed_post_roles')
    after = {n:list((confirmed if confirmed is not None else episode['post_roles'])[n])[:count] for n in sources}
    base = dict(status='DEFER', choice='DEFER', mapping=None, scores=[],
        pre_frames={role:[s['frame'] for s in values] for role,values in before.items()},
        post_frames={str(n):[s['frame'] for s in values] for n,values in after.items()},
        q=q, causal_max_frame=q, candidate_identity_not_certified_by_post_clean=True,
        no_GT=True, no_pixels_serialized=True, new_model_http=0, cost_usd=0)
    for role, values in before.items():
        reason = _segment(values, True)
        if reason: return dict(base, reason=reason, failed_endpoint=role)
        assert all(s['frame'] < episode.get('suspect_frame', q) for s in values), 'Future or risk point in pre reference'
        reference = pre[role].get('anchor')
        if reference is not None:
            assert reference['canonical_id'] == episode['public_ids'][roles.index(role)]
            assert all(_native(s) == reference['native_id'] and s['frame'] <= reference['frame'] for s in values), 'Pre sample is not from exact actual bank anchor source'
        assert all(s['public'] == episode['public_ids'][roles.index(role)]
            and s['version'][0] == _native(s) and s['version'][2] == s['public'] for s in values), 'Wrong frozen physical reference role'
    for n, values in after.items():
        if len(values) != count: return dict(base, reason='FEWER_THAN_THREE_POST_OBSERVATIONS', failed_endpoint=n)
        assert all(q <= s['frame'] <= q+CFG['lag_frames'] for s in values), 'Future post evidence beyond unpublished deadline'
        reason = _segment(values, False)
        if reason: return dict(base, reason=reason, failed_endpoint=n)
        assert all(_native(s) == n for s in values), 'Post role source was changed'
        if confirmed is not None:
            assert all(s in episode['post_roles'][n] for s in values), 'Confirmed post is not from actual anonymous event history'
        q_samples = [s for s in episode['post_roles'][n] if s['frame'] == q]
        if len(q_samples) != 1 or _version(q_samples[0], False) != _version(values[0], False):
            return dict(base, reason='POST_SOURCE_GENERATION_CHANGED_SINCE_FIRST_SPLIT_Q', failed_endpoint=n)
        if any(f not in packets or n not in packets[f]['masks'] for f in range(q, values[-1]['frame']+1)):
            return dict(base, reason='POST_SOURCE_CONTINUITY_BROKEN_OR_UNAVAILABLE_BEFORE_Q', failed_endpoint=n)
    cutoff = max(s['frame'] for values in after.values() for s in values)
    base['causal_max_frame'] = cutoff
    pre_refs, post_refs, depth_facts = {}, {}, {}
    for key, values in list(before.items())+list(after.items()):
        refs, facts = [], []
        for sample in values:
            assert sample['frame'] in packets, 'Missing actual endpoint packet'
            refs.append(_bind(sample, packets[sample['frame']], True))
            _, detail = _extract(sample, packets[sample['frame']]); facts.append(detail)
        (pre_refs if key in roles else post_refs)[key] = refs
        depth_facts[str(key)] = facts
    pre_fit = {role:fit(values) for role,values in before.items()}
    post_fit = {n:fit(values) for n,values in after.items()}
    motion_common = all(f['status']=='AVAILABLE_MEASURED_OLS' for f in list(pre_fit.values())+list(post_fit.values()))
    cache = {}
    def pair_at(a, b):
        assert a < b <= cutoff, 'Future or reversed pair requested'
        if (a,b) not in cache: cache[a,b] = motion_provider(a,b) if motion_provider else None
        return cache[a,b]
    matrix, all_contours = {}, []
    depth_samples = {}
    for role, values in before.items():
        depth_samples[episode['public_ids'][roles.index(role)]] = []
        for sample in values:
            observed, _ = _extract(sample, packets[sample['frame']])
            depth_samples[episode['public_ids'][roles.index(role)]].append(dict(
                frame=sample['frame'], time=sample['time'], version=copy.deepcopy(sample['version']),
                usable=observed['usable'], z_mm=observed.get('z_mm'), mad_mm=observed.get('mad_mm'), fact_id=observed.get('fact_id')))
    depth_rows = {}
    for n, values in after.items():
        depth_rows[n] = []
        for sample in values:
            packet = packets[sample['frame']]; observed, fact = _extract(sample, packet)
            costs, detail = DEPTH.costs(depth_samples, observed, sample['time'], packet['measured'].get('adaptive_full'))
            depth_rows[n].append(dict(frame=sample['frame'], costs=costs, detail=detail, current_fact=fact))
    depth_common = bool(use_depth and all(row['detail']['used'] for rows in depth_rows.values() for row in rows))
    for role, history in before.items():
        pre_short = history[-count:]; a = history[-1]; diag=max(1.,math.hypot(_box(a)[2]-_box(a)[0],_box(a)[3]-_box(a)[1]))
        for n, post in after.items():
            geometry=[]; contours=[]
            for sample in post:
                gap=sample['time']-a['time']; assert gap>0, 'Noncausal endpoint comparison'
                horizon=min(gap,CFG['geometry_prediction_horizon_seconds'])
                predicted=(np.asarray(pre_fit[role]['center_at_last_time_px'])+np.asarray(pre_fit[role]['velocity_px_s'])*horizon
                    if pre_fit[role]['status']=='AVAILABLE_MEASURED_OLS' else np.asarray(_center(a)))
                position=float(np.linalg.norm(predicted-np.asarray(_center(sample)))/diag)
                motion=(float(np.linalg.norm(np.asarray(pre_fit[role]['velocity_px_s'])-np.asarray(post_fit[n]['velocity_px_s'])))*horizon/diag
                    if motion_common else None)
                geometry.append(dict(frame=sample['frame'], position=position, motion=motion,
                    actual_gap_seconds=gap, prediction_horizon_seconds=horizon, predicted_center_px=predicted.tolist(),
                    prediction_model='MEASURED_OLS' if pre_fit[role]['status']=='AVAILABLE_MEASURED_OLS' else 'LAST_OBSERVED_POSITION_MOTION_UNKNOWN'))
            if len(pre_short)==count:
                for left in pre_short:
                    for right in post:
                        previous,current=packets[left['frame']],packets[right['frame']]
                        pair=pair_at(left['frame'],right['frame'])
                        if pair is None:
                            detail=dict(available=False,status='UNKNOWN',reason='NO_ACTUAL_MOTION_PROVIDER')
                        else:
                            detail=_contour(pair,previous['masks'][_native(left)],current['masks'][n])
                            detail['actual_pair']=_pair_contract(pair,previous,current)
                        detail.update(pre_frame=left['frame'],post_frame=right['frame'])
                        contours.append(detail);all_contours.append(detail)
            else:
                detail=dict(available=False,status='UNKNOWN',reason='FEWER_THAN_THREE_PRE_CONTOUR_OBSERVATIONS')
                contours.append(detail);all_contours.append(detail)
            k=episode['public_ids'][roles.index(role)]
            matrix[role,n]=dict(role=role,native=n,public=k,
                geometry=float(np.mean([g['position']+(CFG['motion_weight']*g['motion'] if g['motion'] is not None else 0.) for g in geometry])),
                geometry_samples=geometry,contour_samples=contours,
                contour_cost=float(np.mean([1-c['symmetric_dice'] for c in contours])) if all(c['available'] for c in contours) else None,
                depth_cost=float(np.mean([row['costs'][k] for row in depth_rows[n]])),depth_rows=copy.deepcopy(depth_rows[n]))
    contour_common=all(c['available'] for c in all_contours)
    weights=dict(motion=CFG['motion_weight'] if motion_common else 0.,
        contour=CFG['contour_weight'] if contour_common else 0.,depth=CFG['depth_weight'] if depth_common else 0.)
    scores=[]
    for choice, order in (('H1',sources),('H2',sources[::-1])):
        edges=[copy.deepcopy(matrix[role,n]) for role,n in zip(roles,order)]
        score=sum(e['geometry']+weights['contour']*(e['contour_cost'] or 0.)+weights['depth']*e['depth_cost'] for e in edges)
        scores.append(dict(choice=choice,score=float(score),mapping={n:episode['public_ids'][i] for i,n in enumerate(order)},edges=edges))
    ranked=sorted(scores,key=lambda x:(x['score'],x['choice']));margin=ranked[1]['score']-ranked[0]['score']
    selected=ranked[0] if margin>=CFG['min_joint_margin'] else None
    backwards={str(n):_back_to_q(n,after[n][-1],q,packets,pair_at) for n in sources}
    return dict(base,status='CHOOSE' if selected else 'DEFER',choice=selected['choice'] if selected else 'DEFER',
        mapping=selected['mapping'] if selected else None,reason='FROZEN_JOINT_SHORT_ENDPOINT_COST' if selected else 'INSUFFICIENT_JOINT_MARGIN',
        scores=scores,winning_margin=float(margin),minimum_joint_margin=CFG['min_joint_margin'],common_weights=weights,
        pre_fits=pre_fit,post_fits=post_fit,pre_references=pre_refs,post_references=post_refs,depth_facts=depth_facts,
        post_backward_to_q=backwards,motion_pairs=len(cache),
        contour_selection='LAST_THREE_PRE_X_FIRST_CONFIRMED_THREE_CONSECUTIVE_RAW_CLEAN_POST_FIXED_ALL_PAIRS',
        confirmed_post_supplied_by_frozen_event_manager=confirmed is not None,
        actual_reference_anchors={role:copy.deepcopy(pre[role].get('anchor')) for role in roles},
        depth_missing_model='COMMON_NULL_ENTIRE_TWO_BY_TWO_COMPONENT',
        source_versions_checked_per_endpoint=True,no_assumed_cross_risk_identity=True,
        depth_model='UNCHANGED_DS31_DS1_WLS_FULL_FRAME_BACKGROUND_NORMALIZED_T4',
        no_claim_of_scene_flow_or_foreground_or_physical_identity=True)
