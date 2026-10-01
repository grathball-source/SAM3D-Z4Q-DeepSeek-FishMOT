"""Depth-independent core of every exclusive SAM-mask component.

Distance is Euclidean distance between pixel centers and the nearest zero pixel.
The component crop is zero padded, including when it touches the image boundary.
"""
from __future__ import annotations

import cv2
import numpy as np

FORMULA = 'distance >= max(1.5, min(3.0, 0.5 * component_max_distance))'


def adaptive_core(region, occupancy):
    """Return a fresh boolean ROI and geometry facts, without reading depth.

Each piece describes an original 8-connected *exclusive-mask* component, not a
depth surface. ``samples`` counts retained ROI pixels; valid depth n/fraction/MAD
must still be measured independently and pass the unchanged quality rule.
"""
    region, occupancy = np.asarray(region), np.asarray(occupancy)
    assert region.ndim == 2 and region.size and occupancy.shape == region.shape
    exclusive = region.astype(bool, copy=False) & (occupancy == 1)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(
        exclusive.astype('u1'), connectivity=8)
    roi = np.zeros(region.shape, dtype=bool)
    pieces = []
    for label in range(1, count):
        x,y,width,height,area = map(int, stats[label])
        component = labels[y:y+height, x:x+width] == label
        distance = cv2.distanceTransform(
            np.pad(component.astype('u1'), 1), cv2.DIST_L2,
            cv2.DIST_MASK_PRECISE)[1:-1, 1:-1]
        maximum = float(distance[component].max())
        threshold = max(1.5, min(3.0, .5*maximum))
        selected = component & (distance >= threshold)
        roi[y:y+height, x:x+width] |= selected
        pieces.append(dict(component_id=label, area=area, dt_max_px=maximum,
                           threshold_px=threshold, samples=int(selected.sum())))
    return roi, dict(method='EXCLUSIVE_COMPONENT_ADAPTIVE_L2_CORE', formula=FORMULA,
        connectivity=8, distance_type='DIST_L2', distance_mask='DIST_MASK_PRECISE',
        exterior='ZERO_PADDED_COMPONENT_CROP', mask_area=int(region.astype(bool).sum()),
        exclusive_area=int(exclusive.sum()), roi_area=int(roi.sum()),
        component_count=count-1, pieces=pieces,
        samples_meaning='GEOMETRIC_ROI_PIXELS_NOT_VALID_DEPTH_MEASUREMENTS',
        surface_identity='UNKNOWN')
