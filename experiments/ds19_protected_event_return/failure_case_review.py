"""Postscore-only DS19 joint-failure explanation; no new prediction or counterfactual."""
from common import *
from collections import Counter
import copy, math

ARM='MIXED_RETURN'
DATASETS=('Feeding','fishsa_development_8400','fishsa_validation_2888','L3','LW')


def dataset(segment):
    return 'Feeding' if segment.startswith('feeding_') else segment


def same(left,right):
    if left.get('status')!='UNIQUE_IOU_MATCH' or right.get('status')!='UNIQUE_IOU_MATCH':return 'UNKNOWN'
    return 'SAME' if left['gt_id']==right['gt_id'] else 'DIFFERENT'


def require_complete():
    # All three files must exist before any GT-derived scalar audit is opened.
    from report import require_complete as gate
    metric=gate()
    for segment in SEGMENTS:
        public=RUN/segment/'public'
        audit=read(public/'EVENT_AUDIT.json')
        assert audit['arms']==metric['event_audits'][segment]
        assert read(public/'METRICS.json')==metric['segments'][segment]
    return metric


def genuine_joint_commit(event):
    restore=event.get('restore') or {}
    return (restore.get('status')=='COMMIT' and restore.get('decision_source')==ARM and
        restore.get('stage_error') is None and restore.get('selected_choice') in ('H1','H2') and
        restore.get('mapping') is not None and bool(restore.get('changes')))


def summarize_and_select(metric):
    summary={name:dict(events=0,split_q=0,no_split=0,joint_COMMIT=0,joint_resolve_no_ID_change=0,
        bank_physical_counts=Counter(),pre_consensus_counts=Counter(),H0=0,fallback=0,
        no_failed_COMMIT_means_correct=False) for name in DATASETS}
    candidates={name:[] for name in DATASETS};sources=[]
    for segment in SEGMENTS:
        public=RUN/segment/'public';unit=summary[dataset(segment)]
        events=read(public/'EVENTS.json')[ARM]
        audits={row['event']:row for row in read(public/'EVENT_AUDIT.json')['arms'][ARM]['group_events']}
        assert len(audits)==len(events)
        unit['events']+=len(events)
        for event in events:
            grade=audits[event['id']];restore=event.get('restore') or {}
            if event['q'] is None:
                unit['no_split']+=1;continue
            unit['split_q']+=1
            unit['H0']+=restore.get('selected_choice')=='H0'
            unit['fallback']+=restore.get('fallback') is not None or restore.get('decision_source')=='OWN_BRANCH_LOCAL_FALLBACK'
            unit['joint_resolve_no_ID_change']+=restore.get('status')=='RESOLVE_NO_ID_CHANGE'
            if genuine_joint_commit(event):
                unit['joint_COMMIT']+=1
                unit['bank_physical_counts'][grade['physical']]+=1
                unit['pre_consensus_counts'][grade['committed_pre_consensus_verdict']]+=1
                if grade['physical'] in ('WRONG','UNSCORABLE'):
                    candidates[dataset(segment)].append(dict(segment=segment,event=event,audit=grade,
                        global_q=SEGMENTS[segment][0]+event['q']-1))
        sources.extend(artifact(public/file) for file in ('EVENTS.json','EVENT_AUDIT.json','ORDER_EVIDENCE.jsonl.gz'))
    selected={}
    for name in DATASETS:
        choices=sorted(candidates[name],key=lambda row:(row['global_q'],row['segment'],row['event']['id']))
        selected[name]=choices[0] if choices else None
        summary[name]['eligible_failed_committed_joint_restores']=len(choices)
        summary[name]['selection_status']='EARLIEST_FAILED_COMMITTED_JOINT_RESTORE' if choices else 'NO_FAILED_COMMITTED_JOINT_RESTORE_OBSERVED'
        summary[name]['bank_physical_counts']=dict(summary[name]['bank_physical_counts'])
        summary[name]['pre_consensus_counts']=dict(summary[name]['pre_consensus_counts'])
    return summary,selected,sources


