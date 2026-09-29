"""Reconstruct S0-P q sources without GT, then independently score after sealing."""
import copy
import gzip
import json
import sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OLD=ROOT/'experiments/ms1_s0_development_8400'
sys.path.insert(0,str(OLD))
sys.path.insert(0,str(ROOT/'online/closed_loop_2888/z4q_source'))
from bridge import read,rows,stream,sha  # noqa: E402
from merge_split_manager import choice_mapping,numeric_choice  # noqa: E402
from manager_p import GroupBridgeP,MergeSplitManagerP  # noqa: E402
from replay_p import OBS,PROFILES,ASSIGN,SCAN,OUT,emit,no_truth,write_new  # noqa: E402

PRIVATE=HERE/'run_8400_v2/private_source'


def prepare():
    assert read(OUT/'PREDICTIONS_SEALED.json')['status']=='SEALED_AWAITING_INDEPENDENT_SCORING'
    assert (OUT/'METRICS.json').exists()
    assert not PRIVATE.exists()
    PRIVATE.mkdir(parents=True)
    assignments={r['frame']:r for r in rows(ASSIGN)}
    scan=read(SCAN)
    suspects={x['frame']:x for x in scan['suspects']}
    conf=read(OLD/'CONFIG_V7.json')
    bridge=GroupBridgeP(read(ROOT/'online/closed_loop_2888/z4q_source/CONFIG.json'))
    manager=MergeSplitManagerP('HOLD-P',bridge,suspects,conf,assignments)
    q_states=[]
    sys.addaudithook(no_truth)
    with gzip.open(OUT/'predictions_development.jsonl.gz','rt',encoding='utf-8') as expected:
        for (row,profiles),raw in zip(stream(OBS,PROFILES,8400,1),expected,strict=True):
            frame=row['frame']
            manager.before(row,profiles)
            view=bridge.preview(frame,row['time'],row['observations'],profiles)
            e=manager.active
            if e and e['q']==frame:
                choice,detail=numeric_choice(e)
                mapping=choice_mapping(e,choice) if choice in ('H1','H2') else None
                txn,error=bridge.stage_group_restore(view,e,mapping) if mapping else (None,'numeric_unresolved')
                if txn:
                    ids,_=bridge.commit_once(view,txn)
                    status='COMMIT' if txn['changes'] else 'RESOLVE_NO_ID_CHANGE'
                else:
                    txn,_=bridge.local_fallback(view,e)
                    ids,_=bridge.commit_once(view,txn)
                    status=txn['trace']['merge_split_local_fallback']['status']
                q_states.append(dict(id=e['id'],q=frame,suspect_frame=e['suspect_frame'],
                    member_sources=e['member_sources'],public_ids=e['public_ids'],
                    pre=copy.deepcopy(e['pre']),post_roles=copy.deepcopy(e['post_roles']),
                    choice=choice,status=status,first_published={str(n):ids[n] for n in e['post_roles']}))
                manager.finish(frame,status)
            else:
                ids,_=bridge.commit_once(view)
            manager.after(row,profiles)
            assert emit(row,ids)==json.loads(raw)['variants']['HOLD-P'],frame
    events=read(OUT/'EVENTS.json')['events']
    assert [(x['id'],x['q'],x['status']) for x in events if x['q'] is not None]==[
        (x['id'],x['q'],x['status']) for x in q_states]
    private=PRIVATE/'Q_REFERENCE_SNAPSHOTS.json'
    write_new(private,dict(q_states=q_states,predictions_sha256=sha(OUT/'predictions_development.jsonl.gz')))
    write_new(OUT/'REFERENCE_SNAPSHOT_SEALED.json',dict(
        status='SOURCE_REPLAY_MATCHED_SEALED_PREDICTIONS_NO_GT',q_count=len(q_states),
        private_path=str(private),private_bytes=private.stat().st_size,private_sha256=sha(private),
        source_replay_sha256=sha(Path(__file__)),predictions_sha256=sha(OUT/'predictions_development.jsonl.gz')))
    print('REFERENCE_SEALED',len(q_states))


