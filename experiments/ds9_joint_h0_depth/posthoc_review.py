"""Read sealed DS9 event/score summaries; never replay, rescore, or access pixels."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import math
import statistics
from pathlib import Path
from common import HERE, RUN, SEGMENTS, ARMS, read, sha, artifact, write_new

EVENT_ARMS = ARMS[1:]


def spread(values):
    values = sorted(float(v) for v in values if v is not None and math.isfinite(v))
    if not values:
        return dict(n=0, minimum=None, median=None, maximum=None)
    return dict(n=len(values), minimum=values[0], median=statistics.median(values),
                maximum=values[-1], mean=statistics.mean(values))


def normalized_map(mapping):
    return {str(n): int(p) for n, p in (mapping or {}).items()}


def mapping_reference(mapping, expected):
    return ('UNKNOWN_NO_REFERENCE_BIJECTION' if not expected else
            'CORRECT' if normalized_map(mapping) == normalized_map(expected) else 'WRONG')


def gate(run):
    """Check public seal bindings before reading scores or event decisions."""
    scoring = read(run / 'SCORING_SEALED.json')
    assert scoring['status'] == 'ALL_SEGMENTS_AND_EVENTS_SCORED'
    all_path = run / 'ALL_PREDICTIONS_SEALED.json'
    assert scoring['all_prediction_seal_sha256'] == sha(all_path)
    all_seals = read(all_path)
    assert all_seals['status'] == 'ALL_SIX_BRANCHES_FOUR_SEGMENTS_SEALED'
    assert all_seals['frames'] == 1471 and tuple(all_seals['arms']) == ARMS
    access = read(run / 'ACCESS_SEALED.json')
    assert access['prediction_all_seal']['sha256'] == sha(all_path)
    for name in ('METRICS.json', 'EVENT_AUDIT.json'):
        assert sha(run / name) == scoring['artifacts_sha256'][name]
    event_files = {}
    for name in SEGMENTS:
        public = run / name / 'public'
        seal_path = public / 'PREDICTIONS_SEALED.json'
        assert sha(seal_path) == all_seals['seals'][name]
        seal = read(seal_path)
        assert seal['status'] == 'SEALED_AWAITING_INDEPENDENT_SCORING'
        assert tuple(seal['arms']) == ARMS
        event_files[name] = public / 'EVENTS.json'
        assert sha(event_files[name]) == seal['artifacts_sha256']['EVENTS.json']
    return event_files, dict(scoring=artifact(run / 'SCORING_SEALED.json'),
        all_predictions=artifact(all_path), access=artifact(run / 'ACCESS_SEALED.json'),
        metrics=artifact(run / 'METRICS.json'), event_audit=artifact(run / 'EVENT_AUDIT.json'),
        events={name: artifact(path) for name, path in event_files.items()})


def engineering_exception(run):
    """Describe the explicit append-only scoring exception, not a clean exact gate."""
    manifest_path = HERE / 'APPENDED_SCORE_PROVENANCE_SEALED.json'
    manifest = read(manifest_path)
    assert manifest['score_seal']['sha256'] == sha(run / 'SCORING_SEALED.json')
    for item in manifest['append_only_provenance']:
        path = Path(item['path'])
        assert path.stat().st_size == item['bytes'] and sha(path) == item['sha256']
    audit = read(HERE / 'SOURCE_FLOAT_AUDIT.json')
    frozen = read(HERE / 'FLOAT_SCORE_ADAPTER_FROZEN.json')
    accepted = read(HERE / 'FLOAT_SCORE_ADAPTER_ACCEPTANCE.json')
    assert audit['actual_measurement_facts_exact'] and audit['material_difference_count'] == 0
    assert accepted['count'] == audit['difference_count']
    assert not frozen['scientific_thresholds_changed'] and not frozen['predictions_or_sources_changed']
    return dict(status=accepted['status'], provenance=artifact(manifest_path),
        original_exact_metadata_equality_gate_passed=False,
        original_failure_log=frozen['original_failed_execution'],
        source_objects=audit['source_objects'], metadata_difference_count=audit['difference_count'],
        difference_fields=audit['difference_fields'], max_float32_ulp_distance=audit['max_float32_ulp_distance'],
        max_absolute_metadata_difference_px=audit['max_absolute_metadata_difference_px'],
        actual_measurement_facts_exact=audit['actual_measurement_facts_exact'],
        exact_fact_scope=audit['exact_scope'], operative_thresholds_exact=accepted['all_operative_thresholds_exact'],
        adapter_frozen_before_gt=frozen['status'], allowed_exception=frozen['allowed'],
        scientific_thresholds_changed=False, predictions_or_sources_changed=False,
        original_decision_and_scoring_code_changed=False,
        runtime_cause='UNKNOWN', serialized_roi_bitmap_bitwise_equivalence='NOT_CHECKED',
        limitations=audit['limitations'])


def contribution(first, second):
    return {key: first[key] - second[key] for key in
            ('geometry_log_lr', 'depth_log_lr', 'log_prior', 'log_score')}


def geometry_limits(forecast):
    if not forecast['available']:
        return dict(available=False, reason=forecast['reason'], samples=forecast['samples'])
    residuals = forecast['calibration']['residuals']
    norms = [math.hypot(*r['residual_px']) for r in residuals]
    shape = forecast['shape_px2']
    determinant = shape[0][0] * shape[1][1] - shape[0][1] * shape[1][0]
    covariance = forecast['inflated_covariance_px2']
    return dict(available=True, samples=forecast['samples'],
        pre_fact_ids=[x['fact_id'] for x in forecast['pre_facts']],
        pre_frames=[x['frame'] for x in forecast['pre_facts']],
        mean_mode=forecast['mean_mode'], both_pre_velocity_available=forecast['both_pre_velocity_available'],
        post_velocity_status=forecast['post_velocity_status'],
        actual_gap_seconds=forecast['actual_gap_seconds'],
        capped_mean_gap_seconds=forecast['capped_mean_gap_seconds'],
        real_pre_span_seconds=forecast['real_pre_span_seconds'],
        time_scale_seconds=forecast['time_scale_seconds'], growth_factor=forecast['growth_factor'],
        residual_count=forecast['calibration']['residual_count'],
        covariance_method=forecast['calibration']['method'], residual_norm_px=spread(norms),
        inflated_axis_sd_px=[math.sqrt(covariance[i][i]) for i in (0, 1)],
        shape_determinant_px4=determinant,
        normalization_logdet_component=-.5 * math.log(determinant),
        calibrated_physical_accuracy=False)


def candidate_summary(candidate):
    keys = ('labels', 'mapping', 'log_prior', 'geometry_log_lr', 'depth_log_lr',
            'geometry_log_likelihood', 'depth_log_likelihood', 'log_joint_density', 'log_score', 'posterior')
    result = {key: candidate[key] for key in keys}
    result['pairs'] = []
    for pair in candidate['pairs']:
        result['pairs'].append(dict(role=pair['role'], source=pair['source'], associated=pair['associated'],
            geometry={k: pair['geometry'].get(k) for k in
                ('used', 'raw_log_density', 'background_log_density', 'mixture_log_density', 'log_lr')},
            depth={k: pair['depth'].get(k) for k in
                ('used', 'raw_log_density', 'background_log_density', 'mixture_log_density', 'log_lr',
                 'measurement_fact_id', 'assigned_depth_source', 'observation_scale_mm', 'combined_scale_mm', 'missing_model')}))
    return result


def summarize_q(event, reference):
    detail = event['numeric']['detail']
    restore = event['restore']
    expected = reference['expected_mapping']
    baseline = normalized_map(detail['baseline_mapping'])
    first = normalized_map(reference['first_public_mapping'])
    baseline_ref = mapping_reference(baseline, expected)
    first_ref = mapping_reference(first, expected)
    changed = first != baseline
    staged = not restore['status'].startswith('LOCAL_FALLBACK')
    if baseline_ref.startswith('UNKNOWN'):
        transition = 'UNKNOWN_NO_REFERENCE_BIJECTION'
    elif baseline_ref == first_ref:
        transition = f'{baseline_ref}_TO_{first_ref}'
    else:
        transition = f'{baseline_ref}_TO_{first_ref}'
    entry = {r: x['identity_reference'] for r, x in reference['pre_entry_reference'].items()}
    candidates = detail['candidates']
    best = detail['best']
    runner = detail['runner_up']
    return dict(segment=reference['segment'], arm=reference['arm'], event=event['id'],
        local_q=event['q'], original_q=reference['original_q'],
        selected_choice=event['numeric']['choice'], best_unique_hypothesis=best,
        accepted=detail['accepted'], reason=detail['reason'],
        runner_up=runner, margin=detail['margin'], minimum_log_odds=detail['minimum_log_odds'],
        unique_physical_candidates=detail['unique_physical_candidates'],
        baseline_mapping=baseline, selected_numeric_mapping=normalized_map(detail['selected_mapping']),
        expected_mapping=normalized_map(expected), first_public_mapping=first,
        numerical_acceptance_is_actual_stage=bool(detail['accepted'] and staged),
        commit_status=restore['status'], stage_error=restore['stage_error'],
        decision_source=restore['decision_source'], staged=staged,
        actual_changed_against_lawful_preview=changed,
        changes_against_lawful_preview=restore['changes'],
        changed_relative_to_previous=restore['changed_relative_to_previous'],
        baseline_reference=baseline_ref, first_public_reference=first_ref,
        first_public_reference_transition=transition,
        pre_entry_reference=entry,
        pre_entry_already_different_from_bank_anchor=any(x == 'DIFFERENT_FROM_ANCHOR' for x in entry.values()),
        pre_entry_reference_unknown=any(x == 'UNKNOWN' for x in entry.values()),
        first_public_interpretation='RGB identity correspondence at actual bank anchors; not depth-surface ownership or a new metric',
        best_vs_h0_contribution=contribution(candidates[best], candidates['H0']),
        best_vs_runner_contribution=contribution(candidates[best], candidates[runner]) if runner else None,
        candidates={label: candidate_summary(c) for label, c in candidates.items()},
        geometry_limits={r: geometry_limits(g) for r, g in detail['geometry_forecasts'].items()},
        depth_enabled=detail['depth_enabled'], depth_used_edges=detail['used_edges'],
        current_post_depth_pair_usable=detail['post_pair_usable'],
        depth_forecasts={r: {key: p.get(key) for key in
            ('status', 'samples', 'mu_mm', 'scale_mm', 'delta_seconds', 'time_scale_seconds',
             'sample_frames', 'sample_fact_ids', 'version_key', 'source', 'public')}
            for r, p in detail['depth_forecasts'].items()},
        depth_assignment=detail['depth_assignment'],
        physical_surface_identity='UNKNOWN', physical_depth_accuracy_mm='UNKNOWN')


def compare_q(a, b):
    common_q = a['local_q'] == b['local_q']
    source_set_same = set(a['baseline_mapping']) == set(b['baseline_mapping'])
    a_physical = {tuple(sorted(c['mapping'].items())): c for c in a['candidates'].values()}
    b_physical = {tuple(sorted(c['mapping'].items())): c for c in b['candidates'].values()}
    same_physical_candidates = a_physical.keys() == b_physical.keys()
    same_geometry = (same_physical_candidates and all(
        a_physical[key]['geometry_log_lr'] == b_physical[key]['geometry_log_lr'] for key in a_physical))
    same_baseline = a['baseline_mapping'] == b['baseline_mapping']
    return dict(first_arm=a['arm'], second_arm=b['arm'], segment=a['segment'], event=a['event'],
        original_q=a['original_q'], same_q=common_q, same_post_sources=source_set_same,
        same_lawful_baseline=same_baseline, same_physical_candidate_set=same_physical_candidates,
        identical_geometry_scores=same_geometry,
        same_numeric_selected_mapping=a['selected_numeric_mapping'] == b['selected_numeric_mapping'],
        same_first_public_mapping=a['first_public_mapping'] == b['first_public_mapping'],
        first_selected=a['selected_choice'], second_selected=b['selected_choice'],
        first_reference=a['first_public_reference'], second_reference=b['first_public_reference'],
        first_transition=a['first_public_reference_transition'], second_transition=b['first_public_reference_transition'],
        direct_same_state_association_comparison=bool(common_q and source_set_same and same_baseline and same_geometry),
        state_path_confound_if_false=True)


def review(run=RUN):
    run = Path(run)
    files, provenance = gate(run)
    metrics, audit = read(run / 'METRICS.json'), read(run / 'EVENT_AUDIT.json')
    assert metrics['status'] == 'SCORED_AFTER_ALL_PREDICTION_SEALS'
    assert audit['status'] == 'POSTSEAL_ACTUAL_BANK_ANCHOR_REFERENCE'
    assert metrics['frames'] == 1471
    reference = {(x['segment'], x['arm'], x['event']): x for x in audit['events']}
    all_events, q_rows, non_q = {}, [], []
    for segment, path in files.items():
        data = read(path)
        assert set(data) == set(EVENT_ARMS)
        for arm, events in data.items():
            for event in events:
                key = (segment, arm, event['id'])
                assert key not in all_events and key in reference
                all_events[key] = event
                ref = reference[key]
                if event['q'] is None:
                    non_q.append(dict(segment=segment, arm=arm, event=event['id'],
                        status=event['status'], suspect=event['suspect_frame'], confirm=event['confirm_frame'],
                        reference_outcome=ref['first_public_physical']))
                else:
                    q_rows.append(summarize_q(event, ref))
    assert set(all_events) == set(reference)
    by_episode = defaultdict(dict)
    for row in q_rows:
        by_episode[(row['segment'], row['event'])][row['arm']] = row
    pairs = (('J1_RAW_DEPTH','J0_GEOMETRY'), ('J2_RESTORED_DEPTH','J0_GEOMETRY'),
             ('J2_RESTORED_DEPTH','J1_RAW_DEPTH'), ('J2_RESTORED_DEPTH','J2_DEPTH_ZERO'),
             ('J2_RESTORED_DEPTH','J2_DEPTH_PERMUTE'), ('J2_DEPTH_ZERO','J0_GEOMETRY'))
    comparisons, missing_pairs = [], []
    for (segment,event), episode in by_episode.items():
        for first,second in pairs:
            if first in episode and second in episode:
                comparisons.append(compare_q(episode[first],episode[second]))
            else:
                missing_pairs.append(dict(segment=segment,event=event,first_arm=first,second_arm=second,
                                          reason='NO_Q_FOR_AT_LEAST_ONE_ARM'))
    summaries = {}
    for arm in EVENT_ARMS:
        selected = [r for r in q_rows if r['arm'] == arm]
        geometry = [g for r in selected for g in r['geometry_limits'].values() if g['available']]
        summaries[arm] = dict(all_events=sum(k[1] == arm for k in all_events), q_events=len(selected),
            no_q_events=sum(r['arm'] == arm for r in non_q),
            selected_choices=dict(Counter(r['selected_choice'] for r in selected)),
            numerical_reasons=dict(Counter(r['reason'] for r in selected)),
            commit_statuses=dict(Counter(r['commit_status'] for r in selected)),
            actual_first_public_changes=sum(r['actual_changed_against_lawful_preview'] for r in selected),
            accepted_but_not_staged=sum(r['accepted'] and not r['staged'] for r in selected),
            first_public_reference_transitions=dict(Counter(r['first_public_reference_transition'] for r in selected)),
            pre_entry_already_different=sum(r['pre_entry_already_different_from_bank_anchor'] for r in selected),
            pre_entry_unknown=sum(r['pre_entry_reference_unknown'] for r in selected),
            depth_used_edge_counts=dict(Counter(r['depth_used_edges'] for r in selected)),
            depth_forecast_statuses=dict(Counter(p['status'] for r in selected for p in r['depth_forecasts'].values())),
            geometry_mean_modes=dict(Counter(g['mean_mode'] for g in geometry)),
            geometry_covariance_methods=dict(Counter(g['covariance_method'] for g in geometry)),
            geometry_gap_seconds=spread(g['actual_gap_seconds'] for g in geometry),
            geometry_growth_factor=spread(g['growth_factor'] for g in geometry),
            geometry_residual_count=spread(g['residual_count'] for g in geometry),
            geometry_inflated_axis_sd_px=spread(v for g in geometry for v in g['inflated_axis_sd_px']),
            selected_candidate_depth_log_lr=spread(r['candidates'][r['selected_choice']]['depth_log_lr'] for r in selected),
            best_vs_runner_depth_contribution=spread(r['best_vs_runner_contribution']['depth_log_lr']
                for r in selected if r['best_vs_runner_contribution']))
    pooled = metrics['pooled_metrics']
    depth_output_equals_geometry = {arm: sum(segment[f'{arm}_vs_J0_GEOMETRY']
        for segment in metrics['changed_frames'].values()) == 0 for arm in ('J1_RAW_DEPTH','J2_RESTORED_DEPTH')}
    actual_changes = [r for r in q_rows if r['actual_changed_against_lawful_preview']]
    findings = dict(primary_rule_met=metrics['frozen_support_rule_met'],
        idf1_real_depth_equals_native=all(pooled[a]['IDF1'] == pooled['SAM3_NATIVE']['IDF1']
            for a in ('J1_RAW_DEPTH','J2_RESTORED_DEPTH')),
        real_depth_output_equals_geometry=depth_output_equals_geometry,
        real_depth_increment_vs_geometry_or_zero='NOT_OBSERVED',
        all_actual_first_public_changes=[dict(arm=r['arm'],original_q=r['original_q'],
            changed_edges=r['changes_against_lawful_preview'],
            transition=r['first_public_reference_transition'],pre_entry_reference=r['pre_entry_reference'])
            for r in actual_changes],
        accepted_without_actual_stage=[dict(arm=r['arm'],original_q=r['original_q'],
            margin=r['margin'],stage_error=r['stage_error'],reference=r['first_public_reference'])
            for r in q_rows if r['accepted'] and not r['staged']],
        permuted_actual_reference_harms=[r['original_q'] for r in actual_changes if
            r['arm']=='J2_DEPTH_PERMUTE' and r['first_public_reference_transition']=='CORRECT_TO_WRONG'],
        permutation_interpretation='Wrong assigned depth can cause wrong publication; this does not establish necessity or an actual benefit of correctly assigned depth.')
    return dict(status='POSTSEAL_ASSOCIATION_ALL_EVENTS_REVIEW', input_provenance=provenance,
        coverage=dict(all_events=len(all_events), q_events=len(q_rows), no_q_events=len(non_q),
                      all_scored_events_included=True, no_best_case_selection=True),
        pooled_metrics=metrics['pooled_metrics'], pooled_delta=metrics['pooled_delta'],
        changed_frames=metrics['changed_frames'], frozen_support_rule_met=metrics['frozen_support_rule_met'],
        score_support_layers=metrics['score_support_layers'], summaries=summaries,
        observed_findings=findings, engineering_scoring_exception=engineering_exception(run),
        q_events=q_rows, non_q_events=non_q, arm_comparisons=comparisons, missing_arm_pairs=missing_pairs,
        limitations=[
            'All 1471 frames are exposed development data; score gains are not independent validation.',
            'First-public reference is RGB polygon identity at actual bank anchors, not physical depth ownership or mm accuracy.',
            'Different pre-entry RGB reference is separated from new first-public errors; unknown references remain UNKNOWN.',
            'Candidate contribution differences are arithmetic decomposition of sealed scores, not new replay or tuned counterfactual performance.',
            'Different lawful baseline or geometry scores can reflect prior committed state; such arm contrasts are not a same-state depth intervention.',
            'Past residual covariance is prediction-consistency proxy; t posterior and geometry-depth independence are uncalibrated assumptions.',
            'Restored native v2 uses upstream RGB/next-frame support; restored evidence is offline, raw evidence remains causal.',
            'No raw depth/RGB/GT raster, future post, tracker replay, new scoring, or parameter changes are read or executed here.'],
        next_experiment_started=False)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',type=Path,default=RUN)
    parser.add_argument('--write-new',action='store_true')
    args=parser.parse_args()
    result=review(args.run)
    if args.write_new:
        write_new(HERE/'ASSOCIATION_POSTRUN.json',result)
    print(__import__('json').dumps(dict(status=result['status'],coverage=result['coverage'],
        support=result['frozen_support_rule_met'],summaries=result['summaries']),ensure_ascii=False))


if __name__=='__main__':main()
