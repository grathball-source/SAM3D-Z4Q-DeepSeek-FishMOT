"""SLR-2 sealed-output local-continuity evaluation; never writes tracker state."""
from collections import Counter
from pathlib import Path
import json
import statistics


def canonical(option):
    """Discard option names while preserving physical decisions and WAIT hypotheses."""
    if option is None:
        return None
    return dict(state=option['state'],
                matches=sorted([[int(t),int(o)] for t,o in option['matches']]),
                groups=sorted([[int(o),sorted(int(t) for t in ts)] for o,ts in option['groups']]),
                unresolved=sorted(int(t) for t in option['unresolved']))


def proposed_match(option):
    return option is not None and option['state']=='MATCH'


def proposal_metrics(option, truth, baseline_correct):
    """Local proposal accuracy and ideal fallback policy are separate quantities."""
    proposed=proposed_match(option)
    actual={int(t):int(o) for t,o in option['matches']} if proposed else {}
    truth={int(t):int(o) for t,o in truth.items()}
    correct=bool(proposed and actual==truth)
    return dict(proposed=proposed,correct_assignment=correct,abstain=not proposed,
                correct_repair=correct and not baseline_correct,
                wrong_proposal=proposed and not correct,
                harms_stable_success=bool(baseline_correct and proposed and not correct),
                policy_correct=correct if proposed else bool(baseline_correct),
                preserves_stable_success=bool(baseline_correct and (correct or not proposed)))


def consensus(records):
    """All three independently returned views must be legal and physically identical."""
    if len(records)!=3:
        return None,'incomplete_three_views'
    if not all(r['valid'] for r in records):
        return None,'at_least_one_invalid'
    oo=[canonical(r['option']) for r in records]
    if not all(o==oo[0] for o in oo[1:]):
        return None,'physical_decision_disagreement'
    if not proposed_match(oo[0]):
        return None,'consistent_wait'
    return oo[0],None


def public_guard(option, pre_public_by_native, current_public_by_native, focal_native_ids):
    """Evaluate a hypothetical two-observation rewrite; preserve every other mask.

    Existing nonfocal nonnegative identities are protected. A newly born current
    identity is not automatically protected. Duplicate nonnegative IDs after the
    hypothetical rewrite veto the proposal. No real predictions are mutated.
    """
    pre={int(k):int(v) for k,v in pre_public_by_native.items()}
    current={int(k):int(v) for k,v in current_public_by_native.items()}
    focal={int(t) for t in focal_native_ids}
    detail=dict(approved=False,veto_reasons=[],protected_public_ids=[],
                protected_selected_observations=[],duplicate_public_ids=[],hypothetical_public_by_native=None)
    if not proposed_match(option):
        detail['veto_reasons']=['no_match_proposal'];return detail
    pairs=[(int(t),int(o)) for t,o in option['matches']]
    if (len(pairs)!=len(focal) or {t for t,o in pairs}!=focal or
        len({o for t,o in pairs})!=len(pairs) or not focal<=set(pre) or
        not {o for t,o in pairs}<=set(current)):
        detail['veto_reasons']=['invalid_complete_assignment'];return detail
    target={pre[t] for t in focal}
    if len(target)!=len(focal) or any(x<0 for x in target):
        detail['veto_reasons']=['ambiguous_or_unconfirmed_pre_public_anchors'];return detail
    protected={p for p in pre.values() if p>=0 and p not in target}
    detail['protected_public_ids']=sorted(protected)
    collisions=[dict(native_observation=o,current_public_id=current[o],proposed_public_id=pre[t])
                for t,o in pairs if current[o] in protected]
    if collisions:
        detail['veto_reasons'].append('preexisting_nonfocal_public_identity')
        detail['protected_selected_observations']=collisions
    hypothetical=dict(current)
    for t,o in pairs:hypothetical[o]=pre[t]
    duplicates=sorted(p for p,n in Counter(v for v in hypothetical.values() if v>=0).items() if n>1)
    if duplicates:
        detail['veto_reasons'].append('duplicate_nonnegative_public_identity')
        detail['duplicate_public_ids']=duplicates
    detail['hypothetical_public_by_native']=hypothetical
    detail['approved']=not detail['veto_reasons']
    return detail


