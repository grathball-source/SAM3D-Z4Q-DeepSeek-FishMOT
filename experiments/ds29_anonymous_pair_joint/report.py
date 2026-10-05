"""Report all outcomes from sealed predictions; no best-branch selection."""
from common import *
from collections import Counter
import math
metrics=read(RUN/'METRICS.json');analysis=read(HERE/'MECHANISM_ANALYSIS.json')
inputs=read(HERE/'INPUT_DIAGNOSIS.json');overlap=read(HERE/'SUPPORT_OVERLAP_AUDIT.json');causes=read(HERE/'CAUSE_AUDIT.json')
fields=('IDF1','HOTA','AssA','IDSW','FP','FN');all_rows=[];summaries={};joint_counts={a:Counter() for a in ARMS[2:]}
for name in SEGMENTS:
    audit=read(RUN/name/'public/JOINT_ACTION_AUDIT.json')
    for a in ARMS[2:]:joint_counts[a].update(audit['counts'][a])
    for a in ARMS:all_rows.append((name,a,metrics['segments'][name]['metrics'][a]))
    summaries[name]=read(RUN/name/'public/RUN_SUMMARY.json')
for a in ARMS:all_rows.append(('Feeding pooled 1471',a,metrics['feeding_pooled']['metrics'][a]))
depth_changed=sum(len(s['depth_vs_geometry_changed_frames']) for s in analysis['segments'].values())
status='FULL_REPLAY_COMPLETE_NO_DEPTH_INCREMENT' if not depth_changed else 'FULL_REPLAY_COMPLETE_DEPTH_CHANGED_STATE_REQUIRES_SOURCEWISE_RESULT'
counts=analysis['counts'];q=counts.get('JOINT_DEPTH/q',0)
result=dict(status=status,engineering='PASS_SOURCE_NULL_VERSION_TRANSACTION_PUBLICATION_AND_FULL_SCORE',
    depth_increment='NO_PUBLISHED_MAPPING_INCREMENT' if not depth_changed else 'ACTUAL_CHANGED_PUBLICATIONS',
    metrics=artifact(RUN/'METRICS.json'),mechanism=artifact(HERE/'MECHANISM_ANALYSIS.json'),
    depth_vs_geometry_changed_frames=depth_changed,joint_physical_counts={a:dict(v) for a,v in joint_counts.items()},
    whole_frames=20098,prediction_branch_frames=80392,scientific_goal='DEPTH_GOAL_NOT_ACHIEVED',
    input_diagnosis=artifact(HERE/'INPUT_DIAGNOSIS.json'),support_overlap=artifact(HERE/'SUPPORT_OVERLAP_AUDIT.json'),
    causal_audit=artifact(HERE/'CAUSE_AUDIT.json'),new_model_http=0,cost_usd=0)
