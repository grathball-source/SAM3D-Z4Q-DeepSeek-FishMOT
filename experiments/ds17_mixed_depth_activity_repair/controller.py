"""Original Z4Q activity remains live; event identity measurements stay frozen.

The bank is the legacy read interface. Only its clean fields are references;
last_seen/last_frame/partners/contact_time are mutable observation activity.
Native source activity records are anonymous when the event is unresolved.
"""
import copy
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
_spec = importlib.util.spec_from_file_location(
    'ds17_reused_frozen_ds16_controller',
    ROOT / 'experiments/ds16_relative_depth_order/controller.py')
_ds16 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_ds16)
OriginalReturn = _ds16.OriginalReturn
Bridge = _ds16.Bridge
FrozenEventBridge = _ds16.EventBridge
FrozenEventManager = _ds16.EventManager

CLEAN_FIELDS = ('clean_count', 'clean_time', 'clean_box', 'motion', 'areas',
                'anchor', 'depth_history', 'ema')
ACTIVITY_FIELDS = ('last_seen', 'last_frame', 'partners', 'contact_time')
ANONYMOUS_CLASSES = {'GROUP_MEASUREMENT', 'POST_UNASSIGNED', 'ANONYMOUS_RESIDUAL',
                     'UNRESOLVED_EVENT_OBSERVATION'}
EMPTY_CLEAN = dict(clean_count=0, clean_time=None, motion=[], areas=[],
                   depth_history=[], ema=None)


def clean_reference(bank):
    return {k: copy.deepcopy(bank[k]) for k in CLEAN_FIELDS if k in bank}


def restore_clean(bank, reference):
    for key in CLEAN_FIELDS:
        bank.pop(key, None)
    bank.update(copy.deepcopy(reference))


