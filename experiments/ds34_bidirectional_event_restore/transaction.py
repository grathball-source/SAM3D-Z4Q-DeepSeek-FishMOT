"""Two-member event writes on the original Z4Q engine; old sources stay readonly."""
import copy
import sys

from common import ROOT, OLD, S0P, digest

for path in (ROOT / 'online/closed_loop_2888/z4q_source', OLD, S0P):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
from bridge import Bridge, StableReturn
from manager_p import GroupBridgeP

NATIVE_FIELDS = ('alias', 'birth', 'pending', 'native_seen', 'native_runs',
                 'recent_core', 'return_quarantine', 'empty_quarantine', 'first_eligible')
PUBLIC_FIELDS = ('bank', 'view_bank')
EVENT_ALIAS_SOURCES = {'DS34_EVENT_NUMERIC', 'DS34_UNRESOLVED_SOURCE_CONTINUITY'}


def engine_state(engine):
    return {k:copy.deepcopy(v) for k,v in vars(engine).items() if k != 'protected'}


def full_state(bridge):
    return dict(engine=copy.deepcopy(vars(bridge.engine)), version=bridge.version,
                previous=bridge.previous, epochs=bridge.epochs, provenance=bridge.provenance)


def bridge_hash(bridge):
    return digest(full_state(bridge))


def outside_state(engine, natives, publics):
    return dict(native={field:{n:copy.deepcopy(v) for n,v in getattr(engine, field).items() if n not in natives}
                       for field in NATIVE_FIELDS},
                public={field:{k:copy.deepcopy(v) for k,v in getattr(engine, field).items() if k not in publics}
                       for field in PUBLIC_FIELDS}, retired=engine.retired - natives)


