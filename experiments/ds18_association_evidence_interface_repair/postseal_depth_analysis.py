"""Stream sealed public depth/state evidence; never open reference pixels or rerun a branch."""
import guard
from common import *
from collections import Counter, defaultdict
import math

FOCUS = ('ACTIVITY_ORDER', 'MIXED_ORDER', 'MIXED_OFF')
PAIRS = (('ACTIVITY_ORDER', 'MIXED_ORDER'), ('MIXED_ORDER', 'MIXED_OFF'))
ROIS = ('whole', 'birth_core', 'core')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def scalar_valid(stat, mad=True):
    return bool(stat.get('median') is not None and stat['median'] > 0 and stat['n'] >= 16 and
        stat['valid_fraction'] >= .2 and (not mad or stat.get('mad') is not None and max(15., 1.4826 * stat['mad']) <= 60.))


def binding_min(binding):
    if not binding:
        return None
    return {k: binding.get(k) for k in ('association_role', 'native', 'frame', 'global_frame', 'measurement_fact_id',
        'roi_definition', 'roi_binding', 'actual_scalar', 'eligible_single', 'measurement_valid', 'screened_eligible',
        'status', 'reason', 'source_version', 'version_key', 'identity_state', 'binding_sha256')}


def paired_min(pair):
    return dict(frame=pair['frame'], time=pair['time'], delta_B_minus_A_mm=pair['delta_B_minus_A_mm'],
        pair_scale_mm=pair['pair_scale_mm'], p_A_nearer=pair['p_A_nearer'],
        roles={role: {k: pair[role].get(k) for k in ('frame', 'fact_id', 'source_native', 'public', 'version_key',
            'z_mm', 'mad_mm', 'n', 'valid_fraction', 'core_usable')} for role in ('A', 'B')})


def order_min(row):
    detail, restore = row['detail'], row['restore']
    evidence = detail['order_evidence']
    candidates = {k: {key: c.get(key) for key in ('mapping', 'log_prior', 'geometry_log_lr', 'order_log_lr', 'log_score', 'order')}
                  for k, c in detail['candidates'].items()}
    # This is arithmetic on the stored candidate scores, not a new tracker run.
    ranked = sorted(candidates, key=lambda k: (-(candidates[k]['log_prior'] + candidates[k]['geometry_log_lr']), k != 'H0', k))
    margin = ((candidates[ranked[0]]['log_prior'] + candidates[ranked[0]]['geometry_log_lr']) -
              (candidates[ranked[1]]['log_prior'] + candidates[ranked[1]]['geometry_log_lr'])) if len(ranked) > 1 else None
    geometry_choice = ranked[0] if (evidence['eligible'] and len(ranked) > 1 and ranked[0] != 'H0' and
                                    margin >= detail['minimum_log_odds']) else 'H0'
    pre_pairs = [paired_min(p) for p in evidence['pre_pairs']]
    post = {key: {k: value.get(k) for k in ('observation_source', 'actual_state_source', 'assigned_depth_source',
        'assigned_measurement_fact_id', 'core')} for key, value in evidence['post_bindings'].items()}
    context = dict(baseline=detail['baseline_mapping'],
        candidates={k: {key: c[key] for key in ('mapping', 'log_prior', 'geometry_log_lr')} for k, c in candidates.items()},
        pre_pairs=[dict(frame=p['frame'], delta=p['delta_B_minus_A_mm'], scale=p['pair_scale_mm'],
            roles={r: dict(native=p['roles'][r]['source_native'], public=p['roles'][r]['public'],
                version=(p['roles'][r]['version_key'][2:] if p['roles'][r]['version_key'] else None),
                z_mm=p['roles'][r]['z_mm'], mad_mm=p['roles'][r]['mad_mm']) for r in ('A', 'B')}) for p in pre_pairs],
        post=post, eligible=evidence['eligible'], p_pre=evidence.get('p_A_nearer_at_q'))
    return dict(frame=row['frame'], global_frame=row['global_frame'], arm=row['arm'], event=row['event'],
        q=row['q'], selected_choice=row['selected_choice'], published_mapping=row['published_mapping'],
        restore={k: restore.get(k) for k in ('status', 'changes', 'stage_error', 'decision_source', 'baseline_preview_mapping')},
        reason=detail['reason'], eligible=evidence['eligible'], evidence_reason=evidence['reason'],
        p_A_nearer_at_q=evidence.get('p_A_nearer_at_q'), pre_scale_at_q_mm=evidence.get('pre_scale_at_q_mm'),
        last_delta_B_minus_A_mm=evidence.get('last_delta_B_minus_A_mm'),
        ordinal_changes_same_candidate_geometry_choice=(row['selected_choice'] != geometry_choice),
        same_candidate_geometry_diagnostic=dict(choice=geometry_choice, best=ranked[0], margin=margin,
            no_replay=True, no_new_prediction=True), candidates=candidates, pre_pairs=pre_pairs, post_bindings=post,
        source_geometry_context_sha256=digest(context))