class EventReturn(_ds16.EventReturn):
    def __init__(self, config):
        super().__init__(config)
        self.source_activity = {}  # Native keys: real observed sources, not identities.
        self.identity_reference_registry = {}  # Event/generation -> public clean references.
        self.observation_frame = None
        self.observation_classes = {}

    def step(self, frame, now, observations, profiles=None):
        profiles = profiles or {}
        spec = next(iter(self.protected.values()), None)
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
        before_clean = {k: clean_reference(self.bank.get(k, EMPTY_CLEAN)) for k in public}
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
        association_observations = copy.deepcopy(observations)
        association_profiles = copy.deepcopy(profiles)
        invalid = dict(n=0, valid_fraction=0., median=None, mad=None,
                       association_status='ANONYMOUS_EVENT_NOT_INDIVIDUAL_DEPTH')
        for observation in association_observations:
            n = observation['id']
            if n not in anonymous:
                continue
            # Keep the source/mask/geometry in the original lifecycle. A current
            # group depth cannot certify an individual reservation or birth.
            observation['depth'] = copy.deepcopy(invalid)
            if n in association_profiles:
                for view in ('whole', 'core'):
                    association_profiles[n][view] = copy.deepcopy(invalid)
        ids, trace = super().step(frame, now, association_observations, association_profiles)
        # The original step has advanced real activity, source continuity and
        # automatic transactions. Restore no activity or ownership fields.
        for k in public:
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
            self.source_activity[n] = dict(frame=frame, time=now,
                observation_class=cls,
                identity_measurement_certified=(n not in anonymous and
                    self.bank.get(ids[n], {}).get('anchor', {}).get('frame') == frame),
                received_association_observation=copy.deepcopy(observation),
                received_association_profile=copy.deepcopy(profiles.get(n)),
                source_version=copy.deepcopy(profiles.get(n, {}).get('source_version', 'UNKNOWN')))
        activity = {str(k): {field: copy.deepcopy(self.bank[k].get(field)) for field in ACTIVITY_FIELDS}
                    for k in sorted(public) if k in self.bank}
        trace['activity_reference_separation'] = dict(
            protected_clean_fields=list(CLEAN_FIELDS), live_activity_fields=list(ACTIVITY_FIELDS),
            public_reference_keys=sorted(public), anonymous_native_keys=sorted(anonymous),
            public_activity=activity, missing_sources_not_updated=sorted(anonymous - set(ids)),
            certified_recent_core_frozen=sorted(anonymous),
            anonymous_current_depth_blocked=sorted(anonymous & set(ids)),
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
        return ids, trace


class EventBridge(_ds16.EventBridge):
    def __init__(self, config):
        super().__init__(config)
        self.engine = EventReturn(config)

    def causal_view(self, frame, now, observations, profiles):
        assert len(self.engine.protected) <= 1
        trial = copy.deepcopy(self.engine)
        ids, trace = trial.step(frame, now, observations, profiles)
        assert set(ids) == {o['id'] for o in observations}
        assert len(ids) == len(set(ids.values()))
        return dict(version=self.version, frame=frame, now=now, observations=observations,
            profiles=profiles, engine=trial, mapping=ids, trace=trace,
            epochs={n: self.epochs.get(n, 0) + (n not in self.previous) for n in ids})

    preview = causal_view

    def _stage_episode(self, view, episode):
        # The event snapshot is immutable. Activity changing is expected and is
        # not a reference failure. The old atomic stage sees a validated copy.
        if view['version'] != self.version or episode['id'] not in view['engine'].protected:
            return None, 'stale_episode'
        if episode['generation'] != view['engine'].protected[episode['id']]['generation']:
            return None, 'stale_generation'
        if view['frame'] != episode['q']:
            return None, 'protected_reference_changed'
        key = f"{episode['id']}:{episode['generation']}"
        registry = view['engine'].identity_reference_registry.get(key)
        if registry is None:
            return None, 'missing_certified_reference_registry'
        for public in episode['public_ids']:
            current = view['engine'].bank.get(public)
            frozen = episode['bank_snapshot'].get(public)
            if current is None or frozen is None or clean_reference(current) != clean_reference(frozen):
                return None, 'protected_reference_changed'
            if (registry['references'].get(str(public)) != clean_reference(frozen) or
                    registry['views'].get(str(public)) != view['engine'].view_bank.get(public)):
                return None, 'protected_view_provenance_changed'
        adapted = copy.deepcopy(episode)
        adapted['bank_snapshot'] = {k: copy.deepcopy(view['engine'].bank[k]) for k in episode['public_ids']}
        return adapted, None

    def stage_group_restore(self, view, episode, selected):
        adapted, error = self._stage_episode(view, episode)
        if adapted is None:
            return None, error
        transaction, error = super().stage_group_restore(view, adapted, selected)
        if transaction is not None:
            transaction['trace'] = copy.deepcopy(transaction['trace'])
            transaction['trace']['group_reference_guard'] = dict(
                scope='EXPLICIT_CLEAN_REFERENCE_FIELDS', fields=list(CLEAN_FIELDS),
                original_episode_snapshot_unchanged=True, activity_changes_allowed=True)
        return transaction, error

    def stage_group_unresolved(self, view, episode, temporary):
        adapted, error = self._stage_episode(view, episode)
        if adapted is None:
            return None, error
        return super().stage_group_unresolved(view, adapted, temporary)

    def local_fallback(self, view, episode):
        assert view['version'] == self.version and view['frame'] == episode['q']
        assert episode['id'] in view['engine'].protected
        # This is this branch's complete actual causal preview. Release only
        # the event protection; no second step can invent a different decision.
        trial = copy.deepcopy(view['engine'])
        trial.protected.pop(episode['id'])
        trace = copy.deepcopy(view['trace'])
        detail = dict(episode=episode['id'], status='LOCAL_FALLBACK_COMMITTED',
            candidate_source='OWN_BRANCH_CURRENT_CAUSAL_PREVIEW', copies_other_branch=False,
            outside_mapping_and_ownership_equal=True, event_protection_released=True,
            unassigned_q_not_certified_as_pre=True, guessed_permutation_published=False)
        trace['merge_split_local_fallback'] = detail
        return dict(engine=trial, mapping=dict(view['mapping']), trace=trace, changes={}, anchors={}), detail


class EventManager(_ds16.EventManager):
    def before(self, row, profiles):
        result = super().before(row, profiles)
        self.bridge.engine.observation_frame = row['frame']
        self.bridge.engine.observation_classes = copy.deepcopy(self.frame_class)
        return result
