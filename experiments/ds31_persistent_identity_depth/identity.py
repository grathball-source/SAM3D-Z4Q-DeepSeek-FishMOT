"""PID bank and frame-local source handles are separate; commit precedes publish."""
from common import *
import copy, math, numpy as np
from scipy.optimize import linear_sum_assignment
from pycocotools import mask as coco
from depth import extract,forecast,costs
CFG=read(HERE/'CONFIG.json')

def center(o):return np.array([(o['box'][0]+o['box'][2])/2,(o['box'][1]+o['box'][3])/2])
def diag(o):return max(1.,math.hypot(o['box'][2]-o['box'][0],o['box'][3]-o['box'][1]))
def decode(r):return coco.decode(dict(size=r['size'],counts=r['counts'].encode('ascii'))).astype(bool)
def prediction(bank,now):
    ss=bank['motion'][-CFG['fit_observations']:];last=ss[-1];dt=now-last['time'];v=np.zeros(2);res=[]
    if len(ss)>=3:
        ts=np.array([s['time']-last['time'] for s in ss]);xy=np.array([s['center'] for s in ss])
        design=np.column_stack((np.ones(len(ts)),ts));beta=np.linalg.lstsq(design,xy,rcond=None)[0]
        v=np.clip(beta[1],-CFG['motion_clip_px_s'],CFG['motion_clip_px_s']);res=(xy-design@beta).tolist()
    shift=v*min(dt,CFG['prediction_horizon_seconds'])
    return np.asarray(last['center'])+shift,dict(status='OLS' if len(ss)>=3 else 'UNKNOWN_VELOCITY_LAST_POSITION',
        velocity_px_s=v.tolist() if len(ss)>=3 else None,residual_px=res,sample_frames=[s['frame'] for s in ss],
        sample_versions=[s['version'] for s in ss],gap_seconds=dt,horizon_seconds=min(dt,CFG['prediction_horizon_seconds']),shift_px=shift.tolist())

def match(values,edges):
    n,m=values.shape
    if not n or not m:return [],dict(best_cost=n*CFG['dummy_cost'],pairs=[])
    matrix=np.full((n,m+n),1e6);matrix[:,:m]=np.where(edges,values,1e6)
    matrix[np.arange(n),m+np.arange(n)]=CFG['dummy_cost']
    def solve(forbid=None):
        trial=matrix.copy()
        if forbid is not None:trial[forbid]=1e6
        rr,cc=linear_sum_assignment(trial)
        return float(trial[rr,cc].sum()),list(zip(rr.tolist(),cc.tolist()))
    best,pairs=solve();accepted=[];details=[]
    for i,j in pairs:
        if j>=m:continue
        margin=solve((i,j))[0]-best;ok=margin>=CFG['global_margin']
        details.append(dict(row=i,col=j,margin=margin,accepted=ok))
        if ok:accepted.append((i,j,margin))
    return accepted,dict(best_cost=best,pairs=details,dummy_cost=CFG['dummy_cost'])