def public_maps(request_map):
    """Translate private anonymous maps to native-mask keys only inside evaluator."""
    pre={int(k):int(v) for k,v in request_map['pre_public_by_native'].items()}
    current={int(request_map['observation_native_map'][o]):int(p)
             for o,p in request_map['current_public_by_observation'].items()}
    if 'current_public_by_native' in request_map:
        assert current=={int(k):int(v) for k,v in request_map['current_public_by_native'].items()}
    focal=sorted(int(n) for n in request_map['track_native_map'].values())
    assert set(current)==set(int(x) for x in request_map['observation_native_map'].values())
    assert set(focal)<=set(pre)
    if 'pre_public_by_track' in request_map:
        assert all(pre[int(n)]==int(request_map['pre_public_by_track'][t])
                   for t,n in request_map['track_native_map'].items())
    if 'protected_nonfocal_observations' in request_map:
        protected={v for v in pre.values() if v>=0 and v not in {pre[t] for t in focal}}
        expected={o for o,v in request_map['current_public_by_observation'].items() if int(v) in protected}
        assert expected==set(request_map['protected_nonfocal_observations'])
    if 'baseline_option_id' in request_map:
        baseline=canonical(request_map['option_map'][request_map['baseline_option_id']])
        possible={t:[o for o,p in current.items() if p==pre[t]] for t in focal}
        unique_complete=all(len(v)==1 for v in possible.values()) and len({v[0] for v in possible.values() if len(v)==1})==len(focal)
        if unique_complete:
            assert baseline['state']=='MATCH'
            assert dict(baseline['matches'])=={t:v[0] for t,v in possible.items()}
        else:
            assert baseline['state']=='UNRESOLVED'
    return pre,current,focal


def aggregate(rows):
    keys=['proposed','correct_assignment','abstain','correct_repair','wrong_proposal',
          'harms_stable_success','policy_correct','preserves_stable_success']
    return {k:sum(bool(r[k]) for r in rows) for k in keys}


def physical_consistency(a,b):
    if not (a['valid'] and b['valid']):return dict(consistent=False,reason='invalid_output')
    aa,bb=canonical(a['option']),canonical(b['option'])
    if aa==bb:return dict(consistent=True,reason='same_physical_decision')
    if proposed_match(aa) and proposed_match(bb):why='different_physical_assignment'
    elif proposed_match(aa)!=proposed_match(bb):why='MATCH_vs_WAIT'
    else:why='WAIT_hypothesis_difference'
    return dict(consistent=False,reason=why)


