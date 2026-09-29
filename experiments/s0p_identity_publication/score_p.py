"""Score sealed S0-P and archived HOLD with unchanged TrackEval and CLEAR matching."""
import gzip
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OLD=ROOT/'experiments/ms1_s0_development_8400'
sys.path.insert(0,str(OLD))
import score as old_score  # noqa: E402
from scipy.optimize import linear_sum_assignment  # noqa: E402

np=old_score.np
coco=old_score.coco
trackeval=old_score.trackeval
ARMS=('B0','OLD-HOLD','HOLD-P')
NEW=HERE/'run_8400_v2/public'
PRIOR=OLD/'run_development_v7_recovery/public'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def rows(path):
    with gzip.open(path,'rt',encoding='utf-8') as handle:
        yield from map(json.loads,handle)


def write_new(path,value):
    with path.open('x',encoding='utf-8') as handle:
        json.dump(value,handle,ensure_ascii=False,indent=2,allow_nan=False)
        handle.write('\n')


def verify_before_gt():
    seal=read(NEW/'PREDICTIONS_SEALED.json')
    old=read(PRIOR/'PREDICTIONS_SEALED.json')
    assert seal['status']==old['status']=='SEALED_AWAITING_INDEPENDENT_SCORING'
    assert seal['frames']==seal['published_frames']==old['frames']==8400
    for name,key in [('predictions_development.jsonl.gz','predictions_sha256'),
                     ('TRANSACTIONS.jsonl.gz','transactions_sha256'),
                     ('PUBLISH_LEDGER.jsonl','publish_ledger_sha256'),
                     ('EVENTS.json','events_sha256'),('CALL_LEDGER.jsonl','call_ledger_sha256'),
                     ('FREEZE.json','freeze_sha256')]:
        assert old_score.digest(NEW/name)==seal[key],name
    assert old_score.digest(PRIOR/'predictions_development.jsonl.gz')==old['predictions_sha256']
    assert old_score.digest(PRIOR/'METRICS.json')==read(NEW/'FREEZE.json')['old_hold_metrics_sha256']
    for name,entry in read(NEW/'FREEZE.json')['source'].items():
        p=Path(name)
        assert p.stat().st_size==entry['bytes'] and old_score.digest(p)==entry['sha256'],name
    with gzip.open(NEW/'predictions_development.jsonl.gz','rt',encoding='utf-8') as pred, \
         (NEW/'PUBLISH_LEDGER.jsonl').open('r',encoding='utf-8') as ledger:
        count=0
        for count,(line,raw) in enumerate(zip(pred,ledger,strict=True),1):
            item=json.loads(raw)
            assert item['frame']==count
            assert hashlib.sha256(line.encode()).hexdigest()==item['prediction_row_sha256']
            assert item['first_publish_time_monotonic']>=item['frame_received_monotonic']
        assert count==8400
    return seal,old


def switch_step(gt_ids,mask_keys,tracker_ids,similarity,previous,previous_step,frame):
    now={}
    changes=[]
    if gt_ids and tracker_ids:
        matrix=1000*np.array([[tracker_ids[j]==previous_step.get(g)
                               for j in range(len(tracker_ids))] for g in gt_ids],float)+similarity
        matrix[similarity < .5-np.finfo(float).eps]=0
        matched_rows,matched_cols=linear_sum_assignment(-matrix)
        for i,j in zip(matched_rows,matched_cols):
            if matrix[i,j]<=np.finfo(float).eps:
                continue
            gt,current=gt_ids[i],tracker_ids[j]
            old=previous.get(gt)
            if old is not None and old!=current:
                changes.append(dict(frame=frame,gt_id=gt,from_public_id=old,to_public_id=current,
                                    native_mask=mask_keys[j],matched_iou=float(similarity[i,j])))
            now[gt]=current
            previous[gt]=current
    return now,changes


