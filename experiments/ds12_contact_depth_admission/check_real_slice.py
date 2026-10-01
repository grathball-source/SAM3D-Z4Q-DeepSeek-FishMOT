"""GT-free earliest eligible first-birth slice, with the full semantic contracts."""
from common import *


def main():
    import evaluate as scorer
    from input_contract import verify_cached_segment
    root=HERE/'slice';sample=read(root/'REAL_SLICE.json');checks=[];earliest=None;q_checks=0
    for name,(start,stop) in SEGMENTS.items():
        public=root/name/'public'
        if not (public/'predictions.jsonl.gz').exists():continue
        verify_cached_segment(name)
        old_public=HERE.parent/'ds11_depth_birth_reconnect/run'/name/'public'
        old_seal=read(old_public/'PREDICTIONS_SEALED.json')
        for file,h in old_seal['artifacts_sha256'].items():assert sha(old_public/file)==h
        previous={x['frame']:x for x in rows(old_public/'predictions.jsonl.gz')}
        predictions={x['frame']:x for x in rows(public/'predictions.jsonl.gz')};nframes=len(predictions)
        assert set(predictions)==set(range(1,nframes+1))
        assignments={x['frame']:x for x in rows(input_dir(name)/'assignments.jsonl.gz')}
        publish={x['frame']:x for x in rows(public/'PUBLISH_LEDGER.jsonl')}
        transactions={(x['frame'],x['arm']):x for x in rows(public/'TRANSACTIONS.jsonl.gz')}
        states={(x['frame'],x['arm']):x for x in rows(public/'DEPTH_STATES.jsonl.gz')}
        expected={(f,a) for f in predictions for a in ARMS[1:]}
        assert set(transactions)==set(states)==expected and set(publish)==set(predictions)
        measurements={x['frame']:x for x in rows(public/'DEPTH_OBSERVATIONS.jsonl.gz')}
        old_measurements={x['frame']:x for x in rows(old_public/'DEPTH_OBSERVATIONS.jsonl.gz')}
        assert set(measurements)==set(predictions)
        with scorer.gzip.open(public/'predictions.jsonl.gz','rt',encoding='utf-8') as lines:
            for f,line in enumerate(lines,1):
                pred=predictions[f];old=previous[f]
                assert scorer.hashlib.sha256(line.encode()).hexdigest()==publish[f]['prediction_row_sha256']
                scorer.check_objects(assignments[f],pred)
                assert all(pred[k]==old[k] for k in ('frame','global_frame','time'))
                assert pred['variants']['SAM3_NATIVE']==old['variants']['SAM3_NATIVE']
                assert pred['variants']['F9_RESTORED']==old['variants']['F9_RESTORED']
                scorer.check_source_extraction(measurements[f],old_measurements[f])
                for arm in ARMS[1:]:
                    actual={int(x['mask'][2:]):x['id'] for x in pred['variants'][arm]}
                    assert scorer.intmap(transactions[(f,arm)]['actual_published_mapping'])==actual
        sources={};generations={};last={};generation={}
        for row in rows(input_dir(name)/'observations.jsonl.gz'):
            f=row['frame']
            if f>nframes:break
            objects={o['id']:o for o in row['observations']};sources[f]=dict(time=row['time'],observations=objects)
            for n in objects:
                g=generation.get(n,0)+(last.get(n)!=f-1);generations[(f,n)]=g;generation[n]=g;last[n]=f
        contacts,cchecks=scorer.recompute_contact_rows(public,name,sources,measurements,publish)
        births=scorer.bound_birth_rows(public,publish)
        bchecks=scorer.check_birth_rows(births,name,sources,measurements,predictions,publish,transactions,states,generations,contacts)
        checks.append(dict(segment=name,frames=nframes,**bchecks,**cchecks))
        for b in births:
            if earliest is not None or b['arm']!=ARMS[2] or b['frame']==1 or b['group_blocked']:continue
            for query in b['queries']:
                p=query['query_observation'];cert=query['contact_certificate']
                if p['quality'] and p['neighbors'] and p['area']>=64 and cert and cert['eligible'] and any(c['eligible'] for c in query['candidates']):
                    earliest=(name,b,query);break
        for arm,events in read(public/'EVENTS.json').items():
            for event in events:
                scorer.check_geometry_history(event,arm,name,sources,transactions,generations)
                for frozen in (event['depth_frozen'] or {}).values():
                    for point in frozen['samples']:scorer.check_frozen_sample(point,frozen,arm,name,measurements,states)
                if event['q'] is not None:
                    scorer.check_q_binding(event,arm,predictions,publish,transactions,states)
                    scorer.check_association(event,arm,name,measurements,transactions);q_checks+=1
    if earliest is None:
        assert sample['status']=='NO_AUTOMATIC_ELIGIBLE_BIRTH_SLICE'
        assert len(checks)==len(SEGMENTS) and sum(x['frames'] for x in checks)==1471
        status='NO_AUTOMATIC_ELIGIBLE_BIRTH_SLICE_CONTRACTS_PASS'
    else:
        name,b,query=earliest
        assert sample['segment']==name and sample['q']==b['frame'] and sample['original_q']==b['global_frame']
        assert sample['birth_row']==b and sample['query']==query and sample['source']==query['source']
        assert sample['first_public_id']==query['actual_first_public_id']
        scorer.check_source_extraction(sample['measured'],read_slice_measurement(root,name,b['frame']))
        assert checks[-1]['segment']==name and checks[-1]['frames']==b['frame']
        status='PASS'
    verify_item(read(root/'ACCESS_SEALED.json')['artifact'])
    write_new(HERE/'REAL_SLICE_ACCEPTANCE.json',dict(status=status,segments=checks,
        earliest_selection='FIRST_SOURCE_CONTACT_BIRTH_RAW_CERTIFICATE_ELIGIBLE_WITH_ANY_ELIGIBLE_ABSENT_CANDIDATE; NO_GT_OR_COMMIT_SELECTION',
        source_to_association_to_first_publish=True,F9_exact_DS11_F9_all_slice_frames=True,native_exact_DS11=True,
        q_semantic_checks=q_checks,all_masks_and_unique_ids=True,exact_cached_measurements=True,
        real_slice=artifact(root/'REAL_SLICE.json'),new_model_http=0,cost_usd=0))
    print('Real automatic birth slice',status)


def read_slice_measurement(root,name,frame):
    return next(row for row in rows(root/name/'public/DEPTH_OBSERVATIONS.jsonl.gz') if row['frame']==frame)


if __name__=='__main__':main()
