"""Verify both seals, then score the OLD+v3 diagnostic at the frozen GT path."""
import gzip
import hashlib
import importlib.util
import json
from collections import Counter
from pathlib import Path

from run import ARMS, DATA, HERE, SOURCE_MANIFEST, px, read

spec = importlib.util.spec_from_file_location('frozen_b0_scorer_v3',
    px.OLD / 'score.py')
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
feeding, np, coco = base.feeding, base.np, base.coco


def verify_before_gt():
    freeze = read(HERE / 'public/FREEZE.json')
    summary = read(HERE / 'public/RUN_SUMMARY.json')
    assert freeze['status'] == 'FROZEN_BEFORE_REAL_REPLAY_AND_GT'
    assert freeze['interpretation'] == 'ANNOTATION_ASSISTED_V3_DIAGNOSTIC'
    assert summary['status'] == 'ALL_SEALED_BEFORE_GT' and summary['model_http'] == 0
    assert summary['freeze_sha256'] == px.sha(HERE / 'public/FREEZE.json')
    assert freeze['test_sha256'] == px.sha(HERE / 'public/TEST_REPORT.json')
    assert all(px.sha(path) == digest for path, digest in freeze['code'].items())
    for key, path in (('source_manifest', SOURCE_MANIFEST), ('data_manifest', DATA / 'manifest.jsonl')):
        desc = freeze[key]
        assert Path(desc['path']) == path and path.stat().st_size == desc['bytes']
        assert px.sha(path) == desc['sha256']
    for group in [*freeze['derived'].values(), freeze['restored']]:
        for desc in group.values():
            path = Path(desc['path'])
            assert path.stat().st_size == desc['bytes'] and px.sha(path) == desc['sha256']
    for name, (start, stop) in px.SEGMENTS.items():
        target = HERE / 'public' / name
        seal = read(target / 'SEAL.json')
        assert px.sha(target / 'SEAL.json') == summary['segments'][name]['seal_sha256']
        assert seal['status'] == 'SEALED_BEFORE_GT' and seal['gt_not_opened']
        assert seal['interpretation'] == freeze['interpretation']
        assert seal['freeze_sha256'] == summary['freeze_sha256']
        assert seal['frames'] == stop - start + 1 and seal['model_http'] == 0
        for key in ('predictions', 'actions', 'publication'):
            desc = seal[key]
            path = Path(desc['path'])
            assert path.stat().st_size == desc['bytes'] and px.sha(path) == desc['sha256']
        with gzip.open(seal['predictions']['path'], 'rt', encoding='utf-8') as pred, \
             Path(seal['publication']['path']).open('r', encoding='utf-8') as pub:
            count = 0
            for count, (line, raw) in enumerate(zip(pred, pub, strict=True), 1):
                p = json.loads(raw)
                assert (p['frame'], p['original_frame']) == (count, start + count - 1)
                assert p['first_publish_monotonic'] >= p['received_monotonic']
                assert hashlib.sha256(line.encode()).hexdigest() == p['prediction_row_sha256']
            assert count == stop - start + 1
    return read(SOURCE_MANIFEST)


def score(manifest):
    by_segment, pooled_truth, pooled_sims = {}, [], []
    pooled_pred = {arm: [] for arm in ARMS}
    switches = {arm: [] for arm in ARMS}
    native_matches = {}
    for offset, (name, (start, stop)) in enumerate(px.SEGMENTS.items()):
        item = manifest['segments']['SOURCE_OLD'][name]
        assignments = px.rows(item['derived']['assignments']['path'])
        publications = px.rows(HERE / 'public' / name / 'PREDICTIONS.jsonl.gz')
        truth, sims = [], []
        pred = {arm: [] for arm in ARMS}
        previous = {arm: {} for arm in ARMS}
        previous_step = {arm: {} for arm in ARMS}
        local_switches = {arm: [] for arm in ARMS}
        for local, (assignment, publication) in enumerate(zip(assignments, publications, strict=True), 1):
            frame = start + local - 1
            assert assignment['frame'] == publication['frame'] == local
            assert assignment['global_frame_id'] == publication['original_frame'] == frame
            masks = [obj['mask'] for obj in assignment['variants']['N0']]
            assert publication['masks'] == masks
            gt = read(DATA / 'labels_640x360' / f'{frame:06d}.json')
            gt_ids, gt_masks = feeding.mask_rles(gt['shapes'])
            pmasks = [feeding.original_score.rle(assignment['masks'][mask]) for mask in masks]
            similarity = (np.asarray(coco.iou(gt_masks, pmasks, [0] * len(pmasks)), float)
                          if gt_ids and pmasks else np.zeros((len(gt_ids), len(pmasks))))
            truth.append(gt_ids); sims.append(similarity)
            pooled_truth.append([g + offset * 10_000_000 for g in gt_ids])
            pooled_sims.append(similarity)
            for arm in ARMS:
                mapping = {int(k): int(v) for k, v in publication['variants'][arm].items()}
                ids = [mapping[int(k.split(':')[1])] for k in masks]
                assert len(ids) == len(set(ids))
                if arm == 'NATIVE':
                    assert all(mapping[n] == n for n in mapping)
                pred[arm].append(ids)
                pooled_pred[arm].append([k + offset * 10_000_000 for k in ids])
                previous_step[arm], matches, new_switches = base.clear_step(
                    gt_ids, masks, ids, similarity, previous[arm], previous_step[arm], frame)
                if arm == 'NATIVE':
                    native_matches[name, local] = {m['native_id']: m['gt_id'] for m in matches}
                local_switches[arm].extend(new_switches)
                switches[arm].extend(dict(s, segment=name) for s in new_switches)
        by_segment[name] = {arm: feeding.metrics(truth, pred[arm], sims) for arm in ARMS}
        for arm in ARMS:
            assert by_segment[name][arm]['IDSW'] == len(local_switches[arm])
    pooled = {arm: feeding.metrics(pooled_truth, pooled_pred[arm], pooled_sims) for arm in ARMS}
    assert all(pooled[arm]['IDSW'] == len(switches[arm]) for arm in ARMS)
    return by_segment, pooled, switches, native_matches


