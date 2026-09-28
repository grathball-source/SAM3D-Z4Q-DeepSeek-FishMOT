"""Independent development TrackEval scoring after a complete prediction seal."""
import gzip
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

DEPS=Path('E:/CAU/D-MOT/tools/jev_z4q_scene_v1_20260922/deps')
sys.path.insert(0,str(DEPS))
from pycocotools import mask as coco  # noqa: E402
for alias,value in (('int',int),('float',float),('bool',bool)):
    if alias not in np.__dict__:
        setattr(np,alias,value)
import trackeval  # noqa: E402

from source_scan import ASSIGN  # noqa: E402

HERE=Path(__file__).resolve().parent
GT=Path('E:/CAU/D-MOT/Depth-Anchored Association/sam3_training_free_association/v03/results/error_audit/gt_grid_and_native_alignment.jsonl.gz')
GT_SHA='ab6bc733911cc07dc4be70ef3a893c1475aca6908fc6ce8bc376923597eed5d1'
ARCHIVED=Path('E:/CAU/D-MOT/tools/sam3_depth_return_guard_20260918/completion_evidence/experiment/predictions_development.jsonl.gz')
OLD_FULL=Path('E:/CAU/D-MOT/tools/sam3_depth_return_guard_20260918/completion_evidence/experiment/fullmetrics_development.json')
ARMS=('B0','B-HOLD-S0','B-VLM-S0')


def digest(path):
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle,'sha256').hexdigest()


def rows(path):
    with gzip.open(path,'rt',encoding='utf-8') as handle:
        yield from map(json.loads,handle)


def rle(x):
    counts=x['counts']
    return dict(size=x['size'],counts=counts.encode() if isinstance(counts,str) else counts)


def metric_data(gt,pred,sims):
    gids=sorted({x for frame in gt for x in frame})
    pids=sorted({x for frame in pred for x in frame})
    gm={x:i for i,x in enumerate(gids)}
    pm={x:i for i,x in enumerate(pids)}
    return dict(num_timesteps=len(gt),num_gt_ids=len(gids),num_tracker_ids=len(pids),
        num_gt_dets=sum(map(len,gt)),num_tracker_dets=sum(map(len,pred)),
        gt_ids=[np.array([gm[x] for x in frame],int) for frame in gt],
        tracker_ids=[np.array([pm[x] for x in frame],int) for frame in pred],
        similarity_scores=sims)


