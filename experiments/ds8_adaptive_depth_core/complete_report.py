"""Append audited aggregate facts without changing predictions/scoring/code seals."""
from common import *
def main():
    p=HERE/'RESULTS.md';text=p.read_text(encoding='utf-8')
    assert '## 封存后的针对性结论' not in text
    old=ROOT/'experiments/ds7_depth_native_recovery'
    times={trial.name:sum(read(x)['elapsed_seconds'] for x in (trial/'run').glob('*/public/RUN_SUMMARY.json'))
        for trial in (old,HERE)}
    events=read(RUN/'EVENT_AUDIT.json')['events'];cases=[]
    for e in events:
        if e['arm']!='P2_RESTORED_DEPTH' or e['first_public_physical']!='WRONG':continue
        whole=read(RUN/e['segment']/'public/EVENTS.json')['P2_RESTORED_DEPTH']
        event=next(x for x in whole if x['id']==e['event']);detail=event['numeric']['detail']
        cases.append(dict(original_q=e['original_q'],status=e['status'],
            first_public=e['first_public_mapping'],expected=e['expected_mapping'],
            history={r:len(x['samples']) for r,x in event['depth_frozen'].items()},
            used_edges=detail.get('used_edges'),post_pair_usable=detail.get('post_pair_usable'),
            gap=detail.get('depth_log_odds_gap'),
            pre_entry_reference=e['pre_entry_reference']))
    bindings=[artifact(RUN/'SCORING_SEALED.json'),artifact(RUN/'EVENT_AUDIT.json'),
              artifact(HERE/'POSTRUN_REVIEW.json'),artifact(HERE/'POSTRUN_EXIT.txt')]
    assert int((HERE/'POSTRUN_EXIT.txt').read_text(encoding='utf-8-sig'))==0
    write_new(HERE/'COMPLETION_EVIDENCE.json',dict(reference_cases=cases,bindings=bindings,
        elapsed_replay_seconds=times,
        observed_images=[519,764,1390,1745,1805],new_model_http=0,cost_usd=0))
    add=['','## 封存后的针对性结论','',
        '当前q post资格：P2从24/38到37/38（14新增、1失；36retained、1inferred、1NONE）；P1到36/38（13新增、1失）。增加的是合格测量覆盖，不是已认证鱼体表面或独立身份信息。',
        '17个有numeric候选的q中，P2有16个当前pair可用，但5事件至少一侧pre历史缺失、16个候选gap未达log9、9个深度与combined方向不一致，原因可重叠。仅F519 gap=3.282432通过H2，公开映射仍50→50、24→24，没有实际身份改变。P1全部17个gap未达log9，0选择通过。',
        'F1745/n190：ROI由99到194，retained实际MAD40.526733mm，对应1.4826×MAD=60.084934mm，略超冻结60mm规则，仍为NONE。它证明扩大采样可以改变表面混合与资格，不证明该阈值物理正确；未按GT将其放宽。F1390/F1805等仍弱，不能把16个未通过写为16次模型错误。',
        '因此两次修复解决了公开身份污染与薄鱼采样不足，却尚未产生任何相对原生的实际恢复。单靠填孔/增点不足以实现目标，当前原生先验之外的联合证据模型及来源不确定性仍是待验证假设。完整逐q事实见POSTRUN_REVIEW；因果分层见下一步规格。',
        '', '|冻结参考下原生首发布WRONG q|pre样本A/B|used edges|gap|本轮动作|','|---|---:|---:|---:|---|']
    for c in cases:
        h=c['history'];gap=c['gap']
        add.append(f"|F{c['original_q']}|{h.get('A',0)}/{h.get('B',0)}|{c['used_edges']}|{gap:.6f}|{c['status']}|")
    add+=['','这些行以实际冻结anchor参考评分；进入前身份是否已与anchor不同、不可评分与片段共识在EVENT_AUDIT中分列，不把全局旧错号偶然换回称作物理恢复。',
        '',f"真实离线回放耗时：DS7 {times[old.name]:.3f}s；DS8 {times[HERE.name]:.3f}s（各五枝1471帧，含IO/重投影/状态/日志，未跑SAM3，不是在线部署延迟）。",
        '必要检查：DS7 4数值/来源+13真实控制器+5评分合成；DS8 10几何+5测量+13真实控制器+5评分合成，随后两次真实全段。最终全1471帧控制/背景一致性、75q边界、728冻结样本pre边界和代码/访问seal另经只读复核。',
        '', '唯一下一步已写成可冻结规格：[NEXT_STEP_PLAN](NEXT_STEP_PLAN.md)，尚未执行。它测试显式原生H0下的联合证据，使用geometry/深度置零/深度错配控制，不滚动降低本轮门槛。',
        '受限图已实际查看，仅本地保留。DS7/DS8代码、配置、测试、日志、数值预测、指标、逐事件/切换与报告统一由DS8/finalize_delivery.py交付；DS7旧的单独delivery脚本本轮未执行。','']
    p.write_text(text+'\n'.join(add),encoding='utf-8',newline='\n')
    execution=read(HERE/'EXECUTION_LOG.json')
    execution['entries'].append(dict(step='POSTRUN',exit_code=0,log=artifact(HERE/'POSTRUN_LOG.txt'),
                                    result=artifact(HERE/'POSTRUN_REVIEW.json')))
    (HERE/'EXECUTION_LOG.json').write_text(__import__('json').dumps(execution,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print('Added sealed case evidence and aggregate diagnosis')
if __name__=='__main__':main()
