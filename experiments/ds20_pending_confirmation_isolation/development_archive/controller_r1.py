"""Keep protected-edge confirmations separate from ordinary Z4Q pending.

Both views still run the frozen complete matrix and natural confirmation loop.
Only the private event proposal receives its own prior protected confirmation.
The ordinary causal engine is adopted unchanged unless the existing local
transaction validates and commits an actual protected-target return.
"""
import copy
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
_spec = importlib.util.spec_from_file_location('ds20_frozen_ds19_controller',
    ROOT/'experiments/ds19_protected_event_return/controller.py')
_ds19 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_ds19)
M = _ds19.M
Bridge = _ds19.Bridge
ANONYMOUS_CLASSES = _ds19.ANONYMOUS_CLASSES
clean_reference, restore_clean = _ds19.clean_reference, _ds19.restore_clean


class EventReturn(_ds19.EventReturn):
    def __init__(self, config):
        super().__init__(config)
        self.event_return_confirmations = {}


class EventBridge(_ds19.EventBridge):
    def __init__(self, config, local_return=False):
        super().__init__(config, local_return=local_return)
        self.engine = EventReturn(config)

    @staticmethod
    def _confirmation_identity(check, spec):
        return dict(event=spec['episode'], generation=spec['generation'],
            native=check['native_id'], public=check['public_id'],
            origin_rule=check['origin_rule'],
            source_version=copy.deepcopy(check['source_version']),
            identity_version=copy.deepcopy(check['identity_version']),
            anchor=copy.deepcopy(check['old_anchor']))

    @staticmethod
    def _records(store):
        return [dict(key=key, **copy.deepcopy(record))
                for key, record in sorted(store.items())]

    @staticmethod
    def _invalid_reason(record, view, spec):
        engine = view['engine']
        identity, pending = record['identity'], record['pending']
        native, public = identity['native'], identity['public']
        context = engine.event_context or {}
        if (not spec or context.get('id') != identity['event'] or
                spec['episode'] != identity['event'] or
                context.get('generation') != identity['generation'] or
                spec['generation'] != identity['generation']):
            return 'EVENT_RELEASED_OR_GENERATION_CHANGED'
        if context.get('q') == view['frame']:
            return 'FIRST_SPLIT_USES_JOINT_DECISION'
        if public not in spec['member_public']:
            return 'TARGET_NO_LONGER_UNRESOLVED_MEMBER'
        if identity['source_version'] != engine.source_versions.get(native):
            return 'SOURCE_GENERATION_CHANGED'
        if identity['identity_version'] != engine.identity_versions.get(native):
            return 'IDENTITY_VERSION_CHANGED'
        if identity['anchor'] != engine.bank.get(public, {}).get('anchor'):
            return 'EXACT_OLD_ANCHOR_CHANGED'
        if native in engine.alias or view['mapping'].get(native, native) != native:
            return 'ORDINARY_SOURCE_ALREADY_RECONNECTED'
        if native in engine.retired:
            return 'SOURCE_RETIRED_BY_ORDINARY_LIFECYCLE'
        if any(n != native and k == public for n, k in view['mapping'].items()):
            return 'PUBLIC_TARGET_OCCUPIED'
        if any(n != native and a['target'] == public for n, a in engine.alias.items()):
            return 'PUBLIC_TARGET_ALIAS_CLAIMED'
        if view['now'] - pending['time'] > .2 or view['now'] - pending['start_time'] > .5:
            return 'ORIGINAL_CONFIRMATION_WINDOW_EXPIRED'
        return None

    def preview(self, frame, now, observations, profiles):
        # This is exactly DS19 local_return=False: no event proposal may write
        # or reset its ordinary pending[native], even for the same source.
        baseline = super().causal_view(frame, now, observations, profiles)
        ordinary_before = copy.deepcopy(self.engine.pending)
        ordinary_after = copy.deepcopy(baseline['engine'].pending)
        spec = next(iter(self.engine.protected.values()), None)
        before = self.engine.event_return_confirmations
        kept, invalidated = {}, []
        for key, record in before.items():
            reason = self._invalid_reason(record, baseline, spec)
            if reason:
                invalidated.append(dict(key=key, identity=copy.deepcopy(record['identity']), reason=reason))
            else:
                kept[key] = copy.deepcopy(record)
        baseline['engine'].event_return_confirmations = kept
        ordinary_accepted = sorted({e['native_id'] for e in baseline['trace'].get('events', [])
            if e.get('kind') == 'reconnect' and e.get('accepted')})
        audit = dict(ordinary_pending_before=ordinary_before,
            ordinary_pending_after=ordinary_after,
            ordinary_pending_after_proposal=copy.deepcopy(ordinary_after),
            event_confirmations_before=self._records(before),
            event_confirmations_after=self._records(kept), invalidated=invalidated,
            ordinary_accepted_sources=ordinary_accepted,
            independent_confirmation_store=True,
            ordinary_pending_not_overwritten=True,
            original_matrix_confirmation_and_windows_unchanged=True,
            proposal_loaded_confirmations=[], carried_confirmations=[],
            evaluated_on_private_clone=True)
        baseline['trace']['ds20_pending_isolation'] = audit
        if (not self.local_return or not spec or
                (self.engine.event_context or {}).get('q') == frame):
            return baseline

        trial = copy.deepcopy(self.engine)
        # The old DS19 store is never populated by DS20. The separate store is
        # bound to event, source/identity versions, exact anchor and target.
        trial.event_return_pending_versions.clear()
        for key, record in kept.items():
            native = record['identity']['native']
            trial.pending[native] = copy.deepcopy(record['pending'])
            audit['proposal_loaded_confirmations'].append(key)
        trial.return_proposal = True
        ids, trace = trial.step(frame, now, observations, profiles)
        trial.return_proposal = False
        proposal = dict(version=self.version, frame=frame, now=now,
            observations=observations, profiles=profiles, engine=trial,
            mapping=ids, trace=trace, epochs=copy.deepcopy(baseline['epochs']))
        accepted = [e for e in trace.get('events', []) if e.get('kind') == 'reconnect'
            and e.get('accepted') and e.get('edge_veto', {}).get('event_return_routed')]
        # A current ordinary reconnect owns the source first. Its actual bank,
        # alias and confirmation transaction cannot be replaced by this route.
        blocked = {e['native_id'] for e in accepted} & set(ordinary_accepted)
        if blocked:
            invalidated.extend(dict(native=n, reason='ORDINARY_RECONNECT_ACCEPTED_THIS_FRAME')
                               for n in sorted(blocked))
            accepted = [e for e in accepted if e['native_id'] not in blocked]
            proposal['trace']['ds19_natural_event_returns'] = copy.deepcopy(accepted)
        routed = {c['native_id'] for c in trial.return_route_checks if c['event_return_routed']}
        accepted_sources = {e['native_id'] for e in accepted}
        _, public = self._write_sets(baseline, {e['native_id']:e['canonical_id']
            for e in accepted}) if accepted else (set(), set())
        outside = self._outside_equal(baseline, proposal, routed, public)
        next_store = {}
        carried = {}
        for check in trial.return_route_checks:
            native, target = check['native_id'], check['public_id']
            pending = trial.pending.get(native)
            if (not check['event_return_routed'] or check['origin_rule'] != 'D1_DELAYED'
                    or native in accepted_sources or native in ordinary_accepted
                    or native in baseline['engine'].alias
                    or not pending or pending['target'] != target or not all(outside.values())):
                continue
            identity = self._confirmation_identity(check, spec)
            key = M._digest(identity)
            record = dict(identity=identity, pending=copy.deepcopy(pending))
            if self._invalid_reason(record, baseline, spec) is not None:
                continue
            next_store[key] = record
            carried[str(native)] = copy.deepcopy(pending)
            audit['carried_confirmations'].append(dict(key=key, **copy.deepcopy(record)))
        for key, record in kept.items():
            if key not in next_store and record['identity']['native'] not in accepted_sources:
                invalidated.append(dict(key=key, identity=copy.deepcopy(record['identity']),
                    reason=('ORDINARY_RECONNECT_ACCEPTED_THIS_FRAME'
                        if record['identity']['native'] in ordinary_accepted else
                        'ORIGINAL_MATRIX_NO_LONGER_CONTINUES_PROTECTED_TARGET')))
        baseline['engine'].event_return_confirmations = next_store
        audit['event_confirmations_after'] = self._records(next_store)
        audit['outside_confirmation_checks'] = copy.deepcopy(outside)
        assert baseline['engine'].pending == ordinary_after, 'event proposal polluted ordinary pending'
        audit['ordinary_pending_after_proposal'] = copy.deepcopy(baseline['engine'].pending)
        baseline['event_return_proposal'] = proposal
        baseline['trace']['ds19_event_return_proposals'] = dict(
            checks=copy.deepcopy(trial.return_route_checks), accepted=copy.deepcopy(accepted),
            carried_original_confirmations=carried, identity_writes_before_stage=False,
            evaluated_on_private_clone=True, original_matrix_and_windows_unchanged=True,
            confirmations_carried_to='SEPARATE_EVENT_TARGET_VERSION_ANCHOR_STORE')
        return baseline

    def stage_event_return(self, view, episode):
        proposal = view.get('event_return_proposal')
        if proposal:
            accepted = proposal['trace'].get('ds19_natural_event_returns', [])
            ordinary = set(view['trace'].get('ds20_pending_isolation', {}).get('ordinary_accepted_sources', []))
            if any(e['native_id'] in ordinary for e in accepted):
                return None, 'ordinary_reconnect_accepted_this_frame'
        transaction, error = super().stage_event_return(view, episode)
        if transaction is not None:
            engine = transaction['engine']
            restored = set(transaction['return_record']['restored_sources'])
            engine.event_return_confirmations = {key:record for key, record in
                engine.event_return_confirmations.items() if record['identity']['native'] not in restored}
            transaction['trace']['ds20_pending_isolation']['event_confirmations_after'] = self._records(
                engine.event_return_confirmations)
            transaction['trace']['ds20_pending_isolation']['confirmation_consumed_by_commit'] = sorted(restored)
            transaction['return_record']['confirmation_policy'] = 'SEPARATE_EVENT_TARGET_VERSION_ANCHOR_STORE'
            transaction['trace']['ds19_event_local_return']['confirmation_policy'] = (
                transaction['return_record']['confirmation_policy'])
        return transaction, error


EventManager = _ds19.EventManager
