"""Actual fixed-source repeat diagnosis; frozen v1 outputs remain read-only."""
from pathlib import Path
import hashlib
import json
import sys
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run
from spatial import spatial_metrics
import cv2
import numpy as np


def binding(array):
    value = np.ascontiguousarray(array)
    return dict(shape=list(value.shape), dtype=str(value.dtype),
        sha256=hashlib.sha256(value.tobytes()).hexdigest())


def difference(left, right, mask, boundary):
    equal = np.equal(left, right)
    if np.issubdtype(left.dtype, np.floating):
        equal |= np.isnan(left) & np.isnan(right)
    mismatch = ~equal
    finite = np.isfinite(left) & np.isfinite(right)
    delta = np.abs(left[finite].astype('f8') - right[finite].astype('f8'))
    result = dict(dtype=str(left.dtype), total_pixel_n=int(left.size),
        exact_equal=bool(equal.all()), mismatch_n=int(mismatch.sum()),
        mask_mismatch_n=int((mismatch & mask).sum()),
        boundary_mismatch_n=int((mismatch & boundary).sum()),
        max_abs_difference=float(delta.max(initial=0.)),
        nonfinite_pattern_equal=bool(np.array_equal(np.isfinite(left), np.isfinite(right))))
    if left.dtype == np.float32:
        bits_a, bits_b = left.view('u4').astype('i8'), right.view('u4').astype('i8')
        result['max_float32_ULP_difference'] = int(np.abs(bits_a[finite] - bits_b[finite]).max(initial=0))
    return result


def main():
    run.verify_freeze()
    cv2.setNumThreads(1)
    records = list(run.old.rows(HERE / 'ENDPOINTS.jsonl.gz'))
    assert records
    chosen = [records[0], records[-1]] if len(records) > 1 else records
    features = run.prior.load_features()
    facts, assignments, pins = run.prior.load_sources(features)
    diagnostics = []
    for entry in chosen:
        fid = entry['fact_id']
        fact = facts[fid]
        sensor = run.RawDepth(fact['segment'])
        try:
            frame = run.prior.load_endpoint_frame(fact['segment'], fact['frame'], facts, assignments, sensor)
            rgb, rgb_binding = run.rgb_frame(sensor, frame)
        finally:
            sensor.close()
        mask = frame['masks'][fact['native']]
        inputs_before = [binding(x) for x in (mask, frame['depth'], rgb)]
        baseline, maps = spatial_metrics(mask, frame['depth'], rgb)
        assert baseline == entry['spatial'], 'Reopened actual input differs from partial frozen record'
        repeats = []
        for repeat in range(12):
            measured, current = spatial_metrics(mask, frame['depth'], rgb)
            repeats.append(dict(repeat=repeat + 1, numeric_metrics_exact_equal=measured == baseline,
                maps={key: difference(maps[key], current[key], mask, maps['mask_inner_boundary']) for key in maps}))
        assert inputs_before == [binding(x) for x in (mask, frame['depth'], rgb)], 'Actual inputs mutated'
        diagnostics.append(dict(fact_id=fid, actual_global_frame=fact['global_frame'],
            actual_local_frame=fact['frame'], native=fact['native'],
            original_record_matches_reopened_actual_metrics=True, actual_inputs_unchanged=True,
            input_array_bindings=dict(zip(('mask', 'depth', 'RGB_private'), inputs_before, strict=True)),
            raw_source_binding=frame['source_binding'], RGB_binding=rgb_binding,
            comparison='SAME_INPUT_VALUES_AND_GRID; SAME_FROZEN_CODE; THREADS_1; NO_TRANSFORM', repeats=repeats))
    changed = sorted({key for item in diagnostics for repeated in item['repeats']
        for key, diff in repeated['maps'].items() if not diff['exact_equal']})
    numeric_equal = all(r['numeric_metrics_exact_equal'] for item in diagnostics for r in item['repeats'])
    run.verify_freeze()
    run.save('NUMERIC_REPEAT_DIAGNOSIS.json', dict(
        status='ACTUAL_FIXED_SOURCE_FLOAT_REPEAT_DIAGNOSIS', frozen_v1=run.old.artifact(HERE / 'FREEZE.json'),
        partial_v1_endpoints=run.old.artifact(HERE / 'ENDPOINTS.jsonl.gz'),
        diagnosis_code=run.old.artifact(Path(__file__)), partial_endpoint_n=len(records),
        selected_first_and_last_partial_fact_ids=[item['fact_id'] for item in chosen],
        actual_cv2_threads=cv2.getNumThreads(), actual_cv2_optimized=cv2.useOptimized(),
        numeric_metrics_all_exact_equal=numeric_equal, changed_map_keys=changed,
        observed_change_confined_to_unrendered_distance_maps=bool(changed) and set(changed) <= {'depth_distance_px', 'rgb_distance_px'},
        only_rendered_private_arrays=('depth_edges', 'rgb_edges'),
        diagnostics=diagnostics, old_frozen_files_unchanged=True,
        no_new_measurement_rules=True, no_new_identity_state=True, no_model_HTTP=True,
        model_HTTP_n=0, cost_usd=0, no_GT=True, no_future_or_shift_search=True))
    print(json.dumps(dict(partial_endpoint_n=len(records), actual_fact_n=len(diagnostics),
        numeric_metrics_all_exact_equal=numeric_equal, changed_map_keys=changed), allow_nan=False))


if __name__ == '__main__':
    main()
