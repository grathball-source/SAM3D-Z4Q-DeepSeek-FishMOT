"""Prepare original saved masks and causal raw-only measurements, without GT."""
from common import *
import time,copy
import numpy as np
from depth_measurement import decode
from measurement import measure_raw
from source import RawDepth,original_sources,polygon_masks,feature_observations,native_masks,FIELD_READS
from features import stats,exclusive_core

def verify_raw_cache(old,current,path=''):
    """Only OpenCV max-distance's nonfunctional last bit may differ."""
    assert type(old) is type(current),(path,type(old),type(current))
    if isinstance(old,dict):
        assert old.keys()==current.keys(),path
        return sum(verify_raw_cache(old[k],current[k],path+'/'+str(k)) for k in old)
    if isinstance(old,list):
        assert len(old)==len(current),path
        return sum(verify_raw_cache(a,b,path+'/'+str(i)) for i,(a,b) in enumerate(zip(old,current,strict=True)))
    if old!=current:
        assert path.endswith('/dt_max_px') and abs(old-current)<=1e-6,(path,old,current)
        return 1
    return 0

def prepare(name):
    base=input_dir(name);assert not base.exists(),base;base.mkdir(parents=True)
    sources=original_sources(name);reader=RawDepth(name);start,stop=SEGMENTS[name]
    bindings=[];input_items={k:artifact(p) for k,p in sources.items()};began=time.perf_counter()
    old=(rows(sources['raw_measurements']) if 'raw_measurements' in sources else None)
    if name in ('L3','LW'):
        camera={r['frame']:r for r in read(sources['manifest'])['frames']}
        incoming=((None,None,None) for _ in range(stop-start+1))
    else:incoming=zip(rows(sources['observations']),rows(sources['profiles']),rows(sources['assignments']),strict=True)
    derived_names=('observations.jsonl.gz','profiles.jsonl.gz','assignments.jsonl.gz','DEPTH_OBSERVATIONS.jsonl.gz')
    handles=[gzip.open(base/n,'xt',encoding='utf-8',compresslevel=3) for n in derived_names]
    coverage=dict(frames=0,sensor_available_frames=0,objects=0,usable_cores=0,valid_pixels=0,old_raw_cache_equal_frames=0,opencv_max_distance_last_bit_differences=0)
    depth_profile_changes=0;auxiliary_rles=0
    try:
        for index,(obs,profile,assignment) in enumerate(incoming,1):
            g=start+index-1
            now=(camera[g]['rgb_timestamp_us']/1e6 if name in ('L3','LW') else obs['time'])
            depth,source_index,native,binding=reader(g,now)
            if name in ('L3','LW'):
                path=Path(sources['manifest']).parent/'labels_raw'/f'{g:06d}.json'
                saved=read(path);assert (saved['imageWidth'],saved['imageHeight'])==(1920,1080)
                masks,scores=polygon_masks(saved['shapes'])
                obs,profile,assignment=feature_observations(masks,scores,{n:None for n in masks},index,g,now,depth)
                input_items[f'prediction/{g}']=artifact(path)
            else:
                assert (obs['frame'],obs['global_frame'],obs['time'])==(index,g,now)
                assert (profile['frame'],profile['global_frame'],profile['time'])==(index,g,now)
                assert assignment['frame']==index and abs(assignment['time']-now)<1e-6
                masks=native_masks(assignment)
                auxiliary_rles+=len(assignment['masks'])-len(masks)
                assert set(masks)=={o['id'] for o in obs['observations']}
                assert obs['native']==[dict(id=x['id'],mask=x['mask']) for x in assignment['variants']['N0']]
                # Preserve all geometry, scores, presence, neighbors and native order.
                obs=copy.deepcopy(obs);profile=copy.deepcopy(profile)
                occupancy=sum((m.astype('u2') for m in masks.values()),np.zeros(depth.shape,'u2'))
                facts={o['id']:o for o in profile['observations']}
                for o in obs['observations']:
                    n=o['id'];whole=stats(depth,masks[n]);exclusive,core=exclusive_core(masks[n],occupancy)
                    cs=stats(depth,core);p=facts[n]
                    if p['whole']!=whole or p['core']!=cs:depth_profile_changes+=1
                    o['depth']={k:whole[k] for k in ('n','valid_fraction','median','mad')}
                    p.update(whole=whole,core=cs)
                assignment=dict(frame=index,global_frame_id=g,time=now,masks={x['mask']:assignment['masks'][x['mask']] for x in obs['native']},variants={'N0':obs['native']})
            occupancy=sum((m.astype('u2') for m in masks.values()),np.zeros(depth.shape,'u2'))
            full,facts=measure_raw(depth,masks,occupancy,name,index)
            if old is not None:
                previous=next(old)
                assert (previous['frame'],previous['global_frame'],previous['time'])==(index,g,now)
                assert previous['adaptive_full']==full,(name,index,'full depth statistics changed')
                coverage['opencv_max_distance_last_bit_differences']+=verify_raw_cache(previous['adaptive_raw'],{str(n):m for n,m in facts.items()})
                # Preserve all exact historical numbers; no ROI/statistical tolerance.
                facts={int(n):m for n,m in previous['adaptive_raw'].items()}
                coverage['old_raw_cache_equal_frames']+=1
            measurement=dict(segment=name,frame=index,global_frame=g,time=now,
                adaptive_full=full,adaptive_raw={str(n):m for n,m in facts.items()},raw_source_binding=binding)
            for handle,value in zip(handles,(obs,profile,assignment,measurement),strict=True):
                handle.write(json.dumps(value,separators=(',',':'),allow_nan=False)+'\n')
            binding=dict(binding,frame=index);bindings.append(binding)
            coverage['frames']+=1;coverage['objects']+=len(facts)
            coverage['sensor_available_frames']+=bool(binding['sensor_available'])
            coverage['usable_cores']+=sum(m['core_usable'] for m in facts.values());coverage['valid_pixels']+=int((depth>0).sum())
            if index%200==0:print(name,'prepare',index,'/',stop-start+1,flush=True)
        assert coverage['frames']==stop-start+1
        if old is not None:assert next(old,None) is None
    finally:
        for h in handles:h.close()
        reader.close()
    scanner=module('ds14_original_scanner',OLD/'source_scan_v4.py')
    scan=scanner.scan(base/'observations.jsonl.gz',base/'assignments.jsonl.gz',base/'scan_v4.json')
    write_new(base/'RAW_SOURCES.json',bindings)
    write_new(base/'FIELD_ACCESS.json',FIELD_READS)
    manifest=dict(status='ORIGINAL_RAW_ONLY_CAUSAL_INPUTS_PREPARED',segment=name,original_frames=[start,stop],
        frames=coverage['frames'],original_inputs=input_items,raw_sources=artifact(base/'RAW_SOURCES.json'),
        derived_inputs={n:artifact(base/n) for n in derived_names},scan=artifact(base/'scan_v4.json'),
        field_access=artifact(base/'FIELD_ACCESS.json'),coverage=coverage,raw_profile_changed_objects=depth_profile_changes,
        archived_unpublished_auxiliary_rles=auxiliary_rles,all_saved_native_masks_preserved=True,
        geometry_policy='EXACT_SAVED_SOURCE_2D_GEOMETRY_OR_RECORDED_CAMERA_PIXEL_CENTER_PROJECTION',
        old_cache_policy='ONLY_RAW_COLUMNS_ACCEPTED_AFTER_ALL_FRAME_ACTUAL_RAW_EQUALITY' if old else 'FRESH_RAW_MEASUREMENT',
        preparation_seconds=time.perf_counter()-began,new_model_http=0,cost_usd=0,no_GT=True,no_RGB=True,
        no_restored_values=True,source_time_nonoverlap_independence='NOT_CLAIMED')
    write_new(base/'SOURCE_MANIFEST.json',manifest)
    write_new(HERE/'inputs'/f'{name}.json',manifest)
    print(name,'PREPARED',coverage,flush=True)

if __name__=='__main__':prepare(sys.argv[1])
