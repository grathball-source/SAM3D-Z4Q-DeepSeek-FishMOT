"""Summarize sealed features and old labels; all raster plots stay private."""
from common import *
from audit import key
from collections import Counter,defaultdict
from statistics import median,mean
import math
import numpy as np

def stats(values):
    v=[x for x in values if x is not None and math.isfinite(x)]
    return dict(n=len(v),median=median(v) if v else None,mean=mean(v) if v else None,
                q10=float(np.quantile(v,.1)) if v else None,q90=float(np.quantile(v,.9)) if v else None,
                minimum=min(v) if v else None,maximum=max(v) if v else None)

def summarize():
    verify_freeze();seal=read(HERE/'FEATURES_SEALED.json')
    for pin in seal['files']:verify_item(pin)
    labeled=read(HERE/'LABELED_ACTIONS.json');assert len(labeled['actions'])==90
    local={key(v['segment'],v['frame'],v['native']):v for v in rows(HERE/'LOCAL_MEASUREMENTS.jsonl.gz')}
    pairs=read(HERE/'LOCAL_PAIR_COMPARISONS.json')['pairs'];actions=[]
    for a in labeled['actions']:
        c=local[a['current']];anchor=local[a['anchors'][a['primary_role']]]
        near=[p for p in pairs if a['current'] in (p['first'],p['second'])]
        usable=[p for p in near if p['both_measured_core_support']]
        actions.append(dict(action_id=a['action_id'],segment=a['segment'],physical=a['physical'],
            actual_reference_physical=a['actual_reference_physical'],current_extract_usable=c['DS35_extract']['usable'],
            anchor_extract_usable=anchor['DS35_extract']['usable'],current_extract_reason=c['DS35_extract']['reason'],
            anchor_extract_reason=anchor['DS35_extract']['reason'],current_background_status=c['local_background']['status'],
            anchor_background_status=anchor['local_background']['status'],neighbors=len(near),both_core_proxy_pairs=len(usable),
            whole_neighbor_auc=stats([p['comparisons']['whole']['separation_auc'] for p in usable]),
            core_neighbor_auc=stats([p['comparisons']['core']['separation_auc'] for p in usable]),
            core_minus_whole_auc=stats([p['comparisons']['core']['separation_auc']-p['comparisons']['whole']['separation_auc'] for p in usable]),
            temporal_comparison=a['temporal_population_comparisons'][a['primary_role']],
            physical_surface_ownership='UNKNOWN',tracker_commit=False))
    grades={}
    for grade in sorted({a['physical'] for a in actions}):
        group=[a for a in actions if a['physical']==grade]
        grades[grade]=dict(actions=len(group),current_depth_usable=sum(a['current_extract_usable'] for a in group),
            anchor_depth_usable=sum(a['anchor_extract_usable'] for a in group),
            both_endpoint_depth_usable=sum(a['current_extract_usable'] and a['anchor_extract_usable'] for a in group),
            actions_with_local_neighbor=sum(a['neighbors']>0 for a in group),
            actions_with_both_core_proxy=sum(a['both_core_proxy_pairs']>0 for a in group),
            current_depth_reasons=dict(Counter(a['current_extract_reason'] for a in group)),
            anchor_depth_reasons=dict(Counter(a['anchor_extract_reason'] for a in group)),
            core_minus_whole_auc=stats([a['core_minus_whole_auc']['mean'] for a in group]))
    bins=defaultdict(list)
    for p in rows(HERE/'CAUSAL_FORECAST_PAIRS.jsonl.gz'):bins[(p['segment'],str(p['nominal_horizon_seconds']))].append(p)
    calibration=[]
    for (name,horizon),values in sorted(bins.items()):
        errors={variant:dict(absolute_error_mm=stats([p['errors'][variant]['absolute_error_mm'] for p in values]),
            normalized_error=stats([p['errors'][variant]['standardized_absolute_error'] for p in values]),
            one_scale_coverage=mean(p['errors'][variant]['within_one_scale'] for p in values),
            two_scale_coverage=mean(p['errors'][variant]['within_two_scales'] for p in values))
            for variant in ('WLS','INTERCEPT_MATCHED_SCALE','LAST_VALUE_MATCHED_SCALE')}
        frag=defaultdict(list)
        for p in values:frag[p['fragment']].append(p)
        difference={f:mean(p['errors']['WLS']['absolute_error_mm']-p['errors']['INTERCEPT_MATCHED_SCALE']['absolute_error_mm'] for p in ps) for f,ps in frag.items()}
        calibration.append(dict(segment=name,horizon_seconds=float(horizon),pairs=len(values),fragments=len(frag),
            actual_horizon_seconds=stats([p['actual_horizon_seconds'] for p in values]),
            combined_scale_mm=stats([p['combined_scale_mm'] for p in values]),
            slope_mm_s=stats([p['forecast']['slope_mm_s'] for p in values]),errors=errors,
            fragment_equal_weight_mean_error_WLS_minus_intercept_mm=stats(list(difference.values())),
            fragments_WLS_better=sum(d<0 for d in difference.values()),fragments_intercept_better=sum(d>0 for d in difference.values()),
            no_independent_sample_significance_claim=True,physical_error_calibration=False))
    gate=list(rows(HERE/'DS35_GATE_SCALE_COMPONENTS.jsonl.gz'))
    summary=read(HERE/'MEASUREMENT_SUMMARY.json')
    result=dict(status='COMPLETE_READ_ONLY_DEPTH_EVIDENCE_AND_FORECAST_AUDIT',original_physical_counts=labeled['physical_counts'],
        measurement_summary=summary,action_support_by_grade=grades,actions=actions,causal_forecast_groups=calibration,
        frozen_DS35_gate_forecasts=gate,local_pair_count=len(pairs),
        local_pair_core_minus_whole_auc=stats([p['comparisons']['core']['separation_auc']-p['comparisons']['whole']['separation_auc'] for p in pairs if p['both_measured_core_support']]),
        local_objects_core_vs_background_auc=stats([v['views']['core']['background_comparison']['separation_auc'] for v in local.values() if v['views']['core']['measurement_support']]),
        current_producer_reset_metadata='UNKNOWN',weak_reference_sources=['L3','LW'],independent_validation=False,
        new_tracker_predictions=None,new_tracker_metrics=None,new_commits=0,model_http=0,cost_usd=0,
        feature_seal=artifact(HERE/'FEATURES_SEALED.json'),original_metrics=artifact(DS35/'run/METRICS.json'))
    save('RESULTS.json',result)
    return result