def predictions(public):
    counts = {f'{a}__{b}': dict(frames_different=0, native_frame_differences=0, first=None, last=None, transitions=[]) for a,b in PAIRS}
    previous = {key: {} for key in counts}
    observed = 0
    for row in rows(public/'predictions.jsonl.gz'):
        maps = {a: {str(o['mask']): o['id'] for o in row['variants'][a]} for a in FOCUS}
        for a,b in PAIRS:
            key = f'{a}__{b}'
            assert set(maps[a]) == set(maps[b])
            difference = {n: [maps[a][n], maps[b][n]] for n in maps[a] if maps[a][n] != maps[b][n]}
            if difference:
                counts[key]['frames_different'] += 1
                counts[key]['native_frame_differences'] += len(difference)
                counts[key]['first'] = counts[key]['first'] or dict(frame=row['frame'], global_frame=row['global_frame'], mappings=difference)
                counts[key]['last'] = dict(frame=row['frame'], global_frame=row['global_frame'])
            if difference != previous[key]:
                counts[key]['transitions'].append(dict(frame=row['frame'], global_frame=row['global_frame'], changed_mapping=difference))
            previous[key] = difference
        observed += 1
    return counts, observed


def action_min(event):
    result = {k: event.get(k) for k in ('origin_rule','native_id','canonical_id','accepted','phase','birth_frame',
        'original_birth_frame','evaluation_frame','source_previously_published','pending_retry','old_anchor',
        'current_depth','history_depth','residual_mm','tolerance_mm','cost','current_depths','core','whole','required_whole_evidence')}
    evidence = event.get('association_evidence_bindings', {})
    if evidence:
        query = evidence.get('query')
        result['query_bindings'] = ({k: binding_min(v) for k,v in query.items()} if isinstance(query, dict) and 'association_role' not in query
                                    else binding_min(query))
        result['target_bindings'] = {k: binding_min(v.get('binding') if v else None) for k,v in evidence.get('target', {}).items()}
        target = evidence.get('target_anchor')
        if target:
            result['target_anchor_binding'] = binding_min(target.get('binding'))
    return result


def transactions(public, firsts):
    counters = {arm: dict(accepted=Counter(), durable=Counter(), birth_failures=Counter(), birth_required_whole=Counter(),
        d1_rejections=Counter(), pending_status=Counter(), rejected_candidate_failures=Counter()) for arm in FOCUS}
    actions = {arm: [] for arm in FOCUS}
    relevant_frames = {item['first']['frame'] for item in firsts.values() if item['first']}
    selected = []
    for row in rows(public/'TRANSACTIONS.jsonl.gz'):
        arm = row['arm']
        if arm not in FOCUS:
            continue
        trace, counter = row['controller_trace'], counters[arm]
        for item in row.get('automatic_candidate_events', []):
            event = item['event']
            counter['accepted'][event.get('origin_rule', 'UNKNOWN')] += 1
        for item in row.get('durable_automatic_commits', []):
            event = item['event']
            counter['durable'][event.get('origin_rule', 'UNKNOWN')] += 1
            actions[arm].append(dict(frame=row['frame'], global_frame=row['global_frame'], event=action_min(event)))
        for check in trace.get('birth_checks', []):
            counter['birth_failures'].update(check.get('failures', []))
            counter['birth_required_whole'][check.get('required_whole_evidence', {}).get('status', 'NOT_EVALUATED')] += 1
        for edge in trace.get('edges', []):
            counter['d1_rejections'][edge.get('rejection') or 'ADMITTED'] += 1
            counter['rejected_candidate_failures'].update(edge.get('edge_veto', {}).get('reasons', []))
        for item in trace.get('pending_birth', {}).values():
            counter['pending_status'][item.get('status', 'UNKNOWN')] += 1
        if row['frame'] in relevant_frames:
            selected.append(dict(frame=row['frame'],global_frame=row['global_frame'],arm=arm,
                signal=row.get('signal'), published=row['actual_published_mapping'],previous=row.get('previous_mapping'),
                alias_targets=row['actual_alias_targets'], restore=row.get('restore'),
                accepted=[action_min(x['event']) for x in row.get('automatic_candidate_events', [])],
                durable=[action_min(x['event']) for x in row.get('durable_automatic_commits', [])],
                birth_checks=[dict(native=c.get('native_id'),target=c.get('canonical_id'),failures=c.get('failures'),
                    rejection=c.get('rejection'),required_whole=c.get('required_whole_evidence'),core=c.get('core'),whole=c.get('whole'),
                    current_depths=c.get('current_depths'),old_anchor=c.get('old_anchor')) for c in trace.get('birth_checks', [])],
                edges=[{k:c.get(k) for k in ('native_id','canonical_id','rejection','edge_veto','current_depth','history_depth','cost')}
                    for c in trace.get('edges', [])]))
    return {a: {k: dict(v) for k,v in values.items()} for a,values in counters.items()}, actions, selected


