"""DS32 postseal numeric mechanism audit; never participates in prediction/score."""
from common import *
from collections import Counter
import copy, math


def mapping(objects):
    return {int(o['mask'][2:]):o['id'] for o in objects}


def decision_edges(trace, accepted_only=False):
    return [dict(phase='BIRTH_REFINE' if e.get('phase')=='birth' else 'D1_DELAYED',
        native_id=e['native_id'],canonical_id=e['canonical_id'],
        accepted=bool(e.get('accepted')),reference=copy.deepcopy(e.get('old_anchor')))
        for e in trace.get('events',[]) if e.get('kind')=='reconnect'
        and (not accepted_only or e.get('accepted'))]


def edge_key(check):
    return (check['frame'],check['phase'],check['native_id'],check['canonical_id'])


def delta_mapping(before, after):
    return [dict(native_id=n,before=before[n],after=after[n])
        for n in sorted(before) if before[n]!=after[n]]


def read_frames(name, output=RUN):
    p=output/name/'public';tx=iter(rows(p/'TRANSACTIONS.jsonl.gz'))
    for pr,ledger,depth in zip(rows(p/'predictions.jsonl.gz'),
        rows(p/'PUBLISH_LEDGER.jsonl'),rows(p/'DEPTH_EXTRACTS.jsonl.gz'),strict=True):
        frame=pr['frame'];assert frame==ledger['frame']==depth['frame']
        assert ledger['prediction_row_sha256']==row_sha(pr)
        assert ledger['depth_extract_row_sha256']==row_sha(depth)
        records={}
        for arm in ARMS[1:]:
            t=next(tx);assert t['arm']==arm and t['frame']==frame
            assert row_sha(t)==ledger['transaction_row_sha256'][arm]
            assert t['decided_before_first_publish'] and t['version']==frame
            assert {int(n):p for n,p in t['mapping'].items()}==mapping(pr['variants'][arm])
            records[arm]=t
        assert all([o['mask'] for o in pr['variants'][a]]==
            [o['mask'] for o in pr['variants']['SAM3_NATIVE']] for a in ARMS)
        yield pr, records, depth
    assert next(tx,None) is None


def physical_from_scored_matches(matches, frame, native, anchor):
    """Reuse already-written scorer matches; never open another reference source."""
    a=matches.get(str(frame),{}).get(str(native),{})
    b=matches.get(str(anchor['frame']),{}).get(str(anchor['native_id']),{}) if anchor else {}
    if a.get('status')!='UNIQUE_IOU_MATCH' or b.get('status')!='UNIQUE_IOU_MATCH':
        return dict(relation='UNKNOWN',physical='UNSCORABLE',current=a,reference=b)
    same=a['gt_id']==b['gt_id']
    return dict(relation='SAME' if same else 'DIFFERENT',physical='CORRECT' if same else 'WRONG',current=a,reference=b)


def query_numeric(check):
    """Only returned observations/predictions; no fabricated residual or age."""
    samples=check['samples'];current=check.get('current') or {};forecast=check.get('forecast') or {}
    anchor_bound=bool(samples and samples[-1]['anchor']==check['anchor'])
    span=samples[-1]['time']-samples[0]['time'] if samples else None
    threshold=check.get('threshold');residual=check.get('residual_mm')
    return dict(target_returned_sample_count=len(samples),current_measured_scale_mm=current.get('scale_mm'),
        target_last_measured_scale_mm=samples[-1]['scale_mm'] if samples else None,
        predicted_scale_mm=forecast.get('scale_mm'),forecast_slope_mm_s=forecast.get('slope_mm_s'),
        bound_anchor_age_s=check['source_contract']['query_time']-samples[-1]['time'] if anchor_bound else None,
        returned_history_time_span_s=span,forecast_fit_span_s=span if forecast.get('status')=='WLS_LINEAR_TIME' else None,
        residual_mm=residual,threshold_mm=threshold,
        residual_over_threshold=residual/threshold if residual is not None and threshold is not None and threshold>0 else None)


def record_query_diagnostics(buckets,check):
    values=query_numeric(check)
    for scope in ('all_queries','original_eligible_queries') if check['original_eligible'] else ('all_queries',):
        for phase,reason in [('ALL','ALL'),(check['phase'],'ALL'),(check['phase'],check['reason'])]:
            bucket=buckets.setdefault((scope,phase,reason),dict(queries=0,current_usable_queries=0,
                forecast_usable_queries=0,fields={}))
            bucket['queries']+=1;bucket['current_usable_queries']+=bool((check.get('current') or {}).get('usable'))
            bucket['forecast_usable_queries']+=bool((check.get('forecast') or {}).get('usable'))
            for field,value in values.items():
                stats=bucket['fields'].setdefault(field,dict(finite_values=[],missing=0,nonfinite=0))
                if value is None:stats['missing']+=1
                elif isinstance(value,(int,float)) and math.isfinite(value):stats['finite_values'].append(value)
                else:stats['nonfinite']+=1


