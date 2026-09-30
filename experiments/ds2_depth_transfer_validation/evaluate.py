"""Independent postseal TrackEval of the four SOURCE_OLD prediction streams."""
from __future__ import annotations

import gzip
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'experiments/feeding_first_two_s0p'))
from prepare import DATA, digest, write_new
SEGMENTS = {'feeding_000701_001060':(701,1060), 'feeding_001201_001906':(1201,1906)}  # noqa: E402

spec=importlib.util.spec_from_file_location('ne1_score_for_ds1',
    ROOT/'experiments/ne1_native_first_event_association/score.py')
ne1_score=importlib.util.module_from_spec(spec)
spec.loader.exec_module(ne1_score)
mask_rles,metrics,original_score=ne1_score.mask_rles,ne1_score.metrics,ne1_score.original_score

np=original_score.np
coco=original_score.coco
ARMS=('SAM3_NATIVE','D0_GEOMETRY','D1_STATIC_LEGACY','D2_FROZEN','D3_ZERO_DRIFT_MATCHED_SCALE')
FEED=ROOT/'experiments/feeding_first_two_s0p'


def records(path):
    with gzip.open(path,'rt',encoding='utf-8') as handle:
        yield from map(json.loads,handle)


def verify_seal(run,name,start,stop):
    public=run/name/'public'
    seal=json.loads((public/'PREDICTIONS_SEALED.json').read_text(encoding='utf-8'))
    assert seal['status']=='SEALED_AWAITING_INDEPENDENT_SCORING'
    assert seal['frames']==seal['published_frames']==stop-start+1
    assert seal['new_model_http']==seal['model_cost_usd']==0
    for filename,expected in seal['artifacts_sha256'].items():
        assert digest(public/filename)==expected,filename
    freeze=json.loads((public/'FREEZE.json').read_text(encoding='utf-8'))
    assert freeze['segment']==name and freeze['original_frames']==[start,stop]
    for path,expected in freeze['code_sha256'].items():
        assert digest(path)==expected,path
    for item in freeze['derived_inputs'].values():
        path=Path(item['path'])
        assert path.stat().st_size==item['bytes'] and digest(path)==item['sha256']
    assert digest(HERE/'private'/name/'SOURCE_MANIFEST.json')==freeze['source_manifest_sha256']
    assert digest(HERE/'private'/name/'sources.json')==freeze['source_list_sha256']
    assert digest(HERE/'private'/name/'scan_v4.json')==freeze['scan_sha256']
    with gzip.open(public/'predictions.jsonl.gz','rt',encoding='utf-8') as predictions, \
         (public/'PUBLISH_LEDGER.jsonl').open('r',encoding='utf-8') as ledger:
        count=0
        for count,(line,item) in enumerate(zip(predictions,ledger,strict=True),1):
            entry=json.loads(item)
            assert entry['frame']==count and entry['global_frame']==start+count-1
            assert hashlib.sha256(line.encode()).hexdigest()==entry['prediction_row_sha256']
        assert count==stop-start+1
    return seal


