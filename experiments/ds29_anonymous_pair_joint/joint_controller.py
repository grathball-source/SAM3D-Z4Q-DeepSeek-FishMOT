"""Reuse clean/activity isolation and atomic S0 transactions; outside events original Z4Q."""
from common import *
import copy, importlib.util, sys

adapter=module('ds29_frozen_clean_transaction',ROOT/'experiments/ds17_mixed_depth_activity_repair/controller.py')
CLEAN_FIELDS=adapter.CLEAN_FIELDS
clean_reference,restore_clean=adapter.clean_reference,adapter.restore_clean
package='ds29_original_controller'
spec=importlib.util.spec_from_file_location(package,DS27/'source/__init__.py',submodule_search_locations=[str(DS27/'source')])
m=importlib.util.module_from_spec(spec);sys.modules[package]=m;spec.loader.exec_module(m)
from ds29_original_controller.px_return import StableReturn

EXTRAS={'protected','identity_reference_registry','observation_frame','observation_classes'}
def engine_state(engine):return {k:v for k,v in vars(engine).items() if k not in EXTRAS}

class JointReturn(StableReturn):
    def __init__(self,config):
        super().__init__(config)
        self.protected={};self.identity_reference_registry={}
        self.observation_frame=None;self.observation_classes={}

    def apply_depth_soft(self,matrix,terms,frame,now,phase,observations):
        # DS27's instrumented original matrices call this hook. All costs stay original.
        return None

    def edge_veto(self,frame,now,observation,public,anchor,origin_rule):
        spec=next(iter(self.protected.values()),None)
        anonymous=set(self.observation_classes) if self.observation_frame==frame else set()
        blocked=bool(spec and (public in spec['member_public'] or observation['id'] in anonymous))
        return dict(veto=blocked,reason='WAIT_ANONYMOUS_PAIR_JOINT_TRANSACTION' if blocked else 'ORIGINAL_EDGE_RETAINED',origin_rule=origin_rule)

    def step(self,frame,now,observations,profiles=None):
        spec=next(iter(self.protected.values()),None)
        classes=self.observation_classes if self.observation_frame==frame else {}
        anonymous=set(classes)
        if spec:anonymous|=set(spec['member_sources'])|set(spec['suppressed'])
        publics={self.alias.get(n,{}).get('target',n) for n in anonymous}
        if spec:publics|=set(spec['member_public'])
        before={k:clean_reference(self.bank.get(k,adapter.EMPTY_CLEAN)) for k in publics}
        views={k:copy.deepcopy(self.view_bank[k]) for k in publics if k in self.view_bank}
        recent={n:copy.deepcopy(self.recent_core[n]) for n in anonymous if n in self.recent_core}
        if spec:
            registry=self.identity_reference_registry.setdefault(f"{spec['episode']}:{spec['generation']}",dict(
                references={str(k):copy.deepcopy(before[k]) for k in spec['member_public']},
                views={str(k):copy.deepcopy(views.get(k)) for k in spec['member_public']}))
            assert all(registry['references'][str(k)]==before[k] and registry['views'][str(k)]==views.get(k) for k in spec['member_public'])
        obs,prof=copy.deepcopy(observations),copy.deepcopy(profiles or {})
        null=dict(n=0,valid_fraction=0.,median=None,mad=None)
        for o in obs:
            if o['id'] in anonymous:
                o['depth']=copy.deepcopy(null)
                for key in ('whole','core'):
                    if o['id'] in prof:prof[o['id']][key]=copy.deepcopy(null)
        ids,trace=super().step(frame,now,obs,prof)
        for k in publics:
            if k in self.bank:
                restore_clean(self.bank[k],before[k]);self.view_bank.pop(k,None)
                if k in views:self.view_bank[k]=views[k]
        for n in anonymous:
            self.recent_core.pop(n,None)
            if n in recent:self.recent_core[n]=recent[n]
        trace['depth_soft_checks']=[]
        trace['joint_protection']=dict(anonymous_sources=sorted(anonymous),protected_publics=sorted(publics),
            activity_updated=True,clean_reference_frozen=True,group_depth_not_written_to_individuals=True)
        return ids,trace

class JointBridge(adapter.EventBridge):
    def __init__(self,config):
        super().__init__(config);self.engine=JointReturn(config)
    def commit_once(self,view,transaction=None):
        ids,trace=super().commit_once(view,transaction)
        if transaction:
            for n in transaction['changes']:self.provenance[n]['source']='DS29_ANONYMOUS_PAIR_JOINT'
        return ids,trace

EventManager=adapter.EventManager
