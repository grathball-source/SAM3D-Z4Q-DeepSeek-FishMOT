"""Postseal numerical evidence, depth coverage and raw/restored case figures."""
from common import *
from collections import Counter
import gzip,importlib.util
def main():
    m=read(RUN/'METRICS.json');audit=read(RUN/'EVENT_AUDIT.json')
    actions={};choices={};coverage=Counter();changes=[]
    for arm in ARMS[1:]:
        events=[e for e in audit['events'] if e['arm']==arm and e['q'] is not None]
        actions[arm]=dict(Counter(e['status'] for e in events))
        choices[arm]=dict(Counter(e['selected_choice'] for e in events))
    for name,(start,stop) in SEGMENTS.items():
        public=RUN/name/'public'
        obs={x['frame']:x for x in rows(public/'DEPTH_OBSERVATIONS.jsonl.gz')}
        ev=read(public/'EVENTS.json')
        for row in obs.values():
            for r in row['restored'].values():
                coverage[r['cohort']]+=1
        by={arm:{e['q']:e for e in series if e['q'] is not None} for arm,series in ev.items()}
        for q in sorted(set(by['P1_RAW_DEPTH'])|set(by['P2_RESTORED_DEPTH'])):
            values={}
            for arm in ('P0_NATIVE_PRESERVE','P1_RAW_DEPTH','P2_RESTORED_DEPTH'):
                e=by[arm].get(q)
                if e:
                    values[arm]=dict(event=e['id'],status=e['status'],choice=e['numeric']['choice'],
                        used_edges=e['numeric']['detail'].get('used_edges'),detail=e['numeric']['detail'],
                        first_public=next(x for x in audit['events'] if x['segment']==name and x['arm']==arm and x['q']==q)['first_public_mapping'],
                        reference=next(x for x in audit['events'] if x['segment']==name and x['arm']==arm and x['q']==q)['first_public_physical'])
            changes.append(dict(segment=name,original_q=start+q-1,branches=values))
    result=dict(status='POSTSEAL_FULL_EVIDENCE',source_objects=sum(coverage.values()),
        restored_cohort_counts=dict(coverage),actions=actions,choices=choices,events=changes,
        official_metrics=m['pooled_metrics'],deltas=m['pooled_delta'],strict_support=m['frozen_support_rule_met'],
        new_model_http=0,cost_usd=0,reference_scope='RGB polygon identity; not mm/surface physical GT')
    write_new(HERE/'DEPTH_EVIDENCE.json',result)
    # Fixed diagnostic frames predeclared in previous failure review, no cherry-pick.
    import numpy as np,cv2
    import matplotlib;matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from restored_source import RestoredDepth
    from depth_measurement import decode
    restored=RestoredDepth()
    private=HERE/'private/visualizations';private.mkdir(parents=True,exist_ok=True)
    figs=[]
    for f in (398,419,519,1821):
        name=next(n for n,(a,b) in SEGMENTS.items() if a<=f<=b)
        local=f-SEGMENTS[name][0]+1
        assignment=next(x for x in rows(input_dir(name)/'assignments.jsonl.gz') if x['frame']==local)
        with np.load(DATA/'depth_rgb_640x360'/f'{f:06d}.npz') as src:raw=src['depth_mm']
        dep,prov,meta=restored(f)
        fig,axes=plt.subplots(1,3,figsize=(14,4))
        for ax,values,title in zip(axes,(raw,dep,prov),('Raw camera-Z mm','Saved v2 reprojected camera-Z mm','Provenance: retained=1, hole=2, replaced=3')):
            im=ax.imshow(np.ma.masked_equal(values,0),vmin=500 if title.startswith(('Raw','Saved')) else 0,
                         vmax=1500 if title.startswith(('Raw','Saved')) else 3,cmap='viridis' if title.startswith(('Raw','Saved')) else 'tab10')
            for key,rle in assignment['masks'].items():
                region=decode(rle)
                ax.contour(region,levels=[.5],colors='white',linewidths=.35)
            ax.set_title(title,fontsize=9);ax.axis('off')
        fig.suptitle(f'F{f}: unchanged SAM3 masks; RGB/surface/mm ground truth not displayed')
        fig.tight_layout();p=private/f'F{f:06d}.png';fig.savefig(p,dpi=130);plt.close(fig);figs.append(artifact(p))
    restored.close()
    write_new(HERE/'VISUALIZATION_INVENTORY.json',dict(private_raw_depth_mask_figures=figs,private_pixels_not_for_git=True))
    # Public plot contains metrics only.
    arms=list(m['pooled_metrics'])
    fig,ax=plt.subplots(figsize=(9,4))
    x=np.arange(len(arms))
    for i,k in enumerate(('IDF1','HOTA','AssA')):
        ax.bar(x+(i-1)*.25,[m['pooled_metrics'][a][k] for a in arms],width=.25,label=k)
    ax.set_xticks(x,arms,rotation=12,fontsize=8);ax.set_ylim(60,100);ax.set_ylabel('Percent, all1471frames');ax.legend()
    fig.tight_layout();fig.savefig(HERE/'PERFORMANCE.svg');plt.close(fig)
    lines=['# DS7：全面复盘与一次针对性深度修复试验','',
        '## 判定','',
        ('**本轮预冻结性能门槛通过。**' if m['frozen_support_rule_met'] else '**本轮预冻结性能门槛未通过；不得把止损或工程通过称为深度超过原生。**'),
        'P2是真正v2原生修复深度重新投影的已曝光开发集离线诊断；其上游用了RGB与前后帧。它不使用v3标注补孔，运行时没有读取RGB/人工参考，但不能称过去帧独占、盲测或跨录像泛化。',
        '', '## 为什么此前失败','',
        '1. **身份发布基准错误。** 旧q先用临时数值H1/H2构造preview，stage的changes再与该preview比较。5个物理参考期望native的q（F419/F519/F1027/F1263/F1719）实际交换两个持续source，却记录RESOLVE_NO_ID_CHANGE。新增10次IDSW，另4次原生切换被重接消除，净+6；104条共有切换中另7条标签受持久alias影响。净多6不是只有6个新增错误。旧D2的F419/F519所谓COMMIT实为改正内部猜配，公开仍保持原生对应。',
        '2. **代理指标和跟踪目标脱节。** DS4筛选提高轮廓深度共识兼容数，却没有认证鱼体表面。DS5发现最大簇会丢正确片，F1821扩大采样后的中位数走向另一层且MAD变小；窄MAD/非零覆盖不证明物理准确。固定mask无法靠身份层补漏检或把共同mask拆成两个检测。',
        '3. **资格与缺测共同清空证据。** F419新F6 pre-B为空、一个post有多片，另一个post含糊；F519唯一关键pre-A在F508筛选失败，F510虽有值但接触风险不能补入历史。全四边joint又把所有剩余证据置零。DS6仅5q joint可用，真正多片post的2q均无joint；不能据零增量否定多片历史机制。',
        '4. **历史外推可辨识性不足。** 许多q只剩单点、短片或宽尺度预测；DS1两次有效选择的斜率仍UNKNOWN，DS2去均值漂移消融与D2完全一致，WLS速度独立收益未证实。丢失/接触后强凑速度会伪造连续身份，本轮仍禁止。',
        '5. **修复值存在来源冲突。** 归档F374的实测约1172mm、LingBot填补约833mm；合并中位数会受占比控制并出现单帧跳变。修复覆盖更多不代表身份线索更真实。v3 aligned p4置零还可能删除被遮住的v2赢家，故本轮直接读真正native v2重投影。',
        '6. **旧归因边界需纠正。** DS1曝光405帧曾比同源native略好；优势未在DS2的新1066帧及全1471保持。原生已正确的对应受到保护与真正原生碎片接回分列。L3/LW/旧8400+2888的来源、碎片模式与Z4Q长期重接条件不同，不能把那里的收益推到分批SOURCE_OLD feeding。评分回归和同源对照未发现足以解释退化的计分器错误。',
        '', '完整逐状态证据见POSTMORTEM_STATE；基线/评分/恢复可识别性见POSTMORTEM_EVALUATION；修复数据实际读取与泄漏边界见RESTORED_SOURCE_REVIEW。', '',
        '## 本轮最小改动','',
        '内部pre/group/post保护与原冻结扫描仍保留；公开与q preview采用本分支实际合法native/既有event alias。未通过深度证据时使用自己的因果当前步释放，不复制其他分支。选择成功才原子stage，并在第一次publish前完成。',
        '原生实测与模型估计core分层，不混合中位数；实测合格优先，否则推断单独入历史，单点推断误差假定60mm。WLS可能随样本数压低拟合均值误差，样本相关性未校准；不把60mm写成整个forecast下限。',
        '缺pre整行共同无信息；两个post都合格时才比较。depth与combined最优一致，两个候选的likelihood gap达到log9才允许恢复。9:1不是相对native/no-attachment的校准后验，也不是测得准确率；这是本轮预冻结改号成本假设，没有评分后调参。',
        '', '## 完整性能','',
        '|1471帧，同源SOURCE_OLD|IDF1|HOTA|AssA|IDSW|FP|FN|',
        '|---|---:|---:|---:|---:|---:|---:|']
    for a,v in m['pooled_metrics'].items():
        lines.append(f"|{a}|{v['IDF1']:.4f}|{v['HOTA']:.4f}|{v['AssA']:.4f}|{v['IDSW']}|{v['FP']}|{v['FN']}|")
    lines+=['','|逐段|分支|IDF1|HOTA|AssA|IDSW|FP|FN|','|---|---|---:|---:|---:|---:|---:|---:|']
    for n,values in m['segment_metrics'].items():
        for a,v in values.items():lines.append(f"|{n}|{a}|{v['IDF1']:.4f}|{v['HOTA']:.4f}|{v['AssA']:.4f}|{v['IDSW']}|{v['FP']}|{v['FN']}|")
    lines+=['','## 增量与未完成边界','']
    for label,v in m['pooled_delta'].items():
        lines.append(f"- {label}：IDF1 {v['IDF1']:+.4f}、HOTA {v['HOTA']:+.4f}、AssA {v['AssA']:+.4f} 点；IDSW {v['IDSW']:+d}。")
    lines+=['',f"修复测量cohort计数：{dict(coverage)}；总原生观测{sum(coverage.values())}。每个q的实际选择、深度可用边、预冻结门槛、首发布参考资格与正确/错误/不可评分均列DEPTH_EVIDENCE/EVENT_AUDIT。不得将fallback或未stage当安全通过。",
        'P0每帧等于同源native，旧D2逐帧复现DS6；P0的止损是共同底座修复，只有P1/P2相对它的差异才属于新深度选择。原mask未删，FP/FN相同；各段ID独立，负ID不忽略。',
        '全部五分支预测、state、事务、event和publisher先封存，后独立TrackEval及RGB参考核验。SWITCH_LEDGER逐条合计等于官方IDSW。旧456公开源码/结果字节锁复核，无新API/模型/补全/SAM3/训练，费用0。',
        '没有独立物理表面或mm真值，修复深度质量与预测误差仍UNKNOWN；不能宣称物理传感器准确或因果在线部署。未新增独立录像或盲测；曝光开发结果不是泛化证据。原生108次切换大多不在合法双鱼q，事件恢复范围不足以修复所有原生错误。',
        '', '## 可复现与交付','',
        'PLAN/CONFIG、生成脚本与生成后代码、实际输入/状态/评分检查、真实切片、全四段数值预测与事务、指标/事件/切换/耗时及可公开数值图均随main交付。private中深度mask图以及来源RLE/原始/修复深度和人工参考仅列真实路径/bytes/SHA；不公开RGB、像素、GT raster或凭据。受限依赖RESTRICTED_INVENTORY，逐公开文件清单ARTIFACT_MANIFEST，真实提交/远端核验另在REMOTE_VERIFICATION。',
        '', '## 一个下一步','',
        '固定本轮有效策略，构造只使用当前及过去帧的无标注修复深度，再在新的非重叠开发片段上与同源native完成一次独立对照；不以本轮曝光成绩替代因果验证。']
    (HERE/'RESULTS.md').write_text('\n'.join(lines)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(dict(cohorts=dict(coverage),actions=actions,strict_support=m['frozen_support_rule_met'])))
if __name__=='__main__':main()

