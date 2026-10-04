"""Postseal-only numeric/source/matrix audit; does not read GT or score metrics."""
from common import *
from collections import Counter, defaultdict
from datetime import datetime, timezone
import math
import statistics
import time


def close(a, b):
    assert math.isclose(float(a), float(b), rel_tol=1e-11, abs_tol=1e-11), (a, b)


def t4_cdf(x):
    u=x/math.hypot(x,2.)
    return max(0.,min(1.,.5+.75*u-.25*u**3))


def audit_measurement(f, parameters):
    assert f['parameters']==parameters
    assert digest({k:v for k,v in f.items() if k!='measurement_sha256'})==f['measurement_sha256']
    assert all(f[k]=='UNKNOWN' for k in ('physical_fish_count','identity','foreground_identity','physical_background'))
    assert f['scalar_replacement']=='NONE_IN_ORIGINAL_Z4Q_BANK'
    assert f['no_GT_RGB_future_or_restored_input'] and f['no_sensor_completion']
    assert f['no_history_input_or_state_write'] and f['no_peak_selection'] and f['no_hole_filling']
    assert f['original_roi_area']>=f['original_roi_missing_n']>=0
    measured=[s for s in f['layers'] if s['kind']=='MEASURED_DEPTH_SUPPORT']
    assert len({s['support_id'] for s in f['layers']})==len(f['layers'])
    assert sum(s['independent_n'] for s in measured)==f['summary']['n']
    for s in f['layers']:
        assert s['physical_surface_identity']=='UNKNOWN' and s['fish_count']=='UNKNOWN'
        if s['kind']=='MISSING_DEPTH':
            assert not s['qualified'] and s['z_mm'] is None and s['sigma_mm'] is None
            continue
        close(s['support_fraction_of_original_roi'],s['independent_n']/max(1,f['original_roi_area']))
        assert s['substantial']==bool(s['independent_n']>=parameters['minimum_layer_n'] and
            s['support_fraction_of_original_roi']>=parameters['minimum_layer_fraction'])
    if f['plane'] is not None:
        plane=f['plane'];sigma=plane['residual_scale_mm']
        close(plane['contrast_threshold_mm'],max(parameters['background_contrast_floor_mm'],
            parameters['background_sigma_factor']*sigma))
        assert plane['physical_accuracy_mm']=='UNKNOWN'
        for s in measured:
            for prefix,stat in (('',s['independent_summary']),('inclusive_',s['inclusive_summary'])):
                if stat['scale_mm'] is None:
                    assert s[prefix+'sigma_mm'] is None
                    continue
                prediction=s[prefix+'prediction_uncertainty_mm']['q90']
                close(s[prefix+'sigma_mm'],math.sqrt(stat['scale_mm']**2+sigma**2+prediction**2))
                contrast=s[prefix+'median_residual_mm']
                compatible='UNKNOWN' if contrast is None else 'BACKGROUND_COMPATIBLE' if abs(contrast)<=plane['contrast_threshold_mm'] else 'DIFFERENT_FROM_LOCAL_ANNULUS_PROXY'
                assert s[prefix+'background_compatibility']==compatible
                assert s[prefix+'qualified']==bool(s[prefix+'substantial'] and sigma<=parameters['max_scale_mm'] and
                    s[prefix+'sigma_mm']<=parameters['max_scale_mm'] and compatible=='DIFFERENT_FROM_LOCAL_ANNULUS_PROXY')
    if f.get('inclusive_independent_partition_agreement') and f.get('inclusive_independent_support_agreement'):
        assert f['qualified_support_ids']==[s['support_id'] for s in measured if s['qualified']]


def audit_endpoint(endpoint, native, facts, arm, frame):
    key=(arm,endpoint['fact_id'],endpoint['measurement_sha256'])
    assert key in facts, ('UNBOUND_ENDPOINT',key)
    f=facts[key]
    assert endpoint['frame']==f['frame']==frame
    assert f['roi_binding']==f['original_mask_bindings'][str(native)], 'Endpoint ROI is not the actual original mask'
    assert endpoint['foreground_identity']=='UNKNOWN'
    available=bool(f.get('inclusive_independent_partition_agreement') and f.get('inclusive_independent_support_agreement') and
        not f.get('substantial_unresolved_support_ids'))
    supports=[s for s in f['layers'] if s['qualified']]
    available=available and len(supports)==1 and f['summary']['n']>=16 and f['summary']['valid_fraction']>=.2
    assert endpoint['status']==('CONDITIONAL_MEASURED_SUPPORT' if available else 'COMMON_NULL')
    if available:
        support=supports[0]
        assert endpoint['support_id']==support['support_id']
        assert endpoint['z_mm']==support['z_mm'] and endpoint['sigma_mm']==support['sigma_mm']
        assert endpoint['independent_n']==support['independent_n']
        close(endpoint['reliability'],min(1.,support['independent_n']/max(1,f['original_roi_area'])))
        assert endpoint['background_and_missing_weight']=='REMAIN_COMMON_NULL'
    else:
        assert not any(k in endpoint for k in ('support_id','z_mm','sigma_mm','reliability'))
    return f


