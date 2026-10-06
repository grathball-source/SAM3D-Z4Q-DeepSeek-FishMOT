"""Synthetic-only checks for coordinate, time, source and uncertainty contracts."""
from __future__ import annotations

import copy
import json
import unittest
from unittest.mock import patch

import cv2
import numpy as np

from flow import PairMotion, array_binding


def sensor(gray,frame=1,rgb_time=1_000_000,depth_time=None):
    h,w=gray.shape;y,x=np.indices((h,w),dtype='f4')
    z=np.full((h,w),1200.,'f4')
    # Synthetic calibrated plane: a 1px shift is 1mm at this depth.
    xyz=np.stack((x-w/2,y-h/2,z),axis=2)
    return dict(gray=gray.copy(),depth_mm=z,source_index=np.arange(h*w,dtype='i4').reshape(h,w),
        native_depth=z.copy(),xyz_mm=xyz,K=np.array([[1200.,0,w/2],[0,1200.,h/2],[0,0,1.]]),
        distortion=np.zeros(8),binding=dict(global_frame=frame,rgb_timestamp_us=rgb_time,
        depth_timestamp_us=rgb_time if depth_time is None else depth_time,delta_us=0,
        calibration_available=True,synthetic=True))


def texture(h=160,w=240):
    rng=np.random.default_rng(33)
    return cv2.GaussianBlur(rng.integers(0,256,(h,w),dtype='u1'),(3,3),0)


def controlled(a,b,forward,backward):
    # Only tests inject known fields; production always calls frozen DIS.
    with patch.object(PairMotion,'_calculate',return_value=(forward.copy(),backward.copy())):
        return PairMotion(a,b)


def translation(dx=5,dy=2,h=160,w=240):
    gray=texture(h,w);current=cv2.warpAffine(gray,np.float32([[1,0,dx],[0,1,dy]]),(w,h))
    a,b=sensor(gray),sensor(current,2,1_033_000)
    forward=np.zeros((h,w,2),'f4');forward[:]=[dx,dy]
    mask=np.zeros((h,w),bool);mask[48:96,64:128]=True
    return a,b,forward,-forward,mask