def full(run_name):
    public=HERE/run_name/'public'
    seal=json.loads((public/'PREDICTIONS_SEALED.json').read_text(encoding='utf-8'))
    assert seal['status']=='SEALED_AWAITING_INDEPENDENT_SCORING'
    assert seal['frames']==seal['published_frames']==8400
    artifacts=(('predictions_development.jsonl.gz','predictions_sha256'),
               ('TRANSACTIONS.jsonl.gz','transactions_sha256'),
               ('EVENTS.json','events_sha256'),('CALL_LEDGER.jsonl','call_ledger_sha256'),
               ('PUBLISH_LEDGER.jsonl','publish_ledger_sha256'))
    for filename,key in artifacts:
        assert digest(public/filename)==seal[key],filename
    manifest=json.loads((public/'SOURCE_MANIFEST.json').read_text(encoding='utf-8'))
    for name,entry in manifest['inputs'].items():
        path=Path(name)
        assert path.stat().st_size==entry['bytes'] and digest(path)==entry['sha256'],name
    pred_path=public/'predictions_development.jsonl.gz'
    with gzip.open(pred_path,'rt',encoding='utf-8') as predictions, \
         (public/'PUBLISH_LEDGER.jsonl').open('r',encoding='utf-8') as published:
        count=0
        for index,(line,record) in enumerate(zip(predictions,published,strict=True),1):
            item=json.loads(record)
            assert item['frame']==index and hashlib.sha256(line.encode()).hexdigest()==item['prediction_row_sha256']
            assert item['first_publish_time_monotonic']>=item['frame_received_monotonic']
            count=index
        assert count==8400

    # The only GT open occurs after all source, output and publication checks.
    assert digest(GT)==GT_SHA
    gt=[]
    pred={name:[] for name in ARMS}
    sims=[]
    changed={name:0 for name in ('B0_vs_HOLD','B0_vs_VLM','HOLD_vs_VLM')}
    for index,(a,p,t,archived) in enumerate(zip(rows(ASSIGN),rows(pred_path),rows(GT),
                                             rows(ARCHIVED),strict=True),1):
        assert a['frame']==p['frame']==p['global_frame']==t['global_frame_id']==archived['frame']==index
        assert p['variants']['B0']==archived['variants']['Z4Q_STABLE']
        native=[x['mask'] for x in a['variants']['N0']]
        assert all(x.startswith('n:') for x in native)
        gid=[int(x['id']) for x in t['gt_grid']]
        gt.append(gid)
        matrix=(coco.iou([rle(x['rle']) for x in t['gt_grid']],
                         [rle(a['masks'][key]) for key in native],[0]*len(native))
                if gid and native else np.zeros((len(gid),len(native))))
        sims.append(matrix)
        for arm in ARMS:
            objects=p['variants'][arm]
            assert [x['mask'] for x in objects]==native
            ids=[int(x['id']) for x in objects]
            assert len(ids)==len(set(ids))
            pred[arm].append(ids)
        changed['B0_vs_HOLD']+=p['variants']['B0']!=p['variants']['B-HOLD-S0']
        changed['B0_vs_VLM']+=p['variants']['B0']!=p['variants']['B-VLM-S0']
        changed['HOLD_vs_VLM']+=p['variants']['B-HOLD-S0']!=p['variants']['B-VLM-S0']
    assert len(gt)==8400

    full_metrics={}
    summary={}
    for arm in ARMS:
        data=metric_data(gt,pred[arm],sims)
        clear=trackeval.metrics.CLEAR({'THRESHOLD':.5,'PRINT_CONFIG':False}).eval_sequence(data)
        identity=trackeval.metrics.Identity({'THRESHOLD':.5,'PRINT_CONFIG':False}).eval_sequence(data)
        hota=trackeval.metrics.HOTA({'PRINT_CONFIG':False}).eval_sequence(data)
        full_metrics[arm]=dict(CLEAR=clear,Identity=identity,HOTA=hota)
        summary[arm]=dict(IDF1=100*float(identity['IDF1']),
            HOTA=100*float(np.mean(hota['HOTA'])),
            AssA=100*float(np.mean(hota['AssA'])),
            DetA=100*float(np.mean(hota['DetA'])),
            IDSW=int(clear['IDSW']),FP=int(clear['CLR_FP']),FN=int(clear['CLR_FN']))
    old=json.loads(OLD_FULL.read_text(encoding='utf-8'))['Z4Q_STABLE']
    for family,values in old.items():
        for key,value in values.items():
            assert np.allclose(full_metrics['B0'][family][key],value,rtol=0,atol=1e-12,equal_nan=True),(family,key)
    delta={arm:{key:summary[arm][key]-summary['B0'][key] for key in summary['B0']}
           for arm in ARMS[1:]}
    delta['B-VLM-S0_vs_B-HOLD-S0']={key:summary['B-VLM-S0'][key]-summary['B-HOLD-S0'][key]
                                     for key in summary['B0']}
    result=dict(status='SCORED_EXPOSED_DEVELOPMENT',frames=8400,mode=seal['mode'],
        metrics=summary,delta=delta,changed_frames=changed,
        selected_episodes=seal['selected_episodes'],http_attempts=seal['http_attempts'],
        interpretation=('DRY_NO_API_MODEL_UNTESTED' if seal['mode']=='dry' else 'REAL_MODEL_TRIAL'),
        archived_B0_fullmetrics_exact=True,prediction_sha256=seal['predictions_sha256'])
    target=public/'METRICS.json'
    assert not target.exists(),target
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    provenance=dict(scorer_sha256=digest(Path(__file__)),gt_path=str(GT),gt_bytes=GT.stat().st_size,
        gt_sha256=GT_SHA,assignment_sha256=digest(ASSIGN),archived_metrics_sha256=digest(OLD_FULL),
        trackeval_path=str(DEPS),scored_after_seal=True)
    (public/'SCORE_PROVENANCE.json').write_text(json.dumps(provenance,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(metrics=summary,delta=delta,changed_frames=changed),ensure_ascii=False))


if __name__=='__main__':
    if len(sys.argv)!=2 or sys.argv[1] not in ('dry_run_corrected','dry_run_v3','dry_run_v4','dry_run_v5','dry_run_v6','run_development_corrected_paid'):
        raise SystemExit('usage: score.py dry_run_corrected|dry_run_v3|dry_run_v4|dry_run_v5|run_development_corrected_paid')
    full(sys.argv[1])
