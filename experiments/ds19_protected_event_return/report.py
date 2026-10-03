"""Postscore numeric report and private actual-depth publication panels; never GT raster."""
from common import *
from collections import Counter

FIELDS=('IDF1','HOTA','AssA','IDSW','FP','FN')
PAIRS=(('ACTIVITY_RETURN','ACTIVITY_ORDER'),('MIXED_RETURN','MIXED_ORDER'),
       ('MIXED_RETURN','ACTIVITY_RETURN'))


def require_complete():
    # This gate precedes every score or GT-derived scalar read.
    for filename in ('ALL_PREDICTIONS_SEALED.json','SCORE_PROVENANCE.json','METRICS.json'):
        assert (RUN/filename).exists(), 'Complete all seals and scoring before report/visualization'
    sealed=read(RUN/'ALL_PREDICTIONS_SEALED.json')
    assert sealed['status']=='ALL_PREDICTIONS_AND_ACCESS_SEALED'
    assert sealed['frames']==sum(b-a+1 for a,b in SEGMENTS.values())==20098
    assert tuple(sealed['arms'])==ARMS and set(sealed['seals'])==set(SEGMENTS)
    for name,item in sealed['seals'].items():
        verify_item(item)
        seal=read(item['path'])
        for filename,digest in seal['artifacts_sha256'].items():
            assert sha(RUN/name/'public'/filename)==digest,(name,filename)
    provenance=read(RUN/'SCORE_PROVENANCE.json')
    assert provenance['reference_opened_after_all_seals'] and provenance['scientific_source_and_runtime_verified']
    metric=read(RUN/'METRICS.json')
    assert metric['status']=='SCORED_AFTER_ALL_FOUR_EVENT_ARMS_AND_CONTROLS_EIGHT_SEALS'
    assert metric['all_seal']==artifact(RUN/'ALL_PREDICTIONS_SEALED.json')
    assert metric['new_model_http']==metric['cost_usd']==0
    return metric


def metric_units(metric):
    result={'Feeding_pooled1471':metric['feeding_pooled']}
    result.update({name:metric['segments'][name] for name in
        ('fishsa_development_8400','fishsa_validation_2888','L3','LW')})
    return result


def differences(summary):
    pairs=PAIRS+tuple((arm,base) for base in ('SAM3_NATIVE','Z4Q_FROZEN') for arm in EVENT_ARMS)
    return {f'{arm}_minus_{base}':{field:summary[arm][field]-summary[base][field] for field in FIELDS}
            for arm,base in pairs}


def switch_difference(switches,arm,base):
    actual={(x['gt_id'],x['frame']):x for x in switches[arm]}
    old={(x['gt_id'],x['frame']):x for x in switches[base]}
    assert len(actual)==len(switches[arm]) and len(old)==len(switches[base])
    order=lambda key:(key[1],str(key[0]))
    return dict(arm=arm,base=base,added=len(actual.keys()-old.keys()),removed=len(old.keys()-actual.keys()),
        net=len(actual)-len(old),added_switches=[actual[k] for k in sorted(actual.keys()-old.keys(),key=order)],
        removed_switches=[old[k] for k in sorted(old.keys()-actual.keys(),key=order)],
        common_transition_changed=[dict(gt_id=k[0],frame=k[1],arm=actual[k],base=old[k])
            for k in sorted(actual.keys()&old.keys(),key=order) if
            (actual[k]['from_public_id'],actual[k]['to_public_id'])!=(old[k]['from_public_id'],old[k]['to_public_id'])])


