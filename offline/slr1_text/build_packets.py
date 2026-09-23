"""Build model-visible packets from raw native predictions; never read GT."""
from common import *
sys.addaudithook(guard)
import numpy as np
import cv2
from collections import defaultdict
sys.path.insert(0,str(ROOT/'tools/sam3_depth_only_reconnect_20260916'))
from rle_decode import decode_rle
cv2.setNumThreads(1)
ASSIGN={'development':ROOT/'tools/sam3_occlusion_identity_20260915/i3_evidence_20260915_complete/identity_cpu10_20260915/run_8400/assignments.jsonl.gz',
 'validation':ROOT/'tools/sam3_depth_birth_quality_20260918/visual_comparison/native_validation_assignments.jsonl.gz'}
AH={'development':'49fc127d359566da392f401a68a304cc213d8e3ac702ad93e91894309200708b','validation':'ea468964e4b287a3879dfb83b304dd64c83f055e9649d3155fa62c41b717a0fc'}
def appearance(im,m):
 yy,xx=np.where(m)
 if len(xx)<16:return None
 xy=np.column_stack([xx,yy]);_,v=np.linalg.eigh(np.cov(xy.T));axis=v[:,-1]
 if axis[0]<0 or axis[0]==0 and axis[1]<0:axis=-axis
 projection=(xy-xy.mean(0))@axis;lo,hi=projection.min(),projection.max()
 frac=(projection-lo)/max(1e-6,hi-lo);idx=(frac>=.25)&(frac<=.75)
 b=np.zeros_like(m);b[yy[idx],xx[idx]]=True
 b=cv2.resize(b.astype('u1'),(1920,1080),interpolation=cv2.INTER_NEAREST).astype(bool)
 pixels=cv2.cvtColor(im,cv2.COLOR_BGR2HSV)[b]
 if len(pixels)<16:return None
 h=np.concatenate([np.histogram(pixels[:,i],bins=16,range=(0,180 if i==0 else 256))[0]/len(pixels) for i in range(3)])
 h=np.sqrt(h);h/=np.linalg.norm(h);return h.tolist()
