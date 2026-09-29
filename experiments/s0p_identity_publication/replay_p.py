"""Independent 8400-frame B0/HOLD-P replay; no model transport is imported."""
import copy
import gzip
import hashlib
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OLD = ROOT/'experiments/ms1_s0_development_8400'
sys.path.insert(0, str(OLD))
sys.path.insert(0, str(ROOT/'online/closed_loop_2888/z4q_source'))

from bridge import Bridge, read, rows, sha, stream  # noqa: E402
from source_scan import OBS, ASSIGN  # noqa: E402
from merge_split_manager import choice_mapping, numeric_choice  # noqa: E402
from manager_p import GroupBridgeP, MergeSplitManagerP  # noqa: E402

PROFILES = Path('E:/CAU/D-MOT/tools/sam3_depth_birth_inherit_20260917/completion_evidence/features_r2/features_development.jsonl.gz')
ARCHIVED = Path('E:/CAU/D-MOT/tools/sam3_depth_return_guard_20260918/completion_evidence/experiment/predictions_development.jsonl.gz')
SCAN = OLD/'private_source/scan_v4.json'
OUT = HERE/'run_8400_v2/public'


def write_new(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write('\n')


def emit(row, mapping):
    result = [dict(id=mapping[x['id']], mask=x['mask']) for x in row['native']]
    assert len(result) == len(row['native']) == len(set(x['id'] for x in result))
    return result


def no_truth(event, args):
    if event == 'open' and args:
        name = str(args[0]).lower().replace('\\', '/')
        if any(x in name for x in ('truth.jsonl', 'offline_matches', 'gt_grid', 'test_gt')):
            raise RuntimeError('GT_DENIED_BEFORE_PREDICTION_SEAL')


def snapshot_outside(bridge, episode, observed):
    if not episode:
        return None
    event_native = set(episode['member_sources']) | set(episode['post_roles']) | {episode['group_source']}
    outside_native = set(observed) - event_native
    outside_public = {bridge.previous[n] for n in outside_native if n in bridge.previous and bridge.previous[n]>=0}
    return dict(native={name:{n:copy.deepcopy(getattr(bridge.engine,name).get(n)) for n in outside_native}
                              for name in ('alias','pending','native_runs','native_seen','recent_core')},
                public={name:{k:copy.deepcopy(getattr(bridge.engine,name).get(k)) for k in outside_public}
                               for name in ('bank','view_bank')},
                epochs={n:bridge.epochs.get(n) for n in outside_native},
                provenance={n:copy.deepcopy(bridge.provenance.get(n)) for n in outside_native},
                previous={n:bridge.previous.get(n) for n in outside_native})


def run():
    assert not OUT.exists(), OUT
    config=read(OLD/'CONFIG_V7.json')
    own=read(HERE/'CONFIG.json')
    assert own['review_base']=='9eca43e8ee35bbbc2949bcefb5ddbc653361d666'
    source_paths=(OBS,PROFILES,ARCHIVED,ASSIGN,SCAN,OLD/'CONFIG_V7.json')
    manifest={str(p):dict(bytes=p.stat().st_size,sha256=sha(p)) for p in source_paths}
    old_public=OLD/'run_development_v7_recovery/public'
    old_seal=read(old_public/'PREDICTIONS_SEALED.json')
    assert old_seal['frames']==8400 and sha(old_public/'predictions_development.jsonl.gz')==old_seal['predictions_sha256']
    OUT.mkdir(parents=True)
    code=(HERE/'manager_p.py',HERE/'replay_p.py',HERE/'CONFIG.json',OLD/'merge_split_manager.py',
          OLD/'source_scan.py',ROOT/'online/closed_loop_2888/z4q_source/bridge.py')
    write_new(OUT/'FREEZE.json',dict(status='FROZEN_BEFORE_REPLAY',review_base=own['review_base'],
        source=manifest,code_sha256={str(p):sha(p) for p in code},
        old_hold_seal_sha256=sha(old_public/'PREDICTIONS_SEALED.json'),
        old_hold_metrics_sha256=sha(old_public/'METRICS.json'),
        new_http=0,frames=8400,arms=own['arms'],first_split_rule=config['decision_protocol']))
    source=list(stream(OBS,PROFILES,8400,1))
    assignments={r['frame']:r for r in rows(ASSIGN)}
    scan=read(SCAN)
    suspects={x['frame']:x for x in scan['suspects']}
    assert len(source)==len(assignments)==8400 and len(suspects)==len(scan['suspects'])
    b0=Bridge(read(ROOT/'online/closed_loop_2888/z4q_source/CONFIG.json'))
    hold=GroupBridgeP(read(ROOT/'online/closed_loop_2888/z4q_source/CONFIG.json'))
    manager=MergeSplitManagerP('HOLD-P',hold,suspects,config,assignments)
    started=time.monotonic()
    published=set()
    previous_event=None
    sys.addaudithook(no_truth)
    with gzip.open(OUT/'predictions_development.jsonl.gz','wt',encoding='utf-8') as pred_file, \
         gzip.open(OUT/'TRANSACTIONS.jsonl.gz','wt',encoding='utf-8') as txn_file, \
         (OUT/'PUBLISH_LEDGER.jsonl').open('x',encoding='utf-8') as pub_file:
        for (row,profiles),archived in zip(source,rows(ARCHIVED),strict=True):
            received=time.monotonic()
            frame,now=row['frame'],row['time']
            v0=b0.preview(frame,now,row['observations'],profiles)
            ids0,_=b0.commit_once(v0)
            b0_objects=emit(row,ids0)
            assert b0_objects==archived['variants']['Z4Q_STABLE'],frame
            signal=manager.before(row,profiles)
            active=manager.active
            before_outside=snapshot_outside(hold,active,[o['id'] for o in row['observations']])
            view=hold.preview(frame,now,row['observations'],profiles)
            transaction=None
            fallback=None
            restore=None
            if active and active['q']==frame:
                assert active['split_first_frame']==active['evidence_cutoff_frame']==frame
                assert all(len(x)==1 and x[0]['frame']==frame for x in active['post_roles'].values())
                choice,detail=numeric_choice(active)
                active['numeric']=dict(choice=choice,detail=detail)
                mapping=choice_mapping(active,choice) if choice in ('H1','H2') else None
                if mapping:
                    transaction,error=hold.stage_group_restore(view,active,mapping)
                else:
                    error='numeric_unresolved'
                if transaction:
                    status='COMMIT' if transaction['changes'] else 'RESOLVE_NO_ID_CHANGE'
                    ids,trace=hold.commit_once(view,transaction)
                else:
                    transaction,fallback=hold.local_fallback(view,active)
                    status=fallback['status']
                    ids,trace=hold.commit_once(view,transaction)
                restore=dict(status=status,selected_choice=choice,stage_error=error,
                    decision_source='NUMERIC' if fallback is None else 'OWN_BRANCH_LOCAL_FALLBACK',
                    mapping=mapping,changes=transaction['changes'],fallback=fallback)
                active['restore']=restore
                manager.finish(frame,status)
            else:
                ids,trace=hold.commit_once(view)
            manager.after(row,profiles)
            after_outside=snapshot_outside(hold,active,[o['id'] for o in row['observations']])
            # The next-frame outside state is recorded, not asserted equal to
            # the previous frame: ordinary observations legitimately update it.
            outside_transition=dict(before_sha256=hashlib.sha256(json.dumps(before_outside,sort_keys=True,default=str).encode()).hexdigest() if before_outside else None,
                                    after_sha256=hashlib.sha256(json.dumps(after_outside,sort_keys=True,default=str).encode()).hexdigest() if after_outside else None)
            branch=emit(row,ids)
            assert [x['mask'] for x in branch]==[x['mask'] for x in b0_objects]
            result=dict(frame=frame,global_frame=row['global_frame'],time=now,
                        variants={'B0':b0_objects,'HOLD-P':branch})
            assert frame not in published
            line=json.dumps(result,separators=(',',':'))+'\n'
            pred_file.write(line)
            pred_file.flush() if active and active.get('q')==frame else None
            published_at=time.monotonic()
            published.add(frame)
            event_publish=(dict(episode=active['id'],q=frame,
                first_pair={str(n):ids[n] for n in active['post_roles']},
                decision_source=restore['decision_source']) if active and active.get('q')==frame else None)
            pub_file.write(json.dumps(dict(frame=frame,first_publish_time_monotonic=published_at,
                frame_received_monotonic=received,receive_to_publish_seconds=published_at-received,
                prediction_row_sha256=hashlib.sha256(line.encode()).hexdigest(),event_publish=event_publish),separators=(',',':'))+'\n')
            txn_file.write(json.dumps(dict(frame=frame,signal=signal,restore=restore,
                active_event=active['id'] if active else None,actual_published_mapping=ids,
                internal_token_state=trace.get('merge_split_group'),
                outside_state_transition=outside_transition),separators=(',',':'),default=str)+'\n')
            if frame%500==0:
                print('FRAME',frame,'events',len(manager.events),flush=True)
    def safe_event(e):
        fields=('id','suspect_frame','confirm_frame','q','split_first_frame','evidence_cutoff_frame',
                'end','status','numeric','restore','publication_policy')
        return {k:copy.deepcopy(e.get(k)) for k in fields}
    write_new(OUT/'EVENTS.json',dict(arm='HOLD-P',events=[safe_event(e) for e in manager.events]))
    (OUT/'CALL_LEDGER.jsonl').write_text('',encoding='utf-8')
    seal=dict(status='SEALED_AWAITING_INDEPENDENT_SCORING',frames=8400,published_frames=len(published),
              mode='S0P_OFFLINE_NO_NEW_MODEL_HTTP',new_inference_http=0,wall_seconds=time.monotonic()-started,
              predictions_sha256=sha(OUT/'predictions_development.jsonl.gz'),
              transactions_sha256=sha(OUT/'TRANSACTIONS.jsonl.gz'),
              publish_ledger_sha256=sha(OUT/'PUBLISH_LEDGER.jsonl'),
              events_sha256=sha(OUT/'EVENTS.json'),call_ledger_sha256=sha(OUT/'CALL_LEDGER.jsonl'),
              freeze_sha256=sha(OUT/'FREEZE.json'))
    write_new(OUT/'PREDICTIONS_SEALED.json',seal)
    print('SEALED',json.dumps(dict(frames=8400,events=len(manager.events),wall_seconds=seal['wall_seconds'])))


if __name__=='__main__':
    run()
