"""Postseal official TrackEval plus event physical-reference audit."""
import hashlib
import gzip
import json
import re
from collections import Counter
from pathlib import Path

import numpy as np
from pycocotools import mask as mu

import original_score as base

HERE=Path(__file__).resolve().parent
PUBLIC=HERE/'run_ms1s0_20260928/public'
PRIVATE=HERE/'run_ms1s0_20260928/private_api'
ARMS=('B0','B-HOLD-S0','B-VLM-S0')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def fragment(user,section,labels):
    text=user.split(section+'\n',1)[1]
    decoder=json.JSONDecoder()
    result={}
    for label in labels:
        text=text.lstrip()
        prefix=label+'：'
        assert text.startswith(prefix)
        obj,end=decoder.raw_decode(text[len(prefix):])
        result[label]=obj
        text=text[len(prefix)+end:]
    return result


def token_native(token,assignments,bindings):
    frame_text,ordinal_text=re.fullmatch(r'F(\d+):O(\d+)',token).groups()
    frame,ordinal=int(frame_text),int(ordinal_text)
    row=assignments[frame]
    ordered=[]
    for key,rle in row['masks'].items():
        x,y,w,h=mu.toBbox(base.rle(rle))
        ordered.append((x+w/2,y+h/2,int(key.split(':')[1])))
    ordered.sort()
    assert 1<=ordinal<=len(ordered)
    actual=bindings[token]
    assert actual['frame']==frame and actual['source']==ordered[ordinal-1][2],token
    return frame,actual['source']


def fragment_consensus(fragment,assignments,matches,bindings):
    facts=fragment['observations']
    actual=[token_native(x['fact_id'],assignments,bindings) for x in facts]
    frames=[f for f,_ in actual]
    sources={n for _,n in actual}
    matched=[matches[f].get(str(n)) for f,n in actual]
    known=[x for x in matched if x is not None]
    continuous=all(b==a+1 for a,b in zip(frames,frames[1:]))
    versions={(x.get('source_generation'),x.get('public_epoch')) for x in facts}
    result=(known[0] if len(known)>=3 and len(set(known))==1 and continuous and len(sources)==1
            and len(versions)==1
            else None)
    return result,dict(frames=frames,source_continuous=continuous and len(sources)==1,
                       same_source_and_public_version=len(versions)==1,
                       matched_count=len(known),matched_identity_set=sorted(set(known)))


