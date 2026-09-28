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


def sample(row, profile=None, observation_class='SOURCE_OBSERVATION',
           generation=None, public_id=None, public_epoch=None):
    return dict(frame=row['frame'], time=row['time'], source=row['id'],
                center=list(center(row)), bbox=list(row['box']), area=row['area'],
                neighbors=list(row.get('neighbors', [])), depth=copy.deepcopy(row.get('depth')),
                core=copy.deepcopy((profile or {}).get('core')),
                whole=copy.deepcopy((profile or {}).get('whole')),
                observation_class=observation_class, source_generation=generation,
                public_id=public_id, public_epoch=public_epoch,
                measured_time=row['time'], time_source='OBSERVATION_STREAM',
                sensor_sync_status='NOT_PROVIDED')


def velocity(history, limit=10):
    """Intercept plus slope OLS on the latest contiguous, same-version observations."""
    points = history[-limit:]
    for index in range(len(points)-1, 0, -1):
        a, b = points[index-1], points[index]
        if (b['frame'] != a['frame']+1 or b['time'] <= a['time']
                or b.get('source_generation') != a.get('source_generation')
                or b.get('public_epoch') != a.get('public_epoch')):
            points = points[index:]
            break
    frames = [p['frame'] for p in points]
    times = [p['time'] for p in points]
    base = dict(status='UNKNOWN', model='OLS_INTERCEPT_LINEAR_TIME', samples=len(points),
                sample_frames=frames, sample_times=times,
                span_seconds=(times[-1]-times[0] if times else None))
    if len(points) < 3 or any(not math.isfinite(t) for t in times) or any(
            b <= a for a,b in zip(times,times[1:])):
        return dict(base, reason='TOO_FEW_OR_INVALID_TIMES')
    t0=times[0]
    relative=[t-t0 for t in times]
    mean_t=sum(relative)/len(relative)
    centered=[t-mean_t for t in relative]
    denom=sum(t*t for t in centered)
    if denom <= 0:
        return dict(base,reason='DEGENERATE_TIME')
    slopes=[]
    intercepts=[]
    residual_axes=[]
    for axis in (0,1):
        values=[p['center'][axis] for p in points]
        mean_value=sum(values)/len(values)
        slope=sum(dt*(v-mean_value) for dt,v in zip(centered,values))/denom
        intercept=mean_value-slope*mean_t
        residual=[v-intercept-slope*t for t,v in zip(relative,values)]
        slopes.append(slope)
        intercepts.append(intercept)
        residual_axes.append(residual)
    rms=[math.sqrt(sum(v*v for v in values)/len(values)) for values in residual_axes]
    residual_2d=math.sqrt(rms[0]**2+rms[1]**2)
    return dict(status='ESTIMATED_FROM_MEASURED',model='OLS_INTERCEPT_LINEAR_TIME',
                samples=len(points), sample_frames=frames,sample_times=times,
                span_seconds=times[-1]-times[0],first_frame=frames[0],last_frame=frames[-1],
                time_origin=times[0],intercept_px=intercepts,
                px_per_second=slopes,speed_px_per_second=math.hypot(*slopes),
                residual_rms_px_by_axis=rms,residual_rms_2d_px=residual_2d,
                residual_max_2d_px=max(math.hypot(*values) for values in zip(*residual_axes)),
                uncertainty='IN_SAMPLE_RESIDUAL_ONLY_NOT_CALIBRATED_FORECAST')


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
        native_keys = suppressed | set(spec['member_sources'])
        saved = {}
        for name in ('bank', 'view_bank', 'alias', 'birth', 'pending', 'native_seen',
                     'native_runs', 'recent_core', 'return_quarantine'):
            store = getattr(self, name)
            keys = members if name in ('bank','view_bank') else native_keys
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
            keys = members if name in ('bank','view_bank') else native_keys
            for k in keys:
                store.pop(k, None)
            store.update(entries)
        self.retired.difference_update(native_keys)
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
        reserved = {target: copy.deepcopy(trial.bank[target]) for target in episode['public_ids']}
        for source in selected:
            # bank/view_bank are keyed by public identity. A source number may
            # collide with a reserved or unrelated public bank: neither is trash.
            trial.alias.pop(source, None)
            trial.pending.pop(source, None)
            trial.retired.discard(source)
            trial.native_runs.pop(source, None)
            trial.recent_core.pop(source, None)
        for target, bank in reserved.items():
            assert trial.bank[target] == bank
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
    """Same full-pair weights; omit a modality for both candidates if any edge lacks it."""
    sources = list(episode['post_roles'])
    assert len(sources) == 2
    pre = [episode['pre'][role] for role in ('A','B')]
    post = [episode['post_roles'][n] for n in sources]
    if any(not x for x in pre+post):
        return 'UNRESOLVED', dict(reason='missing_fragment')
    fits=[velocity(x) for x in pre+post]
    motion_usable=all(x['status']!='UNKNOWN' for x in fits)
    rule=episode.get('depth_rule') or dict(min_points=16,min_valid_fraction=.2,
        risk_floor_mm=15.,mad_scale=1.4826,risk_budget_mm=60.)
    def core_usable(d):
        if not d or any(d.get(k) is None or not isinstance(d[k],(int,float)) or
                        not math.isfinite(d[k]) for k in ('median','mad','n','valid_fraction')):
            return False
        return (d['median']>0 and d['mad']>=0 and d['n']>=rule['min_points'] and
                d['valid_fraction']>=rule['min_valid_fraction'] and
                max(rule['risk_floor_mm'],rule['mad_scale']*d['mad'])<=rule['risk_budget_mm'])
    depth_usable=all(core_usable(x[-1]['core']) for x in pre+post)
    scores = []
    for order in ((0,1),(1,0)):
        score = 0.
        details = []
        for i,j in enumerate(order):
            a,b = pre[i],post[j]
            va,vb = fits[i],fits[2+j]
            gap = b[0]['time']-a[-1]['time']
            if gap <= 0:
                return 'UNRESOLVED', dict(reason='noncausal_gap')
            diag = max(1.,math.hypot(a[-1]['bbox'][2]-a[-1]['bbox'][0],
                                     a[-1]['bbox'][3]-a[-1]['bbox'][1]))
            horizon=min(gap,1.)
            predicted = ([va['intercept_px'][axis]+va['px_per_second'][axis]*
                          (a[-1]['time']+horizon-va['time_origin']) for axis in (0,1)]
                         if motion_usable else list(a[-1]['center']))
            position = math.dist(predicted,b[0]['center'])/diag
            motion = (math.dist(va['px_per_second'],vb['px_per_second']) * horizon/diag
                      if motion_usable else None)
            depth = (abs(a[-1]['core']['median']-b[-1]['core']['median']) /
                     max(15.,a[-1]['core'].get('mad') or 0.,b[-1]['core'].get('mad') or 0.)
                     if depth_usable else None)
            edge = position + (.25*motion if motion is not None else 0.) + (.25*depth if depth is not None else 0.)
            score += edge
            details.append(dict(position=position, motion=motion, core_depth=depth,
                gap_seconds=gap,prediction_interval_seconds=horizon,
                prediction_model='OLS_LINEAR_EXTRAPOLATION' if motion_usable else 'LAST_MEASURED_POSITION_ONLY',
                predicted_center_px=predicted,pre_fit_residual_rms_2d_px=va.get('residual_rms_2d_px'),
                uncertainty='OLS_RESIDUAL_IS_IN_SAMPLE_NOT_FORECAST_BOUND'))
        scores.append(dict(choice='H1' if order==(0,1) else 'H2', score=score, edges=details))
    context=dict(motion_used_for_both=motion_usable,core_depth_used_for_both=depth_usable,
                 missing_modalities_are_not_zero_cost_edges=True)
    if abs(scores[0]['score']-scores[1]['score']) <= 1e-9:
        return episode['temporary_choice'], dict(scores=scores, tie=True,**context)
    return min(scores,key=lambda x:x['score'])['choice'], dict(scores=scores, tie=False,**context)


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
        self.source_generation = {}
        self.last_source_frame = {}
        self.last_native_run_start = {}
        self.frame_class = {}
        self.pending_clear = set()
        self.next_temporary_id = -1000000

    def _generation(self, native, frame):
        return self.source_generation.get(native,0)+(self.last_source_frame.get(native)!=frame-1)

    def _temporary_id(self, episode, native, frame):
        key=(native,self._generation(native,frame))
        if key not in episode['temporary_ids']:
            used=set(self.bridge.previous.values()) | set(episode['temporary_ids'].values())
            while self.next_temporary_id in used:
                self.next_temporary_id-=1
            episode['temporary_ids'][key]=self.next_temporary_id
            self.next_temporary_id-=1
        return episode['temporary_ids'][key]

    def _release(self, episode, frame, status, current):
        episode['status'],episode['end']=status,frame
        self.bridge.engine.protected.pop(episode['id'],None)
        self.frame_class={n:'UNRESOLVED_EVENT_OBSERVATION' for n in
            set(episode['member_sources']) | set(episode['post_roles']) |
            ({episode['group_source']} if episode['group_source'] in current else set())}
        self.pending_clear.update(self.frame_class)
        self.active=None
        self.counts[status.lower()]+=1
        return dict(kind=status,episode=episode['id'])

    def _history_update(self, row, profiles):
        seen = set()
        for o in row['observations']:
            n = o['id']
            seen.add(n)
            generation=self._generation(n,row['frame'])
            epoch=self.bridge.epochs.get(n)
            native_run=self.bridge.engine.native_runs.get(n,{}).get('start_frame')
            prior=self.clean.get(n)
            version_changed=bool(prior and (prior[-1]['source_generation']!=generation or
                prior[-1]['public_epoch']!=epoch or prior[-1]['public_id']!=self.bridge.previous.get(n)))
            if (native_run is not None and self.last_native_run_start.get(n) is not None
                    and native_run!=self.last_native_run_start[n]):
                version_changed=True
            if version_changed:
                self.clean[n]=deque(maxlen=30)
                self.last_clean.pop(n,None)
                self.risk[n]=deque(maxlen=30)
            observation_class=self.frame_class.get(n,'SOURCE_OBSERVATION')
            s = sample(dict(o, frame=row['frame'], time=row['time']), profiles.get(n),
                       observation_class,generation,self.bridge.previous.get(n),epoch)
            clean = (observation_class=='SOURCE_OBSERVATION' and o['area'] >= 64
                     and not o.get('neighbors') and self.bridge.engine.quality(o))
            if clean:
                old = self.clean.get(n, deque(maxlen=30))
                if old and old[-1]['frame'] != row['frame']-1:
                    old = deque(maxlen=30)
                    self.last_clean.pop(n,None)
                old.append(s)
                self.clean[n] = old
                self.risk[n] = deque(maxlen=30)
            else:
                if self.clean.get(n):
                    self.last_clean[n] = list(self.clean[n])
                    self.clean[n] = deque(maxlen=30)
                self.risk.setdefault(n,deque(maxlen=30)).append(s)
            self.source_generation[n]=generation
            self.last_source_frame[n]=row['frame']
            if native_run is not None:
                self.last_native_run_start[n]=native_run
        for n in list(self.clean):
            if n not in seen and self.clean[n]:
                self.last_clean[n] = list(self.clean[n])
                self.clean[n] = deque(maxlen=30)
        for n in self.pending_clear:
            self.clean.pop(n,None)
            self.last_clean.pop(n,None)
            self.risk.pop(n,None)
        self.pending_clear.clear()

    def before(self, row, profiles):
        frame = row['frame']
        self.frame_class={}
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
                    q=None,end=None,status='SUSPECT',temporary_choice='H1',numeric=None,
                    temporary_ids={},depth_rule=copy.deepcopy(self.bridge.engine.birth_config))
                self.events.append(self.active)
                self.counts['suspect'] += 1
        e = self.active
        if e is None:
            return None
        elapsed = row['time']-e['suspect_time']
        if elapsed > self.config['max_episode_seconds']:
            return self._release(e,frame,'TIMEOUT',{o['id']:o for o in row['observations']})
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
            e['group'].append(sample(dict(current[group],frame=frame,time=row['time']),profiles.get(group),
                'GROUP_MEASUREMENT',self._generation(group,frame)))
            self.frame_class[group]='GROUP_MEASUREMENT'
            for n in (a,b):
                if n!=group and n in current:
                    e['group_anonymous'].append(sample(dict(current[n],frame=frame,time=row['time']),profiles.get(n),
                        'ANONYMOUS_RESIDUAL',self._generation(n,frame)))
                    self.frame_class[n]='ANONYMOUS_RESIDUAL'
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
                    outputs[n] = self._temporary_id(e,n,frame)
        elif len(good)==2:
            if e['confirm_frame'] is None:
                return self._release(e,frame,'CANCELLED',current)
            if e['post_roles'] and set(good)!=set(e['post_roles']):
                e['post_roles']={}
                e['post_start']=None
                e['split_confirm']=None
            if not e['post_roles']:
                ordered=sorted(good,key=lambda n:(center(current[n])[0],center(current[n])[1],n))
                e['post_roles']={n:[] for n in ordered}
                e['post_start']=frame
            for n in e['post_roles']:
                e['post_roles'][n].append(sample(dict(current[n],frame=frame,time=row['time']),profiles.get(n),
                    'POST_UNASSIGNED',self._generation(n,frame)))
                self.frame_class[n]='POST_UNASSIGNED'
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
                    outputs[n]=self._temporary_id(e,n,frame)
                    self.frame_class[n]='ANONYMOUS_RESIDUAL'
        else:
            return self._release(e,frame,'OUT_OF_SCOPE',current)
        self.bridge.engine.protected[e['id']]=dict(episode=e['id'],generation=e['generation'],
            member_public=e['public_ids'],member_sources=e['member_sources'],
            suppressed=list(outputs),outputs=outputs)
        return dict(kind=e['status'],episode=e['id'])

    def after(self, row, profiles):
        self._history_update(row,profiles)

    def finish(self, frame, status):
        e=self.active
        assert e and e['q']==frame
        e['status'],e['end']=status,frame
        self.pending_clear.update(set(e['member_sources']) | set(e['post_roles']) | {e['group_source']})
        self.active=None
