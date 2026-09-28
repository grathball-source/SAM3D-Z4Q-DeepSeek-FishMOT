"""Two-member merge protection around the frozen Z4Q controller."""
import copy
import math
from collections import Counter, deque

from mask_geometry import mask, shifted_coverage
from source_scan import center

import sys
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[2] / 'online/closed_loop_2888/z4q_source'
sys.path.insert(0, str(SOURCE))
from bridge import Bridge, StableReturn  # noqa: E402


def sample(row, profile=None):
    return dict(frame=row['frame'], time=row['time'], source=row['id'],
                center=list(center(row)), bbox=list(row['box']), area=row['area'],
                neighbors=list(row.get('neighbors', [])), depth=copy.deepcopy(row.get('depth')),
                core=copy.deepcopy((profile or {}).get('core')),
                whole=copy.deepcopy((profile or {}).get('whole')))


def velocity(history, limit=10):
    points = history[-limit:]
    if len(points) < 3:
        return dict(status='UNKNOWN', samples=len(points))
    t0, t1 = points[0]['time'], points[-1]['time']
    if t1 <= t0:
        return dict(status='UNKNOWN', samples=len(points))
    x0,y0 = points[0]['center']
    x1,y1 = points[-1]['center']
    return dict(status='ESTIMATED_FROM_MEASURED', samples=len(points),
                first_frame=points[0]['frame'], last_frame=points[-1]['frame'],
                px_per_second=[(x1-x0)/(t1-t0), (y1-y0)/(t1-t0)])


class ProtectedStableReturn(StableReturn):
    """Run unrelated Z4Q observations while group references remain untouched."""

    def __init__(self, config):
        super().__init__(config)
        self.protected = {}

    def step(self, frame, now, observations, profiles=None):
        if not self.protected:
            return super().step(frame, now, observations, profiles)
        assert len(self.protected) == 1, 'overlapping groups are out of scope'
        spec = next(iter(self.protected.values()))
        members = set(spec['member_public'])
        suppressed = set(spec['suppressed'])
        saved = {}
        for name in ('bank', 'view_bank', 'alias', 'birth', 'pending', 'native_seen',
                     'native_runs', 'recent_core', 'return_quarantine'):
            store = getattr(self, name)
            keys = members | suppressed
            saved[name] = {k: copy.deepcopy(store[k]) for k in keys if k in store}
            for k in keys:
                store.pop(k, None)
        saved_retired = {k for k in self.retired if k in members | suppressed}
        self.retired.difference_update(members | suppressed)
        active = [o for o in observations if o['id'] not in suppressed]
        active_profiles = {n:p for n,p in (profiles or {}).items() if n not in suppressed}
        ids, trace = super().step(frame, now, active, active_profiles)
        for name, entries in saved.items():
            store = getattr(self, name)
            for k in members | suppressed:
                store.pop(k, None)
            store.update(entries)
        self.retired.difference_update(members | suppressed)
        self.retired.update(saved_retired)
        ids.update({n:k for n,k in spec['outputs'].items() if n in {o['id'] for o in observations}})
        assert len(ids) == len(observations) == len(set(ids.values()))
        trace['merge_split_group'] = dict(episode=spec['episode'], suppressed=sorted(suppressed),
                                          outputs=copy.deepcopy(spec['outputs']))
        return ids, trace


