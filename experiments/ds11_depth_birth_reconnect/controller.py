"""Keep lawful own-branch identities until an event mapping is admitted.

The old manager still collects protected pre/group/post evidence. Its temporary
numeric permutation is never a publication baseline. The current native-return
lifecycle, including previously committed event aliases, supplies that baseline.
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for path in (ROOT/'experiments/ne1_native_first_event_association',
             ROOT/'experiments/s0p_identity_publication',
             ROOT/'experiments/ms1_s0_development_8400',
             ROOT/'online/closed_loop_2888/z4q_source',
             Path('E:/CAU/D-MOT/tools/jev_z4q_scene_v1_20260922/deps')):
    if str(path) not in sys.path:
        sys.path.append(str(path))

from ne_controller import NativeFirstGroupBridgeP
from merge_split_manager import MergeSplitManager


# Same protected write sets as NativeFirstProtectedReturn; bank keys are public,
# while the other stores use native source keys, even when numbers coincide.
PROTECTED_STORES = ('bank', 'view_bank', 'alias', 'birth', 'pending', 'native_seen',
                    'native_runs', 'recent_core', 'return_quarantine',
                    'empty_quarantine', 'first_eligible')


class DepthNativeBridge(NativeFirstGroupBridgeP):
    def stage_birth_reconnect(self, view, changes, candidates_by_source):
        """A birth transaction uses only this branch's real past bank."""
        if self.engine.protected or view['engine'].protected:
            return None, 'active_group_reserved'
        if len(changes)>2:
            return None, 'existing_transaction_capacity_exceeded'
        for native, public in changes.items():
            candidate=candidates_by_source.get(native)
            if (not candidate or not candidate['eligible'] or
                    candidate['public']!=public or native in self.previous):
                return None, 'birth_candidate_not_eligible'
            if any(alias['target']==public for alias in self.engine.alias.values()):
                return None, 'target_alias_claimed'
            actual=self.engine.bank.get(public,{}).get('anchor')
            if not actual or actual!=candidate['anchor'] or actual['frame']>=view['frame']:
                return None, 'past_bank_anchor_changed'
        transaction,error=self.stage(view,changes)
        if transaction is not None:
            transaction['birth_reconnect']=True
            transaction['trace']['ds11_birth_reconnect']=dict(
                changes=copy.deepcopy(changes),decided_before_first_publication=True,
                transaction_version=self.version+1,old_automatic_rules_enabled=False)
        return transaction,error

    def causal_view(self, frame, now, observations, profiles):
        """One current step of this branch's own pre-frame engine, on a clone."""
        assert len(self.engine.protected) <= 1, 'overlapping groups are out of scope'
        trial = copy.deepcopy(self.engine)
        trial.protected.clear()
        ids, trace = trial.step(frame, now, observations, profiles)
        assert set(ids) == {o['id'] for o in observations}
        assert len(ids) == len(set(ids.values()))
        return dict(version=self.version, frame=frame, now=now,
                    observations=observations, profiles=profiles, engine=trial,
                    mapping=ids, trace=trace,
                    epochs={n:self.epochs.get(n, 0)+(n not in self.previous) for n in ids})

    def preview(self, frame, now, observations, profiles):
        view = self.causal_view(frame, now, observations, profiles)
        if not self.engine.protected:
            return view
        episode, original = next(iter(self.engine.protected.items()))
        spec = copy.deepcopy(original)
        public = set(spec['member_public'])
        native = set(spec['suppressed']) | set(spec['member_sources'])
        trial = view['engine']
        # Run the complete legal lifecycle before restoring this event's frozen
        # stores. Removing aliases before an outside native-return check changes
        # occupation semantics; suppressing outside observations loses updates.
        for name in PROTECTED_STORES:
            keys = public if name in ('bank', 'view_bank') else native
            current, before = getattr(trial, name), getattr(self.engine, name)
            for key in keys:
                current.pop(key, None)
                if key in before:
                    current[key] = copy.deepcopy(before[key])
        trial.retired.difference_update(native)
        trial.retired.update(self.engine.retired & native)
        spec['outputs'] = {n:view['mapping'][n] for n in spec['suppressed']
                           if n in view['mapping']}
        trial.protected[episode] = spec
        view['trace']['merge_split_group'] = dict(
            episode=episode, suppressed=sorted(spec['suppressed']),
            outputs=copy.deepcopy(spec['outputs']), preview_only_not_published=True,
            publication_policy='OWN_BRANCH_CAUSAL_EVENT_ALIAS_OR_NATIVE',
            protected_public_banks_preserved=True)
        return view

    def local_fallback(self, view, episode):
        assert view['version'] == self.version and view['frame'] == episode['q']
        assert episode['id'] in self.engine.protected
        candidate = self.causal_view(view['frame'], view['now'],
                                     view['observations'], view['profiles'])
        # The lawful q preview and release have the same published IDs. Release
        # adopts the full *own-branch* causal state, including all outside aliases.
        assert candidate['mapping'] == view['mapping'], 'publication baseline changed'
        native = set(episode['member_sources']) | set(episode['post_roles'])
        native.add(episode['group_source'])
        observed = set(candidate['mapping'])
        outside = observed-native
        detail = dict(episode=episode['id'], status='LOCAL_FALLBACK_COMMITTED',
            candidate_source='OWN_BRANCH_PRE_FRAME_ENGINE',
            event_native_write_set=sorted(native & observed),
            outside_mapping_and_ownership_equal=all(
                candidate['mapping'][n] == view['mapping'][n] for n in outside),
            adopts_complete_own_branch_causal_engine=True,
            copies_other_branch=False, guessed_permutation_published=False)
        trace = copy.deepcopy(candidate['trace'])
        trace['merge_split_local_fallback'] = detail
        return dict(engine=candidate['engine'], mapping=candidate['mapping'],
                    trace=trace, changes={}, anchors={}), detail

    def commit_once(self, view, transaction=None):
        before = dict(self.previous)
        ids, original = super().commit_once(view, transaction)
        if transaction is not None:
            for n in transaction['changes']:
                self.provenance[n]['source'] = ('DS11_DEPTH_BIRTH_RECONNECT'
                    if transaction.get('birth_reconnect') else 'F9_EVENT_NUMERIC')
        trace = copy.deepcopy(original)
        trace['publication_effects'] = dict(
            transaction_changes_against_lawful_baseline=copy.deepcopy(
                transaction['changes'] if transaction else {}),
            existing_source_changes_against_previous={
                n:k for n,k in ids.items() if n in before and before[n] != k},
            new_source_publications={n:k for n,k in ids.items() if n not in before},
            overrides_against_native={n:k for n,k in ids.items() if n != k})
        return ids, trace


class DepthNativeManager(MergeSplitManager):
    def before(self, row, profiles):
        result = super().before(row, profiles)
        episode = self.active
        if episode and episode['id'] in self.bridge.engine.protected:
            spec = self.bridge.engine.protected[episode['id']]
            ids = self.bridge.causal_view(row['frame'], row['time'],
                                         row['observations'], profiles)['mapping']
            spec['outputs'] = {n:ids[n] for n in spec['suppressed'] if n in ids}
            spec['publication_policy'] = 'OWN_BRANCH_CAUSAL_EVENT_ALIAS_OR_NATIVE'
            episode.setdefault('publication_policy', []).append(dict(
                frame=row['frame'], outputs=copy.deepcopy(spec['outputs']),
                policy=spec['publication_policy'],
                internal_anonymous_sources=list(episode['member_sources'])))
        return result
