"""Original own Z4Q always runs; depth proposals atomically replace only unissued suffixes."""
from common import *
import copy, time
from collections import OrderedDict
from bridge import Bridge, stream
from observer import EvidenceBridge, EventManager, History, LagBuffer, state_hash, branch_state
from transaction import DepthBridge
from association import choose, DEPTH
from pycocotools import mask as coco
from verify_inputs import verify_frozen_inputs

def emit(row, mapping):
    assert set(mapping) == {o['id'] for o in row['native']}
    result = [dict(id=mapping[o['id']], mask=o['mask']) for o in row['native']]
    assert len(result) == len(set(o['id'] for o in result)) == len(row['native'])
    return result

def txn(row, mapping, trace, branch, selection='ORIGINAL_OWN_Z4Q', unchanged=None):
    return dict(frame=row['frame'], global_frame=row['global_frame'], time=row['time'], mapping=copy.deepcopy(mapping),
        version=branch.version, controller_trace=copy.deepcopy(trace), actual_actions=[copy.deepcopy(a) for a in
            trace.get('events',[]) if a.get('kind')=='reconnect' and a.get('accepted')],
        engine_state_sha256=digest(vars(branch.engine)), full_state_sha256=state_hash(branch),
        canonical_state_sha256=digest(branch_state(branch)), original_own_preview_state_sha256=unchanged,
        state_selection=selection, actual_aliases=copy.deepcopy(branch.engine.alias), actual_epochs=copy.deepcopy(branch.epochs),
        actual_provenance=copy.deepcopy(branch.provenance),
        bank_anchors={str(k):copy.deepcopy(h.get('anchor')) for k,h in branch.engine.bank.items()},
        source_row_sha256=row_sha(row), decided_before_first_publish=True, already_published_history_rewritten=False)

def runtime(row,mapping,trace,branch,selection='ORIGINAL_OWN_Z4Q',unchanged=None):
    result=copy.deepcopy(row);result.update(mapping=copy.deepcopy(mapping),trace=copy.deepcopy(trace),
        transaction=txn(row,mapping,trace,branch,selection,unchanged));return result

def public_episode(episode):
    result=copy.deepcopy(episode)
    result['temporary_id_records']=[dict(native=k[0],generation=k[1],public=v) for k,v in result.pop('temporary_ids',{}).items()]
    return result

def decode(packet):
    packet['masks']={o['id']:coco.decode(dict(size=packet['assignment']['masks'][o['mask']]['size'],
        counts=packet['assignment']['masks'][o['mask']]['counts'].encode('ascii'))).astype(bool) for o in packet['row']['native']}

