"""Independent postseal arithmetic and fixed-cohort paired observability review."""
from common import *
from collections import Counter
from datetime import datetime,timezone
import math
from measurement_adapter import summarize

def main():
    freeze=check_freeze();seal=read(RUN/'MEASUREMENTS_SEALED.json')
    assert seal['status']=='SEALED_BEFORE_INDEPENDENT_REVIEW'
    for p in seal['artifacts'].values():verify_item(p)
    verify_item(seal['cohort']);verify_item(seal['runtime'])
    cohort=read(HERE/'COHORT.json'); facts={f['fact_id']:f for f in rows(RUN/'ENDPOINT_FACTS.jsonl.gz')}
    oldfacts={f['fact_id']:f for f in rows(RUN/'OLD_UNCHANGED_FACTS.jsonl.gz')}
    pairs=list(rows(RUN/'PAIRINGS.jsonl.gz')); logical=list(rows(RUN/'LOGICAL_PAIR_REFERENCES.jsonl.gz'))
    assert logical==cohort['logical_pairs'] and len(pairs)==651
    oldaudit=module('ds26_independent_old_fact_arithmetic',DS25/'review.py')
    for f in [*facts.values(),*oldfacts.values()]:oldaudit.audit_measurement(f,f['segment'])
    assert {x['task_id'] for x in pairs}.__len__()==len(pairs)
    for p in pairs:
        f=p['frame'];assert f<=p['causal_query_limit'] and not p['state_write']
        old=p['old_contact_roi_citation'];assert digest(oldfacts[old['fact_id']])==old['measurement_sha256']
        assert p['old_contact_roi_summary']==summarize(oldfacts[old['fact_id']])
        for role,ref in p['role_facts'].items():
            actual=facts[ref['fact_id']]
            assert digest(actual)==ref['measurement_sha256'] and ref['summary']==summarize(actual)
            assert actual['roi_binding']==p['actual_masks'][role] and actual['frame']==f
            assert digest(actual['source_binding'])==p['source_binding_sha256']
        cross=p['cross_role'];summaries=[p['role_facts'][r]['summary'] for r in ('A','B')]
        independent=not cross['source_overlaps']['qualified_native_sources']['n']
        eligible=all(s['sole_proxy_eligible'] for s in summaries) and independent
        assert cross['pair_proxy_eligible']==eligible and cross['identity_independence']=='UNKNOWN'
        assert cross['physical_identity']==cross['foreground_identity']=='UNKNOWN'
        assert cross['no_identity_veto'] and cross['no_state_write'] and not cross['source_index_temporal_correspondence']
        for key,pop in cross['source_overlaps'].items():
            assert 0<=pop['n']<=min(cross['populations'][r][key]['n'] for r in ('A','B'))
        if eligible:
            ls=[next(x for x in s['layers'] if x['support_id']==s['sole_proxy_support_id']) for s in summaries]
            delta=ls[1]['z_mm']-ls[0]['z_mm'];sigma=math.hypot(*(x['sigma_mm'] for x in ls))
            assert math.isclose(cross['measured_depth_difference_mm'],delta,abs_tol=1e-10)
            assert math.isclose(cross['propagated_sigma_mm'],sigma,abs_tol=1e-10)
            assert math.isclose(cross['standardized_difference'],delta/sigma,abs_tol=1e-12)
        else:assert cross['measured_depth_difference_mm'] is None and cross['measured_order']=='UNKNOWN'
    stages={}
    for phase in sorted({p['phase'] for p in pairs}):
        group=[p for p in pairs if p['phase']==phase];roles=[r['summary'] for p in group for r in p['role_facts'].values()]
        stages[phase]=dict(paired_frames=len(group),role_references=len(roles),
            old_empty=sum(p['old_contact_roi_summary']['original_roi_area']==0 for p in group),
            actual_mask_empty=sum(s['original_roi_area']==0 for s in roles),
            old_qualified_support_count=dict(Counter(p['old_contact_roi_summary']['qualified_support_count'] for p in group)),
            actual_role_qualified_support_count=dict(Counter(s['qualified_support_count'] for s in roles)),
            actual_role_reasons=dict(Counter(s['original_reason'] for s in roles)),
            sole_proxy_roles=sum(s['sole_proxy_eligible'] for s in roles),
            both_disjoint_sole_proxy_pairs=sum(p['cross_role']['pair_proxy_eligible'] for p in group),
            shared_raw_source_pairs=sum(p['cross_role']['source_overlaps']['inclusive_raw_native_sources']['n']>0 for p in group),
            shared_qualified_source_pairs=sum(p['cross_role']['source_overlaps']['qualified_native_sources']['n']>0 for p in group),
            background_compatible_roles=sum(any(l['background_compatibility']=='BACKGROUND_COMPATIBLE' for l in s['layers']) for s in roles),
            missing_depth_roles=sum(s['original_roi_missing_n']>0 for s in roles),
            raw_support_count=sum(len(s['layers']) for s in roles),
            standardized_differences=[p['cross_role']['standardized_difference'] for p in group if p['cross_role']['pair_proxy_eligible']])
    contexts=[]
    for c in cohort['contexts']:
        group=[p for p in pairs if p['context_id']==c['context_id']];pre=[p for p in group if p['phase'].startswith('PRE')];post=[p for p in group if p['phase'].startswith('POST')]
        relevant=[p for p in logical if p['context_id']==c['context_id']]
        seed=oldfacts[c['key']['seed_fact_id']];contacts={x['fact_id']:oldfacts[x['fact_id']] for p in relevant for x in p['ds25_citations']['anonymous_contact']}
        perquery=[]
        for p in relevant:
            endpoint=next(v for v in post if v['pair_id']==p['pair_id'])
            chain=[oldfacts[x['fact_id']] for x in p['ds25_citations']['anonymous_contact']]
            perquery.append(dict(pair_id=p['pair_id'],q=p['q'],current_native=p['current_native'],
                current_actual_public=p['current_actual_public'],target_public=p['target_public'],
                post_disjoint_sole_proxy=endpoint['cross_role']['pair_proxy_eligible'],
                contact_available_frames=sum(f['status']=='AVAILABLE_TWO_LAYERS' for f in chain),
                contact_frames=len(chain),complete_contact_two_layers=all(f['status']=='AVAILABLE_TWO_LAYERS' for f in chain),
                continuous_identity_chain='UNKNOWN; NO_NEW_SPATIAL_LINK_OR_IDENTITY_RULE'))
        contexts.append(dict(context_id=c['context_id'],segment=c['key']['segment'],
            exact_reference=c['key'],pre_pairs=len(pre),post_candidate_pairs=len(post),
            pre_disjoint_sole_proxy_pairs=sum(p['cross_role']['pair_proxy_eligible'] for p in pre),
            all_pre_disjoint_sole_proxy=all(p['cross_role']['pair_proxy_eligible'] for p in pre),
            post_disjoint_sole_proxy_pairs=sum(p['cross_role']['pair_proxy_eligible'] for p in post),
            seed=summarize(seed),unchanged_contact_unique_facts=len(contacts),
            unchanged_contact_two_layers=sum(f['status']=='AVAILABLE_TWO_LAYERS' for f in contacts.values()),
            unchanged_contact_qualified_count=dict(Counter(len(f['qualified_support_ids']) for f in contacts.values())),
            per_query=perquery,identity_certified=False))
    result=dict(status='ENGINEERING_COMPLETE_READONLY_PHASE_MEASUREMENT_NO_IDENTITY_INCREMENT_TEST',
        created_utc=datetime.now(timezone.utc).isoformat(),cohort_selection=cohort['selection'],
        unique_endpoint_facts=len(facts),unique_old_facts=len(oldfacts),stages=stages,contexts=contexts,
        seed_two_layers=sum(c['seed']['original_status']=='AVAILABLE_TWO_LAYERS' for c in contexts),
        complete_contact_chains=sum(v['complete_contact_two_layers'] for c in contexts for v in c['per_query']),
        new_tracking_predictions=0,state_commits=0,GT_RGB_reads=0,new_model_http=0,cost_usd=0,
        IDF1_HOTA_AssA_IDSW_FP_FN='NOT_RERUN; THIS_IS_A_MEASUREMENT_AUDIT',
        physical_identity='UNKNOWN',physical_depth_accuracy='UNKNOWN',
        limitations=['Fixed prediction contexts are correlated, not independent biological events.',
            'ROI, quality denominator, annulus and background fit change together as the measurement object changes.',
            'Same-mask gap components can include background or both fish; no best peak is selected.',
            'Sole proxy means one unambiguous qualified anonymous support, not a fish identity.',
            'RSS sigma omits shared-annulus covariance and does not certify physical depth accuracy.',
            'Post source geometry does not certify the candidate old identity; complete contact chain remains mandatory for DS25.'])
    write_new(HERE/'RESULTS.json',result)
    write_new(HERE/'POSTSEAL_REVIEW.json',dict(status='PASS',seal=artifact(RUN/'MEASUREMENTS_SEALED.json'),
        reviewed_utc=result['created_utc'],actual_fact_arithmetic_audited=len(facts)+len(oldfacts),
        full_logical_role_version_cohort_preserved=True,all_original_contact_values_unchanged=True,
        paired_endpoint_references=len(pairs),no_GT_or_RGB=True,code={str(p):sha(p) for p in [Path(__file__),DS25/'review.py',HERE/'measurement_adapter.py']},new_model_http=0,cost_usd=0))
    print(json.dumps(dict(status=result['status'],stages=stages,seed_two_layers=result['seed_two_layers'],complete_contact_chains=result['complete_contact_chains']),ensure_ascii=False))

if __name__=='__main__': main()
