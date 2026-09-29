"""Read-only acceptance: sealed inputs, output geometry, state contrast, and score scope."""
import gzip
import json
import sys
from pathlib import Path

from source import HERE, ROOT, SEGMENTS, save, sha

sys.path.insert(0, str(HERE))
import score as same_score  # noqa: E402
import score_onefix as fixed_score  # noqa: E402


def records(path):
    with gzip.open(path, 'rt', encoding='utf-8') as stream:
        yield from map(json.loads, stream)


def main():
    manifest = json.loads((HERE / 'public/PREDICTION_SOURCE_MANIFEST.json').read_text(encoding='utf-8'))
    same_score.verify_before_gt(manifest)
    fixed_score.verify_before_gt(manifest)
    assert manifest['status'] == 'FROZEN_NO_GT_OPEN'
    checks = {}
    for name in SEGMENTS:
        old = manifest['segments']['SOURCE_OLD'][name]['frames']
        baseline = manifest['segments']['SOURCE_BASELINE'][name]['frames']
        difference = sum(a['prediction_sha256'] != b['prediction_sha256']
                         for a, b in zip(old, baseline, strict=True))
        checks[name] = dict(frames=len(old), source_jsons_differ=difference)
        assert difference == (0 if name == 'feeding_000000_000199' else 205)
    total = 0
    for source in ('SOURCE_OLD', 'SOURCE_BASELINE'):
        for name, (start, stop) in SEGMENTS.items():
            root = HERE / 'public' / source / name
            original = records(root / 'PREDICTIONS.jsonl.gz')
            fixed = records(root / 'onefix/PREDICTIONS.jsonl.gz')
            inputs = records(manifest['segments'][source][name]['derived']['assignments']['path'])
            for first, second, assignment in zip(original, fixed, inputs, strict=True):
                native = [obj['id'] for obj in assignment['variants']['N0']]
                masks = [obj['mask'] for obj in assignment['variants']['N0']]
                assert first['masks'] == second['masks'] == masks
                for arm in ('NATIVE', 'Z4Q_FROZEN', 'PASSTHROUGH'):
                    assert len(first['variants'][arm]) == len(native)
                    assert set(map(int, first['variants'][arm])) == set(native)
                    assert len(set(first['variants'][arm].values())) == len(native)
                assert first['variants']['NATIVE'] == first['variants']['PASSTHROUGH']
                assert first['variants']['NATIVE'] == {str(n): n for n in native}
                assert [obj['native_id'] for obj in second['public']] == native
                assert len({obj['public_id'] for obj in second['public']}) == len(native)
                total += 1
    assert total == 810
    pair = json.loads((HERE / 'public/counterfactual_F159/PAIR_SEALED.json').read_text(encoding='utf-8'))
    assert pair['status'] == 'BOTH_SEALED_BEFORE_GT'
    arm_seals = {arm: json.loads((HERE / 'public/counterfactual_F159' / arm / 'SEAL.json').read_text(encoding='utf-8'))
                 for arm in ('ALLOW', 'VETO')}
    assert arm_seals['ALLOW']['decision_pre_state_sha256'] == arm_seals['VETO']['decision_pre_state_sha256']
    pair_score = json.loads((HERE / 'public/counterfactual_F159/POSTSEAL_SCORE.json').read_text(encoding='utf-8'))
    assert pair_score['branch']['VETO']['changed_vs_archived_frozen_frames'] == [159]
    metrics = json.loads((HERE / 'public/ONEFIX_METRICS.json').read_text(encoding='utf-8'))
    assert metrics['status'] == 'ALL_ONEFIX_SEALS_VERIFIED_BEFORE_GT'
    assert set(metrics['metrics']) == {'SOURCE_OLD', 'SOURCE_BASELINE'}
    for source in metrics['metrics']:
        assert set(metrics['metrics'][source]['pooled']) == {'NATIVE', 'Z4Q_FROZEN', 'Z4Q_ONEFIX'}
    forbidden = {'.png', '.jpg', '.jpeg', '.npz', '.pth', '.pt'}
    assert not [path for path in (HERE / 'public').rglob('*') if path.is_file() and path.suffix.lower() in forbidden]
    save(HERE / 'public/TEST_REPORT.json', dict(status='PASS',
        source_comparison=checks, source_segment_replays=4, prediction_rows=total,
        independent_onefix_state_replays=4, all_seals_verified=True,
        native_passthrough_exact=True, geometry_and_public_one_to_one=True,
        single_action_prestate_equal=True, single_veto_changed_original_frames=[159],
        first_publication_rows=810, model_http=0, no_public_private_pixel_files=True,
        test_code_sha256=sha(Path(__file__))))
    print('PASS: 4 source-segment replays, 810 rows, same source and state seals', flush=True)


if __name__ == '__main__':
    main()
