"""Prediction-only causal ID aliases. Native identities have first authority."""
from collections import Counter,deque
from copy import deepcopy
import math
import numpy as np
from scipy.optimize import linear_sum_assignment

CONFIGS={
 'G':dict(use_depth=False,confirm=5,smooth=False),
 'D_fast':dict(use_depth=True,confirm=2,smooth=False),
 'D_balanced':dict(use_depth=True,confirm=5,smooth=False),
 'D_conservative':dict(use_depth=True,confirm=10,smooth=False),
 'D_ewma':dict(use_depth=True,confirm=5,smooth=True),
}

def center(box):return (np.asarray(box[:2])+np.asarray(box[2:]))/2

class DepthIdentityBalance:
 def __init__(self,name='D_balanced'):
  self.name=name;self.cfg=dict(CONFIGS[name]);self.bank={};self.alias={};self.birth={}
  self.pending={};self.retired=set();self.native_seen={};self.counts=Counter();self.first=None

 def quality(self,o):
  if o['area']<64:return False
  presence=o.get('presence')
  if presence is not None and (not math.isfinite(presence) or presence<.5):return False
  if presence is None and o.get('score_birth',0)<.5:return False
  return True

 def depth_valid(self,o):
  d=o.get('depth',{});z=d.get('median')
  return z is not None and math.isfinite(z) and z>0 and d.get('n',0)>=16 and d.get('valid_fraction',0)>=.2

 def z(self,h):return h['ema'] if self.cfg['smooth'] else h['depth_history'][-1][1]

 def partners(self,h,identity):
  result={}
  for p,t in h['partners'].items():
   resolved=self.alias.get(p,{}).get('target',p)
   if resolved!=identity:result[resolved]=max(t,result.get(resolved,-float('inf')))
  return result

 def motion(self,h,o,now):
  age=now-h['clean_time'];box=np.asarray(h['clean_box'],dtype=float)
  diag=max(1.,float(np.linalg.norm(box[2:]-box[:2])));history=h['motion']
  vv=[(np.asarray(b[1])-a[1])/(b[0]-a[0]) for a,b in zip(history,history[1:]) if 0<b[0]-a[0]<=.5]
  velocity=np.median(vv,axis=0) if vv else np.zeros(2)
  speed=float(np.linalg.norm(velocity));velocity*=min(1.,3*diag/max(speed,1e-9));speed=float(np.linalg.norm(velocity))
  predicted=center(box)+velocity*min(age,1.)
  radius=diag*(.5+.5*age)+.25*speed*age
  distance=float(np.linalg.norm(center(o['box'])-predicted));normalized=distance/max(radius,1.)
  return dict(age=age,distance=distance,radius=radius,normalized_distance=normalized,
              motion_cost=1-math.exp(-.5*normalized**2))

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
   if not 0<now-h['last_seen']<=6 or now-h['clean_time']>6:continue
   if h['contact_time'] is None or h['last_seen']-h['contact_time']>1:continue
   if self.cfg['use_depth'] and not h['depth_history']:continue
   old.append(k)
  new=[]
  for o in obs:
   n=o['id'];born=self.birth[n]
   if n in self.alias or n in self.retired or born[0]==self.first or not 0<=now-born[1]<=1:continue
   if not self.quality(o):continue
   if o.get('neighbors'):self.counts['new_contact_rejections']+=1;continue
   if self.cfg['use_depth'] and not self.depth_valid(o):self.counts['invalid_depth_rejections']+=1;continue
   new.append(o)
  terms={};new_pending={}
  if new and old:
   self.counts['candidate_rounds']+=1
   matrix=np.full((len(new),len(old)+len(new)),1e6)
   for i,o in enumerate(new):
    for j,k in enumerate(old):
     h=self.bank[k]
     if h['last_frame']>=self.birth[o['id']][0]:continue
     t=self.motion(h,o,now);t.update(native_id=o['id'],canonical_id=k)
     reason=None
     if t['normalized_distance']>2:reason='outside_motion_range'
     if self.cfg['use_depth']:
      z=self.z(h);obsz=float(o['depth']['median']);hist=np.array([v for _,v in h['depth_history']])
      sigma=max(5.,1.4826*float(np.median(abs(hist-np.median(hist)))))
      tolerance=min(60.,15+3*sigma+3*t['age']);residual=abs(z-obsz)
      alternatives=[]
      # Partner IDs are current-frame/past prediction identities, never GT labels.
      for pk,contact in self.partners(h,k).items():
       ph=self.bank.get(pk)
       if ph and ph['depth_history'] and ph['clean_time'] is not None and now-ph['clean_time']<=6 and h['last_seen']-contact<=1:
        alternatives.append(dict(id=pk,residual_mm=abs(self.z(ph)-obsz)))
      margin=min([a['residual_mm']-residual for a in alternatives],default=None)
      required=min(25.,max(10.,2*sigma))
      t.update(history_depth=z,current_depth=obsz,residual_mm=residual,tolerance_mm=tolerance,
               alternatives=alternatives,partner_margin_mm=margin,required_partner_margin_mm=required)
      if residual>tolerance:reason=reason or 'depth_residual'
      elif margin is not None and margin<required:reason=reason or 'partner_ambiguous'
      elif margin is None and residual>.5*tolerance:reason=reason or 'single_candidate_weak_depth'
      cost=residual/tolerance+.15*t['motion_cost']
     else:
      cost=t['motion_cost']/.8
     t.update(cost=cost,rejection=reason);edges.append(t)
     if reason:self.counts['reject_'+reason]+=1;continue
     terms[i,j]=t;matrix[i,j]=cost
    matrix[i,len(old)+i]=1.
   rr,cc=linear_sum_assignment(matrix);total=float(matrix[rr,cc].sum())
   for i,j in zip(rr,cc):
    if j>=len(old) or matrix[i,j]>=1:continue
    alt=matrix.copy();alt[i,j]=1e6;ar,ac=linear_sum_assignment(alt)
    margin=float(alt[ar,ac].sum()-total)
    if margin<.15:self.counts['assignment_ambiguous']+=1;continue
    o=new[i];n=o['id'];k=old[j];p=self.pending.get(n)
    count=p['count']+1 if p and p['target']==k and p['frame']==frame-1 else 1
    accepted=count>=self.cfg['confirm'];self.counts['proposals']+=1
    event=dict(kind='reconnect',accepted=accepted,confirmations=count,
               assignment_margin=margin,birth_frame=self.birth[n][0],old_anchor=deepcopy(self.bank[k]['anchor']),**terms[i,j])
    events.append(event)
    if accepted:
     assert k not in occupied
     self.alias[n]=dict(target=k,anchor=deepcopy(self.bank[k]['anchor']),commit_frame=frame)
     self.bank.pop(n,None);occupied.add(k);self.counts['commits']+=1
    else:new_pending[n]=dict(target=k,count=count,frame=frame)
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

