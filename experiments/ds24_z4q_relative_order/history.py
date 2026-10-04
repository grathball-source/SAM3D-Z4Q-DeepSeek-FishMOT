"""Branch-owned provenance and read-only causal source lookup, separate from Z4Q bank."""
from common import *
from collections import OrderedDict, Counter
import copy, math
import numpy as np, cv2
from source import RawDepth, native_masks
from evidence import CFG, representative, pair_order, combine
measurement = module('ds24_unchanged_ds22', ROOT/'experiments/ds22_local_background_depth/measurement.py')

def anchor_key(anchor):
    return tuple(anchor[k] for k in ('frame','native_id','canonical_id','mask')) if anchor else None

class Sources:
    def __init__(self, name, handle):
        self.name=name; self.handle=handle; self.frames=OrderedDict(); self.facts={}; self.arrays=OrderedDict()
        self.raw=RawDepth(name); self.reads=[]; self.counts=Counter()
    def add(self,row,assignment,raw_binding):
        assert assignment['frame']==row['frame'] and assignment['global_frame_id']==row['global_frame'] and assignment['time']==row['time']
        self.cutoff=row['frame'];self.now=row['time']
        self.frames[row['frame']]=(row,assignment,raw_binding)
        while self.frames and self.now-next(iter(self.frames.values()))[0]['time']>CFG['max_history_seconds']:
            f,_=self.frames.popitem(last=False)
            for key in [k for k in self.facts if k[0]==f]: self.facts.pop(key)
    def measure(self,frame,native):
        assert frame<=self.cutoff and frame in self.frames,'Future or unavailable historical frame'
        key=(frame,native)
        if key in self.facts:return self.facts[key]
        row,assignment,expected=self.frames[frame]
        if frame not in self.arrays:
            # A fresh cursor allows a previously acquired past frame; the adapter math/fields are unchanged.
            cursor=copy.copy(self.raw);cursor.previous_frame=None
            arrays=cursor(row['global_frame'],row['time'])
            assert arrays[3]==expected,'Actual raw packet differs from immutable saved input'
            self.arrays[frame]=(*arrays,native_masks(assignment))
            while len(self.arrays)>3:self.arrays.popitem(last=False)
            self.reads.append(dict(frame=frame,global_frame=row['global_frame'],query_cutoff_frame=self.cutoff,
                sensor_pair_delta_us=arrays[3].get('delta_us'),source_binding_sha256=digest(arrays[3])))
        depth,index,sensor,binding,masks=self.arrays[frame]
        fact,_=measurement.measure_local_background(depth,index,sensor,masks,native,self.name,frame,
            row['global_frame'],row['time'],source_binding=binding,expected_source_binding=expected)
        self.handle.write(json.dumps(fact,separators=(',',':'),allow_nan=False)+'\n')
        value=representative(fact);self.facts[key]=value;self.counts[value['reason']]+=1
        return value
    def separate(self,frame,a,b):
        row,assignment,_=self.frames[frame];masks=native_masks(assignment)
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
            pairs=[dict(frame=f,time=a[f]['time'],A=self.sources.measure(f,record['native']),B=self.sources.measure(f,m)) for f in shared]
            post=dict(A=self.sources.measure(frame,n),B=self.sources.measure(frame,m))
            order=pair_order(pairs,post,now)
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
