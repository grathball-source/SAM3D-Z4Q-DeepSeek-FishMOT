"""Six own-state causal replays; first-split pair order precedes publication."""
from __future__ import annotations
import copy, gzip, hashlib, json, sys, time
from common import *
import cv2
cv2.setNumThreads(1)
from bridge import stream, Bridge
from depth_state import DepthState
from merge_split_manager import choice_mapping
from order_association import choose as order_choice

_adapter=module('ds16_actual_event_controller',HERE/'controller.py')
EventBridge,EventManager=_adapter.EventBridge,_adapter.EventManager
_absolute=module('ds16_archived_absolute_group',DS15/'group_association.py')
EVENT_ARMS=ARMS[2:]
CONFIG_PATH=ROOT/'online/closed_loop_2888/z4q_source/CONFIG.json'
EVENT_CONFIG=OLD/'CONFIG_V7.json'


class EventDepthState(DepthState):
    def freeze(self,episode,frame,epochs=None,generations=None):
        result=super().freeze(episode,frame,epochs,generations)
        for role,native,public in zip(('A','B'),episode['member_sources'],episode['public_ids']):
            record=self.live.get(native)
            same=bool(record and record['key'][3]==public and
                (epochs is None or record['key'][4]==epochs.get(native)) and
                (generations is None or record['key'][2]==generations.get(native)))
            if same:
                samples=copy.deepcopy(record['latest_fragment'])
                assert all(s['frame']<frame for s in samples)
                result[role].update(key=copy.deepcopy(record['key']),samples=samples,
                    reference_policy='LATEST_INTACT_SAME_VERSION_FRAGMENT_NO_RISK_JOIN_MAX12SECONDS')
        return result


def emit(row,mapping):
    output=[dict(id=mapping[x['id']],mask=x['mask']) for x in row['native']]
    assert len(output)==len(set(x['id'] for x in output))==len(row['native'])
    return output


def automatic_adoption(branch,ids,trace,transaction=None):
    changes=(transaction or {}).get('changes',{})
    actions=[]
    for event in trace.get('events',[]):
        if event.get('kind')!='reconnect' or not event.get('accepted'):continue
        n,k=event['native_id'],event['canonical_id']
        actions.append(dict(event=copy.deepcopy(event),applied_at_first_publication=ids.get(n)==k,
            durable_alias_after_commit=branch.engine.alias.get(n,{}).get('target')==k,
            overridden_by_explicit_transaction=n in changes))
    return dict(actual_alias_targets={str(n):a['target'] for n,a in branch.engine.alias.items()},
        automatic_candidate_events=actions,durable_automatic_commits=[x for x in actions if
            x['applied_at_first_publication'] and x['durable_alias_after_commit'] and
            not x['overridden_by_explicit_transaction']])


def public_event(e):
    keys=('id','suspect_frame','confirm_frame','q','end','status','numeric','restore',
        'member_sources','public_ids','group_source','evidence_cutoff_frame','depth_frozen')
    result={k:copy.deepcopy(e.get(k)) for k in keys}
    result['reference_anchors']={str(k):copy.deepcopy(v.get('anchor')) for k,v in e['bank_snapshot'].items()}
    result['post_first_observations']={str(n):copy.deepcopy(v[0]) for n,v in e['post_roles'].items() if v}
    result['pre_geometry_history']=copy.deepcopy(e['pre'])
    result['group_frames']=[s['frame'] for s in e['group']]
    result['group_observations']=[dict(frame=s['frame'],source=s['source']) for s in e['group']]
    return result


def freeze_inputs(output):
    assert not output.exists(),output
    output.mkdir(parents=True)
    dependencies={Path(m.__file__).resolve() for m in list(sys.modules.values()) if
        getattr(m,'__file__',None) and str(m.__file__).endswith('.py') and
        str(Path(m.__file__).resolve()).lower().startswith(str(ROOT).lower())}
    dependencies.update((OLD/'score.py',OLD/'source_scan_v4.py',OLD/'source_scan.py',
        ROOT/'experiments/ds9_joint_h0_depth/association.py',ROOT/'experiments/ds9_joint_h0_depth/CONFIG.json',
        DS15/'group_association.py',DS15/'controller.py',CONFIG_PATH,EVENT_CONFIG,
        WORK/'tools/annotation/run_sam3_trackeval.py'))
    files=set(HERE.glob('*.py'))|set(HERE.glob('*.json'))|set(HERE.glob('*.md'))|dependencies
    code={str(p.resolve()):sha(p) for p in files}
    for name,(start,stop) in SEGMENTS.items():
        manifest=read(input_dir(name)/'SOURCE_MANIFEST.json')
        for item in manifest['derived_inputs'].values():verify_item(item)
        for key in ('scan','raw_sources','field_access'):verify_item(manifest[key])
        public=output/name/'public';public.mkdir(parents=True)
        write_new(public/'FREEZE.json',dict(status='FROZEN_BEFORE_PREDICTION',segment=name,
            original_frames=[start,stop],frames=stop-start+1,arms=list(ARMS),code_sha256=code,
            source_manifest=artifact(input_dir(name)/'SOURCE_MANIFEST.json'),source_chain=manifest,
            config_scientific_sha256=sha(HERE/'CONFIG.json'),extra_strategy_config=artifact(HERE/'STRATEGY.json'),
            branch_policy='Independent original Z4Q and four independently continuing event states',
            new_model_http=0,model_cost_usd=0,no_gt_before_seal=True))


