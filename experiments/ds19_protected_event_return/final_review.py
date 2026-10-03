"""Final interpretation of the single completed DS19 trial; never new predictions."""
from common import *
from collections import Counter
from report import require_complete, metric_units


def main():
    metric = require_complete()
    summary = read(RUN / 'POSTSCORE_SUMMARY.json')
    coverage = read(HERE / 'ORDER_COVERAGE.json')
    reviews = [HERE / name for name in (
        'POST_SCORE_INTERPRETATION_REVIEW.json', 'PRE_PAIR_DIAGNOSIS.json',
        'DELIVERY_COMPLETE_RECORD_REVIEW.json', 'DIAGNOSTIC_RENDER_REPAIR.json')]
    assert all(path.exists() for path in reviews), 'Finish the independent interpretation first'
    counts = {arm: Counter() for arm in RETURN_ARMS}
    local_cases = []
    for name in SEGMENTS:
        audit = summary['segments'][name]['local_return_audit']
        for arm in RETURN_ARMS:
            counts[arm].update(audit['counts'][arm])
            local_cases.extend({key: item[key] for key in (
                'segment', 'arm', 'event', 'frame', 'global_frame', 'source', 'target',
                'origin_rule', 'physical', 'actual_reference_physical',
                'prior_public_reference_status', 'return_delay_since_first_source_frames')}
                for item in audit['arms'][arm])
    assert sum(counts[arm].total() for arm in RETURN_ARMS) == 3
    q_counts = Counter()
    public_bank = Counter()
    consensus = Counter()
    for item in coverage['dataset_counts'].values():
        q_counts.update(item['selected_choice'])
        public_bank.update(item['first_public_bank'])
        consensus.update(item['first_public_consensus'])
    assert q_counts == {'H0': 50}
    records = list(rows(HERE / 'EXECUTION_LOG.jsonl'))
    finished = {Path(record['command'][2]).name: record for record in records if record['exit_code'] == 0}
    assert all(finished[name]['exit_code'] == 0 for name in ('orchestrate.py', 'score.py', 'report.py'))
    units = metric_units(metric)
    comparisons = {name: dict(
        metrics=unit['metrics'],
        primary_minus_native={k: unit['metrics']['MIXED_RETURN'][k]-unit['metrics']['SAM3_NATIVE'][k] for k in ('IDF1','HOTA','AssA','IDSW','FP','FN')},
        primary_minus_original_z4q={k: unit['metrics']['MIXED_RETURN'][k]-unit['metrics']['Z4Q_FROZEN'][k] for k in ('IDF1','HOTA','AssA','IDSW','FP','FN')},
        repaired_depth_policy_difference={k: unit['metrics']['MIXED_RETURN'][k]-unit['metrics']['ACTIVITY_RETURN'][k] for k in ('IDF1','HOTA','AssA','IDSW','FP','FN')})
        for name, unit in units.items()}
    result = dict(status='COMPLETE_TRIAL_PENDING_ISOLATION_GAP_DEPTH_GOAL_NOT_ACHIEVED',
        layers=dict(
            completion='All eight sources, six columns and independent scoring completed',
            source_and_publication='PASS: source/scalar/ROI/ledger/seal and old-control parity',
            atomic_return='Tested accepted local write sets and immutable publication PASS',
            pending_policy='ENGINEERING_GAP: source-only pending write set can overwrite a competing ordinary target confirmation outside the protected target set',
            input='Raw same source only; 18 weak paired orders and 32 UNKNOWN at 50 first splits',
            shared_return='L3 same event recovered in both RETURN arms; exact original Z4Q metrics recovered',
            depth_increment='No stable positive composite depth policy increment; no ordinal joint COMMIT',
            physical_truth='L3 CORRECT under weak prediction-derived reference; LW UNSCORABLE; depth surface truth UNKNOWN',
            generalization='Reused exposed cohorts; not independent generalization'),
        frames_per_arm=20098, arms=list(ARMS), column_frames=20098*len(ARMS),
        native_observations=sum(read(RUN/name/'public/RUN_SUMMARY.json')['observations'] for name in SEGMENTS),
        comparisons=comparisons, local_return_counts={arm:dict(value) for arm,value in counts.items()},
        local_return_cases=local_cases, S0_choices=dict(q_counts),
        fallback_first_public_bank=dict(public_bank), fallback_pre_consensus=dict(consensus),
        fallback_is_not_joint_COMMIT=True, unique_actual_local_return_source_events=2,
        pending_competition=dict(
            Feeding_ACTIVITY_RETURN=dict(source=38, protected_target=16, ordinary_target=7,
                carry_local_frame=193, first_changed_local_frame=195, first_changed_original_frame=194, changed_frames=6),
            LW_MIXED_RETURN=dict(source=32, protected_target=7, ordinary_target=24,
                carry_local_frames=[949,950,951,952], first_changed_local_frame=952,
                first_changed_original_frame=951, changed_frames=5)),
        timing=dict(formal_prediction_seconds=finished['orchestrate.py']['elapsed_seconds'],
            full_source_checks_and_scoring_seconds=finished['score.py']['elapsed_seconds'],
            report_and_private_return_visuals_seconds=finished['report.py']['elapsed_seconds']),
        new_model_http=0, smoke=0, training=0, sam3_inference=0, completion_service=0, cost_usd=0,
        scientific_files_frozen_no_retune=True, next_trial_not_started=True,
        sources=[artifact(path) for path in reviews]+[artifact(RUN/'METRICS.json'), artifact(RUN/'SCORE_PROVENANCE.json'), artifact(HERE/'ORDER_COVERAGE.json')],
        next_step='Isolate event protected-edge confirmation from ordinary candidate pending; one frozen same-source replay afterward')
    write_new(HERE / 'SUMMARY.json', result)
    lines = ['# DS19 最终复盘：局部止损成立，深度提点未成立', '',
        '## 主判定', '',
        '**COMPLETE_TRIAL_PENDING_ISOLATION_GAP_DEPTH_GOAL_NOT_ACHIEVED**。一次冻结正式试验已完成八段六列，每列20098帧，共120588列帧。'
        'L3追回原Z4Q被保护逻辑挡住的恢复；没有新增超过原Z4Q的稳定深度收益。当前版本封存停止，不追加参数或选择更容易事件。', '',
        '源、ROI、真实标量、版本、测量证据绑定、唯一发布和旧对照复现均通过；19项冻结前单测通过。'
        '评分后发现未accepted保护候选覆盖事件目标集之外普通候选的pending，完整确认隔离合同未通过。'
        '源与已accepted事务检查的PASS不能掩盖此工程缺口。正式完整数字结果保留为该实现的实际表现，'
        '不将它升级为无工程混杂的顺序方法有效/无效证明。', '',
        '## 完整指标与主要比较', '',
        '六列八段的IDF1/HOTA/AssA/IDSW/FP/FN及全部差值见 RESULTS.md、run/METRICS.json。'
        '下表为预先指定MIXED_RETURN；不能事后择优改为ACTIVITY_RETURN。百分指标差值单位为百分点。', '',
        '| 数据 | IDF1 | HOTA | AssA | IDSW | FP | FN | IDF1−同源SAM3 | IDF1−原Z4Q | IDF1−ACTIVITY_RETURN |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for name, item in comparisons.items():
        values = item['metrics']['MIXED_RETURN']
        fields = [f'{values[k]:.6f}' for k in ('IDF1','HOTA','AssA')]+[str(values[k]) for k in ('IDSW','FP','FN')]
        fields += [f'{item[key]["IDF1"]:+.6f}' for key in ('primary_minus_native','primary_minus_original_z4q','repaired_depth_policy_difference')]
        lines.append('| '+name+' | '+' | '.join(fields)+' |')
    lines += ['',
        'Feeding主表是四段1471帧独立ID域汇总；其他数据分别报告，不跨数据集混成一个总分。'
        '当前所有六列mask/count相同，FP/FN也实际相同。L3/LW参考是未经独立验收的预测派生预标注，不能称新盲测或物理深度真值。', '',
        '## 本轮实际修了什么', '',
        '受保护目标的原始D1候选在私有proposal中继续自然矩阵、margin、出生窗和5次确认。'
        '只有自然accepted、来源/版本/anchor/占用/组外写集检查通过后，才以事件局部事务提交真实alias、bank与epoch；'
        '进入参考仍不可变，未恢复成员保持匿名。late q、timeout、局部fallback不复制整套B0，不撤销已提交恢复。'
        '当前帧先commit再唯一发布，过去已发布的新号不改写。', '',
        '该子范围要求来源独占、无当前邻居，实质覆盖D1；原Birth需要邻居见证，尚未由本路由覆盖。'
        '未accepted确认不是身份提交。测量、深度筛选、顺序、阈值、触发、q、二维运动和原输入保持冻结。', '',
        '## 三笔显式局部返回，两件来源事件', '',
        '| 数据/分支 | 原帧 | 来源→public | 相对首次来源发布延迟 | bank物理 | 公共ID原来源 |',
        '|---|---:|---|---:|---|---|']
    for item in local_cases:
        lines.append(f'| {item["segment"]}/{item["arm"]} | {item["global_frame"]} | {item["source"]}→{item["target"]} | {item["return_delay_since_first_source_frames"]}帧 | {item["actual_reference_physical"]} | {item["prior_public_reference_status"]} |')
    lines += ['',
        'L3 local3025/原3024：旧n9@local2712 whole=722.703186 mm，当前n47 whole=678.225586 mm，'
        '残差44.477600/tol60 mm，cost0.748384，原D1自然5次确认。n47首次公开于local2891为47，134帧后恢复9，'
        '跨local3175 TIMEOUT继续自身alias。完整IDF1 +2.318468/HOTA +1.808950/AssA +4.579391；IDSW却+1，'
        '因此不能用切换净数替代全段身份一致性。两分支均等于原Z4Q，是共同事务止损；MIXED−ACTIVITY=0。', '',
        'LW ACTIVITY_RETURN的144→133在原3271提交，实际旧参考与当前观测均无法唯一匹配，维持UNSCORABLE。'
        'IDSW9→8而IDF1不变不能使该例变为正确。所有显式返回均为D1，不与automatic重复计数。', '',
        '## 为什么深度没有产生联合恢复', '',
        'MIXED_RETURN自动95个episode中50个q、45个没有q；episode包括取消/超范围，不能全称真实合并事件。'
        '50个首分离决定全为H0+本分支fallback，实际ordinal joint COMMIT=0。'
        '32个UNKNOWN：16无同帧pre配对、13因果clean pre绑定拒绝、3当前paired depth缺失/非法。'
        '18个可用顺序均为未校准弱代理：11个H0本来最佳，5个joint odds不足，2个无正ordinal支持。', '',
        '真实冻结值：Feeding最早q原170，pre仅一对，Δ=-42.778 mm、gap1.396 s，外推scale897.884 mm、p0.482142，'
        'H1 margin0.089251低于原log9=2.197225。开发q1274，Δ=-101.718 mm、gap9.596 s，scale6168.712 mm、p0.493817。'
        '尺度随间隔迅速变宽，使次序接近无信息；这是当前连续性/噪声模型行为，不证明真实鱼体上下关系变化，也不是物理准确率。', '',
        '保留匿名GROUP混层资料不等于已把它用于有效个体顺序约束；整mask/core中位数顺序仍可能与接触处局部遮挡拓扑不同。'
        '这一轮没有更换表示或调尺度。PRE_PAIR_DIAGNOSIS逐字段保留实际拒绝原因，不将窗口缺口或真实风险强写为clean。', '',
        '13个INVALID_PRE实际逐列失败都是GEOMETRY_FRAME_ABSENT，共199个历史点缺对应几何记录；'
        '11例在前次取消/回退/完成清空manager几何后，DepthState仍保留同key深度片段；2例风险后两种片段错位。'
        '这不等于13例深度源本身错版。16个NO_SAME_FRAME均为被选入最新A/B深度片段真正不共时，'
        '其中14例连几何也不共时，2例几何共时但深度片段不共时。不能跨风险拼接，也不能以GT挑更早好片段。', '',
        '第二层审查区分真实风险与表示损失：两例风险后的错位来自实际POTENTIAL_MIXTURE被mixed门拒绝，'
        '旧深度不能与新几何拼接；另一方面Feeding MS1-F105和验证MS1-F457曾存过同帧合格历史，'
        '却被A/B各自较晚的不共时latest片段覆盖。按时间因果记录共同片段是尚未实现的表达问题，'
        '本轮不重选旧输入，也不据此预报新成绩。', '',
        'fallback首次发布相对bank为30正确/10错误/10不可评分；相对pre片段共识为16/5/29。'
        '这些是原发布诊断，不是模型或ordinal提交成绩。五数据最早未恢复H0控制均生成真实深度/全部邻mask六列前中后图，'
        '没有错误joint提交可选，失败提交图为0；不补造失败。', '',
        '## 未提交也会影响状态：确认竞争', '',
        'Feeding local193，n38→保护16的count1写回pending，覆盖普通n38→7的count3；'
        'ORDER在local195正常接7，RETURN只有count2，195–200六帧仍发布38。'
        '它只有HOTA微变、没有显式local_return，不能算恢复收益。', '',
        'LW local949–952，n32→保护7的确认反复覆盖普通目标24，导致ORDER在952接24、RETURN到957才接24，'
        '五帧差异而完整指标相同。只检查显式提交数会漏掉该副作用。'
        '逐次新/消除切换、共同帧转移变化和真实pending链见POST_SCORE_INTERPRETATION_REVIEW.json及POSTSCORE_SUMMARY.json。', '',
        '## 耗时、复现与交付边界', '',
        f'正式六列回放{result["timing"]["formal_prediction_seconds"]:.3f}秒；完整来源检查与评分{result["timing"]["full_source_checks_and_scoring_seconds"]:.3f}秒。'
        '本地最多六个单线程片段作业，CUDA空；不代表实时部署。模型HTTP/smoke/训练/SAM3推理/补全服务/费用全部0。', '',
        '旧5618个锁定文件未改，82冻结依赖与123正式封存文件完整。八段事务11块，最大73438610 bytes；'
        '完整记录不截断。SOURCE_OLD、原depth_mm/source_index与同源SAM3保存源及DS18封存当帧测量缓存均保留真实依赖。', '',
        '初始化曾直接执行并成功，ENVIRONMENT_INITIAL与CONFIG_INHERITANCE保留；不伪造不存在的初始化stdout日志。'
        '冻结前第一次测试的序列化错误与后续成功记录保留。正式回放/评分一次通过；'
        '仅封存后控制绘图曾因无序读取失败，排序后重跑，日志及可反向核验的诊断源码副本见DIAGNOSTIC_RENDER_REPAIR。'
        'TrackEval可选BURST导入提示缺tabulate不影响本轮官方CLEAR/Identity/HOTA，旧四对照逐帧和数值完全相同。', '',
        '公共交付包括代码、配置、测试、完整数字预测/事务/调用与耗时记录、逐事件评分、报告和聚合指标图。'
        '实际深度/mask图与原始私人输入仅列RESTRICTED_ARTIFACTS真实路径、字节、SHA和复现依赖，图不进入Git；'
        '不公开RGB、GT raster或凭据。远端提交/ref/blob结果写REMOTE_VERIFICATION，最终main在交付后再次实际核验。', '',
        '## 唯一下一步', '',
        '隔离受保护边与普通候选的确认进度，使未accepted事件proposal不能覆盖普通pending；'
        '保留原矩阵/阈值/出生窗与自然接受，再做一次同源冻结验证。具体范围见NEXT_STEP_PLAN.md。'
        '本轮没有执行该下一轮，没有自动加大模型。', '']
    with (HERE/'FINAL_REVIEW.md').open('x',encoding='utf-8',newline='\n') as f:
        f.write('\n'.join(lines))
    plan = '''# 唯一下一步：隔离事件边确认与普通候选确认

状态：仅规划，未启动。DS19正式版本已完整运行并封存；不得覆盖其源码、输入、预测、评分或seal。

## 依据与唯一变量

DS19两处真实链证明，未accepted的保护候选把自己的target/count写入普通pending[native]，重置另一目标的确认：Feeding38→16对普通7产生6帧延迟，LW32→7对普通24产生5帧延迟。显式提交为零仍可产生发布差异，现有19项测试没有涵盖这一竞争。先解决这一实际状态问题，防止未来深度提案通过确认副作用改变普通Z4Q。

下一轮只将事件保护边的确认状态与普通pending分开，并按event generation/source generation/精确旧anchor/target区分。普通路线继续自己的自然矩阵与确认；受保护边只推进实际当帧符合原资格的候选。两者不能互相重置，也不能把被普通合法重接后失效的事件候选继续提交。不会更改深度质量、whole/core/ordinal、q、trigger、候选物理含义、权重、出生或first_eligible时限，不以GT挑新样本。

## 必要检查与正式验证

直接复现Feeding local193–200与LW949–957竞争切片，验证事件未accepted时普通确认与return-off完全相同；版本/anchor/占用变化切断事件确认、真实超时仍生效。L3原3024自然5次确认恢复、进入参考不变、跨timeout持续alias、失败/preview/异常不污染组外仍须保持。未知与无neighbor范围照旧，不能宣称Birth已覆盖。

随后仅一次八段六列同源全段：SAM3_NATIVE/Z4Q_FROZEN、当前冻结ACTIVITY_RETURN/MIXED_RETURN归档、以及对应确认隔离后的两个新分支。每列继续自己的真实状态，预测全封存后用相同官方评分与实际anchor审计。汇报两处竞争是否消失、L3止损是否保留、逐次新增/消除切换及完整IDF1/HOTA/AssA/IDSW/FP/FN；不只看净IDSW、不将不可评分算安全。

这是确认状态修复验证；即使工程通过，也不自动证明深度增量。修复后组合深度−相同底座活动分支、同源SAM3及原Z4Q分别比较。若深度提点仍未成立，完整交付并停止该冻结版本，不滚动放宽顺序scale或log-odds至命中。模型HTTP/smoke/训练/SAM3推理/补全费用继续0；不自动执行下一方案。

所有产物在新目录，完整日志/预测/评分/分析/可公开图同步main，真实私有像素仅保留受限清单。实际push并读取远端ref和文件验证。PRE_PAIR_DIAGNOSIS与未校准宽scale的事实保留为后续研究边界，本计划不顺带改这两个方法问题。
'''
    with (HERE/'NEXT_STEP_PLAN.md').open('x',encoding='utf-8',newline='\n') as f:
        f.write(plan)
    print('DS19 final interpretation written; next trial not started; model HTTP/cost = 0')


if __name__ == '__main__':
    main()
