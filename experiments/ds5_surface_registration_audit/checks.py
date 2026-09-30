"""Known correspondence and depth-discontinuity checks, no research GT."""
import unittest
from types import SimpleNamespace
from audit import np, depth_pieces, shift_counts, jumps, projection_shadow, calibration_geometry, HERE, write_new


class Checks(unittest.TestCase):
    def test_two_layers_and_no_invented_hole_points(self):
        d=np.full((5,8),800.,'f4'); d[:,4:]=1100
        s=np.ones(d.shape,bool)
        for gap in (30,60):
            out=depth_pieces(d,s,gap)
            self.assertEqual(out['qualified_pieces'],2)
            self.assertEqual([p['n'] for p in out['pieces']],[20,20])
            self.assertIsNone(out['largest_median_mm'])
        s[:,3:5]=False; self.assertEqual(depth_pieces(d,s,60)['n'],30)

    def test_known_translation_recovers_correspondence_no_wrap(self):
        s=np.zeros((10,15),bool); s[2:6,3:7]=True
        fish=np.zeros_like(s); fish[4:8,6:10]=True
        self.assertEqual(shift_counts(s,fish,fish,3,2)['fish'],16)
        out=shift_counts(s,fish,fish,-9,0)
        self.assertEqual(out['out_of_view'],16); self.assertEqual(out['n'],16)

    def test_continuous_gradient_remains_connected(self):
        d=np.tile(np.arange(12,dtype='f4')*5+800,(4,1)); s=np.ones(d.shape,bool)
        self.assertEqual(len(depth_pieces(d,s,30)['pieces']),1)

    def test_missing_is_not_edge_or_measurement(self):
        d=np.array([[800.,0,1100.]],'f4'); i=np.array([[0,-1,1]],'i4'); native=np.array([800.,1100.],'f4')
        self.assertFalse(jumps(d,i,native).any())
        out=depth_pieces(d,np.zeros_like(d,bool),60)
        self.assertEqual(out['n'],0); self.assertIsNone(out['largest_median_mm'])

    def test_native_suspect_not_normal_boundary(self):
        d=np.array([[800.,12000.]],'f4'); i=np.array([[0,1]],'i4')
        self.assertFalse(jumps(d,i,d.ravel()).any())

    def test_equal_mapping_and_proper_rotation_shadow_identity(self):
        geom,nearest,structure=calibration_geometry()
        self.assertGreater(structure['max_orthogonality_error'],1e-3)
        self.assertTrue(np.allclose(nearest.T@nearest,np.eye(3)))
        self.assertAlmostEqual(float(np.linalg.det(nearest)),1.)
        selected=np.zeros((360,640),bool)
        self.assertEqual(projection_shadow(geom,nearest,None,None,None,selected)['n'],0)

    def test_shadow_identity_preserves_original_samples(self):
        geom=SimpleNamespace(r=np.eye(3),t=np.zeros(3),rays=np.array([[[0.,0,1],[1.,0,1]]]),
                             project_xyz=lambda p:p[:,:2]/p[:,2,None])
        d=np.array([[800.,1100.]],'f4'); i=np.array([[0,1]],'i4'); s=np.ones(d.shape,bool)
        original=d.copy(); out=projection_shadow(geom,np.eye(3),i,d,d,s)
        self.assertEqual(out['shadow_displacement_px']['max'],0)
        self.assertEqual(out['shadow_z_delta_mm']['max'],0)
        self.assertTrue(np.array_equal(d,original))

    def test_ambiguous_repeat_is_not_resolved_by_shift(self):
        s=np.zeros((12,25),bool); s[4:8,10:14]=True
        fish=np.zeros_like(s); fish[4:8,4:8]=True; fish[4:8,16:20]=True
        left=shift_counts(s,fish,fish,-6,0); right=shift_counts(s,fish,fish,6,0)
        self.assertEqual(left,right)


if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Checks)
    out=unittest.TextTestRunner(verbosity=2).run(suite)
    write_new(HERE/'CHECKS.json',dict(passed=out.wasSuccessful(),tests=out.testsRun,
        failures=len(out.failures),errors=len(out.errors),model_http=0,real_measurements_changed=False))
    raise SystemExit(not out.wasSuccessful())
