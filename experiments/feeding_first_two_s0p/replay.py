"""Three independent causal S0-P replays on two FEEDING source segments."""
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
OLD = ROOT / 'experiments/ms1_s0_development_8400'
P = ROOT / 'experiments/s0p_identity_publication'
sys.path[:0] = [str(P), str(OLD), str(ROOT/'online/closed_loop_2888/z4q_source')]
from bridge import Bridge, read, rows, sha, stream  # noqa: E402
import event_packet  # noqa: E402
from event_packet import packet, render_images, token_map  # noqa: E402
from manager_p import GroupBridgeP, MergeSplitManagerP  # noqa: E402
from merge_split_manager import choice_mapping, numeric_choice  # noqa: E402
from provider_v7 import Provider, PER_SLOT_USD  # noqa: E402
from prepare import SEGMENTS, write_new  # noqa: E402

CONFIG_PATH = ROOT/'online/closed_loop_2888/z4q_source/CONFIG.json'
V7_CONFIG = OLD/'CONFIG_V7.json'
CODE = (HERE/'prepare.py', HERE/'scan.py', HERE/'replay.py', HERE/'score.py',
        OLD/'merge_split_manager.py', OLD/'source_scan_v4.py', OLD/'event_packet.py',
        OLD/'provider_v7.py', OLD/'MS1_MODEL_PROMPTS.md', P/'manager_p.py',
        ROOT/'online/closed_loop_2888/z4q_source/bridge.py', CONFIG_PATH, V7_CONFIG)
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
            'publication_policy','M_status','S_raw_choice','S_parse_status')
    return {key:copy.deepcopy(event.get(key)) for key in keys}


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


def freeze_all(mode):
    assert mode in ('dry','real')
    output = HERE/('dry_v2' if mode=='dry' else 'run')
    assert not output.exists(), output
    if mode == 'real':
        assert os.environ.get('DEEPSEEK_API_KEY'), 'DEEPSEEK_API_KEY missing'
    output.mkdir()
    code_hashes = {str(path):sha(path) for path in CODE}
    for name,(start,stop) in SEGMENTS.items():
        private = HERE/'private'/name
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
            model_selection='all live two-frame confirmed episodes; M once at confirmation, S0 once at first split',
            max_inference_http=2*unique_frames if mode=='real' else 0,
            per_request_peak_reserve_usd=PER_SLOT_USD if mode=='real' else 0,
            no_rgb_no_gt_before_seal=True,model='deepseek-flash' if mode=='real' else None,
            decision='S0 before first current-frame publication; invalid/DEFER uses same HOLD numeric fallback',
            source_limitation='saved batched SAM3 raw polygons, not a continuous SAM3 tracking session'))
    return output


