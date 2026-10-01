"""Postseal DS9 diagnosis only: no replay, raster reads or decision-rule writes."""
import json
import math
from pathlib import Path
from collections import Counter

HERE=Path(__file__).resolve().parent
OLD=HERE.parents[1]/'ds9_joint_h0_depth'
RUN=OLD/'run'
ARM='J2_RESTORED_DEPTH'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def digest(p):return __import__('hashlib').sha256(Path(p).read_bytes()).hexdigest()
def intmap(m):return {int(k):v for k,v in (m or {}).items()}
def logadd(a,b):
 h=max(a,b);return h+math.log(math.exp(a-h)+math.exp(b-h))
def signature(s):return (s['segment'],s['frame'],s['gt_id'],s['native_id'])

def diagnose():
 seal=read(RUN/'SCORING_SEALED.json')
 for name in ('EVENT_AUDIT.json','METRICS.json','SWITCH_LEDGER.json','FRAGMENT_REFERENCE_AUDIT.json'):
  assert digest(RUN/name)==seal['artifacts_sha256'][name]
 audit=read(RUN/'EVENT_AUDIT.json');metrics=read(RUN/'METRICS.json')
 ledger=read(RUN/'SWITCH_LEDGER.json')['events'];fragment=read(RUN/'FRAGMENT_REFERENCE_AUDIT.json')
 frozen_refs={(x['segment'],x['event'],x['role']):x for x in fragment['roles'] if x['arm']==ARM}
 all_events=[];source_files=[]
 for segment in metrics['segment_metrics']:
  path=RUN/segment/'public/EVENTS.json';events=read(path)[ARM]
  all_events.extend(dict(e,segment=segment) for e in events)
  source_files.append(dict(path=str(path),sha256=digest(path)))
 facts={(e['segment'],e['event']):e for e in audit['events'] if e['arm']==ARM and e['q'] is not None}
 qs=[]
 for event in all_events:
  if event['q'] is None:continue
  a=facts[(event['segment'],event['id'])];d=a['score_detail'];expected=intmap(a['expected_mapping'])
  native={int(n):int(n) for n in a['first_public_mapping']};first=intmap(a['first_public_mapping'])
  correct_label=next((k for k,c in d['candidates'].items() if intmap(c['mapping'])==expected),None)
  if not expected:category='UNSCORABLE_POST_PAIR_NOT_SAME_BANK_IDENTITIES'
  elif native!=expected and first==expected:category='NATIVE_REFERENCE_BREAK_ALREADY_REPAIRED'
  elif native!=expected:category='IN_SCOPE_MISSED_REFERENCE_RECONNECTION'
  elif first==expected:category='NATIVE_CORRECT_KEPT'
  else:category='NEW_WRONG_PUBLICATION'
  exact_switches={arm:[s for s in ledger[arm] if s['segment']==event['segment'] and s['frame']==a['original_q']]
                 for arm in ('SAM3_NATIVE',ARM)}
  pair_switches={arm:[s for s in events if s['native_id'] in native] for arm,events in exact_switches.items()}
  breakdown={}
  for role,p in d['depth_forecasts'].items():
   ref=frozen_refs[(event['segment'],event['id'],role)]
   total=p['scale_mm']**2 if p['scale_mm'] is not None else None
   process=225*(1+(p['delta_seconds']/p['time_scale_seconds'])**2) if total is not None else None
   breakdown[role]=dict(status=p['status'],samples=p['samples'],mu_mm=p['mu_mm'],scale_mm=p['scale_mm'],
      actual_gap_seconds=p['delta_seconds'],pre_time_scale_seconds=p['time_scale_seconds'],
      process_variance_mm2=process,total_variance_mm2=total,
      process_fraction=process/total if total else None,
      wls_or_last_measurement_variance_mm2=total-process if total else None,
      slope_mm_s=p['slope_mm_s'],pre_rgb_identity_reference=ref['pre_identity_reference'],
      pre_reference_exclusions=ref['exclusions'],physical_depth_surface_identity='UNKNOWN')
  proof=None
  if category=='IN_SCOPE_MISSED_REFERENCE_RECONNECTION':
   correct=d['candidates'][correct_label];null=d['candidates']['H0']
   shared=[dict(role=p['role'],source=p['source'],geometry_log_lr=p['geometry']['log_lr'],
       depth_log_lr=p['depth']['log_lr']) for p in correct['pairs'] if
       any((p['role'],p['source'])==(q['role'],q['source']) for q in null['pairs'])]
   additions=[]
   for pair in correct['pairs']:
    if any((pair['role'],pair['source'])==(p['role'],p['source']) for p in shared):continue
    old_pair=next(p for p in null['pairs'] if p['source']==pair['source'])
    assert not old_pair['associated'] and pair['associated']
    observation=d['depth_assignment'][str(pair['source'])]
    noise=max(15.,1.4826*observation['observation_mad_mm'])
    minimum=math.hypot(15.,noise)
    peak=math.lgamma(2.5)-math.lgamma(2.)-.5*math.log(4*math.pi)-math.log(minimum)
    bg=pair['depth']['background_log_density']
    maximum_lr=logadd(math.log(.9)+peak-bg,math.log(.1))
    additions.append(dict(role=pair['role'],source=pair['source'],observed_mm=observation['observation_mm'],
        observed_mad_mm=observation['observation_mad_mm'],query_noise_mm=noise,
        assumed_best_possible_forecast_scale_mm=15.,assumed_best_possible_forecast_mean='EXACT_CURRENT_OBSERVATION',
        minimum_combined_scale_mm=minimum,maximum_t4_log_signal_density=peak,
        actual_whole_frame_log_background_density=bg,maximum_mixture_log_lr=maximum_lr,
        actual_depth_log_lr=pair['depth']['log_lr']))
   geom=correct['geometry_log_lr']-null['geometry_log_lr']
   maximum=geom+sum(p['maximum_mixture_log_lr'] for p in additions)
   proof=dict(correct_candidate=correct_label,shared_edges_cancel_exactly=shared,
       log_prior_difference=correct['log_prior']-null['log_prior'],geometry_difference=geom,
       actual_depth_difference=correct['depth_log_lr']-null['depth_log_lr'],
       actual_joint_difference=correct['log_score']-null['log_score'],new_edges=additions,
       idealized_joint_difference_upper_bound=maximum,log9=math.log(9.),
       below_threshold_even_with_impossible_ideal_forecast=maximum<math.log(9.),
       conditions=['unchanged geometry and H0 mapping','unchanged normalized t4/.9/.1 and whole-frame depth background',
         'forecast scale >=15mm and existing post noise floor','same-role same-source edge cancels across mappings',
         'uniform distinct-map priors; compare correct candidate against H0',
         'GT marks the correct map for diagnosis only; ideal mean is an analytic upper bound, never a decision input'])
  row=dict(original_q=a['original_q'],local_q=event['q'],segment=event['segment'],event=event['id'],category=category,
      bank_expected_mapping=expected,native_post_mapping=native,actual_first_public_mapping=first,
      native_pair_reference_correct=bool(expected and native==expected),first_public_reference=a['first_public_physical'],
      pre_entry_reference=a['pre_entry_reference'],depth_history=breakdown,
      original_native_switches_at_q=exact_switches['SAM3_NATIVE'],j2_switches_at_q=exact_switches[ARM],
      original_native_switches_on_post_sources_at_q=pair_switches['SAM3_NATIVE'],
      j2_switches_on_post_sources_at_q=pair_switches[ARM],
      latest_clear_identity_disagrees_with_bank_target=[dict(source=s['native_id'],gt_id=s['gt_id'],
        clear_previous_public=s['from_public_id'],bank_reference_target=expected.get(s['native_id']))
        for s in pair_switches['SAM3_NATIVE'] if expected and s['from_public_id']!=expected.get(s['native_id'])],
      choice=d['selected_mapping'],selected_hypothesis=a['selected_choice'],best=d['best'],margin=d['margin'],
      used_depth_edges=d['used_edges'],post_pair_usable=d['post_pair_usable'],commit_status=a['commit_status'],
      transaction_stage_error=event['restore']['stage_error'],visible_member_residual=a['residual'],
      candidates={k:{f:c[f] for f in ('mapping','geometry_log_lr','depth_log_lr','log_prior','log_score','posterior')}
                  for k,c in d['candidates'].items()},
      correct_candidate=correct_label,forecast_only_repair_upper_bound=proof,
      actual_post_measurement_facts=d['depth_assignment'],actual_background=d['background']['depth'])
  qs.append(row)
 assert len(qs)==19
 def temporal(arm):
  out=[]
  for s in ledger[arm]:
   q=next((e for e in qs if e['segment']==s['segment'] and e['original_q']==s['frame']),None)
   window=[e['id'] for e in all_events if e['segment']==s['segment'] and
      e['suspect_frame']<=s['local_frame']<=(e['end'] or len_range(e['segment']))]
   where=('EXACT_Q_ON_POST_SOURCE' if q and s['native_id'] in q['native_post_mapping'] else
          'EXACT_Q_OTHER_SOURCE' if q else 'IN_EVENT_WINDOW_WITHOUT_Q_DECISION' if window else 'OUTSIDE_ALL_EVENT_WINDOWS')
   out.append(dict(s,temporal_class=where,active_event_windows=window,q_case=q['event'] if q else None))
  return out
 detailed={arm:temporal(arm) for arm in ('SAM3_NATIVE',ARM)}
 source_by_sig={arm:{signature(s):s for s in ledger[arm]} for arm in ('SAM3_NATIVE',ARM)}
 native_sigs,j2_sigs=source_by_sig['SAM3_NATIVE'],source_by_sig[ARM]
 return dict(status='DS9_POSTSEAL_ALL_Q_AND_SWITCH_DIAGNOSIS',q_count=19,q_cases=sorted(qs,key=lambda x:x['original_q']),
    case_class_counts=dict(Counter(x['category'] for x in qs)),
    switch_class_counts={a:dict(Counter(x['temporal_class'] for x in xs)) for a,xs in detailed.items()},
    all_native_and_j2_switches=detailed,
    removed_native_physical_switch_events=[native_sigs[k] for k in native_sigs.keys()-j2_sigs.keys()],
    added_j2_physical_switch_events=[j2_sigs[k] for k in j2_sigs.keys()-native_sigs.keys()],
    same_physical_switch_with_changed_public_history=[dict(native=native_sigs[k],j2=j2_sigs[k])
       for k in native_sigs.keys()&j2_sigs.keys() if native_sigs[k]['from_public_id']!=j2_sigs[k]['from_public_id']],
    pooled_metrics={a:metrics['pooled_metrics'][a] for a in ('SAM3_NATIVE',ARM)},
    inferred_global_idtp={a:metrics['pooled_metrics'][a]['IDF1']/100*(metrics['pooled_metrics'][a]['GT']+
       metrics['pooled_metrics'][a]['predictions'])/2 for a in ('SAM3_NATIVE',ARM)},
    provenance=dict(inputs=source_files,score_seal_sha256=digest(RUN/'SCORING_SEALED.json')),
    method_recommendation='Jointly repair forecast extrapolation/uncertainty and detected-object-level H0 depth null; keep native policy, quality, geometry, distinct-map priors, log9, and guards.',
    user_current_target='Improve actual complete tracking against same-source SAM3_NATIVE; pure-geometry comparison is diagnostic only, not an acceptance gate.',
    scope='Exposed postseal RGB identity reference; no physical depth-mm or pixel-surface ground truth',
    no_gt_in_decision_rules=True,no_old_artifacts_modified=True,no_replay_or_new_metric_scoring=True)

