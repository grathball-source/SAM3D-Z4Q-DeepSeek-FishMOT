"""Conditional relative order with common null; no peak/identity certification."""
from common import *
from history import History, anchor_key
from collections import OrderedDict, Counter
raw_source = module('ds29_causal_raw_source', ROOT/'experiments/ds16_relative_depth_order/source.py')
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
            self.cache[key]=dict(fact=fact,maps=dict(selected_positions={s:maps['selected_positions'][s] for s in ids}),source_index=index)
            while len(self.cache)>64:self.cache.popitem(last=False)
        return self.cache[key]
    def separate(self,frame,a,b):
        masks=self.masks(frame)
        return not np.any(cv2.dilate(masks[a].astype('u1'),np.ones((7,7),'u1'))&masks[b])
    def close(self):self.raw.close()

