"""Postscore reporting/inventory only; never alters the frozen measurement rule."""
import json
import subprocess
from collections import Counter
from pathlib import Path

from common import HERE, ROOT, OLD, SEGMENTS, records, artifact, write_new, verify, digest, np


def percent(value):
    return 'UNKNOWN' if value is None else f'{100*value:.2f}%'


def report():
    seal=json.loads((HERE/'SCORING_SEALED.json').read_text())
    for item in seal['artifacts']: verify(item)
    summary=json.loads((HERE/'SUMMARY.json').read_text()); timing=json.loads((HERE/'TIMING.json').read_text())
    p=summary['groups']['POOLED']; rows=list(records(HERE/'OCCUPANCY_AUDIT.jsonl.gz'))
    measured={(r['segment'],r['frame'],token):obj for name in SEGMENTS
              for r in records(HERE/f'{name}_measurements.jsonl.gz') for token,obj in r['objects'].items()}
    usable=[r for r in rows if r['reference_status']=='SCORABLE' and r['core_usable']]
    dominated=[r for r in usable if r['core']['background']>r['core']['n']/2]
    stable_dominated=[r for r in dominated if measured[(r['segment'],r['frame'],r['token'])]['core']['mad']<=10]
    available=[r for r in rows if r['filter_status']=='AVAILABLE']
    deltas=[r['median_delta_core_mm'] for r in available if r['median_delta_core_mm'] is not None]
    signs=Counter(measured[(r['segment'],r['frame'],r['token'])]['foreground']['selected_sign'] for r in available)
    diagnostics=dict(postscore_descriptive_only=True,scorable_core_usable=len(usable),
        core_majority_outside_all_manual_fish=len(dominated),core_majority_background_and_mad_le10mm=len(stable_dominated),
        dominated_filter_available=sum(r['filter_status']=='AVAILABLE' for r in dominated),
        selected_signs=dict(signs),core_to_filter_median_delta_mm_quantiles=(np.quantile(deltas,[0,.1,.5,.9,1]).tolist() if deltas else []),
        caution='Manual silhouette occupancy is not physical raw-depth foreground truth; no new thresholds or tracking effect.')
    write_new(HERE/'POSTSCORE_DIAGNOSTICS.json',diagnostics)
    inventory=json.loads((HERE/'SOURCE_INVENTORY.json').read_text())
    restricted=[]
    for sources in inventory.values():
        for source in sources:
            for kind in ('prediction','depth'):
                restricted.append(dict(category='ORIGINAL_'+kind.upper(),path=source[kind+'_path'],
                    bytes=source[kind+'_bytes'],sha256=source[kind+'_sha256']))
    for item in json.loads((HERE/'REFERENCE_INVENTORY_POSTSEAL.json').read_text()):
        verify(item); restricted.append(dict(category='POSTSEAL_MANUAL_REFERENCE_POLYGON',**item))
    for name in SEGMENTS:
        for filename in ('assignments.jsonl.gz','profiles.jsonl.gz'):
            restricted.append(dict(category='READONLY_DS2_DERIVED_INPUT',**artifact(OLD/'private'/name/filename)))
    for path in sorted((HERE/'private').rglob('*')):
        if path.is_file(): restricted.append(dict(category='NEW_PRIVATE_PIXEL_PROVENANCE_OR_VISUALIZATION',**artifact(path)))
    write_new(HERE/'RESTRICTED_INVENTORY.json',dict(files=len(restricted),bytes=sum(i['bytes'] for i in restricted),
        items=restricted,reproduction=dict(interpreter='E:/researchsoftware/anaconda3/envs/D-MOT/python.exe',
            dependencies=['numpy','opencv','pycocotools','matplotlib','frozen DS1 measurement and FEED prepare/features'],
            dataset='SOURCE_OLD original SAM3 polygons plus original aligned depth_mm, authorized manual polygons after sealing',
            private_new='runner.py regenerates crop RLE; evaluate.py regenerates raw depth figures, only in fresh directory'),
        uploaded=False,raw_rgb_read=False,instance_id_plane_read=False))
    plots=[]
    methods=[('whole','Whole','#9b9b9b'),('core','Legacy core','#3f77bd'),('foreground','Filtered','#30885e')]
    svg=['<svg xmlns="http://www.w3.org/2000/svg" width="900" height="430" viewBox="0 0 900 430">',
         '<rect width="900" height="430" fill="white"/>',
         '<g font-family="sans-serif" fill="#222"><text x="35" y="35" font-size="22">DS3: paired accepted silhouette occupancy</text>']
    for i,(key,label,color) in enumerate(methods):
        value=p['paired_accepted_metrics'][key]['purity']; y=80+i*65
        svg += [f'<text x="35" y="{y+22}" font-size="16">{label}</text>',
                f'<rect x="170" y="{y}" width="{550*value:.2f}" height="32" fill="{color}"/>',
                f'<text x="{180+550*value:.2f}" y="{y+23}" font-size="16">{percent(value)}</text>']
    svg += [f'<text x="35" y="300" font-size="18">Retained matched fish pixels: {percent(p["matched_foreground_retention"])}</text>',
            f'<text x="35" y="335" font-size="18">Acceptance among legacy core usable: {percent(p["core_usable_acceptance"])}</text>',
            '<text x="35" y="375" font-size="15">Exposed same-recording measurement diagnosis; not depth accuracy or tracking gain.</text>',
            f'<text x="35" y="408" font-size="15">{p["paired_accepted"]} paired objects; UNKNOWN and unscorable kept in full audit.</text></g></svg>']
    (HERE/'MEASUREMENT_SUMMARY.svg').write_text('\n'.join(svg)+'\n',encoding='utf-8')
    table=['|范围|原轮廓|可评分|F2可用 / UNKNOWN|配对对象|core→F2纯度|鱼体保留|原core可用对象的F2覆盖|',
           '|---|---:|---:|---:|---:|---:|---:|---:|']
    for name,g in summary['groups'].items():
        pair=g['paired_accepted_metrics']
        table.append(f'|{name}|{g["objects"]}|{g["scorable"]}|{g["accepted"]} / {g["unknown"]}|{g["paired_accepted"]}|'
            f'{percent(pair["core"]["purity"])}→{percent(pair["foreground"]["purity"])}|'
            f'{percent(g["matched_foreground_retention"])}|{percent(g["core_usable_acceptance"])}|')
    baseline=['|测量|全部可评分对象的像素纯度|同一配对对象像素纯度|同一配对对象平均纯度|配对真实有效样本数|',
              '|---|---:|---:|---:|---:|']
    for key,label,_ in methods:
        pair=p['paired_accepted_metrics'][key]
        baseline.append(f'|{label}|{percent(p["all_scorable"][key]["purity"])}|{percent(pair["purity"])}|'
                        f'{percent(pair["mean_object_purity"])}|{pair["n"]}|')
    text=f'''# DS3：轮廓内深度前景筛选的完整测量验证

## 主判定

**{p['decision']}**。工程、真实输入、全量测量和封存后评分完成；本轮固定测量假设按冻结门槛判定。
使用已曝光 DS2 的1066帧、全部{p['objects']}个原SAM3轮廓，绝非新盲测。
F2相对同一批配对对象的旧core像素纯度变化 **{p['purity_gain_pp']:+.4f}个百分点**；
保留原轮廓内有效、匹配人工鱼体像素 **{percent(p['matched_foreground_retention'])}**；
在原core可用对象上可用率 **{percent(p['core_usable_acceptance'])}**。
冻结通过门槛分别为≥10个百分点、≥50%、≥50%，必须全部满足。
没有改变任何跟踪状态、trigger、q、候选、二维运动、发布或数值关联权重，因此本轮**没有新的IDF1/HOTA成绩**。
新模型HTTP、smoke、训练、SAM3推理、深度补全和费用全部为0。

## 实际改了什么

原逻辑是SAM3多边形whole，以及去重叠后的7×7腐蚀core，不是矩形框。
新增 `foreground.measure(depth, region, other)` 只接收当前原始depth_mm、当前轮廓及其他预测轮廓的占用。
先排除邻鱼，用轮廓外5–20像素环带拟合Huber局部深度平面；再分别检查近侧、远侧显著深度差，
要求空间连通、真实样本量、残差尺度与70%主导性。没有用身份候选的预测深度来挑像素。
3×3闭运算只帮助定义连通支持，绝不为孔洞赋值；测量只含原始有限正深度。
背景不足、不可分或多区域歧义输出UNKNOWN，同时保留原whole/core及所有匿名证据。
具体生效常数在CONFIG；来源和实际函数在FREEZE；逐轮廓fact_id绑定私有crop/RLE、
全局像素坐标、source mask、原NPZ及原预测SHA，可逐像素复现。

## 同源完整结果

{chr(10).join(table)}

{chr(10).join(baseline)}

主比较只包含同一批F2可用、唯一匹配且core有样本的{p['paired_accepted']}个对象；
全部可评分对象表包含F2拒绝对象的零采样，但该微平均**不会把UNKNOWN算成正确**。
原{p['objects']}个轮廓中F2可用{p['accepted']}、UNKNOWN{p['unknown']}；
人工轮廓可评分{p['scorable']}、不可评分{p['unscorable']}，原因{json.dumps(p['reference_reasons'],ensure_ascii=False)}。
配对逐对象纯度提高{p['paired_objects_improved']}、下降{p['paired_objects_worsened']}、相等{p['paired_objects_equal']}；
对象平均变化{p['mean_paired_purity_delta_pp']:+.4f}个百分点，中位鱼体保留{percent(p['median_paired_retention'])}。
多取样大对象不会被误称为更多独立事件。本轮无显著性或跨录像泛化声明。

拒绝原因：{json.dumps(p['filter_reasons'],ensure_ascii=False)}。
有效样本构造性valid_fraction=1不等于可靠：日志另有原区域有效率、连通支持有效率、
样本量、主导率、背景拟合尺度、组件竞争和实际深度差。

## 为什么不能仅凭这次叫作“鱼体深度修好了”

评分真值是事后人工鱼体轮廓，占用位置有意义，但不是每个对齐深度像素的物理表面标签。
轮廓内仍可能有对齐误差、鳍/尾穿透、孔洞及背景混值，人工轮廓本身也未经独立认证。
因此“纯度”严格是有效采样落在匹配人工轮廓内的比例；不能把它写成毫米深度准确率。
局部像素坐标平面也不是经水体折射标定的真实三维平面。
保留率的分母只取原SAM3轮廓内已有的有效匹配鱼体像素；未预测到的鱼体和缺测不能因此被恢复。
多区域拒绝和弱深度差拒绝具有真实可用性代价；也未证明所选组件一定属于该鱼。

事后描述性审计：可评分且旧core可用{len(usable)}个对象，
其中{len(dominated)}个core超过一半采样位于**所有**人工鱼体轮廓之外，
其中{len(stable_dominated)}个MAD≤10mm。这支持“很稳定仍可能采到背景”的几何诊断，
但数量依赖人工轮廓/对齐，不能代替物理深度真值。
所选近/远侧分别{dict(signs)}；core→筛选median变化的0/10/50/90/100分位为
{diagnostics['core_to_filter_median_delta_mm_quantiles']}mm。变化不是自动更准确。
该描述性审计在评分后生成，未用于更改规则、过滤样本或冻结判定。

## 工程与封存证据

10项直接检查通过：缺失/稀疏背景、无深度差、两个相当组件及相反符号、孤立极端值、
邻鱼排除、真实F701及对象顺序、当前帧只读无修改、坐标平移、倾斜背景与孔洞、单样本不足。
真实切片和全量测量期间禁止socket连接、人工/测试参考访问及NPZ中非depth_mm键。
全部1066帧原polygon重新栅格化与旧cached masks一致；每个whole/core统计与旧DS2精确一致。
全部测量和像素输出封存后才打开人工标签；评分验证实际代码、CONFIG、源文件、
旧输入、测量流、像素流和完整seal绑定。所有旧公共DS1/DS2及使用过的私有输入保持原SHA。
未读sealed test、RGB、v3、instance_id平面或旧模型回答。
新 `report.py` 只在评分后汇总和登记产物，不属于测量/评分执行链，不更改冻结源码和结论。

测量全程{timing['total_seconds']:.3f}秒；每帧baseline/来源复核中位{timing['baseline_source_median_ms']:.3f}ms，
新filter/像素编码中位{timing['filter_median_ms']:.3f}ms；独立占用评分{summary['scoring_seconds']:.3f}秒。
这是本地离线CPU耗时，不能称实时部署或滤波核心的单独净耗时。

## 产物、公开边界与交付

完整代码、固定配置、测试、公开数值measurements、逐对象OCCUPANCY_AUDIT、
SUMMARY、POSTSCORE_DIAGNOSTICS、真实运行日志、seals及数字SVG均同步main。
原始像素/RLE/人工轮廓和三张实际深度对照保留本地private与原数据目录。
RESTRICTED_INVENTORY记录{len(restricted)}个实际受限文件、{sum(i['bytes'] for i in restricted)}字节、路径及SHA与复现依赖，未公开上传。
三张图按预先规则选择：最早可用、最早有显著像素但UNKNOWN、配对纯度最大下降；
实际查看记录另列，不能用挑图替代完整结果。图中首次出现人工轮廓均在封存之后。
交付commit和实际origin/main ref/blob/关键文件核验见REMOTE_VERIFICATION.json；
此正文不伪造自引用的最终commit。

## 一个下一步

在这批已冻结像素结果上，做一份小规模鱼体/背景**深度像素**独立人工审计，
明确轮廓误差、RGB-D对齐和真实背景混入的区别，再决定是否接入深度状态。
不修改本轮阈值、不自动启动跟踪对照或加入大模型。
'''
    (HERE/'RESULTS.md').write_text(text,encoding='utf-8')
    print(json.dumps(diagnostics,indent=2))


if __name__=='__main__': report()
