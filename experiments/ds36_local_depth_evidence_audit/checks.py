from common import *
from measurement import measure,compare,components
import copy
import numpy as np

def binding(depth,index,native):
    return dict(global_frame=0,time=10.,actual_fields_read=['depth_mm','source_index'],
        native_fields_read=['current_native_depth_mm'],aligned_depth=MEASUREMENT.array_binding(depth),
        aligned_source_index=MEASUREMENT.array_binding(index),native_depth=MEASUREMENT.array_binding(native),
        RGB_read=False,GT_read=False,restored_read=False)

def main():
    passed=[]
    assert compare([1,1],[1,1])['auc_nearer_a']==.5
    assert compare([1,2],[3,4])['auc_nearer_a']==1
    assert compare([], [1])['status']=='UNKNOWN_MISSING_POPULATION';passed.append('TIED_RANK_AND_MISSING')
    depth=np.full((64,96),1000.,'f4');index=np.arange(depth.size,dtype='i4').reshape(depth.shape)
    a=np.zeros(depth.shape,bool);a[22:36,16:42]=True
    b=np.zeros(depth.shape,bool);b[22:36,53:79]=True
    depth[a]=535.;depth[b]=700.;native=depth.copy();masks={1:a,2:b}
    raw=binding(depth,index,native)
    value,pop=measure(depth,index,native,masks,1,'synthetic',1,0,10.,raw,raw)
    assert value['views']['core']['summary']['median']==535.
    assert np.array_equal(sum((pop['rois'][f'patch{i}'].astype(int) for i in range(1,4))),pop['rois']['core'])
    assert value['views']['whole']['summary']['n']==a.sum();passed.append('CORE_PATCH_PARTITION_WITHOUT_PEAK_SELECTION')
    d=depth.copy();d[~a]=1200.;ix=index.copy();nat=d.copy();bb=binding(d,ix,nat)
    value2,_=measure(d,ix,nat,masks,1,'synthetic',1,0,10.,bb,bb)
    assert value2['views']['core']['summary']==value['views']['core']['summary'];passed.append('OUTSIDE_MASK_DOES_NOT_ENTER_CORE')
    ix=index.copy();pa=np.flatnonzero(a)[0];pb=np.flatnonzero(b)[0];ix.ravel()[pb]=ix.ravel()[pa]
    bb=binding(depth,ix,native);v,_=measure(depth,ix,native,masks,1,'synthetic',1,0,10.,bb,bb)
    assert v['views']['whole']['source_exclusions']['shared_source_pixels_excluded']>=1
    assert v['views']['whole']['summary']['n']==int(a.sum())-1;passed.append('SHARED_NATIVE_SOURCE_EXCLUDED')
    d=np.zeros_like(depth);ix=np.full_like(index,-1);bb=binding(d,ix,d)
    v,_=measure(d,ix,d,masks,1,'synthetic',1,0,10.,bb,bb)
    assert not v['views']['core']['measurement_support'] and v['views']['core']['summary']['median'] is None
    passed.append('MISSING_DEPTH_REMAINS_UNKNOWN')
    try:measure(depth,index,native,masks,1,'synthetic',1,0,10.,raw,dict(raw,time=9.))
    except AssertionError:passed.append('SELF_CONSISTENT_UNTRUSTED_SOURCE_REJECTED')
    else:raise AssertionError('Source substitution accepted')
    samples=[dict(frame=i+1,time=10.+i*.033,z_mm=600.+i,mad_mm=2.,version=[1,1,1,1],fact_id=f'f{i}') for i in range(10)]
    pred=DEPTH.forecast(samples,11.);c=components(pred,samples)
    assert c['total_variance_mm2']>0 and pred['sample_fact_ids']==[s['fact_id'] for s in samples]
    passed.append('REAL_WLS_VARIANCE_EQUATION_AND_CITATIONS')
    for name,change in [('VERSION_BREAK',lambda s:s[4].update(version=[1,2,1,1])),
                        ('FRAME_GAP',lambda s:s[4].update(frame=99)),
                        ('UNUSABLE_POINT',lambda s:s[4].update(usable=False))]:
        bad=copy.deepcopy(samples);change(bad);assert not DEPTH.forecast(bad,11.)['usable'];passed.append(name)
    assert not DEPTH.forecast(samples,10.1)['usable'];passed.append('FUTURE_HISTORY_REJECTED')
    # One actual saved endpoint, source -> exact N0 mask -> core/source-index binding.
    req=read(HERE/'COHORT.json')['requests'][0];name=req['segment'];frame=req['frame'];n=req['native']
    assignment=next(r for r in rows(input_dir(name)/'assignments.jsonl.gz') if r['frame']==frame)
    recorded=next(r for r in rows(DS35/'run'/name/'public/FRAME_INPUTS_BINDINGS.jsonl.gz') if r['frame']==frame)
    sensor=SOURCE.RawDepth(name)
    try:
        d,ix,nat,actual=sensor(recorded['global_frame'],recorded['time'])
        assert actual==recorded['raw_source_binding'] and line_hash(assignment)==recorded['assignment_row_sha256']
        v,_=measure(d,ix,nat,SOURCE.native_masks(assignment),n,name,frame,recorded['global_frame'],recorded['time'],actual,recorded['raw_source_binding'])
        assert v['views']['core']['roi_binding']==recorded['DS18_extracts'][str(n)]['roi_binding']
        assert v['views']['core']['population_binding']['selected_source_index_binding']==recorded['DS18_extracts'][str(n)]['selected_source_index_binding']
    finally:sensor.close()
    passed.append('REAL_SOURCE_MASK_CORE_POPULATION_SLICE')
    save('CHECKS.json',dict(status='PASS',checks=passed,real_slice=req,code=[artifact(__file__),artifact(HERE/'measurement.py')],
        physical_label_content_read=False,RGB=False,GT=False,model_http=0,cost_usd=0))
    print('CHECKS PASS',len(passed),flush=True)

if __name__=='__main__':main()