def run_segment(name, mode, output, send_enabled):
    start,stop=SEGMENTS[name]
    private=HERE/'private'/name
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
    hold=GroupBridgeP(read(CONFIG_PATH))
    vlm=GroupBridgeP(read(CONFIG_PATH))
    mh=MergeSplitManagerP('B-HOLD-S0-P',hold,suspects,config,assignment)
    mv=MergeSplitManagerP('B-VLM-S0-P',vlm,suspects,config,assignment)
    provider=None
    if mode=='real':
        provider_config=dict(config,max_inference_http=2*len(suspects),budget_usd=None)
        provider=Provider(output/name,provider_config)
        provider.send_enabled=send_enabled
    selected=[]
    began=time.monotonic()
    with gzip.open(public/'predictions.jsonl.gz','wt',encoding='utf-8') as pred_file, \
         gzip.open(public/'TRANSACTIONS.jsonl.gz','wt',encoding='utf-8') as txn_file, \
         (public/'PUBLISH_LEDGER.jsonl').open('x',encoding='utf-8') as publish_file:
        for row,profiles in source:
            received=time.monotonic()
            frame,now=row['frame'],row['time']
            v0=b0.preview(frame,now,row['observations'],profiles)
            ids0,_=b0.commit_once(v0)
            branch={}
            for arm,bridge,manager in (('B-HOLD',hold,mh),('B-VLM',vlm,mv)):
                signal=manager.before(row,profiles)
                view=bridge.preview(frame,now,row['observations'],profiles)
                episode=manager.active
                if arm=='B-VLM' and episode and episode['confirm_frame']==frame:
                    selected.append(episode['id'])
                    episode['model_selected']=True
                    if mode=='real':
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
                    if arm=='B-VLM' and episode.get('model_selected') and not residual:
                        if mode=='real':
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
                                         'NUMERIC' if arm=='B-HOLD' else 'NUMERIC_FALLBACK')
                    restore=dict(status=status,numeric_choice=numeric,selected_choice=choice,
                                 raw_choice=raw_choice,parse_status=parse_status,
                                 mapping=mapping,unassigned_member_residual=residual,
                                 changes=transaction['changes'],
                                 stage_error=error,decision_source=decision_source,fallback=fallback)
                    episode['restore']=restore
                    manager.finish(frame,status)
                ids,trace=bridge.commit_once(view,transaction)
                manager.after(row,profiles)
                branch[arm]=emit(row,ids)
                txn_file.write(json.dumps(dict(frame=frame,global_frame=row['global_frame'],
                    arm=arm,signal=signal,active_event=episode['id'] if episode else None,
                    restore=restore,actual_published_mapping=ids,
                    internal_token_state=trace.get('merge_split_group')),
                    ensure_ascii=False,separators=(',',':'),default=str)+'\n')
            result=dict(frame=frame,global_frame=row['global_frame'],time=now,
                        variants={'B0':emit(row,ids0),**branch})
            assert all([item['mask'] for item in value]==[item['mask'] for item in result['variants']['B0']]
                       for value in branch.values())
            line=json.dumps(result,separators=(',',':'),allow_nan=False)+'\n'
            pred_file.write(line)
            event_publish={}
            for arm,manager,objects in (('B-HOLD',mh,branch['B-HOLD']),
                                        ('B-VLM',mv,branch['B-VLM'])):
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
    write_new(public/'EVENTS.json',dict(B_HOLD=[public_event(e) for e in mh.events],
                                         B_VLM=[public_event(e) for e in mv.events],
                                         selected_confirmed=selected))
    call_ledger=public/'CALL_LEDGER.jsonl'
    if not call_ledger.exists():
        call_ledger.write_text('',encoding='utf-8')
    seal=dict(status='SEALED_AWAITING_INDEPENDENT_SCORING',segment=name,
              original_frames=[start,stop],frames=len(source),published_frames=len(source),
              mode=mode,model='deepseek-flash' if mode=='real' else None,
              http_attempts=provider.attempts if provider else 0,
              peak_charge_upper_usd=provider.spent_upper if provider else 0,
              send_enabled_at_end=provider.send_enabled if provider else False,
              selected_confirmed=selected,wall_seconds=time.monotonic()-began,
              predictions_sha256=sha(public/'predictions.jsonl.gz'),
              transactions_sha256=sha(public/'TRANSACTIONS.jsonl.gz'),
              publish_ledger_sha256=sha(public/'PUBLISH_LEDGER.jsonl'),
              events_sha256=sha(public/'EVENTS.json'),
              call_ledger_sha256=sha(call_ledger),freeze_sha256=sha(public/'FREEZE.json'))
    write_new(public/'PREDICTIONS_SEALED.json',seal)
    print(name,'SEALED',json.dumps(dict(frames=seal['frames'],events=len(mv.events),
                                        http_attempts=seal['http_attempts'],
                                        charge_upper=seal['peak_charge_upper_usd'])),flush=True)
    return seal['send_enabled_at_end'] if provider else send_enabled


def main(mode):
    output=freeze_all(mode)
    send_enabled=True
    for name in SEGMENTS:
        send_enabled=run_segment(name,mode,output,send_enabled)


if __name__=='__main__':
    if len(sys.argv)!=2 or sys.argv[1] not in ('dry','real'):
        raise SystemExit('usage: replay.py dry|real')
    main(sys.argv[1])
