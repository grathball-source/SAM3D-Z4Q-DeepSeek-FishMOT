"""Branch-owned provenance and read-only causal source lookup, separate from Z4Q bank."""
from common import *
from collections import OrderedDict, Counter
import copy, math
import numpy as np, cv2
from source import RawDepth, native_masks
from association import CFG, evaluate
import measurement
from mixed_depth import array_binding

def combine(comparisons):
    reliable=[x for x in comparisons if x['status'] in ('CONFLICT','COMPATIBLE')]
    veto=bool(reliable and all(x['status']=='CONFLICT' for x in reliable))
    return dict(status='EXCLUDED' if veto else 'KEEP_ORIGINAL',veto=veto,
        reason='ALL_COMPARABLE_SPATIAL_PATHS_CONTRADICT' if veto else
               'COMPATIBLE_PARTNER_RETAINS_ORIGINAL' if any(x['status']=='COMPATIBLE' for x in reliable) else 'NO_RELIABLE_LOCAL_SPATIAL_CHAIN',
        comparisons=comparisons,unknown_partner_count=sum(x['status']=='UNKNOWN' for x in comparisons))

def anchor_key(anchor):
    return tuple(anchor[k] for k in ('frame','native_id','canonical_id','mask')) if anchor else None

class Sources:
    def __init__(self, name, handle):
        self.name=name; self.handle=handle; self.frames=OrderedDict(); self.arrays=OrderedDict()
        self.raw=RawDepth(name); self.reads=[]; self.counts=Counter(); self.written=set()
        self.mask_cache=OrderedDict(); self.packet_cache=OrderedDict(); self.seed_cache={}
        self.private_cache_bytes=0;self.max_private_cache_bytes=0
    def add(self,row,assignment,raw_binding):
        assert assignment['frame']==row['frame'] and assignment['global_frame_id']==row['global_frame'] and assignment['time']==row['time']
        self.cutoff=row['frame'];self.now=row['time']
        self.frames[row['frame']]=(row,assignment,raw_binding)
        while self.frames and self.now-next(iter(self.frames.values()))[0]['time']>CFG['max_history_seconds']:
            f,_=self.frames.popitem(last=False)
            for key in [k for k in self.seed_cache if k[0]==f]:self.seed_cache.pop(key)
            for key in [k for k in self.packet_cache if k[0]==f]:
                removed=self.packet_cache.pop(key);self.private_cache_bytes-=removed['private_cache_bytes']
    def masks(self,frame):
        assert frame<=self.cutoff and frame in self.frames,'Future or expired acquired mask'
        if frame not in self.mask_cache:
            self.mask_cache[frame]=native_masks(self.frames[frame][1])
            while len(self.mask_cache)>3:self.mask_cache.popitem(last=False)
        return self.mask_cache[frame]
    def arrays_at(self,frame):
        assert frame<=self.cutoff and frame in self.frames,'Future or unavailable historical frame'
        row,assignment,expected=self.frames[frame]
        if frame not in self.arrays:
            # A fresh cursor allows a previously acquired past frame; the adapter math/fields are unchanged.
            cursor=copy.copy(self.raw);cursor.previous_frame=None
            arrays=cursor(row['global_frame'],row['time'])
            assert arrays[3]==expected,'Actual raw packet differs from immutable saved input'
            self.arrays[frame]=arrays
            while len(self.arrays)>3:self.arrays.popitem(last=False)
            self.reads.append(dict(frame=frame,global_frame=row['global_frame'],query_cutoff_frame=self.cutoff,
                sensor_pair_delta_us=arrays[3].get('delta_us'),source_binding_sha256=digest(arrays[3])))
        return self.arrays[frame]
    def packet(self,frame,roi,roles=None,seed=False):
        assert frame<=self.cutoff and frame in self.frames,'Future or expired measurement'
        key=(frame,array_binding(roi)['sha256'])
        if key not in self.packet_cache:
            row,_,expected=self.frames[frame];depth,index,sensor,binding=self.arrays_at(frame)
            fact,maps=measurement.measure_region(depth,index,sensor,self.masks(frame),roi,self.name,frame,
                row['global_frame'],row['time'],source_binding=binding,expected_source_binding=expected)
            if fact['fact_id'] not in self.written:
                self.handle.write(json.dumps(fact,separators=(',',':'),allow_nan=False)+'\n')
                self.written.add(fact['fact_id']);self.counts[fact['reason']]+=1
            # All layer facts remain public; only geometry needed by the chain stays in RAM.
            observed=np.zeros(roi.shape,bool)
            for support in maps['support_masks'].values():observed|=support
            ids=fact['qualified_support_ids']
            compact=dict(roi=maps['roi'],all_support_union=observed,
                support_masks={i:maps['support_masks'][i] for i in ids},
                selected_positions={i:maps['selected_positions'][i] for i in ids})
            size=compact['roi'].nbytes+observed.nbytes+sum(x.nbytes for d in ('support_masks','selected_positions') for x in compact[d].values())
            self.packet_cache[key]=dict(fact=fact,maps=compact,private_cache_bytes=size)
            self.private_cache_bytes+=size
            while self.private_cache_bytes>384*1024**2 and len(self.packet_cache)>1:
                _,removed=self.packet_cache.popitem(last=False);self.private_cache_bytes-=removed['private_cache_bytes']
            self.max_private_cache_bytes=max(self.max_private_cache_bytes,self.private_cache_bytes)
        value=dict(self.packet_cache[key],contact_seed=seed)
        if roles is not None:value['roles']=roles
        return value
    def find_seed(self,anchor_frame,a,b,query_frame):
        key=(anchor_frame,a,b);state=self.seed_cache.setdefault(key,dict(last=anchor_frame,found=None))
        if state['found'] is not None:return state['found']
        for f in range(state['last']+1,query_frame):
            if f not in self.frames:continue
            masks=self.masks(f)
            if a in masks and b in masks:
                seed=measurement.contact_seed(masks,a,b)
                if seed.any():
                    state['found']=(f,seed);break
            state['last']=f
        return state['found']
    def sequence(self,shared,a,b,n):
        query=self.cutoff;anchor=shared[-1];found=self.find_seed(anchor,a,b,query)
        if found is None:
            return dict(status='UNKNOWN',veto=False,reason='NO_ACTUAL_GEOMETRY_CONTACT_SEED',
                evaluated_pre_frames=shared,anonymous_interval_frames=list(range(anchor+1,query)),
                source_query_cutoff=query,mapping_is_hypothesis=True)
        if any(f not in self.frames for f in [*shared,*range(anchor+1,query+1)]):
            return dict(status='UNKNOWN',veto=False,reason='ACQUIRED_LOCAL_CHAIN_FRAME_EXPIRED',source_query_cutoff=query)
        seed_frame,seed=found;kernel=np.ones((2*CFG['local_expansion_px']+1,)*2,'u1')
        window=cv2.dilate(seed.astype('u1'),kernel).astype(bool);initial_window=window.copy();pre=[];contacts=[]
        sy,sx=np.nonzero(seed);seed_center=np.array([sx.mean(),sy.mean()])
        for f in shared:
            masks=self.masks(f);roi=window&(masks[a]|masks[b])
            pre.append(self.packet(f,roi,dict(A=masks[a],B=masks[b])))
        previous=pre[-1]
        def next_window(packet,last_window):
            if packet['fact']['status']!='AVAILABLE_TWO_LAYERS':return last_window
            centers=[]
            for sid in packet['fact']['qualified_support_ids']:
                yy,xx=np.divmod(packet['maps']['selected_positions'][sid],window.shape[1])
                centers.append([xx.mean(),yy.mean()])
            dx,dy=np.mean(centers,axis=0)-seed_center
            moved=cv2.warpAffine(initial_window.astype('u1'),np.array([[1.,0.,dx],[0.,1.,dy]]),
                (window.shape[1],window.shape[0]),flags=cv2.INTER_NEAREST,borderMode=cv2.BORDER_CONSTANT,borderValue=0).astype(bool)
            assert moved.sum()<=initial_window.sum(),'Local patch expanded beyond frozen seed footprint'
            return moved
        for f in range(anchor+1,query):
            masks=self.masks(f);union=np.zeros(window.shape,bool)
            for mask in masks.values():union|=mask
            window=next_window(previous,window);roi=window&union
            previous=self.packet(f,roi,seed=f==seed_frame);contacts.append(previous)
        masks=self.masks(query);window=next_window(previous,window);roi=window&(masks[n]|masks[b])
        post=self.packet(query,roi,dict(A=masks[n],B=masks[b]))
        result=evaluate(pre,contacts,post)
        return dict(result,source_query_cutoff=query,actual_contact_seed_frame=seed_frame,
            actual_contact_seed_binding=array_binding(seed),seed_original_mask_bindings={str(i):array_binding(self.masks(seed_frame)[i]) for i in (a,b)},
            initial_bounded_local_window_binding=array_binding(initial_window),initial_window_area=int(initial_window.sum()),
            retrospective_within_q=True,identity_reference_changed=False)
    def separate(self,frame,a,b):
        masks=self.masks(frame)
        return not np.any(cv2.dilate(masks[a].astype('u1'),np.ones((7,7),'u1'))&masks[b])
    def close(self): self.raw.close()

