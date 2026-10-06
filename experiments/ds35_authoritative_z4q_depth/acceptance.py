"""Actual-engine slices preserve original good BirthRefine and veto weak event writes."""
from common import *
from score import verify_publications
logical=[]
for folder,name,last in [('slice_dev_v2','fishsa_development_8400',3940),('slice_val','fishsa_validation_2888',2725)]:
    public=HERE/folder/name/'public'
    assert read(public/'RUN_SUMMARY.json')['published']==last
    for pin in ('ACCESS.json','RUN_SUMMARY.json','EVENTS.json'):assert (public/pin).is_file()
    assert read(public/'ACCESS.json')['status']=='RAW_DEPTH_CACHE_NO_GT_RESTORED_RGB_NETWORK'
    result,_=verify_publications(name,public,last);logical.append(dict(segment=name,source_to_publication_contract=result))
cases=[]
for folder,name,q,source,target in [('slice_dev_v2','fishsa_development_8400',3902,7,0),
                                  ('slice_val','fishsa_validation_2888',2188,8,3)]:
    public=HERE/folder/name/'public';values=[t for t in rows(public/'TRANSACTIONS.jsonl.gz') if t['frame']==q]
    assert len(values)==3
    for t in values:
        assert t['mapping'][str(source)]==target
        actions=[a for a in t['actual_actions'] if a['native_id']==source and a['canonical_id']==target]
        assert len(actions)==1 and actions[0]['phase']=='birth'
    assert len({t['canonical_state_sha256'] for t in values})==1
    cases.append(dict(segment=name,q=q,source=source,target=target,status='ORIGINAL_REAL_BIRTH_REFINE_RETAINED_ALL_STATE_ARMS',
        transactions=values))
public=HERE/'slice_val/fishsa_validation_2888/public';q=2689
values=[t for t in rows(public/'TRANSACTIONS.jsonl.gz') if t['frame']==q]
assert len({t['canonical_state_sha256'] for t in values})==1
assert all(t['state_selection']=='ORIGINAL_OWN_Z4Q' for t in values)
cases.append(dict(segment='fishsa_validation_2888',q=q,status='NO_DEPTH_NO_GEOMETRY_ONLY_SWAP',transactions=values))
artifacts=[artifact(p) for folder in ('slice_dev_v2','slice_val') for p in (HERE/folder).rglob('*') if p.is_file()]
for p in ('CHECKS_FINAL.json','CHECKS_SCORE.json','CHECKS_EMPTY.json'):assert read(HERE/p)['status']=='PASS'
write_new(HERE/'REAL_ACCEPTANCE.json',dict(status='PASS',cases=cases,artifacts=artifacts,logical_contracts=logical,
    engineering_only_not_metric_gain=True,known_prior_postseal_cases_not_GT_trigger_selection=True,GT_opened=False,new_model_http=0,cost_usd=0))
print('Actual BirthRefine q3902/q2188 preserved; weak geometry q2689 cannot override.',flush=True)
