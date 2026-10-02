"""Postseal ordinal-factor diagnosis; GT identity matches are not depth surface truth."""
from common import *
from collections import Counter
import math

BASELINES = ('SAM3_NATIVE', 'Z4Q_FROZEN')
ORDER_ARMS = ('ORDER_OFF', 'DEPTH_ORDER', 'ORDER_PERMUTE')
REFERENCES = ('expected_mapping', 'clean_endpoint_expected_mapping', 'pre_consensus_expected_mapping')


def normalize_mapping(value):
    return {int(native): target for native, target in value.items()}


def same_input_signature(event, detail):
    """Ignore arm names while preserving actual identity/source/history semantics."""
    frozen = {}
    for role, value in (event.get('depth_frozen') or {}).items():
        key = value.get('key')
        frozen[role] = dict(source=value.get('source'), public=value.get('public'),
            version=(key[:1] + key[2:] if key else None),
            samples=[{key: sample.get(key) for key in ('frame', 'time', 'z_mm', 'mad_mm', 'fact_id', 'observation_class')}
                     for sample in value.get('samples', [])])
    value = {key: event.get(key) for key in ('suspect_frame', 'confirm_frame', 'q', 'member_sources',
             'public_ids', 'group_source', 'reference_anchors', 'pre_geometry_history', 'post_first_observations')}
    value.update(depth=frozen, H0_mapping=detail.get('candidates', {}).get('H0', {}).get('mapping'))
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def order_relation(event, evidence, expected, high, low, cdf, floor):
    """Interpret actual unpermuted core measurements using one reference mapping."""
    if not expected:
        return dict(status='UNKNOWN', reason='IDENTITY_REFERENCE_UNSCORABLE', physical_order_truth='UNKNOWN')
    if not evidence or not evidence.get('eligible'):
        return dict(status='UNKNOWN', reason=(evidence or {}).get('reason', 'NO_ORDINAL_EVIDENCE'),
                    physical_order_truth='UNKNOWN')
    expected = normalize_mapping(expected)
    a_id, b_id = event['public_ids']
    sources = {target: native for native, target in expected.items()}
    if len(expected) != 2 or a_id not in sources or b_id not in sources:
        return dict(status='UNKNOWN', reason='INCOMPLETE_TWO_IDENTITY_REFERENCE', physical_order_truth='UNKNOWN')
    bindings = evidence['post_bindings']
    a, b = (bindings.get(str(sources[target])) for target in (a_id, b_id))
    if a is None or b is None:
        return dict(status='UNKNOWN', reason='CURRENT_RAW_PAIR_UNAVAILABLE', physical_order_truth='UNKNOWN')
    delta = b['actual_core']['median'] - a['actual_core']['median']
    scale = math.hypot(*(max(floor, 1.4826 * value['actual_core']['mad']) for value in (a, b)))
    p_post = cdf(delta / scale)
    p_pre = evidence['p_A_nearer_at_q']
    direction = lambda value: 1 if value >= high else -1 if value <= low else 0
    pre_sign, post_sign = direction(p_pre), direction(p_post)
    latest = evidence['pre_pairs'][-1]['p_A_nearer']
    status = ('UNKNOWN' if not pre_sign or not post_sign else
              'INPUT_ORDER_COMPATIBLE' if pre_sign == post_sign else 'INPUT_ORDER_REVERSAL')
    return dict(status=status, reason='UNCALIBRATED_MEASUREMENT_AND_PROPAGATION_SIGNS',
        expected_mapping=expected, actual_raw_A_source=sources[a_id], actual_raw_B_source=sources[b_id],
        pre_p_A_nearer_at_q=p_pre, latest_measured_pre_p_A_nearer=latest,
        post_raw_p_A_nearer=p_post, post_raw_delta_B_minus_A_mm=delta,
        post_raw_pair_scale_mm=scale, pre_direction=pre_sign, post_direction=post_sign,
        measurement_fact_ids=[a['actual_state_fact_id'], b['actual_state_fact_id']],
        physical_order_truth='UNKNOWN', GT_used_only_for_identity_mapping=True,
        confidence_is_not_calibrated_physical_accuracy=True)