if (HERE/'RESULTS.json').exists():assert read(HERE/'RESULTS.json')==result
else:write_new(HERE/'RESULTS.json',result)
lines=['# DS29 最终复盘：匿名双候选联合关联','',f'主判定：**{status}**。完整八段、四个独立真实状态分支，每分支20098帧，共80392分支帧。主受试列为JOINT_DEPTH；全部预测与访问封存后独立评分，未滚动调整方案。','',
'## 本轮改变与分层边界','',
'当前X/Y同时匿名，不要求B先认证为旧B；A/B来自实际不可变bank anchor的独立clean片段与版本。复用真实OLS及首分离q。深度多个支持按真实独立样本占原ROI比例边际化，未合格/背景/缺测/共享源进入共同null。两候选完整映射都计分，0.25深度权重、0.15联合margin事前冻结；单点post速度UNKNOWN。','',
'保护采用clean/activity隔离；GROUP与post在提交前不认证为个体。D1与Birth在受保护目标/匿名源内等待联合事务，组外原Z4Q继续。取消/超范围/超时不是恢复成功。局部失败只解除本事件保护，不复制B0状态、不改过去输出。原Z4Q对照逐帧复现。','',
'这是同时修正当前匿名解释与共同保护机制的一次试验。JOINT_DEPTH−JOINT_GEOMETRY才反映本轮深度增量，JOINT_*−Z4Q包含保护/联合几何的共同影响。不能把共同收益或损失都归给深度。历史public在进入前可能已错，真实参考恢复正确与最初public来源一致分列。','',
'工程：必要10项状态/数值测试通过，禁用200帧实际状态/输出精确等价，下一固定205帧6次q、3次真实stage。最早200帧无q保留。冻结前发现通用controller模块名碰撞与缺少原矩阵空hook，日志保留，正式冻结前已修复；不能把测试PASS当深度提点。','',
'输入：原保存SAM3/raw depth，同原八段，181842个mask对象未变。Feeding1471帧为四段独立ID域汇总。8400与2888是已曝光开发/历史验证；L3/LW是未经独立验收的预测派生预标注，结论仅为弱参考诊断。未读sealed test、私有RGB、v3或GT实例源；没有训练、GPU、补全、新SAM3、网络模型。','',
'## 完整指标','',
'|数据|分支|IDF1|HOTA|AssA|IDSW|FP|FN|','|---|---|---:|---:|---:|---:|---:|---:|']
for name,a,m in all_rows:lines.append('|'+name+'|'+a+'|'+'|'.join(f'{m[k]:.6f}' if k in fields[:3] else str(int(m[k])) for k in fields)+'|')
lines+=['','## 主受试列的真实差值','',
'百分点为百分指标相减；IDSW/FP/FN为真实计数。','',
'|数据|比较|ΔIDF1|ΔHOTA|ΔAssA|ΔIDSW|ΔFP|ΔFN|','|---|---|---:|---:|---:|---:|---:|---:|']
for name in ['Feeding pooled 1471','fishsa_development_8400','fishsa_validation_2888','L3','LW']:
    ms=metrics['feeding_pooled']['metrics'] if name.startswith('Feeding pooled') else metrics['segments'][name]['metrics']
    for base in ('SAM3_NATIVE','Z4Q_FROZEN','JOINT_GEOMETRY'):
        ds={k:ms['JOINT_DEPTH'][k]-ms[base][k] for k in fields}
        lines.append('|'+name+'|JOINT_DEPTH−'+base+'|'+'|'.join(f'{ds[k]:+.6f}' if k in fields[:3] else f'{int(ds[k]):+d}' for k in fields)+'|')
lines+=['','## 完整事件与实际提交','',
f'JOINT_DEPTH首分离决定{q}次，实际stage {sum(v["joint_stages"]["JOINT_DEPTH"] for v in summaries.values())}次；几何同底座stage {sum(v["joint_stages"]["JOINT_GEOMETRY"] for v in summaries.values())}次。原始DEFER、stage失败、fallback与成功但无映射变化分别保留。',
f'相对两个实际旧参考的已stage联合解释：深度{dict(joint_counts["JOINT_DEPTH"])}；几何{dict(joint_counts["JOINT_GEOMETRY"])}。CORRECT不自动等于修复public原始错误。NO_JOINT_COMMIT不算正确或安全通过。','',
'|数据|深度发现episode|已确认merge|无q|q|已stage|相对Z4Q改变帧|深度−几何改变帧|','|---|---:|---:|---:|---:|---:|---:|---:|']
for name in SEGMENTS:
    s=summaries[name];events=read(RUN/name/'public/EVENTS.json')['JOINT_DEPTH'];c=analysis['segments'][name]['counts']
    lines.append(f'|{name}|{len(events)}|{sum(e["confirm_frame"] is not None for e in events)}|{sum(e["q"] is None for e in events)}|{s["q_decisions"]["JOINT_DEPTH"]}|{s["joint_stages"]["JOINT_DEPTH"]}|{s["changed_frames"]["JOINT_DEPTH"]}|{len(analysis["segments"][name]["depth_vs_geometry_changed_frames"])}|')
lines+=['','## 深度为何起作用或没有起作用','',
f'完整pre/q量测比较{counts.get("JOINT_DEPTH/pre_q_measured_comparison",0)}次，非null顺序代价{counts.get("JOINT_DEPTH/informative_depth",0)}次，改变原始几何选择{counts.get("JOINT_DEPTH/depth_changed_raw_choice",0)}次，最终深度−几何发布差异{depth_changed}帧。下表保留实际缺口，不能把未测当成顺序方法失败。','',
'|计数项|实际数|','|---|---:|']
for k,v in sorted(counts.items()):
    if k.startswith('JOINT_DEPTH/') or k.startswith('qualified_supports_') or k.startswith('measurement_reason_'):lines.append(f'|{k}|{v}|')
