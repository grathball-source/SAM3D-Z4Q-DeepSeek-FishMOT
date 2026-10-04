"""Postseal reporting only: preserve null, negative and mixed results in full."""
from common import *
from collections import Counter
from datetime import datetime, timezone
import argparse

FIELDS = ('IDF1','HOTA','AssA','DetA','IDSW','FP','FN','GT','predictions')
GRADES = ('CORRECT','WRONG','UNSCORABLE','NOT_DURABLE')


def event_key(action):
    return tuple(action[k] for k in ('segment','frame','source','target','origin_rule'))


def verdict(action):
    relations = action['relations']
    expected = ('WRONG' if 'DIFFERENT' in relations.values() else
        'UNSCORABLE' if 'UNKNOWN' in relations.values() else 'CORRECT')
    return expected if action['actual_published'] and action['durable_alias'] else 'NOT_DURABLE'


def veto_summary(name, item):
    return dict(segment=name, **{k:v for k,v in item.items() if k != 'evidence'},
        evidence_sha256=digest(item['evidence']), evidence_reason=item['evidence']['reason'])


def metric_delta(metrics):
    current = metrics[ARMS[2]]
    return {base:{field:current[field]-metrics[base][field] for field in FIELDS} for base in ARMS[:2]}


def classify(results):
    totals = results['totals']; reliable = results['comparison_statuses'].get('CONFLICT',0)+results['comparison_statuses'].get('COMPATIBLE',0)
    if not totals['changed_frames'] and not totals['veto_checks']:
        return ('ENGINEERING_COMPLETE_NO_EFFECTIVE_LOCAL_CHAIN_NO_INCREMENT' if not reliable else
            'ENGINEERING_COMPLETE_LOCAL_COMPATIBILITY_ONLY_NO_INCREMENT')
    if not totals['changed_frames']:
        return 'ENGINEERING_COMPLETE_EVIDENCE_WITHOUT_PUBLISHED_INCREMENT'
    deltas = [v['Z4Q_FROZEN'] for name,v in results['full_deltas'].items() if name not in ('L3','LW')]
    harm = any(d[k] < 0 for d in deltas for k in ('IDF1','HOTA','AssA')) or any(d['IDSW'] > 0 for d in deltas)
    gain = any(d[k] > 0 for d in deltas for k in ('IDF1','HOTA','AssA')) or any(d['IDSW'] < 0 for d in deltas)
    if harm or results['rejected_edge_physical_counts'].get('CORRECT',0):
        return 'ENGINEERING_COMPLETE_EXPOSED_NEGATIVE_OR_MIXED_RESULT_STOP'
    if gain and results['directly_suppressed_original_action_counts'].get('WRONG',0):
        return 'ENGINEERING_COMPLETE_EXPOSED_GAIN_WITH_SUPPORTED_EDGE_EVIDENCE'
    if gain:
        return 'ENGINEERING_COMPLETE_EXPOSED_NUMERIC_GAIN_PHYSICAL_INCREMENT_UNPROVEN'
    return 'ENGINEERING_COMPLETE_CHANGED_STATE_WITHOUT_SUPPORTED_METRIC_INCREMENT'