def plot_public(result):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    public=HERE/'visuals';public.mkdir(exist_ok=True)
    private=HERE/'private';private.mkdir(exist_ok=True)
    groups=result['causal_forecast_groups'];fig,axes=plt.subplots(2,1,figsize=(11,8),layout='constrained')
    for name in SEGMENTS:
        data=sorted([g for g in groups if g['segment']==name],key=lambda g:g['horizon_seconds'])
        if not data:continue
        x=[g['horizon_seconds'] for g in data]
        axes[0].plot(x,[g['errors']['WLS']['absolute_error_mm']['median'] for g in data],marker='o',label=name+' WLS')
        axes[0].plot(x,[g['errors']['INTERCEPT_MATCHED_SCALE']['absolute_error_mm']['median'] for g in data],linestyle='--',label=name+' intercept')
        axes[1].plot(x,[g['combined_scale_mm']['median'] for g in data],marker='o',label=name)
    axes[0].set(title='Causal prefix forecasts: observed mask-proxy error',ylabel='Median absolute error (mm)')
    axes[1].set(title='Frozen WLS scale (unvalidated physical uncertainty)',ylabel='Median combined scale (mm)',xlabel='Nominal holdout horizon (seconds)')
    for ax in axes:ax.set_xscale('log');ax.grid(alpha=.25);ax.legend(fontsize=6,ncol=2)
    fig.suptitle('DS36 descriptive audit — same continuous source; no tracking intervention',fontsize=11)
    fig.savefig(public/'CAUSAL_FORECAST_DIAGNOSTIC.svg');fig.savefig(private/'CAUSAL_FORECAST_DIAGNOSTIC.png',dpi=150);plt.close(fig)
    return [artifact(public/'CAUSAL_FORECAST_DIAGNOSTIC.svg')]