def finish_query_diagnostics(buckets):
    import numpy as np
    result={scope:dict(overall=None,by_phase={}) for scope in ('all_queries','original_eligible_queries')}
    for (scope,phase,reason),bucket in sorted(buckets.items()):
        counts={key:value for key,value in bucket.items() if key!='fields'};fields={}
        for field,stats in bucket['fields'].items():
            values=stats['finite_values'];assert len(values)+stats['missing']+stats['nonfinite']==bucket['queries']
            quantiles=dict(zip(('min','q25','median','q75','max'),map(float,np.quantile(values,[0,.25,.5,.75,1])))) if values else None
            fields[field]=dict(denominator_queries=bucket['queries'],finite=len(values),missing=stats['missing'],
                nonfinite=stats['nonfinite'],quantiles=quantiles)
        group=dict(counts,fields=fields)
        if phase=='ALL':result[scope]['overall']=group
        else:
            destination=result[scope]['by_phase'].setdefault(phase,dict(overall=None,by_reason={}))
            if reason=='ALL':destination['overall']=group
            else:destination['by_reason'][reason]=group
    result['interpretation']=dict(no_missing_imputation=True,query_weighted_not_unique_event_weighted=True,
        zero_returned_samples_can_mean_unavailable_anchor_not_no_global_history=True,
        anchor_age_only_from_bound_actual_sample_time=True,residual_threshold_only_when_actually_defined=True,
        finite_measured_scale_does_not_certify_usable_measurement=True,
        forecast_scale_is_uncalibrated_proxy_not_physical_accuracy=True)
    return result


def record_fragment_break(classification,frame,now,last_source,pending_break,fragment_breaks,extract):
    native=classification['native'];record=dict(copy.deepcopy(classification),frame=frame,time=now)
    record['actual_depth_extract']=None if extract is None else {
        key:copy.deepcopy(extract.get(key)) for key in ('native','frame','time','reason','usable','quality','fact_id')}
    prior=last_source.get(native,{});previous=prior.get('last');prior_clean=prior.get('last_clean')
    identity=lambda r:(r['public'],r['source_generation'],r['public_epoch']) if r else None
    gap=[previous['frame']+1,frame-1] if previous and previous['frame']<frame-1 else None
    pending=pending_break.get(native)
    if classification['observation_class']!='CLEAN_ACTUAL_BANK_ANCHOR':
        if pending is None:
            pending=pending_break[native]=dict(first=record,last=record,observations=0,
                preceding_clean=copy.deepcopy(prior_clean),reasons=Counter(),depth_gate_reason_counts=Counter(),
                undefined_depth_gate_reasons=0,identities=set(),missing_gaps=[],all_depth_only=True)
        pending['last']=record;pending['observations']+=1;pending['reasons'].update(classification['reasons'])
        if extract is not None and extract.get('reason') is not None:pending['depth_gate_reason_counts'][extract['reason']]+=1
        else:pending['undefined_depth_gate_reasons']+=1
        pending['identities'].add(identity(record));pending['all_depth_only']&=classification['reasons']==['UNRELIABLE_CURRENT_DEPTH']
        if gap:pending['missing_gaps'].append(gap)
    elif classification['fragment_start']==frame:
        gaps=(pending['missing_gaps'][:] if pending else [])+([gap] if gap else [])
        changes={key:bool(previous and previous[key]!=record[key]) for key in ('public','source_generation','public_epoch')}
        clean_changes={key:bool(prior_clean and prior_clean[key]!=record[key]) for key in changes}
        depth_only=bool(pending and pending['all_depth_only'] and not gaps and prior_clean and
            pending['identities']=={identity(record)} and identity(prior_clean)==identity(record) and
            pending['first']['frame']==prior_clean['frame']+1)
        fragment_breaks[(native,frame)]=dict(native=native,fragment_start=frame,source_version=record['source_version'],
            previous_actual_observation=copy.deepcopy(previous),consecutive_from_previous_actual=bool(previous and not gap),
            preceding_clean_observation=copy.deepcopy(prior_clean),missing_native_frame_intervals=gaps,
            public_generation_epoch_change_from_previous_actual=changes,public_generation_epoch_change_from_previous_clean=clean_changes,
            preceding_risk_observations=0 if pending is None else pending['observations'],
            preceding_risk_reason_counts={} if pending is None else dict(pending['reasons']),
            preceding_risk_depth_gate_reason_counts={} if pending is None else dict(pending['depth_gate_reason_counts']),
            preceding_risk_undefined_depth_gate_reasons=0 if pending is None else pending['undefined_depth_gate_reasons'],
            first_preceding_risk=None if pending is None else copy.deepcopy(pending['first']),
            last_preceding_risk=None if pending is None else copy.deepcopy(pending['last']),
            pure_unreliable_current_depth_interruption=depth_only,
            pure_flag_semantics='Software observer reason only; UNRELIABLE_CURRENT_DEPTH also includes mixing, ownership, '
                'points, coverage and wide scale. It does not certify a pure sensor hole.',
            boundary='Actual branch source observations before this exact fragment; no inferred identity or predicted repair gain.')
        pending_break.pop(native,None)
    last_source[native]=dict(last=record,last_clean=record if classification['observation_class']=='CLEAN_ACTUAL_BANK_ANCHOR' else prior_clean)


