"""Two-factor causal experiment on frozen Z2; no GT or future observations."""
from pathlib import Path
import copy
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'sam3_depth_birth_refine_20260918'))
from controller_z2 import BirthRefine, DepthRepair


class NativePrior(BirthRefine):
    def __init__(self, config, requalify=False, native_prior=False, enabled=True):
        super().__init__(config, enabled=enabled)
        self.requalify = requalify
        self.native_prior = native_prior
        self.native_runs = {}
        self._edge_context = None

    def certificate(self, k, frame, now, current):
        o = current.get(k)
        r = self.native_runs.get(k)
        failures = []
        if o is None or o['id'] != k:
            failures.append('not_unmapped_native_incumbent')
        if k in self.alias or k in self.retired:
            failures.append('alias_or_retired')
        if o is not None and not self.quality(o):
            failures.append('current_quality')
        if r is None:
            failures.append('no_native_run')
        else:
            if r['last_frame'] != frame - 1:
                failures.append('native_frame_gap')
            if not 0 < now - r['time'] <= self.birth_config['native_max_gap_s']:
                failures.append('native_time_gap')
            if r['count'] < self.birth_config['native_past_frames']:
                failures.append('short_native_run')
        return dict(qualified=not failures, failures=failures, run=copy.deepcopy(r))

    def history(self, k, view, frame, now):
        regular = super().history(k, view, frame, now)
        if regular is not None or not self.requalify or self._edge_context is None:
            return regular
        ctx = self._edge_context
        # Only active survivors can requalify. Targets and dormant competitors
        # retain Z2's five actual ROI observations and twelve-second age bound.
        if k == ctx['target'] or k not in ctx['occupied']:
            return None
        cert = self.certificate(k, frame, now, ctx['current'])
        h = self.view_bank.get(k, {}).get(view)
        if not cert['qualified'] or h is None:
            return None
        a = h['anchor']
        assert a['frame'] < frame and h['time'] < now and a['canonical_id'] == k
        if not (h['count'] >= 1 and now - h['time'] <= self.birth_config['max_history_age_s']
                and a['native_id'] == k and a['frame'] >= cert['run']['start_frame']):
            return None
        ctx['relaxations'][f'{k}:{view}'] = dict(id=k, view=view, count=h['count'],
                                                anchor=copy.deepcopy(a), certificate=cert)
        return copy.deepcopy(h)

    def edge(self, frame, now, o, k, profiles, occupied, current, born, old):
        if not self.requalify and not self.native_prior:
            return super().edge(frame, now, o, k, profiles, occupied, current, born, old)
        assert self._edge_context is None
        ctx = dict(target=k, occupied=occupied, current=current, relaxations={})
        self._edge_context = ctx
        try:
            t = super().edge(frame, now, o, k, profiles, occupied, current, born, old)
        finally:
            self._edge_context = None
        t['history_requalifications'] = list(ctx['relaxations'].values())
        t['native_reservations'] = 0
        for d in t['partners']:
            if not d['active']:
                continue
            cert = self.certificate(d['id'], frame, now, current)
            d['native_certificate'] = cert
            d['native_reservation'] = False
            if not self.native_prior or not cert['qualified']:
                continue
            histories = [d.get('core_history'), d.get('whole_history')]
            same_run = all(h is None or (h['anchor']['native_id'] == d['id']
                            and h['anchor']['frame'] >= cert['run']['start_frame']) for h in histories)
            d['native_history_same_run'] = same_run
            margin = d.get('joint_core_margin')
            # This prior resolves a nonnegative near tie only. It never
            # overrides a depth preference for swapping, missing evidence,
            # self-incompatibility, poor observation, or whole-mask veto.
            if (not same_run or margin is None or not 0 <= margin < self.birth_config['assignment_margin']
                    or d['failures'] != ['joint_core_opposed_or_ambiguous']
                    or not d.get('survivor_quality') or d.get('own_core') is None
                    or d['own_core']['cost'] >= 1):
                continue
            d['failures'] = []
            d['state'] = 'reserved_by_native_prior'
            d['native_reservation'] = True
            t['native_reservations'] += 1
            t['failures'].remove('partner_' + str(d['id']) + '_joint_core_opposed_or_ambiguous')
        if t['native_reservations'] and 'no_verified_local_survivor' in t['failures']:
            t['failures'].remove('no_verified_local_survivor')
        # Keep positive depth witnesses separate from native reservations.
        t['rejection'] = t['failures'][0] if t['failures'] else None
        return t

    def step(self, frame, now, observations, profiles=None):
        ids, trace = super().step(frame, now, observations, profiles)
        resets = {k for e in trace['events'] if e['kind'] == 'native_conflict_rollback'
                  for k in [e['native_id'], e['canonical_id']]}
        previous = self.native_runs
        current = {}
        for o in sorted(observations, key=lambda x: x['id']):
            n = o['id']
            if ids[n] != n or n in self.alias or n in self.retired or n in resets or not self.quality(o):
                continue
            p = previous.get(n)
            continuous = (p is not None and p['last_frame'] == frame - 1
                          and 0 < now - p['time'] <= self.birth_config['native_max_gap_s'])
            current[n] = dict(start_frame=p['start_frame'] if continuous else frame,
                              count=p['count'] + 1 if continuous else 1, last_frame=frame, time=now)
        self.native_runs = current
        return ids, trace

    def d1_state(self):
        extra = {'requalify', 'native_prior', 'native_runs', '_edge_context'}
        return {k: v for k, v in super().d1_state().items() if k not in extra}

    def z2_state(self):
        extra = {'requalify', 'native_prior', 'native_runs', '_edge_context'}
        return {k: v for k, v in vars(self).items() if k not in extra}
