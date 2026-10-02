"""Postscore-only public scalar/action audit; no GT, pixels or new predictions."""
from collections import Counter
from common import ARMS, HERE, RUN, SEGMENTS, artifact, read, rows, sha, write_new

FIELDS = ('IDF1', 'HOTA', 'AssA', 'IDSW', 'FP', 'FN')
PAIRS = [('Z4Q_FROZEN', 'SAM3_NATIVE'), ('DS16_ORDER', 'Z4Q_FROZEN'),
         ('ACTIVITY_ORDER', 'SAM3_NATIVE'), ('ACTIVITY_ORDER', 'Z4Q_FROZEN'),
         ('ACTIVITY_ORDER', 'DS16_ORDER'), ('MIXED_ORDER', 'SAM3_NATIVE'),
         ('MIXED_ORDER', 'Z4Q_FROZEN'), ('MIXED_ORDER', 'ACTIVITY_ORDER'),
         ('MIXED_ORDER', 'MIXED_OFF'), ('MIXED_OFF', 'SAM3_NATIVE'),
         ('MIXED_OFF', 'Z4Q_FROZEN'), ('MIXED_OFF', 'ACTIVITY_ORDER')]


def compare(switches, arm, base):
    actual = {(x['gt_id'], x['frame']): x for x in switches[arm]}
    reference = {(x['gt_id'], x['frame']): x for x in switches[base]}
    assert len(actual) == len(switches[arm]) and len(reference) == len(switches[base])
    order = lambda key: (key[1], key[0])
    added = [actual[k] for k in sorted(actual.keys() - reference.keys(), key=order)]
    removed = [reference[k] for k in sorted(reference.keys() - actual.keys(), key=order)]
    assert len(added) - len(removed) == len(actual) - len(reference)
    return dict(arm=arm, base=base, added=added, removed=removed,
        added_count=len(added), removed_count=len(removed), common=len(actual.keys() & reference.keys()),
        net=len(actual) - len(reference),
        common_transition_changed=[dict(gt_id=k[0], global_frame=k[1], arm_switch=actual[k], base_switch=reference[k])
            for k in sorted(actual.keys() & reference.keys(), key=order)
            if (actual[k]['from_public_id'], actual[k]['to_public_id']) !=
               (reference[k]['from_public_id'], reference[k]['to_public_id'])])


