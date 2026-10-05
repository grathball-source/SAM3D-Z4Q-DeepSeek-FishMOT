"""Postseal interpretation from exact action/query facts; no experiment mutation."""
from common import *
from collections import Counter
import math
import score

score.verify_all()
a=read(HERE/'ANALYSIS_POSTSEAL.json');assert a['status'].startswith('PASS')
legal=Counter();actions=Counter();wrong=[]
for name,segment in a['segments'].items():
    for phase in segment['query_forecast_diagnostics']['original_eligible_queries']['by_phase'].values():
        legal.update({reason:group['queries'] for reason,group in phase['by_reason'].items()})
    for action in segment['original_accepted_action_followup']:
        actions[action['original_physical']]+=1
        if action['original_physical']!='WRONG':continue
        candidate=action['depth_same_frame_actions'];assert len(candidate)==1
        check=candidate[0]['event']['depth_veto']
        assert (check['frame'],check['native_id'],check['canonical_id'],check['phase'])==(
            action['frame'],action['native_id'],action['canonical_id'],action['phase'])
        current=check['current'] or {};forecast=check['forecast'] or {}
        measured=current.get('z_mm');predicted=forecast.get('mu_mm')
        difference=abs(measured-predicted) if current.get('usable') and forecast.get('usable') else None
        if difference is not None:assert math.isfinite(difference)
        wrong.append(dict(segment=name,frame=action['frame'],global_frame=action['global_frame'],phase=action['phase'],
            native_id=action['native_id'],canonical_id=action['canonical_id'],query_reason=check['reason'],
            physical_original=action['original_physical'],physical_extra_bank=action['extra_reference_physical_judgment'],
            references_differ=action['original_scoring_anchor_differs_from_extra'],original_reference=action['original_reference'],
            extra_reference=check['anchor'],query_fact_id=current.get('fact_id'),
            measured_current_mm=measured,predicted_mu_mm=predicted,predicted_scale_mm=forecast.get('scale_mm'),
            actual_numeric=action['query_numeric_diagnostics'],
            runtime_residual_mm=check.get('residual_mm'),runtime_threshold_mm=check.get('threshold'),
            postseal_diagnostic_abs_residual_mm=difference,
            diagnostic_is_not_a_runtime_test_or_actual_veto=True,
            actual_target_fragment_break=action['exact_target_fragment_preceding_break']))
assert sum(legal.values())==a['totals']['original_eligible_edges']==1552
assert actions==Counter(WRONG=17,CORRECT=16,UNSCORABLE=57)
assert Counter(x['query_reason'] for x in wrong)==Counter(TARGET_FORECAST_TOO_BROAD=14,
    TARGET_INSUFFICIENT_CONTIGUOUS_HISTORY=2,TARGET_ANCHOR_CHANGED_OR_UNREGISTERED_REFERENCE=1)
assert all(x['physical_extra_bank']['physical']=='WRONG' for x in wrong)
assert all(not x['actual_target_fragment_break'].get('preceding_break',{}).get(
    'pure_unreliable_current_depth_interruption',False) for x in wrong)
assert a['totals']['legal_edges_deleted']==a['totals']['changed_frames']==0
write_new(HERE/'INTERPRETATION_FACTS.json',dict(original_eligible_reason_counts=dict(legal),original_action_counts=dict(actions),
    all_original_wrong_actions=wrong,all_wrong_actions_extra_bank_independently_wrong=True,
    postseal_diagnostic_differences_do_not_fill_missing_runtime_residual=True,
    source_analysis=artifact(HERE/'ANALYSIS_POSTSEAL.json'),helper=artifact(__file__),model_http=0,cost_usd=0))

