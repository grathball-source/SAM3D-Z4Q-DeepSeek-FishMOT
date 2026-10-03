"""Same-frame relative depth supports; never select a fish, layer or identity.

The affine fit is DS3's fixed five-step Huber IRLS equation. Unlike DS3,
samples are unique physical sources and every two-sided component is retained.
Only this module's second return value contains private pixel arrays.
"""
from __future__ import annotations

import copy
import json
import math
from pathlib import Path

import cv2
import numpy as np

from mixed_depth import array_binding, PARAMETERS as OLD_PARAMETERS, _old

ROOT = Path(__file__).resolve().parents[2]
CONFIG_SOURCE = ROOT / 'experiments/ds3_depth_foreground_filter/CONFIG.json'
_cfg = json.loads(CONFIG_SOURCE.read_text(encoding='utf-8'))
PARAMETERS = dict(OLD_PARAMETERS, background_max_condition=_cfg['background_max_condition'],
                  irls_steps=_cfg['irls_steps'], huber_c=_cfg['huber_c'])
assert (PARAMETERS['annulus_inner_px'], PARAMETERS['annulus_outer_px'],
        PARAMETERS['neighbor_margin_px'], PARAMETERS['background_minimum_n'],
        PARAMETERS['minimum_layer_n'], PARAMETERS['minimum_coverage_fraction'],
        PARAMETERS['scale_floor_mm'], PARAMETERS['max_scale_mm'], PARAMETERS['irls_steps'],
        PARAMETERS['huber_c'], PARAMETERS['background_max_condition']) == (5, 20, 3, 64, 16, .2, 15., 60., 5, 1.5, 100.)

SCHEMA = 'DS22_SAME_FRAME_BACKGROUND_RELATIVE_SUPPORT_V1'
ALLOWED_FIELDS = {'depth_mm', 'source_index', 'frame_id', 'aligned/raw_depth_mm',
                  'aligned/raw_source_index', 'native/original_depth_mm', 'current_native_depth_mm'}


def _dilate(mask, radius):
    return cv2.dilate(mask.astype('u1'), np.ones((2 * radius + 1,) * 2, 'u1')).astype(bool)


def _summary(values, area):
    return _old._stats(np.asarray(values, dtype='f8'), area)


def _selected(roi, valid, index, excluded_sources):
    return _old._canonical_selection(roi, valid, index, excluded_sources)


def _binding(positions, index, depth):
    return dict(selected_pixel_binding=array_binding(positions),
                selected_source_index_binding=array_binding(index.ravel()[positions]),
                selected_depth_binding=array_binding(depth.ravel()[positions]))


def _coordinates(positions, width, cx, cy):
    yy, xx = np.divmod(positions, width)
    return np.column_stack((np.ones(len(positions)),
        (xx - cx) / PARAMETERS['annulus_outer_px'],
        (yy - cy) / PARAMETERS['annulus_outer_px']))


def _range_summary(values):
    values = np.asarray(values, dtype='f8')
    return dict(n=len(values), median=float(np.median(values)) if len(values) else None,
        minimum=float(values.min()) if len(values) else None,
        maximum=float(values.max()) if len(values) else None,
        q90=float(np.quantile(values, .9)) if len(values) else None)


