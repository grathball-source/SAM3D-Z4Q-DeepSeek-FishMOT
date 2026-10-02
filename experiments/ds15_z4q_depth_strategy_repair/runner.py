"""DS15 retain original Z4Q reconnects; additional depth edits precede first publication."""
from __future__ import annotations
import copy,gzip,hashlib,importlib.util,json,sys,time
from pathlib import Path
from common import *
import cv2
cv2.setNumThreads(1)
from bridge import stream, Bridge
from hybrid import HybridBridge, EventDepthState
from group_association import choose as repaired_group_choice
from merge_split_manager import choice_mapping,numeric_choice
from depth_state import DepthState
from birth_memory import BirthMemory
from reconnect import choose as birth_choice
from contact_measurement import measure_contact,array_binding
from source import RawDepth
from depth_measurement import decode
_spec=importlib.util.spec_from_file_location('ds12_actual_controller',HERE/'controller.py')
_native=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(_native)
DepthNativeBridge,DepthNativeManager=_native.DepthNativeBridge,_native.DepthNativeManager
_spec9=importlib.util.spec_from_file_location('ds12_frozen_group_choice',HERE.parent/'ds9_joint_h0_depth/association.py')
_old9=importlib.util.module_from_spec(_spec9);_spec9.loader.exec_module(_old9)
EVENT_ARMS=ARMS[2:]
CONFIG_PATH=ROOT/'online/closed_loop_2888/z4q_source/CONFIG.json'
EVENT_CONFIG=OLD/'CONFIG_V7.json'
def build_contact_frame(row,assignment,measured,reader):
    """Current actual raw pixels, preserved masks and original source index."""
    f,g,now=row['frame'],row['global_frame'],row['time']
    depth,index,native,binding=reader(g,now)
    masks={int(n[2:]):decode(rle) for n,rle in assignment['masks'].items()}
    assert set(masks)=={o['id'] for o in row['observations']}
    binding.update(frame=f,time=now,global_frame=g,
        assignment_row_sha256=hashlib.sha256(json.dumps(assignment,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest(),
        declared_observation_neighbors={str(o['id']):list(o.get('neighbors',[])) for o in row['observations']},
        measurement_fact_ids={str(n):m['fact_id'] for n,m in measured['adaptive_raw'].items()})
    raw=measure_contact(depth,index,masks,row['segment'],f,g,source_binding=binding,native_depth=native)
    return dict(frame=f,global_frame=g,time=now,status='ACTUAL_CURRENT_BIRTH_FRAME_MEASUREMENTS',
        raw={str(n):c for n,c in raw.items()},raw_source_binding=binding)


def emit(row,mapping):
    result=[dict(id=mapping[x['id']],mask=x['mask']) for x in row['native']]
    assert len(result)==len(row['native'])==len(set(x['id'] for x in result))
    return result

def public_event(e):
    keys=('id','suspect_frame','confirm_frame','q','end','status','numeric','restore',
          'member_sources','public_ids','group_source','evidence_cutoff_frame','depth_frozen')
    out={k:copy.deepcopy(e.get(k)) for k in keys}
    out['reference_anchors']={str(k):copy.deepcopy(v.get('anchor')) for k,v in e['bank_snapshot'].items()}
    out['post_first_observations']={str(n):copy.deepcopy(v[0]) for n,v in e['post_roles'].items() if v}
    out['pre_geometry_history']=copy.deepcopy(e['pre'])
    out['group_frames']=[s['frame'] for s in e['group']]
    out['group_observations']=[dict(frame=s['frame'],source=s['source']) for s in e['group']]
    return out

def freeze_inputs(output):
    assert not output.exists(),output
    output.mkdir(parents=True)
    dependencies={Path(m.__file__).resolve() for m in list(sys.modules.values())
        if getattr(m,'__file__',None) and str(m.__file__).endswith('.py')
        and str(Path(m.__file__).resolve()).lower().startswith(str(ROOT).lower())}
    dependencies.update((OLD/'score.py',OLD/'source_scan_v4.py',OLD/'source_scan.py',
        HERE.parent/'ds9_joint_h0_depth/association.py',HERE.parent/'ds9_joint_h0_depth/CONFIG.json',
        HERE.parent/'ds10_depth_failure_repair/association.py',HERE.parent/'ds11_depth_birth_reconnect/reconnect.py',
        HERE.parent/'ds10_depth_failure_repair/adaptive_core.py',
        WORK/'tools/depth_restoration/geometry.py',WORK/'tools/depth_restoration/build_aligned_dataset.py',
        WORK/'tools/sam3_depth_birth_inherit_20260917/features.py',WORK/'tools/annotation/run_sam3_trackeval.py',
        CONFIG_PATH,EVENT_CONFIG))
    files=set(HERE.glob('*.py'))|set(HERE.glob('*.json'))|set(HERE.glob('*.md'))|dependencies
    code={str(p.resolve()):sha(p) for p in files}
    for name,(start,stop) in SEGMENTS.items():
        manifest=read(input_dir(name)/'SOURCE_MANIFEST.json')
        for item in manifest['derived_inputs'].values():verify_item(item)
        for key in ('scan','raw_sources','field_access'):verify_item(manifest[key])
        frozen=dict(status='FROZEN_BEFORE_PREDICTION',segment=name,original_frames=[start,stop],frames=stop-start+1,
            arms=list(ARMS),code_sha256=code,source_manifest=artifact(input_dir(name)/'SOURCE_MANIFEST.json'),
            source_chain=manifest,config_scientific_sha256=sha(HERE/'CONFIG.json'),
            config_metadata_note='CONFIG byte-identical DS12; actual five arms and eight ranges in DS15 common; inactive metadata is descriptive only.',
            branch_policy='Independent state; original Z4Q, exact R12 and shared-protection control; repaired depth cannot edit old seals'
            , extra_strategy_config=artifact(HERE/'STRATEGY.json'),
            new_model_http=0,model_cost_usd=0,no_gt_before_seal=True)
        public=output/name/'public';public.mkdir(parents=True)
        write_new(public/'FREEZE.json',frozen)


def state_summary(state):
    return {str(n):dict(key=list(r['key']),last_frame=r['last_frame'],
        sample_frames=[s['frame'] for s in r['samples']],
        latest_fragment_frames=[s['frame'] for s in r['latest_fragment']]) for n,r in state.live.items()}


def automatic_adoption(branch,ids,trace,transaction=None):
    """A preview's accepted candidate is not necessarily an adopted alias."""
    changes=(transaction or {}).get('changes',{})
    events=[]
    for event in trace.get('events',[]):
        if event.get('kind')!='reconnect' or not event.get('accepted'):continue
        native,target=event['native_id'],event['canonical_id']
        events.append(dict(event=copy.deepcopy(event),applied_at_first_publication=ids.get(native)==target,
            durable_alias_after_commit=branch.engine.alias.get(native,{}).get('target')==target,
            overridden_by_explicit_transaction=native in changes))
    durable=[item for item in events if item['applied_at_first_publication'] and
        item['durable_alias_after_commit'] and not item['overridden_by_explicit_transaction']]
    return dict(actual_alias_targets={str(n):a['target'] for n,a in branch.engine.alias.items()},
        automatic_candidate_events=events,durable_automatic_commits=durable)

def plan_births(branch,view,queries,measured,full,mode,segment,disabled=False,group_blocked=False,contact_certificates=None):
    """One batch: colliding targets never get sequentially stolen by source order."""
    proposals={};selected={}
    for q in queries:
        n=q['source'];q.update(selected_target=None,selected_anchor=None,selected_reference_anchor=None,
            selected_candidate=None,selection=None,stage_error=None,status='KEEP_NATIVE',
            admission_body_sha256=None)
        if view['frame']==1:q['status']='INITIAL_FRAME_NOT_ASSOCIATED';continue
        if disabled:q['status']='F9_CONTROL_DISABLED';continue
        if group_blocked:q['status']='ACTIVE_GROUP_FRAME_BLOCKED';continue
        target,detail=birth_choice(q['query_observation'],q['candidates'],measured,full,mode,segment,contact_certificates)
        q['selection']=detail
        q['admission_body_sha256']=detail.get('admission_body_sha256')
        if target is None:continue
        candidate=next(c for c in q['candidates'] if c['public']==target and c['eligible'])
        q.update(selected_target=target,selected_candidate=copy.deepcopy(candidate),
            selected_anchor=copy.deepcopy(candidate['anchor']),
            selected_reference_anchor=copy.deepcopy(candidate['reference_anchor']),status='PROPOSED')
        proposals[n]=target;selected[n]=candidate
    conflicts={target for target in proposals.values() if list(proposals.values()).count(target)>1}
    for q in queries:
        if q['source'] in proposals and proposals[q['source']] in conflicts:
            q['status']='TARGET_COLLISION_REJECTED';q['stage_error']='shared_best_target'
            proposals.pop(q['source']);selected.pop(q['source'])
    if len(proposals)>2:
        for q in queries:
            if q['source'] in proposals:q.update(status='BATCH_CAPACITY_REJECTED',stage_error='existing_transaction_capacity_exceeded')
        return None,{},'BATCH_CAPACITY_REJECTED'
    if not proposals:return None,{},'NO_BIRTH_COMMIT'
    admissions={q['source']:q['selection']['admission_body'] for q in queries
        if q['source'] in proposals and q['selection'].get('admission_body') is not None}
    transaction,error=branch.stage_birth_reconnect(view,proposals,selected,admissions)
    for q in queries:
        if q['source'] in proposals:q.update(status='COMMIT' if transaction else 'STAGE_REJECTED',stage_error=error)
    return transaction,(proposals if transaction else {}),'COMMIT' if transaction else 'STAGE_REJECTED'

def run_segment(name,output,slice_mode=False,stop_at=None):
    start,stop=SEGMENTS[name];base=input_dir(name);public=output/name/'public';public.mkdir(parents=True,exist_ok=True)
    sources=stream(base/'observations.jsonl.gz',base/'profiles.jsonl.gz',stop-start+1)
    measurements=rows(base/'DEPTH_OBSERVATIONS.jsonl.gz')
    assignments={r['frame']:r for r in rows(base/'assignments.jsonl.gz')}
    reader=RawDepth(name);native_seen=set()
    suspects={r['frame']:r for r in read(base/'scan_v4.json')['suspects']}
    config=read(CONFIG_PATH);event_config={'max_episode_seconds':read(EVENT_CONFIG)['max_episode_seconds']}
    branches={a:(DepthNativeBridge(config) if a=='R12_RAW' else HybridBridge(config,a=='Z4Q_DEPTH')) for a in EVENT_ARMS}
    z4q=Bridge(config)
    managers={a:DepthNativeManager(a,branches[a],suspects,event_config,assignments) for a in EVENT_ARMS}
    states={a:(DepthState(name,a) if a=='R12_RAW' else EventDepthState(name,a)) for a in EVENT_ARMS}
    support={a:DepthState(name,a+'_SENSOR_SUPPORT') for a in EVENT_ARMS}
    memories={a:BirthMemory(name) for a in EVENT_ARMS}
    processed=observed=0;first_slice=None;candidate_times=[];update_times=[];began=time.perf_counter()
    birth_counts={a:dict(queries=0,proposals=0,commits=0) for a in EVENT_ARMS}
    with gzip.open(public/'predictions.jsonl.gz','wt',encoding='utf-8') as predictions, \
         gzip.open(public/'DEPTH_OBSERVATIONS.jsonl.gz','wt',encoding='utf-8') as obsfile, \
         gzip.open(public/'DEPTH_STATES.jsonl.gz','wt',encoding='utf-8') as statefile, \
         gzip.open(public/'TRANSACTIONS.jsonl.gz','wt',encoding='utf-8') as txfile, \
         gzip.open(public/'BIRTHS.jsonl.gz','wt',encoding='utf-8') as births, \
         gzip.open(public/'CONTACT_CERTIFICATES.jsonl.gz','wt',encoding='utf-8') as certfile, \
         (public/'PUBLISH_LEDGER.jsonl').open('x',encoding='utf-8') as publisher:
        for index,((row,profiles),measured) in enumerate(zip(sources,measurements,strict=True)):
            frame,now=row['frame'],row['time'];received=time.perf_counter()
            assert frame==index+1 and row['global_frame']==start+index
            assert (measured['frame'],measured['global_frame'],measured['time'])==(frame,row['global_frame'],now)
            raw={int(n):v for n,v in measured['adaptive_raw'].items()}
            assert set(raw)=={o['id'] for o in row['observations']}
            obsfile.write(json.dumps(measured,separators=(',',':'),allow_nan=False)+'\n')
            current=set(raw);born=current-native_seen;native_seen.update(current)
            then=time.perf_counter()
            if frame>1 and born:
                contact_row=build_contact_frame(dict(row,segment=name),assignments[frame],measured,reader)
            else:
                contact_row=dict(frame=frame,global_frame=row['global_frame'],time=now,
                    status='NO_NONINITIAL_FIRST_EVER_BIRTH',raw={},raw_source_binding=None)
            contact_row['born_sources']=sorted(born) if frame>1 else []
            extraction_seconds=time.perf_counter()-then
            cline=json.dumps(contact_row,separators=(',',':'),allow_nan=False)+'\n'
            contact_line_sha=hashlib.sha256(cline.encode()).hexdigest();certfile.write(cline)
            original_view=z4q.preview(frame,now,row['observations'],profiles)
            original_ids,original_trace=z4q.commit_once(original_view,None)
            output_row={'SAM3_NATIVE':row['native'],'Z4Q_FROZEN':emit(row,original_ids)};event_publish={};birth_rows=[]
            txfile.write(json.dumps(dict(frame=frame,global_frame=row['global_frame'],arm='Z4Q_FROZEN',
                actual_published_mapping=original_ids,controller_trace=original_trace,version=z4q.version,
                **automatic_adoption(z4q,original_ids,original_trace)),
                separators=(',',':'),allow_nan=False,default=str)+'\n')
            for arm in EVENT_ARMS:
                branch,manager,state,rawstate,memory=branches[arm],managers[arm],states[arm],support[arm],memories[arm]
                state_measured=raw
                full=measured['adaptive_full']
                mode='RAW_DEPTH'
                previous=dict(branch.previous);pre_version=branch.version
                if arm!='R12_RAW':branch.bind_depth(row,state_measured,full,memory,rawstate)
                signal=manager.before(row,profiles);episode=manager.active;group_blocked=bool(episode)
                if episode and episode['suspect_frame']==frame:
                    episode['depth_frozen']=state.freeze(episode,frame,branch.epochs,manager.source_generation)
                    for n in episode['member_sources']:state.break_source(n);rawstate.break_source(n)
                view=branch.preview(frame,now,row['observations'],profiles)
                snapshot=dict(bank_anchors={str(k):copy.deepcopy(v.get('anchor')) for k,v in branch.engine.bank.items()},
                    alias_targets={str(n):a['target'] for n,a in branch.engine.alias.items()},
                    group_reserved_targets=sorted({k for s in branch.engine.protected.values() for k in s['member_public']}),
                    epochs=copy.deepcopy(branch.epochs),source_generations=copy.deepcopy(manager.source_generation),
                    previous_mapping=previous,birth_raw_arm=rawstate.arm)
                queries=memory.before(row,profiles,manager,rawstate,view)
                certificates={int(n):c for n,c in contact_row['raw'].items()}
                view['contact_certificates']=certificates
                for query in queries:
                    query['current_measurement_fact_id']=state_measured[query['source']]['fact_id']
                    query['contact_certificate']=copy.deepcopy(certificates.get(query['source']))
                    query['contact_row_sha256']=contact_line_sha
                transaction=restore=None
                if episode and episode['q']==frame:
                    assert episode['evidence_cutoff_frame']==frame and all(len(s)==1 for s in episode['post_roles'].values())
                    for n in episode['post_roles']:state.record_pending(n,state_measured[n],frame)
                    residual=sorted((set(episode['member_sources']) & {o['id'] for o in row['observations']})-set(episode['post_roles']))
                    legacy,_=numeric_choice(episode);then=time.perf_counter()
                    if arm=='R12_RAW':
                        choice,detail=_old9.choose(episode,episode['depth_frozen'],state_measured,full,view['mapping'],mode,name)
                    elif arm=='Z4Q_SHARED':
                        choice,detail='H0',dict(reason='SHARED_PROTECTION_ONLY_NO_EXTRA_ID_EDITS',evidence_max_frame=frame,accepted=False)
                    else:
                        choice,detail=repaired_group_choice(episode,episode['depth_frozen'],state_measured,full,view['mapping'],mode,name)
                    candidate_times.append(dict(arm=arm,frame=frame,kind='GROUP_ASSOCIATION',seconds=time.perf_counter()-then))
                    episode['numeric']=dict(choice=choice,detail=detail,legacy_choice=legacy)
                    mapping=choice_mapping(episode,choice) if choice in ('H1','H2') else None
                    error=('visible_member_residual_outside_two_member_restore' if residual else 'H0_KEEP_LAWFUL_MAPPING' if choice=='H0' else 'numeric_unresolved')
                    if mapping and not residual:transaction,error=branch.stage_group_restore(view,episode,mapping)
                    if transaction is None:
                        transaction,fallback=branch.local_fallback(view,episode);status=fallback['status'];decision_source='OWN_BRANCH_LOCAL_FALLBACK'
                    else:
                        fallback=None;status='COMMIT' if transaction['changes'] else 'RESOLVE_NO_ID_CHANGE';decision_source=arm
                    restore=dict(status=status,selected_choice=choice,numeric_choice=legacy,mapping=mapping,
                        unassigned_member_residual=residual,changes=transaction['changes'],stage_error=error,
                        decision_source=decision_source,fallback=fallback,
                        mapping_relative_to_native={n:k for n,k in (mapping or {}).items() if n!=k},
                        published_previous_mapping={n:previous.get(n) for n in episode['post_roles']},
                        baseline_preview_mapping={n:view['mapping'][n] for n in episode['post_roles']},
                        changed_relative_to_previous={n:k for n,k in transaction['mapping'].items() if n in previous and previous[n]!=k})
                    episode['restore']=restore;manager.finish(frame,status)
                then=time.perf_counter()
                birth_tx,changes,birth_status=plan_births(branch,view,queries,state_measured,full,mode,name,
                    disabled=(arm=='Z4Q_SHARED'),group_blocked=group_blocked,contact_certificates=certificates)
                candidate_times.append(dict(arm=arm,frame=frame,kind='BIRTH',seconds=time.perf_counter()-then))
                assert transaction is None or birth_tx is None
                if birth_tx is not None:transaction=birth_tx
                ids,trace=branch.commit_once(view,transaction)
                if arm=='R12_RAW':
                    assert all(c['veto'] for c in trace.get('native_first_auto_edge_checks',[]))
                    assert not any(e.get('kind')=='reconnect' and e.get('accepted') for e in trace.get('events',[]))
                else:
                    trace['ds15_strategy']=dict(original_automatic_rules_active=True,depth_guard=(arm=='Z4Q_DEPTH'),
                        event_depth_decision=(arm=='Z4Q_DEPTH'),shared_protection=True)
                post_restored=(set(episode['post_roles']) if episode and restore and restore['status'] in ('COMMIT','RESOLVE_NO_ID_CHANGE') else set())
                classes={};then=time.perf_counter()
                for item in row['observations']:
                    n=item['id'];cls=manager.frame_class.get(n,'SOURCE_OBSERVATION')
                    if n in post_restored:cls='RESTORED_POST'
                    if cls in ('SOURCE_OBSERVATION','RESTORED_POST') and (item['area']<64 or item.get('neighbors') or not branch.engine.quality(item)):
                        cls='QUALITY_OR_CONTACT_RISK'
                    classes[n]=cls
                    for target,facts in ((state,state_measured),(rawstate,raw)):
                        target.update(n,facts[n],frame,now,ids[n],branch.epochs.get(n),manager._generation(n,frame),cls)
                memory.after(row,profiles,manager,rawstate,ids,classes,raw)
                update_times.append(dict(arm=arm,frame=frame,seconds=time.perf_counter()-then))
                manager.after(row,profiles)
                output_row[arm]=emit(row,ids)
                for q in queries:
                    q['actual_first_public_id']=ids[q['source']];q['transaction_version']=branch.version
                birth_counts[arm]['queries']+=len(queries)
                birth_counts[arm]['proposals']+=sum(q['selected_target'] is not None for q in queries)
                birth_counts[arm]['commits']+=len(changes)
                birth_rows.append(dict(frame=frame,global_frame=row['global_frame'],time=now,arm=arm,
                    baseline_before=copy.deepcopy(view['mapping']),actual_mapping=copy.deepcopy(ids),changes=changes,
                    status=birth_status,queries=queries,group_blocked=group_blocked,
                    preframe=snapshot,preframe_version=pre_version,transaction_version=branch.version))
                statefile.write(json.dumps(dict(frame=frame,global_frame=row['global_frame'],arm=arm,
                    active_event=episode['id'] if episode else None,signal=signal,live=state_summary(state),
                    birth_raw_arm=rawstate.arm,birth_raw_live=state_summary(rawstate),observation_classes=classes,
                    breaks=state.breaks,updates=state.updates,group_count=len(state.groups),pending_count=len(state.pending),
                    resident_live_objects=len(state.live),resident_cache_samples=sum(len(r['cache']) for r in state.live.values()),
                    resident_current_samples=sum(len(r['samples']) for r in state.live.values()),
                    resident_latest_fragment_samples=sum(len(r['latest_fragment']) for r in state.live.values())),
                    separators=(',',':'),allow_nan=False,default=str)+'\n')
                txfile.write(json.dumps(dict(frame=frame,global_frame=row['global_frame'],arm=arm,signal=signal,
                    active_event=episode['id'] if episode else None,restore=restore,birth_restore=dict(status=birth_status,changes=changes),
                    actual_published_mapping=ids,previous_mapping=previous,epochs=branch.epochs,
                    bank_anchors={str(k):copy.deepcopy(v.get('anchor')) for k,v in branch.engine.bank.items()},
                    controller_trace=trace,**automatic_adoption(branch,ids,trace,transaction)),separators=(',',':'),allow_nan=False,default=str)+'\n')
                if episode and restore:
                    event_publish[arm]=dict(episode=episode['id'],q=frame,original_frame=row['global_frame'],post_sample_count=1,
                        first_public_pair={str(n):ids[n] for n in episode['post_roles']},decision_source=restore['decision_source'])
            prediction=dict(frame=frame,global_frame=row['global_frame'],time=now,variants=output_row)
            line=json.dumps(prediction,separators=(',',':'),allow_nan=False)+'\n'
            line_sha=hashlib.sha256(line.encode()).hexdigest();predictions.write(line)
            birth_hashes={};birth_publish={}
            for b in birth_rows:
                b['prediction_row_sha256']=line_sha
                bline=json.dumps(b,separators=(',',':'),allow_nan=False)+'\n';births.write(bline)
                birth_hashes[b['arm']]=hashlib.sha256(bline.encode()).hexdigest()
                if b['queries']:
                    birth_publish[b['arm']]=dict(transaction_version=b['transaction_version'],changes=b['changes'],
                        post_sample_count=1,first_public_ids={str(q['source']):q['actual_first_public_id'] for q in b['queries']},
                        admission_body_sha256={str(q['source']):q['admission_body_sha256'] for q in b['queries']})
                if first_slice is None and b['arm']=='R12_RAW':
                    qualified=next((q for q in b['queries'] if frame>1 and not b['group_blocked'] and
                        q['query_observation']['quality'] and q['query_observation']['neighbors'] and
                        q['query_observation']['area']>=64 and q.get('contact_certificate') and q['contact_certificate']['eligible'] and
                        any(c['eligible'] for c in q['candidates'])),None)
                    if qualified:
                        first_slice=dict(segment=name,q=frame,original_q=row['global_frame'],source=qualified['source'],
                            arm=b['arm'],query=copy.deepcopy(qualified),birth_row=copy.deepcopy(b),
                            measured=copy.deepcopy(measured),first_public_id=qualified['actual_first_public_id'])
            published=time.perf_counter()
            publisher.write(json.dumps(dict(frame=frame,global_frame=row['global_frame'],extraction_seconds=extraction_seconds,
                measurement_policy='SOURCE_BOUND_RAW_HISTORY_GROUP_CACHE_PLUS_ACTUAL_CURRENT_CONTACT_DEPTH',receive_to_publish_seconds=published-received,
                prediction_row_sha256=line_sha,birth_row_sha256=birth_hashes,contact_row_sha256=contact_line_sha,event_publish=event_publish,
                birth_publish=birth_publish),separators=(',',':'),allow_nan=False)+'\n')
            processed+=1;observed+=len(row['observations'])
            if frame%50==0:print(name,frame,'/',stop-start+1,'birth_commits', {a:v['commits'] for a,v in birth_counts.items()},flush=True)
            if stop_at is not None and frame==stop_at:break
            if slice_mode and first_slice:break
    reader.close()
    write_new(public/'EVENTS.json',{a:[public_event(e) for e in managers[a].events] for a in EVENT_ARMS})
    write_new(public/'COMMON_STATE_SHADOW.json',[])
    write_new(public/'PERFORMANCE.json',dict(candidate_times=candidate_times,state_update_times=update_times,
        note='Local CPU one native/OpenCV thread; raw source-bound history/group cache; elapsed includes actual current-birth reprojection/certificate, state and logs.'))
    write_new(public/'RUN_SUMMARY.json',dict(segment=name,frames=processed,observations=observed,
        elapsed_seconds=time.perf_counter()-began,peak_python_allocated_bytes=None,birth_counts=birth_counts,
        state={a:dict(updates=states[a].updates,breaks=states[a].breaks,groups=len(states[a].groups),pending=len(states[a].pending)) for a in EVENT_ARMS},
        new_model_http=0,model_cost_usd=0))
    if stop_at is not None:return first_slice
    if slice_mode:
        if first_slice:write_new(output/'REAL_SLICE.json',first_slice)
        return first_slice
    assert processed==stop-start+1
    filenames=('predictions.jsonl.gz','DEPTH_OBSERVATIONS.jsonl.gz','DEPTH_STATES.jsonl.gz','BIRTHS.jsonl.gz','CONTACT_CERTIFICATES.jsonl.gz',
        'TRANSACTIONS.jsonl.gz','PUBLISH_LEDGER.jsonl','EVENTS.json','RUN_SUMMARY.json','FREEZE.json','COMMON_STATE_SHADOW.json','PERFORMANCE.json')
    write_new(public/'PREDICTIONS_SEALED.json',dict(status='SEALED_AWAITING_INDEPENDENT_SCORING',segment=name,
        original_frames=[start,stop],frames=processed,published_frames=processed,arms=list(ARMS),new_model_http=0,model_cost_usd=0,
        artifacts_sha256={f:sha(public/f) for f in filenames}))
    return first_slice

if __name__=='__main__':freeze_inputs(RUN)