def order_summary(detail):
    evidence=detail.get('order_evidence') or {}
    probability=evidence.get('p_A_nearer_at_q')
    finite=isinstance(probability,(int,float)) and math.isfinite(probability)
    strength=('UNKNOWN' if evidence.get('status')=='UNKNOWN' or not finite else
        'WEAK_UNCALIBRATED_PROXY' if .1<probability<.9 else 'OUTSIDE_WEAK_BAND_UNCALIBRATED_PROXY')
    candidates={label:dict(mapping=value['mapping'],posterior=value.get('posterior'),
        log_prior=value.get('log_prior'),geometry_log_lr=value.get('geometry_log_lr'),
        order_log_lr=value.get('order_log_lr'),log_score=value.get('log_score'),order=value.get('order'))
        for label,value in detail.get('candidates',{}).items()}
    changed={key:detail[key] for key in ('order_changed_choice','order_effect_on_choice','choice_changed_by_order') if key in detail}
    return dict(status=evidence.get('status','ABSENT'),reason=evidence.get('reason'),eligible=evidence.get('eligible'),
        order_enabled=detail.get('order_enabled'),actual_sealed_best=detail.get('best'),
        actual_sealed_reason=detail.get('reason'),margin=detail.get('margin'),minimum_log_odds=detail.get('minimum_log_odds'),
        descriptive_strength=strength,weak_band=[.1,.9],weak_band_is_analysis_only_not_a_decision_rule=True,
        p_A_nearer_at_q=probability,explicit_choice_effect_fields=changed,
        order_changed_choice=changed if changed else 'UNKNOWN_NO_EXPLICIT_SEALED_FIELD',
        no_new_choice_computation_or_counterfactual=True,candidates=candidates,evidence=evidence,
        physical_depth_order_truth='UNKNOWN')


def inspect_case(item):
    segment,event,grade=item['segment'],item['event'],item['audit'];public=RUN/segment/'public';q=event['q']
    order=next(row for row in rows(public/'ORDER_EVIDENCE.jsonl.gz') if row['arm']==ARM and row['frame']==q)
    assert order['event']==event['id'] and order['detail']==event['numeric']['detail'] and order['restore']==event['restore']
    predictions={};first_seen={}
    for row in rows(public/'predictions.jsonl.gz'):
        if row['frame']==q:predictions[q]=row
        for obj in row['variants']['SAM3_NATIVE']:first_seen.setdefault(int(obj['mask'][2:]),row['frame'])
    references={row['frame']:row['matches'] for row in rows(public/'REFERENCE_MATCHES.jsonl.gz')}
    def match(frame,native):
        if frame is None:return dict(status='SOURCE_OR_REFERENCE_MISSING')
        return references.get(frame,{}).get(str(native),dict(status='SOURCE_OR_REFERENCE_MISSING'))
    roles={}
    for role,target in zip(('A','B'),event['public_ids'],strict=True):
        anchor=event['reference_anchors'].get(str(target))
        history=event['pre_geometry_history'].get(role,[])
        clean=history[-1] if history else None
        origin_frame=first_seen.get(target)
        origin=match(origin_frame,target) if origin_frame is not None and origin_frame<=q else dict(status='NO_CAUSAL_NATIVE_ORIGIN_REFERENCE')
        bank=match(anchor['frame'],anchor['native_id']) if anchor else dict(status='MISSING_BANK_ANCHOR')
        endpoint=match(clean['frame'],clean['source']) if clean else dict(status='MISSING_CLEAN_FRAGMENT')
        roles[role]=dict(public_target=target,entry_bank_anchor=anchor,clean_fragment_endpoint=clean,
            native_public_origin_frame=origin_frame,bank_match=bank,clean_endpoint_match=endpoint,native_origin_match=origin,
            bank_vs_public_origin=same(bank,origin),clean_vs_public_origin=same(endpoint,origin),
            preexisting_public_error=('YES' if same(bank,origin)=='DIFFERENT' else 'NO_MATCHED_BANK_ORIGIN_CONFLICT' if same(bank,origin)=='SAME' else 'UNKNOWN'),
            depth_history_endpoint=(event.get('depth_frozen',{}).get(role,{}).get('samples') or [None])[-1],
            fragment_consensus=grade.get('pre_consensus_support',{}).get(role))
    packet=next(row for row in rows(public/'MIXED_DEPTH.jsonl.gz') if row['frame']==q)
    core={}
    for native in event['post_first_observations']:
        cert=packet['objects'][native]
        core[native]={view:{key:copy.deepcopy(cert[view].get(key)) for key in ('status','eligible_single','mixture_flag',
            'quality_usable','source_ownership_exclusive','inclusive_summary','summary','layers')}
            for view in ('whole','birth_core','core')}
    actual={int(obj['mask'][2:]):obj['id'] for obj in predictions[q]['variants'][ARM]
            if int(obj['mask'][2:]) in {int(n) for n in event['post_first_observations']}}
    assert actual=={int(n):k for n,k in grade['actual_first_public_mapping'].items()}
    return dict(dataset=dataset(segment),segment=segment,event=event['id'],arm=ARM,
        suspect=event['suspect_frame'],confirm=event['confirm_frame'],q=q,global_q=item['global_q'],
        bank_physical=grade['physical'],clean_endpoint_physical=grade['first_public_clean_endpoint_verdict'],
        pre_consensus_physical=grade['committed_pre_consensus_verdict'],actual_first_public_mapping=actual,
        actual_choice=event['restore']['selected_choice'],roles=roles,order=order_summary(order['detail']),
        actual_current_depth=core,bank_and_public_origin_separate=True,UNKNOWN_not_correct=True,
        postseal_only=True,new_prediction=False,source_audit=artifact(public/'EVENT_AUDIT.json'),
        numeric_reference_matches=artifact(public/'REFERENCE_MATCHES.jsonl.gz'),event_record=event)


