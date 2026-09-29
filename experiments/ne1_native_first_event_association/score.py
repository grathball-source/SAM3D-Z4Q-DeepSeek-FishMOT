"""Independently score the sealed NE-1 SOURCE_OLD prediction streams."""
import gzip
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
FEED = ROOT/'experiments/feeding_first_two_s0p'
sys.path.insert(0, str(ROOT/'experiments/ms1_s0_development_8400'))
sys.path.insert(0, str(FEED))
spec=importlib.util.spec_from_file_location('original_ms1_score',
    ROOT/'experiments/ms1_s0_development_8400/score.py')
original_score=importlib.util.module_from_spec(spec)
spec.loader.exec_module(original_score)
from prepare import DATA, SEGMENTS, digest, write_new  # noqa: E402

np = original_score.np
coco = original_score.coco
trackeval = original_score.trackeval
cv2 = __import__('cv2')
ARMS = ('SAM3_NATIVE','Z4Q_FROZEN','EVENT_NUM','EVENT_VLM')


def records(path):
    with gzip.open(path,'rt',encoding='utf-8') as handle:
        yield from map(json.loads,handle)


def mask_rles(shapes):
    masks = {}
    for shape in shapes:
        assert shape['shape_type']=='polygon'
        identity=int(shape['group_id'])
        item=masks.setdefault(identity,np.zeros((360,640),np.uint8))
        points=np.rint(np.asarray(shape['points'],float)).astype(np.int32)
        cv2.fillPoly(item,[points],1)
    identities=sorted(masks)
    encoded=[coco.encode(np.asfortranarray(masks[n])) for n in identities]
    return identities,encoded


def metrics(truth,pred,sims):
    data=original_score.metric_data(truth,pred,sims)
    clear=trackeval.metrics.CLEAR({'THRESHOLD':.5,'PRINT_CONFIG':False}).eval_sequence(data)
    identity=trackeval.metrics.Identity({'THRESHOLD':.5,'PRINT_CONFIG':False}).eval_sequence(data)
    hota=trackeval.metrics.HOTA({'PRINT_CONFIG':False}).eval_sequence(data)
    return dict(IDF1=100*float(identity['IDF1']),HOTA=100*float(np.mean(hota['HOTA'])),
                AssA=100*float(np.mean(hota['AssA'])),DetA=100*float(np.mean(hota['DetA'])),
                IDSW=int(clear['IDSW']),FP=int(clear['CLR_FP']),FN=int(clear['CLR_FN']),
                GT=int(data['num_gt_dets']),predictions=int(data['num_tracker_dets']))


def checked_segment(run, name, start, stop):
    public=run/name/'public'
    seal=json.loads((public/'PREDICTIONS_SEALED.json').read_text(encoding='utf-8'))
    assert seal['status']=='SEALED_AWAITING_INDEPENDENT_SCORING'
    assert seal['frames']==seal['published_frames']==stop-start+1
    artifacts=(('predictions.jsonl.gz','predictions_sha256'),
               ('TRANSACTIONS.jsonl.gz','transactions_sha256'),
               ('EVENTS.json','events_sha256'),
               ('AUTO_RECONNECT_AUDIT.json','auto_reconnect_audit_sha256'),
               ('CALL_LEDGER.jsonl','call_ledger_sha256'),
               ('PUBLISH_LEDGER.jsonl','publish_ledger_sha256'),('FREEZE.json','freeze_sha256'))
    for filename,key in artifacts:
        assert digest(public/filename)==seal[key],filename
    freeze=json.loads((public/'FREEZE.json').read_text(encoding='utf-8'))
    assert freeze['segment']==name and freeze['original_frames']==[start,stop]
    for path,expected in freeze['code_sha256'].items():
        assert digest(path)==expected,path
    for item in freeze['derived_inputs'].values():
        path=Path(item['path'])
        assert path.stat().st_size==item['bytes'] and digest(path)==item['sha256']
    with gzip.open(public/'predictions.jsonl.gz','rt',encoding='utf-8') as predictions, \
         (public/'PUBLISH_LEDGER.jsonl').open('r',encoding='utf-8') as ledger:
        count=0
        for count,(line,record) in enumerate(zip(predictions,ledger,strict=True),1):
            item=json.loads(record)
            assert item['frame']==count and item['global_frame']==start+count-1
            assert hashlib.sha256(line.encode()).hexdigest()==item['prediction_row_sha256']
            assert item['first_publish_time_monotonic']>=item['frame_received_monotonic']
        assert count==stop-start+1
    return seal