class History:
    def __init__(self,name):
        self.name=name;self.previous={};self.live={};self.frames=OrderedDict();self.anchors={}
    def current_version(self,n,frame,mapping,epochs):
        prior=self.previous.get(n)
        generation=(prior['generation'] if prior and prior['frame']==frame-1 else (prior['generation']+1 if prior else 1))
        return [n,generation,mapping.get(n,n),epochs.get(n,0)]
    def observe(self,row,mapping,epochs,engine):
        frame,now=row['frame'],row['time'];objects={};fragments={}
        for o in row['observations']:
            n=o['id'];k=mapping[n];version=self.current_version(n,frame,mapping,epochs)
            anchor=engine.bank.get(k,{}).get('anchor')
            clean=bool(k>=0 and anchor==dict(frame=frame,native_id=n,canonical_id=k,mask=o['mask'])
                and engine.quality(o) and not o.get('neighbors') and n not in engine.retired)
            previous=self.live.get(n)
            continuous=bool(clean and previous and previous[-1]['frame']==frame-1 and previous[-1]['version']==version)
            item=dict(frame=frame,time=now,native=n,public=k,version=version,
                box=o['box'],area=o['area'],neighbors=list(o.get('neighbors',[])),
                observation_class='CLEAN_ACTUAL_BANK_ANCHOR' if clean else 'ANONYMOUS_RISK_OBSERVATION')
            objects[n]=item
            if clean:
                self.live[n]=((previous if continuous else [])+[item])[-CFG['history_frames']:]
                fragments[n]=tuple(self.live[n][-CFG['fit_observations']:])
                self.anchors[anchor_key(anchor)]=dict(time=now,version=version,frame=frame,native=n,public=k)
            else:self.live.pop(n,None)
            self.previous[n]=dict(frame=frame,generation=version[1])
        for n in list(self.live):
            if n not in objects:self.live.pop(n,None)
        self.frames[frame]=dict(time=now,objects=objects,fragments=fragments)
        while self.frames and now-next(iter(self.frames.values()))['time']>CFG['max_history_seconds']:self.frames.popitem(last=False)
        for key,record in list(self.anchors.items()):
            if now-record['time']>CFG['max_history_seconds']:self.anchors.pop(key)
        return objects

