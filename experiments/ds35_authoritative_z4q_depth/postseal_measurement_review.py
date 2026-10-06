"""Created after all prediction seals: explain zero writes without changing experiment or GT."""
from common import *
from collections import Counter
from datetime import datetime,timezone
from verify_inputs import verify_all

def main():
    verify_all();results={};totals=Counter();reasons=Counter();forecast_reasons=Counter();partial=[]
    for name in SEGMENTS:
        public=RUN/name/'public';events=read(public/'EVENTS.json')['DEPTH_OVERRIDE']
        wanted={s['frame'] for e in events for v in e['joint_pre'].values() for s in v['samples']}
        measured={r['frame']:r for r in rows(public/'FRAME_INPUTS_BINDINGS.jsonl.gz') if r['frame'] in wanted}
        data=[];counts=Counter();current_reasons=Counter();pred_reasons=Counter()
        for e in events:
            d=e.get('joint_decision',{});gate=d.get('depth_gate',{});q=e.get('q')
            counts['events']+=1;counts['with_q']+=q is not None
            counts['complete_endpoint_cost']+=bool(d.get('scores'))
            counts['common_depth_available']+=d.get('common_weights',{}).get('depth')==CFG['depth_weight']
            counts['eligible_proposals']+=bool(gate.get('eligible'));counts['actual_commits']+=bool(e.get('restore',{}).get('staged'))
            reasons[d.get('reason',e['status'])]+=1
            pre=[]
            for role,reference in e['joint_pre'].items():
                facts=[measured[s['frame']]['DS18_extracts'][str(s['native'])] for s in reference['samples']]
                usable=sum(f['usable'] for f in facts)
                failed=[f for f in facts if not f['usable']]
                risk=any(f.get('quality',{}).get('core_multilayer') or f.get('quality',{}).get('whole_multilayer') or
                    not f.get('quality',{}).get('exclusive_native_sources',False) or f.get('quality',{}).get('unverified_source_n',0) for f in failed)
                value=dict(role=role,reference_status=reference['status'],samples=len(facts),usable_depth_points=usable,
                    failed_depth_reasons=dict(Counter(f['reason'] for f in failed)),has_depth_mixture_or_ownership_risk=risk,
                    all_recorded_identity_versions_same=bool(reference['samples']) and all(s['version']==reference['samples'][-1]['version'] for s in reference['samples']))
                pre.append(value)
                counts['pre_references']+=1;counts['unknown_pre_references']+=reference['status']=='UNKNOWN_REFERENCE'
                counts['pre_samples']+=len(facts);counts['pre_usable_depth_points']+=usable
                if usable>=3 and failed:
                    opportunity=dict(segment=name,event=e['id'],q=q,**value)
                    partial.append(opportunity)
                    counts['partial_depth_pre_with_at_least_three_valid_points']+=1
                    counts['partial_depth_pre_without_observed_mixture_or_ownership_risk']+=not risk
            seen_current=set();seen_forecast=set()
            for candidate in d.get('scores',[]):
                for edge in candidate['edges']:
                    for row in edge['depth_rows']:
                        key=(edge['native'],row['frame'])
                        if key not in seen_current:
                            seen_current.add(key);current_reasons['USABLE' if row['current_fact']['usable'] else 'UNUSABLE_CURRENT_ENDPOINT']+=1
                        for pid,p in row['detail']['forecasts'].items():
                            key=(edge['native'],row['frame'],pid)
                            if key not in seen_forecast:
                                seen_forecast.add(key);pred_reasons[p.get('reason',p['status'])]+=1
            data.append(dict(event=e['id'],q=q,decision_reason=d.get('reason'),underlying_endpoint_reason=d.get('original_evidence_reason'),
                gate=gate,pre=pre,common_weights=d.get('common_weights'),staged=e.get('restore',{}).get('staged',False)))
        totals.update(counts);forecast_reasons.update(pred_reasons)
        results[name]=dict(counts=dict(counts),current_endpoint_reasons=dict(current_reasons),forecast_reasons=dict(pred_reasons),events=data)
    result=dict(status='READ_ONLY_POSTSEAL_MEASUREMENT_REVIEW',created_utc=datetime.now(timezone.utc).isoformat(),
        all_prediction_seal=artifact(RUN/'ALL_PREDICTIONS_SEALED.json'),helper=artifact(__file__),
        counts=dict(totals),decision_reasons=dict(reasons),forecast_reasons=dict(forecast_reasons),segments=results,
        partial_depth_in_qualified_contiguous_pre=partial,
        partial_is_hypothesis_only_not_new_forecast_or_association=True,mixture_and_ownership_risk_must_not_be_skipped_or_joined=True,
        predictions_and_scores_unchanged=True,GT_opened=False,RGB_pixels_opened=False,raw_sensor_pixels_opened=False,new_model_http=0,cost_usd=0)
    write_new(HERE/'POSTSEAL_MEASUREMENT_REVIEW.json',result)
    text=['# DS35 封存后深度可用性复盘','本程序在八段预测与访问全部封存之后新增，只读数值证书与事件记录。未读取GT或像素，未改关联、门槛、评分及封存代码。',
        '## 真实计数','```json',json.dumps(dict(counts=dict(totals),decision_reasons=dict(reasons),forecast_reasons=dict(forecast_reasons)),ensure_ascii=False,indent=2),'```',
        '计数分别区分：自动事件、有首分离q、能构建完整端点成本、共同深度可用、深度门槛通过及真实提交。它们不等价。',
        '## 缺测与身份风险边界',
        f'有至少3个有效深度点、同时有不合格深度点的合格连续pre片段：{len(partial)}；其中未发现混层或来源占用风险者：{sum(not p["has_depth_mixture_or_ownership_risk"] for p in partial)}。',
        '这只是下一轮候选机制的观测机会，不运行新的WLS，不把不合格点改为有效，不把混层/来源风险当成普通缺测并跳过，也不跨身份版本或风险连接两端。',
        '未知pre来源不能靠换锚变成合格；宽预测、相近深度和混合掩码不提供独立身份认证。恢复原Z4Q是止损，不是新增深度收益。',
        '逐事件pre有效数量、失败理由、共同权重、预测状态与门槛实值均在JSON中保留。正式指标以独立METRICS为准。']
    with (HERE/'POSTSEAL_MEASUREMENT_REVIEW.md').open('x',encoding='utf-8',newline='\n') as f:f.write('\n\n'.join(text)+'\n')
    print(json.dumps(dict(counts=dict(totals),decision_reasons=dict(reasons),forecast_reasons=dict(forecast_reasons)),ensure_ascii=False),flush=True)
if __name__=='__main__':main()
