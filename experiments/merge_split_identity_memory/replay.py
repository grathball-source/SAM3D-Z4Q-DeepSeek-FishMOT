"""Three full, independent state replays; API sees only causal geometry packets."""
import copy
import gzip
import hashlib
import json
import os
import sys
import time
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'online/closed_loop_2888'))
from preflight import OBS,PROFILES,ARCHIVED  # noqa: E402
sys.path.insert(0,str(ROOT/'online/closed_loop_2888/z4q_source'))
from bridge import Bridge,read,rows,stream,sha  # noqa: E402
from event_packet import packet,render_images,token_map  # noqa: E402
from merge_split_manager import GroupBridge,MergeSplitManager,choice_mapping,numeric_choice  # noqa: E402
from provider import Provider,PER_SLOT_USD,append,write_new  # noqa: E402


def no_truth(event,args):
    if event=='open' and args:
        name=str(args[0]).lower().replace('\\','/')
        if any(x in name for x in ('truth.jsonl','offline_matches','gt_grid','test_gt')):
            raise RuntimeError('GT_DENIED_BEFORE_PREDICTION_SEAL')


def load_sources():
    source=list(stream(OBS,PROFILES,2888,9301))
    assignments={r['frame']:r for r in rows(HERE/'private_source/assignments.jsonl.gz')}
    assert len(assignments)==2888
    tokens=token_map([r for r,_ in source])
    scan=read(HERE/'private_source/scan.json')
    suspects={x['frame']:x for x in scan['suspects']}
    return source,assignments,tokens,suspects


def output_ids(row,ids):
    result=[dict(id=ids[x['id']],mask=x['mask']) for x in row['native']]
    assert len(result)==len(row['native'])==len({x['id'] for x in result})
    return result


def source_manifest(config,scan):
    source={str(p):dict(bytes=p.stat().st_size,sha256=sha(p))
            for p in (OBS,PROFILES,ARCHIVED,HERE/'private_source/assignments.jsonl.gz',
                      HERE/'private_source/scan.json')}
    return dict(review_base=config['review_base'],inputs=source,frames=2888,
                candidate_suspects=len(scan['suspects']),
                selection='first eight qualifying episodes in confirmation order, no GT',
                exposure='EXPOSED_VALIDATION_NOT_BLIND')


