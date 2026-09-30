"""Describe sealed actual results and render source-safe numerical figures."""
from common import *
from collections import Counter
import numpy as np

def main():
    import evaluate
    evaluate.verify_all_seals()
    m=read(RUN/'METRICS.json');pooled=m['pooled_metrics'];audit=read(RUN/'EVENT_AUDIT.json')
    native=pooled['SAM3_NATIVE'];events=audit['events']
    elapsed=sum(read(p)['elapsed_seconds'] for p in RUN.glob('*/public/RUN_SUMMARY.json'))
    execution=[json.loads(line) for line in (HERE/'EXECUTION_LOG.jsonl').read_text(encoding='utf-8').splitlines()]
    wall=next(x['elapsed_seconds'] for x in execution if x['command'][-2:]==[str(HERE/'launch.py'),'full'])
    lines=['# DS9：H0联合证据真实完整回放','',
        '## 主判定与分层','',
        '**达到同源native跟踪门槛，独立深度贡献需由消融另判。**' if m['frozen_support_rule_met'] else
        '**未达到利用深度超过同源native的冻结目标，停止此冻结版本。**',
        '工程链与方法指标分列；不把更多合格点、归一化后验或测试PASS当成深度有效。六枝均完整1471帧、各自真实状态，所有预测/访问seal后才独立官方TrackEval与参考核验。',
        '', '## 本轮修改','',
        '仅替换事件选择器：显式合法原生/既有alias H0，按物理映射去重；几何与深度含尺度归一化项和共同背景。几何均值沿原实际运动，past同版本下一点残差只估计一致性代理。保留DS8实际core提取、深度质量、风险历史、触发/q/参考以及首发布事务。',
        'J0为几何；J1原始深度；J2真实v2；ZERO完全删除深度似然且必须逐帧等于J0；PERMUTE仅错配当前两个post用于打分的深度，state仍接收原量。每次候选先关联/局部stage，后首次写当前帧；失败/H0继续自己的合法状态。没有改最终预测文件回填。',
        '', '## 完整同源主表','',
        '|分支|IDF1|HOTA|AssA|IDSW|FP|FN|','|---|---:|---:|---:|---:|---:|---:|']
    for a in ARMS:
        v=pooled[a];lines.append(f"|{a}|{v['IDF1']:.6f}|{v['HOTA']:.6f}|{v['AssA']:.6f}|{v['IDSW']}|{v['FP']}|{v['FN']}|")
    lines+=['','|对照|ΔIDF1|ΔHOTA|ΔAssA|ΔIDSW|','|---|---:|---:|---:|---:|']
    pairs=[(a,'SAM3_NATIVE') for a in ARMS[1:]]+[(a,b) for a,b in
        [('J1_RAW_DEPTH','J0_GEOMETRY'),('J2_RESTORED_DEPTH','J0_GEOMETRY'),
         ('J2_RESTORED_DEPTH','J2_DEPTH_ZERO'),('J2_RESTORED_DEPTH','J2_DEPTH_PERMUTE'),
         ('J2_RESTORED_DEPTH','J1_RAW_DEPTH')]]
    for a,b in pairs:
        d={k:pooled[a][k]-pooled[b][k] for k in ('IDF1','HOTA','AssA','IDSW')}
        lines.append(f"|{a}−{b}|{d['IDF1']:+.6f}|{d['HOTA']:+.6f}|{d['AssA']:+.6f}|{d['IDSW']:+d}|")
    lines+=['','pooled是在原TrackEval协议按segment命名空间合并计算，非四段率的平均；全部mask、残片、负ID都计分。每段成绩、深度覆盖、switch ledger、支持层详见run/METRICS.json、EVENT_AUDIT及SWITCH_LEDGER。',
        '', '## 首发布与实际动作','',
        '|枝|q数|真实COMMIT|首发布正确/错误/不可评分|','|---|---:|---:|---|']
    detail_rows=[]
    for a in ARMS[1:]:
        es=[e for e in events if e['arm']==a and e['q'] is not None]
        counts=Counter(e['first_public_physical'] for e in es)
        lines.append(f"|{a}|{len(es)}|{sum(e['status']=='COMMIT' for e in es)}|{dict(counts)}|")
        for e in es:
            archive=read(RUN/e['segment']/'public/EVENTS.json')[a]
            orig=next(x for x in archive if x['id']==e['event']);score=orig['numeric']['detail']
            detail_rows.append(dict(segment=e['segment'],arm=a,event=e['event'],original_q=e['original_q'],
                choice=orig['numeric']['choice'],status=e['status'],first_public=e['first_public_mapping'],
                expected=e['expected_mapping'],first_physical=e['first_public_physical'],
                pre_entry_reference=e.get('pre_entry_reference'),best=score.get('best'),margin=score.get('margin'),
                candidates=score.get('candidates'),depth_frozen=orig['depth_frozen'],
                post_pair_usable=score.get('post_pair_usable'),used_edges=score.get('used_edges')))
    write_new(HERE/'CASE_REVIEW.json',dict(events=detail_rows,
        note='Actual frozen-bank physical reference and entry status separated; UNKNOWN remains unscorable. No GT depth truth.'))
    lines+=['','实际选择、H0实际map、去重先验、每边density/background、残差fact、深度fact错配、首发布与局部事务都在逐事件JSON中。COMMIT表示相对当前合法映射实际改变；stage NO_ID_CHANGE不是新增恢复。首发布正确不等于修复了进入前旧错号；实际bank参考、进入前已错/未知和片段共识分列。',
        '', '## 输入、工程与证据边界','',
        '当前测量逐帧与DS8来源/抽取对照；native同源逐帧一致；ZERO与几何逐帧一致；所有旧678 tracked文件字节锁；所有预测、代码、来源、实际publisher和score封存绑定。',
        'v2来自真实已有full_v2，而非v3含标注补孔；其上游含RGB与未来i±1清理。J2仅已曝光离线开发诊断，不能宣称因果在线、独立录像泛化或鱼体表面/mm准确度。背景whole统计、MAD、噪声floor和条件独立只是冻结模型假设，不是物理真值或校准身份概率。',
        '完整来源/扫描/时间索引预加载；新选择器只用截至q的合法片段/current post。native HDF5底层I/O并非Python路径audit全覆盖；静态reader按当前图像行取值。既有v2未来支持单独揭示。',
        f'真实六枝全段回放总墙钟{wall:.3f}s，各段runner计时之和{elapsed:.3f}s，含IO/重投影/状态/日志，不含新SAM3且不称实时部署。新模型HTTP/smoke/训练/SAM3/补全服务=0，费用0。',
        '', '## 未完成边界与一个下一步','',
        '未完成：未建立独立鱼体表面/mm真值、v2因果等价或独立未曝光录像验证。该单次冻结试验不自动扩触发、调阈值、接入大模型或训练。',
        '唯一下一步已写入NEXT_STEP_PLAN.md：用同版本连续真实过去的下一点残差校准深度过程不确定性；仅规划，未启动。',
        '', '## 交付与复现','',
        '代码、CONFIG/PLAN、必要测试、真实slice链路、执行日志、六枝预测/metrics/事件/切换和数值图随main正常推送。私有像素/源RLE/GT/凭据不发布，RESTRICTED_INVENTORY列实际路径、字节、SHA与复现依赖；REMOTE_VERIFICATION记录实际ref及关键文件读取。旧archive/seal只读。','']
    (HERE/'RESULTS.md').write_text('\n'.join(lines),encoding='utf-8',newline='\n')
    import matplotlib;matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(12,4));x=np.arange(len(ARMS))
    for i,k in enumerate(('IDF1','HOTA','AssA')):ax.bar(x+(i-1)*.24,[pooled[a][k] for a in ARMS],width=.24,label=k)
    ax.set_xticks(x,['Native','Geometry','Raw','V2','Zero','Permute']);ax.set_ylim(50,100);ax.legend();ax.set_ylabel('Percent; all1471frames')
    fig.tight_layout();fig.savefig(HERE/'PERFORMANCE.svg');plt.close(fig)
    print('Actual sealed report and numeric visualization written')
if __name__=='__main__':main()
