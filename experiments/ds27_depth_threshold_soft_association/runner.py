"""Six genuine state branches. All masks survive; decision precedes publication."""
from common import *
from bridge import stream, Bridge
from soft_controller import SoftBridge
from history import History
from evidence import Sources, Context
import copy, time, cv2
cv2.setNumThreads(1)

def emit(row,ids):
    result=[dict(id=ids[x['id']],mask=x['mask']) for x in row['native']]
    assert len(result)==len(set(x['id'] for x in result))==len(row['native'])
    return result

def engine_state(engine):
    return {k:v for k,v in vars(engine).items() if k not in ('soft_context','soft_cost_checks')}

def run_segment(name,output=RUN,stop_at=None,disabled=False):
    start,stop=SEGMENTS[name];base=input_dir(name);public=output/name/'public';public.mkdir(parents=True,exist_ok=True)
    if stop_at is None:
        for p,h in read(public/'FREEZE.json')['code'].items():assert sha(p)==h,p
    config=read(CONFIG_PATH);branches={'Z4Q_FROZEN':Bridge(config),**{a:SoftBridge(config) for a in ARMS[2:]}}
    histories={a:History(name) for a in ARMS[2:]};altered={a:False for a in ARMS[2:]}
    names=('predictions.jsonl.gz','TRANSACTIONS.jsonl.gz','ORDER_CHECKS.jsonl.gz','MEASUREMENTS.jsonl.gz','ANONYMOUS_RISK.jsonl.gz')
    handles={f:gzip.open(public/f,'xt',encoding='utf-8') for f in names}
    provider=Sources(name,handles['MEASUREMENTS.jsonl.gz']);ledger=(public/'PUBLISH_LEDGER.jsonl').open('x',encoding='utf-8')
    began=time.perf_counter();totals=dict(frames=0,objects=0,changed_frames={a:0 for a in ARMS[2:]},checks={a:0 for a in ARMS[2:]},soft_cost_updates={a:0 for a in ARMS[2:]})
    archive=iter(rows(ROOT/'experiments/ds20_pending_confirmation_isolation/run'/name/'public/predictions.jsonl.gz'))
    def dump(filename,value):
        handles[filename].write(json.dumps(value,separators=(',',':'),allow_nan=False)+'\n');return row_sha(value)
    try:
        for i,((row,profiles),assignment,measured,archived) in enumerate(zip(stream(base/'observations.jsonl.gz',base/'profiles.jsonl.gz'),
            rows(base/'assignments.jsonl.gz'),rows(base/'DEPTH_OBSERVATIONS.jsonl.gz'),archive,strict=True),1):
            frame,now=row['frame'],row['time'];received=time.perf_counter()
            assert frame==i and row['global_frame']==start+i-1
            assert (measured['frame'],measured['global_frame'],measured['time'])==(frame,row['global_frame'],now)
            provider.add(row,assignment,measured['raw_source_binding'])
            results={'SAM3_NATIVE':row['native']};tx_sha={};checks={}
            for arm,branch in branches.items():
                if arm in histories:branch.engine.soft_context=None if disabled else Context(row,histories[arm],provider,dict(branch.previous),dict(branch.epochs),arm)
                view=branch.preview(frame,now,row['observations'],profiles);ids,trace=branch.commit_once(view,None)
                results[arm]=emit(row,ids);applied=[]
                for action in trace.get('events',[]):
                    if action.get('kind')=='reconnect' and action.get('accepted'):
                        n,k=action['native_id'],action['canonical_id']
                        applied.append(dict(action=action,actual_published=ids[n]==k,durable_alias=branch.engine.alias.get(n,{}).get('target')==k))
                transaction=dict(frame=frame,global_frame=row['global_frame'],time=now,arm=arm,
                    actual_published_mapping=ids,branch_version=branch.version,
                    actual_alias_targets={str(n):a['target'] for n,a in branch.engine.alias.items()},
                    bank_anchors={str(k):h.get('anchor') for k,h in branch.engine.bank.items()},
                    engine_state_sha256=digest(engine_state(branch.engine)),controller_trace=trace,actual_actions=applied)
                tx_sha[arm]=dump('TRANSACTIONS.jsonl.gz',transaction)
                if arm in histories:
                    checks[arm]=branch.engine.soft_cost_checks
                    count=sum(bool(x.get('applied_delta_cost',0)) for x in checks[arm]);altered[arm]|=bool(count)
                    totals['checks'][arm]+=len(checks[arm]);totals['soft_cost_updates'][arm]+=count
                    if not altered[arm] or disabled:
                        assert results[arm]==results['Z4Q_FROZEN']
                        assert digest(engine_state(branch.engine))==digest(engine_state(branches['Z4Q_FROZEN'].engine)),'UNKNOWN/disabled changed original state'
                    objects=histories[arm].observe(row,branch.previous,branch.epochs,branch.engine)
                    dump('ANONYMOUS_RISK.jsonl.gz',dict(arm=arm,frame=frame,global_frame=row['global_frame'],time=now,
                        observations={str(n):v for n,v in objects.items() if v['observation_class']=='ANONYMOUS_RISK_OBSERVATION'},
                        input_observation_row_sha256=row_sha(row),no_individual_depth_history_write=True,no_Z4Q_bank_measurement_write=True))
                    totals['changed_frames'][arm]+=results[arm]!=results['Z4Q_FROZEN']
            assert results['SAM3_NATIVE']==archived['variants']['SAM3_NATIVE']==assignment['variants']['N0']
            assert results['Z4Q_FROZEN']==archived['variants']['Z4Q_FROZEN'],'Same-source Z4Q regression'
            check_sha=dump('ORDER_CHECKS.jsonl.gz',dict(frame=frame,global_frame=row['global_frame'],time=now,checks=checks,
                dummy_invalid_and_original_gates_unchanged=True,depth_cost_is_conditional_soft_evidence=True))
            prediction_sha=dump('predictions.jsonl.gz',dict(frame=frame,global_frame=row['global_frame'],time=now,variants=results))
            ledger.write(json.dumps(dict(frame=frame,global_frame=row['global_frame'],time=now,prediction_row_sha256=prediction_sha,
                transaction_row_sha256=tx_sha,checks_row_sha256=check_sha,receive_to_first_publish_seconds=time.perf_counter()-received,model_http=0),separators=(',',':'))+'\n')
            totals['frames']+=1;totals['objects']+=len(row['native'])
            if i%500==0:print(name,i,'/',stop-start+1,flush=True)
            if stop_at==i:break
    finally:
        provider.close();ledger.close()
        for h in handles.values():h.close()
    write_new(public/'SOURCE_ACCESS.json',dict(status='CAUSAL_CURRENT_OR_ALREADY_ACQUIRED_PAST_RAW_ONLY',actual_reads=provider.reads,
        GT_RGB_restored_future_network=False,new_model_http=0,cost_usd=0))
    write_new(public/'RUN_SUMMARY.json',dict(segment=name,**totals,measured_objects=len(provider.written),measurement_reasons=dict(provider.counts),
        measurement_unit='POLICY_FRAME_ORIGINAL_MASK_ANONYMOUS_FACT',maximum_private_cached_packets=64,
        elapsed_seconds=time.perf_counter()-began,disabled_evidence=disabled,every_native_mask_unchanged=True,
        every_original_Z4Q_publication_exact=True,new_model_http=0,cost_usd=0,deployment='OFFLINE_SAVED_MASK_CPU_REPLAY_NOT_REALTIME'))
    if stop_at is None:
        assert totals['frames']==stop-start+1
        files=names+('FREEZE.json','PUBLISH_LEDGER.jsonl','RUN_SUMMARY.json','SOURCE_ACCESS.json')
        write_new(public/'PREDICTIONS_SEALED.json',dict(status='SEALED_AWAITING_INDEPENDENT_SCORING',segment=name,frames=totals['frames'],arms=ARMS,
            artifacts_sha256={f:sha(public/f) for f in files},new_model_http=0,cost_usd=0))
    print(name,json.dumps(totals),flush=True)