class GroupBridge(Bridge):
    def __init__(self, config):
        super().__init__(config)
        self.engine = ProtectedStableReturn(config)

    def stage_group_restore(self, view, episode, selected):
        """Atomically release one protected pair into a complete observed bijection."""
        if view['version'] != self.version or episode['id'] not in view['engine'].protected:
            return None, 'stale_episode'
        if episode['generation'] != view['engine'].protected[episode['id']]['generation']:
            return None, 'stale_generation'
        if view['frame'] != episode['q'] or any(
                view['engine'].bank.get(k) != episode['bank_snapshot'][k]
                for k in episode['public_ids']):
            return None, 'protected_reference_changed'
        if set(selected) != set(episode['post_roles']) or set(selected.values()) != set(episode['public_ids']):
            return None, 'invalid_bijection'
        observed = {o['id'] for o in view['observations'] if o['area'] >= 64}
        if not set(selected).issubset(observed):
            return None, 'post_observation_missing'
        wanted = dict(view['mapping'])
        wanted.update(selected)
        if len(wanted) != len(set(wanted.values())):
            return None, 'occupied_target'
        trial = copy.deepcopy(view['engine'])
        trial.protected.pop(episode['id'])
        for source in selected:
            if source not in episode['member_sources'] and source in trial.bank:
                trial.bank.pop(source, None)
                trial.view_bank.pop(source, None)
            trial.alias.pop(source, None)
            trial.pending.pop(source, None)
            trial.retired.discard(source)
            trial.native_runs.pop(source, None)
            trial.recent_core.pop(source, None)
        for source, target in selected.items():
            anchor = copy.deepcopy(trial.bank[target]['anchor'])
            if source != target:
                trial.alias[source] = dict(target=target, anchor=anchor,
                                           commit_frame=view['frame'], source='MS1_GROUP_RESTORE',
                                           transaction_version=self.version+1)
            h = trial.bank[target]
            h['last_seen'] = view['now']
            h['last_frame'] = view['frame']
            # The q observation is real; earlier group centroid/depth never enters either bank.
            o = next(o for o in view['observations'] if o['id'] == source)
            if trial.quality(o) and not o.get('neighbors'):
                h['clean_box'] = list(o['box'])
                h['clean_time'] = view['now']
                h['motion'] = [(p['time'], p['center']) for p in episode['post_roles'][source][-5:]]
                h['anchor'] = dict(frame=view['frame'], native_id=source,
                                   mask=o['mask'], canonical_id=target)
                h['areas'] = (h['areas'] + [o['area']])[-15:]
                h['clean_count'] += 1
                if trial.depth_valid(o):
                    z = float(o['depth']['median'])
                    h['depth_history'] = (h['depth_history'] + [(view['now'], z)])[-15:]
                    h['ema'] = z if h['ema'] is None else .2*z+.8*h['ema']
        return dict(engine=trial, mapping=wanted, trace=view['trace'],
                    changes={n:k for n,k in selected.items() if view['mapping'][n] != k},
                    anchors={n:copy.deepcopy(episode['bank_snapshot'][k]['anchor']) for n,k in selected.items()}), None


def numeric_choice(episode):
    """Frozen full-pair comparison: position 1, velocity .25, comparable depth .25."""
    sources = list(episode['post_roles'])
    assert len(sources) == 2
    pre = [episode['pre'][role] for role in ('A','B')]
    post = [episode['post_roles'][n] for n in sources]
    scores = []
    depth_usable = all(x and x[-1]['core'] and x[-1]['core'].get('median') is not None
                       for x in pre + post)
    for order in ((0,1),(1,0)):
        score = 0.
        details = []
        for i,j in enumerate(order):
            a,b = pre[i],post[j]
            if not a or not b:
                return 'UNRESOLVED', dict(reason='missing_fragment')
            va,vb = velocity(a),velocity(b)
            gap = b[0]['time']-a[-1]['time']
            diag = max(1.,math.hypot(a[-1]['bbox'][2]-a[-1]['bbox'][0],
                                     a[-1]['bbox'][3]-a[-1]['bbox'][1]))
            predicted = [a[-1]['center'][axis] + (va['px_per_second'][axis]*min(gap,1.)
                        if va['status']!='UNKNOWN' else 0.) for axis in (0,1)]
            position = math.dist(predicted,b[0]['center'])/diag
            motion = (math.dist(va['px_per_second'],vb['px_per_second']) * min(gap,1.)/diag
                      if va['status']!='UNKNOWN' and vb['status']!='UNKNOWN' else None)
            depth = (abs(a[-1]['core']['median']-b[-1]['core']['median']) /
                     max(15.,a[-1]['core'].get('mad') or 0.,b[-1]['core'].get('mad') or 0.)
                     if depth_usable else None)
            edge = position + (.25*motion if motion is not None else 0.) + (.25*depth if depth is not None else 0.)
            score += edge
            details.append(dict(position=position, motion=motion, core_depth=depth, gap_seconds=gap))
        scores.append(dict(choice='H1' if order==(0,1) else 'H2', score=score, edges=details))
    if abs(scores[0]['score']-scores[1]['score']) <= 1e-9:
        return episode['temporary_choice'], dict(scores=scores, tie=True)
    return min(scores,key=lambda x:x['score'])['choice'], dict(scores=scores, tie=False)


