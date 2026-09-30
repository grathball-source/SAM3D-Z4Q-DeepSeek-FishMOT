"""Direct algorithm and real-source checks, with forbidden I/O blocked."""
import json
import socket
import unittest
from pathlib import Path
from unittest.mock import patch

from common import HERE, OLD, CFG, records, load_depth, extract_frame, np, write_new
from foreground import measure


def scene():
    yy, xx = np.indices((180,220))
    depth = 1200.+.4*xx+.2*yy
    region = np.zeros(depth.shape, bool)
    region[50:130,60:160] = True
    fish = np.zeros(depth.shape, bool)
    fish[65:115,85:135] = True
    depth[fish] -= 180.
    return depth, region, fish, np.zeros(depth.shape, bool)


class Checks(unittest.TestCase):
    def test_tilted_background_and_missing_holes(self):
        depth, region, fish, other = scene()
        depth[75:80,95:100] = 0
        facts, pixels = measure(depth, region, other)
        self.assertEqual(facts['status'], 'AVAILABLE')
        selected = pixels['selected']; x0,y0,x1,y1 = facts['crop']
        expected = fish[y0:y1,x0:x1] & (depth[y0:y1,x0:x1]>0)
        np.testing.assert_array_equal(selected, expected)
        self.assertEqual(facts['selected']['n'], 2475)
        self.assertTrue(np.all(depth[y0:y1,x0:x1][selected]>0))
        self.assertLess(abs(facts['signed_contrast_median_mm']-180), 1e-6)

    def test_no_contrast(self):
        depth,region,fish,other = scene(); depth[fish] += 180
        self.assertEqual(measure(depth,region,other)[0]['reason'], 'NO_SIGNIFICANT_DEPTH_CONTRAST')

    def test_all_missing_and_sparse_background(self):
        depth,region,fish,other = scene()
        self.assertEqual(measure(np.zeros_like(depth),region,other)[0]['status'], 'UNKNOWN')
        depth[~region] = 0
        self.assertEqual(measure(depth,region,other)[0]['reason'], 'INSUFFICIENT_BACKGROUND_SAMPLES')

    def test_comparable_components_same_and_opposite_sign(self):
        for sign in [-1,1]:
            depth,region,fish,other = scene(); depth[fish] += 180
            depth[65:90,75:100] -= 180; depth[100:125,120:145] += sign*180
            self.assertEqual(measure(depth,region,other)[0]['reason'], 'AMBIGUOUS_MULTIPLE_DEPTH_COMPONENTS')

    def test_isolated_extreme_noise_not_preferred(self):
        depth,region,fish,other = scene(); depth[55,65] = 1
        facts,pixels = measure(depth,region,other)
        x0,y0,x1,y1 = facts['crop']
        self.assertEqual(facts['status'], 'AVAILABLE')
        self.assertFalse(pixels['selected'][55-y0,65-x0])

    def test_neighbor_excluded_from_ring(self):
        depth,region,fish,other = scene(); other[50:130,165:178] = True
        depth[other] = 600
        facts,pixels = measure(depth,region,other); x0,y0,x1,y1 = facts['crop']
        self.assertFalse(np.any(pixels['annulus'] & other[y0:y1,x0:x1]))
        self.assertEqual(facts['status'], 'AVAILABLE')

    def test_single_sample_unknown(self):
        depth,region,fish,other = scene(); depth[fish] += 180; depth[85,105] -= 180
        self.assertEqual(measure(depth,region,other)[0]['reason'], 'NO_QUALIFIED_CONNECTED_COMPONENT')

    def test_current_only_no_identity_and_no_mutation(self):
        depth,region,fish,other = scene()
        original=[a.copy() for a in (depth,region,other)]
        a,pa=measure(depth,region,other)
        future=np.zeros_like(depth); future[:]=9999
        b,pb=measure(depth,region,other)
        self.assertEqual(a,b)
        for key in pa: np.testing.assert_array_equal(pa[key],pb[key])
        for before,after in zip(original,(depth,region,other)): np.testing.assert_array_equal(before,after)

    def test_crop_translation_consistency(self):
        depth,region,fish,other = scene(); a,pa=measure(depth,region,other)
        shifted=[np.pad(x,((9,0),(13,0))) for x in (depth,region,other)]
        b,pb=measure(*shifted)
        self.assertEqual(a['selected'],b['selected'])
        np.testing.assert_array_equal(pa['selected'],pb['selected'])

    def test_real_source_and_reordered_objects(self):
        private=OLD/'private/feeding_000701_001060'
        assignment=next(records(private/'assignments.jsonl.gz'))
        profile=next(records(private/'profiles.jsonl.gz'))
        source=json.loads((private/'sources.json').read_text())[0]
        original_open=Path.open
        original_key=np.lib.npyio.NpzFile.__getitem__
        def guarded_open(path,*args,**kwargs):
            self.assertNotIn('labels_640x360',str(path)); self.assertNotIn('sealed_test',str(path))
            return original_open(path,*args,**kwargs)
        def guarded_key(sensor,key):
            self.assertEqual(key,'depth_mm')
            return original_key(sensor,key)
        with patch.object(Path,'open',guarded_open), patch.object(np.lib.npyio.NpzFile,'__getitem__',guarded_key), \
             patch.object(socket.socket,'connect',side_effect=AssertionError('network forbidden')):
            depth=load_depth(source['depth_path'])
            _,old,masks,occ=extract_frame(depth,assignment,{r['id']:r for r in profile['observations']})
            first={n:measure(depth,m,(occ-m.astype('u2'))>0)[0] for n,m in masks.items()}
            second={n:measure(depth,m,(occ-m.astype('u2'))>0)[0] for n,m in reversed(list(masks.items()))}
        self.assertEqual(first,second)
        self.assertEqual(len(old),source['native_count'])
        self.assertTrue(all(x['status'] in ('AVAILABLE','UNKNOWN') for x in first.values()))


if __name__ == '__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Checks)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    write_new(HERE/'CHECKS.json',dict(tests=result.testsRun,failures=len(result.failures),
        errors=len(result.errors),passed=result.wasSuccessful(),real_frame=701,
        blocked=['network connect','manual/test references','NPZ keys other than depth_mm'],
        constants=CFG))
    raise SystemExit(0 if result.wasSuccessful() else 1)