def audit_pair(pair, a, b, frame, facts, arm):
    audit_endpoint(pair['A'],a,facts,arm,frame);audit_endpoint(pair['B'],b,facts,arm,frame)
    ea,eb=pair['A'],pair['B']
    if pair['status']=='COMMON_NULL':
        assert pair['probability_A_nearer']==.5
        if ea['status']!='COMMON_NULL' and eb['status']!='COMMON_NULL':
            assert pair['reason']=='SHARED_NATIVE_SOURCE_COMMON_NULL'
        return
    assert pair['status']=='CONDITIONAL_ORDER_PROXY'
    assert ea['status']==eb['status']=='CONDITIONAL_MEASURED_SUPPORT'
    delta=eb['z_mm']-ea['z_mm'];scale=math.hypot(ea['sigma_mm'],eb['sigma_mm'])
    p=t4_cdf(delta/scale);reliability=ea['reliability']*eb['reliability']
    close(pair['delta_B_minus_A_mm'],delta);close(pair['scale_mm'],scale)
    close(pair['distribution_probability'],p);close(pair['common_null_weight'],1-reliability)
    close(pair['probability_A_nearer'],.5+reliability*(p-.5))
    assert pair['physical_accuracy_mm']=='UNKNOWN'


def audit_check(check, arm, row, facts, metadata, cfg):
    assert check['query_frame']==row['frame'] and check['query_time']==row['time']
    assert not check['hard_veto'] and check['own_dummy_cost']==1.
    assert check['competition_window']==cfg['competition_window']
    assert abs(check['requested_delta_cost'])<=cfg['soft_weight']+1e-12
    assert check['cost_effective']==max(0.,check['cost_original']+check['requested_delta_cost'])
    assert check['applied_delta_cost']==check['cost_effective']-check['cost_original']
    assert check['delta_cost']==check['requested_delta_cost']
    if check['status'] in ('UNKNOWN','DISABLED','COMMON_NULL'):
        assert check['delta_cost']==0.
    deltas=[]
    for c in check.get('comparisons',[]):
        if 'pre_pairs' not in c:
            assert c['status']=='COMMON_NULL' and c['delta_cost']==0.
            deltas.append(0.);continue
        pre=c['pre_frames'];q=row['frame'];old=check['anchor']['native_id'];partner=c['partner_native']
        assert len(pre)==len(c['pre_pairs']) and pre==sorted(set(pre)) and len(pre)>=cfg['minimum_pre_pairs']
        assert pre[-1]==check['anchor']['frame'] and all(g<q for g in pre)
        assert c['pre_versions']['A']==check['target_anchor_version']
        assert c['pre_versions']['B']==c['current_partner_claim_version']
        assert c['pre_versions']['A'][0]==old and c['pre_versions']['A'][2]==check['public_id']
        assert c['pre_versions']['B'][0]==partner and c['pre_versions']['B'][2]==c['partner_public']
        assert c['complete_mapping_hypothesis']=={str(check['native_id']):check['public_id'],str(partner):c['partner_public']}
        for g,pair in zip(pre,c['pre_pairs'],strict=True):audit_pair(pair,old,partner,g,facts,arm)
        audit_pair(c['current_pair'],check['native_id'],partner,q,facts,arm)
        pp=statistics.median(x['probability_A_nearer'] for x in c['pre_pairs'])
        pq=c['current_pair']['probability_A_nearer'];age=max(0.,row['time']-metadata[pre[-1]]['time'])
        attenuation=max(0.,1-age/cfg['age_attenuation_s'])
        delta=(-cfg['soft_weight']*(2*pp-1)*(2*pq-1)*attenuation
            if abs(pp-.5)>=cfg['minimum_pre_probability_distance'] else 0.)
        close(c['pre_probability_median'],pp);close(c['current_probability'],pq)
        close(c['elapsed_seconds'],age);close(c['age_attenuation'],attenuation);close(c['delta_cost'],delta)
        assert c['status']==('SOFT_CONDITIONAL_ORDER' if delta else 'COMMON_NULL')
        assert [r['frame'] for r in c['anonymous_interval']]==list(range(pre[-1]+1,q))
        for r in c['anonymous_interval']:
            assert r['time']==metadata[r['frame']]['time']
            assert r['identity_roles']=='UNKNOWN_RISK_EVIDENCE_NOT_REFERENCE'
        deltas.append(delta)
    close(check['requested_delta_cost'],statistics.mean(deltas) if deltas else 0.)


