"""Postseal same-source TrackEval scores and exact CLEAR switch decomposition."""
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path

from source import DATA, HERE, ROOT, SEGMENTS, save, sha

spec = importlib.util.spec_from_file_location('feeding_frozen_scorer',
    ROOT / 'experiments/feeding_first_two_s0p/score.py')
feeding = importlib.util.module_from_spec(spec)
spec.loader.exec_module(feeding)
from scipy.optimize import linear_sum_assignment  # noqa: E402

np = feeding.np
coco = feeding.coco
ARMS = ('NATIVE', 'Z4Q_FROZEN')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def records(path):
    with gzip.open(path, 'rt', encoding='utf-8') as handle:
        yield from map(json.loads, handle)


def verify_before_gt(manifest):
    summary = read(HERE / 'public/TRACE_RUN_SUMMARY.json')
    assert summary['status'] == 'ALL_SEALED_BEFORE_GT'
    assert summary['source_manifest_sha256'] == sha(HERE / 'public/PREDICTION_SOURCE_MANIFEST.json')
    for source in ('SOURCE_OLD', 'SOURCE_BASELINE'):
        for name, (start, stop) in SEGMENTS.items():
            target = HERE / 'public' / source / name
            seal = read(target / 'PREDICTIONS_SEALED.json')
            assert sha(target / 'PREDICTIONS_SEALED.json') == summary['seals'][source][name]
            assert seal['status'] == 'SEALED_NO_GT_OPEN' and seal['frames'] == stop-start+1
            assert seal['http_attempts'] == 0 and seal['passthrough_equals_native']
            assert seal['input_manifest_sha256'] == summary['source_manifest_sha256']
            for entry in (seal['prediction'], seal['actions'], seal['publication'], *seal['input_derived'].values()):
                path = Path(entry['path'])
                assert path.stat().st_size == entry['bytes'] and sha(path) == entry['sha256']
            for path, expected in seal['code'].items():
                assert sha(path) == expected, path
            with gzip.open(seal['prediction']['path'], 'rt', encoding='utf-8') as pred, \
                 (target / 'PUBLISH_LEDGER.jsonl').open('r', encoding='utf-8') as pub:
                count = 0
                for count, (line, raw) in enumerate(zip(pred, pub, strict=True), 1):
                    item = json.loads(raw)
                    assert item['frame'] == count and item['original_frame'] == start+count-1
                    assert item['first_publish_monotonic'] >= item['received_monotonic']
                    assert hashlib.sha256(line.encode()).hexdigest() == item['prediction_row_sha256']
                assert count == stop-start+1
            assert manifest['segments'][source][name]['prediction_dir'] == seal['source_prediction_dir']
    return summary


def clear_step(gt_ids, mask_keys, tracker_ids, similarity, previous, previous_step, frame):
    now, matches, switches = {}, [], []
    if gt_ids and tracker_ids:
        matrix = (1000 * np.asarray([[tracker_ids[j] == previous_step.get(g)
                                      for j in range(len(tracker_ids))] for g in gt_ids], float)
                  + similarity)
        matrix[similarity < .5 - np.finfo(float).eps] = 0
        rr, cc = linear_sum_assignment(-matrix)
        for i, j in zip(rr, cc):
            if matrix[i, j] <= np.finfo(float).eps:
                continue
            gt, current = gt_ids[i], tracker_ids[j]
            old = previous.get(gt)
            item = dict(frame=frame, gt_id=gt, native_mask=mask_keys[j],
                        native_id=int(mask_keys[j].split(':')[1]), public_id=current,
                        matched_iou=float(similarity[i, j]))
            matches.append(item)
            if old is not None and old != current:
                switches.append(dict(item, from_public_id=old, to_public_id=current))
            now[gt] = current
            previous[gt] = current
    return now, matches, switches


