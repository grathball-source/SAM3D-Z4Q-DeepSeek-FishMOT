"""Count the exact shared populations discarded by the frozen whole-support null."""
from common import *
from collections import Counter
assert read(RUN/'ALL_PREDICTIONS_SEALED.json')['frames']==20098
counts=Counter();records=[]
for name in SEGMENTS:
    facts={(r['measurement']['fact_id'],digest(r['measurement'])):r['measurement'] for r in rows(RUN/name/'public/MEASUREMENTS.jsonl.gz')}
    for row in rows(RUN/name/'public/ORDER_CHECKS.jsonl.gz'):
        for d in row['checks']['JOINT_DEPTH']:
            p=d['detail']['current_pair']
            if p is None:continue
            counts['complete_pre_q']+=1
            if not p['combinations']:counts['no_qualified_current_support_pair']+=1
            for c in p['combinations']:
                if not c['shared_native_sources']:continue
                values={}
                for role,key in [('A','A_support'),('B','B_support')]:
                    e=p[role];f=facts[e['fact_id'],e['measurement_sha256']]
                    s=next(s for s in f['layers'] if s['support_id']==c[key])
                    values[role]=dict(fact_id=e['fact_id'],measurement_sha256=e['measurement_sha256'],
                        independent_n=s['independent_n'],shared_fraction=c['shared_native_sources']/s['independent_n'],
                        z_mm=s['z_mm'],sigma_mm=s['sigma_mm'],support_weight=s['independent_n']/f['original_roi_area'])
                counts['entire_current_qualified_combo_null_on_any_shared_source']+=1
                records.append(dict(segment=name,event=d['event'],q=d['frame'],global_frame=d['global_frame'],
                    exact_shared_unique_sources=c['shared_native_sources'],discarded_candidate_pair_mass=c['weight'],
                    endpoints=values,actual_current_probability=p['probability_A_nearer'],
                    executed_policy='ANY_SHARED_SOURCE_NULLS_ENTIRE_SUPPORT_COMBINATION',
                    proposed_unique_only_remeasurement_not_executed=True,no_GT_used=True))
write_new(HERE/'SUPPORT_OVERLAP_AUDIT.json',dict(status='POSTSEAL_EXACT_SHARED_POPULATION_AUDIT',counts=counts,records=records,
    original_seals_unchanged=True,no_new_method_or_prediction_executed=True,new_model_http=0,cost_usd=0))
print(json.dumps(dict(counts=counts,records=records)),flush=True)