def audit_matrix_trace(tx, checks, cfg):
    trace=tx['controller_trace'];bound={}
    for phase,key in (('D1_DELAYED','edges'),('BIRTH_REFINE','birth_checks')):
        by_native=defaultdict(list)
        for edge in trace.get(key,[]):
            if 'cost_original' not in edge:continue
            n,k=edge['native_id'],edge['canonical_id'];original=edge['cost_original']
            original_formula=(edge['residual_mm']/edge['tolerance_mm']+.15*edge['motion_cost']
                if phase=='D1_DELAYED' else edge['core']['cost']+.15*edge['motion_cost'])
            close(original,original_formula)
            assert edge['cost']==edge['cost_effective']
            by_native[n].append(edge)
            if 'depth_soft' in edge:
                assert (phase,n,k) not in bound
                bound[phase,n,k]=edge['depth_soft']
                assert edge['cost_effective']==edge['depth_soft']['cost_effective']
            else:assert edge['cost_effective']==original
        for n,edges in by_native.items():
            minimum=min([1.,*[e['cost_original'] for e in edges]])
            near=[e for e in edges if e['cost_original']<=minimum+cfg['competition_window']]
            dummy_near=1.<=minimum+cfg['competition_window']
            expected=near if len(near)+int(dummy_near)>=2 else []
            assert {e['canonical_id'] for e in edges if 'depth_soft' in e}=={e['canonical_id'] for e in expected}
            for e in expected:
                c=e['depth_soft'];assert c['row_original_minimum']==minimum and c['own_dummy_near']==dummy_near
                assert set(c['near_target_ids'])=={v['canonical_id'] for v in near}
    assert len(bound)==len(checks)
    for c in checks:assert bound[c['origin_rule'],c['native_id'],c['public_id']]==c


def brief_check(c, global_frame):
    keys=('origin_rule','native_id','public_id','cost_original','cost_effective',
          'requested_delta_cost','applied_delta_cost','status','reason')
    return dict(frame=c['query_frame'],global_frame=global_frame,**{k:c[k] for k in keys})


