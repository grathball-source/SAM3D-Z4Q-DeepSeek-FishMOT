"""Postseal numeric report only: no GT, predictor, model or parameter change."""
from common import *
from collections import Counter
from datetime import datetime

BASES = ('SAM3_NATIVE', 'Z4Q_FROZEN', 'Z4Q_SHARED')
STATE_ARMS, EVENT_ARMS = ARMS[1:], ARMS[2:]
FIELDS = ('IDF1', 'HOTA', 'AssA', 'IDSW', 'FP', 'FN')


def integrity():
    seal = read(RUN / 'ALL_PREDICTIONS_SEALED.json')
    assert seal['status'] in ('ALL_FIVE_BRANCHES_EIGHT_SEGMENTS_SEALED', 'ALL_PREDICTIONS_AND_ACCESS_SEALED')
    assert seal['frames'] == 20098 and tuple(seal['arms']) == ARMS
    assert set(seal['seals']) == set(seal['access_seals']) == set(SEGMENTS)
    checked = {}

    def check(path, expected):
        path = str(Path(path).resolve())
        if path not in checked:
            checked[path] = sha(path)
        assert checked[path] == expected, path

    for name in SEGMENTS:
        public = RUN / name / 'public'
        for item in (seal['seals'][name], seal['access_seals'][name]):
            check(item['path'], item['sha256'])
            assert Path(item['path']).stat().st_size == item['bytes']
        segment_seal = read(public / 'PREDICTIONS_SEALED.json')
        for filename, digest in segment_seal['artifacts_sha256'].items():
            check(public / filename, digest)
        frozen = read(public / 'FREEZE.json')
        for path, digest in frozen['code_sha256'].items():
            check(path, digest)
        verify_item(frozen['source_manifest'])
        assert frozen['no_gt_before_seal'] and frozen['new_model_http'] == frozen['model_cost_usd'] == 0
    old = read(HERE / 'OLD_READONLY_LOCK.json')['files']
    for path, digest in old.items():
        check(ROOT / path, digest)
    return dict(status='PASS', old_unchanged_files=len(old), checked_file_hashes=len(checked),
                all_eight_prediction_access_seals_verified=True, frozen_code_unchanged=True,
                original_inputs_immutable=True, new_model_http=0, cost_usd=0)


def counts(name):
    public = RUN / name / 'public'
    events, audit = read(public / 'EVENTS.json'), read(public / 'EVENT_AUDIT.json')['arms']
    automatic = read(public / 'AUTOMATIC_RECONNECT_AUDIT.json')
    result = {arm: dict(controller_events=Counter(), automatic_edge_checks=Counter(),
                       automatic_vetoes=0, accepted_auto_actions=0,
                       accepted_causal_preview_candidates=0,
                       birth_query_status=Counter(), birth_stage_status=Counter()) for arm in STATE_ARMS}
    for transaction in rows(public / 'TRANSACTIONS.jsonl.gz'):
        out, trace = result[transaction['arm']], transaction['controller_trace']
        out['accepted_auto_actions'] += len(transaction['durable_automatic_commits'])
        for event in trace.get('events', []):
            out['controller_events'][event['kind']] += 1
            out['accepted_causal_preview_candidates'] += bool(event.get('kind') == 'reconnect' and event.get('accepted'))
        for check in trace.get('ds15_auto_depth_checks', []):
            out['automatic_edge_checks'][check['reason']] += 1
            out['automatic_vetoes'] += bool(check['veto'])
    for birth in rows(public / 'BIRTHS.jsonl.gz'):
        out = result[birth['arm']]
        out['birth_stage_status'][birth['status']] += 1
        out['birth_query_status'].update(q['status'] for q in birth['queries'])
    for arm in STATE_ARMS:
        result[arm]['automatic_physical_counts'] = automatic['counts'][arm]
        if arm not in EVENT_ARMS:
            continue
        values = events[arm]
        result[arm].update(suspects=len(values), confirmed=sum(e['confirm_frame'] is not None for e in values),
            first_splits=sum(e['q'] is not None for e in values),
            event_status=dict(Counter(e['status'] for e in values)),
            group_admission_reason=dict(Counter(e['numeric']['detail'].get('reason', 'NO_REASON')
                for e in values if e.get('numeric'))),
            group_restore_status=dict(Counter(e['restore']['status'] for e in values if e.get('restore'))),
            group_commits=sum(bool(e.get('restore') and e['restore']['status'] == 'COMMIT') for e in values),
            group_physical_counts=audit[arm]['group_physical_counts'],
            birth_physical_counts=audit[arm]['birth_physical_counts'])
    changed = {base: 0 for base in BASES}
    for row in rows(public / 'predictions.jsonl.gz'):
        for base in BASES:
            changed[base] += row['variants']['Z4Q_DEPTH'] != row['variants'][base]
    for out in result.values():
        for key, value in list(out.items()):
            if isinstance(value, Counter):
                out[key] = dict(value)
    source = read(input_dir(name) / 'SOURCE_MANIFEST.json')['coverage']
    return dict(arms=result, depth_changed_frames_vs=changed, raw_core_coverage=source,
                execution=read(public / 'RUN_SUMMARY.json'))


