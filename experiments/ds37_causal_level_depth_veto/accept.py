"""Bind real F159 control/state/publisher checks without reading a reference."""
from common import *
assert read(HERE/'CHECKS_FINAL_V3_COMPLETE.json')['status']=='PASS'
name='feeding_000000_000199'
paths=[HERE/s/name/'public' for s in ('slice_f159_fast','slice_f159_final','slice_disabled')]
oldp,newp,disabled=paths
for file in ('predictions.jsonl.gz','TRANSACTIONS.jsonl.gz','DEPTH_EXTRACTS.jsonl.gz'):
    for a,b in zip(rows(oldp/file),rows(newp/file),strict=True):assert a==b,(file,a.get('frame'))
for pr,disabled_pr in zip(rows(newp/'predictions.jsonl.gz'),rows(disabled/'predictions.jsonl.gz'),strict=True):
    assert pr==disabled_pr
assert all(read(p/'ACCESS.json')['status']=='NO_GT_RGB_RESTORED_NETWORK' for p in paths)
for p in paths:
    summary=read(p/'RUN_SUMMARY.json');assert summary['frames']==160 and summary['original_Z4Q_and_DS32_WLS_full_state_exact']
    assert all(v['changed_frames']==0 for v in summary['counts'].values())
for tx in rows(newp/'TRANSACTIONS.jsonl.gz'):
    if tx['frame']==160 and tx['arm']=='Z4Q_LEVEL_VETO':write_new(HERE/'F159_SOURCE_BODY_STATE_V3.json',tx)
write_new(HERE/'REAL_ACCEPTANCE_V3.json',dict(status='PASS_REAL_F159_SOURCE_OWN_STATE_PUBLICATION_AND_EXACT_HASH_ADAPTER',
    frames=160,artifacts=[artifact(p/f) for p in paths for f in ('RUN_SUMMARY.json','ACCESS.json','predictions.jsonl.gz','TRANSACTIONS.jsonl.gz')],
    all_160_fast_and_original_scientific_trace_rows_exact=True,disabled_all_masks_and_ids_exact=True,
    before_seconds=read(oldp/'RUN_SUMMARY.json')['elapsed_seconds'],after_seconds=read(newp/'RUN_SUMMARY.json')['elapsed_seconds'],
    same_full_content_hash_no_copy_optimization=True,no_parameter_change_from_slice=True,no_GT_read=True,model_http=0,cost_usd=0))
print('REAL_F159_ACCEPTANCE_PASS',flush=True)