def main():
    from common import P,ROOT,PREV,STAGE,save,read,sha,now,limit_cpu
    from evaluation_checks import run_checks
    limit_cpu()
    assert not (P/'EVALUATION_ACCEPTANCE.json').exists(),'evaluation already sealed'
    ma=read(P/'MODEL_ACCEPTANCE.json');assert ma['exit_code']==0
    for n,h in ma['hashes'].items():assert sha(P/n)==h,(n,'model seal mismatch')
    for n,h in read(P/'MODEL_FREEZE.json').items():assert sha(Path(n) if Path(n).is_absolute() else P/n)==h,(n,'frozen input mismatch')
    tests=run_checks()
    models=read(P/'MODEL_DECISIONS.json');maps=read(P/'REQUEST_MAPS.json')
    requests=read(P/'REQUESTS.json');indexes=read(P/'PRIVATE_INDEX.json')
    baselines=read(P/'BASELINE_DECISIONS.json')
    assert len(models)==len(maps)==len(requests)==144
    assert len(indexes)==len(baselines)==36
    assert len({r['request_id'] for r in models})==144
    assert {r['request_id'] for r in models}==set(maps)=={r['request_id'] for r in requests}
    assert len({r['query_id'] for r in indexes})==36
    query_ix={r['query_id']:r for r in indexes};rq={r['request_id']:r for r in requests}
    bd={r['query_id']:r for r in baselines};assert set(bd)==set(query_ix)
    by={}
    for r in models:
        mp=maps[r['request_id']];req=rq[r['request_id']]
        for k in ['query_id','arm','view']:assert r[k]==mp[k]==req[k]
        assert mp['stage']==query_ix[r['query_id']]['stage']
        assert isinstance(r['valid'],bool)
        option_id=(r.get('output') or {}).get('option_id')
        option=mp['option_map'].get(option_id)
        if r['valid']:
            assert option is not None
            assert set(r['output'])=={'option_id','evidence_ids','reason_codes'}
            assert isinstance(r['output']['evidence_ids'],list) and r['output']['evidence_ids']
            assert all(e in req['packet']['evidence'] for e in r['output']['evidence_ids'])
        key=(r['query_id'],r['arm'],r['view']);assert key not in by
        by[key]=dict(valid=r['valid'],option=canonical(option),request_id=r['request_id'])
    expected=set()
    for ix in indexes:
        assert ix['stage'] in ['first_split','merge_snapshot']
        for arm in ['T','V']:
            for view in (['original','repeat','permuted'] if ix['stage']=='first_split' else ['original']):expected.add((ix['query_id'],arm,view))
    assert set(by)==expected
    assert sum(ix['stage']=='first_split' for ix in indexes)==18
    assert sum(ix['stage']=='merge_snapshot' for ix in indexes)==18

    # Only after the entire 144-response seal and request coverage pass, open GT.
    truth_path=STAGE/'E0_event_audit/EVENTS_gap15.json'
    assert sha(truth_path)==read(PREV/'SELECTION_ACCEPTANCE.json')['source_sha256']
    truth_events=read(truth_path)
    event_results=[];merge_results=[]
    for ix in indexes:
        qid=ix['query_id']
        if ix['stage']=='merge_snapshot':
            mr=dict(query_id=qid,event=ix['event'],frame=ix['frame'],arms={})
            for arm in ['T','V']:
                r=by[qid,arm,'original'];mp=maps[r['request_id']];pre,current,focal=public_maps(mp)
                op=r['option'] if r['valid'] else None
                mr['arms'][arm]=dict(valid=r['valid'],state=(r['option'] or {}).get('state'),
                    guarded_proposal=public_guard(op,pre,current,focal))
            merge_results.append(mr);continue
        matches=[e for e in truth_events if e['eligible'] and e['merge_frames'] and e['split']==ix['split']
                 and e['last_independent_frame']==ix['pre'] and e['split_first_frame']==ix['frame']
                 and sorted(e['pre_native_ids'])==sorted(ix['track_native_map'].values())]
        assert len(matches)==1;e=matches[0]
        truth=dict(zip(e['pre_native_ids'],e['post_native_ids']))
        b0=e['pre_public_ids']==e['post_public_ids']
        assert b0==e['stable']['first_split_correct']
        rr=dict(query_id=qid,event=ix['event'],frame=ix['frame'],split=ix['split'],
                stable_correct=b0,truth_native_mapping=truth,arms={})
        base_mp=maps[by[qid,'T','original']['request_id']]
        pre,current,focal=public_maps(base_mp)
        assert {n:pre[n] for n in e['pre_native_ids']}==dict(zip(e['pre_native_ids'],e['pre_public_ids']))
        assert {n:current[n] for n in e['post_native_ids']}==dict(zip(e['post_native_ids'],e['post_public_ids']))
        bo=canonical(base_mp['option_map'][bd[qid]['option_id']]);bg=public_guard(bo,pre,current,focal)
        rr['B2']=dict(option=bo,reason=bd[qid]['reason'],original=proposal_metrics(bo,truth,b0),
                      guard=bg,guarded=proposal_metrics(bo if bg['approved'] else None,truth,b0))
        for arm in ['T','V']:
            views={v:by[qid,arm,v] for v in ['original','repeat','permuted']}
            vv={}
            for view,r in views.items():
                mp=maps[r['request_id']];vpre,vcurrent,vfocal=public_maps(mp)
                assert (vpre,vcurrent,vfocal)==(pre,current,focal),'public maps changed across views'
                vv[view]=dict(valid=r['valid'],option=r['option'],
                              metrics=proposal_metrics(r['option'] if r['valid'] else None,truth,b0))
            co,why=consensus(list(views.values()));gd=public_guard(co,pre,current,focal)
            rr['arms'][arm]=dict(views=vv,consensus_option=co,consensus_wait_reason=why,
                consensus=proposal_metrics(co,truth,b0),guard=gd,
                guarded_consensus=proposal_metrics(co if gd['approved'] else None,truth,b0),
                original_repeat=physical_consistency(views['original'],views['repeat']),
                original_permuted=physical_consistency(views['original'],views['permuted']))
        event_results.append(rr)
    assert len(event_results)==len(merge_results)==18
    stable=sum(r['stable_correct'] for r in event_results);assert stable==13
    arms={}
    for arm in ['T','V']:
        aa=[r['arms'][arm] for r in event_results]
        ar=dict(valid_responses=sum(r['valid'] for r in models if r['arm']==arm),total_responses=72,
                first_split_views={v:aggregate([r['views'][v]['metrics'] for r in aa]) for v in ['original','repeat','permuted']},
                consensus=aggregate([r['consensus'] for r in aa]),guarded_consensus=aggregate([r['guarded_consensus'] for r in aa]),
                consensus_wait_reasons=dict(Counter(r['consensus_wait_reason'] for r in aa if r['consensus_wait_reason'])),
                guard_veto_events=sum(proposed_match(r['consensus_option']) and not r['guard']['approved'] for r in aa),
                guard_veto_reasons=dict(Counter(reason for r in aa if proposed_match(r['consensus_option']) for reason in r['guard']['veto_reasons'])))
        for key in ['original_repeat','original_permuted']:
            ar[key]=dict(consistent=sum(r[key]['consistent'] for r in aa),total=18,
                         categories=dict(Counter(r[key]['reason'] for r in aa)))
        merges=[r['arms'][arm] for r in merge_results]
        ar['merge_safety']=dict(total=18,valid=sum(r['valid'] for r in merges),
             states=dict(Counter(r['state'] if r['valid'] else 'INVALID' for r in merges)),
             single_call_match_passes_public_guard=sum(r['guarded_proposal']['approved'] for r in merges),
             physical_occlusion_truth_scored=False,actual_tracker_actions=0)
        arms[arm]=ar
    V=arms['V']['guarded_consensus'];T=arms['T']['guarded_consensus']
    gate=dict(all_144_sealed=True,T_valid_at_least_69=arms['T']['valid_responses']>=69,
              V_valid_at_least_69=arms['V']['valid_responses']>=69,V_policy_at_least_15=V['policy_correct']>=15,
              V_repairs_at_least_2=V['correct_repair']>=2,V_zero_harms=V['harms_stable_success']==0,
              V_exceeds_T_by_at_least_1=V['policy_correct']>=T['policy_correct']+1)
    passed=all(gate.values())
    latencies=sorted(r['seconds'] for r in models)
    usage={k:sum((r.get('usage') or {}).get(k,0) or 0 for r in models)
           for k in ['prompt_tokens','completion_tokens','total_tokens','prompt_cache_hit_tokens','prompt_cache_miss_tokens']}
    summary=dict(at=now(),decision='PASS_SHADOW_ONLY' if passed else 'STOP_SLR2',events=18,queries=36,model_responses=144,
                 stable_correct=stable,arms=arms,conservative_cost_usd_including_smoke=ma['conservative_cost_usd'],B2=dict(original=aggregate([r['B2']['original'] for r in event_results]),
                 guarded=aggregate([r['B2']['guarded'] for r in event_results])),gates=gate,usage=usage,
                 latency_seconds=dict(mean=statistics.mean(latencies),p95=latencies[min(len(latencies)-1,int(.95*len(latencies)))],maximum=max(latencies)),
                 returned_models=sorted({r['returned_model'] for r in models}),evaluation_checks=tests,
                 oracle_conditioned=True,independent_blind_test=False,continuous_tracking_modified=False,
                 ground_truth_read_after_all_model_outputs_sealed=True,
                 notes=['Stable13/18 is local pre-to-post public-ID continuity, not global identity accuracy.',
                   'Three calls must agree on the same legal physical MATCH; otherwise retain frozen Stable.',
                   'Public guard only simulates two-mask ID assignment and preserves all other current mask IDs.',
                   'Existing nonfocal nonnegative public IDs are protected; newly born IDs may be replaced.',
                   'All exposed correlated events belong to one sequence. No IDF1/HOTA or deployment claim.',
                   'Original-repeat estimates stochastic variability; original-permuted also includes variability.',
                   'Merge snapshots have no physical occlusion truth score and no tracker actions.'])
    save(P/'EVENT_RESULTS.json',dict(first_split=event_results,merge_snapshots=merge_results))
    save(P/'SUMMARY.json',summary)
    rows=[]
    for label,values in [('B0 Stable',dict(policy_correct=stable,correct_assignment=None,correct_repair=0,harms_stable_success=0)),
                         ('B2 单次守卫',summary['B2']['guarded'])]:
        explicit=values.get('correct_assignment');explicit='—' if explicit is None else explicit
        rows.append(f"|{label}|{values['policy_correct']}|{explicit}|{values['correct_repair']}|{values['harms_stable_success']}|")
    for arm in ['T','V']:
        for name,values in [('原始单次',arms[arm]['first_split_views']['original']),('三次共识',arms[arm]['consensus']),('共识+公共ID守卫',arms[arm]['guarded_consensus'])]:
            rows.append(f"|{arm} {name}|{values['policy_correct']}|{values['correct_assignment']}|{values['correct_repair']}|{values['harms_stable_success']}|")
    report=f'''# SLR-2 第二轮结果

判定：**{summary['decision']}**。144份真实响应全部封存后，独立读取离线身份对应关系评分。T为结构化数值摘要，V为相同数值加实际RGB/mask图；事件、历史构建和输出契约相同。

|方案|影子策略正确/18|明确正确提案|正确补救|破坏原正确|
|---|---:|---:|---:|---:|
{chr(10).join(rows)}

T合法{arms['T']['valid_responses']}/72；V合法{arms['V']['valid_responses']}/72。T原始-精确重复一致{arms['T']['original_repeat']['consistent']}/18、原始-重排一致{arms['T']['original_permuted']['consistent']}/18；V分别{arms['V']['original_repeat']['consistent']}/18、{arms['V']['original_permuted']['consistent']}/18。区别不能全部归因于排列或编号。

公共ID守卫拒绝T {arms['T']['guard_veto_events']}个、V {arms['V']['guard_veto_events']}个一致匹配：保护pre已存在的非目标身份，并检查替换后全当前候选是否产生重复非负ID。新出生ID不一概禁止重接；其余候选保留原ID。这里是一次影子事务检查，未写回跟踪器，未验证连续状态或非目标鱼的全视频指标。

晋级条件：每臂至少69/72合法；V守卫后至少15/18、至少2次补救、零误改，并至少比T多1个正确事件。各门布尔结果见SUMMARY.json。合并期18×2次调用仅报告状态与守卫结果，不把离线抽样时刻当物理遮挡真值。

全部18事件已暴露且相关，Stable13/18也是局部身份连续性；本轮不属于盲测，不声称泛化或IDF1/HOTA提升。冻结三次共识和弃权回退不等于在线系统已安全部署。没有改动原Z4Q/SAM，也不自动开展下一轮。
'''
    (P/'RESULTS.md').write_text(report,encoding='utf-8')
    save(P/'EVALUATION_ACCEPTANCE.json',dict(at=now(),exit_code=0,model_outputs_sealed_before_GT=True,
         model_decisions_sha256=sha(P/'MODEL_DECISIONS.json'),truth_sha256=sha(truth_path),
         reproduced_stable_local_correct=13,semantic_checks=tests,decision=summary['decision'],
         hashes={n:sha(P/n) for n in ['EVENT_RESULTS.json','SUMMARY.json','RESULTS.md']}))
    print(summary['decision'],flush=True)


if __name__=='__main__':main()
