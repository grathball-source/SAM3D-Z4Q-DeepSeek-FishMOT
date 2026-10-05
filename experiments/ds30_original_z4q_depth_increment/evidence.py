"""Conditional relative order with common null; no peak/identity certification."""
from common import *
from history import History, anchor_key
from collections import OrderedDict, Counter
raw_source = module('ds30_causal_raw_source', ROOT/'experiments/ds16_relative_depth_order/source.py')
RawDepth, native_masks = raw_source.RawDepth, raw_source.native_masks
from measurement import Measurement
from mixed_depth import array_binding
import copy, math
import numpy as np, cv2
CFG=read(HERE/'CONFIG.json')

def t4_cdf(x):
    u=x/math.hypot(x,2.)
    return max(0.,min(1.,.5+.75*u-.25*u**3))

class Sources:
    """One causal raw cursor/cache shared across policies; no branch identity state."""
    def __init__(self,name,handle):
        self.name=name;self.handle=handle;self.frames=OrderedDict();self.raw=RawDepth(name)
        self.arrays=OrderedDict();self.mask_cache=OrderedDict();self.cache=OrderedDict()
        self.reads=[];self.written=set();self.counts=Counter();self.cutoff=0
        self.producers={arm:Measurement(policy) for arm,policy in VARIANTS.items()}
    def add(self,row,assignment,binding):
        assert (assignment['frame'],assignment['global_frame_id'],assignment['time'])==(row['frame'],row['global_frame'],row['time'])
        self.cutoff=row['frame'];self.now=row['time'];self.frames[row['frame']]=(row,assignment,binding)
        while self.frames and self.now-next(iter(self.frames.values()))[0]['time']>CFG['max_history_seconds']:
            self.frames.popitem(last=False)
    def masks(self,frame):
        assert frame<=self.cutoff and frame in self.frames,'Future/expired frame'
        if frame not in self.mask_cache:
            self.mask_cache[frame]=native_masks(self.frames[frame][1])
            while len(self.mask_cache)>3:self.mask_cache.popitem(last=False)
        return self.mask_cache[frame]
    def arrays_at(self,frame):
        assert frame<=self.cutoff and frame in self.frames,'Future/expired frame'
        if frame not in self.arrays:
            row,_,expected=self.frames[frame];cursor=copy.copy(self.raw);cursor.previous_frame=None
            arrays=cursor(row['global_frame'],row['time']);assert arrays[3]==expected
            self.arrays[frame]=arrays
            self.reads.append(dict(frame=frame,global_frame=row['global_frame'],query_cutoff_frame=self.cutoff,
                source_binding_sha256=digest(arrays[3])))
            while len(self.arrays)>3:self.arrays.popitem(last=False)
        return self.arrays[frame]
    def packet(self,arm,frame,n):
        assert frame<=self.cutoff and frame in self.frames
        key=(arm,frame,n)
        if key not in self.cache:
            row,_,expected=self.frames[frame];depth,index,sensor,binding=self.arrays_at(frame)
            masks=self.masks(frame);assert n in masks
            fact,maps=self.producers[arm].measure_region(depth,index,sensor,masks,masks[n],self.name,frame,
                row['global_frame'],row['time'],source_binding=binding,expected_source_binding=expected)
            pin=digest(fact);identifier=(arm,fact['fact_id'],pin)
            if identifier not in self.written:
                self.handle.write(json.dumps(dict(arm=arm,measurement=fact),separators=(',',':'),allow_nan=False)+'\n')
                self.written.add(identifier);self.counts[arm+'/'+fact['reason']]+=1
            # Source indices are frame-local; only measured support positions retained.
            ids=fact['qualified_support_ids']
            self.cache[key]=dict(fact=fact,maps=dict(selected_positions=maps['selected_positions'],mask_selected=maps['mask_selected']),source_index=index,native=n)
            while len(self.cache)>64:self.cache.popitem(last=False)
        return self.cache[key]
    def unique_pair(self,arm,frame,a,b):
        first,second=self.packet(arm,frame,a),self.packet(arm,frame,b)
        ia=first['source_index'][first['maps']['mask_selected']]
        ib=second['source_index'][second['maps']['mask_selected']]
        shared=np.intersect1d(ia,ib)
        if not shared.size:return first,second,dict(shared_unique_sources=0,remeasured=False)
        depth,index,sensor,binding=self.arrays_at(frame);masks=self.masks(frame);row,_,expected=self.frames[frame]
        result=[]
        for n,base in ((a,first),(b,second)):
            fact,maps=self.producers[arm].measure_region(depth,index,sensor,masks,masks[n],self.name,frame,
                row['global_frame'],row['time'],source_binding=binding,expected_source_binding=expected,excluded_native_sources=shared)
            fact.pop('measurement_sha256')
            fact['remeasured_from']=dict(fact_id=base['fact']['fact_id'],measurement_sha256=digest(base['fact']))
            fact['measurement_sha256']=digest(fact)
            pin=digest(fact);identifier=(arm,fact['fact_id'],pin)
            if identifier not in self.written:
                self.handle.write(json.dumps(dict(arm=arm,measurement=fact),separators=(',',':'),allow_nan=False)+'\n')
                self.written.add(identifier);self.counts[arm+'/'+fact['reason']]+=1
            result.append(dict(fact=fact,maps=dict(selected_positions=maps['selected_positions']),source_index=index,native=n))
        return *result,dict(shared_unique_sources=int(shared.size),shared_source_binding=array_binding(shared),
            remeasured=True,original_facts_retained=True,original_ROI_denominators_unchanged=True)
    def separate(self,frame,a,b):
        masks=self.masks(frame)
        return not np.any(cv2.dilate(masks[a].astype('u1'),np.ones((7,7),'u1'))&masks[b])
    def close(self):self.raw.close()

