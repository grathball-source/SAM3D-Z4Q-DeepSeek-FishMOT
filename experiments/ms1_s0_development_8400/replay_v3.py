"""Three full, independent state replays; API sees only causal geometry packets."""
import copy
import gzip
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'online/closed_loop_2888/z4q_source'))
from bridge import Bridge,read,rows,stream,sha  # noqa: E402
from event_packet import packet,render_images,token_map  # noqa: E402
from merge_split_manager_v3 import GroupBridge,MergeSplitManager,choice_mapping,numeric_choice  # noqa: E402
from provider import Provider,PER_SLOT_USD,append,write_new  # noqa: E402
from source_scan import OBS,ASSIGN  # noqa: E402

PROFILES=Path('E:/CAU/D-MOT/tools/sam3_depth_birth_inherit_20260917/completion_evidence/features_r2/features_development.jsonl.gz')
ARCHIVED=Path('E:/CAU/D-MOT/tools/sam3_depth_return_guard_20260918/completion_evidence/experiment/predictions_development.jsonl.gz')
SCAN=HERE/'private_source/scan_v3.json'


def no_truth(event,args):
    if event=='open' and args:
        name=str(args[0]).lower().replace('\\','/')
        if any(x in name for x in ('truth.jsonl','offline_matches','gt_grid','test_gt')):
            raise RuntimeError('GT_DENIED_BEFORE_PREDICTION_SEAL')


def load_sources():
    source=list(stream(OBS,PROFILES,8400,1))
    assignments={r['frame']:r for r in rows(ASSIGN)}
    assert len(assignments)==8400
    tokens=token_map([r for r,_ in source])
    scan=read(SCAN)
    suspects={x['frame']:x for x in scan['suspects']}
    assert len(suspects)==len(scan['suspects'])
    return source,assignments,tokens,suspects


def output_ids(row,ids):
    result=[dict(id=ids[x['id']],mask=x['mask']) for x in row['native']]
    assert len(result)==len(row['native'])==len({x['id'] for x in result})
    return result


def source_manifest(config,scan):
    source={str(p):dict(bytes=p.stat().st_size,sha256=sha(p))
            for p in (OBS,PROFILES,ARCHIVED,ASSIGN,SCAN)}
    return dict(review_base=config['review_base'],inputs=source,frames=8400,
                candidate_suspects=len(scan['suspects']),
                selection='first qualifying episode in confirmation order, prediction masks only, no GT',
                exposure='EXPOSED_DEVELOPMENT_NOT_BLIND')


def freeze_bindings(output,episode,stage,body,tokens,images):
    inverse={value:key for key,value in tokens.items()}
    facts=sorted(set(re.findall(r'F\d+:O\d+',body['user'])))
    bindings={fact:dict(frame=inverse[fact][0],source=inverse[fact][1],
                        mask=f'n:{inverse[fact][1]}') for fact in facts}
    write_new(output/'private_api'/f'{episode["id"]}-{stage}.bindings.json',
              dict(stage=stage,evidence_cutoff=episode['confirm_frame'] if stage=='M' else episode['q'],
                   token_to_actual_source=bindings,
                   images=[dict(frame=x['frame'],sha256=x['sha256'],bindings=x['bindings']) for x in images]))


def publish_once(predictions, ledger, pred, already_published, frame_received_monotonic,
                 event_publish=None):
    """The sole public write point; preview never reaches this handle."""
    frame=pred['frame']
    assert frame not in already_published
    raw=json.dumps(pred,separators=(',',':'))+'\n'
    predictions.write(raw)
    if event_publish:
        predictions.flush()
    published=time.monotonic()
    already_published.add(frame)
    ledger.write(json.dumps(dict(frame=frame,global_frame=pred['global_frame'],
        first_publish_time_monotonic=published,
        frame_received_monotonic=frame_received_monotonic,
        receive_to_publish_seconds=published-frame_received_monotonic,
        prediction_row_sha256=hashlib.sha256(raw.encode()).hexdigest(),
        event_publish=event_publish),separators=(',',':'))+'\n')
    return published


