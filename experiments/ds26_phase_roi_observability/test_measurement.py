"""Focused checks through the actual unchanged DS25 producer; no research score."""
from common import *
import copy
import numpy as np
from measurement_adapter import summarize, pair_summary


def fixture():
    depth = np.full((360, 640), 1500., dtype='f4')
    index = np.arange(depth.size, dtype='i4').reshape(depth.shape)
    native = np.full((576, 640), 1000., dtype='f4')
    a = np.zeros(depth.shape, bool); b = a.copy()
    a[120:160, 260:290] = True; b[120:160, 340:370] = True
    depth[a] = 1100.; depth[b] = 1300.
    return depth, index, native, {1: a, 2: b}


def measure(arrays, role):
    depth, index, native, masks = arrays
    binding = dict(frame=1, global_frame=0, time=0., actual_fields_read=['depth_mm', 'source_index'],
        native_fields_read=['current_native_depth_mm'], RGB_read=False, GT_read=False, restored_read=False,
        aligned_depth=old_measurement.array_binding(depth), aligned_source_index=old_measurement.array_binding(index),
        native_depth=old_measurement.array_binding(native))
    return old_measurement.measure_region(depth, index, native, masks, masks[role], 'synthetic_ds26', 1, 0, 0.,
        source_binding=binding, expected_source_binding=binding)


def check():
    passed = []
    arrays = fixture(); originals = [x.copy() for x in arrays[:3]]
    original_masks = {n: x.copy() for n, x in arrays[3].items()}
    a, ma = measure(arrays, 1); b, mb = measure(arrays, 2)
    sa, sb = summarize(a), summarize(b)
    assert a['status'] == b['status'] == 'UNKNOWN'
    assert a['reason'] == b['reason'] == 'EXACTLY_TWO_QUALIFIED_LOCAL_SUPPORTS_REQUIRED'
    assert sa['sole_proxy_eligible'] and sb['sole_proxy_eligible']
    assert sa['qualified_support_count'] == sb['qualified_support_count'] == 1
    result = pair_summary(a, ma, b, mb, arrays[1])
    assert result['pair_proxy_eligible'] and result['measured_depth_difference_mm'] == 200.
    assert result['measured_order'] == 'A_PROXY_NEARER' and result['identity_independence'] == 'UNKNOWN'
    assert result['propagated_sigma_mm'] > 0 and result['standardized_difference'] > 0
    assert all(np.array_equal(x, y) for x, y in zip(arrays[:3], originals))
    assert all(np.array_equal(arrays[3][n], original_masks[n]) for n in original_masks)
    assert all(sa['parent_gates'].values()) and not result.get('veto', False)
    passed.append('actual_DS25_single_layer_UNKNOWN_is_diagnostic_sole_proxy_not_identity')

    arrays = fixture()
    arrays[1][arrays[3][2]] = arrays[1][arrays[3][1]]
    arrays[0][arrays[3][2]] = 1100.
    a, ma = measure(arrays, 1); b, mb = measure(arrays, 2)
    result = pair_summary(a, ma, b, mb, arrays[1])
    assert summarize(a)['sole_proxy_eligible'] and summarize(b)['sole_proxy_eligible']
    assert result['source_overlaps']['qualified_native_sources']['n'] == 1200
    assert result['source_overlaps']['inclusive_raw_native_sources']['n'] == 1200
    assert not result['pair_proxy_eligible'] and result['identity_independence'] == 'UNKNOWN'
    assert result['measured_depth_difference_mm'] is result['standardized_difference'] is None
    assert result['reason'] == 'QUALIFIED_NATIVE_SOURCE_REUSED_BY_BOTH_ROLES'
    passed.append('same_native_sources_in_two_roles_are_not_double_independent_evidence')

    arrays = fixture(); arrays[0][arrays[3][2]] = 1500.
    fact, maps = measure(arrays, 2); summary = summarize(fact)
    assert not summary['sole_proxy_eligible']
    assert any(x['background_compatibility'] == 'BACKGROUND_COMPATIBLE' for x in summary['layers'])
    assert summary['layers'] == fact['layers']
    passed.append('background_compatible_support_is_retained_without_foreground_claim')

    arrays = fixture()
    arrays[0][120:121, 260:270] = 900.
    arrays[0][125:130, 260:262] = np.nan; arrays[1][125:130, 260:262] = -1
    fact, maps = measure(arrays, 1); summary = summarize(fact)
    assert any(x['kind'] == 'MISSING_DEPTH' for x in summary['layers'])
    assert any(x['kind'] == 'MEASURED_DEPTH_SUPPORT' and x['independent_n'] == 10 and not x['qualified']
        for x in summary['layers'])
    assert summary['layers'] == fact['layers'] and summary['original_roi_missing_n'] == 10
    passed.append('minor_weak_and_missing_depth_components_remain_in_diagnostic')

    arrays = fixture(); a, ma = measure(arrays, 1); b, mb = measure(arrays, 2)
    changed = copy.deepcopy(a); changed['layers'][0]['z_mm'] += 1.
    try: summarize(changed)
    except AssertionError: pass
    else: raise AssertionError('Changed producer fact was accepted')
    changed_index = arrays[1].copy(); changed_index[0, 0] = 10
    try: pair_summary(a, ma, b, mb, changed_index)
    except AssertionError: pass
    else: raise AssertionError('Wrong source-index array was accepted')
    changed = copy.deepcopy(ma)
    sid = a['qualified_support_ids'][0]
    changed['selected_positions'][sid][0] = 0
    try: pair_summary(a, changed, b, mb, arrays[1])
    except AssertionError: pass
    else: raise AssertionError('Source point outside actual role support was accepted')
    passed.append('producer_fact_index_and_private_support_corruption_rejected')
    return dict(status='PASS', checks=passed, synthetic_only=True, GT_read=False,
        new_model_http=0, identity_replay=False, pixels_serialized=False)


if __name__ == '__main__':
    print(json.dumps(check(), ensure_ascii=False, indent=2))
