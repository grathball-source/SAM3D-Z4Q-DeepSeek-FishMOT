"""Frozen DS32 real engine/preview transaction; replace owned evidence only."""
from common import OLD32, CFG, readonly_module
from evidence import OLD, DepthEvidence
from immutable_sources import digest_snapshot
import inspect, textwrap

CONTROL = readonly_module('ds37_readonly_ds32_controller',
    OLD32.HERE/'controller.py', evidence=OLD)
engine_state, full_state, committed_edges = CONTROL.engine_state, CONTROL.full_state, CONTROL.committed_edges

def engine_read(engine):
    """Internal read-only values, serialized immediately; no mutable view export."""
    return {k:v for k,v in vars(engine).items() if k not in CONTROL.EXTRA_FIELDS}

def snapshot(bridge):
    """Same full-state hash content, without copying immutable depth sources.

    Both before/after digests serialize actual current content. No memoized
    hashes, omitted fields, or assumed equal baseline state.
    """
    base=CONTROL._plain(dict(engine=engine_read(bridge.engine),veto_enabled=bridge.engine.veto_enabled,
        allow_edge=bridge.engine.allow_edge,version=bridge.version,previous=bridge.previous,
        epochs=bridge.epochs,provenance=bridge.provenance))
    base['evidence']=bridge.engine.evidence._read_state()
    return base

original_preview=textwrap.dedent(inspect.getsource(CONTROL.DepthBridge.preview))
assert original_preview.count('digest(full_state(self))')==2
preview_source=original_preview.replace('digest(full_state(self))','digest_snapshot(snapshot(self))')
assert preview_source.count('prior = engine_state(self.engine)')==1
preview_source=preview_source.replace('prior = engine_state(self.engine)','prior = engine_read(self.engine)')
assert preview_source.count('digest(engine_state(trial))')==3
preview_source=preview_source.replace('digest(engine_state(trial))','digest(engine_read(trial))')
assert preview_source.count('physical_before_observe = digest(engine_read(trial))')==1
preview_source=preview_source.replace('physical_before_observe = digest(engine_read(trial))','physical_before_observe = actual_hash')
preview_scope=dict(vars(CONTROL),snapshot=snapshot,engine_read=engine_read,digest_snapshot=digest_snapshot)
exec(compile(preview_source,
    __file__+':exact_preview_adapter','exec'),preview_scope)

class DepthBridge(CONTROL.DepthBridge):
    preview=preview_scope['preview']
    def __init__(self, config, namespace, mode, enabled=True):
        super().__init__(config, namespace, enabled)
        self.engine.evidence = DepthEvidence(namespace, CFG, mode)