def target_fragment_break(check,fragment_breaks):
    samples=check['samples'] if check else []
    if not samples:return dict(status='UNAVAILABLE_NO_BOUND_RETURNED_SAMPLES',no_history_inference=False)
    version=samples[-1]['version'];key=(samples[-1]['native'],version[-1]);record=fragment_breaks.get(key)
    if (not record or record['source_version']!=version or samples[-1]['anchor']!=check['anchor'] or
        any(s['version']!=version or s['native']!=key[0] for s in samples)):
        return dict(status='UNAVAILABLE_EXACT_FRAGMENT_BINDING_NOT_ESTABLISHED',no_history_inference=False)
    return dict(status='BOUND_TO_ACTUAL_TARGET_FRAGMENT',actual_bank_anchor=check['anchor'],
        target_version=version,target_sample_fact_ids=[s['fact_id'] for s in samples],preceding_break=copy.deepcopy(record))


def summarize(name, output=RUN, global_diagnostics=None):
    p=output/name/'public';summary=read(p/'RUN_SUMMARY.json')
    veto_audit=read(p/'VETO_AUDIT.json');physical={edge_key(x):x for x in veto_audit['conflicts']}
    counts=Counter();reasons=Counter();lookups=Counter();source_reasons=Counter()
    phases={phase:Counter() for phase in ('D1_DELAYED','BIRTH_REFINE')}
    query_diagnostics={}
    last_source={};pending_break={};fragment_breaks={}
    deletions=[];changes=[];first_nulls={};frames={}
    references=read(p/'REFERENCE_MATCHES.json');action_audit=read(p/'ACTION_AUDIT.json')
    switches=read(p/'SWITCHES.json');switches_by_frame={};native_switches={}
    for switch in switches['SAM3_NATIVE']:
        native_switches.setdefault((switch['gt_id'],switch['frame']),[]).append(switch)
    for switch in switches['Z4Q_FROZEN']:
        switches_by_frame.setdefault(switch['frame'],[]).append(switch)
    assert len(switches['Z4Q_FROZEN'])==read(p/'METRICS.json')['metrics']['Z4Q_FROZEN']['IDSW']
    switch_followup=[];switch_counts=Counter()
    baseline_by_frame={}
    for action in action_audit['actions']:
        if action['arm']=='Z4Q_FROZEN':baseline_by_frame.setdefault(action['frame'],[]).append(action)
    baseline_followup=[];baseline_counts=Counter();prior_original_sha=prior_depth_sha=None
    regression_frames={'feeding_000351_000555':{14},'fishsa_development_8400':{3902}}.get(name,set())
    for pr,transactions,depth in read_frames(name,output):
        f=pr['frame'];t=transactions['Z4Q_DEPTH_VETO'];trace=t['controller_trace']
        counts['frames']+=1;counts['objects']+=len(pr['variants']['SAM3_NATIVE'])
        checks=trace['depth_checks'];deleted=[x for x in checks if x['veto']]
        own={int(n):k for n,k in t['original_own_state_mapping'].items()}
        current={int(n):k for n,k in t['mapping'].items()}
        external=mapping(pr['variants']['Z4Q_FROZEN'])
        original_trace=t['original_own_state_trace']
        original_commits=decision_edges(original_trace,True)
        actual_commits=decision_edges(trace,True)
        orig_proposals=decision_edges(original_trace);actual_proposals=decision_edges(trace)
        own_publication=delta_mapping(own,current);external_publication=delta_mapping(external,current)
        counts['hook_edges']+=len(checks)
        counts['veto_frames']+=bool(deleted)
        counts['original_own_state_null_checks']+=not deleted
        counts['changed_frames']+=bool(external_publication)
        counts['same_prior_publication_changed_frames']+=bool(own_publication)
        counts['selected_commit_changes']+=original_commits!=actual_commits
        counts['selected_proposal_changes']+=orig_proposals!=actual_proposals
        counts['original_own_state_accepted_commits']+=len(original_commits)
        counts['actual_accepted_commits']+=len(actual_commits)
        if not deleted:
            assert t['engine_state_sha256']==t['original_own_state_sha256']
            assert current==own and t['full_state_null_checked']
        for check in checks:
            record_query_diagnostics(query_diagnostics,check)
            if global_diagnostics is not None:record_query_diagnostics(global_diagnostics,check)
            phase=check['phase'];phases[phase]['hook_edges']+=1
            eligible=check['original_eligible'];raw=check['conflict'];active=check['veto']
            legal=not check['terms']['failures'] and check['terms']['cost'] is not None if phase=='BIRTH_REFINE' else check['terms']['rejection'] is None
            assert eligible==legal and active==(eligible and raw and check['veto_enabled'] and not check['counterfactual_allowed'])
            for key,value in [('original_eligible_edges',eligible),('original_rejected_edges',not eligible),
                ('raw_conflicts',raw),('redundant_conflicts',raw and not eligible),('legal_edges_deleted',active)]:
                counts[key]+=bool(value);phases[phase][key]+=bool(value)
            reasons[check['reason']]+=1
            lookups[check['source_contract']['target_lookup']]+=1
            counts['reliable_current_query_edges']+=bool((check.get('current') or {}).get('usable'))
            counts['source_bound_wls_query_edges']+=bool(check.get('forecast') and check['forecast'].get('status')=='WLS_LINEAR_TIME')
            if check['reason'] not in first_nulls and not raw:
                first_nulls[check['reason']]=dict(frame=f,phase=phase,native_id=check['native_id'],canonical_id=check['canonical_id'],
                    target_lookup=check['source_contract']['target_lookup'],anchor=check['anchor'],
                    current_fact_id=(check.get('current') or {}).get('fact_id'),
                    target_sample_fact_ids=[x['fact_id'] for x in check['samples']])
            if raw:
                result=physical[edge_key(check)]
                assert result['actual_matrix_deletion']==active and result['original_eligible']==eligible
                counts['raw_conflict_'+result['physical']]+=1
                if active:counts['actual_deletion_'+result['physical']]+=1
            if not active:continue
            samples=check['samples'];forecast=check['forecast'];observed=check['current']
            assert eligible and raw and samples and forecast['status']=='WLS_LINEAR_TIME'
            assert all(s['frame']<f and s['time']<t['time'] for s in samples)
            assert all(s['version']==samples[-1]['version'] for s in samples)
            assert samples[-1]['anchor']==check['anchor']
            assert observed['frame']==f and observed['time']==t['time'] and observed['native']==check['native_id']
            expected=max(CFG['absolute_conflict_floor_mm'],CFG['conflict_scale_multiplier']*
                math.hypot(forecast['scale_mm'],observed['scale_mm']))
            assert math.isclose(check['threshold'],expected,rel_tol=0,abs_tol=1e-9)
            assert abs(observed['z_mm']-forecast['mu_mm'])>expected
            original_selected=any(x['phase']==phase and x['native_id']==check['native_id'] and x['canonical_id']==check['canonical_id'] for x in orig_proposals)
            original_accepted=any(x['phase']==phase and x['native_id']==check['native_id'] and x['canonical_id']==check['canonical_id'] for x in original_commits)
            counts['deleted_edge_original_selected_proposal']+=original_selected
            counts['deleted_edge_original_accepted_commit']+=original_accepted
            deletions.append(dict(frame=f,global_frame=pr['global_frame'],time=t['time'],phase=phase,
                native_id=check['native_id'],canonical_id=check['canonical_id'],
                actual_evidence_bank_anchor=check['anchor'],original_scoring_reference=result['original_scoring_reference'],
                anchor_references_differ=result['original_scoring_reference'] is not None and result['original_scoring_reference']!=check['anchor'],
                current=observed,samples=samples,forecast=forecast,residual_mm=check['residual_mm'],threshold_mm=check['threshold'],
                source_contract=check['source_contract'],original_cost=check['terms']['cost'],unchanged_dummy_cost=1.,
                original_selected_proposal=original_selected,original_accepted_commit=original_accepted,
                actual_accepted_commits=actual_commits,same_prior_publication_changes=own_publication,
                original_public_id=own[check['native_id']],actual_public_id=current[check['native_id']],
                actual_physical_reference_judgment=physical[edge_key(check)],
                trace_artifact=str(p/'TRANSACTIONS.jsonl.gz'),transaction_row_sha256=row_sha(t)))
        # Original wrong/correct/unscorable commits are followed individually,
        # rather than explained from the frequency of unrelated null candidates.
        prior_same=prior_original_sha==prior_depth_sha
        # CLEAR's switch.frame is the global frame passed to clear_step, not local q.
        # A same-frame accepted edge describes coverage, not a complete causal diagnosis.
        frozen_trace=transactions['Z4Q_FROZEN']['controller_trace']
        for switch in switches_by_frame.get(pr['global_frame'],[]):
            native,public=switch['native_id'],switch['public_id']
            assert external[native]==public
            accepted=[edge for edge in decision_edges(frozen_trace,True)
                if (edge['native_id'],edge['canonical_id'])==(native,public)]
            matching_native=native_switches.get((switch['gt_id'],pr['global_frame']),[])
            acceptance=('ACCEPTED_D1_OR_BIRTH_CURRENT_NATIVE_PUBLIC' if accepted else
                'NOT_ACCEPTED_AT_THIS_ROUND_TWO_ENTRANCES')
            native_presence=('NATIVE_SWITCH_FRAME_PRESENT' if matching_native else
                'NO_NATIVE_SWITCH_SAME_FRAME')
            related_checks=[check for check in checks if check['native_id']==native]
            switch_counts['original_switches']+=1;switch_counts[acceptance]+=1
            switch_counts[native_presence]+=1;switch_counts[acceptance+'|'+native_presence]+=1
            switch_followup.append(dict(frame=f,global_frame=pr['global_frame'],clear_switch=copy.deepcopy(switch),
                same_frame_inheritance_class=acceptance,current_native_public_accepted_edges=accepted,
                native_same_gt_global_frame_class=native_presence,native_same_gt_global_frame_switches=copy.deepcopy(matching_native),
                original_trace_event_kinds=[e.get('kind') for e in frozen_trace.get('events',[])],
                original_related_trace_events=[copy.deepcopy(e) for e in frozen_trace.get('events',[])
                    if native in (e.get('native_id'),e.get('incumbent_native'),e.get('keep_native'))],
                query_link_scope='SAME_PRIOR_FULL_ENGINE' if prior_same else 'CROSS_BRANCH_STATE_DIFFERENT',
                same_frame_current_native_queries=[dict(phase=c['phase'],native_id=c['native_id'],canonical_id=c['canonical_id'],
                    matches_current_published_public=c['canonical_id']==public,reason=c['reason'],
                    target_lookup=c['source_contract']['target_lookup'],original_eligible=c['original_eligible'],
                    raw_conflict=c['conflict'],actual_deletion=c['veto'],anchor=c['anchor']) for c in related_checks],
                query_phases=sorted({c['phase'] for c in related_checks}),
                query_null_reasons=dict(Counter(c['reason'] for c in related_checks if not c['conflict'])),
                coverage_boundary='No same-frame accepted inheritance only means no accepted commit at these two entrances; '
                    'it does not imply no query, no earlier alias effect, or no causal association.'))
        for action in baseline_by_frame.get(f,[]):
            event=action['event'];phase='BIRTH_REFINE' if event.get('phase')=='birth' else 'D1_DELAYED'
            native,public=event['native_id'],event['canonical_id']
            same_edges=[check for check in checks if (check['phase'],check['native_id'],check['canonical_id'])==(phase,native,public)]
            assert len(same_edges)<=1
            check=same_edges[0] if same_edges else None
            outcome=('NO_CORRESPONDING_QUERY_IN_NEW_BRANCH' if check is None else
                'ACTUAL_LEGAL_EDGE_DELETED' if check['veto'] else
                'RAW_CONFLICT_BUT_ORIGINAL_EDGE_ALREADY_REJECTED' if check['conflict'] and not check['original_eligible'] else check['reason'])
            extra=physical_from_scored_matches(references,f,native,check['anchor']) if check else None
            own_actual=[a for a in action_audit['actions'] if a['arm']=='Z4Q_DEPTH_VETO' and a['frame']==f
                and a['event']['native_id']==native and a['event']['canonical_id']==public]
            baseline_counts[action['physical']]+=1
            baseline_counts[action['physical']+'|'+outcome]+=1
            baseline_counts['same_prior_links']+=prior_same
            baseline_counts['cross_branch_prior_state_different_links']+=not prior_same
            baseline_followup.append(dict(frame=f,global_frame=pr['global_frame'],phase=phase,native_id=native,canonical_id=public,
                original_reference=action['actual_reference'],original_physical=action['physical'],original_event=event,
                link_scope='SAME_PRIOR_FULL_ENGINE' if prior_same else 'CROSS_BRANCH_STATE_DIFFERENT',
                prior_full_engine_hashes=dict(original=prior_original_sha,depth=prior_depth_sha),
                unvetoed_or_deleted_reason=outcome,query_exists=check is not None,
                query_reason=check['reason'] if check else None,target_lookup=check['source_contract']['target_lookup'] if check else None,
                query_original_eligible=check['original_eligible'] if check else None,raw_conflict=check['conflict'] if check else None,
                actual_deletion=check['veto'] if check else False,
                extra_bank_reference=check['anchor'] if check else None,
                original_scoring_anchor_differs_from_extra=bool(check and action['actual_reference']!=check['anchor']),
                extra_reference_physical_judgment=extra,
                extra_reference_judgment_not_transferred_from_original=True,
                query_fact_id=(check.get('current') or {}).get('fact_id') if check else None,
                forecast=check['forecast'] if check else None,
                query_quality=(check.get('current') or {}).get('quality') if check else None,
                query_target_sample_fact_ids=[sample['fact_id'] for sample in check['samples']] if check else [],
                query_numeric_diagnostics=query_numeric(check) if check else None,
                exact_target_fragment_preceding_break=target_fragment_break(check,fragment_breaks),
                depth_same_frame_named_edge_accepted=bool(own_actual),depth_same_frame_actions=own_actual,
                actual_depth_public_id=current.get(native),original_frozen_public_id=external.get(native)))
        prior_original_sha=transactions['Z4Q_FROZEN']['engine_state_sha256'];prior_depth_sha=t['engine_state_sha256']
        for classification in trace['source_observations'].values():
            record_fragment_break(classification,f,t['time'],last_source,pending_break,fragment_breaks,
                depth['extracts'].get(str(classification['native'])))
            counts['source_observations']+=1
            counts['source_clean_actual_bank_anchor']+=classification['observation_class']=='CLEAN_ACTUAL_BANK_ANCHOR'
            for reason in classification['reasons']:source_reasons[reason]+=1
        if own_publication or original_commits!=actual_commits:
            changes.append(dict(frame=f,global_frame=pr['global_frame'],actual_legal_deletions=len(deleted),
                same_prior_publication_changes=own_publication,external_original_publication_changes=external_publication,
                original_own_state_commits=original_commits,actual_commits=actual_commits))
        if f in regression_frames:
            frames[f]=dict(frame=f,global_frame=pr['global_frame'],variants=pr['variants'],
                original_frozen_actions=decision_edges(transactions['Z4Q_FROZEN']['controller_trace'],True),
                actual_depth_actions=actual_commits,depth_checks=checks,
                current_reference_matches=references[str(f)])
    for key,value in summary['counts'].items():assert counts[key]==value,(name,key,counts[key],value)
    assert counts['frames']==summary['frames'] and counts['objects']==summary['objects']
    assert len(switch_followup)==len(switches['Z4Q_FROZEN'])
    return dict(counts=dict(counts),reason_counts=dict(reasons),target_lookup_counts=dict(lookups),
        source_reason_counts=dict(source_reasons),phase_counts={k:dict(v) for k,v in phases.items()},
        actual_deletions=deletions,first_null_examples=first_nulls,same_prior_decision_changes=changes,
        regression_frames=frames,original_accepted_action_followup=baseline_followup,
        original_accepted_action_followup_counts=dict(baseline_counts),
        original_switch_followup=switch_followup,original_switch_followup_counts=dict(switch_counts),
        query_forecast_diagnostics=finish_query_diagnostics(query_diagnostics),
        switch_frame_semantics='SWITCHES.frame is global_frame; native comparison uses gt_id plus global_frame, not public ID.',
        cross_branch_full_hash_includes_original_counters=True,
        independent_physical_audit=artifact(p/'VETO_AUDIT.json'))


