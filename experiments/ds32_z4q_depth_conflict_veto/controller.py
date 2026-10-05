"""Original Z4Q lifecycle, with read-only depth vetoes before candidate admission."""
import copy
import sys

from common import HERE, CFG, digest
from bridge import Bridge, StableReturn as CanonicalStableReturn

sys.path.insert(0, str(HERE / 'source'))
from ds32_return import StableReturn
from evidence import DepthEvidence


EXTRA_FIELDS = frozenset(('evidence', 'veto_enabled', 'query_context',
    'depth_checks', 'source_observations', 'allow_edge'))


def engine_state(engine):
    """Every original physical/lifecycle field; omit only DS32 side evidence."""
    return {key: copy.deepcopy(value) for key, value in vars(engine).items()
            if key not in EXTRA_FIELDS}


def _plain(value):
    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list, set)):
        return [_plain(item) for item in (sorted(value) if isinstance(value, set) else value)]
    if hasattr(value, 'tolist'):
        return value.tolist()
    return value


def full_state(bridge):
    """Bind actual original state plus branch-owned side evidence and publication."""
    return _plain(dict(engine=engine_state(bridge.engine),
        evidence=bridge.engine.evidence.state(), veto_enabled=bridge.engine.veto_enabled,
        allow_edge=bridge.engine.allow_edge, version=bridge.version,
        previous=bridge.previous, epochs=bridge.epochs, provenance=bridge.provenance))


def committed_edges(trace):
    """Compare actual identity writes without attached diagnostic formatting."""
    return [dict(native_id=event['native_id'], canonical_id=event['canonical_id'],
                 phase='BIRTH_REFINE' if event.get('phase') == 'birth' else 'D1_DELAYED',
                 old_anchor=copy.deepcopy(event.get('old_anchor')))
            for event in trace.get('events', [])
            if event.get('kind') == 'reconnect' and event.get('accepted')]


class DepthVetoEngine(StableReturn):
    def __init__(self, config, namespace, enabled=True, allow_edge=None):
        super().__init__(config)
        self.evidence = DepthEvidence(namespace, CFG)
        self.veto_enabled = enabled
        self.allow_edge = None if allow_edge is None else tuple(allow_edge)
        self.query_context = None
        self.depth_checks = []
        self.source_observations = {}

    def edge_veto(self, frame, now, observation, public, anchor, origin_rule,
                  original_terms, original_eligible):
        assert origin_rule in ('D1_DELAYED', 'BIRTH_REFINE')
        context = self.query_context
        assert context is not None and context['row']['frame'] == frame
        assert context['row']['time'] == now
        result = self.evidence.query(frame, now, observation, public, anchor,
                                     context['extracts'])
        raw_conflict = bool(result['veto'])
        counterfactual_allowed = self.allow_edge == (
            frame, origin_rule, observation['id'], public)
        actual_veto = bool(self.veto_enabled and original_eligible and raw_conflict
                           and not counterfactual_allowed)
        check = dict(result, frame=frame, time=now, phase=origin_rule,
            origin_rule=origin_rule, native_id=observation['id'], public_id=public,
            canonical_id=public, raw_conflict=raw_conflict, conflict=raw_conflict,
            original_eligible=bool(original_eligible), terms=copy.deepcopy(original_terms),
            veto=actual_veto, actual_matrix_deletion=actual_veto,
            counterfactual_allowed=counterfactual_allowed,
            veto_enabled=self.veto_enabled)
        self.depth_checks.append(copy.deepcopy(check))
        return check


class DepthBridge(Bridge):
    def __init__(self, config, namespace, enabled=True, allow_edge=None):
        super().__init__(config)
        self.engine = DepthVetoEngine(config, namespace, enabled, allow_edge)

    def preview(self, row, profiles, extracts, anonymous=()):
        """Preview both policies from this branch's same prior; publish neither."""
        frame, now = row['frame'], row['time']
        before = digest(full_state(self))
        prior = engine_state(self.engine)
        original = CanonicalStableReturn.__new__(CanonicalStableReturn)
        original.__dict__.update(copy.deepcopy(prior))
        original_mapping, original_trace = original.step(
            frame, now, row['observations'], profiles)
        original_hash = digest(vars(original))
        trial = copy.deepcopy(self.engine)
        trial.depth_checks = []
        trial.source_observations = {}
        assert trial.query_context is None
        trial.query_context = dict(row=row, extracts=extracts)
        try:
            mapping, trace = trial.step(frame, now, row['observations'], profiles)
        finally:
            trial.query_context = None
        actual_deletions = sum(bool(check['veto']) for check in trial.depth_checks)
        actual_hash = digest(engine_state(trial))
        if not actual_deletions:
            assert mapping == original_mapping, 'NULL policy changed original mapping'
            assert actual_hash == original_hash, 'NULL policy changed original engine state'
        # commit_once will increment exactly these epochs if the trial is selected.
        post_epochs = dict(self.epochs)
        for native, public in mapping.items():
            if self.previous.get(native) != public:
                post_epochs[native] = post_epochs.get(native, 0) + 1
        physical_before_observe = digest(engine_state(trial))
        trial.source_observations = trial.evidence.observe(
            row, mapping, post_epochs, trial, extracts, anonymous)
        assert digest(engine_state(trial)) == physical_before_observe, 'Observer wrote Z4Q state'
        trace['depth_checks'] = copy.deepcopy(trial.depth_checks)
        trace['source_observations'] = copy.deepcopy(trial.source_observations)
        trace['same_prior_original_mapping'] = copy.deepcopy(original_mapping)
        trace['same_prior_original_engine_state_sha256'] = original_hash
        trace['actual_engine_state_sha256'] = actual_hash
        trace['null_original_state_exact'] = not actual_deletions
        assert digest(full_state(self)) == before, 'Preview mutated authoritative state'
        effective_epochs = {native: self.epochs.get(native, 0) + (native not in self.previous)
                            for native in mapping}
        return dict(version=self.version, frame=frame, now=now,
            observations=row['observations'], profiles=profiles, engine=trial,
            mapping=mapping, trace=trace, epochs=effective_epochs,
            original_mapping=original_mapping, original_trace=original_trace,
            original_engine_state_sha256=original_hash,
            actual_engine_state_sha256=actual_hash,
            actual_matrix_deletions=actual_deletions, post_epochs=post_epochs,
            original_commits=committed_edges(original_trace),
            actual_commits=committed_edges(trace))
