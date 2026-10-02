"""Current exclusive-core measurements; no identity or surface certificate.

Geometry follows the DS10 adaptive-core formula with exact grid distances. No depth-edge threshold or
candidate-dependent component selection is introduced. Pixel arrays stay in
memory; public facts contain only statistics, source bindings and hashes.
"""
from __future__ import annotations
import copy
import hashlib
import json
import math
from pathlib import Path

import cv2
import numpy as np
from scipy.ndimage import distance_transform_edt
from common import HERE, ROOT, DATA, read, artifact
from depth_measurement import statistics, usable

CFG = read(HERE/'CONFIG.json')
assert (CFG['min_points'], CFG['min_fraction'], CFG['raw_scale_floor_mm'],
        CFG['max_raw_scale_mm']) == (16, .2, 15, 60)
SOURCE_POLICY = 'SHARED_ACROSS_ANY_MASK_EXCLUDED; SAME_MASK_ROW_MAJOR_CANONICAL_ONCE'


def adaptive_core(region, occupancy):
    """Apply the frozen geometric formula using exact integer pixel distances.

Nearest zero-pixel coordinates are integers. Selecting on squared distances
avoids nondeterministic float32 EDT rounding, including equality boundaries.
Depth, candidate identities and labels are never read by this calculation.
"""
    region, occupancy = np.asarray(region), np.asarray(occupancy)
    assert region.ndim == 2 and region.size and occupancy.shape == region.shape
    exclusive = region.astype(bool, copy=False) & (occupancy == 1)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(
        exclusive.astype('u1'), connectivity=8)
    roi = np.zeros(region.shape, dtype=bool)
    pieces = []
    for label in range(1, count):
        x, y, width, height, area = map(int, stats[label])
        component = labels[y:y+height, x:x+width] == label
        padded = np.pad(component, 1)
        nearest = distance_transform_edt(padded, return_distances=False, return_indices=True)
        difference = np.indices(padded.shape, dtype=np.int64) - nearest
        squared = np.sum(difference*difference, axis=0)[1:-1, 1:-1]
        maximum_squared = int(squared[component].max())
        maximum = math.sqrt(maximum_squared)
        threshold = max(1.5, min(3.0, .5*maximum))
        if maximum_squared <= 9:
            selected = component & (squared >= 3)
        elif maximum_squared >= 36:
            selected = component & (squared >= 9)
        else:
            selected = component & (4*squared >= maximum_squared)
        roi[y:y+height, x:x+width] |= selected
        pieces.append(dict(component_id=label, area=area, dt_max_px=maximum,
            dt_max_squared_px=maximum_squared, threshold_px=threshold, samples=int(selected.sum())))
    return roi, dict(method='EXCLUSIVE_COMPONENT_ADAPTIVE_L2_CORE',
        formula='distance >= max(1.5, min(3.0, 0.5 * component_max_distance))',
        connectivity=8, distance_type='DIST_L2', distance_mask='EXACT_NEAREST_ZERO_INTEGER_GRID',
        arithmetic='INTEGER_SQUARED_SELECTION; FLOAT64_SQRT_METADATA',
        exterior='ZERO_PADDED_COMPONENT_CROP', mask_area=int(region.astype(bool).sum()),
        exclusive_area=int(exclusive.sum()), roi_area=int(roi.sum()),
        component_count=count-1, pieces=pieces,
        samples_meaning='GEOMETRIC_ROI_PIXELS_NOT_VALID_DEPTH_MEASUREMENTS', surface_identity='UNKNOWN')


def array_binding(array):
    value = np.ascontiguousarray(array)
    header = json.dumps([value.dtype.str, list(value.shape)], separators=(',', ':')).encode()
    return dict(dtype=value.dtype.str, shape=list(value.shape),
                sha256=hashlib.sha256(header+b'\n'+value.tobytes()).hexdigest())