def score():
    run=HERE/'run'
    all_seals=json.loads((run/'ALL_PREDICTIONS_SEALED.json').read_text())
    assert all_seals['frames']==1066
    assert all(digest(run/name/'public/PREDICTIONS_SEALED.json')==v for name,v in all_seals['seals'].items())
    seals={name:verify_seal(run,name,*bounds) for name,bounds in SEGMENTS.items()}
    combined_truth=[]
    combined={arm:[] for arm in ARMS}
    combined_sims=[]
    segment_metrics={}
    reference={}
    changed={}
    for segment_index,(name,(start,stop)) in enumerate(SEGMENTS.items()):
        truth=[]
        predictions={arm:[] for arm in ARMS}
        sims=[]
        reference_hash=hashlib.sha256()
        changed[name]={f'{arm}_vs_NATIVE':0 for arm in ARMS[1:]}
        changed[name]['D2_vs_D0']=0
        changed[name]['D2_vs_D1']=0
        changed[name]['D2_vs_D3']=0
        for i,(assignment,prediction) in enumerate(zip(
                records(HERE/'private'/name/'assignments.jsonl.gz'),
                records(run/name/'public/predictions.jsonl.gz'),strict=True),1):
            global_frame=start+i-1
            assert assignment['frame']==prediction['frame']==i
            assert assignment['global_frame_id']==prediction['global_frame']==global_frame
            path=DATA/'labels_640x360'/f'{global_frame:06d}.json'
            raw=path.read_bytes()
            reference_hash.update(path.name.encode()+b'\0'+raw)
            gt=json.loads(raw)
            gt_ids,gt_masks=mask_rles(gt['shapes'])
            native=[item['mask'] for item in assignment['variants']['N0']]
            masks=[original_score.rle(assignment['masks'][key]) for key in native]
            sim=(np.asarray(coco.iou(gt_masks,masks,[0]*len(masks)),float)
                 if gt_masks and masks else np.zeros((len(gt_ids),len(native))))
            truth.append(gt_ids)
            sims.append(sim)
            combined_truth.append([n+segment_index*10_000_000 for n in gt_ids])
            combined_sims.append(sim)
            for arm in ARMS:
                objects=prediction['variants'][arm]
                assert [x['mask'] for x in objects]==native
                ids=[int(x['id']) for x in objects]
                assert len(ids)==len(set(ids))
                predictions[arm].append(ids)
                combined[arm].append([n+segment_index*10_000_000 for n in ids])
            for arm in ARMS[1:]:
                changed[name][f'{arm}_vs_NATIVE']+=prediction['variants'][arm]!=prediction['variants']['SAM3_NATIVE']
            changed[name]['D2_vs_D0']+=prediction['variants']['D2_FROZEN']!=prediction['variants']['D0_GEOMETRY']
            changed[name]['D2_vs_D3']+=prediction['variants']['D2_FROZEN']!=prediction['variants']['D3_ZERO_DRIFT_MATCHED_SCALE']
            changed[name]['D2_vs_D1']+=prediction['variants']['D2_FROZEN']!=prediction['variants']['D1_STATIC_LEGACY']
        assert len(truth)==stop-start+1
        segment_metrics[name]={arm:metrics(truth,predictions[arm],sims) for arm in ARMS}
        reference[name]=dict(label_dir=str(DATA/'labels_640x360'),frames=len(truth),
            ordered_file_bytes_sha256=reference_hash.hexdigest(),
            checked_field='false_in_source; human edited, not independently certified')
    pooled={arm:metrics(combined_truth,combined[arm],combined_sims) for arm in ARMS}
    delta={f'{arm}_vs_{other}':{key:pooled[arm][key]-pooled[other][key]
        for key in ('IDF1','HOTA','AssA','DetA','IDSW','FP','FN')}
        for arm,other in (('D2_FROZEN','D0_GEOMETRY'),('D2_FROZEN','D1_STATIC_LEGACY'),
                          ('D2_FROZEN','SAM3_NATIVE'),('D2_FROZEN','D3_ZERO_DRIFT_MATCHED_SCALE'))}
    result=dict(status='SCORED_AFTER_BOTH_PREDICTION_SEALS',frames=1066,
        input='SOURCE_OLD saved batched SAM3 raw polygons and aligned depth_mm',
        segment_metrics=segment_metrics,pooled_metrics=pooled,pooled_delta=delta,
        changed_frames=changed,reference=reference,
        seal_sha256={name:digest(run/name/'public/PREDICTIONS_SEALED.json') for name in SEGMENTS},
        new_model_http=0,model_cost_usd=0,no_negative_id_filtering=True,
        segment_identity_reset=True,
        pooled_method='disjoint_GT_and_prediction_ID_namespaces_per_segment')
    write_new(run/'METRICS.json',result)
    write_new(run/'SCORE_PROVENANCE.json',dict(score_sha256=digest(HERE/'score.py'),
        scored_after_both_seals=True,trackeval_path=str(original_score.DEPS),
        reference=reference,segment_seal_sha256=result['seal_sha256']))
    print(json.dumps(dict(pooled=pooled,delta=delta,changed=changed),ensure_ascii=False))


