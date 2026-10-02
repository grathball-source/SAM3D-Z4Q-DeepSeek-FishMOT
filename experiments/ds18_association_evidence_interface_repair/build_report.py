"""Full fixed-cohort results, isolated archived diagnosis and no result-driven rerun."""
from common import *
from collections import Counter

FIELDS=('IDF1','HOTA','AssA','IDSW','FP','FN')

def difference(a,b):return {k:a[k]-b[k] for k in FIELDS}

def main():
    metric=read(RUN/'METRICS.json');assert read(RUN/'SCORE_PROVENANCE.json')['reference_opened_after_all_seals']
    report=read(RUN/'POSTSEAL_REPORT.json');prior=read(DS17/'run/METRICS.json')
    scopes={name:x['metrics'] for name,x in metric['segments'].items()}
    scopes={'Feeding1471':metric['feeding_pooled']['metrics'],**{k:v for k,v in scopes.items() if not k.startswith('feeding_')}}
    oldscopes={'Feeding1471':prior['feeding_pooled']['metrics'],**{k:v['metrics'] for k,v in prior['segments'].items() if not k.startswith('feeding_')}}
    increments={k:{'vs_native':difference(v['MIXED_ORDER'],v['SAM3_NATIVE']),
        'vs_original_z4q':difference(v['MIXED_ORDER'],v['Z4Q_FROZEN']),
        'vs_same_interface':difference(v['MIXED_ORDER'],v['ACTIVITY_ORDER']),
        'ordinal_vs_off':difference(v['MIXED_ORDER'],v['MIXED_OFF']),
        'vs_archived_ds17':difference(v['MIXED_ORDER'],oldscopes[k]['MIXED_ORDER'])} for k,v in scopes.items()}
    actions=Counter();reference_actions=Counter();prior_reference=Counter();incidental_returns=0;groups=Counter();accepted=0;durable=0;q=0
    for name,s in report['segments'].items():
        a=s['automatic_actions']['MIXED_ORDER'];actions.update(a['physical_counts']);accepted+=a['accepted'];durable+=a['actual_durable_commits']
        reference_actions.update(a['actual_reference_physical_counts']);prior_reference.update(a['prior_public_reference_counts']);incidental_returns+=a['incidental_public_origin_returns']
        g=s['group_restores']['MIXED_ORDER'];groups.update(g['committed_pre_consensus']);q+=len(s['q_details']['MIXED_ORDER']['rows'])
    contracts={name:read(HERE/name)['status'] for name in ('CHECKS_R5.json','PREFIX_CHECKS.json','IMMUTABLE_EQUIVALENCE.json','IMMUTABLE_RECORD_EQUIVALENCE.json','REAL_SLICE_CHECKS.json','REAL_SLICE_SOURCE_SCORER.json','SOURCE_POPULATION_CHECKS.json','IMMUTABLE_FACTS_REVIEW.json')}
    gain=any(v['vs_same_interface']['IDF1']>1e-9 for v in increments.values())
    loss=any(v['vs_same_interface']['IDF1']<-1e-9 for v in increments.values())
    judgement=('COMPLETE_TRIAL_CONDITIONAL_DEPTH_GAIN_WITH_LOSSES' if gain and loss else
        'COMPLETE_TRIAL_CONDITIONAL_DEPTH_GAIN' if gain else 'COMPLETE_TRIAL_NO_SAME_INTERFACE_DEPTH_GAIN')
    summary=dict(status=judgement,frames_per_arm=20098,branch_frames=20098*6,arms=list(ARMS),
        metrics=scopes,differences=increments,source_state_checks=contracts,
        original_native_z4q_parity=read(RUN/'BASELINE_PARITY.json')['status'],
        archived_ds16_parity=read(RUN/'DS16_PARITY.json')['status'],
        mixed_automatic_accepted=accepted,mixed_actual_durable_commits=durable,
        mixed_automatic_physical=dict(actions),mixed_group_q=q,mixed_group_committed_pre_consensus=dict(groups),
        mixed_actual_reference_physical=dict(reference_actions),mixed_prior_public_reference=dict(prior_reference),mixed_incidental_origin_returns=incidental_returns,
        new_model_http=0,model_cost_usd=0,no_threshold_or_prompt_retuning=True,
        all_prediction_seal=artifact(RUN/'ALL_PREDICTIONS_SEALED.json'),metrics_artifact=artifact(RUN/'METRICS.json'),
        archived_ds17_metrics=artifact(DS17/'run/METRICS.json'),private_visuals=artifact(HERE/'PRIVATE_VISUALS.json'),
        limitations=['Exposed reused cohort; no independent generalization','L3/LW weak prediction-derived unreviewed references',
            'Mixture flags and source certification do not identify physical fish or validate actual occlusion topology',
            'Restoring original Z4Q gain is loss prevention, not new depth gain',
            'Saved SAM3 frontend zero-lookahead was not recertified; this association uses no future q frames'])
    write_new(HERE/'SUMMARY.json',summary)
    write_new(HERE/'MAIN_JUDGEMENT.json',dict(status=judgement,engineering=contracts,
        input='SAME_SOURCE_RAW_SEPARATE_ACTUAL_ROI_BINDINGS',depth_increment=summary['differences'],
        physical_surface_or_identity_truth='UNKNOWN',full_predictions_and_scoring_completed=True,
        no_automatic_new_experiment=True))
    lines=['# DS18 完整验收与结果','',f'主判定：`{judgement}`。完成六臂、八段、每臂 20098 帧；新增模型 HTTP/费用均为 0。','',
        '## 本轮修复','',
        'D1 whole、Birth 固定 exclusive core 与 S0 adaptive core 分别绑定实际 ROI/source population/标量，质量筛选不跨 ROI。匿名当前测量与个体历史认证分开；原出生时刻保留，失败提案待决，合法状态事务后才发布。Birth 所需 whole 反证缺失保持 UNKNOWN_NO_COMMIT；不删反证或给某边零代价。原 trigger/q、二维运动、参考、权重及候选含义固定。','',
        '## 完整主表','', '|范围|分支|IDF1|HOTA|AssA|IDSW|FP|FN|','|---|---|---:|---:|---:|---:|---:|---:|']
    for scope,arms in scopes.items():
        for arm,m in arms.items():lines.append(f'|{scope}|{arm}|{m["IDF1"]:.6f}|{m["HOTA"]:.6f}|{m["AssA"]:.6f}|{m["IDSW"]}|{m["FP"]}|{m["FN"]}|')
    lines+=['','## MIXED_ORDER 真实差值','', '|范围|参照|ΔIDF1|ΔHOTA|ΔAssA|ΔIDSW|','|---|---|---:|---:|---:|---:|']
    for scope,comparisons in increments.items():
        for base,d in comparisons.items():lines.append(f'|{scope}|{base}|{d["IDF1"]:+.6f}|{d["HOTA"]:+.6f}|{d["AssA"]:+.6f}|{d["IDSW"]:+d}|')
    lines+=['','旧 DS17 是只读归档诊断列，不混入本轮六臂。恢复原 Z4Q 的提升叫止损；相同接口底座上的增量才可归于本轮组合质量策略。少切换不等于更高 IDF1/HOTA/AssA。',
        '', '## 真实动作与边界','',f'MIXED_ORDER 原自动 accepted={accepted}，实际首次发布且 durable={durable}；实际bank参考相对物理判定 {dict(reference_actions)}；进入前公共身份语义 {dict(prior_reference)}；严格bank+公共起源联合判定 {dict(actions)}；偶然回到公共起源但不符合实际bank的次数={incidental_returns}，不算物理恢复。组 q={q}；实际提交的 pre 共识判定 {dict(groups)}。未知、不可评分与未提交没有算作正确。',
        '', '所有新增/消除切换、D1/BIRTH 来源、逐候选拒绝/缺测、group q 当前首帧映射与 literal/pre 共识分列见 run/POSTSEAL_REPORT.json、各段 AUTOMATIC_RECONNECT_AUDIT.json、EVENT_AUDIT.json 与 TRANSACTIONS.jsonl.gz。',
        '', '工程单测/真实前缀/实际 ROI 来源核对独立于指标。统计签名认证采样来源，不证明鱼身份；上下关系因子仍是有条件、未校准的代理。Feeding 是固定四段共1471帧，其余436保存帧未纳入。FishSA 旧开发/验证已曝光；L3/LW 为未审查预标注，不能称跨数据集强泛化。',
        '', '全部 mask、残片与 ID 都评分；每个分支继续自己状态。所有预测与访问封存后才评分，没有GT选动作或事后改历史。私有 depth/mask 可视化不进入 Git，完整本地路径/字节/SHA 见 PRIVATE_VISUALS.json 和 RESTRICTED_ARTIFACTS.json。',
        '', '## 复现与封存','',
        '测量事实与历史事实记录在内部验证后只读共享，150帧真实预测/证据与优化前完全一致；普通JSON输入仍完整验签。这是正常分支防写污染约束，不是隔离同进程恶意Python程序。第一次慢速工程前缀及后续LW旧存储前缀在正式冻结前终止，部分输出与日志保留在受限清单；四个已完成真实前缀保留，LW由最终存储版本重新回放。同样科学逻辑，仅存储优化，没有GT评分、模型调用或正式版本择优。',
        '', 'MIXED_DEPTH.jsonl.gz 是含完整分块SHA/字节数的JSONL引用；实际全量行在同目录MIXED_DEPTH.part*.jsonl.gz。common.rows验证每块后读取，未截断证据。',
        '', '实际新bank参考的恢复正确性、进入前公共ID起源是否已污染、严格联合判定分列。统一TrackEval评分公式未改变；移除“mask相同就必然FP/FN相等”的错误验收假设，记录真实FP/FN。官方CLEAR优先历史匹配，可因ID变化改变匹配数量；合成数学反例保存在EVALUATION_MASK_INVARIANT_CHECK.json，未读取真实GT。',
        '复用受限 DS14 来源与现有依赖，在全新输出目录依次运行 tests、source_population_check、check_prefix、check_real_slices、freeze、orchestrate、baseline_check、score、ds16_full_parity、postseal_report、visualize_postseal、build_report。不能覆盖旧目录/旧seal。EXECUTION_LOG.jsonl 保存实际命令、退出、耗时与完整日志摘要。',
        '', '本冻结版本完成后停止。下一步只在 NEXT_STEP_PLAN.md 规划；不自动调用大模型、训练或再次调参。']
    (HERE/'FINAL_REVIEW.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    (HERE/'RESULTS.md').write_text('\n'.join(lines[lines.index('## 完整主表'):])+'\n',encoding='utf-8')
    (HERE/'README.md').write_text('# DS18 关联证据接口修复\n\n先读 PLAN.md、FINAL_REVIEW.md、NEXT_STEP_PLAN.md。旧 DS17 与更早封存只读。本轮源像素/GT raster/凭据不公开。新增模型 HTTP/费用=0。完整指标和真实调用日志分别在 run/METRICS.json 与 EXECUTION_LOG.jsonl。\n',encoding='utf-8')
    print(judgement, json.dumps(increments),flush=True)

if __name__=='__main__':main()
