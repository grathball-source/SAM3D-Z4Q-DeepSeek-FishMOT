"""Sourcewise results from sealed predictions; never pick the best branch."""
from common import *
from collections import Counter
import math
metrics=read(RUN/'METRICS.json');analysis=read(HERE/'MECHANISM_ANALYSIS.json');inputs=read(HERE/'INPUT_DIAGNOSIS.json')
actionable=read(HERE/'ACTIONABILITY_AUDIT.json')
fields=('IDF1','HOTA','AssA','IDSW','FP','FN');summaries={n:read(RUN/n/'public/RUN_SUMMARY.json') for n in SEGMENTS}
changed=sum(s['changed_frames']['DEPTH_INCREMENT'] for s in summaries.values())
status='FULL_REPLAY_COMPLETE_NO_DEPTH_STATE_INCREMENT' if not changed else 'FULL_REPLAY_COMPLETE_ACTUAL_DEPTH_STATE_CHANGES_SOURCEWISE_RESULTS'
counts=inputs['counts'];physical=Counter()
for n in SEGMENTS:physical.update(read(RUN/n/'public/JOINT_ACTION_AUDIT.json')['counts']['DEPTH_INCREMENT'])
write_new(HERE/'RESULTS.json',dict(status=status,engineering='PASS_REAL_ORIGINAL_STATE_NULL_SOURCE_TRANSACTION_PUBLICATION_AND_FULL_SCORE',
    scientific_goal='NOT_ACHIEVED_NO_DEPTH_INCREMENT' if not changed else 'SOURCEWISE_METRICS_AND_PHYSICAL_EDGES_REPORTED',
    whole_frames=20098,branch_frames=60294,original_objects_unchanged=181842,changed_frames=changed,
    input_counts=counts,physical_counts=physical,metrics=artifact(RUN/'METRICS.json'),
    mechanism=artifact(HERE/'MECHANISM_ANALYSIS.json'),new_model_http=0,cost_usd=0))
lines=['# DS30 最终报告：原Z4Q上的深度增量','',f'主判定：**{status}**。八段20098帧、三个独立真实状态分支，总60294分支帧。没有API、模型、GPU、训练、新SAM3或补全；费用0。','',
'## 改动与工程边界','',
'原Z4Q的engine/bank/alias/pending/出生与延迟恢复全部运行。事件管理器只操作旁路克隆；匿名GROUP/post和精确版本pre记录不再冻结或veto原状态。无深度、DEFER、stage失败时提交本分支完整原预览，禁止改用新几何H1或复制其他分支状态。每帧先决定、stage/commit再首次唯一发布；所有原mask与残片保留。','',
'共享native深度来源逐点在两端排除，重新计算原层、连通支持、背景对比、尺度与质量；原量测保留，被排除点计共同无信息，原ROI分母不变。多支持边际化，不择峰。对齐相机Z与native传感器Z是不同坐标，不假设数值相等；深度支持不认证鱼体或永久上下关系。','',
'原0.25深度权重、0.15联合margin与质量门槛不变；本轮事前增加深度自身margin也须≥0.15、且偏好与最终选择一致，避免极弱非零信号给新几何改号放行。仍须原Bridge.stage通过占用、质量、native-return与实际anchor检查。实际bank目标anchor改变则拒绝，不将冻结旧bank强行写回，不制造原候选。','',
'9项必要单测通过；真实4524帧完整engine/previous/epochs/provenance/version与原Z4Q逐帧相同，F3902出生native7→public0保留，F4524为native1→1、native7→0，无额外交换。完整回放前全部运行/评分源码和参数冻结。初始切片与新增状态hash日志后的最终切片均保留，不以预检PASS冒称研究收益。','',
'## 输入与评价边界','',
'固定DS14八段原SAM3保存源、原始raw深度、原scan_v4和首分离q；不按GT改变锚/候选/触发，不使用v3、annotation实例输入、RGB或未来帧。Feeding四段独立ID域汇总1471帧；FishSA8400/2888已曝光开发/历史验证。L3/LW是未经独立验收的预测派生预标注，仅作弱参考诊断；不能当盲测/物理GT/跨域泛化。全部预测和访问seal后才沿旧官方TrackEval完整评分。','',
'## 完整指标','',
'|数据|分支|IDF1|HOTA|AssA|IDSW|FP|FN|','|---|---|---:|---:|---:|---:|---:|---:|']
all_rows=[]
for name in [*SEGMENTS,'Feeding pooled 1471']:
    ms=metrics['feeding_pooled']['metrics'] if name.startswith('Feeding pooled') else metrics['segments'][name]['metrics']
    for arm in ARMS:
        m=ms[arm];all_rows.append((name,arm,m))
        lines.append('|'+name+'|'+arm+'|'+'|'.join(f'{m[k]:.6f}' if k in fields[:3] else str(int(m[k])) for k in fields)+'|')