def cf_analysis(selection, seal):
    if 'edge' not in selection:
        assert not seal['counterfactual']
        return dict(status='NO_REMOVABLE_ORIGINAL_LEGAL_CONFLICT_NO_COUNTERFACTUAL',thresholds_not_relaxed=True)
    name=selection['segment'];key=tuple(selection['allow_edge']);q=key[0]
    comparisons=[];allowed=[];veto_replay=0;first_change=None
    all_metrics=read(RUN/'METRICS.json')['counterfactual']
    counts=Counter();timeline=[]
    for fm,allow,veto in zip(read_frames(name),read_frames(name,HERE/'counter_allow'),read_frames(name,HERE/'counter_veto'),strict=True):
        fp,ft,fd=fm;ap,at,ad=allow;vp,vt,vd=veto;f=fp['frame'];counts['frames']+=1
        assert f==ap['frame']==vp['frame'] and fp['variants']==vp['variants']
        for field in ('engine_state_sha256','evidence_state_sha256','source_row_sha256','depth_packet_sha256'):
            assert ft['Z4Q_DEPTH_VETO'][field]==vt['Z4Q_DEPTH_VETO'][field]
            if f<q:assert at['Z4Q_DEPTH_VETO'][field]==vt['Z4Q_DEPTH_VETO'][field]
        veto_replay+=1
        a=at['Z4Q_DEPTH_VETO'];v=vt['Z4Q_DEPTH_VETO']
        amap=mapping(ap['variants']['Z4Q_DEPTH_VETO']);vmap=mapping(vp['variants']['Z4Q_DEPTH_VETO'])
        if f<q:assert ap['variants']==vp['variants']
        changes=delta_mapping(amap,vmap)
        counts['changed_publication_frames']+=bool(changes)
        counts['changed_engine_state_frames']+=a['engine_state_sha256']!=v['engine_state_sha256']
        ac=decision_edges(a['controller_trace'],True);vc=decision_edges(v['controller_trace'],True)
        counts['changed_commit_frames']+=ac!=vc
        for check in a['controller_trace']['depth_checks']:
            if not check['counterfactual_allowed']:continue
            assert edge_key(check)==key and check['conflict'] and check['original_eligible'] and not check['veto']
            allowed.append(copy.deepcopy(check))
        if changes or ac!=vc:
            row=dict(frame=f,global_frame=fp['global_frame'],publication_changes=changes,allow_commits=ac,veto_commits=vc)
            comparisons.append(row)
            if first_change is None:first_change=row
        if abs(f-q)<=12:
            timeline.append(dict(frame=f,global_frame=fp['global_frame'],
                allow_public=amap.get(key[2]),veto_public=vmap.get(key[2]),
                observed_depth=(ad['extracts'].get(str(key[2])) or {}).get('z_mm'),
                observed_depth_usable=(ad['extracts'].get(str(key[2])) or {}).get('usable',False)))
    assert len(allowed)==1 and counts['frames']==SEGMENTS[name][1]-SEGMENTS[name][0]+1
    metrics={mode:all_metrics[mode]['metrics']['Z4Q_DEPTH_VETO'] for mode in ('counter_allow','counter_veto')}
    return dict(status='PASS_FIXED_SINGLE_EDGE_ACTUAL_STATE_COUNTERFACTUAL',segment=name,selected_edge=selection,
        exactly_one_allow=allowed,original_reference_is_actual_selected_bank=True,
        formal_veto_replay_exact_frames=veto_replay,identical_before_selected_frame=True,
        post_choice_own_state_continued=True,counts=dict(counts),first_publication_or_commit_change=first_change,
        changes=comparisons,timeline=timeline,metrics=metrics,
        veto_minus_allow={k:metrics['counter_veto'][k]-metrics['counter_allow'][k] for k in ('IDF1','HOTA','AssA','IDSW','FP','FN')})