def create_summary(metric):
    units=metric_units(metric)
    summary={name:dict(frames=unit['frames'],metrics=unit['metrics'],deltas=differences(unit['metrics']))
             for name,unit in units.items()}
    segments={};sources=[artifact(RUN/f) for f in ('ALL_PREDICTIONS_SEALED.json','METRICS.json','SCORE_PROVENANCE.json')]
    all_returns=[]
    for name in SEGMENTS:
        public=RUN/name/'public';events=read(public/'EVENTS.json');switches=read(public/'SWITCHES.json')
        local=read(public/'LOCAL_RETURN_AUDIT.json')
        all_returns.extend(item for arm in RETURN_ARMS for item in local['arms'][arm])
        attempts={arm:Counter() for arm in RETURN_ARMS};commits={arm:[] for arm in RETURN_ARMS}
        for transaction in rows(public/'TRANSACTIONS.jsonl.gz'):
            arm=transaction['arm'];stage=transaction.get('local_return_stage')
            if stage:
                attempts[arm][stage['stage_error'] or 'STAGED']+=1
            if transaction.get('return_record'):
                commits[arm].append(transaction['return_record'])
        event_summary={}
        for arm in EVENT_ARMS:
            order_rows=[row for row in rows(public/'ORDER_EVIDENCE.jsonl.gz') if row['arm']==arm]
            event_summary[arm]=dict(events=len(events[arm]),split_decisions=len(order_rows),
                no_split=sum(event['q'] is None for event in events[arm]),
                statuses=dict(Counter(event['status'] for event in events[arm])),
                S0_choices=dict(Counter(row['selected_choice'] for row in order_rows)),
                order_evidence_status=dict(Counter((row['detail'].get('order_evidence') or {}).get('status','ABSENT') for row in order_rows)),
                joint_waits=[dict(event=e['id'],suspect=e['suspect_frame'],confirm=e['confirm_frame'],q=e['q'],end=e['end'],status=e['status'],
                    local_returns=e.get('local_returns'),returned_members=e.get('returned_members')) for e in events[arm]])
        metrics=metric['segments'][name]['metrics']
        segments[name]=dict(frames=metric['segments'][name]['frames'],metrics=metrics,deltas=differences(metrics),
            reference_status=metric['segments'][name]['reference_status'],events=event_summary,
            stage_attempts={arm:dict(value) for arm,value in attempts.items()},committed_transactions=commits,
            local_return_audit=local,switch_comparisons=[switch_difference(switches,arm,base)
                for arm,base in PAIRS+tuple((arm,base) for base in ('SAM3_NATIVE','Z4Q_FROZEN') for arm in RETURN_ARMS)])
        for filename in ('METRICS.json','SWITCHES.json','EVENT_AUDIT.json','AUTOMATIC_RECONNECT_AUDIT.json','LOCAL_RETURN_AUDIT.json'):
            sources.append(artifact(public/filename))
    result=dict(status='COMPLETE_POSTSCORE_CAUSAL_REPORT_NO_AUTOMATIC_NEXT_TRIAL',frames_per_arm=20098,
        units=summary,segments=segments,local_return_cases=all_returns,sources=sources,
        mechanisms=dict(return_effect='Each RETURN minus its matching frozen control: shared event-local transaction effect',
            repaired_depth_effect='MIXED_RETURN minus ACTIVITY_RETURN: unchanged composite depth qualification/order policy on repaired own-state branches',
            original_Z4Q_gain_recovery='LOSS_PREVENTION; NOT_NEW_DEPTH_GAIN',
            downstream_branches='After any commit, later history/candidate/input can diverge; full-run differences are policy effects, not identical local inputs'),
        boundaries=['No physical depth-surface truth is supplied by identity GT',
            'Bank physical recovery and already-wrong public origin are separate; UNKNOWN is not correct',
            'Reused exposed cohorts, not independent generalization; L3/LW weak prediction-derived preannotation',
            'No new RGB, GT raster, model HTTP, SAM3 inference, completion service or training',
            'All frame publication is immutable; future panels are postseal diagnosis only'],
        model_http=0,cost_usd=0)
    write_new(RUN/'POSTSCORE_SUMMARY.json',result)
    lines=['# DS19 完整结果与因果分层','',
        '四个事件状态分支与同源SAM3/原Z4Q两列参照，各20098帧；所有预测封存后评分。新增模型HTTP、费用均为0。','',
        '恢复原Z4Q收益只称止损。两对RETURN开关量化共同事务效果；修复后的MIXED−ACTIVITY才是当前组合深度政策差值。分支后续状态可能不同，不能把完整差值写成同一局部输入的深度准确率。','']
    for name,unit in summary.items():
        lines+=['## '+name,'','| 分支 | IDF1 | HOTA | AssA | IDSW | FP | FN |','|---|---:|---:|---:|---:|---:|---:|']
        for arm in ARMS:
            values=unit['metrics'][arm]
            lines.append('| '+arm+' | '+' | '.join(f'{values[field]:.6f}' if field in FIELDS[:3] else str(values[field]) for field in FIELDS)+' |')
        lines+=['','| 差值 | IDF1 | HOTA | AssA | IDSW | FP | FN |','|---|---:|---:|---:|---:|---:|---:|']
        for label,values in unit['deltas'].items():
            lines.append('| '+label+' | '+' | '.join(f'{values[field]:+.6f}' if field in FIELDS[:3] else f'{values[field]:+}' for field in FIELDS)+' |')
        lines+=['']
    lines+=['## 实际局部重接逐例','',
        '| 数据/分支 | 原帧 | 来源→公开ID | 原规则 | bank物理 | 原公共ID来源 | 联合保守判定 | 从首次来源发布到重接/帧 |',
        '|---|---:|---|---|---|---|---|---:|']
    for item in all_returns:
        lines.append(f'| {item["segment"]}/{item["arm"]} | {item["global_frame"]} | {item["source"]}→{item["target"]} | {item["origin_rule"]} | {item["actual_reference_physical"]} | {item["prior_public_reference_status"]} | {item["physical"]} | {item["return_delay_since_first_source_frames"]} |')
    if not all_returns:lines+=['| 全部 | — | 无实际提交 | — | — | — | — | — |']
    lines+=['','八片段全部指标、逐次新增/消除切换、q/等待/超时、失败门槛、不可评分与实际事务见POSTSCORE_SUMMARY.json。',
        '公共图仅含聚合数值；真实深度/mask发布对照保存在private/visuals，列真实路径/字节/SHA。',
        '本脚本不选择下一机制、不按结果修改冻结参数。','']
    with (HERE/'RESULTS.md').open('x',encoding='utf-8',newline='\n') as f:f.write('\n'.join(lines))
    return result


