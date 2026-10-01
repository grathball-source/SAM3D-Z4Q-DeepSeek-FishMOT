"""Report actual complete results and source-bound failure facts; no prediction edit."""
from common import *
from collections import Counter
import numpy as np

def main():
    result=read(RUN/'METRICS.json');assert read(HERE/'FINAL_CHECKS.json')['status']=='PASS'
    names=['fishsa_development_8400','fishsa_validation_2888','Feeding','L3','LW']
    labels=['FishSA开发8400','FishSA验证2888','Feeding四段1471','L3（弱参考）','LW（弱参考）']
    table=['| 数据 | 分支 | IDF1 | HOTA | AssA | IDSW | FP | FN |','|---|---|---:|---:|---:|---:|---:|---:|']
    dtable=['| 数据 | ΔIDF1 | ΔHOTA | ΔAssA | ΔIDSW |','|---|---:|---:|---:|---:|']
    for name,label in zip(names,labels):
        item=result['feeding_pooled'] if name=='Feeding' else result['segments'][name]
        for arm in ARMS:
            m=item['metrics'][arm];table.append(f"| {label} | {arm} | {m['IDF1']:.6f} | {m['HOTA']:.6f} | {m['AssA']:.6f} | {m['IDSW']} | {m['FP']} | {m['FN']} |")
        d=item['delta'];dtable.append(f"| {label} | {d['IDF1']:+.6f} | {d['HOTA']:+.6f} | {d['AssA']:+.6f} | {d['IDSW']:+d} |")
    eventtable=['| 片段 | 帧 | 疑似/确认/首分离 | 联合提交：对/错/不可评分 | 新ID提交：对/错/不可评分 | 改变发布帧数 |','|---|---:|---:|---:|---:|---:|']
    coverage=[];groupdiagnostics=[];totals=Counter();birth_status={};timing={}
    for name in SEGMENTS:
        public=RUN/name/'public';manifest=read(input_dir(name)/'SOURCE_MANIFEST.json');s=read(public/'RUN_SUMMARY.json');a=read(public/'EVENT_AUDIT.json')
        es=read(public/'EVENTS.json')['R12_RAW'];gc=a['group_physical_counts'];bc=a['birth_physical_counts']
        eventtable.append(f"| {name} | {s['frames']} | {len(read(input_dir(name)/'scan_v4.json')['suspects'])}/{sum(e['confirm_frame'] is not None for e in es)}/{sum(e['q'] is not None for e in es)} | {gc.get('CORRECT',0)}/{gc.get('WRONG',0)}/{gc.get('UNSCORABLE',0)} | {bc.get('CORRECT',0)}/{bc.get('WRONG',0)}/{bc.get('UNSCORABLE',0)} | {len(result['segments'][name]['changed_frames'])} |")
        cov=manifest['coverage'];coverage.append(dict(segment=name,**cov,core_usable_fraction=cov['usable_cores']/cov['objects']))
        for k in ('CORRECT','WRONG','UNSCORABLE'):totals['group_'+k]+=gc.get(k,0);totals['birth_'+k]+=bc.get(k,0)
        statuses=Counter()
        for b in rows(public/'BIRTHS.jsonl.gz'):
            if b['frame']>1:
                for q in b['queries']:statuses[q['status']]+=1
        birth_status[name]=dict(statuses)
        lat=[x['receive_to_publish_seconds'] for x in rows(public/'PUBLISH_LEDGER.jsonl')]
        timing[name]=dict(preparation_seconds=manifest['preparation_seconds'],replay_seconds=s['elapsed_seconds'],publish_mean_seconds=float(np.mean(lat)),publish_p95_seconds=float(np.quantile(lat,.95)))
        for event in es:
            if event['restore'] is None or event['restore']['status']!='COMMIT':continue
            d=event['numeric']['detail'];best=d['candidates'][d['best']];base=d['candidates']['H0']
            outcome=next(x for x in a['group_events'] if x['event']==event['id'])
            forecasts={role:{k:f.get(k) for k in ('status','samples','mu_mm','scale_mm','slope_mm_s','delta_seconds','sample_frames')} for role,f in d['depth_forecasts'].items()}
            groupdiagnostics.append(dict(segment=name,q=event['q'],original_q=SEGMENTS[name][0]+event['q']-1,physical=outcome['physical'],
                selected=event['numeric']['choice'],mapping=event['restore']['mapping'],baseline=d['baseline_mapping'],
                geometry_delta_vs_native=best['geometry_log_lr']-base['geometry_log_lr'],depth_delta_vs_native=best['depth_log_lr']-base['depth_log_lr'],
                combined_margin=d['margin'],minimum_log_odds=d['minimum_log_odds'],post_depth=d['depth_assignment'],depth_forecasts=forecasts,
                geometric_available={k:v['available'] for k,v in d['geometry_forecasts'].items()},
                candidate_components={k:{f:v[f] for f in ('geometry_log_lr','depth_log_lr','posterior')} for k,v in d['candidates'].items()}))
    records=list(rows(HERE/'EXECUTION_LOG.jsonl'));log_lookup={sha(p):artifact(p) for p in (HERE/'logs').glob('*.txt')}
    relocated=[]
    for r in records:
        item=log_lookup[r['log']['sha256']];assert item['bytes']==r['log']['bytes']
        if item['path']!=r['log']['path']:relocated.append(dict(original_record_path=r['log']['path'],actual_preserved_log=item))
    write_new(HERE/'LOG_RELOCATIONS.json',relocated)
    write_new(HERE/'DIAGNOSTICS.json',dict(actual_group_commits=groupdiagnostics,raw_coverage=coverage,noninitial_birth_status=birth_status,
        physical_commit_counts=dict(totals),timing=timing,source_prediction_masks=sum(c['objects'] for c in coverage),
        depth_sensor_frames=sum(c['sensor_available_frames'] for c in coverage),model_http=0,smoke=0,fees_usd=0,
        prediction_workers_max=3,preparation_peak_workers=6,local_single_thread_per_worker=True))
    correction=read(HERE/'ORIGINAL_REFERENCE_SELECTION.json')
    body='''# DS14 原始深度全量跨片段性能验证（2026-10-02）

## 主判定与边界

COMPLETE_NEGATIVE_MULTI_DATASET_VALIDATION。全部20098帧、八个独立片段均完成真实分支回放、封存和统一评分。当前冻结R12_RAW没有稳定超过同源SAM3：8400和L3明显退化；2888的IDF1略升但IDSW增加；Feeding复现旧微增益；LW完全不变。停止扩展这一冻结版本，不改变参数后再选最好结果。此结果不支持“所有深度信息无效”的理论结论。

工程/输入/发布/统一评分验收PASS；评分引用接线有两次失败及追加修复，原代码、失败日志、原seal全部保留。独立旧NATIVE六项指标逐字段精确复现，Feeding全部1471帧R12映射和事件逐项复现。科学参数、触发、q、参考、候选、二维运动和事务从冻结到结束未改；受试系统是NE1/S0-P底座的冻结R12原始深度版，未启用旧Z4Q常驻D1_DELAYED/BIRTH_REFINE。不能借用旧完整Z4Q或VLM成绩替代本表。

## 完整指标

单位为百分数；Δ为R12_RAW−同源SAM3，百分数差为百分点。所有mask/残片和ID均保留，不删除反光/背景预测，不忽略ID评分。

'''+'\n'.join(table)+'\n\n'+'\n'.join(dtable)+'''

Feeding使用原四段SOURCE_OLD保存预测，合并成绩按ID命名空间隔离后的官方整体统计，非百分数平均。

覆盖边界：Feeding本轮只测试既定四段1471帧，不是0–1906连续1907帧全量。实际核查1907个保存SAM3标签均存在；未纳入的是200–350、556–700、1061–1200，共436帧，不能称输入缺失。详见COVERAGE_BOUNDARIES.json。8400与2888分别清空状态；Feeding每段、L3、LW也分别初始化。L3/LW为分批SAM3拼接保存源，参考是待校正、依赖预测的预标注；只称弱参考诊断，不等同独立GT泛化。已有暴露和两相机时间重叠限制明确保留。没有跨数据集混合总分。

## 事件、正确性与首次发布

以下正确性是封存后的参考身份核对；不能把不可评分当正确或安全。

'''+'\n'.join(eventtable)+'''

全轮联合提交5次：2正确、2错误、1不可评分；新ID重接3次：1正确、2不可评分。联合提交是每次两身份的一个原子事务，不按两个ID计两次。Feeding两次正确联合恢复来自共用旧组机制，一次F1886 n198→176来自新生源路径，维持21帧，不能把共用机制都记作新深度贡献。L3 F668 n19→18、F734 n21→20均无有效参考匹配，保持不可评分。2888的那次联合提交也不可评分，纵使整段IDF1上涨也不能改称正确物理恢复。

每个q只读当前首个合格分离帧；联合选择/提交后第一次发布。PUBLISH_LEDGER绑定实际预测行SHA，TRANSACTIONS绑定实际状态映射。全部q只有一条post事实，未读取后四帧或回填历史。错误提交继续自身映射，因此会扩散到后续帧；这不是只改输出文件的试验。

## 失败原因：有原始深度仍然错改

8400的F4524把n7→1、n1→7，原生映射实际正确。错误alias持续F4524–8400，共3877帧，产生额外2次切换并显著破坏全局身份关联。A身份没有合格clean历史；B深度仅8个连续样本（F4489–4496）。旧组路径仍调用DS9/DS1的WLS，估计摘要趋势−70.986267 mm/s，外推0.933秒得到590.649920mm、尺度117.506677mm。当前n7/n1原始core深度为657.804199/570.173645mm，MAD9.863342/4.697632mm。真实测量有区别，预测均值与宽尺度削弱了区别。这些是掩码core摘要的测量/回归值，不是刚体运动速度或有物理真值的鱼体表面。

错误候选相对原生的几何log证据差+4.183910；深度log证据差−0.071458，深度实际上略偏向原生。联合差+4.112452超过log9=2.197225，遂把单个身份的空间解释变为两个旧ID的强制交换。A缺失虽使用共同无信息模型，仍允许B一条身份独力决定双身份映射；所谓used_edges=2是B的几何与深度两种模态，不是两条身份均获支持。98.39%是未校准的插件式候选后验，不能当物理正确概率。

这暴露一个接线范围问题：R12新生源用修复后的局部水平预测，共用组恢复仍冻在旧WLS。原生优先底座关闭常驻继承，使真正能改变身份的路径主要落在组恢复；开发8400的3个非初始新源全部处于事件保护，未走新生源提交。原始深度覆盖好，也不能补齐缺失身份历史或自动纠正外推/联合准入错误。

L3本地q1421（原F1420）也把ID6/9错误交换；两次新生源提交不可评分。LW有70个疑似、19个确认、8个首分离事件，均未改映射，所以零增益不等于没有事件。详细分项在DIAGNOSTICS、逐段EVENT_AUDIT、BIRTHS、EVENTS及完整SWITCHES中。两臂实验不识别深度独立必要性，但已经证明当前整个深度版在该输入范围没有稳定提点。

## 原始来源、缺测与评分修正

输入只读原始sensor。FishSA仅aligned/raw_depth_mm、aligned/raw_source_index、native/original_depth_mm；global1原本无配对深度，保留缺失。L3/LW按原标定、像素中心投影和最近Z规则对齐；超5ms帧记缺测。Feeding仅depth_mm/source_index与原native NPY。H5/NPZ字段白名单实际拒绝其他列；混合文件的整文件SHA不代表读取其中GT/v3。匿名、风险、版本切断与不可评分原样保留。coverage和时间见DIAGNOSTICS；可用core不是物理深度准确率。

两类评分接线错误单列：初始开发GT摘要字符串漏字，追加采用旧固定scorer的64位SHA；对齐包labels_original改写imagePath/imageData/dataset_frame_id，且原F9398另有一处标注版本差异。正式验证段按原baseline inputs.zip内的GT归档和每条原始SHA读取，完整1080栅格后最近邻到640，严格复现旧NATIVE成绩。先前失败不能算方法结果，也未覆盖任何旧seal/已评分文件。SCORING_FREEZE、SCORING_REFERENCE_FIX和ORIGINAL_REFERENCE_SELECTION保留逐次来源；FINAL_CHECKS证明全部基线精确复现。实际完整评分链为score_frozen_outputs→finish_scoring；score_remaining的旧假设失败保留。复现的新空输出应使用score_protocol.py；禁止对本封存目录重评分。

输入适配还保留失败记录：旧缓存OpenCV距离统计末位差约1e−6像素，所有ROI/深度统计/质量必须精确一致后保留旧raw缓存字节；FishSA旧采集文件附带未发布的救援提案RLE，按保存N0白名单取真正原生观测，全部N0 mask保留。没有用这些旧提案或旧身份分支作新预测。

## 调用、时延、产物与复现

新增模型HTTP0、smoke0、训练0、SAM3推理0、补全0、费用$0，无key依赖。全部本地CPU；正式预测最多3个独立单线程进程，输入准备峰值6个，未用GPU或服务器。缓存准备和实时取当前出生帧的测量时间分开列出；回放不等于整套SAM3实时部署。普通数据/代码/日志与数值预测公开；原深度、预测RLE、GT归档和实际像素可视化受限，真实路径/字节/SHA见输入来源及RESTRICTED_INVENTORY、RESTRICTED_VISUALS。私有前中后图基于实际发布映射，只在封存后画q±1，不作为输入。公开PERFORMANCE.svg只有数值指标。

全部1334个旧受保护文件核验未变。所有成功/失败命令及出口在EXECUTION_LOG；失败日志为保留而改名，LOG_RELOCATIONS按原SHA绑定真实保存路径。图像QA已经实际查看8400 F4524与L3原F1420错改前后，public图没有私有像素。提交与origin/main实际核验另追加在REMOTE_VERIFICATION。

## 未完成边界与唯一下一步

没有独立GT验证L3/LW，没有物理鱼体深度真值，没有证明深度单独必要，没有修复或重跑本冻结版本。预测、评分、全部数字记录和报告已完成；原始私有像素按约定不进入Git。

唯一下一步：统一组恢复与新生源的深度预测接线，检查逐身份支持，设计一版以可辨别深度证据准入的联合恢复修复；冻结后在相同完整段检验能否超过同源原生。首先针对F4524这类缺一条历史而强制交换的真实失败，原有UNKNOWN不补造。修复仅恢复原生水平应称止损，不能称提点。本轮不自动启动该修复、不加模型。
'''
    write_new(HERE/'RUN_NOTES.json',dict(status='COMPLETE_NEGATIVE_MULTI_DATASET_VALIDATION',frames=20098,masked_or_ignored_IDs=0,
        engine_input_publication_scoring='PASS_WITH_APPEND_ONLY_SCORING_REFERENCE_ERRATA',scientific_goal='NOT_MET_ACROSS_DATASETS',
        annotation_version_differences=len(correction['annotation_version_differences']),original_models_HTTP=0,actual_new_model_HTTP=0,
        scientific_version_stopped=True,full_prediction_and_metrics_complete=True,automatic_next_trial=False))
    (HERE/'RESULTS.md').write_text(body,encoding='utf-8',newline='\n')
    inventory=[artifact(p) for p in (HERE/'private').rglob('*') if p.is_file()]
    write_new(HERE/'RESTRICTED_INVENTORY.json',dict(private_derived_and_failed_attempt_artifacts=inventory,
        original_sources='Actual paths/bytes/SHA in inputs/*.json and private RAW_SOURCES.json; shared source arrays immutable',
        dependencies='Existing D-MOT Python/TrackEval, recorded original raw packages and saved native masks required; no service/key',
        reproduction='New isolated output copy; prepare raw inputs; adapter/real-prefix checks; freeze; full own-state replay; score_protocol; post checks. Never overwrite run/private old seals.'))
    print('Complete report, all case facts, private inventory, log relocation proof written')
if __name__=='__main__':main()
