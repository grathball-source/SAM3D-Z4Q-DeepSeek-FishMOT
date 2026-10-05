"""Observed contact-local depth supports; no layer is a fish or an identity."""
from __future__ import annotations

import copy
import json
import math

import cv2
import numpy as np

from common import ROOT, digest, module

_background = module('ds25_unchanged_ds22_measurement',
    ROOT / 'experiments/ds22_local_background_depth/measurement.py')
_layers = _background._old
PARAMETERS = dict(_background.PARAMETERS)
SCHEMA = 'DS25_CONTACT_LOCAL_ANONYMOUS_LAYERS_V1'
array_binding = _background.array_binding
_dilate = _background._dilate


def contact_seed(masks, a, b):
    """The original 3px mask contact geometry, without an ownership claim."""
    assert a != b and a in masks and b in masks
    first, second = np.asarray(masks[a]), np.asarray(masks[b])
    assert first.dtype == second.dtype == np.dtype(bool)
    assert first.ndim == 2 and first.shape == second.shape
    radius = PARAMETERS['neighbor_margin_px']
    return (_dilate(first, radius) & second) | (_dilate(second, radius) & first)


def _groups(depth, index, positions, fact_id, unit):
    # The frozen DS17 producer retains every >30mm sorted-gap group.
    return _layers._layer_facts(depth, index, positions, fact_id,
        dict(quality_usable=False), unit)


