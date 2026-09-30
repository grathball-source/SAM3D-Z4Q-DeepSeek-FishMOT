"""Direct DS4 checks on synthetic geometry and exposed 701/704/766 sources."""
import json
import socket
import unittest
from pathlib import Path
from unittest.mock import patch

from bootstrap import (HERE, DS3, CONFIG, ARMS, baseline, source_depth, main_region,
                       records, decode, statistics, KERNEL, np, cv2, write_new)
from selector import measure as separated_measure
from runner import methods


def scene(contrast=180.):
    yy, xx = np.indices((180, 220))
    depth = 1200.+.4*xx+.2*yy
    region = np.zeros(depth.shape, bool); region[50:130, 60:160] = True
    fish = np.zeros(depth.shape, bool); fish[65:115, 85:135] = True
    depth[fish] -= contrast
    return depth, region, fish, np.zeros(depth.shape, bool)


def run_methods(depth, region, other=None, suspect=None):
    if other is None: other = np.zeros(depth.shape, bool)
    if suspect is None: suspect = np.zeros(depth.shape, bool)
    clean = depth.copy(); clean[suspect] = 0
    return methods(depth, clean, suspect, region, other)


def global_pixels(facts, region, shape):
    x0, y0, x1, y1 = facts['crop']
    out = np.zeros(shape, bool); out[y0:y1, x0:x1] = region
    return out