def validate_source(depth, index, native_depth, masks, segment, frame, global_frame, time,
                    source_binding, expected_source_binding=None):
    """Check real arrays and field/frame semantics, beyond a self-consistent hash.

    Aligned camera Z and native sensor Z are different coordinates. Equality
    between these Z values is intentionally not invented as a calibration test.
    A trusted source adapter's expected binding rejects same-frame array swaps.
    """
    assert depth.ndim == index.ndim == native_depth.ndim == 2
    assert depth.size and depth.shape == index.shape
    assert np.issubdtype(index.dtype, np.signedinteger)
    assert isinstance(segment, str) and segment
    assert isinstance(frame, (int, np.integer)) and frame >= 1
    assert isinstance(global_frame, (int, np.integer)) and global_frame >= 0
    assert math.isfinite(time)
    assert source_binding['global_frame'] == global_frame and source_binding['time'] == time
    assert source_binding.get('frame', frame) == frame
    assert not any(source_binding.get(k, False) for k in ('GT_read', 'RGB_read', 'restored_read'))
    fields = source_binding['actual_fields_read'] + source_binding.get('native_fields_read', [])
    assert set(fields) <= ALLOWED_FIELDS, 'Unexposed or non-depth field'
    valid = np.isfinite(depth) & (depth > 0)
    assert np.array_equal(valid, index >= 0), 'Depth/source-index validity mismatch'
    assert np.all(index[valid] < native_depth.size), 'Illegal native source index'
    assert np.all(np.isfinite(native_depth.ravel()[index[valid]]) &
                  (native_depth.ravel()[index[valid]] > 0)), 'Index references a missing native measurement'
    for key, array in [('aligned_depth', depth), ('aligned_source_index', index), ('native_depth', native_depth)]:
        assert source_binding[key] == array_binding(array), f'Actual {key} array differs from source'
    if expected_source_binding is not None:
        assert source_binding == expected_source_binding, 'Trusted actual source binding mismatch'
    assert all(mask.shape == depth.shape for mask in masks.values())
    if source_binding.get('raw_h5') is not None:
        assert source_binding['source_color_index'] + 1 == global_frame
        assert source_binding['h5_row'] >= 0
    return valid