def factor_review(detail, selected):
    candidates = detail.get('candidates', {})
    if not candidates:
        return dict(status='NO_CANDIDATE_MATRIX')
    geometry = {name: candidate['log_prior'] + candidate['geometry_log_lr'] for name, candidate in candidates.items()}
    ranked = sorted(candidates, key=lambda key: (-geometry[key], key != 'H0', key))
    best, runner = ranked[0], ranked[1] if len(ranked) > 1 else None
    margin = geometry[best] - geometry[runner] if runner else None
    order = detail.get('order_evidence')
    counterfactual = ('H0' if not order or not order.get('eligible') or best == 'H0' or
                      margin is None or margin < detail['minimum_log_odds'] else best)
    components = {name: dict(mapping=candidate['mapping'], log_prior=candidate['log_prior'],
        geometry_log_lr=candidate['geometry_log_lr'], depth_log_lr=candidate.get('depth_log_lr', 0.),
        order_log_lr=candidate.get('order_log_lr', 0.), log_score=candidate['log_score'],
        order=candidate.get('order')) for name, candidate in candidates.items()}
    return dict(status='SAME_FROZEN_REQUEST_SCORE_DECOMPOSITION', candidates=components,
        geometry_only_best=best, geometry_only_runner_up=runner, geometry_only_margin=margin,
        order_best=detail.get('best'), order_joint_margin=detail.get('margin'),
        selected_choice=selected, counterfactual_order_off_choice=counterfactual,
        order_changes_choice_on_same_input=(selected != counterfactual) if order else None,
        separate_full_state_ORDER_OFF_branch_required=True,
        conditional_score_diagnostic_is_not_new_prediction=True)


def integrity():
    all_path = RUN / 'ALL_PREDICTIONS_SEALED.json'
    sealed = read(all_path)
    assert tuple(sealed['arms']) == ARMS and sealed['frames'] == 20098
    assert set(sealed['seals']) == set(sealed['access_seals']) == set(SEGMENTS)
    for name in SEGMENTS:
        verify_item(sealed['seals'][name]); verify_item(sealed['access_seals'][name])
        public = RUN / name / 'public'
        seal = read(public / 'PREDICTIONS_SEALED.json')
        assert tuple(seal['arms']) == ARMS
        for filename, digest in seal['artifacts_sha256'].items():
            assert sha(public / filename) == digest, (name, filename)
        for path, digest in read(public / 'FREEZE.json')['code_sha256'].items():
            assert sha(path) == digest, path
    provenance = read(RUN / 'SCORE_PROVENANCE.json')
    assert provenance['reference_opened_after_all_seals'] and not provenance['GT_used_for_predictions']
    assert provenance['masked_or_ignored_ids'] == 0
    for key in ('scorer', 'scoring_freeze', 'prediction_parity'):
        verify_item(provenance[key])
    return dict(all_predictions_seal=artifact(all_path), scoring_provenance=artifact(RUN / 'SCORE_PROVENANCE.json'))


