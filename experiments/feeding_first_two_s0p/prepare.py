"""Build causal Z4Q inputs from saved, unedited FEEDING SAM3 predictions.

Human labels are deliberately absent from this module.  The aligned depth NPZ
also contains an annotation-derived instance_id plane; only depth_mm is read.
"""
import gzip
import hashlib
import json
import os
import sys
from pathlib import Path

os.environ.update(CUDA_VISIBLE_DEVICES='', OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1',
                  MKL_NUM_THREADS='1', NUMEXPR_NUM_THREADS='1')

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = Path('E:/CAU/D-MOT/data/AlignedFeeding_v1')
RAW = Path('E:/CAU/D-MOT/data/AnnotationFeeding_20260924/ML/labels_raw')
sys.path.insert(0, 'E:/CAU/D-MOT/tools/sam3_depth_birth_inherit_20260917')
sys.path.insert(0, 'E:/CAU/D-MOT/tools/jev_z4q_scene_v1_20260922/deps')
from features import stats, exclusive_core  # noqa: E402
from pycocotools import mask as coco  # noqa: E402

cv2.setNumThreads(1)
KERNEL = np.ones((7, 7), np.uint8)
SEGMENTS = {'feeding_000000_000199': (0, 199), 'feeding_000351_000555': (351, 555)}


def digest(path):
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def write_new(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write('\n')


def prediction_masks(shapes):
    masks = {}
    scores = {}
    for shape in shapes:
        identity = int(shape['group_id'])
        item = masks.setdefault(identity, np.zeros((360, 640), np.uint8))
        points = np.rint((np.asarray(shape['points'], dtype=float) + .5) / 3 - .5).astype(np.int32)
        cv2.fillPoly(item, [points], 1)
        scores[identity] = max(scores.get(identity, 0.), float(shape.get('score') or 0.))
    assert all(np.any(item) for item in masks.values())
    return masks, scores


def build_frame(local_frame, meta):
    global_frame = meta['frame']
    name = f'{global_frame:06d}'
    raw_path = RAW / f'{name}.json'
    depth_path = DATA / meta['depth_aligned']
    assert raw_path.is_file() and depth_path.is_file()
    shapes = json.loads(raw_path.read_text(encoding='utf-8'))['shapes']
    with np.load(depth_path) as sensor:
        # instance_id is generated from the later human annotations: never read it.
        assert 'depth_mm' in sensor.files
        depth = sensor['depth_mm']
    assert depth.shape == (360, 640)
    masks, scores = prediction_masks(shapes)
    occupancy = np.zeros((360, 640), np.uint16)
    for item in masks.values():
        occupancy += item
    neighbors = {n: [] for n in masks}
    keys = sorted(masks)
    for i, n in enumerate(keys):
        expanded = cv2.dilate(masks[n], KERNEL).astype(bool)
        for other in keys[i+1:]:
            if np.any(expanded & masks[other].astype(bool)):
                neighbors[n].append(other)
                neighbors[other].append(n)
    observations, profiles, encoded = [], [], {}
    for n in keys:
        actual = masks[n].astype(bool)
        ys, xs = np.where(actual)
        box = [float(xs.min()), float(ys.min()), float(xs.max()+1), float(ys.max()+1)]
        whole = stats(depth, actual)
        exclusive, core = exclusive_core(actual, occupancy)
        core_stat = stats(depth, core)
        token = f'n:{n}'
        observations.append(dict(id=n, mask=token, box=box, area=int(actual.sum()),
                                 score_birth=scores[n], presence=None,
                                 depth={k:whole[k] for k in ('n','valid_fraction','median','mad')},
                                 neighbors=neighbors[n]))
        profiles.append(dict(id=n, mask=token, area=int(actual.sum()), box=box,
                             neighbors=neighbors[n], score_birth=scores[n], presence=None,
                             whole=whole, core=core_stat,
                             overlap_pixels=int((actual & (occupancy > 1)).sum()),
                             exclusive_area=int(exclusive.sum()), core_area=int(core.sum())))
        rle = coco.encode(np.asfortranarray(masks[n]))
        encoded[token] = dict(size=list(rle['size']), counts=rle['counts'].decode('ascii'))
    now = meta['rgb_timestamp_us'] / 1e6
    common = dict(frame=local_frame, global_frame=global_frame, time=now)
    observation = dict(common, observations=observations,
                       native=[dict(id=n, mask=f'n:{n}') for n in keys])
    profile = dict(common, evidence_max_global_frame=global_frame, observations=profiles)
    assignment = dict(frame=local_frame, global_frame_id=global_frame, time=now,
                      masks=encoded, variants={'N0':observation['native']})
    source = dict(frame=global_frame, prediction_path=str(raw_path),
                  prediction_bytes=raw_path.stat().st_size, prediction_sha256=digest(raw_path),
                  depth_path=str(depth_path), depth_bytes=depth_path.stat().st_size,
                  depth_sha256=digest(depth_path), native_count=len(keys))
    return observation, profile, assignment, source


def prepare_segment(name, start, stop):
    target = HERE / 'private' / name
    assert not target.exists(), target
    target.mkdir(parents=True)
    manifest = {row['frame']:row for row in map(json.loads,
                (DATA/'manifest.jsonl').read_text(encoding='utf-8').splitlines())}
    assert set(range(start, stop+1)).issubset(manifest)
    paths = {kind:target/f'{kind}.jsonl.gz' for kind in ('observations','profiles','assignments')}
    sources = []
    with gzip.open(paths['observations'],'wt',encoding='utf-8',compresslevel=3) as obs_file, \
         gzip.open(paths['profiles'],'wt',encoding='utf-8',compresslevel=3) as profile_file, \
         gzip.open(paths['assignments'],'wt',encoding='utf-8',compresslevel=3) as assign_file:
        for local, global_frame in enumerate(range(start,stop+1),1):
            row = manifest[global_frame]
            assert row['segment'].lower() == name
            obs, profile, assignment, source = build_frame(local,row)
            for item, handle in ((obs,obs_file),(profile,profile_file),(assignment,assign_file)):
                handle.write(json.dumps(item,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n')
            sources.append(source)
            if local % 50 == 0:
                print(name,local,'/',stop-start+1,flush=True)
    write_new(target/'sources.json',sources)
    result=dict(name=name,start=start,stop=stop,frames=stop-start+1,
                prediction_source='saved_2026_09_24_SAM3_20_frame_batches_with_5_frame_overlap',
                depth_source='aligned_depth_mm_only; annotation_instance_id_not_read',
                inputs={str(p):dict(bytes=p.stat().st_size,sha256=digest(p))
                        for p in (DATA/'manifest.jsonl',)},
                derived={kind:dict(path=str(p),bytes=p.stat().st_size,sha256=digest(p))
                         for kind,p in paths.items()},
                sources_sha256=digest(target/'sources.json'))
    write_new(target/'SOURCE_MANIFEST.json',result)
    return result


if __name__ == '__main__':
    for name,(start,stop) in SEGMENTS.items():
        print(prepare_segment(name,start,stop),flush=True)