def populations(public, interesting):
    stats = {roi: dict(total=0, eligible=0, old_scalar_valid=0, old_valid_but_rejected=0,
        status=Counter(), reason=Counter(), flags=Counter()) for roi in ROIS}
    joint = Counter()
    selected = []
    frames = 0
    for packet in rows(public/'MIXED_DEPTH.jsonl.gz'):
        for native, certificate in packet['objects'].items():
            eligible = []
            for roi in ROIS:
                fact, counter = certificate[roi], stats[roi]
                old_valid = scalar_valid(fact['inclusive_summary'], mad=roi!='whole')
                counter['total'] += 1; counter['eligible'] += bool(fact['eligible_single'])
                counter['old_scalar_valid'] += old_valid
                counter['old_valid_but_rejected'] += old_valid and not fact['eligible_single']
                counter['status'][fact['status']] += 1; counter['reason'][fact['reason']] += 1
                flags = {
                    'mixture':fact['mixture_flag'],'inclusive_mixture':fact['inclusive_mixture_flag'],
                    'independent_mixture':fact['independent_mixture_flag'],
                    'source_ownership_not_exclusive':not fact['source_ownership_exclusive'],
                    'source_population_unverified':fact['source_population_unverified_n']>0,
                    'shared_source_pixels':fact['shared_source_pixels_excluded']>0,
                    'within_roi_duplicate_pixels':fact['within_mask_duplicate_pixels_excluded']>0,
                    'independent_quality_not_usable':not fact['quality_usable'],
                    'original_pixel_quality_not_usable':not fact['original_pixel_quality_usable'],
                    'independent_points_below16':fact['summary']['n']<16,
                    'independent_fraction_below0p2':fact['summary']['valid_fraction']<.2,
                    'independent_scale_above60':fact['summary']['scale_mm'] is not None and fact['summary']['scale_mm']>60,
                    'original_whole_birth_quality_valid':scalar_valid(fact['inclusive_summary']) if roi=='whole' else False,
                }
                counter['flags'].update(k for k,v in flags.items() if v)
                eligible.append(int(fact['eligible_single']))
            joint['whole%d_fixed%d_adaptive%d'%tuple(eligible)] += 1
        if packet['frame'] in interesting:
            selected.append(dict(frame=packet['frame'], global_frame=packet['global_frame'],
                objects={n:{roi:{k:c[roi][k] for k in ('status','reason','eligible_single','mixture_flag','source_ownership_exclusive',
                    'source_population_unverified_n','shared_source_pixels_excluded','within_mask_duplicate_pixels_excluded',
                    'summary','inclusive_summary','roi_definition','roi_binding','fact_id')} for roi in ROIS}
                    for n,c in packet['objects'].items()}))
        frames += 1
        if frames % 1000 == 0:
            print(public.parent.name,'depth population',frames,flush=True)
    return {roi:{k:dict(v) if isinstance(v,Counter) else v for k,v in counter.items()} for roi,counter in stats.items()},dict(joint),selected,frames


