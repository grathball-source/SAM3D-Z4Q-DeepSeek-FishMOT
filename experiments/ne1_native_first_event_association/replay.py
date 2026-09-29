"""Native-first event association on the fixed SOURCE_OLD FEEDING segments."""
import copy
import gzip
import hashlib
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
FEED = ROOT / 'experiments/feeding_first_two_s0p'
OLD = ROOT / 'experiments/ms1_s0_development_8400'
P = ROOT / 'experiments/s0p_identity_publication'
PX = ROOT / 'experiments/z4q_pairwise_reconnect_repair/source'
sys.path[:0] = [str(FEED), str(P), str(OLD), str(ROOT/'online/closed_loop_2888/z4q_source')]
from bridge import Bridge, read, rows, sha, stream  # noqa: E402
import event_packet  # noqa: E402
from event_packet import packet, render_images, token_map  # noqa: E402
from manager_p import GroupBridgeP, MergeSplitManagerP  # noqa: E402
from merge_split_manager import choice_mapping, numeric_choice  # noqa: E402
from provider_v7 import Provider, PER_SLOT_USD, append  # noqa: E402
from prepare import SEGMENTS, write_new  # noqa: E402
from ne_controller import NativeFirstGroupBridgeP  # noqa: E402

CONFIG_PATH = ROOT/'online/closed_loop_2888/z4q_source/CONFIG.json'
V7_CONFIG = OLD/'CONFIG_V7.json'
CODE = (HERE/'CONFIG.json', HERE/'ne_controller.py', HERE/'replay.py', HERE/'score.py', HERE/'test_ne.py',
        FEED/'prepare.py', FEED/'scan.py',
        OLD/'merge_split_manager.py', OLD/'source_scan_v4.py', OLD/'event_packet.py',
        OLD/'provider_v7.py', OLD/'MS1_MODEL_PROMPTS.md', P/'manager_p.py',
        ROOT/'online/closed_loop_2888/z4q_source/bridge.py', CONFIG_PATH, V7_CONFIG,
        *(PX/f'px_{name}.py' for name in ('return','z4','z3','z2','d1')))
event_packet.COORDINATES = (
    '预测mask网格640×360；x向右、y向下；位置/框为像素，速度px/s；'
    '深度为原生传感器投影到RGB相机的Z方向毫米中位数/MAD，0为缺失，未做补全或折射校正。'
    '非零深度不保证鱼体精度；每帧RGB/深度采集时间差来自manifest。'
    '无邻居、非零面积、同source只是预测观测属性，不证明完整鱼体或跨时身份。')


def emit(row, mapping):
    result = [dict(id=mapping[x['id']], mask=x['mask']) for x in row['native']]
    assert len(result) == len(row['native']) == len(set(x['id'] for x in result))
    return result


def public_event(event):
    keys = ('id','suspect_frame','confirm_frame','q','end','status','numeric','restore',
            'publication_policy','M_status','S_raw_choice','S_parse_status',
            'model_selected','member_sources','public_ids','group_source',
            'evidence_cutoff_frame')
    result={key:copy.deepcopy(event.get(key)) for key in keys}
    result['reference_anchors']={str(k):copy.deepcopy(v.get('anchor'))
                                 for k,v in event.get('bank_snapshot',{}).items()}
    result['post_first_observations']={str(n):copy.deepcopy(series[0])
        for n,series in event.get('post_roles',{}).items() if series}
    return result


def annotate_sensor_timing(episode, offsets):
    """Replace old dataset's unknown sync field with this bag's measured offset."""
    sequences=[*episode['pre'].values(),*episode['pre_risk'].values(),
               episode['group'],episode['group_anonymous'],
               *episode['post_roles'].values()]
    for series in sequences:
        for item in series:
            delta=offsets[item['frame']]
            item['time_source']='FEEDING_MANIFEST_RGB_TIMESTAMP_US'
            item['sensor_sync_status']=f'MEASURED_RGB_MINUS_DEPTH_DELTA_US={delta}'


class CappedProvider(Provider):
    """A hard HTTP and dollar cap turns budget exhaustion into an unsent record."""

    def infer(self, episode, stage, body, images):
        if self.attempts >= self.config['max_inference_http'] or (
                self.config['budget_usd'] is not None and
                self.spent_upper+PER_SLOT_USD > self.config['budget_usd']):
            self.send_enabled=False
        return super().infer(episode,stage,body,images)


