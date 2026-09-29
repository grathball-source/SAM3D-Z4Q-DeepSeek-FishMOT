"""Apply the frozen V4 prediction-only merge scan separately per segment."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'experiments/ms1_s0_development_8400'))
from source_scan_v4 import scan  # noqa: E402
from prepare import SEGMENTS, digest, write_new  # noqa: E402


def main():
    for name, (start, stop) in SEGMENTS.items():
        base = HERE / 'private' / name
        source = json.loads((base/'SOURCE_MANIFEST.json').read_text(encoding='utf-8'))
        assert source['frames'] == stop-start+1
        for item in source['derived'].values():
            path = Path(item['path'])
            assert path.stat().st_size == item['bytes'] and digest(path) == item['sha256']
        result = scan(base/'observations.jsonl.gz', base/'assignments.jsonl.gz',
                      base/'scan_v4.json')
        write_new(base/'SCAN_MANIFEST.json',
                  dict(segment=name,scanner='frozen_ms1_s0_v4',frames=result['frames'],
                       suspects=len(result['suspects']),scan_sha256=digest(base/'scan_v4.json')))


if __name__ == '__main__':
    main()