class Checks(unittest.TestCase):
    def assert_equivalent(self, a, pa, b, pb):
        self.assertEqual(a, b)
        self.assertEqual(set(pa), set(pb))
        for key in pa: np.testing.assert_array_equal(pa[key], pb[key])

    def test_background15_clone_exact_on_direct_branches(self):
        scenes = []
        for contrast in (0., 35., 180., -180.):
            depth, region, _, other = scene(contrast)
            scenes.append((depth, region, other))
        depth, region, fish, other = scene()
        depth[80, 100] = 0; depth[90, 110] = np.nan; depth[100, 120] = np.inf
        scenes.append((depth, region, other))
        depth, region, fish, other = scene(0.)
        depth[65:90, 75:100] -= 180.; depth[100:125, 120:145] += 180.
        scenes.append((depth, region, other))
        depth, region, _, other = scene(); other[50:130, 165:178] = True; depth[other] = 600.
        scenes.append((depth, region, other))
        depth, region, _, other = scene(); depth[~region] = 0.
        scenes.append((depth, region, other))
        depth, region, _, other = scene(); scenes.append((np.zeros_like(depth), region, other))
        for index, (depth, region, other) in enumerate(scenes):
            with self.subTest(scene=index):
                a, pa = baseline.measure(depth, region, other)
                b, pb = separated_measure(depth, region, other, 15.)
                self.assert_equivalent(a, pa, b, pb)

    def test_background1_recovers_coherent35_with_component_floor15(self):
        depth, region, fish, other = scene(35.)
        facts, pixels = run_methods(depth, region, other)
        self.assertEqual(facts['F2_DS3']['selector']['reason'], 'NO_SIGNIFICANT_DEPTH_CONTRAST')
        low = facts['F6_BG_NOISE']['selector']
        self.assertEqual(low['status'], 'AVAILABLE')
        self.assertEqual(low['selected_sign'], 'NEARER')
        self.assertEqual(low['plane']['contrast_threshold_mm'], 30.)
        self.assertEqual(low['plane']['residual_scale_mm'], 1.)
        self.assertEqual(low['selected']['n'], 2500)
        self.assertEqual(low['components'][0]['raw_scale_mm'], 15.)
        actual = global_pixels(low, pixels['F6_BG_NOISE']['selected'], depth.shape)
        np.testing.assert_array_equal(actual, fish)
        self.assertAlmostEqual(low['signed_contrast_median_mm'], 35., places=7)

    def test_background1_preserves_foreground_dispersion_rejection(self):
        depth, region, fish, other = scene(0.)
        depth[65:115, 85:135] = np.linspace(600., 1000., 50)[None, :]
        facts, pixels = separated_measure(depth, region, other, 1.)
        self.assertEqual(facts['reason'], 'NO_QUALIFIED_CONNECTED_COMPONENT')
        self.assertEqual(facts['significant_n'], 2500)
        self.assertGreater(facts['components'][0]['raw_scale_mm'], 60.)
        self.assertFalse(facts['components'][0]['qualified'])
        self.assertFalse(pixels['selected'].any())

    def test_dense_far_suspect_refused_and_legal_far_retained(self):
        for value, suspect_value in [(12250., True), (1300., False)]:
            depth, region, fish, other = scene(0.)
            # An unambiguous constant background isolates the admission policy.
            depth[:] = 1200.; depth[fish] = value
            suspect = fish.copy() if suspect_value else np.zeros_like(fish)
            before = depth.copy(); facts, pixels = run_methods(depth, region, other, suspect)
            self.assertEqual(facts['F2_DS3']['selector']['status'], 'AVAILABLE')
            self.assertEqual(facts['F2_DS3']['selector']['selected_sign'], 'FARTHER')
            for arm in ('F3_RANGE', 'F5_RANGE_MAIN', 'F6_BG_NOISE'):
                selected = facts[arm]['selector']
                if suspect_value:
                    self.assertEqual(selected['status'], 'UNKNOWN')
                    self.assertFalse(pixels[arm]['selected'].any())
                    self.assertEqual(facts[arm]['source_suspect_within_mask'], 2500)
                else:
                    self.assertEqual(selected['status'], 'AVAILABLE')
                    self.assertEqual(selected['selected_sign'], 'FARTHER')
                    self.assertEqual(selected['selected']['median'], 1300.)
                    self.assertEqual(selected['selected']['n'], 2500)
            np.testing.assert_array_equal(depth, before)

    def test_admission_uses_native_source_and_strict5000_boundary(self):
        class Sensor(dict):
            def __enter__(self): return self
            def __exit__(self, *args): return False
        depth = np.zeros((360, 640), 'f4'); index = np.full(depth.shape, -1, 'i4')
        native = np.zeros((576, 640), 'f4')
        for x, aligned, original in [(10, 1200., 5001.), (11, 8000., 1200.), (12, 1100., 5000.)]:
            depth[10, x] = aligned; index[10, x] = x; native.ravel()[x] = original
        sensor = Sensor(depth_mm=depth, source_index=index)
        with patch('bootstrap.np.load', side_effect=[sensor, native]), patch('bootstrap.digest', return_value='synthetic'):
            raw, clean, suspect, quality = source_depth(0)
        self.assertTrue(suspect[10, 10]); self.assertEqual(clean[10, 10], 0.)
        self.assertFalse(suspect[10, 11]); self.assertEqual(clean[10, 11], 8000.)
        self.assertFalse(suspect[10, 12]); self.assertEqual(clean[10, 12], 1100.)
        self.assertEqual(quality['native_suspect_n'], 1)
        self.assertEqual(quality['sensor_valid_range'], 'UNKNOWN')
        np.testing.assert_array_equal(raw, depth)
        self.assertEqual(native.ravel()[10], 5001.)

    def test_main_side_fragment_retains_original_mask_crop_and_annulus(self):
        depth, region, fish, other = scene(0.)
        depth[:] = 1200.; region[80:100, 180:200] = True; depth[80:100, 180:200] = 1000.
        original = region.copy(); main, geometry = main_region(region)
        self.assertTrue(geometry['main_unique']); self.assertEqual(geometry['main_area'], 8000)
        self.assertEqual(geometry['minor_area'], 400)
        facts, pixels = run_methods(depth, region, other)
        old = facts['F2_DS3']['selector']; restricted = facts['F4_MAIN']['selector']
        self.assertEqual(old['status'], 'AVAILABLE'); self.assertEqual(old['selected']['n'], 400)
        self.assertEqual(restricted['reason'], 'NO_SIGNIFICANT_DEPTH_CONTRAST')
        self.assertEqual(old['crop'], restricted['crop'])
        self.assertEqual(old['annulus'], restricted['annulus'])
        np.testing.assert_array_equal(pixels['F2_DS3']['annulus'], pixels['F4_MAIN']['annulus'])
        self.assertEqual(old['exclusive_area'], 8400); self.assertEqual(restricted['exclusive_area'], 8000)
        selected = global_pixels(old, pixels['F2_DS3']['selected'], depth.shape)
        self.assertFalse((selected & main).any())
        np.testing.assert_array_equal(region, original)

    def test_main_tie_has_no_arbitrary_winner(self):
        depth = np.full((180, 220), 1200.)
        region = np.zeros(depth.shape, bool); region[50:70, 60:80] = True; region[50:70, 140:160] = True
        depth[50:70, 60:80] = 1000.; before = region.copy()
        main, geometry = main_region(region)
        self.assertFalse(geometry['main_unique']); self.assertFalse(main.any())
        self.assertEqual(geometry['components'], 2); self.assertEqual(geometry['minor_area'], 800)
        facts, pixels = run_methods(depth, region)
        self.assertEqual(facts['F2_DS3']['selector']['status'], 'AVAILABLE')
        for arm in ('F4_MAIN', 'F5_RANGE_MAIN'):
            self.assertEqual(facts[arm]['selector']['exclusive_area'], 0)
            self.assertEqual(facts[arm]['selector']['status'], 'UNKNOWN')
            self.assertFalse(pixels[arm]['selected'].any())
            np.testing.assert_array_equal(pixels[arm]['annulus'], pixels['F2_DS3']['annulus'])
        np.testing.assert_array_equal(region, before)

    def test_holes_are_support_only_and_all_inputs_unmodified(self):
        depth, region, fish, other = scene(); suspect = np.zeros_like(region)
        depth[80, 100] = 0.; depth[90, 110] = np.nan; depth[100, 120] = np.inf
        clean = depth.copy(); originals = [a.copy() for a in (depth, clean, suspect, region, other)]
        facts, pixels = methods(depth, clean, suspect, region, other)
        for arm in ARMS:
            f = facts[arm]['selector']; x0, y0, x1, y1 = f['crop']; raw = depth[y0:y1, x0:x1]
            selected = pixels[arm]['selected']; support = pixels[arm]['support']
            self.assertEqual(f['status'], 'AVAILABLE'); self.assertEqual(f['selected']['n'], 2497)
            self.assertTrue(np.all(np.isfinite(raw[selected]) & (raw[selected] > 0)))
            for y, x in [(80, 100), (90, 110), (100, 120)]:
                self.assertFalse(selected[y-y0, x-x0]); self.assertTrue(support[y-y0, x-x0])
        for before, after in zip(originals, (depth, clean, suspect, region, other)):
            np.testing.assert_array_equal(before, after)
        again, again_pixels = methods(depth, clean, suspect, region, other)
        self.assertEqual(facts, again)
        for arm in ARMS:
            for key in pixels[arm]: np.testing.assert_array_equal(pixels[arm][key], again_pixels[arm][key])

    def real_frame(self, frame):
        name = 'feeding_000701_001060'
        measurement = private = None
        for a, b in zip(records(DS3/f'{name}_measurements.jsonl.gz'),
                        records(DS3/'private'/f'{name}_pixels.jsonl.gz'), strict=True):
            if a['frame'] == frame:
                self.assertEqual(a['frame'], b['frame']); measurement, private = a, b; break
        self.assertIsNotNone(measurement)
        depth, clean, suspect, quality = source_depth(frame)
        masks = {token: decode(obj['source_mask']) for token, obj in private['objects'].items()}
        occupancy = sum((m.astype('u2') for m in masks.values()), np.zeros(depth.shape, 'u2'))
        return measurement, private, depth, clean, suspect, quality, masks, occupancy

    def compare_real(self, frame, tokens=None):
        measurement, private, depth, clean, suspect, quality, masks, occupancy = self.real_frame(frame)
        before = [a.copy() for a in (depth, clean, suspect)]
        out = {}
        for token in tokens or masks:
            own = masks[token]; other = (occupancy-own.astype('u2')) > 0
            expected = measurement['objects'][token]; pp = private['objects'][token]
            self.assertEqual(statistics(depth, own), expected['whole'])
            core = cv2.erode((own & ~other).astype('u1'), KERNEL).astype(bool)
            self.assertEqual(statistics(depth, core), expected['core'])
            facts, pixels = methods(depth, clean, suspect, own, other)
            self.assertEqual(facts['F2_DS3']['selector'], expected['foreground'])
            for key, rle in pp['regions'].items():
                np.testing.assert_array_equal(pixels['F2_DS3'][key], decode(rle))
            clone, clone_pixels = separated_measure(depth, own, other, 15.)
            self.assert_equivalent(expected['foreground'], pixels['F2_DS3'], clone, clone_pixels)
            for arm in ARMS:
                selected = global_pixels(facts[arm]['selector'], pixels[arm]['selected'], depth.shape)
                self.assertFalse((selected & ~own).any())
                self.assertFalse((selected & other).any())
                self.assertTrue(np.all(np.isfinite(depth[selected]) & (depth[selected] > 0)))
                if ARMS[arm][0]: self.assertFalse((selected & suspect).any())
            out[token] = (facts, pixels)
        for a, b in zip(before, (depth, clean, suspect)): np.testing.assert_array_equal(a, b)
        return out, measurement, private, depth, clean, suspect

    def test_real701_all_objects_exact_and_order_independent(self):
        out, measurement, private, depth, clean, suspect = self.compare_real(701)
        masks = {t: decode(p['source_mask']) for t, p in private['objects'].items()}
        occupancy = sum((m.astype('u2') for m in masks.values()), np.zeros(depth.shape, 'u2'))
        for token in reversed(list(masks)):
            own = masks[token]
            facts, pixels = methods(depth, clean, suspect, own, (occupancy-own.astype('u2')) > 0)
            self.assertEqual(out[token][0], facts)
            for arm in ARMS:
                for key in pixels[arm]: np.testing.assert_array_equal(out[token][1][arm][key], pixels[arm][key])

    def test_real704_exact_and_main_blocks_old_side_fragment(self):
        out, measurement, _, depth, _, _ = self.compare_real(704, ['o013'])
        facts, pixels = out['o013']; old = facts['F2_DS3']['selector']
        self.assertEqual(old['selected']['n'], 20)
        self.assertEqual(measurement['objects']['o013']['core']['n'], 7)
        self.assertFalse(measurement['objects']['o013']['core_usable'])
        self.assertEqual(facts['F4_MAIN']['main_geometry']['areas_descending'], [243, 128])
        self.assertEqual(facts['F4_MAIN']['selector']['status'], 'UNKNOWN')
        self.assertFalse(pixels['F4_MAIN']['selected'].any())
        self.assertEqual(facts['F4_MAIN']['selector']['crop'], old['crop'])
        np.testing.assert_array_equal(pixels['F4_MAIN']['annulus'], pixels['F2_DS3']['annulus'])

    def test_real766_exact_and_native_admission_blocks_old57_points(self):
        out, measurement, _, depth, _, suspect = self.compare_real(766, ['o012'])
        facts, pixels = out['o012']; old = facts['F2_DS3']['selector']
        self.assertEqual(old['selected']['n'], 57)
        self.assertEqual(old['selected']['median'], 12254.619140625)
        self.assertEqual(old['selected_sign'], 'FARTHER')
        self.assertEqual(measurement['objects']['o012']['core']['n'], 66)
        self.assertTrue(measurement['objects']['o012']['core_usable'])
        selected = global_pixels(old, pixels['F2_DS3']['selected'], depth.shape)
        self.assertTrue(np.all(suspect[selected]))
        for arm in ('F3_RANGE', 'F5_RANGE_MAIN', 'F6_BG_NOISE'):
            changed = global_pixels(facts[arm]['selector'], pixels[arm]['selected'], depth.shape)
            self.assertFalse((changed & selected).any())
        self.assert_equivalent(old, pixels['F2_DS3'], facts['F4_MAIN']['selector'], pixels['F4_MAIN'])