def regression_cases(segments):
    cases={}
    for name,frame,label in [('feeding_000351_000555',14,'F364_ORIGINAL_ALREADY_AVOIDED_DS31_WRONG_ASSOCIATION'),
        ('fishsa_development_8400',3902,'F3902_ORIGINAL_BIRTH_RECOVERY')]:
        row=copy.deepcopy(segments[name]['regression_frames'][frame]);maps={arm:mapping(objects) for arm,objects in row['variants'].items()}
        row['actual_mapping_by_native']=maps
        row['no_forced_trigger_or_GT_candidate_choice']=True
        if frame==14:
            row['original_keeps_both_current_sources']=all(maps['Z4Q_FROZEN'].get(n)==n for n in (30,66))
            row['depth_matches_original_at_case']=maps['Z4Q_DEPTH_VETO']==maps['Z4Q_FROZEN']
            row['not_counted_as_new_repair']=row['original_keeps_both_current_sources'] and row['depth_matches_original_at_case']
        else:
            prior=[e for e in row['original_frozen_actions'] if e['phase']=='BIRTH_REFINE' and e['native_id']==7 and e['canonical_id']==0]
            current=[e for e in row['actual_depth_actions'] if e['phase']=='BIRTH_REFINE' and e['native_id']==7 and e['canonical_id']==0]
            row['original_named_restore_present']=bool(prior)
            row['same_frame_named_restore_retained']=bool(prior and current and maps['Z4Q_DEPTH_VETO'].get(7)==0)
            row['actual_reference_match_or_change']=dict(original=prior,depth=current)
        cases[label]=row
    return cases


