"""Postscore integrity and state-effect acceptance for all four sealed replays."""
import json
from pathlib import Path

from run import HERE, MANIFEST, SEGMENTS, save, sha


def read(path):
    return json.loads(Path(path).read_text(encoding='utf8'))


def main():
    freeze = read(HERE/'public/FREEZE.json')
    assert freeze['status'] == 'FROZEN_AFTER_REAL_F159_SLICE_BEFORE_FOUR_FULL_REPLAYS'
    assert freeze['source_manifest_sha256'] == sha(MANIFEST)
    assert freeze['slice_sha256'] == sha(HERE/'public/SLICE_F159.json')
    assert freeze['test_report_sha256'] == sha(HERE/'public/TEST_REPORT.json')
    for path, digest in freeze['code'].items():
        assert sha(path) == digest, path
    summary = read(HERE/'public/RUN_SUMMARY.json')
    metrics = read(HERE/'public/METRICS.json')
    audit = read(HERE/'public/SOURCE_AUDIT.json')
    assert summary['status'] == 'ALL_SEALED_BEFORE_GT'
    assert metrics['status'] == 'SCORED_AFTER_ALL_PXA_SEALS'
    assert metrics['run_summary_sha256'] == sha(HERE/'public/RUN_SUMMARY.json')
    assert audit['metric_sha256'] == sha(HERE/'public/METRICS.json')
    assert summary['model_http'] == metrics['model_http'] == audit['model_http'] == 0
    checked = {}
    for source in ('SOURCE_OLD', 'SOURCE_BASELINE'):
        checked[source] = {}
        for segment, (start, stop) in SEGMENTS.items():
            directory = HERE/'public'/source/segment
            seal = read(directory/'SEAL.json')
            assert sha(directory/'SEAL.json') == summary['source'][source][segment]['seal_sha256']
            assert seal['status'] == 'SEALED_BEFORE_GT' and seal['gt_not_opened']
            assert seal['frames'] == stop-start+1 and seal['model_http'] == 0
            assert seal['input_derived'] == freeze['input_derived'][source][segment]
            for label in ('prediction', 'actions', 'publication'):
                desc = seal[label]
                assert Path(desc['path']).stat().st_size == desc['bytes']
                assert sha(desc['path']) == desc['sha256']
            for path, digest in seal['code'].items():
                assert sha(path) == digest
            case = audit['source'][source][segment]
            assert case['frames'] == stop-start+1
            assert not case['source_state_diverged'] or case['published_change_count'] > 0
            assert case['old_state_comparable_edges'] <= sum(case['new_lookup'].values())
            checked[source][segment] = dict(frames=seal['frames'],
                edge_checks=sum(case['new_lookup'].values()),
                old_unknown_new_registered=case['old_unknown_new_registered_count'],
                vetoes=len(case['vetoes']), publication_changes=case['published_change_count'],
                seal_sha256=sha(directory/'SEAL.json'))
        pooled = metrics['metrics'][source]['pooled']
        if all(checked[source][s]['publication_changes'] == 0 for s in SEGMENTS):
            assert pooled['PX_ANCHOR_RETENTION'] == pooled['ARCHIVED_PX']
    save(HERE/'public/ACCEPTANCE.json', dict(
        status='ENGINEERING_PASS' if all(v['frames'] for m in checked.values() for v in m.values()) else 'ENGINEERING_FAILURE',
        source=checked, freeze_sha256=sha(HERE/'public/FREEZE.json'),
        run_summary_sha256=sha(HERE/'public/RUN_SUMMARY.json'),
        metric_sha256=sha(HERE/'public/METRICS.json'),
        audit_sha256=sha(HERE/'public/SOURCE_AUDIT.json'), model_http=0))
    print(json.dumps(checked, ensure_ascii=False))


if __name__ == '__main__':
    main()