def run(mode):
    assert mode in ('dry','real')
    config=read(HERE/'CONFIG.json')
    source,assignments,tokens,suspects=load_sources()
    scan=read(HERE/'private_source/scan.json')
    output=HERE/('dry_run' if mode=='dry' else 'run_ms1_20260928')
    assert not output.exists(),output
    output.mkdir()
    public=output/'public'
    public.mkdir()
    manifest=source_manifest(config,scan)
    write_new(public/'SOURCE_MANIFEST.json',manifest)
    if mode=='real':
        assert os.environ.get('DEEPSEEK_API_KEY')
        assert 16*PER_SLOT_USD<=config['budget_usd']
        code={p.name:sha(p) for p in (HERE/'mask_geometry.py',HERE/'source_scan.py',
              HERE/'merge_split_manager.py',HERE/'event_packet.py',HERE/'provider.py',
              HERE/'replay.py',HERE/'CONFIG.json',HERE/'MS1_MODEL_PROMPTS.md')}
        write_new(public/'FREEZE.json',dict(status='FROZEN_BEFORE_FIRST_REQUEST',at=time.time(),
            review_base=config['review_base'],code_sha256=code,source_sha256=manifest['inputs'],
            max_http=config['max_inference_http'],max_paid_episodes=config['max_paid_episodes'],
            budget_usd=config['budget_usd'],slot_reserve_peak_usd=PER_SLOT_USD,
            full_16_slot_reserve_peak_usd=16*PER_SLOT_USD,
            pricing_url='https://api-docs.deepseek.com/quick_start/pricing/',
            model='deepseek-flash',output_tokens_per_request_max=65536))
    b0=Bridge(read(ROOT/'online/closed_loop_2888/z4q_source/CONFIG.json'))
    hold=GroupBridge(read(ROOT/'online/closed_loop_2888/z4q_source/CONFIG.json'))
    vlm=GroupBridge(read(ROOT/'online/closed_loop_2888/z4q_source/CONFIG.json'))
    mh=MergeSplitManager('B-HOLD',hold,suspects,config,assignments)
    mv=MergeSplitManager('B-VLM',vlm,suspects,config,assignments)
    provider=Provider(output,config) if mode=='real' else None
    selected=[]
    spent_start=time.monotonic()
    predictions=gzip.open(public/'predictions_validation.jsonl.gz','wt',encoding='utf-8')
    transactions=gzip.open(public/'TRANSACTIONS.jsonl.gz','wt',encoding='utf-8')
    archived=rows(ARCHIVED)
    try:
        sys.addaudithook(no_truth)
        for (row,profiles),baseline in zip(source,archived,strict=True):
            frame,now=row['frame'],row['time']
            view0=b0.preview(frame,now,row['observations'],profiles)
            ids0,_=b0.commit_once(view0)
            assert output_ids(row,ids0)==baseline['variants']['Z4Q_STABLE'],frame
            views={}
            records={}
            for name,bridge,manager in (('B-HOLD',hold,mh),('B-VLM',vlm,mv)):
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
                body=packet(e,'M',tokens,images)
                if mode=='real':
                    _,status,response=provider.infer(e,'M',body,images)
                    e['M_status']=status
                    e['M_hypothesis']=response['content'] if response and status=='OK' else None
                else:
                    e['M_status']='DRY_NO_API'
                    e['M_hypothesis']=None
                    write_new(public/'dry_packets'/f'{e["id"]}-M.json',body)
                records['B-VLM']['M_status']=e['M_status']
            branches={}
            for name,bridge,manager in (('B-HOLD',hold,mh),('B-VLM',vlm,mv)):
                view=views[name]
                e=manager.active
                transaction=None
                if e and e['q']==frame:
                    numeric,detail=numeric_choice(e)
                    e['numeric']=dict(choice=numeric,detail=detail)
                    choice=numeric
                    raw_choice=None
                    parse_status=None
                    if name=='B-VLM' and e['id'] in selected:
                        images=render_images(e,'S',assignments,tokens,output/'private_source/geometry')
                        body=packet(e,'S',tokens,images,e.get('M_hypothesis'))
                        if mode=='real':
                            raw_choice,parse_status,response=provider.infer(e,'S',body,images)
                        else:
                            raw_choice,parse_status,response='DEFER','DRY_DEFER',None
                            write_new(public/'dry_packets'/f'{e["id"]}-S.json',body)
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
                                      mapping=mapping,changes=transaction['changes'] if transaction else None)
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
            assert [x['mask'] for x in pred['variants']['B0']]==[x['mask'] for x in branches['B-HOLD']]==[x['mask'] for x in branches['B-VLM']]
            predictions.write(json.dumps(pred,separators=(',',':'))+'\n')
            transactions.write(json.dumps(dict(meta,branches=records),separators=(',',':'))+'\n')
            if frame%500==0:
                print('FRAME',frame,'selected',len(selected),'HTTP',provider.attempts if provider else 0,flush=True)
    finally:
        predictions.close()
        transactions.close()
    def safe_event(e):
        fields=('id','suspect_frame','confirm_frame','post_start','split_confirm','q','end','status',
                'model_selected','M_status','S_raw_choice','S_parse_status','numeric','restore')
        return {k:copy.deepcopy(e.get(k)) for k in fields}
    events={'B-HOLD':[safe_event(x) for x in mh.events],
            'B-VLM':[safe_event(x) for x in mv.events]}
    write_new(public/'EVENTS.json',events)
    if provider:
        attempts,upper=provider.attempts,provider.spent_upper
    else:
        attempts,upper=0,0.
    ledger=public/'CALL_LEDGER.jsonl'
    if not ledger.exists():
        ledger.write_text('',encoding='utf-8')
    seal=dict(status='SEALED_AWAITING_INDEPENDENT_SCORING',frames=2888,mode=mode,
              selected_episodes=selected,http_attempts=attempts,peak_charge_upper_usd=upper,
              wall_seconds=time.monotonic()-spent_start,
              predictions_sha256=sha(public/'predictions_validation.jsonl.gz'),
              transactions_sha256=sha(public/'TRANSACTIONS.jsonl.gz'),
              events_sha256=sha(public/'EVENTS.json'),call_ledger_sha256=sha(ledger))
    write_new(public/'PREDICTIONS_SEALED.json',seal)
    print('SEALED',json.dumps(dict(frames=2888,selected=selected,http=attempts,upper_usd=upper,
                                    events=events),ensure_ascii=False),flush=True)


if __name__=='__main__':
    if len(sys.argv)!=2 or sys.argv[1] not in ('dry','real'):
        raise SystemExit('usage: replay.py dry|real')
    run(sys.argv[1])