def count_segment(name):
    public = RUN/name/'public'
    differences,frames = predictions(public)
    ordinals = [order_min(r) for r in rows(public/'ORDER_EVIDENCE.jsonl.gz')]
    summaries = {}
    for arm in ARMS[2:]:
        values = [o for o in ordinals if o['arm']==arm]
        eligible = [o for o in values if o['eligible']]
        summaries[arm] = dict(q_count=len(values),eligible=len(eligible),unknown=len(values)-len(eligible),
            weak_pre_order=sum(.1<o['p_A_nearer_at_q']<.9 for o in eligible),
            reason=dict(Counter(o['reason'] for o in values)),evidence_reason=dict(Counter(o['evidence_reason'] for o in values)),
            choice=dict(Counter(o['selected_choice'] for o in values)),restore=dict(Counter(o['restore']['status'] for o in values)),
            changed_s0_choice_vs_same_candidate_geometry=sum(o['ordinal_changes_same_candidate_geometry_choice'] for o in values),
            commits_with_actual_changes=sum(o['restore']['status']=='COMMIT' and bool(o['restore']['changes']) for o in values))
    by_event=defaultdict(dict)
    for o in ordinals:by_event[o['event']][o['arm']]=o
    contrasts=[]
    for event,arms in by_event.items():
        if all(a in arms for a in ('MIXED_ORDER','MIXED_OFF')):
            a,b=arms['MIXED_ORDER'],arms['MIXED_OFF']
            contrasts.append(dict(event=event,frame=a['frame'],global_frame=a['global_frame'],
                same_context=a['source_geometry_context_sha256']==b['source_geometry_context_sha256'],
                order_choice=a['selected_choice'],off_choice=b['selected_choice'],order_reason=a['reason'],
                order_published=a['published_mapping'],off_published=b['published_mapping'],
                order_restore=a['restore'],off_restore=b['restore'],published_different=a['published_mapping']!=b['published_mapping']))
    counters,actions,first_transactions=transactions(public,differences)
    interesting={o['frame'] for o in ordinals}|{v['first']['frame'] for v in differences.values() if v['first']}
    population,joint,selected_depth,count=populations(public,interesting)
    assert frames==count==SEGMENTS[name][1]-SEGMENTS[name][0]+1
    return dict(frames=frames,population=population,joint_ROI_eligibility=joint,ordinal_summary=summaries,
        ordinal_events=ordinals,order_off_contrasts=contrasts,publication_differences=differences,
        automatic_candidate_counts=counters,durable_automatic_actions=actions,first_difference_transactions=first_transactions,
        selected_depth_measurements=selected_depth,source_artifacts={f:artifact(public/f) for f in (
            'PREDICTIONS_SEALED.json','MIXED_DEPTH.jsonl.gz','ORDER_EVIDENCE.jsonl.gz','TRANSACTIONS.jsonl.gz','predictions.jsonl.gz')})


def counts():
    seal=read(RUN/'ALL_PREDICTIONS_SEALED.json')
    for item in seal['seals'].values():verify_item(item)
    result={}
    for name in SEGMENTS:
        print(name,'sealed depth audit start',flush=True)
        result[name]=count_segment(name)
        print(name,'sealed depth audit complete',flush=True)
    write_new(HERE/'POSTSEAL_DEPTH_MECHANISM_COUNTS.json',dict(status='SEALED_SOURCE_ONLY_COUNTS_COMPLETE',
        all_seals=artifact(RUN/'ALL_PREDICTIONS_SEALED.json'),segments=result,GT_raster_read=False,
        new_scientific_configuration=False,new_model_http=0,arithmetic_diagnostic_scope='Stored identical candidate scores only; no branch rerun'))


