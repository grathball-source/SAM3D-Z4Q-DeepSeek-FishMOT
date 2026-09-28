"""Read-only old/new output accounting after the MS1-R prediction seal."""
from collections import Counter, defaultdict

from provider import write_new
from replay import HERE, OLD, read, rows, sha


def main():
    current=HERE/'run_ms1r_20260928/public'
    prior=OLD/'run_ms1_20260928/public'
    seal=read(current/'PREDICTIONS_SEALED.json')
    assert sha(current/'predictions_validation.jsonl.gz')==seal['predictions_sha256']
    event=read(current/'EVENTS.json')['B-VLM-R'][0]
    counts=Counter()
    stages=defaultdict(Counter)
    residual=[]
    changed_by_source=Counter()
    for before,after in zip(rows(prior/'predictions_validation.jsonl.gz'),
                            rows(current/'predictions_validation.jsonl.gz'),strict=True):
        frame=after['frame']
        assert frame==before['frame']
        assert before['variants']['B0']==after['variants']['B0']
        assert after['variants']['B-HOLD-R']==after['variants']['B-VLM-R']
        stage=('before' if frame<event['suspect_frame'] else
               'group' if frame<event['post_start'] else
               'split_pending' if frame<event['q'] else 'q_or_after')
        for old_arm,new_arm in (('B-HOLD','B-HOLD-R'),('B-VLM','B-VLM-R')):
            old=before['variants'][old_arm]
            new=after['variants'][new_arm]
            assert [x['mask'] for x in old]==[x['mask'] for x in new]
            if old!=new:
                counts[old_arm+'_changed_frames']+=1
                stages[stage][old_arm+'_changed_frames']+=1
            for a,b in zip(old,new):
                if a['id']!=b['id']:
                    counts[old_arm+'_changed_detections']+=1
                    stages[stage][old_arm+'_changed_detections']+=1
                    changed_by_source[a['mask']]+=1
        if event['suspect_frame']<=frame<event['post_start']:
            mapping={x['mask']:x['id'] for x in after['variants']['B-HOLD-R']}
            residual.append(dict(frame=frame,raw_residual_mask_present='n:4' in mapping,
                                 temporary_id=mapping.get('n:4') if mapping.get('n:4',0)<0 else None))
    report=dict(status='POSTSEAL_NO_GT_OUTPUT_COMPARISON',old_seal_sha256=sha(prior/'PREDICTIONS_SEALED.json'),
                new_seal_sha256=sha(current/'PREDICTIONS_SEALED.json'),counts=dict(counts),
                by_stage={stage:dict(value) for stage,value in stages.items()},
                changed_detections_by_mask=dict(changed_by_source),
                first_suspect=event['suspect_frame'],post_start=event['post_start'],q=event['q'],
                temporary_residual_by_group_frame=residual,
                note='Output differences only; physical-reference verdict is in independent scorer.')
    write_new(current/'POSTSEAL_OLD_NEW_COMPARISON.json',report)
    print(report)


if __name__=='__main__':
    main()
