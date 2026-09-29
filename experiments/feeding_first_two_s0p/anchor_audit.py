"""Reconstruct sealed branch states and score their actual protected anchors."""
import copy
import json
import sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path[:0]=[str(HERE),str(ROOT/'experiments/s0p_identity_publication'),
              str(ROOT/'experiments/ms1_s0_development_8400'),
              str(ROOT/'online/closed_loop_2888/z4q_source')]
from bridge import read, rows, stream  # noqa: E402
from manager_p import GroupBridgeP, MergeSplitManagerP  # noqa: E402
from merge_split_manager import choice_mapping, numeric_choice  # noqa: E402
from prepare import DATA, SEGMENTS, digest, write_new  # noqa: E402
from postseal_audit import source_match  # noqa: E402
from score import records  # noqa: E402

ARMS={'B_HOLD':'B-HOLD','B_VLM':'B-VLM'}
CONFIG=ROOT/'online/closed_loop_2888/z4q_source/CONFIG.json'
OLD=ROOT/'experiments/ms1_s0_development_8400/CONFIG_V7.json'


def seal_anchors(name, arm_key, arm):
    start,stop=SEGMENTS[name]
    base=HERE/'private'/name
    public=HERE/'run'/name/'public'
    seal=read(public/'PREDICTIONS_SEALED.json')
    assert digest(public/'predictions.jsonl.gz')==seal['predictions_sha256']
    source=list(stream(base/'observations.jsonl.gz',base/'profiles.jsonl.gz',stop-start+1))
    assignments={item['frame']:item for item in rows(base/'assignments.jsonl.gz')}
    suspects={item['frame']:item for item in read(base/'scan_v4.json')['suspects']}
    predictions={item['frame']:item for item in records(public/'predictions.jsonl.gz')}
    old_events=read(public/'EVENTS.json')[arm_key]
    decisions={item['q']:item for item in old_events if item['q'] is not None}
    bridge=GroupBridgeP(read(CONFIG))
    manager=MergeSplitManagerP(arm,bridge,suspects,read(OLD),assignments)
    snapshots=[]
    for row,profiles in source:
        frame=row['frame']
        manager.before(row,profiles)
        episode=manager.active
        if episode and episode['confirm_frame']==frame and arm=='B-VLM':
            episode['model_selected']=True
        view=bridge.preview(frame,row['time'],row['observations'],profiles)
        transaction=None
        if episode and episode['q']==frame:
            frozen=decisions[frame]
            numeric,_=numeric_choice(episode)
            assert frozen['numeric']['choice']==numeric
            residual=sorted((set(episode['member_sources']) &
                             {item['id'] for item in row['observations']})-
                            set(episode['post_roles']))
            assert residual==frozen['restore']['unassigned_member_residual']
            raw_choice=frozen['restore']['raw_choice'] if arm=='B-VLM' else None
            chosen=raw_choice if raw_choice in ('H1','H2') else numeric
            assert chosen==frozen['restore']['selected_choice']
            mapping=choice_mapping(episode,chosen) if chosen in ('H1','H2') else None
            assert ({str(n):v for n,v in mapping.items()} if mapping else None)==frozen['restore']['mapping'],(name,arm,frame,mapping,frozen['restore']['mapping'])
            if mapping and not residual:
                transaction,error=bridge.stage_group_restore(view,episode,mapping)
            if transaction is None:
                transaction,_=bridge.local_fallback(view,episode)
            assert transaction['changes']=={int(n):v for n,v in frozen['restore']['changes'].items()}
            snapshots.append(dict(segment=name,arm=arm,event=episode['id'],q=frame,
                original_q=row['global_frame'],status=frozen['restore']['status'],
                raw_choice=raw_choice,numeric_choice=numeric,selected_choice=chosen,
                selected_mapping=mapping,residual=residual,
                anchors={target:copy.deepcopy(episode['bank_snapshot'][target]['anchor'])
                         for target in episode['public_ids']},
                post_sources=list(episode['post_roles'])))
            manager.finish(frame,frozen['restore']['status'])
        ids,_=bridge.commit_once(view,transaction)
        manager.after(row,profiles)
        emitted=[dict(id=ids[item['id']],mask=item['mask']) for item in row['native']]
        assert emitted==predictions[frame]['variants'][arm],(name,arm,frame)
    assert len(snapshots)==len(decisions)
    return snapshots,assignments


def audit():
    results=[]
    replay_count=0
    for name,(start,stop) in SEGMENTS.items():
        for arm_key,arm in ARMS.items():
            snapshots,assignments=seal_anchors(name,arm_key,arm)
            replay_count+=stop-start+1
            for item in snapshots:
                q=item['q']
                anchor_scores={}
                for public_id,anchor in item['anchors'].items():
                    frame=anchor['frame']
                    global_frame=start+frame-1
                    label=read(DATA/'labels_640x360'/f'{global_frame:06d}.json')
                    match=source_match(assignments[frame],label,[anchor['native_id']])
                    anchor_scores[public_id]=dict(frame=frame,original_frame=global_frame,
                        native_source=anchor['native_id'],match=match[anchor['native_id']])
                q_label=read(DATA/'labels_640x360'/f'{item["original_q"]:06d}.json')
                post_scores=source_match(assignments[q],q_label,item['post_sources'])
                expected={}
                physical='UNSCORABLE'
                anchored={v['match']['gt_id']:k for k,v in anchor_scores.items()
                          if v['match']['status']=='UNIQUE_IOU_MATCH'}
                if (item['residual'] or item['status'].startswith('LOCAL_FALLBACK')):
                    physical='NOT_STAGED'
                elif (len(anchored)==len(anchor_scores)==2 and
                      len(post_scores)==2 and
                      all(v['status']=='UNIQUE_IOU_MATCH' for v in post_scores.values())):
                    if set(anchored)=={v['gt_id'] for v in post_scores.values()}:
                        expected={n:anchored[post_scores[n]['gt_id']] for n in post_scores}
                        physical=('CORRECT' if item['selected_mapping']==expected else 'WRONG')
                    else:
                        physical='NO_TWO_MEMBER_GT_BIJECTION'
                results.append(dict(**item,anchor_matches=anchor_scores,post_matches=post_scores,
                                    expected_mapping=expected,physical=physical))
    summary={arm:{status:sum(x['arm']==arm and x['physical']==status for x in results)
                   for status in ('CORRECT','WRONG','NOT_STAGED','NO_TWO_MEMBER_GT_BIJECTION','UNSCORABLE')}
             for arm in ARMS.values()}
    result=dict(status='SEALED_BRANCH_RECONSTRUCTION_EXACT_AND_POSTSEAL_ANCHOR_AUDIT',
        branch_frames_replayed=replay_count,reference='actual protected bank anchor + first split native masks',
        gt_reference='human edited polygons; checked=false',iou_min=.5,margin_min=.1,
        summary=summary,events=results,
        prediction_seals={name:digest(HERE/'run'/name/'public/PREDICTIONS_SEALED.json') for name in SEGMENTS})
    write_new(HERE/'run/ANCHOR_AUDIT.json',result)
    print(json.dumps(summary,ensure_ascii=False))
    return result


if __name__=='__main__':
    audit()
