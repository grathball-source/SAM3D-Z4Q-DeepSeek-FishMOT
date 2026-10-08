"""Additional postseal lifecycle and prefilter diagnostics; never new tracker input."""
from common import *
from collections import Counter
import numpy as np

def main():
    verified_freeze();data=read(HERE/'RESULTS.json');actions=data['actions']
    candidates={c['action']['action_id']:c for c in rows(HERE/'run/CANDIDATES.jsonl.gz')}
    matches={n:read(DS37/'run'/n/'public/REFERENCE_MATCHES.json') for n in SEGMENTS}
    tx={n:[t for t in rows(DS37/'run'/n/'public/TRANSACTIONS.jsonl.gz') if t['arm']=='Z4Q_WLS_VETO'] for n in SEGMENTS}
    lifecycles=[];prefilter=[];owners=[];selected_orders=[]
    for action in actions:
        a=action['action'];name=a['segment'];q=a['frame'];n=a['native'];s=candidates[a['action_id']]['phase_snapshot']
        current=matches[name][str(q)].get(str(n),{});bank={b['id']:b for b in action['bank']}
        past={}
        for t in tx[name][:q-1]:
            for target,ref in t['bank_anchors'].items():
                k=int(target)
                if not ref or k==action['availability_by_source_role']['incumbent_public'] or ref['native_id']==n: continue
                if relation(current,matches[name][str(ref['frame'])].get(str(ref['native_id']),{}))!='SAME': continue
                past.setdefault(k,dict(first_snapshot=t['frame']))
                past[k].update(last_same_snapshot=t['frame'],last_same_anchor=ref)
        for k,r in past.items():
            b=bank.get(k)
            if b is None: status='BANK_REMOVED'
            elif b['physical_reference']=='DIFFERENT': status='ANCHOR_REPLACED_BY_OTHER_PHYSICAL_REFERENCE'
            elif b['physical_reference']=='UNKNOWN': status='CURRENT_ANCHOR_UNSCORABLE'
            else: status='SAME_REFERENCE_RETAINED'
            r.update(target=k,status=status,current_anchor=None if b is None else b['anchor'],
                current_failures=None if b is None else b['entry_or_edge_failures'])
        lifecycles.append(dict(action_id=a['action_id'],physical=action['physical'],
            availability=action['availability_by_source_role'],independent_same_bank_seen_before_q=bool(past),
            references=list(past.values()),posthoc_GT_lookup=True,new_candidate_created=False))
        row=[]
        for b in action['bank']:
            if not b['actual_matrix_column']: continue
            p=b['distribution'];qterms=b['original_depth_query']['terms'] if b['original_depth_query'] else {}
            row.append(dict(target=b['id'],physical=b['used_depth_reference_physical'],selected=b['selected'],
                legal=b['legal_matrix_edge'],failures=b['entry_or_edge_failures'],
                core_wasserstein_mm=p['comparisons']['core']['wasserstein_mm'] if p and 'comparisons' in p else None,
                whole_wasserstein_mm=p['comparisons']['whole']['wasserstein_mm'] if p and 'comparisons' in p else None,
                original_cost_before_rejection=qterms.get('cost'),core_supported=p and p.get('both_core_supported')))
        def rank(role):
            scores=[(b[f'{role}_wasserstein_mm'],b['physical'],b['target']) for b in row if b[f'{role}_wasserstein_mm'] is not None]
            same=[d for d,r,_ in scores if r=='SAME']
            if not same: return 'NO_CORRECT_COLUMN'
            best=min(d for d,_,_ in scores);r=[r for d,r,_ in scores if d==best]
            return 'CORRECT_MINIMUM' if r==['SAME'] else 'OTHER_OR_TIED_MINIMUM'
        prefilter.append(dict(action_id=a['action_id'],global_frame=a['global_frame'],physical=action['physical'],
            rows=row,prefilter_rank={r:rank(r) for r in ('whole','core')},
            scope='ACTUAL_ORIGINAL_COLUMNS_BEFORE_EDGE_FILTERS; NO_GT_SELECTED_HISTORY'))
        for b in action['bank']:
            if b['physical_reference']!='SAME' or 'occupied' not in b['failures'] or b['id']==n: continue
            active=[int(source) for source,pid in s['current_public'].items() if pid==b['id']]
            owners.append(dict(action_id=a['action_id'],target=b['id'],active_sources=active,
                candidate_vs_current_occupant=[dict(native=src,relation=relation(current,matches[name][str(q)].get(str(src),{}))) for src in active],
                old_anchor=b['anchor'],occupied_target_cannot_be_assigned_twice=True))
        qualifying=[o for o in data['relative_order'] if o['action_id']==a['action_id'] and o['target']==a['target']
                    and o['status']=='SAME_VERSION_MEASURED_PROXY_ORDER']
        selected_orders.append(dict(action_id=a['action_id'],physical=action['physical'],qualified=len(qualifying),
            reversed=sum(o['raw_order_reversed'] is True for o in qualifying)))
    save('BANK_REFERENCE_LIFECYCLE.json',dict(actions=lifecycles,postseal_diagnostic_only=True,GT_raster=False))
    save('PREFILTER_DISTRIBUTION_RANKS.json',dict(actions=prefilter,postseal_diagnostic_only=True))
    save('OCCUPIED_REFERENCE_REVIEW.json',dict(records=owners,postseal_diagnostic_only=True))
    save('SELECTED_EDGE_ORDER_REVIEW.json',dict(actions=selected_orders,qualified_selected_witnesses=sum(r['qualified'] for r in selected_orders)))
    wrong=[p for p in prefilter if p['physical']=='WRONG']
    summary=dict(prefilter_wrong_ranks={r:dict(Counter(p['prefilter_rank'][r] for p in wrong)) for r in ('whole','core')},
        missing_bank_lifecycle=[dict(action_id=r['action_id'],ever_same=r['independent_same_bank_seen_before_q'],
            statuses=dict(Counter(x['status'] for x in r['references']))) for r in lifecycles
            if r['physical']=='WRONG' and not r['availability']['independent_bank_same']],
        selected_qualified_order_witnesses=sum(r['qualified'] for r in selected_orders),
        actual_original_entry_code=artifact(ORIGINAL/'online/closed_loop_2888/z4q_source/source/sam3_depth_failure_repair_20260917/repair_controller_r3.py'),
        exposed_diagnostic=True,new_tracker=False)
    depths=data['summary']['input_depth_descriptions']
    summary['depth_descriptive']={}
    for physical,group in depths.items():
        summary['depth_descriptive'][physical]={}
        for side in ('current','selected_reference'):
            records=[p[side] for p in group if p[side] is not None];d={}
            for metric in ('core_n','core_scale_mm','whole_core_gap_mm','patch_median_range_mm'):
                v=[p[metric] for p in records if p[metric] is not None]
                d[metric]=dict(n=len(v),median=float(np.median(v)) if v else None,
                    min=min(v) if v else None,max=max(v) if v else None)
            d['supported']=sum(p['core_support'] for p in records)
            summary['depth_descriptive'][physical][side]=d
    save('DEEP_REVIEW_DATA.json',summary)
    lines=['# DS38深度复盘','',
        '## 已确认的机制限制','',
        '17次错关联最终都没有合法的同物理旧参考边。7次缺少独立正确bank参考、5次在候选资格层被排除、5次正确列被旧边规则拒绝。这个结论只适用于本次曝光的Feeding错误队列。','',
        'D1原代码用`depth_residual/tolerance + 0.15*motion_cost`选择，dummy=1，运动只占小项，连续确认并未提供独立身份证据。深度接近的不同鱼会形成低成本错误边；正确鱼因深度变化、伙伴历史歧义或质量风险可能先被挡住。这里没有用GT修改原规则。','',
        '## 放回原有被拒列是否足够','',
        json.dumps(summary['prefilter_wrong_ranks'],ensure_ascii=False,indent=2),'',
        '这是原矩阵列过滤前的分布诊断，不是改候选池后的新成绩。只在F1516，whole/core完整分布的最小距离是正确参考；另外四次含正确列的错误中，分布最小值仍落在错误身份上。不能把“取消门槛+换分布距离”当成已经得到解法。','',
        'F1516：正确p136的core W1=12.204mm，选中错误p119=23.103mm，正确边被partner_ambiguous拒绝。F522：正确p22=50.503mm，错误选中p73=8.328mm；F1390：错误p126=11.342mm，正确p136/p167=57.551/63.933mm。不同鱼的深度分布确实可能更接近当前观测。','',
        '## 历史生命周期与占用','',
        'BANK_REFERENCE_LIFECYCLE.json逐例区分：原来从未留下可评分独立anchor、曾有但bank删除、被其他物理来源覆盖、当前anchor不可评分、仍保留但被规则排除。以上是旧数字reference-match摘要的事后诊断，不把这些GT找到的历史作为新输入。','',
        json.dumps(summary['missing_bank_lifecycle'],ensure_ascii=False,indent=2),'',
        '“occupied”保持一对一约束。OCCUPIED_REFERENCE_REVIEW.json另核当前占用观测；有同物理旧anchor也不能直接把两个现有mask写成同一public ID，不能把占用问题简化为放宽门槛。','',
        '## 混层、背景与质量','',
        json.dumps(summary['depth_descriptive'],ensure_ascii=False,indent=2),'',
        '这些量来自去重独立原始测量。whole/core和几何分区差只证明掩码内深度不均匀，不能区分鱼体倾斜、背景混入或上下鱼混合。原始depth的视角、配准误差与水下物理标定仍未知；当前core支持不能认证真实身体表面。','',
        '## 相对次序不能借用无关见证','',
        '全bank共有65条同版本、连续质量合格的次序比较，1244条UNKNOWN。但27条实际选中边的合格见证总数是0：不能把65条旧bank上的代理比较算成真实错误动作可被否决的证据。选择性放宽到命中也不能证明上下关系稳定。','',
        '## 性能和下一步边界','',
        '本轮只有原Z4Q逐帧一致的诊断回放，没有新跟踪策略或新指标涨跌。5项检查、实际入口/85条矩阵边与锚点核验、235个深度时刻/6289个观测、2019个分布比较、1309个次序记录均已保留。27张公开统计图和27组真实私有前后图覆盖全部提交。','',
        '下一步单一计划见NEXT_STEP.md；不在这批曝光错误上滚动找阈值，不自动启动下一实验。']
    (HERE/'DEEP_REVIEW.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__': main()
