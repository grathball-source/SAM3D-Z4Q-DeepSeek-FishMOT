"""Fixed-grid edge proximity diagnostics, never identity or registration truth.

Only the returned numeric dictionary is public. RGB, raster masks, edge maps
and distance arrays remain private. No shifts, registration search or resizing.
"""
from pathlib import Path

import cv2
import numpy as np


PARAMETERS = dict(depth_edge_mm=30.,
    depth_edge_definition='HORIZONTAL_VERTICAL_VALID_PAIRS_BOTH_ENDPOINTS',
    mask_boundary='MASK_MINUS_3X3_EROSION_ZERO_BORDER',
    roi='21X21_SQUARE_DILATION_10PX_CHEBYSHEV_RADIUS',
    rgb_edge='UINT8_BGR_TO_GRAY_CANNY_50_100', distance='EUCLIDEAN_PIXEL_CENTERS',
    shift_search=False, resize=False, RGB_is_private_proxy=True)


def _proximity(boundary, edges):
    """Euclidean nearest-edge distance; absence stays UNKNOWN, not infinity."""
    n = int(boundary.sum())
    if not n or not edges.any():
        return dict(status='UNKNOWN', reason='EMPTY_MASK_BOUNDARY' if not n else 'NO_MEASURED_EDGE',
            query_n=n, n=0, median_px=None, p90_px=None,
            fractions_within_px={str(k): None for k in (1, 3, 5, 10)}), np.full(edges.shape, np.nan)
    distances = cv2.distanceTransform((~edges).astype('uint8'), cv2.DIST_L2, cv2.DIST_MASK_PRECISE)
    selected = distances[boundary]
    return dict(status='AVAILABLE', query_n=n, n=n,
        median_px=float(np.median(selected)), p90_px=float(np.quantile(selected, .9)),
        fractions_within_px={str(k): float(np.mean(selected <= k)) for k in (1, 3, 5, 10)}), distances


def spatial_metrics(mask, depth, rgb_bgr):
    """Measure at the exact input grid; depth discontinuities need two valid pixels."""
    assert isinstance(mask, np.ndarray) and mask.ndim == 2 and mask.dtype == bool
    assert isinstance(depth, np.ndarray) and depth.shape == mask.shape and np.issubdtype(depth.dtype, np.number)
    assert isinstance(rgb_bgr, np.ndarray) and rgb_bgr.shape == (*mask.shape, 3) and rgb_bgr.dtype == np.uint8
    valid = np.isfinite(depth) & (depth > 0)
    edges = np.zeros(mask.shape, bool)
    horizontal = valid[:, :-1] & valid[:, 1:] & (np.abs(depth[:, 1:].astype('f8') - depth[:, :-1]) >= 30.)
    vertical = valid[:-1, :] & valid[1:, :] & (np.abs(depth[1:, :].astype('f8') - depth[:-1, :]) >= 30.)
    edges[:, :-1] |= horizontal
    edges[:, 1:] |= horizontal
    edges[:-1, :] |= vertical
    edges[1:, :] |= vertical
    eroded = cv2.erode(mask.astype('uint8'), np.ones((3, 3), 'uint8'),
        borderType=cv2.BORDER_CONSTANT, borderValue=0).astype(bool)
    boundary = mask & ~eroded
    roi = cv2.dilate(mask.astype('uint8'), np.ones((21, 21), 'uint8'),
        borderType=cv2.BORDER_CONSTANT, borderValue=0).astype(bool)
    rgb_edges = cv2.Canny(cv2.cvtColor(rgb_bgr, cv2.COLOR_BGR2GRAY), 50, 100).astype(bool)
    depth_near, depth_distance = _proximity(boundary, edges)
    rgb_near, rgb_distance = _proximity(boundary, rgb_edges)
    coverage = {}
    for name, region in (('mask', mask), ('mask_inner_boundary', boundary), ('roi10', roi)):
        count = int(region.sum())
        available = int((valid & region).sum())
        coverage[name] = dict(pixel_n=count, valid_depth_pixel_n=available,
            valid_depth_fraction=available / count if count else None)
    metrics = dict(status='MEASURED', shape=list(mask.shape), rules=PARAMETERS.copy(),
        coverage=coverage,
        edge_counts={name: dict(full_frame=int(edge.sum()), inside_mask=int((edge & mask).sum()),
            inside_roi10=int((edge & roi).sum())) for name, edge in (('depth', edges), ('rgb', rgb_edges))},
        boundary_to_depth_edge=depth_near, boundary_to_rgb_edge=rgb_near,
        physical_registration_accuracy='UNKNOWN', mask_ownership='UNKNOWN', identity='UNKNOWN')
    debug = dict(mask_inner_boundary=boundary, valid_depth=valid, depth_edges=edges, rgb_edges=rgb_edges,
        roi10=roi, depth_distance_px=depth_distance, rgb_distance_px=rgb_distance)
    return metrics, debug


