"""Original matrices plus the existing two edge hooks; no PX exclusion observer."""
import copy
from common import *
from bridge import Bridge
from px_return import StableReturn as HookReturn

class RelativeReturn(HookReturn):
    def __init__(self,config):
        super().__init__(config);self.relative_context=None;self.edge_veto_checks=[]
    def edge_veto(self,frame,now,observation,public,anchor,origin_rule):
        if self.relative_context is None:
            result=dict(veto=False,status='DISABLED',reason='NO_NEW_EVIDENCE',origin_rule=origin_rule)
        else:
            assert (frame,now)==(self.relative_context.row['frame'],self.relative_context.row['time'])
            result=self.relative_context.check(self,observation,public,anchor,origin_rule)
        self.edge_veto_checks.append(copy.deepcopy(result));return result
    def step(self,frame,now,observations,profiles=None):
        self.edge_veto_checks=[]
        ids,trace=super().step(frame,now,observations,profiles)
        trace['relative_order_checks']=copy.deepcopy(self.edge_veto_checks)
        return ids,trace

class OrderBridge(Bridge):
    def __init__(self,config):
        super().__init__(config);self.engine=RelativeReturn(config)
