"""Reopen every actual endpoint and independently check populations/label scope."""
from pathlib import Path
from collections import Counter
from datetime import datetime
import copy
import json
import math
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run
from common import artifact, read, rows, write_new
from source import RawDepth
from measurement import PARAMETERS, array_binding, measure_local_background
import cv2
import numpy as np


def canonical(roi, valid, index, excluded):
    positions = np.flatnonzero(roi & valid & ~np.isin(index, excluded))
    if len(positions):
        _, first = np.unique(index.ravel()[positions], return_index=True)
        positions = positions[np.sort(first)]
    return positions


def dilate(mask, radius):
    return cv2.dilate(mask.astype('u1'), np.ones((2 * radius + 1,) * 2, 'u1')).astype(bool)


def check_pixels(record, debug, frame, native):
    """Direct actual-array checks; do not accept caller digest as population truth."""
    depth, index, sensor, masks = (frame[k] for k in ('depth', 'source_index', 'native_depth', 'masks'))
    own = masks[native]
    other = np.logical_or.reduce([v for n, v in masks.items() if n != native]) if len(masks) > 1 else np.zeros(own.shape, bool)
    valid = np.isfinite(depth) & (depth > 0) & (index >= 0)
    assert np.all(np.isfinite(sensor.ravel()[index[valid]]) & (sensor.ravel()[index[valid]] > 0))
    own_sources, other_sources = np.unique(index[own & valid]), np.unique(index[other & valid])
    neighbors = dilate(other, 3)
    roi = own & ~neighbors
    ring = dilate(own, 20) & ~dilate(own, 5) & ~neighbors
    selected = canonical(roi, valid, index, other_sources)
    background = canonical(ring, valid, index, np.union1d(own_sources, other_sources))
    for actual, positions in ((debug['mask_selected'], selected), (debug['background_selected'], background)):
        expected = np.zeros(own.shape, bool); expected.ravel()[positions] = True
        assert np.array_equal(actual, expected)
        assert len(np.unique(index.ravel()[positions])) == len(positions)
    assert record['mask_summary']['n'] == len(selected)
    assert record['background']['summary']['n'] == len(background)
    assert record['original_mask_area'] == int(own.sum())
    assert record['sampling_roi_area'] == int(roi.sum())
    assert record['mask_summary']['valid_fraction'] == len(selected) / max(1, int(own.sum()))
    assert record['source_binding'] == frame['source_binding']
    assert record['parameters'] == PARAMETERS
    assert record['foreground_identity'] == record['physical_background'] == record['identity'] == 'UNKNOWN'
    assert record['no_peak_selection'] and record['no_hole_filling'] and record['no_history_input_or_state_write']
    if record['plane'] is None:
        assert record['status'] == 'UNKNOWN' and not record['components']
        return
    plane = record['plane']; cx, cy = plane['origin_px']; beta = plane['beta_mm']
    gy, gx = np.indices(depth.shape)
    expected_plane = beta[0] + beta[1] * (gx - cx) / 20. + beta[2] * (gy - cy) / 20.
    assert np.array_equal(debug['plane_mm'], expected_plane)
    assert np.allclose(debug['residual_mm'][valid], depth[valid] - expected_plane[valid], rtol=0, atol=1e-10)
    assert plane['sample_n'] == len(background)
    assert 'scale_mm' not in plane['mask_prediction_leverage']
    assert 'scale_mm' not in plane['mask_prediction_uncertainty_mm']
    if record['reason'] in ('BACKGROUND_RESIDUAL_TOO_BROAD', 'INSUFFICIENT_INDEPENDENT_MASK_COVERAGE'):
        assert record['status'] == 'UNKNOWN' and not record['components']
        return
    significant = roi & valid & (np.abs(debug['residual_mm']) > plane['contrast_threshold_mm'])
    assert np.array_equal(significant, debug['significant'])
    components, qualified, labels = [], [], np.zeros(own.shape, 'i4')
    number = 0
    for sign, sign_mask in [('NEARER', debug['residual_mm'] < 0), ('FARTHER', debug['residual_mm'] > 0)]:
        count, local = cv2.connectedComponents((significant & sign_mask).astype('u1'), connectivity=8)
        for ordinal in range(1, count):
            number += 1; region = local == ordinal; labels[region] = number
            positions = selected[region.ravel()[selected]]
            values = debug['residual_mm'].ravel()[positions]
            median = float(np.median(values)) if len(values) else None
            scale = max(15., 1.4826 * float(np.median(np.abs(values - median)))) if len(values) else None
            good = bool(len(positions) >= 16 and len(positions) / max(1, len(selected)) >= .2 and scale <= 60.)
            component = record['components'][number - 1]
            assert component['numeric_label'] == number and component['sign'] == sign
            assert component['independent_n'] == len(positions) and component['geometric_area'] == int(region.sum())
            assert component['mask_source_fraction'] == len(positions) / max(1, len(selected))
            assert component['qualified'] == good and component['median_residual_mm'] == median
            assert component['scale_mm'] == scale
            assert component['population_binding']['selected_pixel_binding'] == array_binding(positions)
            assert component['population_binding']['selected_source_index_binding'] == array_binding(index.ravel()[positions])
            assert component['population_binding']['selected_depth_binding'] == array_binding(depth.ravel()[positions])
            assert component['geometric_component_binding'] == array_binding(region)
            components.append(component)
            if good: qualified.append(positions)
    assert len(record['components']) == len(components)
    assert np.array_equal(debug['component_labels'], labels)
    assert record['qualified_component_n'] == len(qualified)
    assert record['qualified_independent_n'] == sum(map(len, qualified))
    assert (record['status'] == 'AVAILABLE') == bool(qualified)