def actual_anchor_audit():
    import types
    sys.path.insert(0,str(ROOT/'experiments/ds1_depth_only'))
    import postseal as frozen_audit
    function=types.FunctionType(frozen_audit.audit.__code__,
        dict(frozen_audit.audit.__globals__,HERE=HERE,score=sys.modules[__name__],ARMS=ARMS),
        'ds2_anchor_audit',frozen_audit.audit.__defaults__)
    function()


def verify_publication():
    checked=[]; q_checks=group_checks=0
    for name,(start,stop) in SEGMENTS.items():
        verify_seal(HERE/'run',name,start,stop)
        public=HERE/'run'/name/'public'
        actual=list(records(public/'predictions.jsonl.gz'))
        inputs=list(records(HERE/'private'/name/'assignments.jsonl.gz'))
        states={(x['frame'],x['arm']):x for x in records(public/'DEPTH_STATES.jsonl.gz')}
        events=json.loads((public/'EVENTS.json').read_text())
        ledger={x['frame']:x for x in map(json.loads,(public/'PUBLISH_LEDGER.jsonl').read_text().splitlines())}
        assert len(actual)==len(ledger)==len(inputs)==stop-start+1
        for prediction,assignment in zip(actual,inputs,strict=True):
            assert prediction['variants']['SAM3_NATIVE']==assignment['variants']['N0']
            native=prediction['variants']['SAM3_NATIVE']
            for arm in ARMS[1:]:
                objects=prediction['variants'][arm]
                assert [x['mask'] for x in objects]==[x['mask'] for x in native]
                assert len(objects)==len(set(x['id'] for x in objects))
        for arm in ARMS[1:]:
            for e in events[arm]:
                for group in e['group_observations']:
                    live=states[(group['frame'],arm)]['live'].get(str(group['source']))
                    assert not live or group['frame'] not in live['sample_frames']
                    group_checks+=1
                for fragment in e['depth_frozen'].values():
                    samples=fragment['samples']
                    assert all(x['frame']<e['suspect_frame'] for x in samples)
                    assert all(b['frame']==a['frame']+1 and b['time']>a['time'] for a,b in zip(samples,samples[1:]))
                q=e['q']
                if q is None: continue
                assert e['evidence_cutoff_frame']==q
                assert all(x['frame']==q for x in e['post_first_observations'].values())
                pub=ledger[q]['event_publish'][arm]
                assert pub['post_sample_count']==1
                mapping={int(x['mask'][2:]):x['id'] for x in actual[q-1]['variants'][arm]}
                assert {int(n):v for n,v in pub['first_public_pair'].items()}=={int(n):mapping[int(n)] for n in e['post_first_observations']}
                if not e['restore']['status'].startswith('LOCAL_FALLBACK'):
                    assert {int(n):v for n,v in e['restore']['mapping'].items()}=={int(n):mapping[int(n)] for n in e['post_first_observations']}
                    for n in e['post_first_observations']:
                        live=states[(q,arm)]['live'].get(n)
                        assert not live or all(f>=q for f in live['sample_frames'])
                q_checks+=1
        checked.append(dict(segment=name,frames=len(actual),native_exact=True))
    write_new(HERE/'run/VERIFICATION.json',dict(status='PASS_BEFORE_GT_SCORING',segments=checked,
        first_publication_checks=q_checks,group_checks=group_checks,group_violations=0,deleted_masks=0))


if __name__=='__main__':
    verify_publication()
    score()
    actual_anchor_audit()
