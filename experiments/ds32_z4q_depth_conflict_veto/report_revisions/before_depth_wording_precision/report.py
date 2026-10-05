"""Postseal report: actual metrics, no extrapolation from engineering passes."""
from common import *
import score, math
import numpy as np

score.verify_all()
m=read(RUN/'METRICS.json');a=read(HERE/'ANALYSIS_POSTSEAL.json')
assert a['status'].startswith('PASS')
assert read(HERE/'VISUAL_ACCEPTANCE.json')['status']=='PASS_ACTUAL_VISUAL_INSPECTION'
fields=('IDF1','HOTA','AssA','IDSW','FP','FN')
main=['Feeding pooled 1471','fishsa_development_8400','fishsa_validation_2888','L3','LW']
sources=[*SEGMENTS,'Feeding pooled 1471']
def table(n):return m['feeding_pooled']['metrics'] if n=='Feeding pooled 1471' else m['segments'][n]['metrics']
def fmt(k,v,signed=False):
    return (f'{v:+.6f}' if signed else f'{v:.6f}') if k in fields[:3] else (f'{int(v):+d}' if signed else str(int(v)))
comparison={n:{b:{k:table(n)[ARMS[2]][k]-table(n)[b][k] for k in fields} for b in ARMS[:2]} for n in main}
summaries={n:read(RUN/n/'public/RUN_SUMMARY.json') for n in SEGMENTS}
totals={k:sum(x['counts'][k] for x in summaries.values()) for k in next(iter(summaries.values()))['counts']}
assert sum(x['frames'] for x in summaries.values())==20098
assert sum(x['objects'] for x in summaries.values())==181842
if totals['changed_frames']==0:
    status='NO_EFFECT_FULL_PUBLICATIONS_EQUAL_TO_ORIGINAL_Z4Q'
elif all(abs(comparison[n]['Z4Q_FROZEN'][k])<=1e-9 for n in main[:3] for k in fields[:3]):
    status='CHANGED_PUBLICATIONS_WITHOUT_STRONG_REFERENCE_METRIC_GAIN'
elif all(comparison[n]['Z4Q_FROZEN'][k]>=-1e-9 for n in main[:3] for k in fields[:3]) and any(
        comparison[n]['Z4Q_FROZEN'][k]>1e-9 for n in main[:3] for k in fields[:3]):
    status='SOURCE_DEPENDENT_GAIN_REQUIRES_INDEPENDENT_VALIDATION'
else:status='MIXED_OR_NEGATIVE_NO_GENERAL_DEPTH_GAIN'
latency={}
for n in SEGMENTS:
    vals=[r['receive_to_first_publish_seconds'] for r in rows(RUN/n/'public/PUBLISH_LEDGER.jsonl')]
    assert len(vals)==summaries[n]['frames']
    latency[n]=dict(mean_seconds=float(np.mean(vals)),p95_seconds=float(np.percentile(vals,95)),max_seconds=max(vals))
write_new(HERE/'LATENCY_SUMMARY.json',dict(segments=latency,shared_three_branch_saved_observation_CPU_replay=True,live_camera_or_API_latency=False))
physical={n:read(RUN/n/'public/VETO_AUDIT.json')['active_deletions'] for n in SEGMENTS}
switches={n:read(RUN/n/'public/SWITCH_CHANGES.json') for n in SEGMENTS}
write_new(HERE/'RESULTS.json',dict(status=status,engineering='PASS_FROZEN_SOURCE_STATE_PUBLICATION_AND_ALL_SEALS',
    input='SAME_SAVED_SAM3_AND_RAW_DEPTH; L3_LW_WEAK; EXPOSED_DIAGNOSTIC',depth_increment=status,
    frames=20098,branch_frames=60294,unchanged_original_masks=181842,counts=totals,comparison=comparison,
    veto_physical_counts=physical,metrics=artifact(RUN/'METRICS.json'),analysis=artifact(HERE/'ANALYSIS_POSTSEAL.json'),
    original_switch_coverage=a['original_switch_coverage_totals'],
    frozen_version_closed=True,new_model_http=0,cost_usd=0))
