"""Frozen StableReturn plus one causal, pair-specific reconnect veto."""
import copy

from co_visibility_exclusion import CoVisibilityExclusion
from px_return import StableReturn


class PairwiseStableReturn(StableReturn):
    def __init__(self, config, enabled=True, namespace='test'):
        super().__init__(config, enabled=enabled)
        self.co_visibility = CoVisibilityExclusion(self.cfg['confirm'], history_seconds=12,
                                                   namespace=namespace)
        self.edge_veto_checks = []

    def edge_veto(self, frame, now, observation, public, anchor, origin_rule):
        assert self.co_visibility.frame == frame and self.co_visibility.now == now
        result = self.co_visibility.check(observation['id'], public, anchor, origin_rule)
        self.edge_veto_checks.append(copy.deepcopy(result))
        return result

    def step(self, frame, now, observations, profiles=None):
        self.edge_veto_checks = []
        self.co_visibility.prepare(frame, now, observations, self)
        mapping, trace = super().step(frame, now, observations, profiles)
        self.co_visibility.finish(frame, now, observations, mapping, self)
        trace['edge_veto_checks'] = copy.deepcopy(self.edge_veto_checks)
        trace['co_visibility_version_count'] = len(self.co_visibility.live_segments)
        trace['anchor_registry_count'] = len(self.co_visibility.anchor_registry)
        trace['pair_witness_count'] = len(self.co_visibility.pair_witnesses)
        trace['source_lifecycle'] = copy.deepcopy(self.co_visibility.lifecycle)
        return mapping, trace
