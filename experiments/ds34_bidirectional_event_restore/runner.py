"""Original Z4Q outside protected events; real delayed pair transactions before publication."""
from common import *
import copy, time
from collections import OrderedDict
from bridge import Bridge, stream
from pycocotools import mask as coco
from transaction import GroupBridge, engine_state
from manager import EventManager
from history import History
from evidence import choose
from lag import LagBuffer, state_hash
from sensor import Sensor
from flow import PairMotion
from verify_inputs import verify_frozen_inputs

DEPTH = module('ds34_unchanged_depth', ROOT/'experiments/ds31_persistent_identity_depth/depth.py')

def emit(row, mapping):
    assert set(mapping)=={x['id'] for x in row['native']}
    result=[dict(id=mapping[x['id']],mask=x['mask']) for x in row['native']]
    assert len(result)==len(row['native'])==len(set(x['id'] for x in result))
    return result

def txn(row, mapping, trace, branch):
    return dict(frame=row['frame'],global_frame=row['global_frame'],time=row['time'],mapping=copy.deepcopy(mapping),
        version=branch.version,controller_trace=copy.deepcopy(trace),
        actual_actions=[copy.deepcopy(x) for x in trace.get('events',[]) if x.get('kind')=='reconnect' and x.get('accepted')],
        engine_state_sha256=digest(engine_state(branch.engine)),full_state_sha256=state_hash(branch),
        actual_aliases=copy.deepcopy(branch.engine.alias),actual_epochs=copy.deepcopy(branch.epochs),
        actual_provenance=copy.deepcopy(branch.provenance),
        bank_anchors={str(k):copy.deepcopy(h.get('anchor')) for k,h in branch.engine.bank.items()},
        source_row_sha256=row_sha(row),decided_before_first_publish=True,already_published_history_rewritten=False)

def runtime(row,mapping,trace,branch):
    result=copy.deepcopy(row);result.update(mapping=copy.deepcopy(mapping),trace=copy.deepcopy(trace),transaction=txn(row,mapping,trace,branch))
    return result

def decode(packet):
    if 'masks' not in packet:
        packet['masks']={o['id']:coco.decode(dict(size=packet['assignment']['masks'][o['mask']]['size'],
            counts=packet['assignment']['masks'][o['mask']]['counts'].encode('ascii'))).astype(bool) for o in packet['row']['native']}
    return packet['masks']

def public_episode(episode):
    result=copy.deepcopy(episode)
    result['temporary_id_records']=[dict(native=k[0],generation=k[1],public=v)
        for k,v in result.pop('temporary_ids',{}).items()]
    return result