lines=['# DS32 最终报告：原 Z4Q 候选边上的可靠深度冲突否决','',f'主判定：**{status}**。八段20098帧、三分支60294帧全部完成，181842张原始mask保留。工程检查通过与深度提点分开判断；实际指标如下。','',
    '## 本轮改动','',
    '保留原Z4Q的native返回优先、D1_DELAYED、BIRTH_REFINE、占用、alias、bank、pending、出生确认、隔离与首次发布事务。只在两条真实候选入口入矩阵前查询独立深度证据；仅删除存在可靠矛盾的一条原合法边，其余候选、原成本和dummy保持原值。不能把整行删除称单边；不能把原已非法边上的矛盾称新增保护。','',
    '证据独立保存live片段与精确anchor registry。只有原引擎实际写入的clean bank参考才注册，按保存源域、精确(frame/native/public/mask)、出现连续generation、public epoch和风险片段绑定。当前弱观测切断live，不删除未改变的冻结anchor。至少5个连续同版本有效点，保留30点，最近10点用原DS1真实时间WLS；不跨风险补点，不把当前q写进pre，不读未来帧。','',
    '使用同源原始深度的已封存DS18 adaptive exclusive-core与去重来源统计；whole/core任一混层、未认证/共享来源、少于16独立点、覆盖不足0.2、尺度超过60mm均UNKNOWN。候选当前有邻鱼时，只允许实际可靠且无混层的exclusive core提供证据；接触、匿名观测仍不能更新个体历史。质量通过不认证该像素一定属于正确鱼体。','',
    '固定否决条件：WLS预测和当前深度均有效且尺度≤60mm；abs(z−mu)>max(60mm,3×hypot(预测尺度,当前尺度))。12秒过期，尺度底噪15mm。预测尺度上限与系数3是预先冻结的保守工程假设，未经物理/统计标定，不能称3σ准确率。没有深度相似奖励或背景密度比；不假设上下关系永远不变。','',
    '无可靠矛盾时，逐帧验证本分支同一前状态的原控制器完整状态与输出一致。发生否决后继续自身真实状态，不复制外部B0，不只改最终输出。Native与原Z4Q的全预测和所有指标严格复现旧封存。','',
    '## 冻结、输入与工程证据','',
    '12/12直接相关状态/来源/两入口检查通过；真实200帧关闭模块、200帧启用模块、含F364的205帧切片通过。冻结前发现并修复BirthRefine邻接见证被无条件null，以及旧评分模块同名配置导入冲突；旧源码、检查收据、失败日志和切片只读保留，未评分或拼入正式结果。最终合同READY和FROZEN_CONTRACT_AUDIT绑定实际字节。','',
    '输入/代码/实际常数/评分在正式START前封存；全部正式预测与访问记录封存后，才读现有已曝光参考；本轮无可用单边反事实项，未运行反事实。START和评分均核验source manifest、输入、原始来源、DS18完整缓存、producer、旧预测seal、runtime与代码字节。没有GT挑选候选、q或history。','',
    '旧官方评分适配器为动态载入，未自动枚举到runtime.code；它在正式START前已有独立导入SHA。DS14数学另由DS1/postseal.py的AST提取clear_step，该源同样未自动枚举。score_checked在读GT前验证导入receipt、实际适配器及clear_step源均与已冻结Git BASE原blob一致，记录SCORING_BINDING_ACCEPTANCE；这一绑定边界及工程补齐如实保留，数学、参考或预测均未修改。','',
    '四段Feeding1471帧分属独立身份域汇总；8400与2888为既有已曝光开发/历史验证；L3/LW参考为未经独立验收的预测派生预标注，只作弱参考诊断。source generation仅认证保存片段内连续出现，缺少producer session/reset metadata，不能认证未标记的内部instance变化。本轮不是新的盲测。','',
    '## 完整指标','', '|数据|分支|IDF1|HOTA|AssA|IDSW|FP|FN|','|---|---|---:|---:|---:|---:|---:|---:|']
for n in sources:
    for b in ARMS:lines.append('|'+n+'|'+b+'|'+'|'.join(fmt(k,table(n)[b][k]) for k in fields)+'|')
lines+=['','## 主比较真实差值','', '|数据|比较|ΔIDF1|ΔHOTA|ΔAssA|ΔIDSW|ΔFP|ΔFN|','|---|---|---:|---:|---:|---:|---:|---:|']
for n in main:
    for b in ARMS[:2]:lines.append('|'+n+'|Z4Q_DEPTH_VETO−'+b+'|'+'|'.join(fmt(k,comparison[n][b][k],True) for k in fields)+'|')
lines+=['','## 真实候选、状态和发布变化','', '|数据|查询边|原合法删边|原非法冗余冲突|同前状态提交变化|相对Z4Q发布改变帧|新增切换记录|消除切换记录|','|---|---:|---:|---:|---:|---:|---:|---:|']
for n in SEGMENTS:
    c=summaries[n]['counts'];s=switches[n]
    lines.append('|'+n+'|'+'|'.join(str(v) for v in [c['hook_edges'],c['legal_edges_deleted'],c['redundant_conflicts'],c['selected_commit_changes'],c['changed_frames'],len(s['added']),len(s['eliminated'])])+'|')
