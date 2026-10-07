"""Independent own-state replays; only frozen original candidate edges can veto."""
from common import *
from bridge import Bridge, stream
from adapter import DepthBridge, engine_state, engine_read
from predictor import DEPTH
from immutable_sources import digest_state,digest_snapshot
import copy, time

def emit(row, ids):
    result=[dict(id=ids[o['id']],mask=o['mask']) for o in row['native']]
    assert len(result)==len(set(o['id'] for o in result))==len(row['native'])
    return result

def verify_packet(row, assignment, measured, packet, frame, start):
    assert frame==row['frame']==packet['frame']==assignment['frame']==measured['frame']
    assert row['global_frame']==start+frame-1==packet['global_frame']==measured['global_frame']
    assert packet['time']==row['time']==measured['time']
    assert packet['actual_depth_binding']==measured['raw_source_binding']['aligned_depth']
    assert packet['actual_source_index_binding']==measured['raw_source_binding']['aligned_source_index']
    assert {int(n) for n in packet['objects']}=={o['id'] for o in row['observations']}
    for c in packet['objects'].values():
        assert c['certificate_sha256']==digest({k:v for k,v in c.items() if k!='certificate_sha256'})
        assert (c['frame'],c['global_frame'],c['time'])==(frame,row['global_frame'],row['time'])
        assert c['frame_binding_sha256']==packet['frame_binding_sha256']
        assert c['core']['roi_binding']==c['core_binding'] and c['whole']['roi_binding']==c['mask_binding']
        for part in ('whole','core'):
            assert c[part]['inclusive_statistics_sha256']==digest(c[part]['inclusive_summary'])
            assert c[part]['source_quality_denominator']=='ORIGINAL_GEOMETRIC_ROI_AREA_INCLUDING_MISSING_SHARED_DUPLICATE_PIXELS'

