"""Synthetic source/quality checks and one earliest prediction-born packet.

The optional real packet uses SOURCE_OLD masks and current depth only. It does
not inspect any reference label, old scored event, or future image array.
"""
from __future__ import annotations
import argparse
import copy
import importlib.util
import unittest
import numpy as np
from common import HERE, ROOT, SEGMENTS, input_dir, read, rows, artifact, write_new
from depth_measurement import decode
from contact_measurement import (measure_contact, load_raw_frame, array_binding,
                                 check_certificate, _digest, adaptive_core)


def packet(masks=None, depth=None, index=None, provenance=None, fact_ids=None):
    shape = (64, 96)
    if masks is None:
        mask = np.zeros(shape, bool); mask[8:28, 8:28] = True; masks = {1: mask}
    if depth is None: depth = np.full(shape, 900., 'f4')
    if index is None: index = np.arange(np.prod(shape), dtype='i4').reshape(shape)
    binding = dict(frame=1, global_frame=0, time=1.25,
        measurement_fact_ids=fact_ids or {str(n): f'test/F1/n:{n}/adaptive/raw' for n in masks})
    return measure_contact(depth, index, masks, 'test', 1, 0,
        source_binding=binding, provenance=provenance,
        native_depth=np.full(shape, 1400., 'f4'))


