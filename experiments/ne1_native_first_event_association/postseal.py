"""After both seals: actual-anchor physical audit and exact CLEAR switch ledger."""
import json
import sys
from pathlib import Path

from scipy.optimize import linear_sum_assignment

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
FEED=ROOT/'experiments/feeding_first_two_s0p'
sys.path.insert(0,str(HERE))
import score  # noqa: E402
from verify import digest, lines, gzlines, SEGMENTS  # noqa: E402

np=score.np
ARMS=('SAM3_NATIVE','Z4Q_FROZEN','EVENT_NUM','EVENT_VLM')


def match_sources(assignment,label,sources):
    identities,reference=score.mask_rles(label['shapes'])
    keys=[item['mask'] for item in assignment['variants']['N0']]
    native=[score.original_score.rle(assignment['masks'][key]) for key in keys]
    matrix=score.coco.iou(reference,native,[0]*len(native)) if identities and native else []
    matches={}
    for source in sources:
        key=f'n:{source}'
        if key not in keys:
            matches[source]=dict(status='SOURCE_MISSING')
            continue
        column=keys.index(key)
        ranked=sorted(((float(matrix[i][column]),identities[i]) for i in range(len(identities))),reverse=True)
        best=ranked[0] if ranked else (0.,None)
        second=ranked[1][0] if len(ranked)>1 else 0.
        if best[0]>=.5 and best[0]-second>=.1:
            matches[source]=dict(status='UNIQUE_IOU_MATCH',gt_id=best[1],iou=best[0],second_iou=second)
        else:
            matches[source]=dict(status='UNSCORABLE_LOW_OR_AMBIGUOUS_IOU',
                                 best_iou=best[0],second_iou=second)
    ids=[item['gt_id'] for item in matches.values() if item['status']=='UNIQUE_IOU_MATCH']
    if len(ids)!=len(set(ids)):
        for item in matches.values():
            if item['status']=='UNIQUE_IOU_MATCH':
                item['status']='UNSCORABLE_SHARED_GT_MATCH'
    return matches


def clear_step(gt_ids,mask_keys,public_ids,similarity,previous,previous_step,frame):
    now,matches,switches={},[],[]
    if gt_ids and public_ids:
        matrix=1000*np.asarray([[public_ids[j]==previous_step.get(g)
                                  for j in range(len(public_ids))] for g in gt_ids],float)+similarity
        matrix[similarity<.5-np.finfo(float).eps]=0
        rr,cc=linear_sum_assignment(-matrix)
        for i,j in zip(rr,cc):
            if matrix[i,j]<=np.finfo(float).eps:
                continue
            gt,current=gt_ids[i],public_ids[j]
            old=previous.get(gt)
            item=dict(frame=frame,gt_id=gt,native_mask=mask_keys[j],
                      native_id=int(mask_keys[j].split(':')[1]),public_id=current,
                      matched_iou=float(similarity[i,j]))
            matches.append(item)
            if old is not None and old!=current:
                switches.append(dict(item,from_public_id=old,to_public_id=current))
            now[gt]=current
            previous[gt]=current
    return now,matches,switches


