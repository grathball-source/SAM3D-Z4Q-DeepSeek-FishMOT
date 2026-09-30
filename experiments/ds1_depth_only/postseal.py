"""GT-only-after-seal event mapping and exact CLEAR switch audit."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from scipy.optimize import linear_sum_assignment

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE))
import score  # noqa: E402

np=score.np
ARMS=score.ARMS


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
    ids=[x['gt_id'] for x in matches.values() if x['status']=='UNIQUE_IOU_MATCH']
    if len(ids)!=len(set(ids)):
        for item in matches.values():
            if item['status']=='UNIQUE_IOU_MATCH':
                item['status']='UNSCORABLE_SHARED_GT_MATCH'
    return matches


def clear_step(gt_ids,mask_keys,public_ids,similarity,previous,previous_step,frame):
    now,switches={},[]
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
            if old is not None and old!=current:
                switches.append(dict(frame=frame,gt_id=gt,native_mask=mask_keys[j],
                    native_id=int(mask_keys[j].split(':')[1]),public_id=current,
                    matched_iou=float(similarity[i,j]),from_public_id=old,to_public_id=current))
            now[gt]=current
            previous[gt]=current
    return now,switches


def audit():
    run=HERE/'run'
    metrics=json.loads((run/'METRICS.json').read_text(encoding='utf-8'))
    assert metrics['status']=='SCORED_AFTER_BOTH_PREDICTION_SEALS'
    events_out=[]
    switches={arm:[] for arm in ARMS}
    for name,(start,stop) in score.SEGMENTS.items():
        public=run/name/'public'
        score.verify_seal(run,name,start,stop)
        predictions={item['frame']:item for item in score.records(public/'predictions.jsonl.gz')}
        assignments={item['frame']:item for item in score.records(score.FEED/'private'/name/'assignments.jsonl.gz')}
        events=json.loads((public/'EVENTS.json').read_text(encoding='utf-8'))
        publish={item['frame']:item for item in map(json.loads,(public/'PUBLISH_LEDGER.jsonl').read_text(encoding='utf-8').splitlines())}
        previous={arm:{} for arm in ARMS}
        previous_step={arm:{} for arm in ARMS}
        for local in range(1,stop-start+2):
            original=start+local-1
            label=json.loads((score.DATA/'labels_640x360'/f'{original:06d}.json').read_text(encoding='utf-8'))
            ids,reference=score.mask_rles(label['shapes'])
            mask_keys=[item['mask'] for item in assignments[local]['variants']['N0']]
            native=[score.original_score.rle(assignments[local]['masks'][key]) for key in mask_keys]
            similarity=(np.asarray(score.coco.iou(reference,native,[0]*len(native)),float)
                if ids and native else np.zeros((len(ids),len(native))))
            for arm in ARMS:
                public_ids=[x['id'] for x in predictions[local]['variants'][arm]]
                previous_step[arm],new=clear_step(ids,mask_keys,public_ids,similarity,
                    previous[arm],previous_step[arm],original)
                switches[arm].extend(dict(x,segment=name) for x in new)
        for arm in ARMS[1:]:
            for event in events[arm]:
                if event['confirm_frame'] is None:
                    continue
                q=event['q']
                base=dict(segment=name,arm=arm,event=event['id'],suspect=event['suspect_frame'],
                    confirm=event['confirm_frame'],original_confirm=start+event['confirm_frame']-1,
                    q=q,original_q=start+q-1 if q else None,status=event['status'],
                    reference_anchors=event['reference_anchors'])
                if q is None:
                    events_out.append(dict(**base,physical='NO_SPLIT',first_public_physical='NO_SPLIT'))
                    continue
                post_sources=[int(n) for n in event['post_first_observations']]
                assert len(post_sources)==2
                anchors={}
                for key,anchor in event['reference_anchors'].items():
                    public_id=int(key)
                    if not anchor or not 1<=anchor['frame']<q:
                        anchors[public_id]=dict(status='INVALID_OR_MISSING_ANCHOR')
                        continue
                    frame=start+anchor['frame']-1
                    label=json.loads((score.DATA/'labels_640x360'/f'{frame:06d}.json').read_text(encoding='utf-8'))
                    match=match_sources(assignments[anchor['frame']],label,[anchor['native_id']])
                    anchors[public_id]=dict(original_frame=frame,native_source=anchor['native_id'],
                                            **match[anchor['native_id']])
                label=json.loads((score.DATA/'labels_640x360'/f'{start+q-1:06d}.json').read_text(encoding='utf-8'))
                posts=match_sources(assignments[q],label,post_sources)
                expected={}
                if (len(anchors)==len(posts)==2 and
                    all(x['status']=='UNIQUE_IOU_MATCH' for x in anchors.values()) and
                    all(x['status']=='UNIQUE_IOU_MATCH' for x in posts.values())):
                    target_by_gt={x['gt_id']:k for k,x in anchors.items()}
                    if len(target_by_gt)==2 and set(target_by_gt)=={x['gt_id'] for x in posts.values()}:
                        expected={n:target_by_gt[x['gt_id']] for n,x in posts.items()}
                restore=event['restore']
                selected={int(n):k for n,k in (restore['mapping'] or {}).items()}
                actual={int(n):k for n,k in publish[q]['event_publish'][arm]['first_public_pair'].items()}
                if restore['status'].startswith('LOCAL_FALLBACK'):
                    physical='NOT_STAGED'
                elif not expected:
                    physical='UNSCORABLE_OR_NO_BIJECTION'
                else:
                    physical='CORRECT' if selected==expected else 'WRONG'
                first=('UNSCORABLE_OR_NO_BIJECTION' if not expected else
                       'CORRECT' if actual==expected else 'WRONG')
                events_out.append(dict(**base,physical=physical,first_public_physical=first,
                    selected_choice=restore['selected_choice'],decision_source=restore['decision_source'],
                    selected_mapping=selected,first_public_mapping=actual,expected_mapping=expected,
                    residual=restore['unassigned_member_residual'],anchor_matches=anchors,
                    post_matches=posts))
    for arm in ARMS:
        assert len(switches[arm])==metrics['pooled_metrics'][arm]['IDSW'],arm
    summary={arm:{status:sum(x['arm']==arm and x['physical']==status for x in events_out)
        for status in ('CORRECT','WRONG','NOT_STAGED','UNSCORABLE_OR_NO_BIJECTION','NO_SPLIT')}
        for arm in ARMS[1:]}
    (run/'EVENT_AUDIT.json').write_text(json.dumps(dict(status='POSTSEAL_ACTUAL_ANCHOR',
        summary=summary,events=events_out,mask_iou_min=.5,margin_min=.1,
        prediction_seals=metrics['seal_sha256']),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (run/'SWITCH_LEDGER.json').write_text(json.dumps(dict(status='POSTSEAL_CLEAR_SWITCHES',
        events=switches,metrics_sha256=score.digest(run/'METRICS.json')),
        ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(summary=summary,switches={k:len(v) for k,v in switches.items()})))


if __name__=='__main__':
    audit()