if __name__ == '__main__':
    cv2.setNumThreads(1)
    original_open = Path.open; original_key = np.lib.npyio.NpzFile.__getitem__
    accessed_keys = []
    def guarded_open(path, *args, **kwargs):
        parts = str(path).lower().replace('\\', '/').split('/')
        assert not any(part in ('labels_640x360', 'sealed_test', 'rgb_640x360', 'v3', 'depth_restored') for part in parts), path
        return original_open(path, *args, **kwargs)
    def guarded_key(sensor, key):
        assert key in ('depth_mm', 'source_index'), key
        accessed_keys.append(key)
        return original_key(sensor, key)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Checks)
    with patch.object(Path, 'open', guarded_open), \
         patch.object(np.lib.npyio.NpzFile, '__getitem__', guarded_key), \
         patch.object(socket.socket, 'connect', side_effect=AssertionError('network forbidden')):
        result = unittest.TextTestRunner(verbosity=2).run(suite)
    write_new(HERE/'CHECKS.json', dict(tests=result.testsRun, failures=len(result.failures),
        errors=len(result.errors), passed=result.wasSuccessful(), real_frames=[701, 704, 766],
        real_cases=['F701_ALL_OBJECTS', 'F704:o013', 'F766:o012'],
        allowed_npz_keys=sorted(set(accessed_keys)),
        blocked=['network connect', 'manual/test references', 'RGB', 'v3/restored planes', 'all other NPZ keys'],
        config=CONFIG, arms={name: list(settings) for name, settings in ARMS.items()}))
    raise SystemExit(0 if result.wasSuccessful() else 1)