def choice_mapping(episode, choice):
    sources = list(episode['post_roles'])
    targets = episode['public_ids'] if choice == 'H1' else episode['public_ids'][::-1]
    return dict(zip(sources, targets))


class MergeSplitManager:
    def __init__(self, arm, bridge, suspects, config, assignments):
        self.arm, self.bridge, self.suspects, self.config = arm, bridge, suspects, config
        self.assignments = assignments
        self.clean = {}
        self.last_clean = {}
        self.risk = {}
        self.active = None
        self.events = []
        self.counts = Counter()

    def _history_update(self, row, profiles):
        seen = set()
        for o in row['observations']:
            n = o['id']
            seen.add(n)
            s = sample(dict(o, frame=row['frame'], time=row['time']), profiles.get(n))
            clean = o['area'] >= 64 and not o.get('neighbors') and self.bridge.engine.quality(o)
            if clean:
                old = self.clean.get(n, deque(maxlen=30))
                if old and old[-1]['frame'] != row['frame']-1:
                    old = deque(maxlen=30)
                old.append(s)
                self.clean[n] = old
                self.risk[n] = deque(maxlen=30)
            else:
                if self.clean.get(n):
                    self.last_clean[n] = list(self.clean[n])
                    self.clean[n] = deque(maxlen=30)
                self.risk.setdefault(n,deque(maxlen=30)).append(s)
        for n in list(self.clean):
            if n not in seen and self.clean[n]:
                self.last_clean[n] = list(self.clean[n])
                self.clean[n] = deque(maxlen=30)

    def before(self, row, profiles):
        frame = row['frame']
        hit = self.suspects.get(frame)
        if self.active is None and hit:
            sources = hit['sources']
            prior = self.bridge.previous
            targets = [prior.get(n) for n in sources]
            if len(set(targets)) != 2 or any(k is None or k not in self.bridge.engine.bank
                                                or not self.bridge.engine.bank[k].get('anchor') for k in targets):
                self.counts['out_of_scope_reference'] += 1
            else:
                eid = 'MS1-F'+str(frame)
                pre = {role:list(self.clean.get(n) or self.last_clean.get(n, []))[-30:]
                       for role,n in zip(('A','B'),sources)}
                risk = {role:list(self.risk.get(n, [])) for role,n in zip(('A','B'),sources)}
                self.active = dict(id=eid,generation=frame,source_suspect=hit,
                    member_sources=sources,group_source=hit['group'],public_ids=targets,
                    bank_snapshot={k:copy.deepcopy(self.bridge.engine.bank[k]) for k in targets},
                    pre=pre,pre_risk=risk,suspect_frame=frame,suspect_time=row['time'],
                    confirm_frame=None,group=[],group_anonymous=[],post_roles={},post_start=None,split_confirm=None,
                    q=None,end=None,status='SUSPECT',temporary_choice='H1',numeric=None)
                self.events.append(self.active)
                self.counts['suspect'] += 1
        e = self.active
        if e is None:
            return None
        elapsed = row['time']-e['suspect_time']
        if elapsed > self.config['max_episode_seconds']:
            e['status'],e['end'] = 'TIMEOUT',frame
            self.bridge.engine.protected.pop(e['id'],None)
            self.active = None
            self.counts['timeout'] += 1
            return dict(kind='TIMEOUT',episode=e['id'])
        current = {o['id']:o for o in row['observations']}
        a,b = e['member_sources']
        if frame==e['suspect_frame']:
            good=[e['group_source']]
        else:
            last=e['group'][-1]
            reference=mask(self.assignments[last['frame']]['masks'][f'n:{last["source"]}'])
            good=[]
            for n,o in current.items():
                if not self.bridge.engine.quality(o) or f'n:{n}' not in self.assignments[frame]['masks']:
                    continue
                cx,cy=center(o)
                x1,y1,x2,y2=last['bbox']
                radius=max(8.,.25*math.hypot(x2-x1,y2-y1))
                if not (x1-radius<=cx<=x2+radius and y1-radius<=cy<=y2+radius):
                    continue
                actual=mask(self.assignments[frame]['masks'][f'n:{n}'])
                if shifted_coverage(actual,reference,0,0,radius)>.15:
                    good.append(n)
        if len(good)==1:
            group = good[0]
            e['group_source']=group
            e['group'].append(sample(dict(current[group],frame=frame,time=row['time']),profiles.get(group)))
            for n in (a,b):
                if n!=group and n in current:
                    e['group_anonymous'].append(sample(dict(current[n],frame=frame,time=row['time']),profiles.get(n)))
            e['post_roles'] = {}
            e['post_start'] = None
            e['split_confirm'] = None
            if frame==e['suspect_frame']+1:
                e['confirm_frame'],e['status'] = frame,'MERGED'
                self.counts['confirmed'] += 1
            carrier=(self.bridge.previous.get(group) if group in self.bridge.previous else None)
            if carrier not in e['public_ids']:
                carrier=e['public_ids'][0]
            outputs={group:carrier}
            for n in (a,b):
                if n != group and n in current:
                    outputs[n] = -100000-frame*10-n
        elif len(good)==2:
            if e['confirm_frame'] is None:
                e['status'],e['end'] = 'CANCELLED',frame
                self.bridge.engine.protected.pop(e['id'],None)
                self.active = None
                self.counts['cancelled'] += 1
                return dict(kind='CANCELLED',episode=e['id'])
            if e['post_roles'] and set(good)!=set(e['post_roles']):
                e['post_roles']={}
                e['post_start']=None
                e['split_confirm']=None
            if not e['post_roles']:
                ordered=sorted(good,key=lambda n:(center(current[n])[0],center(current[n])[1],n))
                e['post_roles']={n:[] for n in ordered}
                e['post_start']=frame
            for n in e['post_roles']:
                e['post_roles'][n].append(sample(dict(current[n],frame=frame,time=row['time']),profiles.get(n)))
            length=min(map(len,e['post_roles'].values()))
            if length==1:
                e['temporary_choice'],e['temporary_numeric']=numeric_choice(e)
                if e['temporary_choice']=='UNRESOLVED':
                    e['temporary_choice']='H1'
            if length==3:
                e['split_confirm']=frame
            if length==5:
                e['q']=frame
                e['status']='READY_TO_RESTORE'
            outputs=choice_mapping(e,e['temporary_choice'])
            for n in (a,b):
                if n not in outputs and n in current:
                    outputs[n]=-100000-frame*10-n
        else:
            e['status'],e['end']='OUT_OF_SCOPE',frame
            self.bridge.engine.protected.pop(e['id'],None)
            self.active=None
            self.counts['out_of_scope']+=1
            return dict(kind='OUT_OF_SCOPE',episode=e['id'])
        self.bridge.engine.protected[e['id']]=dict(episode=e['id'],generation=e['generation'],
            member_public=e['public_ids'],suppressed=list(outputs),outputs=outputs)
        return dict(kind=e['status'],episode=e['id'])

    def after(self, row, profiles):
        self._history_update(row,profiles)

    def finish(self, frame, status):
        e=self.active
        assert e and e['q']==frame
        e['status'],e['end']=status,frame
        self.active=None