def collect():
    """Read only finished public records. No tracking, source pixels or GT load."""
    all_seal = read(RUN/'ALL_PREDICTIONS_SEALED.json')
    metrics = read(RUN/'METRICS.json'); review = read(HERE/'INPUT_REVIEW.json')
    assert all_seal['frames'] == metrics['frames'] == review['frames'] == 20098
    assert review['status'] == 'PASS' and review['formal_predictions_sealed']
    assert tuple(all_seal['arms']) == ARMS and metrics['status'] == 'SCORED_AFTER_ALL_EIGHT_PREDICTION_AND_ACCESS_SEALS'
    assert metrics['all_seal'] == artifact(RUN/'ALL_PREDICTIONS_SEALED.json')
    totals = dict(frames=0,objects=0,changed_frames=0,veto_checks=0,checks=0,measured_objects=0)
    evidence = Counter(); partner = Counter(); measurement = Counter(); statuses = Counter(); stages = Counter()
    layer_counts = Counter(); fact_statuses = Counter(); initial_failures = Counter()
    actions = []; vetos = []; source_inputs = []; first_cases = {}; per_segment = {}
    seed_signatures = set(); query_measurement_frames = set(); available_frames = set(); all_fact_frames = set()
    full_metrics = {'Feeding_pooled':metrics['feeding_pooled']['metrics']}
    assert metrics['feeding_pooled']['frames'] == 1471
    for name in SEGMENTS:
        verify_seal(name); verify_item(all_seal['seals'][name]); verify_item(all_seal['access_seals'][name])
        public = RUN/name/'public'; summary = read(public/'RUN_SUMMARY.json'); audit = read(public/'ACTION_AUDIT.json')
        detail = review['segments'][name]; scored = metrics['segments'][name]
        assert scored == read(public/'METRICS.json') and len(scored['changed_frames']) == summary['changed_frames']
        for key in totals: totals[key] += summary[key]
        evidence.update(detail['evidence_reasons']); partner.update(detail['partner_reasons'])
        measurement.update(detail['measurement_reasons']); statuses.update(detail['comparison_statuses'])
        full_metrics[name] = scored['metrics']; facts = {}; local_layers = Counter(); local_status = Counter(); local_failures = Counter()
        for fact in rows(public/'MEASUREMENTS.jsonl.gz'):
            assert fact['fact_id'] not in facts; facts[fact['fact_id']] = fact
            local_status[fact['status']] += 1; all_fact_frames.add((name,fact['frame']))
            if fact['status'] == 'AVAILABLE_TWO_LAYERS': available_frames.add((name,fact['frame']))
            for layer in fact['layers']:
                local_layers['retained_support_records'] += 1
                local_layers['qualified_support_records'] += bool(layer['qualified'])
                local_layers['missing_support_records'] += layer['kind'] == 'MISSING_DEPTH'
                local_layers['background_compatible_support_records'] += layer['background_compatibility'] == 'BACKGROUND_COMPATIBLE'
                local_layers['substantial_unresolved_support_records'] += layer['support_id'] in fact.get('substantial_unresolved_support_ids',[])
            local_layers['missing_roi_pixels_counted_per_fact'] += fact['original_roi_missing_n']
        assert len(facts) == summary['measured_objects']
        fact_statuses.update(local_status); layer_counts.update(local_layers)
        for row in rows(public/'ORDER_CHECKS.jsonl.gz'):
            for check in row['checks']:
                if not check['comparisons']: stages['TARGET_GATE_BEFORE_PARTNER_COMPARISON'] += 1
                for comparison in check['comparisons']:
                    reason = comparison['reason']
                    if 'pre_pairs' not in comparison:
                        stage = 'NO_CONTACT_SEED_BEFORE_MEASUREMENT' if reason == 'NO_ACTUAL_GEOMETRY_CONTACT_SEED' else 'UPSTREAM_PAIR_OR_ACQUIRED_SOURCE_BLOCK'
                    elif comparison['status'] in ('CONFLICT','COMPATIBLE'):
                        stage = 'RELIABLE_CONDITIONAL_LOCAL_CHAIN'
                    elif reason == 'EVERY_FRAME_REQUIRES_EXACTLY_TWO_QUALIFIED_LOCAL_LAYERS':
                        stage = 'LOCAL_MEASUREMENT_COVERAGE_FAILURE'
                    elif reason == 'ENDPOINT_SPATIAL_OWNERSHIP_AMBIGUOUS': stage = 'ENDPOINT_OWNERSHIP_FAILURE'
                    elif reason.startswith('SPATIAL_'): stage = 'CONTINUOUS_SPATIAL_CHAIN_FAILURE'
                    elif reason in ('WEAK_OBSERVED_LOCAL_ORDER','OBSERVED_LOCAL_ORDER_REVERSAL'): stage = 'LOCAL_ORDER_FAILURE'
                    else: stage = 'OTHER_LOCAL_CHAIN_CONTRACT_OR_INPUT_FAILURE'
                    stages[stage] += 1
                    record = dict(segment=name,frame=row['frame'],global_frame=row['global_frame'],
                        source=check['native_id'],target=check['public_id'],origin_rule=check['origin_rule'],
                        partner=comparison['partner_native'],reason=reason,stage=stage,
                        status=comparison['status'],veto=comparison['veto'],anchor=check['anchor'])
                    first_cases.setdefault(reason,record)
                    if 'pre_pairs' not in comparison: continue
                    query_measurement_frames.add((name,row['frame']))
                    seed_signatures.add((name,comparison['actual_contact_seed_frame'],check['anchor']['native_id'],comparison['partner_native']))
                    nodes = [('PRE',x) for x in comparison['pre_pairs']]+[('ANONYMOUS_CONTACT',x) for x in comparison['anonymous_contact']]+[('CURRENT',comparison['current_pair'])]
                    failed = next(((phase,node) for phase,node in nodes if node['status'] != 'AVAILABLE_TWO_LAYERS'),None)
                    if failed is not None:
                        phase,node = failed; local_failures[phase+'/'+node['reason']] += 1
                        first_cases[reason].setdefault('first_unavailable_node',dict(phase=phase,**node))
        initial_failures.update(local_failures)
        for action in audit['actions']:
            action = dict(segment=name,**action)
            assert action['arm'] in ARMS[1:] and action['physical'] == verdict(action)
            assert action['actual_reference_physical'] in ('CORRECT','WRONG','UNSCORABLE')
            assert action['preexisting_public_origin'] in ('MISMATCH','SAME','UNKNOWN')
            actions.append(action)
        vetos.extend(veto_summary(name,x) for x in audit['actual_vetos'])
        per_segment[name] = dict(frames=summary['frames'],objects=summary['objects'],checks=summary['checks'],
            partner_comparisons=detail['partner_comparisons'],veto_checks=summary['veto_checks'],
            changed_frames=summary['changed_frames'],changed_global_frames=scored['changed_frames'],
            measured_objects=len(facts),measurement_statuses=dict(local_status),layer_counts=dict(local_layers),
            first_unavailable_node_reasons=dict(local_failures),comparison_stages=detail['comparison_stages'],
            evidence_reasons=detail['evidence_reasons'],partner_reasons=detail['partner_reasons'],
            measurement_reasons=detail['measurement_reasons'],reference_status=scored['reference_status'],
            elapsed_replay_seconds=summary['elapsed_seconds'])
        source_inputs.extend(artifact(public/f) for f in ('RUN_SUMMARY.json','METRICS.json','ACTION_AUDIT.json',
            'MEASUREMENTS.jsonl.gz','ORDER_CHECKS.jsonl.gz','PREDICTIONS_SEALED.json'))
    assert totals['frames'] == 20098 and len(vetos) == totals['veto_checks']
    for field,current in (('candidate_checks',totals['checks']),('measured_objects',totals['measured_objects']),
                          ('veto_checks',totals['veto_checks']),('changed_frames',totals['changed_frames'])):
        assert review[field] == current
    old = {event_key(a):a for a in actions if a['arm'] == 'Z4Q_FROZEN'}
    new = {event_key(a):a for a in actions if a['arm'] == 'Z4Q_LOCAL_LAYERS'}
    assert len(old) == sum(a['arm'] == 'Z4Q_FROZEN' for a in actions) == 90
    assert len(new) == sum(a['arm'] == 'Z4Q_LOCAL_LAYERS' for a in actions)
    previous = read(ROOT/'experiments/ds24_z4q_relative_order/ACTUAL_AUTOMATIC_ACTIONS.json')
    original = {event_key(a):a for a in previous['actions'] if a['arm'] == 'Z4Q_FROZEN'}
    assert old == original, 'Original 90 actions or physical grades differ from sealed DS24 baseline'
    retained = []; lost = []; additions = []; suppressed = Counter()
    for key,action in old.items():
        if key in new:
            retained.append(dict(original=action,new=new[key],anchor_unchanged=action['anchor'] == new[key]['anchor'],
                strict_grade_unchanged=action['physical'] == new[key]['physical']))
        else:
            direct = [v for v in vetos if event_key(v) == key]
            lost.append(dict(original=action,direct_vetos=direct,
                loss_basis='DIRECT_SAME_EDGE_VETO' if direct else 'DOWNSTREAM_STATE_OR_ASSIGNMENT_CHANGE',
                later_same_source_target_actions=[a for a in new.values() if (a['segment'],a['source'],a['target']) ==
                    (action['segment'],action['source'],action['target'])]))
            if direct: suppressed[action['physical']] += 1
    additions = [action for key,action in new.items() if key not in old]
    physical = {arm:{grade:sum(a['arm'] == arm and a['physical'] == grade for a in actions) for grade in GRADES} for arm in ARMS[1:]}
    reference_physical = {arm:{grade:sum(a['arm'] == arm and a['actual_reference_physical'] == grade for a in actions)
        for grade in GRADES[:3]} for arm in ARMS[1:]}
    rejected = Counter(v['physical_rejected_edge'] for v in vetos)
    deltas = {name:metric_delta(value) for name,value in full_metrics.items()}
    result = dict(totals=totals,engineering='PASS',input_source_contract='PASS',
        full_metrics=full_metrics,full_deltas=deltas,segments=per_segment,
        evidence_reasons=dict(evidence),partner_reasons=dict(partner),measurement_reasons=dict(measurement),
        comparison_statuses=dict(statuses),stage_counts=dict(stages),measurement_statuses=dict(fact_statuses),
        layer_counts=dict(layer_counts),first_unavailable_node_reasons=dict(initial_failures),
        coverage=dict(unique_roi_facts=totals['measured_objects'],
            available_two_layer_roi_facts=fact_statuses.get('AVAILABLE_TWO_LAYERS',0),
            available_two_layer_fact_fraction=fact_statuses.get('AVAILABLE_TWO_LAYERS',0)/max(1,totals['measured_objects']),
            unique_measured_segment_frame_pairs=len(all_fact_frames),unique_available_segment_frame_pairs=len(available_frames),
            unique_query_frames_reaching_measurement=len(query_measurement_frames),unique_contact_seed_signatures=len(seed_signatures),
            unit='ROI_FACT_OR_REPEATED_COMPARISON; NOT_INDEPENDENT_FISH_OR_INTERACTION_EVENT',
            physical_two_fish_accuracy='UNKNOWN',support_ownership_accuracy='UNKNOWN'),
        physical_counts_by_arm=physical,actual_bank_reference_physical_counts=reference_physical,
        rejected_edge_physical_counts=dict(rejected),directly_suppressed_original_action_counts=dict(suppressed),
        original_action_retention=dict(original_actions=90,retained_edges=len(retained),lost_edges=len(lost),
            retained_with_changed_anchor=sum(not x['anchor_unchanged'] for x in retained),
            retained_with_changed_strict_grade=sum(not x['strict_grade_unchanged'] for x in retained),
            newly_added_or_moved_controller_actions=len(additions),retained=retained,lost=lost,new_or_moved=additions),
        actual_vetos=vetos,first_recorded_cases_by_reason=first_cases,
        original_Z4Q_gain_attribution='INHERITED_BASELINE; NOT_DS25_INCREMENT',
        method_capacity='ONLY_THIS_FROZEN_REPRESENTATION_TESTED; NO_GENERAL_DEPTH_IMPOSSIBILITY_CLAIM',
        new_model_http=0,cost_usd=0)
    failure = read(HERE/'FAILURE_REVIEW.json')
    assert failure['status'] == 'SEALED_PREDICTION_ONLY_FAILURE_REVIEW'
    assert not failure['GT_read'] and not failure['metrics_read'] and not failure['core_or_old_results_modified']
    assert failure['INPUT_REVIEW_counts_exact']
    for key, expected in (('frames',totals['frames']),('candidate_checks',totals['checks']),
        ('partner_comparisons',sum(statuses.values())),('unique_measurement_facts',totals['measured_objects']),
        ('actual_veto_checks',totals['veto_checks']),('actual_changed_frames',totals['changed_frames']),
        ('distinct_segment_frames_measured',len(all_fact_frames))):
        assert failure[key] == expected, key
    assert failure['diagnostics']['statuses'] == dict(fact_statuses)
    assert sum(failure['diagnostics']['qualified_count'].values()) == totals['measured_objects']
    assert failure['comparison_reasons'] == dict(partner)
    for item in failure['source_artifacts']: verify_item(item)
    result['failure_review'] = dict(artifact=artifact(HERE/'FAILURE_REVIEW.json'),
        markdown_artifact=artifact(HERE/'FAILURE_REVIEW.md'),
        **{key:failure[key] for key in ('diagnostics','upstream_partner_gate_count','upstream_partner_gate_fraction',
            'upstream_gate_reasons','actual_sequence_reference_occurrences','distinct_whole_fact_sequences',
            'distinct_anchor_partner_seed_reference_contexts','reference_contexts_are_not_independent_biological_events',
            'measurement_citation_occurrences','distinct_facts_cited','repeated_fact_citation_occurrences',
            'per_stage_endpoint_seed','earliest_unavailable_phase_references','earliest_unavailable_phase_distinct_facts',
            'phase_ROI_diagnosis','fixed_chronological_cases')})
    result['status'] = classify(result)
    return result,actions,source_inputs