def draw_figures(result, metrics):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    plt.rcParams.update({'font.family':'DejaVu Sans','svg.fonttype':'none'})
    target=HERE/'figures';target.mkdir(exist_ok=True)
    inspection=HERE/'private'/'inspection';inspection.mkdir(parents=True,exist_ok=True)
    names=['Feeding pooled 1471','fishsa_development_8400','fishsa_validation_2888','L3','LW']
    labels=['Feeding 1471','FishSA 8400','FishSA 2888','L3 (weak)','LW (weak)']
    fig,axes=plt.subplots(1,3,figsize=(14,5),constrained_layout=True)
    for ax,field in zip(axes,('IDF1','HOTA','AssA')):
        values=[]
        for name in names:
            data=metrics['feeding_pooled']['metrics'] if name==names[0] else metrics['segments'][name]['metrics']
            values.append(data['Z4Q_DEPTH_VETO'][field]-data['Z4Q_FROZEN'][field])
        ax.barh(labels,values,color=['#237c70' if v>=0 else '#b45245' for v in values]);ax.axvline(0,color='black',lw=.8)
        ax.invert_yaxis();ax.set_xlabel('VETO minus original Z4Q (percentage points)');ax.set_title(field)
        for y,value in enumerate(values):ax.annotate(f'{value:+.4f}',(value,y),xytext=(4 if value>=0 else -4,0),
            textcoords='offset points',va='center',ha='left' if value>=0 else 'right',fontsize=9)
        extent=max(.15,max(map(abs,values),default=0)*1.45);ax.set_xlim(-extent,extent)
    fig.suptitle('DS32 complete same-source replay; L3/LW weak references; unchanged masks')
    path=target/'DS32_METRIC_DELTAS.svg';preview=inspection/'DS32_METRIC_DELTAS.png'
    assert not path.exists() and not preview.exists()
    fig.savefig(path,metadata={'Date':None});fig.savefig(preview,dpi=150);plt.close(fig)
    cf=result['counterfactual'];fig,axes=plt.subplots(1,2,figsize=(14,5),constrained_layout=True)
    if cf.get('exactly_one_allow'):
        check=cf['exactly_one_allow'][0];samples=check['samples'];forecast=check['forecast'];current=check['current']
        ax=axes[0];ax.plot([s['time'] for s in samples],[s['z_mm'] for s in samples],'o-',label='Actual reliable pre measurements')
        query=check['time'];pred=forecast['mu_mm'];threshold=check['threshold']
        ax.errorbar([query],[pred],yerr=[threshold],fmt='x',color='#66469a',label='Forecast + conflict proxy (not CI)',capsize=5)
        ax.scatter([query],[current['z_mm']],color='#b45245',label='Actual current exclusive-core measurement',zorder=5)
        ax.set_xlabel('Real recorded time (seconds)');ax.set_ylabel('Depth (mm)');ax.legend(fontsize=8)
        ax.set_title(f"{cf['segment']} / F{check['frame']} / n{check['native_id']} -> public{check['canonical_id']}")
        ax=axes[1];timeline=cf['timeline']
        for mode,color in [('allow','#6a53a3'),('veto','#237c70')]:
            x=[r['global_frame'] for r in timeline if r[mode+'_public'] is not None]
            y=[r[mode+'_public'] for r in timeline if r[mode+'_public'] is not None]
            ax.step(x,y,where='post',label=mode.upper()+' actual published ID',color=color)
        ax.axvline(cf['selected_edge']['global_frame'],color='black',ls='--',lw=.8)
        ax.set_xlabel('Global frame; later frames are postseal diagnostics');ax.set_ylabel('Actual public ID (categorical integer)')
        ax.legend(fontsize=8);ax.set_title('Single allowed edge; all later state evolves independently')
    else:
        values=[result['totals'].get(k,0) for k in ('hook_edges','original_eligible_edges','raw_conflicts','legal_edges_deleted','selected_commit_changes')]
        axes[0].barh(['Hook edges','Original eligible','Reliable conflicts','Legal deletions','Commit-change frames'],values,color='#237c70')
        axes[0].invert_yaxis();axes[0].set_xlabel('Counts with different denominators');axes[0].set_title('No actual removable conflict: no counterfactual invented')
        reasons=Counter()
        for segment in result['segments'].values():reasons.update(segment['reason_counts'])
        common=reasons.most_common(6);axes[1].barh([k for k,v in common],[v for k,v in common],color='#7b8798')
        axes[1].invert_yaxis();axes[1].set_xlabel('Candidate-query count');axes[1].set_title('Retained original-edge reasons')
    fig.suptitle('Only public numeric facts; no RGB, mask or GT raster; no forecast is an observation')
    path2=target/'DS32_CANDIDATE_AND_PUBLICATION.svg';preview2=inspection/'DS32_CANDIDATE_AND_PUBLICATION.png'
    assert not path2.exists() and not preview2.exists()
    fig.savefig(path2,metadata={'Date':None});fig.savefig(preview2,dpi=150);plt.close(fig)
    figures=[dict(artifact(p),public_numeric_only=True,private_pixels=False,GT_raster=False) for p in (path,path2)]
    previews=[dict(artifact(p),source_svg=artifact(svg),numeric_only=True,private_delivery_only=True,
        git_publish=False) for p,svg in ((preview,path),(preview2,path2))]
    return figures,previews