lines+=['','## 主比较的真实差值','',
'|数据|比较|ΔIDF1|ΔHOTA|ΔAssA|ΔIDSW|ΔFP|ΔFN|','|---|---|---:|---:|---:|---:|---:|---:|']
for name in ['Feeding pooled 1471','fishsa_development_8400','fishsa_validation_2888','L3','LW']:
    ms=metrics['feeding_pooled']['metrics'] if name.startswith('Feeding pooled') else metrics['segments'][name]['metrics']
    for arm in ARMS[:2]:
        ds={k:ms['DEPTH_INCREMENT'][k]-ms[arm][k] for k in fields}
        lines.append('|'+name+'|DEPTH_INCREMENT−'+arm+'|'+'|'.join(f'{ds[k]:+.6f}' if k in fields[:3] else f'{int(ds[k]):+d}' for k in fields)+'|')
lines+=['','## 全部事件、准入与实际发布','',
f'正式q {counts.get("q",0)}，非null深度 {counts.get("non_null_depth",0)}，实际新增深度提交 {counts.get("actual_depth_commits",0)}。已stage物理关系计数：{dict(physical)}。未提交不能算正确/安全。没有实际修改时恢复原Z4Q只是止损，不能叫深度提点。','',
'|数据|episode|确认merge|无q|q|深度提交|相对原Z4Q改变帧|无事务完整状态检查|','|---|---:|---:|---:|---:|---:|---:|---:|']
for name,s in summaries.items():
    es=read(RUN/name/'public/EVENTS.json')['DEPTH_INCREMENT']
    lines.append(f'|{name}|{len(es)}|{sum(e["confirm_frame"] is not None for e in es)}|{sum(e["q"] is None for e in es)}|{s["q_decisions"]["DEPTH_INCREMENT"]}|{s["joint_stages"]["DEPTH_INCREMENT"]}|{s["changed_frames"]["DEPTH_INCREMENT"]}|{s["no_transaction_full_state_checks"]}|')