def score(run_name):
    run=HERE/run_name
    assert run_name in ('run','dry_v2')
    seals={name:checked_segment(run,name,*bounds) for name,bounds in SEGMENTS.items()}
    all_sims=[]
    combined_truth=[]
    combined_predictions={arm:[] for arm in ARMS}
    segment_metrics={}
    reference_inputs={}
    changed={name:{'EVENT_NUM_vs_NATIVE':0,'EVENT_VLM_vs_NATIVE':0,
                   'EVENT_VLM_vs_NUM':0} for name in SEGMENTS}
    for segment_index,(name,(start,stop)) in enumerate(SEGMENTS.items()):
        public=run/name/'public'
        truth=[]
        predictions={arm:[] for arm in ARMS}
        sims=[]
        reference_hash=hashlib.sha256()
        for i,(assignment,prediction) in enumerate(zip(
                records(FEED/'private'/name/'assignments.jsonl.gz'),
                records(public/'predictions.jsonl.gz'),strict=True),1):
            global_frame=start+i-1
            assert assignment['frame']==prediction['frame']==i
            assert assignment['global_frame_id']==prediction['global_frame']==global_frame
            path=DATA/'labels_640x360'/f'{global_frame:06d}.json'
            raw=path.read_bytes()
            reference_hash.update(path.name.encode()+b'\0'+raw)
            gt=json.loads(raw)
            gt_ids,gt_masks=mask_rles(gt['shapes'])
            native=[item['mask'] for item in assignment['variants']['N0']]
            predicted_masks=[original_score.rle(assignment['masks'][key]) for key in native]
            similarity=(np.asarray(coco.iou(gt_masks,predicted_masks,[0]*len(predicted_masks)),float)
                        if gt_masks and predicted_masks else np.zeros((len(gt_ids),len(native))))
            truth.append(gt_ids)
            sims.append(similarity)
            for arm in ARMS:
                objects=prediction['variants'][arm]
                assert [item['mask'] for item in objects]==native
                ids=[int(item['id']) for item in objects]
                assert len(ids)==len(set(ids))
                predictions[arm].append(ids)
                combined_predictions[arm].append([n+segment_index*10_000_000 for n in ids])
            combined_truth.append([n+segment_index*10_000_000 for n in gt_ids])
            all_sims.append(similarity)
            changed[name]['EVENT_NUM_vs_NATIVE']+=prediction['variants']['SAM3_NATIVE']!=prediction['variants']['EVENT_NUM']
            changed[name]['EVENT_VLM_vs_NATIVE']+=prediction['variants']['SAM3_NATIVE']!=prediction['variants']['EVENT_VLM']
            changed[name]['EVENT_VLM_vs_NUM']+=prediction['variants']['EVENT_NUM']!=prediction['variants']['EVENT_VLM']
        assert len(truth)==stop-start+1
        reference_inputs[name]=dict(label_dir=str(DATA/'labels_640x360'),frames=len(truth),
                                    ordered_file_bytes_sha256=reference_hash.hexdigest(),
                                    checked_field='false_in_source; human edited, not independently certified')
        segment_metrics[name]={arm:metrics(truth,predictions[arm],sims) for arm in ARMS}
    pooled={arm:metrics(combined_truth,combined_predictions[arm],all_sims) for arm in ARMS}
    delta={f'{arm}_vs_{reference}':{key:pooled[arm][key]-pooled[reference][key]
            for key in pooled[arm] if key not in ('GT','predictions')}
           for arm,reference in (('Z4Q_FROZEN','SAM3_NATIVE'),
                                 ('EVENT_NUM','SAM3_NATIVE'),('EVENT_VLM','SAM3_NATIVE'),
                                 ('EVENT_VLM','EVENT_NUM'),('EVENT_NUM','Z4Q_FROZEN'),
                                 ('EVENT_VLM','Z4Q_FROZEN'))}
    result=dict(status='SCORED_AFTER_BOTH_PREDICTION_SEALS',run=run_name,
                frames=sum(stop-start+1 for start,stop in SEGMENTS.values()),
                input='SOURCE_OLD saved batched SAM3 raw preannotations + aligned depth_mm; not native continuous SAM3',
                segment_metrics=segment_metrics,pooled_metrics=pooled,pooled_delta=delta,
                changed_frames=changed,reference=reference_inputs,
                seal_sha256={name:digest(run/name/'public/PREDICTIONS_SEALED.json') for name in SEGMENTS},
                new_model_http=sum(item['http_attempts'] for item in seals.values()),
                peak_charge_upper_usd=sum(item['peak_charge_upper_usd'] for item in seals.values()),
                no_negative_id_filtering=True,segment_identity_reset=True,
                pooled_method='disjoint_GT_and_prediction_ID_namespaces_per_segment')
    write_new(run/'METRICS.json',result)
    write_new(run/'SCORE_PROVENANCE.json',dict(score_sha256=digest(HERE/'score.py'),
              scored_after_both_seals=True,trackeval_path=str(original_score.DEPS),
              reference=reference_inputs,segment_seal_sha256=result['seal_sha256']))
    print(json.dumps(dict(pooled=pooled,delta=delta,http=result['new_model_http']),ensure_ascii=False))
    return result


if __name__=='__main__':
    if len(sys.argv)!=2:
        raise SystemExit('usage: score.py dry|run')
    score(sys.argv[1])