def private_plots(result):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    labeled=read(HERE/'LABELED_ACTIONS.json')['actions'];wanted=[]
    for a in labeled:
        if a['physical']=='WRONG':wanted.append(dict(name=a['action_id'],selection='ALL_OLD_WRONG_ACTIONS_POSTSEAL',
            grade=a['physical'],keys=[a['anchors'][a['primary_role']],a['current']]))
    for name in SEGMENTS:
        for grade in ('CORRECT','UNSCORABLE'):
            controls=[a for a in labeled if a['segment']==name and a['physical']==grade]
            if controls:
                a=min(controls,key=lambda a:a['frame']);wanted.append(dict(name=a['action_id'],selection='EARLIEST_GRADE_CONTROL_PER_SOURCE_POSTSEAL',
                    grade=grade,keys=[a['anchors'][a['primary_role']],a['current']]))
        for e in read(DS35/'run'/name/'public/EVENTS.json')['DEPTH_OVERRIDE']:
            if not e.get('joint_decision',{}).get('common_weights',{}).get('depth'):continue
            ks=[key(name,ref['anchor']['frame'],ref['anchor']['native_id']) for ref in e['joint_pre'].values() if ref['anchor']]
            ks.extend(key(name,e['q'],int(n)) for n,post in e['post_roles'].items() if any(p['frame']==e['q'] for p in post))
            wanted.append(dict(name=name+'/'+e['id'],selection='ALL_DS35_COMMON_DEPTH_GATE_CASES',grade='UNKNOWN_EVENT_MAPPING',keys=ks))
    local={key(v['segment'],v['frame'],v['native']):v for v in rows(HERE/'LOCAL_MEASUREMENTS.jsonl.gz')}
    destination=HERE/'private/cases';destination.mkdir(parents=True,exist_ok=False)
    records=[]
    for number,case in enumerate(wanted,1):
        name=case['keys'][0].split('/')[0];views={};sensor=SOURCE.RawDepth(name)
        keys=sorted(set(case['keys']),key=lambda k:(local[k]['frame'],local[k]['native']))
        frames={local[k]['frame'] for k in keys}
        assignments={r['frame']:r for r in rows(input_dir(name)/'assignments.jsonl.gz') if r['frame'] in frames}
        try:
            for k in keys:
                f=local[k];d,ix,nat,b=sensor(f['global_frame'],f['time']);assert b==f['source_binding']
                masks=SOURCE.native_masks(assignments[f['frame']]);own=masks[f['native']]
                assert MEASUREMENT.array_binding(own)==f['mask_binding']
                occupancy=sum((m.astype('u2') for m in masks.values()),np.zeros(own.shape,'u2'))
                core,_=MEASUREMENT._old.adaptive_core(own,occupancy)
                views[k]=(d,own,core,masks)
        finally:sensor.close()
        fig,axes=plt.subplots(2,len(keys),figsize=(5*len(keys),7),squeeze=False,layout='constrained')
        for col,k in enumerate(keys):
            f=local[k];d,own,core,masks=views[k];yy,xx=np.nonzero(own)
            x0,x1=max(0,int(xx.min())-24),min(640,int(xx.max())+25);y0,y1=max(0,int(yy.min())-24),min(360,int(yy.max())+25)
            cut=d[y0:y1,x0:x1];valid=cut[cut>0];lo,hi=np.quantile(valid,[.02,.98]) if len(valid) else (0,1)
            ax=axes[0,col];im=ax.imshow(np.where(cut>0,cut,np.nan),cmap='viridis',vmin=lo,vmax=max(hi,lo+1),extent=(x0,x1,y1,y0))
            ax.contour(own.astype(float),levels=[.5],colors=['red'],linewidths=1)
            if core.any():ax.contour(core.astype(float),levels=[.5],colors=['cyan'],linewidths=.9)
            for n,m in masks.items():
                if n!=f['native'] and (MEASUREMENT._dilate(own,20)&m).any():ax.contour(m.astype(float),levels=[.5],colors=['orange'],linewidths=.5)
            ax.set_xlim(x0,x1);ax.set_ylim(y1,y0);ax.set_title(f'F{f["frame"]} / native {f["native"]}\nred mask, cyan core; raw Z mm')
            fig.colorbar(im,ax=ax,fraction=.04)
            ax=axes[1,col]
            for role in ('whole','core','patch1','patch2','patch3'):
                s=f['views'][role]['summary'];z=s['median']
                if z is not None:ax.errorbar([role],[z],yerr=[[z-s['q10']],[s['q90']-z]],fmt='o',label=f'{role}: n={s["n"]}, cov={s["valid_fraction"]:.2f}')
            s=f['background']['summary']
            if s['median'] is not None:ax.axhline(s['median'],color='black',ls='--',label=f'annulus proxy n={s["n"]}')
            ax.set_ylabel('Median / 10–90% population range (mm)');ax.legend(fontsize=7);ax.grid(alpha=.2)
        fig.suptitle(case['name']+'\n'+case['grade']+' — pixel ownership UNKNOWN; no GT/RGB pixels',fontsize=11)
        path=destination/f'{number:03d}.png';fig.savefig(path,dpi=120);plt.close(fig)
        records.append(dict(case,artifact=artifact(path),source_frames=[dict(key=k,source=local[k]['source_binding'],mask=local[k]['mask_binding']) for k in keys]))
        print('PRIVATE_CASE',number,case['name'],flush=True)
    save('PRIVATE_VISUALS.json',dict(status='ALL_WRONG_AND_FIXED_CONTROLS_AND_ALL_GATE_FAILURES_RENDERED',cases=records,
        pixels_private=True,GT_raster=False,RGB=False,model_http=0,cost_usd=0))
    return records

