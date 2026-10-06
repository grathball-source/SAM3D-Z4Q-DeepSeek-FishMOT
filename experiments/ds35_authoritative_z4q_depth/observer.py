"""The event manager can mutate its evidence copy, never the authoritative Bridge."""
from common import *
import copy
from bridge import Bridge

History = module('ds35_exact_reference_history', PRIOR/'history.py').History
EventManager = module('ds35_unchanged_event_rules', PRIOR/'manager.py').EventManager
LAG = module('ds35_unchanged_publication_buffer', PRIOR/'lag.py')
LagBuffer, state_hash = LAG.LagBuffer, LAG.state_hash

def branch_state(branch):
    return dict(engine=copy.deepcopy(vars(branch.engine)), version=branch.version,
        previous=copy.deepcopy(branch.previous), epochs=copy.deepcopy(branch.epochs), provenance=copy.deepcopy(branch.provenance))

class EvidenceBridge(Bridge):
    def sync(self, branch):
        protected = copy.deepcopy(getattr(self.engine, 'protected', {}))
        self.engine = copy.deepcopy(branch.engine)
        self.engine.protected = protected
        self.previous, self.epochs = copy.deepcopy(branch.previous), copy.deepcopy(branch.epochs)
        self.version, self.provenance = branch.version, copy.deepcopy(branch.provenance)

