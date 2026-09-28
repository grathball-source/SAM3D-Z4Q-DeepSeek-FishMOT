"""Postseal physical-reference audit; never used to choose triggers or q."""
import gzip
import json
import sys
from collections import Counter
from pathlib import Path

HERE=Path(__file__).resolve().parent
MATCHES=Path('E:/CAU/D-MOT/tools/sam3_depth_return_guard_20260918/completion_evidence/experiment/offline_matches_development.jsonl.gz')
PAIRS={'H1':{'A':'X','B':'Y'},'H2':{'A':'Y','B':'X'}}


def rows(path):
    with gzip.open(path,'rt',encoding='utf-8') as handle:
        yield from map(json.loads,handle)


def verdict(ref,post,choice):
    if choice not in PAIRS or None in (*ref.values(),*post.values()) or len(set(ref.values()))!=2:
        return 'UNSCORABLE'
    return 'CORRECT' if all(ref[a]==post[x] for a,x in PAIRS[choice].items()) else 'WRONG'


def run(name):
    target=HERE/name
    public=target/'public'
    seal=json.loads((public/'PREDICTIONS_SEALED.json').read_text(encoding='utf-8'))
    assert seal['status']=='SEALED_AWAITING_INDEPENDENT_SCORING' and seal['frames']==8400
    assert (public/'METRICS.json').exists()
    events=json.loads((public/'EVENTS.json').read_text(encoding='utf-8'))
    matches={x['frame']:x['native_to_gt'] for x in rows(MATCHES)}
    assert len(matches)==8400
    q_frames={x['q'] for x in events['B-HOLD-S0'] if x['q'] is not None}
    predictions={x['frame']:x for x in rows(public/'predictions_development.jsonl.gz')
                 if x['frame'] in q_frames}
    results=[]
    for event in events['B-HOLD-S0']:
        basic=dict(episode=event['id'],suspect_frame=event['suspect_frame'],
                   confirm_frame=event['confirm_frame'],q=event['q'],status=event['status'])
        if event['q'] is None:
            results.append(dict(basic,scoring_status='NO_FIRST_SPLIT_Q'))
            continue
        state=json.loads((target/'private_source'/f'{event["id"]}-B-HOLD-S0-episode_q.json').read_text(encoding='utf-8'))
        pre={role:state['pre'][role] for role in ('A','B')}
        post=dict(zip(('X','Y'),state['post_roles']))
        anchor={role:(matches[items[-1]['frame']].get(str(items[-1]['source'])) if items else None)
                for role,items in pre.items()}
        consensus={}
        support={}
        for role,items in pre.items():
            known=[matches[x['frame']].get(str(x['source'])) for x in items]
            known=[x for x in known if x is not None]
            contiguous=all(b['frame']==a['frame']+1 for a,b in zip(items,items[1:]))
            versions={(x.get('source_generation'),x.get('public_epoch')) for x in items}
            consensus[role]=(known[0] if len(known)>=3 and len(set(known))==1 and
                             contiguous and len(versions)==1 else None)
            support[role]=dict(frames=[x['frame'] for x in items],known_count=len(known),
                               identity_set=sorted(set(known)),contiguous=contiguous,
                               same_source_public_version=len(versions)==1)
        current={role:matches[event['q']].get(str(n)) for role,n in post.items()}
        q=predictions[event['q']]
        published={arm:{role:next(x['id'] for x in q['variants'][arm] if x['mask']==f'n:{n}')
                        for role,n in post.items()} for arm in ('B0','B-HOLD-S0','B-VLM-S0')}
        selected=event.get('restore',{}).get('selected_choice')
        results.append(dict(basic,scoring_status='SCORED_AFTER_SEAL',
            pre_last_frame={role:(items[-1]['frame'] if items else None) for role,items in pre.items()},
            pre_anchor_gt=anchor,pre_consensus_gt=consensus,pre_consensus_support=support,
            q_native_sources=post,q_gt=current,
            candidate_anchor_verdict={c:verdict(anchor,current,c) for c in PAIRS},
            candidate_consensus_verdict={c:verdict(consensus,current,c) for c in PAIRS},
            numeric_choice=event.get('numeric',{}).get('choice'),
            applied_choice=selected,applied_anchor_verdict=verdict(anchor,current,selected),
            applied_consensus_verdict=verdict(consensus,current,selected),
            first_public_pair=published,
            hold_changes_first_public=published['B-HOLD-S0']!=published['B0'],
            model_status='DRY_NO_API_UNTESTED' if seal['mode']=='dry' else 'SEE_MODEL_RECORD'))
    summary=dict(status='POSTSEAL_DEVELOPMENT_AUDIT',run=name,
        total_events=len(results),with_q=sum(x['q'] is not None for x in results),
        status_counts=dict(Counter(x['status'] for x in results)),
        applied_anchor_verdict_counts=dict(Counter(x.get('applied_anchor_verdict','NO_Q') for x in results)),
        applied_consensus_verdict_counts=dict(Counter(x.get('applied_consensus_verdict','NO_Q') for x in results)),
        no_gt_used_for_trigger_or_q=True,events=results)
    out=public/'PHYSICAL_EVENT_AUDIT.json'
    assert not out.exists(),out
    out.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in summary.items() if k!='events'},ensure_ascii=False))


if __name__=='__main__':
    if len(sys.argv)!=2 or sys.argv[1] not in ('dry_run_corrected','dry_run_v3','dry_run_v4','dry_run_v5','dry_run_v6'):
        raise SystemExit('usage: postseal_event.py dry_run_corrected|dry_run_v3|dry_run_v4|dry_run_v5')
    run(sys.argv[1])
