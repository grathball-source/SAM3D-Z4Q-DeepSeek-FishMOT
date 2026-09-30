"""Reuse frozen source decoding and measurements, without tracking/model imports."""
import gzip
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT/'experiments/feeding_first_two_s0p'))
from prepare import DATA, RAW, digest, write_new, prediction_masks  # noqa: E402
sys.path.insert(0, str(ROOT/'experiments/ds1_depth_only'))
from depth_measurement import decode, extract_frame, statistics, KERNEL  # noqa: E402
import cv2  # noqa: E402
import numpy as np  # noqa: E402
from pycocotools import mask as coco  # noqa: E402

SEGMENTS = {'feeding_000701_001060': (701, 1060),
            'feeding_001201_001906': (1201, 1906)}
OLD = ROOT/'experiments/ds2_depth_transfer_validation'
CFG = json.loads((HERE/'CONFIG.json').read_text(encoding='utf-8'))


def records(path):
    with gzip.open(path, 'rt', encoding='utf-8') as handle:
        yield from map(json.loads, handle)


def encoded(mask):
    out = coco.encode(np.asfortranarray(mask.astype('u1')))
    return dict(size=out['size'], counts=out['counts'].decode('ascii'))


def dump_line(handle, value):
    handle.write(json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':'))+'\n')


def artifact(path):
    path = Path(path)
    return dict(path=str(path), bytes=path.stat().st_size, sha256=digest(path))


def verify(item):
    path = Path(item['path'])
    assert path.stat().st_size == item['bytes'] and digest(path) == item['sha256'], path


def load_depth(path):
    with np.load(path) as sensor:
        return sensor['depth_mm'].copy()
