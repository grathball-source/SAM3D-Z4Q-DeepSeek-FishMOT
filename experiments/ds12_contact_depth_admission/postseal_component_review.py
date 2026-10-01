"""Independent sealed-log census. No GT files, predictor or replay are invoked."""
from __future__ import annotations

from collections import Counter
import json
import math
from pathlib import Path
import statistics
import sys

from common import HERE, RUN, SEGMENTS, ARMS, read, rows, sha, artifact, write_new


def histogram(values):
    return dict(sorted(Counter(values).items(), key=lambda item: str(item[0])))


def distribution(values):
    finite=sorted(float(x) for x in values if isinstance(x,(int,float)) and math.isfinite(x))
    if not finite:return dict(n=0,min=None,median=None,max=None)
    return dict(n=len(finite),min=finite[0],median=statistics.median(finite),max=finite[-1])


def certificate_summary(cert):
    if not cert:return None
    keys=('component_id','area','n','valid_fraction','median_mm','actual_mad_mm','scale_mm',
          'qualified','weight','exclusion_reasons','selected_source_points',
          'shared_source_pixels_excluded','duplicate_pixels_excluded','inferred_pixels_excluded')
    return dict(fact_id=cert['fact_id'],certificate_sha256=cert['certificate_sha256'],
        source_measurement_fact_id=cert['source_measurement_fact_id'],source=cert['source'],
        mode=cert['mode'],mask_area=cert['mask_area'],eligible=cert['eligible'],
        qualified_component_count=cert['qualified_component_count'],
        core_area=cert['geometric_components']['roi_area'],
        exclusive_geometric_component_count=cert['geometric_components']['component_count'],
        actual_core_8_component_count=len(cert['components']),
        components=[{k:p[k] for k in keys if k in p} for p in cert['components']],
        mixture_weights=[p['weight'] for p in cert['qualified_components']],
        measured_neighbor_relations=cert['neighbors'],
        shared_mask_pixels_excluded=cert['shared_mask_pixels_excluded'],
        physical_surface_identity='UNKNOWN',physical_depth_accuracy_mm='UNKNOWN')


def score_summary(score,query):
    if score is None:return None
    if score['is_new']:
        return {k:score.get(k) for k in ('public','is_new','log_prior','geometry_log_lr',
            'depth_log_lr','log_score','posterior')}
    geo,depth=score['geometry_forecast'],score['depth_forecast']
    residuals=geo['calibration']['residuals']
    errors=[sum(x*x for x in r['residual_px']) for r in residuals]
    delta=[a-b for a,b in zip(query['center'],geo['mu_px'])]
    last=score['qualification']['frozen_depth']['samples'][-1]
    components=score['depth'].get('components')
    return dict(public=score['public'],source=score['source'],is_new=False,
        log_prior=score['log_prior'],geometry_log_lr=score['geometry_log_lr'],
        depth_log_lr=score['depth_log_lr'],log_score=score['log_score'],posterior=score['posterior'],
        geometry=dict(mean_mode=geo['mean_mode'],mean_distance_to_query_px=math.hypot(*delta),
            actual_gap_seconds=geo['actual_gap_seconds'],capped_mean_gap_seconds=geo['capped_mean_gap_seconds'],
            real_pre_span_seconds=geo['real_pre_span_seconds'],growth_factor=geo['growth_factor'],
            history_samples=geo['samples'],residual_count=geo['calibration']['residual_count'],
            next_step_residual_rms_px=math.sqrt(sum(errors)/len(errors)) if errors else None,
            calibration_method=geo['calibration']['method'],covariance_px2=geo['covariance_px2'],
            inflated_covariance_px2=geo['inflated_covariance_px2'],
            raw_log_density=score['geometry']['raw_log_density'],
            background_log_density=score['geometry']['background_log_density']),
        depth=dict(used=score['depth']['used'],forecast_status=depth['status'],
            forecast_mu_mm=depth['mu_mm'],forecast_scale_mm=depth['scale_mm'],
            history_samples=depth['samples'],last_certified_frame=last['frame'],last_certified_time=last['time'],
            last_certified_z_mm=last['z_mm'],last_certified_mad_mm=last['mad_mm'],
            raw_log_density=score['depth']['raw_log_density'],
            background_log_density=score['depth']['background_log_density'],
            mixture_log_density=score['depth']['mixture_log_density'],components=components,
            missing_model=score['depth'].get('missing_model'),
            calibration={k:v for k,v in (depth.get('calibration') or {}).items()
                         if k not in ('increments','version_key')}))


