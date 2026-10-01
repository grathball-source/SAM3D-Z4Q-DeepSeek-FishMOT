"""Report actual sealed tracking results, never modify predictions."""
from common import *
from collections import Counter
import numpy as np

def main():
    import evaluate
    evaluate.verify_all_seals()
    m=read(RUN/'METRICS.json');audit=read(RUN/'EVENT_AUDIT.json');p=m['pooled_metrics']
    execute=[json.loads(x) for x in (HERE/'EXECUTION_LOG.jsonl').read_text().splitlines()]
    wall=next(x['elapsed_seconds'] for x in execute if x['command'][-2:]==[str(HERE/'launch.py'),'full'])
    lines=['# DS10 完整实验与失败复盘','',
        '## 主判定','',
        '**新深度系统超过同源原生基线。**' if m['frozen_support_rule_met'] else '**本轮新深度系统未达到超过同源原生的完整目标。**',
        '工程、输入和跟踪指标分列。主比较是SAM3_NATIVE；纯几何不是本轮晋级门槛。一个预测/null联合修复版本，四枝独立真实状态、完整同源1471帧/四段，全部封存后独立官方评分。','',
        '## 完整指标','',
        '|分支|IDF1|HOTA|AssA|IDSW|FP|FN|','|---|---:|---:|---:|---:|---:|---:|']
    for a in ARMS:
        v=p[a];lines.append(f"|{a}|{v['IDF1']:.6f}|{v['HOTA']:.6f}|{v['AssA']:.6f}|{v['IDSW']}|{v['FP']}|{v['FN']}|")
    lines+=['','|新枝−原生|ΔIDF1|ΔHOTA|ΔAssA|ΔIDSW|','|---|---:|---:|---:|---:|']
    for a in ('D10_RAW','D10_RESTORED'):
        d={k:p[a][k]-p['SAM3_NATIVE'][k] for k in ('IDF1','HOTA','AssA','IDSW')}
        lines.append(f"|{a}|{d['IDF1']:+.6f}|{d['HOTA']:+.6f}|{d['AssA']:+.6f}|{d['IDSW']:+d}|")
    lines+=['','指标为完整TrackEval pooled值，按segment命名空间直接合并全部帧，非分段率平均。所有mask、残片、负ID计分。分段指标、完整切换、GT来源/哈希与改动帧数见run/METRICS、SWITCH_LEDGER。','',
        '## 真实首发布和提交','',
        '|分支|q数|实际提交|fallback|首发布正确/错误/不可评分|','|---|---:|---:|---:|---|']
    review=[]
    for a in ARMS[1:]:
        es=[x for x in audit['events'] if x['arm']==a and x['q'] is not None]
        physical=Counter(x['first_public_physical'] for x in es)
        lines.append(f"|{a}|{len(es)}|{sum(x['status']=='COMMIT' for x in es)}|{sum(x['status'].startswith('LOCAL_FALLBACK') for x in es)}|{dict(physical)}|")
        for e in es:
            original=next(x for x in read(RUN/e['segment']/'public/EVENTS.json')[a] if x['id']==e['event'])
            review.append(dict(arm=a,segment=e['segment'],event=e['event'],original_q=e['original_q'],
                status=e['status'],choice=original['numeric']['choice'],
                actual_first_mapping=e['first_public_mapping'],expected=e['expected_mapping'],
                first_public_physical=e['first_public_physical'],physical_commit=e['physical'],
                pre_entry=e.get('pre_entry_reference'),restore=original['restore'],
                depth_forecasts=original['numeric']['detail']['depth_forecasts'],
                background=original['numeric']['detail']['background'],candidates=original['numeric']['detail']['candidates']))
    write_new(HERE/'NEW_CASE_REVIEW.json',dict(events=review,note='Actual bank physical reference and pre-entry status separate; no GT-derived actions or physical surface GT.'))
    lines+=['','提交、选择或首发布正确三者分别记录；不可评分不算成功。新源被接回与既有连续source交换分开，先前错号偶然换回不算物理恢复。所有无q事件、拒绝和fallback都保留。','',
        '## 实际失败原因与对应方案','',
        '诊断覆盖DS9全部19q：9次正确保持、2次正确接回、4次漏接回、4次post无法构成原bank两鱼的双射。108次native IDSW里100次不在首分离q。不能把所有切换归于事件关联，也不能把第三鱼残片guard拒绝当成模型排错。',
        '短窗WLS对较长遮挡缺口的均值/参数传播假定过强：F470预测1987mm而两post约1179/1159mm；F1027预测795mm而post约1172/1028mm。多数典型宽scale来自WLS参数传播，单改过程项不够。',
        'H0旧null是全图按像素面积统计，当前候选却是掩码对象；原背景高密度使一些理想预测仍不能到达log9。本轮改为当前所有合格对象的等权t4混合，保留query自身、共同null与15/60floor。',
        '新depth均值取同版本最后实测，移除长缺口WLS均值/参数传播，保留原缺口过程下限与过去增量扩散代理。无/1/2点历史保持旧predict。原ROI、质量、trigger/q、2D预测、H0合法map、9倍门槛和发布事务全部保留。',
        '这是一版联合修复；结果只检验整体系统相对native，不能拆成均值或null单项贡献。详见PLAN、三个diagnosis报告及逐列事实JSON。','',
        '## 可视化与数据边界','',
        '旧失败实际深度图覆盖4错例、4受限例、2错配控制，共10张；显示raw/v2、真实mask/core、匿名残片与邻鱼、ROI直方图、完整pre/current时间线和候选分数。图由真实数据重新读出，GT只标旧封存结果；没有GT raster/RGB纹理或假路径。',
        '所有19q列全图与对象深度分布统计；数值合格不能认证鱼体表面。near-tank深度不自动判背景，也不按GT筛某个像素。原始与v2 separately报告；v2含上游RGB/未来清理，只是曝光离线诊断。KDE含query，diffusion有噪声相关/截断偏差，后验与物理深度准确率均未校准。',
        '私有图与源RLE/GT像素不推送；PRIVATE_INVENTORY/RESTRICTED_INVENTORY列真实路径、字节、SHA与依赖。公开DECISION_SUMMARY/PERFORMANCE图仅数值。','',
        '## 工程验收与实际耗时','',
        f'四枝全段墙钟{wall:.3f}秒；复用保存预测，无新SAM3。F9逐帧复现DS9.J2，native同源，全部source/状态/首发布语义在GT评分前验收。',
        'dt_max_px仅允许预先冻结的float32 nextafter相邻且实际阈值不变；所有使用量、资格、cohort、来源和其余typed字段strict exact。接受记录在VERIFICATION，不是事后修改科学规则。',
        '首次controller测试出现系统DLL临时加载失败，原失败日志保留；单独验证同解释器导入成功后重跑通过，没有安装依赖或修改系统策略。其余必要测试与真实最早切片记录全部保留。模型HTTP/smoke、训练、SAM3、补全服务、费用均0。','',
        '## 交付与未完成边界','',
        '所有本轮公开代码/配置/测试/日志/预测/指标/逐事件与完整报告同步main，正常push并实际读取远端ref和关键字节。旧DS1–9字节锁保持。',
        '未完成：独立未曝光录像验证、v2因果在线等价、鱼体表面/mm真值，以及触发范围之外的通用重接。本轮不自动拓展其他模块或滚动调门槛。唯一下一步见NEXT_STEP_PLAN.md，未启动。','']
    (HERE/'RESULTS.md').write_text('\n'.join(lines),encoding='utf-8',newline='\n')
    import matplotlib;matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(9,4));x=np.arange(len(ARMS))
    for i,k in enumerate(('IDF1','HOTA','AssA')):ax.bar(x+(i-1)*.25,[p[a][k] for a in ARMS],.25,label=k)
    ax.set_xticks(x,['Native','Frozen DS9','New raw','New v2']);ax.set_ylabel('Percent; all 1471 frames');ax.set_ylim(50,100);ax.legend()
    fig.tight_layout();fig.savefig(HERE/'PERFORMANCE.svg');plt.close(fig)
    print('Actual DS10 sealed result report written')
if __name__=='__main__':main()
