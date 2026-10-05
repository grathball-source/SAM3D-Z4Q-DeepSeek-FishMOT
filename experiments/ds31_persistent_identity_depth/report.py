"""Publish complete sourcewise results and independently validated numeric tables."""
from common import *
from collections import Counter
import math
import numpy as np
import score

score.verify_all()
metrics=read(RUN/'METRICS.json')
mechanism=read(RUN/'MECHANISM_ANALYSIS.json')
origin=read(HERE/'ORIGIN_ACTION_SUMMARY.json')
analysis=read(HERE/'ANALYSIS.json')
assert mechanism['status']=='PASS' and origin['status']=='PASS'
assert (HERE/'INTERPRETATION.md').is_file() and (HERE/'NEXT_STEP_PLAN.md').is_file()
assert read(HERE/'VISUAL_ACCEPTANCE.json')['status']=='PASS_ACTUAL_VISUAL_INSPECTION'
fields=('IDF1','HOTA','AssA','IDSW','FP','FN')
summaries={n:read(RUN/n/'public/RUN_SUMMARY.json') for n in SEGMENTS}
sources=[*SEGMENTS,'Feeding pooled 1471']
main_sources=['Feeding pooled 1471','fishsa_development_8400','fishsa_validation_2888','L3','LW']
def source_metrics(name):
    return metrics['feeding_pooled']['metrics'] if name=='Feeding pooled 1471' else metrics['segments'][name]['metrics']
def row(name,arm,m):
    return '|'+name+'|'+arm+'|'+'|'.join(f'{m[k]:.6f}' if k in fields[:3] else str(int(m[k])) for k in fields)+'|'
def delta(name,base):
    m=source_metrics(name)
    return {k:m['PID_DEPTH'][k]-m[base][k] for k in fields}
comparison={n:{base:delta(n,base) for base in ARMS[:3]} for n in main_sources}
changed_counts={a:Counter() for a in ARMS[2:]}
for n in SEGMENTS:
    for a in read(RUN/n/'public/ACTION_AUDIT.json')['actions']:
        if a['mapping_changed']:changed_counts[a['arm']][a['physical']]+=1
latencies={}
for n in SEGMENTS:
    values=[x['receive_to_first_publish_seconds'] for x in rows(RUN/n/'public/PUBLISH_LEDGER.jsonl')]
    assert len(values)==summaries[n]['frames']
    latencies[n]=dict(frames=len(values),mean_seconds=float(np.mean(values)),p95_seconds=float(np.percentile(values,95)),
        max_seconds=max(values),four_arms_shared_CPU_replay=True)
write_new(HERE/'LATENCY_SUMMARY.json',dict(segments=latencies,not_live_camera_or_API_latency=True))
assert sum(s['objects'] for s in summaries.values())==181842
assert sum(s['frames'] for s in summaries.values())==20098
status='FULL_REPLAY_COMPLETE_SOURCEWISE_PERSISTENT_IDENTITY_AND_DEPTH_RESULTS'
goal='NOT_ACHIEVED_ALL_FIVE_SUMMARIES_BELOW_NATIVE_AND_ORIGINAL_Z4Q'
assert all(source_metrics(n)['PID_DEPTH'][k]<source_metrics(n)[base][k]
    for n in main_sources for base in ARMS[:2] for k in ('IDF1','HOTA','AssA'))
write_new(HERE/'RESULTS.json',dict(status=status,engineering='PASS_FINAL_V2_STATE_SOURCE_PUBLICATION_AND_ALL_SEALS',
    scientific_goal=goal,frames=20098,branch_frames=80392,
    unchanged_original_masks=181842,changed_PID_action_physical_counts=changed_counts,comparison=comparison,
    metrics=artifact(RUN/'METRICS.json'),mechanism=artifact(RUN/'MECHANISM_ANALYSIS.json'),
    analysis=artifact(HERE/'ANALYSIS.json'),engineering_v1_unscored=True,new_model_http=0,cost_usd=0))
