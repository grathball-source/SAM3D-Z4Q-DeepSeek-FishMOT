"""Postscore-only H0/fallback controls and sealed ordinal coverage, not failed commits."""
from common import *
from collections import Counter
import math
from failure_case_review import (ARM, DATASETS, dataset, require_complete, inspect_case,
                                install_pixel_guard, order_summary)


def summarize(metric):
    summaries={name:dict(split_decisions=0,order_eligible=0,missing_p=0,
        weak_uncalibrated_proxy=0,order_status=Counter(),order_reasons=Counter(),
        decision_reasons=Counter(),restore_status=Counter(),selected_choice=Counter(),
        candidate_order_used=Counter(),first_public_bank=Counter(),first_public_consensus=Counter(),
        local_return_bank=Counter(),local_return_joint=Counter(),local_return_public_origin=Counter())
        for name in DATASETS}
    choices={name:[] for name in DATASETS};facts=[];sources=[]
    for segment in SEGMENTS:
        public=RUN/segment/'public';unit=summaries[dataset(segment)]
        events={event['id']:event for event in read(public/'EVENTS.json')[ARM]}
        audits={row['event']:row for row in read(public/'EVENT_AUDIT.json')['arms'][ARM]['group_events']}
        for row in rows(public/'ORDER_EVIDENCE.jsonl.gz'):
            if row['arm']!=ARM:continue
            event=events[row['event']];grade=audits[row['event']]
            detail=row['detail'];evidence=detail['order_evidence'];restore=row['restore']
            assert row['frame']==event['q'] and detail==event['numeric']['detail'] and restore==event['restore']
            probability=evidence.get('p_A_nearer_at_q')
            finite=isinstance(probability,(int,float)) and math.isfinite(probability)
            unit['split_decisions']+=1;unit['order_eligible']+=bool(evidence.get('eligible'))
            unit['missing_p']+=not finite
            unit['weak_uncalibrated_proxy']+=finite and .1<probability<.9
            unit['order_status'][evidence.get('status','ABSENT')]+=1
            unit['order_reasons'][evidence.get('reason','ABSENT')]+=1
            unit['decision_reasons'][detail.get('reason','ABSENT')]+=1
            unit['restore_status'][restore.get('status','ABSENT')]+=1
            unit['selected_choice'][restore.get('selected_choice','ABSENT')]+=1
            unit['first_public_bank'][grade.get('first_public_physical','ABSENT')]+=1
            unit['first_public_consensus'][grade.get('first_public_pre_consensus_verdict','ABSENT')]+=1
            for label,candidate in detail.get('candidates',{}).items():
                if candidate.get('order',{}).get('used'):unit['candidate_order_used'][label]+=1
            global_q=SEGMENTS[segment][0]+row['frame']-1
            facts.append(dict(dataset=dataset(segment),segment=segment,event=row['event'],
                q=row['frame'],global_q=global_q,order=order_summary(detail),restore=restore,
                first_public_bank=grade.get('first_public_physical'),
                first_public_consensus=grade.get('first_public_pre_consensus_verdict'),
                actual_joint_commit=restore.get('status')=='COMMIT',
                H0_fallback_is_not_correctness=True))
            if restore.get('selected_choice')=='H0' and (restore.get('fallback') is not None or
                    restore.get('decision_source')=='OWN_BRANCH_LOCAL_FALLBACK'):
                choices[dataset(segment)].append(dict(segment=segment,event=event,audit=grade,global_q=global_q))
        local=read(public/'LOCAL_RETURN_AUDIT.json')['arms'][ARM]
        for row in local:
            unit['local_return_bank'][row['actual_reference_physical']]+=1
            unit['local_return_joint'][row['physical']]+=1
            unit['local_return_public_origin'][row['prior_public_reference_status']]+=1
        sources.extend(artifact(public/file) for file in
            ('EVENTS.json','EVENT_AUDIT.json','ORDER_EVIDENCE.jsonl.gz','LOCAL_RETURN_AUDIT.json'))
    selected={name:min(values,key=lambda x:(x['global_q'],x['segment'],x['event']['id'])) if values else None
              for name,values in choices.items()}
    for name,unit in summaries.items():
        for key,value in tuple(unit.items()):
            if isinstance(value,Counter):unit[key]=dict(value)
        unit['H0_fallback_controls_available']=len(choices[name])
    units={'Feeding':metric['feeding_pooled'],**{name:metric['segments'][name] for name in DATASETS[1:]}}
    fields=('IDF1','HOTA','AssA','IDSW','FP','FN')
    deltas={name:{f:unit['metrics']['MIXED_RETURN'][f]-unit['metrics']['ACTIVITY_RETURN'][f] for f in fields}
            for name,unit in units.items()}
    return summaries,selected,facts,sources,deltas