def len_range(segment):
 start,stop=map(int,segment.removeprefix('feeding_').split('_'));return stop-start+1

def report(d):
 intro='''# DS9真实关联失败复盘：全部19个q与完整ID切换记录

本报告只读DS9封存事件、既有评分、RGB身份审计和切换记录；不重放、不重新评分、不改旧规则或seal。GT仅用于已曝光数据的诊断，不进入任何新选择规则。当前用户目标是超过同源SAM3_NATIVE，纯几何比较只作机制说明，不作为成功门槛。

## 核心结论

DS9 J2有19次首分离决策：9次保持原生正确身份、2次接回原生丢失的旧身份、4次漏掉已有bank一一对应的接回、4次当前post根本不是原bank两条鱼，无法评分为两边恢复。不能把19次H0或缺测全部算成关联失败。

Native共108次CLEAR IDSW，J2为106次；FP487/FN985/DetA89.730606不变。IDF1两者均80.97675951，按固定GT39706、predictions39208可还原全局IDTP均为31951。消除局部switch不必增加全局最优身份匹配的IDTP；具体每条track对全局Hungarian的抵消分量在既有摘要中未列，不能自行编造归因。HOTA/AssA略升，不能称已达到本轮用户的完整目标。

### 先区分事件覆盖和真正能接回的错误

只有8条native switch发生在19个q时点，其中7条在实际post source上，但只有6条属于有bank双射的恢复候选；另2条分别为F470的组外n81/GT4和F1280与bank另一鱼无关的错误post n168/GT5。其余100条在q之外，不是当前首分离选择器的直接决定。下面还把q外分成实际事件窗口内和触发窗口外；窗口内的其他鱼错号不因此成为该事件的合法member。

F1239接回167→136、F1745接回190→188，另一边分别128与9保持；两个native switch真正消除，未新增物理switch事件。但F1239接回的GT4在F1347再次发生native新ID：native为167→170，J2为136→170，同一物理switch仍然存在，只改变其from标签。恢复一次不等于后续身份持续。

F470特别需要单列：bank参考希望82→1，但CLEAR此前GT9的public已经是24，q记录24→82。进入事件前source1与bank仍是同一RGB参考，不代表群组期间GT9从未被carrier24覆盖。此时接回bank1也可能仍产生24→1的CLEAR切换，不能承诺消除当前switch。q同时另有n81/GT4的20→81错号，超出本事件两post。

## 全部19个q病例表

表中μ/σ仅为预测统计量，不能认证鱼体表面或mm准确度。A/B是该事件冻结角色；正确/错误均相对实际bank锚点RGB身份。背景模型、均匀候选先验、几何和log9均来自原冻结方法。

|q|原生/实际J2结果|参考应接回的两边|J2选择/事务|depth边|A历史点数 μ/σ mm|B历史点数 μ/σ mm|机制分类|
|---:|---|---|---|---:|---|---|---|
'''
 lines=[intro]
 names={'NATIVE_CORRECT_KEPT':'原生正确，保持','NATIVE_REFERENCE_BREAK_ALREADY_REPAIRED':'原生断号，已接回',
        'IN_SCOPE_MISSED_REFERENCE_RECONNECTION':'有参考的接回遗漏','UNSCORABLE_POST_PAIR_NOT_SAME_BANK_IDENTITIES':'post与bank不是同一两鱼，不可评分'}
 for x in d['q_cases']:
  desc=[]
  for r in ('A','B'):
   p=x['depth_history'][r]
   desc.append(f"{p['samples']} / {p['mu_mm']:.2f}/{p['scale_mm']:.2f}" if p['mu_mm'] is not None else f"{p['samples']} / UNKNOWN")
  expected=', '.join(f'{n}→{p}' for n,p in x['bank_expected_mapping'].items()) or 'UNKNOWN'
  lines.append(f"|{x['original_q']}|{'正确' if x['native_pair_reference_correct'] else '错误' if x['bank_expected_mapping'] else 'UNKNOWN'} / {x['first_public_reference']}|{expected}|{x['selected_hypothesis']} / {x['commit_status']}|{x['used_depth_edges']}|{desc[0]}|{desc[1]}|{names[x['category']]}|\n")
 lines.append('\n## 完整切换覆盖分类\n\n|分支|q两post|q其他source|事件窗口内但不在q|全部事件窗口外|\n|---|---:|---:|---:|---:|\n')
 for a,counts in d['switch_class_counts'].items():
  lines.append('|'+a+'|'+ '|'.join(str(counts.get(k,0)) for k in ['EXACT_Q_ON_POST_SOURCE','EXACT_Q_OTHER_SOURCE','IN_EVENT_WINDOW_WITHOUT_Q_DECISION','OUTSIDE_ALL_EVENT_WINDOWS'])+'|\n')
 lines.append('''
## 四个漏接回事件：失败机制与预测-only修复上界

这四次正确候选均为H1，相对H0只新增一条旧角色→新source关联；另一条相同role/source边的geometry、depth和prior精确抵消。H0新增source边使用共同背景LR0。设新增边得到不可能的理想预测：μ直接等于当前观测，forecast σ仅15mm；保留真实post噪声与原背景。归一化t4峰值为 Γ(2.5)/[Γ(2)√(4π)×combined_sigma]，因此下列是对任何仅改forecast的保守最优上界。它不是新算法，绝不输入GT或理想μ到选择器。

|q|正确−H0的geometry|当前depth差|当前joint差|理想预测depth最大LR|joint最大上界|log9是否可达|
|---:|---:|---:|---:|---:|---:|---|
''')
 for x in d['q_cases']:
  p=x['forecast_only_repair_upper_bound']
  if p:lines.append(f"|{x['original_q']}|{p['geometry_difference']:.6f}|{p['actual_depth_difference']:.6f}|{p['actual_joint_difference']:.6f}|{sum(z['maximum_mixture_log_lr'] for z in p['new_edges']):.6f}|{p['idealized_joint_difference_upper_bound']:.6f}|{'不能，低于2.197225' if p['below_threshold_even_with_impossible_ideal_forecast'] else '理论可达但历史不足'}|\n")
 lines.append('''
- **F470**：应恢复82→1，但A没有任何可用depth历史。B的旧WLS预测μ1987.27mm、斜率+921.04mm/s；当前两post仅1179.15/1158.64mm。这个均值外推已偏离当前观测，scale157.52mm中过程项只占8.48%，并非单纯“process过宽”。正确边A既无历史，其geometry LR也为负；只改process或WLS都不能跨越上界。群组carrier造成的此前public混用还限制即时IDSW修复。
- **F764**：应恢复118→100。对应B只有2点，保留末测量μ1181.42mm，与post1175.78mm接近；但σ544.09mm使深度新增边LR为−1.590263。99.91%的方差来自gap/pre-span过程项，但短历史不可凭GT答案收缩。即便理想σ15，整幅背景在1175.78mm附近密度很高，最大joint仍1.456293，无法到log9。
- **F1390**：应恢复172→170，B只有1点；旧末值μ1161.67mm，当前post1090.21mm，sigma363.35mm。正确候选虽最佳，joint margin仅0.098218。理想上界允许过门槛，但单点并不能证实真实速度、过去过程率或新的μ，所以必须保留short fallback，不能按GT造出新历史。
- **F1805**：应恢复194→149，A的WLS均值1124.42mm对当前1140.28mm并非严重偏差；但σ252.55mm，过程项只有8.04%，WLS均值传播σ242.18mm。pre拟合残差仅约3–5mm，不能因此直接把所有不确定性降到这个量。正确新增边depth LR为−1.116539，把geometry的+0.755392变为joint−0.361147。只改process不能处理主要传播项；即便μ/σ理想，whole-pixel背景限制仍使joint上界1.791705。

## 无法评分与事务拒绝不是同一个问题

F398/F434/F1280/F1504均有原member继续作为两post之外的residual，分别为59/3/88/132。根据封存RGB参考，当前post第二条鱼与原bank第二角色不一致：F434的新72是GT19，bank3是GT16；F1280的新168是GT5，bank88是GT26；F1504的新180是GT15，bank132是GT8。故不是两鱼真的分离后深度排错那么简单。原post提取仅依据上一group的mask覆盖/邻近和现有quality，可能把第三鱼当split source；guard正确阻止两身份硬写。

F434的深度让H2超过log9，实际却要把仍在场的source3身份移交给别的post；stage被visible-member-residual guard拒绝，发布依旧native/自身alias。绕过guard会把统计信号支持错误事件结构当作恢复。其余三个本身没有接受。新修复继续保留这些UNKNOWN和guard，不从GT筛去某个source，也不暗中扩大两member事务。

## 历史身份与物理深度来源边界

19个q的pre-entry角色均与各自实际bank锚点RGB参考一致。38个冻结depth角色中有30个有历史，既有逐sample参考审计均为同一RGB参考；8个无历史仍UNKNOWN，未发现可用pre depth片段跨到了其他RGB鱼身份。这个结论不能推广到group期间public归属或深度物理表面：F470的CLEAR历史就已不同于bank目标，mask内depth也可能取到水箱表面或错位表面。既有audit不含物理surface/mm真值。

## 最有证据的最小对应修复

需要同时处理两项明确深度模型问题，而不是降低log9或只把σ变小：

1. 足够同版本clean历史时用robust local-level末次真实z，移除短窗WLS斜率长期外推及其均值协方差传播；保留15/60测量floor，原gap增长过程项作为下限，并用过去非负增量扩散率保留动态不稳定证据。n≤2、无历史、版本/risk断开继续原predict/fallback，斜率未知不能写成0。
2. H0代表“当前已经检测到的鱼，但未知旧身份”，其depth null应使用当帧已有合格object测量的等权归一化t4混合，而不是整幅大部分tank像素的median/MAD。所有core_usable当前对象纳入，含query自身、不leaveout，每对象一票；按既有cohort保留15/60有效噪声，少于3component回到原whole-frame null。不能按GT/目标身份/面积挑component。

这是两项深度修复的一个联合版本，不能声称单次试验拆清各自收益。query-inclusive KDE给定当前facts时归一化，但属于数据自适应plug-in identity contrast，不是已校准Bayesian后验；合格mask仍可能采到背景，不能认证物理鱼体。完整4枝SAM3_NATIVE/F9_RESTORED/D10_RAW/D10_RESTORED单次冻结对照，保留所有帧、所有失败、GT仅封存后评分；主目标仅看真实深度枝相对sameNative的IDF1/HOTA/AssA和IDSW，不附加“必须胜纯几何”门槛。

### 尚不能承诺

上述修复不创造F470的缺失A历史，不改F1390的单点fallback，不处理触发窗口外大部分错号，也不保证全段IDTP提高。null和forecast只是因果统计模型，源空间配准、鱼体表面及mm准确度仍UNKNOWN。若最终不提点，必须按新真实逐事件发布和完整评分报告，不用改号数/可用像素数替代跟踪收益。
''')
 return ''.join(lines)

if __name__=='__main__':
 d=diagnose()
 for name,data in [('ASSOCIATION_FAILURE_DIAGNOSIS.json',json.dumps(d,ensure_ascii=False,indent=2,allow_nan=False)+'\n'),
                  ('ASSOCIATION_FAILURE_DIAGNOSIS.md',report(d))]:
  with (HERE/name).open('x',encoding='utf-8',newline='\n') as f:f.write(data)
 print(json.dumps({'cases':d['case_class_counts'],'switches':d['switch_class_counts']},ensure_ascii=False))