def main():
    assert not (HERE / 'POSTSEAL_ORDER_REVIEW.json').exists(), 'Completed review is immutable'
    proof = integrity()
    from score import order_records, row_sha, verify_order_sources
    from order_association import t4_cdf
    config = read(HERE / 'CONFIG.json')
    high, low = config['minimum_joint_odds'] / (1. + config['minimum_joint_odds']), 1. / (1. + config['minimum_joint_odds'])
    all_metrics = read(RUN / 'METRICS.json')
    assert all_metrics['status'] == 'SCORED_AFTER_ALL_SIX_ARMS_EIGHT_SEALS'
    segments = {}
    counts = {arm: Counter() for arm in ARMS[2:]}
    for name, (start, stop) in SEGMENTS.items():
        public = RUN / name / 'public'
        source_contract = verify_order_sources(public)
        events, orders = read(public / 'EVENTS.json'), order_records(public)
        audit = read(public / 'EVENT_AUDIT.json')['arms']
        ledgers = {row['frame']: row for row in rows(public / 'PUBLISH_LEDGER.jsonl')}
        by_arm = {arm: [] for arm in ARMS[2:]}
        signatures = {}
        for arm in ARMS[2:]:
            for event in events[arm]:
                q = event['q']
                counts[arm]['events'] += 1
                if q is None:
                    counts[arm]['NO_SPLIT'] += 1
                    by_arm[arm].append(dict(event=event['id'], status=event['status'], q=None,
                        input_order='UNKNOWN_NO_FIRST_SPLIT', actual_commit=False))
                    continue
                row = orders[(arm, q)]
                assert row_sha(row) == ledgers[q]['order_row_sha256'][arm]
                detail, restore = row['detail'], row['restore']
                evidence = detail.get('order_evidence')
                identity = next(item for item in audit[arm]['group_events'] if item['q'] == q)
                outcomes = {reference: order_relation(event, evidence, identity[reference], high, low,
                    t4_cdf, config['raw_scale_floor_mm']) for reference in REFERENCES}
                status = (evidence or {}).get('status', 'ABSOLUTE_DEPTH_CONTROL_NO_ORDINAL_FACTOR')
                counts[arm][status] += 1
                counts[arm]['actual_group_commits'] += restore['status'] == 'COMMIT'
                counts[arm]['first_public_' + identity['first_public_physical']] += 1
                counts[arm]['pre_consensus_' + identity['first_public_pre_consensus_verdict']] += 1
                if evidence:
                    counts[arm]['reference_order_' + outcomes['pre_consensus_expected_mapping']['status']] += 1
                permutations = ([(native, binding['assigned_depth_source']) for native, binding in evidence['post_bindings'].items()
                    if int(native) != binding['assigned_depth_source']] if evidence else [])
                changed_values = (sum(binding['actual_core'] != binding['core'] for binding in evidence['post_bindings'].values())
                                  if evidence else 0)
                signature = same_input_signature(event, detail)
                signatures[(arm, q)] = signature
                factor = factor_review(detail, row['selected_choice'])
                if factor.get('order_changes_choice_on_same_input'):
                    counts[arm]['order_changes_same_input_choice'] += 1
                by_arm[arm].append(dict(event=event['id'], q=q, global_q=start + q - 1,
                    actual_first_published_mapping=row['published_mapping'], selected_choice=row['selected_choice'],
                    selected_mapping=detail.get('selected_mapping'), restore_status=restore['status'],
                    changes=restore['changes'], stage_error=restore.get('stage_error'),
                    fallback=restore.get('fallback'), decision_source=restore.get('decision_source'),
                    order_status=status, order_reason=(evidence or {}).get('reason', detail.get('reason')),
                    ordinal_evidence=evidence, score_decomposition=factor,
                    identity_reference_outcomes={key: identity[key] for key in (
                        'physical', 'first_public_physical', 'first_public_clean_endpoint_verdict',
                        'first_public_pre_consensus_verdict', 'committed_pre_consensus_verdict')},
                    input_order_under_reference_mapping=outcomes, source_contract='PASS',
                    source_binding_permutations=permutations, permuted_current_statistic_changes=changed_values,
                    same_input_semantic_sha256=signature, order_row= dict(sha256=row_sha(row)),
                    prediction_row_sha256=row['prediction_row_sha256']))
        for arm in ('DEPTH_ORDER', 'ORDER_PERMUTE'):
            for case in by_arm[arm]:
                if case['q'] is None:
                    continue
                case['same_input_as_ORDER_OFF'] = signatures.get(('ORDER_OFF', case['q'])) == case['same_input_semantic_sha256']
                case['full_branch_contrast_scope'] = ('SAME_CAUSAL_INPUT' if case['same_input_as_ORDER_OFF'] else
                    'CONDITIONAL_ON_DIFFERENT_OWN_STATE_OR_EVENT_CONTEXT')
        changed, first_difference = {arm: 0 for arm in ARMS[2:]}, {arm: None for arm in ARMS[2:]}
        for row in rows(public / 'predictions.jsonl.gz'):
            ledger = ledgers[row['frame']]
            assert row_sha(row) == ledger['prediction_row_sha256']
            for arm in ARMS[2:]:
                if row['variants'][arm] != row['variants']['ORDER_OFF']:
                    changed[arm] += 1
                    if first_difference[arm] is None:
                        first_difference[arm] = dict(frame=row['frame'], global_frame=row['global_frame'],
                            arm_mapping={item['mask']: item['id'] for item in row['variants'][arm]},
                            order_off_mapping={item['mask']: item['id'] for item in row['variants']['ORDER_OFF']})
        metrics = all_metrics['segments'][name]['metrics']
        for arm in BASELINES:
            assert metrics[arm] == read(DS15 / 'run/METRICS.json')['segments'][name]['metrics'][arm]
        segments[name] = dict(source_contract=source_contract, cases=by_arm, metrics=metrics,
            changed_frames_vs_ORDER_OFF=changed, first_differences_vs_ORDER_OFF=first_difference,
            reference_status=all_metrics['segments'][name]['reference_status'])
    result = dict(status='POSTSEAL_ORDER_REVIEW_COMPLETE', frames=20098, arms=list(ARMS), segments=segments,
        counts={arm: dict(value) for arm, value in counts.items()}, integrity=proof,
        physical_depth_order_truth='UNKNOWN_NO_SURFACE_GT', exposed_temporal_diagnostic_only=True,
        reference_identity_consensus_is_not_depth_accuracy=True, no_prediction_or_scoring_edits=True,
        model_http=0, cost_usd=0)
    write_new(HERE / 'POSTSEAL_ORDER_REVIEW.json', result)
    output = ['# DS16 相对深度次序封存后审查', '',
        '本审查读取已封存请求侧次序、候选评分、实际首次发布与独立身份诊断；不重新预测、不改评分。'
        '相对次序来自真实exclusive-core测量与未标定噪声代理。GT只核验身份对应，不提供鱼体表面深度真值。', '',
        '## 边界', '',
        '- UNKNOWN、不可评分、无分离及局部回退分别保留，均不自动算正确。',
        '- ORDER_PERMUTE只置换当前打分的深度绑定；实际状态仍按真实source写入。',
        '- 单请求去掉次序因子的选择仅为条件评分诊断；完整ORDER_OFF分支仍是主对照。',
        '- 分支前序状态或参考不同后，后续选择差异不解释成同一输入上的独立次序增量。', '',
        '## 全部首次分离记录', '',
        '| 片段 | 分支 | 原帧q | 原始选择 | 实际恢复 | 次序输入 | 首帧端点 | 片段共识 | 同ORDER_OFF输入 |',
        '|---|---|---|---|---|---|---|---|---|']
    for name, segment in segments.items():
        for arm, cases in segment['cases'].items():
            for case in cases:
                if case['q'] is None:
                    output.append(f"| {name} | {arm} | — | — | {case['status']} | UNKNOWN | — | — | — |")
                    continue
                verdicts = case['identity_reference_outcomes']
                output.append(f"| {name} | {arm} | {case['global_q']} | {case['selected_choice']} | {case['restore_status']} | "
                    f"{case['order_status']} | {verdicts['first_public_clean_endpoint_verdict']} | "
                    f"{verdicts['first_public_pre_consensus_verdict']} | {case.get('same_input_as_ORDER_OFF', 'control')} |")
    output += ['', '完整source事实回查、输入次序兼容/反转/未知、各候选geometry/ordinal分数、'
        '置换是否实际改变测量，以及全段状态分歧见POSTSEAL_ORDER_REVIEW.json。', '']
    with (HERE / 'POSTSEAL_ORDER_REVIEW.md').open('x', encoding='utf-8', newline='\n') as target:
        target.write('\n'.join(output))
    print(json.dumps(dict(status=result['status'], counts=result['counts']), ensure_ascii=False))


if __name__ == '__main__':
    main()