def create_metric_plot(metric):
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    units=metric_units(metric);names=list(units);x=np.arange(len(names))
    labels=('Feeding1471','Dev8400','Val2888','L3','LW')
    fig,axes=plt.subplots(3,2,figsize=(15,12))
    for ax,field in zip(axes.ravel(),FIELDS):
        for i,(arm,base) in enumerate(PAIRS):
            ax.bar(x+(i-1)*.24,[units[name]['metrics'][arm][field]-units[name]['metrics'][base][field] for name in names],
                width=.23,label=f'{arm} minus {base}')
        ax.axhline(0,color='black',lw=.7);ax.set_title(field+' actual change')
        ax.set_xticks(x,labels,rotation=0,fontsize=9);ax.grid(axis='y',alpha=.2)
        ax.set_ylabel('percentage points' if field in FIELDS[:3] else 'count')
    handles,labels=axes[0,0].get_legend_handles_labels();fig.legend(handles,labels,loc='lower center',ncol=1,fontsize=9)
    fig.suptitle('DS19: frozen depth, event-local return; reused cohorts / L3-LW weak labels',fontsize=13)
    fig.tight_layout(rect=(0,.085,1,.96))
    files=[HERE/'METRIC_COMPARISON.png',HERE/'METRIC_COMPARISON.svg']
    for file in files:
        assert not file.exists();fig.savefig(file,dpi=150)
    plt.close(fig)
    write_new(HERE/'PUBLIC_PLOTS.json',dict(status='AGGREGATE_NUMERIC_ONLY_NO_PRIVATE_PIXELS',
        figures=[artifact(file) for file in files],metric_source=artifact(RUN/'METRICS.json')))


