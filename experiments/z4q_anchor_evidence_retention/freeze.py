"""Freeze executable, source, tests, and exact original-depth inputs before replay."""
import json
from pathlib import Path

from run import BRIDGE, CODE, CONFIG, HERE, MANIFEST, ROOT, SEGMENTS, read, save, sha


def main():
    target = HERE / 'public/FREEZE.json'
    assert not target.exists()
    assert sha(MANIFEST) == '746aa6e53e6ea8deb8988ecc889afa13362c38336bd93f05690eb7208c6bd438'
    manifest = read(MANIFEST)
    inputs = {}
    for source in ('SOURCE_OLD', 'SOURCE_BASELINE'):
        inputs[source] = {}
        for segment in SEGMENTS:
            item = manifest['segments'][source][segment]
            derived = item['derived']
            assert 'v3' not in json.dumps(derived).lower()
            for entry in derived.values():
                path = Path(entry['path'])
                assert path.stat().st_size == entry['bytes'] and sha(path) == entry['sha256']
            inputs[source][segment] = derived
    code = sorted(set([*CODE, HERE/'score.py', HERE/'test_pairwise.py',
                       HERE/'freeze.py', ROOT/'experiments/z4q_pairwise_reconnect_repair/score.py']))
    save(target, dict(status='FROZEN_AFTER_REAL_F159_SLICE_BEFORE_FOUR_FULL_REPLAYS',
                      review_base='85f71d854f8d9b0bcc6d7bf1d200d1a01dd8de08',
                      code={str(path): sha(path) for path in code},
                      source_manifest_sha256=sha(MANIFEST), input_derived=inputs,
                      slice_sha256=sha(HERE/'public/SLICE_F159.json'),
                      test_report_sha256=sha(HERE/'public/TEST_REPORT.json'),
                      confirm=5, history_seconds=12, original_depth=True,
                      model_http=0, sam3_new_inference=0))


if __name__ == '__main__':
    main()