def expected_comparison(current, anchor):
    """Fixed common nominal threshold; real uncertainty stays descriptive."""
    pairs = []
    for c in current['components']:
        if not c['qualified']: continue
        for a in anchor['components']:
            if not a['qualified']: continue
            gap = abs(c['median_residual_mm'] - a['median_residual_mm'])
            sigma = math.sqrt(c['scale_mm'] ** 2 + a['scale_mm'] ** 2 +
                current['background']['residual_scale_mm'] ** 2 + anchor['background']['residual_scale_mm'] ** 2)
            pairs.append(dict(current_support_id=c['support_id'], anchor_support_id=a['support_id'],
                current_sign=c['sign'], anchor_sign=a['sign'], difference_mm=gap,
                common_scale_mm=30., threshold_mm=90., compatible=gap <= 90.,
                actual_uncertainty_scale_mm=sigma, actual_uncertainty_threshold_mm=max(30., 3. * sigma),
                actual_uncertainty_compatible=gap <= max(30., 3. * sigma)))
    status = ('UNKNOWN' if current['status'] != 'AVAILABLE' or anchor['status'] != 'AVAILABLE' or not pairs else
        'DEPTH_EXPLANATION_COMPATIBLE_PROXY' if any(p['compatible'] for p in pairs) else 'DEPTH_EXPLANATION_CONFLICT_PROXY')
    return status, pairs


def semantic_selfcheck():
    """Two-sided actual pixels, affine plane recovery and missing-edge semantics."""
    gy, gx = np.indices((96, 96)); depth = (1000. + .25 * gx + .5 * gy).astype('f8')
    mask = np.zeros(depth.shape, bool); mask[35:61, 35:61] = True
    depth[35:61, 35:48] -= 80.; depth[35:61, 48:61] += 95.
    index = np.arange(depth.size, dtype='i4').reshape(depth.shape); sensor = depth.copy()
    def binding(d, i, n):
        return dict(global_frame=10, time=.3, aligned_depth=array_binding(d), aligned_source_index=array_binding(i),
            native_depth=array_binding(n), actual_fields_read=['current_native_depth_mm'], RGB_read=False, GT_read=False, restored_read=False)
    source = binding(depth, index, sensor)
    record, debug = measure_local_background(depth, index, sensor, {1: mask}, 1, 'SYNTHETIC', 11, 10, .3,
        source_binding=source, expected_source_binding=source)
    check_pixels(record, debug, dict(depth=depth, source_index=index, native_depth=sensor, masks={1:mask}, source_binding=source), 1)
    assert record['status'] == 'AVAILABLE' and {c['sign'] for c in record['components'] if c['qualified']} == {'NEARER', 'FARTHER'}
    expected = 1000. + .25 * gx + .5 * gy
    assert np.allclose(debug['plane_mm'], expected, atol=1e-8)
    assert {round(c['median_residual_mm'], 5) for c in record['components']} == {-80., 95.}
    missing = copy.deepcopy(record); missing['status'] = 'UNKNOWN'; missing['components'] = []
    assert expected_comparison(record, missing) == ('UNKNOWN', [])
    malicious = copy.deepcopy(source); malicious['global_frame'] = 11
    try:
        measure_local_background(depth, index, sensor, {1:mask}, 1, 'SYNTHETIC', 11, 10, .3,
            source_binding=malicious, expected_source_binding=malicious)
    except AssertionError: pass
    else: raise AssertionError('Self-consistent metadata frame violation accepted')
    return dict(status='PASS', checks=3, actual_two_sided_pixels=True, no_GT=True)