def audit_segment(name, runtime):
    public=RUN/name/'public';start,end=SEGMENTS[name];cfg=runtime['actual_soft_parameters']
    metadata={r['frame']:dict(global_frame=r['global_frame'],time=r['time'],binding=r['raw_source_binding'])
        for r in rows(input_dir(name)/'DEPTH_OBSERVATIONS.jsonl.gz')}
    assert len(metadata)==end-start+1
    facts={};measurements={a:Counter() for a in ARMS[2:]};qualifications={a:Counter() for a in ARMS[2:]}
    for item in rows(public/'MEASUREMENTS.jsonl.gz'):
        arm=item['arm'];f=item['measurement'];meta=metadata[f['frame']]
        assert arm in measurements and f['segment']==name
        assert (f['global_frame'],f['time'],f['source_binding'])==(meta['global_frame'],meta['time'],meta['binding'])
        audit_measurement(f,runtime['effective_measurement_parameters'][arm])
        key=(arm,f['fact_id'],digest(f));assert key not in facts,'Duplicated sealed measurement identifier'
        facts[key]=f;measurements[arm][f['reason']]+=1
        qualifications[arm]['facts']+=1;qualifications[arm]['qualified_supports']+=sum(s['qualified'] for s in f['layers'])
        qualifications[arm]['qualified_support_count_'+str(sum(s['qualified'] for s in f['layers']))]+=1
        qualifications[arm]['missing_depth_pixels']+=f['original_roi_missing_n']
        qualifications[arm]['background_compatible_supports']+=sum(s['background_compatibility']=='BACKGROUND_COMPATIBLE' for s in f['layers'])
    aggregate={a:dict(counts=Counter(),reasons=Counter(),comparison_reasons=Counter(),phases=Counter(),
        actions=[],first_cost_update=None,first_publication_divergence=None,first_state_divergence=None) for a in ARMS[1:]}
    tx=iter(rows(public/'TRANSACTIONS.jsonl.gz'));risk=iter(rows(public/'ANONYMOUS_RISK.jsonl.gz'))
    archive=rows(ROOT/'experiments/ds20_pending_confirmation_isolation/run'/name/'public/predictions.jsonl.gz')
    changed={a:False for a in ARMS[2:]};objects=0;count=0
    for count,(p,assignment,old,ledger,checkrow,observationrow) in enumerate(zip(rows(public/'predictions.jsonl.gz'),
        rows(input_dir(name)/'assignments.jsonl.gz'),archive,rows(public/'PUBLISH_LEDGER.jsonl'),
        rows(public/'ORDER_CHECKS.jsonl.gz'),rows(input_dir(name)/'observations.jsonl.gz'),strict=True),1):
        assert p['frame']==count and p['global_frame']==start+count-1
        identity=(count,p['global_frame'],p['time'])
        assert (ledger['frame'],ledger['global_frame'],ledger['time'])==identity
        assert (checkrow['frame'],checkrow['global_frame'],checkrow['time'])==identity
        assert (observationrow['frame'],observationrow['global_frame'],observationrow['time'])==identity
        assert ledger['prediction_row_sha256']==row_sha(p) and ledger['checks_row_sha256']==row_sha(checkrow)
        assert ledger['model_http']==0
        assert tuple(p['variants'])==ARMS and set(ledger['transaction_row_sha256'])==set(ARMS[1:])
        assert set(checkrow['checks'])==set(ARMS[2:])
        assert p['variants']['SAM3_NATIVE']==assignment['variants']['N0']==old['variants']['SAM3_NATIVE']
        assert p['variants']['Z4Q_FROZEN']==old['variants']['Z4Q_FROZEN']
        native=p['variants']['SAM3_NATIVE'];masks=[o['mask'] for o in native];objects+=len(native)
        sources=[int(m[2:]) for m in masks];baseline_tx=None
        for arm in ARMS:
            published=p['variants'][arm]
            assert [o['mask'] for o in published]==masks
            assert len({o['id'] for o in published})==len(native)
            if arm=='SAM3_NATIVE':continue
            record=next(tx);trace=record['controller_trace'];stats=aggregate[arm]
            assert (record['frame'],record['global_frame'],record['time'])==identity and record['arm']==arm
            assert row_sha(record)==ledger['transaction_row_sha256'][arm] and record['branch_version']==count
            mapping={str(n):o['id'] for n,o in zip(sources,published,strict=True)}
            assert record['actual_published_mapping']==mapping
            stats['last_engine_state_sha256']=record['engine_state_sha256']
            stats['counts']['frames']+=1
            for event in trace['events']:
                stats['counts']['event_'+event['kind']]+=1
                if event.get('kind')=='reconnect':stats['counts']['proposals_accepted' if event.get('accepted') else 'proposals_pending']+=1
            for item in record['actual_actions']:
                action=item['action'];n,k=action['native_id'],action['canonical_id']
                assert item['actual_published']==(mapping[str(n)]==k)
                assert item['durable_alias']==(record['actual_alias_targets'].get(str(n))==k)
                if 'cost_effective' in action:assert action['cost']==action['cost_effective']
                stats['actions'].append(dict(frame=count,global_frame=p['global_frame'],source=n,target=k,
                    phase='BIRTH_REFINE' if action.get('phase')=='birth' else 'D1_DELAYED',
                    original_cost=action.get('cost_original',action['cost']),effective_cost=action['cost'],
                    assignment_margin=action['assignment_margin'],confirmations=action['confirmations'],
                    anchor=action.get('old_anchor'),actual_published=item['actual_published'],durable_alias=item['durable_alias'],
                    physical_reference_verdict='NOT_READ_IN_THIS_NO_GT_AUDIT'))
            if arm=='Z4Q_FROZEN':baseline_tx=record;continue
            checks=checkrow['checks'][arm];assert checks==trace['depth_soft_checks']
            audit_matrix_trace(record,checks,cfg)
            for c in checks:
                audit_check(c,arm,p,facts,metadata,cfg)
                stats['counts']['checks']+=1;stats['reasons'][c['reason']]+=1;stats['phases'][c['origin_rule']]+=1
                stats['counts']['status_'+c['status']]+=1
                for comparison in c.get('comparisons',[]):
                    stats['comparison_reasons'][comparison.get('reason',comparison['status'])]+=1
                    if 'pre_pairs' in comparison:
                        for pair in [*comparison['pre_pairs'],comparison['current_pair']]:
                            stats['counts']['pair_'+pair['status']]+=1
                            for endpoint in (pair['A'],pair['B']):stats['counts']['endpoint_'+endpoint['status']]+=1
                if c['applied_delta_cost']:
                    changed[arm]=True;stats['counts']['soft_cost_updates']+=1
                    if stats['first_cost_update'] is None:stats['first_cost_update']=brief_check(c,p['global_frame'])
            if record['engine_state_sha256']!=baseline_tx['engine_state_sha256']:
                if stats['first_state_divergence'] is None:stats['first_state_divergence']=dict(frame=count,global_frame=p['global_frame'])
            if not changed[arm]:assert record['engine_state_sha256']==baseline_tx['engine_state_sha256']
            if published!=p['variants']['Z4Q_FROZEN']:
                stats['counts']['changed_publication_frames']+=1
                if stats['first_publication_divergence'] is None:
                    stats['first_publication_divergence']=dict(frame=count,global_frame=p['global_frame'],changes=[dict(
                        native=n,mask=new['mask'],original_public_id=before['id'],new_public_id=new['id'])
                        for n,before,new in zip(sources,p['variants']['Z4Q_FROZEN'],published,strict=True) if before!=new])
            if not changed[arm]:assert published==p['variants']['Z4Q_FROZEN']
            riskrow=next(risk)
            assert (riskrow['frame'],riskrow['global_frame'],riskrow['time'])==identity and riskrow['arm']==arm
            assert riskrow['input_observation_row_sha256']==row_sha(observationrow)
            assert riskrow['no_individual_depth_history_write'] and riskrow['no_Z4Q_bank_measurement_write']
        if count%2000==0:print('POSTSEAL_QA',name,count,flush=True)
    assert next(tx,None) is None and next(risk,None) is None and count==end-start+1
    summary=read(public/'RUN_SUMMARY.json');assert summary['frames']==count and summary['objects']==objects
    for arm in ARMS[2:]:
        assert summary['checks'][arm]==aggregate[arm]['counts']['checks']
        assert summary['soft_cost_updates'][arm]==aggregate[arm]['counts']['soft_cost_updates']
        assert summary['changed_frames'][arm]==aggregate[arm]['counts']['changed_publication_frames']
    assert len(facts)==summary['measured_objects']
    return dict(frames=count,objects=objects,arms=aggregate,measurement_reasons=measurements,
        measurement_qualifications=qualifications,unique_measurements=len(facts),
        native_and_original_Z4Q_same_source_exact=True,mask_retention_and_same_frame_public_id_uniqueness=True,
        ledger_transaction_checks_and_input_source_bindings=True,
        transient_matrix_audit='RECONSTRUCTED_LEGAL_COSTS_BOUND_TO_ACTUAL_CALL_TRACE_AND_FROZEN_RUNTIME; BINARY_MATRIX_NOT_EXPORTED',
        native_source_intersection_boundary='Frozen runtime performs actual intersection; public source hashes alone are not a new independent pixel-level recomputation.')