def run(mode):
    assert mode in ('dry','real')
    config=read(HERE/'CONFIG_V3.json')
    source,assignments,tokens,suspects=load_sources()
    scan=read(SCAN)
    output=HERE/('dry_run_v3' if mode=='dry' else 'run_development_v3_paid')
    assert not output.exists(),output
    output.mkdir()
    public=output/'public'
    public.mkdir()
    manifest=source_manifest(config,scan)
    write_new(public/'SOURCE_MANIFEST.json',manifest)
    if mode=='real':
        assert config['paid_authorization']=='USER_APPROVED_NEW_BATCH'
        assert os.environ.get('DEEPSEEK_API_KEY')
        assert config['max_inference_http']*PER_SLOT_USD<=config['budget_usd']
        code={p.name:sha(p) for p in (HERE/'mask_geometry.py',HERE/'source_scan.py',
              HERE/'merge_split_manager.py',HERE/'event_packet.py',HERE/'provider.py',
              HERE/'replay_v3.py',HERE/'score.py',HERE/'CONFIG_V3.json',
              HERE/'MS1_MODEL_PROMPTS.md')}
        write_new(public/'FREEZE.json',dict(status='FROZEN_BEFORE_FIRST_REQUEST',at=time.time(),
            review_base=config['review_base'],code_sha256=code,source_sha256=manifest['inputs'],
            max_http=config['max_inference_http'],max_paid_episodes=config['max_paid_episodes'],
            budget_usd=config['budget_usd'],slot_reserve_peak_usd=PER_SLOT_USD,
            full_slot_reserve_peak_usd=config['max_inference_http']*PER_SLOT_USD,
            pricing_url='https://api-docs.deepseek.com/quick_start/pricing/',
            model='deepseek-flash',output_tokens_per_request_max=65536,
            scoring_gate='postseal original TrackEval; q first split physical mapping and pre fragment consensus separate',
            trigger_gate='prediction-only local area/mask V2 scanner; live two-frame confirmation and q'))
    b0=Bridge(read(ROOT/'online/closed_loop_2888/z4q_source/CONFIG.json'))
    hold=GroupBridge(read(ROOT/'online/closed_loop_2888/z4q_source/CONFIG.json'))
    vlm=GroupBridge(read(ROOT/'online/closed_loop_2888/z4q_source/CONFIG.json'))
    mh=MergeSplitManager('B-HOLD-S0',hold,suspects,config,assignments)
    mv=MergeSplitManager('B-VLM-S0',vlm,suspects,config,assignments)
    provider=Provider(output,config) if mode=='real' else None
    selected=[]
    spent_start=time.monotonic()
    predictions=gzip.open(public/'predictions_development.jsonl.gz','wt',encoding='utf-8')
    transactions=gzip.open(public/'TRANSACTIONS.jsonl.gz','wt',encoding='utf-8')
    publish_ledger=(public/'PUBLISH_LEDGER.jsonl').open('x',encoding='utf-8')
    published_frames=set()
    archived=rows(ARCHIVED)
    try:
        sys.addaudithook(no_truth)
        for (row,profiles),baseline in zip(source,archived,strict=True):
            frame_received=time.monotonic()
            frame,now=row['frame'],row['time']
            view0=b0.preview(frame,now,row['observations'],profiles)
            ids0,_=b0.commit_once(view0)
            assert output_ids(row,ids0)==baseline['variants']['Z4Q_STABLE'],frame
            views={}
            records={}
            for name,bridge,manager in (('B-HOLD-S0',hold,mh),('B-VLM-S0',vlm,mv)):
                detection=manager.before(row,profiles)
                view=bridge.preview(frame,now,row['observations'],profiles)
                views[name]=view
                records[name]=dict(frame=frame,kind=detection,status='NATIVE')
            e=mv.active
            if e and e['confirm_frame']==frame and e['id'] not in selected and len(selected)<config['max_paid_episodes']:
                selected.append(e['id'])
                e['model_selected']=True
                mh.active['model_selected']=False
                images=render_images(e,'M',assignments,tokens,output/'private_source/geometry')
                body=packet(e,'M',tokens,images,assignments)
                freeze_bindings(output,e,'M',body,tokens,images)
                if mode=='real':
                    _,status,response=provider.infer(e,'M',body,images)
                    e['M_status']=status
                    e['M_hypothesis']=response['content'] if response and status=='OK' else None
                else:
                    e['M_status']='DRY_NO_API'
                    e['M_hypothesis']=None
                    write_new(public/'dry_packets'/f'{e["id"]}-M.json',body)
                records['B-VLM-S0']['M_status']=e['M_status']
            branches={}
            for name,bridge,manager in (('B-HOLD-S0',hold,mh),('B-VLM-S0',vlm,mv)):
                view=views[name]
                e=manager.active
                transaction=None
                if e and e['q']==frame:
                    assert e['split_first_frame']==frame and all(len(x)==1 for x in e['post_roles'].values())
                    packet_state={k:v for k,v in e.items() if k not in ('bank_snapshot','temporary_ids')}
                    write_new(output/'private_source'/f'{e["id"]}-{name}-episode_q.json',packet_state)
                    numeric,detail=numeric_choice(e)
                    e['numeric']=dict(choice=numeric,detail=detail)
                    choice=numeric
                    raw_choice=None
                    parse_status=None
                    if name=='B-VLM-S0' and e['id'] in selected:
                        images=render_images(e,'S0',assignments,tokens,output/'private_source/geometry')
                        body=packet(e,'S0',tokens,images,assignments,e.get('M_hypothesis'))
                        freeze_bindings(output,e,'S0',body,tokens,images)
                        if mode=='real':
                            raw_choice,parse_status,response=provider.infer(e,'S0',body,images)
                        else:
                            raw_choice,parse_status,response='DEFER','DRY_DEFER',None
                            write_new(public/'dry_packets'/f'{e["id"]}-S0.json',body)
                        if raw_choice in ('H1','H2'):
                            choice=raw_choice
                    e['S_raw_choice']=raw_choice
                    e['S_parse_status']=parse_status
                    mapping=choice_mapping(e,choice) if choice in ('H1','H2') else None
                    if mapping:
                        transaction,error=bridge.stage_group_restore(view,e,mapping)
                        status='COMMIT' if transaction and transaction['changes'] else 'RESOLVE_NO_ID_CHANGE' if transaction else 'STAGE_REJECTED'
                    else:
                        error='numeric_unresolved'
                        status='UNRESOLVED'
                    if transaction is None:
                        # Only this group's lock is released; unrelated state already advanced in view.
                        view['engine'].protected.pop(e['id'],None)
                    e['restore']=dict(status=status,selected_choice=choice,raw_choice=raw_choice,
                                      parse_status=parse_status,stage_error=error,
                                      mapping=mapping,changes=transaction['changes'] if transaction else None,
                                      decision_source=('MODEL' if raw_choice in ('H1','H2') and transaction else
                                                       'MODEL_DEFER_NUMERIC_FALLBACK' if raw_choice=='DEFER' else
                                                       'NUMERIC' if name=='B-HOLD-S0' else 'NUMERIC_FALLBACK'))
                    records[name]['restore']=copy.deepcopy(e['restore'])
                    manager.finish(frame,status)
                ids,trace=bridge.commit_once(view,transaction)
                manager.after(row,profiles)
                branches[name]=output_ids(row,ids)
                records[name]['status']=e['restore']['status'] if e and e.get('q')==frame else \
                    (records[name]['kind'] or {}).get('kind','NATIVE')
                records[name]['changes']=None if transaction is None else transaction['changes']
                records[name]['protected_ids_preserved']=bool(e and e['id'] in bridge.engine.protected and
                    all(k in bridge.engine.bank for k in e['public_ids']))
            meta=dict(frame=frame,global_frame=row['global_frame'],time=now)
            pred=dict(meta,variants={'B0':output_ids(row,ids0),**branches})
            assert [x['mask'] for x in pred['variants']['B0']]==[x['mask'] for x in branches['B-HOLD-S0']]==[x['mask'] for x in branches['B-VLM-S0']]
            event_publish={}
            for name,manager in (('B-HOLD-S0',mh),('B-VLM-S0',mv)):
                e=next((x for x in manager.events if x['q']==frame),None)
                if e:
                    actual={int(x['mask'].split(':')[1]):x['id'] for x in pred['variants'][name]}
                    event_publish[name]=dict(episode=e['id'],evidence_cutoff_frame=frame,
                        post_sample_count=1,decision_source=e['restore']['decision_source'],
                        first_public_pair={role:dict(fact_id=tokens[(frame,n)],public_id=actual.get(n))
                            for role,n in zip(('X','Y'),e['post_roles'])})
            publish_once(predictions,publish_ledger,pred,published_frames,frame_received,event_publish or None)
            transactions.write(json.dumps(dict(meta,branches=records),separators=(',',':'))+'\n')
            if frame%500==0:
                print('FRAME',frame,'selected',len(selected),'HTTP',provider.attempts if provider else 0,flush=True)
    finally:
        predictions.close()
        transactions.close()
        publish_ledger.close()
    def safe_event(e):
        fields=('id','suspect_frame','confirm_frame','post_start','split_first_frame',
                'evidence_cutoff_frame','split_confirm','q','end','status',
                'model_selected','M_status','S_raw_choice','S_parse_status','numeric','restore')
        return {k:copy.deepcopy(e.get(k)) for k in fields}
    events={'B-HOLD-S0':[safe_event(x) for x in mh.events],
            'B-VLM-S0':[safe_event(x) for x in mv.events]}
    write_new(public/'EVENTS.json',events)
    if provider:
        attempts,upper=provider.attempts,provider.spent_upper
    else:
        attempts,upper=0,0.
    ledger=public/'CALL_LEDGER.jsonl'
    if not ledger.exists():
        ledger.write_text('',encoding='utf-8')
    seal=dict(status='SEALED_AWAITING_INDEPENDENT_SCORING',frames=8400,mode=mode,
              selected_episodes=selected,http_attempts=attempts,peak_charge_upper_usd=upper,
              wall_seconds=time.monotonic()-spent_start,
              predictions_sha256=sha(public/'predictions_development.jsonl.gz'),
              transactions_sha256=sha(public/'TRANSACTIONS.jsonl.gz'),
              events_sha256=sha(public/'EVENTS.json'),call_ledger_sha256=sha(ledger),
              publish_ledger_sha256=sha(public/'PUBLISH_LEDGER.jsonl'),
              published_frames=len(published_frames))
    write_new(public/'PREDICTIONS_SEALED.json',seal)
    print('SEALED',json.dumps(dict(frames=8400,selected=selected,http=attempts,upper_usd=upper,
                                    events=events),ensure_ascii=False),flush=True)


if __name__=='__main__':
    if len(sys.argv)!=2 or sys.argv[1] not in ('dry','real'):
        raise SystemExit('usage: replay.py dry|real')
    run(sys.argv[1])
