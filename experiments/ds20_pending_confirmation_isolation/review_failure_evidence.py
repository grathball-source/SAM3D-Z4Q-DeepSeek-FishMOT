"""Read every sealed S0 input/decision/publication; no association or truth reads."""
import guard
from common import *
from collections import Counter
import math
import statistics

MIXED = 'MIXED_ISOLATED'
ACTIVITY = 'ACTIVITY_ISOLATED'
ROLES = ('A', 'B')


def digest_row(row):
    return hashlib.sha256((json.dumps(row, separators=(',', ':'), allow_nan=False)+'\n').encode()).hexdigest()


def describe(values):
    values = [v for v in values if isinstance(v, (int, float)) and math.isfinite(v)]
    return dict(n=len(values), minimum=min(values) if values else None,
                median=statistics.median(values) if values else None,
                maximum=max(values) if values else None)


def summary(events, decisions):
    return dict(events=len(events), q=sum(e['q'] is not None for e in events),
        no_q=sum(e['q'] is None for e in events),
        event_status=dict(Counter(e['status'] for e in events)),
        no_q_status=dict(Counter(e['status'] for e in events if e['q'] is None)),
        choice=dict(Counter(d['choice'] for d in decisions)),
        restore_status=dict(Counter(d['restore_status'] for d in decisions)),
        order_reason=dict(Counter(d['order_reason'] for d in decisions)),
        joint_reason=dict(Counter(d['joint_reason'] for d in decisions)),
        order_eligible=sum(d['order_eligible'] for d in decisions),
        unknown=sum(not d['order_eligible'] for d in decisions),
        ordinal_joint_commits=sum(d['restore_status']=='COMMIT' for d in decisions))


