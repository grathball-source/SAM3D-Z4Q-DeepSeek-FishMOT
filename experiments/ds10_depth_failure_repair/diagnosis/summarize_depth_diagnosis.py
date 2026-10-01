"""Summarize already bound DS9 diagnostics; numeric plots only, no pixel reads."""
from pathlib import Path
import sys, json, hashlib, math
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams['svg.fonttype'] = 'none'


def artifact(path):
    data = path.read_bytes()
    return dict(path=str(path), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def t4(grid, mean, scale):
    return np.exp(math.lgamma(2.5)-math.lgamma(2.)-.5*math.log(4*math.pi)
                  -math.log(scale)-2.5*np.log1p(((grid-mean)/scale)**2/4))


def table(header, rows):
    return '\n'.join(['| '+' | '.join(header)+' |', '| '+' | '.join(['---']*len(header))+' |']
                     + ['| '+' | '.join(map(str, row))+' |' for row in rows])


def main():
    source = HERE/'CASE_STATS.json'
    data = json.loads(source.read_text(encoding='utf-8'))
    cases = data['cases']
    assert len(cases) == 19 and data['private_figures'] == 10
    outputs = ['BACKGROUND_DENSITY.svg', 'BACKGROUND_DENSITY.png', 'BACKGROUND_DENSITY_META.json', 'FAILURE_ANALYSIS.md']
    assert all(not (HERE/name).exists() for name in outputs), 'Append-only outputs already exist'
    fig, axes = plt.subplots(5, 4, figsize=(19, 18), constrained_layout=True)
    summary = []
    for case, ax in zip(cases, axes.flat):
        for field, color in [('raw', '#2476b5'), ('v2', '#c34437')]:
            full = case['full_'+field]
            pop = case['object_population_'+field]
            kernels = pop['kernels']
            # Numeric component diagnostic only: deliberately no query convolution.
            base = [math.hypot(k['scale_mm'], 15.) for k in kernels]
            oldscale = max(60., 1.4826*full['mad'])
            lo = max(1., min([full['median']-4*oldscale] + [k['median_mm']-4*s for k,s in zip(kernels, base)]))
            hi = max([full['median']+4*oldscale] + [k['median_mm']+4*s for k,s in zip(kernels, base)])
            grid = np.linspace(lo, hi, 600)
            assert len(kernels) >= 3
            density = np.mean([t4(grid, k['median_mm'], s) for k,s in zip(kernels, base)], axis=0)
            ax.plot(grid, t4(grid, full['median'], oldscale), '--', color=color, alpha=.8,
                    label=field.upper()+' old pixel null')
            ax.plot(grid, density, '-', color=color, label=field.upper()+' object BASE KDE')
            summary.append(dict(global_q=case['global_q'], modality=field, full_frame=full,
                current_objects=pop['total_current_objects'], nonmissing=pop['all_nonmissing_core_medians'],
                usable=pop['all_usable_core_medians'], usable_cohorts=pop['usable_cohorts'],
                component_sigma_floor_mm=15., component_additional_floor_mm=15.,
                query_convolution=False, kernel_count=len(kernels)))
        ax.set_title('F'+str(case['global_q'])+' / '+case['event'], fontsize=10)
        ax.set_xlabel('recorded camera Z, mm', fontsize=8)
        ax.set_ylabel('normalized density, 1/mm', fontsize=8)
        ax.tick_params(labelsize=7)
        ax.grid(alpha=.18)
    axes.flat[-1].axis('off')
    handles, labels = axes.flat[0].get_legend_handles_labels()
    axes.flat[-1].legend(handles, labels, loc='upper left', fontsize=10)
    axes.flat[-1].text(0, .50, 'Numbers only; no depth/RGB/GT pixels.\nEqual current qualified objects; query included.\nSolid: component/base diagnostic KDE.\nNo query-specific convolution here.\nNot a calibrated posterior.\nGraph limits describe t4 densities, not sensor range.', fontsize=10, va='top')
    fig.suptitle('All 19 sealed DS9 queries: whole-frame pixel null vs object-equal COMPONENT/BASE diagnostic KDE\n'
                 'Solid curves have base hypot(component sigma, 15 mm); no query convolution; not new-selector scores', fontsize=14)
    fig.savefig(HERE/'BACKGROUND_DENSITY.svg')
    fig.savefig(HERE/'BACKGROUND_DENSITY.png', dpi=125)
    plt.close(fig)
    meta = dict(status='PASS', input=artifact(source), code=artifact(Path(__file__)), queries=19,
        old_private_purple_semantics='UNCONVOLVED_STATISTICAL_KDE_WITH_MAX_15_1.4826_CORE_MAD; NOT_ACTUAL_DS10_SELECTOR_DENSITY',
        public_solid_semantics='COMPONENT_BASE_DIAGNOSTIC_KDE_HYPOT_COMPONENT_SIGMA_15; NO_QUERY_CONVOLUTION',
        actual_planned_selector_semantics='base=hypot(component_sigma,15); query_scale=hypot(base,query_sigma); all candidates share query-specific background density',
        component_selection='ALL_CURRENT_CORE_USABLE_OBJECTS_ONCE_EQUAL_WEIGHT_INCLUDES_QUERY_NO_GT_OR_IDENTITY_FILTER',
        interpretation='NORMALIZED_CURRENT_OBSERVATION_PLUGIN_CONTRAST_NOT_CALIBRATED_POSTERIOR',
        plots=[artifact(HERE/name) for name in outputs[:2]], rows=summary,
        RGB_reads=0, GT_raster_reads=0, depth_pixel_reads=0, new_replays=0, new_model_calls=0)
    (HERE/'BACKGROUND_DENSITY_META.json').write_text(json.dumps(meta, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    wrong = [c for c in cases if c['branches']['J2_RESTORED_DEPTH']['first_public_reference']=='WRONG']
    assert {c['global_q'] for c in wrong} == {470,764,1390,1805}
    wrong_rows = []
    for c in wrong:
        for native,p in c['posts'].items():
            a = p['v2']; core = a['core']
            assert a['core_usable'] and a['cohort']=='retained'
            wrong_rows.append([c['global_q'], 'n'+native, core['area'], core['n'], f"{core['valid_fraction']:.3f}",
                f"{core['median']:.3f}", f"{a['actual_selected_mad_mm']:.3f}", 'retained / PASS'])
    pre_rows = []
    for c in wrong:
        b=c['branches']['J2_RESTORED_DEPTH']; pre=b['depth_forecasts']
        pre_rows.append([c['global_q'], '/'.join(str(pre[r]['samples']) for r in ['A','B']),
            '/'.join('NA' if pre[r]['scale_mm'] is None else f"{pre[r]['scale_mm']:.3f}" for r in ['A','B']),
            '/'.join('NA' if pre[r].get('time_scale_seconds') is None else f"{pre[r]['time_scale_seconds']:.3f}" for r in ['A','B']),
            '/'.join('NA' if pre[r].get('delta_seconds') is None else f"{pre[r]['delta_seconds']:.3f}" for r in ['A','B'])])
    bg_rows=[]
    event_rows=[]
    for c in cases:
        cells=[c['global_q']]
        for field in ['raw','v2']:
            f=c['full_'+field]; p=c['object_population_'+field]; z=p['all_usable_core_medians']
            cells += [f"{f['median']:.2f}/{f['mad']:.2f}", f"{z['count']}/{p['total_current_objects']}",
                f"{z['minimum']:.2f}–{z['maximum']:.2f}",f"{z['IQR']:.2f}"]
        bg_rows.append(cells)
        b=c['branches']['J2_RESTORED_DEPTH']
        event_rows.append([c['global_q'],c['event'],b['first_public_reference'],b['best'],b['choice'],
            f"{b['margin']:.6f}", 'PASS' if b['post_pair_usable'] else 'FAIL',
            ','.join('n'+str(n) for n in b['visible_member_residual']) or '无'])
    text = f'''# DS10：旧失败数据与实际深度 ROI 诊断

## 范围与结论

只读复查 DS9 全部 19 个 q。实际当前帧深度、同一预测掩码和既有测量重算逐项核验；10 张真实受限图覆盖全部四个首发布 WRONG（F470/F764/F1390/F1805）、全部四个可见成员残片限制（F398/F434/F1280/F1504）及两处真实置乱损害（F519/F1027）。没有选择容易成功案例替代失败集合。没有读取 RGB 或 GT 栅格，没有运行模型或新的跟踪回放。

**当前点数不足不是四个 WRONG 的共同解释：八个 post 核均为 retained 且数值合格。更直接的已记录问题是历史缺失、短历史远距离外推与深度评分方向；整幅像素背景分布也不等同于当前对象深度统计量的分布。** 这些证据支持只修改历史预测模型与零假设背景统计单位。它们不能预报新模型效果，也没有证明预测掩码内深度像素属于目标鱼体。

DS9 的 raw/v2/ZERO 与纯几何实际出版输出相同；原深度没有已证实的输出增量。下表 CORRECT/WRONG 来自旧封存的 RGB 身份对应参考，仅用于展示选择与候选映射说明，不参与 ROI、像素所有权或参数选择。

## 四个首发布错误：post 已数值合格

规则保持 n≥16、有效比例≥0.2、max(15,1.4826×实际 MAD)≤60 mm。MAD 表示样本中位绝对偏差；合格只说明数值稳定和覆盖满足规则。

{table(['全局 q','post','ROI 面积','有效 n','有效比例','median mm','实际 MAD mm','来源/资格'], wrong_rows)}

八个核都没有 >5000 mm 的诊断可疑值。全 38 个 post 核的 raw/v2 可疑计数也均为零；这不证明全场采集无异常，不把 5000 mm 冒充传感器量程。

{table(['q','pre 样本 A/B','预测 scale A/B mm','历史 span A/B s','距末样本 A/B s'], pre_rows)}

- F470：A 无历史。H0 与正确 H1 的 depth log-LR 精确相同（−2.283013），无法从缺失角色产生身份区分；只补当前深度孔洞不能补历史。n82 median1179.155 与无标签掩码外环 median1183.553 相差−4.398 mm，是背景相近的数值证据，不是已证实的鱼体像素污染。
- F764：正确 H1 的 depth log-LR −0.096855，错误 H0 为+1.493409；深度方向反对正确映射1.590263。B 只有两样本，历史 span0.033 s、gap1.196 s、scale544.086 mm。当前 n95 retained 96 点确实保留真实测量；raw 核136点包含较高尾部，v2 retained MAD16.808→7.178，但不能据此宣布删除的像素一定是背景。
- F1390：正确 H1 相对错误 H0 的几何优势+0.994005被深度−0.895782几乎抵消，联合 margin0.098223，小于 log9=2.197225，实际仍发布 H0。B 仅一条历史、预测 scale363.347 mm。门槛保持原值，不能按此错误参考降低。
- F1805：正确 H1 几何优势+0.755392，深度贡献−1.116539，旧联合模型偏向错误 H0；A/B gap均1.396 s，历史 span仅0.299/0.199 s。当前两个核原始测量充足，换补全不是此处已见直接瓶颈。

## 两处真实置乱损害

- F519：v2 两个 retained 核 median934.242/1155.879 mm、实际 MAD3.394/7.598。正确 H0 的 depth log-LR2.732211、错误 H1−0.550220，正确深度优势3.282432；几何也偏向正确 H0，联合 margin4.124292。原始身份出版保持原生输出。仅交换当前深度给候选评分后，错误 H1 margin2.440572并真实错误提交。它证明该控制有实际扰动与方法敏感性，不能证明原深度已带来正增量。
- F1027：正确 H0 的深度优势1.621738被错误 H1 的几何优势1.847592抵消，错误最佳候选 margin仅0.225854，未过 log9，H0 回退保持正确原生输出。置乱后错误 margin3.469330并真实提交。raw n137 核62/88点、实际 MAD42.936，scale63.656>60而拒绝；v2 retained相同，新增 inferred20/88点让 pair 可用（19 q raw17→v2 18）。inferred 实际 MAD0.213，接口 MAD40.469=60/1.4826是故意扩大后的噪声适配量，不能把0.213当测量精度，也不能把40.469当实测离散度。其 median1172.023 与无标签外环1183.820相近，物理鱼体归属仍 UNKNOWN。

## 受限残片与资格边界

F398/F434/F1280/F1504 的两成员恢复路径还存在第三个可见成员残片，依次 n59/n3/n88/n132。图中显示这些匿名残片和全部邻近预测轮廓，未删除残片来美化病例。F434 旧数值已接受 H2（margin2.556323），仍被可见残片限制阻止真实恢复；深度分数变好不会自动解除控制器的两成员边界。其 post retained167/178点都合格。

F1745 是扩大 ROI 的资格损失边界：n190 ROI194，raw126点 MAD41.071→scale60.891>60；v2 retained119点 MAD40.527→scale60.085>60；inferred只有11/194=0.0567，n与比例同时不足。另一 post n9 retained260/333合格。pair共享资格使所有 depth 边无信息，正确提交来自原几何。扩大 ROI 确实可纳入异质深度，不能因为接近60门槛而按 GT 删像素或放宽阈值。

## 全部 19 q：背景统计单位

整幅统计使用所有有限正深度像素；对象统计使用每个当帧 core_usable 预测对象的选定 cohort median，每对象等权一次，包括 query。没有按 GT、鱼 ID、候选角色或结果过滤背景。对象范围/IQR 是对象 median 的分布，不是像素分布、物理鱼群真值或新的预测收益。

{table(['q','raw 全幅 median/MAD','raw usable/全部对象','raw 对象 median 范围','raw 对象 IQR','v2 全幅 median/MAD','v2 usable/全部对象','v2 对象 median 范围','v2 对象 IQR'], bg_rows)}

全幅 median一直约1156–1164 mm、MAD约30–39 mm，而当前对象 median 范围和 IQR 明显更宽，且多个对象在约800–1050 mm。旧零假设由像素计数主导，密集背景像素可压过对象数量；把这种分布直接作为对象 median 的零假设，存在统计单位不一致。该判断不需要确认哪些像素是水缸或鱼体。

公开 BACKGROUND_DENSITY.svg/png 仅由上述数值生成，全19 q叠加旧整幅 t4 null与对象等权 component/base诊断 KDE；两者均为归一化密度，单位1/mm。新公开实线 component_base=hypot(max(15,1.4826×core接口MAD),15)，尚未卷入 query_sigma。旧10张受限图的紫线更简单：直接使用max(15,1.4826×core接口MAD)的未卷积统计 KDE。**两组诊断曲线都不冒称实际 DS10 新选择器密度或后验。** 实际计划中的新选择器额外使用hypot(component_base,query_sigma)，每个post得到同一组候选共享的查询背景密度；inferred保持60mm适配下限。背景含查询，是当帧拟合的 plug-in 对比，不是校准后的 Bayesian posterior。

## 来源、配准与可识别边界

实际 raw aligned NPZ 的 depth_mm/source_index 回查同帧 native uint16，再按记录 R/t投到RGB网格。全38个核的记录投影最大误差 {max(p['source_binding']['raw_recorded_reprojection_max_error_mm'] for c in cases for p in c['posts'].values()):.10f} mm（float32舍入量级）。这是记录来源和计算一致性的证据，不是物理标定准确性的证明。

记录 R 的 det={data['calibration_summary']['recorded_rotation_det']:.16f}，奇异值={data['calibration_summary']['singular_values']}，正交误差={data['calibration_summary']['orthogonality_error']:.16f}。不修改记录输入、不用 GT 求修正；真实鱼体表面深度、光学/水下标定准确性、硬件异常根因仍 UNKNOWN。

v2来自三个实际保存的 native H5当前精确index/row，使用原记录投影和最近正Z光栅。retained与inferred分别统计，未来支持为UPSTREAM_I_PLUS_1_OFFLINE且上游使用RGB；不是在线因果深度。未读取v3，不采用剔除p4的近似投影。v2新增近处推断点可改变原深度投影竞争者，source_index和逐病例native winner摘要已绑定；不能假设两张对齐图同坐标一定来自同个native像素。

## 仅保留一版最小修复

1. 保持同版本、同干净历史资格与断点，把短WLS外推改为稳健 local-level；所有尺度证据仅来自过去。不能利用q/post/身份评分压缩预测尺度，历史缺失保持无信息。
2. 保持背景公共密度和合法H0映射，将整幅像素零假设改为当帧所有合格对象等权t4 KDE，包含query，至少3对象；保留既有15/60mm下限与缺少对象时的整幅回退。显式记录component/base与query卷积。

ROI、触发、q、几何、发布/state版本和log9保持冻结方案。新效果须由独立封存全段输出、实际首次出版和原生比较确认；本诊断不预测效果，也不要求以纯几何为深度收益门槛。

## 全19 q选择与实际发布概览

best与实际choice分开：低margin或stage限制可保留H0。旧参考不可用于GT挑选像素或调参。

{table(['q','event','首发布参考','数值 best','实际 choice','margin','post pair','可见残片'], event_rows)}

## 绑定与受限图清单

CASE_STATS.json：{artifact(source)['bytes']} bytes，SHA256 {artifact(source)['sha256']}。

PRIVATE_INVENTORY.json：SHA256 {artifact(HERE/'PRIVATE_INVENTORY.json')['sha256']}，逐图真实绝对路径/bytes/SHA，not_for_Git=true；10图共 {sum(p['artifact']['bytes'] for p in json.loads((HERE/'PRIVATE_INVENTORY.json').read_text(encoding='utf-8'))['private_figures'])} bytes。图只含原深度、预测轮廓、来源/资格、数值直方图/时间线，不含RGB私有纹理或GT栅格。>5000值以红色和数值说明，不裁掉高值以隐藏异常。

DS9 SCORING_SEALED SHA256 {data['scoring']['sha256']}。原strict metadata比较失败及append-only浮点adapter评分背景保留于DS9封存审查；本诊断未修订旧预测/旧分数。

生成代码、全部来源路径/bytes/SHA、事件/测量seal绑定、当前原native/v2 row、记录标定摘要详见CASE_STATS；新增纯数值图语义和元数据绑定见BACKGROUND_DENSITY_META.json。公开文件无像素坐标—深度逐点表、mask/RLE、GT ID栅格或rawpayload。诊断退出0。
'''
    (HERE/'FAILURE_ANALYSIS.md').write_text(text, encoding='utf-8')
    print('Sealed old diagnosis summary PASS: 19 queries; 10 private actual-depth figures; numeric-only density plots')


if __name__ == '__main__':
    main()