def main():
 start=time.monotonic();cpu=limit_cpu();assert not (P/'PACKETS_ACCEPTANCE.json').exists()
 save(P/'STATUS.json',dict(stage='BUILDING_PACKETS',at=now(),pid=os.getpid(),cpu=cpu,model_calls=0))
 selectors=read(P/'SELECTORS.json');assert sha(P/'SELECTORS.json')==read(P/'SELECTION_ACCEPTANCE.json')['selectors_sha256']
 inputs={str(P/'SELECTORS.json'):sha(P/'SELECTORS.json')};old=read(STAGE/'E1_merge_freeze/INPUT_HASHES.json')
 obs={};profiles={};needed=defaultdict(set);references={}
 for split in ['development','validation']:
  op=ROOT/f'tools/sam3_depth_failure_repair_20260917/diagnosis_evidence/diagnosis/observations_{split}.jsonl.gz'
  fp=ROOT/f'tools/sam3_depth_birth_inherit_20260917/completion_evidence/features_r2/features_{split}.jsonl.gz'
  for p in [op,fp]:
   h=sha(p);assert h==old[str(p)];inputs[str(p)]=h
  obs[split]={r['global_frame']:r for r in rows(op)}
  profiles[split]={r['global_frame']:{x['id']:x for x in r['observations']} for r in rows(fp)}
  for r in obs[split].values():r['by_id']={x['id']:x for x in r['observations']}
 for e in selectors:
  split=e['split'];lower=2 if split=='development' else 9301
  for n in e['historical_native_ids']:
   found=[];fallback=[]
   for g in range(e['pre'],max(lower,e['pre']-119)-1,-1):
    o=obs[split][g]['by_id'].get(n)
    if o is None:continue
    fallback.append(g)
    if o['area']>=64 and o.get('presence') is not None and o['presence']>=.5 and not o['neighbors']:found.append(g)
   ref=sorted(found[:3] if found else fallback[:3]);references[(e['key'],n)]=(ref,bool(found))
   for g in ref:needed[(split,g)].add(n)
  for g in e['query_frames']:needed[(split,g)].update(obs[split][g]['by_id'])
 rles={}
 for split,ap in ASSIGN.items():
  h=sha(ap);assert h==AH[split];inputs[str(ap)]=h
  for r in rows(ap):
   g=r['frame']+(9300 if split=='validation' else 0)
   for n in needed.get((split,g),[]):rles[(split,g,n)]=r['masks'][f'n:{n}']
 print('Raw sources verified; extracting',len(rles),'unique native descriptors.',flush=True)
 manifest={r['frame_id']+1:r for r in map(json.loads,(DATA/'manifest.jsonl').read_text(encoding='utf-8').splitlines())}
 inputs[str(DATA/'manifest.jsonl')]=sha(DATA/'manifest.jsonl');features={};crop_index=[]
 for j,((split,g),ids) in enumerate(sorted(needed.items())):
  ip=DATA/manifest[g]['rgb_original'];h=sha(ip);assert h==manifest[g]['source_rgb_sha256'];inputs[str(ip)]=h
  im=cv2.imread(str(ip));assert im.shape[:2]==(1080,1920)
  for n in sorted(ids):
   o=obs[split][g]['by_id'][n];m=decode_rle(rles[(split,g,n)]);assert int(m.sum())==o['area']
   count,_,stats,_=cv2.connectedComponentsWithStats(m.astype('u1'),8)
   frac=float(stats[1:,cv2.CC_STAT_AREA].max()/m.sum()) if count>1 else None
   a=appearance(im,m);core=profiles[split][g][n]['core'];whole=profiles[split][g][n]['whole']
   ctr=None if not m.any() else np.array(np.where(m)[::-1]).mean(1).tolist()
   features[(split,g,n)]=dict(center_px=ctr,bbox_xyxy_px=o['box'],area_px=o['area'],presence=o['presence'],
    largest_component_fraction=frac,neighbor_count=len(o['neighbors']),raw_depth_mm=dict(whole=whole,core=core),
    appearance_hsv_body=a,mask_sha256=hashlib.sha256(m.tobytes()).hexdigest())
   if m.any():
    yy,xx=np.where(m);x0=max(0,int(xx.min())-8)*3;y0=max(0,int(yy.min())-8)*3;x1=min(640,int(xx.max())+9)*3;y1=min(360,int(yy.max())+9)*3
    name=alias('crop',f'{split}:{g}:{n}')+'.png';path=P/'review_crops'/name
    path.parent.mkdir(exist_ok=True);assert cv2.imwrite(str(path),im[y0:y1,x0:x1])
    crop_index.append(dict(frame=g,native_id=n,path=str(path.relative_to(P)),sha256=sha(path),bbox=[x0,y0,x1,y1]))
  if j%20==0:print('descriptor frames',j+1,'/',len(needed),flush=True)
 packets=[];private=[]
 for e in selectors:
  split=e['split'];pre=e['pre'];tracks={n:alias('T',e['key']+':'+str(n)) for n in e['historical_native_ids']}
  for stage,g in enumerate(e['query_frames']):
   t=obs[split][g]['time'];q=alias('Q',e['key']+':'+str(stage));idmap={n:alias('O',q+':'+str(n)) for n in obs[split][g]['by_id']}
   hist=[]
   for n in e['historical_native_ids']:
    ff,clean=references[(e['key'],n)];samples=[]
    for f in ff:
     samples.append(dict(evidence_id=alias('H',q+':'+str(f)+':'+str(n)),time_s=obs[split][f]['time']-t,**features[(split,f,n)]))
    velocity=None
    if len(samples)>=2:
     dt=samples[-1]['time_s']-samples[0]['time_s']
     if dt>0 and samples[0]['center_px'] is not None and samples[-1]['center_px'] is not None:
      velocity=((np.array(samples[-1]['center_px'])-samples[0]['center_px'])/dt).tolist()
    hist.append(dict(track=tracks[n],samples=samples,geometry_independent_reference=clean,
     ownership='unverified_native_lineage_proxy',velocity_px_s=velocity,velocity_source='past_only_reference_endpoints' if velocity else 'missing'))
   current=[dict(observation=idmap[n],time_s=0.0,**features[(split,g,n)]) for n in sorted(idmap)]
   pair=[]
   for hh in hist:
    refs=hh['samples'];last=refs[-1] if refs else None;age=-last['time_s'] if last else None
    avec=[x['appearance_hsv_body'] for x in refs if x['appearance_hsv_body'] is not None]
    av=np.median(avec,axis=0) if avec else None
    if av is not None:av/=np.linalg.norm(av)
    for c in current:
     costs={k:None for k in ['depth','appearance','motion']};weights={k:0.0 for k in costs};delta=None
     if last:
      d=last['raw_depth_mm']['core'];dd=c['raw_depth_mm']['core']
      if all(x['n']>=16 and x['valid_fraction']>=.2 and x['median'] is not None and x['mad'] is not None for x in [d,dd]):
       delta=abs(dd['median']-d['median']);costs['depth']=delta/(15+1.4826*(d['mad']+dd['mad']));weights['depth']=min(d['valid_fraction'],dd['valid_fraction'])
      if av is not None and c['appearance_hsv_body'] is not None:
       costs['appearance']=max(0.,float(1-np.dot(av,c['appearance_hsv_body'])))/.010273070237761233;weights['appearance']=1.
      if hh['velocity_px_s'] is not None and last['center_px'] is not None and c['center_px'] is not None:
       pred=np.array(last['center_px'])+np.array(hh['velocity_px_s'])*age
       box=last['bbox_xyxy_px'];diag=max(1.,float(np.linalg.norm(np.array(box[2:])-box[:2])))
       costs['motion']=float(np.linalg.norm(np.array(c['center_px'])-pred)/diag);weights['motion']=1/(1+age)
     if not hh['geometry_independent_reference']:
      weights={k:v*.25 for k,v in weights.items()}
     score=sum(costs[k]*weights[k] for k in costs if costs[k] is not None)/sum(weights.values()) if sum(weights.values()) else None
     pair.append(dict(track=hh['track'],observation=c['observation'],history_age_s=age,core_depth_difference_mm=delta,
      costs=costs,quality_weights=weights,available_modalities=sum(x is not None for x in costs.values()),weighted_cost=score))
   # Fixed causal timeline: future boundary fields never enter packet.
   frames=sorted(set(int(round(x)) for x in np.linspace(pre,g,5)))
   recent=[]
   for f in frames:
    rr=obs[split][f];recent.append(dict(time_s=rr['time']-t,observations=[dict(
     observation=alias('R',q+':'+str(f)+':'+str(o['id'])),bbox_xyxy_px=o['box'],area_px=o['area'],
     neighbor_count=len(o['neighbors']),raw_depth_mm=o['depth'],
     native_lineage_focal_track=tracks.get(o['id']),lineage_is_identity_proof=False) for o in rr['observations']]))
   packet=dict(schema='SLR1.numeric.v1',query_id=q,time_s=0.0,grid_px=[640,360],
    physical_3d_position=None,physical_size=None,focal_tracks=list(tracks.values()),history=hist,recent=recent,current=current,pairwise=pair,
    limitations=['History ownership is not verified; clean geometry does not prove identity.',
     'All current native observations are included; a mask is not guaranteed to be one object.',
     'Raw depth in millimetres is a visible-surface statistic, not calibrated fish length or water depth.',
     'This query was sampled offline; automatic event detection is not evaluated.'])
   assert all(x['time_s']<=0 for h in hist for x in h['samples']) and all(x['time_s']<=0 for x in recent)
   packets.append(packet);private.append(dict(query_id=q,event=e['key'],stage=['merge_snapshot','first_split'][stage],
    split=split,frame=g,pre=pre,track_native_map={v:k for k,v in tracks.items()},observation_native_map={v:k for k,v in idmap.items()},
    source_frames=sorted(set(frames+[f for n in tracks for f in references[(e['key'],n)][0]]))))
 save(P/'PACKETS.json',packets);save(P/'PRIVATE_INDEX.json',private);save(P/'CROP_INDEX.json',crop_index);save(P/'INPUT_HASHES.json',inputs)
 # Verify original input files remained unchanged after extraction.
 for path,h in inputs.items():assert sha(path)==h
 save(P/'PACKETS_ACCEPTANCE.json',dict(at=now(),exit_code=0,packets=len(packets),events=len(selectors),unique_features=len(features),
  source_frame_count=len(needed),model_calls=0,gt_reads=False,oracle_selectors=True,opened_paths=sorted(set(OPENED)),
  cpu=cpu,seconds=time.monotonic()-start,hashes={n:sha(P/n) for n in ['PACKETS.json','PRIVATE_INDEX.json','CROP_INDEX.json','INPUT_HASHES.json']}))
 save(P/'STATUS.json',dict(stage='PACKETS_READY',at=now(),packets=len(packets),model_calls=0))
 print('36 causal packets sealed, no GT reads; elapsed',round(time.monotonic()-start,2),flush=True)
if __name__=='__main__':main()