def report(result,public,private):
    g=result['action_support_by_grade'];table=['|旧物理标签|动作|当前深度可用|旧anchor可用|两端均可用|存在局部伙伴|双core代理可测|',
        '|---|---:|---:|---:|---:|---:|---:|']
    for grade,v in g.items():table.append('|'+grade+'|'+'|'.join(str(v[k]) for k in ('actions','current_depth_usable','anchor_depth_usable','both_endpoint_depth_usable','actions_with_local_neighbor','actions_with_both_core_proxy'))+'|')
    lines=['# DS36 局部深度证据与因果外推审查',
        '主判定：完成全部固定测量与旧标签连接。原Z4Q状态、预测、trigger、q、候选和全部旧seal未改。没有新的跟踪性能试验或提点成绩。',
        '## 对称覆盖', '\n'.join(table),
        f'原90动作、75事件，实际测量{result["measurement_summary"]["raw_frames"]}个raw帧、{result["measurement_summary"]["measured_objects"]}个mask上下文、{result["local_pair_count"]}个同帧匿名邻域配对。每个来源、缺失请求、原始层/质量与群组情况均在MEASUREMENT_SUMMARY/LOCAL_MEASUREMENTS保存。',
        '局部core/三分块由mask几何选择，所有深度层保留；native源去重，跨mask共用源排除。分布AUC是两个匿名mask人口的数值区分，不是鱼体表面、身份或可恢复准确率。背景annulus/平面也是代理。',
        '## 冻结时间外推对照',
        '|来源|目标间隔s|配对/片段|WLS median误差mm|intercept median误差mm|last-value median误差mm|median combined scale mm|WLS一倍scale覆盖|',
        '|---|---:|---:|---:|---:|---:|---:|---:|']
    for c in result['causal_forecast_groups']:
        e=c['errors'];lines.append(f'|{c["segment"]}|{c["horizon_seconds"]:.4f}|{c["pairs"]}/{c["fragments"]}|'+
            '|'.join(f'{e[k]["absolute_error_mm"]["median"]:.3f}' for k in ('WLS','INTERCEPT_MATCHED_SCALE','LAST_VALUE_MATCHED_SCALE'))+
            f'|{c["combined_scale_mm"]["median"]:.3f}|{100*e["WLS"]["one_scale_coverage"]:.2f}%|')
    lines.extend(['同版本、实际bank当前anchor、无neighbors、无实际群组/pending和无混层的连续mask片段用于时间代理核对。验证目标不进入过去拟合；首个达到目标间隔的观测缺测时保留缺失，不挑下一个可用帧。时间风险/缺测与每个片段机会完整保存。单片段相关样本不按独立样本做显著性检验。',
        'INTERCEPT/LAST_VALUE沿用同一WLS scale，仅核对均值外推误差；未成为新跟踪策略。1/2倍scale覆盖只是代理残差覆盖，未标定为物理准确率。较长间隔没有可用片段时保持无样本，不能外推到遮挡期间。',
        '## DS35尺度来源',
        f'逐一重算{len(result["frozen_DS35_gate_forecasts"])}个唯一冻结预测，严格核验mu、slope、scale及全部引用，分解参数协方差与15mm时间漂移项；数值在DS35_GATE_SCALE_COMPONENTS中。匿名post对所有候选分别列残差，未按正确标签选解释。',
        '## 可视化与来源限制',
        f'全部旧错误动作、每来源最早正确/不可评分对照及全部共同深度门槛病例生成{len(private)}份真实raw depth/mask图。私有路径、字节、SHA及来源绑定见PRIVATE_VISUALS；聚合数值图见visuals。图中没有GT raster或RGB。',
        '同录像及既有曝光片段的探索诊断，L3/LW仍是弱预测派生参考；producer reset与水下物理深度标定UNKNOWN。mask内部单峰、高AUC和非零值均不认证鱼体。',
        '## 工程与费用',
        '必要数值/来源检查通过；旧源码和全部预测/源绑定在运行前冻结并在测量封存及交付前复核。初始化阶段的配置namespace和私有manifest/Git范围两次适配失败日志保留；正式测量只接受冻结后的完整seal。新HTTP、smoke、GPU、服务器作业、训练、SAM3推理、补全与费用全部0。',
        '## 后续边界',
        '本报告是数值自动汇总；具体病例原因、尺度合理性与唯一后续方案见DEEP_REVIEW.md。未按本轮标签改门槛或生成新的关联成绩。'])
    with (HERE/'FINAL_REVIEW.md').open('x',encoding='utf-8',newline='\n') as f:f.write('\n\n'.join(lines)+'\n')
    save('REPORT_VALIDATION.json',dict(status='PASS',actions=sum(v['actions'] for v in g.values()),events=75,
        result=artifact(HERE/'RESULTS.json'),report=artifact(HERE/'FINAL_REVIEW.md'),public_figures=public,
        private_cases=len(private),old_seals_verified=True,new_metrics=False,new_predictions=False,model_http=0,cost_usd=0))

if __name__=='__main__':
    result=summarize();public=plot_public(result);private=private_plots(result);report(result,public,private)
    print('REPORT COMPLETE',flush=True)
