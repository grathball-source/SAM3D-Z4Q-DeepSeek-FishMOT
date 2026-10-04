"""Sealed-input mechanisms and postscore actual-reference action coverage."""
from common import *
from collections import Counter
import statistics
import score

def action_key(a):
    return (a['frame'],a['origin_rule'],a['source'],a['target'],digest(a['anchor']))

def main():
    score.verify_all();metrics=read(RUN/'METRICS.json');segments={}
    totals={a:Counter() for a in ARMS[2:]};comparisons={a:Counter() for a in ARMS[2:]}
    formal=[];allcoverage=[];cost_updates=[]
    for name in SEGMENTS:
        public=RUN/name/'public';facts={a:Counter() for a in ARMS[2:]};by_fact={}
        for r in rows(public/'MEASUREMENTS.jsonl.gz'):
            arm,f=r['arm'],r['measurement'];facts[arm]['facts']+=1
            facts[arm]['single_qualified_support_facts']+=len(f['qualified_support_ids'])==1
            facts[arm]['multiple_qualified_support_facts']+=len(f['qualified_support_ids'])>1
            facts[arm]['no_qualified_support_facts']+=not f['qualified_support_ids']
            k=(f['frame'],digest(f['roi_binding']))
            if k in by_fact:assert by_fact[k]==f,'Identical raw ROI/policy measured differently across branches'
            by_fact[k]=f
        detail={a:dict(checks=Counter(),comparisons=Counter(),complete_comparisons=[],first_nonzero=None) for a in ARMS[2:]}
        audit=read(public/'ACTION_AUDIT.json');original={action_key(a):a for a in audit['actions'] if a['arm']=='Z4Q_FROZEN'}
        changed_queries={(x['arm'],x['frame'],x['source'],x['target']):x for x in audit['actual_soft_cost_updates']}
        for tx in rows(public/'TRANSACTIONS.jsonl.gz'):
            for c in tx['controller_trace'].get('depth_soft_checks',[]):
                if not c['applied_delta_cost']:continue
                key=(tx['arm'],tx['frame'],c['native_id'],c['public_id']);verdict=changed_queries[key]
                events=[e for e in tx['controller_trace']['events'] if e.get('kind')=='reconnect'
                    and (e['native_id'],e['canonical_id'])==(c['native_id'],c['public_id'])]
                cost_updates.append(dict(segment=name,arm=tx['arm'],frame=tx['frame'],global_frame=tx['global_frame'],
                    source=c['native_id'],target=c['public_id'],actual_reference_physical=verdict['physical_candidate'],
                    original_cost=c['cost_original'],effective_cost=c['cost_effective'],delta=c['applied_delta_cost'],
                    own_dummy_cost=c['own_dummy_cost'],original_dummy_gap=c['own_dummy_cost']-c['cost_original'],
                    actual_assignment_events=events,actual_published_mapping=tx['actual_published_mapping'],
                    source_can_have_other_global_assignment_competitors=True,check=c))
        action_coverage=[]
        original_by_frame={}
        for a in original.values():original_by_frame.setdefault(a['frame'],[]).append(a)
        for r in rows(public/'ORDER_CHECKS.jsonl.gz'):
            for arm in ARMS[2:]:
                d=detail[arm];checks={(c['origin_rule'],c['native_id'],c['public_id']):c for c in r['checks'][arm]}
                assert len(checks)==len(r['checks'][arm])
                for c in checks.values():
                    d['checks']['checks']+=1;d['checks'][c['origin_rule']]+=1
                    d['checks']['reason_'+c['reason']]+=1
                    if c['applied_delta_cost']:
                        d['checks']['nonzero_cost_edges']+=1
                        if d['first_nonzero'] is None:d['first_nonzero']=dict(frame=r['frame'],global_frame=r['global_frame'],check=c)
                    for comp in c.get('comparisons',[]):
                        d['comparisons']['all_partner_references']+=1
                        d['comparisons']['gate_'+comp.get('reason',comp['status'])]+=1
                        if 'pre_pairs' not in comp:continue
                        pp,pq=comp['pre_probability_median'],comp['current_probability']
                        weak=abs(pp-.5)<read(HERE/'CONFIG.json')['minimum_pre_probability_distance']
                        current_null=comp['current_pair']['status']=='COMMON_NULL'
                        counts=d['comparisons'];counts['complete_comparisons']+=1
                        counts['weak_pre']+=weak;counts['admitted_pre']+=not weak
                        counts['current_common_null']+=current_null
                        counts['admitted_pre_current_null']+=(not weak and current_null)
                        counts['admitted_pre_nonnull_current']+=(not weak and not current_null)
                        counts['nonzero_comparisons']+=bool(comp['delta_cost'])
                        row=dict(segment=name,arm=arm,frame=r['frame'],global_frame=r['global_frame'],
                            source=c['native_id'],target=c['public_id'],phase=c['origin_rule'],partner=comp['partner_native'],
                            pre_frames=comp['pre_frames'],pre_probability=pp,current_probability=pq,
                            pre_current_sign_agreement=(pp-.5)*(pq-.5),delta_cost=comp['delta_cost'],
                            requested_edge_delta=c['requested_delta_cost'],applied_edge_delta=c['applied_delta_cost'],
                            original_edge_cost=c['cost_original'],effective_edge_cost=c['cost_effective'],
                            pre_qualified_order_references=sum(p['status']=='CONDITIONAL_ORDER_PROXY' for p in comp['pre_pairs']),
                            current_pair_status=comp['current_pair']['status'],
                            pre_versions=comp['pre_versions'],anchor=c['anchor'],
                            current_pair=comp['current_pair'],physical_identity='UNKNOWN_UNTIL_POSTSCORE_REFERENCE',
                            repeated_reference_not_independent_event=True)
                        d['complete_comparisons'].append(row);formal.append(row)
                for a in original_by_frame.get(r['frame'],[]):
                    key=(a['origin_rule'],a['source'],a['target']);c=checks.get(key)
                    complete=sum('pre_pairs' in x for x in c.get('comparisons',[])) if c else 0
                    record=dict(segment=name,arm=arm,original_action=a,
                        edge_checked=c is not None,full_pre_q_comparisons=complete,
                        nonzero_cost=bool(c and c['applied_delta_cost']),
                        actual_check=c,reference_selection='FIXED_ORIGINAL_ACTION_AFTER_NEW_PREDICTIONS_SEALED',
                        missing_check_may_follow_prior_branch_state_divergence=True)
                    action_coverage.append(record);allcoverage.append(record)
        action_result={}
        for arm in ARMS[2:]:
            own={action_key(a):a for a in audit['actions'] if a['arm']==arm}
            action_result[arm]=dict(original_exact_actions_retained=sum(k in own for k in original),
                original_actions_removed=[original[k] for k in original.keys()-own.keys()],
                new_or_reference_changed_actions=[own[k] for k in own.keys()-original.keys()],
                actual_reference_counts=dict(Counter(a['actual_reference_physical'] for a in own.values())),
                origin_and_actual_reference_counts=dict(Counter(a['physical'] for a in own.values())),
                total_durable_actions=len(own))
            totals[arm].update(detail[arm]['checks']);totals[arm].update(facts[arm]);comparisons[arm].update(detail[arm]['comparisons'])
        segments[name]=dict(measurement_counts=facts,evidence=detail,actions=action_result,original_action_coverage=action_coverage)
    coverage={}
    for arm in ARMS[2:]:
        records=[r for r in allcoverage if r['arm']==arm]
        coverage[arm]={v:dict(original_actions=sum(r['original_action']['actual_reference_physical']==v for r in records),
            checked=sum(r['edge_checked'] and r['original_action']['actual_reference_physical']==v for r in records),
            full_pre_q=sum(r['full_pre_q_comparisons']>0 and r['original_action']['actual_reference_physical']==v for r in records),
            nonzero=sum(r['nonzero_cost'] and r['original_action']['actual_reference_physical']==v for r in records))
            for v in ('CORRECT','WRONG','UNSCORABLE')}
    result=dict(status='POSTSEAL_DEPTH_ENTRY_AND_REAL_ACTION_MECHANISM_DIAGNOSIS',
        source_frames=20098,arms=ARMS,counts=totals,comparison_counts=comparisons,
        original_action_coverage=coverage,segments=segments,actual_nonzero_cost_updates=cost_updates,
        max_absolute_cost_update=max((abs(c['delta']) for c in cost_updates),default=0.),
        all_eight_sources_included=True,
        same_policy_same_actual_raw_ROI_fact_equality=True,
        no_GT_case_q_anchor_threshold_selection=True,model_http=0,cost_usd=0)
    write_new(HERE/'MECHANISM_ANALYSIS.json',result)
    with gzip.open(HERE/'FORMAL_COMPARISONS.jsonl.gz','xt',encoding='utf-8') as h:
        for r in formal:h.write(json.dumps(r,separators=(',',':'),allow_nan=False)+'\n')
    print(json.dumps(dict(counts=totals,comparison_counts=comparisons,original_action_coverage=coverage)))

if __name__=='__main__':main()