lines+=['',
'### 实际证据链的断点','',
'51个首分离q中，34个没有同帧的独立pre对，1个二维参考过期而在量测前退出，5个缺少精确pre参考，剩余11个完成pre/q比较。11个比较中，9个当前端没有合格的独立深度支持对，2个因任一共享来源使整个支持组合进入null。另有一次pre年龄衰减为0；它属于上述11次，不应另加一次。所有q的深度代价均为0，JOINT_DEPTH与JOINT_GEOMETRY在全20098帧上完全相同。','',
'110个实际不同量测中，56个只有一个合格支持、54个没有合格支持，没有实际多合格层案例。旧量测producer的EXACTLY_TWO_QUALIFIED_LOCAL_SUPPORTS_REQUIRED字符串不等于新联合算法要求恰好两个峰；新算法会读取合格支持。多层边际化仅由合成测试验证，本轮真实事件未提供多层能力证据。valid_fraction接近1也不代表鱼体可靠。','',
'Feeding第二段局部q48/原F398：两端合格支持369/308点，均值1026.750/1138.239 mm；仅1个共享原始来源，占0.271%/0.325%，却使整个0.625734支持组合质量作废。L3局部q1421/原F1420：1803/580点、650.737/687.071 mm，20个共享来源占1.109%/3.448%，使0.999446组合质量作废。这是当前保守来源规则的可定位缺陷，尚未执行去掉共享点后的真实重测，不能声称改后已得到有效深度或提点。Feeding该q还有可见残片事务失败，深度更好也不保证提交。','',
'### 共用保护/几何机制为何伤害原Z4Q','',
'8400帧F3902，原Z4Q的BIRTH_REFINE将native7恢复到public0，参考native6@F3836，事后物理与public原来源均正确。新事件的匿名源/保护身份规则使该候选进入WAIT_ANONYMOUS_PAIR_JOINT_TRANSACTION，个体当前深度为空；联合DEFER后首次发布native7为7，错过原正确出生恢复。不是仅改变最后预测文件。','',
'8400帧F4524，pre/current深度概率均0.5，没有深度证据；新联合几何H1仍提交native7→public1、native1→public7。两个实际参考为native1@F4477和native7@F4496，进入前原来源均一致，但两条当前→参考关系均DIFFERENT。这两个错误别名各连续发布3877帧直到段末。此处3877是映射持续长度，不是独立GT错误数；也没有单事件ALLOW/VETO全段反事实来精确分摊指标。原Z4Q同帧映射为native1→1、native7→0。长别名持续解释了净IDSW仅+1却IDF1下降16.562863个百分点的风险。','',
'共同机制也有正确提前恢复：F8035把native8恢复到public2，相对实际native2@F7890正确，早于原D1在F8054的提交19帧；它仍没有深度代价，不能记为深度独有收益。','',
'原Z4Q的90次已提交动作中，新分支44次同帧保留、42次在该帧未保留、1次已有联合恢复、3次在其他帧由原规则提交。42次未保留同时含10次旧正确动作、8次旧错误动作和24次不可评分，不能全部称有害，也不能用净切换增量代替新增/消除明细。实际路径比较不是逐动作独立反事实因果效应。','',
'L3局部F1421的6/9错误联合交换相对弱参考成立，两个别名连续发布1470/2290帧；后续原正确恢复的实际目标历史已改变。LW局部F388的3/6错误交换持续3242/2573帧；其后一次旧正确D1未保留，但当帧边仍合法且没有显式veto，更细确认状态归因保持UNKNOWN。L3/LW参考未独立验收，不将这些关系当物理GT。LW的IDSW下降1但IDF1下降6.295302个百分点，再次说明不能仅以切换数评价身份质量。','',
'因此本轮失败有两个层次：深度输入链没有提供一次实际非null增量；同时保护与无证据时的新几何改号损害了原有状态路径。不能说这些退化由有效深度比较造成，也不能据此否定深度顺序的所有可能用途。当前冻结版结束，不在本轮追加权重/放宽来源门槛再择优。','',
'来源修复消除了“必须先认出稳定伙伴”这个循环前提，但没有补造pre连续性：既有bank anchor仍可能陈旧，两条冻结clean片段可能无共时帧。发生混层时保留各支持，只表示匿名观测分布；背景辨识与局部proxy质量不等于鱼体认证。样本量、覆盖和共同null实际衰减顺序强度，不能把宽尺度或0.5叫作物理准确率。',
'本轮在原事件范围内禁止自动占用保护身份，会改变原Z4Q的出生/延迟恢复时机；长时间未分离或超范围可能错过原出生窗。几何预测只有pre可靠，post一帧没有实测速度。每次切换与新增/消除记录在各段SWITCHES.json、SWITCH_CHANGES.json；不得用净增数冒称恰好新增同样数量错误。','',
'## 逐事件证据与失败可视化','',
'各段JOINT_ACTION_AUDIT.json包含原始选择、事务结果、实际首次发布、相对新参考物理关系与进入前错号；FORMAL_JOINT_DECISIONS.jsonl.gz包含完整候选代价、pre来源、混合支持、共同null与q截止。EVENTS.json保留全部匿名group/residual和无q事件。TRANSACTIONS与PUBLISH_LEDGER逐帧绑定实际状态、决定与预测。','',
'PRIVATE_VISUALS.json记录真实原始深度/mask及四分支合并前、中、q与q后实际发布图。首q、首有效深度、首深度选择变化按时间取；另显示评分后首错误，GT只用于事后类别，未读GT raster或RGB。q后图仅为封存后解释，未用于关联、回填或修改历史。图中灰色局部邻鱼保留，不把掩码颜色当外观信息。','',
'## 耗时、费用与复现','',
f'独立统一评分耗时{metrics["score_seconds"]:.3f}秒。每段实际CPU回放耗时见RUN_SUMMARY，逐帧接收到首次发布延迟见PUBLISH_LEDGER；不是实时部署。新模型HTTP=0、smoke=0、费用=0美元，不需要key。',
'RUNTIME_FREEZE含实际量测和决策常数、旧源码、评分路径、原scanner门槛、输入来源hash。ACCESS阻止GT/RGB/v3/网络，SOURCE_ACCESS记实际字段读取与q截止。旧输出、源码、seal只读。受限输入/图片真实路径、字节、SHA与本机解释器/deps在RESTRICTED_ARTIFACTS；全部公开代码、配置、日志、完整预测、评分与报告main非force同步，远端实际ref/blob核验另记REMOTE_VERIFICATION。','',
'## 未完成边界与唯一下一步','',
'不把弱预标注当盲测，不证明物理深度顺序永恒，不覆盖单事件管理器未管理的并发交互。有效输入下的本次成绩完整保留，当前冻结版结束，不追加权重或挑样本。唯一下一步：回到原Z4Q的完整权威状态，匿名事件历史作旁路证据；无信息时完整状态等价原Z4Q，只对有独立深度证据的合法联合解释提交，并把共享点逐点转入共同null后重测剩余支持。记录在NEXT_STEP_PLAN.md；本轮未执行该后续实验。']
path=HERE/'FINAL_REVIEW.md';content='\n'.join(lines)+'\n'
if path.exists():assert path.read_text(encoding='utf-8')==content
else:path.write_text(content,encoding='utf-8')
# Check each displayed complete metric row against authoritative scoring numbers.
parsed=[x.split('|')[1:-1] for x in path.read_text(encoding='utf-8').splitlines() if x.startswith('|')]
rows_checked=[r for r in parsed if len(r)==8 and r[1] in ARMS];assert len(rows_checked)==36
for r in rows_checked:
    name,arm,*values=r;expected=metrics['feeding_pooled']['metrics'][arm] if name=='Feeding pooled 1471' else metrics['segments'][name]['metrics'][arm]
    assert all(math.isclose(float(v),expected[k],rel_tol=0,abs_tol=5.1e-7) for k,v in zip(fields,values))
for x in rows(HERE/'EXECUTION_LOG.jsonl'):verify_item(x['stdout']);verify_item(x['stderr'])
for p,h in read(HERE/'RUNTIME_FREEZE.json')['code'].items():assert sha(p)==h
write_new(HERE/'REPORT_VALIDATION.json',dict(status='PASS_REPORT_NUMBERS_SEALS_AND_EXECUTION_RECORDS',metric_rows_verified=36,
    report=artifact(path),metrics=artifact(RUN/'METRICS.json'),analysis=artifact(HERE/'MECHANISM_ANALYSIS.json'),
    not_a_second_independent_expert_review=True,new_model_http=0,cost_usd=0))
print(status,'depth changed frames',depth_changed,'joint physical',dict(joint_counts['JOINT_DEPTH']),flush=True)
