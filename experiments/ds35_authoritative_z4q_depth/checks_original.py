"""Old scientific states, not just old predictions, bind the real engineering controls."""
from common import *
fields=('mapping','actual_actions','engine_state_sha256','full_state_sha256','actual_aliases',
        'actual_epochs','actual_provenance','bank_anchors','controller_trace')
results=[]
for folder,name,frames in [('slice_dev_v2','fishsa_development_8400',3940),('slice_val','fishsa_validation_2888',2725)]:
    values=rows(PRIOR/'run'/name/'public/TRANSACTIONS.jsonl.gz')
    current=rows(HERE/folder/name/'public/TRANSACTIONS.jsonl.gz')
    for frame in range(1,frames+1):
        before=next(values);assert before['arm']=='Z4Q_FROZEN' and before['frame']==frame
        for a in ('EVENT_RGB','EVENT_RGBD'):ignored=next(values);assert ignored['arm']==a and ignored['frame']==frame
        after=next(current);assert after['arm']=='Z4Q_FROZEN' and after['frame']==frame
        for a in EVENT_ARMS:
            independent=next(current);assert independent['arm']==a and independent['frame']==frame
            for k in fields:
                if k!='full_state_sha256':assert independent[k]==after[k],(name,frame,a,k)
        for k in fields:assert before[k]==after[k],(name,frame,k)
    assert next(current,None) is None
    results.append(dict(segment=name,frames=frames,original_scientific_state_fields=list(fields),status='ALL_FRAMES_EXACT'))
write_new(HERE/'CHECKS_ORIGINAL.json',dict(status='PASS',frames=6665,results=results,GT_opened=False,new_model_http=0,cost_usd=0))
print('6665 actual original-state/trace/alias/provenance/anchor frames exact',flush=True)