def install_pixel_guard():
    # GT-derived public scalar audit is allowed only after require_complete;
    # reference raster/RGB and network remain forbidden for these pictures.
    import sys
    blocked=('/labels_','/labels/','gt_grid','truth.jsonl','/rgb/','/rgb_original/','/rgb_640x360/','/color/')
    def check(event,args):
        if event=='socket.connect':raise RuntimeError('No service/model call in postscore review')
        if event=='open' and isinstance(args[0],(str,bytes,os.PathLike)):
            path=str(args[0]).replace('\\','/').lower()
            if any(token in path for token in blocked):raise RuntimeError('Forbidden raster/RGB read: '+path)
    sys.addaudithook(check)
    import numpy as np
    original=np.lib.npyio.NpzFile.__getitem__
    def npz_field(sensor,key):
        assert key in ('depth_mm','source_index'),'No instance/annotation/RGB NPZ field'
        return original(sensor,key)
    np.lib.npyio.NpzFile.__getitem__=npz_field
    import h5py
    original_h5=h5py.Group.__getitem__
    allowed={'/frame_id','/aligned/raw_depth_mm','/aligned/raw_source_index','/native/original_depth_mm'}
    def h5_field(group,key):
        assert isinstance(key,str)
        absolute=key if key.startswith('/') else group.name.rstrip('/')+'/'+key
        assert absolute in allowed,'No instance/annotation/RGB HDF5 field'
        return original_h5(group,key)
    h5py.Group.__getitem__=h5_field


