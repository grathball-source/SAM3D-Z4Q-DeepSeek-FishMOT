"""Conditional relative order with common null; no peak/identity certification."""
from common import *
from history import History, anchor_key
from collections import OrderedDict, Counter
raw_source = module('ds28_causal_raw_source', ROOT/'experiments/ds16_relative_depth_order/source.py')
RawDepth, native_masks = raw_source.RawDepth, raw_source.native_masks
from measurement import Measurement
from mixed_depth import array_binding
import copy, math
import numpy as np, cv2
CFG=read(HERE/'CONFIG.json')

def t4_cdf(x):
    u=x/math.hypot(x,2.)
    return max(0.,min(1.,.5+.75*u-.25*u**3))

def endpoint(packet):
    f=packet['fact']
    out=dict(fact_id=f['fact_id'],measurement_sha256=digest(f),frame=f['frame'],
        status='COMMON_NULL',reason=f['reason'],foreground_identity='UNKNOWN')
    if not (f.get('inclusive_independent_partition_agreement') and
            f.get('inclusive_independent_support_agreement')):
        return out
    if f.get('substantial_unresolved_support_ids'):
        return dict(out,reason='UNRESOLVED_MIXTURE_COMMON_NULL')
    supports=[s for s in f['layers'] if s['qualified']]
    if len(supports)!=1:
        return dict(out,reason='ZERO_OR_MULTIPLE_SIGNIFICANT_SUPPORTS_COMMON_NULL')
    s=supports[0]
    if f['summary']['n']<CFG['min_points'] or f['summary']['valid_fraction']<CFG['min_fraction']:
        return dict(out,reason='INSUFFICIENT_ENDPOINT_COVERAGE_COMMON_NULL')
    return dict(out,status='CONDITIONAL_MEASURED_SUPPORT',reason='SOLE_DISTINCT_ANNULUS_PROXY_NOT_FISH_CERTIFICATE',
        support_id=s['support_id'],z_mm=s['z_mm'],sigma_mm=s['sigma_mm'],
        reliability=min(1.,s['independent_n']/max(1,f['original_roi_area'])),
        independent_n=s['independent_n'],background_and_missing_weight='REMAIN_COMMON_NULL')

def pair(a,b):
    ea,eb=endpoint(a),endpoint(b)
    out=dict(A=ea,B=eb,status='COMMON_NULL',probability_A_nearer=.5)
    if ea['status']=='COMMON_NULL' or eb['status']=='COMMON_NULL':return out
    ia=a['maps']['selected_positions'][ea['support_id']]
    ib=b['maps']['selected_positions'][eb['support_id']]
    # All roles are measured in the same frame. The raw source adapter deduplicates each ROI.
    ra=a['source_index'].ravel()[ia];rb=b['source_index'].ravel()[ib]
    if np.intersect1d(ra,rb).size:return dict(out,reason='SHARED_NATIVE_SOURCE_COMMON_NULL')
    delta=eb['z_mm']-ea['z_mm'];scale=math.hypot(ea['sigma_mm'],eb['sigma_mm'])
    p=t4_cdf(delta/scale)
    reliability=ea['reliability']*eb['reliability']
    return dict(out,status='CONDITIONAL_ORDER_PROXY',delta_B_minus_A_mm=delta,scale_mm=scale,
        distribution_probability=p,common_null_weight=1-reliability,
        probability_A_nearer=.5+reliability*(p-.5),physical_accuracy_mm='UNKNOWN')

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

