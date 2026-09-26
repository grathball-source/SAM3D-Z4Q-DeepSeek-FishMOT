"""Frozen, transparent endpoint-history comparators; intermediate masks are uncertainty only."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from prepare import M2, put, read


def reliable_depth(obs):
    d = obs.get('depth')
    if not d or d.get('epistemic_type') != 'MEASUREMENT' or d.get('overlap_pixels', 1) > 0 or obs['neighbor_count']:
        return None
    c = d.get('core') or {}
    return c if c.get('n', 0) >= 16 and c.get('valid_fraction', 0) >= .2 and c.get('median') is not None else None


def edge(a, b, diagonal, depth):
    pre, post = a['observations'], b['observations']
    if not pre or not post:
        return dict(status='UNKNOWN', reason='MISSING_PRE_OR_POST_OBSERVATION')
    x, y = pre[-1], post[0]
    gap = y['source_time_seconds']-x['source_time_seconds']
    if gap <= 0:
        return dict(status='UNKNOWN', reason='INVALID_TIME_ORDER')
    start, end = x['bbox_center_px'], y['bbox_center_px']
    distance = math.dist(start, end)
    motion = {}
    residuals = []
    for name, segment, direction in (('forward', a, 1), ('backward', b, -1)):
        v = segment['velocity']
        if v['epistemic_type'] == 'ESTIMATE':
            velocity = v['velocity_px_per_s']
            origin, target = (start, end) if direction == 1 else (end, start)
            projection = [origin[k]+direction*velocity[k]*gap for k in (0, 1)]
            error = math.dist(projection, target)
            # A long gap is uncertain; residual grows with time, never a hard reachability veto.
            scale = diagonal + v['residual_rms_px']*(1+gap/max(.1, v['time_interval_seconds'][1]-v['time_interval_seconds'][0]))
            motion[name] = dict(predicted_px=[round(z, 3) for z in projection],
                                error_px=round(error, 3), scale_px=round(scale, 3), normalized=error/scale,
                                velocity_source_fact_ids=v['source_fact_ids'])
            residuals.append(error/scale)
        else:
            motion[name] = dict(status='UNKNOWN', reason=v['reason'])
    geometry = sum(residuals)/len(residuals) if residuals else distance/diagonal
    result = dict(status='AVAILABLE', endpoint_fact_ids=[x['fact_id'], y['fact_id']], gap_seconds=round(gap, 3),
                  position_distance_px=round(distance, 3), roi_diagonal_px=round(diagonal, 3),
                  motion=motion, geometry_cost=round(geometry, 6),
                  no_constant_velocity_truth_claim=True)
    if depth:
        d1, d2 = reliable_depth(x), reliable_depth(y)
        if d1 and d2:
            delta = abs(d1['median']-d2['median'])
            scale = 15+d1['mad']+d2['mad']
            result['depth_cost'] = round(delta/scale, 6)
            result['depth'] = dict(delta_pipeline_mm=round(delta, 3), uncertainty_scale_pipeline_mm=round(scale, 3),
                                   source='actual_raw_sensor_core_profiles; frame-local, not persistent identity')
        else:
            result['depth_cost'] = None
            result['depth'] = dict(status='UNKNOWN', reason='CORE_DEPTH_QUALITY_OR_MIXTURE')
    return result


def compare(packet, roi, depth):
    diag = math.hypot(roi[2]-roi[0], roi[3]-roi[1])
    edges = {f'{a}-{b}': edge(packet['PRE_HISTORY'][a], packet['POST_HISTORY_TO_Q'][b], diag, depth)
             for a in 'AB' for b in 'XY'}
    totals = {}
    for hypothesis in packet['hypotheses']:
        parts = [edges[f'{hypothesis["mapping"][current]}-{current}'] for current in 'XY']
        if any(x['status'] != 'AVAILABLE' for x in parts):
            totals[hypothesis['id']] = None
        else:
            totals[hypothesis['id']] = round(sum(x['geometry_cost'] + (x.get('depth_cost') or 0)
                                                  for x in parts), 6)
    available = {k: v for k, v in totals.items() if v is not None}
    chosen = min(available, key=available.get) if len(available) == 2 and len(set(available.values())) == 2 else 'DEFER'
    return dict(choice=chosen, candidate_costs=totals, edge_costs=edges,
                type='ENDPOINT_HISTORY_BASELINE',
                limitation='Uses the same reliable PRE/POST samples; intermediate anonymous observations only flag uncertainty and do not make this a full same-information history comparator. No VLM necessity claim.')


def main(run):
    packets = read(run/'public/EPISODE_FACTS.json')
    old = {x['case_alias']: x for x in read(M2/'public/SOURCE_MANIFEST.json')['cases']}
    result = {}
    for p in packets:
        case = p['request_id'].split('-')[-1]
        result[case] = dict(B0_source='frozen_existing_prediction; scored only postseal',
                            N_H2D=compare(p, old[case]['roi_mask_xyxy'], False),
                            N_HD=compare(p, old[case]['roi_mask_xyxy'], True))
    put(run/'public/NUMERIC_REFERENCE.json', result)
    print(json.dumps({x: (r['N_H2D']['choice'], r['N_HD']['choice']) for x, r in result.items()}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', type=Path, required=True)
    main(parser.parse_args().run)
