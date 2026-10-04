"""Postseal DS26 report generation from the complete fixed numeric cohort."""
from common import *
from datetime import datetime,timezone

def main():
    check_freeze();r=read(HERE/'RESULTS.json');s=read(RUN/'SUMMARY.json');g=read(HERE/'GATE_DIAGNOSIS.json')
    independent=read(HERE/'INDEPENDENT_REVIEW.json');assert independent['status'].startswith('PASS')
    assert read(HERE/'POSTSEAL_REVIEW.json')['status']=='PASS'
    visual=read(HERE/'PRIVATE_VISUALS.json');assert len(visual['figures'])==15
    assert read(HERE/'VISUAL_REVIEW.json')['status'].startswith('PASS')
    cohorts=read(HERE/'COHORT.json');review=read(HERE/'COHORT_REVIEW.json')
    pre=r['stages']['PRE_ACTUAL_CLEAN_ANCHORS'];post=r['stages']['POST_ACTUAL_GEOMETRY_IDENTITY_UNKNOWN']
    contexts=[]
    for c in r['contexts']:
        contexts.append(f"| {c['segment']} | {c['context_id']} | {c['exact_reference']['anchor']['frame']} / {c['exact_reference']['seed_frame']} | {c['pre_disjoint_sole_proxy_pairs']}/{c['pre_pairs']} | {c['post_disjoint_sole_proxy_pairs']}/{c['post_candidate_pairs']} | {c['seed']['qualified_support_count']} |")
    source=[]
    for name,v in g['segments'].items():
        if not v['unique_actual_mask_facts']:continue
        d=v['mutually_exclusive_diagnostic'];source.append(f"| {name} | {v['unique_actual_mask_facts']} | {d.get('NO_QUALIFIED_SUPPORT_WITH_PARENT_GATES_PASSED',0)} | {d.get('SUBSTANTIAL_UNRESOLVED_SUPPORT',0)} | {d.get('BACKGROUND_MODEL_SCALE_FAILED',0)} | {d.get('SOLE_QUALIFIED_PROXY',0)} | {v['substantial_abs_residual_mm']['median']:.3f} | {v['annulus_contrast_threshold_mm']['median']:.3f} |")
    text=f'''# DS26完整复盘：阶段测量ROI修正与真实可观测性

## 主判定

**工程和来源验收通过；端点覆盖错误修正成立；现有规则下配对深度仍稀少，完整接触链仍为零。没有新的身份恢复或跟踪性能结果。**

本轮是用户“启动”授权的DS25唯一下一步，只读测量固定15个预测参考上下文，不是再次完整跟踪试验。基点`{BASE}`。旧DS25与所有历史封存结果只读。原Z4Q没有修改、身份状态没有写入、新预测0；因此IDF1/HOTA/AssA/IDSW/FP/FN本轮均**未重跑**，不能填写0差值当新成绩，也不能把旧分数复制为DS26。用户最终目标“深度超过原生及保住原Z4Q”尚未实现。

| 层次 | 实际结论 | 边界 |
|---|---|---|
| 工程/来源 | 1116个实际mask事实、468个实际raw帧、651个配对逐项复现 | 同一冻结生产函数复算证明来源与可复现性，不是传感器物理真值 |
| 输入覆盖 | 532个post逻辑配对中旧ROI空346；1064个实际mask均非空 | ROI面积分母、环带样本及平面自然同时变化，不能单说深度数据改善 |
| 匿名支持 | pre 9/119双sole，post 2/532双sole | sole是相对环带代理的匿名支持，身份与前景鱼体仍UNKNOWN |
| 时间链 | 15种子可用双层0；532条完整匿名接触链0 | 不用端点差替代被遮挡鱼的连续观测，不沿用swapped-endpoint veto |
| 性能 | 未做新回放/评分、提交身份0 | 不宣称提点、止损或理论无效 |

## 1. 固定范围与计数纠正

从旧DS25全部带`pre_pairs`的原预测检查选择，无深度/GT/成绩筛选：540条原路径引用，532个严格候选角色/版本配对，15个anchor/partner/seed上下文。8个birth路径与同帧D1重复语义合并，但两条原引用均保留。旧378是相同fact序列的去重数，不是候选配对：空/相同ROI会使多个身份解释共用同一测量序列。

纳入全部119个同步pre时刻（238角色）与全部532个q（1064角色）。15上下文来自Feeding后三段、L3、LW；Feeding第一段与8400/2888段原日志没有这样的合格测量链，保留零上下文，未补造事件。这是同一历史预测队列的诊断，不能声称新数据独立泛化、532个独立事件或未曝光test验证。所有q、reference、candidate、source generation和public epoch照旧。

实际531? **没有该计数。正式逻辑配对严格532**，主报告计数来自`COHORT_REVIEW.json`与全任务集合复核，不从总量推测事件。

## 2. 改了什么

pre与q分别调用原DS25 `measure_region`，ROI为角色实际SAM3原mask，不是外接框，不选最大/最近/最像鱼的深度峰。实际mask/原深度/源index全绑定。接触期全部引用原封存匿名区域，2343个旧唯一事实逐值相同；532语义配对有59513次旧引用，原540路径更高的引用数保留在cohort而不混用计数单位。

保留旧实际常数：深度gap30mm、独立点至少16、比例/覆盖0.2、尺度floor15/max60mm、annulus5/20px、邻域3px、背景点至少64、5次Huber1.5、condition100、对比`max(30,3*background_sigma)`。质量分母包括原ROI所有缺测与重复投影；先按frame-local原传感点去重，整段从未将source index当时序表面对应。二维、两矩阵和事务策略未执行新逻辑。

原生产函数status“恰好两层”继续保留。clean单mask只有一合格支持时，仍可能原status UNKNOWN，但可单列匿名sole proxy：原parent门槛与inclusive/independent一致、无substantial unresolved、恰一个合格支持。没有改生产资格门槛。A/B同帧原点/合格点交集另算，共享不得充当两个角色的独立证据；本固定队列651对交集均0。差值只在两个sole支持且无共享时记录，没有身份veto。

## 3. 身份来源合同

238/238 pre角色符合实际当帧bank anchor和published映射，且绑定原版本。post只通过旧候选入口的geometry/quality/伙伴版本门槛，**不是旧target身份已认证**。540原路径引用中538次当前source实际public不等于候选target；336次当前source是自身q-frame bank anchor、204次不是；partner全部不是q-frame bank anchor。以上统计按原路径，不应直接写成532配对统计。mask有有效深度不能提升身份资格。图中的A/B表示几何角色，原风险和接触区間仍匿名。小残片即使旧几何门槛通过也不自动成为完整鱼体。

## 4. 真正的配对结果

| 统计单位 | pre | post/q |
|---|---:|---:|
| 配对时刻/逻辑候选 | 119 | 532 |
| 角色mask引用 | 238 | 1064 |
| 旧contact ROI为空 | 18 | 346 |
| 实际角色mask为空 | 0 | 0 |
| 角色有一个声明合格支持 | 32 | 79 |
| 两边各sole且无共享原点 | 9 | 2 |
| 含背景兼容支持的角色 | 215 | 1012 |
| 含缺测的角色 | 193 | 810 |
| 实际支持/缺测记录数 | 634 | 2599 |

post合格率2/532=0.376%；pre双sole9/119=7.563%，全部9个来自同一个上下文，不能当9个独立实验证据。它们的绝对标准化差只有0.746–1.202；本轮仅记录符号，不称置信顺序。两条post实测差B−A分别是−250.928mm（global548，sigma63.718）和+86.622mm（global1318，sigma49.756）。标准化差−3.938/+1.741，只是现测支持的差，传播尺度假设未估计共享annulus协方差；没有真值身份证明，没有完成接触链。

### 全部15参考上下文（帧号为local）

| 段 | context | anchor / seed | pre双sole | q双sole | seed合格支持数 |
|---|---|---:|---:|---:|---:|
{chr(10).join(contexts)}

## 5. 深度仍难介入的机制

第一，旧接触窗口在鱼移动后没有覆盖端点真实mask。F432的旧ROI面积0，实际A/B面积525/530且独立点522/504；A仍0合格，B为1合格。覆盖修正确实恢复测量，没有恢复双边可靠证据。旧378个唯一当前ROI空247与本轮532角色配对空346是两种计数，不能互相冲销。

第二，现测mask中很多主支持被标为局部背景兼容。唯一1116个实际frame-mask事实中，原parent及population门槛通过但0合格有906；substantial unresolved114、背景尺度过宽15、sole proxy81。111个角色sole引用来自这81个事实。背景相容意味着与当前环带模型不足以区分，**不等于已经证明是物理背景**；也可能有浅层差、模型污染、mask混合或投影误差。本轮没有GT/物理深度真值来鉴别这些解释。

| 段 | 唯一mask事实 | parent通过但0合格 | substantial unresolved | 背景尺度失败 | sole proxy | 主支持绝对残差中位mm | 对比门槛中位mm |
|---|---:|---:|---:|---:|---:|---:|---:|
{chr(10).join(source)}

原15mm尺度floor使对比门槛最低45mm，而主要支持相对环带残差中位约15–28mm。该逻辑把“明显区别背景”作为可用于关联的前置条件，在本队列形成大量拒绝；这证明筛选机制如何起作用，尚不能证明删掉该条件会改善身份。尤其L3图中鱼形现测支持可见，却大部分被背景兼容标记；可见深度轮廓不等于可测可靠相对秩。

第三，接触观测本身没有完整双层，修端点不能补回未测到的下面鱼。所有15种子保留原事实，仍0个AVAILABLE_TWO_LAYERS。把“每个接触帧必须观测到两层”作为身份连续链条件在这个冻结队列无可用链；这个路线应停止，不能滚动放宽直到命中，也不能把缺测转换成二鱼连续的假观测。

第四，候选属于原Z4Q矩阵假设，而不是已恢复后的完整物理鱼。部分q的source只是小mask残片；背景/碎片都有可能产生稳定深度。深度顺序能否恢复还需真实状态和封存后评分，本轮不允许端点差值直接指定身份。

## 6. 必要检查、真实切片与封存

5组实际生产函数检查通过：单层UNKNOWN但可诊断sole、跨角色duplicate source、背景保留、弱/缺测保留、事实/index/support篡改拒绝。最早固定真实Feeding F432切片：9个完整pre+首q、20个mask事实、69个旧事实、零状态写入。之后在未读新结果之前冻结全部科学文件/cohort/输入/判定，140.342秒完整实际测量结束，随后封存。

封存后独立数值审查3459个新/旧事实，且另一个独立任务构建器逐列重建119/532的整个语义集合。复读468帧原raw+mask复算1116事实、651对三类source集合/交集/差值，全部相等；复算耗时173.445秒。来源/access guard禁止GT/RGB/v3/网络/非原深度字段。所有原raw packet与保存binding一致，没有把对齐camera-Z当作原native camera-Z。

## 7. 全部可视化与一次报告层故障

全部15上下文各4固定阶段，共60个旧ROI节点和90个新端点事实精确复现。图用raw depth与mask，无RGB/GT/补全；完整弱、背景、缺测保留，颜色标几何role而非身份。像素只在`private/`，路径字节SHA见`PRIVATE_VISUALS.json`与`RESTRICTED_ARTIFACTS.json`。总览检查全部15图，四图全尺寸细看；未依据视觉结果重选区域、reference或q。

第一次renderer生成15私有图后，最终公开索引尝试在原guard内读取postseal审查文件，被文件名规则拒绝。已保留失败log和这15图；报告代码将审查artifact在guard安装前绑定，最终版本另存`private/v2`并通过。只修报告收尾，冻结科学代码、数值、阈值和seal未动，没有重测身份或择优结果。两套私有图均库存，不覆盖。

## 8. 调用、同步与未完成边界

技术模型HTTP0、研究模型HTTP0、smoke0、费用0美元。无API key需求、LLM/VLM、补全、训练、SAM3推理、GPU或服务器作业。只有本机单线程CPU旧源读取。正式测量139.363秒内核/140.342秒进程；独立复算172.471秒内核/173.445秒进程。末尾执行日志保留实际每次退出与stdout/stderr SHA。

新增代码、配置、cohort、必要检查、全部公开数字日志/事实/配对/审查/报告提交main；research/HANDOFF与.gitignore仅增量更新。旧科学代码及seal不变，private像素/GT raster/凭据/provider IDs不上传。常规push后实际读取远端main ref和全部公开文件，科学commit由`REMOTE_VERIFICATION.json`记载；最终receipt后的main SHA在实际核验输出与交付消息给出，不在commit前伪填。

未完成的科学目标：没有新身份回放、没有新IDF1/HOTA、没有物理前景/深度精度真值、没有连续双层证据、没有证明深度增量或超过Native。下一计划未执行。公开代码/数字应全部同步，受限像素与输入原数据只列库存和复现依赖。

## 唯一下一步

{(HERE/'NEXT_STEP_PLAN.md').read_text(encoding='utf-8')}
'''
    # No speculative count is published; keep the fixed semantic count only.
    text=text.replace('实际531? **没有该计数。正式逻辑配对严格532**，主报告计数来自`COHORT_REVIEW.json`与全任务集合复核，不从总量推测事件。','主报告计数来自`COHORT_REVIEW.json`与全任务集合复核，不从总量推测事件。')
    with (HERE/'FINAL_REVIEW.md').open('x',encoding='utf-8',newline='\n') as f:f.write(text)
    write_new(HERE/'NEXT_STEP_SELECTION.json',dict(status='PLANNED_NOT_STARTED',title='背景标签与相对深度可测性分离的软关联试验',
        hypothesis='Foreground contrast certification may discard real measurements useful for relative candidate comparison; not yet proven wrong.',
        plan=artifact(HERE/'NEXT_STEP_PLAN.md'),evidence=[artifact(HERE/'RESULTS.json'),artifact(HERE/'GATE_DIAGNOSIS.json')],
        no_new_experiment_started=True,new_model_http=0,cost_usd=0))
    write_new(HERE/'REPORT_PROVENANCE.json',dict(created_utc=datetime.now(timezone.utc).isoformat(),
        code=artifact(Path(__file__)),runtime=artifact(HERE/'FREEZE.json'),
        inputs=[artifact(HERE/n) for n in ('RESULTS.json','GATE_DIAGNOSIS.json','POSTSEAL_REVIEW.json','INDEPENDENT_REVIEW.json','COHORT_REVIEW.json','PRIVATE_VISUALS.json','VISUAL_REVIEW.json','NEXT_STEP_PLAN.md')],
        report=artifact(HERE/'FINAL_REVIEW.md'),model_http=0,cost_usd=0))
    print('Complete fixed-cohort measurement report written; no tracking scores or identity gain claimed')

if __name__=='__main__':main()