def main():
    seal_all = read(RUN/'ALL_PREDICTIONS_SEALED.json')
    assert seal_all['status'] == 'ALL_PREDICTIONS_AND_ACCESS_SEALED'
    config = read(HERE/'CONFIG.json')
    # Reuse the frozen diagnostic's exact source/time/version predicates only.
    # Its association entry point is never called; it does not read truth.
    inspector_path = DS19/'diagnose_pre_pair.py'
    inspector = module('ds20_readonly_pre_pair_predicates', inspector_path)
    assert inspector.CFG == config
    evidence = []; segments = {}; decisions = []; no_q = []; q_comparisons = []
    pre_error_counts = Counter(); unknown_event_errors = Counter()
    current_status = Counter(); current_rejected_status = Counter(); ds19_reason = Counter()
    for name, (start, stop) in SEGMENTS.items():
        public = RUN/name/'public'
        verify_item(seal_all['seals'][name])
        seal = read(public/'PREDICTIONS_SEALED.json')
        files = ('EVENTS.json', 'ORDER_EVIDENCE.jsonl.gz', 'PUBLISH_LEDGER.jsonl',
                 'predictions.jsonl.gz', 'FREEZE.json')
        for filename in files:
            path = public/filename
            assert sha(path) == seal['artifacts_sha256'][filename]
            evidence.append(artifact(path))
        frozen = read(public/'FREEZE.json')
        assert frozen['config_scientific_sha256'] == sha(HERE/'CONFIG.json')
        events = read(public/'EVENTS.json')
        index = {arm: {e['id']: e for e in events[arm]} for arm in (MIXED, ACTIVITY)}
        orders = {(o['arm'], o['event']): o for o in rows(public/'ORDER_EVIDENCE.jsonl.gz')
                  if o['arm'] in (MIXED, ACTIVITY)}
        assert len(orders) == sum(e['q'] is not None for arm in (MIXED, ACTIVITY) for e in events[arm])
        wanted = {o['frame'] for o in orders.values()}
        ledgers = {r['frame']: r for r in rows(public/'PUBLISH_LEDGER.jsonl') if r['frame'] in wanted}
        published = {r['frame']: r for r in rows(public/'predictions.jsonl.gz') if r['frame'] in wanted}
        local = []
        for event in events[MIXED]:
            if event['q'] is None:
                no_q.append(dict(segment=name, event=event['id'], suspect_frame=event['suspect_frame'],
                    confirm_frame=event['confirm_frame'], end=event['end'], status=event['status'],
                    member_sources=event['member_sources'], public_ids=event['public_ids'],
                    group_frames=event['group_frames'], no_split_decision_or_joint_commit=True))
                continue
            order = orders[MIXED, event['id']]
            frame = event['q']; detail = order['detail']; ordinal = detail['order_evidence']
            assert frame == order['frame'] == order['q'] == event['evidence_cutoff_frame']
            assert order['global_frame'] == start+frame-1
            assert event['numeric']['detail']['order_evidence'] == ordinal
            prediction, ledger = published[frame], ledgers[frame]
            assert digest_row(prediction) == order['prediction_row_sha256'] == ledger['prediction_row_sha256']
            assert digest_row(order) == ledger['order_row_sha256'][MIXED]
            actual = {str(int(p['mask'][2:])): p['id'] for p in prediction['variants'][MIXED]}
            assert all(actual[n] == k for n, k in order['published_mapping'].items())
            assert all(p['frame'] == frame for p in event['post_first_observations'].values())
            inspected = inspector.inspect(event, order, name)
            if ordinal['reason'] == 'INVALID_CAUSAL_CLEAN_PRE_SOURCE_BINDING':
                fields = {error for r in inspected['roles'].values() for f in r['failures'] for error in f['errors']}
                unknown_event_errors.update(fields)
                pre_error_counts.update(error for r in inspected['roles'].values()
                    for f in r['failures'] for error in f['errors'])
            current = {}
            for native, packets in detail['association_measurement_contract']['current'].items():
                binding = packets['S0_ADAPTIVE_CORE']
                current[native] = {k: binding.get(k) for k in ('native', 'frame', 'global_frame',
                    'measurement_fact_id', 'certificate_fact_id', 'certificate_sha256', 'frame_binding_sha256',
                    'binding_sha256', 'source_version', 'version_key', 'identity_state',
                    'eligible_single', 'measurement_valid', 'screened_eligible', 'status', 'reason', 'actual_scalar')}
                assert binding['frame'] == frame and binding['native'] == int(native)
                assert binding['identity_state'] == 'IDENTITY_UNASSIGNED'
                current_status[binding['status']] += 1
                if ordinal['reason'] == 'INVALID_OR_MISSING_CURRENT_PAIRED_DEPTH' and not binding['eligible_single']:
                    current_rejected_status[binding['status']] += 1
            candidate_factors = {key: {k: candidate.get(k) for k in ('geometry_log_lr', 'order_log_lr',
                'log_score', 'posterior')} | dict(order=candidate['order'])
                for key, candidate in detail['candidates'].items()}
            probability = ordinal.get('p_A_nearer_at_q')
            weak = bool(ordinal['eligible'] and
                1/(1+config['minimum_joint_odds']) < probability < config['minimum_joint_odds']/(1+config['minimum_joint_odds']))
            record = dict(segment=name, event=event['id'], q=frame, original_q=order['global_frame'],
                choice=order['selected_choice'], restore_status=order['restore']['status'],
                joint_reason=detail['reason'], best=detail['best'], runner_up=detail['runner_up'],
                margin=detail['margin'], fixed_minimum_log_odds=detail['minimum_log_odds'],
                order_reason=ordinal['reason'], order_status=ordinal['status'], order_eligible=ordinal['eligible'],
                weak_uncalibrated_proxy=weak, p_A_nearer_at_q=probability,
                measured_relative_depth_mm=ordinal.get('last_delta_B_minus_A_mm'),
                propagated_pre_scale_mm=ordinal.get('pre_scale_at_q_mm'),
                actual_order_calibration=ordinal.get('calibration'), candidate_factors=candidate_factors,
                geometry_prediction={role: {k: detail['geometry_forecasts'][role].get(k) for k in
                    ('available', 'reason', 'samples', 'actual_gap_seconds', 'real_pre_span_seconds',
                     'time_scale_seconds', 'growth_factor', 'mean_mode', 'both_pre_velocity_available',
                     'post_velocity_status')} for role in ROLES},
                pre_pair_source_diagnosis=inspected, actual_current_depth_bindings=current,
                actual_first_q_publication=order['published_mapping'],
                actual_complete_q_publisher=actual,
                actual_order_row_sha256=digest_row(order), prediction_row_sha256=digest_row(prediction),
                group_retained_anonymous_frames=event['group_frames'],
                physical_identity_result='NOT_READ_NOT_GRADED_BY_THIS_NUMERIC_INPUT_DIAGNOSIS')
            decisions.append(record); local.append(record)
            activity = orders.get((ACTIVITY, event['id']))
            comparison = dict(segment=name, event=event['id'], mixed_q=frame,
                activity_event_present=event['id'] in index[ACTIVITY],
                activity_q=index[ACTIVITY].get(event['id'], {}).get('q'),
                same_q=bool(activity and activity['frame'] == frame))
            if comparison['same_q']:
                assert digest_row(activity) == ledger['order_row_sha256'][ACTIVITY]
                activity_actual = {str(int(p['mask'][2:])): p['id'] for p in prediction['variants'][ACTIVITY]}
                assert all(activity_actual[n] == k for n, k in activity['published_mapping'].items())
                comparison.update(activity_choice=activity['selected_choice'], mixed_choice=order['selected_choice'],
                    activity_reason=activity['detail']['reason'], mixed_reason=detail['reason'],
                    activity_order_reason=activity['detail']['order_evidence']['reason'],
                    mixed_order_reason=ordinal['reason'],
                    activity_native_pair=list(activity['published_mapping']), mixed_native_pair=list(order['published_mapping']),
                    same_native_pair=set(activity['published_mapping']) == set(order['published_mapping']),
                    activity_first_q_publication=activity['published_mapping'], mixed_first_q_publication=order['published_mapping'],
                    complete_actual_publisher_equal=activity_actual == actual,
                    compared_fields_are_actual_publication_not_physical_truth=True)
            q_comparisons.append(comparison)
        segments[name] = summary(events[MIXED], local)
        old_public = DS19/'run'/name/'public'
        old_seal = read(old_public/'PREDICTIONS_SEALED.json')
        old_path = old_public/'ORDER_EVIDENCE.jsonl.gz'
        assert sha(old_path) == old_seal['artifacts_sha256'][old_path.name]
        evidence.append(artifact(old_path))
        for row in rows(old_path):
            if row['arm'] == 'MIXED_RETURN':
                ds19_reason[row['detail']['order_evidence']['reason']] += 1
    totals = summary([e for name in SEGMENTS for e in read(RUN/name/'public/EVENTS.json')[MIXED]], decisions)
    eligible = [d for d in decisions if d['order_eligible']]
    common = [c for c in q_comparisons if c['same_q']]
    errors = dict(sample_field_counts=dict(pre_error_counts), affected_event_counts=dict(unknown_event_errors))
    supported = (unknown_event_errors['GEOMETRY_FRAME_ABSENT'] > 0 or
                 totals['order_reason'].get('NO_SAME_FRAME_PRE_PAIR', 0) > 0)
    next_step = ('Build and freeze one jointly qualified pre-risk geometry/depth provenance fragment per identity; '
        'preserve source generation/identity epoch/frame-time bindings and anonymous risk, and test it in one frozen full replay. '
        'Do not stitch across risk, change references using truth, relax current depth quality, or alter thresholds.') if supported else None
    output = dict(status='POSTSEAL_NUMERIC_INPUT_AND_ACTUAL_PUBLICATION_DIAGNOSIS',
        GT_read=False, metrics_read=False, RGB_or_GT_raster_read=False, new_prediction=False,
        new_association=False, new_model_http=0, cost_usd=0,
        method='Every MIXED_ISOLATED episode/q retained; exact saved frame/time/version predicates; actual publisher hash chain',
        all_predictions_seal=artifact(RUN/'ALL_PREDICTIONS_SEALED.json'),
        frozen_config=artifact(HERE/'CONFIG.json'), frozen_method_sources=[artifact(HERE/'controller.py'),
            artifact(HERE/'runner.py'), artifact(ROOT/'experiments/ds16_relative_depth_order/order_association.py')],
        diagnostic_helper=artifact(Path(__file__)), reused_readonly_predicates=artifact(inspector_path),
        source_artifacts=evidence, segments=segments, totals=totals,
        all_q_decisions=decisions, all_no_q_episodes=no_q,
        pre_pair_errors=errors, current_depth_status_counts=dict(current_status),
        rejected_current_pair_status_counts=dict(current_rejected_status),
        eligible_proxy_summary=dict(p_A_nearer_at_q=describe(d['p_A_nearer_at_q'] for d in eligible),
            propagated_pre_scale_mm=describe(d['propagated_pre_scale_mm'] for d in eligible),
            real_gap_seconds=describe(d['actual_order_calibration']['real_gap_seconds'] for d in eligible),
            real_pre_span_seconds=describe(d['actual_order_calibration']['real_pre_span_seconds'] for d in eligible),
            weak_uncalibrated_proxy=sum(d['weak_uncalibrated_proxy'] for d in eligible),
            maximum_abs_candidate_ordinal_log_lr=max((abs(c['order_log_lr']) for d in eligible
                for c in d['candidate_factors'].values()), default=None),
            descriptive_band_is_not_new_admission_rule=True, physical_accuracy_calibrated=False),
        actual_activity_vs_mixed_q_comparisons=q_comparisons,
        common_q_summary=dict(same_q=len(common), unmatched_mixed_q=len(q_comparisons)-len(common),
            same_native_pair=sum(c['same_native_pair'] for c in common),
            choice_different=sum(c['activity_choice'] != c['mixed_choice'] for c in common),
            complete_actual_q_publisher_different=sum(not c['complete_actual_publisher_equal'] for c in common)),
        readonly_DS19_MIXED_RETURN_order_reason_counts=dict(ds19_reason),
        input_reason_counts_equal_DS19=dict(ds19_reason) == totals['order_reason'],
        interpretation=['H0/fallback is the actual causal branch output, not DEFER or evidence of physical correctness.',
            'A missing synchronized pre-pair can coexist with numerically valid depth; no unknown sample was certified.',
            'The propagated scale is an uncalibrated continuity proxy, not physical accuracy or a proof of order invariance.',
            'This audit never invokes association, modifies input, changes a frozen threshold, or grades identity.'],
        one_next_step=next_step)
    write_new(HERE/'FAILURE_EVIDENCE_REVIEW.json', output)
    lines = ['# DS20 S0证据与实际发布复核', '',
        '仅复核全部封存数值输入与实际发布，不读GT、指标、RGB或GT raster，不重新关联、修复或改阈值。', '',
        f"MIXED_ISOLATED共有{totals['events']}个自动事件：{totals['q']}个q，{totals['no_q']}个无q；全部逐例保留。",
        f"q选择={totals['choice']}；恢复状态={totals['restore_status']}；S0联合COMMIT={totals['ordinal_joint_commits']}。这不含另一路原D1事件局部返回。", '',
        '| 段 | 事件 | q | 无q | 可用顺序 | UNKNOWN |', '|---|---:|---:|---:|---:|---:|']
    for name, stats in segments.items():
        lines.append(f"| {name} | {stats['events']} | {stats['q']} | {stats['no_q']} | {stats['order_eligible']} | {stats['unknown']} |")
    lines += ['', '## 数值输入限制', '',
        f"顺序原因：{totals['order_reason']}。联合决定原因：{totals['joint_reason']}。", '',
        f"前史逐列核验：受影响事件={dict(unknown_event_errors)}；失败采样字段计数={dict(pre_error_counts)}。",
        '这些事实区分深度本身缺测与几何/深度片段、时间、来源版本未对齐；不把历史中存在深度自动认证成可用身份历史。', '',
        f"可用顺序有{len(eligible)}例，其中{sum(d['weak_uncalibrated_proxy'] for d in eligible)}例仍处在原9:1门槛对应的0.1–0.9弱代理区间。",
        f"当前配对深度被拒的实际状态={dict(current_rejected_status)}；混合层被保留为观测事实，没有冒充单鱼身份深度。", '',
        '尺度、真实采样跨度、q间隔、候选ordinal贡献与实际FACT/SHA逐例列于JSON；它们是未标定的噪声/连续性代理，不能当作物理准确率或拓扑上下关系真值。', '',
        '## 与同轮ACTIVITY_ISOLATED比较', '',
        f"同event且同q共{len(common)}例，原始选择不同{sum(c['activity_choice'] != c['mixed_choice'] for c in common)}例；完整当帧实际publisher不同{sum(not c['complete_actual_publisher_equal'] for c in common)}例。",
        '事件/q或候选源不同的情况单列，不把底座状态差异归为本次ordinal恢复。H0保留自己当前映射，不能算安全或物理正确。', '',
        f"输入原因计数与只读DS19相同={output['input_reason_counts_equal_DS19']}。确认隔离修复没有同时解决这些前史合同与顺序强度限制。", '',
        '## 一个下一步', '',
        '将进入风险前的几何与深度共同合格片段作为同一来源包冻结；两模态共享实际source generation、identity epoch、帧和时间绑定。缺测、混合层与风险仍匿名，不跨风险拼历史，不按GT换锚，不放宽当前门槛。随后仅做一次冻结同源全段验证。'
        if supported else '本轮尚无证据支持预先选定的联合来源片段改进；先保留UNKNOWN，交由完整结果复盘确定一个方向。', '',
        '这是数值输入/发布诊断，不是科研PASS或物理恢复正确率；完整指标与独立物理评分由主报告另列。', '']
    with (HERE/'FAILURE_EVIDENCE_REVIEW.md').open('x', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(lines))
    print('Postseal S0 input diagnosis:', totals['events'], 'events /', totals['q'],
          'q /', totals['unknown'], 'UNKNOWN /', totals['ordinal_joint_commits'], 'ordinal joint commits')


if __name__ == '__main__':
    main()
