"""Postscore report and inventory only; never changes a frozen experiment."""
import json
import subprocess
from pathlib import Path
from collections import Counter

from bootstrap import (HERE, ROOT, OLD, DATA, SEGMENTS, ARMS, artifact, verify,
    records, write_new, digest)


def pct(value): return 'UNKNOWN' if value is None else f'{100*value:.4f}%'


def finalize():
    for filename in ('MEASUREMENTS_SEALED.json','SCORING_SEALED.json'):
        for item in json.loads((HERE/filename).read_text())['artifacts']: verify(item)
    summary=json.loads((HERE/'SUMMARY.json').read_text()); timing=json.loads((HERE/'TIMING.json').read_text())
    pooled=summary['groups']['POOLED']; source=json.loads((HERE/'SOURCE_INVENTORY.json').read_text())
    rows=[r for name in SEGMENTS for r in records(HERE/f'{name}_occupancy.jsonl.gz')]
    changes={}; reasons={}
    for arm in ARMS:
        reasons[arm]=dict(Counter(r['methods'][arm]['reason'] for r in rows))
        changes[arm]=dict(status_changed=sum(r['methods'][arm]['status']!=r['methods']['F2_DS3']['status'] for r in rows),
            median_changed=sum(r['methods'][arm]['median_mm']!=r['methods']['F2_DS3']['median_mm'] for r in rows),
            selected_n_changed=sum(r['methods'][arm]['selected_n']!=r['methods']['F2_DS3']['selected_n'] for r in rows))
    pixel_changes=Counter(); background_changes=Counter(); suspects=0
    for name in SEGMENTS:
        for facts,private in zip(records(HERE/f'{name}_measurements.jsonl.gz'),
            records(HERE/'private'/f'{name}_pixels.jsonl.gz'),strict=True):
            suspects+=facts['quality']['native_suspect_n']
            for token,obj in private['objects'].items():
                base=obj['methods']['F2_DS3']
                for arm in ARMS:
                    pixel_changes[arm]+=obj['methods'][arm]['regions']['selected']!=base['regions']['selected']
                    background_changes[arm]+=facts['objects'][token]['methods'][arm]['selector']['plane']!=\
                        facts['objects'][token]['methods']['F2_DS3']['selector']['plane']
    for arm in ARMS:
        changes[arm].update(actual_selected_pixel_set_changed=pixel_changes[arm],
                            fitted_background_changed=background_changes[arm])
    transitions={}
    for arm in ARMS:
        transitions[arm]=dict(Counter(
            ('UNKNOWN' if r['methods']['F2_DS3']['reference_compatible'] is None else
             'COMPATIBLE' if r['methods']['F2_DS3']['reference_compatible'] else 'DISCORDANT')+'->'+
            ('UNKNOWN' if r['methods'][arm]['reference_compatible'] is None else
             'COMPATIBLE' if r['methods'][arm]['reference_compatible'] else 'DISCORDANT')
            for r in rows if r['reference_usable']))
    write_new(HERE/'POSTSCORE_DIAGNOSTICS.json',dict(method_changes=changes,reasons=reasons,
        fixed_R_transitions_from_DS3=transitions,native_suspect_aligned_pixel_occurrences=suspects,
        scope='POSTSCORE_DESCRIPTIVE_NO_RULE_CHANGE_NO_TRACKER_INTEGRATION'))
    restricted=[]
    for sources in source['original'].values():
        for row in sources:
            for kind in ('prediction','depth'):
                restricted.append(dict(category='ORIGINAL_'+kind.upper(),path=row[kind+'_path'],
                    bytes=row[kind+'_bytes'],sha256=row[kind+'_sha256']))
    restricted += [dict(category='ORIGINAL_NATIVE_DEPTH',**i) for i in source['native']]
    restricted += [dict(category='POSTSEAL_MANUAL_POLYGON',**i) for i in
                   json.loads((HERE/'REFERENCE_INVENTORY_POSTSEAL.json').read_text())]
    for name in SEGMENTS:
        for filename in ('assignments.jsonl.gz','profiles.jsonl.gz'):
            restricted.append(dict(category='READONLY_DS2_INPUT',**artifact(OLD/'private'/name/filename)))
        restricted.append(dict(category='READONLY_DS3_PIXEL_PROVENANCE',
            **artifact(ROOT/'experiments/ds3_depth_foreground_filter/private'/f'{name}_pixels.jsonl.gz')))
    for p in sorted((HERE/'private').rglob('*')):
        if p.is_file(): restricted.append(dict(category='NEW_PIXEL_PROVENANCE_OR_QA',**artifact(p)))
    source_audit=json.loads((HERE/'SOURCE_AUDIT.json').read_text())
    bag=Path(source_audit['lineage']['source_bag'])
    write_new(HERE/'RESTRICTED_INVENTORY.json',dict(files=len(restricted),bytes=sum(i['bytes'] for i in restricted),
        items=restricted,uploaded=False,RGB_read=False,instance_id_read=False,
        auxiliary_source_audit_bag=dict(path=str(bag),bytes=bag.stat().st_size,
            sha256_historical_record=source_audit['lineage']['recorded_bag_sha256'],
            current_whole_bag_hash_recomputed=False,
            target_current_raw_message_data_sha256=source_audit['raw_message']['data_sha256']),
        reproduction=dict(python='E:/researchsoftware/anaconda3/envs/D-MOT/python.exe',
            dependencies=['numpy','opencv','pycocotools','matplotlib','DS1/DS3/FEED frozen local helpers'],
            source='original aligned depth_mm/source_index, raw native depth, saved SOURCE_OLD polygons',
            raw_BAG_audit='SOURCE_AUDIT.json gives original BAG path/size/slice/record binding; audit does not hash entire BAG',
            outputs='fresh independent output directory; never overwrite this sealed run',
            order=['checks.py','score_checks.py','runner.py','score.py','report_artifacts.py','finalize.py'])))
    header=['|方法|可用 / UNKNOWN（S）|一致 / 冲突 / UNKNOWN（R）|一致率|冲突率|鱼体样本保留（Q）|非匹配样本率（Q）|可用时轮廓纯度|',
            '|---|---:|---:|---:|---:|---:|---:|---:|']
    for arm,m in pooled['arms'].items():
        r=m['fixed_R']; q=m['Q']
        header.append(f'|{arm}|{m["accepted"]} / {m["unknown"]}|{r["compatible"]} / {r["discordant"]} / {r["unknown"]}|'
            f'{pct(r["compatible_yield"])}|{pct(r["discordant_yield"])}|{pct(q["fish_yield"])}|{pct(q["nonfish_yield"])}|'
            f'{pct(m["conditional_available"]["micro_purity"])}|')
    bysegment=['|范围|方法|S / Q / R|可用|一致 / 冲突 / UNKNOWN|鱼体保留|',
               '|---|---|---:|---:|---:|---:|']
    for name,g in summary['groups'].items():
        if name=='POOLED': continue
        for arm,m in g['arms'].items():
            r=m['fixed_R']; bysegment.append(f'|{name}|{arm}|{m["source_objects"]}/{m["q_n"]}/{m["r_n"]}|'
                f'{m["accepted"]}|{r["compatible"]}/{r["discordant"]}/{r["unknown"]}|{pct(m["Q"]["fish_yield"])}|')
    cases=json.loads((HERE/'CASES_POSTSEAL.json').read_text())
    case_table=['|真实病例|参考|方法|结果 / n / median mm|一致性|匹配鱼体 / 其他鱼 / 背景|',
                '|---|---|---|---|---|---|']
    for row in cases['exposed_regressions']:
        ref=row['reference']; reftext=str(ref['median_mm']) if ref['usable'] else 'UNKNOWN'
        for arm,m in row['methods'].items():
            quality='UNKNOWN' if m['reference_compatible'] is None else '一致' if m['reference_compatible'] else '冲突'
            o=m['occupancy']; c=f'{o["fish"]}/{o["other_fish"]}/{o["background"]}' if o else '不可评分'
            case_table.append(f'|F{row["frame"]}/{row["token"]}|{reftext}|{arm}|{m["status"]} / {m["selected_n"]} / '
                f'{m["median_mm"]}|{quality}|{c}|')
    base=pooled['arms']['F2_DS3']; full=pooled['arms']['F6_BG_NOISE']; rangeonly=pooled['arms']['F3_RANGE']
    delta_c=full['fixed_R']['compatible']-base['fixed_R']['compatible']
    delta_d=full['fixed_R']['discordant']-base['fixed_R']['discordant']
    bg_c=full['fixed_R']['compatible']-rangeonly['fixed_R']['compatible']
    bg_d=full['fixed_R']['discordant']-rangeonly['fixed_R']['discordant']
    text=f'''# DS4 深度提取失败复盘与一次冻结修复实验

日期：2026-09-30。用户要求深度复盘、查看失败、提出计划并立即开始实验。
审查基点：ace9a37b1c6a2a59d3d5397f335d081f1a5a8ae8。

## 1. 主判定与边界

**{summary['decision']}**。工程与输入链通过；此判定只针对固定原始轮廓深度共识。
不等于物理深度正确、不等于身份恢复成功，也没有新的IDF1/HOTA/AssA。
1066帧、28382原轮廓全部完成。S=28382，Q={base['q_n']}，R={base['r_n']}；
{base['unscorable']}不可评分的匹配质量为null，参考不可用和弃权均保留。
同一录像、同一已经暴露的DS2/DS3片段，是测量开发诊断，不称新盲测。

主方案F6相对旧F2：一致对象{delta_c:+d}、冲突对象{delta_d:+d}；
相对仅准入F3：一致{bg_c:+d}、冲突{bg_d:+d}。
主门槛预先冻结：冲突率必须降低且一致率不得降低；降低冲突却损失一致为TRADEOFF。
无共同输出时纯度null；UNKNOWN不是正确，全部拒绝不能通过。
未根据结果挑选赢家、改阈值或写入DepthState。

## 2. 失败原因：具体证据与尚未知部分

### 2.1 正深度、低MAD、valid_fraction=1不代表真实鱼体距离

F766/o012原F2选57点，median12254.619mm，55点位于人工鱼轮廓内，纯度96.49%；
旧core为1141.787mm。这说明轮廓内占用率不能检查数值来自哪种物理表面。
SOURCE_AUDIT逐点追到57个不同原生点：BAG mono16本身已有12228–12288，
原native整帧与消息字节完全相等，完整对齐depth/source_index也逐元素一致。
没有证据把错误归给此次解码、字节序或重投影。设备有效量程、底层硬件原因UNKNOWN；
不能宣称多径或强光已经被确认，也不能擅自剪去高位。
已有数据README将>5m列异常候选，本轮据此定义SUSPECT准入，明确不是厂商量程。
F1319旧core自身也约11.86m；因此“core一致”本身也不能证明物理准确。

### 2.2 掩码内连通、对比显著不等于属于目标鱼

代码原本使用真实polygon掩码，不是只采bbox；但polygon内部仍有背景、孔洞和碎片。
F704的原mask有243/128px两片，F2选20点全部来自128px侧支；7点旧core全在主片。
组件74.07%占优、样本≥16、与平面有明显差异，仍会选错。
全28382轮廓组件重建精确通过。按旧选片不重新选择的主片排除审计会拒绝164旧可用例，捕捉7/17零匹配鱼体例，
其162可评分对象旧选点含7909匹配鱼体点、344其他鱼点、153背景点；另2例148点不可评分。
这是旧选点的条件拒绝成本，不能冒充新主片分支的真实运行损失。F4实际重新拟合/选片，
完整运行可用净+135、匹配鱼体选点净+9012；新结果与这个静态拒绝审计分列。
另外10例零鱼体误选位于主片，主片不是鱼体认证。只碰core也挡不住F766。
原mask中3例最大片并列（均旧UNKNOWN）；不任意挑一个。
因此主片约束只作对照，所有副片和原mask仍保留，不删除匿名证据。

### 2.3 外环拟合好，不证明向掩码内部延伸的背景面正确

20例远侧里只有3例约11.9–12.3m，其余17例为1.11–1.16m。
F930选点处平面预测约1103.94mm，外环median1150.22；F1788预测1013.46、外环1154.83。
纵向斜率可约−3至−4.75mm/px。FARTHER只是相对拟合面远，不等于鱼在背景后面。
本轮不统一禁止FARTHER，也不按这些已曝光斜率设置新成功阈值。
局部背景外推归属/水下标定不确定性仍待验证。
实际打开F704和F701对照图时，显著低深度条带与原SAM3轮廓还有空间未覆盖现象。
不能据图直接认证它是哪条鱼或断言配准损坏；可能涉及mask误差、RGB-D空间配准或水下外参。
源重投影逐元素一致只证明现有投影代码复现，不能验证真实表面配准精度。
mask内筛选本身无法追回mask之外的深度表面；RGB人工轮廓内原始共识也可能包含背景。
因此本轮proxy通过仍不足以把新median送入身份关联。

### 2.4 关联尺度被用于背景噪声尺度，排除了弱对比信号

旧背景scale≥15mm，3倍门槛使对比至少45mm。4442个无显著对比对象中2258例
未floor残差尺度<15mm（中位4.014）。固定旧平面下30mm描述性shadow有679个合格占优组件
被45mm门槛挡住；这仅是机制证据，不是新实验成绩。
DS4将背景floor单独设1mm（SDK量化依据的新假设），保留30mm对比下限、
前景15mm尺度下限和原60mm拒绝条件。IRLS权重及拟合面也受此变化影响，
不是只把最后一道阈值改小。1mm不能称为物理噪声标定。
旧3596例无合格组件中3529例全部不足16点；没有偷偷降低样本门槛或填洞。

## 3. 冻结方案与实际流程

见PLAN/CONFIG/FREEZE。F2复现原DS3；F3仅native准入；F4仅唯一最大主片；
F5二者结合；F6为native准入+独立背景floor，原geometry不变。
F6对F3隔离背景floor增量；F2/F3/F4/F5为2×2诊断。
原depth、whole/core、mask保持不变，准入只修改工作副本。仅采实际原始有效像素；
闭运算仅连接support，不填出新深度。不使用RGB、GT、未来帧、v3、instance_id或模型回答。
新源表仅depth_mm/source_index/raw native，公开不含像素、原始RLE或GT raster。

11项真实/合成测量测试+7项评分测试通过。独立68组341对象coco匹配与旧整数IoU严格等价，
15组原始统计绑定通过；原DS3每个对象的事实和选点逐值/逐像素精确复现。
启动前修复两处评分空值；另一次启动读取验收字段错误在FREEZE之前退出，
PRE_FREEZE_ATTEMPT_LOG/PREFREEZE_REPAIR保留，修复只读状态字段后正式运行一次。
全部代码/请求数0/有效参数/来源先冻结，全部测量先封存，然后才读取人工polygon统一评分。

R来自当前帧人工鱼轮廓排除重叠后的7×7原始深度core，n≥16、fraction≥.2、
max(15,1.4826MAD)≤60；与所有算法选点独立。容差max(30,3scale)。
这是原始轮廓共识，稳定原始深度误差可以同时污染参考；人工polygon本身未独立认证。
Q固定原unique IoU≥.5、margin≥.1；完全复现旧28088/294，未只给幸存对象重匹配。

## 4. 完整实测

{chr(10).join(header)}

Q鱼体分母={base['Q']['fish_denominator']}原始有效匹配鱼体样本；非匹配包括其他鱼和背景。
R一致/冲突/UNKNOWN的分母均为固定{base['r_n']}，不是各方法幸存者。
“可用时纯度”有条件且有天花板，只作描述，不能称距离准确率。
F6采样扩大时，匹配鱼体点净+{full['Q']['selected_counts']['fish']-base['Q']['selected_counts']['fish']}，
其他鱼点净+{full['Q']['selected_counts']['other_fish']-base['Q']['selected_counts']['other_fish']}、
背景点净+{full['Q']['selected_counts']['background']-base['Q']['selected_counts']['background']}；
合计非匹配点净+16620。条件纯度从98.9106%降至98.6966%，不能隐去这个代价。
固定R仍有44新增冲突：39由旧一致转冲突、5由旧UNKNOWN转冲突。
旧冲突67转一致、36转UNKNOWN；合起来是冲突净−59，并非每个对象都改善。
F747/o010是最早新增冲突：原290点median1056.193，参考1017.662，误差38.531；
新选择扩大后跨过预定45mm容差。原/新选点均在匹配鱼轮廓内，说明对象内位置/深度分布
变化也会改变代表性median，不能把它直接判为新背景混入或物理深度错误。
新320点median1064.386、误差46.723mm，完整保留在CASES_POSTSEAL。
原whole/core控制逐值复现；见SUMMARY.raw_controls和POSTSCORE_DIAGNOSTICS的逐臂实际选点变化与转移。
完整选点fish/other/background计数、误差分布、不可评分交叉表和每个对象都可回查。

{chr(10).join(bysegment)}

## 5. 真实失败病例的修复与代价

{chr(10).join(case_table)}

CASES_POSTSEAL还保留最早新增可用和最早新增冲突，展示失败而非只展示修好的病例。
独立复盘又查出以下重要反例，已实际打开ADDITIONAL_FAILURE_FIGURES三张图：

- F1821/o008：原34点全被保留，又加52点；闭运算support把两段深度连成同一个86点组件。
  median838.139→1136.486，参考840.761、容差88.669，误差2.622→295.725mm；
  MAD17.673→10.727却更小，q10仍822.411、q90=1147.475。小MAD可掩盖少数另一深度mode，
  图像连通也不认证深度分布单一。规则资格通过不等于正确表面。
- F1044/o016：旧UNKNOWN，新19个选点按人工轮廓占用全落在另一条鱼上。
  原预测其他鱼排除并不等于真实其他鱼排除；不能靠GT掩码补救本轮输入。
- F1385/o015：新59点按轮廓占用全为other_fish，参考共识却判一致。
  接近的深度值无法认证属于哪条鱼，也直接展示本轮代理分数的盲点。
- F1319/o007：参考自身19点全被native SUSPECT政策标记，median11855.604；
  旧67点11863.940会被参考判一致，新准入拒绝变UNKNOWN。
  参考与测量共享原始异常时，一致不代表准确；本轮未为了提分删掉这个参考。

POSTSCORE_REVIEW为独立全量计数和失败机制复核；没有修改任何输出或评分。
VISUALIZATION_FILES列实际私有图；数值量程完整且>5m显式红色，不把12m藏进正常背景色。
初版长图例裁切已保留原图，并用独立报告脚本仅换行/紧布局重绘；
VISUALIZATION_CAPTION_REPAIR列新图及SHA，VISUALIZATION_INSPECTION记录实际打开核查。
公开MEASUREMENT_SUMMARY.svg仅含封存数字。人工距离真值仍UNKNOWN。

## 6. 耗时、限制与交付

本地CPU单原生线程，测量{timing['total_seconds']:.3f}s，中位{timing['median_frame_ms']:.3f}ms/帧，
后封存评分{summary['scoring_seconds']:.3f}s；不是实时部署性能。无新增API、smoke、训练、
SAM3推理或深度补全服务，新增HTTP=0、费用USD0。
DS1/DS2/DS3公共文件由OLD_READONLY_LOCK逐文件核验不变；没有旧分数回写。
受限{len(restricted)}文件、{sum(i['bytes'] for i in restricted)}字节，仅列真实路径/大小/SHA与复现依赖，未上传像素。
全部公开代码、配置、检查、日志、测量、逐对象评分、完整复盘和数值图同步main；
实际commit/远端ref/关键文件读取证据见REMOTE_VERIFICATION，不在正文猜最终SHA。

未完成：物理距离标定/独立像素表面真值、盲测泛化、与DepthState关联的真实跟踪增量；
均未启动，也未用旧IDF1/HOTA补写。

**一个下一步：对封存的新增冲突与低保留病例进行独立鱼体/背景/异常深度逐像素核验，
再决定背景外推是否需要约束；本轮冻结版本结束，不继续调到通过或自动接入跟踪。**
'''
    with (HERE/'RESULTS.md').open('x',encoding='utf-8') as out: out.write(text)
    write_new(HERE/'EXECUTION_LOG.json',dict(base=summary.get('base','ace9a37b1c6a2a59d3d5397f335d081f1a5a8ae8'),
        inference_http=0,smoke=0,training=0,sam3_inference=0,completion_service=0,cost_usd=0,
        frozen_trial_runs=1,prefreeze_failed_launches=1,measurement_seconds=timing['total_seconds'],
        scoring_seconds=summary['scoring_seconds'],decision=summary['decision'],
        prediction_or_tracking_changed=False,all_original_objects_retained=True,
        private_pixels_uploaded=False,old_experiments_modified=False))


if __name__=='__main__': finalize()
