"""Focused actual-array/source checks; no pixels, reference labels or state writes."""
from __future__ import annotations

import copy
import json
import math

import numpy as np

from common import HERE, ROOT, SEGMENTS, input_dir, module, rows


def _fixture(offsets=(-400., -200.)):
    yy, xx = np.indices((360, 640))
    depth = (1500. + .10 * xx + .05 * yy).astype('f4')
    first = np.zeros(depth.shape, bool)
    second = first.copy()
    first[120:160, 260:290] = True
    second[120:160, 290:320] = True
    depth[first] += offsets[0]
    depth[second] += offsets[1]
    index = np.arange(depth.size, dtype='i4').reshape(depth.shape)
    native = np.full((576, 640), 1000., 'f4')
    return depth, index, native, {1: first, 2: second}, first | second


def _binding(measurement, arrays, frame=1, global_frame=0, time=0.):
    depth, index, native = arrays[:3]
    return dict(frame=frame, global_frame=global_frame, time=time,
        actual_fields_read=['depth_mm', 'source_index'],
        native_fields_read=['current_native_depth_mm'],
        aligned_depth=measurement.array_binding(depth),
        aligned_source_index=measurement.array_binding(index),
        native_depth=measurement.array_binding(native),
        aligned_coordinates='RECORDED_RGB_CAMERA_Z_MM',
        native_coordinates='RECORDED_NATIVE_SENSOR_Z_MM',
        RGB_read=False, GT_read=False, restored_read=False)


def _measure(measurement, arrays, binding=None, expected=None, **coordinates):
    binding = binding or _binding(measurement, arrays)
    expected = binding if expected is None else expected
    return measurement.measure_region(*arrays, 'synthetic_source',
        coordinates.get('frame', 1), coordinates.get('global_frame', 0),
        coordinates.get('time', 0.), source_binding=binding,
        expected_source_binding=expected)


def _reject(call, message):
    try:
        call()
    except AssertionError:
        return
    raise AssertionError(message)


def _qualified(fact):
    return [layer for layer in fact['layers'] if layer['qualified']]


def _actual_checks(measurement):
    """First old measurement opportunity in recorded segment/row order, no grade selection."""
    from source import RawDepth, native_masks

    selected = None
    for segment in SEGMENTS:
        path = ROOT / 'experiments/ds24_z4q_relative_order/run' / segment / 'public/ORDER_CHECKS.jsonl.gz'
        for row in rows(path):
            for check in row['checks']:
                comparison = next((x for x in check.get('comparisons', []) if x.get('pre_pairs')), None)
                if comparison is not None:
                    selected = segment, row, check, comparison
                    break
            if selected is not None:
                break
        if selected is not None:
            break
    assert selected is not None, 'Old recorded measurement fixture is absent'
    segment, row, check, comparison = selected
    assert (segment, row['frame'], row['global_frame'], check['native_id'],
        check['anchor']['native_id'], comparison['partner_native']) == (
        'feeding_000351_000555', 82, 432, 73, 30, 66)
    anchor = comparison['pre_pairs'][-1]['frame']
    assert anchor == check['anchor']['frame'] == 22
    wanted = {anchor, row['frame']}
    assignments = {r['frame']: r for r in rows(input_dir(segment) / 'assignments.jsonl.gz') if r['frame'] in wanted}
    saved = {r['frame']: r for r in rows(input_dir(segment) / 'DEPTH_OBSERVATIONS.jsonl.gz') if r['frame'] in wanted}
    assert set(assignments) == set(saved) == wanted
    sensor = RawDepth(segment)
    try:
        for frame, first in ((anchor, check['anchor']['native_id']), (row['frame'], check['native_id'])):
            source = saved[frame]
            depth, index, native, binding = sensor(source['global_frame'], source['time'])
            assert binding == source['raw_source_binding'], 'Actual raw source differs from immutable fixture'
            assert not any(binding.get(k, False) for k in ('RGB_read', 'GT_read', 'restored_read'))
            masks = native_masks(assignments[frame])
            second = comparison['partner_native']
            roi = masks[first] | masks[second]
            seed = measurement.contact_seed(masks, first, second)
            assert seed.dtype == np.dtype(bool) and not np.any(seed & ~roi)
            originals = [array.copy() for array in (depth, index, native, roi)]
            original_masks = {n: mask.copy() for n, mask in masks.items()}
            args = (depth, index, native, masks, roi, segment, frame, source['global_frame'], source['time'])
            fact, maps = measurement.measure_region(*args, source_binding=binding, expected_source_binding=source['raw_source_binding'])
            repeated, _ = measurement.measure_region(*args, source_binding=binding, expected_source_binding=source['raw_source_binding'])
            assert fact == repeated, 'Fixed actual source measurement must reproduce its numeric facts'
            assert fact['status'] in ('AVAILABLE_TWO_LAYERS', 'UNKNOWN')
            assert fact['foreground_identity'] == fact['identity'] == fact['physical_fish_count'] == 'UNKNOWN'
            assert fact['original_roi_area'] == int(roi.sum())
            assert sum(x['independent_n'] for x in fact['layers']) == fact['summary']['n']
            json.dumps(fact, allow_nan=False)
            for actual, original in zip((depth, index, native, roi), originals):
                assert np.array_equal(actual, original, equal_nan=True)
            assert all(np.array_equal(masks[n], original_masks[n]) for n in masks)
            assert all(not np.any(support & ~roi) for support in maps['support_masks'].values())
    finally:
        sensor.close()
    return ['actual_first_old_measured_pair_raw_binding_and_numeric_reproduction']


