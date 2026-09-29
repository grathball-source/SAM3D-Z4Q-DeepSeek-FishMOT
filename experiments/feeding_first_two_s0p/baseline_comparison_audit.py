"""Audit the sealed FEEDING replay against the archived SAM3 baseline inputs.

This reads existing predictions and labels; it does not rerun the tracker or API.
"""
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

import numpy as np

import score
from prepare import DATA, HERE, RAW, SEGMENTS, digest, prediction_masks


BASE = Path('E:/CAU/D-MOT/output/evaluation/sam3_feeding_20260928_v2')
RESULT = HERE / 'baseline_comparison_audit' / 'AUDIT.json'
ARMS = ('SAM3_same_input', 'B0', 'B-HOLD', 'B-VLM')


def evaluate(gt, ids, sims):
    data = score.original_score.metric_data(gt, ids, sims)
    objects = [score.trackeval.metrics.HOTA({'PRINT_CONFIG': False}),
               score.trackeval.metrics.CLEAR({'THRESHOLD': .5, 'PRINT_CONFIG': False}),
               score.trackeval.metrics.Identity({'THRESHOLD': .5, 'PRINT_CONFIG': False})]
    details = {obj.get_name(): obj.eval_sequence(data) for obj in objects}
    h, c, i = (details[key] for key in ('HOTA', 'CLEAR', 'Identity'))
    summary = dict(IDF1=100 * float(i['IDF1']), HOTA=100 * float(np.mean(h['HOTA'])),
                   AssA=100 * float(np.mean(h['AssA'])), DetA=100 * float(np.mean(h['DetA'])),
                   IDSW=int(c['IDSW']), FP=int(c['CLR_FP']), FN=int(c['CLR_FN']),
                   GT=int(data['num_gt_dets']), predictions=int(data['num_tracker_dets']))
    return summary, details, objects


def combine(details_by_segment, objects):
    result = {obj.get_name(): obj.combine_sequences(
        {name: details[obj.get_name()] for name, details in details_by_segment.items()})
        for obj in objects}
    h, c, i = (result[key] for key in ('HOTA', 'CLEAR', 'Identity'))
    return dict(IDF1=100 * float(i['IDF1']), HOTA=100 * float(np.mean(h['HOTA'])),
                AssA=100 * float(np.mean(h['AssA'])), DetA=100 * float(np.mean(h['DetA'])),
                IDSW=int(c['IDSW']), FP=int(c['CLR_FP']), FN=int(c['CLR_FN']))