def case_summary(segment,row,query,audit,events,transaction):
    observation=query['query_observation'];selection=query.get('selection')
    refs={(r['source'],r['public']):r for r in audit['candidate_references']}
    candidates=[]
    for candidate in query['candidates']:
        reference=refs[(candidate['source'],candidate['public'])]
        score=(selection or {}).get('candidates',{}).get(f"OLD:{candidate['public']}")
        if score and score['source']!=candidate['source']:score=None
        candidates.append(dict(source=candidate['source'],public=candidate['public'],
            eligible=candidate['eligible'],reasons=candidate['reasons'],
            history_count=len(candidate['geometry_history']),raw_history_count=len(candidate['frozen_depth']['samples']),
            full_reference_gap_seconds=candidate['risk_interval']['full_gap_seconds'],
            clean_reference_frame=(candidate.get('reference_anchor') or {}).get('frame'),
            actual_bank_frame=(candidate.get('anchor') or {}).get('frame'),
            current_vs_clean=reference['current_vs_anchor'],
            clean_vs_actual_bank=reference['reference_vs_actual_bank'],
            source_origin_vs_clean=reference['source_original_vs_anchor'],
            pre_all_vs_clean=reference['pre_all_vs_anchor'],
            current_vs_actual_bank=reference['current_vs_actual_bank'],
            score=score_summary(score,observation)))
    active=next((e for e in events if e['id']==transaction.get('active_event')),None)
    active_roles=(set(active['member_sources'])|{active['group_source']}|
                  {int(n) for n in active.get('post_first_observations',{})}) if active else set()
    correct=[c for c in candidates if c['eligible'] and c['current_vs_clean']=='SAME']
    certified=[c for c in correct if c['clean_vs_actual_bank']=='SAME' and c['source_origin_vs_clean']=='SAME']
    selected_candidate=next((c for c in candidates if c['public']==query['selected_target'] and
                            c['source']==(query.get('selected_candidate') or {}).get('source')),None)
    selected_score=((selection or {}).get('candidates',{}).get((selection or {}).get('selected')) or {})
    return dict(segment=segment,arm=row['arm'],frame=row['frame'],global_frame=row['global_frame'],source=query['source'],
        status=query['status'],selection_reason=(selection or {}).get('reason'),
        actual_first_public_id=query['actual_first_public_id'],selected_target=query['selected_target'],
        stage_error=query.get('stage_error'),group_blocked=row['group_blocked'],
        active_event=transaction.get('active_event'),query_in_active_event_roles=(query['source'] in active_roles) if active else False,
        active_event_member_sources=active['member_sources'] if active else [],
        active_event_group_source=active['group_source'] if active else None,
        active_event_post_sources=sorted(int(n) for n in active.get('post_first_observations',{})) if active else [],
        current=dict(quality=observation['quality'],area=observation['area'],neighbors=observation['neighbors'],
            observation_class=observation['observation_class'],
            unique_RGB_reference=audit['post_match']['status']=='UNIQUE_IOU_MATCH'),
        certificate=certificate_summary(query.get('contact_certificate')),
        admission_body_sha256=query.get('admission_body_sha256'),
        physical=audit['physical'],first_public_physical=audit['first_public_physical'],
        certified_physical_restore_qualification=audit['certified_physical_restore_qualification'],
        selected_current_vs_clean=audit['anchor_current_relation'],
        selected_clean_vs_actual_bank=audit['reference_vs_actual_bank'],
        selected_source_origin_vs_clean=audit['selected_source_origin_vs_clean'],
        eligible_same_clean_candidates=len(correct),eligible_same_clean_bank_origin_candidates=len(certified),
        best=(selection or {}).get('best'),selected=(selection or {}).get('selected'),
        runner_up=(selection or {}).get('runner_up'),margin=(selection or {}).get('margin'),
        best_vs_NEW_margin=(selection or {}).get('best_vs_new_margin'),
        minimum_log_odds=(selection or {}).get('minimum_log_odds'),
        depth_used=(selection or {}).get('depth_used'),common_query_depth_uninformative=(selection or {}).get('all_candidate_query_depth_common_uninformative'),
        background_method=((selection or {}).get('background',{}).get('depth') or {}).get('method'),
        background_component_count=((selection or {}).get('background',{}).get('depth') or {}).get('component_count'),
        best_geometry_log_lr=((selection or {}).get('candidates',{}).get((selection or {}).get('best')) or {}).get('geometry_log_lr'),
        best_depth_log_lr=((selection or {}).get('candidates',{}).get((selection or {}).get('best')) or {}).get('depth_log_lr'),
        dummy_score=score_summary((selection or {}).get('candidates',{}).get('NEW'),observation),
        selected_score=score_summary(selected_score,observation) if selected_score else None,
        candidates=candidates,selected_candidate=selected_candidate,
        physical_surface_identity='UNKNOWN',physical_depth_accuracy_mm='UNKNOWN')


