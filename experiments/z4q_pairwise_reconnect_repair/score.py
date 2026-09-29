"""Verify all new prediction seals before opening the edited FEEDING reference."""
import gzip
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OLD = ROOT / 'experiments/b0_same_source_regression_repair'
sys.path.insert(0, str(OLD))
from source import DATA, SEGMENTS, save, sha  # noqa: E402
from trace import rows  # noqa: E402

spec = importlib.util.spec_from_file_location('frozen_b0_score', OLD / 'score.py')
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
feeding, np, coco = base.feeding, base.np, base.coco
MANIFEST = OLD / 'public/PREDICTION_SOURCE_MANIFEST.json'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def verify_before_gt():
    summary = read(HERE / 'public/RUN_SUMMARY.json')
    assert summary['status'] == 'ALL_SEALED_BEFORE_GT' and summary['model_http'] == 0
    assert summary['source_manifest_sha256'] == sha(MANIFEST)
    assert summary['slice_sha256'] == sha(HERE / 'public/SLICE_F159.json')
    manifest = read(MANIFEST)
    for source in ('SOURCE_OLD', 'SOURCE_BASELINE'):
        for name, (start, stop) in SEGMENTS.items():
            target = HERE / 'public' / source / name
            seal = read(target / 'SEAL.json')
            assert sha(target / 'SEAL.json') == summary['source'][source][name]['seal_sha256']
            assert seal['status'] == 'SEALED_BEFORE_GT' and seal['model_http'] == 0
            assert seal['gt_not_opened'] and seal['frames'] == stop-start+1
            assert seal['source_manifest_sha256'] == sha(MANIFEST)
            assert seal['input_derived'] == manifest['segments'][source][name]['derived']
            for entry in (seal['prediction'], seal['actions'], seal['publication'],
                          *seal['input_derived'].values()):
                path = Path(entry['path'])
                assert path.stat().st_size == entry['bytes'] and sha(path) == entry['sha256']
            for path, expected in seal['code'].items():
                assert sha(path) == expected, path
            with gzip.open(seal['prediction']['path'], 'rt', encoding='utf-8') as pred, \
                 Path(seal['publication']['path']).open('r', encoding='utf-8') as pub:
                count = 0
                for count, (line, raw) in enumerate(zip(pred, pub, strict=True), 1):
                    p = json.loads(raw)
                    assert (p['frame'], p['original_frame']) == (count, start+count-1)
                    assert p['first_publish_monotonic'] >= p['received_monotonic']
                    assert hashlib.sha256(line.encode()).hexdigest() == p['prediction_row_sha256']
                assert count == stop-start+1
    return manifest


def score_source(source, manifest):
    by_segment, switch_ledger = {}, []
    pooled_gt, pooled_pred, pooled_sims = [], [], []
    matched_path = HERE / 'public' / source / 'GT_MATCHED_LEDGER.jsonl'
    matched_path.parent.mkdir(parents=True, exist_ok=True)
    with matched_path.open('x', encoding='utf-8', newline='\n') as matches_file:
        for offset, (name, (start, stop)) in enumerate(SEGMENTS.items()):
            item = manifest['segments'][source][name]
            assignments = rows(item['derived']['assignments']['path'])
            publications = rows(HERE / 'public' / source / name / 'PREDICTIONS.jsonl.gz')
            gt, pred, sims = [], [], []
            previous, previous_step, local_switches = {}, {}, []
            for local, (assignment, publication) in enumerate(zip(assignments, publications, strict=True), 1):
                frame = start+local-1
                assert assignment['frame'] == publication['frame'] == local
                assert assignment['global_frame_id'] == publication['original_frame'] == frame
                masks = [obj['mask'] for obj in assignment['variants']['N0']]
                assert publication['masks'] == masks
                native = [int(mask.split(':')[1]) for mask in masks]
                assert [x['native_id'] for x in publication['public']] == native
                assert [x['mask'] for x in publication['public']] == masks
                public = [x['public_id'] for x in publication['public']]
                assert len(public) == len(set(public)) and all(isinstance(n, int) for n in public)
                truth = read(DATA / 'labels_640x360' / f'{frame:06d}.json')
                gt_ids, gt_masks = feeding.mask_rles(truth['shapes'])
                pmasks = [feeding.original_score.rle(assignment['masks'][mask]) for mask in masks]
                similarity = (np.asarray(coco.iou(gt_masks, pmasks, [0]*len(pmasks)), float)
                              if gt_ids and pmasks else np.zeros((len(gt_ids), len(pmasks))))
                gt.append(gt_ids); pred.append(public); sims.append(similarity)
                pooled_gt.append([g+offset*10_000_000 for g in gt_ids])
                pooled_pred.append([p+offset*10_000_000 for p in public])
                pooled_sims.append(similarity)
                previous_step, matched, switches = base.clear_step(
                    gt_ids, masks, public, similarity, previous, previous_step, frame)
                local_switches.extend(switches)
                switch_ledger.extend(dict(s, segment=name) for s in switches)
                matches_file.write(json.dumps(dict(source=source, segment=name, local_frame=local,
                    original_frame=frame, matches=matched), ensure_ascii=False, separators=(',', ':'))+'\n')
            by_segment[name] = feeding.metrics(gt, pred, sims)
            assert by_segment[name]['IDSW'] == len(local_switches)
    pooled = feeding.metrics(pooled_gt, pooled_pred, pooled_sims)
    assert pooled['IDSW'] == len(switch_ledger)
    return dict(segment=by_segment, pooled=pooled), switch_ledger, matched_path


