"""Frozen postseal report assembly from actual predictions and independent scores."""
from common import *
from collections import Counter
import numpy as np

FIELDS=('IDF1','HOTA','AssA','IDSW','FP','FN')


def table(header,values):
    return '\n'.join(['| '+' | '.join(header)+' |','| '+' | '.join(['---']*len(header))+' |',
        *['| '+' | '.join(map(str,value))+' |' for value in values]])


def distribution(values):
    if not values:return dict(n=0,min=None,median=None,p95=None,max=None)
    a=np.asarray(values,'f8')
    assert np.isfinite(a).all()
    return dict(n=len(values),min=float(a.min()),median=float(np.median(a)),p95=float(np.quantile(a,.95)),max=float(a.max()))


def metric_rows(sections):
    return [[name,arm,*[f'{packet["metrics"][arm][k]:.4f}' if k in FIELDS[:3] else packet['metrics'][arm][k] for k in FIELDS]]
        for name,packet in sections for arm in ARMS]


def difference_rows(sections):
    return [[name,base+' → '+arm,*[f'{packet["metrics"][arm][k]-packet["metrics"][base][k]:+.4f}' if k in FIELDS[:3]
        else f'{packet["metrics"][arm][k]-packet["metrics"][base][k]:+d}' for k in FIELDS]]
        for name,packet in sections for base in ('SAM3_NATIVE','Z4Q_FROZEN','EVENT_RGB')
        for arm in ARMS[2:] if arm!=base]


