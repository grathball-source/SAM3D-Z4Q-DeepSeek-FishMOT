"""Freeze both saved SAM3 sources without opening edited reference labels."""
import gzip
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OLD = ROOT / 'experiments/feeding_first_two_s0p'
sys.path.insert(0, str(OLD))
import prepare  # noqa: E402

DATA = prepare.DATA
SEGMENTS = prepare.SEGMENTS
BASE = Path('E:/CAU/D-MOT/output/evaluation/sam3_feeding_20260928_v2')
ML = Path('E:/CAU/D-MOT/data/AnnotationFeeding_20260924/ML')


def sha(path):
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='\n') as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write('\n')


def descriptor(path):
    path = Path(path)
    return dict(path=str(path.resolve()), bytes=path.stat().st_size, sha256=sha(path))


def producer_batch(frame, source):
    if source == 'SOURCE_BASELINE' and frame >= 351:
        folder = ML / 'segments_v2/sam3_run_000351_001906/full'
        relative = frame - 351
    else:
        folder = ML / 'full'
        relative = frame
    for path in sorted(folder.glob('*.json.gz')):
        start, stop = map(int, path.name.removesuffix('.json.gz').split('-'))
        if start <= relative <= stop:
            return dict(batch_file=str(path), batch_start_relative=start,
                        batch_stop_relative=stop, frame_relative=relative)
    raise AssertionError((source, frame, folder))


def make_baseline_segment(name, start, stop, raw_dir, meta):
    target = HERE / 'private' / 'baseline' / name
    assert not target.exists(), target
    target.mkdir(parents=True)
    paths = {kind: target / f'{kind}.jsonl.gz' for kind in ('observations', 'profiles', 'assignments')}
    previous = prepare.RAW
    prepare.RAW = raw_dir
    try:
        with gzip.open(paths['observations'], 'wt', encoding='utf-8', compresslevel=3) as observations, \
             gzip.open(paths['profiles'], 'wt', encoding='utf-8', compresslevel=3) as profiles, \
             gzip.open(paths['assignments'], 'wt', encoding='utf-8', compresslevel=3) as assignments:
            for local, frame in enumerate(range(start, stop + 1), 1):
                obs, profile, assignment, source = prepare.build_frame(local, meta[frame])
                assert source['prediction_path'] == str(raw_dir / f'{frame:06d}.json')
                for item, handle in ((obs, observations), (profile, profiles), (assignment, assignments)):
                    handle.write(json.dumps(item, ensure_ascii=False, separators=(',', ':'), allow_nan=False) + '\n')
    finally:
        prepare.RAW = previous
    return {key: descriptor(path) for key, path in paths.items()}


def main():
    output = HERE / 'public/PREDICTION_SOURCE_MANIFEST.json'
    assert not output.exists(), output
    protocol = json.loads((BASE / 'protocol.json').read_text(encoding='utf-8'))
    meta = {row['frame']: row for row in map(json.loads, (DATA / 'manifest.jsonl').read_text(encoding='utf-8').splitlines())}
    result = dict(status='FROZEN_NO_GT_OPEN', segments={},
                  baseline_protocol=descriptor(BASE / 'protocol.json'),
                  old_prepare=descriptor(OLD / 'prepare.py'),
                  aligned_manifest=descriptor(DATA / 'manifest.jsonl'),
                  rasterization='1920x1080 polygon points -> (point+0.5)/3-0.5 -> rint -> cv2.fillPoly on 640x360; union by native group_id',
                  producer='20-frame saved SAM3 batches; first covering batch published by postprocess.py; 5-frame overlap',
                  postprocess=descriptor(Path('E:/CAU/D-MOT/tools/prelabel_feeding_20260924/postprocess.py')))
    for source in ('SOURCE_OLD', 'SOURCE_BASELINE'):
        result['segments'][source] = {}
        for index, (name, (start, stop)) in enumerate(SEGMENTS.items()):
            old_dir = prepare.RAW
            baseline = Path(protocol['segments'][index]['prediction_dir'])
            assert protocol['segments'][index]['range'] == [start, stop]
            raw_dir = old_dir if source == 'SOURCE_OLD' else baseline
            assert raw_dir.is_dir()
            old_private = OLD / 'private' / name
            if raw_dir == old_dir:
                derived = {kind: descriptor(old_private / f'{kind}.jsonl.gz')
                           for kind in ('observations', 'profiles', 'assignments')}
                previous_sources = json.loads((old_private / 'sources.json').read_text(encoding='utf-8'))
            else:
                derived = make_baseline_segment(name, start, stop, raw_dir, meta)
                previous_sources = None
            frames = []
            for local, frame in enumerate(range(start, stop + 1), 1):
                item = raw_dir / f'{frame:06d}.json'
                raw = item.read_bytes()
                pred = json.loads(raw)
                native_count = len({int(shape['group_id']) for shape in pred['shapes']})
                depth = DATA / meta[frame]['depth_aligned']
                row = dict(original_frame=frame, local_frame=local,
                           prediction_path=str(item), prediction_sha256=hashlib.sha256(raw).hexdigest(),
                           prediction_bytes=len(raw), rgb_sha256=meta[frame]['source_rgb_sha256'],
                           depth_path=str(depth), depth_sha256=sha(depth), depth_bytes=depth.stat().st_size,
                           native_count=native_count, producer_batch=producer_batch(frame, source))
                if previous_sources is not None:
                    old = previous_sources[local - 1]
                    assert (old['frame'], old['prediction_sha256'], old['depth_sha256'], old['native_count']) == \
                           (frame, row['prediction_sha256'], row['depth_sha256'], native_count)
                frames.append(row)
            result['segments'][source][name] = dict(start=start, stop=stop,
                                                     prediction_dir=str(raw_dir), derived=derived, frames=frames)
            print(source, name, len(frames), flush=True)
    save(output, result)
    print('FROZEN', sha(output), flush=True)


if __name__ == '__main__':
    main()
