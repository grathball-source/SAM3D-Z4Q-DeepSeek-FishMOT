"""Causal birth-only depth association; immutable D1 supplies the fallback."""
from pathlib import Path
import copy,math,sys
from collections import Counter
import numpy as np
from scipy.optimize import linear_sum_assignment
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'sam3_depth_failure_repair_20260917'))
from repair_controller_r3 import DepthRepair

class BirthRefine(DepthRepair):
 def __init__(self,config,enabled=True):
  super().__init__();self.birth_config=copy.deepcopy(config);self.birth_enabled=enabled
  self.view_bank={};self.birth_counts=Counter()

 def measurement(self,p,view):
  d={} if p is None else p.get(view,{})
  if any(d.get(k) is None or not math.isfinite(d[k]) for k in ['median','mad']):return None
  if d['median']<=0 or d['mad']<0 or d.get('n',0)<self.birth_config['min_points'] or d.get('valid_fraction',0)<self.birth_config['min_valid_fraction']:return None
  u=max(self.birth_config['risk_floor_mm'],self.birth_config['mad_scale']*d['mad'])
  if u>self.birth_config['risk_budget_mm']:return None
  return dict(z=float(d['median']),u=float(u),n=d['n'],fraction=d['valid_fraction'],mad=float(d['mad']))

 def history(self,k,view,frame,now):
  h=self.view_bank.get(k,{}).get(view)
  if h is None:return None
  assert h['anchor']['frame']<frame and h['time']<now and h['anchor']['canonical_id']==k
  if h['count']<self.birth_config['min_history_count'] or now-h['time']>self.birth_config['max_history_age_s']:return None
  return copy.deepcopy(h)

 def comparison(self,a,b):
  if a is None or b is None:return None
  r=abs(a['z']-b['z']);u=max(a['u'],b['u'])
  return dict(residual_mm=r,risk_mm=u,lower_mm=max(0.,r-u),upper_mm=r+u,cost=(r+u)/self.birth_config['risk_budget_mm'])

 def whole_veto(self,target,alternative=None):
  if target is None:return None
  if target['lower_mm']>self.birth_config['risk_budget_mm']:return 'whole_explicit_target_conflict'
  if alternative is not None and alternative['upper_mm']+self.birth_config['whole_veto_margin_mm']<target['lower_mm']:return 'whole_explicit_competitor'
  return None

 def edge(self,frame,now,o,k,profiles,occupied,current,born,old):
  h=self.bank[k];p=profiles.get(o['id']);cc=self.measurement(p,'core');cw=self.measurement(p,'whole')
  hc=self.history(k,'core',frame,now);hw=self.history(k,'whole',frame,now)
  core=self.comparison(cc,hc);whole=self.comparison(cw,hw)
  t=self.motion(h,o,now);fail=[]
  t.update(native_id=o['id'],canonical_id=k,phase='birth',evidence_max_frame=frame,
   old_anchor=None if hc is None else hc['anchor'],depth_anchors=dict(core=hc,whole=hw),
   current_depths=dict(core=cc,whole=cw),core=core,whole=whole,partners=[],excluded_partners=[],failures=fail)
  if t['normalized_distance']>2:fail.append('outside_motion_range')
  if not self.quality(o):fail.append('current_quality_invalid')
  if cc is None:fail.append('current_core_unavailable')
  if hc is None:fail.append('target_core_history_unavailable')
  if core is not None and core['cost']>=1:fail.append('target_core_risk')
  w=self.whole_veto(whole)
  if w:fail.append(w)
  historical={q for q,ts in self.partners(h,k).items() if 0<=h['last_seen']-ts<=1}
  local={self.alias.get(n,{}).get('target',n) for n in o.get('neighbors',[])}-{k,o['id']}
  related=local|{q for q in historical if q not in occupied}
  related-={k,o['id']}
  for q in sorted(historical-related):t['excluded_partners'].append(dict(id=q,reason='historical_active_not_current_neighbor'))
  witnesses=0
  for q in sorted(related):
   pc=self.history(q,'core',frame,now);pw=self.history(q,'whole',frame,now)
   alt=self.comparison(cc,pc);aw=self.comparison(cw,pw)
   d=dict(id=q,active=q in occupied,current_neighbor=q in local,historical_direct=q in historical,
    core_history=pc,whole_history=pw,candidate_core=alt,candidate_whole=aw,state='unknown',failures=[])
   veto=self.whole_veto(whole,aw)
   if veto:d['failures'].append(veto)
   ownw=crossw=None
   if q in occupied:
    po=current[q];sw=self.measurement(profiles.get(po['id']),'whole')
    ownw=self.comparison(sw,pw);crossw=self.comparison(sw,hw)
    d.update(current_whole=sw,own_whole=ownw,cross_whole=crossw)
    own_veto=self.whole_veto(ownw,crossw)
    if own_veto:d['failures'].append('survivor_'+own_veto)
   if pc is None or core is None:
    d['failures'].append('related_identity_unresolved')
   elif q not in occupied:
    d['core_margin']=alt['cost']-core['cost']
    if d['core_margin']<self.birth_config['assignment_margin']:d['failures'].append('dormant_core_competitor')
    else:d['state']='excluded_by_depth'
   else:
    po=current[q];cp=profiles.get(po['id']);sc=self.measurement(cp,'core');sw=self.measurement(cp,'whole')
    own=self.comparison(sc,pc);cross=self.comparison(sc,hc)
    ph=self.bank.get(q);area_ref=float(np.median(ph['areas'])) if ph and ph['areas'] else 0.
    survivor_quality=self.quality(po) and .5*area_ref<=po['area']<=1.8*area_ref
    d.update(current_core=sc,current_whole=sw,own_core=own,cross_core=cross,own_whole=ownw,cross_whole=crossw,survivor_quality=survivor_quality)
    if sc is not None and own is not None and cross is not None:
     margin=alt['cost']+cross['cost']-core['cost']-own['cost'];d['joint_core_margin']=margin
     if margin<self.birth_config['assignment_margin']:d['failures'].append('joint_core_opposed_or_ambiguous')
     if survivor_quality and own['cost']<1 and margin>=self.birth_config['assignment_margin'] and not d['failures']:
      d['state']='support';witnesses+=1
     if not survivor_quality:d['failures'].append('survivor_observation_unreliable')
     if own['cost']>=1:d['failures'].append('survivor_core_incompatible')
    else:
     d['failures'].append('related_current_core_unmeasured')
   if d['failures']:
    d['state']='unknown' if any(x in d['failures'] for x in ['related_identity_unresolved','related_current_core_unmeasured']) else 'oppose_or_ambiguous'
    fail.extend('partner_'+str(q)+'_'+x for x in d['failures'])
   t['partners'].append(d)
  # Whole may explicitly contradict the target even for another available
  # unoccupied identity outside the historical contact set.
  t['whole_other_candidates']=[]
  for q in old:
   if q==k or q in related:continue
   qm=self.motion(self.bank[q],o,now)
   if qm['normalized_distance']>2:
    t['whole_other_candidates'].append(dict(id=q,excluded='outside_motion_range',normalized_distance=qm['normalized_distance']));continue
   aw=self.comparison(cw,self.history(q,'whole',frame,now));veto=self.whole_veto(whole,aw)
   t['whole_other_candidates'].append(dict(id=q,comparison=aw,veto=veto))
   if veto:fail.append('candidate_'+str(q)+'_'+veto)
  if witnesses<1:fail.append('no_verified_local_survivor')
  cost=None if core is None else core['cost']+self.birth_config['motion_weight']*t['motion_cost']
  if cost is not None and cost>=1:fail.append('total_cost_exceeds_dummy')
  t.update(survivor_witnesses=witnesses,cost=cost,rejection=fail[0] if fail else None)
  return t

 def step(self,frame,now,observations,profiles=None):
  profiles={} if profiles is None else profiles
  for n,p in profiles.items():assert p['frame']==frame and p['id']==n and p['mask']==f'n:{n}'
  obs=sorted(observations,key=lambda o:o['id']);native={o['id'] for o in obs};checks=[];events=[]
  born=[o for o in obs if o['id'] not in self.birth] if self.first is not None else []
  if self.birth_enabled and born:
   self.birth_counts['births']+=len(born);occupied={self.alias.get(n,{}).get('target',n) for n in native}
   current={self.alias.get(o['id'],{}).get('target',o['id']):o for o in obs};conflict=len(occupied)!=len(native)
   old=[];eligibility=[]
   for k,h in sorted(self.bank.items()):
    reasons=[]
    if k in occupied:reasons.append('occupied')
    if k in self.alias:reasons.append('alias_source')
    if h['clean_count']<5:reasons.append('insufficient_D1_history')
    if h['clean_time'] is None:reasons.append('no_D1_clean_anchor')
    elif now-h['clean_time']>12:reasons.append('D1_history_expired')
    if not 0<now-h['last_seen']<=6:reasons.append('not_recently_missing')
    if h['contact_time'] is None or h['last_seen']-h['contact_time']>1:reasons.append('no_recent_interaction')
    if not h['depth_history']:reasons.append('no_D1_depth_history')
    eligibility.append(dict(id=k,eligible=not reasons,failures=reasons,last_seen_age_s=now-h['last_seen'],clean_age_s=None if h['clean_time'] is None else now-h['clean_time'],clean_count=h['clean_count']))
    if not reasons:old.append(k)
   matrix=np.full((len(born),len(old)+len(born)),1e6);terms={}
   for i,o in enumerate(born):
    matrix[i,len(old)+i]=1.
    if conflict:
     checks.append(dict(native_id=o['id'],rejection='existing_alias_conflict_defer_to_D1',failures=['existing_alias_conflict_defer_to_D1'],evidence_max_frame=frame,old_eligibility=eligibility));continue
    for j,k in enumerate(old):
     t=self.edge(frame,now,o,k,profiles,occupied,current,{x['id'] for x in born},old);t['old_eligibility']=eligibility;checks.append(t)
     if not t['failures'] and t['cost'] is not None:matrix[i,j]=t['cost'];terms[i,j]=t
    if not old:checks.append(dict(native_id=o['id'],rejection='no_eligible_unoccupied_history',failures=['no_eligible_unoccupied_history'],evidence_max_frame=frame,old_eligibility=eligibility))
   rr,cc=linear_sum_assignment(matrix);total=float(matrix[rr,cc].sum());accepted=[]
   for i,j in zip(rr,cc):
    if j>=len(old) or matrix[i,j]>=1:continue
    alt=matrix.copy();alt[i,j]=1e6;ar,ac=linear_sum_assignment(alt);margin=float(alt[ar,ac].sum()-total);t=terms[i,j]
    if margin<self.birth_config['assignment_margin']:
     t['failures'].append('assignment_ambiguous');t['rejection']='assignment_ambiguous';continue
    t['assignment_margin']=margin;accepted.append((born[i],old[j],t))
   for o,k,t in accepted:
    n=o['id'];assert k not in occupied and n not in self.alias
    self.alias[n]=dict(target=k,anchor=copy.deepcopy(t['old_anchor']),commit_frame=frame)
    self.pending.pop(n,None);self.bank.pop(n,None);self.view_bank.pop(n,None);occupied.add(k)
    self.birth_counts['commits']+=1
    events.append(dict(kind='reconnect',accepted=True,confirmations=1,birth_frame=frame,confirmation_span_s=0.,extra_confirmation_frames=0,first_public_id=k,**copy.deepcopy(t)))
  areas_before={k:list(h['areas']) for k,h in self.bank.items()}
  ids,tr=super().step(frame,now,obs)
  reset=set()
  for e in tr['events']:
   if e['kind']=='native_conflict_rollback':
    reset.update([e['native_id'],e['canonical_id']])
  for k in list(self.view_bank):
   if k not in self.bank or k in reset:self.view_bank.pop(k,None)
  occupied=set(ids.values())
  for o in obs:
   n=o['id'];k=ids[n];h=self.bank[k]
   if k in reset:continue
   previous_areas=areas_before.get(k,[])
   area_ref=float(np.median(previous_areas)) if previous_areas else float(o['area'])
   latent=any(q not in occupied and 0<=now-ts<=6 for q,ts in self.partners(h,k).items())
   common_clean=self.quality(o) and not o.get('neighbors') and .5*area_ref<=o['area']<=1.8*area_ref and not latent
   if not common_clean:continue
   a=dict(frame=frame,native_id=n,mask=o['mask'],canonical_id=k);p=profiles.get(n)
   for view in ['core','whole']:
    m=self.measurement(p,view)
    if m is None:continue
    oldview=self.view_bank.get(k,{}).get(view)
    count=1 if oldview is None or now-oldview['time']>self.birth_config['max_history_age_s'] else oldview['count']+1
    self.view_bank.setdefault(k,{})[view]=dict(m,anchor=copy.deepcopy(a),time=now,count=count)
  if self.birth_enabled:tr['events']=events+tr['events'];tr['birth_checks']=checks
  assert len(set(ids.values()))==len(ids)==len(native)
  return ids,tr

 def d1_state(self):
  return {k:v for k,v in vars(self).items() if k not in ['birth_config','birth_enabled','view_bank','birth_counts']}
