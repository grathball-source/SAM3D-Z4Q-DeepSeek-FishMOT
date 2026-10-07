"""Frozen DS32 real engine/preview transaction; replace owned evidence only."""
from common import OLD32, CFG, readonly_module
from evidence import OLD, DepthEvidence
import inspect, textwrap

CONTROL = readonly_module('ds37_readonly_ds32_controller',
    OLD32.HERE/'controller.py', evidence=OLD)
engine_state, full_state, committed_edges = CONTROL.engine_state, CONTROL.full_state, CONTROL.committed_edges

def snapshot(bridge):
    """Same full-state hash content, without copying immutable depth sources.

    Both before/after digests serialize actual current content. No memoized
    hashes, omitted fields, or assumed equal baseline state.
    """
    base=CONTROL._plain(dict(engine=engine_state(bridge.engine),veto_enabled=bridge.engine.veto_enabled,
        allow_edge=bridge.engine.allow_edge,version=bridge.version,previous=bridge.previous,
        epochs=bridge.epochs,provenance=bridge.provenance))
    base['evidence']=bridge.engine.evidence._read_state()
    return base

original_preview=textwrap.dedent(inspect.getsource(CONTROL.DepthBridge.preview))
assert original_preview.count('digest(full_state(self))')==2
preview_scope=dict(vars(CONTROL),snapshot=snapshot)
exec(compile(original_preview.replace('digest(full_state(self))','digest(snapshot(self))'),
    __file__+':exact_preview_adapter','exec'),preview_scope)

class DepthBridge(CONTROL.DepthBridge):
    preview=preview_scope['preview']
    def __init__(self, config, namespace, mode, enabled=True):
        super().__init__(config, namespace, enabled)
        self.engine.evidence = DepthEvidence(namespace, CFG, mode)
