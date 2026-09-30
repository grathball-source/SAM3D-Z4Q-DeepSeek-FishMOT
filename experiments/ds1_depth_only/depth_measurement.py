"""Candidate-independent measurements from the aligned raw depth plane."""
from __future__ import annotations

import cv2
import numpy as np
from pycocotools import mask as coco

KERNEL = np.ones((7, 7), np.uint8)


def decode(rle):
    return coco.decode(dict(size=rle['size'], counts=rle['counts'].encode('ascii'))).astype(bool)


def statistics(depth, region):
    values = np.asarray(depth[region], dtype='f8')
    finite = values[np.isfinite(values) & (values > 0)]
    out = dict(area=int(region.sum()), n=int(finite.size),
               valid_fraction=float(finite.size / max(1, values.size)),
               median=None, mad=None, q10=None, q25=None, q75=None, q90=None)
    if finite.size:
        median = float(np.median(finite))
        q10, q25, q75, q90 = np.quantile(finite, [.1, .25, .75, .9])
        out.update(median=median, mad=float(np.median(np.abs(finite-median))),
                   q10=float(q10), q25=float(q25), q75=float(q75), q90=float(q90))
    return out


def usable(core):
    return (core['n'] >= 16 and core['valid_fraction'] >= .2 and
            core['median'] is not None and core['median'] > 0 and
            core['mad'] is not None and np.isfinite(core['mad']) and core['mad'] >= 0 and
            max(15., 1.4826*core['mad']) <= 60.)


def extract_frame(depth, assignment, profiles):
    """Return full-frame background and independent per-mask whole/core facts.

    The same eroded exclusive core and n/fraction/median/MAD convention as
    FEEDING prepare.py is used; no annotation plane is opened here.
    """
    assert depth.shape == (360, 640)
    masks = {int(key[2:]): decode(rle) for key, rle in assignment['masks'].items()}
    occupancy = np.zeros(depth.shape, np.uint16)
    for region in masks.values():
        occupancy += region
    out = {}
    for native, region in masks.items():
        exclusive = region & (occupancy == 1)
        core_region = cv2.erode(exclusive.astype('u1'), KERNEL, iterations=1).astype(bool)
        whole, core = statistics(depth, region), statistics(depth, core_region)
        old = profiles[native]
        for name, current in (('whole', whole), ('core', core)):
            for field in ('n', 'valid_fraction', 'median', 'mad'):
                assert current[field] == old[name][field], (native, name, field, current[field], old[name][field])
        ys, xs = np.nonzero(region)
        components = cv2.connectedComponents(region.astype('u1'), connectivity=8)[0]-1
        bbox_center = [(float(xs.min())+float(xs.max()))/2, (float(ys.min())+float(ys.max()))/2]
        centroid = [float(xs.mean()), float(ys.mean())]
        out[native] = dict(native=native, source='RAW_SENSOR_OR_ALIGNED_RAW',
            whole=whole, core=core, core_usable=bool(usable(core)),
            core_whole_area_ratio=core['area']/max(1, whole['area']),
            components=int(components), centroid_bbox_delta_px=[centroid[i]-bbox_center[i] for i in (0, 1)],
            core_whole_median_delta_mm=(core['median']-whole['median']
                if core['median'] is not None and whole['median'] is not None else None))
    full = statistics(depth, np.ones(depth.shape, bool))
    return full, out, masks, occupancy
