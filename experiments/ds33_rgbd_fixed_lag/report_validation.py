"""Late report review: bind public sealed facts; do not open reference pixels."""
from common import *
from collections import Counter
from datetime import datetime, timezone
from statistics import median
from verify_inputs import verify_all


def report_tables(text):
    result, block = {}, []
    for line in text.splitlines() + ['']:
        if line.startswith('| '):
            block.append([value.strip() for value in line.strip().strip('|').split('|')])
        elif block:
            assert len(block) >= 2 and all(set(value) <= {'-', ':'} for value in block[1])
            result.setdefault(tuple(block[0]), []).extend(block[2:])
            block = []
    return result


def assert_table(tables, header, expected):
    actual = tables[tuple(header)]
    assert len(actual) == len(expected) and actual == expected, header


def main():
    verify_all()
    report_path = HERE / 'FINAL_REVIEW.md'
    report_pin = artifact(report_path)
    text = report_path.read_text(encoding='utf-8')
    tables = report_tables(text)
    score = read(RUN / 'METRICS.json')
    results = read(HERE / 'RESULTS.json')
    state = read(HERE / 'STATE_PUBLICATION_REVIEW.json')
    diag = read(HERE / 'EVIDENCE_DIAGNOSTICS.json')
    checks = read(HERE / 'CHECKS_FINAL.json')
    acceptance = read(HERE / 'REAL_ACCEPTANCE.json')
    provenance = read(RUN / 'SCORE_PROVENANCE.json')
    correction = read(HERE / 'REPORT_CORRECTION_1.json')
    assembly = read(HERE / 'REPORT_ASSEMBLY.json')
    assert correction['current_report'] == report_pin
    assert artifact(correction['archived_old_report']['path']) == correction['archived_old_report']
    assert assembly['report']['sha256'] == correction['archived_old_report']['sha256']
    for key in ('metrics', 'results', 'state_review', 'diagnostics'):
        assert artifact(assembly[key]['path']) == assembly[key]
    assert score['frames'] == state['frames'] == results['frames'] == 20098
    assert state['status'] == checks['status'] == 'PASS' and not state['GT_opened']
    assert provenance['reference_opened_after_all_seals'] and provenance['original_controls_exact']
    assert not provenance['GT_used_for_prediction'] and not provenance['ignored_public_ids']
    assert sum(checks['direct_check_counts'].values()) == 50
    assert acceptance['source_frames'] == sum(v['frames'] for v in acceptance['details'].values()) == 280
    assert sum(v['objects'] for v in acceptance['details'].values()) == 7512

    fields = ('IDF1', 'HOTA', 'AssA', 'IDSW', 'FP', 'FN')
    sources = [(n, score['segments'][n]) for n in SEGMENTS if n not in ('L3', 'LW')]
    sources += [('Feeding 四段独立命名空间合池', score['feeding_pooled'])]
    sources += [(n, score['segments'][n]) for n in ('L3', 'LW')]
    metric_rows, delta_rows = [], []
    for name, packet in sources:
        for arm in ARMS:
            metric = packet['metrics'][arm]
            metric_rows.append([name, arm, *[f'{metric[k]:.4f}' if k in fields[:3] else str(metric[k]) for k in fields]])
        for arm in ARMS[2:]:
            assert packet['metrics'][arm] == packet['metrics']['Z4Q_FROZEN']
        before, after = [packet['metrics'][a] for a in ('SAM3_NATIVE', 'RGBD_LAG')]
        delta_rows.append([name, *[f'{after[k]-before[k]:+.4f}' for k in fields[:3]], f'{after["IDSW"]-before["IDSW"]:+d}'])
    assert_table(tables, ('来源', '分支', *fields), metric_rows)
    assert_table(tables, ('来源', 'ΔIDF1', 'ΔHOTA', 'ΔAssA', 'ΔIDSW'), delta_rows)

    event_rows, evidence_rows, delay_rows, physical_rows = [], [], [], []
    event_totals = {arm:Counter() for arm in ARMS[2:]}
    evidence_totals = {arm:Counter() for arm in ARMS[2:]}
    physical_totals = {arm:Counter() for arm in ARMS[2:]}
    public_totals = {arm:Counter() for arm in ARMS[2:]}
    outcome_totals = {arm:Counter() for arm in ARMS[2:]}
    publish_totals, wall_lags = Counter(), []
    for name in SEGMENTS:
        original = state['sources'][name]
        packet = results['segments'][name]
        for arm in ARMS[2:]:
            parity = original['compared_with_Z4Q'][arm]
            assert all(parity[k] == original['frames'] for k in ('full_bridge_state_equal', 'engine_state_equal', 'mapping_equal'))
            assert parity['state_only_difference'] == 0
            event_totals[arm].update(original['event_counts'][arm])
            evidence_totals[arm].update(original['evidence_availability'][arm]['counts'])
            assert not packet['changed_publication_global_frames'][arm]
            events = score['event_audits'][name]['event_arms'][arm]
            counts = Counter(e['physical_preanchor'] for e in events)
            physical_totals[arm].update(counts)
            physical_rows.append([name, arm, *[str(counts[k]) for k in ('CORRECT', 'WRONG', 'UNSCORABLE', 'NOT_ALL_SOURCES_RECONNECTED')]])
            for event in events:
                assert not event['submitted_alternative'] and not event['selection_changes_real_publication']
                assert event['physical_references_are_actual_published_actions']
                assert event['public_reference_correctness_is_separate_from_physical_reconnect']
                outcome_totals[arm][event['outcome_role']] += 1
                for source in event['selected_sources']:
                    public_totals[arm][source['public_reference_correctness']] += 1
                    ref = source['public_origin_reference']
                    if ref: assert ref['frame'] < event['request_frame']
                    for edge in source['selected_edge_references']:
                        assert edge['actual_published_action']['kind'] == 'reconnect' and edge['actual_published_action']['accepted']
                        assert edge['actual_action_reference']['frame'] < event['request_frame']
        rgb, rgbd = [original['event_counts'][a] for a in ARMS[2:]]
        event_rows.append([name, str(original['frames']), str(rgb['requests']), str(rgb['independent_window_replays']),
            str(rgb['overlap']), str(rgb['out_of_scope']), f'{rgb["UNKNOWN"]}/{rgbd["UNKNOWN"]}',
            str(original['evidence_availability']['RGBD_LAG']['counts']['windows_with_positive_common_depth_weight']),
            str(rgbd['independent_changed_commits'])])
        c = original['evidence_availability']['RGBD_LAG']['counts']
        evidence_rows.append([name, *[str(c[k]) for k in ('comparisons', 'RGB_available_comparisons',
            'pre_anchor_depth_qualified_comparisons', 'local_3D_depth_qualified_comparisons')]])
        f, dt, wall = [packet[k] for k in ('publication_delay_frames', 'publication_data_time_delay_seconds', 'receive_to_first_publish_wall_seconds')]
        delay_rows.append([name, f'{f["min"]:.0f}/{f["median"]:.0f}/{f["max"]:.0f}',
            f'{dt["median"]:.3f}/{dt["p95"]:.3f}/{dt["max"]:.3f}', f'{wall["median"]:.3f}/{wall["p95"]:.3f}/{wall["max"]:.3f}'])
        for publication in rows(RUN / name / 'public' / 'PUBLISH_LEDGER.jsonl'):
            delay = publication['actual_delay_frames']
            assert delay == min(30, original['frames'] - publication['frame'])
            publish_totals['fixed30' if delay == 30 else 'EOF_short'] += 1
            assert not publication['already_published_history_rewritten']
            wall_lags.append(publication['receive_to_first_publish_seconds'])
    assert_table(tables, ('来源', '帧', '每臂请求', '每臂独立窗口', '重叠', '超范围', 'RGB/RGBD UNKNOWN', 'RGBD深度窗口', '改动提交'), event_rows)
    assert_table(tables, ('来源', '比较数', 'RGB轮廓可用', 'pre深度合格', '当前局部3D支持合格'), evidence_rows)
    assert_table(tables, ('来源', '分支', 'CORRECT', 'WRONG', 'UNSCORABLE', '未全部重接'), physical_rows)
    assert_table(tables, ('来源', '发布延迟帧 min/median/max', '数据时间秒 median/p95/max', '实际墙钟秒 median/p95/max'), delay_rows)
    for arm in ARMS[2:]:
        assert event_totals[arm]['requests'] == 89 and event_totals[arm]['independent_window_replays'] == 77
        assert event_totals[arm]['overlap'] == event_totals[arm]['out_of_scope'] == 6
        assert event_totals[arm]['q_minus_one_checkpoint_checks'] == event_totals[arm]['selected_state_cutoff_checks'] == 77
        assert event_totals[arm]['all_request_q_minus_one_hash_matches'] == 89
        assert event_totals[arm]['independent_changed_commits'] == event_totals[arm]['publication_changed_requests'] == 0
        assert evidence_totals[arm]['comparisons'] == results['totals'][arm]['edge_observations'] == 698
        assert evidence_totals[arm]['RGB_available_comparisons'] == 94
        assert evidence_totals[arm]['pre_anchor_depth_qualified_comparisons'] == 632
        assert evidence_totals[arm]['local_3D_depth_qualified_comparisons'] == 462
    assert event_totals['RGB_LAG']['UNKNOWN'] == 75 and event_totals['RGBD_LAG']['UNKNOWN'] == 74
    assert evidence_totals['RGBD_LAG']['windows_with_positive_common_depth_weight'] == 12
    assert diag['aggregate_both_arm_observation_counts']['comparisons'] == 1396
    assert '全来源每臂698个比较' in text and '每臂798' not in text
    assert publish_totals == dict(fixed30=19858, EOF_short=240)
    executions = list(rows(HERE / 'EXECUTION_LOG.jsonl'))
    timings = {Path(r['command'][1]).name:r for r in executions if Path(r['command'][1]).name in ('orchestrate.py', 'score.py')}
    for name, execution in timings.items():
        assert execution['exit_code'] == 0 and f'{execution["elapsed_seconds"]:.3f}秒' in text
    assert datetime.fromisoformat(timings['score.py']['started_utc']) > datetime.fromisoformat(timings['orchestrate.py']['ended_utc'])
    assert artifact(report_path) == report_pin, 'Report changed while under review'
    pins = {name:artifact(HERE / name) for name in ('FINAL_REVIEW.md', 'RESULTS.json', 'STATE_PUBLICATION_REVIEW.json',
        'EVIDENCE_DIAGNOSTICS.json', 'RUNTIME_FREEZE.json', 'CHECKS_FINAL.json', 'REAL_ACCEPTANCE.json', 'REPORT_CORRECTION_1.json')}
    pins.update({f'run/{name}':artifact(RUN / name) for name in ('METRICS.json', 'SCORE_PROVENANCE.json',
        'SCORING_FREEZE.json', 'ALL_PREDICTIONS_SEALED.json')})
    pins.update({f'{name}/input_freeze':artifact(RUN / name / 'public' / 'FREEZE.json') for name in SEGMENTS})
    receipt = dict(status='PASS', created_utc=datetime.now(timezone.utc).isoformat(),
        role='INDEPENDENT_LATE_REPORT_FACT_AND_SCOPE_REVIEW', helper=artifact(__file__), artifacts=pins,
        reference_pixels_opened=False, private_pixels_reviewed=False, remote_ref_verified=False,
        scope_exclusions=['Private image content and inventories still in preparation', 'Git commit/push and remote verification'],
        frames=20098, metric_rows_checked=len(metric_rows), delta_rows_checked=len(delta_rows),
        event_table_rows_checked=len(event_rows), evidence_table_rows_checked=len(evidence_rows),
        physical_reference_rows_checked=len(physical_rows), latency_rows_checked=len(delay_rows),
        event_counts={a:dict(c) for a,c in event_totals.items()}, evidence_counts={a:dict(c) for a,c in evidence_totals.items()},
        physical_preaction_reference_counts={a:dict(c) for a,c in physical_totals.items()},
        public_origin_reference_counts={a:dict(c) for a,c in public_totals.items()},
        outcome_roles={a:dict(c) for a,c in outcome_totals.items()}, publication=dict(publish_totals),
        wall_lag_seconds=dict(minimum=min(wall_lags), median=median(wall_lags), maximum=max(wall_lags)),
        protocol_scope_review=dict(accepted_original_edges_only=True, continuous_native_joint_swaps_not_covered=True,
            cumulative_forward_contour_not_bidirectional=True, RGBD_affinity_not_independent_scene_flow=True,
            exact_anchor_is_source_bound_hypothesis_not_dynamic_version_certification=True,
            SELF_score_separate_from_old_identity_edge_score=True, no_formal_alternative_commit=True,
            hypothetical_next_experiment_not_started=True),
        arithmetic_correction='Initial prose798 was a manual-sum error; actual sealed per-arm comparison count698 and total1396 are unchanged',
        new_model_http=0, cost_usd=0)
    write_new(HERE / 'REPORT_VALIDATION.json', receipt)
    print(json.dumps(dict(status='PASS', report=report_pin, receipt=artifact(HERE / 'REPORT_VALIDATION.json')), separators=(',', ':')))


if __name__ == '__main__':
    main()
