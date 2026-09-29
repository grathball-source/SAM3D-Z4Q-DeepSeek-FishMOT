"""Final postscore integrity and interpretation checks."""
from run import HERE, px, read


def main():
    public = HERE / 'public'
    metrics = read(public / 'METRICS.json')
    delta = read(public / 'DELTA_AUDIT.json')
    edge = read(public / 'EDGE_AUDIT.json')
    sensitive = read(public / 'PROVENANCE4_SENSITIVITY.json')
    summary = read(public / 'RUN_SUMMARY.json')
    assert metrics['status'] == 'SCORED_AFTER_BOTH_V3_SEALS'
    assert metrics['run_summary_sha256'] == px.sha(public / 'RUN_SUMMARY.json')
    assert summary['status'] == 'ALL_SEALED_BEFORE_GT' and summary['model_http'] == 0
    assert sum(s['frames'] for s in summary['segments'].values()) == 405
    assert delta['v3_pairwise_equals_v3_frozen_all_405']
    assert metrics['pooled']['Z4Q_FROZEN_V3'] == metrics['pooled']['Z4Q_PAIRWISE_V3']
    assert metrics['pooled']['NATIVE'] == metrics['original_raw_depth_old']['pooled']['NATIVE']
    assert sensitive['frames'] == 405 and not sensitive['changed_publications']
    assert len(edge['vetoes']) == 0
    assert (public / 'FAILED_ATTEMPT_1/FREEZE.json').is_file()
    assert not (public / 'FAILED_ATTEMPT_1/feeding_000000_000199/SEAL.json').exists()
    files = {name: dict(bytes=(public / name).stat().st_size, sha256=px.sha(public / name))
             for name in ('FREEZE.json', 'TEST_REPORT.json', 'RUN_SUMMARY.json',
                          'METRICS.json', 'DELTA_AUDIT.json', 'EDGE_AUDIT.json',
                          'DEPTH_AUDIT.json', 'SWITCH_LEDGER.json',
                          'PROVENANCE4_SENSITIVITY.json', 'F374_DEPTH_SOURCE.json')}
    px.save(public / 'ACCEPTANCE.json', dict(
        status='ENGINEERING_PASS_ANNOTATION_ASSISTED_DIAGNOSTIC_NO_PAIRWISE_INCREMENT',
        full_old_frames=405, two_independent_segments=True,
        source='SOURCE_OLD', depth='restored_v3',
        native_identical_to_old=True,
        pairwise_equals_frozen_v3_on_all_frames=True,
        annotation_fill_ablation_changed_publications=0,
        edge_vetoes=0, model_http=0,
        original_failed_attempt_preserved=True, checked_files=files))
    print('ACCEPTED 405 frames; pairwise=Z4Q, zero veto, native exact, label-fill ablation exact', flush=True)


if __name__ == '__main__':
    main()
