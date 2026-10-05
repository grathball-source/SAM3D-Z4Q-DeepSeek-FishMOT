"""Explain every depth-unavailable q from actual frozen body facts, without truth."""
from common import *
from collections import Counter
import math
assert read(RUN/'ALL_PREDICTIONS_SEALED.json')['frames']==20098
total=Counter();segments={};details=[]
for name in SEGMENTS:
    verify_seal(name);counts=Counter();pairs=[];facts={}
    for record in rows(RUN/name/'public/MEASUREMENTS.jsonl.gz'):
        f=record['measurement'];facts[f['fact_id'],digest(f)]=f
    for row in rows(RUN/name/'public/ORDER_CHECKS.jsonl.gz'):
        for d in row['checks']['JOINT_DEPTH']:
            r=d['detail'];reason=None;counts['q']+=1
            before=r['pre'];intervals={role:dict(anchor=p['anchor'],version=p['version'],status=p['status'],
                sample_frames=[s['frame'] for s in p['samples']],sample_count=len(p['samples'])) for role,p in before.items()}
            if not all(p['samples'] for p in before.values()):reason='MISSING_EXACT_PRE_REFERENCE'
            elif not r['pre_pairs']:reason='NO_SYNCHRONOUS_PRE_OR_EXPIRED_RAW'
            else:
                factors=dict(pre_order=r['pre_probability']-.5,current_order=r['current_probability']-.5,
                    age_attenuation=r['age_attenuation'])
                weak=[k for k,v in factors.items() if abs(v)<1e-12]
                reason='NONZERO_DEPTH' if not weak else 'NULL_FACTOR_'+'_AND_'.join(weak)
                endpoints=[]
                for when,ps in [('PRE',r['pre_pairs']),('Q',[r['current_pair']])]:
                    for pair in ps:
                        for role in ('A','B'):
                            e=pair[role];f=facts[e['fact_id'],e['measurement_sha256']]
                            endpoints.append(dict(when=when,role=role,frame=e['frame'],fact_id=e['fact_id'],
                                fact_sha256=e['measurement_sha256'],measured_reason=f['reason'],roi_area=f['original_roi_area'],
                                independent_points=f['summary']['n'],valid_fraction=f['summary']['valid_fraction'],
                                qualified_layers=len(f['qualified_support_ids']),null_weight=e['null_weight'],
                                measurement_not_physical_fish_certificate=True))
                            counts[when+'_MEASUREMENT_'+f['reason']]+=1
                pairs.append(dict(event=d['event'],frame=d['frame'],factors=factors,endpoints=endpoints,
                    full_joint_candidates=r['candidates'],staged=d['staged'],raw_choice=d['choice']))
            counts[reason]+=1
            details.append(dict(segment=name,event=d['event'],q=d['frame'],global_frame=d['global_frame'],
                suspect_frame=d['suspect_frame'],input_failure_or_signal=reason,independent_pre_intervals=intervals,
                pre_frames=r.get('pre_frames',[]),pre_probability=r['pre_probability'],current_probability=r['current_probability'],
                age_attenuation=r.get('age_attenuation'),no_GT_used=True))
    total.update(counts);segments[name]=dict(counts=counts,actual_pre_q_comparisons=pairs)
write_new(HERE/'INPUT_DIAGNOSIS.json',dict(status='COMPLETE_ACTUAL_FROZEN_Q_INPUT_DIAGNOSIS_NO_GT',counts=total,
    segments=segments,every_q=details,no_new_selection_or_threshold_changes=True,new_model_http=0,cost_usd=0))
print(json.dumps(total),flush=True)
