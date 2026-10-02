"""Source, mixture and sparse-support checks for current-mask layer representation."""
import copy
import json
import unittest

import numpy as np

from mixed_depth import adaptive_core, guard_inputs, guard_raw, measure_mixed, validate_certificate


def fixture():
    depth = np.full((48, 48), 1500., dtype='f4')
    index = np.arange(depth.size, dtype='i4').reshape(depth.shape)
    region = np.zeros(depth.shape, bool)
    region[12:36, 12:36] = True
    depth[region] = 1000.
    return [depth, index, {1: region}, 'test', 1, 0], dict(global_frame=0, frame=1, time=.1, GT_read=False, RGB_read=False)


def run(data, binding):
    return measure_mixed(*data, source_binding=binding, native_depth=np.full(data[0].shape, 1000., 'f4'))


class MixedDepthTests(unittest.TestCase):
    def test_single_layer_keeps_actual_support_and_background_is_diagnostic(self):
        data, binding = fixture()
        result = run(data, binding)['objects'][1]
        self.assertTrue(result['core']['eligible_single'])
        self.assertEqual(result['core']['summary']['median'], 1000.)
        self.assertEqual(result['core']['qualified_layer_count'], 1)
        self.assertTrue(result['annulus']['quality_usable'])
        self.assertEqual(result['core']['layers'][0]['background_compatibility'], 'DIFFERENT_FROM_LOCAL_ANNULUS_PROXY')
        self.assertEqual(result['physical_mask_fish_count'], 'UNKNOWN')

    def test_two_substantial_layers_are_preserved_without_peak_selection(self):
        data, binding = fixture()
        data[0][12:36, 24:36] = 1200.
        result = run(data, binding)['objects'][1]
        for part in ('core', 'whole'):
            self.assertTrue(result[part]['mixture_flag'])
            self.assertFalse(result[part]['eligible_single'])
            self.assertEqual([p['median'] for p in result[part]['layers']], [1000., 1200.])
            self.assertAlmostEqual(sum(p['measured_support_fraction'] for p in result[part]['layers']), 1.)
            self.assertTrue(all(p['fish_count'] == 'UNKNOWN' for p in result[part]['layers']))
        self.assertTrue(result['no_nearest_or_largest_layer_selected'])

    def test_background_compatible_second_layer_is_not_silently_removed(self):
        data, binding = fixture()
        data[0][12:36, 24:36] = 1500.
        result = run(data, binding)['objects'][1]['core']
        self.assertTrue(result['mixture_flag'])
        self.assertEqual(result['layers'][1]['background_compatibility'], 'BACKGROUND_COMPATIBLE')
        self.assertEqual(result['layers'][1]['median'], 1500.)

    def test_source_duplicates_cannot_fabricate_quality(self):
        data, binding = fixture()
        data[1][data[2][1]] = 0
        result = run(data, binding)['objects'][1]
        self.assertEqual(result['whole']['summary']['n'], 1)
        self.assertFalse(result['whole']['quality_usable'])
        self.assertFalse(result['whole']['eligible_single'])
        self.assertGreater(result['whole']['within_mask_duplicate_pixels_excluded'], 0)

    def test_sparse_disconnected_same_layer_is_not_fragmented_by_connectivity(self):
        data, binding = fixture()
        region = np.zeros(data[0].shape, bool)
        region[18:28, 18:28] = True
        data[2] = {1: region}
        data[0][region] = 0.
        core, _ = adaptive_core(region, region.astype('u2'))
        points = np.flatnonzero(core)
        data[0].ravel()[points[::2]] = 1000.
        result = run(data, binding)['objects'][1]['core']
        self.assertEqual(result['layer_count'], 1)
        self.assertTrue(result['eligible_single'])
        self.assertGreaterEqual(result['summary']['n'], 16)

    def test_minor_layer_retained_and_continuous_bridge_limit_explicit(self):
        data, binding = fixture()
        data[0][12:14, 12:36] = 1200.
        result = run(data, binding)['objects'][1]['whole']
        self.assertEqual(result['layer_count'], 2)
        self.assertFalse(result['mixture_flag'])
        self.assertGreater(result['minor_layer_n'], 0)
        self.assertTrue(result['eligible_single'])
        self.assertTrue(any('Continuous or bridged' in text for text in result['limitations']))

    def test_shared_sensor_sources_are_excluded_across_original_masks(self):
        data, binding = fixture()
        other = np.zeros(data[0].shape, bool)
        other[1:9, 1:9] = True
        data[2][2] = other
        positions = np.flatnonzero(data[2][1])
        data[1].ravel()[positions] = np.resize(data[1][other], len(positions))
        result = run(data, binding)['objects'][1]['whole']
        self.assertEqual(result['summary']['n'], 0)
        self.assertFalse(result['eligible_single'])
        self.assertGreater(result['shared_source_pixels_excluded'], 0)

    def test_overlap_pollution_cannot_be_certified_by_excluding_its_points(self):
        data, binding = fixture()
        other = np.zeros(data[0].shape, bool)
        other[12:36, 24:36] = True
        data[2][2] = other
        data[0][other] = 1400.
        result = run(data, binding)['objects'][1]
        self.assertTrue(result['whole']['inclusive_mixture_flag'])
        self.assertFalse(result['whole']['eligible_single'])
        self.assertFalse(result['whole']['source_ownership_exclusive'])
        self.assertEqual([p['median'] for p in result['whole']['inclusive_layers']], [1000., 1400.])
        self.assertEqual(result['whole']['summary']['median'], 1000.)

    def test_guards_separate_whole_core_and_do_not_replace_original_scalar(self):
        data, binding = fixture()
        core, _ = adaptive_core(data[2][1], data[2][1].astype('u2'))
        data[0][data[2][1] & ~core] = 1400.
        certificate = run(data, binding)['objects']
        self.assertTrue(certificate[1]['whole']['mixture_flag'])
        self.assertTrue(certificate[1]['core']['eligible_single'])
        raw = {1: dict(core_usable=True, core=dict(n=100, median=1000., mad=0., valid_fraction=1.), fact_id='original')}
        row = dict(observations=[dict(id=1, mask='n:1', box=[1, 2, 3, 4], depth=dict(n=100, median=1000., mad=0., valid_fraction=1.))])
        profiles = {1: dict(whole=dict(raw[1]['core']), core=dict(raw[1]['core']))}
        original = copy.deepcopy((raw, row, profiles))
        new_raw = guard_raw(raw, certificate)
        new_row, new_profiles = guard_inputs(row, profiles, certificate)
        self.assertEqual(new_raw[1]['core'], raw[1]['core'])
        self.assertEqual(new_raw[1]['fact_id'], 'original')
        self.assertTrue(new_raw[1]['core_usable'])
        self.assertIsNone(new_row['observations'][0]['depth']['median'])
        self.assertEqual(new_profiles[1]['core'], profiles[1]['core'])
        self.assertEqual(new_row['observations'][0]['mask'], 'n:1')
        self.assertEqual((raw, row, profiles), original)

    def test_empty_mask_keeps_unknown_object_and_certificate_tamper_rejected(self):
        data, binding = fixture()
        data[2][1][:] = False
        result = run(data, binding)['objects']
        self.assertIn(1, result)
        self.assertEqual(result[1]['whole']['summary']['n'], 0)
        self.assertEqual(result[1]['core']['status'], 'UNKNOWN')
        self.assertFalse(result[1]['core']['eligible_single'])
        self.assertTrue(validate_certificate(result[1]))
        tampered = copy.deepcopy(result[1])
        tampered['core']['eligible_single'] = True
        self.assertFalse(validate_certificate(tampered))

    def test_future_and_model_inputs_rejected_and_order_has_no_effect(self):
        data, binding = fixture()
        for field in ('GT_read', 'RGB_read', 'restored_read'):
            invalid = dict(binding, **{field: True})
            with self.assertRaises(AssertionError):
                run(data, invalid)
        with self.assertRaises(AssertionError):
            run(data, dict(binding, global_frame=1))
        original = copy.deepcopy(data)
        result = run(data, binding)
        self.assertTrue(np.array_equal(data[0], original[0]))
        self.assertTrue(np.array_equal(data[1], original[1]))
        json.dumps(result, allow_nan=False)


if __name__ == '__main__':
    unittest.main()
