"""Source-to-first-publication acceptance on earliest automatically found q."""
from common import *

def main():
    import evaluate as scorer
    slice=read(HERE/'slice/REAL_SLICE.json');name=slice['segment'];q=slice['q']
    preds=list(rows(HERE/'slice'/name/'public/predictions.jsonl.gz'))
    assert preds[-1]['frame']==q and slice['score']['choice'] in ('H0','H1','H2')
    pub=next(x for x in rows(HERE/'slice'/name/'public/PUBLISH_LEDGER.jsonl') if x['frame']==q)
    old_public=HERE.parent/'ds9_joint_h0_depth/run'/name/'public'
    old_seal=read(old_public/'PREDICTIONS_SEALED.json')
    old_all=read(HERE.parent/'ds9_joint_h0_depth/run/ALL_PREDICTIONS_SEALED.json')
    assert sha(old_public/'PREDICTIONS_SEALED.json')==old_all['seals'][name]
    for item,h in old_seal['artifacts_sha256'].items():assert sha(old_public/item)==h
    old_predictions={x['frame']:x for x in rows(old_public/'predictions.jsonl.gz')}
    assignments={x['frame']:x for x in rows(input_dir(name)/'assignments.jsonl.gz')}
    for frame in preds:
        scorer.check_objects(assignments[frame['frame']],frame)
        previous=old_predictions[frame['frame']]
        assert all(frame[k]==previous[k] for k in ('frame','global_frame','time'))
        assert frame['variants']['SAM3_NATIVE']==previous['variants']['SAM3_NATIVE']
        assert frame['variants']['F9_RESTORED']==previous['variants']['J2_RESTORED_DEPTH']
        native=frame['variants']['SAM3_NATIVE']
        for arm in ARMS:
            values=frame['variants'][arm]
            assert [x['mask'] for x in values]==[x['mask'] for x in native]
            assert len(values)==len(set(x['id'] for x in values))
    for arm,pair in pub['event_publish'].items():
        actual={int(x['mask'][2:]):x['id'] for x in preds[-1]['variants'][arm]}
        assert pair['post_sample_count']==1 and all(actual[int(n)]==k for n,k in pair['first_public_pair'].items())
    public=HERE/'slice'/name/'public'
    transactions={(x['frame'],x['arm']):x for x in rows(public/'TRANSACTIONS.jsonl.gz')}
    states={(x['frame'],x['arm']):x for x in rows(public/'DEPTH_STATES.jsonl.gz')}
    measurements={x['frame']:x for x in rows(public/'DEPTH_OBSERVATIONS.jsonl.gz')}
    old_measurements={x['frame']:x for x in rows(old_public/'DEPTH_OBSERVATIONS.jsonl.gz')}
    source_precision=[]
    for f,measurement in measurements.items():
        source_precision.extend(dict(frame=f,**item) for item in scorer.check_source_extraction(measurement,old_measurements[f]))
    sources={};generations={};last={};current_generation={}
    for row in rows(input_dir(name)/'observations.jsonl.gz'):
        f=row['frame']
        if f>q:break
        objects={o['id']:o for o in row['observations']}
        sources[f]=dict(time=row['time'],observations=objects)
        for n in objects:
            g=current_generation.get(n,0)+(last.get(n)!=f-1)
            generations[(f,n)]=g;current_generation[n]=g;last[n]=f
    q_checks=0
    for arm,events in read(public/'EVENTS.json').items():
        for e in events:
            scorer.check_geometry_history(e,arm,name,sources,transactions,generations)
            for frozen in (e['depth_frozen'] or {}).values():
                for sample in frozen['samples']:
                    scorer.check_frozen_sample(sample,frozen,arm,name,measurements,states)
            if e['q'] is not None:
                scorer.check_q_binding(e,arm,{x['frame']:x for x in preds},
                    {x['frame']:x for x in rows(public/'PUBLISH_LEDGER.jsonl')},transactions,states)
                scorer.check_association(e,arm,name,measurements,transactions);q_checks+=1
    verify_item(read(HERE/'slice/ACCESS_SEALED.json')['artifact'])
    write_new(HERE/'REAL_SLICE_ACCEPTANCE.json',dict(status='PASS',segment=name,q=q,
        original_q=slice['original_q'],first_published_pair=slice['first_public_pair'],
        choice=slice['score']['choice'],source_to_association_to_first_publish=True,
        F9_exact_DS9_restored_all_slice_frames=True,native_exact_DS9=True,all_masks_and_unique_ids=True,
        source_comparison_precision_exceptions=source_precision,
        q_semantic_checks=q_checks,pre_geometry_depth_sources_and_versions_bound=True,
        real_slice=artifact(HERE/'slice/REAL_SLICE.json'),new_model_http=0,cost_usd=0))
    print('Real automatic first-q slice PASS',name,q)
if __name__=='__main__':main()