def main():
    protocol = json.loads((BASE / 'protocol.json').read_text(encoding='utf-8'))
    baseline_script = Path('E:/CAU/D-MOT/tools/annotation/evaluate_feeding_saved.py')
    assert digest(baseline_script) == protocol['script_sha256']
    assert digest(score.original_score.DEPS / 'trackeval/metrics/clear.py') == protocol['official_trackeval_CLEAR_sha256']
    with (BASE / 'metrics.csv').open(encoding='utf-8-sig') as stream:
        archived = {int(row['sequence'].split('_')[1]): row for row in csv.DictReader(stream)
                    if row['mode'] == 'mask' and row['sequence'].startswith('FEEDING_')}
    pred_digest, gt_digest = hashlib.sha256(), hashlib.sha256()
    for item in protocol['segments']:
        start, stop = item['range']
        source = Path(item['prediction_dir'])
        for frame in range(start, stop + 1):
            key = f'{frame:06d}'.encode() + b'\0'
            pred_digest.update(key + (source / f'{frame:06d}.json').read_bytes())
            gt_digest.update(key + (DATA / 'labels_source' / f'{frame:06d}.json').read_bytes())
    assert pred_digest.hexdigest() == protocol['prediction_input_sha256']
    assert gt_digest.hexdigest() == protocol['reference_input_sha256']
    old_metrics = json.loads((HERE / 'run/METRICS.json').read_text(encoding='utf-8'))
    result = dict(status='READ_ONLY_RESCORING', frames=405,
                  audit_script_sha256=digest(Path(__file__)),
                  old_score_script_sha256=digest(HERE / 'score.py'),
                  old_metrics_sha256=digest(HERE / 'run/METRICS.json'),
                  old_seal_sha256={name: digest(HERE / 'run' / name / 'public/PREDICTIONS_SEALED.json')
                                   for name in SEGMENTS},
                  archived_baseline_protocol_sha256=digest(BASE / 'protocol.json'),
                  archived_baseline_script_sha256=digest(baseline_script),
                  source_mismatch={}, segment_metrics={}, pooled_metrics={},
                  canonical_1920_archived={}, resolution_delta={})
    pooled_truth = []
    pooled_sims = {kind: [] for kind in ('old', 'canonical')}
    pooled_ids = {kind: {arm: [] for arm in (ARMS if kind == 'old' else ('SAM3_canonical',))}
                  for kind in ('old', 'canonical')}
    details = {kind: {} for kind in ('old', 'canonical')}
    objects = None
    for segment_index, (name, (start, stop)) in enumerate(SEGMENTS.items()):
        score.checked_segment(HERE / 'run', name, start, stop)
        canonical_dir = Path(protocol['segments'][segment_index]['prediction_dir'])
        assert protocol['segments'][segment_index]['range'] == [start, stop]
        baseline_manifest = json.loads(Path(protocol['segments'][segment_index]['prediction_manifest']).read_text(encoding='utf-8'))
        baseline_rows = {row['frame']: row for row in baseline_manifest['frames']}
        data_rows = {row['frame']: row for row in map(json.loads, (DATA / 'manifest.jsonl').read_text(encoding='utf-8').splitlines())}
        sources = json.loads((HERE / 'private' / name / 'sources.json').read_text(encoding='utf-8'))
        truth, sims_old, sims_canonical = [], [], []
        predictions_old = {arm: [] for arm in ARMS}
        predictions_canonical = []
        changed_files = changed_instance_count = 0
        old_detection_count = canonical_detection_count = 0
        old_gt_exact_parts = canonical_gt_exact_parts = gt_parts = 0
        for local, (assignment, published) in enumerate(zip(
                score.records(HERE / 'private' / name / 'assignments.jsonl.gz'),
                score.records(HERE / 'run' / name / 'public/predictions.jsonl.gz'), strict=True), 1):
            frame = start + local - 1
            assert assignment['global_frame_id'] == published['global_frame'] == frame
            assert data_rows[frame]['source_rgb_sha256'] == baseline_rows[frame]['rgb_sha256']
            old_file, canonical_file = RAW / f'{frame:06d}.json', canonical_dir / f'{frame:06d}.json'
            assert sources[local - 1]['prediction_sha256'] == digest(old_file)
            changed_files += digest(old_file) != digest(canonical_file)
            old_masks = [score.original_score.rle(assignment['masks'][item['mask']])
                         for item in assignment['variants']['N0']]
            old_ids = [int(item['id']) for item in assignment['variants']['N0']]
            canonical_shapes = json.loads(canonical_file.read_text(encoding='utf-8'))['shapes']
            canonical_masks_by_id, _ = prediction_masks(canonical_shapes)
            canonical_ids = sorted(canonical_masks_by_id)
            canonical_masks = [score.coco.encode(np.asfortranarray(canonical_masks_by_id[key]))
                               for key in canonical_ids]
            old_detection_count += len(old_ids)
            canonical_detection_count += len(canonical_ids)
            changed_instance_count += len(old_ids) != len(canonical_ids)
            gt_small = json.loads((DATA / 'labels_640x360' / f'{frame:06d}.json').read_text(encoding='utf-8'))
            gt_source = json.loads((DATA / 'labels_source' / f'{frame:06d}.json').read_text(encoding='utf-8'))
            assert digest(DATA / 'labels_source' / f'{frame:06d}.json') == data_rows[frame]['source_label_sha256']
            assert len(gt_small['shapes']) == len(gt_source['shapes'])
            def geometry(shapes):
                return Counter(json.dumps(shape['points'], separators=(',', ':')) for shape in shapes)
            gt_geometry = geometry(gt_source['shapes'])
            gt_parts += len(gt_source['shapes'])
            old_gt_exact_parts += sum((gt_geometry & geometry(json.loads(old_file.read_text(encoding='utf-8'))['shapes'])).values())
            canonical_gt_exact_parts += sum((gt_geometry & geometry(canonical_shapes)).values())
            for small, original in zip(gt_small['shapes'], gt_source['shapes'], strict=True):
                assert small['group_id'] == original['group_id']
                assert np.allclose(small['points'], (np.asarray(original['points']) + .5) / 3 - .5, atol=1e-9, rtol=0)
            gt_ids, gt_masks = score.mask_rles(gt_small['shapes'])
            truth.append(gt_ids)
            for kind, pred_masks, pred_ids, sims in (
                    ('old', old_masks, old_ids, sims_old),
                    ('canonical', canonical_masks, canonical_ids, sims_canonical)):
                matrix = (np.asarray(score.coco.iou(gt_masks, pred_masks, [0] * len(pred_masks)), float)
                          if gt_ids and pred_ids else np.zeros((len(gt_ids), len(pred_ids))))
                sims.append(matrix)
                pooled_sims[kind].append(matrix)
            predictions_old['SAM3_same_input'].append(old_ids)
            predictions_canonical.append(canonical_ids)
            for arm in ARMS[1:]:
                assert [item['mask'] for item in published['variants'][arm]] == [item['mask'] for item in assignment['variants']['N0']]
                predictions_old[arm].append([int(item['id']) for item in published['variants'][arm]])
            pooled_truth.append([identity + segment_index * 10_000_000 for identity in gt_ids])
            for arm in ARMS:
                pooled_ids['old'][arm].append([identity + segment_index * 10_000_000 for identity in predictions_old[arm][-1]])
            pooled_ids['canonical']['SAM3_canonical'].append([identity + segment_index * 10_000_000 for identity in canonical_ids])
        result['source_mismatch'][name] = dict(previous_source=str(RAW), canonical_baseline_source=str(canonical_dir),
                                               changed_files=changed_files, frames_with_different_instance_count=changed_instance_count,
                                               previous_detections=old_detection_count, canonical_detections=canonical_detection_count,
                                               reference_polygon_parts=gt_parts,
                                               previous_exact_geometry_parts=old_gt_exact_parts,
                                               canonical_exact_geometry_parts=canonical_gt_exact_parts)
        result['segment_metrics'][name] = {}
        for arm in ARMS:
            summary, raw, objects = evaluate(truth, predictions_old[arm], sims_old)
            result['segment_metrics'][name][arm] = summary
            details['old'].setdefault(arm, {})[name] = raw
            if arm != 'SAM3_same_input':
                expected = old_metrics['segment_metrics'][name][arm]
                for key, value in summary.items():
                    assert np.isclose(value, expected[key], atol=1e-10, rtol=0), (name, arm, key, value, expected[key])
        summary, raw, objects = evaluate(truth, predictions_canonical, sims_canonical)
        result['segment_metrics'][name]['SAM3_canonical'] = summary
        details['canonical'].setdefault('SAM3_canonical', {})[name] = raw
        original = archived[start]
        result['canonical_1920_archived'][name] = {key: float(original[key]) if key not in ('IDSW', 'FP', 'FN', 'GT_detections', 'predicted_detections') else int(original[key])
                                                     for key in ('IDF1', 'HOTA', 'AssA', 'DetA', 'IDSW', 'FP', 'FN', 'GT_detections', 'predicted_detections')}
        result['resolution_delta'][name] = {key: summary[key] - float(original[key]) for key in ('IDF1', 'HOTA', 'AssA', 'DetA')}
    for arm in ARMS:
        summary, _, _ = evaluate(pooled_truth, pooled_ids['old'][arm], pooled_sims['old'])
        result['pooled_metrics'][arm] = summary
        combined = combine(details['old'][arm], objects)
        for key, value in combined.items():
            assert np.isclose(value, summary[key], atol=1e-9, rtol=0), (arm, key, value, summary[key])
        if arm != 'SAM3_same_input':
            for key, value in summary.items():
                assert np.isclose(value, old_metrics['pooled_metrics'][arm][key], atol=1e-10, rtol=0)
    summary, _, _ = evaluate(pooled_truth, pooled_ids['canonical']['SAM3_canonical'], pooled_sims['canonical'])
    result['pooled_metrics']['SAM3_canonical'] = summary
    combined = combine(details['canonical']['SAM3_canonical'], objects)
    for key, value in combined.items():
        assert np.isclose(value, summary[key], atol=1e-9, rtol=0), (key, value, summary[key])
    result['checks'] = dict(old_seals_verified=True, old_scores_reproduced=True,
                            segment_namespace_equals_trackeval_combine=True,
                            gt_640_points_match_source_pixel_center_transform=True,
                            baseline_evaluator_and_trackeval_hash_match=True,
                            baseline_prediction_and_reference_hash_match=True,
                            dataset_manifest_rgb_and_label_hash_match=True)
    if RESULT.exists():
        assert json.loads(RESULT.read_text(encoding='utf-8')) == result, 'Existing audit differs; preserve it and investigate'
    else:
        RESULT.parent.mkdir(parents=True, exist_ok=True)
        with RESULT.open('x', encoding='utf-8', newline='\n') as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write('\n')
    print(json.dumps(dict(mismatch=result['source_mismatch'], pooled=result['pooled_metrics']), ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