class PreflightProvider:
    """Build exact causal packets and geometry on a numeric-path shadow, without HTTP."""

    attempts=0
    spent_upper=0.
    send_enabled=False

    def __init__(self, output):
        self.output=output

    def infer(self, episode, stage, body, images):
        tag=episode['id']+'-'+stage
        payload=dict(stage=stage,episode=episode['id'],cutoff=episode['confirm_frame'] if stage=='M' else episode['q'],
                     system_chars=len(body['system']),user_chars=len(body['user']),
                     estimated_input_tokens=int(.6*(len(body['system'])+len(body['user'])))+16384*len(images)+1024,
                     image_bytes=[Path(x['path']).stat().st_size for x in images],
                     image_sha256=[x['sha256'] for x in images],
                     max_output_tokens=65536,peak_slot_usd=PER_SLOT_USD)
        append(self.output/'public/PREFLIGHT_PACKETS.jsonl',payload)
        write_new(self.output/'public/requests'/f'{tag}.json',body)
        return ('DEFER','PREFLIGHT_NO_HTTP',None) if stage=='S0' else (None,'PREFLIGHT_NO_HTTP',None)


def freeze_all(mode):
    assert mode in ('dry','preflight','real')
    output = HERE/('dry_v2' if mode=='dry' else 'preflight' if mode=='preflight' else 'run')
    assert not output.exists(), output
    if mode == 'real':
        assert os.environ.get('DEEPSEEK_API_KEY'), 'DEEPSEEK_API_KEY missing'
    output.mkdir()
    code_hashes = {str(path):sha(path) for path in CODE}
    for name,(start,stop) in SEGMENTS.items():
        private = FEED/'private'/name
        source = read(private/'SOURCE_MANIFEST.json')
        scan_manifest = read(private/'SCAN_MANIFEST.json')
        scan = read(private/'scan_v4.json')
        assert source['frames']==scan['frames']==stop-start+1
        assert scan_manifest['scan_sha256']==sha(private/'scan_v4.json')
        for item in source['derived'].values():
            path=Path(item['path'])
            assert path.stat().st_size==item['bytes'] and sha(path)==item['sha256']
        unique_frames=len({item['frame'] for item in scan['suspects']})
        public=output/name/'public'
        public.mkdir(parents=True)
        write_new(public/'FREEZE.json',dict(status='FROZEN_BEFORE_ANY_MODEL_CALL',
            mode=mode,segment=name,original_frames=[start,stop],frames=stop-start+1,
            code_sha256=code_hashes,source_manifest_sha256=sha(private/'SOURCE_MANIFEST.json'),
            derived_inputs=source['derived'],scan_sha256=scan_manifest['scan_sha256'],
            scanner='frozen prediction-only V4; last candidate at duplicate frame as existing manager',
            scanner_suspects=len(scan['suspects']),unique_suspect_frames=unique_frames,
            model_selection='globally earliest eight live two-frame confirmed episodes by SOURCE_OLD time; M once at confirmation, S0 at first split if legal',
            max_inference_http=16 if mode=='real' else 0,
            total_budget_usd=4.0 if mode=='real' else 0,
            per_request_peak_reserve_usd=PER_SLOT_USD if mode=='real' else 0,
            no_rgb_no_gt_before_seal=True,model='deepseek-flash' if mode=='real' else None,
            decision='S0 before first current-frame publication; invalid/DEFER uses same HOLD numeric fallback',
            source_limitation='saved batched SAM3 raw polygons, not a continuous SAM3 tracking session'))
    return output