def run_segment(name,output,stop_at=None):
    start,stop=SEGMENTS[name];base=input_dir(name);public=output/name/'public'
    public.mkdir(parents=True,exist_ok=True)
    sources=stream(base/'observations.jsonl.gz',base/'profiles.jsonl.gz',stop-start+1)
    measurements=rows(base/'DEPTH_OBSERVATIONS.jsonl.gz')
    assignments={r['frame']:r for r in rows(base/'assignments.jsonl.gz')}
    suspects={r['frame']:r for r in read(base/'scan_v4.json')['suspects']}
    config=read(CONFIG_PATH);event_config={'max_episode_seconds':read(EVENT_CONFIG)['max_episode_seconds']}
    z4q=Bridge(config)
    branches={a:EventBridge(config) for a in EVENT_ARMS}
    managers={a:EventManager(a,branches[a],suspects,event_config,assignments) for a in EVENT_ARMS}
    states={a:EventDepthState(name,a) for a in EVENT_ARMS}
    processed=observed=0;began=time.perf_counter();candidate_times=[]
    filenames=('predictions.jsonl.gz','DEPTH_OBSERVATIONS.jsonl.gz','DEPTH_STATES.jsonl.gz',
        'TRANSACTIONS.jsonl.gz','BIRTHS.jsonl.gz','CONTACT_CERTIFICATES.jsonl.gz','ORDER_EVIDENCE.jsonl.gz')
    streams={f:gzip.open(public/f,'wt',encoding='utf-8') for f in filenames}
    publisher=(public/'PUBLISH_LEDGER.jsonl').open('x',encoding='utf-8')
    def dump(filename,value):
        line=json.dumps(value,separators=(',',':'),allow_nan=False,default=str)+'\n'
        streams[filename].write(line)
        return hashlib.sha256(line.encode()).hexdigest()
    try:
        for index,((row,profiles),measured) in enumerate(zip(sources,measurements,strict=True)):
            frame,now=row['frame'],row['time'];received=time.perf_counter()
            assert frame==index+1 and row['global_frame']==start+index
            assert (measured['frame'],measured['global_frame'],measured['time'])==(frame,row['global_frame'],now)
            raw={int(n):v for n,v in measured['adaptive_raw'].items()}
            assert set(raw)=={o['id'] for o in row['observations']}
            dump('DEPTH_OBSERVATIONS.jsonl.gz',measured)
            contact=dict(frame=frame,global_frame=row['global_frame'],time=now,
                status='REUSED_IMMUTABLE_RAW_MEASUREMENTS_NO_EXTRA_BIRTH_MODULE',raw={},raw_source_binding=None,born_sources=[])
            contact_sha=dump('CONTACT_CERTIFICATES.jsonl.gz',contact)
            original_view=z4q.preview(frame,now,row['observations'],profiles)
            original_ids,original_trace=z4q.commit_once(original_view,None)
            output_row={'SAM3_NATIVE':row['native'],'Z4Q_FROZEN':emit(row,original_ids)}
            dump('TRANSACTIONS.jsonl.gz',dict(frame=frame,global_frame=row['global_frame'],arm='Z4Q_FROZEN',
                actual_published_mapping=original_ids,controller_trace=original_trace,version=z4q.version,
                **automatic_adoption(z4q,original_ids,original_trace)))
            event_publish={};birth_rows=[];order_rows=[]
            for arm in EVENT_ARMS:
                branch,manager,state=branches[arm],managers[arm],states[arm]
                previous=dict(branch.previous)
                signal=manager.before(row,profiles);episode=manager.active
                if episode and episode['suspect_frame']==frame:
                    episode['depth_frozen']=state.freeze(episode,frame,branch.epochs,manager.source_generation)
                    for n in episode['member_sources']:state.break_source(n)
                view=branch.preview(frame,now,row['observations'],profiles)
                transaction=restore=None
                if episode and episode['q']==frame:
                    assert episode['evidence_cutoff_frame']==frame and all(len(s)==1 for s in episode['post_roles'].values())
                    for n in episode['post_roles']:state.record_pending(n,raw[n],frame)
                    residual=sorted((set(episode['member_sources']) & set(raw))-set(episode['post_roles']))
                    then=time.perf_counter()
                    if arm=='Z4Q_STATE_FIXED':
                        choice,detail=_absolute.choose(episode,episode['depth_frozen'],raw,measured['adaptive_full'],view['mapping'],'RAW_DEPTH',name)
                    else:
                        mode={'ORDER_OFF':'ORDER_OFF','DEPTH_ORDER':'ORDER','ORDER_PERMUTE':'ORDER_PERMUTE'}[arm]
                        choice,detail=order_choice(episode,episode['depth_frozen'],raw,measured['adaptive_full'],view['mapping'],mode,name)
                    candidate_times.append(dict(arm=arm,frame=frame,kind='GROUP_ASSOCIATION',seconds=time.perf_counter()-then))
                    episode['numeric']=dict(choice=choice,detail=detail,legacy_choice=None)
                    mapping=choice_mapping(episode,choice) if choice in ('H1','H2') else None
                    error=('visible_member_residual_outside_two_member_restore' if residual else
                        'H0_KEEP_OWN_CAUSAL_MAPPING' if choice=='H0' else 'numeric_unresolved')
                    if mapping and not residual:transaction,error=branch.stage_group_restore(view,episode,mapping)
                    if transaction is None:
                        transaction,fallback=branch.local_fallback(view,episode)
                        status=fallback['status'];decision_source='OWN_BRANCH_LOCAL_FALLBACK'
                    else:
                        fallback=None;status='COMMIT' if transaction['changes'] else 'RESOLVE_NO_ID_CHANGE';decision_source=arm
                    restore=dict(status=status,selected_choice=choice,numeric_choice=None,mapping=mapping,
                        unassigned_member_residual=residual,changes=transaction['changes'],stage_error=error,
                        decision_source=decision_source,fallback=fallback,
                        mapping_relative_to_native={n:k for n,k in (mapping or {}).items() if n!=k},
                        published_previous_mapping={n:previous.get(n) for n in episode['post_roles']},
                        baseline_preview_mapping={n:view['mapping'][n] for n in episode['post_roles']},
                        changed_relative_to_previous={n:k for n,k in transaction['mapping'].items() if n in previous and previous[n]!=k})
                    episode['restore']=restore;manager.finish(frame,status)
                ids,trace=branch.commit_once(view,transaction)
                trace['ds16_strategy']=dict(original_automatic_rules_active=True,
                    identity_reference_banks_frozen_source_lifecycle_live=True,group_method=arm,
                    extra_birth_module=False,first_split_before_publication=True)
                restored=set(episode['post_roles']) if episode and restore and restore['status'] in ('COMMIT','RESOLVE_NO_ID_CHANGE') else set()
                classes={}
                for item in row['observations']:
                    n=item['id'];cls=manager.frame_class.get(n,'SOURCE_OBSERVATION')
                    if n in restored:cls='RESTORED_POST'
                    if cls in ('SOURCE_OBSERVATION','RESTORED_POST') and (item['area']<64 or item.get('neighbors') or not branch.engine.quality(item)):
                        cls='QUALITY_OR_CONTACT_RISK'
                    classes[n]=cls
                    generation=manager._generation(n,frame)
                    state.update(n,raw[n],frame,now,ids[n],branch.epochs.get(n),generation,cls)
                    record=state.live.get(n)
                    if record and record['samples'] and record['samples'][-1]['frame']==frame:
                        record['samples'][-1].update(version_key=list(record['key']),observation_class=cls,
                            source_native=n,n=raw[n]['core']['n'],valid_fraction=raw[n]['core']['valid_fraction'],
                            core_usable=raw[n]['core_usable'])
                manager.after(row,profiles)
                output_row[arm]=emit(row,ids)
                birth_rows.append(dict(frame=frame,global_frame=row['global_frame'],time=now,arm=arm,
                    baseline_before=copy.deepcopy(view['mapping']),actual_mapping=copy.deepcopy(ids),changes={},
                    status='ORIGINAL_Z4Q_AUTOMATIC_ONLY',queries=[],group_blocked=bool(episode),
                    preframe={},preframe_version=view['version'],transaction_version=branch.version))
                dump('DEPTH_STATES.jsonl.gz',dict(frame=frame,global_frame=row['global_frame'],arm=arm,
                    active_event=episode['id'] if episode else None,signal=signal,observation_classes=classes,
                    updates=state.updates,breaks=state.breaks,group_count=len(state.groups),pending_count=len(state.pending),
                    sample_counts={str(n):len(v['samples']) for n,v in state.live.items()},
                    source_versions={str(n):list(v['key']) for n,v in state.live.items()}))
                dump('TRANSACTIONS.jsonl.gz',dict(frame=frame,global_frame=row['global_frame'],arm=arm,signal=signal,
                    active_event=episode['id'] if episode else None,restore=restore,birth_restore=dict(status='ORIGINAL_AUTO_ONLY',changes={}),
                    actual_published_mapping=ids,previous_mapping=previous,epochs=branch.epochs,
                    bank_anchors={str(k):copy.deepcopy(v.get('anchor')) for k,v in branch.engine.bank.items()},
                    controller_trace=trace,**automatic_adoption(branch,ids,trace,transaction)))
                if episode and restore:
                    event_publish[arm]=dict(episode=episode['id'],q=frame,original_frame=row['global_frame'],post_sample_count=1,
                        first_public_pair={str(n):ids[n] for n in episode['post_roles']},decision_source=restore['decision_source'])
                    order_rows.append(dict(frame=frame,global_frame=row['global_frame'],time=now,arm=arm,event=episode['id'],q=frame,
                        detail=detail,selected_choice=choice,restore=restore,
                        published_mapping={n:ids[n] for n in episode['post_roles']}))
            prediction=dict(frame=frame,global_frame=row['global_frame'],time=now,variants=output_row)
            line_sha=dump('predictions.jsonl.gz',prediction)
            birth_hashes={};order_hashes={}
            for b in birth_rows:
                b['prediction_row_sha256']=line_sha;birth_hashes[b['arm']]=dump('BIRTHS.jsonl.gz',b)
            for order in order_rows:
                order['prediction_row_sha256']=line_sha;order_hashes[order['arm']]=dump('ORDER_EVIDENCE.jsonl.gz',order)
            publisher.write(json.dumps(dict(frame=frame,global_frame=row['global_frame'],extraction_seconds=0.,
                measurement_policy='IMMUTABLE_PRECOMPUTED_RAW_MEASUREMENT_FACTS_WITH_SOURCE_HASHES',
                receive_to_publish_seconds=time.perf_counter()-received,prediction_row_sha256=line_sha,
                birth_row_sha256=birth_hashes,contact_row_sha256=contact_sha,event_publish=event_publish,
                birth_publish={},order_row_sha256=order_hashes),separators=(',',':'),allow_nan=False)+'\n')
            processed+=1;observed+=len(row['observations'])
            if frame%100==0:print(name,frame,'/',stop-start+1,flush=True)
            if stop_at is not None and frame==stop_at:break
    finally:
        publisher.close()
        for handle in streams.values():handle.close()
    write_new(public/'EVENTS.json',{a:[public_event(e) for e in managers[a].events] for a in EVENT_ARMS})
    write_new(public/'COMMON_STATE_SHADOW.json',[])
    write_new(public/'PERFORMANCE.json',dict(candidate_times=candidate_times,state_update_times=[],
        note='CPU own-state replay; saved raw measurements; no API/SAM3/completion; not real-time deployment'))
    write_new(public/'RUN_SUMMARY.json',dict(segment=name,frames=processed,observations=observed,
        elapsed_seconds=time.perf_counter()-began,new_model_http=0,model_cost_usd=0,
        state={a:dict(updates=states[a].updates,breaks=states[a].breaks,groups=len(states[a].groups),pending=len(states[a].pending)) for a in EVENT_ARMS}))
    if stop_at is not None:return
    assert processed==stop-start+1
    sealed=filenames+('PUBLISH_LEDGER.jsonl','EVENTS.json','RUN_SUMMARY.json','FREEZE.json','COMMON_STATE_SHADOW.json','PERFORMANCE.json')
    write_new(public/'PREDICTIONS_SEALED.json',dict(status='SEALED_AWAITING_INDEPENDENT_SCORING',segment=name,
        original_frames=[start,stop],frames=processed,published_frames=processed,arms=list(ARMS),new_model_http=0,model_cost_usd=0,
        artifacts_sha256={f:sha(public/f) for f in sealed}))


if __name__=='__main__':freeze_inputs(RUN)