def visualize(case):
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from source import RawDepth,native_masks
    segment,q=case['segment'],case['q'];public=RUN/segment/'public'
    columns=[]
    for role,facts in case['roles'].items():
        anchor=facts['entry_bank_anchor']
        if anchor:columns.append((f'{role} bank anchor',anchor['frame']))
    columns.extend((('merge confirm',case['confirm']),('first split q',q),('q+5 postseal',min(q+5,SEGMENTS[segment][1]-SEGMENTS[segment][0]+1))))
    frames={frame for _,frame in columns}
    predictions={row['frame']:row for row in rows(public/'predictions.jsonl.gz') if row['frame'] in frames}
    assignments={row['frame']:row for row in rows(input_dir(segment)/'assignments.jsonl.gz') if row['frame'] in frames}
    packets={row['frame']:row for row in rows(public/'MIXED_DEPTH.jsonl.gz') if row['frame'] in frames}
    material={};sensor=RawDepth(segment)
    try:
        for frame in frames:
            row=predictions[frame];depth,index,native,binding=sensor(row['global_frame'],row['time']);binding['frame']=frame
            assert binding==packets[frame]['source_binding']
            material[frame]=(depth,native_masks(assignments[frame]))
    finally:sensor.close()
    valid=np.concatenate([depth[np.isfinite(depth)&(depth>0)] for depth,_ in material.values()])
    lo,hi=np.quantile(valid,[.02,.98]) if len(valid) else (0,1)
    out=HERE/'private/failure_visuals';out.mkdir(parents=True,exist_ok=True);inventory=[]
    relevant={int(n) for n in case['actual_first_public_mapping']}
    relevant.update(int(n) for n in case['event_record']['member_sources'])
    if case['event_record']['group_source'] is not None:relevant.add(int(case['event_record']['group_source']))
    relevant.update(facts['entry_bank_anchor']['native_id'] for facts in case['roles'].values() if facts['entry_bank_anchor'])
    shape=material[q][0].shape;region=np.zeros(shape,dtype=bool)
    for depth,masks in material.values():
        for native in relevant:
            if native in masks:region|=masks[native]
    ys,xs=np.where(region)
    roi=[max(0,int(xs.min())-24),max(0,int(ys.min())-24),min(shape[1],int(xs.max())+25),min(shape[0],int(ys.max())+25)] if len(xs) else [0,0,shape[1],shape[0]]
    for scope,bounds in (('FULL',[0,0,shape[1],shape[0]]),('ROI',roi)):
        x0,y0,x1,y1=bounds
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
                    yy,xx=np.where(local);ax.text(xx.mean(),yy.mean(),f'n{native}:p{mapping[native]}',fontsize=8 if scope=='ROI' else 6,
                        color='red',bbox=dict(facecolor='white',alpha=.7,pad=.3))
                ax.set_title(f'{arm}\n{label} actual F{row["global_frame"]}',fontsize=9);ax.axis('off')
        fig.suptitle(f'{segment}/{case["event"]}: MIXED_RETURN bank {case["bank_physical"]}, pre-consensus {case["pre_consensus_physical"]}; actual published IDs / no RGB or GT raster',fontsize=12)
        fig.tight_layout(rect=(0,0,1,.97));file=out/f'{segment}_{case["event"]}_{scope}.png'
        assert not file.exists();fig.savefig(file,dpi=125);plt.close(fig)
        inventory.append(dict(segment=segment,event=case['event'],scope=scope,artifact=artifact(file),
            displayed_columns=[dict(role=label,frame=frame,global_frame=predictions[frame]['global_frame']) for label,frame in columns],
            ROI=dict(xyxy=bounds,full_shape=list(shape),native_mask_union_sources=sorted(relevant),padding_px=24,
                transform='crop(x,y)=(full_x-x0,full_y-y0)',selection_uses_GT=False),
            depth_scale_mm=[float(lo),float(hi)],common_color_scale=True,all_visible_neighbor_masks_and_fragments_retained=True,
            source_bindings=[packets[frame]['source_binding'] for frame in sorted(frames)],
            future_panels_postseal_diagnosis_only=True,RGB=False,GT_raster=False))
    return inventory