def score():
    from postseal_event import MATCHES,verdict  # noqa: E402
    seal=read(OUT/'REFERENCE_SNAPSHOT_SEALED.json')
    pred_seal=read(OUT/'PREDICTIONS_SEALED.json')
    assert seal['status']=='SOURCE_REPLAY_MATCHED_SEALED_PREDICTIONS_NO_GT'
    assert sha(OUT/'predictions_development.jsonl.gz')==seal['predictions_sha256']==pred_seal['predictions_sha256']
    p=Path(seal['private_path'])
    assert p.stat().st_size==seal['private_bytes'] and sha(p)==seal['private_sha256']
    snapshots=read(p)['q_states']
    assert len(snapshots)==seal['q_count']
    matches={x['frame']:x['native_to_gt'] for x in rows(MATCHES)}
    assert len(matches)==8400
    results=[]
    for e in snapshots:
        pre=e['pre']
        post=dict(zip(('X','Y'),e['post_roles']))
        anchor={role:(matches[items[-1]['frame']].get(str(items[-1]['source'])) if items else None)
                for role,items in pre.items()}
        consensus={}
        support={}
        for role,items in pre.items():
            known=[matches[x['frame']].get(str(x['source'])) for x in items]
            known=[x for x in known if x is not None]
            continuous=all(b['frame']==a['frame']+1 for a,b in zip(items,items[1:]))
            versions={(x.get('source_generation'),x.get('public_epoch')) for x in items}
            consensus[role]=(known[0] if len(known)>=3 and len(set(known))==1 and continuous
                             and len(versions)==1 else None)
            support[role]=dict(observations=len(items),known=len(known),continuous=continuous,
                               same_version=len(versions)==1,gt_ids=sorted(set(known)))
        current={role:matches[e['q']].get(str(n)) for role,n in post.items()}
        post_consensus={}
        for role,n in post.items():
            values=[]
            for frame in range(e['q'],min(8400,e['q']+10)+1):
                value=matches[frame].get(str(n))
                if value is None:
                    break
                values.append(value)
            post_consensus[role]=values[0] if len(values)>=3 and len(set(values))==1 else None
        c=e['choice']
        applied='UNRESOLVED' if c not in ('H1','H2') else c
        pair_ref=dict(zip(('A','B'),e['public_ids']))
        physical_public={role:(next((a for a,public in pair_ref.items() if public==e['first_published'][str(n)]),None))
                         for role,n in post.items()}
        def publication_verdict(ref):
            if None in ref.values() or None in current.values() or None in physical_public.values():
                return 'UNSCORABLE'
            return ('CORRECT' if all(ref[physical_public[role]]==current[role] for role in post)
                    else 'WRONG')
        results.append(dict(episode=e['id'],suspect_frame=e['suspect_frame'],q=e['q'],
            decision_status=e['status'],numeric_choice=c,applied_choice=applied,
            pre_public_reference=pair_ref,pre_last_anchor_gt=anchor,pre_consensus_gt=consensus,
            pre_support=support,q_native_source=post,q_actual_gt=current,
            post_q_through_q10_consensus_gt=post_consensus,
            selected_anchor_verdict=verdict(anchor,current,applied),
            selected_pre_consensus_verdict=verdict(consensus,current,applied),
            first_published=e['first_published'],first_publication_anchor_verdict=publication_verdict(anchor),
            first_publication_pre_consensus_verdict=publication_verdict(consensus)))
    write_new(OUT/'PHYSICAL_EVENT_AUDIT.json',dict(status='POSTSEAL_EXPOSED_SOURCE_REFERENCE_AUDIT',
        q_events=len(results),verdict_counts={field:dict(__import__('collections').Counter(x[field] for x in results))
            for field in ('selected_anchor_verdict','selected_pre_consensus_verdict',
                          'first_publication_anchor_verdict','first_publication_pre_consensus_verdict')},
        direct_anchor_and_fragment_consensus_separate=True,
        unresolved_is_not_correct=True,results=results))
    print('PHYSICAL_AUDIT',len(results))


if __name__=='__main__':
    if len(sys.argv)!=2 or sys.argv[1] not in ('prepare','score'):
        raise SystemExit('usage: reference_audit.py prepare|score')
    globals()[sys.argv[1]]()
