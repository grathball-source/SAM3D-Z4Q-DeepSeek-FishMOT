"""Effective thresholds, isolation, and actual old-endpoint exact parity checks."""
from common import *
import copy
import numpy as np
from measurement import Measurement, _original


def _maps_equal(first, second):
    assert first.keys() == second.keys()
    for key in first:
        if isinstance(first[key], dict):
            _maps_equal(first[key], second[key])
        else:
            assert np.array_equal(first[key], second[key], equal_nan=True), key


def run_checks():
    source_checks = module('ds27_readonly_ds25_source_checks',
        ROOT / 'experiments/ds25_contact_local_layers/source_checks.py')
    before = [copy.deepcopy(m.PARAMETERS) for m in (_original, _original._background, _original._layers)]
    measurements = {arm:Measurement(policy) for arm,policy in VARIANTS.items()}
    assert len({id(m._layers) for m in measurements.values()}) == 4
    assert len({id(m._background) for m in measurements.values()}) == 4
    assert len({id(m.measure_region.__globals__) for m in measurements.values()}) == 4
    passed = []
    for offsets, missing in (((-400., -200.), False), ((-200., 0.), False),
            ((-20., -200.), False), ((-400., -200.), True)):
        arrays = source_checks._fixture(offsets)
        if missing:
            arrays[0][125:130,270:275] = np.nan
            arrays[1][125:130,270:275] = -1
        binding = source_checks._binding(_original, arrays)
        args = (*arrays, 'synthetic_source', 1, 0, 0.)
        old, old_maps = _original.measure_region(*args, source_binding=binding, expected_source_binding=binding)
        outputs = {}
        for arm, m in measurements.items():
            fact, maps = m.measure_region(*args, source_binding=binding, expected_source_binding=binding)
            outputs[arm] = fact
            assert fact['parameters'] == m.PARAMETERS and m.PARAMETERS['layer_gap_mm'] == 30.
            assert fact['foreground_identity'] == fact['identity'] == fact['physical_fish_count'] == 'UNKNOWN'
            assert fact['plane']['residual_scale_mm'] == VARIANTS[arm]['scale_floor_mm']
            assert fact['plane']['contrast_threshold_mm'] == max(
                VARIANTS[arm]['contrast'][0], VARIANTS[arm]['contrast'][1]*VARIANTS[arm]['scale_floor_mm'])
            assert fact['plane']['physical_accuracy_mm'] == 'UNKNOWN'
            assert len(fact['layers']) == len(old['layers']), 'Thresholds removed raw supports'
            if missing:
                absent = [x for x in fact['layers'] if x['kind'] == 'MISSING_DEPTH']
                assert len(absent) == 1 and absent[0]['inclusive_n'] == 25
                assert absent[0]['z_mm'] is None and absent[0]['qualified'] is False
            if arm == 'SOFT_C0_S15':
                assert fact == old, 'Old-level synthetic numeric facts differ'
                _maps_equal(maps, old_maps)
            assert m._layers._stats(np.array([700.,700.,700.]),3)['scale_mm'] == VARIANTS[arm]['scale_floor_mm']
        if offsets[0] == -20.:
            assert len(outputs['SOFT_C0_S15']['qualified_support_ids']) == 1
            assert len(outputs['SOFT_C1_S5']['qualified_support_ids']) == 2
        assert [m.PARAMETERS for m in (_original, _original._background, _original._layers)] == before
    passed += ['all_four_actual_summary_and_IRLS_floor_levels_effective',
        'contrast_levels_actually_effective', 'old_level_synthetic_facts_and_all_maps_exact',
        'private_global_bindings_no_shared_parameter_write', 'all_weak_background_and_missing_supports_retained']

    raw_source = module('ds27_measurement_check_raw_source',
        ROOT / 'experiments/ds16_relative_depth_order/source.py')
    RawDepth, native_masks = raw_source.RawDepth, raw_source.native_masks
    ds26 = ROOT / 'experiments/ds26_phase_roi_observability/run'
    pre = [p for p in rows(ds26/'PAIRINGS.jsonl.gz') if p['phase'].startswith('PRE')]
    pair = min(pre, key=lambda p:(list(SEGMENTS).index(p['segment']),p['frame'],p['task_id']))
    role = 'A'; segment, frame, native_id = pair['segment'], pair['frame'], pair['native_roles'][role]
    assert (segment, frame, native_id) == ('feeding_000351_000555',14,30)
    oldfact = next(f for f in rows(ds26/'ENDPOINT_FACTS.jsonl.gz') if f['fact_id'] == pair['role_facts'][role]['fact_id'])
    assignment = next(r for r in rows(input_dir(segment)/'assignments.jsonl.gz') if r['frame'] == frame)
    saved = next(r for r in rows(input_dir(segment)/'DEPTH_OBSERVATIONS.jsonl.gz') if r['frame'] == frame)
    sensor = RawDepth(segment)
    try:
        depth,index,native,binding = sensor(saved['global_frame'],saved['time'])
        assert binding == saved['raw_source_binding'] == oldfact['source_binding']
        masks = native_masks(assignment)
        args = (depth,index,native,masks,masks[native_id],segment,frame,saved['global_frame'],saved['time'])
        expected,maps = _original.measure_region(*args,source_binding=binding,expected_source_binding=saved['raw_source_binding'])
        actual,newmaps = measurements['SOFT_C0_S15'].measure_region(*args,source_binding=binding,expected_source_binding=saved['raw_source_binding'])
        assert actual == expected == oldfact, 'True old PRE endpoint must reproduce all original sealed facts'
        _maps_equal(maps,newmaps)
        lowered,_ = measurements['SOFT_C0_S5'].measure_region(*args,source_binding=binding,expected_source_binding=saved['raw_source_binding'])
        assert lowered['plane']['residual_scale_mm'] < actual['plane']['residual_scale_mm']
        assert lowered['parameters']['scale_floor_mm'] == 5.
        assert [m.PARAMETERS for m in (_original, _original._background, _original._layers)] == before
    finally:
        sensor.close()
    passed += ['actual_first_PRE_endpoint_sealed_fact_and_maps_exact', 'actual_lower_floor_changes_real_measurement']
    return dict(status='PASS', checks=passed, real_fixture=dict(segment=segment, frame=frame,
        global_frame=saved['global_frame'],native=native_id, old_fact_sha256=digest(oldfact),
        old_background_scale_mm=actual['plane']['residual_scale_mm'],
        revised_background_scale_mm=lowered['plane']['residual_scale_mm']),
        model_http=0,cost_usd=0,GT_read=False,RGB_read=False,synthetic_not_research_success=True)


if __name__ == '__main__':
    print(json.dumps(run_checks(),ensure_ascii=False))
