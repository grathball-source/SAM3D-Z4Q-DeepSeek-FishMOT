"""Final interpretation only after full seals, scoring and actual-store audit."""
from common import *
from collections import Counter
from report import require_complete


def main():
    metric=require_complete()
    audit=read(HERE/'CONFIRMATION_AUDIT.json')
    assert audit['status']=='PASS_ACTUAL_PENDING_VERSION_ANCHOR_AND_PUBLICATION_ISOLATION'
    post=read(RUN/'POSTSCORE_SUMMARY.json')
    prefix=read(HERE/'CONFIRMATION_SLICE_CHECKS.json')
    assert prefix['status']=='PASS' and read(HERE/'CHECKS.json')['status']=='PASS'
    units=post['units'];primary='MIXED_ISOLATED'
    paired={name:value['deltas']['MIXED_ISOLATED_minus_ACTIVITY_ISOLATED'] for name,value in units.items()}
    # An explicit descriptive check, not a claim of independent significance.
    positive=[name for name,delta in paired.items() if delta['IDF1']>1e-9 or delta['HOTA']>1e-9]
    negative=[name for name,delta in paired.items() if delta['IDF1'] < -1e-9 or delta['HOTA'] < -1e-9]
    joint=Counter();orders=Counter()
    for name in SEGMENTS:
        for event in read(RUN/name/'public/EVENTS.json')[primary]:
            if event['q'] is not None:
                joint[(event.get('restore') or {}).get('status','ABSENT')]+=1
                orders[((event.get('numeric') or {}).get('detail',{}).get('order_evidence') or {}).get('status','ABSENT')]+=1
    new_returns=[case for case in post['local_return_cases'] if case['arm'] in ISOLATED_ARMS]
    status=('COMPLETE_CONFIRMATION_REPAIR_MIXED_DEPTH_INCREMENT_OBSERVED_WITH_LIMITS'
        if positive and not negative else 'COMPLETE_CONFIRMATION_REPAIR_DEPTH_GOAL_NOT_ESTABLISHED')
    layers=dict(completion='All eight sources and six independent own-state columns completed',
        confirmation_isolation=audit['status'],source_scoring='PASS all old-control parity and actual source/seal/publication contracts',
        input='Original raw depth and immutable DS18 current-frame facts; pre-pair/scale limitations unchanged',
        depth_increment='Descriptive paired positive/negative units kept separately; no independent significance or physical depth accuracy claim',
        physical='Actual bank and public origin grades separate; UNKNOWN remains UNSCORABLE; L3/LW weak references',
        scope='D1 conservative no-current-neighbor route; Birth coverage not established',
        generalization='Reused exposed cohorts, not new independent validation')
    write_new(HERE/'SUMMARY.json',dict(status=status,layers=layers,frames_per_arm=20098,column_frames=120588,
        arms=list(ARMS),comparisons=units,paired_depth_positive_units=positive,paired_depth_negative_units=negative,
        primary_S0_status=dict(joint),primary_order_evidence_status=dict(orders),new_local_returns=new_returns,
        models=dict(new_model_http=0,smoke=0,training=0,SAM3=0,completion_service=0,cost_usd=0),
        sources=[artifact(RUN/'METRICS.json'),artifact(RUN/'SCORE_PROVENANCE.json'),
            artifact(HERE/'CONFIRMATION_AUDIT.json'),artifact(HERE/'CONFIRMATION_SLICE_CHECKS.json'),
            artifact(RUN/'POSTSCORE_SUMMARY.json')]))
    lines=['# DS20 最终复盘：确认状态隔离与深度增量分列','',f'主判定：**{status}**。',
        '', '完整八段六列，每列20098帧，所有预测封存后统一评分；四个归档控制逐帧及完整指标精确复现DS19。',
        '实际确认状态隔离审计覆盖40196个新分支帧，比较真实提交后字典、版本、精确anchor、普通优先级与publisher。工程通过不能替代深度增量或物理身份正确性。',
        '', '## 主分支完整指标','',
        '| 数据 | IDF1 | HOTA | AssA | IDSW | FP | FN | IDF1−同源SAM3 | IDF1−原Z4Q | IDF1−旧MIXED_RETURN | IDF1−ACTIVITY_ISOLATED |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for name,value in units.items():
        m=value['metrics'][primary];d=value['deltas']
        lines.append('| '+name+' | '+' | '.join(f'{m[k]:.6f}' for k in ('IDF1','HOTA','AssA'))+
            ' | '+' | '.join(str(m[k]) for k in ('IDSW','FP','FN'))+' | '+' | '.join(
                f'{d[primary+"_minus_"+base]["IDF1"]:+.6f}' for base in
                ('SAM3_NATIVE','Z4Q_FROZEN','MIXED_RETURN','ACTIVITY_ISOLATED'))+' |')
    lines+=['', '全部六列、八片段、Feeding独立ID域汇总和逐次新增/消除切换见RESULTS.md与run/POSTSCORE_SUMMARY.json。百分差值均为百分点，不跨数据集混成单一总分。',
        '', '## 状态修复与真实切片','',
        '普通pending原样自然推进；事件边使用独立的事件代/来源代/身份版本/精确anchor/target键，私有proposal不借普通同目标计数。普通合法重接、换版、换锚、占用和原0.2/0.5秒窗口失效时切断事件进度。保留原矩阵、5次确认、出生窗、触发、q和实际局部事务。',
        '首次公开造成实际身份版本变化时，旧事件键重新开始；这会影响自然接受时间，实际延迟必须报告，不能假设与DS19完全相同。已公开历史不回填，失败/timeout不整套复制B0。',
        '4190帧真实前缀的两竞争窗和L3自然返回见CONFIRMATION_SLICE_CHECKS.md；完整确认进度、普通接受与消费见CONFIRMATION_AUDIT.md。',
        '', '## 新分支显式局部返回','',
        '| 数据/分支 | 原帧 | source→public | bank物理 | 公共ID旧来源 | 保守判定 | 从首次发布延迟/帧 |',
        '|---|---:|---|---|---|---|---:|']
    for item in new_returns:
        lines.append(f'| {item["segment"]}/{item["arm"]} | {item["global_frame"]} | {item["source"]}→{item["target"]} | {item["actual_reference_physical"]} | {item["prior_public_reference_status"]} | {item["physical"]} | {item["return_delay_since_first_source_frames"]} |')
    if not new_returns:lines.append('| 全部 | — | 无显式提交 | — | — | — | — |')
    lines+=['', '## 深度结果与未完成边界','',
        f'组合深度相对同底座活动列：出现正IDF1或HOTA差值的单位={positive}；出现负差值的单位={negative}。完整有符号差值保留，不能选择最好数据或重复。',
        f'主分支首分离状态={dict(joint)}；顺序证据状态={dict(orders)}。fallback、UNKNOWN和不可评分不升级为成功。',
        '当前共同几何/深度历史缺口、各对象latest片段不共时、未校准宽scale及whole/core中位数与局部遮挡关系的差异仍未修复；本轮只处理确认状态。深度表面身份真值未知，L3/LW预测派生弱参考不作盲测。D1无邻居范围不能称Birth路径全覆盖。',
        '', '## 过程、可视化与交付','',
        '冻结前R1工程前缀因私有proposal借普通同目标旧计数的合同缺口被主动终止，三个经PID/命令核验的本任务进程和父流程全部落账；原源码、部分切片及日志保留，不评分、不混入R2。真实自然count1→4构造验证修复，10项正式单测通过。开发原型测试只有工具输出，没有持久stdout，不伪造日志；完整正式检查由execute记录。见ENGINEERING_PREFIX_ABORT.json、CONSTRUCTION_REVIEW.md。',
        '正式回放/评分/audit/report退出码和耗时见EXECUTION_LOG.jsonl。最多六个本地CPU单线程片段作业，CUDA空；模型HTTP/smoke/训练/SAM3/补全服务/费用均0，不代表实时部署。',
        '固定Feeding195、LW952、L33025及实际返回前中后深度/mask图为封存后诊断，未来列明确标注且不进入预测。公开图仅聚合数字；私有像素列RESTRICTED_ARTIFACTS真实路径/字节/SHA/依赖，GT raster、RGB、凭据不公开。',
        '旧seal只读，公共代码/配置/测试/完整数字预测与事务/评分/报告同步main，远端ref与文件字节实际核验，更新HANDOFF。',
        '', '## 唯一下一步','', '仅规划NEXT_STEP_PLAN.md中的一个后续步骤，不在本轮自动启动。','']
    with (HERE/'FINAL_REVIEW.md').open('x',encoding='utf-8',newline='\n') as f:f.write('\n'.join(lines))
    print(status,len(new_returns),'new local returns')


if __name__=='__main__':main()
