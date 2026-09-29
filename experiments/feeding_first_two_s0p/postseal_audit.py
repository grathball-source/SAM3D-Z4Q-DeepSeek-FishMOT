"""Postseal event-level check against edited polygon identity labels."""
import json
from pathlib import Path

from prepare import DATA, SEGMENTS, digest, write_new
from score import coco, mask_rles, original_score, records

HERE=Path(__file__).resolve().parent
ARMS={'B_HOLD':'B-HOLD','B_VLM':'B-VLM'}


def source_match(assignment, label, sources):
    identities, reference=mask_rles(label['shapes'])
    keys=[item['mask'] for item in assignment['variants']['N0']]
    native=[original_score.rle(assignment['masks'][key]) for key in keys]
    matrix=coco.iou(reference,native,[0]*len(native)) if identities and native else []
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
            matches[source]=dict(status='UNIQUE_IOU_MATCH',gt_id=best[1],iou=best[0],
                                 second_iou=second)
        else:
            matches[source]=dict(status='UNSCORABLE_LOW_OR_AMBIGUOUS_IOU',
                                 best_iou=best[0],second_iou=second)
    ids=[item['gt_id'] for item in matches.values() if item['status']=='UNIQUE_IOU_MATCH']
    if len(ids)!=len(set(ids)):
        for item in matches.values():
            if item['status']=='UNIQUE_IOU_MATCH':
                item['status']='UNSCORABLE_SHARED_GT_MATCH'
    return matches


def audit():
    run=HERE/'run'
    metrics=json.loads((run/'METRICS.json').read_text(encoding='utf-8'))
    assert metrics['status']=='SCORED_AFTER_BOTH_PREDICTION_SEALS'
    details=[]
    for name,(start,stop) in SEGMENTS.items():
        public=run/name/'public'
        seal=json.loads((public/'PREDICTIONS_SEALED.json').read_text(encoding='utf-8'))
        assert digest(public/'predictions.jsonl.gz')==seal['predictions_sha256']
        pred={row['frame']:row for row in records(public/'predictions.jsonl.gz')}
        assign={row['frame']:row for row in records(HERE/'private'/name/'assignments.jsonl.gz')}
        events=json.loads((public/'EVENTS.json').read_text(encoding='utf-8'))
        scan=json.loads((HERE/'private'/name/'scan_v4.json').read_text(encoding='utf-8'))
        suspects={item['frame']:item for item in scan['suspects']}
        for arm_key,arm in ARMS.items():
            for event in events[arm_key]:
                q=event['q']
                if q is None:
                    continue
                suspect=event['suspect_frame']
                pre=suspect-1
                assert pre>=1 and q>=suspect
                sources=suspects[suspect]['sources']
                selected=event['restore']
                mapping={int(k):v for k,v in (selected['mapping'] or {}).items()}
                pre_public={int(item['mask'][2:]):item['id'] for item in pred[pre]['variants'][arm]}
                pre_sources=[source for source in sources if source in pre_public]
                post_sources=list(mapping)
                pre_global=pred[pre]['global_frame']
                q_global=pred[q]['global_frame']
                pre_gt=json.loads((DATA/'labels_640x360'/f'{pre_global:06d}.json').read_text(encoding='utf-8'))
                post_gt=json.loads((DATA/'labels_640x360'/f'{q_global:06d}.json').read_text(encoding='utf-8'))
                earlier=source_match(assign[pre],pre_gt,pre_sources)
                later=source_match(assign[q],post_gt,post_sources)
                physical='UNSCORABLE'
                expected={}
                if selected['status'].startswith('LOCAL_FALLBACK'):
                    physical='NOT_STAGED'
                elif (len(pre_sources)==len(post_sources)==2 and
                        all(item['status']=='UNIQUE_IOU_MATCH' for item in earlier.values()) and
                        all(item['status']=='UNIQUE_IOU_MATCH' for item in later.values())):
                    source_by_gt={earlier[n]['gt_id']:pre_public[n] for n in pre_sources}
                    if set(source_by_gt)=={later[n]['gt_id'] for n in post_sources}:
                        expected={n:source_by_gt[later[n]['gt_id']] for n in post_sources}
                        physical='CORRECT' if mapping==expected else 'WRONG'
                    else:
                        physical='NO_TWO_MEMBER_GT_BIJECTION'
                details.append(dict(segment=name,arm=arm,event=event['id'],
                    suspect_frame=suspect,pre_frame=pre,q=q,
                    pre_original_frame=pre_global,q_original_frame=q_global,
                    source_pair=sources,pre_public={str(n):pre_public.get(n) for n in sources},
                    pre_gt={str(n):v for n,v in earlier.items()},
                    post_gt={str(n):v for n,v in later.items()},
                    model_raw_choice=selected['raw_choice'],numeric_choice=selected['numeric_choice'],
                    applied_choice=selected['selected_choice'],status=selected['status'],
                    decision_source=selected['decision_source'],
                    chosen_mapping=mapping,expected_mapping=expected,
                    physical_proxy=physical,
                    mapping_reference='native sources at pre-suspect frame; actual protected bank anchor not revalidated'))
    summary={arm:{status:sum(item['arm']==arm and item['physical_proxy']==status for item in details)
                  for status in ('CORRECT','WRONG','NOT_STAGED','NO_TWO_MEMBER_GT_BIJECTION','UNSCORABLE')}
             for arm in ARMS.values()}
    result=dict(status='POSTSEAL_DIAGNOSTIC',reference='edited polygon labels, checked=false',
        mask_iou_min=.5,margin_min=.1,segment_identity_reset=True,
        classification_limitation='pre-suspect source proxy is not the bank anchor; physical outcome does not certify historical anchor correctness',
        summary=summary,events=details,
        metrics_sha256=digest(run/'METRICS.json'),
        predictions_sha256={name:digest(run/name/'public/predictions.jsonl.gz') for name in SEGMENTS})
    write_new(run/'POSTSEAL_EVENT_AUDIT.json',result)
    print(json.dumps(summary,ensure_ascii=False))
    return result


if __name__=='__main__':
    audit()