def render_figure(path, rgb_bgr, depth, masks, target_native, fact_id, metrics, debug):
    """Four same-coordinate private panels with all intersecting mask outlines."""
    path = Path(path).resolve()
    assert 'private' in {part.lower() for part in path.parts}, 'Private RGB/depth figures cannot be public'
    assert path.suffix.lower() == '.png' and not path.exists(), 'Never replace a diagnostic raster'
    target = masks[target_native]
    assert depth.shape == (360, 640), 'Actual frozen grid is 640x360'
    assert all(mask.shape == depth.shape and mask.dtype == bool for mask in masks.values())
    actual, maps = spatial_metrics(target, depth, rgb_bgr)
    assert actual == metrics, 'Figure facts do not match actual input'
    assert set(maps) == set(debug)
    assert all(np.array_equal(maps[key], debug[key], equal_nan=True) for key in maps), 'Figure raster mismatch'
    yy, xx = np.where(target)
    assert len(xx), 'No selected mask pixels'
    x0, y0 = max(0, int(xx.min()) - 24), max(0, int(yy.min()) - 24)
    x1, y1 = min(640, int(xx.max()) + 25), min(360, int(yy.max()) + 25)
    crop = np.s_[y0:y1, x0:x1]
    extent = (x0 - .5, x1 - .5, y1 - .5, y0 - .5)
    cropped_depth = depth[crop]
    finite = cropped_depth[np.isfinite(cropped_depth) & (cropped_depth > 0)]
    lo, hi = map(float, np.quantile(finite, [.02, .98])) if len(finite) else (0., 1.)
    if hi <= lo:
        hi = lo + 1.
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 4, figsize=(18, 6))
    views = (cv2.cvtColor(rgb_bgr[crop], cv2.COLOR_BGR2RGB),
        np.where(np.isfinite(cropped_depth) & (cropped_depth > 0), cropped_depth, np.nan),
        debug['depth_edges'][crop], debug['rgb_edges'][crop])
    titles = ('Private original RGB', 'Raw aligned depth [mm]', 'Measured depth edges >=30mm', 'RGB gray Canny 50/100')
    for column, (ax, view, title) in enumerate(zip(axes, views, titles, strict=True)):
        kwargs = dict(cmap='viridis', vmin=lo, vmax=hi) if column == 1 else dict(cmap='gray', vmin=0, vmax=1) if column > 1 else {}
        plotted = ax.imshow(view, extent=extent, interpolation='nearest', **kwargs)
        for native, region in sorted(masks.items()):
            outline = region & ~cv2.erode(region.astype('uint8'), np.ones((3, 3), 'uint8'),
                borderType=cv2.BORDER_CONSTANT, borderValue=0).astype(bool)
            points_y, points_x = np.where(outline[crop])
            if len(points_x):
                ax.scatter(points_x + x0, points_y + y0, s=2 if native == target_native else 1,
                    color='cyan' if native == target_native else 'orange', alpha=.9)
        ax.set_title(title, fontsize=10)
        ax.set_xlim(x0 - .5, x1 - .5)
        ax.set_ylim(y1 - .5, y0 - .5)
        ax.set_xlabel('Original grid x [px]')
        if column == 1:
            fig.colorbar(plotted, ax=ax, fraction=.045, pad=.025)
    axes[0].set_ylabel('Original grid y [px]')
    fig.suptitle(f'{fact_id}\nCyan: actual selected mask; orange: other actual masks. '
        'Edge proximity is not registration or identity truth.', fontsize=11)
    near = metrics['boundary_to_depth_edge']
    fig.text(.02, .02, f'Depth-edge proximity: {near["status"]}; boundary n={near["query_n"]}; '
        f'median={near["median_px"]} px; p90={near["p90_px"]} px. '
        'No GT, shifts, resizing, future frames or identity actions.', fontsize=9)
    fig.tight_layout(rect=(0, .06, 1, .88))
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open('xb') as handle:
            fig.savefig(handle, format='png', dpi=130)
    finally:
        plt.close(fig)
    return dict(fact_id=fact_id, target_native=int(target_native),
        roi=dict(xyxy=[x0, y0, x1, y1], full_shape=[360, 640], padding_px=24,
            transform='crop_xy=original_xy-[x0,y0]; numerical rasters are not resampled'),
        depth_display_limits_mm=[lo, hi], RGB_private=True, GT=False,
        physical_registration_accuracy='UNKNOWN', identity='UNKNOWN')
