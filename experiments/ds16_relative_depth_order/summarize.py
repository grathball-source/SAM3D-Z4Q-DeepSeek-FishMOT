"""Full frozen-trial report; numeric gains, physical identities and order kept separate."""
from common import *
from collections import Counter

FIELDS=('IDF1','HOTA','AssA','IDSW','FP','FN')
BASES=('SAM3_NATIVE','Z4Q_FROZEN','Z4Q_STATE_FIXED','ORDER_OFF','ORDER_PERMUTE')

def main():
    scored=read(RUN/'METRICS.json');review=read(HERE/'POSTSEAL_ORDER_REVIEW.json')
    assert scored['status']=='SCORED_AFTER_ALL_SIX_ARMS_EIGHT_SEALS'
    assert read(RUN/'SCORE_PROVENANCE.json')['reference_opened_after_all_seals']
    from score import verify_all
    _,proof=verify_all()
    old=read(HERE/'OLD_READONLY_LOCK.json')['files']
    for p,digest in old.items():assert sha(ROOT/p)==digest,p
    units={n:r['metrics'] for n,r in scored['segments'].items() if not n.startswith('feeding_')}
    units['Feeding_pooled1471']=scored['feeding_pooled']['metrics']
    deltas={n:{b:{f:values['DEPTH_ORDER'][f]-values[b][f] for f in FIELDS} for b in BASES} for n,values in units.items()}
    counts={};cases=[]
    for name in SEGMENTS:
        events=read(RUN/name/'public/EVENTS.json')
        audits=read(RUN/name/'public/EVENT_AUDIT.json')['arms']
        automatic=read(RUN/name/'public/AUTOMATIC_RECONNECT_AUDIT.json')
        counts[name]={a:dict(automatic_physical=automatic['counts'][a],automatic_commits=sum(x['durable_automatic_commit'] for x in automatic['arms'][a])) for a in ARMS[1:]}
        for a in ARMS[2:]:
            e=events[a]
            counts[name][a].update(suspects=len(e),confirmed=sum(x['confirm_frame'] is not None for x in e),
                first_splits=sum(x['q'] is not None for x in e),group_commits=sum(bool(x.get('restore') and x['restore']['status']=='COMMIT') for x in e),
                statuses=dict(Counter(x['status'] for x in e)),group_physical=audits[a]['group_physical_counts'],
                order_reasons=dict(Counter(x['numeric']['detail'].get('order_evidence',{}).get('reason',x['numeric']['detail'].get('reason')) for x in e if x.get('numeric'))))
            cases.extend(dict(segment=name,arm=a,**x) for x in review['segments'][name]['cases'][a] if x['q'] is not None)
    own= [x for x in cases if x['arm']=='DEPTH_ORDER']
    committed=[x for x in own if x['restore_status']=='COMMIT']
    physical=dict(Counter(x['identity_reference_outcomes']['committed_pre_consensus_verdict'] for x in committed))
    stable=all(all(v['DEPTH_ORDER'][f]>v[b][f] for f in ('IDF1','HOTA','AssA') for b in ('SAM3_NATIVE','Z4Q_FROZEN')) and
        all(v['DEPTH_ORDER']['IDSW']<=v[b]['IDSW'] for b in ('SAM3_NATIVE','Z4Q_FROZEN')) for v in units.values())
    independent=any(x['restore_status']=='COMMIT' and x['score_decomposition'].get('order_changes_choice_on_same_input') and
        x['identity_reference_outcomes']['committed_pre_consensus_verdict']=='CORRECT' for x in own)
    judgement=dict(main='SUPPORTED_ON_EXPOSED_COHORT' if stable and independent else 'FROZEN_ORDINAL_SUPPORT_RULE_NOT_MET',
        engineering='PASS',input='SOURCE_BOUND_RAW_PASS; PHYSICAL_SURFACE_ORDER_UNKNOWN',
        ordinal='CORRECT_ORDINAL_SPECIFIC_RECOVERY_OBSERVED' if independent else 'NO_CERTIFIED_ORDINAL_SPECIFIC_RECOVERY',
        whole_cohort_superiority=stable,correct_ordinal_specific_recovery=independent,
        depth_order_commits=len(committed),committed_pre_consensus=physical,
        model_http=0,cost_usd=0,no_roll_after_freeze=True)
    write_new(HERE/'MAIN_JUDGEMENT.json',judgement)
    write_new(HERE/'SUMMARY.json',dict(status='COMPLETE_FROZEN_TRIAL',frames=20098,main_units=units,deltas=deltas,
        counts=counts,order_counts=review['counts'],main_judgement=judgement,
        metrics=artifact(RUN/'METRICS.json'),postseal_review=artifact(HERE/'POSTSEAL_ORDER_REVIEW.json'),
        old_unchanged_files=len(old),new_model_http=0,cost_usd=0))
    write_new(HERE/'FINAL_CHECKS.json',dict(status='PASS',proof=proof,old_unchanged_files=len(old),
        all_mask_and_public_bijections=True,all_prediction_access_seals_before_reference=True,
        all_source_and_q_fact_bindings=True,all_switches_recomputed=True,model_http=0,cost_usd=0))
    lines=['# DS16：事件内相对深度次序试验结果','',f"主判定：**{judgement['main']}**。完整六分支、八段20098帧；新增模型HTTP及费用均0。",
        '', '## 方法与归因边界','',
        '共同底座只冻结公共身份bank/view_bank；真实来源连续性、候选与alias保持更新。合并与未分配post不认证为个体pre。原两条自动规则保持，没有额外DS12出生修复。STATE_FIXED保留旧绝对深度组关联；ORDER三个分支使用同一资格、几何、参考、q和事务。启用次序时以一个相对关系因子替换绝对深度因子，置换只改打分绑定。',
        '代表core深度的次序、图像上下位置和真实局部遮挡拓扑分别理解。次序噪声与时间传播是未校准代理；单点和弱差值如实保留。没有物理表面深度GT，UNKNOWN、不可评分和回退不计正确。',
        '', '## 全段指标','', '| 数据 | 分支 | IDF1 | HOTA | AssA | IDSW | FP | FN |','|---|---|---|---|---|---|---|---|']
    for name,values in units.items():
        for arm in ARMS:
            v=values[arm];lines.append('| '+ ' | '.join([name,arm]+[f'{v[k]:.6f}' if k in ('IDF1','HOTA','AssA') else str(v[k]) for k in FIELDS])+' |')
    lines+=['','## DEPTH_ORDER相对对照的真实差值','', '| 数据 | 对照 | ΔIDF1 | ΔHOTA | ΔAssA | ΔIDSW |','|---|---|---|---|---|---|']
    for name,values in deltas.items():
        for base,value in values.items():lines.append(f"| {name} | {base} | {value['IDF1']:+.6f} | {value['HOTA']:+.6f} | {value['AssA']:+.6f} | {value['IDSW']:+g} |")
    lines+=['','## 首分离帧与物理恢复','',f'次序分支实际group提交{len(committed)}；连续pre片段共识判定：{physical}。',
        f"同请求去掉次序项诊断中，可评分正确且选择实际改变的恢复存在：{independent}。整个同源队列超过原生与原Z4Q的冻结标准：{stable}。单请求诊断与完整ORDER_OFF分支分开；分支状态发生分歧后的后续差异不能直接解释成同输入独立增量。",
        '全部事件、原始选择、stage拒绝、首次发布、端点/片段判定、UNKNOWN与无分离见POSTSEAL_ORDER_REVIEW.md/json和各段EVENT_AUDIT.json。完整每次切换见SWITCHES.json。',
        '', '## 数据、输入与耗时','',
        'FishSA8400及曝光验证2888独立初始化；Feeding原四段1471，另436保存帧未纳入原冻结协议；L3/LW为依赖预测预标注的弱参考诊断。全部已经曝光，不称盲测或独立录像泛化。原生与原Z4Q全部帧/指标精确复现DS15；保留所有mask、残片及ID评分。',
        f"评分及来源验证耗时{scored['elapsed_seconds']:.3f}秒。各段回放耗时见RUN_SUMMARY，实际启动/退出/命令见EXECUTION_LOG.jsonl。CPU3子进程各1线程，GPU、服务、模型调用、训练、SAM3推理、深度补全均0。", 
        f'旧追踪实验{len(old)}个文件SHA保持不变。冻结代码、source、publisher、次序fact和所有seal已实际核验。',
        '', '## 未完成边界','',
        '真实局部遮挡拓扑、毫米物理校准、独立视频泛化仍未验证；Feeding额外436帧未运行，L3/LW弱参考未人工独立验收。私有像素按真实路径/字节/SHA留本机，不能随公开仓库分发。',
        '', '## 一个下一步','',
        '围绕已封存交叉案例，核验代表core次序与局部真实遮挡关系的一致性及反转来源，再决定是否把关系证据收窄到交叉区域；本轮结束不自动改阈值或启动新实验。','']
    with (HERE/'RESULTS.md').open('x',encoding='utf-8',newline='\n') as f:f.write('\n'.join(lines))
    print(json.dumps(judgement,ensure_ascii=False))

if __name__=='__main__':main()