def summarize_segment(name,metrics):
    public=RUN/name/'public';summary=read(public/'RUN_SUMMARY.json');events=read(public/'EVENTS.json')
    ledgers=list(rows(public/'PUBLISH_LEDGER.jsonl'));inputs=list(rows(public/'FRAME_INPUTS_BINDINGS.jsonl.gz'))
    times={r['frame']:r['time'] for r in inputs}
    assert len(ledgers)==len(inputs)==metrics['frames']==summary['frames']
    published=[r['frame'] for r in ledgers];assert published==list(range(1,summary['frames']+1))
    changes={arm:Counter() for arm in ARMS[2:]};rgbd_vs_rgb=0
    for prediction in rows(public/'predictions.jsonl.gz'):
        for arm in ARMS[2:]:
            for base in ('SAM3_NATIVE','Z4Q_FROZEN'):
                changes[arm][base]+=prediction['variants'][arm]!=prediction['variants'][base]
        rgbd_vs_rgb+=prediction['variants']['EVENT_RGBD']!=prediction['variants']['EVENT_RGB']
    flow=list(rows(public/'FLOW.jsonl.gz'));by_arm={arm:[] for arm in ARMS[2:]}
    for value in flow:by_arm[value['arm']].append(value)
    cascade_records=[]
    for transaction in rows(public/'TRANSACTIONS.jsonl.gz'):
        trace=transaction['controller_trace'];cascade=trace.get('ds34_event_return_cascade')
        if not cascade:continue
        actions=[a for a in trace.get('events',[]) if a.get('source')=='DS34_CURRENT_FRAME_EVENT_RETURN_CASCADE']
        assert actions and all(a['already_published_history_rewritten'] is False for a in actions)
        assert cascade['future_read'] is False and cascade['bank_copied'] is False
        cascade_records.append(dict(arm=transaction['arm'],frame=transaction['frame'],global_frame=transaction['global_frame'],
            detail=cascade,actual_alias_revocations=actions,
            actual_qualified_returns=cascade.get('actual_qualified_returns',[]),
            extra_return_quality_qualification_required=False,
            physical_identity='UNKNOWN',new_depth_contribution=False))
    arm_summaries={}
    for arm,values in events.items():
        qevents=[e for e in values if e.get('q') is not None]
        decisions=[e.get('joint_decision',{}) for e in qevents]
        audit=metrics['audit']['event_arms'][arm]
        assert {e['id'] for e in values}=={e['event'] for e in audit}
        contours=[c for d in decisions for candidate in d.get('scores',[]) for edge in candidate['edges'] for c in edge['contour_samples']]
        # Each 2x2 edge appears once across H1 and H2. Depth forecasts are
        # candidate-shared; the counts below remain logical evidence records.
        depth_facts=[f for d in decisions for facts in d.get('depth_facts',{}).values() for f in facts]
        arm_summaries[arm]=dict(automatic_episodes=len(values),first_split_windows=len(qevents),
            no_split_episodes=len(values)-len(qevents),status_counts=dict(Counter(e['status'] for e in values)),
            choice_counts=dict(Counter(d.get('choice','UNKNOWN') for d in decisions)),
            reason_counts=dict(Counter(d.get('reason','UNKNOWN') for d in decisions)),
            actual_joint_stages=sum(bool(e.get('restore',{}).get('staged')) for e in qevents),
            staged_first_publication_differs_Z4Q=sum(e['staged'] and e['changes_real_publication'] for e in audit),
            staged_internal_preview_changes=sum(e['staged'] and bool(e['preview_changes']) for e in audit),
            actual_fallbacks=sum(not e.get('restore',{}).get('staged',False) for e in qevents),
            fallback_reasons=dict(Counter(str(e.get('restore',{}).get('error') or e.get('joint_decision',{}).get('reason') or 'UNKNOWN')
                for e in qevents if not e.get('restore',{}).get('staged',False))),
            depth_weight_used_windows=sum(d.get('common_weights',{}).get('depth',0)>0 for d in decisions),
            contour_weight_used_windows=sum(d.get('common_weights',{}).get('contour',0)>0 for d in decisions),
            motion_weight_used_windows=sum(d.get('common_weights',{}).get('motion',0)>0 for d in decisions),
            depth_logical_fact_rows=len(depth_facts),depth_usable_logical_fact_rows=sum(bool(f.get('usable')) for f in depth_facts),
            contour_edge_pair_rows=len(contours),contour_available_rows=sum(bool(c['available']) for c in contours),
            contour_reliable_fraction=distribution([c[k] for c in contours for k in ('forward_reliable_fraction','backward_reliable_fraction') if k in c]),
            contour_raw_symmetric_dice=distribution([c['symmetric_dice'] for c in contours if 'symmetric_dice' in c]),
            actual_flow_pairs=len(by_arm[arm]),recorded_flow_seconds=sum(p['actual_pair']['flow_seconds'] for p in by_arm[arm]),
            actual_flow_depth_unknown_pairs=sum(p['actual_pair']['depth_status']=='UNKNOWN' for p in by_arm[arm]),
            physical_counts_all_events=dict(Counter(e['physical_preanchor'] for e in audit)),
            physical_counts_actual_joint_stages=dict(Counter(e['physical_preanchor'] for e in audit if e['staged'])),
            physical_prefragment_joint_stages=dict(Counter(e['physical_prefragment'] for e in audit if e['staged'])),
            postfragment_preanchor_joint_stages=dict(Counter(e['postfragment_preanchor'] for e in audit if e['staged'])),
            postfragment_prefragment_joint_stages=dict(Counter(e['postfragment_prefragment'] for e in audit if e['staged'])),
            public_reference_joint_stages=dict(Counter(e['public_reference_correctness'] for e in audit if e['staged'])),
            first_publication_vs_Z4Q_changed_frames=changes[arm]['Z4Q_FROZEN'],
            first_publication_vs_native_changed_frames=changes[arm]['SAM3_NATIVE'],
            original_manager_counts=summary['counts'][arm])
        assert arm_summaries[arm]['actual_joint_stages']==summary['joint_stages'][arm]
    return dict(frames=summary['frames'],objects=summary['objects'],elapsed_seconds=summary['elapsed_seconds'],
        arm_summaries=arm_summaries,RGBD_minus_RGB_changed_frames=rgbd_vs_rgb,
        publication_delay_frames=distribution([r['actual_delay_frames'] for r in ledgers]),
        publication_data_time_delay_seconds=distribution([times[r['first_publish_at_arrival_frame']]-times[r['frame']] for r in ledgers]),
        receive_to_first_publish_wall_seconds=distribution([r['receive_to_first_publish_seconds'] for r in ledgers]),
        scan_dispositions={arm:dict(Counter(r['status'] for r in values)) for arm,values in read(public/'SCAN_DISPOSITIONS.json').items()},
        current_frame_event_alias_return_cascades=cascade_records,
        cascade_counts={arm:dict(frames=sum(r['arm']==arm for r in cascade_records),
            aliases_revoked=sum(len(r['actual_alias_revocations']) for r in cascade_records if r['arm']==arm)) for arm in ARMS[2:]},
        actual_switch_changes=read(public/'SWITCH_CHANGES.json'),prediction_seal=artifact(public/'PREDICTIONS_SEALED.json'))


