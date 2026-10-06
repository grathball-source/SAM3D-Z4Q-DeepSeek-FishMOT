"""Dense nonrigid RGB correspondence and actual aligned-depth point motion.

All image/flow/XYZ arrays stay private. Optical-flow correspondence is an
uncertain observation proxy, not certification that two pixels are one fish.
"""
from __future__ import annotations

import hashlib
import math
import time

import cv2
import numpy as np


FLOW_DEFAULTS = dict(fb_max_px=1.5, texture_min_std=2., texture_window_px=5,
    photometric_max_gray=25., min_correspondences=16,
    min_correspondence_fraction=.2, depth_edge_jump_mm=60., point_patch_px=32,
    point_min_patch_points=16, point_scale_floor_mm=15., point_scale_cap_mm=60.,
    point_residual_sigma=3., point_mad_sigma=1.4826)
DIS_EXPECTED = dict(FinestScale=1, PatchSize=8, PatchStride=3,
    GradientDescentIterations=25, VariationalRefinementIterations=5,
    VariationalRefinementAlpha=20., VariationalRefinementDelta=5.,
    VariationalRefinementGamma=10., UseMeanNormalization=True,
    UseSpatialPropagation=True)


def array_binding(value):
    a=np.ascontiguousarray(value)
    return dict(shape=list(a.shape),dtype=str(a.dtype),
        sha256=hashlib.sha256(a.tobytes()).hexdigest())


def _finite_number(value):
    return isinstance(value,(int,float,np.number)) and math.isfinite(float(value))


def _range(values):
    values=np.asarray(values,dtype='f8');values=values[np.isfinite(values)]
    return dict(n=int(values.size),median=float(np.median(values)) if values.size else None,
        mad=float(np.median(np.abs(values-np.median(values)))) if values.size else None,
        q90=float(np.quantile(values,.9)) if values.size else None,
        maximum=float(np.max(values)) if values.size else None)


def _vector_summary(values):
    values=np.asarray(values,dtype='f8')
    if not len(values):return dict(n=0,median=None,mad=None,norm=_range([]))
    center=np.median(values,axis=0)
    return dict(n=len(values),median=center.tolist(),mad=np.median(np.abs(values-center),axis=0).tolist(),
        norm=_range(np.linalg.norm(values,axis=1)))


def _timestamp(binding,key):
    value=binding.get(key)
    return float(value) if _finite_number(value) else None


def _std(gray,window):
    x=gray.astype('f4')
    mean=cv2.boxFilter(x,-1,(window,window),normalize=True,borderType=cv2.BORDER_REFLECT)
    square=cv2.boxFilter(x*x,-1,(window,window),normalize=True,borderType=cv2.BORDER_REFLECT)
    return np.sqrt(np.maximum(0.,square-mean*mean))


