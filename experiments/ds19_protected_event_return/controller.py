"""An original protected-target proposal becomes an event-local transaction.

The old matrix, costs, confirmation and time windows run on a private proposal
clone. Only a validated local write set can replace the ordinary causal view.
"""
import copy
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
_spec = importlib.util.spec_from_file_location('ds19_frozen_ds18_controller',
    ROOT/'experiments/ds18_association_evidence_interface_repair/controller.py')
_ds18 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_ds18)
M = _ds18._measure
clean_reference, restore_clean = _ds18.clean_reference, _ds18.restore_clean
Bridge = _ds18.Bridge
ANONYMOUS_CLASSES = _ds18.ANONYMOUS_CLASSES


def _member_records(episode):
    return episode.get('returned_members', {})


class EventReturn(_ds18.EventReturn):
    def __init__(self, config):
        super().__init__(config)
        self.return_proposal = False
        self.return_route_checks = []
        self.event_returns = {}
        self.event_return_pending_versions = {}

    def edge_veto(self, frame, now, observation, public, anchor, origin_rule):
        check = super().edge_veto(frame, now, observation, public, anchor, origin_rule)
        spec = next(iter(self.protected.values()), None)
        if not self.return_proposal or not spec or public not in spec['member_public']:
            return check
        reasons = [r for r in check['reasons'] if r != 'WAIT_JOINT_GROUP_TRANSACTION']
        context = self.event_context or {}
        if context.get('id') != spec['episode'] or context.get('generation') != spec['generation']:
            reasons.append('EVENT_CONTEXT_CHANGED')
        if context.get('q') == frame:
            reasons.append('FIRST_SPLIT_USES_JOINT_DECISION')
        native = observation['id']
        certificate = self.certificates.get(native, {})
        whole = certificate.get('whole', {})
        if (not whole.get('source_ownership_exclusive') or
                whole.get('source_population_unverified_n', 1)):
            reasons.append('CURRENT_SOURCE_OWNERSHIP_UNKNOWN_OR_SHARED')
        if not self.quality(observation) or observation.get('neighbors'):
            reasons.append('CURRENT_QUALITY_OR_CONTACT_RISK')
        if self.source_versions.get(native) is None:
            reasons.append('CURRENT_SOURCE_VERSION_UNKNOWN')
        check.update(veto=bool(reasons), reasons=reasons,
            reason=reasons[0] if reasons else 'ROUTED_ORIGINAL_EVENT_RETURN_EDGE',
            event_return_routed=not reasons, event=spec['episode'],
            event_generation=spec['generation'], old_anchor=copy.deepcopy(anchor),
            source_version=copy.deepcopy(self.source_versions.get(native)),
            identity_version=copy.deepcopy(self.identity_versions.get(native)))
        self.return_route_checks.append(copy.deepcopy(check))
        return check

    # This method is copied from the frozen DS18 step below. Its sole additional
    # operation is to keep the naturally written clean state of an accepted
    # routed target in the proposal clone. The authoritative view stays frozen.


    def step(self, frame, now, observations, profiles=None):
        profiles = profiles or {}
        self.return_route_checks = []
        spec = next(iter(self.protected.values()), None)
        if spec and spec['episode'] in self.event_returns:
            # The frozen manager recreates its spec before its diagnostic causal
            # view. Apply committed local membership inside the clone as well.
            returned = self.event_returns[spec['episode']]
            remaining = [k for k in returned['member_public'] if str(k) not in returned['returned_members']]
            spec.update(member_public=remaining,
                member_sources=[n for n,k in zip(returned['member_sources'],returned['member_public']) if k in remaining],
                returned_members=copy.deepcopy(returned['returned_members']),
                returned_sources=copy.deepcopy(returned['returned_sources']))
        classes = (dict(self.observation_classes)
                   if self.observation_frame == frame else {})
        event_sources = set()
        if spec:
            event_sources = set(spec['member_sources']) | set(spec['suppressed'])
            for native in spec['suppressed']:
                classes.setdefault(native, 'GROUP_MEASUREMENT')
        anonymous = event_sources | {n for n, cls in classes.items() if cls in ANONYMOUS_CLASSES}
        public = set(spec['member_public']) if spec else set()
        # New pending sources can have their own native bank. It is not a clean
        # identity reference until the S0 transaction selects their mapping.
        public.update(self.alias.get(n, {}).get('target', n) for n in anonymous)
        before_clean = {k: clean_reference(self.bank.get(k, _ds18.EMPTY_CLEAN)) for k in public}
        before_views = {k: copy.deepcopy(self.view_bank[k]) for k in public if k in self.view_bank}
        before_recent = {n: copy.deepcopy(self.recent_core[n]) for n in anonymous if n in self.recent_core}
        if spec:
            key = f"{spec['episode']}:{spec['generation']}"
            registry = self.identity_reference_registry.setdefault(key, dict(
                episode=spec['episode'], generation=spec['generation'],
                references={str(k): copy.deepcopy(before_clean[k]) for k in spec['member_public']},
                views={str(k): copy.deepcopy(before_views.get(k)) for k in spec['member_public']}))
            assert all(registry['references'][str(k)] == before_clean[k]
                       for k in spec['member_public']), 'certified event reference changed'
            assert all(registry['views'][str(k)] == before_views.get(k)
                       for k in spec['member_public']), 'certified event view provenance changed'
        self._active_anonymous = anonymous
        self._step_observations = {o['id']: o for o in observations}
        self._step_profiles = profiles
        self.evidence_checks = []
        self._joint_certified_sources = set()
        self._candidate_bindings = {}
        self._birth_edge_terms = {}
        ids, trace = _ds18._ds16.EventReturn.step(self, frame, now, observations, profiles)
        natural_returns = [e for e in trace.get('events', []) if e.get('kind') == 'reconnect'
            and e.get('accepted') and e.get('edge_veto', {}).get('event_return_routed')]
        returned_targets = {e['canonical_id'] for e in natural_returns}
        trace['ds19_natural_event_returns'] = copy.deepcopy(natural_returns)
        # The original step has advanced real activity, source continuity and
        # automatic transactions. Restore no activity or ownership fields.
        for k in public:
            if k in returned_targets:
                continue  # The original loop already wrote this real clean observation.
            if k not in self.bank:
                continue  # A valid source-bank retirement is not resurrection.
            restore_clean(self.bank[k], before_clean[k])
            self.view_bank.pop(k, None)
            if k in before_views:
                self.view_bank[k] = copy.deepcopy(before_views[k])
        for n in anonymous:
            self.recent_core.pop(n, None)
            if n in before_recent:
                self.recent_core[n] = copy.deepcopy(before_recent[n])
        for observation in observations:
            n = observation['id']
            cls = classes.get(n, 'SOURCE_OBSERVATION')
            if n in anonymous and cls == 'SOURCE_OBSERVATION':
                cls = 'UNRESOLVED_EVENT_OBSERVATION'
            self.source_activity[n] = M._freeze_facts(dict(frame=frame, time=now,
                observation_class=cls,
                identity_measurement_certified=(n not in anonymous and
                    self.bank.get(ids[n], {}).get('anchor', {}).get('frame') == frame),
                received_association_observation=copy.deepcopy(observation),
                received_association_profile=copy.deepcopy(profiles.get(n)),
                source_version=copy.deepcopy(profiles.get(n, {}).get('source_version', self.source_versions.get(n, 'UNKNOWN')))))
        activity = {str(k): {field: copy.deepcopy(self.bank[k].get(field)) for field in _ds18.ACTIVITY_FIELDS}
                    for k in sorted(public) if k in self.bank}
        trace['activity_reference_separation'] = dict(
            protected_clean_fields=list(_ds18.CLEAN_FIELDS), live_activity_fields=list(_ds18.ACTIVITY_FIELDS),
            public_reference_keys=sorted(public), anonymous_native_keys=sorted(anonymous),
            public_activity=activity, missing_sources_not_updated=sorted(anonymous - set(ids)),
            certified_recent_core_frozen=sorted(anonymous),
            anonymous_current_measurement_preserved=sorted(anonymous & set(ids)),
            anonymous_identity_stage_separate=True,
            source_activity={str(n): copy.deepcopy(self.source_activity[n]) for n in sorted(anonymous & set(ids))})
        if spec:
            trace['activity_reference_separation']['immutable_reference_registry'] = copy.deepcopy(registry)
            trace['activity_reference_separation']['reference_status'] = {
                str(k): dict(
                    status=('LIVE_BANK_RETIRED' if k not in self.bank else
                        'NO_CERTIFIED_REFERENCE' if not self.bank[k].get('anchor') else
                        'REFERENCE_EXPIRED' if now - self.bank[k]['clean_time'] > 12 else
                        'UNCHANGED_CERTIFIED_REFERENCE'),
                    actual_bank_anchor=copy.deepcopy(self.bank.get(k, {}).get('anchor')),
                    actual_view_anchors={view: copy.deepcopy(value.get('anchor'))
                                        for view, value in self.view_bank.get(k, {}).items()},
                    actual_observed_alias_owners=[n for n, public_id in ids.items() if public_id == k])
                for k in spec['member_public']}
        if spec:
            spec['outputs'] = {n: ids[n] for n in spec['suppressed'] if n in ids}
            trace['merge_split_group'] = dict(episode=spec['episode'],
                suppressed=sorted(spec['suppressed']), outputs=copy.deepcopy(spec['outputs']),
                preview_only_not_published=True,
                publication_policy='OWN_BRANCH_CAUSAL_EVENT_ALIAS_OR_NATIVE',
                protected_public_banks_preserved=False,
                protected_clean_references_preserved=True,
                protected_identity_reference_stores=['bank.clean_fields', 'view_bank', 'recent_core'],
                source_proposal_lifecycle='ACTUAL_CURRENT_ORIGINAL_Z4Q_NOT_FROZEN',
                visible_source_state={str(n): dict(native_seen=self.native_seen.get(n),
                    native_run=copy.deepcopy(self.native_runs.get(n)),
                    recent_core_anchor=copy.deepcopy(self.recent_core.get(n, {}).get('anchor')))
                    for n in sorted(anonymous & set(ids))},
                depth_history_policy='GROUP_AND_UNASSIGNED_POST_REMAIN_ANONYMOUS')
        trace['association_evidence_checks'] = copy.deepcopy(self.evidence_checks)
        for action in trace['events']:
            if action.get('kind') == 'reconnect' and action.get('accepted'):
                action.setdefault('origin_rule','BIRTH_REFINE' if action.get('phase')=='birth' else 'D1_DELAYED')
                key=(action['origin_rule'],action['native_id'],action['canonical_id'])
                action['association_evidence_bindings'] = copy.deepcopy(self._candidate_bindings[key])
                action['association_evidence_sha256'] = M._digest(self._candidate_bindings[key])
        trace['ds19_natural_event_returns'] = copy.deepcopy(natural_returns)
        return ids, trace


