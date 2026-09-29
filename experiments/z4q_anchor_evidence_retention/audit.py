"""Compare archived PX's old-state queries with sealed PX-A decisions.

Only prefix-identical public decisions can be called same-controller-state
comparisons.  This audit never turns old-state lookup coverage into new gain.
"""
import json
import gzip
from collections import Counter
from pathlib import Path

from run import HERE, ROOT, SEGMENTS, save, sha

PX = ROOT / 'experiments/z4q_pairwise_reconnect_repair/public'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf8'))


def rows(path):
    path = Path(path)
    opener = gzip.open if path.suffix == '.gz' else open
    with opener(path, 'rt', encoding='utf8') as stream:
        yield from map(json.loads, stream)


def key(check):
    a = check['anchor'] or {}
    return (check['origin_rule'], check['native_id'], check['public_id'],
            a.get('frame'), a.get('native_id'), a.get('mask'))


def main():
    assert read(HERE/'public/METRICS.json')['status'] == 'SCORED_AFTER_ALL_PXA_SEALS'
    result = {}
    first_gain = None
    for source in ('SOURCE_OLD', 'SOURCE_BASELINE'):
        result[source] = {}
        for segment, (start, stop) in SEGMENTS.items():
            newdir, olddir = HERE/'public'/source/segment, PX/source/segment
            newseal, oldseal = read(newdir/'SEAL.json'), read(olddir/'SEAL.json')
            for directory, seal in ((newdir, newseal), (olddir, oldseal)):
                for label, filename in (('prediction','PREDICTIONS.jsonl.gz'),
                                        ('actions','ACTION_LEDGER.jsonl'),
                                        ('publication','PUBLISH_LEDGER.jsonl')):
                    assert sha(directory/filename) == seal[label]['sha256']
            newact, oldact = rows(newdir/'ACTION_LEDGER.jsonl'), rows(olddir/'ACTION_LEDGER.jsonl')
            newpred, oldpred = rows(newdir/'PREDICTIONS.jsonl.gz'), rows(olddir/'PREDICTIONS.jsonl.gz')
            lookup, reason, pair, old_reason, lifecycle = (Counter() for _ in range(5))
            gained, changed, vetoes, comparable = [], [], [], 0
            prefix_same = True
            for na, oa, np, op in zip(newact, oldact, newpred, oldpred, strict=True):
                f = na['original_frame']
                assert f == oa['original_frame'] == np['original_frame'] == op['original_frame']
                assert np['masks'] == op['masks']
                oldmap = {v['native_id']: v['public_id'] for v in op['public']}
                newmap = {v['native_id']: v['public_id'] for v in np['public']}
                for n in sorted(set(oldmap) | set(newmap)):
                    if oldmap.get(n) != newmap.get(n):
                        changed.append(dict(original_frame=f, native_id=n,
                                            archived_px=oldmap.get(n), pxa=newmap.get(n)))
                oldchecks = {key(c): c for c in oa['edge_veto_checks']}
                assert len(oldchecks) == len(oa['edge_veto_checks'])
                for c in na['edge_veto_checks']:
                    lookup[c['target_lookup']] += 1
                    reason[c['reason']] += 1
                    pair[c['pair_status']] += 1
                    if c['veto']:
                        vetoes.append(dict(original_frame=f, **c))
                    if prefix_same:
                        old = oldchecks.get(key(c))
                        if old:
                            comparable += 1
                            old_reason[old['reason']] += 1
                            if old['reason'] == 'target_anchor_lineage_unknown' and c['target_lookup'] == 'REGISTERED':
                                event = dict(source=source, segment=segment, original_frame=f,
                                             native_id=c['native_id'], public_id=c['public_id'],
                                             anchor=c['anchor'], source_version=c['source_version'],
                                             target_version=c['target_version'],
                                             pair_status=c['pair_status'], new_reason=c['reason'])
                                gained.append(event)
                                if first_gain is None or f < first_gain['original_frame']:
                                    first_gain = event
                lifecycle.update(e['kind'] for e in na['source_lifecycle'])
                prefix_same &= oldmap == newmap
            result[source][segment] = dict(frames=stop-start+1,
                old_state_comparable_edges=comparable, source_state_diverged=not prefix_same,
                old_cache_reason=dict(old_reason), new_lookup=dict(lookup), new_reason=dict(reason),
                pair_status=dict(pair), lifecycle=dict(lifecycle),
                old_unknown_new_registered_count=len(gained), first_lookup_gain=gained[0] if gained else None,
                all_lookup_gains=gained, vetoes=vetoes,
                published_change_count=len(changed), published_changes=changed,
                old_prediction_sha256=oldseal['prediction']['sha256'],
                new_prediction_sha256=newseal['prediction']['sha256'])
    save(HERE/'public/SOURCE_AUDIT.json', dict(status='POSTSEAL_OLD_STATE_COVERAGE_SEPARATE_FROM_NEW_EFFECT',
         source=result, first_lookup_gain=first_gain,
         metric_sha256=sha(HERE/'public/METRICS.json'), model_http=0))
    print(json.dumps(dict(first_lookup_gain=first_gain,
        summary={s:{n:{k:v for k,v in x.items() if k in ('old_unknown_new_registered_count','published_change_count','new_lookup','pair_status')}
                    for n,x in m.items()} for s,m in result.items()}), ensure_ascii=False))


if __name__ == '__main__':
    main()