def visualize_control(case):
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from source import RawDepth,native_masks
    segment,q=case['segment'],case['q'];public=RUN/segment/'public'
    columns=[]
    for role,value in case['roles'].items():
        anchor=value['entry_bank_anchor']
        if anchor:columns.append((role+' bank anchor',anchor['frame']))
    columns.extend((('merge confirm',case['confirm']),('first split q',q),
        ('q+5 postseal',min(q+5,SEGMENTS[segment][1]-SEGMENTS[segment][0]+1))))
    frames={frame for _,frame in columns}
    predictions={row['frame']:row for row in rows(public/'predictions.jsonl.gz') if row['frame'] in frames}
    assignments={row['frame']:row for row in rows(input_dir(segment)/'assignments.jsonl.gz') if row['frame'] in frames}
    packets={row['frame']:row for row in rows(public/'MIXED_DEPTH.jsonl.gz') if row['frame'] in frames}
    material={};sensor=RawDepth(segment)
    try:
        for frame in sorted(frames):
            row=predictions[frame];depth,index,native,binding=sensor(row['global_frame'],row['time']);binding['frame']=frame
            assert binding==packets[frame]['source_binding']
            material[frame]=(depth,native_masks(assignments[frame]))
    finally:sensor.close()
    valid=np.concatenate([d[np.isfinite(d)&(d>0)] for d,_ in material.values()])
    lo,hi=np.quantile(valid,[.02,.98]) if len(valid) else (0,1)
    shape=material[q][0].shape
    relevant={int(n) for n in case['actual_first_public_mapping']}
    relevant.update(int(n) for n in case['event_record']['member_sources'])
    if case['event_record']['group_source'] is not None:relevant.add(int(case['event_record']['group_source']))
    relevant.update(v['entry_bank_anchor']['native_id'] for v in case['roles'].values() if v['entry_bank_anchor'])
    region=np.zeros(shape,dtype=bool)
    for depth,masks in material.values():
        for native in relevant:
            if native in masks:region|=masks[native]
    ys,xs=np.where(region)
    roi=[max(0,int(xs.min())-24),max(0,int(ys.min())-24),min(shape[1],int(xs.max())+25),
         min(shape[0],int(ys.max())+25)] if len(xs) else [0,0,shape[1],shape[0]]
    out=HERE/'private/unrestored_control_visuals';out.mkdir(parents=True,exist_ok=True);inventory=[]
    for scope,bounds in (('FULL',[0,0,shape[1],shape[0]]),('ROI',roi)):
        x0,y0,x1,y1=bounds
        # Six rows are the six actual state branches; columns are causal/postseal snapshots.
        fig,axes=plt.subplots(len(ARMS),len(columns),figsize=(4*len(columns),18),squeeze=False)
        for j,(label,frame) in enumerate(columns):
            row=predictions[frame];depth,masks=material[frame]
            for i,arm in enumerate(ARMS):
                ax=axes[i,j];crop=depth[y0:y1,x0:x1]
                ax.imshow(np.where(crop>0,crop,np.nan),cmap='viridis',vmin=lo,vmax=hi)
                mapping={int(obj['mask'][2:]):obj['id'] for obj in row['variants'][arm]}
                for native,mask in masks.items():
                    local=mask[y0:y1,x0:x1]
                    if not local.any():continue
                    ax.contour(local,levels=[.5],colors='white',linewidths=.7)
                    yy,xx=np.where(local);ax.text(xx.mean(),yy.mean(),f'n{native}:p{mapping[native]}',
                        fontsize=8 if scope=='ROI' else 6,color='red',bbox=dict(facecolor='white',alpha=.7,pad=.3))
                ax.set_title(f'{arm}\n{label} actual F{row["global_frame"]}',fontsize=9);ax.axis('off')
        fig.suptitle(f'{segment}/{case["event"]}: UNRESTORED H0/FALLBACK CONTROL; not a failed joint COMMIT; actual raw depth / published IDs',fontsize=12)
        fig.tight_layout(rect=(0,0,1,.97));file=out/f'{segment}_{case["event"]}_{scope}.png'
        assert not file.exists();fig.savefig(file,dpi=125);plt.close(fig)
        inventory.append(dict(dataset=case['dataset'],segment=segment,event=case['event'],scope=scope,
            artifact=artifact(file),selection='Earliest genuine H0/fallback q, not WRONG joint restore',
            displayed_columns=[dict(role=label,frame=frame,global_frame=predictions[frame]['global_frame']) for label,frame in columns],
            ROI=dict(xyxy=bounds,full_shape=list(shape),native_mask_union_sources=sorted(relevant),padding_px=24,
                transform='crop(x,y)=(full_x-x0,full_y-y0)',selection_uses_GT=False),
            depth_scale_mm=[float(lo),float(hi)],common_color_scale=True,
            all_visible_neighbor_masks_and_fragments_retained=True,
            source_bindings=[packets[frame]['source_binding'] for frame in sorted(frames)],
            future_panels_postseal_diagnosis_only=True,RGB=False,GT_raster=False))
    return inventory