def run_segment(name,output=RUN,stop_at=None,disabled=False):
    start,stop=SEGMENTS[name];limit=stop-start+1 if stop_at is None else stop_at
    base=input_dir(name);public=output/name/'public';public.mkdir(parents=True,exist_ok=True)
    if stop_at is None:
        frozen=read(public/'FREEZE.json');verify_frozen_inputs(frozen)
        pins_path=frozen['rgb_pins']['path']
    else:
        pins_path=ROOT/'experiments/ds33_rgbd_fixed_lag/RGB_INPUT_PINS.jsonl'
        write_new(public/'PREFIX_FREEZE.json',dict(segment=name,frames=limit,disabled=disabled,base=BASE,
            code={str(p):sha(p) for p in HERE.glob('*.py')},configuration=artifact(HERE/'CONFIG.json'),
            source=artifact(base/'SOURCE_MANIFEST.json'),rgb_pins=artifact(pins_path),model_http=0,GT=False))
    rgb_pins={p['global_frame']:p['rgb'] for p in rows(pins_path) if p['segment']==name}
    suspects=[] if disabled else read(base/'scan_v4.json')['suspects']
    assignments={};packets=OrderedDict();original=Bridge(read(CONFIG_PATH));sensor=Sensor(name)
    branches={}
    for arm in ARMS[2:]:
        branch=GroupBridge(read(CONFIG_PATH));manager=EventManager(arm,branch,suspects,CFG,assignments)
        branches[arm]=dict(bridge=branch,manager=manager,history=History(name),lag=LagBuffer(branch),pre_packets={},
            q_checkpoint=None,history_checkpoint=None,q_spec=None,changed_frames=0,changed_commits=0,stages=0,changed_fallbacks=0)
    files=('predictions.jsonl.gz','TRANSACTIONS.jsonl.gz','FRAME_INPUTS_BINDINGS.jsonl.gz','FLOW.jsonl.gz')
    handles={f:gzip.open(public/f,'xt',encoding='utf-8',newline='\n') for f in files}
    ledger=(public/'PUBLISH_LEDGER.jsonl').open('x',encoding='utf-8',newline='\n')
    cached=DS18/'run'/name/'public/MIXED_DEPTH.jsonl.gz'
    archive=ROOT/'experiments/ds33_rgbd_fixed_lag/run'/name/'public/predictions.jsonl.gz'
    began=time.perf_counter();published=objects=flow_count=0
    def dump(file,value):
        line=json.dumps(value,separators=(',',':'),allow_nan=False,default=lambda x:sorted(x) if isinstance(x,set) else x.tolist())+'\n'
        handles[file].write(line);return hashlib.sha256(line.encode()).hexdigest()
    def resolve(arm,forced=None):
        nonlocal flow_count
        owner=branches[arm];manager=owner['manager'];e=manager.active;assert e and e['q'] is not None
        cutoff=current_frame;q=e['q'];assert q<=cutoff<=q+CFG['lag_frames']
        available=dict(owner['pre_packets']);available.update(packets)
        pairs={};actual_sensors={}
        def actual(f):
            assert f in available and f<=cutoff,'unacquired/future source requested'
            if f not in actual_sensors:
                p=available[f];r=p['row'];sensor.previous=None # Explicit archived acquired-past lookup, not a chronological motion pair.
                sensor.raw.previous_frame=None
                s=sensor.read(r['global_frame'],r['time']);assert s['binding']['rgb']==rgb_pins[r['global_frame']]
                for k in ('aligned_depth','aligned_source_index','native_depth'):
                    assert s['binding'][k]==p['measured']['raw_source_binding'][k]
                actual_sensors[f]=s
                p['sensor']=s
            return actual_sensors[f]
        def motion(a,b):
            nonlocal flow_count
            assert a<b<=cutoff
            if (a,b) not in pairs:
                pair=PairMotion(actual(a),actual(b),CFG['flow']);pairs[a,b]=pair;flow_count+=1
                dump('FLOW.jsonl.gz',dict(event=e['id'],arm=arm,pre_frame=a,post_frame=b,evidence_cutoff=cutoff,
                    actual_pair=pair.numeric_summary,no_cumulative_long_anchor_warp=True))
            return pairs[a,b]
        used=set(s['frame'] for v in e['joint_pre'].values() for s in v['samples'])|set(
            s['frame'] for v in e['post_roles'].values() for s in v)
        for f in used:
            if f in available:decode(available[f])
        assessment=(dict(status='DEFER',choice='DEFER',mapping=None,reason=forced,causal_max_frame=cutoff)
            if forced else choose(e,e['joint_pre'],available,arm=='EVENT_RGBD',motion))
        for f in used:
            if f in available:
                available[f].pop('sensor',None);available[f].pop('masks',None)
        original_q_mapping=owner['lag'].rows[-(cutoff-q+1)]['mapping']
        def rebuild(wanted):
            selected=copy.deepcopy(owner['q_checkpoint']);selected.engine.protected={e['id']:copy.deepcopy(owner['q_spec'])}
            replay=[];new_history=copy.deepcopy(owner['history_checkpoint']);stage=False;error=None;fallback=None
            for f in range(q,cutoff+1):
                p=packets[f];r=p['row'];view=selected.preview(f,r['time'],r['observations'],p['profiles']);transaction=None
                if f==q:
                    if wanted:
                        transaction,error=selected.stage_group_restore(view,e,{int(n):int(k) for n,k in wanted.items()});stage=transaction is not None
                    if not stage:transaction,fallback=selected.local_fallback(view,e)
                mapping,trace=selected.commit_once(view,transaction)
                new_history.observe(r,mapping,selected.epochs,selected.engine)
                replay.append((runtime(r,mapping,trace,selected),copy.deepcopy(selected)))
            return selected,replay,new_history,stage,error,fallback
        try:
            selected,replay,new_history,stage,error,fallback=rebuild(assessment.get('mapping'))
        except (AssertionError,KeyError,ValueError) as failure:
            if not assessment.get('mapping'):raise
            # Every candidate is an isolated complete own-state replay; no failed suffix is published.
            selected,replay,new_history,stage,error,fallback=rebuild(None)
            error='CANDIDATE_SUFFIX_REJECTED: '+type(failure).__name__+': '+str(failure)
        record=owner['lag'].resolve(q-1,selected,replay,cutoff)
        owner['bridge']=selected;manager.bridge=selected;owner['history']=new_history
        changes={str(n):dict(before=original_q_mapping[n],after=replay[0][0]['mapping'][n]) for n in original_q_mapping if original_q_mapping[n]!=replay[0][0]['mapping'][n]}
        controls={a:{int(o['mask'][2:]):o['id'] for o in packets[q]['baseline'][a]} for a in ARMS[:2]}
        actual_differences={a:{str(n):dict(before=k,after=replay[0][0]['mapping'][n]) for n,k in m.items() if k!=replay[0][0]['mapping'][n]} for a,m in controls.items()}
        owner['stages']+=stage;owner['changed_commits']+=bool(stage and actual_differences['Z4Q_FROZEN']);owner['changed_fallbacks']+=bool(not stage and actual_differences['Z4Q_FROZEN'])
        status=('JOINT_COMMIT_CHANGED_VS_Z4Q' if actual_differences['Z4Q_FROZEN'] else 'JOINT_COMMIT_SAME_Q_PUBLICATION_VS_Z4Q') if stage else 'LOCAL_FALLBACK'
        e.update(joint_decision=assessment,restore=dict(status=status,staged=stage,error=error,fallback=fallback,changes=changes,
            preview_changes=changes,preview_was_never_published=True,first_publication_differences_vs_controls=actual_differences),
            actual_first_mapping=copy.deepcopy(replay[0][0]['mapping']),decision_cutoff=cutoff,lag_resolution=record,
            future_in_q_state=False,post_used_as_anonymous_until_selected=True)
        manager.finish(cutoff,status);owner['pre_packets']={};owner['q_checkpoint']=owner['history_checkpoint']=owner['q_spec']=None
    def publish(arrival,flush=False):
        nonlocal published
        ready={arm:owner['lag'].pop_ready(arrival,flush) for arm,owner in branches.items()}
        assert [r['frame'] for r in ready[ARMS[2]]]==[r['frame'] for r in ready[ARMS[3]]]
        for i,first in enumerate(ready[ARMS[2]]):
            f=first['frame'];assert f==published+1;p=packets[f];values=copy.deepcopy(p['baseline']);transactions={'Z4Q_FROZEN':p['base_transaction']};txpins={}
            for arm,owner in branches.items():
                r=ready[arm][i];values[arm]=emit(r,r['mapping']);transactions[arm]=r['transaction']
                owner['changed_frames']+=values[arm]!=values['Z4Q_FROZEN']
                for e in owner['manager'].events:
                    if e.get('q')==f:
                        assert e.get('decision_cutoff',arrival)<=arrival
                        e['first_publish_at_arrival_frame']=arrival;e['first_published_mapping']=copy.deepcopy(r['mapping'])
            for arm,t in transactions.items():txpins[arm]=dump('TRANSACTIONS.jsonl.gz',dict(arm=arm,**t))
            pin=dump('predictions.jsonl.gz',dict(frame=f,global_frame=p['row']['global_frame'],time=p['row']['time'],variants=values))
            ledger.write(json.dumps(dict(frame=f,global_frame=p['row']['global_frame'],prediction_row_sha256=pin,transaction_row_sha256=txpins,
                frame_inputs_row_sha256=p['input_pin'],first_publish_at_arrival_frame=arrival,actual_delay_frames=arrival-f,EOF_flush=flush,
                receive_to_first_publish_seconds=time.perf_counter()-p['received'],model_http=0,published_history_rewritten=False),separators=(',',':'))+'\n');published+=1
        # Scalars and compressed saved RLE retained only to make exact <=12-second pre anchors available.
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
                base_transaction=txn(row,ids,trace,original),received=received)
            p['quality_pin']=digest(quality);p['row_pin']=row_sha(row)
            p['input_pin']=dump('FRAME_INPUTS_BINDINGS.jsonl.gz',dict(frame=f,global_frame=row['global_frame'],time=current_time,
                source_row_sha256=row_sha(row),assignment_row_sha256=row_sha(assignment),measured_row_sha256=row_sha(measured),
                DS18_packet_sha256=p['quality_pin'],DS18_extracts=extracts,raw_source_binding=measured['raw_source_binding'],
                rgb_pin=rgb_pins[row['global_frame']],actual_RGB_read='ONLY_EVENT_ENDPOINTS_SEPARATE_FLOW_LEDGER',GT=False))
            packets[f]=p
            for arm,owner in branches.items():
                branch=owner['bridge'];manager=owner['manager'];signal=manager.before(row,profiles);e=manager.active
                if e and e['suspect_frame']==f:
                    e['joint_pre']=owner['history'].freeze_pre(e)
                    ids_pre={s['frame'] for v in e['joint_pre'].values() for s in v['samples']}
                    owner['pre_packets']={g:copy.deepcopy(packets[g]) for g in ids_pre if g in packets}
                if e and e['q']==f:
                    owner['q_checkpoint']=owner['lag'].checkpoint(f-1);owner['history_checkpoint']=copy.deepcopy(owner['history'])
                    owner['q_spec']=copy.deepcopy(branch.engine.protected[e['id']])
                view=branch.preview(f,current_time,row['observations'],profiles);transaction=None
                releasing=getattr(manager,'release_episode',None)
                if releasing:
                    transaction,detail=branch.local_release(view,releasing)
                    releasing['release_transaction']=detail
                mapping,trace=branch.commit_once(view,transaction);owner['lag'].buffer(runtime(row,mapping,trace,branch),branch)
                owner['history'].observe(row,mapping,branch.epochs,branch.engine,classes=manager.frame_class,
                    depth_refs={n:dict(frame=f,time=current_time,fact_id=v.get('fact_id'),certificate_sha256=v.get('certificate_sha256'),
                        packet_sha256=p['quality_pin'],source_row_sha256=p['row_pin']) for n,v in extracts.items()})
                manager.after(row,profiles)
                if releasing:manager.finish(f,releasing['status'])
                e=manager.active
                if e and e['q'] is not None:
                    if current_time-e['suspect_time']>CFG['max_episode_seconds']:resolve(arm,'UNKNOWN_EPISODE_TIMEOUT')
                    elif e.get('ready'):resolve(arm)
                    elif e.get('post_broken'):resolve(arm,'UNKNOWN_POST_SOURCE_BREAK')
                    elif e.get('deadline_reached') or f>=e['q']+30:resolve(arm,'UNKNOWN_DEADLINE')
                if disabled:
                    assert mapping==ids and digest(engine_state(branch.engine))==digest(vars(original.engine))
            publish(f);objects+=len(row['native'])
            if f%500==0:print(name,f,'/',limit,{a:dict(o['manager'].counts) for a,o in branches.items()},flush=True)
            if f==limit:break
        for arm,owner in branches.items():
            e=owner['manager'].active
            if e and e.get('q') is not None:resolve(arm,'UNKNOWN_EOF')
            elif e:e.update(status='UNKNOWN_EOF_GROUP_RESERVED',end=current_frame)
        publish(current_frame,True);assert published==limit
    finally:
        for h in handles.values():h.close()
        ledger.close();sensor.close()
    write_new(public/'EVENTS.json',{a:[public_episode(e) for e in o['manager'].events] for a,o in branches.items()})
    write_new(public/'SCAN_DISPOSITIONS.json',{a:o['manager'].scan_records for a,o in branches.items()})
    write_new(public/'RUN_SUMMARY.json',dict(segment=name,frames=limit,objects=objects,published=published,
        counts={a:dict(o['manager'].counts) for a,o in branches.items()},changed_frames={a:o['changed_frames'] for a,o in branches.items()},
        joint_stages={a:o['stages'] for a,o in branches.items()},changed_commits={a:o['changed_commits'] for a,o in branches.items()},
        changed_fallbacks={a:o['changed_fallbacks'] for a,o in branches.items()},
        actual_flow_pairs=flow_count,elapsed_seconds=time.perf_counter()-began,all_masks_retained=True,
        original_Z4Q_exact=True,published_once=True,disabled=disabled,fixed_lag_frames=30,model_http=0,cost_usd=0))
    sealed=files+('PUBLISH_LEDGER.jsonl','EVENTS.json','SCAN_DISPOSITIONS.json','RUN_SUMMARY.json',
        'FREEZE.json' if stop_at is None else 'PREFIX_FREEZE.json')
    write_new(public/'PREDICTIONS_SEALED.json',dict(status='SEALED_AWAITING_INDEPENDENT_SCORING',segment=name,frames=limit,
        arms=ARMS,artifacts_sha256={f:sha(public/f) for f in sealed},model_http=0,cost_usd=0))
    print(name,'SEALED',limit,flush=True)
