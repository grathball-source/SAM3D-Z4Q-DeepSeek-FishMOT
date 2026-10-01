"""Postseal DS10 review of existing scores and events; no replay or label access."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import statistics

from common import HERE, RUN, SEGMENTS, ARMS, read, sha, artifact, write_new

EVENT_ARMS = ARMS[1:]
PAIR_ARMS = (('F9_RESTORED', 'D10_RAW'),
             ('F9_RESTORED', 'D10_RESTORED'),
             ('D10_RAW', 'D10_RESTORED'))


def mapping(value):
    return {str(int(n)): int(p) for n, p in (value or {}).items()}


def physical_key(value):
    return tuple(sorted((int(n), int(p)) for n, p in mapping(value).items()))


def outcome(value, expected):
    return ('UNKNOWN_NO_BANK_REFERENCE_BIJECTION' if not expected else
            'CORRECT' if mapping(value) == mapping(expected) else 'WRONG')


def finite_spread(values):
    values = sorted(float(x) for x in values if x is not None and math.isfinite(x))
    return dict(n=len(values), minimum=values[0] if values else None,
                median=statistics.median(values) if values else None,
                maximum=values[-1] if values else None)


def without_arm_key(value, field=None):
    """Remove only the arm slot of a version key; preserve all other state facts."""
    if isinstance(value, dict):
        return {k: without_arm_key(v, k) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        result = [without_arm_key(v) for v in value]
        if field in ('key', 'version_key') and len(result) == 5 and result[1] in ARMS:
            result[1] = '<ARM_SLOT_ONLY>'
        return result
    return value


def signature(value):
    encoded = json.dumps(without_arm_key(value), sort_keys=True,
                         separators=(',', ':'), allow_nan=False).encode()
    return hashlib.sha256(encoded).hexdigest()


def gate(run):
    """Bind every read numerical artifact to its completed prediction/score seal."""
    scoring = read(run / 'SCORING_SEALED.json')
    assert scoring['status'] == 'ALL_SEGMENTS_AND_EVENTS_SCORED'
    all_path = run / 'ALL_PREDICTIONS_SEALED.json'
    assert scoring['all_prediction_seal_sha256'] == sha(all_path)
    all_seals = read(all_path)
    assert all_seals['status'] == 'ALL_FOUR_BRANCHES_FOUR_SEGMENTS_SEALED'
    assert all_seals['frames'] == 1471 and tuple(all_seals['arms']) == ARMS
    access = read(run / 'ACCESS_SEALED.json')
    assert access['prediction_all_seal']['sha256'] == sha(all_path)
    names = ('METRICS.json', 'EVENT_AUDIT.json', 'SWITCH_LEDGER.json')
    for name in names:
        assert sha(run / name) == scoring['artifacts_sha256'][name], name
    files = {}
    for name in SEGMENTS:
        public = run / name / 'public'
        seal_path = public / 'PREDICTIONS_SEALED.json'
        assert sha(seal_path) == all_seals['seals'][name]
        seal = read(seal_path)
        assert seal['status'] == 'SEALED_AWAITING_INDEPENDENT_SCORING'
        assert tuple(seal['arms']) == ARMS
        files[name] = public / 'EVENTS.json'
        assert sha(files[name]) == seal['artifacts_sha256']['EVENTS.json']
    return files, dict(scoring=artifact(run / 'SCORING_SEALED.json'),
        all_predictions=artifact(all_path), access=artifact(run / 'ACCESS_SEALED.json'),
        numerical_inputs={name: artifact(run / name) for name in names},
        events={name: artifact(path) for name, path in files.items()})


def selected_fields(value, fields):
    return {field: value.get(field) for field in fields}


def candidate_summary(value):
    result = selected_fields(value, ('labels', 'mapping', 'log_prior', 'geometry_log_lr',
        'depth_log_lr', 'geometry_log_likelihood', 'depth_log_likelihood',
        'log_joint_density', 'log_score', 'posterior'))
    result['mapping'] = mapping(result['mapping'])
    result['pairs'] = []
    for pair in value['pairs']:
        result['pairs'].append(dict(role=pair['role'], source=pair['source'],
            associated=pair['associated'],
            geometry=selected_fields(pair['geometry'], ('used', 'raw_log_density',
                'background_log_density', 'mixture_log_density', 'log_lr')),
            depth=selected_fields(pair['depth'], ('used', 'raw_log_density',
                'background_log_density', 'mixture_log_density', 'log_lr',
                'observation_scale_mm', 'combined_scale_mm', 'measurement_fact_id',
                'assigned_depth_source', 'missing_model'))))
    return result


def difference(first, second):
    return {k: first[k] - second[k] for k in
            ('geometry_log_lr', 'depth_log_lr', 'log_prior', 'log_score')}


def geometry_summary(value):
    if not value['available']:
        return selected_fields(value, ('available', 'reason', 'samples'))
    covariance = value['inflated_covariance_px2']
    return dict(available=True, samples=value['samples'], mu_px=value['mu_px'],
        pre_fact_ids=[x['fact_id'] for x in value['pre_facts']],
        pre_frames=[x['frame'] for x in value['pre_facts']],
        mean_mode=value['mean_mode'], both_pre_velocity_available=value['both_pre_velocity_available'],
        actual_gap_seconds=value['actual_gap_seconds'],
        capped_mean_gap_seconds=value['capped_mean_gap_seconds'],
        real_pre_span_seconds=value['real_pre_span_seconds'],
        growth_factor=value['growth_factor'],
        residual_count=value['calibration']['residual_count'],
        covariance_method=value['calibration']['method'],
        inflated_axis_sd_px=[math.sqrt(covariance[i][i]) for i in (0, 1)],
        residual_norm_px=finite_spread(math.hypot(*x['residual_px'])
                                     for x in value['calibration']['residuals']))


def forecast_summary(value):
    result = selected_fields(value, ('status', 'samples', 'mu_mm', 'scale_mm',
        'slope_mm_s', 'mean_model', 'velocity_status', 'delta_seconds',
        'time_scale_seconds', 'sample_frames', 'sample_fact_ids', 'version_key',
        'cutoff_frame', 'source', 'public'))
    # Keep aggregate causal facts, not per-pixel depth arrays.
    if 'calibration' in value:
        result['calibration'] = value['calibration']
    legacy = value.get('legacy_reference')
    if legacy:
        result['legacy_reference'] = selected_fields(legacy, ('status', 'samples',
            'mu_mm', 'scale_mm', 'slope_mm_s', 'delta_seconds', 'time_scale_seconds'))
        for field, label in (('mu_mm', 'mean_mm'), ('scale_mm', 'scale_mm')):
            result[f'same_input_new_minus_legacy_{label}'] = (
                value[field] - legacy[field] if value.get(field) is not None
                and legacy.get(field) is not None else None)
    return result


def summarize_q(event, ref):
    detail, restore = event['numeric']['detail'], event['restore']
    baseline, expected = mapping(detail['baseline_mapping']), mapping(ref['expected_mapping'])
    first = mapping(ref['first_public_mapping'])
    baseline_result, first_result = outcome(baseline, expected), outcome(first, expected)
    staged = restore['status'] in ('COMMIT', 'RESOLVE_NO_ID_CHANGE')
    actual_change = first != baseline
    candidates = {label: candidate_summary(c) for label, c in detail['candidates'].items()}
    best, runner = detail['best'], detail['runner_up']
    expected_label = next((label for label, c in candidates.items()
                           if expected and c['mapping'] == expected), None)
    entry = {role: x['identity_reference'] for role, x in ref['pre_entry_reference'].items()}
    state = event['depth_frozen'] or {}
    background = detail['background'].get('depth')
    # DS9 background contains only a whole-frame mu/scale; retain its original facts.
    return dict(segment=ref['segment'], arm=ref['arm'], event=event['id'],
        local_q=event['q'], original_q=ref['original_q'],
        suspect=event['suspect_frame'], confirm=event['confirm_frame'], end=event['end'],
        selected_choice=event['numeric']['choice'], best=best, runner_up=runner,
        numerical_accepted=detail['accepted'], numerical_reason=detail['reason'],
        margin=detail['margin'], minimum_log_odds=detail['minimum_log_odds'],
        unique_physical_candidates=detail['unique_physical_candidates'],
        baseline_mapping=baseline, selected_numeric_mapping=mapping(detail['selected_mapping']),
        native_pair_mapping={source: int(source) for source in baseline},
        expected_mapping=expected, first_public_mapping=first,
        commit_status=restore['status'], stage_error=restore['stage_error'],
        decision_source=restore['decision_source'], staged=staged,
        actual_changed_against_lawful_preview=actual_change,
        true_changed_commit=bool(staged and actual_change),
        accepted_but_transaction_rejected=bool(detail['accepted'] and not staged),
        changes_against_lawful_preview=restore['changes'],
        changed_relative_to_previous=restore['changed_relative_to_previous'],
        baseline_reference=baseline_result, first_public_reference=first_result,
        native_pair_reference=outcome({source: int(source) for source in baseline}, expected),
        first_public_reference_transition=f'{baseline_result}_TO_{first_result}',
        pre_entry_reference=entry,
        pre_entry_already_wrong=any(x == 'DIFFERENT_FROM_ANCHOR' for x in entry.values()),
        pre_entry_unknown=any(x == 'UNKNOWN' for x in entry.values()),
        anchor_matches=ref.get('anchor_matches'), post_matches=ref.get('post_matches'),
        candidates=candidates,
        best_vs_h0=difference(candidates[best], candidates['H0']),
        best_vs_runner=difference(candidates[best], candidates[runner]) if runner else None,
        expected_candidate=expected_label,
        expected_vs_h0=difference(candidates[expected_label], candidates['H0']) if expected_label else None,
        geometry={role: geometry_summary(g) for role, g in detail['geometry_forecasts'].items()},
        depth_enabled=detail['depth_enabled'], depth_used_edges=detail['used_edges'],
        current_post_pair_usable=detail['post_pair_usable'],
        depth_forecasts={role: forecast_summary(p) for role, p in detail['depth_forecasts'].items()},
        depth_assignment=detail['depth_assignment'], depth_background=background,
        frozen_state_signatures={role: signature(f) for role, f in state.items()},
        frozen_state_roles={role: dict(source=f.get('source'), public=f.get('public'),
            version_key=f.get('key'), cutoff_frame=f.get('cutoff_frame'),
            sample_frames=[s['frame'] for s in f.get('samples', [])],
            sample_fact_ids=[s.get('fact_id') for s in f.get('samples', [])])
            for role, f in state.items()},
        geometry_pre_signature=signature(event.get('pre_geometry_history')),
        physical_surface_identity='UNKNOWN', physical_depth_accuracy_mm='UNKNOWN')


def compare_q(first, second):
    a = {physical_key(c['mapping']): c for c in first['candidates'].values()}
    b = {physical_key(c['mapping']): c for c in second['candidates'].values()}
    shared = sorted(a.keys() & b.keys())
    same_candidates = a.keys() == b.keys()
    same_geometry = same_candidates and all(a[k]['geometry_log_lr'] == b[k]['geometry_log_lr']
                                            for k in shared)
    same_frozen = first['frozen_state_signatures'] == second['frozen_state_signatures']
    same_baseline = first['baseline_mapping'] == second['baseline_mapping']
    same_geometry_history = first['geometry_pre_signature'] == second['geometry_pre_signature']
    same_post = first['native_pair_mapping'] == second['native_pair_mapping']
    same_q = first['local_q'] == second['local_q']
    return dict(segment=first['segment'], event=first['event'], original_q=first['original_q'],
        first_arm=first['arm'], second_arm=second['arm'], same_q=same_q,
        same_post_sources=same_post, same_lawful_baseline=same_baseline,
        same_physical_candidate_set=same_candidates, identical_geometry_scores=same_geometry,
        identical_pre_geometry_history_except_arm_slot=same_geometry_history,
        identical_frozen_depth_state_except_arm_slot=same_frozen,
        direct_same_state_depth_model_comparison=bool(same_q and same_post and same_baseline
            and same_candidates and same_geometry and same_geometry_history and same_frozen),
        state_or_measurement_cohort_confound=not same_frozen,
        source_background_first=first['depth_background'], source_background_second=second['depth_background'],
        forecast_first=first['depth_forecasts'], forecast_second=second['depth_forecasts'],
        shared_candidate_differences=[dict(mapping=dict(k),
            second_minus_first=difference(b[k], a[k]),
            pair_differences=[dict(source=p['source'], role=p['role'],
                old_role=q['role'], geometry_lr_delta=p['geometry']['log_lr']-q['geometry']['log_lr'],
                depth_lr_delta=p['depth']['log_lr']-q['depth']['log_lr'],
                depth_foreground_logdensity_old=q['depth']['raw_log_density'],
                depth_foreground_logdensity_new=p['depth']['raw_log_density'],
                source_background_logdensity_old=q['depth']['background_log_density'],
                source_background_logdensity_new=p['depth']['background_log_density'])
                for p in b[k]['pairs'] for q in a[k]['pairs'] if p['source'] == q['source']])
            for k in shared],
        first_numeric_selected=first['selected_numeric_mapping'],
        second_numeric_selected=second['selected_numeric_mapping'],
        first_public_mapping=first['first_public_mapping'],
        second_public_mapping=second['first_public_mapping'],
        first_commit_status=first['commit_status'], second_commit_status=second['commit_status'],
        first_transition=first['first_public_reference_transition'],
        second_transition=second['first_public_reference_transition'],
        numeric_mapping_changed=first['selected_numeric_mapping'] != second['selected_numeric_mapping'],
        actual_first_public_mapping_changed=first['first_public_mapping'] != second['first_public_mapping'],
        interpretation='Sealed arithmetic decomposition; combined mean/null change, not isolated causal performance.')


def switch_key(item, include_public=False):
    fields = ('segment', 'frame', 'gt_id', 'native_id')
    if include_public:
        fields += ('from_public_id', 'to_public_id')
    return tuple(item.get(k) for k in fields)


def switch_comparison(ledger, first, second):
    a, b = ledger['events'][first], ledger['events'][second]
    aa, bb = {switch_key(x): x for x in a}, {switch_key(x): x for x in b}
    assert len(aa) == len(a) and len(bb) == len(b)
    common = sorted(aa.keys() & bb.keys())
    return dict(first_arm=first, second_arm=second, first_count=len(a), second_count=len(b),
        physical_signature_definition=['segment', 'frame', 'gt_id', 'native_id'],
        removed_physical_switches=[aa[k] for k in sorted(aa.keys()-bb.keys())],
        added_physical_switches=[bb[k] for k in sorted(bb.keys()-aa.keys())],
        same_physical_switch_changed_public_transition=[dict(first=aa[k], second=bb[k])
            for k in common if switch_key(aa[k], True) != switch_key(bb[k], True)],
        common_physical_switch_count=len(common))


def summarize_arm(rows):
    geometry = [g for row in rows for g in row['geometry'].values() if g['available']]
    forecasts = [p for row in rows for p in row['depth_forecasts'].values()]
    return dict(q_events=len(rows), selected_choices=dict(Counter(x['selected_choice'] for x in rows)),
        numeric_reasons=dict(Counter(x['numerical_reason'] for x in rows)),
        transaction_statuses=dict(Counter(x['commit_status'] for x in rows)),
        actual_changed_commits=sum(x['true_changed_commit'] for x in rows),
        accepted_but_transaction_rejected=sum(x['accepted_but_transaction_rejected'] for x in rows),
        first_public_transitions=dict(Counter(x['first_public_reference_transition'] for x in rows)),
        native_pair_reference=dict(Counter(x['native_pair_reference'] for x in rows)),
        pre_entry_already_wrong=sum(x['pre_entry_already_wrong'] for x in rows),
        pre_entry_unknown=sum(x['pre_entry_unknown'] for x in rows),
        used_depth_edge_counts=dict(Counter(x['depth_used_edges'] for x in rows)),
        forecast_statuses=dict(Counter(x['status'] for x in forecasts)),
        background_methods=dict(Counter((x['depth_background'] or {}).get('method',
            'DS9_LEGACY_WHOLE_FRAME' if x['depth_background'] else 'NO_BACKGROUND') for x in rows)),
        forecast_scale_mm=finite_spread(x['scale_mm'] for x in forecasts),
        same_input_local_level_minus_legacy_mean_mm=finite_spread(
            x.get('same_input_new_minus_legacy_mean_mm') for x in forecasts),
        same_input_local_level_minus_legacy_scale_mm=finite_spread(
            x.get('same_input_new_minus_legacy_scale_mm') for x in forecasts),
        geometry_mean_modes=dict(Counter(x['mean_mode'] for x in geometry)),
        geometry_growth_factor=finite_spread(x['growth_factor'] for x in geometry),
        geometry_residual_count=finite_spread(x['residual_count'] for x in geometry))


def review(run=RUN):
    run = Path(run)
    files, provenance = gate(run)
    metrics, audit, ledger = [read(run / name) for name in
                             ('METRICS.json', 'EVENT_AUDIT.json', 'SWITCH_LEDGER.json')]
    assert metrics['status'] == 'SCORED_AFTER_ALL_PREDICTION_SEALS' and metrics['frames'] == 1471
    assert audit['status'] == 'POSTSEAL_ACTUAL_BANK_ANCHOR_REFERENCE'
    references = {(x['segment'], x['arm'], x['event']): x for x in audit['events']}
    q_rows, non_q, all_events = [], [], {}
    for segment, path in files.items():
        events = read(path)
        assert set(events) == set(EVENT_ARMS)
        for arm, arm_events in events.items():
            for event in arm_events:
                key = segment, arm, event['id']
                assert key not in all_events and key in references
                all_events[key] = event
                reference = references[key]
                if event['q'] is None:
                    non_q.append(dict(segment=segment, arm=arm, event=event['id'],
                        suspect=event['suspect_frame'], confirm=event['confirm_frame'],
                        end=event['end'], status=event['status'],
                        reference_outcome=reference['first_public_physical']))
                else:
                    q_rows.append(summarize_q(event, reference))
    assert set(all_events) == set(references)
    by_episode = defaultdict(dict)
    for row in q_rows:
        by_episode[row['segment'], row['event']][row['arm']] = row
    comparisons, unmatched = [], []
    for (segment, event), episode in by_episode.items():
        for first, second in PAIR_ARMS:
            if first in episode and second in episode:
                comparisons.append(compare_q(episode[first], episode[second]))
            else:
                unmatched.append(dict(segment=segment, event=event, first_arm=first,
                    second_arm=second, reason='AT_LEAST_ONE_ARM_WITHOUT_Q'))
    for arm in ARMS:
        assert len(ledger['events'][arm]) == metrics['pooled_metrics'][arm]['IDSW']
    native_switches = []
    for item in ledger['events']['SAM3_NATIVE']:
        local = item['local_frame']
        segment_events = [e for (s, a, _), e in all_events.items()
                          if s == item['segment'] and a == 'F9_RESTORED']
        q_same = [e for e in segment_events if e['q'] == local]
        q_post = [e for e in q_same if str(item['native_id']) in e['post_first_observations']]
        in_window = [e for e in segment_events if e['suspect_frame'] <= local <=
                     (e['end'] if e['end'] is not None else SEGMENTS[item['segment']][1]-SEGMENTS[item['segment']][0]+1)]
        category = ('EXACT_Q_POST_SOURCE' if q_post else 'EXACT_Q_OTHER_SOURCE' if q_same else
                    'INSIDE_EVENT_WINDOW_NO_Q_DECISION' if in_window else 'OUTSIDE_EVENT_WINDOWS')
        native_switches.append(dict(item, temporal_scope=category,
            q_events=[e['id'] for e in q_same], event_windows=[e['id'] for e in in_window]))
    summaries = {arm: summarize_arm([r for r in q_rows if r['arm'] == arm]) for arm in EVENT_ARMS}
    pooled = metrics['pooled_metrics']
    metric_deltas = {arm: {name: pooled[arm][name]-pooled['SAM3_NATIVE'][name]
        for name in ('IDF1', 'HOTA', 'AssA', 'IDSW')} for arm in EVENT_ARMS}
    return dict(status='POSTSEAL_DS10_ALL_Q_AND_SWITCH_REVIEW', input_provenance=provenance,
        coverage=dict(all_events=len(all_events), q_events=len(q_rows), no_q_events=len(non_q),
            unique_q_episodes=len(by_episode), q_counts={a: summaries[a]['q_events'] for a in EVENT_ARMS},
            expected_scope_q_episodes=19, all_scored_events_included=True,
            all_native_switches_included=True, no_best_case_selection=True),
        pooled_metrics=pooled, native_metric_deltas=metric_deltas,
        pooled_delta=metrics.get('pooled_delta'), changed_frames=metrics['changed_frames'],
        frozen_support_rule_met=metrics['frozen_support_rule_met'],
        score_support_layers=metrics.get('score_support_layers'), summaries=summaries,
        q_events=q_rows, non_q_events=non_q, arm_comparisons=comparisons,
        unmatched_q_comparisons=unmatched,
        switch_comparisons=[switch_comparison(ledger, a, b) for a, b in
            [('SAM3_NATIVE', arm) for arm in EVENT_ARMS]+list(PAIR_ARMS)],
        native_switch_temporal_scope=dict(Counter(x['temporal_scope'] for x in native_switches)),
        native_switches=native_switches,
        actual_changed_commits=[r for r in q_rows if r['true_changed_commit']],
        accepted_but_transaction_rejected=[r for r in q_rows if r['accepted_but_transaction_rejected']],
        depth_model_scope='Combined robust local-level mean/process plus current object-level KDE null; individual causal contributions unidentifiable in this four-arm experiment.',
        limitations=[
            'Primary target is improvement over same-source native; comparison with DS9 is diagnostic, not an advancement gate.',
            'All data are exposed development data; this is not independent validation.',
            'Bank-anchor/post RGB references do not certify physical depth surface identity or depth accuracy in mm.',
            'Candidate arithmetic and the same-input legacy reference are model diagnostics, not a new replay or performance counterfactual.',
            'Changed earlier transactions can alter later baseline/version/history; arm slot normalization retains all other state facts.',
            'Raw and restored branches can have different measurement cohorts; restored v2 upstream RGB/next-frame support is an offline scope.',
            'Object KDE is query-inclusive fitted contrast; component count and normalized weights do not make it a calibrated posterior.',
            'Diffusion and geometry residuals are consistency proxies; independence and null modeling remain assumptions.',
            'NO_ID_CHANGE, stage rejection, first publication and official CLEAR switch are separate quantities.',
            'No raw pixels, GT files, tracker replay, parameter search, threshold modification or new experiment is accessed here.'],
        next_experiment_started=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, default=RUN)
    parser.add_argument('--write-new', action='store_true')
    args = parser.parse_args()
    result = review(args.run)
    if args.write_new:
        write_new(HERE / 'POSTRUN_REVIEW.json', result)
    print(json.dumps(dict(status=result['status'], coverage=result['coverage'],
        native_metric_deltas=result['native_metric_deltas'], summaries=result['summaries']),
        ensure_ascii=False, allow_nan=False))


if __name__ == '__main__':
    main()
