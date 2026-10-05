"""Four own-state branches; current observation -> atomic commit -> publish once."""
from common import *
from bridge import Bridge,stream
from identity import Identity
import time,copy

def emit(row,ids):
    objects=[dict(id=ids[x['id']],mask=x['mask']) for x in row['native']]
    assert len(objects)==len(set(x['id'] for x in objects))==len(row['native'])
    return objects

def run_segment(name,output=RUN,stop_at=None):
    start,stop=SEGMENTS[name];base=input_dir(name);p=output/name/'public';p.mkdir(parents=True,exist_ok=True)
    if stop_at is None:
        for file,h in read(p/'FREEZE.json')['code'].items():assert sha(file)==h,file
    scan=read(base/'scan_v4.json');suspects={}
    for hit in scan['suspects']:suspects.setdefault(hit['frame'],[]).append(hit)
    native=Bridge(read(CONFIG_PATH));branches={a:Identity(a,suspects) for a in ARMS[2:]}
    cached=old.DS18/'run'/name/'public/MIXED_DEPTH.jsonl.gz'
    handles={f:gzip.open(p/f,'xt',encoding='utf-8') for f in ('predictions.jsonl.gz','TRANSACTIONS.jsonl.gz','DEPTH_EXTRACTS.jsonl.gz')}
    ledger=(p/'PUBLISH_LEDGER.jsonl').open('x',encoding='utf-8');began=time.perf_counter();counts={a:dict(commits=0,changed_frames=0,depth_rows=0,depth_changed_choice=0) for a in ARMS[2:]}
    object_count=0;archive=iter(rows(ROOT/'experiments/ds30_original_z4q_depth_increment/run'/name/'public/predictions.jsonl.gz'))
    def dump(file,value):handles[file].write(json.dumps(value,separators=(',',':'),allow_nan=False)+'\n');return row_sha(value)
    try:
        for f,((row,profiles),assignment,measured,packet,archived) in enumerate(zip(stream(base/'observations.jsonl.gz',base/'profiles.jsonl.gz'),
            rows(base/'assignments.jsonl.gz'),rows(base/'DEPTH_OBSERVATIONS.jsonl.gz'),rows(cached),archive,strict=True),1):
            t=time.perf_counter();assert f==row['frame']==packet['frame']==assignment['frame']==measured['frame']
            assert row['global_frame']==start+f-1==packet['global_frame']==measured['global_frame']
            assert packet['time']==row['time']==measured['time'] and packet['actual_depth_binding']==measured['raw_source_binding']['aligned_depth']
            assert packet['actual_source_index_binding']==measured['raw_source_binding']['aligned_source_index']
            assert {int(n) for n in packet['objects']}=={o['id'] for o in row['observations']}
            packet['full_frame']=measured['adaptive_full']
            for n,c in packet['objects'].items():
                assert c['certificate_sha256']==digest({k:v for k,v in c.items() if k!='certificate_sha256'})
                assert c['frame']==f and c['global_frame']==row['global_frame'] and c['time']==row['time']
                assert c['frame_binding_sha256']==packet['frame_binding_sha256']
                assert c['core']['roi_binding']==c['core_binding'] and c['whole']['roi_binding']==c['mask_binding']
                for part in ('whole','core'):
                    assert c[part]['inclusive_statistics_sha256']==digest(c[part]['inclusive_summary'])
                    assert c[part]['source_quality_denominator']=='ORIGINAL_GEOMETRIC_ROI_AREA_INCLUDING_MISSING_SHARED_DUPLICATE_PIXELS'
            view=native.preview(f,row['time'],row['observations'],profiles);ids,ztrace=native.commit_once(view)
            results={'SAM3_NATIVE':row['native'],'Z4Q_FROZEN':emit(row,ids)};txpins={}
            txpins['Z4Q_FROZEN']=dump('TRANSACTIONS.jsonl.gz',dict(arm='Z4Q_FROZEN',frame=f,global_frame=row['global_frame'],time=row['time'],
                version=native.version,mapping=ids,controller_trace=ztrace,actual_actions=[x for x in ztrace.get('events',[]) if x.get('accepted')],decided_before_first_publish=True))
            extracts=None
            for arm,b in branches.items():
                prior=digest(b.state());view=b.preview(row,profiles,assignment,packet);assert prior==digest(b.state()),'preview mutated prior state'
                ids,trace=b.commit(view);results[arm]=emit(row,ids)
                for action in trace['actions']:assert ids[action['source']]==action['target']
                extracts=trace.pop('measurements')
                txpins[arm]=dump('TRANSACTIONS.jsonl.gz',dict(arm=arm,frame=f,global_frame=row['global_frame'],time=row['time'],version=b.version,
                    mapping=ids,state_sha256=digest(b.state()),controller_trace=trace,source_row_sha256=row_sha(row),depth_packet_sha256=digest(packet),
                    decided_before_first_publish=True,actual_actions=trace['actions']))
                counts[arm]['commits']+=len(trace['actions']);counts[arm]['changed_frames']+=results[arm]!=results['Z4Q_FROZEN']
                counts[arm]['depth_rows']+=sum(bool(d.get('active')) for d in trace['depth_rows'])
                counts[arm]['depth_changed_choice']+=sum(a['target']!=a['geometry_selected_target'] and bool(a['depth_row'].get('active')) for a in trace['actions'])
            assert results['SAM3_NATIVE']==assignment['variants']['N0']==archived['variants']['SAM3_NATIVE']
            assert results['Z4Q_FROZEN']==archived['variants']['Z4Q_FROZEN']
            dp=dump('DEPTH_EXTRACTS.jsonl.gz',dict(frame=f,global_frame=row['global_frame'],extracts=extracts,
                source_packet_sha256=digest(packet),source_packet= str(cached),full_frame=measured['adaptive_full']))
            pin=dump('predictions.jsonl.gz',dict(frame=f,global_frame=row['global_frame'],time=row['time'],variants=results))
            ledger.write(json.dumps(dict(frame=f,global_frame=row['global_frame'],prediction_row_sha256=pin,transaction_row_sha256=txpins,
                depth_extract_row_sha256=dp,receive_to_first_publish_seconds=time.perf_counter()-t,model_http=0),separators=(',',':'))+'\n')
            object_count+=len(row['native'])
            if f%500==0:print(name,f,'/',stop-start+1,flush=True)
            if f==stop_at:break
    finally:
        for h in handles.values():h.close()
        ledger.close()
    write_new(p/'EVENTS.json',{a:b.events for a,b in branches.items()})
    write_new(p/'RUN_SUMMARY.json',dict(segment=name,frames=f,objects=object_count,counts=counts,elapsed_seconds=time.perf_counter()-began,
        all_masks_retained=True,original_Z4Q_exact=True,zero_RGB_GT_restored_future_network=True,model_http=0,cost_usd=0))
    if stop_at is None:
        assert f==stop-start+1
        sealed=tuple(handles)+('FREEZE.json','PUBLISH_LEDGER.jsonl','RUN_SUMMARY.json','EVENTS.json')
        write_new(p/'PREDICTIONS_SEALED.json',dict(status='SEALED_AWAITING_INDEPENDENT_SCORING',frames=f,arms=ARMS,
            artifacts_sha256={file:sha(p/file) for file in sealed},new_model_http=0,cost_usd=0))
    print(name,json.dumps(counts),flush=True)