def create_actual_visuals(summary):
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from source import RawDepth,native_masks
    # Fixed source-diagnostic L3 case plus the chronological first actual return
    # of each segment/arm. No outcome-based replacement or best-case selection.
    cases={('L3',3025):dict(reason='PREDECLARED_DS18_PROTECTED_TARGET_DEAD_END',cases=[])}
    for name in SEGMENTS:
        for arm in RETURN_ARMS:
            records=summary['segments'][name]['local_return_audit']['arms'][arm]
            if records:
                item=min(records,key=lambda x:(x['frame'],x['source']))
                case=cases.setdefault((name,item['frame']),dict(reason='FIRST_ACTUAL_LOCAL_RETURN_CHRONOLOGICALLY',cases=[]))
                case['cases'].append(item)
    out=HERE/'private/visuals';out.mkdir(parents=True,exist_ok=True);inventory=[]
    for (name,query),case in cases.items():
        last=SEGMENTS[name][1]-SEGMENTS[name][0]+1
        frames=sorted(set((max(1,query-5),query,min(last,query+5))))
        public=RUN/name/'public'
        pred={x['frame']:x for x in rows(public/'predictions.jsonl.gz') if x['frame'] in frames}
        assignments={x['frame']:x for x in rows(input_dir(name)/'assignments.jsonl.gz') if x['frame'] in frames}
        certs={x['frame']:x for x in rows(public/'MIXED_DEPTH.jsonl.gz') if x['frame'] in frames}
        sensor=RawDepth(name);material={}
        try:
            for frame in frames:
                row=pred[frame];depth,index,native,binding=sensor(row['global_frame'],row['time'])
                binding['frame']=frame
                assert binding==certs[frame]['source_binding']
                material[frame]=(depth,native_masks(assignments[frame]))
        finally:sensor.close()
        values=np.concatenate([depth[np.isfinite(depth)&(depth>0)] for depth,_ in material.values()])
        lo,hi=np.quantile(values,[.02,.98]) if len(values) else (0,1)
        fig,axes=plt.subplots(len(ARMS),len(frames),figsize=(15,15),squeeze=False)
        for j,frame in enumerate(frames):
            row=pred[frame];depth,masks=material[frame]
            for i,arm in enumerate(ARMS):
                ax=axes[i,j];ax.imshow(np.where(depth>0,depth,np.nan),cmap='viridis',vmin=lo,vmax=hi)
                mapping={int(x['mask'][2:]):x['id'] for x in row['variants'][arm]}
                for native,mask in masks.items():
                    ax.contour(mask,levels=[.5],colors='white',linewidths=.35)
                    ys,xs=np.where(mask)
                    if len(xs):ax.text(xs.mean(),ys.mean(),f'n{native}:p{mapping[native]}',fontsize=6,color='red',
                        bbox=dict(facecolor='white',alpha=.6,pad=.2))
                ax.set_title(f'{arm} / actual F{row["global_frame"]}',fontsize=9);ax.axis('off')
        fig.suptitle(f'{name} local{query}: {case["reason"]}; actual depth/masks, no RGB or GT raster; future panel postseal only',fontsize=10)
        fig.tight_layout(rect=(0,0,1,.97));file=out/f'{name}_frame{query}_actual_publication.png'
        assert not file.exists();fig.savefig(file,dpi=130);plt.close(fig)
        inventory.append(dict(segment=name,local_frame=query,reason=case['reason'],case_rows=case['cases'],
            artifact=artifact(file),frames=frames,actual_source_bindings=[certs[frame]['source_binding'] for frame in frames],
            depth_scale_mm=[float(lo),float(hi)],common_color_scale_across_frames_and_branches=True))
        sources={item['source'] for item in case['cases']}
        targets={item['target'] for item in case['cases']}
        sources.update(item['actual_old_anchor']['native_id'] for item in case['cases'])
        if name=='L3' and query==3025:sources.update((47,6))
        # Actual observed source and actual public target owners only. This is
        # postscore viewing, and never changes the source, candidate or q.
        for frame in frames:
            for arm in ARMS:
                sources.update(int(item['mask'][2:]) for item in pred[frame]['variants'][arm] if item['id'] in targets)
        shape=material[query][0].shape
        region=np.zeros(shape,dtype=bool)
        for _,masks in material.values():
            for native in sources:
                if native in masks:region|=masks[native]
        ys,xs=np.where(region)
        if len(xs):
            y0,y1=max(0,int(ys.min())-24),min(shape[0],int(ys.max())+25)
            x0,x1=max(0,int(xs.min())-24),min(shape[1],int(xs.max())+25)
            roi_status='ACTUAL_SOURCE_TARGET_MASK_UNION_WITH_FIXED_24PX_PADDING'
        else:
            x0,y0,x1,y1=0,0,shape[1],shape[0];roi_status='NO_VISIBLE_CASE_MASK_FULL_FRAME_FALLBACK'
        roi=dict(status=roi_status,xyxy=[x0,y0,x1,y1],full_shape=list(shape),
            selected_native_sources=sorted(sources),public_targets=sorted(targets),
            transform='crop(x,y)=(full_x-x0,full_y-y0); no resampling of numeric depth',GT_selection=False)
        fig,axes=plt.subplots(len(ARMS),len(frames),figsize=(15,15),squeeze=False)
        for j,frame in enumerate(frames):
            row=pred[frame];depth,masks=material[frame]
            for i,arm in enumerate(ARMS):
                ax=axes[i,j];ax.imshow(np.where(depth[y0:y1,x0:x1]>0,depth[y0:y1,x0:x1],np.nan),
                    cmap='viridis',vmin=lo,vmax=hi)
                mapping={int(item['mask'][2:]):item['id'] for item in row['variants'][arm]}
                for native,mask in masks.items():
                    cropped=mask[y0:y1,x0:x1]
                    if not cropped.any():continue
                    ax.contour(cropped,levels=[.5],colors='white',linewidths=.7)
                    ys,xs=np.where(cropped)
                    ax.text(xs.mean(),ys.mean(),f'n{native}:p{mapping[native]}',fontsize=9,color='red',
                        bbox=dict(facecolor='white',alpha=.7,pad=.3))
                ax.set_title(f'{arm} / actual F{row["global_frame"]}',fontsize=10);ax.axis('off')
        fig.suptitle(f'{name} local{query}: actual mask-defined ROI {roi["xyxy"]}; all visible local masks retained / no RGB or GT raster',fontsize=11)
        fig.tight_layout(rect=(0,0,1,.97));file=out/f'{name}_frame{query}_actual_publication_ROI.png'
        assert not file.exists();fig.savefig(file,dpi=130);plt.close(fig)
        inventory.append(dict(segment=name,local_frame=query,reason=case['reason'],artifact=artifact(file),frames=frames,
            ROI=roi,depth_scale_mm=[float(lo),float(hi)],common_color_scale_with_full_panels=True,
            postseal_future_diagnosis_only=True))
    write_new(HERE/'PRIVATE_VISUALS.json',dict(status='ACTUAL_POSTSCORE_PUBLISHED_MAPPINGS',figures=inventory,
        deterministic_case_selection=True,private_pixels=True,GT_raster=False,RGB=False,
        postseal_future_diagnosis_only=True,not_model_input=True))


def main():
    metric=require_complete()
    assert not (RUN/'POSTSCORE_SUMMARY.json').exists(),'Never overwrite a completed report'
    summary=create_summary(metric)
    create_metric_plot(metric)
    create_actual_visuals(summary)
    print('DS19 postscore numeric report and actual-depth private figures complete')


if __name__=='__main__':main()