def main():
    from verify_inputs import verify_all
    verify_all();scored=read(RUN/'METRICS.json');provenance=read(RUN/'SCORE_PROVENANCE.json')
    assert scored['status']=='SCORED_AFTER_ALL_EIGHT_FORMAL_PREDICTION_AND_ACCESS_SEALS'
    assert scored['frames']==20098 and provenance['reference_opened_after_all_seals'] and provenance['original_controls_exact']
    assert provenance['official_metric_math_unchanged'] and not provenance['GT_used_for_prediction'] and provenance['ignored_public_ids']==0
    segments={name:summarize_segment(name,dict(scored['segments'][name],audit=scored['event_audits'][name])) for name in SEGMENTS}
    sections=[(name,scored['segments'][name]) for name in SEGMENTS]+[('Feeding four-segment pooled',scored['feeding_pooled'])]
    differences=difference_rows(sections)
    changed=sum(v['RGBD_minus_RGB_changed_frames'] for v in segments.values())
    depth_windows=sum(v['arm_summaries']['EVENT_RGBD']['depth_weight_used_windows'] for v in segments.values())
    stages={arm:sum(v['arm_summaries'][arm]['actual_joint_stages'] for v in segments.values()) for arm in ARMS[2:]}
    increased=[];decreased=[]
    for name,packet in sections:
        if name.startswith('feeding_'):continue # Separate source rows still remain in all tables.
        for base in ('SAM3_NATIVE','Z4Q_FROZEN','EVENT_RGB'):
            delta={k:packet['metrics']['EVENT_RGBD'][k]-packet['metrics'][base][k] for k in FIELDS}
            if any(delta[k]>0 for k in FIELDS[:3]) or delta['IDSW']<0:increased.append(dict(source=name,baseline=base,deltas=delta))
            if any(delta[k]<0 for k in FIELDS[:3]) or delta['IDSW']>0:decreased.append(dict(source=name,baseline=base,deltas=delta))
    exact_z4q=all(packet['metrics']['EVENT_RGBD']==packet['metrics']['Z4Q_FROZEN'] for _,packet in sections)
    verdict=('COMPLETE_TRIAL_NO_METRIC_INCREMENT_OVER_Z4Q' if exact_z4q else
        'COMPLETE_TRIAL_MIXED_IMPROVEMENT_AND_REGRESSION' if increased and decreased else
        'COMPLETE_TRIAL_OBSERVED_IMPROVEMENT' if increased else 'COMPLETE_TRIAL_NO_OBSERVED_IMPROVEMENT')
    records=list(rows(HERE/'EXECUTION_LOG.jsonl'))
    successful=lambda script:[r for r in records if Path(r['command'][1]).name==script and r['exit_code']==0]
    replay,score_jobs=successful('orchestrate.py'),successful('score.py')
    assert len(replay)==len(score_jobs)==1
    summary=dict(status=verdict,frames=20098,segments=segments,new_model_http=0,cost_usd=0,
        actual_joint_stages=stages,actual_depth_weight_windows=depth_windows,RGBD_minus_RGB_changed_frames=changed,
        increases=increased,decreases=decreased,metric_equality_RGBD_and_Z4Q=exact_z4q,
        GT_used_only_after_all_predictions_sealed=True,depth_increment_is_RGBD_minus_RGB=True,
        shared_protection_and_prior_repairs_not_unique_depth_credit=True,
        physical_depth_or_scene_flow_accuracy='UNKNOWN',core_frozen_runtime=artifact(HERE/'RUNTIME_FREEZE.json'),
        metrics=artifact(RUN/'METRICS.json'),scoring_provenance=artifact(RUN/'SCORE_PROVENANCE.json'))
    write_new(HERE/'RESULTS.json',summary)
    events=[];physical=[];switches=[];delays=[];automatic=[];cascade_rows=[]
    for name,value in segments.items():
        for arm,counts in value['cascade_counts'].items():cascade_rows.append([name,arm,counts['frames'],counts['aliases_revoked']])
        for arm,count in value['arm_summaries'].items():
            events.append([name,arm,count['automatic_episodes'],count['first_split_windows'],count['no_split_episodes'],
                count['actual_joint_stages'],count['staged_first_publication_differs_Z4Q'],count['actual_fallbacks'],
                count['depth_weight_used_windows'],count['contour_weight_used_windows'],count['actual_flow_pairs']])
            for basis in ('physical_counts_actual_joint_stages','physical_prefragment_joint_stages','postfragment_preanchor_joint_stages',
                'postfragment_prefragment_joint_stages','public_reference_joint_stages'):
                c=count[basis];physical.append([name,arm,basis,*[c.get(k,0) for k in ('CORRECT','WRONG','UNSCORABLE')]])
        for comparison,c in value['actual_switch_changes'].items():
            switches.append([name,comparison,len(c['added']),len(c['eliminated']),c['net_IDSW'],len(c['occurrence_added']),len(c['occurrence_eliminated'])])
        delay=value['publication_delay_frames'];data=value['publication_data_time_delay_seconds'];wall=value['receive_to_first_publish_wall_seconds']
        delays.append([name,f'{delay["min"]:.0f}/{delay["median"]:.0f}/{delay["max"]:.0f}',
            f'{data["median"]:.3f}/{data["p95"]:.3f}/{data["max"]:.3f}',f'{wall["median"]:.3f}/{wall["p95"]:.3f}/{wall["max"]:.3f}'])
        for arm in ARMS[1:]:
            actions=[a for a in scored['event_audits'][name]['automatic_actions'] if a['arm']==arm]
            for phase in ('D1_DELAYED','BIRTH_REFINE'):
                subset=[a for a in actions if a['phase']==phase]
                pc=Counter(a['physical_preanchor'] for a in subset);uc=Counter(a['public_reference_correctness'] for a in subset)
                automatic.append([name,arm,phase,len(subset),*['/'.join(str(c[k]) for k in ('CORRECT','WRONG','UNSCORABLE')) for c in (pc,uc)]])
    text=f'''# DS34：双端短片段与有限延迟事件联合恢复

## 1. 主判定与分层边界

**{verdict}**。固定八套来源共20,098帧，四个分支全部继续自己的真实状态至段末；全部预测和访问记录先封存，随后独立统一评分。EVENT_RGB/EVENT_RGBD真实联合stage次数为 `{json.dumps(stages)}`；EVENT_RGBD实际启用深度权重的窗口为{depth_windows}，相对EVENT_RGB改变发布的帧数为{changed}。本报告按真实结果填写，不把工程通过、一次CHOICE或宽尺度覆盖写成性能收益。

- 工程：实际预览、原子stage/commit、未发布suffix回放、一次首次发布和全部mask/残片保留均有封存证据；原SAM3/原Z4Q逐帧控制及官方指标与DS33严格一致。
- 输入：固定原SAM3、原始深度、真实RGB/时间戳/实际标定和DS18来源质量；精确bank anchor、独立source generation/public epoch、匿名GROUP/post分开。隐藏的producer身份版本与水下物理标定精度仍UNKNOWN。
- 方法：原Z4Q组外策略保留；事件保护/几何/轮廓/深度和局部回退共同影响结果。EVENT_RGBD−Z4Q不能全记为深度收益；EVENT_RGBD−EVENT_RGB才是本轮深度模块整体增量。
- 证据：本轮是既有曝光数据上的探索性试验，L3/LW为弱参考诊断；没有新的盲测泛化结论。DEFER、无分离、无历史、缺测、非法候选与不可评分均保留，不能算安全通过。

基点 `{BASE}`。新增大模型HTTP=0、smoke=0、训练=0、SAM3推理=0、深度补全服务=0、费用=0美元。内部事件和候选不是大模型调用。

## 2. 冻结方法和实际科学范围

沿用原V4预测扫描与两鱼保护范围：首次疑似立即保护，合并只记录匿名GROUP；持续native及新source可进入真实两候选联合映射。最后可靠pre来自实际bank anchor的同版本连续片段，30帧缓存、最近10点真实时间OLS/WLS，immutable anchor最多12秒；风险切断live，不能删除仍未改变的anchor来源，也不能按public整数拼接另一source。

q是首次两个分离候选。当前与后续观测在关联前保持匿名，采用首个满足固定规则的3帧连续raw-clean片段，最长等待30帧或10秒/EOF。先选择完整H1/H2物理bijection，再在本分支q−1checkpoint上真实stage/commit并回放q至cutoff，随后第一次发布q；q状态只能使用q实际观测，未来测量不写进q bank。已经发布的历史不改写。失败使用本事件写集的局部回退，保住组外状态和先前修复；不存在整套复制B0 engine的回退。

轮廓用真实pre最后3帧与post固定3帧的所有短端点对，已安装OpenCV DIS MEDIUM前后向RGB灰度对应；没有从旧anchor一路长链传播到重现端。RGB可靠性由双向误差、纹理和光度判断；深度原源去重独立约束测量质量。两个新分支采用相同RGB轮廓传播，深度以独立候选代价参与完整解释。post反向回到q只作候选无关连续性诊断，不参与身份分数。未进行RAFT-3D训练/推理，也没有补画或分割mask。

深度使用同一片段真实DS18 whole/core质量与DS1原时间WLS预测，原源去重、混层/共享/缺失均可追溯；比较预测与当前深度的背景归一化t4代价。整个2×2比较共同可用才启用冻结权重0.25，否则共同无信息；未知和宽尺度不使某条边自动少罚。二维真实回归运动权重0.25、轮廓权重0.25、联合margin0.10保持冻结。真实depth时间重复不报3D速度；RGB对应和可靠点支持仍不是鱼的物理身份或遮挡真值。

V4初始群组需要既有前帧source和面积历史，不能宣称覆盖所有新ID群组；多事件同时相交仍在原单活动组范围。源原先已错号、未观察的producer reset/串鱼、末帧GT缺失均不能靠public整数或模型假设填真值。详细边界见DATA_CONTRACT。

## 3. 完整指标

百分指标单位%，差值为百分点。IDSW/FP/FN是全段完整计数，任何ID和mask均未排除。Feeding四段以独立身份命名空间合池，不能与FishSA/L3/LW混成一个总体标题。

{table(('来源','分支',*FIELDS),metric_rows(sections))}

L3/LW参考为未独立审查的预测辅助标注，保持弱参考标签。FishSA沿用原参考raster/版本，Feeding640、L3/LW1080p polygon，CLEAR/Identity IoU0.5和HOTA19alpha数学不变。

### 同源原生、原Z4Q及深度增量的完整差值

{table(('来源','比较',*('Δ'+k for k in FIELDS)),differences)}

相对较弱原Z4Q的提升不自动表示超过同源SAM3；恢复到原Z4Q只是止损。出现指标涨跌时分别报告，不用净IDSW掩盖新增错误。

## 4. 事件、真实提交、深度和弃权

{table(('来源','分支','疑似episode','q窗口','无分离','联合stage','stage首帧异Z4Q','数值局部回退','depth λ>0','contour λ>0','实际flow对'),events)}

首帧与Z4Q的差异包含共同保护与先前自身修复，不能直接当作当前选择的独有作用。`preview_changes`只比较从未发布的内部临时H1；真实发布差异单独对照同源最终Native/Z4Q。stage即使首帧ID不变，也可能真实建立了后续alias；不能只数ID变化判断状态提交。

逐来源完整选择/状态/reason、缺测、数值fallback、来源窗口和证据计数写入RESULTS.json，原始EVENTS、FLOW、TRANSACTIONS和PUBLISH_LEDGER保持封存。逻辑fact与候选pair会共享测量，不能把行数当独立鱼事件数。可靠轮廓比例、宽深度区间覆盖不是物理准确率。

## 5. 物理参考与公共ID原始来源分开

下表只对实际联合stage评价物理恢复；无stage的回退、DEFER和无q顶层都为UNSCORABLE，保留观测映射诊断另列。literal q必须实际匹配该首帧；postfragment共识要求全部预先固定3帧各自唯一匹配同一GT，缺一帧或冲突即不可评分，不挑可评分子集。prefragment独立要求至少3个固定连续观测同一共识。

{table(('来源','分支','实际评分依据','CORRECT','WRONG','UNSCORABLE'),physical)}

旧bank实际物理anchor和public严格早于q的首次实际发布来源分列；public整数等于GT整数没有意义。旧参考已错号时，偶然换回公共ID不能当物理身份恢复。EVENT_AUDIT逐edge同时保存literal-q、prefragment、postfragment、public-origin及原参考已错来源；评分映射按实际新物理候选，不按未置换H标签查答案。

### 事件alias的当前帧返回冲突处理

{table(('来源','分支','实际cascade帧','实际撤销event alias数'),cascade_rows)}

这里由当前真实观测和alias占用经过原单轮冲突仲裁后仍存在的重复触发，仅局部撤销与本分支DS34关联的alias链，让原Z4Q当前帧仲裁继续运行；日志为`ds34_event_return_cascade`和`DS34_CURRENT_FRAME_EVENT_RETURN_CASCADE`。`actual_qualified_returns`可为空，这项安全处理没有新增“canonical native必须另行合格返回”的资格门槛。原低质量native quarantine已使重复为空时不撤销alias。这属于共同状态安全处理，不是新的深度身份贡献，也不认证物理鱼恢复。未读取未来返回、未复制B0 bank、未回填已发布历史；全部当前帧实际撤销记录和原始trigger详情保存在RESULTS中。

### 原常驻继承动作（不能全记为本轮事件新贡献）

{table(('来源','分支','原动作来源','实际动作','物理正确/错/不可评','公共来源正确/错/不可评'),automatic)}

BirthRefine的kind也可为reconnect，明确以phase=birth区分BIRTH_REFINE和D1_DELAYED；按最终实际published transaction而非未选中试运行统计。

## 6. 每次切换的新增和消除

{table(('来源','比较','新增完整record','消除完整record','净IDSW','新增GT/帧occurrence','消除GT/帧occurrence'),switches)}

完整record包含具体旧/新public；同GT同帧发生但public不同可以同时算新增和消除而净差0。SWITCHES和SWITCH_CHANGES保留全部原记录、same-GT/frame对应关系，不用净差推断错误个数。

## 7. 延迟、耗时和UNKNOWN

{table(('来源','发布帧延迟min/median/max','真实数据秒median/p95/max','接收到首发墙钟秒median/p95/max'),delays)}

统一首次发布最长30帧，末尾EOF不足则刷新；真实时间戳不均匀，不能把30帧统一写成1秒，不能称实时部署。四臂共同全段编排耗时{replay[0]['elapsed_seconds']:.3f}秒，评分耗时{score_jobs[0]['elapsed_seconds']:.3f}秒，真实exit0。每臂实际FLOW秒数是记录工作量，与同时运行的端到端墙钟不同。

UNKNOWN包括：无独立pre片段、source/generation断裂、未确认分离、共享或混层深度、少量原源点、重复depth timestamp、可靠轮廓不足、无公共历史来源、literal-q GT缺失、三帧参考冲突及弱参考未审查。它们保持UNKNOWN/UNSCORABLE，不改成DEFER模型错误，也不算保护成功。没有新大模型介入。

## 8. 失败机制的实际证据和解释边界

性能增益与退化的逐来源完整差值见第3节，阶段原因见RESULTS内reason_counts/fallback_reasons。若深度权重启用却EVENT_RGBD−EVENT_RGB发布和指标没有变化，只能说此固定输入/候选/代价下未产生增量；不能说深度文件全缺，也不能推广为任何深度方法无效。若q候选因实际旧成员/residual占用或后续alias冲突不可提交，则是合法事务/候选范围限制，与depth是否能识别鱼分开。

双端短片段避免累计长链误差，但合并可污染掩码、单体质量和motion；清晰的source连续存在也不认证物理鱼连续。原Z4Q的常驻出生/返回继承和本分支先前修复能继续影响后续状态。观察到何种原因，只能从真实候选、实际选择、stage拒绝、局部回退和封存后GT关系追溯；不按结果滚动调阈值，不用GT回填或选更容易片段。

## 9. 复现、产物与main同步

源码、实际生效参数和所有动态官方数学/二进制依赖在RUNTIME_FREEZE冻结。全部预测/访问/seal、原始来源、真实body/flow、完整状态/alias/epoch、q至cutoff replay和首次发布hash先验收再开参考。测试仅验证协议/状态/数值，不代替完整性能试验；人工先判对或数值先提点都不是启动条件。

解释器 `E:/researchsoftware/anaconda3/envs/D-MOT/python.exe`，CPU本地运行，安装环境与原输入SHA见ENVIRONMENT/冻结manifest。复现需固定DS14原SAM3、原始native/aligned depth/source_index、真实RGB/标定及DS18质量包，另起新目录按同样检查、冻结、完整回放、封存和评分，不覆盖旧seal。报告生成不改科学源码、选择、预测或评分。

公开数值图见visuals/FULL_METRICS.svg和EVENT_TIMELINE.svg；病例使用实际pre/合并/q/确认帧的本地私有RGB和深度，不公开像素或GT raster。真实路径/字节/SHA和复现依赖见PRIVATE_INVENTORY、PRIVATE_VISUALS_INVENTORY.json及private病例索引。原始响应旧实验只读，本轮未读key、不产生provider file IDs。

所有本轮代码、配置、测试、公开日志/预测/指标/报告/数值图由main普通提交和非force push交付；私有像素只登记真实清单。实际提交SHA、origin/main远端ref及关键blob必须在REMOTE_VERIFICATION实读核验，最终回复单列；报告不能用未知或自引用commit代替远端证据。

## 10. 唯一下一步（未启动）

**按本轮真实错误与不可提交事件，对最主要的一种来源或状态瓶颈做单一修复假设，再冻结完整同源复验；保留原Z4Q和全部mask，仅可靠深度证据产生合法新映射时提交。** 具体优先瓶颈由封存后的逐事件诊断确定，不继续使用已证实无作用的门槛而不检查证据，也不在本轮封存版本上滚动试到通过。本轮结束不自动启动另一轮或加入大模型。
'''
    path=HERE/'FINAL_REVIEW.md'
    with path.open('x',encoding='utf-8',newline='\n') as output:output.write(text)
    write_new(HERE/'REPORT_ASSEMBLY.json',dict(status='POSTSEAL_REPORT_WRITTEN_AWAITING_INDEPENDENT_REVIEW',
        helper=artifact(__file__),report=artifact(path),results=artifact(HERE/'RESULTS.json'),
        metrics=artifact(RUN/'METRICS.json'),new_model_http=0,cost_usd=0))
    print('DS34 complete report assembled',flush=True)


if __name__=='__main__':main()