class ProtectedStableReturn(StableReturn):
    def __init__(self, config):
        super().__init__(config)
        self.protected = {}

    def _step_with_event_return(self, frame, now, observations, profiles):
        """Resolve only a current original conflict that would break an event alias chain."""
        owned={n for n,a in self.alias.items() if a.get('source') in EVENT_ALIAS_SOURCES}
        if not owned:return super().step(frame,now,observations,profiles)
        current={o['id']:o for o in observations};aliases=copy.deepcopy(self.alias);quarantine=set();returns=set()
        owners={}
        for n,a in aliases.items():
            if n in current and current[n]['area']>0:owners.setdefault(a['target'],[]).append(n)
        for k,members in owners.items():
            if k not in current or k in aliases:continue
            if self.quality(current[k]):returns.add(k)
            elif self.return_guard_enabled and self.birth_enabled and len(members)==1:quarantine.add(k)
        native=set(current)-quarantine
        connected=set(owned)
        while True:
            previous=set(connected)
            for n,a in aliases.items():
                if n in connected or a['target'] in connected:connected.update((n,a['target']))
            if connected==previous:break
        def original_once(plan):
            plan=copy.deepcopy(plan);groups={}
            for n in sorted(native):groups.setdefault(plan.get(n,{}).get('target',n),[]).append(n)
            for k,members in groups.items():
                if len(members)<2:continue
                keep=k if k in members else max(members,key=lambda n:(self.native_seen.get(n,-1),-n))
                for n in members:
                    if n!=keep:plan.pop(n,None)
            occupied={}
            for n in native:occupied.setdefault(plan.get(n,{}).get('target',n),[]).append(n)
            return plan,{k:ns for k,ns in occupied.items() if len(ns)>1}
        # Current native arbitration and actual accepted aliases supply the conflict; no future is assumed.
        events=[];plan=copy.deepcopy(aliases)
        while True:
            remaining,duplicates=original_once(plan)
            duplicates={k:ns for k,ns in duplicates.items() if k in connected}
            if not duplicates:break
            cancel={n for ns in duplicates.values() for n in ns if n in remaining and n in owned}
            if not cancel:
                raise AssertionError('DS34_UNSAFE_OUTSIDE_RETURN_CASCADE')
            for n in sorted(cancel):
                a=plan.pop(n);events.append(dict(kind='native_conflict_rollback',native_id=n,
                    canonical_id=a['target'],keep_native=a['target'],
                    source='DS34_CURRENT_FRAME_EVENT_RETURN_CASCADE',frame=frame,
                    old_alias=copy.deepcopy(a),actual_qualified_return_natives=sorted(returns),
                    physical_identity='UNKNOWN',already_published_history_rewritten=False))
        for event in events:
            n,k=event['native_id'],event['canonical_id'];self.alias.pop(n,None);self.pending.pop(n,None)
            self.retired.add(n);self.counts['native_conflict_rollbacks']+=1
            for key in (n,k):
                self.native_runs.pop(key,None);self.recent_core.pop(key,None);self.view_bank.pop(key,None)
        ids,trace=super().step(frame,now,observations,profiles)
        if events:
            trace['events']=events+trace['events']
            trace['ds34_event_return_cascade']=dict(frame=frame,actual_qualified_returns=sorted(returns),
                event_aliases_revoked=[e['native_id'] for e in events],bank_copied=False,
                non_DS34_aliases_explicitly_changed=False,future_read=False,original_return_arbitration=True)
        return ids,trace

    def step(self, frame, now, observations, profiles=None):
        if not self.protected:
            return self._step_with_event_return(frame, now, observations, profiles)
        assert len(self.protected) == 1, 'DS34 has one active protected pair'
        spec = next(iter(self.protected.values()))
        public = set(spec['member_public'])
        suppressed = set(spec['suppressed'])
        natives = suppressed | set(spec['member_sources'])
        saved = {}
        for field in PUBLIC_FIELDS + NATIVE_FIELDS:
            store = getattr(self, field)
            keys = public if field in PUBLIC_FIELDS else natives
            saved[field] = {k:copy.deepcopy(store[k]) for k in keys if k in store}
            for k in keys: store.pop(k, None)
        retired = self.retired & natives
        self.retired.difference_update(natives)
        try:
            active = [o for o in observations if o['id'] not in suppressed]
            pp = {n:p for n,p in (profiles or {}).items() if n not in suppressed}
            ids, trace = self._step_with_event_return(frame, now, active, pp)
        finally:
            for field, entries in saved.items():
                store = getattr(self, field)
                keys = public if field in PUBLIC_FIELDS else natives
                for k in keys: store.pop(k, None)
                store.update(entries)
            self.retired.difference_update(natives)
            self.retired.update(retired)
        ids.update({n:k for n,k in spec['outputs'].items() if n in {o['id'] for o in observations}})
        assert len(ids) == len(observations) == len(set(ids.values())), 'protected publication collision'
        trace['merge_split_group'] = dict(episode=spec['episode'], suppressed=sorted(suppressed),
            outputs=copy.deepcopy(spec['outputs']), member_reference_updated=False, preview_only_not_published=True)
        return ids, trace


