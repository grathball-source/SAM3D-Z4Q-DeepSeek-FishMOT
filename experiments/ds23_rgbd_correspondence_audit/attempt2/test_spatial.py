"""Small runnable checks for fixed-grid diagnostics, no source data or labels."""
from pathlib import Path
import json
import sys
import unittest

sys.dont_write_bytecode = True
sys.path.append(str(Path(__file__).resolve().parents[3] / 'experiments/ds20_pending_confirmation_isolation'))
import common  # Existing local numerical dependency paths; no installation.
from spatial import spatial_metrics
import numpy as np


def fixture():
    mask = np.zeros((10, 10), bool)
    mask[2:8, 1:5] = True
    depth = np.full(mask.shape, 1000., 'f4')
    rgb = np.zeros((*mask.shape, 3), 'uint8')
    return mask, depth, rgb


class SpatialTests(unittest.TestCase):
    def test_empty_edges_are_unknown_and_json_finite(self):
        metrics, debug = spatial_metrics(*fixture())
        for name in ('boundary_to_depth_edge', 'boundary_to_rgb_edge'):
            self.assertEqual(metrics[name]['status'], 'UNKNOWN')
            self.assertEqual(metrics[name]['query_n'], 16)
            self.assertEqual(metrics[name]['n'], 0)
            self.assertIsNone(metrics[name]['median_px'])
        self.assertFalse(debug['depth_edges'].any())
        json.dumps(metrics, allow_nan=False)

    def test_missing_depth_never_creates_a_measured_edge(self):
        mask, depth, rgb = fixture()
        depth[:, 5:] = 0.
        depth[0, 1] = np.nan
        depth[1, 1] = np.inf
        metrics, debug = spatial_metrics(mask, depth, rgb)
        self.assertFalse(debug['depth_edges'].any())
        self.assertEqual(metrics['boundary_to_depth_edge']['status'], 'UNKNOWN')
        self.assertLess(metrics['coverage']['roi10']['valid_depth_fraction'], 1.)
        json.dumps(metrics, allow_nan=False)

    def test_known_vertical_depth_edge_marks_both_endpoints_and_exact_distance(self):
        mask, depth, rgb = fixture()
        depth[:, 5:] += 30.
        metrics, debug = spatial_metrics(mask, depth, rgb)
        expected = np.zeros(mask.shape, bool)
        expected[:, 4:6] = True
        np.testing.assert_array_equal(debug['depth_edges'], expected)
        np.testing.assert_allclose(debug['depth_distance_px'][:, 1], 3., atol=1e-6)
        np.testing.assert_allclose(debug['depth_distance_px'][:, 4], 0., atol=1e-6)
        self.assertEqual(metrics['edge_counts']['depth']['full_frame'], 20)
        self.assertEqual(metrics['edge_counts']['depth']['inside_mask'], 6)
        self.assertAlmostEqual(metrics['boundary_to_depth_edge']['median_px'], 1.5)
        self.assertAlmostEqual(metrics['boundary_to_depth_edge']['fractions_within_px']['1'], .5)
        self.assertEqual(metrics['identity'], 'UNKNOWN')

    def test_horizontal_edge_and_threshold_are_fixed(self):
        mask, depth, rgb = fixture()
        depth[5:, :] += 29.99
        self.assertFalse(spatial_metrics(mask, depth, rgb)[1]['depth_edges'].any())
        depth[5:, :] = 1030.
        metrics, debug = spatial_metrics(mask, depth, rgb)
        expected = np.zeros(mask.shape, bool)
        expected[4:6, :] = True
        np.testing.assert_array_equal(debug['depth_edges'], expected)
        self.assertEqual(metrics['rules']['depth_edge_mm'], 30.)

    def test_empty_mask_is_unknown_and_inputs_not_mutated(self):
        data = fixture()
        data[1][:, 5:] += 50.
        data[2][:, 5:] = 255
        saved = [value.copy() for value in data]
        metrics, debug = spatial_metrics(*data)
        self.assertGreater(metrics['edge_counts']['rgb']['full_frame'], 0)
        for actual, original in zip(data, saved, strict=True):
            np.testing.assert_array_equal(actual, original)
        data[0][:] = False
        metrics, _ = spatial_metrics(*data)
        self.assertEqual(metrics['boundary_to_depth_edge']['reason'], 'EMPTY_MASK_BOUNDARY')
        self.assertIsNone(metrics['coverage']['mask']['valid_depth_fraction'])
        json.dumps(metrics, allow_nan=False)


if __name__ == '__main__':
    unittest.main()
