"""A qualified native observation is required to revoke a verified alias.

The frozen Q controller and its quality predicate are reused unchanged.
All raw records are exported; quarantined records get output-only negative IDs.
"""
from pathlib import Path
import copy
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'sam3_depth_birth_quality_20260918'))
from controller_z4 import QualityBirth


class StableReturn(QualityBirth):
    def __init__(self, config, guard=True, enabled=True):
        super().__init__(config, recent_core=True, empty_return=False, enabled=enabled)
        self.return_guard_enabled = guard
        self.return_quarantine = {}

    def step(self, frame, now, observations, profiles=None):
        if not self.return_guard_enabled or not self.birth_enabled:
            return super().step(frame, now, observations, profiles)
        profiles = {} if profiles is None else profiles
        for n, p in profiles.items():
            assert p['frame'] == frame and p['id'] == n and p['mask'] == f'n:{n}'
        obs = sorted(observations, key=lambda o: o['id'])
        by_native = {o['id']: o for o in obs}
        assert len(by_native) == len(obs) and all(n >= 0 for n in by_native)
        owners = {}
        for n, alias in sorted(self.alias.items()):
            if n in by_native and by_native[n]['area'] > 0:
                owners.setdefault(alias['target'], []).append(n)
        quarantine, checks = {}, []
        for k, candidates in sorted(owners.items()):
            o = by_native.get(k)
            if o is None or len(candidates) != 1 or k in self.alias:
                continue
            qualified = self.quality(o)
            reason = None
            if not qualified:
                if o['area'] < 64:
                    reason = 'below_existing_min_area_64'
                elif o.get('presence') is not None:
                    reason = 'invalid_or_low_existing_presence'
                else:
                    reason = 'below_existing_birth_score'
            check = dict(native_id=k, incumbent_native=candidates[0], public_id=k,
                         area=o['area'], presence=o.get('presence'), score_birth=o.get('score_birth'),
                         qualified=qualified, reason=reason, evidence_max_frame=frame,
                         action='native_priority' if qualified else 'retain_verified_alias')
            checks.append(check)
            if not qualified:
                quarantine[k] = dict(check, placeholder_id=-1-k)
        active = [o for o in obs if o['id'] not in quarantine]
        active_profiles = {n: p for n, p in profiles.items() if n not in quarantine}
        ids, trace = super().step(frame, now, active, active_profiles)
        for k, previous in sorted(self.return_quarantine.items()):
            if k not in quarantine or quarantine[k]['incumbent_native'] != previous['incumbent_native']:
                trace['events'].append(dict(kind='native_return_quarantine_end', native_id=k,
                    incumbent_native=previous['incumbent_native'], public_id=k, placeholder_id=-1-k))
        for k, q in sorted(quarantine.items()):
            if k not in self.return_quarantine or self.return_quarantine[k]['incumbent_native'] != q['incumbent_native']:
                trace['events'].append(dict(kind='native_return_quarantine_begin', **copy.deepcopy(q)))
            assert ids[q['incumbent_native']] == k
            ids[k] = q['placeholder_id']
        self.return_quarantine = quarantine
        trace['native_return_checks'] = checks
        trace['return_quarantine'] = {str(k): copy.deepcopy(q) for k, q in quarantine.items()}
        assert set(ids) == set(by_native) and len(set(ids.values())) == len(ids)
        assert all(k >= 0 for k in self.bank)
        assert all(n >= 0 and a['target'] >= 0 for n, a in self.alias.items())
        return ids, trace

    def q_state(self):
        extra = {'return_guard_enabled', 'return_quarantine'}
        return {k: v for k, v in vars(self).items() if k not in extra}


def parent_trace(trace):
    t = copy.deepcopy(trace)
    t.pop('native_return_checks', None)
    t.pop('return_quarantine', None)
    t['events'] = [e for e in t['events'] if not e['kind'].startswith('native_return_quarantine_')]
    return t
