"""Postseal complete results and one next plan; no rolling selection/tuning."""
from common import *
from collections import Counter
import score

def main():
    score.verify_all();metrics=read(RUN/'METRICS.json');qa=read(HERE/'POSTSEAL_QA.json');assert qa['status'].startswith('PASS')
    totals={a:dict(checks=0,soft_cost_updates=0,changed_frames=0,measurements=0) for a in ARMS[2:]}
    reasons={a:Counter() for a in ARMS[2:]};partners={a:Counter() for a in ARMS[2:]};segments={};actions={a:Counter() for a in ARMS[1:]}
    for name in SEGMENTS:
        public=RUN/name/'public';summary=read(public/'RUN_SUMMARY.json');audit=read(public/'ACTION_AUDIT.json')
        for arm in ARMS[2:]:
            for k in ('checks','soft_cost_updates','changed_frames'):totals[arm][k]+=summary[k][arm]
        for r in rows(public/'MEASUREMENTS.jsonl.gz'):totals[r['arm']]['measurements']+=1
        for r in rows(public/'ORDER_CHECKS.jsonl.gz'):
            for arm,checks in r['checks'].items():
                for x in checks:
                    reasons[arm][x['reason']]+=1
                    for y in x.get('comparisons',[]):partners[arm][y.get('reason','COMPARABLE_MEASURED_ORDER')]+=1
        for a in ARMS[1:]:actions[a].update(audit['counts'][a])
        changes=read(public/'SWITCH_CHANGES.json')
        segments[name]=dict(run_summary=summary,metrics=metrics['segments'][name],actions=audit['counts'],
            switch_changes={a:dict(added=len(v['added']),eliminated=len(v['eliminated']),common=v['common_count']) for a,v in changes.items()})
    no_updates=not any(v['soft_cost_updates'] for v in totals.values())
    no_measurements=not any(v['measurements'] for v in totals.values())
    status='FULL_REPLAY_COMPLETE_NO_COMPARABLE_ORDER_INPUT_NO_INCREMENT' if no_measurements else 'FULL_REPLAY_COMPLETE_NO_COST_INCREMENT' if no_updates else 'FULL_REPLAY_COMPLETE_MEASURED_SOFT_COST_RESULTS'
    result=dict(status=status,frames=20098,arms=ARMS,totals=totals,segments=segments,feeding_pooled=metrics['feeding_pooled'],
        candidate_reasons={a:dict(v) for a,v in reasons.items()},partner_reasons={a:dict(v) for a,v in partners.items()},actual_actions={a:dict(v) for a,v in actions.items()},
        engineering='PASS_EFFECTIVE_STATISTICS_AND_REAL_MATRIX_STATE_FLOW',input='NO_FORMAL_COMPARABLE_ORDER_MEASUREMENTS' if no_measurements else 'CONDITIONAL_ORDER_PROXY_NOT_CERTIFIED_IDENTITIES',
        depth_increment='UNTESTED_AT_MEASUREMENT_FACTOR_LEVEL; SYSTEM_INCREMENT_ZERO' if no_measurements else 'MEASUREMENT_FACTORS_CHANGED_SUPPORTS_BUT_NO_TRACKING_INCREMENT',
        measurement_signal_counts={a:qa['totals_by_arm'][a] for a in ARMS[2:]},
        original_native_and_Z4Q_exact=True,model_HTTP=0,cost_usd=0,uncompleted=['No independent sensor physical accuracy/repeatability calibration','No new blind/generalization validation','No model or training experiment authorized or performed'])
    write_new(HERE/'RESULTS.json',result)
    fields=('IDF1','HOTA','AssA','IDSW','FP','FN')
    lines=['# DS27 深度门槛软关联完整回放报告','',f'主判定：**{status}**。八段20098帧、六分支完整真实状态回放与封存后评分完成。','',
        '## 改了什么','',
        '背景资格旧max(30,3σ)/修订max(10,2σ)，测量floor旧15/修订5毫米，固定2×2。实际统计、五轮背景拟合与资格计算生效，原模块只读；合成及真实旧端点逐字段一致性检验通过。5毫米来自旧PRE229事实q25=3.699向上取5，不是测距精度。原Z4Q既有合法矩阵完成后，在含dummy的固定0.15竞争范围内加入有共同null的相对深度软成本；候选、二维、原深度权重/门槛、触发、q、dummy、确认、事务和mask不变。实际选择进入状态后首次发布，每支独立继续。','',
        '## 工程、输入和研究边界','',
        '工程：必要单测、旧水平实际端点精确复现、禁用200帧完整状态/发布等价、真实205帧片段、六分支真矩阵与真实提交路径检查通过。预测前冻结来源/参数/代码/评分；全部预测和访问封存后读取已曝光评分参考。测试不代表科研提点。','',
        '输入：伙伴当前风险、版本变化、同步历史不足和精确anchor来源逐项检查，不能为了介入跨风险拼接或把匿名观测认证为身份。风险过程保存原观测深度及来源；未知保留。','']
    if no_measurements:
        lines += ['本次正式关联**没有产生任何可比较的pre/q深度测量**。四种政策各自完整回放，但都在测量之前被来源/伙伴/历史合同挡住。数值门槛确已修改并通过真实测量单测，正式2×2的测量因子效果没有获得输入，不能说降低门槛无效，也不能宣称深度理论失败。系统增量是实测0。','']
    if not no_measurements:
        lines += ['本轮共有688条政策×帧×mask正式事实，每策略172条，来自Feeding第四段36/L3 74/LW62。每策略41次完整pre/q比較。唯一有qualified support的事实数为10/22/20/119；C1/S5为120个支持，因为一个mask有两个显著支持不能挑峰。其他三组全部441次配对引用仍为共同null；C1/S5有204次条件pre顺序引用、26次条件当前引用（230），这些是反复引用而非230独立事件。门槛因子确实改善观测资格，不能报告“因子未测试”。','',
            '实际零成本机制：C1/S5的41次比较中40次pre概率中位距0.5小于冻结0.1；唯一达到门槛是Feeding第四段local621/global1821，n191→旧149、partner175，pre550..559、旧anchor559，历史p=.386349550456，而当前候选无唯一显著支持，p_q=.5。所有age attenuation>0，本轮不是时间衰减清零。没有一次同时满足pre顺序门槛和当前非null。','',
            '另外检验了“独立N/面积可能错误惩罚投影重复”的原因：172事实/策略的重复及共享来源排除数均0，所有qualified支持independent_n=inclusive_n；改用inclusive覆盖在此数据精确无变化。C1/S5条件pre原始|CDF−.5|中位.0255482、可靠性乘积中位.9993174，弱pre主要来自真实两mask深度差相对尺度太小，不是覆盖权重。连移除全部coverage衰减的诊断极端也仍只有一个pre够强。这只是封存事实敏感性诊断，没有新跟踪分支，也没有据此调到通过。','']
    lines += ['## 完整指标','', '以下四个soft组合全部逐项报告；相同项不是四份独立样本。IDF1/HOTA/AssA均为百分数；IDSW/FP/FN为计数。','',
        '|来源/片段|分支|IDF1|HOTA|AssA|IDSW|FP|FN|','|---|---|---:|---:|---:|---:|---:|---:|']
    units=[(n,v['metrics']) for n,v in metrics['segments'].items()]+[('Feeding pooled 1471',metrics['feeding_pooled']['metrics'])]
    for name,arms in units:
        for arm in ARMS:
            m=arms[arm];lines.append('|'+name+'|'+arm+'|'+'|'.join(f'{m[k]:.6f}' if k in fields[:3] else str(m[k]) for k in fields)+'|')
    lines += ['', '各修订臂相对同源Native、Z4Q，以及背景/尺度两个因子的一次固定差值，见run/METRICS.json；未将旧405帧源或另一个SAM3保存源混入。L3/LW仍为未独立验收的预测派生弱参考，不能称真实盲测。FishSA/Feeding也是已曝光开发/历史验证参考，不声明新泛化。','',
        '## 真实介入和原因','', '|分支|候选检查|正式测量|非零成本更新|改变发布帧|','|---|---:|---:|---:|---:|']
    for a,v in totals.items():lines.append(f"|{a}|{v['checks']}|{v['measurements']}|{v['soft_cost_updates']}|{v['changed_frames']}|")
    lines += ['', '所有实际既有身份恢复按真实bank reference、原public origin和当前物理匹配分别评分；正确/错误/不可评分分列，不能把原来已错的public标签偶然换回称为正确物理恢复。全部新增/消除切换记录在逐源SWITCH_CHANGES.json，完整切换在SWITCHES.json。净差不等于新增数。','',
        '候选级阻断（各臂相同则这里只展示一臂，完整四臂在RESULTS.json）：','']
    for k,v in reasons[ARMS[2]].items():lines.append(f'- {k}：{v}')
    lines += ['', '伙伴级阻断（同一次候选可能有多个伙伴，不可当作独立事件）：','']
    for k,v in partners[ARMS[2]].items():lines.append(f'- {k}：{v}')
    lines += ['', '解释：成本接近只是一种数值入口，并不等于真正发生身份歧义。它可能漏掉低成本但实际有害的继承，并把深度调用留到伙伴来源已无法认证的时刻。8400开发段没有该范围的竞争行，birth真实竞争也没有覆盖。这是当前入口与完整历史合同的交集不足；不能不断降低测量门槛来掩盖。保留原Z4Q的既有有效恢复，同时单列它相对Native的损害。','',
        '## 证据、可视化与公开边界','',
        '正式MEASUREMENTS.jsonl.gz只包含进入真实输入合同的事实。若它为空，事后失败诊断的深度图和DIAGNOSTIC_ENDPOINTS是明确独立的postseal诊断，不会写回正式输入或评分。固定最早阻断例，原始深度、原mask、全部支持/背景/缺测可追溯；原native仅是来源，候选旧身份是假设。图像只留本地private，PRIVATE_VISUALS与PRIVATE_VISUALS_V2列真实路径/字节/SHA。v1因文字过近追加v2，仅增加16px标题间隔，原图/producer/manifest保留，支持/阈值/案例不变；不公布RGB、GT raster、凭据。','',
        '冻结CONFIG保留了只为兼容旧模块加载所需的旧字段，以及未被新软关联读取的旧空间链说明字段（schema、require_actual_contact_seed、qualified_layer_count等）。这些不是实际生效的新控制；有效policy以RUNTIME_FREEZE的四臂measurement参数、soft_controller/evidence代码与本报告为准。旧空间链未执行。门槛15/5与原Z4Q的risk_floor15是不同量。','',
        '模型HTTP、smoke、补全、训练、新SAM3、GPU/服务器、费用均0。运行是离线保存输入CPU回放，不是实时部署。全部日志和失败/零结果保留；旧科学目录/seal不变。源码和公开数值将普通提交并推送main，实际远端验收记在REMOTE_VERIFICATION。','',
        '## 未完成边界和唯一下一步','',
        '未证明深度增量、物理测距精度或盲测泛化；不自动加入大模型。停止当前冻结入口的继续门槛搜索。唯一下一步：把深度进入条件从“原成本接近”改为“预测交互风险”，检验其覆盖的历史是否更有顺序信息；来源未知仍保持未知，不跨风险、不改变原Z4Q候选/事务；固定一次覆盖消融后才评价提点。本轮没有启动该下一实验。','']
    with (HERE/'FINAL_REVIEW.md').open('x',encoding='utf-8') as h:h.write('\n'.join(lines))
    plan='''# 唯一下一步（未启动）：预测交互风险驱动的深度入口覆盖消融

本轮四组完整回放交付后，停止只降低测量门槛的重复路线。一次检验将原成本接近0.15作为深度入口的政策，与原预测接触/失踪风险内全部原合法候选入边比较；复用本轮冻结测量和soft/null规则，不另挑GT事件，不新增LLM/训练/新SAM3。参考来源/版本、原mask/二维/q、候选与真实事务不变，未知仍零成本修正；不将低成本当身份正确，不把观察到风险等同于已认证两个身份。

先从日志核对各阶段可比较历史覆盖、错误/正确原动作的入口覆盖（GT仅事后诊断），把所有失败写为明确UNKNOWN原因；规则与数值一次冻结后完整回放并独立评分，保留原Native/原Z4Q。不按成绩滚动扩大门槛，不预报提点。这个计划尚未启动，需下一条用户指令。
'''
    with (HERE/'NEXT_STEP_PLAN.md').open('x',encoding='utf-8') as h:h.write(plan)
    write_new(HERE/'NEXT_STEP_SELECTION.json',dict(one_next_step='PREDICTED_INTERACTION_RISK_ENTRY_COVERAGE_ABLATION',started=False,
        rationale='Threshold factors improved formal support coverage, but40/41pre medians remain weak and the sole admitted pre has current null; narrow cost entry omits original confident event candidates',new_model_http=0))
    write_new(HERE/'REPORT_PROVENANCE.json',dict(results=artifact(HERE/'RESULTS.json'),metrics=artifact(RUN/'METRICS.json'),
        qa=artifact(HERE/'POSTSEAL_QA.json'),visuals=artifact(HERE/'PRIVATE_VISUALS.json'),visuals_v2=artifact(HERE/'PRIVATE_VISUALS_V2.json'),report=artifact(HERE/'FINAL_REVIEW.md'),
        plan=artifact(HERE/'NEXT_STEP_PLAN.md'),runtime=artifact(HERE/'RUNTIME_FREEZE.json'),new_model_http=0,cost_usd=0))
    print(status,json.dumps(totals),flush=True)

if __name__=='__main__':main()
