"""Source and measurement citations, source cutoffs and pair completeness, no GT read."""
from common import *
from collections import Counter
from evidence import representative,pair_order,combine

def review():
    manifest=read(RUN/'ALL_PREDICTIONS_SEALED.json');assert manifest['frames']==20098
    results={};total_checks=total_comparisons=total_measures=0
    for name in SEGMENTS:
        verify_seal(name);public=RUN/name/'public';facts={};summary=read(public/'RUN_SUMMARY.json')
        for f in rows(public/'MEASUREMENTS.jsonl.gz'):
            assert f['fact_id'] not in facts
            facts[f['fact_id']]=f
            assert f['segment']==name and f['no_peak_selection'] and f['no_hole_filling'] and f['no_history_input_or_state_write']
        reasons=Counter();partner_reasons=Counter();statuses=Counter();eligible_original=Counter();compared=0;checks=0;citations=0
        tx=iter(rows(public/'TRANSACTIONS.jsonl.gz'))
        for r in rows(public/'ORDER_CHECKS.jsonl.gz'):
            original=next(tx);actual=next(tx)
            assert (original['frame'],original['arm'])==(r['frame'],'Z4Q_FROZEN')
            assert (actual['frame'],actual['arm'])==(r['frame'],'Z4Q_RELATIVE_ORDER')
            assert actual['controller_trace']['relative_order_checks']==r['checks']
            for x in r['checks']:
                checks+=1;reasons[x['reason']]+=1
                for c in x['comparisons']:
                    compared+=1;partner_reasons[c['reason']]+=1;statuses[c['status']]+=1
                    if 'pre_pairs' not in c:continue
                    pairs=c['pre_pairs'];post=c['current_pair']
                    for pair in pairs:
                        assert pair['frame']<r['frame'] and pair['time']<r['time']
                        for role in ('A','B'):
                            rep=pair[role];f=facts[rep['fact_id']];assert f['frame']==pair['frame']
                            assert representative(f)==rep;citations+=1
                    for role in ('A','B'):
                        rep=post[role];f=facts[rep['fact_id']];assert f['frame']==r['frame'] and f['time']==r['time']
                        assert representative(f)==rep;citations+=1
                    recomputed=pair_order(pairs,post,r['time'])
                    assert all(c[k]==v for k,v in recomputed.items())
                    assert c['pre_versions']['B']==c['current_partner_claim_version']
                    assert all(y['frame']<r['frame'] for y in c['anonymous_risk_interval'])
                if 'target_anchor_version' in x:
                    recomputed=combine(x['comparisons']);assert all(x[k]==v for k,v in recomputed.items())
                edges=actual['controller_trace']['edges' if x['origin_rule']=='D1_DELAYED' else 'birth_checks']
                relevant=[e for e in edges if e.get('native_id')==x['native_id'] and e.get('canonical_id')==x['public_id']]
                assert len(relevant)==1 and relevant[0]['edge_veto']==x
                edge=relevant[0]
                if x['veto']:assert edge['rejection']=='pairwise_history_conflict' or edge.get('rejection') is not None
                if edge.get('rejection') is None and edge.get('cost') is not None and edge['cost']<1:
                    eligible_original[x['reason']]+=1
        access=read(public/'SOURCE_ACCESS.json')
        assert all(x['frame']<=x['query_cutoff_frame'] for x in access['actual_reads'])
        assert not access['GT_RGB_restored_future_network']
        assert checks==summary['checks'] and len(facts)==summary['measured_objects']
        total_checks+=checks;total_comparisons+=compared;total_measures+=len(facts)
        results[name]=dict(frames=summary['frames'],candidate_checks=checks,partner_comparisons=compared,
            measured_objects=len(facts),measurement_reasons=summary['measurement_reasons'],
            evidence_reasons=dict(reasons),partner_reasons=dict(partner_reasons),comparison_statuses=dict(statuses),
            original_still_eligible_edge_reasons=dict(eligible_original),actual_measurement_citations=citations,
            actual_veto_checks=summary['veto_checks'],actual_changed_frames=summary['changed_frames'])
    write_new(HERE/'INPUT_REVIEW.json',dict(status='PASS',GT_read=False,frames=20098,
        candidate_checks=total_checks,partner_comparisons=total_comparisons,measured_objects=total_measures,
        segments=results,every_derived_order_recomputed=True,measurement_hash_and_frame_bindings=True,
        unknown_is_original_behavior=True,new_model_http=0,cost_usd=0))
    print(json.dumps(dict(checks=total_checks,partner_comparisons=total_comparisons,measured_objects=total_measures)),flush=True)

if __name__=='__main__':review()