lines=['# DS31 最终报告：持续身份与动态原始深度','',
    f'主判定：**完整实验已完成，提点目标未实现（{goal}）**。八段20098帧、四个独立状态分支，共80392分支帧、181842张原始mask。全段完成并封存后评分；没有新模型HTTP、GPU、训练、SAM3推理或补全，费用0。','',
    '## 实验思路与实际取舍','',
    '采用用户建议的核心：持续PID与每帧native观测分离；因遮挡/接触失去独立观测时保留身份和旧参考；清楚观测用真实运动外推，可能重现的观测联合竞争旧身份及dummy；深度只补充关联歧义。已被scan/邻接识别的疑似合并观测记录group，保护成员参考；首次满足可见分离条件的帧先关联、提交再唯一发布，post不提前进入pre。两帧确认只满足程序到帧条件，不认证持续物理合并；q可能尚无confirm或受残片占用阻断，不泛称完整恢复。','',
    '本轮不改变任何原mask或残片、不补画不可见鱼体。暂不做合并mask硬拆分：旧M1误切分证据及混层风险仍在，先用相同检测mask检验身份层和深度增量。原建议的颜色、RGB光流和未来双向补回未加入；实际运动为最近10个连续同版本clean观测的OLS回归，记录残差，运输旧mask只用已测位置变化。','',
    'SAM3_NATIVE、Z4Q_FROZEN、PID_MOTION、PID_DEPTH均继续自己的真实状态。原生SAM3与原Z4Q逐帧及全指标严格复现。PID_MOTION和PID_DEPTH使用相同的新身份生命周期、候选、运动与事务规则；二者仅深度代价不同。新身份层移除了原Z4Q的native返回优先、D1/BirthRefine等政策，因此相对Z4Q的整体变化不能全部算成深度贡献。','',
    '零IoU在合理运动搜索范围内仍可接回；未匹配身份仍存在。基础搜索半径为max(32px,旧/当前框对角线均值)，再以80px/s增长最多1.5s；预测运动外推最多1s，历史最多12s；mask/距离代价0.6/0.4，dummy1，全局margin0.15。普通新来源至少5个clean且出生后≥6s建立新身份，首帧来源只需5点；6s并非硬重接截止。实际生效代码、CONFIG及旧依赖在全段前冻结，不用GT调门槛。','',
    '深度采用相同raw来源的DS18独立native测量去重、adaptive exclusive-core及whole/core混层检查，原ROI/样本分母可追溯。至少16独立点、覆盖0.2、scale≤60mm、底噪15mm；多层、缺测或未认证来源保留UNKNOWN，不择有利峰。最近30观测缓存、最近10连续同版本可靠时刻用原DS1真实时间WLS，保留拟合速度及随时间增长的不确定性。','',
    '几何最优与替代（含dummy）间隔≤0.3才启用深度。代价为归一化Student-t信号/共同背景似然比的0.9信号+0.1无信息混合，包含log尺度，外乘固定0.25一次；整条可行候选行缺任何必要深度则全部共同null，不让某个未知候选获利。深度不改硬几何范围或dummy；因此仍可能影响接受/拒绝，而不只是H1/H2换位，这在实际矩阵分析中单列。','',
    '## 工程与输入分层','',
    '工程v1在评分前发现“组外clean观测能认领尚未分离的缺席成员”并停止；所有源码、冻结记录、未完成流及停止原因追加封存，未读取评分参考、未作为方法成绩。v2排除所有active成员PID，并逐帧验证受保护bank完全未改变。必要状态检查12/12、深度检查9/9，真实200帧切片重新通过；正式结果只来自随后独立的v2全段。','',
    '输入保持原DS14八段SAM3保存源与原始深度，没有v3、annotation instance_id、未来帧或RGB参与预测。Feeding四段1471帧分属独立ID域后汇总；8400/2888为已曝光开发/历史验证。L3/LW为未经独立验收的预测派生预标注，只作弱参考诊断，不能作为盲测、物理身份真值或跨数据集泛化。质量PASS并不认证测量像素一定来自正确鱼体，远近关系也不被假设永久不变。','',
    '所有八段预测与访问记录先封存，再统一用旧官方TrackEval/参考适配器评分。每张mask与每个ID均参与，不忽略残片、不删漏检难例、不重画历史。评分动作对本次选定PID决策前的真实bank参考核验；进入前public来源已错与本次物理参考匹配分列。','',
    '## 完整指标','',
    '|数据|分支|IDF1|HOTA|AssA|IDSW|FP|FN|','|---|---|---:|---:|---:|---:|---:|---:|']
for n in sources:
    for a in ARMS:lines.append(row(n,a,source_metrics(n)[a]))
lines+=['','## 主比较真实差值','',
    '|数据|比较|ΔIDF1|ΔHOTA|ΔAssA|ΔIDSW|ΔFP|ΔFN|','|---|---|---:|---:|---:|---:|---:|---:|']
for n in main_sources:
    for base in ARMS[:3]:
        d=comparison[n][base]
        lines.append('|'+n+'|PID_DEPTH−'+base+'|'+'|'.join(f'{d[k]:+.6f}' if k in fields[:3] else f'{int(d[k]):+d}' for k in fields)+'|')
