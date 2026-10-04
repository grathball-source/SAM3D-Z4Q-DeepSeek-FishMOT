"""Postseal interpretation and complete metrics; no tracking or parameter changes."""
from common import *
from collections import Counter

def table(metrics):
    lines=['| 分支 | IDF1 | HOTA | AssA | IDSW | FP | FN |','|---|---:|---:|---:|---:|---:|---:|']
    for arm,m in metrics.items():lines.append(f'| {arm} | {m["IDF1"]:.6f} | {m["HOTA"]:.6f} | {m["AssA"]:.6f} | {m["IDSW"]} | {m["FP"]} | {m["FN"]} |')
    return '\n'.join(lines)

def main():
    metrics=read(RUN/'METRICS.json');review=read(HERE/'INPUT_REVIEW.json');assert review['status']=='PASS'
    segments=metrics['segments'];counts=Counter();partner=Counter();measurement=Counter();physical=Counter();weak=[];actual_events=[]
    totals=dict(frames=0,objects=0,changed_frames=0,veto_checks=0,checks=0,measured_objects=0)
    for name in SEGMENTS:
        s=read(RUN/name/'public/RUN_SUMMARY.json')
        for k in totals:totals[k]+=s[k]
        counts.update(review['segments'][name]['evidence_reasons']);partner.update(review['segments'][name]['partner_reasons']);measurement.update(review['segments'][name]['measurement_reasons'])
        assert segments[name]['metrics'][ARMS[1]]==segments[name]['metrics'][ARMS[2]]
        for a in read(RUN/name/'public/ACTION_AUDIT.json')['actions']:
            physical[(a['arm'],a['physical'])]+=1;actual_events.append(dict(segment=name,**a))
        for r in rows(RUN/name/'public/ORDER_CHECKS.jsonl.gz'):
            for x in r['checks']:
                for c in x['comparisons']:
                    if c.get('reason')=='WEAK_PROPAGATED_OR_CURRENT_ORDER':
                        weak.append(dict(segment=name,frame=r['frame'],global_frame=r['global_frame'],source=x['native_id'],target=x['public_id'],
                            partner=c['partner_native'],last_pre=c['calculated_pre'][-1],p_pre_at_q=c['pre_probability_A_nearer_at_q'],
                            p_post=c['current_probability_A_nearer'],gap_seconds=c['real_gap_seconds'],pre_span_seconds=c['real_pre_span_seconds'],
                            pre_scale_at_q_mm=c['pre_scale_at_q_mm'],current_delta_mm=c['current_delta_B_minus_A_mm'],current_scale_mm=c['current_scale_mm']))
    assert totals['frames']==20098 and totals['changed_frames']==totals['veto_checks']==0
    result=dict(status='ENGINEERING_COMPLETE_NO_EFFECTIVE_ORDER_EVIDENCE_NO_INCREMENT',totals=totals,
        inherited_automatic_physical_counts={a:{k:physical[a,k] for k in ('CORRECT','WRONG','UNSCORABLE','NOT_DURABLE') if physical[a,k]} for a in ARMS[1:]},
        evidence_reasons=dict(counts),partner_reasons=dict(partner),measurement_reasons=dict(measurement),weak_numeric_comparisons=weak,
        new_relative_order_commits=0,discarded_original_correct_recoveries=0,method_capacity='INCONCLUSIVE_NO_DECISIVE_PROXY_PAIRS',
        depth_independent_increment='ZERO_FOR_THIS_FROZEN_RULE; ORIGINAL_Z4Q_GAIN_NOT_ATTRIBUTED_TO_DS24',
        engineering='PASS',input_source_contract='PASS',effective_order_coverage='NONE',new_model_http=0,cost_usd=0)
    write_new(HERE/'RESULTS.json',result);write_new(HERE/'ACTUAL_AUTOMATIC_ACTIONS.json',dict(actions=actual_events,new_interventions=0,old_results_not_rewritten=True))
    sections=['# DS24最终复盘：原Z4Q上的相对深度顺序反证',
        '## 主判定与边界',
        '**ENGINEERING_COMPLETE_NO_EFFECTIVE_ORDER_EVIDENCE_NO_INCREMENT。** 完整8段、20,098帧三分支真实状态回放和统一评分完成；新增反证提交0，发布改变0。新分支逐帧、逐mask、逐公开映射与原Z4Q相同；原bank、alias、pending、出生和返回状态的哈希也逐帧相同。本轮没有退化，也没有深度增量。原Z4Q超过Native的部分全部属于原底座。',
        '工程链通过、来源合同通过；有效顺序覆盖为零。不能把这次结果解释为“深度不可能提点”或“上下关系方法已被完整否定”：实际没有一次满足当前可靠性条件的顺序反证。也不能把零误杀称为反证有效，因为没有实际干预。当前冻结规则停止，不据评分放宽阈值。',
        '## 完整指标',
        '指标单位为百分数，差值为百分点。所有分支使用同一原始SAM3保存源和未改mask；D1/Birth/返回隔离等原策略保留。所有预测及访问封存后才加载参考。没有忽略负ID、残片、重复mask或任何ID。']
    sections+=['### Feeding四段汇总（1,471帧）',table(metrics['feeding_pooled']['metrics'])]
    for name,v in segments.items():sections+=['### '+name+f'（{v["frames"]}帧）',table(v['metrics'])]
    sections+=['L3/LW参考来自未独立验收、预测衍生预标注，作为弱诊断单列；较大FP不据此宣称跨数据集泛化。其余也是此前曝光开发/验证片段，不是新的盲测。',
        '### 与两种基线的差值',
        '| 来源 | 本轮−Native IDF1 | 本轮−Native HOTA | 本轮−Native AssA | 本轮−Native IDSW | 本轮−原Z4Q 全指标 |',
        '|---|---:|---:|---:|---:|---|']
    groups={'Feeding四段':metrics['feeding_pooled']['metrics'],**{n:segments[n]['metrics'] for n in SEGMENTS if not n.startswith('feeding_')}}
    for n,v in groups.items():
        a,b=v[ARMS[0]],v[ARMS[2]];sections.append(f'| {n} | {b["IDF1"]-a["IDF1"]:+.6f} | {b["HOTA"]-a["HOTA"]:+.6f} | {b["AssA"]-a["AssA"]:+.6f} | {b["IDSW"]-a["IDSW"]:+d} | 全部0 |')
    sections+=['Feeding相对Native原本有额外24次IDSW；本轮相对原Z4Q新增0次。这些切换未被新模块制造，也未被修复，完整逐切换记录在各段SWITCHES.json。',
        '## 反证为什么没有起作用',
        f'共{totals["checks"]:,}次候选入边检查、{review["partner_comparisons"]:,}次伙伴比较；这些是重复时刻和候选检查数，不是独立交互事件数。全部伙伴结果UNKNOWN。前置的真实版本、同步历史和当前风险条件，不等同于“人工/数值先通过科研指标”的资格评审。',
        '| UNKNOWN原因 | 次数 |','|---|---:|']
    for reason,count in partner.most_common():sections.append(f'| {reason} | {count} |')
    sections+=['原始历史与当前claim版本变化、群组/接触及残片风险首先使许多伙伴不可比较。目标精确bank锚点的双方连续同步历史也常不足5帧，不能跨接触把分散的clean_count拼成连续身份历史。8400和2888两段的候选在这些来源/配对条件就全退回UNKNOWN，本轮没有对这两段建立有效深度顺序比较；不是证明其原始深度总体较差。',
        f'仍实际读取并封存了{totals["measured_objects"]:,}个对象测量：759个有单一合格局部背景相对支持，1,009个无合格支持，32个背景残差过宽、24个独立支持相对原mask不足、3个多合格层、2个反向混合支持、1个合并不确定性过宽。非零深度覆盖并不保证鱼体归属。759个支持也只是可用代理，不能直接称鱼体准确率。',
        '817次已构造真实配对测量的比较历史支持不足，68次当前支持不足，剩余36次进入完整数值顺序计算但仍较弱：6次当前顺序强、历史弱，30次历史与当前都弱。没有任何可信反转被强行当作物理错误。',
        '### 真实案例F548：当前可分，历史仍不能证明身份次序',
        'Feeding第二段local198/global548：候选n86→p15，伙伴n66。固定bank参考global372（local22），最后pre相对深度B−A=−27.0908mm，合成尺度35.3427mm，参考当时的p(A更近)=0.2431，已经不是强顺序。只用0.266秒连续片段外推5.848秒，尺度扩至468.1899mm，p变为0.4783。当前B−A=−213.3448mm、尺度46.4418mm，p=0.00504，当前次序清楚；仍不足以反证一个从未清楚建立的过去次序。去掉时间不确定性也不会自动让过去次序可靠。这些概率是未校准连续性代理，不是物理置信度验收。',
        '### 真实案例L3 global900：双方深度差本身接近噪声尺度',
        'local901/global900：n23→p14，伙伴n9。最后pre差10.5814mm、尺度31.2566mm，参考概率0.6240；间隔3.977秒后尺度285.6128mm，概率0.5139。当前差−22.0378mm、尺度30.1300mm，概率0.2525。中位数符号改变不能当作上下身份翻转。',
        '### F159：与前轮一致保留缺证据',
        '真实F159实际提交为n26→p16（D1_DELAYED），旧anchor为global14/local15的n16，独立事后评分判WRONG；p8是另一候选，不能混写成该帧的实际动作。新模块对p16的伙伴分别遇到当前几何风险、同步历史不足或generation/epoch变化，仍保留原错误恢复。原SAM3目标mask在RGB中贴近鱼体，原深度却多为背景兼容；先前DS23已核验坐标合同，未发现可唯一修正的几何错误。真实raw端点单测确认n26没有合格局部支持，未编造鱼体深度。图中实际公开ID与TRANSACTIONS逐帧绑定。',
        '## 实际恢复与误杀',
        '新增相对顺序提交0，原正确恢复误杀0；两者都源自零有效反证。原Z4Q两分支保留同样90次实际自动提交，严格物理审计15正确、17错误、58不可评分（实际旧参考端点与公共出生来源分列）。17个旧错误也没有被修好；原来不可评分的不能变成安全成功。完整记录见ACTUAL_AUTOMATIC_ACTIONS.json和各段ACTION_AUDIT.json。',
        '## 可视化与封存证据',
        'PRIVATE_VISUALS.json列出实际生成的原bank参考、风险中帧、当前帧三分支发布对照和原始深度。图中ID是已封存发布claim，不是GT身份。像素只留本地，公开的是来源路径、字节、SHA和数值映射。没有改画历史输出以隐藏错误。',
        '主要证据：RUNTIME_FREEZE.json；run/ALL_PREDICTIONS_SEALED.json；INPUT_REVIEW.json；run/METRICS.json；各段TRANSACTIONS/ORDER_CHECKS/MEASUREMENTS/ANONYMOUS_RISK/PUBLISH_LEDGER；13项必要测试、真实200帧禁用/开启前缀和两个真实矩阵入口测试。预冻结两处技术问题及原FAIL记录保留，正式批次没有代码/参数滚动修改。',
        '## 费用、复现和未完成边界',
        '新增模型HTTP、smoke、训练、SAM3推理、补全服务和费用全部0。完整回放四个单线程CPU作业，端到端生成耗时见EXECUTION_LOG.jsonl；既有SAM3推理和采集耗时不计入当前回放，不称实时部署。',
        '截断合同采用原配对帧及其RGB时间坐标，传感器delta_us逐次记录；原深度配对可能比RGB时间晚1–2ms，不声称严格同一传感器时刻或零等待。没有读取q之后的配对帧；严格实时传感器闭环和上游保存SAM3是否前视仍未认证。',
        '没有未跑完的授权片段。尚未实现的是深度增量与有效的相对顺序覆盖；水下物理校准、支持归属和弱参考泛化仍未知。本轮无需凭据、权限或服务解阻。旧结果/封存只读。PUBLIC_ARTIFACT_MANIFEST.json、RESTRICTED_ARTIFACTS.json及REMOTE_VERIFICATION.json给出交付与实际远端核验。',
        '## 唯一下一步（尚未执行）',
        '保持原Z4Q底座，检验**接触局部的双层空间证据**：在实际交互ROI保留两层匿名支持及其空间归属，用局部次序比较替代整鱼中位数的次序。只改这项反证表示，仍走原两个候选入口、独立状态全段回放；混合层不能直接认证为A/B，不跨风险凑速度，不按GT选层或调到命中。此计划不预报提点，也不在本轮自动执行。']
    blocks=[];table_lines=[]
    for section in sections:
        if section.startswith('|'):table_lines.append(section);continue
        if table_lines:blocks.append('\n'.join(table_lines));table_lines=[]
        blocks.append(section)
    if table_lines:blocks.append('\n'.join(table_lines))
    path=HERE/'FINAL_REVIEW.md';assert not path.exists();path.write_text('\n\n'.join(blocks)+'\n',encoding='utf-8')
    plan=sections[-1]
    (HERE/'NEXT_STEP_PLAN.md').open('x',encoding='utf-8').write('# 唯一下一步：接触局部双层空间反证\n\n'+plan+'\n')
    write_new(HERE/'REPORT_PROVENANCE.json',dict(report=artifact(path),metrics=artifact(RUN/'METRICS.json'),input_review=artifact(HERE/'INPUT_REVIEW.json'),
        original_Z4Q_increment_not_DS24=True,new_model_http=0,cost_usd=0))
    print(json.dumps(result['totals']),flush=True)

if __name__=='__main__':main()