def main():
    # No prediction/result/GT audit is allowed until the actual final seal exists.
    manifest=read(RUN/'ALL_PREDICTIONS_SEALED.json')
    assert manifest['status']=='ALL_PREDICTIONS_AND_ACCESS_SEALED' and manifest['frames']==20098
    runtime=read(HERE/'RUNTIME_FREEZE.json')
    assert all(Path(p).resolve()!=Path(__file__).resolve() for p in runtime['code']), 'Postseal review is accidentally part of frozen runtime'
    for p,pin in runtime['code'].items():assert sha(p)==pin,p
    import score
    assert score.verify_all()==manifest
    began=time.perf_counter();segments={}
    for name in SEGMENTS:segments[name]=audit_segment(name,runtime)
    assert sum(x['frames'] for x in segments.values())==20098
    totals={a:Counter() for a in ARMS[1:]}
    for segment in segments.values():
        for arm,stats in segment['arms'].items():totals[arm].update(stats['counts'])
    result=dict(status='PASS_POSTSEAL_ENGINEERING_INPUT_MATRIX_AND_PUBLICATION_QA',
        created_utc=datetime.now(timezone.utc).isoformat(),frames=20098,arms=ARMS,
        runtime_freeze=artifact(HERE/'RUNTIME_FREEZE.json'),all_predictions_seal=artifact(RUN/'ALL_PREDICTIONS_SEALED.json'),
        reviewer=artifact(__file__),frozen_code_verified=len(runtime['code']),segments=segments,totals_by_arm=totals,
        elapsed_seconds=time.perf_counter()-began,
        score_metric_files_read=False,GT_RGB_depth_rasters_read=False,new_model_http=0,cost_usd=0,
        conclusion_boundary='Engineering consistency is not depth efficacy, physical identity correctness or metric improvement.')
    write_new(HERE/'POSTSEAL_QA.json',result)
    print(json.dumps(dict(status=result['status'],frames=20098,totals_by_arm=totals),ensure_ascii=False),flush=True)

if __name__=='__main__':main()
