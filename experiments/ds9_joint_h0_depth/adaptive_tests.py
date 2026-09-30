"""Fixed-formula geometry checks, no labels, depth selection or model service."""
from __future__ import annotations

import os
import unittest

os.environ.update(CUDA_VISIBLE_DEVICES='', OMP_NUM_THREADS='1',
                  OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
import cv2
import numpy as np
cv2.setNumThreads(1)
from adaptive_core import adaptive_core


def occupancy(masks):
    return sum((x.astype('u4') for x in masks.values()),
               np.zeros(next(iter(masks.values())).shape, dtype='u4'))


class AdaptiveCoreTests(unittest.TestCase):
    def test_thin_diagonal_retains_samples_when_square7_loses_them(self):
        mask = np.zeros((64,64),np.uint8)
        cv2.line(mask,(8,8),(55,55),1,thickness=5)
        mask = mask.astype(bool)
        fixed = cv2.erode(mask.astype('u1'),np.ones((7,7),np.uint8)).astype(bool)
        roi,meta = adaptive_core(mask,mask.astype('u2'))
        self.assertLess(int(fixed.sum()),16)
        self.assertGreaterEqual(int(roi.sum()),16)
        self.assertEqual(meta['component_count'],1)
        self.assertGreater(meta['pieces'][0]['dt_max_px'],3.)
        self.assertLess(meta['pieces'][0]['threshold_px'],3.)
        self.assertTrue(np.all(~roi | mask))

    def test_wide_mask_caps_threshold_at_three(self):
        mask = np.zeros((64,64),bool)
        mask[16:48,16:48] = True
        roi,meta = adaptive_core(mask,mask.astype('u2'))
        piece = meta['pieces'][0]
        self.assertEqual(piece['dt_max_px'],16.)
        self.assertEqual(piece['threshold_px'],3.)
        self.assertEqual(piece['samples'],28*28)
        self.assertEqual(int(roi.sum()),28*28)

    def test_overlap_is_excluded_before_connectivity_and_distance(self):
        a,b = np.zeros((48,64),bool),np.zeros((48,64),bool)
        a[8:40,4:40] = True
        b[2:46,20:32] = True
        occ = occupancy({1:a,2:b})
        roi,meta = adaptive_core(a,occ)
        self.assertFalse(np.any(roi & b))
        self.assertEqual(meta['component_count'],2)
        self.assertEqual(meta['exclusive_area'],int((a & ~b).sum()))
        self.assertEqual(meta['roi_area'],sum(p['samples'] for p in meta['pieces']))

    def test_all_disconnected_components_remain_truthful(self):
        mask = np.zeros((64,80),bool)
        mask[5:25,5:25] = True
        mask[35:40,50:65] = True
        mask[55,70] = True
        roi,meta = adaptive_core(mask,mask.astype('u2'))
        self.assertEqual(meta['component_count'],3)
        self.assertEqual([p['area'] for p in meta['pieces']],[400,75,1])
        self.assertGreater(int(roi[35:40,50:65].sum()),0)
        self.assertEqual(meta['pieces'][-1]['samples'],0)
        self.assertFalse(roi[55,70])
        self.assertEqual(sum(p['area'] for p in meta['pieces']),int(mask.sum()))
        self.assertEqual(sum(p['samples'] for p in meta['pieces']),int(roi.sum()))
        self.assertTrue(np.all(~roi | mask))

    def test_connectivity_is_eight_and_holes_are_not_filled(self):
        mask = np.zeros((48,48),bool)
        mask[5:20,5:20] = True
        mask[20:35,20:35] = True  # Only diagonal contact.
        mask[9:13,9:13] = False
        roi,meta = adaptive_core(mask,mask.astype('u2'))
        self.assertEqual(meta['component_count'],1)
        self.assertFalse(np.any(roi[9:13,9:13]))
        self.assertTrue(np.all(~roi | mask))

    def test_empty_and_too_thin_do_not_fabricate_samples(self):
        empty = np.zeros((32,32),bool)
        roi,meta = adaptive_core(empty,np.zeros_like(empty,'u2'))
        self.assertFalse(np.any(roi))
        self.assertEqual(meta['pieces'],[])
        thin = empty.copy()
        thin[15,3:29] = True
        roi,meta = adaptive_core(thin,thin.astype('u2'))
        self.assertEqual(meta['pieces'],[dict(component_id=1,area=26,
            dt_max_px=1.,threshold_px=1.5,samples=0)])
        self.assertFalse(np.any(roi))

    def test_image_exterior_zero_padding_has_finite_distance(self):
        mask = np.ones((9,9),bool)
        roi,meta = adaptive_core(mask,mask.astype('u2'))
        self.assertEqual(meta['pieces'][0]['dt_max_px'],5.)
        self.assertEqual(meta['pieces'][0]['threshold_px'],2.5)
        self.assertEqual(int(roi.sum()),25)
        self.assertTrue(np.isfinite(meta['pieces'][0]['dt_max_px']))

    def test_source_mask_and_occupancy_are_not_mutated(self):
        mask = np.zeros((32,48),bool)
        mask[4:28,5:43] = True
        occ = mask.astype('u2')
        before_mask,before_occ = mask.copy(),occ.copy()
        mask.setflags(write=False)
        occ.setflags(write=False)
        roi,_ = adaptive_core(mask,occ)
        np.testing.assert_array_equal(mask,before_mask)
        np.testing.assert_array_equal(occ,before_occ)
        self.assertEqual(roi.dtype,np.dtype(bool))
        self.assertFalse(np.shares_memory(roi,mask))
        self.assertFalse(np.shares_memory(roi,occ))

    def test_mask_input_order_has_no_effect(self):
        masks = {}
        for native,left in ((2,4),(7,20),(4,38)):
            region = np.zeros((48,64),bool)
            region[8:40,left:left+20] = True
            masks[native] = region
        reversed_masks = dict(reversed(list(masks.items())))
        original_occ,reordered_occ = occupancy(masks),occupancy(reversed_masks)
        np.testing.assert_array_equal(original_occ,reordered_occ)
        for native,region in masks.items():
            a,am = adaptive_core(region,original_occ)
            b,bm = adaptive_core(reversed_masks[native],reordered_occ)
            np.testing.assert_array_equal(a,b)
            self.assertEqual(am,bm)

    def test_processing_after_q_masks_cannot_change_current_roi(self):
        current = np.zeros((32,48),bool)
        current[4:28,10:20] = True
        current_occ = current.astype('u2')
        original,meta = adaptive_core(current,current_occ)
        for shape in ((15,27),(100,100),(9,9)):
            future = np.ones(shape,bool)
            adaptive_core(future,future.astype('u2'))
        again,again_meta = adaptive_core(current,current_occ)
        np.testing.assert_array_equal(original,again)
        self.assertEqual(meta,again_meta)


if __name__ == '__main__':
    unittest.main()