class ContactMeasurementTests(unittest.TestCase):
    def test_exact_core_agrees_with_independent_euclidean_grid(self):
        # Direct nearest-zero enumeration independently covers floor/half/clamp.
        for radius in (2, 3, 4, 5, 8):
            yy, xx = np.indices((25, 25))
            region = (yy-12)**2 + (xx-12)**2 <= radius**2
            roi, geometry = adaptive_core(region, region.astype('u2'))
            padded = np.pad(region, 1)
            zeros = np.argwhere(~padded)
            points = np.argwhere(padded)
            expected = np.zeros_like(padded)
            squared = ((points[:, None, :] - zeros[None, :, :])**2).sum(axis=2).min(axis=1)
            maximum = int(squared.max())
            selected = squared >= 3 if maximum <= 9 else (squared >= 9 if maximum >= 36 else 4*squared >= maximum)
            expected[tuple(points[selected].T)] = True
            self.assertTrue(np.array_equal(roi, expected[1:-1, 1:-1]))
            self.assertEqual(geometry['pieces'][0]['dt_max_squared_px'], maximum)
            repeated_roi, repeated_geometry = adaptive_core(region, region.astype('u2'))
            self.assertTrue(np.array_equal(roi, repeated_roi))
            self.assertEqual(geometry, repeated_geometry)

    def test_measured_n_and_fraction_are_not_geometric_samples(self):
        baseline = packet()[1]
        area = baseline['components'][0]['area']
        depth = np.zeros((64, 96), 'f4')
        positions = np.flatnonzero(np.pad(np.ones((16, 16), bool), ((10, 38), (10, 70))))[:52]
        depth.ravel()[positions] = 900
        c = packet(depth=depth)[1]; p = c['components'][0]
        self.assertEqual(p['area'], area); self.assertEqual(p['n'], 52)
        self.assertEqual(p['valid_fraction'], 52/area); self.assertTrue(p['qualified'])
        self.assertNotEqual(p['geometric_samples'], p['n'])

    def test_no_depth_threshold_split_and_actual_mad_gate(self):
        depth = np.full((64, 96), 900., 'f4'); depth[18:28, 8:28] = 1200
        c = packet(depth=depth)[1]
        self.assertEqual(len(c['components']), 1)
        self.assertEqual(c['components'][0]['actual_mad_mm'], 150)
        self.assertFalse(c['eligible'])
        self.assertIn('ACTUAL_MAD_SCALE_ABOVE_60_MM', c['components'][0]['exclusion_reasons'])

    def test_all_geometry_components_including_empty_thin_fragment(self):
        region = np.zeros((64, 96), bool)
        region[5:25, 5:25] = 1; region[35:55, 50:85] = 1; region[60, 3:20] = 1
        depth = np.full(region.shape, 900., 'f4'); depth[35:55, 50:85] = 1100
        c = packet(masks={1: region}, depth=depth)[1]
        self.assertEqual(c['geometric_components']['component_count'], 3)
        self.assertEqual(len(c['components']), 2)
        self.assertEqual([p['weight'] for p in c['qualified_components']], [.5, .5])
        self.assertEqual(c['geometric_components']['pieces'][-1]['samples'], 0)
        self.assertEqual(c['geometric_components']['pieces'][-1]['core_empty_reason'], 'NO_GEOMETRIC_CORE_PIXELS')

    def test_shared_mask_and_duplicate_mask_are_excluded(self):
        a = np.zeros((64, 96), bool); a[8:40, 8:40] = 1
        b = a.copy()
        c = packet(masks={1:a, 2:b})
        self.assertFalse(c[1]['eligible']); self.assertFalse(c[2]['eligible'])
        self.assertEqual(c[1]['shared_mask_pixels_excluded'], 32*32)
        self.assertTrue(c[1]['neighbors'][0]['duplicate_mask'])

    def test_shared_native_source_is_excluded_even_outside_other_core(self):
        a = np.zeros((64,96), bool); a[8:28,8:28] = 1
        b = np.zeros_like(a); b[35:55,55:75] = 1
        index = np.arange(a.size, dtype='i4').reshape(a.shape)
        index[35,55] = index[10,10]  # Neighbor's edge, outside its adaptive core.
        c = packet(masks={1:a,2:b}, index=index)[1]
        self.assertEqual(c['components'][0]['n'], 255)
        self.assertEqual(c['components'][0]['shared_source_pixels_excluded'], 1)
        self.assertEqual(c['neighbors'][0]['overlap_pixels'], 0)
        self.assertEqual(c['neighbors'][0]['shared_native_source_indices'], 1)

    def test_same_mask_duplicate_sensor_point_is_canonical_row_major(self):
        index = np.arange(64*96, dtype='i4').reshape(64,96)
        index[10,11] = index[10,10]
        c = packet(index=index)[1]; p = c['components'][0]
        self.assertEqual(p['n'], 255); self.assertEqual(p['duplicate_pixels_excluded'], 1)
        selected = np.zeros(index.shape, bool); selected[10:26,10:26] = 1; selected[10,11] = 0
        self.assertEqual(c['selected_binding'], array_binding(selected))
        self.assertEqual(p['selected_source_points'], p['n'])

    def test_retained_only_and_scalar_inferred_binding_are_independent(self):
        prov = np.full((64,96), 2, 'u1')
        c = packet(provenance=prov)[1]
        self.assertFalse(c['eligible']); self.assertEqual(c['components'][0]['n'], 0)
        self.assertEqual(c['components'][0]['inferred_pixels_excluded'], 256)
        prov[8:28,8:28] = 1
        actual_scalar = 'test/F1/n:1/adaptive/v2/inferred'
        c = packet(provenance=prov, fact_ids={'1':actual_scalar})[1]
        self.assertTrue(c['eligible']); self.assertEqual(c['source_measurement_fact_id'], actual_scalar)
        self.assertEqual(c['source'], 'NATIVE_V2_RETAINED_CONTACT_CORE')
        self.assertFalse(c['inferred_measurement_certificate'])

    def test_suspect_diagnostic_is_not_a_new_range_threshold(self):
        c = packet(depth=np.full((64,96), 12254., 'f4'))[1]
        self.assertTrue(c['eligible'])
        self.assertEqual(c['components'][0]['aligned_above_5000_mm_diagnostic_n'], 256)
        self.assertEqual(c['sensor_valid_range'], 'UNKNOWN')

    def test_missing_depth_common_uninformative_and_semantic_tamper_rejected(self):
        c = packet(depth=np.full((64,96), np.nan, 'f4'))[1]
        self.assertFalse(c['eligible']); self.assertEqual(c['qualified_components'], [])
        self.assertEqual(c['missing_policy'], 'COMMON_UNINFORMATIVE_NO_COMMIT')
        self.assertTrue(check_certificate(c)); self.assertFalse(check_certificate(c, frame=2))
        forged = copy.deepcopy(c); forged['eligible'] = True; forged['certificate_sha256'] = _digest(forged)
        self.assertFalse(check_certificate(forged))
        forged = copy.deepcopy(c); forged['time'] = 2.; forged['certificate_sha256'] = _digest(forged)
        self.assertFalse(check_certificate(forged))

    def test_input_arrays_and_candidate_order_are_not_used_or_mutated(self):
        depth = np.full((64,96), 900., 'f4'); index = np.arange(depth.size, dtype='i4').reshape(depth.shape)
        a = np.zeros_like(depth, bool); a[8:28,8:28] = 1
        before = [array_binding(x) for x in (depth,index,a)]
        first = packet(masks={1:a}, depth=depth, index=index)
        self.assertEqual(before, [array_binding(x) for x in (depth,index,a)])
        self.assertEqual(first, packet(masks={1:a}, depth=depth, index=index))


