"""Verify actual per-frame outside-object state against the same-frame preview."""
import copy
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OLD=ROOT/'experiments/ms1_s0_development_8400'
sys.path.insert(0,str(OLD))
sys.path.insert(0,str(ROOT/'online/closed_loop_2888/z4q_source'))
from bridge import read,rows,stream,sha  # noqa: E402
from merge_split_manager import choice_mapping,numeric_choice  # noqa: E402
from manager_p import GroupBridgeP,MergeSplitManagerP  # noqa: E402
from replay_p import OBS,PROFILES,ASSIGN,SCAN,OUT,emit,write_new,no_truth  # noqa: E402


def signature(bridge,natives,publics):
    engine=bridge.engine
    return dict(native={name:{str(n):copy.deepcopy(getattr(engine,name).get(n)) for n in natives}
                         for name in ('alias','birth','pending','native_seen','native_runs',
                                      'recent_core','return_quarantine','empty_quarantine')},
        public={name:{str(k):copy.deepcopy(getattr(engine,name).get(k)) for k in publics}
                        for name in ('bank','view_bank')},
        retired=sorted(engine.retired & natives),
        previous={str(n):bridge.previous.get(n) for n in natives},
        epochs={str(n):bridge.epochs.get(n) for n in natives},
        provenance={str(n):copy.deepcopy(bridge.provenance.get(n)) for n in natives})


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,default=str).encode()).hexdigest()


def run():
    assert sha(OUT/'predictions_development.jsonl.gz')==read(OUT/'PREDICTIONS_SEALED.json')['predictions_sha256']
    assignments={r['frame']:r for r in rows(ASSIGN)}
    suspects={x['frame']:x for x in read(SCAN)['suspects']}
    bridge=GroupBridgeP(read(ROOT/'online/closed_loop_2888/z4q_source/CONFIG.json'))
    manager=MergeSplitManagerP('HOLD-P',bridge,suspects,read(OLD/'CONFIG_V7.json'),assignments)
    records=[]
    sys.addaudithook(no_truth)
    for (row,profiles),pred in zip(stream(OBS,PROFILES,8400,1),rows(OUT/'predictions_development.jsonl.gz'),strict=True):
        f=row['frame']
        manager.before(row,profiles)
        e=manager.active
        view=bridge.preview(f,row['time'],row['observations'],profiles)
        expected=copy.deepcopy(bridge)
        expected.commit_once(view)
        if e and e['q']==f:
            choice,_=numeric_choice(e)
            mapping=choice_mapping(e,choice) if choice in ('H1','H2') else None
            txn,error=bridge.stage_group_restore(view,e,mapping) if mapping else (None,'numeric_unresolved')
            if txn:
                ids,_=bridge.commit_once(view,txn)
                status='COMMIT' if txn['changes'] else 'RESOLVE_NO_ID_CHANGE'
            else:
                txn,_=bridge.local_fallback(view,e)
                ids,_=bridge.commit_once(view,txn)
                status=txn['trace']['merge_split_local_fallback']['status']
            manager.finish(f,status)
        else:
            ids,_=bridge.commit_once(view)
        assert emit(row,ids)==pred['variants']['HOLD-P'],f
        if e:
            members=set(e['member_sources'])|set(e['post_roles'])|{e['group_source']}
            outside={o['id'] for o in row['observations']}-members
            publics={view['mapping'][n] for n in outside if view['mapping'][n]>=0}
            publics|={a['target'] for n,a in view['engine'].alias.items() if n in outside}
            expected_state=signature(expected,outside,publics)
            actual_state=signature(bridge,outside,publics)
            record=dict(frame=f,event=e['id'],event_status=e['status'],
                outside_natives=sorted(outside),outside_public_banks=sorted(publics),
                expected_same_frame_sha256=digest(expected_state),actual_sha256=digest(actual_state),
                exactly_preserved=expected_state==actual_state)
            if not record['exactly_preserved']:
                record['different_domains']=[k for k in expected_state if expected_state[k]!=actual_state[k]]
            records.append(record)
        manager.after(row,profiles)
    write_new(OUT/'OUTSIDE_STATE_AUDIT.json',dict(status='INDEPENDENT_SAME_FRAME_BRANCH_STATE_REPLAY',
        prediction_sha256=sha(OUT/'predictions_development.jsonl.gz'),checked_active_frames=len(records),
        exact_frames=sum(x['exactly_preserved'] for x in records),
        failures=[x for x in records if not x['exactly_preserved']],records=records))
    print('OUTSIDE_STATE',len(records),'exact',sum(x['exactly_preserved'] for x in records))


if __name__=='__main__':
    run()