lines+=['','## 逐例输入与失败原因','',
'|诊断项|数量|','|---|---:|']
for k,v in sorted(counts.items()):lines.append(f'|{k}|{v}|')
lines+=['','INPUT_DIAGNOSIS保留每个q的实际pre区间、概率、年龄衰减、深度margin、原始选择、stage错误与首次发布。它区分缺少精确参考、无共时pre、过期几何、共同null、深度/总代价不足和原事务边界；不能把这些全部解释为深度理论无效。','',
'SHARED_SOURCE_DIAGNOSIS仅重测旧DS29输入失败，不作为当前正式q/成绩：Feeding原F398共享1来源后顺序概率约0.770602；L3局部F1421共享20来源后约0.692289。这证实“整支持作废”已修复，不证明顺序方向正确，更不保证当前事件可提交。正式事件使用本分支的新真实参考，不强套旧状态答案。','',
'实际量测producer为本轮unique_supports.py，复用DS25方程而新增共享来源排除和完整重测，不是只改CONFIG或原函数完全不变。原始118个事实与重测8个事实分别保留；不存在实际多合格层，不能以合成多层测试称真实混层已充分验证。','',
'### 为什么不是简单降低门槛就能提点','',
'两个非零案例的深度自身代价间隔仅0.038728/0.052970，均小于冻结0.15，而且偏好均与总代价赢家相反。Feeding原F398：深度偏好H1（50→50、30→59），几何偏好H2；物理参考事后核验30→59为DIFFERENT，该建议整体WRONG。public59仍由可见native59发布，旧成员残片未进入当前两候选，直接建议还违反一对一占用；public50实际bank anchor在q之前也已由F10变为F37。L3局部F1421：深度偏好H2（6→6、9→9），相对弱参考CORRECT，但原Z4Q本来已经同样发布，没有需要新增的修改。','',
'这些是事后对未提交建议的物理/占用诊断，不是新的stage结果或反事实全段指标。不能称降低margin一定能提点，也不能把两个建议全部当深度错误。多数事件的输入历史缺口仍未修复；恢复原Z4Q解决了上一轮共用机制退化，当前深度关联能力仍未得到实际增量证明。细节在ACTIONABILITY_AUDIT。','',
'EVENTS保留所有group/residual及无q；TRANSACTIONS绑定实际自动动作、bank anchor、alias、完整branch状态hash和无事务时原预览hash；PUBLISH_LEDGER绑定决定/事务/实际预测。SWITCHES与SWITCH_CHANGES重算每次切换，新增/消除分别保留，不把净增数当新增错误数。JOINT_ACTION_AUDIT区分原始选择、stage、实际发布、相对实际pre参考的物理关系与进入前public原来源。','',
'## 可视化与耗时','',
'PRIVATE_VISUALS是原始深度/mask与三个分支实际合并前、中、q、q+2发布图；首q/首有效深度/首选择变化按时间显示，失败图在封存评分后选择。q+2只作事后解释，不读未来决策、不回填输出。未使用RGB或GT raster，私有像素不入Git。','',
f'正式分段耗时见RUN_SUMMARY；统一评分{metrics["score_seconds"]:.3f}秒，逐帧实际接收到首次发布延迟见PUBLISH_LEDGER。这是离线CPU保存mask回放，不称实时部署。原始资料、私有图、字节/SHA与本机解释器/deps及复现顺序见RESTRICTED_ARTIFACTS。所有公开成果main非force同步，实际远端ref/每文件hash核验见REMOTE_VERIFICATION。','',
'## 结束与未完成边界','',
'当前冻结版本结束，不滚动调整门槛或挑更容易事件；共同机制修复不等于深度有效。不证明永久深度上下关系，不覆盖未管理并发交互，不将弱预标注当独立GT。唯一下一步：审计原Z4Q全部实际错误及全部候选/事件的覆盖与深度可执行性，定位真正可改变的错误；不能为产生提交直接降门槛。详见NEXT_STEP_PLAN，本轮未执行该后续计划。']
path=HERE/'FINAL_REVIEW.md';path.write_text('\n'.join(lines)+'\n',encoding='utf-8')
parsed=[x.split('|')[1:-1] for x in path.read_text(encoding='utf-8').splitlines() if x.startswith('|')]
checked=[r for r in parsed if len(r)==8 and r[1] in ARMS];assert len(checked)==27
for r in checked:
    n,a,*values=r;m=metrics['feeding_pooled']['metrics'][a] if n=='Feeding pooled 1471' else metrics['segments'][n]['metrics'][a]
    assert all(math.isclose(float(v),m[k],rel_tol=0,abs_tol=5.1e-7) for k,v in zip(fields,values))
for x in rows(HERE/'EXECUTION_LOG.jsonl'):verify_item(x['stdout']);verify_item(x['stderr'])
for p,h in read(HERE/'RUNTIME_FREEZE.json')['code'].items():assert sha(p)==h
write_new(HERE/'REPORT_VALIDATION.json',dict(status='PASS_REPORT_NUMBERS_SEALS_AND_EXECUTION_RECORDS',
    complete_metric_rows_verified=27,report=artifact(path),metrics=artifact(RUN/'METRICS.json'),
    not_a_second_independent_expert_review=True,new_model_http=0,cost_usd=0))
print(status,dict(counts),flush=True)