def measure_region(depth, source_index, native_depth, masks, roi, segment, frame,
                   global_frame, time, *, source_binding, expected_source_binding=None, excluded_native_sources=()):
    """Return public bound facts and private full-raster spatial support maps.

    Qualification is relative to the original geometric contact ROI, never the
    full fish or a selected layer. Original masks are used only as observed
    geometry. Missing depth and background-compatible groups remain explicit.
    """
    depth, index, sensor = map(np.asarray, (depth, source_index, native_depth))
    roi = np.asarray(roi)
    assert roi.dtype == np.dtype(bool) and roi.ndim == 2 and roi.shape == depth.shape
    regions = {int(n): np.asarray(mask) for n, mask in masks.items()}
    assert len(regions) == len(masks)
    assert all(mask.dtype == np.dtype(bool) for mask in regions.values())
    valid = _background.validate_source(depth, index, sensor, regions, segment, frame,
        global_frame, time, source_binding, expected_source_binding)
    union = np.zeros(depth.shape, bool)
    for mask in regions.values():
        union |= mask
    assert not np.any(roi & ~union), 'Contact ROI includes pixels outside original observed masks'
    excluded = np.asarray(excluded_native_sources, dtype=index.dtype)
    joint_shared = roi & valid & np.isin(index, excluded)
    area = int(roi.sum())
    roi_binding = array_binding(roi)
    fact_id = f'{segment}/F{frame}/contact_roi:{digest(roi_binding)}/raw'
    if excluded.size: fact_id += '/independent_pair:' + digest(array_binding(excluded))
    positions, exclusions = _background._selected(roi, valid, index, excluded)
    inclusive_positions = np.flatnonzero(roi & valid & ~joint_shared)
    own_sources = np.unique(index[union & valid])
    annulus = (_dilate(roi, PARAMETERS['annulus_outer_px']) &
        ~_dilate(roi, PARAMETERS['annulus_inner_px']) &
        ~_dilate(union, PARAMETERS['neighbor_margin_px']))
    bg_positions, bg_exclusions = _background._selected(annulus, valid, index, own_sources)
    summary = _background._summary(depth.ravel()[positions], area)
    inclusive_summary = _background._summary(depth.ravel()[inclusive_positions], area)
    bg_summary = _background._summary(depth.ravel()[bg_positions], int(annulus.sum()))
    independent_groups = _groups(depth, index, positions, fact_id + '/independent',
        'UNIQUE_NATIVE_SOURCE_POINTS')
    inclusive_groups = _groups(depth, index, inclusive_positions, fact_id + '/inclusive',
        'ORIGINAL_ALIGNED_VALID_DEPTH_PIXELS')
    nan = np.full(depth.shape, np.nan, dtype='f8')
    maps = dict(roi=roi.copy(), annulus=annulus, plane_mm=nan.copy(), residual_mm=nan.copy(),
        background_selected=np.zeros(depth.shape, bool), mask_selected=np.zeros(depth.shape, bool),
        support_masks={}, selected_positions={}, missing=roi & ~valid)
    maps['background_selected'].ravel()[bg_positions] = True
    maps['mask_selected'].ravel()[positions] = True
    facts = dict(schema=SCHEMA, fact_id=fact_id, segment=segment, frame=int(frame),
        global_frame=int(global_frame), time=float(time), status='UNKNOWN', reason=None,
        parameters=dict(PARAMETERS), source_binding=copy.deepcopy(source_binding),
        actual_depth_binding=array_binding(depth), actual_source_index_binding=array_binding(index),
        native_depth_binding=array_binding(sensor), roi_binding=roi_binding,
        original_mask_bindings={str(n): array_binding(mask) for n, mask in sorted(regions.items())},
        original_masks_union_binding=array_binding(union), original_roi_area=area,
        original_roi_missing_n=int(maps['missing'].sum()),
        joint_shared_source_count=int(excluded.size), joint_shared_aligned_pixel_n=int(joint_shared.sum()),
        joint_shared_population_binding=_background._binding(np.flatnonzero(joint_shared), index, depth),
        excluded_native_sources_binding=array_binding(excluded),
        excluded_native_sources_policy='ACTUALLY_SHARED_POINTS_COMMON_NULL; ORIGINAL_ROI_DENOMINATOR_UNCHANGED', summary=summary,
        inclusive_summary=inclusive_summary, roi_source_exclusions=exclusions,
        roi_population_binding=_background._binding(positions, index, depth),
        inclusive_roi_population_binding=_background._binding(inclusive_positions, index, depth),
        annulus_binding=array_binding(annulus),
        background=dict(summary=bg_summary, exclusions=bg_exclusions,
            population_binding=_background._binding(bg_positions, index, depth)),
        plane=None, layers=[], independent_depth_groups=independent_groups,
        inclusive_depth_groups=inclusive_groups, qualified_support_ids=[],
        physical_fish_count='UNKNOWN', identity='UNKNOWN', foreground_identity='UNKNOWN',
        physical_background='UNKNOWN', aligned_native_z_equality_assumed=False,
        no_GT_RGB_future_or_restored_input=True, no_sensor_completion=True,
        no_peak_selection=True, no_hole_filling=True, no_history_input_or_state_write=True,
        source_policy='CONTACT_ROI_DEDUPLICATED_ONCE; JOINT_SHARED_SOURCES_EXCLUDED_FROM_STATISTICS; ORIGINAL_MEASURED_FACT_RETAINED',
        quality_denominator='ORIGINAL_GEOMETRIC_CONTACT_ROI_AREA_INCLUDING_MISSING_AND_DUPLICATE_PIXELS',
        spatial_policy='FULL_INCLUSIVE_ALIGNED_RASTER; UNIQUE_NATIVE_SOURCE_POINTS_FOR_STATISTICS',
        scalar_replacement='NONE_IN_ORIGINAL_Z4Q_BANK',
        limitations=['A depth gap or a spatial support does not identify a fish.',
            'A bent fish or background can produce multiple layers; all supports remain anonymous.',
            'A hidden fish without measured depth cannot be reconstructed.',
            'An annulus can contain undetected fish or a nonplanar background.',
            'Frame-local native source indices do not provide temporal surface correspondence.'])

    # Group on all measured pixels first: canonical source selection must not
    # create artificial holes in the spatial raster.
    values = depth.ravel()[inclusive_positions]
    for group_number, group in enumerate(inclusive_groups, 1):
        group_positions = inclusive_positions[(values >= group['minimum_mm']) &
            (values <= group['maximum_mm'])]
        group_mask = np.zeros(depth.shape, 'u1')
        group_mask.ravel()[group_positions] = 1
        count, labels = cv2.connectedComponents(group_mask, connectivity=8)
        for component_number in range(1, count):
            component = labels == component_number
            inclusive = group_positions[component.ravel()[group_positions]]
            selected = positions[component.ravel()[positions]]
            support_id = f'{fact_id}/gap:{group_number}/support:{component_number}'
            independent_stats = _background._summary(depth.ravel()[selected], area)
            inclusive_stats = _background._summary(depth.ravel()[inclusive], area)
            substantial = bool(len(selected) >= PARAMETERS['minimum_layer_n'] and
                len(selected) / max(1, area) >= PARAMETERS['minimum_layer_fraction'])
            inclusive_substantial = bool(len(inclusive) >= PARAMETERS['minimum_layer_n'] and
                len(inclusive) / max(1, area) >= PARAMETERS['minimum_layer_fraction'])
            layer = dict(support_id=support_id, depth_gap_group=group_number,
                component_number=component_number, kind='MEASURED_DEPTH_SUPPORT', qualified=False,
                inclusive_qualified=False, substantial=substantial,
                inclusive_substantial=inclusive_substantial, independent_n=len(selected),
                inclusive_n=len(inclusive), geometric_area=int(component.sum()),
                support_fraction_of_original_roi=len(selected) / max(1, area),
                inclusive_fraction_of_original_roi=len(inclusive) / max(1, area),
                independent_summary=independent_stats, inclusive_summary=inclusive_stats,
                z_mm=independent_stats['median'], sigma_mm=None, inclusive_sigma_mm=None,
                background_compatibility='UNKNOWN', inclusive_background_compatibility='UNKNOWN',
                median_residual_mm=None, inclusive_median_residual_mm=None,
                **_layers._spatial(inclusive, depth.shape[1]),
                independent_spatial=_layers._spatial(selected, depth.shape[1]),
                population_binding=_background._binding(selected, index, depth),
                inclusive_population_binding=_background._binding(inclusive, index, depth),
                geometric_component_binding=array_binding(component),
                physical_surface_identity='UNKNOWN', fish_count='UNKNOWN')
            facts['layers'].append(layer)
            maps['support_masks'][support_id] = component
            maps['selected_positions'][support_id] = selected
    missing_positions = np.flatnonzero(maps['missing'])
    if len(missing_positions):
        missing_id = fact_id + '/missing_depth'
        facts['layers'].append(dict(support_id=missing_id, depth_gap_group=None,
            kind='MISSING_DEPTH', qualified=False, inclusive_qualified=False, substantial=False,
            inclusive_substantial=False, independent_n=0, inclusive_n=len(missing_positions),
            geometric_area=len(missing_positions), support_fraction_of_original_roi=0.,
            inclusive_fraction_of_original_roi=len(missing_positions) / max(1, area),
            z_mm=None, sigma_mm=None, background_compatibility='UNKNOWN_NO_MEASURED_DEPTH',
            **_layers._spatial(missing_positions, depth.shape[1]),
            population_binding=_background._binding(np.array([], dtype='i8'), index, depth),
            inclusive_population_binding=_background._binding(missing_positions, index, depth),
            geometric_component_binding=array_binding(maps['missing']),
            physical_surface_identity='UNKNOWN', fish_count='UNKNOWN'))
        maps['support_masks'][missing_id] = maps['missing']
        maps['selected_positions'][missing_id] = np.array([], dtype='i8')

    def finish(reason):
        facts['reason'] = reason
        facts['measurement_sha256'] = digest(facts)
        json.dumps(facts, allow_nan=False)
        return facts, maps

    if not area:
        return finish('EMPTY_ORIGINAL_CONTACT_ROI')
    if bg_summary['n'] < PARAMETERS['background_minimum_n']:
        return finish('INSUFFICIENT_INDEPENDENT_BACKGROUND_SOURCES')
    if bg_summary['valid_fraction'] < PARAMETERS['minimum_coverage_fraction']:
        return finish('INSUFFICIENT_INDEPENDENT_BACKGROUND_COVERAGE')
    yy, xx = np.nonzero(roi)
    cx, cy = (int(xx.min()) + int(xx.max())) / 2., (int(yy.min()) + int(yy.max())) / 2.
    design = _background._coordinates(bg_positions, depth.shape[1], cx, cy)
    condition = float(np.linalg.cond(design))
    if np.linalg.matrix_rank(design) < 3 or not math.isfinite(condition) or condition > PARAMETERS['background_max_condition']:
        facts['background']['design_condition'] = condition if math.isfinite(condition) else None
        return finish('DEGENERATE_BACKGROUND_GEOMETRY')
    bg_values = depth.ravel()[bg_positions].astype('f8')
    beta = np.array([np.median(bg_values), 0., 0.])
    # The same five fixed Huber IRLS updates and leverage equation as DS22.
    for _ in range(PARAMETERS['irls_steps']):
        residual = bg_values - design @ beta
        scale = _background._summary(residual, len(bg_values))['scale_mm']
        weight = np.minimum(1., PARAMETERS['huber_c'] * scale / np.maximum(np.abs(residual), 1e-12))
        weighted = design * np.sqrt(weight[:, None])
        beta = np.linalg.lstsq(weighted, bg_values * np.sqrt(weight), rcond=None)[0]
    bg_residual = bg_values - design @ beta
    residual_stats = _background._summary(bg_residual, len(bg_values))
    sigma = residual_stats['scale_mm']
    threshold = max(PARAMETERS['background_contrast_floor_mm'], PARAMETERS['background_sigma_factor'] * sigma)
    gy, gx = np.indices(depth.shape)
    plane = beta[0] + beta[1] * (gx - cx) / PARAMETERS['annulus_outer_px'] + beta[2] * (gy - cy) / PARAMETERS['annulus_outer_px']
    maps['plane_mm'] = plane
    maps['residual_mm'] = np.where(valid, depth - plane, np.nan)
    covariance = np.linalg.pinv(weighted.T @ weighted)

    def uncertainty(points):
        coordinates = _background._coordinates(points, depth.shape[1], cx, cy)
        leverage = np.einsum('ij,jk,ik->i', coordinates, covariance, coordinates)
        return leverage, sigma * np.sqrt(np.maximum(0., leverage))

    leverage, prediction_uncertainty = uncertainty(positions)
    facts['plane'] = dict(origin_px=[cx, cy], coordinate_scale_px=PARAMETERS['annulus_outer_px'],
        beta_mm=list(map(float, beta)), residual_summary=residual_stats, residual_scale_mm=sigma,
        contrast_threshold_mm=threshold, condition=condition,
        weighted_condition=float(np.linalg.cond(weighted)), sample_n=len(bg_values),
        design_rank=int(np.linalg.matrix_rank(design)),
        background_sample_geometry=_layers._spatial(bg_positions, depth.shape[1]),
        roi_prediction_leverage=_background._range_summary(leverage),
        roi_prediction_uncertainty_mm=_background._range_summary(prediction_uncertainty),
        background_fit_residual_binding=array_binding(bg_residual), physical_accuracy_mm='UNKNOWN')
    measured = [layer for layer in facts['layers'] if layer['kind'] == 'MEASURED_DEPTH_SUPPORT']
    for layer in measured:
        selected = maps['selected_positions'][layer['support_id']]
        inclusive = np.flatnonzero(maps['support_masks'][layer['support_id']])
        for prefix, points, stats, substantial in (
            ('', selected, layer['independent_summary'], layer['substantial']),
            ('inclusive_', inclusive, layer['inclusive_summary'], layer['inclusive_substantial'])):
            _, prediction = uncertainty(points)
            prediction_summary = _background._range_summary(prediction)
            residual_summary = _background._summary(maps['residual_mm'].ravel()[points], area)
            contrast = residual_summary['median']
            compatibility = ('UNKNOWN' if contrast is None else
                'BACKGROUND_COMPATIBLE' if abs(contrast) <= threshold else 'DIFFERENT_FROM_LOCAL_ANNULUS_PROXY')
            combined = None if stats['scale_mm'] is None else math.sqrt(
                stats['scale_mm'] ** 2 + sigma ** 2 + prediction_summary['q90'] ** 2)
            layer[prefix + 'sigma_mm'] = combined
            layer[prefix + 'median_residual_mm'] = contrast
            layer[prefix + 'background_compatibility'] = compatibility
            layer[prefix + 'prediction_uncertainty_mm'] = prediction_summary
            layer[prefix + 'residual_summary'] = residual_summary
            layer[prefix + 'qualified'] = bool(substantial and sigma <= PARAMETERS['max_scale_mm'] and
                combined is not None and combined <= PARAMETERS['max_scale_mm'] and
                compatibility == 'DIFFERENT_FROM_LOCAL_ANNULUS_PROXY')
    if sigma > PARAMETERS['max_scale_mm']:
        return finish('BACKGROUND_RESIDUAL_TOO_BROAD')
    if summary['n'] < PARAMETERS['minimum_layer_n'] or summary['valid_fraction'] < PARAMETERS['minimum_coverage_fraction']:
        return finish('INSUFFICIENT_INDEPENDENT_ROI_COVERAGE')
    # Canonical deduplication can expose an otherwise bridged depth gap. Neither
    # population is preferred when their partitions or qualifications disagree.
    partition_agrees = len(independent_groups) == len(inclusive_groups)
    if partition_agrees:
        partition_agrees = all(a['minimum_mm'] >= b['minimum_mm'] and a['maximum_mm'] <= b['maximum_mm']
            for a, b in zip(independent_groups, inclusive_groups))
    flags_agree = all(layer['qualified'] == layer['inclusive_qualified'] and
        layer['substantial'] == layer['inclusive_substantial'] and
        layer['background_compatibility'] == layer['inclusive_background_compatibility'] for layer in measured)
    facts['inclusive_independent_partition_agreement'] = bool(partition_agrees)
    facts['inclusive_independent_support_agreement'] = bool(flags_agree)
    qualified = [layer for layer in measured if layer['qualified']]
    facts['qualified_support_ids'] = [layer['support_id'] for layer in qualified]
    unresolved = [layer['support_id'] for layer in measured
        if (layer['substantial'] or layer['inclusive_substantial']) and not layer['qualified'] and
        (layer['background_compatibility'] != 'BACKGROUND_COMPATIBLE' or
            layer['sigma_mm'] is None or layer['sigma_mm'] > PARAMETERS['max_scale_mm'] or
            layer['inclusive_sigma_mm'] is None or layer['inclusive_sigma_mm'] > PARAMETERS['max_scale_mm'])]
    facts['substantial_unresolved_support_ids'] = unresolved
    if not partition_agrees or not flags_agree:
        return finish('INCLUSIVE_INDEPENDENT_DEPTH_OR_SUPPORT_DISAGREEMENT')
    if unresolved:
        return finish('SUBSTANTIAL_NOISY_OR_UNRESOLVED_SUPPORT')
    if len(qualified) != 2:
        return finish('EXACTLY_TWO_QUALIFIED_LOCAL_SUPPORTS_REQUIRED')
    if qualified[0]['depth_gap_group'] == qualified[1]['depth_gap_group']:
        return finish('TWO_SPATIAL_PIECES_ARE_NOT_TWO_DEPTH_GAP_LAYERS')
    facts['status'] = 'AVAILABLE_TWO_LAYERS'
    return finish('TWO_NOISE_QUALIFIED_ANONYMOUS_LOCAL_DEPTH_LAYERS; PHYSICAL_OWNERSHIP_UNKNOWN')
