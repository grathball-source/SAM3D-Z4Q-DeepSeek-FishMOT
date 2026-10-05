"""Every frozen q's evidence/decision bottleneck; no labels needed."""
from common import *
from collections import Counter
import score
score.verify_all();counts=Counter();details=[];measurements=Counter()
for name in SEGMENTS:
    p=RUN/name/'public';summary=read(p/'RUN_SUMMARY.json')
    for item in rows(p/'MEASUREMENTS.jsonl.gz'):
        f=item['measurement'];kind='REMEASURED' if f.get('remeasured_from') else 'ORIGINAL'
        measurements[kind+'/facts']+=1
        measurements[kind+'/qualified_supports_'+str(len(f['qualified_support_ids']))]+=1
        measurements[kind+'/'+f['reason']]+=1
    for row in rows(p/'ORDER_CHECKS.jsonl.gz'):
        for d in row['checks']['DEPTH_INCREMENT']:
            r=d['detail'];counts['q']+=1;counts['raw_'+d['choice']]+=1
            counts['reason/'+r['reason']]+=1;counts['stage/'+str(d['stage_error'])]+=1
            if r['depth_used']:counts['non_null_depth']+=1
            if d['staged']:counts['actual_depth_commits']+=1
            source_checks=[]
            for pair in r['pre_pairs']+([r['current_pair']] if r['current_pair'] else []):
                c=pair['joint_source_check'];source_checks.append(c)
                if c['remeasured']:counts['paired_comparisons_remeasured']+=1
            if not all(v['samples'] for v in r['pre'].values()):gap='MISSING_EXACT_REFERENCE'
            elif r['reason']=='UNKNOWN_GEOMETRY':gap='EXPIRED_OR_UNKNOWN_GEOMETRY'
            elif not r['pre_pairs']:gap='NO_SYNCHRONOUS_PRE'
            elif not r['depth_used']:gap='PRE_CURRENT_OR_AGE_COMMON_NULL'
            elif d['choice']=='DEFER':gap='INSUFFICIENT_OR_OPPOSED_DEPTH_OR_TOTAL_MARGIN'
            elif not d['staged']:gap='ORIGINAL_STATE_TRANSACTION_BOUNDARY'
            else:gap='ACTUAL_DEPTH_STATE_COMMIT'
            counts['bottleneck/'+gap]+=1
            details.append(dict(segment=name,event=d['event'],q=d['frame'],global_frame=d['global_frame'],
                decision_reason=r['reason'],input_bottleneck=gap,pre_probability=r['pre_probability'],
                current_probability=r['current_probability'],age_attenuation=r.get('age_attenuation'),
                depth_only_margin=r.get('depth_only_margin'),margin=r.get('margin'),
                raw_choice=d['choice'],stage_error=d['stage_error'],staged=d['staged'],
                actual_published_mapping=d['actual_published_mapping'],changes=d['changes'],
                exact_pre_intervals={k:dict(anchor=v['anchor'],version=v['version'],frames=[s['frame'] for s in v['samples']]) for k,v in r['pre'].items()},
                source_checks=source_checks))
    if name=='fishsa_development_8400':
        old=HERE/'slice_state_final'/name/'public'
        for a,b in zip(rows(old/'predictions.jsonl.gz'),rows(p/'predictions.jsonl.gz')):
            assert a==b
        counts['real_prefix_exact_publications']+=4524
write_new(HERE/'INPUT_DIAGNOSIS.json',dict(status='ALL_FROZEN_Q_SOURCE_AND_DECISION_BOTTLENECKS_REPORTED',
    counts=counts,measurements=measurements,every_q=details,no_GT_used=True,not_a_metric_success_test=True,new_model_http=0,cost_usd=0))
print(json.dumps(counts),flush=True)