class FlowChecks(unittest.TestCase):
    def test_actual_DIS_translation_and_warp_sign(self):
        a,b,_,_,mask=translation(h=360,w=640)
        pair=PairMotion(a,b)
        np.testing.assert_allclose(np.median(pair.forward[mask],axis=0),[5,2],atol=.2)
        expected=cv2.warpAffine(mask.astype('u1'),np.float32([[1,0,5],[0,1,2]]),(640,360)).astype(bool)
        propagated=pair.warp_forward(mask)
        dice=2*np.sum(propagated&expected)/(np.sum(propagated)+np.sum(expected))
        self.assertGreater(dice,.985)
        self.assertGreater(np.mean(pair.forward_reliable[mask]),.95)
        returned=pair.warp_backward(expected)
        self.assertGreater(2*np.sum(returned&mask)/(np.sum(returned)+np.sum(mask)),.985)
        self.assertEqual(pair.numeric_summary['threads'],1)

    def test_nonrigid_local_motion_is_not_whole_mask_translation(self):
        gray=texture();h,w=gray.shape;y,x=np.indices((h,w),dtype='f4')
        shift=np.where(y<80,2.,8.).astype('f4')
        forward=np.stack((shift,np.zeros_like(shift)),axis=2);backward=-forward
        current=cv2.remap(gray,x-shift,y,cv2.INTER_NEAREST,borderMode=cv2.BORDER_CONSTANT)
        a,b=sensor(gray),sensor(current,2,1_033_000)
        mask=np.zeros((h,w),bool);mask[32:64,64:96]=True;mask[96:128,64:96]=True
        pair=controlled(a,b,forward,backward);result=pair.warp_forward(mask)
        expected=np.zeros_like(mask);expected[32:64,66:98]=True;expected[96:128,72:104]=True
        self.assertTrue(np.array_equal(result,expected))
        motion=pair.summarize_roi(mask)['point_motion']
        self.assertEqual(motion['status'],'AVAILABLE_CONDITIONAL_3D_CORRESPONDENCES')
        np.testing.assert_allclose(motion['displacement_xyz_mm']['median'],[5,0,0])
        np.testing.assert_allclose(motion['displacement_xyz_mm']['mad'],[3,0,0])
        support,summary=pair.point_support(mask)
        self.assertEqual(summary['status'],'AVAILABLE_CONDITIONAL_3D_SUPPORT')
        self.assertTrue(np.array_equal(support,expected))
        self.assertEqual(sorted(p['displacement_center_xyz_mm'][0] for p in summary['local_patches']),[2.,8.])

    def test_out_of_bounds_and_forward_backward_disagreement(self):
        a,b,f,r,mask=translation(dx=20,dy=0)
        mask[:]=False;mask[48:80,-12:]=True
        pair=controlled(a,b,f,r);summary=pair.summarize_roi(mask)
        self.assertEqual(summary['out_of_bounds_n'],int(mask.sum()))
        self.assertEqual(int(pair.warp_forward(mask).sum()),0)
        self.assertEqual(summary['point_motion']['status'],'UNKNOWN')
        a,b,f,r,mask=translation();r[:]=0
        pair=controlled(a,b,f,r)
        self.assertFalse(np.any(pair.forward_fb_reliable[mask]))
        self.assertFalse(np.any(pair.warp_forward(mask,quality=True)))

    def test_low_texture_and_photometric_inconsistency(self):
        gray=np.full((160,240),128,'u1');a=sensor(gray);b=sensor(gray,2,1_033_000)
        zero=np.zeros((*gray.shape,2),'f4');mask=np.zeros(gray.shape,bool);mask[48:80,64:96]=True
        pair=controlled(a,b,zero,zero)
        self.assertTrue(np.all(pair.forward_fb_reliable[mask]))
        self.assertFalse(np.any(pair.forward_reliable[mask]))
        self.assertEqual(pair.point_support(mask)[1]['status'],'UNKNOWN')
        gray=texture();a=sensor(gray);b=sensor(np.clip(gray.astype('i2')+80,0,255).astype('u1'),2,1_033_000)
        pair=controlled(a,b,zero,zero)
        self.assertFalse(np.any(pair.forward_reliable[mask]))

    def test_actual_target_depth_and_independent_sensor_time(self):
        a,b,f,r,mask=translation();b['binding']['depth_timestamp_us']=1_037_000;b['binding']['delta_us']=4000
        target=cv2.warpAffine(mask.astype('u1'),np.float32([[1,0,5],[0,1,2]]),(240,160)).astype(bool)
        b['depth_mm'][target]=1500;b['xyz_mm'][target,2]=1500
        pair=controlled(a,b,f,r);motion=pair.summarize_roi(mask)['point_motion']
        self.assertAlmostEqual(motion['depth_dt_s'],.037)
        self.assertAlmostEqual(motion['rgb_dt_s'],.033)
        np.testing.assert_allclose(motion['displacement_xyz_mm']['median'],[5,2,300])
        np.testing.assert_allclose(motion['velocity_xyz_mm_s']['median'],np.array([5,2,300])/.037)
        self.assertEqual(motion['physical_identity'],'UNKNOWN')

    def test_missing_depth_keeps_RGB_and_never_imputes_3D(self):
        a,b,f,r,mask=translation();b['depth_mm'][:]=0;b['source_index'][:]=-1;b['xyz_mm'][:]=np.nan
        pair=controlled(a,b,f,r)
        self.assertGreater(int(pair.warp_forward(mask,quality=True).sum()),0)
        motion=pair.summarize_roi(mask)['point_motion']
        self.assertEqual(motion['status'],'UNKNOWN')
        self.assertEqual(motion['correspondence_n'],0)
        self.assertIsNone(motion['velocity_xyz_mm_s']['median'])
        support,summary=pair.point_support(mask)
        self.assertFalse(np.any(support));self.assertEqual(summary['status'],'UNKNOWN')

    def test_wrong_reused_or_unpaired_time_cannot_make_velocity(self):
        for key,value,reason in [('depth_timestamp_us',1_000_000,'REUSED_NATIVE_DEPTH_TIMESTAMP'),
            ('depth_timestamp_us',999_999,'NONINCREASING_NATIVE_DEPTH_TIME'),
            ('depth_timestamp_us',None,'MISSING_NATIVE_DEPTH_TIME'),
            ('delta_us',5001,'RGB_DEPTH_PAIR_UNRELIABLE')]:
            with self.subTest(key=key,value=value):
                a,b,f,r,mask=translation();b['binding'][key]=value
                pair=controlled(a,b,f,r);motion=pair.summarize_roi(mask)['point_motion']
                self.assertTrue(any(reason in x for x in motion['reasons']))
                self.assertEqual(motion['status'],'UNKNOWN')
                self.assertIsNone(motion['velocity_xyz_mm_s']['median'])
                self.assertGreater(int(pair.warp_forward(mask,quality=True).sum()),0)
                self.assertFalse(np.any(pair.point_support(mask)[0]))
        a,b,f,r,mask=translation();b['binding']['rgb_timestamp_us']=1_000_000
        pair=controlled(a,b,f,r)
        self.assertEqual(pair.rgb_status,'UNKNOWN')
        self.assertFalse(np.any(pair.forward_reliable))
        self.assertFalse(np.any(pair.warp_forward(mask,quality=True)))

    def test_frame_local_source_dedup_does_not_certify_temporal_identity(self):
        a,b,f,r,mask=translation();a['source_index'][:]=0;a['xyz_mm'][:]=[0,0,1200]
        pair=controlled(a,b,f,r);motion=pair.summarize_roi(mask)['point_motion']
        self.assertEqual(motion['correspondence_n'],1)
        self.assertGreater(motion['previous_source_duplicates_removed'],100)
        self.assertEqual(motion['status'],'UNKNOWN')
        self.assertFalse(np.any(pair.point_support(mask)[0]))
        a,b,f,r,mask=translation();b['source_index'][:]=0;b['xyz_mm'][:]=[0,0,1200]
        pair=controlled(a,b,f,r);motion=pair.summarize_roi(mask)['point_motion']
        self.assertEqual(motion['correspondence_n'],1)
        self.assertGreater(motion['current_source_duplicates_removed'],100)
        # The same index integers in two different frames are not rejected or matched as IDs.
        a,b,f,r,mask=translation();pair=controlled(a,b,f,r)
        self.assertEqual(pair.summarize_roi(mask)['point_motion']['status'],'AVAILABLE_CONDITIONAL_3D_CORRESPONDENCES')

    def test_absent_calibration_is_UNKNOWN_no_guess(self):
        for key,value in [('K',None),('distortion',None),('xyz_mm',None)]:
            with self.subTest(key=key):
                a,b,f,r,mask=translation();b[key]=value;pair=controlled(a,b,f,r)
                motion=pair.summarize_roi(mask)['point_motion']
                self.assertEqual(motion['status'],'UNKNOWN')
                self.assertIsNone(motion['velocity_xyz_mm_s']['median'])
                self.assertFalse(np.any(pair.point_support(mask)[0]))
        a,b,f,r,mask=translation();b['binding']['calibration_available']=False
        self.assertEqual(controlled(a,b,f,r).point_support(mask)[1]['status'],'UNKNOWN')

    def test_local_point_outlier_rejection_and_unknown_patch(self):
        a,b,f,r,_=translation(dx=0,dy=0);mask=np.zeros_like(a['gray'],bool);mask[32:64,64:128]=True
        b['xyz_mm'][40,72,0]+=1000
        pair=controlled(a,b,f,r);support,summary=pair.point_support(mask)
        self.assertEqual(summary['status'],'AVAILABLE_CONDITIONAL_3D_SUPPORT')
        self.assertFalse(support[40,72]);self.assertEqual(summary['rejected_or_unknown_point_n'],1)
        # One incoherent patch is unknown; it cannot gain a huge scale to pass itself.
        b['xyz_mm'][32:48,64:96,0]+=100;b['xyz_mm'][48:64,64:96,0]-=100
        pair=controlled(a,b,f,r);support,summary=pair.point_support(mask)
        self.assertFalse(np.any(support[32:64,64:96]))
        self.assertEqual(summary['unknown_patch_n'],1)
        self.assertTrue(np.all(support[32:64,96:128]))
        self.assertEqual(summary['local_patches'][0]['reason'],'LOCAL_3D_MOTION_TOO_DISPERSED')

    def test_no_input_mutation_no_pixels_in_public_JSON(self):
        a,b,f,r,mask=translation();before=[{k:array_binding(v) for k,v in sensor_.items() if isinstance(v,np.ndarray)} for sensor_ in (a,b)]
        bindings=[copy.deepcopy(a['binding']),copy.deepcopy(b['binding'])]
        pair=controlled(a,b,f,r);roi=pair.summarize_roi(mask);_,support=pair.point_support(mask)
        json.dumps(dict(pair=pair.numeric_summary,roi=roi,support=support),allow_nan=False)
        after=[{k:array_binding(v) for k,v in sensor_.items() if isinstance(v,np.ndarray)} for sensor_ in (a,b)]
        self.assertEqual(before,after);self.assertEqual(bindings,[a['binding'],b['binding']])
        self.assertEqual(pair.numeric_summary['maximum_read_global_frame'],2)
        self.assertEqual(support['maximum_read_global_frame'],2)


if __name__=='__main__':
    unittest.main(verbosity=2)
