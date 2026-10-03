"""Numerical and actual-source semantic checks, without labels or identity state."""
import copy
import json
from pathlib import Path
import sys
import unittest

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'experiments/ds20_pending_confirmation_isolation'))
import common  # Initialize the existing DS18/source helper paths.
from measurement import measure_local_background, array_binding
import numpy as np


def fixture():
    yy, xx = np.indices((100, 120))
    depth = (1500. + 2. * xx + 1.5 * yy).astype('f4')
    own = np.zeros(depth.shape, bool)
    own[35:65, 45:75] = True
    depth[own] -= 100.
    index = np.arange(depth.size, dtype='i4').reshape(depth.shape)
    native = np.full(depth.shape, 1000., 'f4')  # Sensor and camera Z need not equal.
    return depth, index, native, {1: own}


def binding(depth, index, native, **extra):
    return dict(global_frame=0, frame=1, time=.1, actual_fields_read=['depth_mm', 'source_index'],
        native_fields_read=['current_native_depth_mm'], aligned_depth=array_binding(depth),
        aligned_source_index=array_binding(index), native_depth=array_binding(native),
        GT_read=False, RGB_read=False, restored_read=False, **extra)


def measure(data, source=None, expected=None):
    source = source or binding(*data[:3])
    return measure_local_background(*data, 1, 'test', 1, 0, .1,
        source_binding=source, expected_source_binding=expected)


class MeasurementTests(unittest.TestCase):
    def test_affine_slope_support_and_no_mutation(self):
        data = fixture()
        old = [x.copy() for x in data[:3]] + [{n: m.copy() for n, m in data[3].items()}]
        facts, maps = measure(data)
        self.assertEqual(facts['status'], 'AVAILABLE')
        np.testing.assert_allclose(facts['plane']['beta_mm'][1:], [40., 30.], atol=1e-8)
        self.assertAlmostEqual(facts['components'][0]['residual_summary']['median'], -100., places=8)
        self.assertEqual(facts['qualified_independent_n'], 900)
        self.assertEqual(facts['foreground_identity'], 'UNKNOWN')
        self.assertTrue(maps['qualified_support'][data[3][1]].all())
        for actual, original in zip(data[:3], old[:3]):
            np.testing.assert_array_equal(actual, original)
        np.testing.assert_array_equal(data[3][1], old[3][1])
        json.dumps(facts, allow_nan=False)

    def test_neighbors_and_shared_source_are_excluded(self):
        data = fixture()
        neighbor = np.zeros(data[0].shape, bool)
        neighbor[30:70, 65:85] = True
        data[3][2] = neighbor
        data[0][neighbor] -= 400.
        facts, maps = measure(data)
        self.assertFalse((maps['annulus'] & maps['neighbor_excluded']).any())
        self.assertFalse((maps['mask_selected'] & maps['neighbor_excluded']).any())
        self.assertGreater(facts['neighbor_overlap_removed_n'], 0)
        np.testing.assert_allclose(facts['plane']['beta_mm'][1:], [40., 30.], atol=1e-8)
        # A physical source repeated outside the neighbor margin still cannot belong to both masks.
        index = data[1]
        index[40, 50] = index[35, 80]
        facts, maps = measure(data)
        self.assertFalse(maps['mask_selected'][40, 50])
        self.assertGreater(facts['mask_source_exclusions']['shared_source_pixels_excluded'], 0)

    def test_background_only_and_empty_mask_keep_unknown(self):
        data = fixture()
        data[0][data[3][1]] += 100.
        facts, maps = measure(data)
        self.assertEqual(facts['status'], 'UNKNOWN')
        self.assertEqual(facts['reason'], 'NO_QUALIFIED_BACKGROUND_RELATIVE_SUPPORT')
        self.assertEqual(facts['significant_independent_n'], 0)
        self.assertFalse(maps['qualified_support'].any())
        data[3][1][:] = False
        self.assertEqual(measure(data)[0]['reason'], 'EMPTY_ORIGINAL_MASK')

    def test_unique_sources_never_count_replicated_pixels_as_quality(self):
        data = fixture()
        data[1][data[3][1]] = 1
        facts, maps = measure(data)
        self.assertEqual(facts['mask_summary']['n'], 1)
        self.assertEqual(facts['mask_source_exclusions']['within_mask_duplicate_pixels_excluded'], 899)
        self.assertEqual(facts['status'], 'UNKNOWN')
        self.assertEqual(facts['reason'], 'INSUFFICIENT_INDEPENDENT_MASK_COVERAGE')
        self.assertEqual(int(maps['mask_selected'].sum()), 1)

    def test_both_signs_retained_without_largest_peak(self):
        data = fixture()
        data[0][35:65, 60:75] += 200.
        facts, maps = measure(data)
        qualified = [p for p in facts['components'] if p['qualified']]
        self.assertEqual([p['sign'] for p in qualified], ['NEARER', 'FARTHER'])
        self.assertEqual([p['independent_n'] for p in qualified], [450, 450])
        self.assertEqual(facts['qualified_independent_n'], 900)
        self.assertTrue(facts['no_peak_selection'])

    def test_self_consistent_frame_and_field_forgeries_rejected_semantically(self):
        data = fixture()
        source = binding(*data[:3])
        for key, value in [('global_frame', 1), ('frame', 2), ('time', .2), ('GT_read', True)]:
            forged = dict(source, **{key: value})
            # The forged caller has a perfectly consistent new manifest.
            json.loads(json.dumps(forged))
            with self.assertRaises(AssertionError):
                measure(data, forged, forged)
        forged = copy.deepcopy(source)
        forged['actual_fields_read'].append('annotation/instance_id')
        with self.assertRaisesRegex(AssertionError, 'Unexposed'):
            measure(data, forged, forged)

    def test_self_consistent_index_corruption_rejected_by_actual_native_values(self):
        data = fixture()
        data[2][0, 0] = 0.
        data[1][40, 50] = 0
        source = binding(*data[:3])
        with self.assertRaisesRegex(AssertionError, 'missing native'):
            measure(data, source, source)
        data = fixture()
        data[1][40, 50] = data[2].size
        source = binding(*data[:3])
        with self.assertRaisesRegex(AssertionError, 'Illegal native'):
            measure(data, source, source)

    def test_same_frame_rolled_source_index_cannot_replace_trusted_projection(self):
        data = fixture()
        expected = binding(*data[:3])
        data[1][:] = np.roll(data[1], 1, axis=1)
        source = binding(*data[:3])
        with self.assertRaisesRegex(AssertionError, 'Trusted actual source'):
            measure(data, source, expected)

    def test_sparse_collinear_background_cannot_fit_plane(self):
        data = fixture()
        own = data[3][1]
        keep = own.copy()
        keep[20, :] = True
        data[0][~keep] = 0.
        data[1][~keep] = -1
        facts, _ = measure(data)
        self.assertEqual(facts['status'], 'UNKNOWN')
        self.assertIn(facts['reason'], ('INSUFFICIENT_INDEPENDENT_BACKGROUND_COVERAGE', 'DEGENERATE_BACKGROUND_GEOMETRY'))


if __name__ == '__main__':
    unittest.main()
