"""All observed scores and failed-source boundaries, no best-run selection."""
from common import *
from collections import Counter
import score

score.verify_all();m=read(RUN/'METRICS.json');a=read(HERE/'MECHANISM_ANALYSIS.json');qa=read(HERE/'POSTSEAL_QA.json')
assert qa['status'].startswith('PASS') and read(HERE/'VISUAL_ACCEPTANCE.json')['status'].startswith('PASS')
fields=('IDF1','HOTA','AssA','IDSW','FP','FN')
segments=m['segments'];updates=a['actual_nonzero_cost_updates']
assert len(updates)==5 and all(x['actual_reference_physical']=='CORRECT' for x in updates)
assert all(v['metrics']['DEPTH_RISK']==v['metrics']['Z4Q_FROZEN']==v['metrics']['DEPTH_NEAR'] for v in segments.values())
wrong=[r for s in a['segments'].values() for r in s['original_action_coverage']
    if r['arm']=='DEPTH_RISK' and r['original_action']['actual_reference_physical']=='WRONG']
assert len(wrong)==17 and all(r['edge_checked'] and not r['full_pre_q_comparisons'] and not r['nonzero_cost'] for r in wrong)
reasons=Counter(r['actual_check']['reason'] for r in wrong)
partners=Counter(c.get('reason',c['status']) for r in wrong for c in r['actual_check'].get('comparisons',[]))
metrics_units=[(n,x['metrics']) for n,x in segments.items()]+[('Feeding pooled 1471',m['feeding_pooled']['metrics'])]
lines=['# DS28 预测风险驱动深度入口完整回放（2026-10-05）','',
    '**主判定：工程完成；入口覆盖改善；深度确有5次真实成本修正；身份关联和跟踪指标增量为0，未达到提点目标。**',
    '全部8段20098帧、4分支真实状态回放、全部预测及访问封存后统一评分已完成。不是只修改输出文件，没有新增模型HTTP/费用、GPU/服务器、训练、SAM3或深度补全。','',
    '## 本轮改变与冻结边界','',
    'DEPTH_NEAR逐帧复现DS27 C1/S5的科学状态及发布。DEPTH_RISK将真实Hungarian前的深度入口从原成本接近0.15改为原预测近期交互后失踪候选池内全部合法边，含单合法候选行。原D1_DELAYED/BIRTH_REFINE的候选、原拒绝、二维、原深度成本、dummy=1、margin/confirm、q、bank参考、事务及发布保持不变。没有硬编码事件、年龄ONEFIX或新硬veto。',
    '测量仍max(10mm,2σbg)、实际floor5mm、层间gap30mm、16点/原ROI覆盖0.2、maxscale60mm。5mm是历史数值变异下限，不是仪器精度。source generation/epoch、风险切断、精确旧anchor、5个同步pre、概率median距0.5门槛0.1、soft_weight0.15、age6秒及共同null完全未改。CONFIG中的只读adapter兼容15/60不是新测量的有效floor；有效值已逐事实回查RUNTIME_FREEZE。','',
    '## 为什么上一轮和本轮都没有提点','',
    '旧封存审计：原90次实际提交只有4次进入near检查（1次正确、3次不可评分）；17次实际参考错接全部未进入。D1/BIRTH原合法边1544/8，旧入口检查492/3。这个覆盖问题真实存在。',
    '本轮risk1552条边全部检查，90次原提交也全部覆盖。但17次错接仍无一次形成完整pre/q比较，成本全部回到null。2次源本身处于风险；另外15次涉及当前伙伴风险、伙伴来源换代、同步clean历史不足或没有可认证伙伴。伙伴原因是多引用且可重叠，不可将计数相加当独立错接数量。',
    f'17错接的主原因：{dict(reasons)}；伙伴引用原因：{dict(partners)}。',
    '这不是“测了17次发现上下关系没用”。17次没有获得当前合同允许的完整比较。当前关联解释把另一条鱼当成已知、同版本、clean的当前身份见证；在两条鱼都变号或分割混合时，这个前提恰好失效。不能把来源未知改为已知，也不能仅不断扩大入口或降低资格线。',
    '深度真正修正的只有Feeding第四段local617–621/global1817–1821，native194→旧149同一条5帧确认链。事后实际旧参考核验为正确，原Z4Q已经恢复正确。这5次不是5个独立成功事件，更不是新恢复。',
    f"最大绝对成本变化{a['max_absolute_cost_update']:.12f}；原边成本0.300337–0.388866，离dummy仍约0.61–0.70。当前顺序概率接近0.5，实际修正很小，没有改变真实选择/确认/alias/公开发布。扩大权重也不能解决17次根本没有完整输入的问题。",'',
    '## 真实输入与决策覆盖','',
    '|分支|合法边检查|正式测量事实|完整伙伴比较|弱pre|达到pre门槛|当前缺证且pre达标|非零成本|新身份提交|',
    '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
for arm in ARMS[2:]:
    c=a['counts'][arm];p=a['comparison_counts'][arm]
    lines.append('|'+arm+'|'+'|'.join(str(x) for x in (c['checks'],c['facts'],p['complete_comparisons'],p['weak_pre'],p['admitted_pre'],p['admitted_pre_current_null'],c.get('nonzero_cost_edges',0),0))+'|')
lines+=['','事实单位为政策×帧×原mask，不是独立鱼或事件。重复pre引用不当独立样本。risk420个事实中176个有单一qualified支持、1个多支持、243个没有支持；near172中118/1/53。所有背景、弱支持、缺测保留，多支持不选择“最好峰”。风险中记录仍匿名，post不提前写pre。','',
    '## 完整同源跟踪指标','',
    '|数据段|分支|IDF1|HOTA|AssA|IDSW|FP|FN|','|---|---|---:|---:|---:|---:|---:|---:|']
for name,arms in metrics_units:
    for arm in ARMS:
        vals=arms[arm];lines.append('|'+name+'|'+arm+'|'+'|'.join(f'{vals[k]:.6f}' if k in fields[:3] else str(vals[k]) for k in fields)+'|')
lines+=['','DEPTH_RISK−原Z4Q、DEPTH_RISK−DEPTH_NEAR在每一数据段及Feeding汇总的全部六指标精确为0。与Native的真实差值全部保留在run/METRICS.json，不能将原Z4Q收益算本模块收益。原Z4Q总IDSW159、Native129；Feeding132/108，多出的切换属于既有底座，本模块新增/消除切换均0。','',
    'L3/LW仍是预测派生、未经独立验收的弱参考；FishSA和Feeding也是已曝光开发/历史验证材料。本轮不是盲测或新泛化，不混另一个保存源，不声明毫米物理准确率。','',
    '## 真实提交、评分与工程','',
    '三种Z4Q分支均保留90次原真实提交（D1 86、Birth4），没有新提交/取消/延迟变化。按实际bank参考为16正确/17错误/57不可评分；包括公开ID初始来源一致性的判定为15正确/17错误/58不可评分。旧标签在进入前已错与当前物理恢复分开记录。所有mask/残片保留，同帧公开ID一对一，忽略ID数0。',
    '必要13项矩阵/状态/来源检查、实际DS27测量事实和全部map一致性、禁用200帧完整状态/发布等价、真实205帧以及全部20098帧near原输出/科学状态等价通过。独立评分链在全部预测/访问seal之后读取已曝光参考，所有发布、START式冻结代码、完整事实引用、成本公式、源帧<=q和事务账本由POSTSEAL_QA回查；未训练、无API。',
    '并行日志文件名微秒碰撞导致L3子作业在启动guard之前失败，原错误日志保留。追加UUID日志启动器，仅首次启动此前未运行L3；原冻结运行/算法文件及7个已完成seal全部原SHA保留。随后八段seal汇总才允许评分。不是选择最好重复，不覆盖任何旧结果。TECHNICAL_RECOVERY及执行日志记录完整过程。','',
    '## 可视化、受限产物与未完成边界','',
    '15张按源/臂最早真实成本修正、完整比较或阻断案例选择的图，以及全部17次旧实际参考错接图，均为真实原始depth/mask，无RGB/GT raster。五页overview实际查看，另完整查看Feeding第四段q617和第二段错接q172。32图的来源、ROI变换、所有支持/背景/弱/缺测以及实际发布前/q/后记录已绑定。',
    '失败图和诊断端点在预测seal/评分后生成，明确不是正式关联输入，不把未来发布timeline回填q。私有像素保留本地private；真实路径/bytes/SHA与复现依赖见RESTRICTED_ARTIFACTS。公开只包含代码、数值、mask引用、来源摘要及日志。',
    '本轮尚未达到超过原Z4Q/同源Native的新增深度收益；没有独立传感器精度标定、blind holdout或匿名联合候选方法的性能结果。保留真实缺证与不可评分，不宣称深度整体理论无效。','',
    '## 唯一下一步（已规划，未执行）','',
    '将“固定稳定伙伴见证”改为“两个当前匿名候选的联合身份解释”：保留两个旧身份的独立冻结pre来源，当前分割观测只作为匿名证据，比较完整H1/H2而不要求当前B已经认证为旧B；混合mask保留全部支持并边际化，缺测共同null。只在自动预测交互内进行合法、原子、发布前恢复，延续原Z4Q在无事件时的自身状态。不按GT挑候选或锚点，不通过删除generation检查来冒充连续观测。先一次冻结状态与来源测试，再做完整四源回放，不滚动加大权重到通过。这个方案仍需真实验证，尚未执行。','']
text='\n'.join(lines)
with (HERE/'FINAL_REVIEW.md').open('x',encoding='utf-8',newline='\n') as h:h.write(text)
nextplan=lines[-2]+'\n'
with (HERE/'NEXT_STEP_PLAN.md').open('x',encoding='utf-8',newline='\n') as h:h.write('# 唯一下一步：匿名双候选联合身份解释\n\n'+nextplan)
write_new(HERE/'NEXT_STEP_SELECTION.json',dict(status='PLANNED_NOT_STARTED',selected='ANONYMOUS_CURRENT_PAIR_JOINT_IDENTITY_EXPLANATIONS',
    evidence='All17wrongactionscheckedbut0fullpre/q; stable-current-partner predicate fails in the difficult events',
    old_pre_source_contract_preserved=True,current_identity_roles_are_hypotheses_not_observations=True,
    new_model_http=0,cost_usd=0,started=False))
write_new(HERE/'RESULTS.json',dict(status='FULL_REPLAY_COMPLETE_COST_CHANGED_NO_ASSOCIATION_INCREMENT',engineering='PASS_WITH_LOG_LAUNCH_RECOVERY',
    input='17_WRONG_ACTIONS_HAVE_NO_FULL_COMPARABLE_ORDER_INPUT',depth_increment='5_COST_UPDATES_ON_ONE_ALREADY_CORRECT_CHAIN_0_NEW_COMMITS_0_METRIC_GAIN',
    frames=20098,arms=ARMS,counts=a['counts'],comparison_counts=a['comparison_counts'],original_action_coverage=a['original_action_coverage'],
    metrics=m,all_original_actions_retained=True,new_identity_commits=0,new_model_http=0,cost_usd=0,
    uncompleted=['No new depth tracking gain','No sensor physical-accuracy calibration','No blind validation','Anonymous joint-pair method planned, not run']))
write_new(HERE/'REPORT_PROVENANCE.json',dict(report=artifact(HERE/'FINAL_REVIEW.md'),metrics=artifact(RUN/'METRICS.json'),
    mechanism=artifact(HERE/'MECHANISM_ANALYSIS.json'),postseal_QA=artifact(HERE/'POSTSEAL_QA.json'),
    real_visuals=artifact(HERE/'PRIVATE_VISUALS.json'),all_wrong_visuals=artifact(HERE/'FAILURE_VISUALS.json'),
    actual_visual_viewing=artifact(HERE/'VISUAL_ACCEPTANCE.json'),technical_recovery=artifact(HERE/'TECHNICAL_RECOVERY.json'),
    producer=artifact(__file__),report_metric_rows=36,new_model_http=0,cost_usd=0))
print('DS28 final report: 36 complete metric rows;5 real cost updates;0 association increment')