def load_raw_frame(global_frame, source_entry=None):
    """Read only the requested NPZ's two fields and its native-depth NPY.

Native sensor Z is a source trace, not numerically equal to aligned camera Z.
The optional SOURCE_OLD row is verified against actual NPZ bytes here.
"""
    frame = int(global_frame)
    assert frame == global_frame and frame >= 0
    path = Path(source_entry['depth_path']) if source_entry else DATA/'depth_rgb_640x360'/f'{frame:06d}.npz'
    raw_binding = artifact(path)
    if source_entry:
        assert raw_binding['bytes'] == source_entry['depth_bytes']
        assert raw_binding['sha256'] == source_entry['depth_sha256']
    assert path.name == f'{frame:06d}.npz', path
    with np.load(path) as source:
        depth, index = source['depth_mm'], source['source_index']
    native_path = DATA/'depth_native_mm'/f'{frame:06d}.npy'
    native = np.load(native_path, allow_pickle=False)
    assert depth.shape == index.shape == (360, 640) and native.shape == (576, 640)
    valid = np.isfinite(depth) & (depth > 0)
    assert np.issubdtype(index.dtype, np.signedinteger)
    assert np.array_equal(valid, index >= 0)
    assert np.all(index[valid] < native.size)
    source_values = native.ravel()[index[valid]]
    assert np.all(np.isfinite(source_values) & (source_values > 0))
    binding = dict(global_frame=frame, raw_npz=raw_binding, native_npy=artifact(native_path),
        actual_fields_read=['depth_mm', 'source_index'], native_fields_read=['current_native_depth_mm'],
        aligned_depth=array_binding(depth), aligned_source_index=array_binding(index),
        native_depth=array_binding(native), aligned_coordinates='RECORDED_RGB_CAMERA_Z_MM',
        native_coordinates='RECORDED_NATIVE_SENSOR_Z_MM; NOT_ASSUMED_EQUAL_TO_ALIGNED_Z',
        sensor_valid_range='UNKNOWN', suspect_above_mm=5000,
        suspect_policy='DIAGNOSTIC_ONLY; NO_NEW_EXCLUSION', RGB_read=False, GT_read=False)
    return depth, index, native, binding


def _reasons(fact):
    reasons = []
    if fact['n'] < 16: reasons.append('MEASURED_N_BELOW_16')
    if fact['valid_fraction'] < .2: reasons.append('MEASURED_FRACTION_BELOW_0_2')
    if fact['median'] is None or fact['median'] <= 0: reasons.append('MISSING_POSITIVE_MEDIAN')
    if fact['mad'] is None or not np.isfinite(fact['mad']) or fact['mad'] < 0:
        reasons.append('MISSING_VALID_ACTUAL_MAD')
    elif max(15., 1.4826*fact['mad']) > 60:
        reasons.append('ACTUAL_MAD_SCALE_ABOVE_60_MM')
    return reasons


def _digest(certificate):
    value = {key: item for key, item in certificate.items() if key != 'certificate_sha256'}
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
        ensure_ascii=False, allow_nan=False).encode('utf-8')).hexdigest()


