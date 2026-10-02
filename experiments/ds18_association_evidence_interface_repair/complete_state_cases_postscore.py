"""Complete the sealed-state report using independent public postscore scalars only."""
from __future__ import annotations
from common import HERE, RUN, DS17, ARMS, SEGMENTS, artifact, read, rows, sha, write_new

FIELDS=('IDF1','HOTA','AssA','IDSW','FP','FN')
AUTOFIELDS=('frame','global_frame','source','target','origin_rule','physical',
    'actual_reference_physical','prior_public_reference_status','incidental_public_origin_return',
    'relations','query_match','bank_match','public_origin_match','actual_old_anchor',
    'durable_automatic_commit','applied_at_first_publication','actual_first_public_id')

def markdown(result):
    lines=['# DS18 封存后真实状态与发布病例审计','',
        '**状态隔离和来源检查不能替代关联性能：本报告只追真实决策、首次公开、后续自身状态及独立封存后判定。**', '',
        '输入为八段六分支共 20,098 帧已封存产物。没有重新预测、反事实回放、测试或修改科学代码；没有读取 GT raster、RGB 或像素。物理判定仅在完整 METRICS/SCORE_PROVENANCE 门槛通过后读取公共独立评分摘要。','',
        '## 归因边界','',
        '- ACTIVITY_ORDER 的匿名当前有效测量与 pending Birth 是共用接口/状态修复，不能计为上下顺序增量。',
        '- MIXED_ORDER−ACTIVITY_ORDER 包含测量资格筛选对整条关联状态链的影响。',
        '- MIXED_ORDER−MIXED_OFF 才保持接口、混合筛选相同，仅改变冻结 ordinal 关联。',
        '- 自动审计 applied_at_first_publication 表示当前决策帧输出采用该映射；延迟 Birth 的实际首次出现/公开必须读 actual_first_source_publication。',
        '- 物理 query↔实际旧 bank 与 bank↔公共 ID 原始起源分列，不能将既有错误公共起源偶然换回当作正确物理恢复。','',
        '## 实际病例','']
    labels={'fishsa_development_8400':'开发 F3902 / native7',
        'fishsa_validation_2888':'验证 local2188 / global11488 / native8',
        'LW':'LW local3064 / global3063 / native133',
        'feeding_001201_001906':'Feeding 末段 local264 / global1464 / native176'}
    for segment,data in result['cases'].items():
        native=data['case']['native'];q=data['case']['frame']
        lines.extend(['### '+labels[segment],'',
            '| 分支 | 当前源首次公开与后续变更（local 帧） | 真正接受动作 | 实际 bank 物理判定 / 公共起源 | 最终 alias |',
            '|---|---|---|---|---|'])
        for arm in ARMS:
            runs=[x for x in data['native_publication_runs'][arm][str(native)] if x['public'] is not None]
            timeline=' → '.join(f"{x['frame']}:{native}→{x['public']}" for x in runs) or '未出现'
            aa=[x for x in data['automatic_actions'].get(arm,[]) if x['source']==native]
            actions='; '.join(f"{x['frame']} {x['origin_rule']}→{x['target']}" for x in aa) or '无'
            verdicts='; '.join(f"{x['actual_reference_physical']} / {x['prior_public_reference_status']}" for x in aa) or '无自动提交'
            final=data['final_actual_state'].get(arm,{})
            alias=final.get('actual_alias_targets',{}).get(str(native),'无/原生')
            lines.append(f'| {arm} | {timeline} | {actions} | {verdicts} | {alias} |')
        lines.extend(['','首次全帧真实发布分歧（不是事后挑选的局部变化）：',''])
        for pair,value in data['first_full_publication_differences'].items():
            lines.append(f"- {pair}: local{value['frame']}/global{value['global_frame']}，{value['changed']}。")
        lines.extend(['','q/目标帧的实际资格与状态：',''])
        for arm in ARMS[3:]:
            state=data['q_actual_state'][arm]
            unknown=sorted({reason for x in data['q_actual_birth_checks'][arm]
                for reason in (x.get('whole') or {}).get('unknown',[])})
            lines.append(f"- {arm}: 发布{native}→{state['actual_mapping'].get(str(native))}；匿名集合{state['anonymous_native_keys']}；当前测量保留{state['current_measurements_preserved']}；缺失来源不更新时间{state['missing_sources_not_updated']}；required whole UNKNOWN={unknown or '无'}。")
        for arm in ARMS[2:]:
            for group in data['q_group_physical_audit'][arm]:
                lines.append(f"- {arm} 联合事件 q={group['q']}：{group['restore_status']} / {group['choice']}；首次实际发布参考判定{group['first_public_physical']}，pre共识判定{group['first_public_pre_consensus_verdict']}。")
        if segment.startswith('fishsa_development'):
            lines.extend(['','开发源7在 q 的Birth实际固定7×7 core n=223、whole n=773，测量保持有效，但身份仍 POST_UNASSIGNED；S0的adaptive core为另一角色，不能混用。q禁止单边自动 alias，H0局部回退。旧公共0真实最后活动3893，clean anchor3836/native6；公共4确实活动到3902，但clean anchor3492已超过12秒。不能凭空给失踪native6更新时间。后续pending回看原3836参考，ACTIVITY3963、MIXED3947才提交，均晚于初次public7。'])
        if segment.startswith('fishsa_validation'):
            lines.extend(['','验证 q 时公共3活动最后2163/clean1935，公共7活动2188/clean1992；缺失source3没有被group更新时间。ACTIVITY在2189合法Birth，mixed筛选使该路径继续UNKNOWN，改由2237 D1；不能把不同路径/不同延迟合并成一次及时S0恢复。'])
        if segment=='LW':
            lines.extend(['','LW3064是自动 Birth 评估帧，不是S0。没有分支在该帧提交native133。ACTIVITY直到3161原Birth窗到期仍不接受；MIXED在3076由D1→129，不能称“3064 Birth被修复”。更早的pending-Birth13→9、19候选迁移和99/105→92改变活动/占用链：native106在ACTIVITY2488→92，而mixed保持106。必须由整段同源指标判断，不能只展示133局部动作。'])
        if segment.startswith('feeding'):
            lines.extend(['','末段176在243首次public176。264 MIXED_ORDER的D1→126不是joint S0；当时活动group属于公共132/159，native176不在该匿名集合。上游native172原190 Birth→126被阻后，ACTIVITY213 D1才→126；mixed又阻了该动作。MIXED_OFF更早39的分离选择导致170后续→136，继而176→136。264的候选及真实旧参考已随分支状态改变，不能强套原bank答案或归为独立一次正确深度恢复。'])
        lines.append('')
    lines.extend(['## 共用修复与深度增量的整段差值','',
        '| 段 | ACTIVITY IDF1 | MIXED IDF1 | ACTIVITY−DS17 ACTIVITY | ACTIVITY−Z4Q | MIXED−ACTIVITY | MIXED−OFF |',
        '|---|---:|---:|---:|---:|---:|---:|'])
    for segment,data in result['metrics'].items():
        m=data['metrics'];delta=data['deltas']
        lines.append(f"| {segment} | {m['ACTIVITY_ORDER']['IDF1']:.6f} | {m['MIXED_ORDER']['IDF1']:.6f} | {data['ds17_to_ds18_activity_interface_delta']['IDF1']:+.6f} | {delta['Z4Q_FROZEN']['ACTIVITY_ORDER']['IDF1']:+.6f} | {delta['ACTIVITY_ORDER']['MIXED_ORDER']['IDF1']:+.6f} | {delta['MIXED_OFF']['MIXED_ORDER']['IDF1']:+.6f} |")
    lines.extend(['','完整IDF1/HOTA/AssA/IDSW/FP/FN及上述各同源差值在JSON metrics表，未仅选保留病例。L3/LW使用既有预测派生弱参考，不上升为独立人工真值性能。','',
        '## pending 日志与残余工程边界','',
        'dev native6的Birth cache最后held/UNKNOWN更新1314，但1327仍实际进行Birth评估且由D1接受6→0；此后bank/view clean推进到3836/native6。pending不参与匿名集合、reference_status或clean注册，因此休眠记录没有继续冻结该已提交别名。该源最后公开活动3893，与q3902失踪源不更新时间一致。','',
        'pending的evaluation_frame是日志snapshot帧；last_evaluation_frame只由remember_birth在held/UNKNOWN更新，不一定等于最后真正尝试。这里订正source-only cache文字中的“实际最后重评”简写：应以birth_checks/accepted事务读取真实尝试。D1接受后未清理Birth cache、源缺失/被retired后不主动退休旧cache，导致终态PENDING字符串和真实资格不能等同；窗口每次有资格重评时仍按原birth/first_eligible检查。','',
        '| 段 | 分支 | RETIRED cache | PENDING cache | 未退休但已过原窗 | 其中已有alias |',
        '|---|---|---:|---:|---:|---:|'])
    for segment,data in result['cases'].items():
        for arm in ARMS[3:]:
            count=data['final_actual_state'][arm]['pending_counts']
            lines.append(f"| {segment} | {arm} | {count.get('RETIRED',0)} | {count.get('PENDING_NOT_IDENTITY_COMMIT',0)} | {count.get('UNRETIRED_SNAPSHOT_PAST_ORIGINAL_WINDOW',0)} | {count.get('DORMANT_ALIASED',0)} |")
    lines.extend(['','另有初次候选循环的资格顺序边界：初次某个候选产生pending后，同帧后续尚未登记的候选暂报PENDING_TARGET_ANCHOR_CHANGED，随后才加入同帧初始targets；这不是实际换锚证据。LW3064该类candidate同时有独立whole UNKNOWN/其他失败，本报告不臆断其造成性能变化。','',
        '## 复现与证据绑定','',
        '只读source提取：`python experiments/ds18_association_evidence_interface_repair/review_state_cases.py --source`。统一评分完成后报告：`python experiments/ds18_association_evidence_interface_repair/complete_state_cases_postscore.py`。脚本均用新增文件写入，不覆盖旧报告；已有输出时应在独立报告目录复现，不能重跑科学预测或评分。','',
        'JSON sources逐一保存真实路径、字节和SHA，包括所有病例封存预测、真实事务、独立自动/事件判定和reference_matches，report_helper绑定实际报告代码。公开产物仅标量、时间、token与来源摘要，不含私有像素。',''])
    return '\n'.join(lines)

