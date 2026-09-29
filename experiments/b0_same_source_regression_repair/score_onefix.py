"""Verify every one-fix replay seal before independently opening ground truth."""
import gzip
import hashlib
import json
from pathlib import Path

from score import DATA, HERE, SEGMENTS, clear_step, coco, feeding, np, read, records
from source import save, sha


def verify_before_gt(manifest):
    summary = read(HERE / 'public/ONEFIX_RUN_SUMMARY.json')
    assert summary['status'] == 'ALL_SEALED_BEFORE_GT' and summary['model_http'] == 0
    assert summary['rule'] == 'NEW_HYPOTHESIS_CERTIFIED_NATIVE_GUARD'
    source_sha = sha(HERE / 'public/PREDICTION_SOURCE_MANIFEST.json')
    for source in ('SOURCE_OLD', 'SOURCE_BASELINE'):
        for name, (start, stop) in SEGMENTS.items():
            target = HERE / 'public' / source / name / 'onefix'
            seal = read(target / 'SEAL.json')
            assert sha(target / 'SEAL.json') == summary['sources'][source][name]['seal_sha256']
            assert seal['status'] == 'SEALED_BEFORE_GT' and seal['model_http'] == 0
            assert seal['frames'] == stop-start+1 and seal['source_manifest_sha256'] == source_sha
            assert seal['source'] == source and seal['segment'] == name
            for entry in (seal['prediction'], seal['actions'], seal['publication'],
                          *seal['input_derived'].values()):
                path = Path(entry['path'])
                assert path.stat().st_size == entry['bytes'] and sha(path) == entry['sha256']
            for path, expected in seal['code'].items():
                assert sha(path) == expected, path
            assert seal['input_derived'] == manifest['segments'][source][name]['derived']
            with gzip.open(seal['prediction']['path'], 'rt', encoding='utf-8') as pred, \
                 (target / 'PUBLISH_LEDGER.jsonl').open('r', encoding='utf-8') as pub:
                count = 0
                for count, (line, raw) in enumerate(zip(pred, pub, strict=True), 1):
                    item = json.loads(raw)
                    assert item['frame'] == count and item['original_frame'] == start+count-1
                    assert item['first_publish_monotonic'] >= item['received_monotonic']
                    assert hashlib.sha256(line.encode()).hexdigest() == item['prediction_row_sha256']
                assert count == stop-start+1
    return summary


def score_source(source, manifest):
    segment_metrics = {}
    switches = []
    pooled_gt, pooled_pred, pooled_sims = [], [], []
    matched_path = HERE / 'public' / source / 'ONEFIX_GT_MATCHED_LEDGER.jsonl'
    with matched_path.open('x', encoding='utf-8', newline='\n') as matched_file:
        for offset, (name, (start, stop)) in enumerate(SEGMENTS.items()):
            item = manifest['segments'][source][name]
            assignments = records(item['derived']['assignments']['path'])
            predictions = records(HERE / 'public' / source / name / 'onefix/PREDICTIONS.jsonl.gz')
            gt, pred, sims = [], [], []
            previous, previous_step = {}, {}
            local_switches = []
            for local, (assignment, publication) in enumerate(zip(assignments, predictions, strict=True), 1):
                frame = start+local-1
                assert assignment['frame'] == publication['frame'] == local
                assert assignment['global_frame_id'] == publication['original_frame'] == frame
                truth = read(DATA / 'labels_640x360' / f'{frame:06d}.json')
                gt_ids, gt_masks = feeding.mask_rles(truth['shapes'])
                mask_keys = [obj['mask'] for obj in assignment['variants']['N0']]
                assert mask_keys == publication['masks']
                native = [int(key.split(':')[1]) for key in mask_keys]
                assert publication['public'] == [dict(native_id=n, public_id=obj['public_id'], mask=f'n:{n}')
                                                 for n, obj in zip(native, publication['public'], strict=True)]
                ids = [obj['public_id'] for obj in publication['public']]
                assert len(ids) == len(set(ids)) and all(isinstance(n, int) for n in ids)
                mask_rles = [feeding.original_score.rle(assignment['masks'][key]) for key in mask_keys]
                similarity = (np.asarray(coco.iou(gt_masks, mask_rles, [0]*len(mask_rles)), float)
                              if gt_ids and mask_keys else np.zeros((len(gt_ids), len(mask_keys))))
                gt.append(gt_ids)
                pred.append(ids)
                sims.append(similarity)
                pooled_gt.append([g+offset*10_000_000 for g in gt_ids])
                pooled_pred.append([p+offset*10_000_000 for p in ids])
                pooled_sims.append(similarity)
                previous_step, matches, new_switches = clear_step(
                    gt_ids, mask_keys, ids, similarity, previous, previous_step, frame)
                local_switches.extend(new_switches)
                switches.extend([dict(event, segment=name) for event in new_switches])
                matched_file.write(json.dumps(dict(source=source, segment=name, original_frame=frame,
                    local_frame=local, matches=matches), ensure_ascii=False, separators=(',', ':')) + '\n')
            segment_metrics[name] = feeding.metrics(gt, pred, sims)
            assert segment_metrics[name]['IDSW'] == len(local_switches)
    pooled = feeding.metrics(pooled_gt, pooled_pred, pooled_sims)
    assert pooled['IDSW'] == len(switches)
    return dict(segment=segment_metrics, pooled=pooled), switches, matched_path


def main():
    manifest = read(HERE / 'public/PREDICTION_SOURCE_MANIFEST.json')
    summary = verify_before_gt(manifest)
    frozen = read(HERE / 'public/FROZEN_METRICS.json')
    scores, switch_ledger, matched_files = {}, {}, {}
    for source in ('SOURCE_OLD', 'SOURCE_BASELINE'):
        scores[source], switch_ledger[source], path = score_source(source, manifest)
        matched_files[source] = dict(path=str(path), bytes=path.stat().st_size, sha256=sha(path))
    output = {}
    for source in scores:
        native = frozen['metrics'][source]['pooled']['NATIVE']
        old = frozen['metrics'][source]['pooled']['Z4Q_FROZEN']
        fixed = scores[source]['pooled']
        output[source] = dict(segment={name: dict(
            NATIVE=frozen['metrics'][source]['segment'][name]['NATIVE'],
            Z4Q_FROZEN=frozen['metrics'][source]['segment'][name]['Z4Q_FROZEN'],
            Z4Q_ONEFIX=scores[source]['segment'][name]) for name in SEGMENTS},
            pooled=dict(NATIVE=native, Z4Q_FROZEN=old, Z4Q_ONEFIX=fixed),
            onefix_minus_native={key: fixed[key]-native[key] for key in fixed},
            onefix_minus_frozen={key: fixed[key]-old[key] for key in fixed})
    save(HERE / 'public/ONEFIX_SWITCH_LEDGER.json', dict(status='POSTSEAL_CLEAR_EXACT',
        source=switch_ledger, gt_match_ledger=matched_files))
    save(HERE / 'public/ONEFIX_METRICS.json', dict(status='ALL_ONEFIX_SEALS_VERIFIED_BEFORE_GT',
        metrics=output, onefix_run_summary_sha256=sha(HERE / 'public/ONEFIX_RUN_SUMMARY.json'),
        frozen_metrics_sha256=sha(HERE / 'public/FROZEN_METRICS.json'),
        scorer_sha256=sha(Path(__file__)), model_http=0,
        gt_source='AlignedFeeding_v1/labels_640x360; edited checked=false'))
    print(json.dumps({source: output[source]['pooled'] for source in output}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