class GroupBridge(GroupBridgeP):
    def __init__(self, config):
        Bridge.__init__(self, config)
        self.engine = ProtectedStableReturn(config)

    def stage_group_restore(self, view, episode, selected):
        before = bridge_hash(self)
        local = copy.deepcopy(episode)
        local['post_roles'] = {n:[p for p in values if p['frame'] <= view['frame']]
                               for n,values in local['post_roles'].items()}
        if any(not values or values[-1]['frame'] != view['frame'] for values in local['post_roles'].values()):
            return None, 'missing_actual_q_observation'
        if any(values[-1]['time'] != view['now'] or values[-1]['source'] != n or
               any(p['time'] > view['now'] for p in values) or
               values[-1]['source_generation'] != episode.get('post_generations', {}).get(n, values[-1]['source_generation'])
               for n,values in local['post_roles'].items()):
            return None, 'q_observation_time_source_or_generation_mismatch'
        targets=set(selected.values())
        event_sources=set(episode['member_sources'])|set(selected)|{episode['group_source']}
        if any(n not in event_sources and a['target'] in event_sources|targets
               for n,a in view['engine'].alias.items()):
            return None, 'OUTSIDE_ALIAS_OWNERSHIP'
        unselected=(set(episode['member_sources']) | {episode['group_source']}) - set(selected)
        if any(o['id'] in unselected and
               (o['id'] in targets or view['engine'].alias.get(o['id'], {}).get('target') in targets)
               for o in view['observations']):
            return None, 'UNSELECTED_MEMBER_OWNERSHIP'
        transaction, error = super().stage_group_restore(view, local, selected)
        if transaction is not None:
            natives = set(episode['member_sources']) | set(selected) | {episode['group_source']}
            publics = set(episode['public_ids'])
            for n in selected:
                transaction['engine'].empty_quarantine.pop(n, None)
                transaction['engine'].return_quarantine.pop(n, None)
                transaction['engine'].first_eligible.pop(n, None)
                if n in transaction['engine'].alias:
                    transaction['engine'].alias[n]['source'] = 'DS34_EVENT_NUMERIC'
            if outside_state(transaction['engine'], natives, publics) != outside_state(view['engine'], natives, publics):
                return None, 'outside_state_changed'
            transaction['provenance_source'] = 'DS34_EVENT_NUMERIC'
            transaction['trace'] = copy.deepcopy(transaction['trace'])
            transaction['trace']['ds34_group_restore'] = dict(episode=episode['id'], q=view['frame'],
                selected=copy.deepcopy(selected), actual_post_frames={n:[p['frame'] for p in v] for n,v in local['post_roles'].items()},
                physical_identity='UNKNOWN_UNTIL_POSTSEAL', future_measurements_written=False,
                complete_member_bijection=True, outside_state_preserved=True)
        assert bridge_hash(self) == before, 'stage mutated authoritative branch'
        return transaction, error

    def local_fallback(self, view, episode):
        before = bridge_hash(self)
        transaction, detail = super().local_fallback(view, episode)
        candidate = copy.deepcopy(self.engine)
        candidate.protected.pop(episode['id'], None)
        candidate_ids, _ = candidate.step(view['frame'], view['now'], view['observations'], view['profiles'])
        if detail['status'] == 'LOCAL_FALLBACK_COMMITTED':
            for n in detail['event_native_write_set']:
                if n in candidate.first_eligible:
                    transaction['engine'].first_eligible[n] = copy.deepcopy(candidate.first_eligible[n])
                else:
                    transaction['engine'].first_eligible.pop(n, None)
        else:
            natives=set(detail['event_native_write_set'])
            outside={o['id'] for o in view['observations']} - natives
            occupied={view['mapping'][n] for n in outside} | {
                a['target'] for n,a in view['engine'].alias.items() if n not in natives}
            chosen={n:view['mapping'][n] for n in outside};used=set(chosen.values())
            trial=transaction['engine'];continuity=[];unsupported=[]
            for n in sorted(natives):
                # Candidate native fields came from a real own-branch q step.
                for field in NATIVE_FIELDS:
                    dst,src=getattr(trial,field),getattr(candidate,field)
                    if n in src:dst[n]=copy.deepcopy(src[n])
                    else:dst.pop(n,None)
                trial.retired.discard(n)
                if n in candidate.retired:trial.retired.add(n)
                prior=self.previous.get(n);bank=view['engine'].bank.get(prior)
                qualified=bool(bank and bank.get('anchor') and bank['anchor']['frame']<view['frame'] and
                               bank.get('clean_count',0)>=5 and bank.get('clean_time') is not None)
                if prior is not None and prior>=0 and prior not in used|occupied and qualified:
                    k=prior;continuity.append(n)
                    trial.alias.pop(n,None)
                    if n!=k:trial.alias[n]=dict(target=k,anchor=copy.deepcopy(bank['anchor']),commit_frame=view['frame'],
                        source='DS34_UNRESOLVED_SOURCE_CONTINUITY',transaction_version=self.version+1)
                    trial.pending.pop(n,None);trial.retired.discard(n)
                    trial.bank[k]=copy.deepcopy(bank)
                    if k in view['engine'].view_bank:trial.view_bank[k]=copy.deepcopy(view['engine'].view_bank[k])
                else:
                    k=candidate_ids[n]
                    if k>=0 and k not in used|occupied:
                        if k in candidate.bank:trial.bank[k]=copy.deepcopy(candidate.bank[k])
                        if k in candidate.view_bank:trial.view_bank[k]=copy.deepcopy(candidate.view_bank[k])
                    else:
                        trial.alias.pop(n,None)
                        k=n if n not in used|occupied else -1000000-n
                        while k in used:k-=1
                        unsupported.append(n)
                chosen[n]=k;used.add(k)
            assert len(chosen)==len(set(chosen.values()))==len(view['observations'])
            for n,k in chosen.items():
                if n in natives and k>=0:assert trial.alias.get(n,{}).get('target',n)==k
            transaction['mapping']=chosen
            detail=dict(detail,actual_alias_continuity_sources=continuity,
                unsupported_persistent_claim_sources=unsupported,
                unresolved_publication='ACTUAL_OWN_ENGINE_NATIVE_OR_QUALIFIED_ALIAS; NEGATIVE_IS_EXPLICIT_UNRESOLVED',
                physical_identity='UNKNOWN')
            transaction['trace']['merge_split_local_fallback']=detail
        transaction['provenance_source'] = 'DS34_OWN_BRANCH_LOCAL_FALLBACK'
        assert bridge_hash(self) == before, 'fallback mutated authoritative branch'
        return transaction, detail

    def local_release(self, view, episode):
        """Release before split; retain legal continuous public labels in actual aliases."""
        local = copy.deepcopy(episode)
        local['q'] = view['frame']
        natives = set(local['member_sources']) | set(local['post_roles']) | {local['group_source']}
        observed = {o['id'] for o in view['observations']}
        local['post_roles'] = {n:[] for n in natives & observed}
        transaction, detail = self.local_fallback(view, local)
        wanted = dict(transaction['mapping'])
        used = {k for n,k in wanted.items() if n not in natives}
        for n in sorted(natives & observed):
            prior = self.previous.get(n)
            if prior is not None and prior >= 0 and prior not in used:
                wanted[n] = prior
                used.add(prior)
        for n in sorted(natives & observed):
            if wanted[n] in used and self.previous.get(n) != wanted[n]:
                wanted[n] = transaction['mapping'][n]
            used.add(wanted[n])
        trial = copy.deepcopy(transaction['engine'])
        outside = observed - natives
        outside_targets = {wanted[n] for n in outside}
        changed = {n:k for n,k in wanted.items() if transaction['mapping'][n] != k}
        safe = len(set(wanted.values())) == len(wanted)
        for n,k in changed.items():
            h = view['engine'].bank.get(k)
            safe &= k not in outside_targets and bool(h and h.get('anchor') and h['anchor']['frame'] < view['frame'])
        if safe:
            for n,k in changed.items():
                trial.alias.pop(n, None)
                if n != k:
                    trial.alias[n] = dict(target=k, anchor=copy.deepcopy(view['engine'].bank[k]['anchor']),
                        commit_frame=view['frame'], source='DS34_UNRESOLVED_SOURCE_CONTINUITY', transaction_version=self.version+1)
                trial.pending.pop(n, None)
                trial.retired.discard(n)
                # Anonymous release observations never overwrite preserved member references.
            for k in episode['public_ids']:
                if k in view['engine'].bank: trial.bank[k] = copy.deepcopy(view['engine'].bank[k])
                if k in view['engine'].view_bank: trial.view_bank[k] = copy.deepcopy(view['engine'].view_bank[k])
            transaction.update(engine=trial, mapping=wanted)
        detail = dict(detail, release_before_split=True, continuity_preserved=safe,
                      physical_identity='UNKNOWN', status='LOCAL_RELEASE_CONTINUITY' if safe else 'LOCAL_RELEASE_FALLBACK')
        transaction['trace']['ds34_local_release'] = detail
        return transaction, detail

    def commit_once(self, view, transaction=None):
        ids, trace = super().commit_once(view, transaction)
        if transaction is not None:
            for n in transaction['changes']:
                if n in self.provenance:
                    self.provenance[n]['source'] = transaction.get('provenance_source', 'DS34_EVENT_NUMERIC')
        return ids, trace