def main():
    seal,old_seal=verify_before_gt()
    assert old_score.digest(old_score.GT)==old_score.GT_SHA
    events=read(NEW/'EVENTS.json')['events']
    old_events=read(PRIOR/'EVENTS.json')['B-HOLD-S0']
    gt=[]
    pred={arm:[] for arm in ARMS}
    sims=[]
    switches={arm:[] for arm in ARMS}
    prev={arm:{} for arm in ARMS}
    prev_step={arm:{} for arm in ARMS}
    changed=Counter()
    for i,(assignment,new,prior,truth,archived) in enumerate(zip(
            rows(old_score.ASSIGN),rows(NEW/'predictions_development.jsonl.gz'),
            rows(PRIOR/'predictions_development.jsonl.gz'),rows(old_score.GT),
            rows(old_score.ARCHIVED),strict=True),1):
        assert i==assignment['frame']==new['frame']==prior['frame']==truth['global_frame_id']==archived['frame']
        native=[x['mask'] for x in assignment['variants']['N0']]
        variants=dict(B0=new['variants']['B0'],
                      **{'OLD-HOLD':prior['variants']['B-HOLD-S0'],'HOLD-P':new['variants']['HOLD-P']})
        assert variants['B0']==archived['variants']['Z4Q_STABLE']==prior['variants']['B0']
        gids=[int(x['id']) for x in truth['gt_grid']]
        gt.append(gids)
        similarity=(coco.iou([old_score.rle(x['rle']) for x in truth['gt_grid']],
                             [old_score.rle(assignment['masks'][m]) for m in native],[0]*len(native))
                    if gids and native else np.zeros((len(gids),len(native))))
        sims.append(similarity)
        for arm,objects in variants.items():
            assert [x['mask'] for x in objects]==native
            ids=[int(x['id']) for x in objects]
            assert len(ids)==len(set(ids))
            pred[arm].append(ids)
            prev_step[arm],extra=switch_step(gids,native,ids,similarity,prev[arm],prev_step[arm],i)
            switches[arm].extend(extra)
        changed['B0_vs_OLD-HOLD']+=variants['B0']!=variants['OLD-HOLD']
        changed['B0_vs_HOLD-P']+=variants['B0']!=variants['HOLD-P']
        changed['OLD-HOLD_vs_HOLD-P']+=variants['OLD-HOLD']!=variants['HOLD-P']
    assert len(gt)==8400
    summary={}
    full={}
    for arm in ARMS:
        data=old_score.metric_data(gt,pred[arm],sims)
        clear=trackeval.metrics.CLEAR({'THRESHOLD':.5,'PRINT_CONFIG':False}).eval_sequence(data)
        identity=trackeval.metrics.Identity({'THRESHOLD':.5,'PRINT_CONFIG':False}).eval_sequence(data)
        hota=trackeval.metrics.HOTA({'PRINT_CONFIG':False}).eval_sequence(data)
        full[arm]=dict(CLEAR=clear,Identity=identity,HOTA=hota)
        summary[arm]=dict(IDF1=100*float(identity['IDF1']),HOTA=100*float(np.mean(hota['HOTA'])),
            AssA=100*float(np.mean(hota['AssA'])),DetA=100*float(np.mean(hota['DetA'])),
            IDSW=int(clear['IDSW']),FP=int(clear['CLR_FP']),FN=int(clear['CLR_FN']))
        assert summary[arm]['IDSW']==len(switches[arm]),arm
    archived_full=read(old_score.OLD_FULL)['Z4Q_STABLE']
    for family,values in archived_full.items():
        for key,value in values.items():
            assert np.allclose(full['B0'][family][key],value,rtol=0,atol=1e-12,equal_nan=True)
    old_metric=read(PRIOR/'METRICS.json')['metrics']['B-HOLD-S0']
    for key,value in old_metric.items():
        assert abs(summary['OLD-HOLD'][key]-value)<1e-9,(key,value,summary['OLD-HOLD'][key])
    delta={f'HOLD-P_vs_{reference}':{k:summary['HOLD-P'][k]-summary[reference][k]
            for k in summary['HOLD-P']} for reference in ('B0','OLD-HOLD')}
    result=dict(status='SCORED_AFTER_NEW_PREDICTION_SEAL',exposure='EXPOSED_DEVELOPMENT',
        frames=8400,metrics=summary,delta=delta,changed_frames=dict(changed),
        prediction_sha256=seal['predictions_sha256'],old_hold_prediction_sha256=old_seal['predictions_sha256'],
        original_paid_run='16_START_15_END_F5927_S0_UNKNOWN',old_hold_source='ZERO_HTTP_RECOVERY_REPLAY',
        new_model_http=0,new_vlm_result=None,b0_archived_exact=True)
    write_new(NEW/'METRICS.json',result)
    provenance=dict(scorer_sha256=old_score.digest(HERE/'score_p.py'),gt_path=str(old_score.GT),
        gt_bytes=old_score.GT.stat().st_size,gt_sha256=old_score.GT_SHA,
        assignment_sha256=old_score.digest(old_score.ASSIGN),
        trackeval_path=str(old_score.DEPS),all_negative_ids_scored=True,scored_after_seal=True)
    write_new(NEW/'SCORE_PROVENANCE.json',provenance)
    old_keys={tuple(x[k] for k in ('frame','gt_id','from_public_id','to_public_id')) for x in switches['OLD-HOLD']}
    b0_keys={tuple(x[k] for k in ('frame','gt_id','from_public_id','to_public_id')) for x in switches['B0']}
    new_keys={tuple(x[k] for k in ('frame','gt_id','from_public_id','to_public_id')) for x in switches['HOLD-P']}
    def annotate(x):
        match=[e for e in events if e['suspect_frame']<=x['frame']<=(e['end'] or 8400)]
        prior_match=[e for e in old_events if e['suspect_frame']<=x['frame']<=(e['end'] or 8400)]
        return dict(x,event=match[0]['id'] if match else None,
                    event_status=match[0]['status'] if match else None,
                    old_event=prior_match[0]['id'] if prior_match else None)
    def key(x):
        return tuple(x[k] for k in ('frame','gt_id','from_public_id','to_public_id'))
    switch_audit=dict(status='POSTSEAL_CLEAR_RECOMPUTED',switches={a:[annotate(x) for x in v]
        for a,v in switches.items()},counts={a:len(v) for a,v in switches.items()},
        old_only=[annotate(x) for x in switches['OLD-HOLD'] if key(x) not in new_keys],
        new_only=[annotate(x) for x in switches['HOLD-P'] if key(x) not in old_keys],
        baseline_removed=[annotate(x) for x in switches['B0'] if key(x) not in new_keys],
        baseline_new=[annotate(x) for x in switches['HOLD-P'] if key(x) not in b0_keys],
        old_temporary_roundtrips_removed=sum(x['from_public_id']<0 or x['to_public_id']<0
            for x in switches['OLD-HOLD'] if key(x) not in new_keys),
        no_id_filtering=True,prediction_sha256=seal['predictions_sha256'])
    write_new(NEW/'SWITCH_AUDIT.json',switch_audit)
    print(json.dumps(dict(metrics=summary,delta=delta,changed=dict(changed),
                          switch_counts=switch_audit['counts']),ensure_ascii=False))


if __name__=='__main__':
    main()
