"""Resume independent scoring using the original baseline GT archive.

The package's labels_original has rewritten imagePath/imageData/dataset_frame_id;
annotation_sha256 describes the original archive bytes, not that rewritten file.
No prediction or scientific bytes change. Previously scored outputs stay read-only.
"""
from common import *
import zipfile
import evaluate as score
ARCHIVE=WORK/'output/evaluation/sam3_trackeval_20260912_1705/inputs.zip'
def validation_reference(name):
    if name!='fishsa_validation_2888':yield from original_reference(name);return
    metadata={r['source_color_index']+1:r for r in rows(WORK/'data/AlignedDataset_v1/manifest.jsonl')}
    with zipfile.ZipFile(ARCHIVE) as z:
        manifest=json.loads(z.read('manifest.json'));assert len(manifest['gt'])==12188
        for g in range(9301,12189):
            row=manifest['gt'][g-1];raw=z.read(row['key'])
            assert hashlib.sha256(raw).hexdigest()==row['sha256']
            assert row['sha256']==metadata[g]['annotation_sha256'],g
            label=json.loads(raw);assert (label['imageHeight'],label['imageWidth'])==(1080,1920)
            ids,encoded=score.polygon_reference(label['shapes'],1080,1920,transform=True)
            yield g,ids,encoded
original_reference=score.reference_rows

def main():
    score.verify_all()
    write_new(HERE/'SCORING_REFERENCE_FIX.json',dict(status='ORIGINAL_BASELINE_REFERENCE_SOURCE_RESUMPTION',
        all_predictions_seal=artifact(RUN/'ALL_PREDICTIONS_SEALED.json'),scorer=artifact(HERE/'evaluate.py'),wrapper=artifact(__file__),
        original_GT_archive=artifact(ARCHIVE),authoritative_protocol=artifact(WORK/'tools/sam3_i1_validation_20260915/prepare_truth.py'),
        aligned_package_writer=artifact(WORK/'tools/depth_restoration/build_aligned_dataset.py'),
        field_reads=['manifest.json','gt[global_frame-1].key JSON only'],RGB_entries_read=False,
        correction='Compare original annotation SHA to original archive bytes, preserve original full-raster then nearest resize scoring.',
        prior_scored_outputs_preserved=True,prediction_state_parameter_changes=0))
    score.reference_rows=validation_reference
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
        resumed_reference_adapter=artifact(__file__),reference_source_correction=artifact(HERE/'SCORING_REFERENCE_FIX.json'),
        source_and_runtime_verified=True,development_reference=artifact(score.GT_DEV),validation_original_archive=artifact(ARCHIVE),
        reference_opened_after_all_seals=True,trackeval_package=artifact(Path(score.trackeval.__file__)),masked_or_ignored_ids=0))
    print(json.dumps(dict(feeding=final['feeding_pooled'],segments={n:r['delta'] for n,r in results.items()})),flush=True)
if __name__=='__main__':main()
