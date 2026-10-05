"""Actual-reference correctness and preexisting public origin are distinct."""
from common import *
from collections import Counter
import score
score.verify_all();all_counts={a:Counter() for a in ARMS[2:]}
for name in SEGMENTS:
    p=RUN/name/'public';matches={r['frame']:{int(n):m for n,m in r['matches'].items()} for r in rows(p/'REFERENCE_MATCHES.jsonl.gz')}
    origins={a:{} for a in ARMS[2:]}
    for r in rows(p/'predictions.jsonl.gz'):
        for arm in ARMS[2:]:
            for o in r['variants'][arm]:origins[arm].setdefault(o['id'],dict(frame=r['frame'],native_id=int(o['mask'][2:])))
    records=[];counts={a:Counter() for a in ARMS[2:]}
    for a in read(p/'ACTION_AUDIT.json')['actions']:
        arm=a['arm'];ref=a['reference'];origin=origins[arm][a['target']]
        def match(f,n):return matches.get(f,{}).get(n,{})
        query=match(a['frame'],a['source']);past=match(ref['frame'],ref['native_id']);initial=match(origin['frame'],origin['native_id'])
        relations=dict(query_vs_actual_reference=score.same(query,past),reference_vs_first_public_origin=score.same(past,initial),query_vs_first_public_origin=score.same(query,initial))
        verdict='WRONG' if relations['query_vs_actual_reference']=='DIFFERENT' else 'CORRECT' if relations['query_vs_actual_reference']=='SAME' else 'UNSCORABLE'
        assert verdict==a['physical']
        counts[arm]['all/'+verdict]+=1
        if a['mapping_changed']:counts[arm]['changed/'+verdict]+=1
        if a['depth_changed_same_state_selection']:counts[arm]['depth_changed/'+verdict]+=1
        counts[arm]['prior_public_origin/'+relations['reference_vs_first_public_origin']]+=1
        if a['mapping_changed']:records.append(dict(**a,first_public_origin=origin,relations=relations,
            initial_public_origin_mismatch=relations['reference_vs_first_public_origin']=='DIFFERENT',
            caveat='First public observation may itself be merged/unscorable; SAME is conditional on unique postseal IoU match, not human-certified identity.'))
    for arm in ARMS[2:]:all_counts[arm].update(counts[arm])
    write_new(p/'ORIGIN_ACTION_AUDIT.json',dict(records=records,counts=counts,origin_policy='FIRST_ACTUAL_PERSISTENT_PID_PUBLICATION',new_GT_raster_read=False))
write_new(HERE/'ORIGIN_ACTION_SUMMARY.json',dict(status='PASS',counts=all_counts,no_relabeling_or_prediction_replay=True))
print(json.dumps(all_counts),flush=True)