def main():
    metric=require_complete()
    assert not (HERE/'ORDER_COVERAGE.json').exists(),'Do not overwrite completed postscore interpretation'
    summary,selected,facts,sources,deltas=summarize(metric)
    cases=[dict(inspect_case(item),control_kind='UNRESTORED_H0_FALLBACK_NOT_FAILED_COMMIT')
           for item in selected.values() if item is not None]
    install_pixel_guard()
    pictures=[picture for case in cases for picture in visualize_control(case)]
    write_new(HERE/'PRIVATE_UNRESTORED_CONTROL_VISUALS.json',dict(status='POSTSCORE_UNRESTORED_CONTROLS',
        figures=pictures,private_pixels=True,new_prediction=False,RGB=False,GT_raster=False,
        postscore_script=artifact(__file__)))
    write_new(HERE/'ORDER_COVERAGE.json',dict(status='POSTSCORE_SEALED_ORDINAL_DESCRIPTION',
        arm=ARM,dataset_counts=summary,decision_rows=facts,MIXED_RETURN_minus_ACTIVITY_RETURN=deltas,
        scientific_sources=sources,metric_source=artifact(RUN/'METRICS.json'),postscore_script=artifact(__file__),
        weak_band=[.1,.9],weak_band_is_uncalibrated_description_not_decision_rule=True,
        no_new_candidate_choice_counterfactual_or_threshold=True,order_choice_effect_without_explicit_field='UNKNOWN',
        common_local_return_benefit_is_not_unique_depth_gain=True,new_model_http=0,cost_usd=0))
    write_new(HERE/'UNRESTORED_CONTROLS.json',dict(status='POSTSCORE_CONTROL_DESCRIPTION_NOT_FAILED_COMMIT',
        selection='Earliest original-frame MIXED_RETURN H0/fallback q per fixed dataset; Feeding pooled',
        cases=cases,private_visual_inventory=artifact(HERE/'PRIVATE_UNRESTORED_CONTROL_VISUALS.json'),
        no_new_prediction_choice_counterfactual_or_test=True,postscore_script=artifact(__file__)))
    lines=['# DS19 ordinal 覆盖与未恢复控制','',
        '这是封存后的既有 H0/fallback 诊断，不是错误 joint 提交或新测试。原失败选择为 0 案例/0 图；本控制另按每个 dataset 最早原帧 q 选择，不挑最好或最坏。','',
        '| 数据 | q决策 | ordinal可用 | p缺失 | weak代理 | order原因 |',
        '|---|---:|---:|---:|---:|---|']
    for name,unit in summary.items():
        lines.append(f'| {name} | {unit["split_decisions"]} | {unit["order_eligible"]} | {unit["missing_p"]} | {unit["weak_uncalibrated_proxy"]} | {unit["order_reasons"]} |')
    lines+=['','## 相同 return 底座的实际差值','',
        '下面仅为完整真实状态结果的 MIXED_RETURN−ACTIVITY_RETURN，公共局部 return 的止损不算深度独有增益。','',
        '| 数据 | ΔIDF1 | ΔHOTA | ΔAssA | ΔIDSW | ΔFP | ΔFN |','|---|---:|---:|---:|---:|---:|---:|']
    for name,delta in deltas.items():lines.append('| '+name+' | '+' | '.join(str(delta[f]) for f in ('IDF1','HOTA','AssA','IDSW','FP','FN'))+' |')
    for case in cases:
        evidence=case['order']
        lines+=['','## '+case['segment']+'/'+case['event'],'',
            f'未恢复控制，原帧 q={case["global_q"]}，实际 H0；bank 提交判定={case["bank_physical"]}，首帧 clean={case["clean_endpoint_physical"]}，提交 pre-consensus={case["pre_consensus_physical"]}。未提交不能称正确或错误 joint 恢复。',
            f'原封存 order={evidence["status"]}/{evidence["reason"]}，p(A更近)={evidence["p_A_nearer_at_q"]}；实际 best={evidence["actual_sealed_best"]}，margin={evidence["margin"]}，min log-odds={evidence["minimum_log_odds"]}，决策原因={evidence["actual_sealed_reason"]}；choice 影响={evidence["order_changed_choice"]}。',
            'whole/birth_core/core 的实际 fact、layer、来源、quality、geometry/depth 原因及 bank/公共来源/片段共识关系见公共数字 JSON；不重新计算候选或门槛。']
        for role,value in case['roles'].items():lines.append(f'{role}: bank/public origin={value["bank_vs_public_origin"]}；进入前公共ID误号={value["preexisting_public_error"]}；clean/public origin={value["clean_vs_public_origin"]}。')
    lines+=['','已生成 '+str(len(pictures))+' 张真实深度/原mask/已发布ID控制图（全景与ROI），仅在 private/unrestored_control_visuals。所有邻鱼和残片保留，q+5仅封存后诊断。真实路径、字节数、SHA及来源绑定见 PRIVATE_UNRESTORED_CONTROL_VISUALS.json。',
        '顺序 p 和宽尺度均为未校准代理，不等于物理准确率或已证明上下不变；UNKNOWN 不算成功。新增推理 HTTP=0、费用=0。','']
    with (HERE/'ORDER_COVERAGE.md').open('x',encoding='utf-8',newline='\n') as f:f.write('\n'.join(lines))
    print('Postscore H0 controls complete; q decisions',sum(x['split_decisions'] for x in summary.values()),
          'ordinal eligible',sum(x['order_eligible'] for x in summary.values()),
          'missing p',sum(x['missing_p'] for x in summary.values()),
          'selected controls',len(cases),'private figures',len(pictures))


if __name__=='__main__':main()
