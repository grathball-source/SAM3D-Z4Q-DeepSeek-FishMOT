"""Authoritative original baseline GT, including its original review version."""
from common import *
import zipfile
import evaluate as score
from score_remaining import ARCHIVE,original_reference

def reference_rows(name):
    if name!='fishsa_validation_2888':yield from original_reference(name);return
    with zipfile.ZipFile(ARCHIVE) as z:
        manifest=json.loads(z.read('manifest.json'));assert len(manifest['gt'])==12188
        for g in range(9301,12189):
            row=manifest['gt'][g-1];raw=z.read(row['key'])
            assert hashlib.sha256(raw).hexdigest()==row['sha256']
            label=json.loads(raw);assert (label['imageHeight'],label['imageWidth'])==(1080,1920)
            ids,encoded=score.polygon_reference(label['shapes'],1080,1920,transform=True)
            yield g,ids,encoded

def main():
    score.verify_all()
    metadata={r['source_color_index']+1:r for r in rows(WORK/'data/AlignedDataset_v1/manifest.jsonl')}
    with zipfile.ZipFile(ARCHIVE) as z:
        manifest=json.loads(z.read('manifest.json'))
        changed=[dict(global_frame=g,baseline_annotation_sha256=manifest['gt'][g-1]['sha256'],aligned_package_annotation_sha256=metadata[g]['annotation_sha256'])
            for g in range(9301,12189) if manifest['gt'][g-1]['sha256']!=metadata[g]['annotation_sha256']]
    write_new(HERE/'ORIGINAL_REFERENCE_SELECTION.json',dict(status='ORIGINAL_BASELINE_PROTOCOL_REFERENCE_FIXED',
        prediction_all_seal=artifact(RUN/'ALL_PREDICTIONS_SEALED.json'),scoring_adapter=artifact(__file__),archive=artifact(ARCHIVE),
        authority=artifact(WORK/'tools/sam3_i1_validation_20260915/prepare_truth.py'),
        annotation_version_differences=changed,aligned_package_reference_not_substituted=True,
        explanation='Aligned package snapshot also includes annotation revisions; use original baseline inputs.zip GT exactly, not updated package annotations.',
        source_chosen_by_original_protocol_not_score=True,new_predictions=0,new_model_http=0))
    score.reference_rows=reference_rows
    results={n:read(RUN/n/'public/METRICS.json') for n in SEGMENTS if (RUN/n/'public/METRICS.json').exists()}
    for n in SEGMENTS:
        if n not in results:results[n]=score.score_segment(n)[0]
    pool_gt=[];pool_pred={a:[] for a in ARMS};pool_sims=[]
    for n in (n for n in SEGMENTS if n.startswith('feeding_')):
        for a,p,t in zip(rows(input_dir(n)/'assignments.jsonl.gz'),rows(RUN/n/'public/predictions.jsonl.gz'),original_reference(n),strict=True):
            _,ids,encoded=t;keys=[x['mask'] for x in a['variants']['N0']];pr=[score.rle(a['masks'][k]) for k in keys]
            sim=score.np.asarray(score.coco.iou(encoded,pr,[0]*len(pr)),float).reshape(len(ids),len(pr)) if ids and pr else score.np.zeros((len(ids),len(pr)))
            pool_gt.append([(n,x) for x in ids]);pool_sims.append(sim)
            for arm in ARMS:pool_pred[arm].append([(n,x['id']) for x in p['variants'][arm]])
    pooled={a:score.metrics(pool_gt,pool_pred[a],pool_sims)[0] for a in ARMS}
    final=dict(status='SCORED_AFTER_ALL_EIGHT_PREDICTION_AND_ACCESS_SEALS',frames=20098,segments=results,
        feeding_pooled=dict(frames=1471,metrics=pooled,delta=score.delta(pooled)),new_model_http=0,cost_usd=0,
        depth_necessary='NOT_IDENTIFIED_WITH_TWO_ARMS',physical_depth_accuracy='UNKNOWN',all_seal=artifact(RUN/'ALL_PREDICTIONS_SEALED.json'))
    write_new(RUN/'METRICS.json',final)
    write_new(RUN/'SCORE_PROVENANCE.json',dict(scorer=artifact(HERE/'evaluate.py'),initial_pin_correction=artifact(HERE/'SCORING_FREEZE.json'),
        authoritative_reference_adapter=artifact(__file__),reference_version_selection=artifact(HERE/'ORIGINAL_REFERENCE_SELECTION.json'),
        source_and_runtime_verified=True,development_reference=artifact(score.GT_DEV),validation_original_archive=artifact(ARCHIVE),
        reference_opened_after_all_seals=True,trackeval_package=artifact(Path(score.trackeval.__file__)),masked_or_ignored_ids=0))
    print(json.dumps(dict(feeding=final['feeding_pooled'],segments={n:r['delta'] for n,r in results.items()})),flush=True)
if __name__=='__main__':main()