class Identity:
    def __init__(self,arm,suspects):
        self.arm=arm;self.bank={};self.sources={};self.groups=[];self.events=[];self.suspects=suspects;self.group_masks={}
        self.used=set();self.next_pid=1000000;self.version=0;self.previous={}
    def allocate(self,n):
        if n not in self.used:k=n
        else:
            while self.next_pid in self.used:self.next_pid+=1
            k=self.next_pid;self.next_pid+=1
        self.used.add(k);return k
    def preview(self,row,profiles,assignment,packet):
        trial=copy.deepcopy(self);mapping,trace=trial.step(row,profiles,assignment,packet)
        return dict(version=self.version,trial=trial,mapping=mapping,trace=trace)
    def commit(self,view):
        assert self.version==view['version'],'stale or double commit'
        self.__dict__=view['trial'].__dict__;self.version+=1
        self.previous=view['mapping'].copy()
        return view['mapping'],view['trace']
    def state(self):
        # RLE bytes stay in runtime only; bind them without publishing raster data.
        banks={}
        for k,b in self.bank.items():
            banks[str(k)]={x:v for x,v in b.items() if x!='rle'}
            banks[str(k)]['rle_sha256']=digest(b['rle']) if b.get('rle') else None
        return dict(bank=banks,sources=self.sources,groups=self.groups,group_mask_bindings={k:digest(v) for k,v in self.group_masks.items()},
            used=self.used,next_pid=self.next_pid,version=self.version,previous=self.previous)
    def step(self,row,profiles,assignment,packet):
        f,now=row['frame'],row['time'];obs={o['id']:o for o in row['observations']};before=digest(self.state())
        measures={n:extract(packet['objects'][str(n)]) for n in obs};mapping={};actions=[];risk=set();group_log=[];trusted=set()
        for n,o in obs.items():
            source=self.sources.get(n)
            if source is None or source['last_frame']!=f-1:
                generation=0 if source is None else source['generation']+1
                self.sources[n]=dict(pid=source['pid'] if source else None,generation=generation,last_frame=f,
                    established=False,streak=0,risk=False,last_clean=None,birth_time=now,birth_frame=f)
            else:source['last_frame']=f
            if o['neighbors']:risk.add(n)
        for hit in self.suspects.get(f,[]):
            pids=[self.sources[n]['pid'] for n in hit['sources'] if n in self.sources and self.sources[n]['pid'] in self.bank]
            if len(set(pids))!=2 or any(set(pids)&set(g['pids']) for g in self.groups):continue
            g=dict(id='PID-F'+str(f)+'-'+str(hit['group']),start=f,time=now,sources=hit['sources'],pids=pids,
                group=hit['group'],donor=hit.get('donor',next((n for n in hit['sources'] if n!=hit['group']),hit['sources'][-1])),
                confirm_frame=None,q=None,status='SUSPECT',anchors={str(k):copy.deepcopy(self.bank[k]['anchor']) for k in pids})
            self.groups.append(g);self.events.append(g)
            if hit['group'] in obs:self.group_masks[g['id']]=assignment['masks'][obs[hit['group']]['mask']]
        split=set();finished=[]
        for g in self.groups:
            risk.update(g['sources']);risk.add(g['group']);minimum=CFG['split_min_area_fraction']*min(self.bank[k]['last']['area'] for k in g['pids'])
            group_mask=decode(self.group_masks[g['id']]) if g['id'] in self.group_masks else None
            candidates=[]
            for n,o in obs.items():
                if o['neighbors'] or o['area']<minimum or not any(self.feasible(k,o,now)[0] for k in g['pids']):continue
                current=decode(assignment['masks'][o['mask']])
                support=int((current&group_mask).sum())/max(1,min(int(current.sum()),int(group_mask.sum()))) if group_mask is not None else 0.
                if support>=.15:candidates.append(n)
            donor=g['donor'];oldarea=self.bank[g['pids'][g['sources'].index(donor)]]['last']['area']
            cancel=f==g['start']+1 and donor in obs and obs[donor]['area']>=.5*oldarea
            if cancel:
                g['status']='CANCELED_DONOR_NOT_COLLAPSED';finished.append(g)
                risk.difference_update(n for n in g['sources']+[g['group']] if n in obs and not obs[n]['neighbors'])
            elif f>g['start'] and len(candidates)>=2:
                g['q']=f;g['status']='FIRST_SPLIT_ASSOCIATION';split.update(candidates);risk.difference_update(candidates);finished.append(g)
            elif now-g['time']>CFG['event_max_seconds']:
                g['status']='TIMEOUT_LOCAL_RELEASE';finished.append(g)
            elif f==g['start']+CFG['merge_confirmations']-1:g['confirm_frame']=f;g['status']='GROUP'
            group_log.append(dict(event=g['id'],status=g['status'],current_native=list(obs),anonymous_sources=[n for n in obs if n in g['sources'] or n==g['group']],
                member_pids=g['pids'],individual_history_updated=False,q=g['q']))
            if g not in finished and g['group'] in obs:
                n=g['group'];s=self.sources[n]
                if s['pid'] is None:s['pid']=self.allocate(n)
                mapping[n]=s['pid']
                self.group_masks[g['id']]=assignment['masks'][obs[n]['mask']]
        protected={k for g in self.groups if g not in finished for k in g['pids']}
        protected_pins={k:digest(self.bank[k]) for k in protected}
        risk.update(n for n in obs if self.sources[n]['pid'] in protected)
        reserved=set(mapping.values());unlocked=[]
        for n,o in obs.items():
            s=self.sources[n];k=s['pid'];clean=self.clean(o,k)
            locked=s['established'] and not s['risk'] and n not in risk and n not in split and clean and k not in reserved
            if n in mapping:continue
            if locked:mapping[n]=k;reserved.add(k);trusted.add(n)
            elif n in risk:
                # Preserve existing publication during overlap; freeze all clean references.
                if k is None or k in reserved:k=self.allocate(n);s['pid']=k
                mapping[n]=k;reserved.add(k)
            else:unlocked.append(n)
        candidates=sorted(k for k,b in self.bank.items() if b['established'] and k not in reserved and k not in protected and b['motion'] and 0<=now-b['motion'][-1]['time']<=CFG['identity_search_seconds'])
        blocked=[dict(event=g['id'],pid=k,current_native=[n for n,v in mapping.items() if v==k],reason='CURRENT_MASK_STILL_OCCUPIES_MEMBER_PID')
            for g in finished if g['q']==f for k in g['pids'] if k in reserved]
        geometry=np.full((len(unlocked),len(candidates)),1e6);edges=np.zeros_like(geometry,dtype=bool);edge_details={}
        for i,n in enumerate(unlocked):
            for j,k in enumerate(candidates):
                possible,detail=self.feasible(k,obs[n],now);edge_details[(i,j)]=detail
                if possible and self.clean(obs[n],k):
                    encoded=assignment['masks'][obs[n]['mask']];last=self.bank[k]
                    predmask=decode(last['rle']);yy,xx=np.where(predmask);dx,dy=np.rint(detail['shift_px']).astype(int)
                    xx,yy=xx+dx,yy+dy;valid=(xx>=0)&(xx<predmask.shape[1])&(yy>=0)&(yy<predmask.shape[0]);xx,yy=xx[valid],yy[valid]
                    current=decode(encoded);intersection=int(current[yy,xx].sum());union=int(len(xx)+current.sum()-intersection)
                    iou=intersection/max(1,union);cost=CFG['mask_cost_weight']*(1-iou)+(1-CFG['mask_cost_weight'])*min(1,detail['distance_px']/detail['radius_px'])
                    geometry[i,j]=cost;edges[i,j]=cost<CFG['dummy_cost'];detail.update(mask_iou=iou,geometry_cost=cost)
        values=geometry.copy();depth_rows=[]
        for i,n in enumerate(unlocked):
            js=np.flatnonzero(edges[i]);pids=[candidates[j] for j in js];sorted_g=sorted([geometry[i,j] for j in js]+[CFG['dummy_cost']])
            ambiguous=len(sorted_g)>=2 and sorted_g[1]-sorted_g[0]<=CFG['depth_ambiguity_margin']
            detail=dict(source=n,active=False,reason='GEOMETRY_CLEAR_OR_NO_EDGE',candidate_pids=pids)
            if self.arm=='PID_DEPTH' and ambiguous and pids:
                delta,detail=costs({k:self.bank[k]['depth'] for k in pids},measures[n],now,packet.get('full_frame',{}))
                detail.update(source=n,candidate_pids=pids,active=detail.get('used',False))
                for j in js:values[i,j]+=CFG['depth_weight']*delta[candidates[j]]
            depth_rows.append(detail)
        selected,global_detail=match(values,edges);geo_selected,_=match(geometry,edges)
        for i,j,margin in selected:
            n,k=unlocked[i],candidates[j];s=self.sources[n];old=s['pid'];reference=copy.deepcopy(self.bank[k]['anchor'])
            assert k not in mapping.values();mapping[n]=k;s['pid']=k;s['established']=True;s['streak']=0
            trusted.add(n)
            # Detach absent handles; a later reappearance has no original-number priority.
            for other,handle in self.sources.items():
                if other!=n and handle['pid']==k and other not in obs:handle['pid']=None;handle['established']=False
            actions.append(dict(source=n,target=k,previous_pid=old,reference=reference,margin=margin,geometry=edge_details[i,j],
                depth_row=depth_rows[i],geometry_selected_target=next((candidates[b] for a,b,_ in geo_selected if a==i),None),
                source_generation=s['generation'],first_publication_frame=f,physical_identity='UNKNOWN_UNTIL_POSTSEAL'))
        for n in unlocked:
            if n in mapping:continue
            s=self.sources[n];k=s['pid']
            if k is None or k in mapping.values():k=self.allocate(n);s['pid']=k;s['streak']=0;s['established']=False
            mapping[n]=k
        assert set(mapping)==set(obs) and len(set(mapping.values()))==len(obs)
        for n,o in obs.items():
            s=self.sources[n];k=mapping[n];clean=n not in risk and self.clean(o,k);s['risk']=n in risk
            oldbank=self.bank.get(k)
            if n in unlocked and n not in trusted and oldbank and oldbank['established']:
                # An unaccepted post mapping is publication continuity, not a new clean reference.
                s['risk']=True;clean=False
            if not clean:s['streak']=0;continue
            version=[n,s['generation'],k];b=self.bank.get(k)
            if b is None:b=dict(established=False,motion=[],depth=[],last={},anchor=None,rle=None,version=None);self.bank[k]=b
            s['streak']+=1
            if s['streak']>=CFG['new_identity_clean_confirmations'] and (s['birth_frame']==1 or now-s['birth_time']>=CFG['new_identity_retry_seconds']):s['established']=True
            b['established']=b['established'] or s['established']
            continuous=b['version']==version and b['motion'] and b['motion'][-1]['frame']==f-1
            if not continuous:b['motion']=[];b['depth_live']=[]
            point=dict(frame=f,time=now,center=center(o).tolist(),version=version)
            b['motion']=(b['motion']+[point])[-CFG['history_frames']:]
            if measures[n]['usable']:
                if not continuous or not b.get('depth_live') or b['depth_live'][-1]['frame']!=f-1:b['depth_live']=[]
                dp=dict(frame=f,time=now,z_mm=measures[n]['z_mm'],mad_mm=measures[n]['mad_mm'],fact_id=measures[n]['fact_id'],version=version)
                b['depth_live']=(b['depth_live']+[dp])[-CFG['history_frames']:];b['depth']=copy.deepcopy(b['depth_live'])
            else:b['depth_live']=[]
            b.update(version=version,last=copy.deepcopy(o),anchor=dict(frame=f,native_id=n,source_generation=s['generation'],pid=k),rle=assignment['masks'][o['mask']])
            s['last_clean']=f
        self.groups=[g for g in self.groups if g not in finished]
        for g in finished:self.group_masks.pop(g['id'],None)
        assert all(digest(self.bank[k])==h for k,h in protected_pins.items()),'Protected member bank changed before joint split'
        return mapping,dict(frame=f,state_before_sha256=before,risk_sources=sorted(risk),unlocked_sources=unlocked,candidate_pids=candidates,
            geometry_cost=geometry.tolist(),cost=values.tolist(),feasible=edges.tolist(),depth_rows=depth_rows,global_assignment=global_detail,
            actions=actions,group_records=group_log,occupied_member_targets=blocked,first_split_events=[g['id'] for g in finished if g['q']==f],future_frames_used=0,
            protected_pids=sorted(protected),protected_reference_pins={str(k):h for k,h in protected_pins.items()},
            protected_reference_unchanged=True,measurements=measures,all_masks_retained=True,decided_before_first_publish=True)
    def clean(self,o,k):
        base=o['area']>=CFG['clean_min_area'] and (o.get('score_birth') is None or o['score_birth']>=CFG['clean_min_score']) and not o['neighbors']
        if k in self.bank:
            ratio=o['area']/max(1,self.bank[k]['last']['area']);base=base and CFG['clean_area_ratio'][0]<=ratio<=CFG['clean_area_ratio'][1]
        return base
    def feasible(self,k,o,now):
        b=self.bank[k];pc,detail=prediction(b,now);distance=float(np.linalg.norm(pc-center(o)))
        radius=max(CFG['search_base_radius_px'],.5*(diag(b['last'])+diag(o)))+CFG['search_growth_px_s']*min(max(0.,detail['gap_seconds']),CFG['search_growth_cap_seconds'])
        detail.update(predicted_center_px=pc.tolist(),observed_center_px=center(o).tolist(),distance_px=distance,radius_px=radius,reference=copy.deepcopy(b['anchor']))
        return distance<=radius and detail['gap_seconds']<=CFG['identity_search_seconds'],detail
