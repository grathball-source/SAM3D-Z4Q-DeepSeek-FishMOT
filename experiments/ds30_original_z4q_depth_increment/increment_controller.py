"""Read-only event observer; the authoritative engine remains the original Z4Q."""
from common import *
from bridge import Bridge
import copy
adapter=module('ds30_readonly_manager',ROOT/'experiments/ds17_mixed_depth_activity_repair/controller.py')

def engine_state(engine):return vars(engine)
def branch_state(branch):
    return dict(engine=vars(branch.engine),version=branch.version,previous=branch.previous,
        epochs=branch.epochs,provenance=branch.provenance)

class EvidenceBridge(Bridge):
    def sync(self,branch):
        protected=copy.deepcopy(getattr(self.engine,'protected',{}))
        self.engine=copy.deepcopy(branch.engine);self.engine.protected=protected
        self.previous=copy.deepcopy(branch.previous);self.epochs=copy.deepcopy(branch.epochs)
        self.version=branch.version;self.provenance=copy.deepcopy(branch.provenance)
    causal_view=Bridge.preview

class IncrementBridge(Bridge):
    def stage_group_restore(self,view,episode,selected):
        if view['version']!=self.version or view['frame']!=episode['q']:return None,'stale_episode'
        if set(selected)!=set(episode['post_roles']) or set(selected.values())!=set(episode['public_ids']):return None,'invalid_bijection'
        # A frozen pre anchor is evidence, not permission to overwrite a newer bank.
        for k in selected.values():
            if self.engine.bank.get(k,{}).get('anchor')!=episode['bank_snapshot'][k].get('anchor'):
                return None,'actual_target_anchor_changed_since_pre'
        changes={n:k for n,k in selected.items() if view['mapping'][n]!=k}
        if not changes:return None,'selected_mapping_already_original'
        transaction,error=self.stage(view,changes)
        if transaction:
            for n in changes:
                alias=transaction['engine'].alias.get(n)
                if alias:alias['source']='DS30_DEPTH_INCREMENT'
        return transaction,error
    def commit_once(self,view,transaction=None):
        result=super().commit_once(view,transaction)
        if transaction:
            for n in transaction['changes']:self.provenance[n]['source']='DS30_DEPTH_INCREMENT'
        return result

EventManager=adapter.EventManager
