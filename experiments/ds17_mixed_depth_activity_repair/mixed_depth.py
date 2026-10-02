"""Preserve all measured depth layers; never identify a fish by choosing a peak."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    'ds17_exact_core', ROOT / 'experiments/ds12_contact_depth_admission/contact_measurement.py')
_core = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_core)
adaptive_core, array_binding = _core.adaptive_core, _core.array_binding
_old = json.loads((ROOT / 'experiments/ds3_depth_foreground_filter/CONFIG.json').read_text(encoding='utf-8'))

PARAMETERS = dict(layer_gap_mm=2. * _old['scale_floor_mm'], scale_floor_mm=_old['scale_floor_mm'],
    max_scale_mm=_old['max_scale_mm'], minimum_layer_n=_old['foreground_min_n'],
    minimum_layer_fraction=_old['foreground_min_support_fraction'],
    minimum_coverage_fraction=_old['background_min_fraction'],
    annulus_inner_px=_old['annulus_inner_px'], annulus_outer_px=_old['annulus_outer_px'],
    neighbor_margin_px=_old['neighbor_margin_px'], background_minimum_n=_old['background_min_n'],
    background_contrast_floor_mm=_old['contrast_floor_mm'], background_sigma_factor=_old['contrast_sigma'])
assert (PARAMETERS['layer_gap_mm'], PARAMETERS['scale_floor_mm'], PARAMETERS['minimum_layer_n'],
        PARAMETERS['minimum_layer_fraction'], PARAMETERS['max_scale_mm']) == (30., 15., 16, .2, 60.)


def _stats(values, area):
    values = np.asarray(values, dtype='f8')
    result = dict(n=int(values.size), area=int(area), valid_fraction=int(values.size) / max(1, int(area)),
                  median=None, mad=None, q10=None, q25=None, q75=None, q90=None, scale_mm=None,
                  minimum_mm=None, maximum_mm=None)
    if values.size:
        median = float(np.median(values))
        mad = float(np.median(np.abs(values - median)))
        result.update(median=median, mad=mad, scale_mm=max(PARAMETERS['scale_floor_mm'], 1.4826 * mad),
            minimum_mm=float(values.min()), maximum_mm=float(values.max()))
        result.update(zip(('q10', 'q25', 'q75', 'q90'), map(float, np.quantile(values, [.1, .25, .75, .9]))))
    return result


def _spatial(positions, width):
    y, x = np.divmod(positions, width)
    return dict(bbox_xyxy=[int(x.min()), int(y.min()), int(x.max()) + 1, int(y.max()) + 1],
                centroid_xy=[float(x.mean()), float(y.mean())]) if len(positions) else dict(bbox_xyxy=None, centroid_xy=None)


def _canonical_selection(roi, valid, index, excluded_sources):
    selected = roi & valid
    shared = selected & np.isin(index, excluded_sources) if len(excluded_sources) else np.zeros(roi.shape, bool)
    selected &= ~shared
    positions = np.flatnonzero(selected)
    before = len(positions)
    if before:
        _, first = np.unique(index.ravel()[positions], return_index=True)
        positions = positions[np.sort(first)]
    return positions, dict(valid_before_source_exclusions=before + int(shared.sum()),
        shared_source_pixels_excluded=int(shared.sum()), within_mask_duplicate_pixels_excluded=before - len(positions),
        selected_independent_native_source_n=int(len(positions)))


def _layer_facts(depth, index, positions, fact_id, background, sample_unit):
    values = depth.ravel()[positions].astype('f8')
    layers = []
    if not len(values):
        return layers
    ordered = np.argsort(values, kind='stable')
    cuts = np.flatnonzero(np.diff(values[ordered]) > PARAMETERS['layer_gap_mm']) + 1
    for number, members in enumerate(np.split(ordered, cuts), 1):
        points = positions[members]
        stats = _stats(values[members], len(points))
        fraction = len(points) / len(positions)
        substantial = bool(len(points) >= PARAMETERS['minimum_layer_n'] and
            fraction >= PARAMETERS['minimum_layer_fraction'])
        qualified = substantial and stats['scale_mm'] <= PARAMETERS['max_scale_mm']
        compatibility, contrast = 'UNKNOWN', None
        if background['quality_usable']:
            contrast = stats['median'] - background['summary']['median']
            scale = math.hypot(stats['scale_mm'], background['summary']['scale_mm'])
            threshold = max(PARAMETERS['background_contrast_floor_mm'], PARAMETERS['background_sigma_factor'] * scale)
            compatibility = ('BACKGROUND_COMPATIBLE' if abs(contrast) <= threshold else
                             'DIFFERENT_FROM_LOCAL_ANNULUS_PROXY')
        layers.append(dict(layer_id=f'{fact_id}/layer:{number}', **stats,
            measured_support_fraction=fraction, substantial=substantial, qualified=bool(qualified),
            sample_unit=sample_unit, **_spatial(points, depth.shape[1]),
            selected_pixel_binding=array_binding(points),
            selected_source_index_binding=array_binding(index.ravel()[points]),
            selected_depth_binding=array_binding(depth.ravel()[points]),
            background_compatibility=compatibility, layer_minus_annulus_mm=contrast,
            physical_surface_identity='UNKNOWN', fish_count='UNKNOWN'))
    return layers


def _mixture_pairs(layers):
    significant = [p for p in layers if p['qualified']]
    result = []
    for i, a in enumerate(significant):
        for b in significant[i + 1:]:
            gap = abs(a['median'] - b['median'])
            threshold = max(PARAMETERS['layer_gap_mm'], a['scale_mm'] + b['scale_mm'])
            if gap > threshold:
                result.append(dict(first_layer_id=a['layer_id'], second_layer_id=b['layer_id'],
                    median_separation_mm=gap, required_separation_mm=threshold))
    return result


def _representation(depth, index, roi, valid, shared_sources, fact_id, background):
    positions, exclusions = _canonical_selection(roi, valid, index, shared_sources)
    area = int(roi.sum())
    summary = _stats(depth.ravel()[positions], area)
    scalar_valid = np.isfinite(depth) & (depth > 0)
    inclusive_positions = np.flatnonzero(roi & scalar_valid)
    inclusive_summary = _stats(depth.ravel()[inclusive_positions], area)
    layers = _layer_facts(depth, index, positions, fact_id + '/independent', background, 'UNIQUE_NATIVE_SOURCE_POINTS')
    inclusive_layers = _layer_facts(depth, index, inclusive_positions, fact_id + '/inclusive', background, 'ORIGINAL_ALIGNED_VALID_DEPTH_PIXELS')
    def quality(s):
        return bool(s['n'] >= PARAMETERS['minimum_layer_n'] and
            s['valid_fraction'] >= PARAMETERS['minimum_coverage_fraction'] and
            s['scale_mm'] is not None and s['scale_mm'] <= PARAMETERS['max_scale_mm'])
    usable = quality(summary)
    substantial = sum(p['substantial'] for p in layers)
    significant = sum(p['qualified'] for p in layers)
    inclusive_substantial = sum(p['substantial'] for p in inclusive_layers)
    inclusive_significant = sum(p['qualified'] for p in inclusive_layers)
    separated = _mixture_pairs(layers)
    inclusive_separated = _mixture_pairs(inclusive_layers)
    mixture = bool(separated or inclusive_separated)
    unverified = int((roi & scalar_valid & ~valid).sum())
    ownership = not exclusions['shared_source_pixels_excluded'] and not unverified
    if mixture:
        status, reason = 'POTENTIAL_MIXTURE', 'SUBSTANTIAL_MEASURED_LAYERS_HAVE_NOISE_SEPARATED_MEDIANS'
    elif not ownership:
        status, reason = 'UNKNOWN', 'ORIGINAL_SCALAR_INCLUDES_SHARED_OR_UNVERIFIED_NATIVE_SOURCES'
    elif not usable:
        status, reason = 'UNKNOWN', 'INSUFFICIENT_INDEPENDENT_COVERAGE_OR_BROAD_SCALAR_SUPPORT'
    elif substantial != 1 or significant != 1 or inclusive_substantial != 1 or inclusive_significant != 1:
        status, reason = 'UNKNOWN', 'NO_SINGLE_QUALIFIED_SUBSTANTIAL_LAYER_IN_BOTH_POPULATIONS'
    else:
        status, reason = 'SINGLE_COMPATIBLE_LAYER', 'NO_SUBSTANTIAL_SEPARATED_SECOND_LAYER_DETECTED'
    return dict(fact_id=fact_id, status=status, reason=reason,
        eligible_single=status == 'SINGLE_COMPATIBLE_LAYER', mixture_flag=mixture,
        independent_mixture_flag=bool(separated), inclusive_mixture_flag=bool(inclusive_separated),
        separated_layer_pairs=separated, inclusive_separated_layer_pairs=inclusive_separated,
        quality_usable=usable, original_pixel_quality_usable=quality(inclusive_summary),
        source_ownership_exclusive=bool(ownership), source_population_unverified_n=unverified,
        summary=summary, layers=layers, layer_count=len(layers),
        substantial_layer_count=substantial, qualified_layer_count=significant,
        inclusive_summary=inclusive_summary, inclusive_layers=inclusive_layers,
        inclusive_layer_count=len(inclusive_layers),
        inclusive_substantial_layer_count=inclusive_substantial,
        inclusive_qualified_layer_count=inclusive_significant,
        scalar_population_difference=dict(original_aligned_valid_pixel_n=len(inclusive_positions),
            independent_native_source_n=len(positions), within_mask_duplicate_pixel_n=exclusions['within_mask_duplicate_pixels_excluded'],
            shared_source_pixel_n=exclusions['shared_source_pixels_excluded'], unverified_native_source_pixel_n=unverified,
            original_pixel_median_mm=inclusive_summary['median'], independent_median_mm=summary['median'],
            original_pixel_mad_mm=inclusive_summary['mad'], independent_mad_mm=summary['mad']),
        minor_layer_n=sum(layer['n'] for layer in layers if not layer['substantial']),
        **exclusions, selected_pixel_binding=array_binding(positions),
        selected_source_index_binding=array_binding(index.ravel()[positions]),
        source_quality_denominator='ORIGINAL_GEOMETRIC_ROI_AREA_INCLUDING_MISSING_SHARED_DUPLICATE_PIXELS',
        layer_fraction_denominator='ALL_POINTS_IN_RESPECTIVE_INCLUSIVE_PIXEL_OR_INDEPENDENT_SOURCE_POPULATION',
        scalar_replacement='NONE; EXISTING_SCALAR_MEDIAN_AND_MAD_MUST_NOT_BE_REPLACED_BY_SELECTED_LAYER',
        physical_single_fish='UNKNOWN', spatial_connectivity='NOT_A_LAYER_CRITERION; NO_HOLE_FILLING',
        limitations=['Multiple layers can be fish/background or one bent fish, not necessarily two fish.',
            'Continuous or bridged multimodality with every sorted adjacent gap <=30 mm is not separated.',
            'Layers with fewer than16 sources or pixels or less than20 percent support remain recorded but are not substantial.',
            'A hidden fish with no observed depth points cannot be reconstructed.',
            'Within-mask repeated source weights can change original scalar statistics; both populations are reported.'])


def _background(depth, index, region, other, valid, own_sources):
    def dilation(mask, radius):
        return cv2.dilate(mask.astype('u1'), np.ones((2 * radius + 1,) * 2, 'u1')).astype(bool)
    ring = (dilation(region, PARAMETERS['annulus_outer_px']) &
        ~dilation(region, PARAMETERS['annulus_inner_px']) &
        ~dilation(other, PARAMETERS['neighbor_margin_px']))
    positions, exclusions = _canonical_selection(ring, valid, index, own_sources)
    summary = _stats(depth.ravel()[positions], int(ring.sum()))
    quality = bool(summary['n'] >= PARAMETERS['background_minimum_n'] and
        summary['valid_fraction'] >= PARAMETERS['minimum_coverage_fraction'] and
        summary['scale_mm'] is not None and summary['scale_mm'] <= PARAMETERS['max_scale_mm'])
    return dict(summary=summary, quality_usable=quality, **exclusions,
        selected_pixel_binding=array_binding(positions),
        selected_source_index_binding=array_binding(index.ravel()[positions]),
        use='DIAGNOSTIC_COMPATIBILITY_ONLY; NO_BACKGROUND_POINTS_REMOVED_FROM_MASK',
        physical_background='UNKNOWN; ANNULUS_MAY_CONTAIN_UNDETECTED_FISH_OR_NONPLANAR_BACKGROUND')


def measure_mixed(depth, source_index, masks, segment, frame, global_frame, *, source_binding, native_depth=None):
    """Current raw arrays and original masks only; shared frame provenance once."""
    depth, index = np.asarray(depth), np.asarray(source_index)
    assert depth.ndim == 2 and depth.size and depth.shape == index.shape
    assert np.issubdtype(index.dtype, np.signedinteger)
    assert int(frame) == frame and frame >= 1 and int(global_frame) == global_frame and global_frame >= 0
    assert source_binding['global_frame'] == global_frame and math.isfinite(source_binding['time'])
    assert source_binding.get('frame', frame) == frame
    assert not any(source_binding.get(k, False) for k in ('GT_read', 'RGB_read', 'restored_read'))
    masks = {int(n): np.asarray(mask, dtype=bool) for n, mask in masks.items()}
    assert all(mask.shape == depth.shape for mask in masks.values())
    occupancy = sum((mask.astype('u2') for mask in masks.values()), np.zeros(depth.shape, 'u2'))
    valid = np.isfinite(depth) & (depth > 0) & (index >= 0)
    if native_depth is not None:
        native = np.asarray(native_depth).ravel()
        assert np.all(index[valid] < len(native))
        valid[valid] &= np.isfinite(native[index[valid]]) & (native[index[valid]] > 0)
    sources = {n: np.unique(index[mask & valid]) for n, mask in masks.items()}
    all_sources = np.concatenate(list(sources.values())) if masks else np.array([], dtype=index.dtype)
    ids, counts = np.unique(all_sources, return_counts=True)
    shared_sources = ids[counts > 1]
    shared = dict(segment=segment, frame=int(frame), global_frame=int(global_frame), time=source_binding['time'],
        source_binding=copy.deepcopy(source_binding), actual_depth_binding=array_binding(depth),
        actual_source_index_binding=array_binding(index), native_depth_binding=array_binding(np.asarray(native_depth)) if native_depth is not None else None)
    shared_sha = _digest(shared)
    objects = {}
    for n in sorted(masks):
        region = masks[n]
        core, geometry = adaptive_core(region, occupancy)
        background = _background(depth, index, region, occupancy > region.astype('u2'), valid, sources[n])
        base = f'{segment}/F{frame}/n:{n}/mixed'
        whole = _representation(depth, index, region, valid, shared_sources, base + '/whole/raw', background)
        inner = _representation(depth, index, core, valid, shared_sources, base + '/core/raw', background)
        objects[n] = dict(native=n, fact_id=base + '/raw', segment=segment, frame=int(frame), global_frame=int(global_frame),
            time=source_binding['time'], frame_binding_sha256=shared_sha, source='RAW_SENSOR_DEDUPLICATED_LAYER_REPRESENTATION',
            mask_binding=array_binding(region), core_binding=array_binding(core), geometry=geometry,
            whole=whole, core=inner, annulus=background, physical_mask_fish_count='UNKNOWN',
            individual_depth_evidence='UNKNOWN_IF_MIXED_OR_UNQUALIFIED; ORIGINAL_SCALAR_IF_SINGLE_COMPATIBLE',
            no_nearest_or_largest_layer_selected=True, no_history_or_identity_write=True)
        objects[n]['certificate_sha256'] = _digest(objects[n])
        assert validate_certificate(objects[n])
    return dict(shared, frame_binding_sha256=shared_sha, objects=objects, parameters=dict(PARAMETERS),
        source_policy='SHARED_NATIVE_SOURCES_ACROSS_MASKS_EXCLUDED; WITHIN_MASK_ROW_MAJOR_CANONICAL_ONCE',
        layer_policy='ALL_SORTED_DEPTH_GAP_COMPONENTS_RETAINED; NO_IDENTITY_DEPENDENT_SELECTION',
        no_GT_RGB_future_or_restored_input=True, no_sensor_completion=True, no_pixel_arrays_serialized=True)


def _digest(item):
    value = {k: v for k, v in item.items() if k != 'certificate_sha256'}
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
        ensure_ascii=False, allow_nan=False).encode('utf-8')).hexdigest()


def validate_certificate(certificate):
    """Metadata checks and immutable producer digest; not a physical fish oracle."""
    try:
        c = certificate
        assert c['certificate_sha256'] == _digest(c)
        assert c['frame'] >= 1 and c['global_frame'] >= 0 and math.isfinite(c['time'])
        assert len(c['frame_binding_sha256']) == 64
        assert c['no_nearest_or_largest_layer_selected'] and c['no_history_or_identity_write']
        assert c['physical_mask_fish_count'] == 'UNKNOWN'
        for part in ('whole', 'core'):
            r = c[part]
            for prefix in ('', 'inclusive_'):
                summary, layers = r[prefix + 'summary'], r[prefix + 'layers']
                assert summary['n'] == sum(p['n'] for p in layers)
                assert summary['valid_fraction'] == summary['n'] / max(1, summary['area'])
                assert r[prefix + 'layer_count'] == len(layers)
                substantial, qualified = 0, 0
                for layer in layers:
                    assert layer['measured_support_fraction'] == layer['n'] / summary['n']
                    substantial_flag = layer['n'] >= PARAMETERS['minimum_layer_n'] and layer['measured_support_fraction'] >= PARAMETERS['minimum_layer_fraction']
                    assert layer['substantial'] == substantial_flag
                    assert layer['scale_mm'] == max(PARAMETERS['scale_floor_mm'], 1.4826 * layer['mad'])
                    assert layer['qualified'] == bool(substantial_flag and layer['scale_mm'] <= PARAMETERS['max_scale_mm'])
                    assert layer['minimum_mm'] <= layer['median'] <= layer['maximum_mm']
                    for field in ('selected_pixel_binding', 'selected_source_index_binding', 'selected_depth_binding'):
                        assert layer[field]['shape'] == [layer['n']] and len(layer[field]['sha256']) == 64
                    assert layer['physical_surface_identity'] == layer['fish_count'] == 'UNKNOWN'
                    substantial += bool(substantial_flag)
                    qualified += bool(layer['qualified'])
                assert all(b['minimum_mm'] - a['maximum_mm'] > PARAMETERS['layer_gap_mm'] for a, b in zip(layers, layers[1:]))
                assert r[prefix + 'substantial_layer_count'] == substantial and r[prefix + 'qualified_layer_count'] == qualified
            summary = r['summary']
            quality = bool(summary['n'] >= PARAMETERS['minimum_layer_n'] and
                summary['valid_fraction'] >= PARAMETERS['minimum_coverage_fraction'] and
                summary['scale_mm'] is not None and summary['scale_mm'] <= PARAMETERS['max_scale_mm'])
            assert r['quality_usable'] == quality
            assert r['selected_independent_native_source_n'] == summary['n']
            assert r['selected_pixel_binding']['shape'] == r['selected_source_index_binding']['shape'] == [summary['n']]
            separated, inclusive_separated = _mixture_pairs(r['layers']), _mixture_pairs(r['inclusive_layers'])
            assert r['separated_layer_pairs'] == separated and r['inclusive_separated_layer_pairs'] == inclusive_separated
            assert r['independent_mixture_flag'] == bool(separated)
            assert r['inclusive_mixture_flag'] == bool(inclusive_separated)
            assert r['mixture_flag'] == bool(separated or inclusive_separated)
            ownership = not r['shared_source_pixels_excluded'] and not r['source_population_unverified_n']
            assert r['source_ownership_exclusive'] == bool(ownership)
            single = (quality and ownership and r['substantial_layer_count'] == r['qualified_layer_count'] ==
                r['inclusive_substantial_layer_count'] == r['inclusive_qualified_layer_count'] == 1)
            expected = 'POTENTIAL_MIXTURE' if r['mixture_flag'] else 'SINGLE_COMPATIBLE_LAYER' if single else 'UNKNOWN'
            assert r['status'] == expected and r['eligible_single'] == (expected == 'SINGLE_COMPATIBLE_LAYER')
        return True
    except (AssertionError, KeyError, TypeError, ValueError, OverflowError, ZeroDivisionError):
        return False


def guard_raw(raw, mixed):
    """Individual core admission only; actual raw scalar facts remain unchanged."""
    guarded = copy.deepcopy(raw)
    for native, measurement in guarded.items():
        c = mixed[native]
        assert validate_certificate(c)
        old = bool(measurement['core_usable'])
        measurement.update(core_usable=old and c['core']['eligible_single'],
            mixed_fact_id=c['core']['fact_id'], mixed_certificate_sha256=c['certificate_sha256'],
            mixed_guard=dict(old_core_usable=old, new_core_usable=old and c['core']['eligible_single'],
                core_mixture_flag=c['core']['mixture_flag'], core_source_quality=c['core']['quality_usable'],
                whole_mixture_flag=c['whole']['mixture_flag'], whole_eligible_single=c['whole']['eligible_single']))
    return guarded


def guard_inputs(row, profiles, mixed):
    """Separate whole/core guards; no mask, identity, motion or actual raw mutation."""
    guarded_row, guarded_profiles = copy.deepcopy(row), copy.deepcopy(profiles)
    assert isinstance(guarded_profiles, dict)
    def unavailable(stats, fact):
        if stats is None:
            return None
        result = dict(stats)
        for field in ('median', 'mad', 'q10', 'q25', 'q75', 'q90'):
            if field in result:
                result[field] = None
        result.update(n=0, valid_fraction=0., mixed_guard_status='UNKNOWN_INDIVIDUAL_SCALAR', mixed_fact_id=fact)
        return result
    for observation in guarded_row['observations']:
        native = observation['id']
        c = mixed[native]
        assert validate_certificate(c)
        if not c['whole']['eligible_single']:
            observation['depth'] = unavailable(observation.get('depth'), c['whole']['fact_id'])
        profile = guarded_profiles[native]
        for part in ('whole', 'core'):
            if not c[part]['eligible_single']:
                profile[part] = unavailable(profile.get(part), c[part]['fact_id'])
        observation['mixed_depth_fact_id'] = c['fact_id']
        profile['mixed_depth_fact_id'] = c['fact_id']
    return guarded_row, guarded_profiles
