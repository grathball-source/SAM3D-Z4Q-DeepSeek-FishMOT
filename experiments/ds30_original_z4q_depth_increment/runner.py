"""Each branch commits its real state before exactly one publication of each frame."""
from common import *
from bridge import Bridge,stream
from increment_controller import IncrementBridge,EvidenceBridge,EventManager,engine_state,branch_state
from evidence import Sources
from history import History
from association import freeze_pre,choose
import copy,time,cv2
cv2.setNumThreads(1)

def emit(row,ids):
    result=[dict(id=ids[x['id']],mask=x['mask']) for x in row['native']]
    assert len(result)==len(row['native'])==len(set(x['id'] for x in result))
    return result

def public_episode(e):
    return {k:copy.deepcopy(e.get(k)) for k in ('id','generation','member_sources','public_ids','suspect_frame',
        'confirm_frame','q','end','status','joint_pre','joint_decision','restore','group','group_anonymous','post_roles')}

def run_segment(name,output=RUN,stop_at=None,disabled=False):
    start,stop=SEGMENTS[name];base=input_dir(name);public=output/name/'public';public.mkdir(parents=True,exist_ok=True)
    if stop_at is None:
        for p,h in read(public/'FREEZE.json')['code'].items():assert sha(p)==h,p
    config=read(CONFIG_PATH);branches={'Z4Q_FROZEN':Bridge(config),**{a:IncrementBridge(config) for a in ARMS[2:]}}
    history={a:History(name) for a in ARMS[2:]};assignments={}
    suspects={} if disabled else {s['frame']:s for s in read(base/'scan_v4.json')['suspects']}
    shadows={a:EvidenceBridge(config) for a in ARMS[2:]}
    managers={a:EventManager(a,shadows[a],suspects,dict(max_episode_seconds=read(HERE/'CONFIG.json')['max_episode_seconds']),assignments) for a in ARMS[2:]}
    files=('predictions.jsonl.gz','TRANSACTIONS.jsonl.gz','ORDER_CHECKS.jsonl.gz','MEASUREMENTS.jsonl.gz','ANONYMOUS_RISK.jsonl.gz')
    handles={f:gzip.open(public/f,'xt',encoding='utf-8') for f in files};provider=Sources(name,handles['MEASUREMENTS.jsonl.gz'])
    ledger=(public/'PUBLISH_LEDGER.jsonl').open('x',encoding='utf-8');began=time.perf_counter()
    totals=dict(frames=0,objects=0,changed_frames={a:0 for a in ARMS[2:]},q_decisions={a:0 for a in ARMS[2:]},joint_stages={a:0 for a in ARMS[2:]},depth_informative=0,
        no_transaction_full_state_checks=0,actual_increment_started=False)
    archive=iter(rows(ROOT/'experiments/ds28_risk_driven_depth_entry/run'/name/'public/predictions.jsonl.gz'))
    def dump(filename,value):
        handles[filename].write(json.dumps(value,separators=(',',':'),allow_nan=False)+'\n');return row_sha(value)
    try:
        for i,((row,profiles),assignment,measured,archived) in enumerate(zip(stream(base/'observations.jsonl.gz',base/'profiles.jsonl.gz'),
            rows(base/'assignments.jsonl.gz'),rows(base/'DEPTH_OBSERVATIONS.jsonl.gz'),archive,strict=True),1):
            frame,now=row['frame'],row['time'];received=time.perf_counter();assignments[frame]=assignment
            assert frame==i and row['global_frame']==start+i-1
            assert (measured['frame'],measured['global_frame'],measured['time'])==(frame,row['global_frame'],now)
            provider.add(row,assignment,measured['raw_source_binding'])
            results={'SAM3_NATIVE':row['native']};tx_sha={};checks={}
            for arm,branch in branches.items():
                transaction=None;decision=None;episode=None;signal=None;expected_state_sha=None
                if arm in managers:
                    before_observer=digest(branch_state(branch));shadows[arm].sync(branch)
                    manager=managers[arm];signal=manager.before(row,profiles);episode=manager.active
                    if episode and episode['suspect_frame']==frame:episode['joint_pre']=freeze_pre(history[arm],episode)
                    assert digest(branch_state(branch))==before_observer,'Observer modified authoritative state'
                view=branch.preview(frame,now,row['observations'],profiles)
                original_view_sha=digest(engine_state(view['engine']))
                if episode and episode['q']==frame:
                    assert all(len(s)==1 and s[0]['frame']==frame for s in episode['post_roles'].values())
                    choice,detail=choose(episode,episode['joint_pre'],row,provider,arm)
                    mapping=detail['candidates'][choice]['mapping'] if choice in ('H1','H2') else None
                    residual=(set(episode['member_sources'])&set(view['mapping']))-set(episode['post_roles'])
                    error='DEFER' if mapping is None else 'VISIBLE_MEMBER_RESIDUAL' if residual else None
                    if mapping and not residual:transaction,error=branch.stage_group_restore(view,episode,mapping)
                    stage=transaction is not None
                    fallback=None if stage else dict(status='ORIGINAL_OWN_BRANCH_PREVIEW_RETAINED',copies_other_branch=False,complete_state_retained=True)
                    status='DEPTH_COMMIT' if stage else 'ORIGINAL_FALLBACK'
                    decision=dict(event=episode['id'],suspect_frame=episode['suspect_frame'],frame=frame,global_frame=row['global_frame'],choice=choice,detail=detail,
                        staged=stage,stage_error=error,fallback=fallback,mapping=mapping,
                        changes=transaction['changes'] if stage else {},references={str(k):copy.deepcopy(v['anchor']) for k,v in episode['bank_snapshot'].items()},
                        signal=signal,status=status,post_velocity='UNKNOWN',future_frames_used=0)
                    episode['joint_decision']=decision;episode['restore']=dict(status=status,changes=decision['changes'])
                    manager.finish(frame,status);totals['q_decisions'][arm]+=1;totals['joint_stages'][arm]+=stage
                    if arm=='DEPTH_INCREMENT':totals['depth_informative']+=detail['depth_used']
                assert digest(engine_state(view['engine']))==original_view_sha,'Stage contaminated original preview'
                if arm in managers and transaction is None:
                    expected=copy.copy(branch);expected.epochs=copy.deepcopy(branch.epochs);expected.provenance=copy.deepcopy(branch.provenance)
                    Bridge.commit_once(expected,view)
                    expected_state_sha=digest(branch_state(expected))
                ids,trace=branch.commit_once(view,transaction);results[arm]=emit(row,ids)
                if arm in managers:
                    if transaction is None:
                        assert digest(branch_state(branch))==digest(branch_state(expected))
                        totals['no_transaction_full_state_checks']+=1
                    else:totals['actual_increment_started']=True
                    if not totals['actual_increment_started']:
                        assert digest(branch_state(branch))==digest(branch_state(branches['Z4Q_FROZEN']))
                applied=[]
                for action in trace.get('events',[]):
                    if action.get('kind')=='reconnect' and action.get('accepted'):
                        n,k=action['native_id'],action['canonical_id']
                        applied.append(dict(action=action,actual_published=ids[n]==k,durable_alias=branch.engine.alias.get(n,{}).get('target')==k))
                if decision:
                    decision.update(actual_published_mapping={str(n):ids[n] for n in episode['post_roles']},
                        actual_aliases={str(n):copy.deepcopy(branch.engine.alias.get(n)) for n in episode['post_roles']},
                        commit_version=branch.version,decided_before_first_publication=True)
                tx_sha[arm]=dump('TRANSACTIONS.jsonl.gz',dict(frame=frame,global_frame=row['global_frame'],time=now,arm=arm,
                    actual_published_mapping=ids,branch_version=branch.version,
                    actual_alias_targets={str(n):a['target'] for n,a in branch.engine.alias.items()},bank_anchors={str(k):h.get('anchor') for k,h in branch.engine.bank.items()},
                    engine_state_sha256=digest(engine_state(branch.engine)),branch_state_sha256=digest(branch_state(branch)),
                    original_own_branch_preview_state_sha256=expected_state_sha,
                    state_selection='DEPTH_TRANSACTION' if transaction else 'ORIGINAL_OWN_BRANCH_PREVIEW',
                    controller_trace=trace,actual_actions=applied,joint_decision=decision,signal=signal))
                if arm in managers:
                    checks[arm]=[] if decision is None else [decision]
                    anonymous=set(manager.frame_class)
                    if episode and not (decision and decision['staged']):anonymous.update(episode['member_sources'])
                    objects=history[arm].observe(row,branch.previous,branch.epochs,branch.engine,anonymous)
                    shadows[arm].sync(branch)
                    manager.after(row,profiles)
                    dump('ANONYMOUS_RISK.jsonl.gz',dict(arm=arm,frame=frame,global_frame=row['global_frame'],time=now,
                        active_event=episode['id'] if episode else None,
                        observations={str(n):v for n,v in objects.items() if v['observation_class']=='ANONYMOUS_RISK_OBSERVATION'},
                        input_observation_row_sha256=row_sha(row),group_observations_kept=True,post_not_pre_before_decision=True))
                    totals['changed_frames'][arm]+=results[arm]!=results['Z4Q_FROZEN']
                    if disabled:
                        assert results[arm]==results['Z4Q_FROZEN']
                        assert digest(engine_state(branch.engine))==digest(engine_state(branches['Z4Q_FROZEN'].engine))
            assert results['SAM3_NATIVE']==archived['variants']['SAM3_NATIVE']==assignment['variants']['N0']
            assert results['Z4Q_FROZEN']==archived['variants']['Z4Q_FROZEN']
            check_sha=dump('ORDER_CHECKS.jsonl.gz',dict(frame=frame,global_frame=row['global_frame'],checks=checks))
            prediction_sha=dump('predictions.jsonl.gz',dict(frame=frame,global_frame=row['global_frame'],time=now,variants=results))
            ledger.write(json.dumps(dict(frame=frame,global_frame=row['global_frame'],prediction_row_sha256=prediction_sha,
                transaction_row_sha256=tx_sha,checks_row_sha256=check_sha,receive_to_first_publish_seconds=time.perf_counter()-received,model_http=0),separators=(',',':'))+'\n')
            totals['frames']+=1;totals['objects']+=len(row['native'])
            # The manager only reads the last group frame and current row.
            while len(assignments)>31:assignments.pop(next(iter(assignments)))
            if i%500==0:print(name,i,'/',stop-start+1,flush=True)
            if stop_at==i:break
    finally:
        provider.close();ledger.close()
        for h in handles.values():h.close()
    write_new(public/'EVENTS.json',{a:[public_episode(e) for e in managers[a].events] for a in managers})
    write_new(public/'SOURCE_ACCESS.json',dict(status='CAUSAL_CURRENT_OR_ALREADY_ACQUIRED_PAST_RAW_ONLY',actual_reads=provider.reads,GT_RGB_restored_future_network=False,new_model_http=0,cost_usd=0))
    write_new(public/'RUN_SUMMARY.json',dict(segment=name,**totals,measured_objects=len(provider.written),measurement_reasons=dict(provider.counts),
        elapsed_seconds=time.perf_counter()-began,disabled=disabled,all_native_masks_unchanged=True,original_Z4Q_exact=True,
        event_policy='ORIGINAL_SCAN_V4_AND_FIRST_SPLIT_Q',deployment='OFFLINE_CPU_SAVED_MASK_REPLAY',new_model_http=0,cost_usd=0))
    if stop_at is None:
        assert totals['frames']==stop-start+1
        sealed=files+('FREEZE.json','EVENTS.json','PUBLISH_LEDGER.jsonl','SOURCE_ACCESS.json','RUN_SUMMARY.json')
        write_new(public/'PREDICTIONS_SEALED.json',dict(status='SEALED_AWAITING_INDEPENDENT_SCORING',segment=name,frames=totals['frames'],arms=ARMS,
            artifacts_sha256={f:sha(public/f) for f in sealed},new_model_http=0,cost_usd=0))
    print(name,json.dumps(totals),flush=True)