def run_segment(name, output=RUN, stop_at=None, disabled=False):
    start, stop=SEGMENTS[name];base=input_dir(name);p=output/name/'public'
    p.mkdir(parents=True,exist_ok=True)
    if stop_at is None:
        frozen=read(p/'FREEZE.json')
        for path,h in frozen['code'].items():assert sha(path)==h,path
        verify_frozen_inputs(frozen)
    original=Bridge(read(CONFIG_PATH))
    branches={arm:DepthBridge(read(CONFIG_PATH),name,mode,not disabled)
        for arm,mode in zip(VETO_ARMS,('WLS','LEVEL'),strict=True)}
    cached=old.DS18/'run'/name/'public/MIXED_DEPTH.jsonl.gz'
    suspects={}
    for hit in read(base/'scan_v4.json')['suspects']:suspects.setdefault(hit['frame'],set()).update(hit['sources'])
    archive=iter(rows(OLD32.RUN/name/'public/predictions.jsonl.gz'))
    archive_tx=iter(rows(OLD32.RUN/name/'public/TRANSACTIONS.jsonl.gz'))
    handles={f:gzip.open(p/f,'xt',encoding='utf-8') for f in
        ('predictions.jsonl.gz','TRANSACTIONS.jsonl.gz','DEPTH_EXTRACTS.jsonl.gz')}
    ledger=(p/'PUBLISH_LEDGER.jsonl').open('x',encoding='utf-8')
    began=time.perf_counter();objects=0;events=[];first={};reasons={arm:{} for arm in VETO_ARMS}
    counts={arm:dict(hook_edges=0,raw_conflicts=0,redundant_conflicts=0,legal_edges_deleted=0,
        changed_frames=0,original_own_state_null_checks=0,veto_frames=0,selected_commit_changes=0) for arm in VETO_ARMS}
    def dump(file,value):
        handles[file].write(json.dumps(value,separators=(',',':'),allow_nan=False)+'\n')
        return row_sha(value)
    try:
        for f,((row,profiles),assignment,measured,packet,archived) in enumerate(zip(
            stream(base/'observations.jsonl.gz',base/'profiles.jsonl.gz'),rows(base/'assignments.jsonl.gz'),
            rows(base/'DEPTH_OBSERVATIONS.jsonl.gz'),rows(cached),archive,strict=True),1):
            received=time.perf_counter();verify_packet(row,assignment,measured,packet,f,start)
            archived_z,archived_w=next(archive_tx),next(archive_tx)
            assert (archived_z['frame'],archived_z['arm'],archived_w['frame'],archived_w['arm'])==(f,'Z4Q_FROZEN',f,'Z4Q_DEPTH_VETO')
            extracts={int(n):DEPTH.extract(c) for n,c in packet['objects'].items()}
            ids,ztrace=original.commit_once(original.preview(f,row['time'],row['observations'],profiles))
            zhash=digest(engine_read(original.engine))
            assert zhash==archived_z['engine_state_sha256']
            values={'SAM3_NATIVE':row['native'],'Z4Q_FROZEN':emit(row,ids)}
            pins={'Z4Q_FROZEN':dump('TRANSACTIONS.jsonl.gz',dict(arm='Z4Q_FROZEN',frame=f,global_frame=row['global_frame'],
                time=row['time'],mapping=ids,version=original.version,controller_trace=ztrace,
                engine_state_sha256=zhash,decided_before_first_publish=True))}
            for arm,branch in branches.items():
                view=branch.preview(row,profiles,extracts,anonymous=suspects.get(f,()))
                bids,trace=branch.commit_once(view);values[arm]=emit(row,bids)
                checks=trace['depth_checks'];deleted=[c for c in checks if c['veto']];counter=counts[arm]
                if deleted and arm not in first:
                    first[arm]=dict(segment=name,arm=arm,frame=f,global_frame=row['global_frame'],edge=copy.deepcopy(deleted[0]),
                        selection='FIRST_ACTUAL_LEGAL_MATRIX_EDGE_DELETION; NO_GT')
                counter['hook_edges']+=len(checks);counter['raw_conflicts']+=sum(c.get('conflict',False) for c in checks)
                counter['redundant_conflicts']+=sum(c.get('conflict',False) and not c['original_eligible'] for c in checks)
                counter['legal_edges_deleted']+=len(deleted);counter['veto_frames']+=bool(deleted)
                counter['original_own_state_null_checks']+=not deleted
                counter['changed_frames']+=values[arm]!=values['Z4Q_FROZEN']
                counter['selected_commit_changes']+=view['actual_commits']!=view['original_commits']
                for check in checks:
                    reasons[arm][check['reason']]=reasons[arm].get(check['reason'],0)+1
                accepted=[e for e in trace.get('events',[]) if e.get('kind')=='reconnect' and e.get('accepted')]
                events.extend(dict(arm=arm,frame=f,global_frame=row['global_frame'],event=copy.deepcopy(e)) for e in accepted)
                eh=digest(engine_read(branch.engine));state=branch.engine.evidence._read_state()
                evidence_hash=digest_state(state)
                if stop_at is not None or f%500==0:assert evidence_hash==digest(state)
                if arm=='Z4Q_WLS_VETO':
                    assert values[arm]==archived['variants']['Z4Q_DEPTH_VETO']
                    assert eh==archived_w['engine_state_sha256']
                    state.pop('predictor_mode');state.pop('predictor_config')
                    assert digest_state(state)==archived_w['evidence_state_sha256']
                pins[arm]=dump('TRANSACTIONS.jsonl.gz',dict(arm=arm,frame=f,global_frame=row['global_frame'],time=row['time'],
                    mapping=bids,version=branch.version,controller_trace=trace,actual_actions=accepted,
                    engine_state_sha256=eh,evidence_state_sha256=evidence_hash,
                    original_own_state_mapping=view['original_mapping'],original_own_state_trace=view['original_trace'],
                    original_own_state_sha256=view['original_engine_state_sha256'],
                    actual_aliases=copy.deepcopy(branch.engine.alias),bank_anchors={str(k):h.get('anchor') for k,h in branch.engine.bank.items()},
                    source_row_sha256=row_sha(row),depth_packet_sha256=digest(packet),
                    decided_before_first_publish=True,full_state_null_checked=not deleted))
                if disabled:
                    assert values[arm]==values['Z4Q_FROZEN'] and eh==zhash
            assert values['SAM3_NATIVE']==assignment['variants']['N0']==archived['variants']['SAM3_NATIVE']
            assert values['Z4Q_FROZEN']==archived['variants']['Z4Q_FROZEN']
            dp=dump('DEPTH_EXTRACTS.jsonl.gz',dict(frame=f,global_frame=row['global_frame'],extracts=extracts,
                source_packet_sha256=digest(packet),source_packet=str(cached)))
            pin=dump('predictions.jsonl.gz',dict(frame=f,global_frame=row['global_frame'],time=row['time'],variants=values))
            ledger.write(json.dumps(dict(frame=f,global_frame=row['global_frame'],prediction_row_sha256=pin,
                transaction_row_sha256=pins,depth_extract_row_sha256=dp,
                receive_to_first_publish_seconds=time.perf_counter()-received,model_http=0),separators=(',',':'))+'\n')
            objects+=len(row['native'])
            if f%500==0:print(name,f,'/',stop-start+1,counts,flush=True)
            if f==stop_at:break
    finally:
        for handle in handles.values():handle.close()
        ledger.close()
    write_new(p/'EVENTS.json',events);write_new(p/'FIRST_LEGAL_VETO.json',first)
    write_new(p/'RUN_SUMMARY.json',dict(segment=name,frames=f,objects=objects,counts=counts,reasons=reasons,
        elapsed_seconds=time.perf_counter()-began,disabled=disabled,all_masks_retained=True,
        original_Z4Q_and_DS32_WLS_full_state_exact=True,model_http=0,cost_usd=0))
    if stop_at is None:
        assert f==stop-start+1 and next(archive_tx,None) is None
        sealed=tuple(handles)+('PUBLISH_LEDGER.jsonl','RUN_SUMMARY.json','EVENTS.json','FIRST_LEGAL_VETO.json','FREEZE.json')
        write_new(p/'PREDICTIONS_SEALED.json',dict(status='SEALED_AWAITING_INDEPENDENT_SCORING',segment=name,frames=f,arms=ARMS,
            artifacts_sha256={file:sha(p/file) for file in sealed},model_http=0,cost_usd=0))
    print(name, 'FINISHED',json.dumps(counts),time.perf_counter()-began,flush=True)
