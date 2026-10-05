"""Accept actual source/engine regressions without reading GT or metrics."""
from common import *
from collections import Counter
artifacts=[];details={}
for folder,name,expected in (
    ('slice_disabled_final','feeding_000000_000199',200),
    ('slice_enabled_final','feeding_000000_000199',200),
    ('slice_f364','feeding_000351_000555',205)):
    p=HERE/folder/name/'public';s=read(p/'RUN_SUMMARY.json');assert s['frames']==expected and s['original_Z4Q_exact']
    assert read(p/'ACCESS.json')['status']=='NO_GT_RGB_RESTORED_NETWORK'
    artifacts.extend(artifact(p/f) for f in ('RUN_SUMMARY.json','ACCESS.json','predictions.jsonl.gz','TRANSACTIONS.jsonl.gz'))
    details[folder]=s
f364=next(r for r in rows(HERE/'slice_f364/feeding_000351_000555/public/predictions.jsonl.gz') if r['frame']==14)
assert f364['global_frame']==364
details['F364']=dict(original={o['mask']:o['id'] for o in f364['variants']['Z4Q_FROZEN']},
    new={o['mask']:o['id'] for o in f364['variants']['Z4Q_DEPTH_VETO']},
    previous_DS31_avoided_error_not_new_improvement=True,GT_not_read=True)
details['F3902']=dict(inspection='CHECK_IN_COMPLETE_FORMAL_REPLAY_AFTER_SEAL',
    note='Existing successful restore checked in full replay; not an extra long prelaunch qualification gate or forced outcome.')
write_new(HERE/'REAL_ACCEPTANCE.json',dict(status='PASS_SOURCE_STATE_PUBLICATION_REGRESSIONS',artifacts=artifacts,details=details,
    no_GT_or_method_score_gate=True,model_http=0,cost_usd=0))
print('Actual regressions passed; method performance remains unscored.',flush=True)