def actual_first_contact():
    """Earliest automatic first-ever native birth with contact and input quality.

This is source acceptance, not actual branch eligibility or identity success.
"""
    selected = None
    for segment, (start, stop) in SEGMENTS.items():
        seen = set()
        for row in rows(input_dir(segment)/'observations.jsonl.gz'):
            current = {o['id'] for o in row['observations']}
            for observation in sorted(row['observations'], key=lambda o:o['id']):
                if row['frame'] == 1 or observation['id'] in seen: continue
                presence = observation.get('presence')
                confidence = presence >= .5 if presence is not None else observation.get('score_birth',0) >= .5
                if observation.get('neighbors') and observation['area'] >= 64 and confidence:
                    selected = segment, row, observation; break
            seen |= current
            if selected: break
        if selected: break
    assert selected, 'No SOURCE_OLD contact birth; do not manufacture a packet'
    segment, row, observation = selected; frame = row['frame']; global_frame = row['global_frame']
    base = input_dir(segment)
    source_entry = read(base/'sources.json')[frame-1]
    depth, index, native, binding = load_raw_frame(global_frame, source_entry)
    assignment = next(x for x in rows(base/'assignments.jsonl.gz') if x['frame'] == frame)
    masks = {int(key[2:]):decode(rle) for key,rle in assignment['masks'].items()}
    cache = ROOT/'experiments/ds10_depth_failure_repair/run'/segment/'public'
    old = next(x for x in rows(cache/'DEPTH_OBSERVATIONS.jsonl.gz') if x['frame'] == frame)
    assert (old['global_frame'], old['time']) == (global_frame, row['time'])
    raw_binding = dict(binding, frame=frame, time=row['time'],
        measurement_fact_ids={n:x['fact_id'] for n,x in old['adaptive_raw'].items()})
    raw = measure_contact(depth,index,masks,segment,frame,global_frame,
        source_binding=raw_binding,native_depth=native)
    spec = importlib.util.spec_from_file_location('ds12_actual_native_v2_reader',
        ROOT/'experiments/ds10_depth_failure_repair/restored_source.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    reader = module.RestoredDepth()
    try:
        restored, provenance, metadata = reader(global_frame)
        frozen = read(cache/'FREEZE.json')
        h5_binding = next(item for item in frozen['restored_sources'].values() if item['path'] == metadata['native_path'])
        assert artifact(metadata['native_path']) == h5_binding
        v2_binding = dict(binding, frame=frame, time=row['time'], restored_source=metadata,
            native_h5=h5_binding, measurement_fact_ids={n:x['fact_id'] for n,x in old['restored'].items()})
        v2 = measure_contact(restored,reader.current_source_index,masks,segment,frame,global_frame,
            source_binding=v2_binding,provenance=provenance,native_depth=native)
    finally:
        reader.close()
    n = observation['id']
    assert all(check_certificate(c,frame=frame,global_frame=global_frame) for c in (*raw.values(),*v2.values()))
    return dict(status='PASS_CURRENT_SOURCE_RECONSTRUCTION_NOT_IDENTITY_SUCCESS',
        segment=segment, frame=frame, global_frame=global_frame, native=n,
        automatic_selection='EARLIEST_FIRST_EVER_NATIVE_CONTACT_BIRTH_WITH_AREA64_AND_INPUT_CONFIDENCE; NO_GT',
        actual_observation=observation, source_list=artifact(base/'sources.json'),
        assignment_source=artifact(base/'assignments.jsonl.gz'), measurement_cache=artifact(cache/'DEPTH_OBSERVATIONS.jsonl.gz'),
        raw_certificate=raw[n], retained_v2_certificate=v2[n],
        all_current_masks=len(masks), every_mask_checked=True,
        certification='PIXEL_SOURCE_AND_MEASUREMENT_QUALITY_ONLY',
        physical_surface_identity='UNKNOWN', background_suspicion='UNKNOWN', GT_read=False, RGB_read=False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--actual-first-contact', action='store_true')
    parser.add_argument('--write-new', action='store_true')
    args = parser.parse_args()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ContactMeasurementTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    assert result.wasSuccessful()
    report = dict(status='PASS', synthetic_tests=result.testsRun, GT_read=False, RGB_read=False)
    if args.actual_first_contact: report['real_source_acceptance'] = actual_first_contact()
    if args.write_new:
        write_new(HERE/'CONTACT_MEASUREMENT_CHECKS.json', report)
    actual = report.get('real_source_acceptance', {})
    print(f"{result.testsRun} synthetic tests PASS; real contact global={actual.get('global_frame')} native={actual.get('native')} raw_eligible={actual.get('raw_certificate',{}).get('eligible')} retained_eligible={actual.get('retained_v2_certificate',{}).get('eligible')}")


if __name__ == '__main__': main()
