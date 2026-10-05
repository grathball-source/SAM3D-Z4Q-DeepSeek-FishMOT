"""Bind actual 4524-frame precheck states, actions and first publications."""
from common import *
p=HERE/'slice_state_final/fishsa_development_8400/public';summary=read(p/'RUN_SUMMARY.json')
assert summary['frames']==4524 and not summary['actual_increment_started']
tx=iter(rows(p/'TRANSACTIONS.jsonl.gz'));cases=[];checked=0
for published in rows(p/'predictions.jsonl.gz'):
    a,b=next(tx),next(tx);assert a['arm']=='Z4Q_FROZEN' and b['arm']=='DEPTH_INCREMENT'
    assert a['frame']==b['frame']==published['frame']
    assert a['branch_state_sha256']==b['branch_state_sha256']==b['original_own_branch_preview_state_sha256']
    assert published['variants']['Z4Q_FROZEN']==published['variants']['DEPTH_INCREMENT']
    assert b['state_selection']=='ORIGINAL_OWN_BRANCH_PREVIEW';checked+=1
    if b['frame'] in (3902,4524):
        if b['frame']==3902:
            assert b['actual_published_mapping']['7']==0
            assert any(x['action'].get('phase')=='birth' and x['action']['native_id']==7 and x['actual_published'] for x in b['actual_actions'])
        else:
            assert b['actual_published_mapping']['1']==1 and b['actual_published_mapping']['7']==0
            assert not b['joint_decision']['detail']['depth_used'] and not b['joint_decision']['staged']
        cases.append(dict(frame=b['frame'],global_frame=b['global_frame'],transaction=b,
            published_row_sha256=row_sha(published)))
assert next(tx,None) is None
write_new(HERE/'REAL_STATE_ACCEPTANCE.json',dict(status='PASS_ACTUAL_NULL_STATE_AND_PUBLICATION_CHECKS',
    full_branch_state_pairs_checked=checked,checks_include_engine_previous_epochs_provenance_version=True,
    real_cases=cases,prefix_summary=artifact(p/'RUN_SUMMARY.json'),prefix_transactions=artifact(p/'TRANSACTIONS.jsonl.gz'),
    prefix_publications=artifact(p/'predictions.jsonl.gz'),no_GT_or_RGB=True,new_model_http=0,cost_usd=0))
print('PASS 4524 actual complete states; F3902 birth retained, F4524 no extra swap',flush=True)
