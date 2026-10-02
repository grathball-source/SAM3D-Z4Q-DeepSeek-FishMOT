"""Original Z4Q proposals, with causal depth vetoes on individual candidate edges."""
import copy
import math
from common import ROOT, HERE, read, module
from bridge import Bridge  # Load the original controller before any adapter module.
DepthNativeBridge=module('ds15_depth_adapter',HERE/'controller.py').DepthNativeBridge
from ne_controller import StableReturn as HookedStableReturn
from depth_score import log_t4, _logaddexp
from forecast import predict
from depth_state import DepthState

CFG=read(HERE/'CONFIG.json')
DENSITY=module('ds15_auto_density',ROOT/'experiments/ds10_depth_failure_repair/association.py')


class EventDepthState(DepthState):
    def freeze(self,episode,frame,epochs=None,generations=None):
        """The live cache is 30 frames; an intact frozen reference expires by time."""
        result=super().freeze(episode,frame,epochs,generations)
        for role,native,public in zip(('A','B'),episode['member_sources'],episode['public_ids']):
            record=self.live.get(native)
            same=bool(record and record['key'][3]==public and
                (epochs is None or record['key'][4]==epochs.get(native)) and
                (generations is None or record['key'][2]==generations.get(native)))
            samples=(copy.deepcopy(record['latest_fragment']) if same else [])
            if samples and all(s['frame']<frame for s in samples):
                result[role].update(key=copy.deepcopy(record['key']),samples=samples,
                    reference_policy='INTACT_LATEST_SAME_VERSION_FRAGMENT; NO_RISK_JOIN; MAX_12_SECONDS_AT_QUERY')
        return result


class HybridReturn(HookedStableReturn):
    def __init__(self,config,depth_enabled):
        super().__init__(config)
        self.protected={}
        self.depth_enabled=depth_enabled
        self.auto_min_history=config['min_history_count']
        self.depth_context={}
        self.auto_depth_checks=[]

    def edge_veto(self,frame,now,observation,public,anchor,origin_rule):
        """UNKNOWN retains the original candidate; no native-age or integer veto."""
        check=dict(frame=frame,native_id=observation['id'],public_id=public,
            origin_rule=origin_rule,veto=False,reason='ORIGINAL_Z4Q_CANDIDATE_RETAINED',
            evidence_max_frame=frame,depth_status='UNKNOWN',physical_identity='UNKNOWN')
        ctx=self.depth_context
        past=ctx.get('past',{}).get(public)
        current=ctx.get('current',{}).get(observation['id'])
        background=ctx.get('background')
        if not self.depth_enabled:
            check['reason']='SHARED_CONTROL_ORIGINAL_EDGE_UNCHANGED'
        elif (ctx.get('frame')==frame and ctx.get('time')==now and past and current and background
              and past['anchor']==anchor and current['qualified']):
            forecast=predict(copy.deepcopy(past['frozen']),now)
            check.update(history=copy.deepcopy(past),query_fact_id=current['fact_id'],
                depth_forecast=forecast,query_core=copy.deepcopy(current['core']))
            if (forecast.get('mu_mm') is not None and forecast.get('scale_mm') is not None
                and math.isfinite(forecast['mu_mm']) and math.isfinite(forecast['scale_mm'])
                and forecast['scale_mm']>0):
                q=current['core'];sigma=max(CFG['raw_scale_floor_mm'],1.4826*q['mad'])
                raw=log_t4(q['median'],forecast['mu_mm'],math.hypot(sigma,forecast['scale_mm']))
                null=DENSITY._background_logdensity(background,q['median'],sigma)
                lr=_logaddexp(math.log(CFG['signal_fraction'])+raw-null,
                              math.log(1.-CFG['signal_fraction']))
                veto=lr<=-math.log(CFG['minimum_joint_odds'])
                check.update(veto=veto,depth_status='SOURCE_BOUND_COMPARABLE',depth_log_lr=lr,
                    contradiction_threshold=-math.log(CFG['minimum_joint_odds']),
                    reason='STRONG_DEPTH_CONTRADICTION_EDGE_VETO' if veto else 'NO_STRONG_DEPTH_CONTRADICTION',
                    missing_model='COMMON_CURRENT_QUERY_BACKGROUND',
                    posterior_interpretation='PLUGIN_CONTRAST_NOT_CALIBRATED_PHYSICAL_PROBABILITY')
        self.auto_depth_checks.append(check)
        return check

    def step(self,frame,now,observations,profiles=None):
        self.auto_depth_checks=[]
        ids,trace=super().step(frame,now,observations,profiles)
        trace['ds15_auto_depth_checks']=copy.deepcopy(self.auto_depth_checks)
        return ids,trace


class HybridBridge(DepthNativeBridge):
    def __init__(self,config,depth_enabled):
        super().__init__(config)
        self.engine=HybridReturn(config,depth_enabled)

    def stage_birth_reconnect(self,view,changes,candidates_by_source,admissions=None):
        transaction,error=super().stage_birth_reconnect(view,changes,candidates_by_source,admissions)
        if transaction:
            transaction['trace']['ds12_birth_reconnect']['old_automatic_rules_enabled']=True
            transaction['trace']['ds12_birth_reconnect']['strategy']='DS15_ADDITIONAL_DEPTH_BIRTH'
        return transaction,error

    def bind_depth(self,row,measurements,full,memory,rawstate):
        """Bind exact pre-frame bank versions; anonymous risk never becomes pre."""
        frame,now=row['frame'],row['time'];past={}
        for public,bank in self.engine.bank.items():
            anchor=bank.get('anchor') or {};native=anchor.get('native_id')
            record=memory.live.get(native)
            if not record or not anchor or anchor.get('frame',frame)>=frame:continue
            key=record['key']
            if (len(key)!=5 or key[3]!=public or
                memory.anchor_versions.get((public,native,anchor['frame']))!=key):continue
            samples=copy.deepcopy(record['samples'][-CFG['fit_observations']:])
            history=record['geometry_history'][-CFG['fit_observations']:]
            if (len(samples)<self.engine.auto_min_history or
                [(s['frame'],s['time']) for s in samples]!=[(s['frame'],s['time']) for s in history]
                or any(s.get('version_key')!=key or s.get('source')!='RAW_SENSOR_ADAPTIVE'
                       or s['frame']>=frame or s['time']>=now for s in samples)
                or any(b['frame']!=a['frame']+1 or b['time']<=a['time'] for a,b in zip(samples,samples[1:]))
                or not 0<now-samples[-1]['time']<=CFG['birth_max_gap_seconds']):continue
            state=rawstate.live.get(native)
            if not state or list(state['key'])!=key:continue
            past[public]=dict(anchor=copy.deepcopy(anchor),source=native,public=public,
                frozen=dict(key=copy.deepcopy(key),source=native,public=public,samples=samples,
                    cutoff_frame=frame-1,acquired_interval_seconds=None))
        current={o['id']:dict(fact_id=measurements[o['id']]['fact_id'],
            core=copy.deepcopy(measurements[o['id']]['core']),
            qualified=bool(measurements[o['id']]['core_usable'] and not o.get('neighbors')
                           and self.engine.quality(o))) for o in row['observations']}
        background=DENSITY._depth_background(measurements,full)
        if background and background['method']=='NO_USABLE_DEPTH_BACKGROUND':background=None
        self.engine.depth_context=dict(frame=frame,time=now,past=past,current=current,background=background)

