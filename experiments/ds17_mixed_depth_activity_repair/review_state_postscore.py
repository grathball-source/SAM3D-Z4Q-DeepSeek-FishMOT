"""Read sealed scalar traces and completed score summaries; never run prediction.

This report helper is outside the scientific freeze. It reads no raster/RGB/GT
source. Run once after SCORE_PROVENANCE; outputs are additive and never replaced.
"""
import collections
import gzip
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RUN = HERE / 'run'
SEGMENTS = ('fishsa_development_8400', 'fishsa_validation_2888', 'L3', 'LW')
ARMS = ('Z4Q_FROZEN', 'DS16_ORDER', 'ACTIVITY_ORDER', 'MIXED_ORDER', 'MIXED_OFF')
METRIC_KEYS = ('IDF1', 'HOTA', 'AssA', 'IDSW', 'FP', 'FN')
WATCH = {
    'fishsa_development_8400': ({3901, 3902, 3903, 3907, 3913}, {7}, 3902, 7, 0),
    'fishsa_validation_2888': ({2187, 2188, 2189, 2233, 2237}, {8}, 2188, 8, 3),
    'L3': ({2872, 2890, 3025}, {6, 9, 47}, 3025, 47, 9),
    'LW': ({571, 828, 1331, 1888, 1938, 2395, 2411, 2511, 2512, 2513, 2514, 2515},
           {24, 30, 50, 80, 99, 105, 106}, 2515, 106, 5),
}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def artifact(path):
    path = Path(path)
    return dict(path=str(path), bytes=path.stat().st_size,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def rows(path):
    with gzip.open(path, 'rt', encoding='utf-8') as stream:
        for line in stream:
            yield json.loads(line)


def pick(value, keys):
    return {key: value.get(key) for key in keys}


def compact_edge(edge):
    return pick(edge, ('native_id', 'canonical_id', 'phase', 'old_anchor',
        'current_depths', 'core', 'whole', 'history_depth', 'current_depth',
        'residual_mm', 'tolerance_mm', 'alternatives', 'reserved_partners',
        'partner_margin_mm', 'required_partner_margin_mm', 'cost', 'failures', 'rejection'))


def audit_segment(name):
    public = RUN / name / 'public'
    seal = read(public / 'PREDICTIONS_SEALED.json')
    bindings = {file: artifact(public / file) for file in
                ('TRANSACTIONS.jsonl.gz', 'predictions.jsonl.gz', 'MIXED_DEPTH.jsonl.gz')}
    for file, binding in bindings.items():
        assert binding['sha256'] == seal['artifacts_sha256'][file], (name, file)
    frames, sources, q, source, target = WATCH[name]
    maps, edges, commits, samples, counters = {}, {}, {}, [], collections.Counter()
    last_owner92 = {}
    for row in rows(public / 'TRANSACTIONS.jsonl.gz'):
        arm, frame, trace = row['arm'], row['frame'], row['controller_trace']
        mapping = row['actual_published_mapping']
        assert len(mapping) == len(set(mapping.values())), (name, frame, arm)
        counters[f'{arm}/one_to_one_public_frames'] += 1
        if frame >= q and str(source) in mapping:
            key = str(mapping[str(source)])
            item = maps.setdefault(arm, {}).setdefault(key, dict(first=frame, last=frame, count=0))
            item['last'] = frame
            item['count'] += 1
        if name == 'LW' and frame <= 2515:
            owners = [n for n, k in mapping.items() if k == 92]
            if owners:
                last_owner92[arm] = dict(frame=frame, native_owners=owners)
        for action in row.get('durable_automatic_commits', []):
            event = action['event']
            commits.setdefault(arm, []).append(dict(frame=frame, global_frame=row['global_frame'],
                source=event['native_id'], target=event['canonical_id'],
                origin_rule=event.get('origin_rule', 'BIRTH_REFINE' if event.get('phase') == 'birth' else 'D1_DELAYED'),
                applied_at_first_publication=action['applied_at_first_publication'],
                durable_alias_after_commit=action['durable_alias_after_commit']))
        relevant_edges = [e for e in trace.get('edges', []) if e.get('native_id') == source and frame >= q]
        for edge in relevant_edges:
            key = f"{arm}/target={edge['canonical_id']}/rejection={edge.get('rejection')}"
            item = edges.setdefault(key, dict(first=frame, last=frame, count=0))
            item['last'] = frame
            item['count'] += 1
        for event in trace.get('events', []):
            if event['kind'] in ('native_return_quarantine_begin', 'native_return_quarantine_end', 'native_conflict_rollback'):
                counters[f"{arm}/{event['kind']}"] += 1
        separation = trace.get('activity_reference_separation', {})
        if separation:
            counters[f'{arm}/separated_activity_frames'] += 1
            present = separation['source_activity']
            assert not set(present) & {str(n) for n in separation['missing_sources_not_updated']}
            for n, observation in present.items():
                assert observation['frame'] == frame and n in mapping
                assert not observation['identity_measurement_certified']
                counters[f"{arm}/anonymous/{observation['observation_class']}"] += 1
                counters[f"{arm}/source_version/{observation['source_version']}"] += 1
            registry = separation.get('immutable_reference_registry')
            if registry:
                for public_id, status in separation['reference_status'].items():
                    if status['status'] != 'LIVE_BANK_RETIRED':
                        assert status['actual_bank_anchor'] == registry['references'][public_id].get('anchor')
                        expected = {v: h.get('anchor') for v, h in (registry['views'][public_id] or {}).items()}
                        assert status['actual_view_anchors'] == expected
                    activity = separation['public_activity'].get(public_id, {})
                    if activity.get('last_frame') == frame:
                        assert status['actual_observed_alias_owners'], (name, frame, arm, public_id)
                    counters[f"{arm}/reference/{status['status']}"] += 1
        if frame in frames:
            checks = [compact_edge(e) for e in trace.get('birth_checks', []) + trace.get('edges', [])
                      if e.get('native_id') in sources]
            anonymous_profiles = {n: pick(o, ('observation_class', 'source_version',
                'identity_measurement_certified', 'received_association_observation', 'received_association_profile'))
                for n, o in separation.get('source_activity', {}).items() if int(n) in sources}
            samples.append(dict(frame=frame, global_frame=row['global_frame'], arm=arm,
                mapping={n: k for n, k in mapping.items() if int(n) in sources},
                aliases={n: k for n, k in row['actual_alias_targets'].items() if int(n) in sources},
                candidate_counts=pick(trace, ('eligible_new', 'eligible_old')),
                checks=checks, automatic_proposals=[pick(e, ('native_id', 'canonical_id', 'accepted',
                    'confirmations', 'assignment_margin')) for e in trace.get('events', [])
                    if e.get('native_id') in sources and e['kind'] == 'reconnect'],
                activity=separation.get('public_activity'), reference_status=separation.get('reference_status'),
                visible_source_state=trace.get('merge_split_group', {}).get('visible_source_state'),
                anonymous_current_depth_blocked=separation.get('anonymous_current_depth_blocked'),
                anonymous_received_measurements=anonymous_profiles,
                bank_anchors={k: row.get('bank_anchors', {}).get(k) for k in ('0', '3', '5', '9', '92', '93', '99', '101', '103')},
                restore=row.get('restore')))
    mixed_samples = []
    for row in rows(public / 'MIXED_DEPTH.jsonl.gz'):
        if row['frame'] == q:
            fact = row['objects'][str(source)]
            mixed_samples.append(dict(frame=q, fact_id=fact['fact_id'], certificate_sha256=fact['certificate_sha256'],
                whole=pick(fact['whole'], ('status', 'eligible_single', 'mixture_flag', 'quality_usable', 'summary')),
                core=pick(fact['core'], ('status', 'eligible_single', 'mixture_flag', 'quality_usable', 'summary')),
                physical_mask_fish_count=fact['physical_mask_fish_count']))
            break
    automatic_audit = read(public / 'AUTOMATIC_RECONNECT_AUDIT.json')
    derived_physical = {arm: [pick(e, ('frame', 'source', 'target', 'origin_rule', 'physical', 'relations', 'actual_old_anchor'))
                            for e in events if e['source'] == source]
                        for arm, events in automatic_audit['arms'].items()}
    metrics = read(public / 'METRICS.json')['metrics']
    return dict(bindings=bindings, scorer_derived_audit=artifact(public / 'AUTOMATIC_RECONNECT_AUDIT.json'),
        metrics={arm: pick(values, METRIC_KEYS) for arm, values in metrics.items()},
        source_after_q=dict(q=q, source=source, target=target, published=maps, delayed_edges=edges),
        durable_automatic_commits=commits, selected_frames=samples,
        mixed_q_summary=mixed_samples, derived_physical=derived_physical,
        actual_trace_invariant_counts=dict(counters), last_actual_public92_before_2515=last_owner92)


def main():
    assert not (HERE / 'STATE_POLICY_REVIEW.json').exists(), 'Never overwrite a completed report'
    provenance = read(RUN / 'SCORE_PROVENANCE.json')
    totals = read(RUN / 'METRICS.json')
    assert totals['status'] == 'SCORED_AFTER_ALL_SIX_ARMS_EIGHT_SEALS'
    assert provenance['scientific_source_and_runtime_verified'] and provenance['reference_opened_after_all_seals']
    assert not provenance['GT_used_for_predictions'] and provenance['masked_or_ignored_ids'] == 0
    all_seal = read(RUN / 'ALL_PREDICTIONS_SEALED.json')
    for binding in all_seal['seals'].values():
        assert artifact(binding['path']) == binding
    result = dict(status='POSTSCORE_READ_ONLY_STATE_POLICY_REVIEW',
        scope='Scalar sealed traces and scorer-derived match summaries only; no GT/RGB raster opened',
        no_new_prediction_scoring_API_or_counterfactual=True, new_model_http=0,
        provenance=artifact(RUN / 'SCORE_PROVENANCE.json'), all_prediction_seal=artifact(RUN / 'ALL_PREDICTIONS_SEALED.json'),
        scientific_metrics=artifact(RUN / 'METRICS.json'), report_helper=artifact(__file__),
        source_lines=dict(controller=dict(path='experiments/ds17_mixed_depth_activity_repair/controller.py',
            sha256=artifact(HERE / 'controller.py')['sha256'], anonymous_current_block=[60, 78, 94],
            restore_only_clean_and_recent=[95, 106], measured_source_activity=[107, 126],
            clean_view_stage_guard=[175, 198], own_branch_local_fallback=[218, 231]),
            birth=dict(path='experiments/z4q_pairwise_reconnect_repair/source/px_z2.py',
                source_first_only=122, current_core_required=51),
            delayed=dict(path='experiments/z4q_pairwise_reconnect_repair/source/px_d1.py',
                register_birth=22, age_and_first_eligible=[54, 60], partner_activity=[79, 89],
                assignment_margin=[107, 117], confirmations=[119, 132])),
        interpretation=dict(engineering='L3 stale partner activity repaired; original n47->9 recovery restored, not new depth recovery',
            identity_vs_measurement_UNKNOWN='POST_UNASSIGNED means the current source identity is unknown. Its observed depth is not inherently missing. Blank current whole/core is a policy gate, not raw sensor absence.',
            main_loss='The same anonymous-current gate also consumes one-shot BirthRefine at dev3902 and val2188; protecting history need not imply hiding query evidence.',
            LW='Mixed filtering recovers original n106->5 at the original time; changed quality/history/candidate competition, not a newly invented correct recovery. MIXED_ORDER and OFF have equal LW predictions/metrics.',
            performance='Contract checks and scalar provenance passing do not establish scientific performance passing.'),
        limits=['No new intervention isolates clean/activity separation from anonymous current-depth blocking within ACTIVITY_ORDER.',
            'source_activity.source_version is UNKNOWN in received legacy profiles; external DepthState versions and event generation still carry separate provenance.',
            'Measured single-compatible-layer does not prove a mask contains exactly one fish or correct physical surface.',
            'L3/LW reference masks are existing weak preannotation; CORRECT is scorer-derived under that reference, not manual physical certification.',
            'Stage/fallback structural consistency does not prove selected physical identities; actual post-stage bank is separate from pre-stage reference trace.',
            'Fallback keeps own causal preview, including consumed birth bookkeeping and any allowed original automatic transaction; it does not replay an unblocked baseline.'],
        segments={name: audit_segment(name) for name in SEGMENTS})
    # Fixed assertions about reported actual sealed actions, not new scientific tests.
    assert result['segments']['fishsa_development_8400']['source_after_q']['published']['ACTIVITY_ORDER']['7']['count'] == 4499
    assert result['segments']['fishsa_validation_2888']['source_after_q']['published']['ACTIVITY_ORDER']['8']['count'] == 49
    assert result['segments']['LW']['last_actual_public92_before_2515']['ACTIVITY_ORDER']['frame'] == 2460
    assert result['segments']['LW']['last_actual_public92_before_2515']['MIXED_ORDER']['frame'] == 2310
    (HERE / 'STATE_POLICY_REVIEW.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    markdown = ['# DS17 状态策略封存后复盘', '',
        '仅读取已封存标量trace与统一评分派生摘要。未读GT/RGB raster，未改冻结科学代码，未追加预测、评分、反事实或API。', '',
        '## 主判定', '',
        '已覆盖的状态隔离/原子发布检查通过，整体关联语义与性能未通过。L3恢复了被DS16活动冻结丢失的原正确自动重接；开发8400和验证2888又因匿名当前测量屏蔽丢失或延迟原正确Birth。不得将身份UNKNOWN当作测量UNKNOWN。', '',
        '## 两次出生机会被消耗', '',
        '- 开发F3902：原Z4Q/DS16将native7首次公开为0，评分派生CORRECT。ACTIVITY/MIXED/OFF因POST_UNASSIGNED将当前whole/core置不可用，首拒current_core_unavailable；n7登记birth后再无Birth机会。3907–3913七条D1边均partner_ambiguous，此后没有接回；3902–8400共4499帧公开7。',
        '- 验证local2188/global11488：同一策略屏蔽native8当前core，原8→3 Birth派生CORRECT被阻断。新分支2233–2237积累五次D1，local2237/global11537实际接回3；49帧曾公开8。',
        '- 两个q的raw scalar whole/core都有n>0与有效深度，混合测量均SINGLE_COMPATIBLE_LAYER；这是策略屏蔽，不是传感器缺失，也不证明物理身份已知。', '',
        '## L3：活动修复的工程收益', '',
        'bank9 clean anchor仍local2712；真实源9到2890仍有观测，新分支last_frame随真实活动到2890，DS16却冻在2872。contact5最后2854：旧last_seen-contact约0.596秒保留竞争5，新真实间隔约1.193秒排除过期竞争。3025/global3024原D1 source47→9得以保留；这不是S0也不是新增深度恢复。匿名recent_core保持未认证，native_runs继续真实更新。', '',
        '## LW：为何ACTIVITY下降、MIXED回到原IDF1', '',
        '主要可评分链是原local2515 source106→5。ACTIVITY2511–12目标5的partner margin为24.946/23.107毫米，小于required25；2513–14仅确认两次。2515目标5cost0.214441和目标92cost0.211113近同，唯一候选的全矩阵替代差约0.003327<0.15，原D1清空pending，此后未提交。ACTIVITY99→92@2395、105→92 Birth@2411使bank92最近真实占用至2460，仍在候选资格窗口。',
        'MIXED两次上述alias未建立，bank92最后实际公开2310，2515已超过6秒候选窗口；目标5历史质量路径也使required降为20.817毫米（原权重/阈值未调整）。2511–15积五次，2515与原Z4Q/DS16同一时刻提交106→5。后1115帧ACTIVITY保持106，MIXED保持5，派生恢复CORRECT。MIXED的LW IDF1回到原64.329395，不是新增正确恢复，HOTA/AssA仍略低于原。MIXED_ORDER=OFF：这项收益不来自上下关系。',
        '源80在ACTIVITY1888→42、MIXED1938→4以及其他资格/alias链也改变；这些恢复派生UNSCORABLE，不宣称物理改进。完整逐动作列表和候选表在JSON。', '',
        '## 指标（同源、全部公开ID纳入）', '',
        '|片段|分支|IDF1|HOTA|AssA|IDSW|FP|FN|',
        '|---|---|---:|---:|---:|---:|---:|---:|']
    for name, segment in result['segments'].items():
        for arm, metric in segment['metrics'].items():
            markdown.append(f"|{name}|{arm}|{metric['IDF1']:.6f}|{metric['HOTA']:.6f}|{metric['AssA']:.6f}|{metric['IDSW']}|{metric['FP']}|{metric['FN']}|")
    markdown += ['', '## 状态/事务边界', '',
        'clean字段、view_bank与recent_core的冻结和活动last_seen/partners继续更新在真实trace中核查；缺失member没有凭空更新时间。公开映射逐帧一对一。stage仍核版本、generation、q、clean+view provenance及目标占用，先stage/commit后首次发布。局部fallback仅采纳本分支完整因果preview并释放本事件，不复制其他分支；它会保留preview里已经消耗的Birth，而不是无阻断Z4Q反事实。',
        '事务只删除选中source的alias/pending/native_runs/recent_core，保留预留public bank；未观察到组外修复被整套覆盖。旧source bank可能在alias生效后作为不可占用候选留存：这是接口边界，不能凭合成PASS保证所有未来映射物理正确。source_activity内部source_version为UNKNOWN，不能将其冒充完整版本证书。', '',
        '## 复现与证据', '',
        '运行 `python -B experiments/ds17_mixed_depth_activity_repair/review_state_postscore.py` 仅重建一次新增报告；完成文件不覆盖。证据路径、字节和SHA、源码行、实际动作/发布、候选成本、匿名来源和测量均在STATE_POLICY_REVIEW.json。', '',
        '下一机制须把匿名当前测量用于候选比较与把测量认证写入历史分开，保留原一次性Birth机会；本轮不修改或再跑该策略。']
    (HERE / 'STATE_POLICY_REVIEW.md').write_text('\n'.join(markdown) + '\n', encoding='utf-8')
    print(json.dumps({name: artifact(HERE / name) for name in ('STATE_POLICY_REVIEW.json', 'STATE_POLICY_REVIEW.md')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