def score_source(source, manifest):
    segment_metrics = {}
    switches = {arm: [] for arm in ARMS}
    pooled_gt, pooled_sims = [], []
    pooled_pred = {arm: [] for arm in ARMS}
    matched_path = HERE / 'public' / source / 'GT_MATCHED_LEDGER.jsonl'
    with matched_path.open('x', encoding='utf-8', newline='\n') as match_file:
        for offset, (name, (start, stop)) in enumerate(SEGMENTS.items()):
            item = manifest['segments'][source][name]
            assignments = records(item['derived']['assignments']['path'])
            predictions = records(HERE / 'public' / source / name / 'PREDICTIONS.jsonl.gz')
            gt, sims = [], []
            pred = {arm: [] for arm in ARMS}
            previous = {arm: {} for arm in ARMS}
            previous_step = {arm: {} for arm in ARMS}
            local_switches = {arm: [] for arm in ARMS}
            for local, (assignment, publication) in enumerate(zip(assignments, predictions, strict=True), 1):
                frame = start+local-1
                assert assignment['frame'] == publication['frame'] == local
                assert assignment['global_frame_id'] == publication['original_frame'] == frame
                reference_path = DATA / 'labels_640x360' / f'{frame:06d}.json'
                truth = json.loads(reference_path.read_text(encoding='utf-8'))
                gt_ids, gt_masks = feeding.mask_rles(truth['shapes'])
                mask_keys = [obj['mask'] for obj in assignment['variants']['N0']]
                assert mask_keys == publication['masks']
                mask_rles = [feeding.original_score.rle(assignment['masks'][key]) for key in mask_keys]
                similarity = (np.asarray(coco.iou(gt_masks, mask_rles, [0]*len(mask_rles)), float)
                              if gt_ids and mask_keys else np.zeros((len(gt_ids), len(mask_keys))))
                gt.append(gt_ids)
                sims.append(similarity)
                pooled_gt.append([g+offset*10_000_000 for g in gt_ids])
                pooled_sims.append(similarity)
                record = dict(source=source, segment=name, original_frame=frame, local_frame=local, matches={})
                for arm in ARMS:
                    mapping = {int(k): int(v) for k, v in publication['variants'][arm].items()}
                    ids = [mapping[int(key.split(':')[1])] for key in mask_keys]
                    assert len(ids) == len(set(ids))
                    pred[arm].append(ids)
                    pooled_pred[arm].append([p+offset*10_000_000 for p in ids])
                    previous_step[arm], matches, new_switches = clear_step(
                        gt_ids, mask_keys, ids, similarity, previous[arm], previous_step[arm], frame)
                    record['matches'][arm] = matches
                    local_switches[arm].extend(new_switches)
                    switches[arm].extend([dict(event, segment=name) for event in new_switches])
                match_file.write(json.dumps(record, ensure_ascii=False, separators=(',', ':')) + '\n')
            segment_metrics[name] = {arm: feeding.metrics(gt, pred[arm], sims) for arm in ARMS}
            for arm in ARMS:
                assert segment_metrics[name][arm]['IDSW'] == len(local_switches[arm])
    pooled = {arm: feeding.metrics(pooled_gt, pooled_pred[arm], pooled_sims) for arm in ARMS}
    for arm in ARMS:
        assert pooled[arm]['IDSW'] == len(switches[arm])
    return dict(segment=segment_metrics, pooled=pooled), switches, matched_path


def link_actions(source, switches):
    ledgers = {}
    for name in SEGMENTS:
        path = HERE / 'public' / source / name / 'B0_ACTION_LEDGER.jsonl'
        ledgers[name] = {row['original_frame']: row for row in map(json.loads, path.read_text(encoding='utf-8').splitlines())}
    def annotate(event):
        row = ledgers[event['segment']][event['frame']]
        native = event['native_id']
        current_events = row['trace'].get('events', [])
        related = []
        for prior_frame in sorted(ledgers[event['segment']], reverse=True):
            if prior_frame > event['frame']:
                continue
            prior = ledgers[event['segment']][prior_frame]
            for action in prior['trace'].get('events', []):
                if action['kind'] not in ('reconnect', 'native_conflict_rollback',
                                          'native_return_quarantine_begin', 'native_return_quarantine_end',
                                          'empty_native_quarantine_begin', 'empty_native_quarantine_end'):
                    continue
                if (native in (action.get('native_id'), action.get('incumbent_native')) or
                    event['from_public_id'] in (action.get('canonical_id'), action.get('public_id')) or
                    event['to_public_id'] in (action.get('canonical_id'), action.get('public_id'))):
                    related.append(dict(frame=prior_frame, event=action))
            if related:
                break
        return dict(event, current_trace_events=current_events,
                    current_state_writes=row['state_write'],
                    nearest_related_action=related[0] if len(related) == 1 else None,
                    action_binding='UNIQUE_NEAREST_CANDIDATE' if len(related) == 1 else 'UNKNOWN')
    return {arm: [annotate(event) for event in items] for arm, items in switches.items()}