class Context:
    """Shared read-only facts; preview never commits provenance, bank or measurements as identity."""
    def __init__(self,row,history,sources,mapping,epochs):
        self.row=row;self.history=history;self.sources=sources;self.mapping=mapping;self.epochs=epochs
    def __deepcopy__(self,memo): return self
    def check(self,engine,observation,public,anchor,origin_rule):
        frame=self.row['frame'];now=self.row['time'];n=observation['id']
        result=dict(origin_rule=origin_rule,native_id=n,public_id=public,anchor=copy.deepcopy(anchor),
            query_frame=frame,status='KEEP_ORIGINAL',veto=False,comparisons=[],
            hypothesis_not_observation=True,new_cost=None)
        key=anchor_key(anchor);record=self.history.anchors.get(key)
        if not record or record['frame'] not in self.history.frames:
            return dict(result,reason='EXACT_BANK_ANCHOR_PROVENANCE_UNKNOWN')
        assert anchor_key(engine.bank[public].get('anchor'))==key
        snapshot=self.history.frames[record['frame']]
        fragment=snapshot['fragments'].get(record['native'],())
        if not fragment or fragment[-1]['version']!=record['version']:
            return dict(result,reason='TARGET_ANCHOR_FRAGMENT_VERSION_MISMATCH')
        if not engine.quality(observation) or observation.get('neighbors'):
            return dict(result,reason='CURRENT_TARGET_QUALITY_OR_CONTACT_RISK')
        current={engine.alias.get(o['id'],{}).get('target',o['id']):o for o in self.row['observations']}
        h=engine.bank[public]
        partners=sorted(p for p,ts in engine.partners(h,public).items()
            if p!=public and p in current and current[p]['id']!=n and 0<=h['last_seen']-ts<=1 and 0<=now-ts<=6)
        comparisons=[]
        for p in partners:
            o=current[p];m=o['id'];pre=snapshot['objects'].get(m)
            unknown=dict(status='UNKNOWN',veto=False,partner_public=p,partner_native=m)
            v=self.history.current_version(m,frame,self.mapping,self.epochs)
            if not pre or pre['public']!=p or pre['version']!=v or self.mapping.get(m)!=p:
                comparisons.append(dict(unknown,reason='PARTNER_CLAIM_GENERATION_OR_EPOCH_CHANGED'));continue
            if not engine.quality(o) or o.get('neighbors') or not self.sources.separate(frame,n,m):
                comparisons.append(dict(unknown,reason='CURRENT_PARTNER_OR_PAIR_GEOMETRY_RISK'));continue
            a={x['frame']:x for x in fragment};b={x['frame']:x for x in snapshot['fragments'].get(m,())}
            shared=sorted(set(a)&set(b))[-CFG['fit_observations']:]
            if len(shared)<CFG['minimum_pre_pairs'] or shared[-1]!=anchor['frame']:
                comparisons.append(dict(unknown,reason='NO_SUFFICIENT_SYNCHRONOUS_ANCHOR_PAIR'));continue
            if any(b[f]['version']!=pre['version'] or a[f]['version']!=record['version'] for f in shared):
                comparisons.append(dict(unknown,reason='PRE_PAIR_VERSION_CHANGE'));continue
            order=self.sources.sequence(shared,record['native'],m,n)
            anonymous=[dict(frame=f,objects={str(k):v for k,v in r['objects'].items()
                if v['observation_class']=='ANONYMOUS_RISK_OBSERVATION' and k in (record['native'],m,n)})
                for f,r in self.history.frames.items() if anchor['frame']<f<frame and any(
                    v['observation_class']=='ANONYMOUS_RISK_OBSERVATION' for k,v in r['objects'].items() if k in (record['native'],m,n))]
            comparisons.append(dict(order,partner_public=p,partner_native=m,
                complete_mapping_hypothesis={str(n):public,str(m):p},
                pre_versions={'A':record['version'],'B':pre['version']},current_partner_claim_version=v,
                anonymous_risk_interval=anonymous,identity_continuity_assumption='CONDITIONAL_ORIGINAL_PARTNER_CLAIM; NOT_GT_CONFIRMED'))
        return dict(result,**combine(comparisons),target_anchor_version=record['version'],
                    partner_candidates=partners)
