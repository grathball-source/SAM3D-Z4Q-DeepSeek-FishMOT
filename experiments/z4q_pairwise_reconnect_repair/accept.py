"""Postscore integrity and outcome checks; does not change any sealed result."""
import gzip
import json
from collections import Counter
from pathlib import Path

from run import HERE, MANIFEST, OLD, SEGMENTS, save, sha


def read(path):
    return json.loads(Path(path).read_text(encoding='utf8'))


def main():
    freeze = read(HERE / 'public/FREEZE.json')
    assert freeze['status'] == 'RULE_AND_SCORER_FROZEN_AFTER_REAL_F159_SLICE_BEFORE_FULL_REPLAY'
    assert freeze['source_manifest_sha256'] == sha(MANIFEST)
    assert freeze['slice_sha256'] == sha(HERE / 'public/SLICE_F159.json')
    assert freeze['test_report_sha256'] == sha(HERE / 'public/TEST_REPORT.json')
    assert all(sha(path) == digest for path, digest in freeze['code'].items())
    run = read(HERE / 'public/RUN_SUMMARY.json')
    result = read(HERE / 'public/METRICS.json')
    audit = read(HERE / 'public/EDGE_AUDIT.json')
    assert result['status'] == 'SCORED_AFTER_ALL_PAIRWISE_SEALS'
    assert result['run_summary_sha256'] == sha(HERE / 'public/RUN_SUMMARY.json')
    assert audit['metrics_sha256'] == sha(HERE / 'public/METRICS.json')
    checked = {}
    for source in ('SOURCE_OLD', 'SOURCE_BASELINE'):
        checked[source] = {}
        assert not audit['source'][source]['rejected_edges']
        for name, (start, stop) in SEGMENTS.items():
            target = HERE / 'public' / source / name
            seal = read(target / 'SEAL.json')
            assert sha(target / 'SEAL.json') == run['source'][source][name]['seal_sha256']
            for desc in (seal['prediction'], seal['actions'], seal['publication']):
                path = Path(desc['path'])
                assert path.stat().st_size == desc['bytes'] and sha(path) == desc['sha256']
            old_path = OLD / 'public' / source / name / 'PREDICTIONS.jsonl.gz'
            changed, frames, checks = [], 0, []
            with gzip.open(target / 'PREDICTIONS.jsonl.gz', 'rt', encoding='utf8') as a, \
                 gzip.open(old_path, 'rt', encoding='utf8') as b:
                for new, old in zip(map(json.loads, a), map(json.loads, b), strict=True):
                    frames += 1
                    assert new['masks'] == old['masks']
                    old_map = {int(n): int(k) for n, k in old['variants']['Z4Q_FROZEN'].items()}
                    new_map = {v['native_id']: v['public_id'] for v in new['public']}
                    assert len(set(new_map.values())) == len(new_map)
                    if old_map != new_map:
                        changed.append(new['original_frame'])
            assert frames == stop-start+1 and not changed
            for row in map(json.loads, (target / 'ACTION_LEDGER.jsonl').read_text(encoding='utf8').splitlines()):
                checks.extend(row['edge_veto_checks'])
            checked[source][name] = dict(frames=frames, changed_vs_frozen=changed,
                                         edge_checks=len(checks), rejected_edges=0,
                                         reasons=dict(Counter(c['reason'] for c in checks)),
                                         origins=dict(Counter(c['origin_rule'] for c in checks)))
        old = result['metrics'][source]['pooled']['Z4Q_FROZEN']
        new = result['metrics'][source]['pooled']['Z4Q_PAIRWISE']
        assert new == old
    old_first = read(HERE / 'public/SOURCE_OLD/feeding_000000_000199/SEAL.json')
    assert old_first['decision_post_state'] != old_first['final_state']
    assert audit['source']['SOURCE_OLD']['origin_counts'] == {'D1_DELAYED': 5, 'BIRTH_REFINE': 1}
    assert any(a['original_frame'] == 468 and a['origin_rule'] == 'BIRTH_REFINE'
               and a['phase'] == 'birth' for a in audit['source']['SOURCE_OLD']['accepted_reconnects'])
    save(HERE / 'public/ACCEPTANCE.json', dict(status='PASS_ENGINEERING_NO_EFFECT_RESEARCH',
        full_source_comparison=checked, freeze_sha256=sha(HERE / 'public/FREEZE.json'),
        run_summary_sha256=sha(HERE / 'public/RUN_SUMMARY.json'),
        metrics_sha256=sha(HERE / 'public/METRICS.json'),
        zero_rejected_edges=True, pairwise_identical_to_frozen_in_all_810_frames=True,
        F468_birth_origin_verified=True, decision_and_final_state_distinct=True,
        model_http=0))
    print(json.dumps(checked, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
