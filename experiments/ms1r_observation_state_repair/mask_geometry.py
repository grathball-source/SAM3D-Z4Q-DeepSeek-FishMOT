"""Prediction-mask geometry only; no RGB or ground truth is read here."""
import numpy as np


def decode_counts(encoded):
    """Decode the compressed COCO RLE count stream."""
    counts = []
    pos = 0
    while pos < len(encoded):
        value = shift = 0
        while True:
            code = ord(encoded[pos]) - 48
            pos += 1
            value |= (code & 31) << shift
            shift += 5
            if not code & 32:
                if code & 16:
                    value |= -1 << shift
                break
        if len(counts) > 2:
            value += counts[-2]
        assert value >= 0
        counts.append(value)
    return counts


def mask(rle):
    height, width = rle['size']
    counts = decode_counts(rle['counts'])
    assert sum(counts) == height * width
    flat = np.empty(height * width, dtype=bool)
    start = 0
    for index, length in enumerate(counts):
        flat[start:start + length] = bool(index & 1)
        start += length
    return flat.reshape((height, width), order='F')


def shifted_coverage(previous, current, dx, dy, tolerance):
    """Fraction of predicted source pixels within tolerance of current mask."""
    from scipy.ndimage import distance_transform_edt

    dx, dy, tolerance = round(dx), round(dy), max(0, round(tolerance))
    h, w = previous.shape
    translated = np.zeros_like(previous)
    x0, x1 = max(0, -dx), min(w, w - dx)
    y0, y1 = max(0, -dy), min(h, h - dy)
    if x0 >= x1 or y0 >= y1:
        return 0.0
    translated[y0 + dy:y1 + dy, x0 + dx:x1 + dx] = previous[y0:y1, x0:x1]
    ys, xs = np.nonzero(translated)
    if not len(xs):
        return 0.0
    left, right = max(0, xs.min() - tolerance), min(w, xs.max() + tolerance + 1)
    top, bottom = max(0, ys.min() - tolerance), min(h, ys.max() + tolerance + 1)
    local = current[top:bottom, left:right]
    if not local.any():
        return 0.0
    distance = distance_transform_edt(~local)
    return float(np.count_nonzero(distance[ys - top, xs - left] <= tolerance) / len(xs))