def main():
    # Before this point the report reads no reference-derived facts.
    assert (RUN/'SCORE_PROVENANCE.json').exists() and (RUN/'METRICS.json').exists()
    metrics=read(RUN/'METRICS.json');provenance=read(RUN/'SCORE_PROVENANCE.json')
    assert metrics['status']=='SCORED_AFTER_ALL_SIX_ARMS_EIGHT_SEALS'
    assert metrics['all_seal']==artifact(RUN/'ALL_PREDICTIONS_SEALED.json')
    assert provenance['scientific_source_and_runtime_verified'] and provenance['reference_opened_after_all_seals']
    assert provenance['GT_used_for_predictions'] is False and provenance['masked_or_ignored_ids']==0
    assert provenance['scorer']==artifact(HERE/'score.py')
    source=read(HERE/'POSTSEAL_STATE_SOURCE_CASES.json')
    assert source['helper']==artifact(HERE/'review_state_cases.py')
    for item in source['sources']:
        assert artifact(item['path'])==item
    old=read(DS17/'run/METRICS.json')
    sources=[artifact(HERE/'POSTSEAL_STATE_SOURCE_CASES.json'),artifact(HERE/'review_state_cases.py'),
        artifact(RUN/'METRICS.json'),artifact(RUN/'SCORE_PROVENANCE.json'),artifact(DS17/'run/METRICS.json')]
    cases={}
    for segment,data in source['segments'].items():
        public=RUN/segment/'public';q=data['case']['frame'];native=data['case']['native']
        extra={'LW':[13,19,99,105,106], 'feeding_001201_001906':[167,170,172]}.get(segment,[])
        audit=read(public/'AUTOMATIC_RECONNECT_AUDIT.json');event=read(public/'EVENT_AUDIT.json')
        sources.extend(artifact(public/name) for name in ('AUTOMATIC_RECONNECT_AUDIT.json',
            'EVENT_AUDIT.json','REFERENCE_MATCHES.jsonl.gz','METRICS.json'))
        actions={arm:[] for arm in ARMS[1:]};wanted_frames={q};wanted_sources={native,*data['case']['extras'],*extra}
        for arm in ARMS[1:]:
            for a in audit['arms'][arm]:
                if a['source'] not in wanted_sources:continue
                item={k:a[k] for k in AUTOFIELDS if k in a}
                action=a['actual_controller_action']
                item['birth_publication_metadata']={k:action[k] for k in (
                    'birth_frame','original_birth_frame','evaluation_frame','public_at_frame','pending_retry',
                    'source_previously_published','actual_first_source_publication','association_evidence_sha256') if k in action}
                first_public=action.get('actual_first_source_publication',{}).get('frame',action.get('birth_frame'))
                item['source_birth_first_publication_is_commit_frame']=(
                    first_public==a['frame'] if first_public is not None else None)
                item['first_source_frame_from_actual_birth_or_publication_metadata']=first_public
                actions[arm].append(item);wanted_frames.add(a['frame'])
                anchor=a['actual_old_anchor']
                if anchor:wanted_frames.add(anchor['frame']);wanted_sources.add(anchor['native_id'])
        difference_frames={x['frame'] for x in data['first_full_publication_differences'].values()}
        groups={arm:[x for x in event['arms'][arm]['group_events'] if x.get('q') is not None and
            (x['q'] in {q,*difference_frames} or
             (x['q']<=q and wanted_sources.intersection(map(int,x.get('posts',{})))))]
                for arm in ARMS[2:]}
        matches={}
        for row in rows(public/'REFERENCE_MATCHES.jsonl.gz'):
            if row['frame'] in wanted_frames:
                matches[str(row['frame'])]={str(n):row['matches'][str(n)] for n in wanted_sources
                    if str(n) in row['matches']}
        initial_checks={};separation={};retirements={}
        for arm in ARMS[2:]:
            snapshot=next(x for x in data['selected_actual_transactions'][arm] if x['frame']==q)
            initial_checks[arm]=[dict(native=x.get('native_id'),target=x.get('canonical_id'),
                failures=x.get('failures'),whole=x.get('required_whole_evidence'),
                edge=x.get('edge_veto'),query=x.get('current_depths'),target_measurements=x.get('depth_anchors'))
                for x in snapshot['birth_checks'] if x.get('native_id')==native]
            separate=snapshot['separation']
            separation[arm]=dict(frame=q,actual_mapping=snapshot['actual_published_mapping'],
                actual_alias_targets=snapshot['actual_alias_targets'],restore=snapshot.get('restore'),
                frozen_reference_registry=snapshot['frozen_reference_registry'],
                anonymous_native_keys=separate.get('anonymous_native_keys'),
                current_measurements_preserved=separate.get('anonymous_current_measurement_preserved'),
                recent_core_frozen=separate.get('certified_recent_core_frozen'),
                missing_sources_not_updated=separate.get('missing_sources_not_updated'),
                actual_activity=separate.get('public_activity'),reference_status=separate.get('reference_status'))
            retirements[arm]=[x for x in data['pending_evaluation_transitions'][arm][str(native)]
                if x.get('retired_reason')]
        cases[segment]=dict(case=data['case'],first_full_publication_differences=data['first_full_publication_differences'],
            native_publication_runs=data['focus_native_mapping_runs'],automatic_actions=actions,
            q_group_physical_audit=groups,q_actual_state=separation,q_actual_birth_checks=initial_checks,
            pending_evaluation_transitions=data['pending_evaluation_transitions'],retirements=retirements,
            final_actual_state=data['final_actual_state'],independent_postseal_reference_matches=matches)
    metric_tables={}
    for segment in SEGMENTS:
        actual=metrics['segments'][segment]['metrics'];past=old['segments'][segment]['metrics']
        for arm in ('SAM3_NATIVE','Z4Q_FROZEN'):
            assert actual[arm]==past[arm],(segment,arm,'archived baseline mismatch')
        metric_tables[segment]=dict(metrics={arm:{f:actual[arm][f] for f in FIELDS} for arm in ARMS},
            deltas={base:{arm:{f:actual[arm][f]-actual[base][f] for f in FIELDS} for arm in ARMS}
                    for base in ('Z4Q_FROZEN','DS16_ORDER','ACTIVITY_ORDER','MIXED_OFF')},
            ds17_to_ds18_activity_interface_delta={f:actual['ACTIVITY_ORDER'][f]-past['ACTIVITY_ORDER'][f] for f in FIELDS})
    result=dict(status='POSTSEAL_STATE_CASES_COMPLETE',frames=20098,new_prediction_runs=0,
        no_gt_raster_or_rgb_read=True,source_review=artifact(HERE/'POSTSEAL_STATE_SOURCE_CASES.json'),
        sources=sources,report_helper=artifact(__file__),cases=cases,metrics=metric_tables,
        interpretation={
            'shared_interface_repair':'Pending Birth and valid anonymous current measurements are common state/evidence repair, not ordinal depth increment.',
            'mixed_quality_increment':'MIXED_ORDER minus ACTIVITY_ORDER includes qualification-induced lifetime/candidate effects; isolate whole sequence rather than one selected frame.',
            'ordinal_increment':'MIXED_ORDER minus MIXED_OFF holds state/interface and mixed qualification fixed.',
            'publication':'applied_at_first_publication on automatic audit means published in that decision frame. Actual first-ever source publication remains independently in Birth metadata.',
            'pending':'snapshot evaluation_frame is not retry time; last_evaluation_frame is the last held/UNKNOWN evaluation that updated the cached record via remember_birth, not necessarily the most recent attempted retry. The source-cache prose calling it the most recent evaluation is superseded by this control-flow correction. Alias/past-window cached PENDING records are dormant, not counted as live eligible proposals.',
            'reference':'Actual bank physical agreement and inherited public-origin mismatch remain separate; conservative physical WRONG can coexist with actual_reference_physical CORRECT.',
            'initial_candidate_order_boundary':'On first proposal frame, a later matrix candidate can see a pending record before its initial target is registered and be marked PENDING_TARGET_ANCHOR_CHANGED. It is registered later that same frame; this is metadata/qualification ordering, not evidence of measured conflict. LW3064 also has independent whole UNKNOWN failures, so no causal performance effect is asserted.'})
    write_new(HERE/'POSTSEAL_STATE_CASES.json',result)
    with (HERE/'POSTSEAL_STATE_CASES.md').open('x',encoding='utf-8',newline='\n') as output:
        output.write(markdown(result))
    return result

if __name__=='__main__':
    main()
