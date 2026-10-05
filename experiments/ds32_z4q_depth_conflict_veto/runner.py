"""Unchanged observations -> own-state candidate veto -> commit -> one publication."""
from common import *
from bridge import Bridge,stream
controller=module('ds32_edge_controller',HERE/'controller.py')
DepthBridge,engine_state=controller.DepthBridge,controller.engine_state
import copy,time

def emit(row,ids):
    out=[dict(id=ids[o['id']],mask=o['mask']) for o in row['native']]
    assert len(out)==len(set(x['id'] for x in out))==len(row['native'])
    return out

def run_segment(name,output=RUN,stop_at=None,disabled=False,allow_edge=None):
    start,stop=SEGMENTS[name];base=input_dir(name);p=output/name/'public';p.mkdir(parents=True,exist_ok=True)
    if stop_at is None:
        freeze=read(p/'FREEZE.json') if output==RUN else read(p/'CF_FREEZE.json')
        if output!=RUN:
            verify_item(freeze['formal_freeze']);verify_item(freeze['selection']);verify_item(freeze['formal_prediction_seal'])
            selection=read(freeze['selection']['path']);assert selection['segment']==name
            assert freeze['allow_edge']==(list(allow_edge) if allow_edge else None)
            freeze=read(freeze['formal_freeze']['path'])
        for path,h in freeze['code'].items():assert sha(path)==h,path
        verify_frozen_inputs(freeze)
    original=Bridge(read(CONFIG_PATH));branch=DepthBridge(read(CONFIG_PATH),name,not disabled,allow_edge)
    cached=old.DS18/'run'/name/'public/MIXED_DEPTH.jsonl.gz'
    depth=module('ds32_unchanged_ds31_extract',ROOT/'experiments/ds31_persistent_identity_depth/depth.py')
    suspects={}
    for hit in read(base/'scan_v4.json')['suspects']:suspects.setdefault(hit['frame'],set()).update(hit['sources'])
    archive=iter(rows(ROOT/'experiments/ds31_persistent_identity_depth/run'/name/'public/predictions.jsonl.gz'))
    cf=allow_edge is not None or output.name.startswith('counter')
    formal=iter(rows(RUN/name/'public/predictions.jsonl.gz')) if cf else None
    handles={f:gzip.open(p/f,'xt',encoding='utf-8') for f in ('predictions.jsonl.gz','TRANSACTIONS.jsonl.gz','DEPTH_EXTRACTS.jsonl.gz')}
    ledger=(p/'PUBLISH_LEDGER.jsonl').open('x',encoding='utf-8');began=time.perf_counter();objects=0;events=[]
    counts=dict(hook_edges=0,raw_conflicts=0,redundant_conflicts=0,legal_edges_deleted=0,changed_frames=0,
        original_own_state_null_checks=0,veto_frames=0,selected_commit_changes=0)
    first=None
    def dump(file,v):handles[file].write(json.dumps(v,separators=(',',':'),allow_nan=False)+'\n');return row_sha(v)
    try:
        for f,((row,profiles),assignment,measured,packet,archived) in enumerate(zip(stream(base/'observations.jsonl.gz',base/'profiles.jsonl.gz'),
            rows(base/'assignments.jsonl.gz'),rows(base/'DEPTH_OBSERVATIONS.jsonl.gz'),rows(cached),archive,strict=True),1):
            received=time.perf_counter();assert f==row['frame']==packet['frame']==assignment['frame']==measured['frame']
            assert row['global_frame']==start+f-1==packet['global_frame']==measured['global_frame']
            assert packet['time']==row['time']==measured['time'] and packet['actual_depth_binding']==measured['raw_source_binding']['aligned_depth']
            assert packet['actual_source_index_binding']==measured['raw_source_binding']['aligned_source_index']
            assert {int(n) for n in packet['objects']}=={o['id'] for o in row['observations']}
            for c in packet['objects'].values():
                assert c['certificate_sha256']==digest({k:v for k,v in c.items() if k!='certificate_sha256'})
                assert c['frame']==f and c['global_frame']==row['global_frame'] and c['time']==row['time']
                assert c['frame_binding_sha256']==packet['frame_binding_sha256']
                assert c['core']['roi_binding']==c['core_binding'] and c['whole']['roi_binding']==c['mask_binding']
                for part in ('whole','core'):
                    assert c[part]['inclusive_statistics_sha256']==digest(c[part]['inclusive_summary'])
                    assert c[part]['source_quality_denominator']=='ORIGINAL_GEOMETRIC_ROI_AREA_INCLUDING_MISSING_SHARED_DUPLICATE_PIXELS'
            extracts={int(n):depth.extract(v) for n,v in packet['objects'].items()}
            ids,ztrace=original.commit_once(original.preview(f,row['time'],row['observations'],profiles))
            values={'SAM3_NATIVE':row['native'],'Z4Q_FROZEN':emit(row,ids)};pins={}
            pins['Z4Q_FROZEN']=dump('TRANSACTIONS.jsonl.gz',dict(arm='Z4Q_FROZEN',frame=f,global_frame=row['global_frame'],mapping=ids,
                version=original.version,controller_trace=ztrace,engine_state_sha256=digest(engine_state(original.engine)),decided_before_first_publish=True))
            view=branch.preview(row,profiles,extracts,anonymous=suspects.get(f,()))
            bids,trace=branch.commit_once(view);values['Z4Q_DEPTH_VETO']=emit(row,bids)
            checks=trace['depth_checks'];deleted=[x for x in checks if x['veto']]
            if first is None and deleted:
                first=dict(segment=name,frame=f,global_frame=row['global_frame'],edge=copy.deepcopy(deleted[0]),
                    selection='FIRST_ACTUAL_LEGAL_MATRIX_EDGE_DELETION_IN_CHRONOLOGICAL_HOOK_ORDER; NO_GT')
            counts['hook_edges']+=len(checks);counts['raw_conflicts']+=sum(x.get('conflict',False) for x in checks)
            counts['redundant_conflicts']+=sum(x.get('conflict',False) and not x['original_eligible'] for x in checks)
            counts['legal_edges_deleted']+=len(deleted);counts['veto_frames']+=bool(deleted)
            counts['original_own_state_null_checks']+=not deleted
            counts['changed_frames']+=values['Z4Q_DEPTH_VETO']!=values['Z4Q_FROZEN']
            accepted=[x for x in trace.get('events',[]) if x.get('kind')=='reconnect' and x.get('accepted')]
            before_accepted=[x for x in view['original_trace'].get('events',[]) if x.get('kind')=='reconnect' and x.get('accepted')]
            counts['selected_commit_changes']+=view['actual_commits']!=view['original_commits']
            events.extend(dict(arm='Z4Q_DEPTH_VETO',frame=f,global_frame=row['global_frame'],event=copy.deepcopy(x)) for x in accepted)
            pins['Z4Q_DEPTH_VETO']=dump('TRANSACTIONS.jsonl.gz',dict(arm='Z4Q_DEPTH_VETO',frame=f,global_frame=row['global_frame'],time=row['time'],
                mapping=bids,version=branch.version,controller_trace=trace,actual_actions=accepted,
                engine_state_sha256=digest(engine_state(branch.engine)),evidence_state_sha256=digest(branch.engine.evidence.state()),
                original_own_state_mapping=view['original_mapping'],original_own_state_trace=view['original_trace'],
                original_own_state_sha256=view['original_engine_state_sha256'],
                actual_aliases=copy.deepcopy(branch.engine.alias),bank_anchors={str(k):h.get('anchor') for k,h in branch.engine.bank.items()},
                source_row_sha256=row_sha(row),depth_packet_sha256=digest(packet),decided_before_first_publish=True,full_state_null_checked=not deleted))
            assert values['SAM3_NATIVE']==assignment['variants']['N0']==archived['variants']['SAM3_NATIVE']
            assert values['Z4Q_FROZEN']==archived['variants']['Z4Q_FROZEN']
            if disabled:
                assert values['Z4Q_DEPTH_VETO']==values['Z4Q_FROZEN']
                assert digest(engine_state(branch.engine))==digest(engine_state(original.engine))
            if formal:
                original_formal=next(formal);assert original_formal['frame']==f
                if allow_edge is None or f<allow_edge[0]:assert values['Z4Q_DEPTH_VETO']==original_formal['variants']['Z4Q_DEPTH_VETO']
            dp=dump('DEPTH_EXTRACTS.jsonl.gz',dict(frame=f,global_frame=row['global_frame'],extracts=extracts,source_packet_sha256=digest(packet),source_packet=str(cached)))
            pin=dump('predictions.jsonl.gz',dict(frame=f,global_frame=row['global_frame'],time=row['time'],variants=values))
            ledger.write(json.dumps(dict(frame=f,global_frame=row['global_frame'],prediction_row_sha256=pin,transaction_row_sha256=pins,
                depth_extract_row_sha256=dp,receive_to_first_publish_seconds=time.perf_counter()-received,model_http=0),separators=(',',':'))+'\n')
            objects+=len(row['native'])
            if f%500==0:print(name,f,'/',stop-start+1,counts,flush=True)
            if f==stop_at:break
    finally:
        for h in handles.values():h.close()
        ledger.close()
    write_new(p/'EVENTS.json',events);write_new(p/'FIRST_LEGAL_VETO.json',first or dict(status='NO_ACTUAL_CONFLICT'))
    write_new(p/'RUN_SUMMARY.json',dict(segment=name,frames=f,objects=objects,counts=counts,elapsed_seconds=time.perf_counter()-began,
        disabled=disabled,allow_edge=allow_edge,all_masks_retained=True,original_Z4Q_exact=True,model_http=0,cost_usd=0))
    if stop_at is None:
        assert f==stop-start+1
        sealed=tuple(handles)+('PUBLISH_LEDGER.jsonl','RUN_SUMMARY.json','EVENTS.json','FIRST_LEGAL_VETO.json')
        sealed+=('FREEZE.json',) if output==RUN else ('CF_FREEZE.json',)
        write_new(p/'PREDICTIONS_SEALED.json',dict(status='SEALED_AWAITING_INDEPENDENT_SCORING',segment=name,frames=f,arms=ARMS,
            artifacts_sha256={file:sha(p/file) for file in sealed},model_http=0,cost_usd=0))
    print(name,json.dumps(counts),flush=True)