def finish():
    assert (RUN/'METRICS.json').exists() and (RUN/'SCORE_PROVENANCE.json').exists(), 'Complete official scoring is required'
    provenance=read(RUN/'SCORE_PROVENANCE.json')
    assert provenance['reference_opened_after_all_seals'] and not provenance['GT_used_for_predictions']
    evidence=read(HERE/'POSTSEAL_DEPTH_MECHANISM_COUNTS.json')
    groups=read(HERE/'POSTSEAL_GROUP_LAYER_COVERAGE.json')
    official=read(RUN/'METRICS.json')
    roi_totals={roi:dict(total=0,eligible=0,old_scalar_valid=0,old_valid_but_rejected=0,flags=Counter(),reason=Counter()) for roi in ROIS}
    q_totals={arm:Counter() for arm in ARMS[2:]}
    contrast_cases=[]; summaries={}; group_summary={}
    fields=('IDF1','HOTA','AssA','IDSW','FP','FN')
    for name,s in evidence['segments'].items():
        for roi,stats in s['population'].items():
            for k in ('total','eligible','old_scalar_valid','old_valid_but_rejected'):roi_totals[roi][k]+=stats[k]
            roi_totals[roi]['flags'].update(stats['flags']);roi_totals[roi]['reason'].update(stats['reason'])
        for arm,values in s['ordinal_summary'].items():
            q_totals[arm].update({k:values[k] for k in ('q_count','eligible','unknown','weak_pre_order',
                'changed_s0_choice_vs_same_candidate_geometry','commits_with_actual_changes')})
        audit=read(RUN/name/'public/EVENT_AUDIT.json')['arms']
        automatic=read(RUN/name/'public/AUTOMATIC_RECONNECT_AUDIT.json')['arms']
        physical={arm:dict(first_public_pre_consensus=dict(Counter(g.get('first_public_pre_consensus_verdict','NO_SPLIT') for g in audit[arm]['group_events'])),
            first_public_endpoint=dict(Counter(g.get('first_public_clean_endpoint_verdict','NO_SPLIT') for g in audit[arm]['group_events'])),
            committed_pre_consensus=dict(Counter(g.get('committed_pre_consensus_verdict','NO_SPLIT') for g in audit[arm]['group_events'])),
            automatic_actual_reference=dict(Counter(a['actual_reference_physical'] for a in automatic[arm])),
            automatic_joint_public_reference=dict(Counter(a['physical'] for a in automatic[arm]))) for arm in FOCUS}
        metrics=official['segments'][name]['metrics']
        deltas={base:{k:metrics['MIXED_ORDER'][k]-metrics[base][k] for k in fields}
                for base in ('SAM3_NATIVE','Z4Q_FROZEN','ACTIVITY_ORDER','MIXED_OFF')}
        firsts=s['publication_differences']
        first_actions=[]
        for pair,values in firsts.items():
            if not values['first']:continue
            frame=values['first']['frame']
            sources={int(token[2:]) for token in values['first']['mappings']}
            first_actions.append(dict(pair=pair,first=values['first'],official_automatic_verdicts={arm:[
                {k:a[k] for k in ('frame','global_frame','source','target','origin_rule','physical','actual_reference_physical',
                    'prior_public_reference_status','durable_automatic_commit','actual_old_anchor')}
                for a in automatic[arm] if a['frame']==frame and a['source'] in sources] for arm in FOCUS}))
        for contrast in s['order_off_contrasts']:
            if not contrast['published_different'] and contrast['order_choice']==contrast['off_choice']:continue
            group={arm:next((g for g in audit[arm]['group_events'] if g['event']==contrast['event']),None) for arm in ('MIXED_ORDER','MIXED_OFF')}
            verdict={arm:({k:g.get(k) for k in ('q','choice','restore_status','first_public_physical','first_public_clean_endpoint_verdict',
                'first_public_pre_consensus_verdict','committed_pre_consensus_verdict','post_q_through_q10_consensus')} if g else None) for arm,g in group.items()}
            contrast_cases.append(dict(segment=name,**contrast,official_postseal_verdicts=verdict,
                causal_scope='SAME_SOURCE_GEOMETRY_CONTEXT_FIRST_DECISION' if contrast['same_context'] else 'ALIAS_HISTORY_PROPAGATION_DIFFERENT_CONTEXT'))
        summaries[name]=dict(metrics=metrics,mixed_deltas=deltas,reference_status=official['segments'][name]['reference_status'],
            ordinal=s['ordinal_summary'],physical=physical,publication_difference_summary={k:{field:v[field] for field in (
                'frames_different','native_frame_differences','first','last')} for k,v in firsts.items()},first_divergence_actions=first_actions)
        group_records=groups['segments'][name]
        roi_group={roi:dict(sum((Counter(g['roi'][roi]) for g in group_records),Counter())) for roi in ROIS}
        split_with_mixed=[dict(event=g['event'],q=g['q'],group_records=g['group_records'],
            mixed_frames_by_roi={roi:g['roi'][roi].get('mixture',0) for roi in ROIS})
            for g in group_records if g['q'] is not None and any(g['roi'][roi].get('mixture',0) for roi in ROIS)]
        group_summary[name]=dict(events=len(group_records),split_q=sum(g['q'] is not None for g in group_records),
            group_records=sum(g['group_records'] for g in group_records),roi=roi_group,
            split_events_with_any_mixed_ROI=split_with_mixed)
    roi_totals={roi:{k:dict(v) if isinstance(v,Counter) else v for k,v in values.items()} for roi,values in roi_totals.items()}
    pooled=official['feeding_pooled']['metrics']
    feeding=dict(metrics=pooled,deltas={base:{k:pooled['MIXED_ORDER'][k]-pooled[base][k] for k in fields}
                                     for base in ('SAM3_NATIVE','Z4Q_FROZEN','ACTIVITY_ORDER','MIXED_OFF')})
    group_totals=dict(events=sum(g['events'] for g in group_summary.values()),
        split_q=sum(g['split_q'] for g in group_summary.values()),
        group_records=sum(g['group_records'] for g in group_summary.values()),
        split_events_with_any_mixed_ROI=sum(len(g['split_events_with_any_mixed_ROI']) for g in group_summary.values()))
    result=dict(status='COMPLETE_POSTSEAL_DEPTH_MECHANISM_ANALYSIS',frames_per_arm=20098,observations=181842,
        roi_totals=roi_totals,ordinal_totals={a:dict(v) for a,v in q_totals.items()},segments=summaries,
        feeding_pooled=feeding,ordinal_contrast_cases=contrast_cases,anonymous_group_depth_coverage=group_summary,
        anonymous_group_depth_totals=group_totals,
        control_boundary={'mixed_vs_activity':'Combined actual-ROI mixture/source/quality screening with own-state propagation',
            'mixed_vs_off':'Frozen ordinal score plus positive-support/H0 admission policy; same pair eligibility',
            'mixed_off':'Same paired measurement eligibility; not unrestricted geometry',
            'anonymous_group_depth':'Recorded distributions are not consumed by the ordinal factor; multiple surfaces do not identify two fish',
            'D1_actual_depth':'D_balanced smooth=False: last clean whole; last15 MAD; EMA recorded but not used as score mean'},
        unknown_not_safe=True,GT_raster_read=False,new_model_http=0,no_new_scientific_configuration=True,
        next_candidate=dict(name='SEPARATE_ORDINAL_CONFIDENCE_FROM_SIGN_BASED_ADMISSION',
            supported_by='All18 usable MIXED pre-order probabilities are weak; an essentially0.5 pre-sign blocks an endpoint-correct mapping, while val11900 and L3 require retaining wrong-swap prevention evidence',
            scope='One frozen causal diagnostic, unchanged current history/measurement/state floor and joint log9 gate; vary only strict positive-LR/H0 sign admission separately from continuous ordinal likelihood',
            risks=['Removing sign admission may admit the physically wrong val11900 swap; no gain forecast',
                   'Cancelling the complete ordinal factor is contradicted by L3 OFF wrong swap and IDF1 loss',
                   'Group mixtures cover only10/50 split events and are not two-fish evidence'],
            not_started=True,no_promised_gain=True,must_keep_preexisting_public_vs_actual_reference_separate=True),
        source_count_artifact=artifact(HERE/'POSTSEAL_DEPTH_MECHANISM_COUNTS.json'),
        anonymous_group_coverage_artifact=artifact(HERE/'POSTSEAL_GROUP_LAYER_COVERAGE.json'),
        official_metrics=artifact(RUN/'METRICS.json'),score_provenance=artifact(RUN/'SCORE_PROVENANCE.json'),
        script=artifact(__file__))
    write_new(HERE/'POSTSEAL_DEPTH_ANALYSIS.json',result)
    lines=['# DS18 封存后深度机制分析','',
        '完成六臂八段、每臂20098帧的只读审计。读取封存的源统计、事务、顺序证据和公开评分判定；未直接读取 GT/raster、RGB 或修复深度，未重跑分支或改冻结参数。','',
        '## 实际测量人口','', '|ROI|全部观测|单层/来源/质量合格|原标量有效|原有效后筛除|潜在混层|共享来源|独立质量不足|',
        '|---|---:|---:|---:|---:|---:|---:|---:|']
    for roi,v in roi_totals.items():
        lines.append(f'|{roi}|{v["total"]}|{v["eligible"]}|{v["old_scalar_valid"]}|{v["old_valid_but_rejected"]}|{v["flags"].get("mixture",0)}|{v["flags"].get("shared_source_pixels",0)}|{v["flags"].get("independent_quality_not_usable",0)}|')
    lines+=['','whole的原标量有效按原D1门槛（n≥16、fraction≥0.2、正深度，不加MAD上限）计算；fixed/adaptive按原core尺度门槛。混层、共享来源、覆盖与尺度可重叠，不能把旗标相加作为总拒绝数。whole的组合筛选同时加入实际源独占性和既有60mm质量尺度，不能把所有差异称为混层效果。',
        '','Birth真实fixed core与S0 adaptive core逐人口分别认证；没有用另一ROI的合格性替代当前标量。depth层代表匿名表面测量；多层不等于多条鱼，单层合格也不证明鱼身份。',
        '','## 实际上下顺序覆盖','', '|分支|q|可用|UNKNOWN|可用但弱|改变同候选几何选择|带实际改动S0提交|','|---|---:|---:|---:|---:|---:|---:|']
    for arm,v in q_totals.items():lines.append(f'|{arm}|{v["q_count"]}|{v["eligible"]}|{v["unknown"]}|{v["weak_pre_order"]}|{v["changed_s0_choice_vs_same_candidate_geometry"]}|{v["commits_with_actual_changes"]}|')
    lines+=['','弱证据是原odds=9对应的pre概率位于0.1–0.9；这是测量置信度代理，不是身份准确率。MIXED_ORDER可用18例全部弱，S0实际改动提交为0。选择改变、事务提交与全段指标必须分开；H0/UNKNOWN没有算作安全。各臂q数会因此前真实状态与事件准入/生命周期分化而不同，触发规则未重新调节。',
        '','## 合并期间保留的匿名层分布','',
        '|段|事件|有q事件|group观测|有q且任一ROI混层的事件|whole混层|fixed混层|adaptive混层|',
        '|---|---:|---:|---:|---:|---:|---:|---:|']
    for name,g in group_summary.items():
        lines.append(f'|{name}|{g["events"]}|{g["split_q"]}|{g["group_records"]}|{len(g["split_events_with_any_mixed_ROI"])}|{g["roi"]["whole"].get("mixture",0)}|{g["roi"]["birth_core"].get("mixture",0)}|{g["roi"]["core"].get("mixture",0)}|')
    lines+=['',f'MIXED_ORDER共有{group_totals["events"]}事件、{group_totals["split_q"]}个q、{group_totals["group_records"]}条group观测；{group_totals["split_events_with_any_mixed_ROI"]}/{group_totals["split_q"]}个有q事件在某个ROI存在潜在混层。val、L3的group观测未检出显著混层；三处ORDER/OFF首次不同选择对应的group也未检出混层。测量被保留为匿名GROUP证据，未写入A/B个体历史；本轮ordinal公式没有消费GROUP层分布。不能把“没有消费”称作层间身份恢复成功，也不能把两层直接解释成两条鱼，或假设该信息覆盖所有失败事件。',
        '','## 相同上下文的顺序影响与随后传播','', '|段/原帧|同输入上下文|ORDER/OFF|原因|ORDER首帧pre共识|OFF首帧pre共识|ORDER末clean端点|OFF末clean端点|',
        '|---|---|---|---|---|---|---|---|']
    for c in contrast_cases:
        verdict=c['official_postseal_verdicts'];a=verdict['MIXED_ORDER'] or {};b=verdict['MIXED_OFF'] or {}
        lines.append(f'|{c["segment"]}/{c["global_frame"]}|{c["same_context"]}|{c["order_choice"]}/{c["off_choice"]}|{c["order_reason"]}|{a.get("first_public_pre_consensus_verdict","UNKNOWN")}|{b.get("first_public_pre_consensus_verdict","UNKNOWN")}|{a.get("first_public_clean_endpoint_verdict","UNKNOWN")}|{b.get("first_public_clean_endpoint_verdict","UNKNOWN")}|')
    lines+=['','首次相同上下文分歧只有三处。Feeding1239的pre p≈0.499457、顺序LR≈−0.000150，却触发正支持硬门；val11900为p≈0.731125、候选相对H0的顺序反证；L3原帧1420的顺序项使联合赔率落到冻结门槛下。随后两个分支即使同选H0，输出也可能不同，因为alias/参考已分化；这不是新一轮顺序因子效果。末点、pre共识与提交后q..q10诊断保留各自UNKNOWN/UNSCORABLE，不能择优使用答案。',
        '','## 同源完整指标差值','', '|范围|参照|ΔIDF1|ΔHOTA|ΔAssA|ΔIDSW|ΔFP|ΔFN|',
        '|---|---|---:|---:|---:|---:|---:|---:|']
    scopes={'Feeding1471':feeding['deltas'],**{name:s['mixed_deltas'] for name,s in summaries.items() if not name.startswith('feeding_')}}
    for name,comparisons in scopes.items():
        for base,d in comparisons.items():lines.append(f'|{name}|{base}|{d["IDF1"]:+.6f}|{d["HOTA"]:+.6f}|{d["AssA"]:+.6f}|{d["IDSW"]:+d}|{d["FP"]:+d}|{d["FN"]:+d}|')
    lines+=['','Mixed−Activity是混层/来源/质量与历史传播的组合效应；Mixed−Off包含顺序打分与正LR/H0门，不是纯连续打分消融。完整预测与全部ID统一评分，FP/FN也按官方CLEAR实际结果保留。恢复原Z4Q是止损；L3/LW为弱参考，重复曝光片段不能称独立泛化。',
        '','## 首次分歧的实际机制','',
        '- Feeding159/375：MIXED新增D1提交；ACTIVITY分别被事件保护/匿名partner门阻止。不能解释为MIXED数值残差更好。',
        '- Feeding849：MIXED丢失当前whole的D1准入；1413双方有合法边，但旧参考统计与确认链不同。',
        '- 开发3947：MIXED在不同survivor参考状态下Birth提交；val11489：MIXED因partner fixed/whole UNKNOWN没有Birth提交。',
        '- L3原帧547：目标历史和运动范围已因筛选变更；LW原帧226：原本合法的Birth因所需whole UNKNOWN阻止。LW当前whole有231点，仅3点共享来源，fixed/adaptive都合格，未检出混层；所需whole采用整个人口的独占来源门，不是按污染比例渐减置信度。该ACTIVITY恢复的实际旧anchor与公开源都UNSCORABLE，不能称“阻止正确恢复”。',
        '',
        'L3原帧1420的ORDER首帧端点与pre共识均CORRECT，OFF交换提交WRONG；OFF相对ORDER的IDF1下降9.588185、HOTA下降7.148416。val11900的OFF首帧pre共识和提交后片段为WRONG，尽管完整IDF1高于ORDER；Feeding1239则末clean端点ORDER WRONG/OFF CORRECT而pre共识不可评分。不同证据方向必须并列。',
        '','原D1的D_balanced smooth=False，关联z(h)取最后clean whole，15点历史用于MAD/tolerance；EMA是记录与核验的状态，不是本轮D1实际深度均值预测。',
        '','## 一个下一步候选（尚未启动）','',
        '针对本轮18个可用pre次序全部弱、极接近0.5的符号仍可形成硬否决，建议下一个冻结诊断实验只分开“连续顺序证据”和“正支持/H0符号硬准入”，保留本轮测量、状态和联合log9门，用真实同源完整回放评估。不能直接取消整个顺序因子：L3已显示取消后的错误交换与完整指标下降。移除符号准入也可能放过val11900的错误交换，因此这只是明确机制的候选，不是提点承诺。必须保留三例的末点/pre共识判定，分别保留避免错误、阻碍正确与不可评分，不能按GT挑事件或滚动搜索门槛。主任务最终只选择一个计划；本审计没有启动新实验。',
        '','来源统计/所有候选、首分歧与后续映射链在POSTSEAL_DEPTH_MECHANISM_COUNTS.json；完整指标、物理分层、依赖SHA在POSTSEAL_DEPTH_ANALYSIS.json。']
    with (HERE/'POSTSEAL_DEPTH_ANALYSIS.md').open('x',encoding='utf-8',newline='\n') as handle:handle.write('\n'.join(lines)+'\n')
    print('COMPLETE_POSTSEAL_DEPTH_MECHANISM_ANALYSIS',flush=True)