def audit_actions(source):
    old_matches = {(r['segment'], r['local_frame']): r for r in map(json.loads,
        (OLD / 'public' / source / 'GT_MATCHED_LEDGER.jsonl').read_text(encoding='utf-8').splitlines())}
    def gt(segment, local, native):
        return [m['gt_id'] for m in old_matches[segment, local]['matches']['NATIVE']
                if m['native_id'] == native]
    actions, vetoes = [], []
    for name, (start, stop) in SEGMENTS.items():
        for row in map(json.loads, (HERE / 'public' / source / name / 'ACTION_LEDGER.jsonl').read_text(encoding='utf-8').splitlines()):
            local, frame = row['frame'], row['original_frame']
            assert frame == start+local-1
            for event in row['events']:
                if event.get('kind') != 'reconnect' or not event.get('accepted'):
                    continue
                anchor = event.get('old_anchor')
                ag = gt(name, anchor['frame'], anchor['native_id']) if anchor else []
                cg = gt(name, local, event['native_id'])
                relation = ('SAME_GT' if ag and cg and ag == cg else
                            'DIFFERENT_GT' if ag and cg else 'UNKNOWN')
                actions.append(dict(source=source, segment=name, original_frame=frame,
                    origin_rule=event['origin_rule'], phase=event.get('phase'),
                    native_id=event['native_id'], public_id=event['canonical_id'],
                    confirmations=event['confirmations'], anchor=anchor,
                    anchor_gt=ag, current_gt=cg, physical_relation=relation))
            for check in row['edge_veto_checks']:
                if not check['veto']:
                    continue
                anchor = check['anchor']
                ag = gt(name, anchor['frame'], anchor['native_id']) if anchor else []
                cg = gt(name, local, check['native_id'])
                relation = ('SAME_GT' if ag and cg and ag == cg else
                            'DIFFERENT_GT' if ag and cg else 'UNKNOWN')
                vetoes.append(dict(source=source, segment=name, original_frame=frame,
                    **check, anchor_gt=ag, current_gt=cg, physical_relation=relation))
    return actions, vetoes


def main():
    manifest = verify_before_gt()
    archived = read(OLD / 'public/ONEFIX_METRICS.json')
    assert archived['status'] == 'ALL_ONEFIX_SEALS_VERIFIED_BEFORE_GT'
    results, switches, audits = {}, {}, {}
    for source in ('SOURCE_OLD', 'SOURCE_BASELINE'):
        pairwise, switch_ledger, matched = score_source(source, manifest)
        old = archived['metrics'][source]
        results[source] = dict(segment={}, pooled={}, pairwise_minus_native={})
        for name in SEGMENTS:
            results[source]['segment'][name] = {
                **{arm: old['segment'][name][arm] for arm in ('NATIVE','Z4Q_FROZEN')},
                'ARCHIVED_ONEFIX': old['segment'][name]['Z4Q_ONEFIX'],
                'Z4Q_PAIRWISE': pairwise['segment'][name]}
        results[source]['pooled'] = {
            **{arm: old['pooled'][arm] for arm in ('NATIVE','Z4Q_FROZEN')},
            'ARCHIVED_ONEFIX': old['pooled']['Z4Q_ONEFIX'],
            'Z4Q_PAIRWISE': pairwise['pooled']}
        native = old['pooled']['NATIVE']
        results[source]['pairwise_minus_native'] = {k: pairwise['pooled'][k]-native[k]
                                                   for k in pairwise['pooled']}
        actions, vetoes = audit_actions(source)
        audits[source] = dict(accepted_reconnects=actions, rejected_edges=vetoes,
                              origin_counts={origin: sum(a['origin_rule'] == origin for a in actions)
                                             for origin in ('D1_DELAYED','BIRTH_REFINE')},
                              relation_counts={relation: sum(a['physical_relation'] == relation for a in actions)
                                               for relation in ('SAME_GT','DIFFERENT_GT','UNKNOWN')})
        switches[source] = dict(events=switch_ledger,
                                matched_ledger=dict(path=str(matched), bytes=matched.stat().st_size,
                                                    sha256=sha(matched)))
    save(HERE / 'public/METRICS.json', dict(status='SCORED_AFTER_ALL_PAIRWISE_SEALS',
        metrics=results, run_summary_sha256=sha(HERE / 'public/RUN_SUMMARY.json'),
        archived_metrics_sha256=sha(OLD / 'public/ONEFIX_METRICS.json'),
        scorer_sha256=sha(Path(__file__)), model_http=0))
    save(HERE / 'public/EDGE_AUDIT.json', dict(status='POSTSEAL_PHYSICAL_AUDIT', source=audits,
         metrics_sha256=sha(HERE / 'public/METRICS.json')))
    save(HERE / 'public/SWITCH_LEDGER.json', dict(status='POSTSEAL_CLEAR_SWITCHES', source=switches,
         metrics_sha256=sha(HERE / 'public/METRICS.json')))
    print(json.dumps({source: results[source]['pooled'] for source in results}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