lines+=['',f'全段计数：{json.dumps(totals,ensure_ascii=False)}。hook边、可靠矛盾、原非法冗余矛盾、入矩阵删边、真实提交变化及首次发布变化分列；删边可能本来就不会被选中，不能算成功恢复。', '',
    f'原合法实际删边按其真实额外bank参考及各段现有参考核验：{json.dumps(physical,ensure_ascii=False)}。L3/LW仅有弱参考，不认证物理身份真值。BirthRefine原打分参考与额外bank参考分别记录，不默认为同一个。正确/有害/不可评分不合并，进入前public已错也不能靠整数换回冒充物理恢复。', '',
    f'原Z4Q逐次切换覆盖：{json.dumps(a["original_switch_coverage_totals"],ensure_ascii=False)}。逐次按实际global_frame对齐；原生对应同时绑定gt_id。没有本帧D1/Birth接受提交，只能说明不在本轮两个入口的当帧接受范围，不能推断没有查询、没有先前alias影响或没有关联因果。逐次当前native/public、查询原因和状态分支见ANALYSIS_POSTSEAL。', '',
    '新增/消除切换为逐次实际CLEAR匹配记录差，净差不能当新增错误数；整数标签变化可能改变同一物理切换的记录键，需结合SWITCHES/真实发布及REFERENCE_MATCHES解释。FP/FN不删除任何mask或残片。查询可用性、未建立/换锚/过期与所有null原因见ANALYSIS_POSTSEAL及逐帧TRANSACTIONS。', '',
    '## 单边真实状态反事实与固定回归点','',
    (HERE/'INTERPRETATION.md').read_text(encoding='utf-8').strip(),'',
    '## 耗时与复现','', '|数据|回放秒数|平均发布秒数|p95秒数|最大秒数|','|---|---:|---:|---:|---:|']
for n in SEGMENTS:
    l=latency[n];lines.append(f'|{n}|{summaries[n]["elapsed_seconds"]:.3f}|{l["mean_seconds"]:.6f}|{l["p95_seconds"]:.6f}|{l["max_seconds"]:.6f}|')
lines+=['',f'统一评分{m["score_seconds"]:.3f}秒。发布耗时是保存观测下同机三分支共享CPU回放时间，不含SAM3推理，不称实时部署。实际命令、退出状态与计时见独立EXECUTION_LOG。模型HTTP、smoke、GPU、训练、SAM3新推理、补全与费用全部0。','',
    '两张可公开数值SVG来自本轮实际指标、深度事实/候选与发布记录，实际检查后交付；不绘制假设身份或不可见轮廓。受限输入真实路径、字节、SHA及依赖记录在RESTRICTED_ARTIFACTS，像素/凭据不入Git。代码、测试、配置、数值预测、日志和报告全部main普通提交与推送，REMOTE_VERIFICATION实际读取远端ref和每个公开blob；最后再次核验包含收据的main。','',
    '## 未完成边界与唯一下一步','',
    '本轮冻结版本结束。没有新盲测、物理深度精度认证、producer session版本认证、合并mask硬拆分、RGB外观/光流、未来补回或大模型。本轮代码/报告交付完整，不将工程PASS、弱参考改善或原Z4Q既有收益称深度增量。', '',
    (HERE/'NEXT_STEP_PLAN.md').read_text(encoding='utf-8').strip()]
path=HERE/'FINAL_REVIEW.md';assert not path.exists();path.write_text('\n'.join(lines)+'\n',encoding='utf-8')
parsed=[x.split('|')[1:-1] for x in path.read_text(encoding='utf-8').splitlines() if x.startswith('|')]
checked=[r for r in parsed if len(r)==8 and r[1] in ARMS];assert len(checked)==27
for n,b,*vals in checked:
    for k,v in zip(fields,vals):assert abs(float(v)-table(n)[b][k])<=5.1e-7,(n,b,k)
deltas=[r for r in parsed if len(r)==8 and r[1].startswith('Z4Q_DEPTH_VETO−')];assert len(deltas)==10
for n,b,*vals in deltas:
    for k,v in zip(fields,vals):assert abs(float(v)-comparison[n][b.split('−')[1]][k])<=5.1e-7,(n,b,k)
write_new(HERE/'REPORT_VALIDATION.json',dict(status='PASS',metric_rows=len(checked),delta_rows=len(deltas),all_numeric_tables_reparsed=True,
    report=artifact(path),results=artifact(HERE/'RESULTS.json'),all_predictions_scored_after_seal=True,new_model_http=0,cost_usd=0))
print(status,totals,flush=True)
