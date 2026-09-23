"""D1: bounded depth reconnection repair; no temporal depth smoothing.
Source step adapted from frozen D_balanced, modifications specified in PLAN.md.
"""
import sys,math
from pathlib import Path
from copy import deepcopy
import numpy as np
from scipy.optimize import linear_sum_assignment
OLD=Path(__file__).resolve().parent.parent/'sam3_depth_identity_balance_20260917'
sys.path.insert(0,str(OLD))
from controller import DepthIdentityBalance,center

class DepthRepair(DepthIdentityBalance):
 def __init__(self):
  super().__init__('D_balanced');self.name='D1';self.first_eligible={}

 def step(self,frame,now,observations):
  obs=sorted(observations,key=lambda o:o['id']);native={o['id'] for o in obs}
  assert len(native)==len(obs)
  if self.first is None:self.first=frame
  events=[];edges=[]
  for o in obs:self.birth.setdefault(o['id'],(frame,now))
  # Flat aliases; preserve the current incumbent unless the original native ID returns.
  groups={}
  for n in sorted(native):groups.setdefault(self.alias.get(n,{}).get('target',n),[]).append(n)
  for k,members in groups.items():
   if len(members)<2:continue
   keep=k if k in members else max(members,key=lambda n:(self.native_seen.get(n,-1),-n))
   for n in members:
    if n!=keep:
     old=self.alias.pop(n,None);assert old is not None
     self.pending.pop(n,None);self.retired.add(n);self.counts['native_conflict_rollbacks']+=1
     events.append(dict(kind='native_conflict_rollback',native_id=n,canonical_id=k,keep_native=keep))
  occupied={self.alias.get(n,{}).get('target',n) for n in native}
  assert len(occupied)==len(native)
  for o in obs:
   k=self.alias.get(o['id'],{}).get('target',o['id'])
   if k not in self.bank:
    self.bank[k]=dict(last_seen=now,last_frame=frame,clean_count=0,clean_time=None,
                      depth_history=[],ema=None,motion=[],areas=[],partners={},contact_time=None)
   h=self.bank[k]
   for other in o.get('neighbors',[]):
    p=self.alias.get(other,{}).get('target',other)
    if p!=k:h['partners'][p]=now;h['contact_time']=now
  old=[]
  for k,h in sorted(self.bank.items()):
   if k in occupied or k in self.alias or h['clean_count']<5 or h['clean_time'] is None:continue
   if not 0<now-h['last_seen']<=6 or now-h['clean_time']>12:continue
   if h['contact_time'] is None or h['last_seen']-h['contact_time']>1:continue
   if self.cfg['use_depth'] and not h['depth_history']:continue
   old.append(k)
  new=[]
  for o in obs:
   n=o['id'];born=self.birth[n]
   if n in self.alias or n in self.retired or born[0]==self.first or not 0<=now-born[1]<=6:continue
   if not self.quality(o):continue
   if o.get('neighbors'):self.counts['new_contact_rejections']+=1;continue
   if self.cfg['use_depth'] and not self.depth_valid(o):self.counts['invalid_depth_rejections']+=1;continue
   self.first_eligible.setdefault(n,now)
   if now>min(born[1]+6,self.first_eligible[n]+3):continue
   new.append(o)
  terms={};new_pending={n:deepcopy(p) for n,p in self.pending.items() if n not in self.alias and now-p['time']<=.2 and now-p['start_time']<=.5}
  current_by_canonical={self.alias.get(o['id'],{}).get('target',o['id']):o for o in obs}
  if new and old:
   self.counts['candidate_rounds']+=1
   matrix=np.full((len(new),len(old)+len(new)),1e6)
   for i,o in enumerate(new):
    for j,k in enumerate(old):
     h=self.bank[k]
     t=self.motion(h,o,now);t.update(native_id=o['id'],canonical_id=k)
     reason=None
     if t['normalized_distance']>2:reason='outside_motion_range'
     if self.cfg['use_depth']:
      z=self.z(h);obsz=float(o['depth']['median']);hist=np.array([v for _,v in h['depth_history']])
      sigma=max(5.,1.4826*float(np.median(abs(hist-np.median(hist)))))
      tolerance=min(60.,15+3*sigma+3*t['age']);residual=abs(z-obsz)
      alternatives=[];reserved=[]
      # Partner IDs are current-frame/past prediction identities, never GT labels.
      for pk,contact in self.partners(h,k).items():
       if pk==o['id']:continue  # The candidate is one observation, not an independent partner.
       ph=self.bank.get(pk)
       if ph and ph['depth_history'] and ph['clean_time'] is not None and now-ph['clean_time']<=6 and h['last_seen']-contact<=1:
        po=current_by_canonical.get(pk)
        # k now has an isolated candidate o; other missing partners still prevent reservation.
        latent=any(p!=k and p not in occupied and 0<=now-ts<=6 for p,ts in self.partners(ph,pk).items())
        area_ref=float(np.median(ph['areas'])) if ph['areas'] else 0.
        area_ok=bool(po and area_ref>0 and .5*area_ref<=po['area']<=1.8*area_ref)
        reservation=bool(po and not po.get('neighbors') and not latent and area_ok and self.quality(po) and self.depth_valid(po) and ph['clean_count']>=5 and now-ph['clean_time']<=6 and abs(po['depth']['median']-self.z(ph))<=15)
        if reservation:
         reserved.append(dict(id=pk,own_history_depth=self.z(ph),current_depth=po['depth']['median'],candidate_residual_mm=abs(self.z(ph)-obsz),basis='native_continuity_plus_depth_compatibility'))
        else:alternatives.append(dict(id=pk,residual_mm=abs(self.z(ph)-obsz)))
      margin=min([a['residual_mm']-residual for a in alternatives],default=None)
      required=min(25.,max(10.,2*sigma))
      t.update(history_depth=z,current_depth=obsz,residual_mm=residual,tolerance_mm=tolerance,
               alternatives=alternatives,reserved_partners=reserved,partner_margin_mm=margin,required_partner_margin_mm=required)
      if residual>tolerance:reason=reason or 'depth_residual'
      elif margin is not None and margin<required:reason=reason or 'partner_ambiguous'
      cost=residual/tolerance+.15*t['motion_cost']
     else:
      cost=t['motion_cost']/.8
     t.update(cost=cost,rejection=reason);edges.append(t)
     if reason:
      self.counts['reject_'+reason]+=1
      if self.pending.get(o['id'],{}).get('target')==k:new_pending.pop(o['id'],None)
      continue
     terms[i,j]=t;matrix[i,j]=cost
    matrix[i,len(old)+i]=1.
   rr,cc=linear_sum_assignment(matrix);total=float(matrix[rr,cc].sum())
   for i,j in zip(rr,cc):
    if j>=len(old) or matrix[i,j]>=1:
     new_pending.pop(new[i]['id'],None);continue
    alt=matrix.copy();alt[i,j]=1e6;ar,ac=linear_sum_assignment(alt)
    margin=float(alt[ar,ac].sum()-total)
    if margin<.15:
     self.counts['assignment_ambiguous']+=1;new_pending.pop(new[i]['id'],None);continue
    o=new[i];n=o['id'];k=old[j];p=self.pending.get(n)
    continued=bool(p and p['target']==k and now-p['time']<=.2 and now-p['start_time']<=.5)
    count=p['count']+1 if continued else 1
    start_time=p['start_time'] if continued else now
    accepted=count>=self.cfg['confirm'];self.counts['proposals']+=1
    event=dict(kind='reconnect',accepted=accepted,confirmations=count,
               assignment_margin=margin,birth_frame=self.birth[n][0],confirmation_span_s=now-start_time,old_anchor=deepcopy(self.bank[k]['anchor']),**terms[i,j])
    events.append(event)
    if accepted:
     assert k not in occupied
     self.alias[n]=dict(target=k,anchor=deepcopy(self.bank[k]['anchor']),commit_frame=frame)
     self.bank.pop(n,None);occupied.add(k);self.counts['commits']+=1;new_pending.pop(n,None)
    else:new_pending[n]=dict(target=k,count=count,frame=frame,time=now,start_time=start_time)
  self.pending=new_pending
  ids={n:self.alias.get(n,{}).get('target',n) for n in native};assert len(set(ids.values()))==len(ids)
  for o in obs:
   n=o['id'];k=ids[n];h=self.bank[k]
   h['last_seen']=now;h['last_frame']=frame
   area_ref=float(np.median(h['areas'])) if h['areas'] else float(o['area'])
   area_ok=.5*area_ref<=o['area']<=1.8*area_ref
   # A merge often leaves one solitary mask: absence of current neighbours is
   # not evidence that the previously contacting fish have separated again.
   latent_merge=any(p not in occupied and 0<=now-t<=6 for p,t in self.partners(h,k).items())
   clean=self.quality(o) and not o.get('neighbors') and area_ok and not latent_merge
   if self.cfg['use_depth']:clean=clean and self.depth_valid(o)
   if clean:
    gap=now-h['clean_time'] if h['clean_time'] is not None else 0
    if gap>.5:h['motion']=[]
    h['motion']=(h['motion']+[(now,center(o['box']).tolist())])[-5:]
    h['clean_box']=list(o['box']);h['clean_time']=now;h['clean_count']+=1
    h['areas']=(h['areas']+[o['area']])[-15:]
    h['anchor']=dict(frame=frame,native_id=n,mask=o['mask'],canonical_id=k)
    if self.cfg['use_depth']:
     z=float(o['depth']['median']);h['depth_history']=(h['depth_history']+[(now,z)])[-15:]
     h['ema']=z if h['ema'] is None else .2*z+.8*h['ema']
   else:self.counts['frozen_history_frames']+=1
   self.native_seen[n]=frame
  trace=dict(events=events,edges=edges,eligible_old=len(old),eligible_new=len(new),
             aliases={str(n):dict(target=a['target'],anchor=a['anchor'],commit_frame=a['commit_frame']) for n,a in self.alias.items() if n in native})
  return ids,trace