def measure_contact(depth, source_index, masks, segment, frame, global_frame, *,
                    source_binding, provenance=None, native_depth=None):
    """Return current-frame certificates for every supplied actual mask.

Fraction denominator is the actual geometric core-piece area, including
missing/inferred/shared/duplicate pixels. Every piece is reported. Qualified
components have fixed equal weights independent of every old-ID candidate.
"""
    depth, index = np.asarray(depth), np.asarray(source_index)
    assert depth.ndim == 2 and depth.shape == index.shape and depth.size
    assert np.issubdtype(index.dtype, np.signedinteger)
    assert int(frame) == frame and frame >= 1 and int(global_frame) == global_frame and global_frame >= 0
    assert source_binding['global_frame'] == global_frame
    assert source_binding['frame'] == frame and math.isfinite(source_binding['time'])
    masks = {int(n): np.asarray(region, dtype=bool) for n, region in masks.items()}
    assert all(region.shape == depth.shape for region in masks.values())
    assert len(masks) < np.iinfo('u2').max
    occupancy = sum((region.astype('u2') for region in masks.values()), np.zeros(depth.shape, 'u2'))
    finite = np.isfinite(depth) & (depth > 0)
    mapped = finite & (index >= 0)
    native_valid = mapped.copy()
    if native_depth is not None:
        native = np.asarray(native_depth).ravel()
        assert np.all(index[mapped] < len(native)), 'source_index outside current native depth'
        native_valid[mapped] = np.isfinite(native[index[mapped]]) & (native[index[mapped]] > 0)
    if provenance is None:
        retained = np.ones(depth.shape, bool); mode = 'RAW_DEPTH'; source = 'RAW_SENSOR_CONTACT_CORE'
    else:
        provenance = np.asarray(provenance)
        assert provenance.shape == depth.shape and np.all(np.isin(provenance, [0, 1, 2, 3]))
        retained = provenance == 1; mode = 'RESTORED_DEPTH'; source = 'NATIVE_V2_RETAINED_CONTACT_CORE'
    mask_pixels = {n: np.flatnonzero(region) for n, region in masks.items()}
    mask_sources = {n: np.unique(index[region & mapped]) for n, region in masks.items()}
    all_sources = np.concatenate(list(mask_sources.values())) if masks else np.array([], dtype=index.dtype)
    source_ids, owner_counts = np.unique(all_sources, return_counts=True)
    shared_sources = source_ids[owner_counts > 1]
    full_binding = dict(source_binding=copy.deepcopy(source_binding),
        actual_depth=array_binding(depth), actual_source_index=array_binding(index),
        actual_provenance=array_binding(provenance) if provenance is not None else None,
        actual_native_depth=array_binding(native_depth) if native_depth is not None else None)
    result = {}
    for n, region in masks.items():
        core, geometry = adaptive_core(region, occupancy)
        count, labels = cv2.connectedComponents(core.astype('u1'), connectivity=8)
        exclusive_count, exclusive_labels = cv2.connectedComponents(
            (region & (occupancy == 1)).astype('u1'), connectivity=8)
        assert exclusive_count-1 == geometry['component_count']
        selected = core & native_valid & retained
        shared = np.zeros(depth.shape, bool)
        shared[core & mapped] = np.isin(index[core & mapped], shared_sources)
        selected &= ~shared
        before_dedup = selected.copy()
        positions = np.flatnonzero(selected)
        _, first = np.unique(index.ravel()[positions], return_index=True)
        selected[:] = False
        selected.ravel()[positions[np.sort(first)]] = True
        relation = []
        dilated = np.flatnonzero(cv2.dilate(region.astype('u1'), np.ones((3, 3), 'u1')))
        for other in sorted(masks):
            if other == n: continue
            overlap = int(np.intersect1d(mask_pixels[n], mask_pixels[other], assume_unique=True).size)
            adjacent = int(np.intersect1d(dilated, mask_pixels[other], assume_unique=True).size)
            shared_n = int(np.intersect1d(mask_sources[n], mask_sources[other], assume_unique=True).size)
            if overlap or adjacent or shared_n:
                relation.append(dict(native=other, mask_area=int(masks[other].sum()),
                    overlap_pixels=overlap, pixels_within_8_neighbor_dilation=adjacent,
                    duplicate_mask=bool(np.array_equal(region, masks[other])),
                    query_contained_in_neighbor=bool(len(mask_pixels[n]) and overlap == len(mask_pixels[n])),
                    neighbor_contained_in_query=bool(len(mask_pixels[other]) and overlap == len(mask_pixels[other])),
                    shared_native_source_indices=shared_n,
                    physical_relationship='UNKNOWN'))
        pieces = []
        for label in range(1, count):
            piece = labels == label
            accepted = piece & selected
            fact = statistics(depth, accepted)
            fact['area'] = int(piece.sum())
            fact['valid_fraction'] = fact['n']/max(1, fact['area'])
            pos = np.flatnonzero(accepted)
            scale = max(15., 1.4826*fact['mad']) if fact['mad'] is not None else None
            in_piece_sources = index[piece & before_dedup]
            duplicate_within = int(len(in_piece_sources)-len(np.unique(in_piece_sources)))
            native_values = native[index[accepted]] if native_depth is not None else None
            pieces.append(dict(component_id=f'{segment}/F{frame}/n:{n}/contact/core:{label}',
                core_label=label, geometric_component_id=int(np.unique(exclusive_labels[piece])[0]),
                **fact, median_mm=fact['median'], actual_mad_mm=fact['mad'], scale_mm=scale,
                qualified=bool(usable(fact)), exclusion_reasons=_reasons(fact),
                geometric_samples=int(piece.sum()), geometric_samples_meaning='CORE_AREA_NOT_MEASURED_N',
                selected_source_points=int(len(np.unique(index[accepted]))),
                finite_positive_before_source_exclusions=int((piece & finite).sum()),
                shared_source_pixels_excluded=int((piece & shared).sum()),
                duplicate_pixels_excluded=int((piece & before_dedup & ~selected).sum()),
                duplicate_within_piece_before_canonical=duplicate_within,
                unmapped_pixels=int((piece & finite & (index < 0)).sum()),
                invalid_native_source_pixels=int((piece & mapped & ~native_valid).sum()),
                inferred_pixels_excluded=int((piece & mapped & ~retained).sum()),
                provenance_counts={str(k): int((piece & (provenance == k)).sum()) for k in range(4)} if provenance is not None else None,
                aligned_above_5000_mm_diagnostic_n=int((depth[accepted] > 5000).sum()),
                native_above_5000_mm_diagnostic_n=int((native_values > 5000).sum()) if native_values is not None else None,
                core_pixel_binding=array_binding(np.flatnonzero(piece)),
                selected_pixel_binding=array_binding(pos),
                selected_depth_binding=array_binding(depth.ravel()[pos]),
                selected_native_index_binding=array_binding(index.ravel()[pos]),
                selected_native_values_binding=array_binding(native_values) if native_values is not None else None,
                physical_surface_identity='UNKNOWN', background_suspicion='UNKNOWN', fragment_identity='UNKNOWN'))
        qualified = [dict(p, weight=1/sum(x['qualified'] for x in pieces)) for p in pieces if p['qualified']]
        for piece in geometry['pieces']:
            piece['core_component_ids'] = [p['component_id'] for p in pieces if p['geometric_component_id'] == piece['component_id']]
            piece['core_empty_reason'] = 'NO_GEOMETRIC_CORE_PIXELS' if not piece['samples'] else None
        cohort = 'raw' if provenance is None else 'retained'
        certificate = dict(native=n, source=source, mode=mode, segment=segment, frame=frame,
            global_frame=global_frame, time=source_binding['time'],
            fact_id=f'{segment}/F{frame}/n:{n}/contact/{cohort}',
            source_measurement_fact_id=source_binding.get('measurement_fact_ids', {}).get(str(n)),
            **full_binding, mask_binding=array_binding(region), core_binding=array_binding(core),
            selected_binding=array_binding(selected), source_index_policy=SOURCE_POLICY,
            mask_area=int(region.sum()), shared_mask_pixels_excluded=int((region & (occupancy > 1)).sum()),
            geometric_components=geometry, components=pieces, qualified_components=qualified,
            qualified_component_count=len(qualified), core_usable=bool(qualified), eligible=bool(qualified),
            neighbors=relation, mixture_policy='EQUAL_QUALIFIED_COMPONENTS_FIXED_BEFORE_CANDIDATE_COMPARISON',
            missing_policy='COMMON_UNINFORMATIVE_NO_COMMIT',
            measured_fraction_denominator='ACTUAL_CORE_COMPONENT_GEOMETRIC_AREA',
            inferred_measurement_certificate=False,
            qualification='CURRENT_MEASUREMENT_AND_SOURCE_ONLY_NOT_FISH_IDENTITY',
            physical_surface_identity='UNKNOWN', background_suspicion='UNKNOWN',
            physical_accuracy='UNKNOWN', sensor_valid_range='UNKNOWN',
            upstream_RGB_and_future_used=provenance is not None,
            no_future_frame_read=True, no_history_write=True,
            no_depth_threshold_segmentation=True)
        certificate['certificate_sha256'] = _digest(certificate)
        assert validate_contact_certificate(certificate)
        result[n] = certificate
    return result


