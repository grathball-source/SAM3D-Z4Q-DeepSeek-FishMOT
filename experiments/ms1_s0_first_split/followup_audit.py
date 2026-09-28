"""Postseal physical-member public-ID switches; never feeds replay decisions."""
import gzip
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
PUBLIC=HERE/'run_ms1s0_20260928/public'
MATCHES=HERE.parent/'merge_split_identity_memory/private_source/offline_matches_validation.jsonl.gz'


def rows(path):
    with gzip.open(path,'rt',encoding='utf-8') as handle:
        yield from map(json.loads,handle)


def main():
    seal=json.loads((PUBLIC/'PREDICTIONS_SEALED.json').read_text(encoding='utf-8'))
    assert hashlib.sha256((PUBLIC/'predictions_validation.jsonl.gz').read_bytes()).hexdigest()==seal['predictions_sha256']
    result=json.loads((PUBLIC/'FIRST_SPLIT_RESULTS.json').read_text(encoding='utf-8'))[0]
    q=result['split_first_frame']
    gt_values=set(result['reference_pre_consensus'].values())
    assert len(gt_values)==2 and None not in gt_values
    arms=('B0','B-HOLD-S0','B-VLM-S0')
    totals={arm:{str(gt):dict(assessable_frames=0,adjacent_switches=0,
                               switch_after_gap=0,first_public_id=None,last_public_id=None)
                 for gt in gt_values} for arm in arms}
    last={arm:{gt:None for gt in gt_values} for arm in arms}
    for row,match in zip(rows(PUBLIC/'predictions_validation.jsonl.gz'),rows(MATCHES),strict=True):
        frame=row['frame']
        assert frame==match['frame']
        if frame<q:
            continue
        members={gt:[int(n) for n,g in match['native_to_gt'].items() if g==gt] for gt in gt_values}
        for arm in arms:
            outputs={int(x['mask'].split(':')[1]):x['id'] for x in row['variants'][arm]}
            for gt in gt_values:
                if len(members[gt])!=1 or members[gt][0] not in outputs:
                    continue
                public=outputs[members[gt][0]]
                record=totals[arm][str(gt)]
                record['assessable_frames']+=1
                if record['first_public_id'] is None:
                    record['first_public_id']=public
                previous=last[arm][gt]
                if previous and previous[1]!=public:
                    key='adjacent_switches' if previous[0]==frame-1 else 'switch_after_gap'
                    record[key]+=1
                record['last_public_id']=public
                last[arm][gt]=(frame,public)
    scan=json.loads((HERE/'private_source/scan.json').read_text(encoding='utf-8'))
    output=dict(status='POSTSEAL_EXPOSED_VALIDATION',q=q,physical_gt_ids=sorted(gt_values),
        through_frame=2888,per_arm=totals,
        later_strict_prediction_merge_suspects=sum(x['frame']>q for x in scan['suspects']),
        remerge_interpretation='No later strict predicted merge opportunity in frozen scan; unobserved physical remerge is not asserted absent.',
        source_prediction_sha256=seal['predictions_sha256'])
    target=PUBLIC/'FOLLOWUP_AUDIT.json'
    assert not target.exists()
    target.write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(output))


if __name__=='__main__':
    main()