def audit(native_matches):
    depth = Counter()
    changed_frames = []
    checks, accepted = [], []
    def relation(name, local, event):
        anchor = event.get('old_anchor') or event.get('anchor')
        old = native_matches.get((name, anchor['frame']), {}).get(anchor['native_id']) if anchor else None
        now = native_matches.get((name, local), {}).get(event['native_id'])
        return dict(anchor_gt=old, current_gt=now, physical_relation=(
            'UNKNOWN' if old is None or now is None else 'SAME_GT' if old == now else 'DIFFERENT_GT'))
    for name in px.SEGMENTS:
        for row in map(json.loads, (HERE / 'public' / name / 'ACTIONS.jsonl').read_text(encoding='utf-8').splitlines()):
            frame, local = row['original_frame'], row['frame']
            d = row['depth_audit']
            depth.update({f'provenance_{k}': v for k, v in d['provenance_in_prediction_union'].items()})
            depth['changed_native_observations'] += d['changed_native_count']
            if d['changed_native_count']:
                changed_frames.append(frame)
            for check in row['edge_veto_checks']:
                checks.append(dict(segment=name, original_frame=frame, **check,
                                   **(relation(name, local, check) if check['veto'] else {})))
            for arm in ('frozen_events', 'pairwise_events'):
                for event in row[arm]:
                    if event.get('kind') == 'reconnect' and event.get('accepted'):
                        accepted.append(dict(arm=arm, segment=name, original_frame=frame,
                            origin_rule=event.get('origin_rule'), phase=event.get('phase'),
                            native_id=event['native_id'], public_id=event['canonical_id'],
                            confirmations=event.get('confirmations'), old_anchor=event.get('old_anchor'),
                            **relation(name, local, event)))
    return dict(total=depth, frames_with_changed_depth_stats=changed_frames), checks, accepted


def main():
    manifest = verify_before_gt()
    by_segment, pooled, switches, native_matches = score(manifest)
    old = read(px.OLD / 'public/FROZEN_METRICS.json')['metrics']['SOURCE_OLD']
    previous_px = read(px.HERE / 'public/METRICS.json')['metrics']['SOURCE_OLD']
    assert pooled['NATIVE'] == old['pooled']['NATIVE']
    for name in px.SEGMENTS:
        assert by_segment[name]['NATIVE'] == old['segment'][name]['NATIVE']
    depth, checks, accepted = audit(native_matches)
    result = dict(status='SCORED_AFTER_BOTH_V3_SEALS',
        interpretation='ANNOTATION_ASSISTED_V3_DIAGNOSTIC',
        segment=by_segment, pooled=pooled,
        original_raw_depth_old=old,
        original_pairwise_old=previous_px,
        v3_minus_raw_frozen={k: pooled['Z4Q_FROZEN_V3'][k] - old['pooled']['Z4Q_FROZEN'][k]
                             for k in pooled['Z4Q_FROZEN_V3']},
        v3_pairwise_minus_v3_frozen={k: pooled['Z4Q_PAIRWISE_V3'][k] - pooled['Z4Q_FROZEN_V3'][k]
                                     for k in pooled['Z4Q_PAIRWISE_V3']},
        v3_pairwise_minus_native={k: pooled['Z4Q_PAIRWISE_V3'][k] - pooled['NATIVE'][k]
                                  for k in pooled['NATIVE']},
        run_summary_sha256=px.sha(HERE / 'public/RUN_SUMMARY.json'),
        scorer_sha256=px.sha(Path(__file__)), model_http=0)
    px.save(HERE / 'public/METRICS.json', result)
    px.save(HERE / 'public/DEPTH_AUDIT.json', dict(status='POSTSEAL_DIAGNOSTIC', **depth,
        metrics_sha256=px.sha(HERE / 'public/METRICS.json')))
    px.save(HERE / 'public/EDGE_AUDIT.json', dict(status='POSTSEAL_PHYSICAL_AUDIT',
        edge_checks=len(checks), edge_reasons=dict(Counter(c['reason'] for c in checks)),
        vetoes=[c for c in checks if c['veto']], accepted_reconnects=accepted,
        metrics_sha256=px.sha(HERE / 'public/METRICS.json')))
    px.save(HERE / 'public/SWITCH_LEDGER.json', dict(status='POSTSEAL_CLEAR_SWITCHES',
        switches=switches, metrics_sha256=px.sha(HERE / 'public/METRICS.json')))
    print(json.dumps(dict(pooled=pooled, depth=depth['total'], edge_checks=len(checks),
                          vetoes=sum(c['veto'] for c in checks)), ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
