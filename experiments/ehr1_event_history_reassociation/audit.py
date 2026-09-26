"""Pre-send source, sensor, history, and paired-request checks; never reads GT."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
from pathlib import Path

from prepare import AO1, DEV_DEPTH, DEV_OBS, VAL, put, read, sha

DATA = Path('/home/data2/xiongxiong/d-mot/data/AlignedDataset_v1')
ASSIGN = {
    'development': Path('/home/data2/xiongxiong/d-mot/experiments/sam3_occlusion_identity_20260915/identity_cpu10_20260915/run_8400/assignments.jsonl.gz'),
    'validation': Path('/home/data2/xiongxiong/d-mot/experiments/sam3_i3_validation_cpu16_20260915/run_validation_2888/assignments.jsonl.gz'),
}
SENSOR_SOURCE = Path('/home/xiongxiong/dmot-experiments/sam3_depth_birth_inherit_20260917')


def selected(path, frames):
    out = {}
    with gzip.open(path, 'rt', encoding='utf-8') as f:
        for line in f:
            row = json.loads(line)
            if row['frame'] in frames:
                out[row['frame']] = row
    assert set(out) == set(frames), (path, set(frames)-set(out))
    return out


def validate_plan(run):
    plan = read(run/'sender/PLAN.json')
    assert len(plan['requests']) == 25
    assert [(r['case'], r['arm']) for r in plan['requests']] == [
        (f'B{i:02}', arm) for i in range(1, 6) for arm in ('E', 'H-2D', 'H-D', 'H-D-REPEAT', 'H-D-PERMUTE')]
    assert (26 * plan['reserve_each_usd']) <= plan['cap_usd']
    record = []
    for i in range(0, 25, 5):
        five = plan['requests'][i:i+5]
        p = [json.loads(x['text']) for x in five]
        assert five[2]['text'] == five[3]['text'] and five[2]['images'] == five[3]['images']
        perm = json.loads(json.dumps(p[2]))
        for c in perm['hypotheses']:
            c['id'] = 'H2' if c['id'] == 'H1' else 'H1'
        perm['hypotheses'].reverse()
        assert perm == p[4], 'permutation changed other evidence'
        assert p[1]['IMAGE_INDEX'] == p[2]['IMAGE_INDEX']
        for arm, packet, req in zip(('E','H-2D','H-D','H-D-REPEAT','H-D-PERMUTE'), p, five):
            q = packet['q_frame']
            assert all(x['frame'] <= q for x in packet['IMAGE_INDEX'])
            assert all(x['source_frame'] <= q for part in ('PRE_HISTORY', 'POST_HISTORY_TO_Q')
                       for v in packet[part].values() for x in v['observations'])
            assert all(x['source_frame'] <= q for x in packet['INTERACTION_OBSERVATIONS'])
            assert len(req['images']) == len(packet['IMAGE_INDEX']) if arm != 'E' else len(req['images']) == 2
            for img in req['images']:
                path = run/'sender/media'/img['media_file']
                assert path.is_file() and path.stat().st_size == img['bytes'] and sha(path) == img['sha256']
            text = req['text']
            assert all(word not in text for word in ('SCORE_KEY', 'GT2', 'GT6', '/home/', 'file-api-', 'api_key'))
            if arm in ('E', 'H-2D'):
                assert '"depth"' not in text
            record.append(dict(attempt_id=req['attempt_id'], text_bytes=len(text.encode()), images=len(req['images']),
                               image_bytes=sum(x['bytes'] for x in req['images'])))
    return record


def sensor_audit(run):
    import cv2
    import numpy as np
    from pycocotools import mask as mu
    sys.path.insert(0, str(SENSOR_SOURCE))
    from features import RawSensor, array_sha, stats, exclusive_core

    ao1 = read(AO1/'public/SOURCE_MANIFEST.json')
    sampling = {}
    for case in ao1['cases']:
        start_post = min(x['frame'] for x in case['V1']['roles'] if x['role'] in 'XY')
        sample = {case['trigger_frame']-1, case['trigger_frame'], start_post, case['query_frame']}
        sampling.setdefault(case['split'], set()).update(sample)
    rows = {}
    for split, frames in sampling.items():
        op = DEV_OBS if split == 'development' else VAL/'observations_validation.jsonl.gz'
        dp = DEV_DEPTH if split == 'development' else VAL/'features_validation.jsonl.gz'
        assert sha(op) == ao1['source_stream_sha256'][split+'_observations']
        rows[split] = (selected(op, frames), selected(dp, frames), selected(ASSIGN[split], frames))
    samples = []
    sensor = RawSensor()
    try:
        jobs = sorted((row['global_frame'], split, frame) for split, (_, fs, _) in rows.items() for frame, row in fs.items())
        for global_frame, split, frame in jobs:
            obs, fs, aa = rows[split]
            o, f, a = obs[frame], fs[frame], aa[frame]
            assert o['time'] == f['time'] == a['time']
            assert f['evidence_max_global_frame'] <= global_frame and f['sensor_available']
            raw = sensor.load(global_frame)
            assert raw.shape == (360, 640) and array_sha(raw) == f['raw_array_sha256']
            rgb_path = DATA/'rgb_original'/f'{global_frame-1:06d}.jpg'
            rgb = cv2.imread(str(rgb_path))
            assert rgb is not None and rgb.shape[:2] == (1080, 1920)
            masks = {}
            for n in a['variants']['N0']:
                encoded = a['masks'][n['mask']]
                masks[n['id']] = mu.decode(dict(size=encoded['size'], counts=encoded['counts'].encode())).astype(bool)
            occupancy = sum((m.astype('u2') for m in masks.values()), np.zeros(raw.shape, 'u2'))
            checked = 0
            for d in f['observations']:
                mask = masks[d['id']]
                _, core = exclusive_core(mask, occupancy)
                assert stats(raw, mask) == d['whole']
                assert stats(raw, core) == d['core']
                checked += 1
            samples.append(dict(case_splits=split, frame=frame, global_frame=global_frame,
                                rgb_path=str(rgb_path), rgb_sha256=sha(rgb_path),
                                raw_array_sha256=f['raw_array_sha256'], actual_masks_checked=checked,
                                invalid_depth_pixels=int((raw <= 0).sum()),
                                overlap_mask_count=sum(d['overlap_pixels'] > 0 for d in f['observations'])))
    finally:
        sensor.close()
    put(run/'public/DEPTH_INPUT_AUDIT.json', dict(status='ACTUAL_RAW_HDF5_RGB_MASK_PROFILE_PARITY',
        source='aligned/raw_depth_mm; frame_id from dataset manifest; no restored or GT channel',
        unit='mm in source array; external scene calibration and water-surface reference unverified',
        samples=samples))
    return samples


def main(run):
    requests = validate_plan(run)
    samples = sensor_audit(run)
    put(run/'public/PREFLIGHT.json', dict(status='PASS', formal_requests=25, smoke_max=1,
        cap_usd=3, reserve_usd=26*.11, actual_depth_frames=len(samples),
        max_text_bytes=max(x['text_bytes'] for x in requests),
        max_images=max(x['images'] for x in requests), requests=requests))
    print(json.dumps(dict(status='PASS', depth_frames=len(samples), max_text_bytes=max(x['text_bytes'] for x in requests))))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', type=Path, required=True)
    main(parser.parse_args().run)
