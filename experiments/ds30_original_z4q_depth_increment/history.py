"""Per-branch exact bank anchors; causal original source records, never identity depth writes."""
from common import *
from collections import OrderedDict, Counter
import copy, math
import numpy as np, cv2
raw_source = module('ds30_causal_raw_source', ROOT/'experiments/ds16_relative_depth_order/source.py')
RawDepth, native_masks = raw_source.RawDepth, raw_source.native_masks
from mixed_depth import array_binding
from measurement import Measurement
CFG=read(HERE/'CONFIG.json')

def anchor_key(anchor):
    return tuple(anchor[k] for k in ('frame','native_id','canonical_id','mask')) if anchor else None

class History:
    def __init__(self,name):
        self.name=name;self.previous={};self.live={};self.frames=OrderedDict();self.anchors={}
    def current_version(self,n,frame,mapping,epochs):
        prior=self.previous.get(n)
        generation=(prior['generation'] if prior and prior['frame']==frame-1 else (prior['generation']+1 if prior else 1))
        return [n,generation,mapping.get(n,n),epochs.get(n,0)]
    def observe(self,row,mapping,epochs,engine,anonymous=()):
        frame,now=row['frame'],row['time'];objects={};fragments={}
        for o in row['observations']:
            n=o['id'];k=mapping[n];version=self.current_version(n,frame,mapping,epochs)
            anchor=engine.bank.get(k,{}).get('anchor')
            clean=bool(n not in anonymous and k>=0 and anchor==dict(frame=frame,native_id=n,canonical_id=k,mask=o['mask'])
                and engine.quality(o) and not o.get('neighbors') and n not in engine.retired)
            previous=self.live.get(n)
            continuous=bool(clean and previous and previous[-1]['frame']==frame-1 and previous[-1]['version']==version)
            item=dict(frame=frame,time=now,native=n,public=k,version=version,
                box=o['box'],area=o['area'],neighbors=list(o.get('neighbors',[])),
                acquired_mask_depth=copy.deepcopy(o.get('depth')),measurement_origin='ORIGINAL_SAVED_OBSERVATION; MASK_MAY_BE_MIXED',
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