def mechanism_tests():
 def o(n,z=700.,x=0.,neighbors=(),area=400,presence=.95):
  return dict(id=n,mask=f'n:{n}',box=[x,0,x+20,20],area=area,score_birth=.95,presence=presence,
              neighbors=list(neighbors),depth=dict(n=area,valid_fraction=1.,median=z,mad=2.))
 def seed(c):
  for f in range(1,21):c.step(f,f/30,[o(1),o(2,850,40)])
  frozen=deepcopy(c.bank[1]['depth_history'])
  c.step(21,21/30,[o(1,800,neighbors=[2]),o(2,800,40,[1])])
  assert c.bank[1]['depth_history']==frozen
 for name,count in [('D_fast',2),('D_balanced',5),('D_conservative',10),('D_ewma',5)]:
  c=DepthIdentityBalance(name);seed(c)
  for f in range(22,22+count):
   ids,_=c.step(f,f/30,[o(9,702,3),o(2,850,40)])
   assert ids[9]==(1 if f==21+count else 9)
  assert c.step(40,40/30,[o(1),o(9),o(2,850,40)])[0][9]==9
  assert 9 in c.retired
 c=DepthIdentityBalance();seed(c)
 for f in range(22,35):assert c.step(f,f/30,[o(1),o(9),o(2,850,40)])[0][9]==9
 for invalid in [None,0.,float('nan')]:
  c=DepthIdentityBalance()
  for f in range(1,40):
   rows=[o(1 if f<22 else 9,invalid),o(2,invalid,40)]
   if f==21:rows[0]['neighbors']=[2];rows[1]['neighbors']=[1]
   assert c.step(f,f/30,rows)[0]=={r['id']:r['id'] for r in rows}
 c=DepthIdentityBalance();seed(c)
 for f in range(22,30):assert c.step(f,f/30,[o(9,849,3),o(2,850,40)])[0][9]==9
 # Expired depth history and old masks present cannot be stolen.
 c=DepthIdentityBalance();seed(c)
 for f in range(22,30):assert c.step(f,8+f/30,[o(9),o(2,850,40)])[0][9]==9
 c=DepthIdentityBalance();seed(c)
 c.step(22,22/30,[o(1,1100,area=1600),o(2,850,40)])
 assert c.bank[1]['depth_history'][-1][1]==700
 c=DepthIdentityBalance();seed(c);frozen=deepcopy(c.bank[1])
 for f in range(22,28):c.step(f,f/30,[o(1,775,area=600)])
 for key in ['depth_history','motion','anchor','clean_time','areas']:
  assert c.bank[1][key]==frozen[key],key
 c.step(28,28/30,[o(1,704),o(2,850,40)])
 assert c.bank[1]['depth_history'][-1][1]==704
 c=DepthIdentityBalance();seed(c)
 c.bank[4]=c.bank.pop(2)
 c.alias[2]=dict(target=4,anchor=deepcopy(c.bank[4]['anchor']),commit_frame=21)
 _,trace=c.step(22,22/30,[o(9,702,3),o(2,850,40)])
 edge=next(e for e in trace['edges'] if e['canonical_id']==1)
 assert [a['id'] for a in edge['alternatives']]==[4]
 a=DepthIdentityBalance();b=DepthIdentityBalance()
 for f in range(1,50):
  rows=[o(1 if f<22 else 9),o(2,850,40)]
  if f==21:rows[0]['neighbors']=[2];rows[1]['neighbors']=[1]
  assert a.step(f,f/30,rows)==b.step(f,f/30,rows[::-1])
 # G does not access depth: a dictionary that raises on all depth reads is harmless.
 class Forbidden(dict):
  def get(self,*args):raise AssertionError('G read depth')
 c=DepthIdentityBalance('G')
 for f in range(1,35):
  rows=[o(1 if f<22 else 9),o(2,850,40)]
  for r in rows:r['depth']=Forbidden()
  if f==21:rows[0]['neighbors']=[2];rows[1]['neighbors']=[1]
  c.step(f,f/30,rows)
 assert c.counts['commits']==1
 return dict(passed=True,checks=21,scope='confirmation timing, contact-to-single-mask freeze, alias partner resolution, conflicts, invalid depth, causal ordering, G no depth access')

if __name__=='__main__':print(mechanism_tests())
