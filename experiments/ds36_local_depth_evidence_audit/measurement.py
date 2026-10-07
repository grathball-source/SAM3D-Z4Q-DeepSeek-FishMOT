"""Spatial distribution diagnostics. All mask populations remain anonymous proxies."""
from common import *
import math
import numpy as np
import cv2
cv2.setNumThreads(1)

def summary(values, area):
    return MEASUREMENT._summary(np.asarray(values,dtype='f8'), int(area))

def compare(a, b):
    """Exact tied rank AUC of mask populations; never fish identification accuracy."""
    a,b = np.asarray(a,dtype='f8'),np.asarray(b,dtype='f8')
    if not len(a) or not len(b):
        return dict(status='UNKNOWN_MISSING_POPULATION',auc_nearer_a=None,separation_auc=None,
                    median_gap_mm=None,standardized_gap=None)
    ordered=np.sort(b)
    auc=float(np.mean((len(b)-np.searchsorted(ordered,a,side='right')+
                      .5*(np.searchsorted(ordered,a,side='right')-np.searchsorted(ordered,a,side='left')))/len(b)))
    aa,bb=summary(a,len(a)),summary(b,len(b))
    gap=aa['median']-bb['median'];scale=math.hypot(aa['scale_mm'],bb['scale_mm'])
    return dict(status='MEASURED_PROXY_POPULATION_COMPARISON',auc_nearer_a=auc,
                separation_auc=max(auc,1-auc),signed_median_gap_mm=gap,median_gap_mm=abs(gap),
                standardized_gap=abs(gap)/scale,combined_scale_mm=scale,
                interpretation='MASK_PROXY_DISTRIBUTION_NOT_PHYSICAL_IDENTITY_ACCURACY')

def measure(depth,index,native_depth,masks,native,segment,frame,global_frame,time,binding,expected):
    valid=MEASUREMENT.validate_source(depth,index,native_depth,masks,segment,frame,global_frame,time,binding,expected)
    own=masks[native];others=np.zeros(own.shape,bool)
    for n,m in masks.items():
        if n!=native:others|=m
    occupancy=sum((m.astype('u2') for m in masks.values()),np.zeros(own.shape,'u2'))
    core,_=MEASUREMENT._old.adaptive_core(own,occupancy)
    other_sources=np.unique(index[others&valid])
    own_sources=np.unique(index[own&valid])
    annulus=(MEASUREMENT._dilate(own,20)&~MEASUREMENT._dilate(own,5)&~MEASUREMENT._dilate(others,3))
    bg_pos,bg_ex=MEASUREMENT._selected(annulus,valid,index,np.union1d(own_sources,other_sources))
    background=depth.ravel()[bg_pos]
    populations={};rois={'whole':own,'core':core}
    # PCA is computed from geometry alone. Three equal-coordinate bins retain every
    # point; bins are not head/tail labels and no depth peak chooses their locations.
    yy,xx=np.nonzero(core)
    axis=None;origin=None;boundaries=[]
    if len(xx)>=2:
        xy=np.column_stack((xx,yy)).astype('f8');origin=xy.mean(0)
        _,_,vectors=np.linalg.svd(xy-origin,full_matrices=False);axis=vectors[0]
        if axis[np.argmax(np.abs(axis))]<0:axis=-axis
        coordinate=(xy-origin)@axis
        boundaries=np.linspace(float(coordinate.min()),float(coordinate.max()),4)
        ids=np.minimum(2,np.searchsorted(boundaries[1:-1],coordinate,side='right'))
        for part in range(3):
            roi=np.zeros(own.shape,bool);roi[yy[ids==part],xx[ids==part]]=True
            rois[f'patch{part+1}']=roi
    else:
        for part in range(3):rois[f'patch{part+1}']=np.zeros(own.shape,bool)
    views={};binding_fn=MEASUREMENT._binding
    for role,roi in rois.items():
        pos,ex=MEASUREMENT._selected(roi,valid,index,other_sources)
        values=depth.ravel()[pos];stats=summary(values,int(roi.sum()))
        eligible=bool(stats['n']>=CFG['minimum_n'] and stats['valid_fraction']>=CFG['minimum_fraction']
                      and stats['scale_mm'] is not None and stats['scale_mm']<=CFG['maximum_measured_scale_mm'])
        views[role]=dict(summary=stats,measurement_support=eligible,source_exclusions=ex,
                        roi_binding=MEASUREMENT.array_binding(roi),population_binding=binding_fn(pos,index,depth),
                        background_comparison=compare(values,background),physical_surface_identity='UNKNOWN')
        populations[role]=values
    local,unused=MEASUREMENT.measure_local_background(depth,index,native_depth,masks,native,segment,frame,
        global_frame,time,source_binding=binding,expected_source_binding=expected)
    neighbors=[]
    wide=MEASUREMENT._dilate(own,CFG['neighbor_radius_px'])
    for n,m in sorted(masks.items()):
        if n!=native and (wide&m).any():neighbors.append(n)
    result=dict(segment=segment,frame=frame,global_frame=global_frame,time=time,native=native,
                fact_id=f'{segment}/F{frame}/n:{native}/ds36-local',source_binding=binding,
                mask_binding=MEASUREMENT.array_binding(own),views=views,neighbor_natives=neighbors,
                pca_axis=None if axis is None else axis.tolist(),pca_origin=None if origin is None else origin.tolist(),
                pca_boundaries=boundaries.tolist() if len(boundaries) else [],
                background=dict(summary=summary(background,int(annulus.sum())),source_exclusions=bg_ex,
                    roi_binding=MEASUREMENT.array_binding(annulus),population_binding=binding_fn(bg_pos,index,depth)),
                local_background=local,all_depth_layers_retained=True,identity='UNKNOWN',state_write=False)
    return result,dict(populations=populations,background=background,rois=rois,background_roi=annulus)

def validate_history(samples,query_time):
    result=DEPTH.forecast(samples,query_time)
    return result

def components(prediction,samples):
    """Recompute the frozen WLS variance equation, not a new fitted scale."""
    if prediction['status']!='WLS_LINEAR_TIME':return dict(status='NO_WLS_DECOMPOSITION')
    last=samples[-10:];times=np.array([s['time'] for s in last]);sigma=np.maximum(15.,1.4826*np.array([s['mad_mm'] for s in last]))
    x=np.column_stack((np.ones(len(times)),times-times[-1]));delta=prediction['delta_seconds']
    inverse=np.linalg.solve((x/sigma[:,None]).T@(x/sigma[:,None]),np.eye(2));h=np.array([1.,delta])
    param=float(prediction['gamma']*h@inverse@h)
    drift=float(225*(1+(delta/prediction['time_scale_seconds'])**2))
    assert math.isclose(param+drift,prediction['scale_mm']**2,rel_tol=1e-10,abs_tol=1e-6)
    return dict(status='FROZEN_WLS_VARIANCE_RECONSTRUCTED',parameter_variance_mm2=param,
                drift_floor_variance_mm2=drift,total_variance_mm2=param+drift,
                parameter_fraction=param/(param+drift),drift_floor_fraction=drift/(param+drift),
                covariance_proxy=prediction['covariance_proxy'],fit_span_seconds=float(times[-1]-times[0]),
                slope_standard_error_proxy_mm_s=math.sqrt(prediction['gamma']*inverse[1,1]),
                physical_calibration='UNKNOWN')