def aggregate(cases):
    scored=[c for c in cases if c['best'] is not None]
    contact=[c for c in cases if c['current']['neighbors']]
    eligible_correct=[c for c in cases if c['eligible_same_clean_candidates']]
    scores=[candidate['score'] for c in cases for candidate in c['candidates'] if candidate['score']]
    return dict(noninitial_queries=len(cases),status_histogram=histogram(c['status'] for c in cases),
        selection_reason_histogram=histogram(c['selection_reason'] for c in cases),
        current_unique_reference=sum(c['current']['unique_RGB_reference'] for c in cases),
        current_contact_queries=len(contact),current_quality_false=sum(not c['current']['quality'] for c in cases),
        current_area_below_64=sum(c['current']['area']<64 for c in cases),
        certificate_eligible=sum(bool(c['certificate'] and c['certificate']['eligible']) for c in cases),
        certificate_piece_count_histogram=histogram(c['certificate']['qualified_component_count'] if c['certificate'] else None for c in cases),
        contact_reaching_selector=sum(c['best'] is not None for c in contact),
        contact_depth_used=sum(c['depth_used'] is True for c in contact),
        contact_blocked_by_active_group=sum(c['group_blocked'] for c in contact),
        group_blocked_outside_event_roles=sum(c['group_blocked'] and not c['query_in_active_event_roles'] for c in cases),
        eligible_same_clean_queries=len(eligible_correct),
        eligible_same_clean_bank_origin_queries=sum(bool(c['eligible_same_clean_bank_origin_candidates']) for c in cases),
        eligible_same_clean_status_histogram=histogram(c['status'] for c in eligible_correct),
        eligible_same_clean_reason_histogram=histogram(c['selection_reason'] for c in eligible_correct),
        eligible_same_clean_with_certificate=sum(bool(c['certificate'] and c['certificate']['eligible']) for c in eligible_correct),
        current_depth_common_uninformative=sum(c['common_query_depth_uninformative'] is True for c in scored),
        background_method_histogram=histogram(c['background_method'] for c in scored),
        candidate_exclusion_reason_histogram=histogram(reason for c in cases for k in c['candidates'] for reason in k['reasons']),
        candidate_eligibility_histogram=histogram(str(k['eligible']) for c in cases for k in c['candidates']),
        scored_candidates=len(scores),geometry_gap_seconds=distribution(s['geometry']['actual_gap_seconds'] for s in scores),
        geometry_growth=distribution(s['geometry']['growth_factor'] for s in scores),
        geometry_history_span_seconds=distribution(s['geometry']['real_pre_span_seconds'] for s in scores),
        geometry_residual_rms_px=distribution(s['geometry']['next_step_residual_rms_px'] for s in scores),
        depth_forecast_scale_mm=distribution(s['depth']['forecast_scale_mm'] for s in scores),
        geometry_lr=distribution(s['geometry_log_lr'] for s in scores),depth_lr=distribution(s['depth_log_lr'] for s in scores),
        commit_physical_histogram=histogram(c['physical'] for c in cases if c['status']=='COMMIT'),
        commit_identity_qualification_histogram=histogram(c['certified_physical_restore_qualification'] for c in cases if c['status']=='COMMIT'),
        stage_failure_histogram=histogram(c['stage_error'] for c in cases if c['stage_error']))


def predictions_only():
    """Sealed measurements/actions only. Never open a scoring or identity audit."""
    assert (RUN/'ALL_PREDICTIONS_SEALED.json').is_file() and (RUN/'ACCESS_SEALED.json').is_file()
    seal=read(RUN/'ALL_PREDICTIONS_SEALED.json')
    bindings=[artifact(RUN/'ALL_PREDICTIONS_SEALED.json'),artifact(RUN/'ACCESS_SEALED.json')]
    census={arm:[] for arm in ARMS[2:]};commits=[]
    for segment in SEGMENTS:
        public=RUN/segment/'public'
        assert seal['seals'][segment]==sha(public/'PREDICTIONS_SEALED.json')
        local=read(public/'PREDICTIONS_SEALED.json')
        assert local['artifacts_sha256']['BIRTHS.jsonl.gz']==sha(public/'BIRTHS.jsonl.gz')
        bindings.append(artifact(public/'BIRTHS.jsonl.gz'))
        for row in rows(public/'BIRTHS.jsonl.gz'):
            if row['arm'] not in ARMS[2:] or row['frame']==1:continue
            for q in row['queries']:
                d=q.get('selection') or {}
                census[row['arm']].append(dict(frame=row['frame'],global_frame=row['global_frame'],source=q['source'],
                    status=q['status'],reason=d.get('reason'),depth_used=d.get('depth_used'),
                    eligible_candidates=sum(c['eligible'] for c in q['candidates']),
                    qualified_current_components=(q.get('contact_certificate') or {}).get('qualified_component_count'),
                    neighbors=q['query_observation']['neighbors']))
                if q['status']!='COMMIT':continue
                scores={label:score_summary(score,q['query_observation']) for label,score in d['candidates'].items()}
                commits.append(dict(segment=segment,arm=row['arm'],frame=row['frame'],global_frame=row['global_frame'],
                    source=q['source'],selected_target=q['selected_target'],actual_first_public_id=q['actual_first_public_id'],
                    status=q['status'],selection_reason=d['reason'],best=d['best'],runner_up=d['runner_up'],
                    margin=d['margin'],minimum_log_odds=d['minimum_log_odds'],best_vs_NEW_margin=d['best_vs_new_margin'],
                    current=dict(quality=q['query_observation']['quality'],area=q['query_observation']['area'],
                        neighbors=q['query_observation']['neighbors'],observation_class=q['query_observation']['observation_class']),
                    certificate=certificate_summary(q.get('contact_certificate')),scores=scores,
                    all_candidate_eligibility=[dict(source=c['source'],public=c['public'],eligible=c['eligible'],reasons=c['reasons']) for c in q['candidates']],
                    background=d['background'],admission_body_sha256=q['admission_body_sha256'],
                    physical_identity_outcome='NOT_READ_PENDING_SCORING_SEAL'))
    output=dict(status='SEALED_PREDICTION_ONLY_NO_IDENTITY_AUDIT',input_bindings=bindings,
        new_GT_files_read=0,scoring_artifacts_read=0,new_replay_runs=0,HTTP_calls=0,
        summaries={arm:dict(queries=len(c),statuses=histogram(x['status'] for x in c),
            reasons=histogram(x['reason'] for x in c),depth_used=sum(x['depth_used'] is True for x in c),
            commits=sum(x['status']=='COMMIT' for x in c)) for arm,c in census.items()},
        all_noninitial_query_exposure=census,actual_commits=commits)
    write_new(HERE/'PREDICTION_COMPONENT_EXPOSURE.json',output)
    print(json.dumps(dict(status=output['status'],summaries=output['summaries'],actual_commits=commits),ensure_ascii=False))