def validate_contact_certificate(certificate, *, native=None, frame=None, global_frame=None, mode=None):
    """Recheck internal statistics/weights/current binding, not physical pixels.

The producer's frozen code and source hashes establish pixel provenance. This
metadata-only validator cannot independently certify the sensor or ownership.
"""
    try:
        c = certificate
        assert c['certificate_sha256'] == _digest(c)
        for key, expected in (('native', native), ('frame', frame), ('global_frame', global_frame), ('mode', mode)):
            assert expected is None or c[key] == expected
        assert c['mode'] in ('RAW_DEPTH', 'RESTORED_DEPTH')
        assert c['source_binding']['global_frame'] == c['global_frame']
        assert c['source_binding']['frame'] == c['frame']
        assert math.isfinite(c['time']) and c['source_binding']['time'] == c['time']
        assert c['no_future_frame_read'] and c['no_history_write'] and c['no_depth_threshold_segmentation']
        binding = c['source_binding']
        if 'native_depth' in binding:
            assert binding['native_depth'] == c['actual_native_depth']
        if c['mode'] == 'RAW_DEPTH':
            for outer, inner in (('aligned_depth', 'actual_depth'), ('aligned_source_index', 'actual_source_index')):
                if outer in binding: assert binding[outer] == c[inner]
        else:
            for outer, inner in (('v2_depth', 'actual_depth'), ('v2_source_index', 'actual_source_index'), ('v2_provenance', 'actual_provenance')):
                if outer in binding: assert binding[outer] == c[inner]
            metadata = binding.get('actual_v2_metadata', binding.get('restored_source'))
            if metadata is not None:
                assert metadata['global_frame'] == metadata['index'] == metadata['native_index'] == c['global_frame']
                assert metadata['delta_us'] == metadata['color_timestamp_us']-metadata['depth_timestamp_us']
                assert metadata['future_support'] == 'UPSTREAM_I_PLUS_1_OFFLINE'
                assert Path(metadata['native_path']).resolve() == Path(binding['native_h5']['path']).resolve()
        assert c['source_measurement_fact_id'] == c['source_binding'].get('measurement_fact_ids', {}).get(str(c['native']))
        assert c['source'] == ('RAW_SENSOR_CONTACT_CORE' if c['mode'] == 'RAW_DEPTH' else 'NATIVE_V2_RETAINED_CONTACT_CORE')
        for key in ('actual_depth', 'actual_source_index', 'mask_binding', 'core_binding', 'selected_binding'):
            binding = c[key]
            assert len(binding['shape']) == 2 and binding['shape'] == c['actual_depth']['shape']
            assert len(binding['sha256']) == 64 and all(x in '0123456789abcdef' for x in binding['sha256'])
        if c['mode'] == 'RESTORED_DEPTH':
            assert c['actual_provenance']['shape'] == c['actual_depth']['shape']
        else:
            assert c['actual_provenance'] is None
        for key in ('raw_npz', 'native_npy', 'native_h5'):
            binding = c['source_binding'].get(key)
            if binding is not None:
                assert isinstance(binding['path'], str) and binding['bytes'] > 0
                assert len(binding['sha256']) == 64 and all(x in '0123456789abcdef' for x in binding['sha256'])
        assert c['source_index_policy'] == SOURCE_POLICY and not c['inferred_measurement_certificate']
        qualified = []
        for p in c['components']:
            assert isinstance(p['n'], int) and isinstance(p['area'], int)
            assert p['n'] == p['selected_source_points'] and 0 <= p['n'] <= p['area']
            assert p['valid_fraction'] == p['n']/max(1, p['area'])
            assert p['median_mm'] == p['median'] and p['actual_mad_mm'] == p['mad']
            assert p['scale_mm'] == (max(15., 1.4826*p['mad']) if p['mad'] is not None else None)
            assert p['exclusion_reasons'] == _reasons(p) and p['qualified'] == bool(usable(p))
            assert p['geometric_samples'] == p['area']
            assert p['core_pixel_binding']['shape'] == [p['area']]
            for key in ('selected_pixel_binding', 'selected_depth_binding', 'selected_native_index_binding'):
                assert p[key]['shape'] == [p['n']]
            if p['qualified']: qualified.append(p)
        expected = [dict(p, weight=1/len(qualified)) for p in qualified]
        assert c['qualified_components'] == expected
        assert c['qualified_component_count'] == len(qualified) and c['core_usable'] == c['eligible'] == bool(qualified)
        assert sum(p['area'] for p in c['components']) == c['geometric_components']['roi_area']
        return True
    except (AssertionError, KeyError, TypeError, ValueError, OverflowError):
        return False


check_certificate = validate_certificate = validate_contact_certificate
