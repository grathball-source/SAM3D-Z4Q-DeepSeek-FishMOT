"""Q: causal recent core witness. R: zero-area native return quarantine.

Public placeholder IDs are bookkeeping for preserved empty observations only.
They never enter the physical identity bank, aliases, or partner histories.
"""
from pathlib import Path
import copy
import sys
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'sam3_depth_birth_native_prior_20260918'))
from controller_z3 import NativePrior, DepthRepair


class QualityBirth(NativePrior):
    def __init__(self, config, recent_core=False, empty_return=False, enabled=True):
        super().__init__(config, native_prior=True, enabled=enabled)
        self.use_recent_core = recent_core
        self.empty_return = empty_return
        self.recent_core = {}
        self.empty_quarantine = {}

    def history(self, k, view, frame, now):
        regular = super().history(k, view, frame, now)
        ctx = self._edge_context
        if not self.use_recent_core or view != 'core' or ctx is None:
            return regular
        if k == ctx['target'] or k not in ctx['occupied']:
            return regular
        cert = self.certificate(k, frame, now, ctx['current'])
        h = self.recent_core.get(k)
        if not cert['qualified'] or h is None:
            return regular
        a = h['anchor']
        if not (a['frame'] < frame and 0 < now - h['time'] <= self.birth_config['recent_core_max_age_s']
                and a['native_id'] == a['canonical_id'] == k
                and a['frame'] >= cert['run']['start_frame']):
            return regular
        ctx['relaxations'][f'{k}:recent_core'] = dict(id=k, view=view, basis='recent_isolated_actual_core',
            anchor=copy.deepcopy(a), certificate=cert, previous_history=copy.deepcopy(regular),
            actual_history=copy.deepcopy(h))
        return copy.deepcopy(h)

    def step(self, frame, now, observations, profiles=None):
        profiles = {} if profiles is None else profiles
        for n, p in profiles.items():
            assert p['frame'] == frame and p['id'] == n and p['mask'] == f'n:{n}'
        if not self.birth_enabled:
            # Matches disabled Z3 behavior; both new factors are dormant.
            return super().step(frame, now, observations, profiles)
        obs = sorted(observations, key=lambda o: o['id'])
        by_native = {o['id']: o for o in obs}
        assert len(by_native) == len(obs) and all(n >= 0 for n in by_native)
        quarantine = {}
        if self.empty_return:
            owners = {}
            for n, a in self.alias.items():
                if n in by_native and by_native[n]['area'] > 0:
                    owners.setdefault(a['target'], []).append(n)
            for k, candidates in sorted(owners.items()):
                o = by_native.get(k)
                if (o is not None and len(candidates) == 1 and k not in self.alias
                        and o['area'] == 0 and o.get('depth', {}).get('n') == 0):
                    quarantine[k] = dict(incumbent_native=candidates[0], public_id=k,
                                        placeholder_id=-1-k, frame=frame)
        # Only evidence-free records are withheld from association. Every raw
        # observation is restored to the exported prediction list below.
        active = [o for o in obs if o['id'] not in quarantine]
        active_profiles = {n: p for n, p in profiles.items() if n not in quarantine}
        areas_before = {k: list(h['areas']) for k, h in self.bank.items()} if self.use_recent_core else {}
        certificates = {o['id']: self.certificate(o['id'], frame, now, by_native)
                        for o in active} if self.use_recent_core else {}
        ids, trace = super().step(frame, now, active, active_profiles)
        resets = {k for e in trace['events'] if e['kind'] == 'native_conflict_rollback'
                  for k in [e['native_id'], e['canonical_id']]}
        if self.use_recent_core:
            for k in list(self.recent_core):
                if (k not in self.native_runs or k in self.alias or k in self.retired or k in resets
                        or now - self.recent_core[k]['time'] > self.birth_config['recent_core_max_age_s']):
                    self.recent_core.pop(k)
            for o in active:
                n = o['id']
                cert = certificates[n]
                area_ref = float(np.median(areas_before[n])) if areas_before.get(n) else 0.
                if (ids[n] != n or n in self.alias or n in self.retired or n in resets
                        or not cert['qualified'] or not self.quality(o) or o.get('neighbors')
                        or area_ref <= 0 or not .5 * area_ref <= o['area'] <= 1.8 * area_ref):
                    continue
                m = self.measurement(profiles.get(n), 'core')
                if m is None or m['u'] > self.birth_config['recent_core_max_risk_mm']:
                    continue
                self.recent_core[n] = dict(m, time=now, count=1,
                    anchor=dict(frame=frame, native_id=n, mask=o['mask'], canonical_id=n))
        if self.empty_return:
            for k, q in sorted(self.empty_quarantine.items()):
                if k not in quarantine or quarantine[k]['incumbent_native'] != q['incumbent_native']:
                    trace['events'].append(dict(kind='empty_native_quarantine_end', native_id=k,
                        incumbent_native=q['incumbent_native'], public_id=k, placeholder_id=-1-k))
            for k, q in sorted(quarantine.items()):
                if k not in self.empty_quarantine or self.empty_quarantine[k]['incumbent_native'] != q['incumbent_native']:
                    trace['events'].append(dict(kind='empty_native_quarantine_begin', native_id=k,
                        incumbent_native=q['incumbent_native'], public_id=k, placeholder_id=-1-k))
                assert ids[q['incumbent_native']] == k
                ids[k] = q['placeholder_id']
            self.empty_quarantine = quarantine
            trace['empty_quarantine'] = {str(k): copy.deepcopy(q) for k, q in quarantine.items()}
        assert set(ids) == set(by_native) and len(set(ids.values())) == len(ids)
        assert all(k >= 0 for k in self.bank) and all(k >= 0 and a['target'] >= 0 for k, a in self.alias.items())
        return ids, trace

    def z3_state(self):
        extra = {'use_recent_core', 'empty_return', 'recent_core', 'empty_quarantine'}
        return {k: v for k, v in vars(self).items() if k not in extra}

    def d1_state(self):
        extra = {'use_recent_core', 'empty_return', 'recent_core', 'empty_quarantine'}
        return {k: v for k, v in super().d1_state().items() if k not in extra}