def full():
    seal=read(PUBLIC/'PREDICTIONS_SEALED.json')
    assert seal['status']=='SEALED_AWAITING_INDEPENDENT_SCORING' and seal['mode']=='real'
    for filename,key in [('predictions_validation.jsonl.gz','predictions_sha256'),
                         ('TRANSACTIONS.jsonl.gz','transactions_sha256'),
                         ('EVENTS.json','events_sha256'),('CALL_LEDGER.jsonl','call_ledger_sha256'),
                         ('PUBLISH_LEDGER.jsonl','publish_ledger_sha256')]:
        assert base.sha(PUBLIC/filename)==seal[key]
    published=[json.loads(x) for x in (PUBLIC/'PUBLISH_LEDGER.jsonl').read_text().splitlines()]
    assert len(published)==seal['published_frames']==2888
    assert [x['frame'] for x in published]==list(range(1,2889))
    with gzip.open(PUBLIC/'predictions_validation.jsonl.gz','rt',encoding='utf-8') as handle:
        for line,entry in zip(handle,published,strict=True):
            assert hashlib.sha256(line.encode()).hexdigest()==entry['prediction_row_sha256']
            assert entry['first_publish_time_monotonic']>=entry['frame_received_monotonic']
    assert base.sha(base.ASSIGN)==base.ASSIGN_SHA
    assert base.sha(base.TRUTH)==base.TRUTH_SHA
    assert base.sha(base.MATCHES)==base.MATCHES_SHA
    gt=[]
    pred={arm:[] for arm in ARMS}
    sims={arm:[] for arm in ARMS}
    output_maps={arm:{} for arm in ARMS}
    assignments={}
    differences=Counter()
    for index,(a,p,t) in enumerate(zip(base.rows(base.ASSIGN),
            base.rows(PUBLIC/'predictions_validation.jsonl.gz'),base.rows(base.TRUTH),strict=True),1):
        assert a['frame']==p['frame']==index and p['global_frame']==t['global_frame_id']==9300+index
        assignments[index]=a
        native_keys=[x['mask'] for x in a['variants']['N0']]
        gid=[int(x['id']) for x in t['gt_grid']]
        gt.append(gid)
        keys=sorted(a['masks'])
        lookup={key:i for i,key in enumerate(keys)}
        matrix=(mu.iou([base.rle(x['rle']) for x in t['gt_grid']],
                       [base.rle(a['masks'][key]) for key in keys],[0]*len(keys))
                if gid and keys else np.zeros((len(gid),len(keys))))
        for arm in ARMS:
            objects=p['variants'][arm]
            assert [x['mask'] for x in objects]==native_keys
            ids=[int(x['id']) for x in objects]
            assert len(ids)==len(set(ids))
            pred[arm].append(ids)
            sims[arm].append(matrix[:,[lookup[x['mask']] for x in objects]])
            output_maps[arm][index]={int(x['mask'].split(':')[1]):int(x['id']) for x in objects}
        differences['B0_vs_HOLD']+=p['variants']['B0']!=p['variants']['B-HOLD-S0']
        differences['HOLD_vs_VLM']+=p['variants']['B-HOLD-S0']!=p['variants']['B-VLM-S0']
        differences['B0_vs_VLM']+=p['variants']['B0']!=p['variants']['B-VLM-S0']
    assert len(gt)==2888
    metrics=base.metrics(gt,pred,sims)
    for key,value in base.BASELINE.items():
        assert abs(metrics['B0'][key]-value)<1e-8
    delta={name:{key:metrics[name][key]-metrics[parent][key] for key in metrics[name]}
           for name,parent in [('B-HOLD-S0','B0'),('B-VLM-S0','B0')]}
    delta['B-VLM-S0_vs_B-HOLD-S0']={key:metrics['B-VLM-S0'][key]-metrics['B-HOLD-S0'][key]
                              for key in metrics['B-VLM-S0']}
    matches={r['frame']:r['native_to_gt'] for r in base.rows(base.MATCHES)}
    assert len(matches)==2888
    fixed_public={}
    for frame in range(1,2889):
        for native,public in output_maps['B0'][frame].items():
            individual=matches[frame].get(str(native))
            if individual is not None and public not in fixed_public:
                fixed_public[public]=individual
    events=read(PUBLIC/'EVENTS.json')
    physical=[]
    first_split=[]
    for e in events['B-VLM-S0']:
        tag=e['id']+'-S0'
        if not (PUBLIC/'requests'/f'{tag}.json').exists():
            physical.append(dict(episode=e['id'],status='NO_SPLIT_REQUEST'))
            continue
        request=read(PUBLIC/'requests'/f'{tag}.json')
        bindings=read(PRIVATE/f'{tag}.bindings.json')['token_to_actual_source']
        user=request['user']
        pre=fragment(user,'【合并之前的原始参考】',('A','B'))
        post=fragment(user,'【分离后的当前短片段】',('X','Y'))
        refs={role:token_native(pre[role]['observations'][-1]['fact_id'],assignments,bindings)
              for role in ('A','B')}
        ends={role:token_native(post[role]['observations'][-1]['fact_id'],assignments,bindings)
              for role in ('X','Y')}
        truth_ref={role:matches[f].get(str(n)) for role,(f,n) in refs.items()}
        truth_end={role:matches[f].get(str(n)) for role,(f,n) in ends.items()}
        consensus_ref={role:fragment_consensus(pre[role],assignments,matches,bindings)[0] for role in ('A','B')}
        consensus_ref_support={role:fragment_consensus(pre[role],assignments,matches,bindings)[1] for role in ('A','B')}
        consensus_end_support={role:fragment_consensus(post[role],assignments,matches,bindings)[1] for role in ('X','Y')}
        def verdict(reference,current,pairs):
            if None in (*reference.values(),*current.values()):
                return 'UNSCORABLE'
            return 'CORRECT' if all(reference[a]==current[x] for a,x in pairs.items()) else 'WRONG'
        mappings={'H1':{'A':'X','B':'Y'},'H2':{'A':'Y','B':'X'}}
        anchor_verdict={choice:verdict(truth_ref,truth_end,pairs) for choice,pairs in mappings.items()}
        first_split_verdict={choice:verdict(consensus_ref,truth_end,pairs) for choice,pairs in mappings.items()}
        raw=e.get('S_raw_choice')
        numeric=e['numeric']['choice'] if e.get('numeric') else None
        selected=e.get('restore',{}).get('selected_choice')
        ref_public={role:output_maps['B-VLM-S0'][f].get(n) for role,(f,n) in refs.items()}
        q_public={role:output_maps['B-VLM-S0'][f].get(n) for role,(f,n) in ends.items()}
        physical.append(dict(episode=e['id'],reference_tokens={r:pre[r]['observations'][-1]['fact_id'] for r in refs},
            q_tokens={r:post[r]['observations'][-1]['fact_id'] for r in ends},
            reference_gt=truth_ref,q_gt=truth_end,reference_public=ref_public,q_public=q_public,
            anchor_only_candidate_verdict=anchor_verdict,
            clean_segment_consensus_reference_gt=consensus_ref,
            clean_segment_consensus_support=dict(pre=consensus_ref_support,post=consensus_end_support),
            pre_consensus_first_split_candidate_verdict=first_split_verdict,
            reference_public_global_first_matched_gt={r:fixed_public.get(p) for r,p in ref_public.items()},
            q_public_global_first_matched_gt={r:fixed_public.get(p) for r,p in q_public.items()},
            model_raw=raw,model_anchor_only_verdict=anchor_verdict.get(raw,'DEFER_OR_INVALID'),
            model_first_split_verdict=first_split_verdict.get(raw,'DEFER_OR_INVALID'),
            numeric_choice=numeric,numeric_first_split_verdict=first_split_verdict.get(numeric,'UNRESOLVED'),
            applied_choice=selected,first_split_pair_correct=first_split_verdict.get(selected,'UNRESOLVED'),
            first_publish=published[e['q']-1]['event_publish'],
            restore_status=e.get('restore',{}).get('status')))
        per_arm={}
        for arm in ('B-HOLD-S0','B-VLM-S0'):
            arm_event=next(x for x in events[arm] if x['id']==e['id'])
            selected_arm=arm_event.get('restore',{}).get('selected_choice')
            entry=published[e['q']-1]['event_publish'][arm]
            assert entry['evidence_cutoff_frame']==e['q']==e['split_first_frame']
            assert entry['post_sample_count']==1
            first_public={role:entry['first_public_pair'][role]['public_id'] for role in ('X','Y')}
            assert first_public=={role:output_maps[arm][e['q']].get(n) for role,(f,n) in ends.items()}
            reference_public={role:output_maps[arm][f].get(n) for role,(f,n) in refs.items()}
            target={gt:reference_public[role] for role,gt in consensus_ref.items() if gt is not None}
            actual_pair_verdict=('UNSCORABLE' if len(target)!=2 or len(set(target.values()))!=2 or
                None in truth_end.values() or truth_end['X']==truth_end['Y'] else
                'CORRECT' if all(first_public[role]==target.get(truth_end[role]) for role in ('X','Y')) else 'WRONG')
            sustained=None
            assessable=0
            streak=0
            for frame in range(e['q'],2889):
                if len(target)!=2 or len(set(target.values()))!=2:
                    break
                gt_to_native={}
                for native,gt in matches[frame].items():
                    if gt in target:
                        gt_to_native.setdefault(gt,[]).append(int(native))
                if any(len(gt_to_native.get(gt,[]))!=1 for gt in target):
                    streak=0
                    continue
                assessable+=1
                correct=all(output_maps[arm][frame].get(gt_to_native[gt][0])==pid
                            for gt,pid in target.items())
                streak=streak+1 if correct else 0
                if streak==3:
                    sustained=frame-2-e['q']
                    break
            per_arm[arm]=dict(first_public_pair=first_public,
                decision_source=entry['decision_source'],
                selected_candidate_verdict=first_split_verdict.get(selected_arm,'UNRESOLVED'),
                first_split_pair_correct=actual_pair_verdict,
                recovery_delay_frames=sustained if sustained is not None else 'UNRESOLVED_OR_UNSCORABLE',
                recovery_rule='first 3 consecutive frames with both physical members uniquely observed and mapped to pre-event public IDs',
                assessable_pair_frames_until_resolution=assessable,
                receive_to_first_publish_seconds=published[e['q']-1]['receive_to_publish_seconds'])
        response_path=PUBLIC/'responses'/f'{tag}.json'
        response=read(response_path) if response_path.exists() else None
        first_split.append(dict(episode=e['id'],split_first_frame=e['split_first_frame'],
            evidence_cutoff_frame=e['q'],post_sample_count=1,
            reference_anchor_only=truth_ref,reference_pre_consensus=consensus_ref,
            first_split_gt=truth_end,anchor_only_candidate_verdict=anchor_verdict,
            pre_consensus_candidate_verdict=first_split_verdict,
            model_raw=e.get('S_raw_choice'),model_parse_status=e.get('S_parse_status'),
            model_first_split_verdict=first_split_verdict.get(raw,'DEFER_OR_INVALID'),
            request_start_monotonic=response.get('request_start_monotonic') if response else None,
            response_end_monotonic=response.get('response_end_monotonic') if response else None,
            api_latency_seconds=response.get('latency_seconds') if response else None,
            first_publish_time_monotonic=published[e['q']-1]['first_publish_time_monotonic'],
            arms=per_arm))
    summary=dict(status='SCORED_EXPOSED_VALIDATION',frames=2888,metrics=metrics,delta=delta,
                 changed_frames=dict(differences),physical_events=physical,
                 source_prediction_sha256=seal['predictions_sha256'])
    assert not (PUBLIC/'METRICS.json').exists()
    (PUBLIC/'METRICS.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (PUBLIC/'PHYSICAL_EVENT_AUDIT.json').write_text(json.dumps(physical,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (PUBLIC/'FIRST_SPLIT_RESULTS.json').write_text(json.dumps(first_split,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (PUBLIC/'DIFF_SUMMARY.json').write_text(json.dumps(dict(changed_frames=dict(differences),delta=delta),
                                                      ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    provenance=dict(scorer_sha256=base.sha(Path(__file__)),original_scorer_sha256=base.sha(Path(base.__file__)),
                    prediction_sha256=seal['predictions_sha256'],
                    assignment_sha256=base.ASSIGN_SHA,truth_sha256=base.TRUTH_SHA,matches_sha256=base.MATCHES_SHA,
                    trackeval_path=str(base.TRACK_PATH),scored_after_seal=True)
    (PUBLIC/'SCORE_PROVENANCE.json').write_text(json.dumps(provenance,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(metrics=metrics,changed_frames=dict(differences),physical=physical),ensure_ascii=False))


if __name__=='__main__':
    full()
