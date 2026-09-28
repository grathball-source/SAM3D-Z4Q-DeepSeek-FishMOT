"""Full development S0 replay with the frozen scanner's zero eligible events."""
import gzip
import hashlib
import json
import os
import sys
import time
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'online/closed_loop_2888/z4q_source'))
from bridge import Bridge,read,rows,stream,sha  # noqa: E402
from merge_split_manager import GroupBridge,MergeSplitManager  # noqa: E402
from source_scan import ASSIGN,OBS  # noqa: E402

PROFILES=Path('E:/CAU/D-MOT/tools/sam3_depth_birth_inherit_20260917/completion_evidence/features_r2/features_development.jsonl.gz')
ARCHIVED=Path('E:/CAU/D-MOT/tools/sam3_depth_return_guard_20260918/completion_evidence/experiment/predictions_development.jsonl.gz')
SCAN=HERE/'private_source/scan.json'
OUT=HERE/'run_development_8400'


def write_new(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as handle:
        json.dump(value,handle,ensure_ascii=False,separators=(',',':'))
        handle.write('\n')
        handle.flush()
        os.fsync(handle.fileno())


def no_truth(event,args):
    if event=='open' and args:
        name=str(args[0]).lower().replace('\\','/')
        if any(word in name for word in ('truth.jsonl','offline_matches','gt_grid','test_gt')):
            raise RuntimeError('GT_DENIED_BEFORE_PREDICTION_SEAL')


def output_ids(row,ids):
    out=[dict(id=ids[x['id']],mask=x['mask']) for x in row['native']]
    assert len(out)==len(row['native'])==len({x['id'] for x in out})
    return out


def publish_once(handle,ledger,row,seen,received):
    frame=row['frame']
    assert frame not in seen
    raw=json.dumps(row,separators=(',',':'))+'\n'
    handle.write(raw)
    stamp=time.monotonic()
    seen.add(frame)
    ledger.write(json.dumps(dict(frame=frame,first_publish_time_monotonic=stamp,
        frame_received_monotonic=received,receive_to_publish_seconds=stamp-received,
        prediction_row_sha256=hashlib.sha256(raw.encode()).hexdigest(),
        event_publish=None),separators=(',',':'))+'\n')


def run():
    config=read(HERE/'CONFIG.json')
    assert config['frames']==8400 and config['global_start']==1
    assert config['max_paid_episodes']==config['max_inference_http']==config['budget_usd']==0
    scan=read(SCAN)
    assert scan['suspects']==[], 'fresh authority is required for paid events'
    assert not OUT.exists(),OUT
    inputs={str(p):dict(bytes=p.stat().st_size,sha256=sha(p))
            for p in (OBS,PROFILES,ARCHIVED,ASSIGN,SCAN)}
    source=list(stream(OBS,PROFILES,8400,1))
    assignments={r['frame']:r for r in rows(ASSIGN)}
    assert len(source)==len(assignments)==8400
    OUT.mkdir()
    public=OUT/'public'
    public.mkdir()
    write_new(public/'SOURCE_MANIFEST.json',dict(review_base=config['review_base'],
        split='development',frames=8400,inputs=inputs,
        selection='unchanged strict prediction-mask two-to-one scan; zero qualified suspects; no GT'))
    code={p.name:sha(p) for p in (HERE/'CONFIG.json',HERE/'source_scan.py',
        HERE/'mask_geometry.py',HERE/'merge_split_manager.py',HERE/'replay.py')}
    write_new(public/'FREEZE.json',dict(status='PREDICTION_CODE_AND_SOURCE_FROZEN_BEFORE_REPLAY',
        at=time.time(),code_sha256=code,source_sha256=inputs,
        selected_suspects=0,max_inference_http=0,budget_usd=0,
        model_route='NOT_ENTERED_NO_ELIGIBLE_TRIGGER'))
    bridge_config=read(ROOT/'online/closed_loop_2888/z4q_source/CONFIG.json')
    branches={'B0':Bridge(bridge_config),
              'B-HOLD-S0':GroupBridge(bridge_config),
              'B-VLM-S0':GroupBridge(bridge_config)}
    managers={name:MergeSplitManager(name,branches[name],{},config,assignments)
              for name in ('B-HOLD-S0','B-VLM-S0')}
    predictions=gzip.open(public/'predictions_development.jsonl.gz','wt',encoding='utf-8')
    transactions=gzip.open(public/'TRANSACTIONS.jsonl.gz','wt',encoding='utf-8')
    publisher=(public/'PUBLISH_LEDGER.jsonl').open('x',encoding='utf-8')
    seen=set()
    started=time.monotonic()
    try:
        sys.addaudithook(no_truth)
        for (row,profiles),archived in zip(source,rows(ARCHIVED),strict=True):
            received=time.monotonic()
            frame,now=row['frame'],row['time']
            assert frame==row['global_frame']==archived['frame']==archived['global_frame']
            assert {k for k in assignments[frame]['masks'] if k.startswith('n:')}=={
                x['mask'] for x in row['native']}
            outputs={}
            records={}
            for name,bridge in branches.items():
                manager=managers.get(name)
                detection=manager.before(row,profiles) if manager else None
                assert detection is None and (manager is None or manager.active is None)
                view=bridge.preview(frame,now,row['observations'],profiles)
                ids,_=bridge.commit_once(view)
                if manager:
                    manager.after(row,profiles)
                outputs[name]=output_ids(row,ids)
                records[name]=dict(detection=detection,version=bridge.version,
                                   protected_count=len(getattr(bridge.engine,'protected',{})))
            assert outputs['B0']==archived['variants']['Z4Q_STABLE'],frame
            assert outputs['B0']==outputs['B-HOLD-S0']==outputs['B-VLM-S0'],frame
            pred=dict(frame=frame,global_frame=frame,time=now,variants=outputs)
            publish_once(predictions,publisher,pred,seen,received)
            transactions.write(json.dumps(dict(frame=frame,branches=records),separators=(',',':'))+'\n')
            if frame%1000==0:
                print('FRAME',frame,'eligible',0,'inference_http',0,flush=True)
    finally:
        predictions.close()
        transactions.close()
        publisher.close()
    assert seen==set(range(1,8401))
    events={name:[] for name in managers}
    write_new(public/'EVENTS.json',events)
    (public/'CALL_LEDGER.jsonl').write_text('',encoding='utf-8')
    write_new(public/'TRIGGER_COVERAGE.json',dict(frames=8400,eligible_events=0,
        count_drop_transitions=scan['transitions'],
        lost_or_out_of_scope=scan['diagnostics'],
        no_gt_trigger_selection=True,
        interpretation='Zero qualified triggers does not mean no physical merge events.'))
    seal=dict(status='SEALED_AWAITING_INDEPENDENT_SCORING',split='development',
        frames=8400,mode='development_no_eligible_event',http_attempts=0,
        model_choices=0,selected_episodes=[],wall_seconds=time.monotonic()-started,
        predictions_sha256=sha(public/'predictions_development.jsonl.gz'),
        transactions_sha256=sha(public/'TRANSACTIONS.jsonl.gz'),
        events_sha256=sha(public/'EVENTS.json'),
        call_ledger_sha256=sha(public/'CALL_LEDGER.jsonl'),
        publish_ledger_sha256=sha(public/'PUBLISH_LEDGER.jsonl'),
        published_frames=len(seen))
    write_new(public/'PREDICTIONS_SEALED.json',seal)
    print('SEALED',json.dumps(dict(frames=8400,eligible_events=0,http_attempts=0,
        prediction_sha256=seal['predictions_sha256'])),flush=True)


if __name__=='__main__':
    run()
