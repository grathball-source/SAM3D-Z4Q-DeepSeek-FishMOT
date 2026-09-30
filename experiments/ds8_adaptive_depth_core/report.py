"""One postseal report; private physical pixels remain local."""
from common import *
from collections import Counter
import numpy as np

def main():
    metrics=read(RUN/'METRICS.json');audit=read(RUN/'EVENT_AUDIT.json')
    old=ROOT/'experiments/ds7_depth_native_recovery'
    before=read(old/'run/METRICS.json');pooled=metrics['pooled_metrics']
    actions={a:dict(Counter(e['status'] for e in audit['events'] if e['arm']==a and e['q'] is not None)) for a in ARMS[1:]}
    layers=metrics['score_support_layers']
    target_met=layers['P1_raw_tracking_support'] or layers['P2_offline_tracking_support']
    lines=['# DS7/DS8全面复盘、针对性修复与真实全段结果','',
        '## 主判定','',
        '**有深度分支超过同源原生，适用范围须按下面分层区分。**' if target_met else '**未达到“利用深度超过同源原生”目标。工程检查通过不等于方法有效。**',
        f"原始深度超过native={layers['P1_raw_tracking_support']}；离线v2超过native={layers['P2_offline_tracking_support']}；v2额外超过raw={layers['P2_restored_increment_vs_raw']}；更严格P2同时超过全部控制门槛={metrics['frozen_support_rule_met']}。",
        '本轮做完两次完整1471帧五枝回放，不挑容易事件、不丢mask；DS7身份发布/来源隔离后，DS8只改变core采样几何。全部预测封存后才读参考独立评分，新模型HTTP、smoke、训练、SAM3和补全服务调用均0，费用0。',
        '', '## 失败原因及本次针对性动作','',
        '1. **临时猜配污染发布基准。** 旧实验5个持续native本来对应正确的q实际交换双ID，却以preview为基准记录NO_ID_CHANGE；新增10次切换、另消除4次，净+6。DS7改为本分支合法native/已提交alias作发布基准，事件不充分时走自身局部因果步，不复制B0状态；恢复先提交再首次发布。P0逐帧与native等价是控制器止损，不算深度增量。',
        '2. **固定腐蚀误杀薄鱼的深度证据。** DS7 14个NONE post中13个core只有0–15像素，12个即使不剔重叠仍不足16；原鱼mask有108–365个有效raw点。填孔没有扩展空core。因此DS8按当前独占mask逐片真实距离变换取内部区，保留所有片；与原7核逐q比较，不改阈值、触发、q、参考或2D权重。',
        '3. **修复覆盖与物理归属不同。** tank/鱼/侧壁在同一mask内可能混层；MAD小也可能稳定取了另一表面。最大簇、盲目扩大区、混合实测和估计都可能错。DS7/8 retained优先、inferred单独，真实MAD和噪声适配代理分列，不拿宽尺度包含或RGB轮廓共识称mm准确率。',
        '4. **历史短、风险中断与缺测限制外推。** 不能跨接触、身份版本或缺帧凑速度。DS1局部405曾略好但新1066未重复；均值漂移消融旧输出相同，速度独立贡献未证实。DS7 F1280新增inferred虽列入两点历史，LAST_VALUE均值仍取较新retained，不能声称该新增点驱动WLS。',
        '5. **可决策事件范围与原生错误范围不匹配。** 108次原生切换大多不在合法双鱼首分离q；冻结mask/触发的身份层不补FN/FP、不分割共同mask。不能期望这次局部深度层消除全体错误。L3/LW/旧长录像上的收益并不证明在SOURCE_OLD分批输入上的同等收益；更细来源差异归因仍待专门验证。',
        '', '## 全1471帧主比较','',
        '|分支|IDF1|HOTA|AssA|IDSW|FP|FN|','|---|---:|---:|---:|---:|---:|---:|']
    for a,v in pooled.items():lines.append(f"|DS8 {a}|{v['IDF1']:.4f}|{v['HOTA']:.4f}|{v['AssA']:.4f}|{v['IDSW']}|{v['FP']}|{v['FN']}|")
    v=before['pooled_metrics']['P2_RESTORED_DEPTH']
    lines.append(f"|DS7 P2 frozen 7核|{v['IDF1']:.4f}|{v['HOTA']:.4f}|{v['AssA']:.4f}|{v['IDSW']}|{v['FP']}|{v['FN']}|")
    lines+=['','所有分段与完整变化见run/METRICS.json； pooled是在同一TrackEval协议合并ID命名空间后计算，非逐段平均。负ID及所有mask均计分，逐切换ledger合计必须等于官方IDSW。',
        '', '|P2相对|ΔIDF1|ΔHOTA|ΔAssA|ΔIDSW|','|---|---:|---:|---:|---:|']
    for label,v in [('SAM3_NATIVE',pooled['SAM3_NATIVE']),('P0',pooled['P0_NATIVE_PRESERVE']),('P1_RAW',pooled['P1_RAW_DEPTH']),('DS7_P2',before['pooled_metrics']['P2_RESTORED_DEPTH'])]:
        d={k:pooled['P2_RESTORED_DEPTH'][k]-v[k] for k in ('IDF1','HOTA','AssA','IDSW')}
        lines.append(f"|{label}|{d['IDF1']:+.4f}|{d['HOTA']:+.4f}|{d['AssA']:+.4f}|{d['IDSW']:+d}|")
    lines+=['','## 事件、工程与输入边界','',f'实际q提交状态：{actions}。',
        '模型原始结果不存在；这些全是固定数值深度选择。正确/错误/不可评分、首发布映射、进入前已错与片段事后共识、真实stage及数值fallback均在EVENT_AUDIT与逐q复盘分列。无stage或不可评分不计成功。',
        '旧D2全1471帧逐条复现DS6；P0原生逐条一致；新的P1/P2独立自身状态；所有代码、source、每帧发布与响应无关的事务均实际封存绑定。DS1–6旧456文件、DS7冻结代码与seal保持字节不变。',
        '使用实际native full_v2三H5按当前帧读取并重新投影，未读v3 annotation补孔。其上游清洗用了i±1及RGB，故P2只为已曝光开发集离线修复诊断，不能称因果在线或独立验证。原始P1单列。没有独立物理表面/mm真值；像素筛选的物理准确度仍UNKNOWN。',
        '完整来源、扫描、assignments及时间索引会预加载；关联计算仅取当前及合法pre截至q，不能字面称未读任何q之后的bytes。新ROI从当前mask独立计算，不使用未来mask改变本帧ROI；v2上游未来支持另行标记。',
        '测试仅验证几何、缺测、来源/噪声语义与真实事务不污染，不替代性能试验。一次初始slice在任何FREEZE文件生成前因缺测试报告退出；补齐已通过控制器测试的实际报告后重新开始，未产生或重用研究预测。日志保留。',
        '', '## 修复计划与下一步','',
        '已执行：①修复合法发布基准与来源分层，完整DS7；②基于真实薄鱼几何不足，单独自适应core，完整DS8。关联gap log9没有按已知答案改成8，未添加GT选择、换锚或二次投票。',
        '唯一下一步：冻结当前提取，设计一个显式保留原生/不接回H0的联合几何—深度事件关联对照，并以深度置零与深度错配消融检验实际恢复是否由深度造成；先记录clean片段预测残差，残差校准只是代理而非物理mm真值，不自动加入大模型。',
        '详细未执行的唯一下一步规格见NEXT_STEP_PLAN.md；它不预报提点，也不代替新冻结试验。',
        '复现、真实耗时、受限产物路径/字节/SHA、源与输出seal见README、run/PERFORMANCE、EXECUTION_LOG及RESTRICTED_INVENTORY。main实际远端ref与关键文件读取核验见REMOTE_VERIFICATION。',
        '']
    (HERE/'RESULTS.md').write_text('\n'.join(lines),encoding='utf-8',newline='\n')
    import matplotlib;matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    labels=['Native','DS7 P2','DS8 raw','DS8 v2']
    vals=[pooled['SAM3_NATIVE'],before['pooled_metrics']['P2_RESTORED_DEPTH'],pooled['P1_RAW_DEPTH'],pooled['P2_RESTORED_DEPTH']]
    fig,ax=plt.subplots(figsize=(9,4));x=np.arange(4)
    for i,k in enumerate(('IDF1','HOTA','AssA')):ax.bar(x+(i-1)*.25,[v[k] for v in vals],width=.25,label=k)
    ax.set_xticks(x,labels);ax.set_ylim(60,100);ax.set_ylabel('Percent; all1471frames');ax.legend()
    fig.tight_layout();fig.savefig(HERE/'PERFORMANCE.svg');plt.close(fig)
    # Fixed failure frames chosen before DS8 prediction; only visualize after seals.
    from depth_measurement import decode,KERNEL
    from adaptive_core import adaptive_core
    from restored_source import RestoredDepth
    import cv2
    source=RestoredDepth();figs=[]
    for f in (519,764,1390,1745,1805):
        name=next(n for n,(a,b) in SEGMENTS.items() if a<=f<=b);local=f-SEGMENTS[name][0]+1
        assignment=next(r for r in rows(input_dir(name)/'assignments.jsonl.gz') if r['frame']==local)
        masks={int(k[2:]):decode(v) for k,v in assignment['masks'].items()}
        occupancy=sum((m.astype('u2') for m in masks.values()),np.zeros((360,640),'u2'))
        prediction=next(r for r in rows(RUN/name/'public/predictions.jsonl.gz') if r['frame']==local)
        dep,prov,_=source(f)
        with np.load(DATA/'depth_rgb_640x360'/f'{f:06d}.npz') as src:raw=src['depth_mm']
        fig,axes=plt.subplots(1,3,figsize=(15,4))
        for ax,arm,values in zip(axes,('SAM3_NATIVE','P1_RAW_DEPTH','P2_RESTORED_DEPTH'),(raw,raw,dep)):
            ax.imshow(np.ma.masked_less_equal(values,0),vmin=600,vmax=1500,cmap='viridis')
            mapping={int(z['mask'][2:]):z['id'] for z in prediction['variants'][arm]}
            for n,mask in masks.items():
                adaptive,_=adaptive_core(mask,occupancy)
                fixed=cv2.erode((mask&(occupancy==1)).astype('u1'),KERNEL).astype(bool)
                ax.contour(mask,levels=[.5],colors='white',linewidths=.3)
                if fixed.any():ax.contour(fixed,levels=[.5],colors='red',linewidths=.4)
                if adaptive.any():ax.contour(adaptive,levels=[.5],colors='cyan',linewidths=.4)
                yy,xx=np.nonzero(mask);ax.text(float(xx.mean()),float(yy.mean()),str(mapping[n]),color='white',fontsize=6)
            ax.set_title(arm,fontsize=10);ax.axis('off')
        fig.suptitle(f'F{f}: actual published IDs; white=SAM3, red=fixed core, cyan=adaptive; no GT/RGB')
        fig.tight_layout();p=HERE/'private/visualizations'/f'F{f:06d}.png';p.parent.mkdir(parents=True,exist_ok=True)
        fig.savefig(p,dpi=130);plt.close(fig);figs.append(artifact(p))
    source.close()
    write_new(HERE/'VISUALIZATION_INVENTORY.json',dict(private_depth_and_actual_publication_figures=figs,
        no_GT_RGB_pixels=True,not_for_git=True))
    print('Report and private fixed-case figures complete')
if __name__=='__main__':main()