def run_checks() -> list[str]:
    measurement = module('ds25_source_check_measurement', HERE / 'measurement.py')
    passed = []

    arrays = _fixture()
    originals = [a.copy() for a in arrays[:3]] + [arrays[4].copy()]
    original_masks = {n: m.copy() for n, m in arrays[3].items()}
    fact, maps = _measure(measurement, arrays)
    layers = _qualified(fact)
    assert fact['status'] == 'AVAILABLE_TWO_LAYERS' and len(layers) == 2
    assert all(x['median_residual_mm'] < -150. for x in layers)
    assert len({x['depth_gap_group'] for x in layers}) == 2
    assert all(math.isfinite(x['sigma_mm']) and x['sigma_mm'] > 0 for x in layers)
    assert all(x['physical_surface_identity'] == x['fish_count'] == 'UNKNOWN' for x in layers)
    assert fact['identity'] == fact['foreground_identity'] == fact['physical_fish_count'] == 'UNKNOWN'
    assert not np.array_equal(arrays[0], arrays[2][:360])
    json.dumps(fact, allow_nan=False)
    for actual, original in zip((*arrays[:3], arrays[4]), originals):
        assert np.array_equal(actual, original)
    assert all(np.array_equal(arrays[3][n], original_masks[n]) for n in arrays[3])
    assert np.array_equal(maps['roi'], arrays[4])
    passed.append('same_sign_two_measured_foreground_layers_remain_anonymous_and_inputs_immutable')

    fact, _ = _measure(measurement, _fixture((-200., 200.)))
    assert fact['status'] == 'AVAILABLE_TWO_LAYERS'
    assert sorted(np.sign(x['median_residual_mm']) for x in _qualified(fact)) == [-1., 1.]
    passed.append('opposite_sign_measured_layers_both_retained')

    fact, _ = _measure(measurement, _fixture((-200., 0.)))
    compatible = [x for x in fact['layers'] if x['background_compatibility'] == 'BACKGROUND_COMPATIBLE']
    assert fact['status'] == 'UNKNOWN' and len(_qualified(fact)) == 1
    assert compatible and all(not x['qualified'] for x in compatible)
    assert all(x['fish_count'] == 'UNKNOWN' for x in compatible)
    passed.append('far_background_compatible_support_retained_without_second_fish_claim')

    arrays = _fixture()
    trusted = _binding(measurement, arrays)
    for key, value in (('frame', 2), ('global_frame', 1), ('time', .1),
                       ('GT_read', True), ('RGB_read', True), ('restored_read', True)):
        forged = dict(trusted, **{key: value})
        _reject(lambda: _measure(measurement, arrays, forged, forged), 'Self-consistent source semantic forgery accepted: ' + key)
    forged = copy.deepcopy(trusted)
    forged['actual_fields_read'].append('annotation/instance_id')
    _reject(lambda: _measure(measurement, arrays, forged, forged), 'Unexposed field accepted')
    future = _binding(measurement, arrays, frame=2, global_frame=1, time=.1)
    _reject(lambda: _measure(measurement, arrays, future, trusted, frame=2, global_frame=1, time=.1), 'Future packet replaced actual bound fixture')
    passed.append('self_consistent_frame_time_field_and_future_packet_forgeries_rejected')

    for position in (0, 1):
        changed = list(_fixture())
        changed[position] = np.roll(changed[position], 1, axis=1)
        forged = _binding(measurement, changed)
        _reject(lambda: _measure(measurement, changed, forged, trusted), 'Self-consistent same-frame array swap accepted')
    changed = list(_fixture())
    changed[2][0, 0] = 0.
    changed[1][130, 270] = 0
    forged = _binding(measurement, changed)
    _reject(lambda: _measure(measurement, changed, forged, forged), 'Source index references missing native depth')
    passed.append('trusted_same_frame_array_swaps_and_missing_native_source_rejected')

    arrays = list(_fixture())
    first = arrays[3][1]
    arrays[0][first] = 1100.
    arrays[1][first] = arrays[1][120, 260]
    fact, maps = _measure(measurement, arrays)
    assert fact['status'] == 'UNKNOWN'
    assert fact['roi_source_exclusions']['within_mask_duplicate_pixels_excluded'] == int(first.sum()) - 1
    assert fact['summary']['n'] == int(arrays[4].sum()) - int(first.sum()) + 1
    retained = [x for x in fact['layers'] if x['kind'] == 'MEASURED_DEPTH_SUPPORT' and x['z_mm'] == 1100.]
    assert len(retained) == 1 and retained[0]['independent_n'] == 1 and not retained[0]['qualified']
    assert int(maps['mask_selected'].sum()) == fact['summary']['n']
    passed.append('legal_repeated_projection_sources_are_counted_once_not_quality_inflated')

    arrays = list(_fixture())
    third = np.zeros_like(arrays[4])
    third[120:160, 340:370] = True
    arrays[3][3] = third
    arrays[4] |= third
    arrays[0][third] = np.linspace(1410., 1660., int(third.sum()), dtype='f4')
    fact, _ = _measure(measurement, arrays)
    assert fact['status'] == 'UNKNOWN' and len(_qualified(fact)) == 2
    broad = [x for x in fact['layers'] if x['substantial'] and x['sigma_mm'] > 60.]
    assert broad and all(not x['qualified'] for x in broad)
    assert any(x['support_id'] in fact['substantial_unresolved_support_ids'] for x in broad)
    assert any(x['background_compatibility'] == 'BACKGROUND_COMPATIBLE' for x in broad)
    passed.append('substantial_noisy_third_support_is_unresolved_even_with_background_compatible_median')

    arrays = list(_fixture())
    arrays[3][2] = np.roll(arrays[3][2], 50, axis=1)
    arrays[4] = arrays[3][1] | arrays[3][2]
    arrays[0][:] = 1500.
    arrays[0][arrays[4]] = 1100.
    fact, _ = _measure(measurement, arrays)
    assert fact['status'] == 'UNKNOWN' and len(_qualified(fact)) == 2
    assert len({x['depth_gap_group'] for x in _qualified(fact)}) == 1
    passed.append('two_disconnected_spatial_pieces_of_same_depth_are_not_two_layers')

    arrays = list(_fixture())
    arrays[3] = {1: arrays[4].copy(), 2: arrays[4].copy()}
    fact, maps = _measure(measurement, arrays)
    assert fact['status'] == 'AVAILABLE_TWO_LAYERS'
    association = module('ds25_source_check_ownership', HERE / 'association.py')
    packet = dict(fact=fact, maps=maps, roles={'A': arrays[3][1], 'B': arrays[3][2]})
    owner, counts = association._ownership(packet, _qualified(fact), .1, .9)
    assert owner is None and all(x['role_fractions'] == {'A': 1., 'B': 1.} for x in counts)
    assert fact['identity'] == 'UNKNOWN'
    passed.append('mixed_actual_mask_membership_does_not_choose_layer_identity')

    arrays = list(_fixture())
    arrays[4] = np.zeros_like(arrays[4])
    fact, maps = _measure(measurement, arrays)
    assert fact['status'] == 'UNKNOWN' and fact['reason'] == 'EMPTY_ORIGINAL_CONTACT_ROI'
    assert not fact['layers'] and not maps['roi'].any()
    outside = list(_fixture())
    outside[4][0, 0] = True
    _reject(lambda: _measure(measurement, outside), 'Unclipped ROI outside actual masks accepted')
    wrong_type = list(_fixture())
    wrong_type[4] = wrong_type[4].astype('u1')
    _reject(lambda: _measure(measurement, wrong_type), 'Non-boolean ROI accepted')
    passed.append('empty_roi_unknown_and_unclipped_or_wrong_type_roi_rejected')

    arrays = _fixture()
    forward = measurement.contact_seed(arrays[3], 1, 2)
    backward = measurement.contact_seed(arrays[3], 2, 1)
    assert forward.any() and np.array_equal(forward, backward)
    assert not np.any(forward & ~arrays[4])
    assert not np.any(measurement.contact_seed({1: arrays[3][1], 2: np.roll(arrays[3][2], 100, axis=1)}, 1, 2))
    passed.append('contact_seed_is_symmetric_actual_mask_geometry_not_depth_selection')

    passed.extend(_actual_checks(measurement))
    return passed


if __name__ == '__main__':
    print(json.dumps(dict(status='PASS', checks=run_checks()), indent=2))