class EventBridge(_ds18.EventBridge):
    def __init__(self, config, local_return=False):
        super().__init__(config)
        self.engine = EventReturn(config)
        self.local_return = bool(local_return)

    @staticmethod
    def _write_sets(view, selected):
        native = set(selected)
        public = set(selected.values())
        # A source bank can be retired only if it is its actual current public
        # bank and no other observed/latent owner claims it.
        for source in native:
            old = view['mapping'][source]
            if (old == source and old not in selected.values() and
                    not any(n not in native and k == old for n, k in view['mapping'].items()) and
                    not any(n not in native and a['target'] == old for n, a in view['engine'].alias.items())):
                public.add(old)
        return native, public

    @staticmethod
    def _outside_equal(baseline, proposal, native, public):
        checks = {}
        checks['mapping'] = {n:k for n,k in baseline['mapping'].items() if n not in native} == {
            n:k for n,k in proposal['mapping'].items() if n not in native}
        for name in ('bank', 'view_bank', 'depth_history_bindings', 'ema_evidence'):
            left, right = getattr(baseline['engine'], name), getattr(proposal['engine'], name)
            checks[name] = {k:v for k,v in left.items() if k not in public} == {
                k:v for k,v in right.items() if k not in public}
        for name in ('alias', 'birth', 'pending', 'native_seen', 'native_runs', 'recent_core',
                     'return_quarantine', 'empty_quarantine', 'first_eligible', 'pending_birth',
                     'source_activity'):
            left, right = getattr(baseline['engine'], name), getattr(proposal['engine'], name)
            checks[name] = {k:v for k,v in left.items() if k not in native} == {
                k:v for k,v in right.items() if k not in native}
        checks['retired'] = baseline['engine'].retired-native == proposal['engine'].retired-native
        checks['immutable_entry_registry'] = (
            baseline['engine'].identity_reference_registry == proposal['engine'].identity_reference_registry)
        return checks

    def preview(self, frame, now, observations, profiles):
        baseline = super().causal_view(frame, now, observations, profiles)
        spec = next(iter(self.engine.protected.values()), None)
        if not self.local_return or not spec or (self.engine.event_context or {}).get('q') == frame:
            return baseline
        trial = copy.deepcopy(self.engine)
        for native, record in trial.event_return_pending_versions.items():
            actual_anchor = trial.bank.get(record['public'], {}).get('anchor')
            if (record['source_version'] != trial.source_versions.get(native) or
                    record['anchor'] != actual_anchor or record['generation'] != spec['generation']):
                trial.pending.pop(native, None)
        trial.return_proposal = True
        ids, trace = trial.step(frame, now, observations, profiles)
        trial.return_proposal = False
        proposal = dict(version=self.version, frame=frame, now=now, observations=observations,
            profiles=profiles, engine=trial, mapping=ids, trace=trace, epochs=copy.deepcopy(baseline['epochs']))
        accepted = [e for e in trace.get('events', []) if e.get('kind') == 'reconnect'
            and e.get('accepted') and e.get('edge_veto', {}).get('event_return_routed')]
        routed_sources = {x['native_id'] for x in trial.return_route_checks if x['event_return_routed']}
        accepted_sources = {e['native_id'] for e in accepted}
        carried = {}
        # Carry only actual unaccepted confirmations, with all other original
        # source/matrix state unchanged. No identity is certified by this step.
        _, candidate_public = self._write_sets(baseline, {
            e['native_id']:e['canonical_id'] for e in accepted}) if accepted else (set(), set())
        pending_comparison = self._outside_equal(baseline, proposal, routed_sources, candidate_public)
        for native in routed_sources-accepted_sources:
            pending = trial.pending.get(native)
            if pending and pending['target'] in spec['member_public']:
                # The only permitted discrepancy at this stage is that pending.
                if all(pending_comparison.values()):
                    baseline['engine'].pending[native] = copy.deepcopy(pending)
                    carried[str(native)] = copy.deepcopy(pending)
                    baseline['engine'].event_return_pending_versions[native] = dict(
                        source_version=copy.deepcopy(trial.source_versions[native]),
                        public=pending['target'], anchor=copy.deepcopy(trial.bank[pending['target']]['anchor']),
                        generation=spec['generation'])
        baseline['event_return_proposal'] = proposal
        baseline['trace']['ds19_event_return_proposals'] = dict(
            checks=copy.deepcopy(trial.return_route_checks), accepted=copy.deepcopy(accepted),
            carried_original_confirmations=carried, identity_writes_before_stage=False,
            evaluated_on_private_clone=True, original_matrix_and_windows_unchanged=True)
        return baseline

    def stage_event_return(self, view, episode):
        if not self.local_return:
            return None, 'local_return_disabled'
        if view['version'] != self.version:
            return None, 'stale_snapshot'
        if not episode or episode['q'] == view['frame']:
            return None, 'first_split_uses_joint_decision'
        spec = view['engine'].protected.get(episode['id'])
        if not spec or spec['generation'] != episode['generation']:
            return None, 'stale_event_generation'
        proposal = view.get('event_return_proposal')
        if not proposal:
            return None, 'no_original_event_return_proposal'
        accepted = proposal['trace'].get('ds19_natural_event_returns', [])
        if not accepted:
            return None, 'no_accepted_original_event_return'
        selected = {e['native_id']:e['canonical_id'] for e in accepted}
        if len(selected) != len(accepted) or len(set(selected.values())) != len(selected):
            return None, 'nonunique_original_event_return'
        if not set(selected.values()).issubset(spec['member_public']):
            return None, 'target_not_unresolved_event_member'
        observed = {o['id']:o for o in view['observations']}
        entry = view['engine'].identity_reference_registry.get(f"{episode['id']}:{episode['generation']}")
        if entry is None:
            return None, 'missing_immutable_entry_reference'
        for event in accepted:
            native, public = event['native_id'], event['canonical_id']
            if native not in observed or native in view['engine']._active_anonymous:
                return None, 'anonymous_or_missing_query'
            gate = event['edge_veto']
            if (gate.get('source_version') != view['engine'].source_versions.get(native) or
                    gate.get('identity_version') != view['engine'].identity_versions.get(native)):
                return None, 'source_or_identity_version_changed'
            original = next((e for e in proposal['trace'].get('events', [])
                if e.get('kind') == 'reconnect' and e.get('accepted') and
                e.get('native_id') == native and e.get('canonical_id') == public), None)
            if original != event:
                return None, 'original_proposal_facts_changed'
            roles = ('D1_WHOLE',) if event['origin_rule'] == 'D1_DELAYED' else ('BIRTH_CORE','BIRTH_WHOLE')
            for role in roles:
                packet = observed[native] if role == 'D1_WHOLE' else view['profiles'].get(native, {})
                stats = packet.get('depth', {}) if role == 'D1_WHOLE' else packet.get(
                    'core' if role == 'BIRTH_CORE' else 'whole', {})
                if view['engine'].current_binding(native, role, stats, packet) is None:
                    return None, 'current_measurement_binding_changed_or_unknown'
            h = view['engine'].bank.get(public)
            old = episode['bank_snapshot'].get(public)
            if (not h or not old or clean_reference(h) != clean_reference(old) or
                    entry['references'].get(str(public)) != clean_reference(old) or
                    h.get('anchor') != event.get('old_anchor')):
                return None, 'exact_old_anchor_or_reference_changed'
            if entry['views'].get(str(public)) != view['engine'].view_bank.get(public):
                return None, 'exact_old_view_reference_changed'
            if any(n not in selected and k == public for n,k in view['mapping'].items()):
                return None, 'public_target_occupied'
            if any(n not in selected and a['target'] == public for n,a in view['engine'].alias.items()):
                return None, 'public_target_alias_claimed'
            if (not proposal['engine'].alias.get(native) or
                    proposal['engine'].alias[native]['target'] != public or
                    proposal['mapping'].get(native) != public):
                return None, 'original_proposal_not_durable'
        wanted = dict(view['mapping']); wanted.update(selected)
        if wanted != proposal['mapping'] or len(set(wanted.values())) != len(wanted):
            return None, 'proposal_changes_outside_event_return_or_occupied_target'
        native, public = self._write_sets(view, selected)
        outside = self._outside_equal(view, proposal, native, public)
        if not all(outside.values()):
            return None, 'outside_event_state_changed'
        trial = copy.deepcopy(view['engine'])
        for name in ('bank', 'view_bank', 'depth_history_bindings', 'ema_evidence'):
            dst, src = getattr(trial, name), getattr(proposal['engine'], name)
            for key in public:
                dst.pop(key, None)
                if key in src:
                    dst[key] = copy.deepcopy(src[key])
        for name in ('alias', 'birth', 'pending', 'native_seen', 'native_runs', 'recent_core',
                     'return_quarantine', 'empty_quarantine', 'first_eligible', 'pending_birth', 'source_activity'):
            dst, src = getattr(trial, name), getattr(proposal['engine'], name)
            for key in native:
                dst.pop(key, None)
                if key in src:
                    dst[key] = copy.deepcopy(src[key])
        trial.retired.difference_update(native)
        trial.retired.update(proposal['engine'].retired & native)
        trial._step_observations = copy.deepcopy(proposal['engine']._step_observations)
        trial._step_profiles = copy.deepcopy(proposal['engine']._step_profiles)
        trial._candidate_bindings = copy.deepcopy(proposal['engine']._candidate_bindings)
        trial._joint_certified_sources = set(native)
        returned_members = copy.deepcopy(_member_records(episode))
        returned_sources = copy.deepcopy(episode.get('returned_sources', {}))
        for event in accepted:
            n,k = event['native_id'],event['canonical_id']
            record = dict(native=n, public=k, frame=view['frame'], origin_rule=event['origin_rule'],
                original_candidate=copy.deepcopy(event), source_version=copy.deepcopy(trial.source_versions[n]),
                precommit_identity_version=copy.deepcopy(trial.identity_versions[n]),
                old_anchor=copy.deepcopy(event['old_anchor']),
                original_first_publication=copy.deepcopy(trial.source_first_publication.get(n)),
                event=episode['id'], generation=episode['generation'])
            returned_members[str(k)] = record
            returned_sources[str(n)] = record
            trial.pending_birth.pop(n, None)
            trial.event_return_pending_versions.pop(n, None)
            trial.alias[n].update(source='DS19_EVENT_LOCAL_RETURN', transaction_version=self.version+1)
        protected = trial.protected[episode['id']]
        remaining = [k for k in episode['public_ids'] if str(k) not in returned_members]
        protected['member_public'] = remaining
        protected['member_sources'] = [n for n,k in zip(episode['member_sources'],episode['public_ids']) if k in remaining]
        protected['returned_members'] = copy.deepcopy(returned_members)
        protected['returned_sources'] = copy.deepcopy(returned_sources)
        trial.event_returns[episode['id']] = dict(member_public=list(episode['public_ids']),
            member_sources=list(episode['member_sources']), returned_members=copy.deepcopy(returned_members),
            returned_sources=copy.deepcopy(returned_sources), generation=episode['generation'])
        protected['outputs'] = {n:wanted[n] for n in protected['suppressed'] if n in wanted}
        trace = copy.deepcopy(view['trace'])
        trace['events'] = [e for e in trace.get('events', []) if not (
            e.get('kind') == 'reconnect' and e.get('native_id') in native)] + copy.deepcopy(accepted)
        record = dict(status='EVENT_LOCAL_RETURN_STAGED', event=episode['id'],
            generation=episode['generation'], frame=view['frame'], q=episode['q'],
            restored_sources=sorted(native), selected=selected, remaining_public=remaining,
            old_publications_unchanged=True, outside_checks=outside,
            native_write_set=sorted(native), public_write_set=sorted(public),
            immutable_entry_reference_preserved=True, original_confirmation_and_windows=True,
            original_proposal_trace_events=copy.deepcopy(accepted),
            first_publication={str(n):copy.deepcopy(trial.source_first_publication.get(n)) for n in native})
        trace['ds19_event_local_return'] = copy.deepcopy(record)
        separation = trace.get('activity_reference_separation', {})
        separation['event_local_return_supersedes_frozen_target_status'] = sorted(selected.values())
        for source, target in selected.items():
            separation.setdefault('reference_status', {})[str(target)] = dict(
                status='LIVE_REFERENCE_UPDATED_BY_ATOMIC_EVENT_RETURN',
                actual_bank_anchor=copy.deepcopy(trial.bank[target].get('anchor')),
                actual_view_anchors={role:copy.deepcopy(value['anchor'])
                    for role,value in trial.view_bank.get(target, {}).items()},
                actual_observed_alias_owners=[source], immutable_entry_reference_unchanged=True)
        return dict(engine=trial, mapping=wanted, trace=trace, changes=selected,
            anchors={n:copy.deepcopy(view['engine'].bank[k]['anchor']) for n,k in selected.items()},
            return_record=record,
            episode_update=dict(returned_members=returned_members, returned_sources=returned_sources)), None

    def _stage_episode(self, view, episode):
        if not _member_records(episode):
            return super()._stage_episode(view, episode)
        if view['version'] != self.version or episode['q'] != view['frame']:
            return None, 'stale_episode'
        spec = view['engine'].protected.get(episode['id'])
        if not spec or spec['generation'] != episode['generation']:
            return None, 'stale_generation'
        entry = view['engine'].identity_reference_registry.get(f"{episode['id']}:{episode['generation']}")
        if entry is None:
            return None, 'missing_certified_reference_registry'
        for public in episode['public_ids']:
            frozen = episode['bank_snapshot'].get(public)
            current = view['engine'].bank.get(public)
            if not frozen or not current or entry['references'].get(str(public)) != clean_reference(frozen):
                return None, 'immutable_entry_reference_changed'
            returned = _member_records(episode).get(str(public))
            if returned:
                native = returned['native']
                if (view['mapping'].get(native) != public or
                        view['engine'].source_versions.get(native) != returned['source_version'] or
                        view['engine'].alias.get(native, {}).get('target') != public):
                    return None, 'committed_event_return_source_or_ownership_changed'
            elif (clean_reference(current) != clean_reference(frozen) or
                  entry['views'].get(str(public)) != view['engine'].view_bank.get(public)):
                return None, 'unresolved_reference_changed'
        adapted = copy.deepcopy(episode)
        adapted['bank_snapshot'] = {k:copy.deepcopy(view['engine'].bank[k]) for k in episode['public_ids']}
        return adapted, None

    def stage_group_restore(self, view, episode, selected):
        for public, returned in _member_records(episode).items():
            if selected.get(returned['native']) != int(public):
                return None, 'committed_event_return_bijection_conflict'
        return super().stage_group_restore(view, episode, selected)

    def commit_once(self, view, transaction=None):
        ids, trace = super().commit_once(view, transaction)
        if transaction is not None and transaction.get('return_record'):
            for native in transaction['return_record']['restored_sources']:
                self.provenance[native]['source'] = 'DS19_EVENT_LOCAL_RETURN'
            trace['ds19_event_local_return'].update(status='EVENT_LOCAL_RETURN_COMMITTED',
                published_mapping={str(n):ids[n] for n in transaction['return_record']['restored_sources']},
                epochs={str(n):self.epochs[n] for n in transaction['return_record']['restored_sources']},
                actual_first_publication={str(n):copy.deepcopy(self.engine.source_first_publication[n])
                    for n in transaction['return_record']['restored_sources']},
                bridge_version=self.version, decisions_before_publication=True)
        return ids, trace