def measure_local_background(depth, source_index, native_depth, masks, native, segment, frame,
                             global_frame, time, *, source_binding, expected_source_binding=None):
    """Return (public numeric/source facts, private full-grid diagnostic arrays).

    Positive residual means farther than the fitted local annulus, negative
    means nearer. These are observed supports, not certified foreground/fish.
    """
    depth, index, sensor = map(np.asarray, (depth, source_index, native_depth))
    regions = {int(n): np.asarray(mask, dtype=bool) for n, mask in masks.items()}
    native = int(native)
    assert native in regions
    valid = validate_source(depth, index, sensor, regions, segment, frame, global_frame, time,
                            source_binding, expected_source_binding)
    own = regions[native]
    other = np.zeros(depth.shape, bool)
    for n, mask in regions.items():
        if n != native:
            other |= mask
    neighbors = _dilate(other, PARAMETERS['neighbor_margin_px'])
    roi = own & ~neighbors
    annulus = (_dilate(own, PARAMETERS['annulus_outer_px']) &
               ~_dilate(own, PARAMETERS['annulus_inner_px']) & ~neighbors)
    own_sources = np.unique(index[own & valid])
    other_sources = np.unique(index[other & valid])
    mask_positions, mask_exclusions = _selected(roi, valid, index, other_sources)
    bg_positions, bg_exclusions = _selected(annulus, valid, index,
        np.union1d(own_sources, other_sources))
    bg_summary = _summary(depth.ravel()[bg_positions], int(annulus.sum()))
    mask_summary = _summary(depth.ravel()[mask_positions], int(own.sum()))
    fact_id = f'{segment}/F{frame}/n:{native}/background_relative/raw'
    facts = dict(schema=SCHEMA, fact_id=fact_id, segment=segment, frame=int(frame),
        global_frame=int(global_frame), time=float(time), native=native, status='UNKNOWN', reason=None,
        source_binding=copy.deepcopy(source_binding), actual_depth_binding=array_binding(depth),
        actual_source_index_binding=array_binding(index), native_depth_binding=array_binding(sensor),
        mask_binding=array_binding(own), neighbor_union_binding=array_binding(other),
        neighbor_exclusion_binding=array_binding(neighbors), sampling_roi_binding=array_binding(roi),
        annulus_binding=array_binding(annulus), parameters=dict(PARAMETERS),
        original_mask_area=int(own.sum()), sampling_roi_area=int(roi.sum()),
        neighbor_overlap_removed_n=int((own & neighbors).sum()),
        mask_summary=mask_summary, mask_source_exclusions=mask_exclusions,
        mask_population_binding=_binding(mask_positions, index, depth),
        background=dict(summary=bg_summary, exclusions=bg_exclusions,
                        population_binding=_binding(bg_positions, index, depth)),
        plane=None, components=[], significant_independent_n=0, qualified_component_n=0,
        qualified_independent_n=0, qualified_mask_source_fraction=None,
        scalar_replacement='NONE', foreground_identity='UNKNOWN', physical_background='UNKNOWN',
        physical_fish_count='UNKNOWN', identity='UNKNOWN', no_peak_selection=True,
        no_hole_filling=True, no_history_input_or_state_write=True,
        aligned_native_z_equality_assumed=False,
        independent_source_policy='ROW_MAJOR_CANONICAL_ONCE; NEIGHBOR_SOURCES_EXCLUDED; '
                                  'ANNULUS_EXCLUDES_ALL_OWN_AND_NEIGHBOR_SOURCES',
        quality_denominator='ORIGINAL_MASK_OR_GEOMETRIC_ANNULUS_AREA; DUPLICATES_DO_NOT_INFLATE_N',
        limitations=['An annulus can contain undetected fish or a nonplanar background.',
            'Camera Z residual is not physical fish identity or foreground pixel truth.',
            'Connected raster support may include repeated projections; independent N is deduplicated.',
            'Five IRLS updates and residual MAD do not certify that the affine surface is the true background.',
            'One-sided annulus leverage and prediction uncertainty remain explicit; no new identity veto.'])
    nan = np.full(depth.shape, np.nan, dtype='f8')
    maps = dict(plane_mm=nan.copy(), residual_mm=nan.copy(), annulus=annulus,
                background_selected=np.zeros(depth.shape, bool), mask_selected=np.zeros(depth.shape, bool),
                significant=np.zeros(depth.shape, bool), qualified_support=np.zeros(depth.shape, bool),
                component_labels=np.zeros(depth.shape, 'i4'), neighbor_excluded=neighbors)
    maps['background_selected'].ravel()[bg_positions] = True
    maps['mask_selected'].ravel()[mask_positions] = True

    def finish(reason):
        facts['reason'] = reason
        # Validate that public output can never carry pixels/nonfinite JSON numbers.
        json.dumps(facts, allow_nan=False)
        return facts, maps

    if not own.any():
        return finish('EMPTY_ORIGINAL_MASK')
    if bg_summary['n'] < PARAMETERS['background_minimum_n']:
        return finish('INSUFFICIENT_INDEPENDENT_BACKGROUND_SOURCES')
    if bg_summary['valid_fraction'] < PARAMETERS['minimum_coverage_fraction']:
        return finish('INSUFFICIENT_INDEPENDENT_BACKGROUND_COVERAGE')
    yy, xx = np.nonzero(own)
    cx, cy = (int(xx.min()) + int(xx.max())) / 2., (int(yy.min()) + int(yy.max())) / 2.
    design = _coordinates(bg_positions, depth.shape[1], cx, cy)
    condition = float(np.linalg.cond(design))
    if np.linalg.matrix_rank(design) < 3 or not math.isfinite(condition) or condition > PARAMETERS['background_max_condition']:
        facts['background']['design_condition'] = condition if math.isfinite(condition) else None
        return finish('DEGENERATE_BACKGROUND_GEOMETRY')
    values = depth.ravel()[bg_positions].astype('f8')
    beta = np.array([np.median(values), 0., 0.])
    for _ in range(PARAMETERS['irls_steps']):
        residual = values - design @ beta
        scale = _summary(residual, len(values))['scale_mm']
        weight = np.minimum(1., PARAMETERS['huber_c'] * scale / np.maximum(np.abs(residual), 1e-12))
        weighted = design * np.sqrt(weight[:, None])
        beta = np.linalg.lstsq(weighted, values * np.sqrt(weight), rcond=None)[0]
    residual = values - design @ beta
    residual_stats = _summary(residual, len(values))
    sigma = residual_stats['scale_mm']
    threshold = max(PARAMETERS['background_contrast_floor_mm'], PARAMETERS['background_sigma_factor'] * sigma)
    gy, gx = np.indices(depth.shape)
    plane = beta[0] + beta[1] * (gx - cx) / PARAMETERS['annulus_outer_px'] + beta[2] * (gy - cy) / PARAMETERS['annulus_outer_px']
    maps['plane_mm'] = plane
    maps['residual_mm'] = np.where(valid, depth - plane, np.nan)
    mask_design = _coordinates(mask_positions, depth.shape[1], cx, cy)
    covariance = np.linalg.pinv(weighted.T @ weighted)
    leverage = np.einsum('ij,jk,ik->i', mask_design, covariance, mask_design)
    uncertainty = sigma * np.sqrt(np.maximum(0., leverage))
    facts['plane'] = dict(origin_px=[cx, cy], coordinate_scale_px=PARAMETERS['annulus_outer_px'],
        beta_mm=list(map(float, beta)), residual_summary=residual_stats, residual_scale_mm=sigma,
        contrast_threshold_mm=threshold, condition=condition,
        weighted_condition=float(np.linalg.cond(weighted)), sample_n=len(values),
        design_rank=int(np.linalg.matrix_rank(design)),
        background_sample_geometry=_old._spatial(bg_positions, depth.shape[1]),
        mask_prediction_leverage=_range_summary(leverage),
        mask_prediction_uncertainty_mm=_range_summary(uncertainty),
        background_fit_residual_binding=array_binding(residual),
        physical_accuracy_mm='UNKNOWN')
    facts['background']['residual_scale_mm'] = sigma
    if sigma > PARAMETERS['max_scale_mm']:
        return finish('BACKGROUND_RESIDUAL_TOO_BROAD')
    if mask_summary['n'] < PARAMETERS['minimum_layer_n'] or mask_summary['valid_fraction'] < PARAMETERS['minimum_coverage_fraction']:
        return finish('INSUFFICIENT_INDEPENDENT_MASK_COVERAGE')
    significant = roi & valid & (np.abs(maps['residual_mm']) > threshold)
    maps['significant'] = significant
    facts['significant_independent_n'] = int(significant.ravel()[mask_positions].sum())
    boundary = own & ~cv2.erode(own.astype('u1'), np.ones((3, 3), 'u1')).astype(bool)
    number = 0
    qualified_positions = []
    for sign, sign_mask in [('NEARER', maps['residual_mm'] < 0), ('FARTHER', maps['residual_mm'] > 0)]:
        count, labels = cv2.connectedComponents((significant & sign_mask).astype('u1'), connectivity=8)
        for label in range(1, count):
            number += 1
            component = labels == label
            positions = mask_positions[component.ravel()[mask_positions]]
            residual_summary = _summary(maps['residual_mm'].ravel()[positions], int(component.sum()))
            population_fraction = len(positions) / max(1, len(mask_positions))
            qualified = bool(len(positions) >= PARAMETERS['minimum_layer_n'] and
                population_fraction >= PARAMETERS['minimum_layer_fraction'] and
                residual_summary['scale_mm'] <= PARAMETERS['max_scale_mm'])
            component_id = f'{fact_id}/support:{number}'
            facts['components'].append(dict(component_id=component_id, support_id=component_id,
                numeric_label=number, sign=sign, scale_mm=residual_summary['scale_mm'],
                median_residual_mm=residual_summary['median'],
                independent_n=len(positions), geometric_area=int(component.sum()),
                mask_source_fraction=population_fraction, qualified=qualified,
                residual_summary=residual_summary, depth_summary=_summary(depth.ravel()[positions], int(component.sum())),
                **_old._spatial(positions, depth.shape[1]),
                touches_original_mask_boundary=bool((component & boundary).any()),
                population_binding=_binding(positions, index, depth),
                residual_binding=array_binding(maps['residual_mm'].ravel()[positions]),
                geometric_component_binding=array_binding(component), foreground_identity='UNKNOWN'))
            maps['component_labels'][component] = number
            if qualified:
                maps['qualified_support'][component] = True
                qualified_positions.append(positions)
    selected = np.concatenate(qualified_positions) if qualified_positions else np.array([], dtype='i8')
    facts['qualified_component_n'] = len(qualified_positions)
    facts['qualified_independent_n'] = len(selected)
    facts['qualified_mask_source_fraction'] = len(selected) / max(1, len(mask_positions))
    facts['qualified_population_binding'] = _binding(selected, index, depth)
    if not len(selected):
        return finish('NO_QUALIFIED_BACKGROUND_RELATIVE_SUPPORT')
    facts['status'] = 'AVAILABLE'
    return finish('ALL_QUALIFIED_TWO_SIDED_CONNECTED_SUPPORTS_RETAINED; PHYSICAL_OWNERSHIP_UNKNOWN')