class Context:
    """Preview reads exact branch history. Missing partners remain null, never a favorable edge."""
    def __init__(self,row,history,sources,mapping,epochs,arm):
        self.row=row;self.history=history;self.sources=sources;self.mapping=mapping;self.epochs=epochs;self.arm=arm
    def __deepcopy__(self,memo):return self
    def check(self,engine,observation,public,anchor,origin_rule):
        f,now,n=self.row['frame'],self.row['time'],observation['id']
        out=dict(origin_rule=origin_rule,native_id=n,public_id=public,anchor=copy.deepcopy(anchor),query_frame=f,
            status='COMMON_NULL',delta_cost=0.,comparisons=[],hypothesis_not_observation=True,
            physical_depth_accuracy_mm='UNKNOWN',no_identity_history_write=True)
        record=self.history.anchors.get(anchor_key(anchor))
        if not record or record['frame'] not in self.history.frames:return dict(out,reason='EXACT_BANK_ANCHOR_PROVENANCE_UNKNOWN')
        assert anchor_key(engine.bank[public].get('anchor'))==anchor_key(anchor)
        snapshot=self.history.frames[record['frame']];fragment=snapshot['fragments'].get(record['native'],())
        if not fragment or fragment[-1]['version']!=record['version']:return dict(out,reason='TARGET_ANCHOR_FRAGMENT_VERSION_MISMATCH')
        if not engine.quality(observation) or observation.get('neighbors'):return dict(out,reason='CURRENT_SOURCE_RISK')
        current={engine.alias.get(o['id'],{}).get('target',o['id']):o for o in self.row['observations']}
        h=engine.bank[public];partners=sorted(p for p,ts in engine.partners(h,public).items()
            if p!=public and p in current and current[p]['id']!=n and 0<=h['last_seen']-ts<=1 and 0<=now-ts<=6)
        changes=[]
        for p in partners:
            o=current[p];m=o['id'];pre=snapshot['objects'].get(m)
            detail=dict(partner_public=p,partner_native=m,status='COMMON_NULL',delta_cost=0.)
            version=self.history.current_version(m,f,self.mapping,self.epochs)
            if not pre or pre['public']!=p or pre['version']!=version or self.mapping.get(m)!=p:
                out['comparisons'].append(dict(detail,reason='PARTNER_GENERATION_OR_EPOCH_CHANGED'));changes.append(0.);continue
            if not engine.quality(o) or o.get('neighbors') or not self.sources.separate(f,n,m):
                out['comparisons'].append(dict(detail,reason='CURRENT_PARTNER_PAIR_RISK'));changes.append(0.);continue
            a={x['frame']:x for x in fragment};b={x['frame']:x for x in snapshot['fragments'].get(m,())}
            shared=sorted(set(a)&set(b))[-CFG['fit_observations']:]
            if len(shared)<CFG['minimum_pre_pairs'] or shared[-1]!=anchor['frame'] or any(
                a[g]['version']!=record['version'] or b[g]['version']!=pre['version'] for g in shared):
                out['comparisons'].append(dict(detail,reason='SYNCHRONOUS_PRE_VERSION_OR_COVERAGE_UNKNOWN'));changes.append(0.);continue
            before=[pair(self.sources.packet(self.arm,g,record['native']),self.sources.packet(self.arm,g,m)) for g in shared]
            after=pair(self.sources.packet(self.arm,f,n),self.sources.packet(self.arm,f,m))
            pp=float(np.median([x['probability_A_nearer'] for x in before]));pq=after['probability_A_nearer']
            age=max(0.,now-snapshot['time']);attenuation=max(0.,1-age/CFG['age_attenuation_s'])
            delta=(-CFG['soft_weight']*(2*pp-1)*(2*pq-1)*attenuation
                if abs(pp-.5)>=CFG['minimum_pre_probability_distance'] else 0.)
            # Do not certify anonymous contact/merge observations as A or B. Keep every acquired interval row.
            anonymous=[dict(frame=g,time=r['time'],objects={str(k):v for k,v in r['objects'].items()
                if k in (record['native'],m,n)},identity_roles='UNKNOWN_RISK_EVIDENCE_NOT_REFERENCE')
                for g,r in self.history.frames.items() if anchor['frame']<g<f]
            detail.update(status='SOFT_CONDITIONAL_ORDER' if delta else 'COMMON_NULL',delta_cost=delta,
                pre_frames=shared,pre_pairs=before,current_pair=after,pre_probability_median=pp,current_probability=pq,
                elapsed_seconds=age,age_attenuation=attenuation,pre_versions={'A':record['version'],'B':pre['version']},
                current_partner_claim_version=version,anonymous_interval=anonymous,
                conditional_assumption='LOCAL_DEPTH_ORDER_MAY_PERSIST; NOT_A_PHYSICAL_IDENTITY_CERTIFICATE',
                complete_mapping_hypothesis={str(n):public,str(m):p},
                null_policy='MISSING_BACKGROUND_OR_MIXED_SUPPORT_CONTRIBUTES_HALF; NO_PEAK_SELECTION_NO_PRODUCT')
            out['comparisons'].append(detail);changes.append(delta)
        delta=float(np.mean(changes)) if changes else 0.
        return dict(out,status='SOFT_COST' if delta else 'COMMON_NULL',delta_cost=delta,
            reason='CONDITIONAL_RELATIVE_ORDER_SOFT_EVIDENCE' if delta else 'NO_RELIABLE_ORDER_INCREMENT',
            target_anchor_version=record['version'],partner_candidates=partners)