def main():
    required = [RUN / name for name in ('ALL_PREDICTIONS_SEALED.json', 'METRICS.json', 'SCORE_PROVENANCE.json')]
    assert all(path.exists() for path in required), 'Wait for all seals and complete independent scoring'
    sealed, metrics, provenance = map(read, required)
    assert sealed['status'] == 'ALL_PREDICTIONS_AND_ACCESS_SEALED'
    assert metrics['status'] == 'SCORED_AFTER_ALL_SIX_ARMS_EIGHT_SEALS'
    assert provenance['reference_opened_after_all_seals'] and not provenance['GT_used_for_predictions']
    assert metrics['all_seal'] == artifact(required[0])
    sources, results = [artifact(p) for p in required], {}
    for name, (start, stop) in SEGMENTS.items():
        if not name.startswith('feeding_'):
            continue
        public = RUN / name / 'public'
        seal = read(public / 'PREDICTIONS_SEALED.json')
        assert artifact(public / 'PREDICTIONS_SEALED.json') == sealed['seals'][name]
        # Only numeric public files are opened; no reference masks/pixel/source package.
        for filename in ('METRICS.json', 'SWITCHES.json', 'AUTOMATIC_RECONNECT_AUDIT.json', 'EVENT_AUDIT.json'):
            sources.append(artifact(public / filename))
        assert sha(public / 'TRANSACTIONS.jsonl.gz') == seal['artifacts_sha256']['TRANSACTIONS.jsonl.gz']
        sources.append(artifact(public / 'TRANSACTIONS.jsonl.gz'))
        scalar = read(public / 'METRICS.json')['metrics']
        switches = read(public / 'SWITCHES.json')
        automatic = read(public / 'AUTOMATIC_RECONNECT_AUDIT.json')['arms']
        event_audit = read(public / 'EVENT_AUDIT.json')['arms']
        for arm in ARMS:
            assert len(switches[arm]) == scalar[arm]['IDSW']
        comparisons = [compare(switches, arm, base) for arm, base in PAIRS]
        relevant_frames = {x['frame'] for comparison in comparisons
            for field in ('added', 'removed') for x in comparison[field]}
        relevant_frames.update(x['global_frame'] for actions in automatic.values() for x in actions)
        transactions, last_source_publication, previous_for_actions = {}, {}, {}
        for transaction in rows(public / 'TRANSACTIONS.jsonl.gz'):
            arm, frame = transaction['arm'], transaction['global_frame']
            mapping = {int(n): target for n, target in transaction['actual_published_mapping'].items()}
            for action in automatic.get(arm, []):
                if action['global_frame'] == frame:
                    previous_for_actions[arm, frame, action['source'], action['target']] = last_source_publication.get((arm, action['source']))
            if frame in relevant_frames:
                transactions[arm, frame] = dict(frame=transaction['frame'], global_frame=frame,
                    actual_published_mapping=mapping, previous_mapping=transaction.get('previous_mapping'),
                    previous_mapping_status=('RECORDED' if 'previous_mapping' in transaction else 'NOT_RECORDED_FOR_FROZEN_BASELINE'),
                    actual_alias_targets=transaction['actual_alias_targets'], restore=transaction.get('restore'),
                    active_event=transaction.get('active_event'),
                    controller_events=transaction['controller_trace'].get('events', []))
            last_source_publication.update({(arm, native): dict(frame=frame, public_id=target)
                for native, target in mapping.items()})
        action_details = {}
        for arm in ARMS[1:]:
            values = []
            for action in automatic.get(arm, []):
                frame, native, target = action['global_frame'], action['source'], action['target']
                raw = action['actual_controller_action']
                assert action['origin_rule'] in ('D1_DELAYED', 'BIRTH_REFINE')
                assert raw.get('phase') != 'birth' or action['origin_rule'] == 'BIRTH_REFINE'
                exact = [x for x in switches[arm] if x['frame'] == frame and
                         x['native_id'] == native and x['to_public_id'] == target]
                prior = previous_for_actions.get((arm, frame, native, target))
                category = ('WRONG_ACTUAL_BANK_MAPPING' if action['actual_reference_physical'] == 'WRONG' else
                    'BANK_CORRECT_WITH_PREEXISTING_PUBLIC_ORIGIN_MISMATCH' if
                    action['actual_reference_physical'] == 'CORRECT' and action['prior_public_reference_status'] == 'PREEXISTING_PUBLIC_ORIGIN_MISMATCH' else
                    'STRICT_CORRECT_BUT_EXISTING_PUBLICATION_CHANGED' if action['physical'] == 'CORRECT' and exact and prior else
                    'STRICT_CORRECT_WITHOUT_DIRECT_CLEAR_SWITCH' if action['physical'] == 'CORRECT' else action['physical'])
                values.append(dict(action=action, category=category, phase=raw.get('phase'),
                    exact_CLEAR_switches=exact, previous_observed_source_publication=prior,
                    source_previously_published_explicit=raw.get('source_previously_published', 'NOT_RECORDED_IN_THIS_ORIGINAL_RULE'),
                    previous_GT_matched_source='UNKNOWN_NOT_RECONSTRUCTED_FROM_GT',
                    first_source_publication=raw.get('actual_first_source_publication')))
            action_details[arm] = dict(accepted=len(values), durable=sum(x['action']['durable_automatic_commit'] for x in values),
                origin_counts=dict(Counter(x['action']['origin_rule'] for x in values)),
                physical_joint_counts=dict(Counter(x['action']['physical'] for x in values)),
                actual_bank_physical_counts=dict(Counter(x['action']['actual_reference_physical'] for x in values)),
                prior_public_reference_counts=dict(Counter(x['action']['prior_public_reference_status'] for x in values)),
                category_counts=dict(Counter(x['category'] for x in values)),
                incidental_public_origin_returns=sum(x['action']['incidental_public_origin_return'] for x in values), values=values)
        divergent = []
        for comparison in comparisons:
            for change in ('added', 'removed'):
                owner = comparison['arm'] if change == 'added' else comparison['base']
                for switch in comparison[change]:
                    frame, native = switch['frame'], switch['native_id']
                    transaction = transactions.get((owner, frame), {})
                    direct = [x for x in action_details.get(owner, {}).get('values', []) if
                        x['action']['global_frame'] == frame and x['action']['source'] == native and
                        x['action']['actual_first_public_id'] == switch['to_public_id']]
                    group = [x for x in event_audit.get(owner, {}).get('group_events', [])
                             if x.get('q') == frame - start + 1]
                    aliases = transaction.get('actual_alias_targets', {})
                    lineage = [x for x in action_details.get(owner, {}).get('values', []) if
                        x['action']['global_frame'] < frame and x['action']['source'] == native and
                        x['action']['target'] == switch['to_public_id'] and x['action']['durable_automatic_commit']]
                    actual_direct = [x for x in direct if x['action']['durable_automatic_commit']]
                    group_commit = [x for x in group if x.get('restore_status') == 'COMMIT' and
                        str(native) in x.get('actual_first_public_mapping', {})]
                    # Event audit integer keys become JSON strings; no invented cause when absent.
                    reason = ('DIRECT_DURABLE_AUTOMATIC_ACTION' if actual_direct else
                        'GROUP_Q_PUBLISHED_TRANSACTION' if group_commit else
                        'PREEXISTING_ALIAS_AT_SOURCE_HANDOFF' if aliases.get(str(native)) == switch['to_public_id'] else
                        'NATIVE_SOURCE_HANDOFF_OR_CLEAR_MATCH_HISTORY')
                    divergent.append(dict(arm=comparison['arm'], base=comparison['base'], change=change,
                        owner=owner, switch=switch, reason=reason, direct_automatic_actions=direct,
                        prior_same_source_alias_actions=lineage, group_q_audit=group,
                        transaction=transaction, previous_GT_match_source='UNKNOWN',
                        attribution_boundary='Actual independent-state lineage; not an isolated edge counterfactual'))
        group_details = {arm: dict(events=len(event_audit[arm]['group_events']),
            literal_counts=dict(Counter(x['physical'] for x in event_audit[arm]['group_events'])),
            committed_pre_consensus_counts=dict(Counter(x.get('committed_pre_consensus_verdict', 'NO_SPLIT')
                for x in event_audit[arm]['group_events'])), values=event_audit[arm]['group_events']) for arm in ARMS[2:]}
        changed_actions = {}
        for arm, base in [('ACTIVITY_ORDER', 'Z4Q_FROZEN'), ('MIXED_ORDER', 'ACTIVITY_ORDER'), ('MIXED_OFF', 'MIXED_ORDER')]:
            key = lambda x: (x['global_frame'], x['source'], x['target'], x['origin_rule'])
            a = {key(x): x for x in automatic.get(arm, []) if x['durable_automatic_commit']}
            b = {key(x): x for x in automatic.get(base, []) if x['durable_automatic_commit']}
            changed_actions[arm + '_vs_' + base] = dict(added=[a[k] for k in sorted(a.keys()-b.keys())],
                removed=[b[k] for k in sorted(b.keys()-a.keys())], common=len(a.keys() & b.keys()))
        results[name] = dict(frames=stop-start+1, metrics=scalar, switch_comparisons=comparisons,
            divergent_switch_actions=divergent, automatic_actions=action_details,
            changed_durable_actions=changed_actions, group_restores=group_details)
    pooled = metrics['feeding_pooled']['metrics']
    assert all(sum(s['metrics'][arm]['IDSW'] for s in results.values()) == pooled[arm]['IDSW'] for arm in ARMS)
    aggregate = []
    for arm, base in PAIRS:
        selected = [c for segment in results.values() for c in segment['switch_comparisons']
                    if c['arm'] == arm and c['base'] == base]
        counts = {field: sum(x[field] for x in selected) for field in ('added_count', 'removed_count', 'common', 'net')}
        assert counts['net'] == pooled[arm]['IDSW'] - pooled[base]['IDSW']
        aggregate.append(dict(arm=arm, base=base, **counts))
    report = dict(status='POSTSEAL_FEEDING_SWITCH_ACTION_REVIEW_COMPLETE', frames=1471,
        pooled_metrics=pooled, segments=results, aggregate_switch_comparisons=aggregate,
        pooled_deltas={base:{arm:{field:pooled[arm][field]-pooled[base][field] for field in FIELDS} for arm in ARMS}
            for base in ('SAM3_NATIVE','Z4Q_FROZEN','ACTIVITY_ORDER','MIXED_OFF')},
        source_bindings=sources, generator=artifact(__file__), direct_GT_or_pixel_reads=False,
        new_rules_or_samples_selected_with_GT=False, old_or_current_seals_modified=False, model_http=0,cost_usd=0,
        limitations=['A switch net is not the number of harmful new actions',
            'Correct relative to an actual bank and public-origin consistency are different outcomes',
            'A known physical recovery can still change an already published ID and increase CLEAR IDSW',
            'Potential depth layers are not physical fish identity/order truth',
            'No new action counterfactual or SAM3 batch/source rerun; correlations do not prove a specific cause',
            'Common switch frames may have different from/to identities; those are listed separately'])
    write_new(HERE/'POSTSEAL_FEEDING_SWITCH_REVIEW.json',report)
    lines=['# DS18 Feeding：完整评分后的切换与真实动作审计','',
        '六臂八段全部封存并完成统一评分后，仅读取公开指标、切换、动作审计和数字事务记录。没有直接读取GT或raster，没有新实验或规则修改。','',
        '## 同源1471帧完整指标','', '|分支|IDF1|HOTA|AssA|IDSW|FP|FN|','|---|---:|---:|---:|---:|---:|---:|']
    for arm,m in pooled.items():lines.append(f'|{arm}|{m["IDF1"]:.6f}|{m["HOTA"]:.6f}|{m["AssA"]:.6f}|{m["IDSW"]}|{m["FP"]}|{m["FN"]}|')
    lines += ['','## 新增与消除分开','', '|分支|参照|新增|消除|共同|净值|','|---|---|---:|---:|---:|---:|']
    for c in aggregate:lines.append(f'|{c["arm"]}|{c["base"]}|{c["added_count"]}|{c["removed_count"]}|{c["common"]}|{c["net"]:+d}|')
    lines += ['','## 原自动动作分列','', '|片段|分支|D1 accepted|Birth accepted|durable|严格联合物理判定|实际bank物理判定|先前公共起源|','|---|---|---:|---:|---:|---|---|---|']
    for name,s in results.items():
        for arm,a in s['automatic_actions'].items():
            lines.append(f'|{name}|{arm}|{a["origin_counts"].get("D1_DELAYED",0)}|{a["origin_counts"].get("BIRTH_REFINE",0)}|{a["durable"]}|{a["physical_joint_counts"]}|{a["actual_bank_physical_counts"]}|{a["prior_public_reference_counts"]}|')
    lines += ['','完整每段指标、逐GT切换新增/消除、共同帧但不同转换、当前发布与alias、直接自动动作和此前同源alias链、group q的 literal/pre共识判定见JSON。phase=birth属于 BIRTH_REFINE，不因kind=reconnect误称D1。',
        '', '新旧物理参考、进入前已错公共身份与严格联合结论分别保留；UNKNOWN、UNSCORABLE和未持久提交不算正确。晚到的真实bank正确恢复可能新增IDSW；少切换也可能降低IDF1/HOTA/AssA。',
        '', 'MIXED_ORDER−ACTIVITY_ORDER仅为同接口底座上的组合质量筛选差值；MIXED_ORDER−MIXED_OFF为冻结顺序因子的条件差值。主比较始终同时包含同源native与原Z4Q。相对较弱旧状态的恢复属于止损，不能称深度独有增量。',
        '', '当前事务能证实直接提交、持久alias和首分离帧实际发布。没有直接动作的切换保留为source handoff/CLEAR历史匹配类；未从GT补造前一次匹配的source，也未新增反事实证明。此报告不把潜在混层或来源质量拒绝当作物理鱼数、真实上下关系或正确身份。','']
    with (HERE/'POSTSEAL_FEEDING_SWITCH_REVIEW.md').open('x',encoding='utf-8',newline='\n') as output:
        output.write('\n'.join(lines))
    print('POSTSEAL_FEEDING_SWITCH_REVIEW_COMPLETE', report['frames'], aggregate)


if __name__ == '__main__':
    main()
