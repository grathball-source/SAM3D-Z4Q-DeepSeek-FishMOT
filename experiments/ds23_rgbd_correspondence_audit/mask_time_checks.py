"""Read-only fixed endpoint mask/frame provenance checks; no RGB or GT pixels."""
from collections import Counter, defaultdict
from pathlib import Path
import importlib.util, json, sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / 'experiments/ds22_local_background_depth'))
spec = importlib.util.spec_from_file_location('ds22_mask_source', ROOT / 'experiments/ds22_local_background_depth/run.py')
ds22 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ds22)
import numpy as np
from source import native_masks, polygon_masks, original_sources
from mixed_depth import array_binding


def main():
    old = ds22.old
    features = ds22.load_features()
    facts, assignments, source_pins = ds22.load_sources(features)
    frames = defaultdict(set)
    for fact in facts.values(): frames[fact['segment']].add(fact['frame'])
    out, pins, summaries = [], {}, []
    def pin(path):
        value = old.artifact(path); pins[value['path']] = value
        return value
    for segment in old.SEGMENTS:
        source = original_sources(segment)
        family = 'FEEDING' if segment.startswith('feeding_') else 'FISHSA' if segment.startswith('fishsa_') else segment
        if family == 'FEEDING':
            path = old.DATA / 'manifest.jsonl'
            metadata = {r['frame']: r for r in old.rows(path)}
        elif family == 'FISHSA':
            path = old.WORK / 'data/AlignedDataset_v1/manifest.jsonl'
            metadata = {r['source_color_index'] + 1: r for r in old.rows(path)}
        else:
            path = source['manifest']
            metadata = {r['frame']: r for r in old.read(path)['frames']}
        metadata_pin = pin(path)
        if family == 'FISHSA':
            original_path = source['assignments']; original_pin = pin(original_path)
            originals = {r['frame']: r for r in old.rows(original_path) if r['frame'] in frames[segment]}
            assert set(originals) == frames[segment]
        mask_count = 0
        for frame in sorted(frames[segment]):
            relevant = [f for f in facts.values() if (f['segment'], f['frame']) == (segment, frame)]
            fact = relevant[0]; g = fact['global_frame']; time = fact['time']
            row = metadata[g]; assignment = assignments[segment][frame]
            assert (assignment['frame'], assignment['global_frame_id'], assignment['time']) == (frame, g, time)
            assert g == old.SEGMENTS[segment][0] + frame - 1
            color_us = row['color_timestamp_us'] if family == 'FISHSA' else row['rgb_timestamp_us']
            depth_us = row['depth_timestamp_us']
            assert row['delta_us'] == color_us - depth_us
            assert abs(time - color_us / 1e6) < 1e-6
            masks = native_masks(assignment)
            if family == 'FEEDING':
                original_path = old.WORK / 'data/AnnotationFeeding_20260924/ML/labels_raw' / f'{g:06d}.json'
            elif family == 'FISHSA':
                original_assignment = originals[frame]
                assert original_assignment['frame'] == frame and original_assignment['time'] == time
                assert original_assignment.get('global_frame_id', g) == g
                expected = native_masks(original_assignment)
            else:
                original_path = Path(source['manifest']).parent / 'labels_raw' / f'{g:06d}.json'
            if family != 'FISHSA':
                original_pin = pin(original_path)
                document = old.read(original_path)
                assert (document['imageWidth'], document['imageHeight']) == (1920, 1080)
                assert Path(document['imagePath']).name == f'{g:06d}.jpg'
                expected, _ = polygon_masks(document['shapes'])
            assert masks.keys() == expected.keys(), (segment, frame, 'NATIVE_SET_CHANGED')
            for native in masks:
                assert masks[native].shape == (360, 640)
                assert np.array_equal(masks[native], expected[native]), (segment, frame, native, 'MASK_CHANGED')
            for f in relevant:
                assert array_binding(masks[f['native']]) == f['certificate']['mask_binding']
            mask_count += len(masks)
            measured = fact['_raw_measurement']['raw_source_binding']
            assert measured['delta_us'] == row['delta_us']
            if family == 'FISHSA':
                assert (measured['source_color_index'], measured['aligned_frame_id'], measured['h5_row']) == (
                    row['source_color_index'], row['frame_id'], row['h5_row'])
                assert row['source_color_index'] + 1 == g
            out.append(dict(segment=segment, frame=frame, global_frame=g, endpoint_count=len(relevant),
                all_native_masks=len(masks), original_prediction=original_pin, metadata=metadata_pin,
                original_domain=[640, 360] if family == 'FISHSA' else [1920, 1080],
                effective_domain=[640, 360], conversion='EXACT_ORIGINAL_N0_RLE' if family == 'FISHSA' else
                'ONE_PIXEL_CENTER_SCALE_1_OVER_3; ROUND_VERTICES_THEN_FILLPOLY',
                timestamp_rgb_us=color_us, timestamp_depth_us=depth_us, delta_us=row['delta_us'],
                source_sensor_after_rgb_us=max(0, depth_us-color_us), original_mask_equal=True,
                same_original_RGB_frame=True, physical_correspondence='UNKNOWN'))
        selected = [r for r in out if r['segment'] == segment]
        summaries.append(dict(segment=segment, endpoints=sum(r['endpoint_count'] for r in selected),
            frames=len(selected), all_native_masks_rechecked=mask_count,
            delta_us_counts=dict(Counter(str(r['delta_us']) for r in selected)),
            depth_timestamp_after_rgb_frames=sum(r['source_sensor_after_rgb_us'] > 0 for r in selected),
            min_delta_us=min(r['delta_us'] for r in selected), max_delta_us=max(r['delta_us'] for r in selected),
            mask_differences=0, frame_binding_differences=0, timestamp_binding_differences=0))
    assert sum(r['endpoints'] for r in summaries) == 171 and len(out) == 168
    assert all(f['actual_anchor_time'] < f['current_time'] for f in features)
    value = dict(status='PASS_FIXED_MASK_FRAME_SOURCE_CONTRACT', endpoint_count=171, frames=168,
        summaries=summaries, frame_records=out, sources=list(pins.values()),
        imported_source=pin(Path(sys.modules['source'].__file__)),
        read_only_old=True, RGB_pixels_read=False, GT_read=False, labels_raw_only=True,
        inference_HTTP=0, cost_usd=0, no_new_predictions=True,
        physical_registered_accuracy='UNKNOWN; metadata/mask equality cannot certify optical alignment',
        temporal_policy='CURRENT_RECORDED_RGB_FRAME; ARCHIVED_NEAREST_SENSOR_PAIR_CAN_BE_MILLISECONDS_LATER; '
            'NOT_STRICT_SENSOR_CAUSAL_REALTIME; UPSTREAM_SAM3_LOOKAHEAD_NOT_CERTIFIED')
    old.write_new(HERE / 'MASK_TIME_CHECKS.json', value)
    print(json.dumps(dict(status=value['status'], endpoint_count=171, frames=168, summaries=summaries),
        ensure_ascii=False, indent=2), flush=True)


if __name__ == '__main__': main()