def run_segment(name,output=RUN,stop_at=None,disabled=False):
    start,stop=SEGMENTS[name];limit=stop-start+1 if stop_at is None else stop_at
    base=input_dir(name);public=output/name/'public';public.mkdir(parents=True,exist_ok=True)
    if stop_at is None:verify_frozen_inputs(read(public/'FREEZE.json'))
    else:write_new(public/'PREFIX_FREEZE.json',dict(segment=name,frames=limit,disabled=disabled,base=BASE,
        code={str(p):sha(p) for p in HERE.glob('*.py')},configuration=artifact(HERE/'CONFIG.json'),
        source=artifact(base/'SOURCE_MANIFEST.json'),model_http=0,GT=False))
    suspects=[] if disabled else read(base/'scan_v4.json')['suspects']
    assignments={};packets=OrderedDict();original=Bridge(read(CONFIG_PATH));branches={}
    for arm in EVENT_ARMS:
        branch=DepthBridge(read(CONFIG_PATH));shadow=EvidenceBridge(read(CONFIG_PATH));shadow.sync(branch)
        manager=EventManager(arm,shadow,suspects,CFG,assignments)
        branches[arm]=dict(bridge=branch,shadow=shadow,manager=manager,history=History(name),lag=LagBuffer(branch),
            pre_packets={},q_checkpoint=None,history_checkpoint=None,stages=0,changed_frames=0,
            observer_state_checks=0,no_transaction_state_checks=0,original_state_parity_frames=0)
    files=('predictions.jsonl.gz','TRANSACTIONS.jsonl.gz','FRAME_INPUTS_BINDINGS.jsonl.gz')
    handles={f:gzip.open(public/f,'xt',encoding='utf-8',newline='\n') for f in files}
    ledger=(public/'PUBLISH_LEDGER.jsonl').open('x',encoding='utf-8',newline='\n')
    cached=DS18/'run'/name/'public/MIXED_DEPTH.jsonl.gz'
    archive=PRIOR/'run'/name/'public/predictions.jsonl.gz'
    began=time.perf_counter();published=objects=0
    def dump(file,value):
        line=json.dumps(value,separators=(',',':'),allow_nan=False,default=lambda x:sorted(x) if isinstance(x,set) else x.tolist())+'\n'
        handles[file].write(line);return hashlib.sha256(line.encode()).hexdigest()
    def refs(p):
        return {n:dict(frame=p['row']['frame'],time=p['row']['time'],fact_id=v.get('fact_id'),
            certificate_sha256=v.get('certificate_sha256'),packet_sha256=p['quality_pin'],source_row_sha256=p['row_pin'])
            for n,v in p['extracts'].items()}
    def resolve(arm,forced=None):
        owner=branches[arm];manager=owner['manager'];e=manager.active;assert e and e['q'] is not None
        cutoff=current_frame;q=e['q'];assert q<=cutoff<=q+CFG['lag_frames']
        available=dict(owner['pre_packets']);available.update(packets)
        used={s['frame'] for v in e['joint_pre'].values() for s in v['samples']}|{s['frame'] for v in e['post_roles'].values() for s in v}
        for f in used:
            if f in available:decode(available[f])
        assessment=(dict(status='DEFER',choice='DEFER',mapping=None,reason=forced,causal_max_frame=cutoff,
            depth_gate=dict(eligible=False,reason=forced)) if forced else choose(e,e['joint_pre'],available,arm=='DEPTH_OVERRIDE' and not disabled))
        for f in used:
            if f in available:available[f].pop('masks',None)
        original_q_mapping=next(r['mapping'] for r in owner['lag'].rows if r['frame']==q)
        retained_sha=digest(branch_state(owner['bridge']));stage=False;error=None;record=None;selected=None;replay=[]
        wanted=assessment.get('mapping')
        if wanted:
            selected=copy.deepcopy(owner['q_checkpoint']);new_history=copy.deepcopy(owner['history_checkpoint'])
            try:
                for f in range(q,cutoff+1):
                    p=packets[f];r=p['row'];view=selected.preview(f,r['time'],r['observations'],p['profiles']);transaction=None
                    if f==q:
                        transaction,error=selected.stage_event(view,e,{int(n):int(k) for n,k in wanted.items()})
                        if transaction is None:break
                    mapping,trace=selected.commit_once(view,transaction)
                    new_history.observe(r,mapping,selected.epochs,selected.engine,classes=p['classes'][arm],depth_refs=refs(p))
                    replay.append((runtime(r,mapping,trace,selected,'DEPTH_EVENT_TRANSACTION' if transaction else 'ORIGINAL_OWN_Z4Q'),copy.deepcopy(selected)))
                if len(replay)==cutoff-q+1:
                    record=owner['lag'].resolve(q-1,selected,replay,cutoff);stage=True
            except (AssertionError,KeyError,ValueError) as failure:
                error='CANDIDATE_SUFFIX_REJECTED: '+type(failure).__name__+': '+str(failure)
        if stage:
            owner['bridge']=selected;owner['history']=new_history;owner['stages']+=1
            first_mapping=copy.deepcopy(replay[0][0]['mapping'])
        else:
            assert digest(branch_state(owner['bridge']))==retained_sha,'rejected proposal contaminated authority'
            first_mapping=copy.deepcopy(original_q_mapping)
        changes={str(n):dict(before=original_q_mapping[n],after=first_mapping[n]) for n in original_q_mapping if original_q_mapping[n]!=first_mapping[n]}
        status='RELIABLE_DEPTH_COMMIT' if stage else 'ORIGINAL_OWN_Z4Q_RETAINED'
        e.update(joint_decision=assessment,restore=dict(status=status,staged=stage,error=error,changes=changes,
            fallback=None if stage else dict(status='ORIGINAL_OWN_Z4Q_RETAINED',complete_own_state_retained=True,copies_external_B0=False),
            own_state_before_proposal_sha256=retained_sha,own_state_after_resolution_sha256=digest(branch_state(owner['bridge']))),
            actual_first_mapping=first_mapping,decision_cutoff=cutoff,lag_resolution=record,
            own_q_mapping_before_proposal=original_q_mapping,future_in_q_state=False,
            post_used_as_anonymous_until_selected=True,authority_never_protected=True)
        manager.finish(cutoff,status);owner['shadow'].sync(owner['bridge'])
        owner['pre_packets']={};owner['q_checkpoint']=owner['history_checkpoint']=None
    def publish(arrival,flush=False):
        nonlocal published
        ready={a:o['lag'].pop_ready(arrival,flush) for a,o in branches.items()}
        assert [r['frame'] for r in ready[EVENT_ARMS[0]]]==[r['frame'] for r in ready[EVENT_ARMS[1]]]
        for i,first in enumerate(ready[EVENT_ARMS[0]]):
            f=first['frame'];assert f==published+1;p=packets[f];values=copy.deepcopy(p['baseline'])
            transactions={'Z4Q_FROZEN':p['base_transaction']};txpins={}
            for a,o in branches.items():
                r=ready[a][i];values[a]=emit(r,r['mapping']);transactions[a]=r['transaction'];o['changed_frames']+=values[a]!=values['Z4Q_FROZEN']
                for e in o['manager'].events:
                    if e.get('q')==f:
                        assert e['decision_cutoff']<=arrival
                        e['first_publish_at_arrival_frame']=arrival;e['first_published_mapping']=copy.deepcopy(r['mapping'])
            assert values['DEPTH_OFF']==values['Z4Q_FROZEN']
            for a,t in transactions.items():txpins[a]=dump('TRANSACTIONS.jsonl.gz',dict(arm=a,**t))
            pin=dump('predictions.jsonl.gz',dict(frame=f,global_frame=p['row']['global_frame'],time=p['row']['time'],variants=values))
            ledger.write(json.dumps(dict(frame=f,global_frame=p['row']['global_frame'],prediction_row_sha256=pin,
                transaction_row_sha256=txpins,frame_inputs_row_sha256=p['input_pin'],first_publish_at_arrival_frame=arrival,
                actual_delay_frames=arrival-f,EOF_flush=flush,receive_to_first_publish_seconds=time.perf_counter()-p['received'],
                model_http=0,published_history_rewritten=False),separators=(',',':'))+'\n');published+=1
        for f,p in list(packets.items()):
            if f<=published and current_time-p['row']['time']>CFG['max_history_seconds']:
                packets.pop(f);assignments.pop(f,None)
    try:
        source=zip(stream(base/'observations.jsonl.gz',base/'profiles.jsonl.gz'),rows(base/'assignments.jsonl.gz'),
            rows(base/'DEPTH_OBSERVATIONS.jsonl.gz'),rows(cached),rows(archive),strict=True)
        for current_frame,((row,profiles),assignment,measured,quality,archived) in enumerate(source,1):
            current_time=row['time'];f=current_frame;received=time.perf_counter()
            assert f==row['frame']==assignment['frame']==measured['frame']==quality['frame']==archived['frame']
            assert row['global_frame']==start+f-1==assignment['global_frame_id']==measured['global_frame']==quality['global_frame']==archived['global_frame']
            assert current_time==assignment['time']==measured['time']==quality['time']==archived['time']
            assert quality['source_binding']==dict(measured['raw_source_binding'],frame=f)
            assert quality['actual_depth_binding']==measured['raw_source_binding']['aligned_depth']
            assert quality['actual_source_index_binding']==measured['raw_source_binding']['aligned_source_index']
            extracts={int(n):DEPTH.extract(cert) for n,cert in quality['objects'].items()}
            for n,cert in quality['objects'].items():
                assert cert['certificate_sha256']==digest({k:v for k,v in cert.items() if k!='certificate_sha256'})
                assert (cert['native'],cert['frame'],cert['time'])==(int(n),f,current_time)
            assignments[f]=assignment
            ids,trace=original.commit_once(original.preview(f,current_time,row['observations'],profiles))
            baseline=dict(SAM3_NATIVE=copy.deepcopy(row['native']),Z4Q_FROZEN=emit(row,ids))
            assert baseline['SAM3_NATIVE']==assignment['variants']['N0']==archived['variants']['SAM3_NATIVE']
            assert baseline['Z4Q_FROZEN']==archived['variants']['Z4Q_FROZEN']
            p=dict(row=row,profiles=profiles,assignment=assignment,measured=measured,extracts=extracts,baseline=baseline,
                base_transaction=txn(row,ids,trace,original),received=received,classes={})
            p['quality_pin']=digest(quality);p['row_pin']=row_sha(row)
            p['input_pin']=dump('FRAME_INPUTS_BINDINGS.jsonl.gz',dict(frame=f,global_frame=row['global_frame'],time=current_time,
                source_row_sha256=row_sha(row),assignment_row_sha256=row_sha(assignment),measured_row_sha256=row_sha(measured),
                DS18_packet_sha256=p['quality_pin'],DS18_extracts=extracts,raw_source_binding=measured['raw_source_binding'],
                actual_RGB_read=False,GT=False))
            packets[f]=p
            for arm,owner in branches.items():
                branch,manager,shadow=owner['bridge'],owner['manager'],owner['shadow']
                before=digest(branch_state(branch));shadow.sync(branch);signal=manager.before(row,profiles);e=manager.active
                assert digest(branch_state(branch))==before;owner['observer_state_checks']+=1
                if e and e['suspect_frame']==f:
                    e['joint_pre']=owner['history'].freeze_pre(e)
                    needed={s['frame'] for v in e['joint_pre'].values() for s in v['samples']}
                    owner['pre_packets']={g:copy.deepcopy(packets[g]) for g in needed if g in packets}
                if e and e['q']==f:
                    owner['q_checkpoint']=owner['lag'].checkpoint(f-1);owner['history_checkpoint']=copy.deepcopy(owner['history'])
                view=branch.preview(f,current_time,row['observations'],profiles)
                mapping,trace=branch.commit_once(view)
                assert vars(branch.engine)==vars(view['engine']) and branch.previous==view['mapping']
                owner['no_transaction_state_checks']+=1
                # Evidence isolation never removes raw masks, nor changes original engine measurements.
                p['classes'][arm]=copy.deepcopy(manager.frame_class)
                owner['history'].observe(row,mapping,branch.epochs,branch.engine,classes=p['classes'][arm],depth_refs=refs(p))
                owner['lag'].buffer(runtime(row,mapping,trace,branch,unchanged=digest(branch_state(branch))),branch)
                if arm=='DEPTH_OFF' or owner['stages']==0:
                    assert mapping==ids and digest(branch_state(branch))==digest(branch_state(original))
                    owner['original_state_parity_frames']+=1
                shadow.sync(branch);manager.after(row,profiles)
                releasing=manager.release_episode
                if releasing:manager.finish(f,releasing['status'])
                e=manager.active
                if e and e['q'] is not None:
                    if current_time-e['suspect_time']>CFG['max_episode_seconds']:resolve(arm,'UNKNOWN_EPISODE_TIMEOUT')
                    elif e.get('ready'):resolve(arm)
                    elif e.get('post_broken'):resolve(arm,'UNKNOWN_POST_SOURCE_BREAK')
                    elif e.get('deadline_reached') or f>=e['q']+CFG['lag_frames']:resolve(arm,'UNKNOWN_DEADLINE')
            publish(f);objects+=len(row['native'])
            if f%500==0:print(name,f,'/',limit,{a:dict(o['manager'].counts) for a,o in branches.items()},flush=True)
            if f==limit:break
        for a,o in branches.items():
            e=o['manager'].active
            if e and e.get('q') is not None:resolve(a,'UNKNOWN_EOF')
            elif e:e.update(status='UNKNOWN_EOF_EVENT_EVIDENCE_ONLY',end=current_frame)
        publish(current_frame,True);assert published==limit
    finally:
        for h in handles.values():h.close()
        ledger.close()
    write_new(public/'EVENTS.json',{a:[public_episode(e) for e in o['manager'].events] for a,o in branches.items()})
    write_new(public/'SCAN_DISPOSITIONS.json',{a:o['manager'].scan_records for a,o in branches.items()})
    write_new(public/'RUN_SUMMARY.json',dict(segment=name,frames=limit,objects=objects,published=published,
        arms={a:{k:v for k,v in o.items() if isinstance(v,int)}|dict(events=len(o['manager'].events),counts=dict(o['manager'].counts)) for a,o in branches.items()},
        elapsed_seconds=time.perf_counter()-began,disabled=disabled,original_Z4Q_exact=True,
        all_native_masks_unchanged=True,authority_never_protected=True,all_fallbacks_keep_complete_own_state=True,
        deployment='OFFLINE_SAVED_MASK_CPU_30FRAME_FIRST_PUBLICATION_BUFFER_NOT_REALTIME',new_model_http=0,cost_usd=0))
    if stop_at is None:
        assert published==stop-start+1
        sealed=files+('FREEZE.json','EVENTS.json','SCAN_DISPOSITIONS.json','PUBLISH_LEDGER.jsonl','RUN_SUMMARY.json')
        write_new(public/'PREDICTIONS_SEALED.json',dict(status='SEALED_AWAITING_INDEPENDENT_SCORING',segment=name,frames=published,
            arms=ARMS,artifacts_sha256={f:sha(public/f) for f in sealed},new_model_http=0,cost_usd=0))
    print(name,'complete',published,{a:o['stages'] for a,o in branches.items()},flush=True)