class PairMotion:
    def __init__(self,previous,current,config=None):
        supplied=(config or {}).get('flow',config or {})
        self.config={k:supplied.get(k,v) for k,v in FLOW_DEFAULTS.items()}
        assert self.config['fb_max_px']==1.5 and self.config['texture_window_px']==5
        assert all(_finite_number(v) and float(v)>=0 for v in self.config.values())
        assert self.config['point_patch_px']==32 and self.config['point_min_patch_points']==16
        assert 0<self.config['point_scale_floor_mm']<=self.config['point_scale_cap_mm']
        self.previous,self.current=previous,current
        a,b=np.asarray(previous['gray']),np.asarray(current['gray'])
        assert a.dtype==b.dtype==np.dtype('u1') and a.ndim==b.ndim==2 and a.shape==b.shape
        self.shape=a.shape;self.yy,self.xx=np.indices(a.shape,dtype='f4')
        self.rgb_status,self.rgb_reason='AVAILABLE','BIDIRECTIONAL_PIXEL_CORRESPONDENCE'
        pb,cb=previous['binding'],current['binding']
        pr,cr=_timestamp(pb,'rgb_timestamp_us'),_timestamp(cb,'rgb_timestamp_us')
        self.rgb_dt_s=None if pr is None or cr is None else (cr-pr)/1e6
        pf,cf=pb.get('global_frame'),cb.get('global_frame')
        if self.rgb_dt_s is None or self.rgb_dt_s<=0:
            self.rgb_status,self.rgb_reason='UNKNOWN','MISSING_OR_NONINCREASING_RGB_TIME'
        elif not isinstance(pf,int) or not isinstance(cf,int) or cf<=pf:
            self.rgb_status,self.rgb_reason='UNKNOWN','MISSING_OR_NONINCREASING_FRAME_ORDER'
        cv2.setNumThreads(1)
        model=cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)
        self.dis_parameters={k:getattr(model,'get'+k)() for k in DIS_EXPECTED}
        assert self.dis_parameters==DIS_EXPECTED,'OpenCV DIS defaults changed from the frozen observed runtime'
        began=time.perf_counter()
        if self.rgb_status=='AVAILABLE':
            self.forward,self.backward=self._calculate(model,a,b)
        else:
            self.forward=np.zeros((*a.shape,2),'f4');self.backward=self.forward.copy()
        self.flow_seconds=time.perf_counter()-began
        assert self.forward.shape==self.backward.shape==(*a.shape,2)
        fs,bs=_std(a,5),_std(b,5)
        self.forward_diagnostics=self._diagnostics(self.forward,self.backward,a,b,fs,bs)
        self.backward_diagnostics=self._diagnostics(self.backward,self.forward,b,a,bs,fs)
        self.forward_fb_reliable=self.forward_diagnostics['fb_reliable']
        self.backward_fb_reliable=self.backward_diagnostics['fb_reliable']
        self.forward_reliable=self.forward_diagnostics['reliable']
        self.backward_reliable=self.backward_diagnostics['reliable']
        self.depth_dt_s,self.depth_unknown_reasons=self._depth_contract()
        self.numeric_summary=dict(schema='DS33_BIDIRECTIONAL_RGB_AND_RAW_DEPTH_CORRESPONDENCE_V1',
            rgb_status=self.rgb_status,rgb_reason=self.rgb_reason,method='OPENCV_DIS_MEDIUM',
            cv2_version=cv2.__version__,threads=cv2.getNumThreads(),actual_DIS_parameters=self.dis_parameters,
            actual_quality_parameters=dict(self.config),previous_frame=pf,current_frame=cf,
            maximum_read_global_frame=max(pf,cf) if isinstance(pf,int) and isinstance(cf,int) else None,
            previous_rgb_timestamp_us=pr,current_rgb_timestamp_us=cr,rgb_dt_s=self.rgb_dt_s,
            previous_depth_timestamp_us=_timestamp(pb,'depth_timestamp_us'),
            current_depth_timestamp_us=_timestamp(cb,'depth_timestamp_us'),depth_dt_s=self.depth_dt_s,
            depth_status='UNKNOWN' if self.depth_unknown_reasons else 'AVAILABLE_RAW_SENSOR_PAIR',
            depth_unknown_reasons=list(self.depth_unknown_reasons),
            flow_forward=array_binding(self.forward),flow_backward=array_binding(self.backward),
            forward_reliable=array_binding(self.forward_reliable),backward_reliable=array_binding(self.backward_reliable),
            previous_gray=array_binding(a),current_gray=array_binding(b),
            previous_source_binding=pb,current_source_binding=cb,
            flow_seconds=self.flow_seconds,
            forward_quality=self._quality_summary(self.forward_diagnostics),
            backward_quality=self._quality_summary(self.backward_diagnostics),
            native_source_index_semantics='FRAME_LOCAL_DEDUPLICATION_ONLY_NOT_TEMPORAL_POINT_ID',
            physical_surface_identity='UNKNOWN',physical_flow_accuracy='UNKNOWN',
            no_depth_completion=True,no_ID_or_bank_write=True,no_mean_depth_subtraction_as_flow=True)

    @staticmethod
    def _calculate(model,a,b):
        return model.calc(a,b,None),model.calc(b,a,None)

    def _diagnostics(self,direct,reverse,source,target,source_std,target_std):
        qx=self.xx+direct[:,:,0];qy=self.yy+direct[:,:,1]
        finite=np.isfinite(direct).all(axis=2)&np.isfinite(qx)&np.isfinite(qy)
        inside=finite&(qx>=0)&(qx<=self.shape[1]-1)&(qy>=0)&(qy<=self.shape[0]-1)
        safe_x=np.where(finite,qx,-1).astype('f4');safe_y=np.where(finite,qy,-1).astype('f4')
        opposite=cv2.remap(reverse,safe_x,safe_y,cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT)
        error=np.linalg.norm(direct+opposite,axis=2)
        fb=inside&np.isfinite(opposite).all(axis=2)&(error<=self.config['fb_max_px'])
        sampled=cv2.remap(target,safe_x,safe_y,cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT)
        target_texture=cv2.remap(target_std,safe_x,safe_y,cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT)
        texture=(source_std>=self.config['texture_min_std'])&(target_texture>=self.config['texture_min_std'])
        photo=np.abs(source.astype('f4')-sampled.astype('f4'))
        photometric=photo<=self.config['photometric_max_gray']
        reliable=fb&texture&photometric
        if self.rgb_status!='AVAILABLE':fb[:]=False;reliable[:]=False
        return dict(inside=inside,fb_error_px=error,fb_reliable=fb,
            texture_reliable=texture,photometric_residual_gray=photo,
            photometric_reliable=photometric,reliable=reliable)

    @staticmethod
    def _quality_summary(d):
        return dict(pixels=int(d['inside'].size),out_of_bounds=int((~d['inside']).sum()),
            fb_reliable_n=int(d['fb_reliable'].sum()),low_texture_n=int((~d['texture_reliable']).sum()),
            photometric_failed_n=int((~d['photometric_reliable']).sum()),reliable_n=int(d['reliable'].sum()),
            fb_error_px=_range(d['fb_error_px'][d['inside']]))

    def _mask(self,mask):
        mask=np.asarray(mask);assert mask.shape==self.shape and mask.dtype==np.dtype(bool)
        return mask

    def warp_forward(self,mask,quality=False):
        """Previous mask on current coordinates: use current->previous pull."""
        mask=self._mask(mask)
        result=cv2.remap(mask.astype('u1'),self.xx+self.backward[:,:,0],self.yy+self.backward[:,:,1],
            cv2.INTER_NEAREST,borderMode=cv2.BORDER_CONSTANT).astype(bool)
        return result&self.backward_reliable if quality else result

    def warp_backward(self,mask,quality=False):
        """Current mask on previous coordinates: use previous->current pull."""
        mask=self._mask(mask)
        result=cv2.remap(mask.astype('u1'),self.xx+self.forward[:,:,0],self.yy+self.forward[:,:,1],
            cv2.INTER_NEAREST,borderMode=cv2.BORDER_CONSTANT).astype(bool)
        return result&self.forward_reliable if quality else result

    def _depth_contract(self):
        reasons=[];pd,cd=(_timestamp(x['binding'],'depth_timestamp_us') for x in (self.previous,self.current))
        dt=None if pd is None or cd is None else (cd-pd)/1e6
        if self.rgb_status!='AVAILABLE':reasons.append('RGB_TIME_OR_SOURCE_ORDER_UNKNOWN')
        if dt is None:reasons.append('MISSING_NATIVE_DEPTH_TIME')
        elif dt==0:reasons.append('REUSED_NATIVE_DEPTH_TIMESTAMP_NO_OBSERVED_VELOCITY')
        elif dt<0:reasons.append('NONINCREASING_NATIVE_DEPTH_TIME')
        for role,sensor in (('PREVIOUS',self.previous),('CURRENT',self.current)):
            binding=sensor['binding'];delta=binding.get('delta_us')
            if not _finite_number(delta) or abs(delta)>5000:reasons.append(role+'_RGB_DEPTH_PAIR_UNRELIABLE')
            k=sensor.get('K');dist=sensor.get('distortion');xyz=sensor.get('xyz_mm')
            valid_k=(k is not None and np.asarray(k).shape==(3,3) and np.isfinite(k).all() and
                np.asarray(k)[0,0]>0 and np.asarray(k)[1,1]>0 and np.allclose(np.asarray(k)[2],[0,0,1]))
            if not binding.get('calibration_available') or not valid_k or dist is None or np.asarray(dist).size!=8 or not np.isfinite(dist).all():
                reasons.append(role+'_CALIBRATION_UNKNOWN_NO_GUESSED_INTRINSICS')
            if xyz is None or np.asarray(xyz).shape!=(*self.shape,3):reasons.append(role+'_ACTUAL_XYZ_UNAVAILABLE')
            for key in ('depth_mm','source_index'):
                if sensor.get(key) is None or np.asarray(sensor[key]).shape!=self.shape:
                    reasons.append(role+'_'+key.upper()+'_UNAVAILABLE')
        return dt,reasons

    def _depth_points(self,mask):
        """Private actual point pairs; sensor IDs deduplicate separately per frame."""
        positions=np.flatnonzero(mask&self.forward_reliable)
        qx=np.rint((self.xx+self.forward[:,:,0]).ravel()[positions]).astype('i8')
        qy=np.rint((self.yy+self.forward[:,:,1]).ravel()[positions]).astype('i8')
        target_positions=qy*self.shape[1]+qx
        a,b=self.previous,self.current
        sa=np.asarray(a['source_index']).ravel()[positions]
        sb=np.asarray(b['source_index']).ravel()[target_positions]
        xa=np.asarray(a['xyz_mm']).reshape(-1,3)[positions]
        xb=np.asarray(b['xyz_mm']).reshape(-1,3)[target_positions]
        za=np.asarray(a['depth_mm']).ravel()[positions];zb=np.asarray(b['depth_mm']).ravel()[target_positions]
        valid=(sa>=0)&(sb>=0)&np.isfinite(xa).all(axis=1)&np.isfinite(xb).all(axis=1)&(za>0)&(zb>0)
        assert np.array_equal(xa[valid,2].astype('f4'),za[valid].astype('f4'))
        assert np.array_equal(xb[valid,2].astype('f4'),zb[valid].astype('f4'))
        original_candidates=len(positions);positions,target_positions,sa,sb,xa,xb=(x[valid] for x in (positions,target_positions,sa,sb,xa,xb))
        error=self.forward_diagnostics['fb_error_px'].ravel()[positions]
        order=np.lexsort((positions,error))
        # Duplicate projection pixels cannot multiply one sensor sample's evidence.
        _,first=np.unique(sa[order],return_index=True);source_order=order[np.sort(first)]
        _,second=np.unique(sb[source_order],return_index=True);keep=source_order[np.sort(second)]
        selected_source,selected_target=positions[keep],target_positions[keep]
        motion=xb[keep].astype('f8')-xa[keep].astype('f8')
        return dict(source_positions=selected_source,target_positions=selected_target,
            source_indices=sa[keep],target_indices=sb[keep],motion=motion,error=error[keep],
            rgb_reliable_candidates=original_candidates,missing_depth_candidates=original_candidates-int(valid.sum()),
            previous_source_duplicates_removed=len(order)-len(source_order),
            current_source_duplicates_removed=len(source_order)-len(keep))

    def _point_motion(self,mask):
        result=dict(status='UNKNOWN',reasons=list(self.depth_unknown_reasons),
            rgb_dt_s=self.rgb_dt_s,depth_dt_s=self.depth_dt_s,original_roi_area=int(mask.sum()),
            correspondence_n=0,correspondence_fraction_of_original_roi=0.,
            displacement_xyz_mm=_vector_summary(np.empty((0,3))),
            velocity_xyz_mm_s=_vector_summary(np.empty((0,3))),
            source_indices_are_frame_local=True,physical_identity='UNKNOWN',physical_accuracy_mm='UNKNOWN',
            depth_edge_risk_is_not_a_verified_occlusion=True,no_background_foreground_certificate=True)
        if self.depth_unknown_reasons:return result
        points=self._depth_points(mask)
        selected_source,selected_target,motion,error=(points[k] for k in
            ('source_positions','target_positions','motion','error'))
        sa,sb=points['source_indices'],points['target_indices']
        n=len(motion)
        coverage=n/max(1,int(mask.sum()))
        enough=n>=self.config['min_correspondences'] and coverage>=self.config['min_correspondence_fraction']
        depth=np.asarray(self.current['depth_mm']);available=np.isfinite(depth)&(depth>0)
        maximum=cv2.dilate(np.where(available,depth,0).astype('f4'),np.ones((3,3),'u1'))
        minimum=cv2.erode(np.where(available,depth,1e12).astype('f4'),np.ones((3,3),'u1'))
        edge=available&((maximum-minimum)>self.config['depth_edge_jump_mm'])
        result.update(status='AVAILABLE_CONDITIONAL_3D_CORRESPONDENCES' if enough else 'UNKNOWN',
            reasons=[] if enough else ['INSUFFICIENT_INDEPENDENT_POINT_COVERAGE'],
            correspondence_n=n,correspondence_fraction_of_original_roi=coverage,
            **{k:points[k] for k in ('rgb_reliable_candidates','missing_depth_candidates',
                'previous_source_duplicates_removed','current_source_duplicates_removed')},
            previous_unique_source_n=int(np.unique(sa).size),current_unique_source_n=int(np.unique(sb).size),
            source_pixel_binding=array_binding(selected_source),target_pixel_binding=array_binding(selected_target),
            previous_frame_local_source_binding=array_binding(sa),current_frame_local_source_binding=array_binding(sb),
            displacement_xyz_mm=_vector_summary(motion),
            velocity_xyz_mm_s=_vector_summary(motion/self.depth_dt_s),
            displacement_binding=array_binding(motion),velocity_binding=array_binding(motion/self.depth_dt_s),
            fb_error_px=_range(error),
            photometric_residual_gray=_range(self.forward_diagnostics['photometric_residual_gray'].ravel()[selected_source]),
            target_depth_edge_risk_n=int(edge.ravel()[selected_target].sum()),
            invalid_RGB_correspondence_is_not_hidden_fish_reconstruction=True)
        return result

    def point_support(self,mask):
        """Sparse current pixels with conditional local 3D-motion consistency.

        The 32px patch and robust displacement center are frozen engineering
        approximations; they neither certify identity nor reconstruct occlusion.
        """
        mask=self._mask(mask);support=np.zeros(self.shape,bool)
        summary=dict(schema='DS33_LOCAL_RGBD_POINT_SUPPORT_V1',status='UNKNOWN',
            reasons=list(self.depth_unknown_reasons),maximum_read_global_frame=self.numeric_summary['maximum_read_global_frame'],
            original_roi_area=int(mask.sum()),independent_correspondence_n=0,support_n=0,support_fraction=0.,
            local_patches=[],actual_parameters={k:v for k,v in self.config.items() if k.startswith('point_')},
            source_indices_are_frame_local=True,physical_identity='UNKNOWN',physical_accuracy_mm='UNKNOWN',
            local_consistency_is_engineering_hypothesis=True,nonrigid_motion_is_local_not_whole_fish_translation=True,
            no_mask_inpainting=True,no_foreground_expansion=True,no_verified_occlusion=True,
            identity_endpoint_quality_requires_separate_DS18_contract=True)
        if self.depth_unknown_reasons:
            summary['support_binding']=array_binding(support);return support,summary
        points=self._depth_points(mask)
        positions,target,motion=(points[k] for k in ('source_positions','target_positions','motion'))
        size=int(self.config['point_patch_px']);width=self.shape[1]
        patch_x=(positions%width)//size;patch_y=(positions//width)//size
        groups=patch_y*math.ceil(width/size)+patch_x
        keep=np.zeros(len(positions),bool)
        for group in np.unique(groups):
            chosen=np.flatnonzero(groups==group);vectors=motion[chosen]
            center=np.median(vectors,axis=0);residual=np.linalg.norm(vectors-center,axis=1)
            raw_scale=self.config['point_mad_sigma']*float(np.median(residual))
            scale=max(self.config['point_scale_floor_mm'],raw_scale)
            enough=len(chosen)>=self.config['point_min_patch_points']
            consistent=scale<=self.config['point_scale_cap_mm']
            accepted=residual<=self.config['point_residual_sigma']*scale if enough and consistent else np.zeros(len(chosen),bool)
            keep[chosen[accepted]]=True
            summary['local_patches'].append(dict(patch_xy=[int(patch_x[chosen[0]]),int(patch_y[chosen[0]])],
                status='AVAILABLE_CONDITIONAL_LOCAL_SUPPORT' if enough and consistent else 'UNKNOWN',
                reason='LOCAL_3D_MOTION_CONSISTENCY' if enough and consistent else
                    'INSUFFICIENT_INDEPENDENT_PATCH_POINTS' if not enough else 'LOCAL_3D_MOTION_TOO_DISPERSED',
                independent_point_n=len(chosen),accepted_n=int(accepted.sum()),rejected_n=int((~accepted).sum()),
                displacement_center_xyz_mm=center.tolist(),displacement_vector_mad_mm=np.median(np.abs(vectors-center),axis=0).tolist(),
                residual_norm_mm=_range(residual),raw_robust_scale_mm=raw_scale,effective_scale_mm=scale))
        support.ravel()[target[keep]]=True
        n=int(support.sum());fraction=n/max(1,int(mask.sum()))
        enough=n>=self.config['min_correspondences'] and fraction>=self.config['min_correspondence_fraction']
        summary.update(status='AVAILABLE_CONDITIONAL_3D_SUPPORT' if enough else 'UNKNOWN',
            reasons=[] if enough else ['INSUFFICIENT_LOCAL_SUPPORT_COVERAGE'],
            independent_correspondence_n=len(positions),support_n=n,support_fraction=fraction,
            unknown_patch_n=sum(p['status']=='UNKNOWN' for p in summary['local_patches']),
            rejected_or_unknown_point_n=int((~keep).sum()),
            **{k:points[k] for k in ('rgb_reliable_candidates','missing_depth_candidates',
                'previous_source_duplicates_removed','current_source_duplicates_removed')},
            source_point_binding=array_binding(positions[keep]),current_point_binding=array_binding(target[keep]),
            support_binding=array_binding(support))
        return support,summary

    def summarize_roi(self,mask):
        mask=self._mask(mask);plain=self.warp_forward(mask);trusted=self.warp_forward(mask,quality=True)
        d=self.forward_diagnostics;area=int(mask.sum());n=int((mask&self.forward_reliable).sum())
        return dict(schema='DS33_DENSE_ROI_PROPAGATION_AND_POINT_MOTION_V1',
            roi_binding=array_binding(mask),predicted_roi_binding=array_binding(plain),
            reliable_predicted_roi_binding=array_binding(trusted),original_roi_area=area,
            predicted_roi_area=int(plain.sum()),reliable_predicted_roi_area=int(trusted.sum()),
            source_reliable_n=n,source_reliable_fraction=n/max(1,area),
            target_prediction_reliable_fraction=int(trusted.sum())/max(1,int(plain.sum())),
            out_of_bounds_n=int((mask&~d['inside']).sum()),
            fb_rejected_n=int((mask&d['inside']&~d['fb_reliable']).sum()),
            low_texture_n=int((mask&~d['texture_reliable']).sum()),
            photometric_rejected_n=int((mask&~d['photometric_reliable']).sum()),
            fb_error_px=_range(d['fb_error_px'][mask&d['inside']]),
            point_motion=self._point_motion(mask),physical_identity='UNKNOWN',
            propagated_mask_is_hypothesis_not_new_observation=True,
            observed_depth_quality_and_identity_endpoint_certificate='SEPARATE_CALLER_DS18_CONTRACT_REQUIRED')

    correspondence_summary=summarize_roi