def main():
    run.verify_freeze(); seal = run.verify_measurement_seal(); selfchecks = semantic_selfcheck()
    features = run.load_features(); facts, assignments, pins = run.load_sources(features)
    measured_rows = list(rows(HERE / 'MEASUREMENTS.jsonl.gz'))
    saved = {entry['fact_id']: entry for entry in measured_rows}
    assert len(saved) == len(measured_rows), 'Duplicate measured endpoint'
    assert set(saved) == set(facts) and len(saved) == seal['unique_endpoint_count']
    checked, frames = [], 0
    for segment in run.old.SEGMENTS:
        sensor = RawDepth(segment)
        try:
            for frame in sorted({f['frame'] for f in facts.values() if f['segment'] == segment}):
                arrays = run.load_endpoint_frame(segment, frame, facts, assignments, sensor); frames += 1
                for fact in sorted((f for f in facts.values() if (f['segment'], f['frame']) == (segment, frame)), key=lambda f:f['native']):
                    current, debug = measure_local_background(arrays['depth'], arrays['source_index'], arrays['native_depth'],
                        arrays['masks'], fact['native'], segment, frame, arrays['global_frame'], arrays['time'],
                        source_binding=arrays['source_binding'], expected_source_binding=fact['_raw_measurement']['raw_source_binding'])
                    assert current == saved[fact['fact_id']]['measurement']
                    assert saved[fact['fact_id']]['old_certificate_sha256'] == fact['certificate']['certificate_sha256']
                    check_pixels(current, debug, arrays, fact['native']); checked.append(fact['fact_id'])
        finally: sensor.close()
    actual = {r['action_id']:r for r in read(HERE / 'ACTION_FEATURES.json')['actions']}
    results = read(HERE / 'RESULTS.json'); labels = {a['action_id']:a for a in read(run.DS21 / 'ACTIONS.json')['actions']}
    joined = {a['action_id']:a for a in results['actions']}
    assert len(actual) == len(joined) == len(labels) == 90
    assert datetime.fromisoformat(seal['sealed_at_utc']) <= datetime.fromisoformat(results['label_join_started_utc'])
    primary, birth_extra = 0, 0
    for f in features:
        got, labeled = actual[f['action_id']], joined[f['action_id']]
        assert got['original_action_feature_sha256'] == run.digest(f)
        assert labeled['physical'] == labels[f['action_id']]['physical']
        assert set(got['comparisons']) == set(f['anchor_fact_ids'])
        assert got['primary_role'] == run.primary_role(f)
        for role, fid in f['anchor_fact_ids'].items():
            anchor_frame = facts[fid]['frame']; assert anchor_frame < f['frame']
            edge = got['comparisons'][role]; assert edge['anchor_fact_id'] == fid and edge['current_fact_id'] == f['current_fact_id']
            status, pairs = expected_comparison(saved[f['current_fact_id']]['measurement'], saved[fid]['measurement'])
            assert edge['comparison']['status'] == status and edge['comparison']['all_qualified_layer_pairs'] == pairs
            assert edge['comparison']['identity'] == 'UNKNOWN' and edge['comparison']['state_action'] == 'NONE'
            assert edge['comparison']['unknown_is_zero_cost'] is False
            if role == got['primary_role']: primary += 2
            else: birth_extra += 2
        assert labeled['primary_comparison'] == got['comparisons'][got['primary_role']]
    assert primary == 180 and birth_extra == 8
    assert Counter(a['physical'] for a in joined.values()) == Counter(CORRECT=15, WRONG=17, UNSCORABLE=58)
    assert results['new_metrics'] is None and not results['new_prediction'] and not results['new_scoring']
    visual = read(HERE / 'PRIVATE_VISUALS.json'); old_visual = read(run.DS21 / 'PRIVATE_VISUALS.json')
    assert [v['action_id'] for v in visual['figures']] == [v['action_id'] for v in old_visual['figures']]
    assert visual['absent_strata'] == old_visual['absent_strata'] and len(visual['figures']) == 10
    for v in visual['figures']:
        assert artifact(v['artifact']['path']) == v['artifact']
        old = labels[v['action_id']]
        assert v['actual_endpoint_fact_ids'] == [old['actual_anchor_fact_id'], old['current_fact_id']]
        for panel in v['panels']:
            assert panel['measurement_record_sha256'] == run.digest(saved[panel['fact_id']]['measurement'])
            assert panel['raw_source_binding'] == saved[panel['fact_id']]['measurement']['source_binding']
        assert not v['future_read'] and v['no_new_prediction']
    run.verify_freeze()
    outcome = dict(status='PASS', checks=selfchecks, actual_raw_endpoints_reopened=len(checked), actual_raw_frames=frames,
        all_raw_populations_components_and_two_sided_residuals_checked=True, action_count=90,
        actual_primary_endpoint_roles=180, actual_birth_secondary_endpoint_roles=8,
        original_views_and_anchors_preserved=True, nominal_common_threshold_mm=90.,
        physical_counts=dict(Counter(a['physical'] for a in joined.values())), unknown_not_safe_or_zero_cost=True,
        fixed_private_visuals_verified=10, manual_visual_inspection='NOT_PERFORMED_BY_THIS_SCRIPT',
        no_GT_pixels=True, no_new_metrics=True, new_model_http=0, cost_usd=0,
        source_pins=pins, verified_measurement_seal=artifact(HERE / 'MEASUREMENTS_SEALED.json'),
        actual_review_code=artifact(Path(__file__)))
    write_new(HERE / 'INDEPENDENT_REVIEW.json', outcome)
    print(json.dumps({k:v for k,v in outcome.items() if k != 'source_pins'}), flush=True)


if __name__ == '__main__': main()
