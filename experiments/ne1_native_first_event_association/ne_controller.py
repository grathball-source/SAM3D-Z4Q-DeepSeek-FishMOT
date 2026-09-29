"""Native-first Z4Q controller with explicit, pre-assignment reconnect gates.

The frozen D1 and BirthRefine implementations are reused through their
pairwise-hook copies. No PX/PX-A co-visibility state or rule is installed.
"""
import copy
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PX = ROOT / 'experiments/z4q_pairwise_reconnect_repair/source'
MS1 = ROOT / 'experiments/ms1_s0_development_8400'
S0P = ROOT / 'experiments/s0p_identity_publication'
FROZEN = ROOT / 'online/closed_loop_2888/z4q_source'
for path in (PX, S0P, MS1, FROZEN):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from px_return import StableReturn  # noqa: E402
from manager_p import GroupBridgeP  # noqa: E402


class NativeFirstProtectedReturn(StableReturn):
    """Preserve measurements and group state; reject only automatic identity edges."""

    def __init__(self, config):
        super().__init__(config)
        self.protected = {}
        self.auto_edge_checks = []

    def edge_veto(self, frame, now, observation, public, anchor, origin_rule):
        assert origin_rule in ('D1_DELAYED', 'BIRTH_REFINE')
        check = dict(frame=frame, native_id=observation['id'], public_id=public,
                     origin_rule=origin_rule, veto=True,
                     reason='NATIVE_FIRST_AUTOMATIC_RECONNECT_DISABLED')
        self.auto_edge_checks.append(check)
        return check

    def step(self, frame, now, observations, profiles=None):
        self.auto_edge_checks = []
        if not self.protected:
            ids, trace = super().step(frame, now, observations, profiles)
        else:
            assert len(self.protected) == 1, 'overlapping groups are out of scope'
            spec = next(iter(self.protected.values()))
            members = set(spec['member_public'])
            suppressed = set(spec['suppressed'])
            native_keys = suppressed | set(spec['member_sources'])
            saved = {}
            for name in ('bank', 'view_bank', 'alias', 'birth', 'pending', 'native_seen',
                         'native_runs', 'recent_core', 'return_quarantine',
                         'empty_quarantine', 'first_eligible'):
                store = getattr(self, name)
                keys = members if name in ('bank', 'view_bank') else native_keys
                saved[name] = {k: copy.deepcopy(store[k]) for k in keys if k in store}
                for k in keys:
                    store.pop(k, None)
            saved_retired = self.retired & native_keys
            self.retired.difference_update(native_keys)
            active = [o for o in observations if o['id'] not in suppressed]
            active_profiles = {n:p for n,p in (profiles or {}).items() if n not in suppressed}
            ids, trace = super().step(frame, now, active, active_profiles)
            for name, entries in saved.items():
                store = getattr(self, name)
                keys = members if name in ('bank', 'view_bank') else native_keys
                for k in keys:
                    store.pop(k, None)
                store.update(entries)
            self.retired.difference_update(native_keys)
            self.retired.update(saved_retired)
            ids.update({n:k for n,k in spec['outputs'].items()
                        if n in {o['id'] for o in observations}})
            assert len(ids) == len(observations) == len(set(ids.values()))
            trace['merge_split_group'] = dict(episode=spec['episode'],
                suppressed=sorted(suppressed), outputs=copy.deepcopy(spec['outputs']),
                preview_only_not_published=True)
        trace['native_first_auto_edge_checks'] = copy.deepcopy(self.auto_edge_checks)
        assert not any(e.get('kind') == 'reconnect' and e.get('accepted')
                       for e in trace.get('events', [])), trace.get('events')
        return ids, trace


class NativeFirstGroupBridgeP(GroupBridgeP):
    def __init__(self, config):
        super().__init__(config)
        self.engine = NativeFirstProtectedReturn(config)