lines+=['','## 实际动作、深度覆盖与保护','',
    '|数据|分支|接受关联|实际换PID|同PID再认证|active深度行|接受的深度选择变化|group数|首分离q|相对Z4Q改变帧|','|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
for n in SEGMENTS:
    for arm in ARMS[2:]:
        b=mechanism['segments'][n]['branches'][arm];groups=mechanism['segments'][n]['groups'][arm]
        values=[b.get('actions',0),b.get('mapping_changed_actions',0),b.get('same_PID_reassociation_actions',0),b.get('active_depth_rows',0),
            b.get('depth_changed_same_state_geometry_selection',0),groups['total'],sum(e['q'] is not None for e in groups['events']),summaries[n]['counts'][arm]['changed_frames']]
        lines.append('|'+n+'|'+arm+'|'+'|'.join(map(str,values))+'|')
lines+=['','“接受关联”包含同PID再认证，不能当作恢复次数；active深度行也不代表改变了选择。ANALYSIS另列同一状态下深度使接受边新增、删除或替代的数值结果；跨分支之后的持续状态差异另列，不用接受动作计数差推断某条鱼被正确恢复。','',
    f'实际换PID动作、按选定真实pre参考判定：{json.dumps(changed_counts,ensure_ascii=False)}。正确/错误/不可评分均保留；DEFER、缺测和未完成配对不算正确。','',
    f'深度输入覆盖（可用独立core/全部对象）：{mechanism["totals"].get("usable_independent_core",0)}/{mechanism["totals"].get("objects",0)}。全部抽取失败原因、混层比例、WLS预测来源、共同null行与组保护逐帧计数见run/MECHANISM_ANALYSIS.json；不将宽尺度覆盖当物理精度。','',
    '## 失败与成功案例复盘','',
    (HERE/'INTERPRETATION.md').read_text(encoding='utf-8').strip(),'',
    'ACTION_AUDIT/ORIGIN_ACTION_AUDIT保留原始选择、实际目标、旧PID、实际anchor、首次公开来源及可评分关系。SWITCHES逐次重算，SWITCH_CHANGES新增/消除分列，不能用净增数代表新增错误数；改变整数标签可令同一物理切换的记录键变化，逐帧真实输出与参考对照一起解释。','',
    '## 耗时、可视化与复现','',
    '|数据|回放秒数|平均首次发布秒数|p95秒数|最大秒数|','|---|---:|---:|---:|---:|']
for n in SEGMENTS:
    l=latencies[n];lines.append(f'|{n}|{summaries[n]["elapsed_seconds"]:.3f}|{l["mean_seconds"]:.6f}|{l["p95_seconds"]:.6f}|{l["max_seconds"]:.6f}|')
lines+=['',f'统一评分{metrics["score_seconds"]:.3f}秒。以上发布延迟为同机四分支保存观测回放的共享接收→完成延迟，不含SAM3推理，不称实时部署或API延迟。完整启动、输出、退出码与耗时见EXECUTION_LOG；没有推理HTTP或费用。','',
    '实际参考前、当前q及q+2诊断图使用原始深度与原mask，展示四分支当时真实发布ID。图按首换PID、首同状态深度改变及封存后首错误选取；q+2只作事后解释，不参与决策。图已实际人工视觉检查，私有像素留本机，公开PRIVATE_VISUALS/PRIVATE_OVERVIEWS记录来源、字节和SHA。原RGB、GT raster、密钥和私有像素均不入Git。','',
    'RESTRICTED_ARTIFACTS记录真实本机输入、缓存、图像、解释器、依赖与复现顺序。原输入和旧seal只读；新结果单独目录。全部公开代码、测试、日志、逐帧数值预测、结果和报告整合main；最终实际读取远端ref及每个公开blob核验，见REMOTE_VERIFICATION收据。','',
    '## 结论边界与唯一下一步','',
    '完整回放、协议和状态隔离通过不等于科研提点。只按表中同源原生、原Z4Q及同底座PID_MOTION对照判断；多数据来源不合并成一个不明权重的总分。当前冻结版本结束，不自动重跑、扩大事件、调阈值、加入模型或掩码拆分。未实施RGB光流、外观、可见区深度拆分、缺失鱼补画或新盲测；完整bank快照/未使用边历史没有逐条公开，状态hash可绑定但不能冒充独立重建所有内部写入。','',
    (HERE/'NEXT_STEP_PLAN.md').read_text(encoding='utf-8').strip()]
path=HERE/'FINAL_REVIEW.md';assert not path.exists();path.write_text('\n'.join(lines)+'\n',encoding='utf-8')
parsed=[x.split('|')[1:-1] for x in path.read_text(encoding='utf-8').splitlines() if x.startswith('|')]
checked=[r for r in parsed if len(r)==8 and r[1] in ARMS];assert len(checked)==36
for n,a,*values in checked:
    assert all(math.isclose(float(v),source_metrics(n)[a][k],rel_tol=0,abs_tol=5.1e-7) for k,v in zip(fields,values))
diff_rows=[r for r in parsed if len(r)==8 and r[1].startswith('PID_DEPTH−')];assert len(diff_rows)==15
for n,label,*values in diff_rows:
    d=delta(n,label.split('−')[1]);assert all(math.isclose(float(v),d[k],rel_tol=0,abs_tol=5.1e-7) for k,v in zip(fields,values))
for x in rows(HERE/'EXECUTION_LOG.jsonl'):verify_item(x['stdout']);verify_item(x['stderr'])
for p,h in read(HERE/'RUNTIME_FREEZE.json')['code'].items():assert sha(p)==h,p
write_new(HERE/'REPORT_VALIDATION.json',dict(status='PASS',complete_metric_rows_verified=36,delta_rows_verified=15,
    report=artifact(path),metrics=artifact(RUN/'METRICS.json'),mechanism=artifact(RUN/'MECHANISM_ANALYSIS.json'),
    analysis=artifact(HERE/'ANALYSIS.json'),new_model_http=0,cost_usd=0))
print(status,json.dumps(comparison),flush=True)