def audit():
    run=HERE/'run'
    metrics=json.loads((run/'METRICS.json').read_text(encoding='utf-8'))
    assert metrics['status']=='SCORED_AFTER_BOTH_PREDICTION_SEALS'
    assert (run/'VERIFICATION.json').is_file()
    physical=[]
    switches={arm:[] for arm in ARMS}
    all_events=[]
    for name,(start,stop) in SEGMENTS.items():
        public=run/name/'public'
        seal=json.loads((public/'PREDICTIONS_SEALED.json').read_text(encoding='utf-8'))
        assert digest(public/'predictions.jsonl.gz')==seal['predictions_sha256']
        predictions={row['frame']:row for row in gzlines(public/'predictions.jsonl.gz')}
        assignments={row['frame']:row for row in gzlines(FEED/'private'/name/'assignments.jsonl.gz')}
        events=json.loads((public/'EVENTS.json').read_text(encoding='utf-8'))
        publish={row['frame']:row for row in lines(public/'PUBLISH_LEDGER.jsonl')}
        previous={arm:{} for arm in ARMS}
        previous_step={arm:{} for arm in ARMS}
        for local in range(1,stop-start+2):
            frame=start+local-1
            assignment=assignments[local]
            row=predictions[local]
            gt=json.loads((score.DATA/'labels_640x360'/f'{frame:06d}.json').read_text(encoding='utf-8'))
            ids,reference=score.mask_rles(gt['shapes'])
            mask_keys=[item['mask'] for item in assignment['variants']['N0']]
            native=[score.original_score.rle(assignment['masks'][key]) for key in mask_keys]
            sims=(np.asarray(score.coco.iou(reference,native,[0]*len(native)),float)
                  if ids and native else np.zeros((len(ids),len(native))))
            for arm in ARMS:
                public_ids=[item['id'] for item in row['variants'][arm]]
                previous_step[arm],_,new=clear_step(ids,mask_keys,public_ids,sims,
                                                     previous[arm],previous_step[arm],frame)
                switches[arm].extend(dict(item,segment=name) for item in new)
        for arm in ('EVENT_NUM','EVENT_VLM'):
            for event in events[arm]:
                if event['confirm_frame'] is None:
                    continue
                q=event['q']
                base=dict(segment=name,arm=arm,event=event['id'],
                          suspect=event['suspect_frame'],confirm=event['confirm_frame'],
                          original_confirm=start+event['confirm_frame']-1,
                          q=q,original_q=start+q-1 if q else None,
                          status=event['status'],model_selected=event.get('model_selected'),
                          M_status=event.get('M_status'),raw_choice=event.get('S_raw_choice'),
                          parse_status=event.get('S_parse_status'),
                          reference_anchors=event['reference_anchors'])
                all_events.append(base)
                if q is None:
                    physical.append(dict(**base,physical='NO_SPLIT',first_public_physical='NO_SPLIT'))
                    continue
                restore=event['restore']
                post_sources=[int(n) for n in event['post_first_observations']]
                assert len(post_sources)==2
                anchor_matches={}
                for key,anchor in event['reference_anchors'].items():
                    public_id=int(key)
                    if not anchor or not 1<=anchor['frame']<q:
                        anchor_matches[public_id]=dict(status='INVALID_OR_MISSING_ANCHOR')
                        continue
                    original=start+anchor['frame']-1
                    gt=json.loads((score.DATA/'labels_640x360'/f'{original:06d}.json').read_text(encoding='utf-8'))
                    m=match_sources(assignments[anchor['frame']],gt,[anchor['native_id']])
                    anchor_matches[public_id]=dict(original_frame=original,
                        native_source=anchor['native_id'],**m[anchor['native_id']])
                gt=json.loads((score.DATA/'labels_640x360'/f'{start+q-1:06d}.json').read_text(encoding='utf-8'))
                post_matches=match_sources(assignments[q],gt,post_sources)
                expected={}
                if (len(anchor_matches)==len(post_matches)==2 and
                    all(v['status']=='UNIQUE_IOU_MATCH' for v in anchor_matches.values()) and
                    all(v['status']=='UNIQUE_IOU_MATCH' for v in post_matches.values())):
                    target_by_gt={v['gt_id']:k for k,v in anchor_matches.items()}
                    if len(target_by_gt)==2 and set(target_by_gt)=={v['gt_id'] for v in post_matches.values()}:
                        expected={n:target_by_gt[v['gt_id']] for n,v in post_matches.items()}
                selected={int(n):k for n,k in (restore['mapping'] or {}).items()}
                actual={int(n):k for n,k in publish[q]['event_publish'][arm]['first_public_pair'].items()}
                if restore['status'].startswith('LOCAL_FALLBACK'):
                    result='NOT_STAGED'
                elif not expected:
                    result='UNSCORABLE_OR_NO_BIJECTION'
                else:
                    result='CORRECT' if selected==expected else 'WRONG'
                first=('UNSCORABLE_OR_NO_BIJECTION' if not expected else
                       'CORRECT' if actual==expected else 'WRONG')
                physical.append(dict(**base,physical=result,first_public_physical=first,
                    numeric_choice=restore['numeric_choice'],selected_choice=restore['selected_choice'],
                    decision_source=restore['decision_source'],selected_mapping=selected,
                    first_public_mapping=actual,expected_mapping=expected,
                    residual=restore['unassigned_member_residual'],
                    anchor_matches=anchor_matches,post_matches=post_matches,
                    native_q_pair_correct=({n:n for n in expected}==expected if expected else None)))
    for arm in ARMS:
        assert len(switches[arm])==metrics['pooled_metrics'][arm]['IDSW'],arm
    summary={arm:{kind:sum(item['arm']==arm and item['physical']==kind for item in physical)
                  for kind in ('CORRECT','WRONG','NOT_STAGED','UNSCORABLE_OR_NO_BIJECTION','NO_SPLIT')}
             for arm in ('EVENT_NUM','EVENT_VLM')}
    (run/'EVENT_AUDIT.json').write_text(json.dumps(dict(status='POSTSEAL_ACTUAL_ANCHOR',
        reference='actual protected bank anchor and first split native mask; edited GT polygon checked=false',
        mask_iou_min=.5,margin_min=.1,summary=summary,events=physical,
        prediction_seals={name:digest(run/name/'public/PREDICTIONS_SEALED.json') for name in SEGMENTS}),
        ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (run/'SWITCH_LEDGER.json').write_text(json.dumps(dict(status='POSTSEAL_CLEAR_SWITCHES',
        events=switches,metrics_sha256=digest(run/'METRICS.json')),
        ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(summary=summary,switches={k:len(v) for k,v in switches.items()})))


if __name__=='__main__':
    audit()