def table(metrics):
    lines = ['| 分支 | IDF1 | HOTA | AssA | DetA | IDSW | FP | FN | GT | 预测数 |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for arm in ARMS:
        m = metrics[arm]
        lines.append('| '+arm+' | '+' | '.join(f'{m[f]:.6f}' if f in FIELDS[:4] else str(m[f]) for f in FIELDS)+' |')
    return '\n'.join(lines)


def counter_table(values, label='原因'):
    lines = [f'| {label} | 次数 |','|---|---:|']
    lines.extend(f'| {key} | {value} |' for key,value in sorted(values.items(),key=lambda x:(-x[1],x[0])))
    if not values: lines.append('| 无记录 | 0 |')
    return '\n'.join(lines)


def render(result, next_step):
    t = result['totals']; coverage = result['coverage']; retained = result['original_action_retention']
    reliable = result['comparison_statuses'].get('CONFLICT',0)+result['comparison_statuses'].get('COMPATIBLE',0)
    lead = (f'完整8段、20,098帧、{t["objects"]:,}个原mask的三分支独立状态回放、来源核验和统一评分完成。'
        f'新增候选反证{t["veto_checks"]:,}次，发布改变{t["changed_frames"]:,}帧。所有表保留完整指标；原Z4Q相对Native的既有收益不归DS25。')
    if not t['changed_frames']:
        lead += ' 新分支逐帧发布与原Z4Q相同，本轮没有发布层面的增量。'
    if not reliable:
        lead += ' 没有建立可靠的完整局部空间链，完整支持链在真实数据中未被实际连续检验，当前结果不能证明反证有效或其干预安全。'
    lines = ['# DS25最终复盘：接触局部匿名双层空间反证','## 主判定',
        f'**{result["status"]}。** '+lead,
        '当前冻结版停止。不依据评分扩大ROI、放宽阈值、跨风险拼接速度或补写身份历史。有效性、物理身份正确性和曝光参考上的数值变化分别报告。',
        '## 完整指标',
        'IDF1/HOTA/AssA/DetA单位为百分数，差值为百分点；IDSW/FP/FN/GT/预测数为计数。Feeding汇总由四段共同评分计算，未平均分段指标。所有预测及访问先封存，随后加载原参考；未忽略负ID、残片、重复mask或任何公开ID。',
        '### Feeding四段汇总（1,471帧）',table(result['full_metrics']['Feeding_pooled'])]
    for name in SEGMENTS:
        lines += [f'### {name}（{result["segments"][name]["frames"]}帧）',table(result['full_metrics'][name])]
    lines += ['L3/LW为未独立验收、预测衍生预标注的弱参考，单独诊断；其较大FP和得分变化不证明跨数据集泛化。其余也是既有曝光开发/验证片段，均不是新的盲测。',
        '### 新分支相对两种基线的完整差值',
        '| 来源 | 基线 | ΔIDF1 | ΔHOTA | ΔAssA | ΔDetA | ΔIDSW | ΔFP | ΔFN | ΔGT | Δ预测数 |',
        '|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for name,deltas in result['full_deltas'].items():
        for base in ARMS[:2]:
            d = deltas[base]
            lines.append('| '+name+' | '+base+' | '+' | '.join(f'{d[f]:+.6f}' if f in FIELDS[:4] else f'{d[f]:+d}' for f in FIELDS)+' |')
    lines += ['## 证据到行为的覆盖',
        f'共{t["checks"]:,}次候选入边检查、{sum(result["comparison_statuses"].values()):,}次伙伴比较。'
        f'实际形成{t["measured_objects"]:,}个唯一帧×局部ROI事实，其中{coverage["available_two_layer_roi_facts"]:,}个满足匿名双层测量规则。'
        f'合格支持记录{result["layer_counts"].get("qualified_support_records",0):,}条；这些支持可能在多个ROI或查询重复出现，不能换算成鱼数或事件数。',
        f'双层事实占已查询ROI事实的{100*coverage["available_two_layer_fact_fraction"]:.4f}%；分母不覆盖全部20,098帧或所有交互。'
        f'共有{coverage["unique_query_frames_reaching_measurement"]}个查询帧进入测量，{coverage["unique_contact_seed_signatures"]}个种子签名。'
        '种子签名按片段、首次接触帧和原native对去重，仍不是独立物理交互事件。双层可用覆盖不能称物理准确率；背景归属、鱼数和支持身份始终UNKNOWN。',
        '阶段表的TARGET_GATE以候选入边检查计数，其余阶段以伙伴比较计数；两种单位不能直接相加当作事件数。',
        '### 各阶段记录',counter_table(result['stage_counts'],'阶段'),
        '### 完整伙伴结果',counter_table(result['comparison_statuses'],'结果'),
        '### 上游与局部链失败原因',counter_table(result['partner_reasons']),
        '### 局部测量原因',counter_table(result['measurement_reasons']),
        '### 连续链首次不可用节点',counter_table(result['first_unavailable_node_reasons'],'阶段/测量原因'),
        '连续链表按每次候选比较的第一个不可用节点计数；其后各帧测量仍完整保留。其余后续空间对应、端点归属、弱顺序或观察到近远反转的失败在伙伴原因表单列。',
        '| 片段 | 候选检查 | 伙伴比较 | ROI事实 | 可用双层事实 | veto | 改变帧 |',
        '|---|---:|---:|---:|---:|---:|---:|']
    for name,s in result['segments'].items():
        lines.append(f'| {name} | {s["checks"]} | {s["partner_comparisons"]} | {s["measured_objects"]} | {s["measurement_statuses"].get("AVAILABLE_TWO_LAYERS",0)} | {s["veto_checks"]} | {s["changed_frames"]} |')
    failure = result['failure_review']; diagnostics = failure['diagnostics']; phases = failure['per_stage_endpoint_seed']
    lines += ['## 独立失败分层：测量对象与支持链',
        'FAILURE_REVIEW.json/md独立读取封存预测与测量记录，不读GT或评分。其来源摘要在RESULTS与REPORT_PROVENANCE中绑定；下列次级诊断可重叠，不能相加当作事件总数。',
        '### 唯一ROI事实的合格支持数',counter_table(diagnostics['qualified_count'],'合格支持记录数'),
        f'两个合格空间支持的{diagnostics["qualified_count"].get("2",0)}个事实中，'
        f'{diagnostics["primary_reasons"].get("TWO_SPATIAL_PIECES_ARE_NOT_TWO_DEPTH_GAP_LAYERS",0)}个属于同一原始深度gap组的不同空间件；'
        f'最终只有{coverage["available_two_layer_roi_facts"]}个AVAILABLE_TWO_LAYERS事实。不能把空间片数、raw modes或合格支持数当作两鱼标签。',
        '| 次级事实诊断（可重叠） | 唯一事实数 |','|---|---:|',
        f'| 原始ROI面积为0 | {diagnostics["zero_area_roi"]} |',
        f'| 至少一个支持与局部背景代理兼容 | {diagnostics["background_compatible_any"]} |',
        f'| 全部有效支持与局部背景代理兼容 | {diagnostics["all_supports_background_compatible"]} |',
        f'| 有重大噪声或未解决支持 | {diagnostics["substantial_unresolved"]} |',
        f'| inclusive/独立源分组不一致 | {diagnostics["independent_inclusive_partition_disagreement"]} |',
        f'| inclusive/独立源支持资格不一致 | {diagnostics["independent_inclusive_support_disagreement"]} |',
        '### 固定参考上下文的阶段观测',
        f'{failure["actual_sequence_reference_occurrences"]}次序列引用对应{failure["distinct_whole_fact_sequences"]}条去重事实序列、'
        f'{failure["distinct_anchor_partner_seed_reference_contexts"]}个anchor/partner/seed参考上下文。'
        f'{failure["measurement_citation_occurrences"]:,}次测量引用中，{failure["distinct_facts_cited"]:,}个事实唯一，'
        f'{failure["repeated_fact_citation_occurrences"]:,}次为重复引用；这些上下文不是独立生物交互事件。',
        '| 阶段 | 引用次数 | 唯一事实 | 空ROI | 0合格支持 | 1合格支持 | 2合格支持 | 可用双层事实 |',
        '|---|---:|---:|---:|---:|---:|---:|---:|']
    for phase in ('first_pre','last_pre','seed','current'):
        values = phases[phase]; unique = values['unique_fact_diagnostics']; counts = unique['qualified_count']
        lines.append(f'| {phase} | {values["reference_occurrences"]} | {values["distinct_facts"]} | '
            f'{unique["zero_area_roi"]} | {counts.get("0",0)} | {counts.get("1",0)} | {counts.get("2",0)} | '
            f'{unique["statuses"].get("AVAILABLE_TWO_LAYERS",0)} |')
    lines += [f'上游原伙伴门挡住{failure["upstream_partner_gate_count"]:,}/{sum(result["comparison_statuses"].values()):,}次比较'
        f'（{100*failure["upstream_partner_gate_fraction"]:.2f}%），没有为测量绕过这些门。',
        f'当前端点{phases["current"]["unique_fact_diagnostics"]["zero_area_roi"]}/{phases["current"]["distinct_facts"]}个唯一ROI为空'
        f'（{100*failure["phase_ROI_diagnosis"]["current_unique_empty_fraction"]:.2f}%）。'
        '这是冻结实现采用有界接触窗口测量clean端点时的测量对象错位证据；已核验实现确实按该窗口计算，不能改称端点拷贝失败或声明与执行不一致。',
        '修正clean端点ROI也不能自动建立连续链：固定种子及端点事实均未有两个合格支持；contact阶段的层可观测性仍须单独验证。独立源与inclusive一致性门在本次未出现分歧，不能解释零完整链。没有连续空间链时不能复用swapped-endpoint veto来认证身份。',
        '### 两个固定时间顺序案例',
        '| 片段/query | 候选native→public | 伙伴 | seed帧 | 阶段 | local帧 | ROI面积 | 独立点 | 合格支持 |',
        '|---|---|---:|---:|---|---:|---:|---:|---:|']
    for case in failure['fixed_chronological_cases']:
        for phase in ('first_pre','last_pre','seed','current'):
            values = case[phase]
            lines.append(f'| {case["segment"]}/{case["query_frame"]} | {case["native_id"]}→{case["public_id"]} | '
                f'{case["partner_native"]} | {case["seed_frame"]} | {phase} | {values["frame"]} | '
                f'{values["roi_area"]} | {values["independent_n"]} | {values["qualified_layers"]} |')
    lines += ['案例按固定预测上下文列示，无GT选区、无以评分挑层；q82当前窗口为空，同时seed23只有一个合格支持。q110当前窗口非空而支持仍不可用，故不能把全部失败归为空端点。']
    lines += ['## 实际动作与严格物理判定',
        '严格CORRECT要求当前目标、实际bank参考和公开ID出生来源三者全部一致；任一明确不同记WRONG，有未决参考且没有明确不同记UNSCORABLE。未形成真实发布及持久alias的动作单列NOT_DURABLE。实际bank端点正确性与公开ID既有来源错位分别保留，数值涨分不自动等于物理身份恢复。',
        '| 分支 | 严格正确 | 严格错误 | 不可评分 | 未持久提交 |', '|---|---:|---:|---:|---:|']
    for arm,counts in result['physical_counts_by_arm'].items():
        lines.append('| '+arm+' | '+' | '.join(str(counts[g]) for g in GRADES)+' |')
    lines += [f'原Z4Q的90条实际动作已与旧DS24封存记录逐项复现。本轮保留原边{retained["retained_edges"]}条，'
        f'丢失原时点动作{retained["lost_edges"]}条，新增或时点改变的原控制器动作{retained["newly_added_or_moved_controller_actions"]}条。'
        '局部模块只否决候选，不直接提交新身份；后续新增动作不全部称为“深度恢复成功”。丢失动作中的直接同边反证和后续状态/分配变化分开记录，延迟的同源同目标动作保留具体时点。',
        '### 反证边及直接阻止的原动作',counter_table(result['rejected_edge_physical_counts'],'被否决边物理判定'),
        counter_table(result['directly_suppressed_original_action_counts'],'直接丢失原动作严格判定'),
        '被否决的CORRECT边为潜在误杀；只有原分支确实提交该边时才是直接丢失原恢复。零veto不能证明安全，UNSCORABLE不能转为正确。',
        '### 原90条动作逐项去向',
        '| 片段 | global/local | 原source→target | 入口 | 严格物理 | 实际bank参考 | 公开来源 | 本轮去向 |',
        '|---|---|---|---|---|---|---|---|']
    records = [(x['original'],'保留原边'+('；参考改变' if not x['anchor_unchanged'] else '')) for x in retained['retained']]
    records += [(x['original'],'丢失原时点；'+x['loss_basis']) for x in retained['lost']]
    for action,outcome in sorted(records,key=lambda x:event_key(x[0])):
        lines.append(f'| {action["segment"]} | {action["global_frame"]}/{action["frame"]} | {action["source"]}→{action["target"]} | '
            f'{action["origin_rule"]} | {action["physical"]} | {action["actual_reference_physical"]} | {action["preexisting_public_origin"]} | {outcome} |')
    lines += ['完整原/新动作、真实bank锚点、三组关系、所有被否决边、延迟替代和新增动作见RESULTS.json及ACTUAL_AUTOMATIC_ACTIONS.json；原始逐边证据保留在各段ACTION_AUDIT/ORDER_CHECKS，不改写旧输出。',
        '## 增量、限制与复现',
        '原生SAM3是主要比较，原Z4Q是同源机制增量比较。各段及Feeding汇总的相对Native/原Z4Q差值已全部列出；原Z4Q既有收益不计入DS25。局部测量可用、完整唯一空间链、真实候选veto、首发改变和物理可评分纠错属于不同层次。仅在曝光参考上变好、只修复既有公开ID错位，或只减少某较弱分支损害，不能宣称深度独立身份能力已证实。',
        '两层原始支持不等于两条鱼；同一弯曲鱼体、背景、共享投影和掩码混合均可能导致层或空间片。相邻空间双射与df4噪声概率仍是未校准条件代理；观察到真实近远穿越时退回UNKNOWN，source_index不跨帧认证身份。当前完整八段不能证明其他场景或水下物理标定已成立。覆盖不足或零介入只约束本冻结表示，不能称深度理论被否定，也不能称完整局部空间链的物理身份能力已被检验。',
        '来源与公式审计PASS，逐帧ledger/事务/候选入口、完整测量引用、独立源及inclusive统计均核对。公开审计重算空间计数的分数与双射，不冒称重新计算私有像素交集；来源/像素绑定和冻结生产代码另由协议检查保护。',
        '新增模型HTTP、smoke、训练、SAM3推理、深度补全服务与费用全部0。仅四个单线程本地作业回放既有保存mask；各段耗时见RUN_SUMMARY、并发墙钟见EXECUTION_LOG，评分耗时另列。既有SAM3推理不计入本轮回放，不能称实时部署。',
        '查询截止为q；仅读当前配对或此前已经取得的原始数据。sensor delta_us保留，配对可能晚于RGB时间约1–2ms，不能宣称严格同时、零等待或上游SAM3完全无前视。无获授权片段未完成；旧seal/数据/状态只读。',
        '主要证据：RUNTIME_FREEZE.json、run/ALL_PREDICTIONS_SEALED.json、INPUT_REVIEW.json、FAILURE_REVIEW.json/md、run/METRICS.json、各段PUBLISH_LEDGER/TRANSACTIONS/ORDER_CHECKS/MEASUREMENTS/ANONYMOUS_RISK/ACTION_AUDIT、REPORT_PROVENANCE.json。私有图片及参考像素不进入公开报告；具体可视化是否生成、检查与远端交付以相应最终清单为准。',
        '## 唯一下一步（未实施）',next_step['title'],next_step['rationale'],next_step['action'],next_step['limits']]
    blocks = []; table_rows = []
    for line in lines:
        if line.startswith('|'):
            table_rows.append(line)
        else:
            if table_rows: blocks.append('\n'.join(table_rows)); table_rows = []
            blocks.append(line)
    if table_rows: blocks.append('\n'.join(table_rows))
    return '\n\n'.join(blocks)+'\n'


def text_new(path, value):
    with Path(path).open('x',encoding='utf-8',newline='\n') as handle: handle.write(value)


def main(selection_path=HERE/'NEXT_STEP_SELECTION.json', collect_only=False):
    result,actions,inputs = collect()
    if collect_only:
        print(json.dumps(dict(status=result['status'],totals=result['totals'],coverage=result['coverage'],
            stage_counts=result['stage_counts'],physical_counts_by_arm=result['physical_counts_by_arm'],
            action_retention_counts={k:v for k,v in result['original_action_retention'].items() if k not in ('retained','lost','new_or_moved')},
            result_digest=digest(result)),ensure_ascii=False,indent=2)); return result
    selection = read(selection_path)
    assert selection['decision'] in ('PLANNED_NOT_STARTED','STOP_ONLY')
    assert all(isinstance(selection[k],str) and selection[k].strip() for k in ('title','rationale','action','limits'))
    if 'evidence_digest' in selection: assert selection['evidence_digest'] == digest(result)
    for item in selection.get('evidence',[]): verify_item(item)
    result['next_step'] = selection
    write_new(HERE/'RESULTS.json',result)
    write_new(HERE/'ACTUAL_AUTOMATIC_ACTIONS.json',dict(actions=actions,actual_vetos=result['actual_vetos'],
        original_action_retention=result['original_action_retention'],old_results_not_rewritten=True))
    text_new(HERE/'FINAL_REVIEW.md',render(result,selection))
    text_new(HERE/'NEXT_STEP_PLAN.md','# 唯一下一步：未实施\n\n'+selection['title']+'\n\n'+
        selection['rationale']+'\n\n'+selection['action']+'\n\n'+selection['limits']+'\n\n'+
        '本计划依据DS25完整封存结果选定；当前冻结版停止。没有启动下一轮作业、修改旧结果或扩大授权。\n')
    outputs = [artifact(HERE/name) for name in ('RESULTS.json','ACTUAL_AUTOMATIC_ACTIONS.json','FINAL_REVIEW.md','NEXT_STEP_PLAN.md')]
    write_new(HERE/'REPORT_PROVENANCE.json',dict(status='REPORT_AFTER_COMPLETE_SEALS_REVIEW_AND_SCORING',
        created_utc=datetime.now(timezone.utc).isoformat(),reporter=artifact(__file__),selection=artifact(selection_path),
        inputs=[artifact(p) for p in (HERE/'INPUT_REVIEW.json',HERE/'FAILURE_REVIEW.json',HERE/'FAILURE_REVIEW.md',RUN/'METRICS.json',RUN/'ALL_PREDICTIONS_SEALED.json',
            RUN/'SCORE_PROVENANCE.json',ROOT/'experiments/ds24_z4q_relative_order/ACTUAL_AUTOMATIC_ACTIONS.json')]+inputs,
        outputs=outputs,no_prediction_or_parameter_changes=True,new_model_http=0,cost_usd=0))
    print(json.dumps(dict(status=result['status'],totals=result['totals'],report='FINAL_REVIEW.md'),ensure_ascii=False),flush=True)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--collect-only',action='store_true')
    parser.add_argument('--next-step-file',type=Path,default=HERE/'NEXT_STEP_SELECTION.json')
    arguments = parser.parse_args(); main(arguments.next_step_file,arguments.collect_only)