def table(headers, values):
    return ['| ' + ' | '.join(headers) + ' |', '|' + '|'.join(['---'] * len(headers)) + '|'] + [
        '| ' + ' | '.join(str(x) for x in row) + ' |' for row in values]


def main():
    assert not (HERE / 'SUMMARY.json').exists() and not (HERE / 'RESULTS.md').exists(), 'Append-only completed report'
    checked = integrity()
    scored, provenance = read(RUN / 'METRICS.json'), read(RUN / 'SCORE_PROVENANCE.json')
    assert scored['frames'] == 20098 and provenance['reference_opened_after_all_seals']
    assert provenance['masked_or_ignored_ids'] == 0 and not provenance['GT_used_for_predictions']
    verify_item(provenance['scorer'])
    verify_item(provenance['scoring_freeze'])
    verify_item(provenance['prediction_parity'])
    detail = {name: counts(name) for name in SEGMENTS}
    units = {name: scored['segments'][name]['metrics'] for name in SEGMENTS if not name.startswith('feeding_')}
    units['Feeding_pooled1471'] = scored['feeding_pooled']['metrics']
    numeric = {}
    for name, values in units.items():
        depth = values['Z4Q_DEPTH']
        numeric[name] = dict(deltas={base: {field: depth[field] - values[base][field] for field in FIELDS} for base in BASES},
            exceeds_native_IDF1=depth['IDF1'] > values['SAM3_NATIVE']['IDF1'],
            exceeds_original_Z4Q_IDF1=depth['IDF1'] > values['Z4Q_FROZEN']['IDF1'],
            exceeds_shared_IDF1=depth['IDF1'] > values['Z4Q_SHARED']['IDF1'],
            HOTA_AssA_non_degraded_vs_native_and_original=all(depth[field] >= values[base][field]
                for field in ('HOTA', 'AssA') for base in ('SAM3_NATIVE', 'Z4Q_FROZEN')),
            numerical_observation_is_not_physical_method_success=True)
    records = list(rows(HERE / 'EXECUTION_LOG.jsonl')) if (HERE / 'EXECUTION_LOG.jsonl').exists() else []
    formal = [r for r in records if r['exit_code'] == 0 and any(Path(x).name == 'guard.py' for x in r['command'])
              and 'run' in r['command']]
    cpu = dict(policy=read(HERE / 'EFFECTIVE_RUNTIME.json'), formal_replay_records=formal,
        summed_formal_process_seconds=sum(r['elapsed_seconds'] for r in formal),
        summed_segment_replay_seconds=sum(d['execution']['elapsed_seconds'] for d in detail.values()),
        scorer_including_source_verification_seconds=scored['elapsed_seconds'],
        peak_resident_RAM='UNMEASURED', GPUs_used=0, server_jobs=0, model_http=0, model_cost_usd=0,
        execution_records_available_at_summary=len(records))
    if formal:
        cpu['formal_replay_wall_seconds'] = (max(datetime.fromisoformat(r['finished_utc']) for r in formal) -
            min(datetime.fromisoformat(r['started_utc']) for r in formal)).total_seconds()
    summary = dict(status='COMPLETE_POSTSEAL_NUMERIC_AND_INTEGRITY_REPORT', frames=20098, arms=list(ARMS),
        integrity=checked, main_units=units, numeric_comparisons=numeric, segment_details=detail, resources=cpu,
        all_prediction_seal=artifact(RUN / 'ALL_PREDICTIONS_SEALED.json'), metrics=artifact(RUN / 'METRICS.json'),
        scientific_boundary=dict(depth_necessary='NOT_IDENTIFIED',
            independent_component_attribution='NOT_IDENTIFIED_THREE_DEPTH_CHANGES_BUNDLED',
            physical_depth_accuracy='UNKNOWN', independent_blind_generalization=False,
            loss_prevention_is_not_increment_over_original_Z4Q=True,
            raw_core_usable_is_not_physical_surface_truth=True), new_model_http=0, cost_usd=0)
    write_new(HERE / 'SUMMARY.json', summary)
    output = ['# DS15 Z4Q与深度策略修复结果', '',
        '全部20098帧、八个独立片段、五臂真实状态回放完成后统一评分。全部原始mask、残片、分数、公开ID和负ID保留。'
        '此报告依据封存数字结果，不读取GT或重新运行预测。', '',
        '原Z4Q与R12使用各自冻结代码；SHARED控制共同保护/状态工程，DEPTH增加三项捆绑深度策略。'
        '超过旧R12而仅回到原Z4Q属于能力恢复或止损；新增提点需与原Z4Q和SHARED的实际差值同时判断。'
        '本五臂不能识别深度独立必要性，也不能识别三项增量各自的独立贡献。', '',
        '## 完整五臂指标', '', 'IDF1/HOTA/AssA为百分数；FP/FN及IDSW为计数。Feeding为官方四段命名空间隔离后整体统计。', '']
    output += table(['数据', '分支', *FIELDS], [[name, arm, *(f'{values[arm][k]:.6f}' if k in ('IDF1', 'HOTA', 'AssA')
        else values[arm][k] for k in FIELDS)] for name, values in units.items() for arm in ARMS])
    output += ['', '## DEPTH相对三个同源对照', '', '变化为百分点或计数差；没有跨数据集混合总分。', '']
    output += table(['数据', '对照', *('Δ' + k for k in FIELDS)], [[name, base, *(f'{delta[k]:+.6f}'
        if k in ('IDF1', 'HOTA', 'AssA') else f'{delta[k]:+d}' for k in FIELDS)]
        for name, comparison in numeric.items() for base, delta in comparison['deltas'].items()])
    output += ['', '## Feeding逐段五臂', '']
    output += table(['片段', '分支', *FIELDS], [[name, arm, *(f'{values[arm][k]:.6f}'
        if k in ('IDF1', 'HOTA', 'AssA') else values[arm][k] for k in FIELDS)]
        for name, row in scored['segments'].items() if name.startswith('feeding_')
        for values in [row['metrics']] for arm in ARMS])
    output += ['', '## 实际动作与身份核对', '',
        '联合提交按一次原子事务计；自动提交要求首次发布采用、提交后alias仍有效且未由显式组/出生事务覆盖。'
        '接受的因果预览候选另列，不等同持久提交。表中对/错/未知使用字面bank与public-origin关系，'
        '清洁端点与至少3帧连续同版本共识在各段EVENT_AUDIT单列；UNKNOWN不计正确或安全。', '']
    action_rows = []
    for name, item in detail.items():
        for arm, out in item['arms'].items():
            group, birth, automatic = out.get('group_physical_counts', {}), out.get('birth_physical_counts', {}), out['automatic_physical_counts']
            triple = lambda values: '/'.join(str(values.get(k, 0)) for k in ('CORRECT', 'WRONG', 'UNSCORABLE'))
            action_rows.append([name, arm, out['accepted_causal_preview_candidates'], out['accepted_auto_actions'], out['automatic_vetoes'],
                out.get('group_commits', 0), triple(group), triple(birth), triple(automatic), automatic.get('NOT_FIRST_PUBLISHED', 0)])
    output += table(['片段', '分支', '预览自动接受', '持久自动提交', '深度否决', '组提交', '组对/错/未知', '出生对/错/未知', '自动对/错/未知', '自动未首次发布'], action_rows)
    output += ['', '事件取消、首分离、准入原因、每种出生状态与控制器动作完整计数均保留在SUMMARY.json；'
        '每次切换在各段SWITCHES.json，无效果和不可评分结果均保留。', '', '## 来源、工程验收与资源', '',
        f"旧受保护文件{checked['old_unchanged_files']}项与封存代码/预测/access摘要核验通过。原生及R12全部逐帧映射/事件和指标精确复现；"
        '原Z4Q旧档案接线差异见BASELINE_PARITY与各段original_z4q_archive_diagnostic，属于来源诊断而非性能准入门。', '',
        f"本地最多3个单线程预测进程；正式分段回放累计{cpu['summed_segment_replay_seconds']:.2f}进程秒，"
        f"评分及来源核验{cpu['scorer_including_source_verification_seconds']:.2f}秒。峰值驻留内存未测量。"
        '模型HTTP/训练/SAM3推理/深度补全/GPU/服务器作业均0，模型费用$0。执行命令、日志及退出码保留。', '',
        'FishSA开发8400与已曝光验证2888分别初始化；Feeding仅原四段1471帧，另436帧存在但未纳入；'
        'L3/LW为依赖预测、待人工校正的弱参考。没有独立录像盲测、物理鱼体深度真值或水下表面精度验证。'
        '可用raw core与插件似然不是身份或物理准确率，数值增益不能替代物理映射核对。', '']
    with (HERE / 'RESULTS.md').open('x', encoding='utf-8', newline='\n') as handle:
        handle.write('\n'.join(output))
    write_new(HERE / 'FINAL_CHECKS.json', dict(checked, summary=artifact(HERE / 'SUMMARY.json'),
        report=artifact(HERE / 'RESULTS.md'), scorer_provenance=artifact(RUN / 'SCORE_PROVENANCE.json'),
        report_generator=artifact(__file__), reference_or_prediction_run_by_report=False))
    print('COMPLETE: numeric report and frozen/old byte verification; zero GT/model/predictor reads by summary')


if __name__ == '__main__':
    main()