def group_layers():
    """Coverage of already recorded anonymous group surfaces, not fish identification."""
    results={}
    for name in SEGMENTS:
        public=RUN/name/'public';events=read(public/'EVENTS.json')['MIXED_ORDER']
        lookup=defaultdict(list);event_rows={}
        for event in events:
            record=dict(event=event['id'],q=event['q'],group_records=0,roi={roi:Counter() for roi in ROIS})
            event_rows[event['id']]=record
            for item in event['group_observations']:
                assert event['q'] is None or item['frame']<event['q']
                lookup[item['frame']].append((event['id'],str(item['source'])))
        for packet in rows(public/'MIXED_DEPTH.jsonl.gz'):
            for event,native in lookup.get(packet['frame'],[]):
                record=event_rows[event];record['group_records']+=1
                assert native in packet['objects']
                c=packet['objects'][native]
                for roi in ROIS:
                    f=c[roi];v=record['roi'][roi]
                    v['frames']+=1;v['mixture']+=bool(f['mixture_flag']);v['independent_quality']+=bool(f['quality_usable'])
                    v['inclusive_two_substantial_layers']+=f['inclusive_substantial_layer_count']>=2
                    v['source_ownership_unknown']+=not f['source_ownership_exclusive']
                    v['individual_eligible']+=bool(f['eligible_single'])
        results[name]=[{**v,'roi':{roi:dict(c) for roi,c in v['roi'].items()}} for v in event_rows.values()]
        print(name,'anonymous group layer coverage complete',flush=True)
    write_new(HERE/'POSTSEAL_GROUP_LAYER_COVERAGE.json',dict(status='SEALED_GROUP_MEASUREMENT_COVERAGE_ONLY',segments=results,
        no_GT_raster=True,no_new_scientific_configuration=True,group_layers_are_not_two_fish=True,
        original_ordinal_consumes_group_depth=False,anonymous_measurement_preserved_not_individual_history=True))


if __name__=='__main__':
    assert sys.argv[1:] in (['counts'],['finish'],['group'])
    {'counts':counts,'finish':finish,'group':group_layers}[sys.argv[1]]()