def main():
    import score
    seal=score.verify_all()
    metrics=read(RUN/'METRICS.json');assert metrics['status']=='SCORED_AFTER_ALL_FORMAL_AND_COUNTERFACTUAL_SEALS'
    for name in SEGMENTS:
        for filename in ('METRICS.json','ACTION_AUDIT.json','VETO_AUDIT.json','REFERENCE_MATCHES.json','SWITCHES.json'):
            assert (RUN/name/'public'/filename).is_file()
    frozen=read(HERE/'RUNTIME_FREEZE.json')
    assert str(Path(__file__).resolve()) not in frozen['code'],'Postseal helper unexpectedly affected prediction'
    for path,h in frozen['code'].items():assert sha(path)==h,path
    query_diagnostics={}
    segments={name:summarize(name,global_diagnostics=query_diagnostics) for name in SEGMENTS};totals=Counter()
    for segment in segments.values():totals.update(segment['counts'])
    assert totals['frames']==20098 and totals['objects']==181842
    selection=read(HERE/'COUNTERFACTUAL_SELECTION.json')
    counter=cf_analysis(selection,seal)
    pins=[artifact(RUN/'ALL_PREDICTIONS_SEALED.json'),artifact(RUN/'METRICS.json'),artifact(HERE/'RUNTIME_FREEZE.json'),artifact(HERE/'COUNTERFACTUAL_SELECTION.json'),artifact(__file__)]
    for name in SEGMENTS:
        pins.extend(artifact(RUN/name/'public'/file) for file in ('PREDICTIONS_SEALED.json','RUN_SUMMARY.json','ACTION_AUDIT.json','VETO_AUDIT.json','SWITCHES.json','SWITCH_CHANGES.json'))
    switch_totals=Counter()
    for segment in segments.values():switch_totals.update(segment['original_switch_followup_counts'])
    result=dict(status='PASS_POSTSEAL_NUMERIC_MECHANISM_AUDIT',segments=segments,totals=dict(totals),counterfactual=counter,
        regression_cases=regression_cases(segments),artifacts_pins=pins,
        original_switch_coverage_totals=dict(switch_totals),
        query_forecast_diagnostics=finish_query_diagnostics(query_diagnostics),
        quality_boundary=dict(physical_depth_identity='UNKNOWN',close_depth_never_certifies_identity=True,
            scales_are_uncalibrated_proxies_not_confidence_intervals=True,producer_session_generation='UNMARKED_BATCH_SESSION_SWITCH_NOT_CERTIFIED; APPEARANCE_CONTINUITY_ONLY',
            L3_LW_weak_reference=True,all_data_previously_exposed=True,no_background_reward_or_native_lifecycle_replacement=True,
            no_direct_GT_file_or_private_pixel_access_by_this_helper=True),model_http=0,cost_usd=0)
    figures,previews=draw_figures(result,metrics)
    write_new(HERE/'ANALYSIS_POSTSEAL.json',result)
    write_new(HERE/'PUBLIC_NUMERIC_VISUALS.json',dict(status='PUBLIC_NUMERIC_ONLY',figures=figures,
        inspection_previews=previews,no_raw_private_pixels=True,no_GT_raster=True,postseal_helper=artifact(__file__)))
    print('POSTSEAL_ANALYSIS_PASS',json.dumps(result['totals']),flush=True)


if __name__=='__main__':main()