class EventManager(_ds18.EventManager):
    def _clip_protection(self, episode):
        spec = self.bridge.engine.protected.get(episode['id'])
        if not spec:
            return
        records = _member_records(episode)
        remaining = [k for k in episode['public_ids'] if str(k) not in records]
        spec.update(member_public=remaining,
            member_sources=[n for n,k in zip(episode['member_sources'],episode['public_ids']) if k in remaining],
            returned_members=copy.deepcopy(records),
            returned_sources=copy.deepcopy(episode.get('returned_sources', {})))
        # Entry references retain both identities even after a live reference
        # is legitimately advanced by a return. Anonymous pixels remain risk.
        key = f"{episode['id']}:{episode['generation']}"
        self.bridge.engine.identity_reference_registry.setdefault(key, dict(
            episode=episode['id'], generation=episode['generation'],
            references={str(k):clean_reference(v) for k,v in episode['bank_snapshot'].items()},
            views={str(k):copy.deepcopy(self.bridge.engine.view_bank.get(k)) for k in episode['public_ids']}))

    def before(self, row, profiles):
        result = super().before(row, profiles)
        if self.active and self.bridge.local_return:
            self._clip_protection(self.active)
        return result

    def record_event_return(self, frame, transaction):
        if transaction is None or not transaction.get('return_record'):
            return
        episode = self.active
        record = transaction['return_record']
        assert episode and record['event'] == episode['id'] and frame == record['frame']
        assert self.bridge.version == transaction['engine'].alias[record['restored_sources'][0]]['transaction_version']
        for native in record['restored_sources']:
            assert self.bridge.previous[native] == record['selected'][native]
        episode.update(copy.deepcopy(transaction['episode_update']))
        episode.setdefault('local_returns', []).append(copy.deepcopy(record))
        self._clip_protection(episode)

    def _release(self, episode, frame, status, current):
        result = super()._release(episode, frame, status, current)
        # Timeout releases unresolved evidence only. It never copies a baseline
        # engine and never retires a previously committed alias/reference.
        returned = {v['native'] for v in _member_records(episode).values()}
        self.pending_clear.difference_update(returned)
        episode['returned_state_preserved_at_release'] = {
            str(n):dict(public=self.bridge.previous.get(n), alias=copy.deepcopy(self.bridge.engine.alias.get(n)))
            for n in returned}
        return result