text=['### 分层结论','',
    '工程通过：两条真实矩阵入口、来源/状态/首次发布与评分封存链跑通。输入是实际同源SAM3和原始深度；观察来源连续性只按当前合同认证，不等于物理身份已认证。深度增量未观察到：全段10509条查询，1552条原合法候选，0条可靠矛盾/实际删边，三分支中的本轮版与原Z4Q所有发布和六项指标完全一致。', '',
    '1552条原合法候选分解：728条预测过宽，698条连续可靠历史不足，115条精确anchor未注册/已改变，1条当前深度不可靠；只有10条进入实际残差比较，全部位于LW弱参考段，均无冲突。其余8957条原非法候选不算新增保护。9508条当前质量可用与4071条WLS查询不能当成可靠否决覆盖率。', '',
    '实际原接受动作90次，按各段现有参考为17错误、16正确、57不可评分；16正确包含2次弱参考判定。全部17错误位于Feeding，15次D1_DELAYED、2次BIRTH_REFINE。14次被预测尺度上限挡住，2次分别仅有1/2点，1次anchor未注册；没有一次进入可靠冲突检验。额外bank参考逐例独立核验也均为不同物理参考；F1390的原打分参考与额外bank参考不同，不能无条件移用原判定。', '',
    '14次错误WLS的实际拟合跨度只有0.166–0.299秒，预测尺度94.051–1067.153mm。全部原合法WLS查询的拟合跨度中位数0.299秒，预测尺度中位数406.827mm。这里尺度是未标定的不确定性代理；短窗斜率与过程项外推到数秒以后，已无法满足本轮≤60mm合同。这揭示短窗预测在实际重接时距上未提供可用否决证据；更窄尺度是否物理合理仍UNKNOWN，不能证明正确物理区间应该只有60mm，也不能靠截断尺度制造可靠性。', '',
    'F159错误边native26→public16：0.299秒历史外推4.817秒，尺度378.332mm；当前实际core深度1190.704mm，预测1185.651mm，事后诊断差仅5.053mm。它说明宽尺度不是唯一障碍，错误身份也可能处于近似深度。F468是BIRTH_REFINE，0.299秒外推2.725秒，尺度224.808mm；不能因kind=reconnect误写成D1。', '',
    '可绑定的16条错误目标片段均没有“仅UNRELIABLE_CURRENT_DEPTH中断”的前置断点，另1条无法绑定。两个短历史错误来自真实接触后新片段；不可跨接触取旧点。纯软件深度断点只出现在其他正确/不可评分动作，不能预报只续接缺测历史就能解决这17次错误；UNRELIABLE_CURRENT_DEPTH本身也不等于传感器空洞。', '',
    '原Z4Q的159次CLEAR切换中，34次有当帧对应D1/Birth接受，125次无这两入口的当帧接受；后125次均有native同gt_id/global_frame切换。该事实仅描述覆盖，不能推断无查询、无更早alias影响，或全部为SAM3根因。净切换差与每次新增/消除记录分开。', '',
    'F364原Z4Q本来就保留native30/66，本轮未新增修复；F3902原Birth native7→public0动作及当帧映射完整保留。没有可靠矛盾触发，ALLOW/VETO反事实未运行，这是证据边界；没有伪造一个“成功保护”样例。', '',
    '### 全部17条错误边：运行事实与事后诊断分列','',
    '下表帧为global_frame。当前值来自实际exclusive-core测量；mu/尺度来自预测，不是观测。事后差仅对已存在且usable的预测与实际观测计算；运行在宽尺度/短历史等处早停，原运行残差及阈值仍为缺失。本表不代表曾执行放宽阈值试验。完整来源、两参考、断点与fact_id见INTERPRETATION_FACTS/ANALYSIS_POSTSEAL。','',
    '|来源|帧|阶段|native→public|原运行原因|当前mm|预测mu mm|预测尺度mm|事后差mm|',
    '|---|---:|---|---|---|---:|---:|---:|---:|']
def fmt(value):return 'UNKNOWN' if value is None else f'{value:.3f}'
for x in wrong:
    text.append('|'+str(x['segment'])+'|'+str(x['global_frame'])+'|'+x['phase']+'|'+
        str(x['native_id'])+'→'+str(x['canonical_id'])+'|'+x['query_reason']+'|'+
        '|'.join(fmt(x[k]) for k in ('measured_current_mm','predicted_mu_mm','predicted_scale_mm','postseal_diagnostic_abs_residual_mm'))+'|')
text+=['','该冻结版本结束。工程PASS和原Z4Q既有优势不是本轮深度收益；没有有效否决边，因此可靠冲突的精度/召回及因果反事实收益仍不可估计。']
path=HERE/'INTERPRETATION.md';assert not path.exists();path.write_text('\n'.join(text)+'\n',encoding='utf-8')
print('POSTSEAL_INTERPRETATION',dict(legal),dict(actions),flush=True)