def run_segment(name, mode, output, provider, selected):
    start,stop=SEGMENTS[name]
    private=FEED/'private'/name
    public=output/name/'public'
    source=list(stream(private/'observations.jsonl.gz',private/'profiles.jsonl.gz',stop-start+1))
    assignment={row['frame']:row for row in rows(private/'assignments.jsonl.gz')}
    assert len(assignment)==len(source)==stop-start+1
    scan=read(private/'scan_v4.json')
    suspects={item['frame']:item for item in scan['suspects']}
    tokens=token_map([row for row,_ in source])
    manifest={item['frame']:item for item in map(json.loads,
              (Path('E:/CAU/D-MOT/data/AlignedFeeding_v1')/'manifest.jsonl').read_text(encoding='utf-8').splitlines())}
    offsets={local:manifest[global_frame]['delta_us']
             for local,global_frame in enumerate(range(start,stop+1),1)}
    config=read(V7_CONFIG)
    b0=Bridge(read(CONFIG_PATH))
    num=NativeFirstGroupBridgeP(read(CONFIG_PATH))
    vlm=NativeFirstGroupBridgeP(read(CONFIG_PATH))
    mn=MergeSplitManagerP('EVENT_NUM',num,suspects,config,assignment)
    mv=MergeSplitManagerP('EVENT_VLM',vlm,suspects,config,assignment)
    start_calls=provider.attempts if provider else 0
    start_charge=provider.spent_upper if provider else 0.
    selected_this=[]
    edge_checks={'EVENT_NUM':{'D1_DELAYED':0,'BIRTH_REFINE':0},
                 'EVENT_VLM':{'D1_DELAYED':0,'BIRTH_REFINE':0}}
    accepted={'Z4Q_FROZEN':{'D1_DELAYED':0,'BIRTH_REFINE':0},
              'EVENT_NUM':{'D1_DELAYED':0,'BIRTH_REFINE':0},
              'EVENT_VLM':{'D1_DELAYED':0,'BIRTH_REFINE':0}}
    no_event_native_checks=0
    began=time.monotonic()
    with gzip.open(public/'predictions.jsonl.gz','wt',encoding='utf-8') as pred_file, \
         gzip.open(public/'TRANSACTIONS.jsonl.gz','wt',encoding='utf-8') as txn_file, \
         (public/'PUBLISH_LEDGER.jsonl').open('x',encoding='utf-8') as publish_file:
        for row,profiles in source:
            received=time.monotonic()
            frame,now=row['frame'],row['time']
            v0=b0.preview(frame,now,row['observations'],profiles)
            ids0,trace0=b0.commit_once(v0)
            for event in trace0.get('events',[]):
                if event.get('kind')=='reconnect' and event.get('accepted'):
                    origin=event.get('origin_rule') or (
                        'BIRTH_REFINE' if event.get('birth_frame')==frame else 'D1_DELAYED')
                    accepted['Z4Q_FROZEN'][origin]+=1
            txn_file.write(json.dumps(dict(frame=frame,global_frame=row['global_frame'],
                arm='Z4Q_FROZEN',actual_published_mapping=ids0,
                bank_anchors={str(k):copy.deepcopy(v.get('anchor')) for k,v in b0.engine.bank.items()},
                alias=copy.deepcopy(b0.engine.alias),controller_trace=trace0),
                ensure_ascii=False,separators=(',',':'),default=str)+'\n')
            branch={}
            for arm,bridge,manager in (('EVENT_NUM',num,mn),('EVENT_VLM',vlm,mv)):
                previous_ids=dict(bridge.previous)
                signal=manager.before(row,profiles)
                view=bridge.preview(frame,now,row['observations'],profiles)
                episode=manager.active
                if arm=='EVENT_VLM' and episode and episode['confirm_frame']==frame:
                    episode['model_selected']=len(selected)<8
                    if episode['model_selected']:
                        selected.append(dict(segment=name,episode=episode['id'],
                                             local_confirm=frame,global_confirm=row['global_frame']))
                        selected_this.append(episode['id'])
                if arm=='EVENT_VLM' and episode and episode['confirm_frame']==frame and episode['model_selected']:
                    if mode in ('real','preflight'):
                        provider.output=output/name
                        annotate_sensor_timing(episode,offsets)
                        images=render_images(episode,'M',assignment,tokens,
                                             output/name/'private_source/geometry')
                        body=packet(episode,'M',tokens,images,assignment)
                        _,status,response=provider.infer(episode,'M',body,images)
                        episode['M_status']=status
                        episode['M_hypothesis']=response['content'] if response and status=='OK' else None
                    else:
                        episode['M_status']='DRY_NO_API'
                        episode['M_hypothesis']=None
                transaction=restore=None
                if episode and episode['q']==frame:
                    assert episode['split_first_frame']==frame
                    assert all(len(series)==1 for series in episode['post_roles'].values())
                    # Two named post roles can coexist with a visible member
                    # residual. That is a three-object observation, so the
                    # two-bank restore cannot safely be staged on this frame.
                    residual=sorted((set(episode['member_sources']) &
                                     {item['id'] for item in row['observations']})-
                                    set(episode['post_roles']))
                    numeric,details=numeric_choice(episode)
                    episode['numeric']=dict(choice=numeric,detail=details)
                    choice=numeric
                    raw_choice=parse_status=None
                    if arm=='EVENT_VLM' and episode.get('model_selected') and not residual:
                        if mode in ('real','preflight'):
                            provider.output=output/name
                            annotate_sensor_timing(episode,offsets)
                            images=render_images(episode,'S0',assignment,tokens,
                                                 output/name/'private_source/geometry')
                            body=packet(episode,'S0',tokens,images,assignment,episode.get('M_hypothesis'))
                            raw_choice,parse_status,_=provider.infer(episode,'S0',body,images)
                        else:
                            raw_choice,parse_status='DEFER','DRY_NO_API'
                        if raw_choice in ('H1','H2'):
                            choice=raw_choice
                    episode['S_raw_choice']=raw_choice
                    episode['S_parse_status']=parse_status
                    mapping=choice_mapping(episode,choice) if choice in ('H1','H2') else None
                    error='visible_member_residual_outside_two_member_restore' if residual else 'numeric_unresolved'
                    if mapping and not residual:
                        transaction,error=bridge.stage_group_restore(view,episode,mapping)
                    if transaction is None:
                        transaction,fallback=bridge.local_fallback(view,episode)
                        status=fallback['status']
                        decision_source='OWN_BRANCH_LOCAL_FALLBACK'
                    else:
                        fallback=None
                        status='COMMIT' if transaction['changes'] else 'RESOLVE_NO_ID_CHANGE'
                        decision_source=('MODEL' if raw_choice in ('H1','H2') else
                                         'MODEL_DEFER_NUMERIC_FALLBACK' if raw_choice=='DEFER' else
                                         'NUMERIC' if arm=='EVENT_NUM' else 'NUMERIC_FALLBACK')
                    restore=dict(status=status,numeric_choice=numeric,selected_choice=choice,
                                 raw_choice=raw_choice,parse_status=parse_status,
                                 mapping=mapping,unassigned_member_residual=residual,
                                 changes=transaction['changes'],
                                 stage_error=error,decision_source=decision_source,fallback=fallback)
                    episode['restore']=restore
                    manager.finish(frame,status)
                ids,trace=bridge.commit_once(view,transaction)
                for check in trace.get('native_first_auto_edge_checks',[]):
                    edge_checks[arm][check['origin_rule']]+=1
                    assert check['veto']
                for action in trace.get('events',[]):
                    if action.get('kind')=='reconnect' and action.get('accepted'):
                        accepted[arm][action['origin_rule']]+=1
                assert all(v==0 for v in accepted[arm].values())
                if not manager.events and not bridge.engine.alias and not episode:
                    assert ids=={o['id']:o['id'] for o in row['observations']}
                    no_event_native_checks+=1
                manager.after(row,profiles)
                branch[arm]=emit(row,ids)
                publication_source={}
                group=trace.get('merge_split_group') or {}
                for n,k in ids.items():
                    if restore and episode and n in episode.get('post_roles',{}):
                        if restore['decision_source']=='MODEL':
                            origin='EVENT_MODEL'
                        elif restore['decision_source']=='OWN_BRANCH_LOCAL_FALLBACK':
                            origin='LOCAL_FALLBACK'
                        else:
                            origin='EVENT_NUMERIC'
                    elif n in group.get('outputs',{}):
                        origin='GROUP_PUBLICATION'
                    elif n in bridge.engine.alias or (n in previous_ids and previous_ids[n]!=k):
                        origin='LIFECYCLE'
                    else:
                        origin='UPSTREAM_NATIVE_CHANGE'
                    publication_source[str(n)]=dict(public_id=k,origin=origin,
                        changed_from_previous=previous_ids.get(n)!=k)
                txn_file.write(json.dumps(dict(frame=frame,global_frame=row['global_frame'],
                    arm=arm,signal=signal,active_event=episode['id'] if episode else None,
                    restore=restore,actual_published_mapping=ids,
                    publication_source=publication_source,
                    bank_anchors={str(k):copy.deepcopy(v.get('anchor')) for k,v in bridge.engine.bank.items()},
                    alias=copy.deepcopy(bridge.engine.alias),
                    controller_trace=trace,
                    internal_token_state=trace.get('merge_split_group')),
                    ensure_ascii=False,separators=(',',':'),default=str)+'\n')
            result=dict(frame=frame,global_frame=row['global_frame'],time=now,
                        variants={'SAM3_NATIVE':row['native'],
                                  'Z4Q_FROZEN':emit(row,ids0),**branch})
            assert all([item['mask'] for item in value]==[item['mask'] for item in result['variants']['SAM3_NATIVE']]
                       for value in branch.values())
            line=json.dumps(result,separators=(',',':'),allow_nan=False)+'\n'
            pred_file.write(line)
            event_publish={}
            for arm,manager,objects in (('EVENT_NUM',mn,branch['EVENT_NUM']),
                                        ('EVENT_VLM',mv,branch['EVENT_VLM'])):
                event=next((item for item in manager.events if item.get('q')==frame),None)
                if event:
                    actual={int(item['mask'][2:]):item['id'] for item in objects}
                    event_publish[arm]=dict(episode=event['id'],original_frame=row['global_frame'],
                        q=frame,post_sample_count=1,
                        first_public_pair={str(n):actual[n] for n in event['post_roles']},
                        decision_source=event['restore']['decision_source'])
            if event_publish:
                pred_file.flush()
            published=time.monotonic()
            publish_file.write(json.dumps(dict(frame=frame,global_frame=row['global_frame'],
                frame_received_monotonic=received,first_publish_time_monotonic=published,
                receive_to_publish_seconds=published-received,
                prediction_row_sha256=hashlib.sha256(line.encode()).hexdigest(),
                event_publish=event_publish),separators=(',',':'))+'\n')
            if frame%50==0:
                print(name,mode,frame,'/',len(source),'events',len(mv.events),flush=True)
    write_new(public/'EVENTS.json',dict(EVENT_NUM=[public_event(e) for e in mn.events],
                                         EVENT_VLM=[public_event(e) for e in mv.events],
                                         selected_confirmed=selected_this))
    write_new(public/'AUTO_RECONNECT_AUDIT.json',dict(edge_checks=edge_checks,
        accepted=accepted,no_event_native_equality_frame_checks=no_event_native_checks,
        policy='D1_DELAYED and BIRTH_REFINE candidate edges vetoed before assignment'))
    call_ledger=public/'CALL_LEDGER.jsonl'
    if not call_ledger.exists():
        call_ledger.write_text('',encoding='utf-8')
    seal=dict(status='SEALED_AWAITING_INDEPENDENT_SCORING',segment=name,
              original_frames=[start,stop],frames=len(source),published_frames=len(source),
              mode=mode,model='deepseek-flash' if mode=='real' else None,
              http_attempts=provider.attempts-start_calls if provider else 0,
              peak_charge_upper_usd=provider.spent_upper-start_charge if provider else 0,
              send_enabled_at_end=provider.send_enabled if provider else False,
              selected_confirmed=selected_this,wall_seconds=time.monotonic()-began,
              predictions_sha256=sha(public/'predictions.jsonl.gz'),
              transactions_sha256=sha(public/'TRANSACTIONS.jsonl.gz'),
              publish_ledger_sha256=sha(public/'PUBLISH_LEDGER.jsonl'),
              events_sha256=sha(public/'EVENTS.json'),
              auto_reconnect_audit_sha256=sha(public/'AUTO_RECONNECT_AUDIT.json'),
              call_ledger_sha256=sha(call_ledger),freeze_sha256=sha(public/'FREEZE.json'))
    write_new(public/'PREDICTIONS_SEALED.json',seal)
    print(name,'SEALED',json.dumps(dict(frames=seal['frames'],events=len(mv.events),
                                        http_attempts=seal['http_attempts'],
                                        charge_upper=seal['peak_charge_upper_usd'])),flush=True)
    return seal


def main(mode):
    output=freeze_all(mode)
    provider=(CappedProvider(output/next(iter(SEGMENTS)),dict(read(V7_CONFIG),
        max_inference_http=16,budget_usd=4.0)) if mode=='real' else
        PreflightProvider(output/next(iter(SEGMENTS))) if mode=='preflight' else None)
    selected=[]
    for name in SEGMENTS:
        run_segment(name,mode,output,provider,selected)
    write_new(output/'SELECTION.json',dict(selected_confirmed=selected,
        max_selected=8,actual_http=provider.attempts if provider else 0,
        peak_charge_upper_usd=provider.spent_upper if provider else 0))


if __name__=='__main__':
    if len(sys.argv)!=2 or sys.argv[1] not in ('dry','preflight','real'):
        raise SystemExit('usage: replay.py dry|preflight|real')
    main(sys.argv[1])