def main():
    manifest = read(HERE / 'public/PREDICTION_SOURCE_MANIFEST.json')
    seals = verify_before_gt(manifest)
    scores, decompositions, matched_files = {}, {}, {}
    old_archived = read(ROOT / 'experiments/feeding_first_two_s0p/run/METRICS.json')
    same_source_audit = read(ROOT / 'experiments/feeding_first_two_s0p/baseline_comparison_audit/AUDIT.json')
    for source in ('SOURCE_OLD', 'SOURCE_BASELINE'):
        scores[source], switches, match_path = score_source(source, manifest)
        matched_files[source] = dict(path=str(match_path), bytes=match_path.stat().st_size, sha256=sha(match_path))
        keys = lambda event: (event['segment'], event['frame'], event['gt_id'],
                              event['from_public_id'], event['to_public_id'])
        native_keys = {keys(item) for item in switches['NATIVE']}
        frozen_keys = {keys(item) for item in switches['Z4Q_FROZEN']}
        decompositions[source] = dict(counts={arm: len(events) for arm, events in switches.items()},
            shared=len(native_keys & frozen_keys), frozen_only=len(frozen_keys-native_keys),
            native_only=len(native_keys-frozen_keys),
            switches=link_actions(source, switches),
            gt_match_ledger=matched_files[source])
    for name in SEGMENTS:
        for key, value in same_source_audit['segment_metrics'][name]['SAM3_same_input'].items():
            assert abs(scores['SOURCE_OLD']['segment'][name]['NATIVE'][key]-value)<1e-9
        for key, value in old_archived['segment_metrics'][name]['B0'].items():
            assert abs(scores['SOURCE_OLD']['segment'][name]['Z4Q_FROZEN'][key]-value)<1e-9
    for key, value in same_source_audit['pooled_metrics']['SAM3_same_input'].items():
        assert abs(scores['SOURCE_OLD']['pooled']['NATIVE'][key]-value)<1e-9
    for key, value in old_archived['pooled_metrics']['B0'].items():
        assert abs(scores['SOURCE_OLD']['pooled']['Z4Q_FROZEN'][key]-value)<1e-9
    for name in SEGMENTS:
        for key, value in same_source_audit['segment_metrics'][name]['SAM3_canonical'].items():
            assert abs(scores['SOURCE_BASELINE']['segment'][name]['NATIVE'][key]-value)<1e-9
    for key, value in same_source_audit['pooled_metrics']['SAM3_canonical'].items():
        assert abs(scores['SOURCE_BASELINE']['pooled']['NATIVE'][key]-value)<1e-9
    save(HERE / 'public/BASELINE_SWITCH_DECOMPOSITION.json',
         dict(status='POSTSEAL_CLEAR_EXACT', source=decompositions,
              new_gt_ledger=matched_files, no_id_filter=True))
    save(HERE / 'public/FROZEN_METRICS.json',
         dict(status='SCORED_AFTER_ALL_TRACE_SEALS', metrics=scores,
              trace_run_summary_sha256=sha(HERE / 'public/TRACE_RUN_SUMMARY.json'),
              source_manifest_sha256=seals['source_manifest_sha256'], scorer_sha256=sha(Path(__file__)),
              gt_source='AlignedFeeding_v1/labels_640x360; edited checked=false',
              model_http=0))
    print(json.dumps({source: scores[source]['pooled'] for source in scores}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