def enrich_review():
    """Interpret the complete generated census; this does not rerun any decision."""
    path=HERE/'POSTRUN_COMPONENT_REVIEW.json';report=read(path)
    seal=read(RUN/'SCORING_SEALED.json')
    assert sha(RUN/'BIRTH_AUDIT.json')==seal['artifacts_sha256']['BIRTH_AUDIT.json']
    audit=read(RUN/'BIRTH_AUDIT.json')
    raw=[c for c in report['all_noninitial_queries'] if c['arm']=='R12_RAW']
    rates=('IDF1','HOTA','AssA','IDSW','FP','FN')
    report['metric_deltas']={arm:{baseline:{key:report['pooled_metrics'][arm][key]-report['pooled_metrics'][baseline][key]
        for key in rates} for baseline in ('SAM3_NATIVE','F9_RESTORED')} for arm in ARMS[2:]}
    report['depth_support_counts']={}
    for arm in ARMS[2:]:
        scored=[p for c in report['all_noninitial_queries'] if c['arm']==arm for p in c['candidates'] if p['score']]
        same=[p for p in scored if p['current_vs_clean']=='SAME']
        report['depth_support_counts'][arm]=dict(scored_old_candidates=len(scored),
            positive=sum(p['score']['depth_log_lr']>0 for p in scored),
            negative=sum(p['score']['depth_log_lr']<0 for p in scored),
            common_zero=sum(p['score']['depth_log_lr']==0 for p in scored),
            same_clean_scored_candidates=len(same),same_clean_positive_depth=sum(p['score']['depth_log_lr']>0 for p in same))
    successful=[]
    for c in report['all_noninitial_queries']:
        if c['status']!='COMMIT':continue
        reference=next(q for q in audit['queries'] if q['segment']==c['segment'] and q['arm']==c['arm']
                       and q['frame']==c['frame'] and q['source']==c['source'])
        selected=next(r for r in reference['candidate_references'] if r['source']==c['selected_candidate']['source']
                      and r['public']==c['selected_target'])
        successful.append(dict(global_frame=c['global_frame'],source=c['source'],target=c['selected_target'],arm=c['arm'],
            current_RGB_match=reference['post_match'],clean_RGB_match=reference['anchor_match'],
            bank_RGB_match=reference['actual_bank_anchor_match'],origin_RGB_match=selected['original_source_reference'],
            original_source_first_local_frame=selected['original_source_first_frame'],pre_all_vs_clean=selected['pre_all_vs_anchor'],
            certified_physical_restore_qualification=c['certified_physical_restore_qualification'],
            geometry_log_lr=c['best_geometry_log_lr'],depth_log_lr=c['best_depth_log_lr'],margin=c['margin'],
            interpretation='ACTUAL_NEW_CORRECT_BIRTH_RESTORE; NOT_METRIC_DEPTH_OR_SURFACE_CALIBRATION'))
    report['successful_birth_details']=successful
    explanations={
        486:'旧22在几何和联合分数上领先且超过log9，但深度LR为负。当前143点的合格片不等于旧身份深度必然更可能；共同当前对象null比该历史预测密度略高。按冻结positive-depth合同保留NEW，没有事务拒绝。',
        746:'旧70是最佳且深度LR为正，联合优势1.719965仍低于log9=2.197225。当前合格片246点、MAD8.929；另一个1点片保留而不评分。非缺测、非group、非stage失败。',
        1043:'旧108最佳，两个真实片51/60点以.5/.5混合；深度LR+.394445，但几何LR1.329366使联合1.723811仍不足。原片全部保留，未按旧候选挑较近片。',
        961:'旧106的同鱼清洁历史仍合格，但真实gap7.277s相对.166s历史窗造成growth1922.710，forecast scale657.902mm；虽当前片145点、MAD10.167，宽历史密度低于当前对象null，depthLR−1.598247而NEW最佳。它说明既有不确定性增长限制远期重接，不能据此收窄scale或承诺提点。',
        1000:'旧68在clean末端与当前query同鱼，但其actual bank与源首次出现均和clean不同。运行时同版本不认证物理身份连续；不是可安全重接的已知正确遗漏。NEW保持，禁止用posthoc身份参考回写规则。'}
    failures=[]
    for frame,explanation in explanations.items():
        c=next(c for c in raw if c['global_frame']==frame)
        correct=[p for p in c['candidates'] if p['eligible'] and p['current_vs_clean']=='SAME']
        failures.append(dict(global_frame=frame,source=c['source'],status=c['status'],reason=c['selection_reason'],
            best=c['best'],margin=c['margin'],qualified_components=[p for p in c['certificate']['components'] if p['qualified']],
            same_clean_candidates=correct,explanation=explanation,
            selection_basis='POSTHOC_COVERAGE_OF_DISTINCT_OBSERVED_FAILURE_MECHANISMS; NOT_RUNTIME_SAMPLE_SELECTION'))
    report['illustrative_failures_all_query_census_retained']=failures
    report['layered_conclusion']=dict(
        engineering='All sealed prediction/scoring inputs verified; contact observations retained risk/neighbors; only one actual birth commit per arm and no stage veto.',
        development_gain='One RGB-reference-certified new birth recovery at F1886, 21 changed publications; all three pooled identity rates improve over same-source native and IDSW108->105, with one switch increment beyond frozen F9.',
        depth_role='Contact depth evidence now actually reaches 52 of 58 scored queries; F1886 depth LR is positive and shares fixed fragments across all candidates. Its geometry contribution already exceeds log9, so a unique necessity of depth correspondence is not isolated.',
        restored_role='Raw and retained make identical decisions/publications. F1886 component statistics and foreground are identical; their LR difference comes from current background. No restored-depth incremental tracking gain is observed.',
        limitations='Only one new birth success in the already exposed development segments. RGB identity qualification does not certify sensor surface, registration, millimeter accuracy or calibrated posterior; no generalization claim.')
    report['next_step']=dict(status='PROPOSED_NOT_AUTOMATICALLY_STARTED',mechanism='UNCHANGED_FROZEN_R12_RAW_VALIDATION',
        rationale='A real new correct birth recovery and native metric gain now exist, but only one event; evidence supports testing reproducibility before another selector change.',
        cohort='A full predeclared continuous development interval with no frame overlap with these four segments; chosen by temporal/source availability, never by GT or recovery events.',
        controls=['SAME_SOURCE_SAM3_NATIVE','F9_RESTORED_ATTRIBUTION_CONTROL','FROZEN_R12_RAW'],
        frozen_constraints=['No change to current certificate/piece mixture, raw-only historical qualification, native/group/occupied/alias guards, priors/NEW, log9 or positive-depth gate.',
            'Use all frames and every first-ever birth/event, seal predictions before independent identity audit.',
            'No threshold search or positive-case selection; no GT fed into decisions; no API, training or SAM3 rerun.'],
        report='Compare actual IDF1/HOTA/AssA/IDSW/FP/FN to native and all correct/wrong/UNKNOWN birth actions; F9 identifies previously existing group effects, without a pure-geometry promotion gate.',
        falsifiable='If no new correct birth or no native-rate improvement appears, retain that result as failure/nonreplication; do not silently retune or start a second mechanism.',
        expected_gain='UNKNOWN_NOT_PROMISED',physical_surface_identity='UNKNOWN')
    with path.open('w',encoding='utf-8',newline='\n') as f:
        json.dump(report,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
    markdown=HERE/'POSTRUN_COMPONENT_REVIEW.md'
    existing=markdown.read_text(encoding='utf-8')
    appendix=existing[existing.index('## 完整出生状态表'):]
    appendix=appendix.replace('下一步候选须在实际结果复核后填写；本工具不预写增益结论或自动启动下一版本。',
        '本轮未读取新GT文件、未回放控制器、未改冻结参数或追加实验。全部210个非首帧出生记录及候选统计见JSON。')
    intro='''# DS12 独立全量组件与出生关联复盘

## 结论与范围

本轮接触独占测量路径产生了一个真实新增且正确的出生重接：F1886，n198→public176。它消除一个原生身份切换，并保持到本段末尾，共改变21帧21条身份发布。R12_RAW和R12_RESTORED输出完全相同。这个已曝光开发范围内观察到增益；一个事件不足以证明泛化、物理深度准确性或恢复深度优于原始深度。

所有分析来自双封存后的预测、事务、评分和身份审计。先前预测侧曝光记录没有读取GT；本报告没有新打开GT文件，也没有重跑选择器或控制器。没有修改任何冻结源码、门槛、预测或seal。

| 分支 | IDF1 | HOTA | AssA | IDSW | FP/FN |
|---|---:|---:|---:|---:|---|
| same-source native | 80.97675951 | 79.96405590 | 71.53049876 | 108 | 487/985 |
| 冻结F9 | 80.97675951 | 80.01204932 | 71.61576345 | 106 | 487/985 |
| R12 raw/retained | 81.02998201 | 80.04715892 | 71.67787189 | 105 | 487/985 |

相对native，IDF1 +0.05322250、HOTA +0.08310302、AssA +0.14737313，IDSW −3。F1239与F1745的两个切换减少来自已冻结F9组恢复；本轮新增出生机制只消除F1886的176→198，没有新增切换。相对F9，IDF1 +0.05322250、HOTA +0.03510960、AssA +0.06210844，IDSW −1。mask集合、检测数、FP/FN保持一致。

## 全部出生机会和失效层次

每支105个非首帧first-ever出生：47个活动组阻断，58个实际进入selector。其中55个有真实neighbors；50个接触query获得合法深度机会，另2个清洁query有深度，合计52。每支最终1个COMMIT、57个KEEP_NATIVE；没有stage veto、目标冲突或批容量拒绝。

58个数值决定包含35个NEW最佳、11个最佳旧候选深度支持非正、5个联合优势不足、3个接触证书无信息、2个当前quality/area不合格、1个清洁当前深度缺失、1个接受。原始证书92/105合格，retained89/105；这包含活动组内事实，不能当成92或89个实际可提交机会。全部不合格片和未知保留。活动组阻断中39个query在该事件member/group/post源集合之外；本合同仍按整活动帧阻断，不越过保护银行或占用关系。

后验RGB审计中26个query有至少一个运行时合格同鱼clean历史：12个组阻断、1个正确提交、13个未提交（7 NEW最佳、3非正深度、3联合不足）。25个query另满足clean/bank/source-origin同身份，F1000是历史物理身份漂移，单独列。两个分支同样覆盖。163个实际评分旧候选中，深度LR为正9个、为负152个、共同零2个；15个同鱼clean候选中正支持4个（F746、F1043、F1671、F1886）。因此当前采样准入问题已显著减少，瓶颈转为历史/当前预测密度与NEW竞争、组保护和物理身份未认证。

## F1886：实际正确提交，而非影子提案

query原SAM面积388，neighbors[157]保留。真实core分成两片：28/34点、median1142.852661、MAD7.947266；45/54点、median1148.069458、MAD7.514526。两片各权重.5、sigma15mm；并非按候选选较近片。NEW与旧public125/149/176/177/178共6个唯一假设，各prior=−log6。

旧176的10点raw认证历史末端为local657/global1857，真实gap0.964s、历史窗0.299s。geometry residual RMS1.422px，增长11.39469，当前到预测均值19.236px；depth local-level均值1154.723572、scale52.809143mm。raw geometry LR3.816346，depth LR0.235869，最佳对NEW margin4.052215>log9=2.197225，旧125/149/177/178的depth LR均为负。retained margin4.097925，depth LR0.281580；signal和片统计相同，差别是共同null的logdensity −5.264316/raw、−5.313851/retained。

封存RGB身份：query GT4、IoU0.876777；clean与actual bank都在local657并匹配GT4、IoU0.922078；源176首次出现local243/global1443也匹配GT4，所有clean pre点同身份。这是已实现的正确bank恢复，actual n198→176发布在F1886–1906持续21帧。逐帧发布差异是实际日志事实；RGB身份审计仍不认证两个深度片的物理鱼体表面。

几何LR本身已超过log9；本轮深度为正的当前支持及旧候选抑制参与真实合同，但没有隔离深度对应关系的唯一必要贡献。这一限制不改变观察到的native跟踪增益，也不另设纯几何晋级门。

## 五个有同鱼合格历史却未提交的案例

这些例子覆盖不同已观察机制。所有210个query仍完整保留，案例不构成新规则或GT选样。

| 帧/source→同鱼clean旧public | 实测当前片 n / median / MAD | geometry LR | depth LR | 真实决定原因 |
|---|---|---:|---:|---|
| F486 /83→22 | 143 /1131.687 /13.718 | 2.681562 | −0.195493 | 联合对NEW 2.486069已过9，但positive-depth门未过 |
| F746 /117→70 | 246 /939.604 /8.929；另1点片不合格保留 | 1.568785 | +0.151180 | 联合1.719965，最佳正确但不足9 |
| F1043 /143→108 | 51 /1180.539 /9.939、60 /1163.901 /8.261，等权 | 1.329366 | +0.394445 | 联合1.723811，最佳正确但不足9 |
| F961 /131→106 | 145 /1190.118 /10.167；3/1点副片保留 | 0.153492 | −1.598247 | 宽历史密度低于当前null，NEW最佳 |
| F1000 /137→68 | 124 /1152.315 /11.757；13/1点副片保留 | −0.024505 | −0.904346 | NEW最佳；clean同鱼但bank/origin不同身份 |

F486有6个clean历史点，gap0.864s/span0.166s，forecast μ1171.642/scale81.317。当前合格测量只是来源与精度代理：前景logdensity −5.547647低于null −5.327872，因此LR负。这里没有缺测、组阻断或事务失败；降低positive-depth门可能同样增加错误，现有结果不授权调它。

F746的gap1.296s/span0.199s，forecast μ1013.398/scale100.583；F1043的gap1.163s/span0.299s、μ1188.891/scale62.081。两者已真实得到正深度支持，但1s均值cap、实际位置残差与联合优势只支持保留NEW。不能把正确GT答案作为降log9或收尺度的依据。

F961的6点历史窗0.166s却跨7.277s完整风险/缺失gap，几何增长1922.710、forecast scale657.902mm。历史均值1149.397离当前1190.118仅约40.7mm，仍因归一化密度尺度很宽而depth LR负：前景−7.472539，null−5.297573。全163个旧候选gap中位6.414s、history span中位0.199s、depth scale中位443.986mm；过去微小next-step残差不能证明远期物理身份或允许收窄不确定性。

F1000的public68原始身份与实际bank不同于当前clean参考，尽管运行时generation/epoch一致。它属于源/银行语义漂移风险，不能计为一个“只要放宽门就能正确恢复”的漏例，也不能用后验身份把public68重新认证。

## 唯一下一步：冻结R12_RAW做独立非重叠验证

当前已有一个新的正确出生恢复与三项native身份指标增益，最有证据的下一步是验证这条已冻结方法能否复现。保留当前R12_RAW源码和全部常量，选择一个与本轮四段无帧重叠的完整、预先声明的开发时间片段，选段只依据时间及输入可用性，不依据GT或有无可救事件。保留same-source native主比较、冻结F9用于分开原有组恢复贡献，完整跑全部帧/first-ever出生/组事件。

不修改触发、窗口、raw历史资格、component等权、NEW/null/priors、log9/positive-depth、alias/occupied/group/原子guards。不增加第二机制或阈值搜索。预测先封存，再独立评价所有正确、错误、UNKNOWN和漏例；报告IDF1/HOTA/AssA/IDSW/FP/FN及新恢复。若未复现增益，保留该结果并明确失败/不可复现，不隐式调参重试。仅提出验证，不自动启动；预期增益UNKNOWN。无API、训练或重跑SAM3。

## 边界

本轮四段曾被反复诊断，属于曝光开发数据；一个正确新增恢复不是跨场景或未调参验证成绩。retained与raw同输出，不支持恢复深度增量优势。当前query-inclusive共同null是一种归一化plug-in对比；共同减法项在候选间抵消，但 .9f+.1b 内的b一般不完全抵消。RGB参考、源字节/索引哈希、pixel独占与统计资格均不认证物理表面、配准、毫米精度或校准身份后验。

'''
    with markdown.open('w',encoding='utf-8',newline='\n') as f:f.write(intro+appendix)
    print(json.dumps(dict(status='PASS',outputs=[artifact(path),artifact(markdown)],
        illustrative_failure_frames=list(explanations),next_step=report['next_step']['mechanism']),ensure_ascii=False))


def main():
    # Fail before opening any new identity/reference audit unless BOTH seals exist.
    assert (RUN/'ALL_PREDICTIONS_SEALED.json').is_file()
    assert (RUN/'SCORING_SEALED.json').is_file()
    all_seal=read(RUN/'ALL_PREDICTIONS_SEALED.json');scoring=read(RUN/'SCORING_SEALED.json')
    assert scoring['all_prediction_seal_sha256']==sha(RUN/'ALL_PREDICTIONS_SEALED.json')
    for filename,digest in scoring['artifacts_sha256'].items():assert sha(RUN/filename)==digest
    audit=read(RUN/'BIRTH_AUDIT.json');metrics=read(RUN/'METRICS.json');switches=read(RUN/'SWITCH_LEDGER.json')
    references={(x['segment'],x['arm'],x['frame'],x['source']):x for x in audit['queries']}
    cases=[];initial=Counter();bindings=[artifact(RUN/p) for p in
        ('ALL_PREDICTIONS_SEALED.json','SCORING_SEALED.json','BIRTH_AUDIT.json','METRICS.json','SWITCH_LEDGER.json','EVENT_AUDIT.json')]
    arithmetic_checks=0;prediction_differences={a:dict(frames=0,objects=0) for a in ARMS[2:]}
    differing_publications={a:[] for a in ARMS[2:]}
    for segment in SEGMENTS:
        public=RUN/segment/'public'
        assert all_seal['seals'][segment]==sha(public/'PREDICTIONS_SEALED.json')
        seal=read(public/'PREDICTIONS_SEALED.json')
        for name in ('BIRTHS.jsonl.gz','TRANSACTIONS.jsonl.gz','EVENTS.json','predictions.jsonl.gz','CONTACT_CERTIFICATES.jsonl.gz'):
            assert seal['artifacts_sha256'][name]==sha(public/name)
            bindings.append(artifact(public/name))
        tx={(r['frame'],r['arm']):r for r in rows(public/'TRANSACTIONS.jsonl.gz')}
        events=read(public/'EVENTS.json')
        for row in rows(public/'BIRTHS.jsonl.gz'):
            if row['arm'] not in ARMS[2:]:continue
            for query in row['queries']:
                if row['frame']==1:initial[row['arm']]+=1;continue
                key=(segment,row['arm'],row['frame'],query['source'])
                cases.append(case_summary(segment,row,query,references[key],events[row['arm']],tx[(row['frame'],row['arm'])]))
                selection=query.get('selection')
                if selection:
                    for candidate in selection['candidates'].values():
                        assert math.isclose(candidate['log_score'],candidate['log_prior']+candidate['geometry_log_lr']+candidate['depth_log_lr'],abs_tol=1e-12)
                        arithmetic_checks+=1
                    assert math.isclose(sum(c['posterior'] for c in selection['candidates'].values()),1.,abs_tol=1e-12)
        for prediction in rows(public/'predictions.jsonl.gz'):
            baseline={x['mask']:x['id'] for x in prediction['variants']['F9_RESTORED']}
            for arm in ARMS[2:]:
                actual={x['mask']:x['id'] for x in prediction['variants'][arm]}
                assert set(actual)==set(baseline) and len(actual)==len(set(actual.values()))
                changed=sum(actual[k]!=baseline[k] for k in actual)
                prediction_differences[arm]['frames']+=bool(changed)
                prediction_differences[arm]['objects']+=changed
                differing_publications[arm].extend(dict(segment=segment,frame=prediction['frame'],
                    global_frame=prediction['global_frame'],source=int(k[2:]),
                    actual_public=actual[k],F9_public=baseline[k]) for k in actual if actual[k]!=baseline[k])
    summaries={arm:aggregate([c for c in cases if c['arm']==arm]) for arm in ARMS[2:]}
    paired={}
    for c in cases:paired.setdefault((c['segment'],c['frame'],c['source']),{})[c['arm']]=c
    arm_differences=[]
    for key,pair in paired.items():
        a,b=(pair[arm] for arm in ARMS[2:])
        keys=('status','selected_target','actual_first_public_id','selection_reason','best','depth_used')
        differences={k:{ARMS[2]:a[k],ARMS[3]:b[k]} for k in keys if a[k]!=b[k]}
        if differences:arm_differences.append(dict(segment=key[0],frame=key[1],source=key[2],global_frame=a['global_frame'],differences=differences))
    publication_intervals={arm:[] for arm in ARMS[2:]}
    for arm,points in differing_publications.items():
        grouped={}
        for point in points:
            key=(point['segment'],point['source'],point['actual_public'],point['F9_public'])
            grouped.setdefault(key,[]).append(point)
        for key,group in grouped.items():
            interval=None
            for point in group:
                if interval and point['frame']==interval['last_frame']+1:
                    interval.update(last_frame=point['frame'],last_global_frame=point['global_frame'],frames=interval['frames']+1)
                else:
                    interval=dict(segment=key[0],source=key[1],actual_public=key[2],F9_public=key[3],
                        first_frame=point['frame'],last_frame=point['frame'],first_global_frame=point['global_frame'],
                        last_global_frame=point['global_frame'],frames=1)
                    publication_intervals[arm].append(interval)
    def switch_key(event):return (event['segment'],event['frame'],event['gt_id'],event['native_mask'])
    native_switches={switch_key(e):e for e in switches['events']['SAM3_NATIVE']}
    f9_switches={switch_key(e):e for e in switches['events']['F9_RESTORED']}
    switch_changes={}
    for arm in ARMS[2:]:
        actual={switch_key(e):e for e in switches['events'][arm]}
        switch_changes[arm]=dict(
            new_vs_native=[e for k,e in actual.items() if k not in native_switches],
            eliminated_vs_native=[e for k,e in native_switches.items() if k not in actual],
            new_vs_F9=[e for k,e in actual.items() if k not in f9_switches],
            eliminated_vs_F9=[e for k,e in f9_switches.items() if k not in actual],
            comparison_unit='SEALED_CLEAR_SWITCH_AT_SAME_SEGMENT_FRAME_GT_NATIVE_MASK; NOT_AN_ORACLE_RECOVERY_SCORE')
    report=dict(status='POSTSEAL_INDEPENDENT_READONLY_COMPONENT_REVIEW',new_gt_files_opened=0,
        new_replay_runs=0,frozen_rule_changes=0,HTTP_calls=0,source_bindings=bindings,
        arithmetic_score_identity_checks=arithmetic_checks,initial_frame_queries=dict(initial),summaries=summaries,
        pooled_metrics=metrics['pooled_metrics'],segment_metrics=metrics['segment_metrics'],
        prediction_differences_vs_F9=prediction_differences,raw_retained_status_choice_differences=arm_differences,
        actual_publication_difference_intervals_vs_F9=publication_intervals,switch_changes=switch_changes,
        physical_reference_scope='POSTSEAL_RGB_IDENTITY_ONLY; SENSOR_SURFACE_AND_METRIC_DEPTH_UNKNOWN',
        all_noninitial_queries=cases,
        switch_counts={arm:len(switches['events'][arm]) for arm in ARMS},
        interpretation_limits=['Current component lineage/quality never certifies fish or background.',
            'Same-version raw history can contain physically changed source identity; origin/clean/bank are separate.',
            'The common subtractive null cancels between old candidates, but its .1 mixture floor does not generally cancel.',
            'A wrong or correct RGB endpoint match is not physical millimeter or RGB-D surface calibration.',
            'Posthoc same-reference coverage is not an oracle performance estimate or a new trigger.'])
    write_new(HERE/'POSTRUN_COMPONENT_REVIEW.json',report)
    lines=['# DS12 独立全量组件与出生关联复盘','',
        '仅分析已封存运行与评分记录；不读取新 GT 文件，不回放控制器，不改变选择规则。', '',
        '## 全量机会与实际结果','',
        '| 分支 | 非首帧出生 | 接触进入评分 | 接触深度可用 | COMMIT | 正确/错误/未知 |',
        '|---|---:|---:|---:|---:|---|']
    for arm,s in summaries.items():
        lines.append(f"| {arm} | {s['noninitial_queries']} | {s['contact_reaching_selector']} | {s['contact_depth_used']} | {s['status_histogram'].get('COMMIT',0)} | {s['commit_physical_histogram']} |")
    lines+=['','## 完整出生状态表','',
        '| 原帧 | source | 分支 | 状态/原因 | 最佳 | margin | 正确旧候选数 | 当前合格片 | clean/bank/origin 资格 |',
        '|---:|---:|---|---|---|---:|---:|---:|---|']
    for c in cases:
        lines.append(f"| {c['global_frame']} | {c['source']} | {c['arm']} | {c['status']} / {c['selection_reason']} | {c['best']} | {c['margin'] if c['margin'] is not None else '—'} | {c['eligible_same_clean_candidates']} | {(c['certificate'] or {}).get('qualified_component_count','—')} | {c['certified_physical_restore_qualification']} |")
    lines+=['','## 证据边界','',
        '接触证书证明实际当前像素来源、独占及统计资格。它不证明片段属于鱼体，也不证明 RGB-D 配准、物理深度准确性或跨风险身份连续性。全部原邻居、匿名风险和不合格片都保留。',
        '', '逐候选几何残差、完整 gap 放大、历史深度尺度、共同 null 和混合密度记录见 JSON。评分减去的共同 null 在候选间抵消，但 .9 signal + .1 background 中的背景一般不会完全抵消。', '',
        '下一步候选须在实际结果复核后填写；本工具不预写增益结论或自动启动下一版本。','']
    target=HERE/'POSTRUN_COMPONENT_REVIEW.md'
    with target.open('x',encoding='utf-8',newline='\n') as f:f.write('\n'.join(lines))
    print(json.dumps(dict(status='PASS',cases=len(cases),summaries=summaries,outputs=[artifact(HERE/'POSTRUN_COMPONENT_REVIEW.json'),artifact(target)]),ensure_ascii=False))


if __name__=='__main__':
    if '--predictions-only' in sys.argv:predictions_only()
    elif '--enrich' in sys.argv:enrich_review()
    else:main()