def main():
    metric=require_complete()
    assert not (HERE/'FAILURE_CASES.json').exists(),'Never overwrite a completed interpretation'
    summary,selected,sources=summarize_and_select(metric)
    cases=[inspect_case(item) for item in selected.values() if item is not None]
    install_pixel_guard()
    pictures=[picture for case in cases for picture in visualize(case)]
    write_new(HERE/'PRIVATE_FAILURE_VISUALS.json',dict(status='POSTSCORE_REAL_DEPTH_MASK_PUBLICATION_PANELS',
        figures=pictures,private_pixels=True,RGB=False,GT_raster=False,new_prediction=False,
        no_outcome_optimized_case_replacement=True,postscore_script=artifact(__file__)))
    write_new(HERE/'FAILURE_CASES.json',dict(status='POSTSCORE_INTERPRETATION_ONLY_NOT_A_NEW_TEST',
        arm=ARM,dataset_counts=summary,cases=cases,selection='Earliest original-frame genuine joint COMMIT with bank WRONG/UNSCORABLE per fixed dataset; Feeding pooled four segments',
        category_counts_overlap_not_a_partition=True,absence_of_failed_commit_is_not_correctness=True,
        no_new_prediction_counterfactual_or_choice_inference=True,private_visual_inventory=artifact(HERE/'PRIVATE_FAILURE_VISUALS.json'),
        scientific_sources=sources,metric_source=artifact(RUN/'METRICS.json'),postscore_script=artifact(__file__),
        new_model_http=0,cost_usd=0))
    lines=['# DS19 封存后 joint 失败案例复盘','',
        '仅解释既有封存结果，不是新测试。每个固定dataset按原帧选择MIXED_RETURN最早的真实joint COMMIT且bank判定WRONG/UNSCORABLE；未选最好案例。无失败提交不等于关联正确，H0、fallback、无split另列；以下计数可能重叠。','',
        '| 数据 | joint COMMIT | bank正确/错误/不可评分 | H0 | fallback | 无split | 选择状态 |',
        '|---|---:|---|---:|---:|---:|---|']
    for name,unit in summary.items():
        counts=unit['bank_physical_counts']
        lines.append(f'| {name} | {unit["joint_COMMIT"]} | {counts.get("CORRECT",0)}/{counts.get("WRONG",0)}/{counts.get("UNSCORABLE",0)} | {unit["H0"]} | {unit["fallback"]} | {unit["no_split"]} | {unit["selection_status"]} |')
    for case in cases:
        lines+=['','## '+case['segment']+'/'+case['event'],'',
            f'原帧q={case["global_q"]}，实际选择{case["actual_choice"]}，首次发布mapping={case["actual_first_public_mapping"]}。bank={case["bank_physical"]}；clean端点={case["clean_endpoint_physical"]}；pre片段共识={case["pre_consensus_physical"]}，三者分列。',
            f'order状态={case["order"]["status"]}；描述性强弱={case["order"]["descriptive_strength"]}；p(A更近)={case["order"]["p_A_nearer_at_q"]}；是否改变choice={case["order"]["order_changed_choice"]}。仅列原封存order、候选代价和margin，不重算纯几何或选择反事实。']
        for role,facts in case['roles'].items():
            lines.append(f'{role}: public target={facts["public_target"]}；bank/public origin关系={facts["bank_vs_public_origin"]}；进入前已错公共ID={facts["preexisting_public_error"]}。UNKNOWN保留，原整数编号出现不是物理同一证明。')
    lines+=['','实际深度、原mask与已发布持久ID的参考anchor/merge确认/q/q+5全景和ROI留private/failure_visuals；ROI保留所有邻鱼/残片，来源不是GT。q+5只用于封存后诊断，未进入预测。',
        '真实路径、字节数、SHA见PRIVATE_FAILURE_VISUALS.json；公共JSON/Markdown仅数字、来源元数据和解释，无RGB、私有像素或GT raster。',
        '顺序置信度为未校准代理，weak带仅描述，不改决策门。缺少显式原始choice影响字段时保持UNKNOWN；本复盘不产生新评分、不调参数、不开始下一试验。','']
    with (HERE/'FAILURE_CASES.md').open('x',encoding='utf-8',newline='\n') as f:f.write('\n'.join(lines))
    print('Postscore interpretation complete; datasets',len(summary),'actual selected cases',len(cases),'private figures',len(pictures))


if __name__=='__main__':main()
