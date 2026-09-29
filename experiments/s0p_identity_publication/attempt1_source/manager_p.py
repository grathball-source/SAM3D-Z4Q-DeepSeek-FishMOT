"""S0-P: separate anonymous event evidence from published tracker identities.

The frozen V7 manager still supplies event detection, history, q and numerical
association.  Only publication and the failed-event transaction change here.
"""
import copy

from merge_split_manager import GroupBridge, MergeSplitManager


class OutputIdentityPolicy:
    """Keep a continuous native source's last public ID while evidence is anonymous."""

    @staticmethod
    def apply(episode, row, previous, last_source_frame, provisional):
        if episode['q'] == row['frame']:
            # At the first split this is an internal preview. The chosen pair is
            # staged before the publisher receives the frame.
            return provisional, {}
        frame = row['frame']
        current = {o['id'] for o in row['observations']}
        members = set(episode['member_sources'])
        outputs = {}
        reasons = {}
        outside = {previous[n] for n in current - set(provisional) if n in previous}
        used = set(outside)

        # Existing, frame-contiguous members have first claim on their *own*
        # last published label. A group carrier cannot steal a visible residual's ID.
        for native in episode['member_sources']:
            target = previous.get(native)
            if (native in provisional and last_source_frame.get(native) == frame-1
                    and target in episode['public_ids'] and target not in used):
                outputs[native] = target
                reasons[native] = 'CONTIGUOUS_SOURCE_LAST_PUBLIC'
                used.add(target)

        group = episode['group_source']
        if group in provisional and group not in outputs:
            preferred = [previous.get(group), provisional[group], *episode['public_ids']]
            target = next((k for k in preferred if k in episode['public_ids'] and k not in used), None)
            if target is not None:
                outputs[group] = target
                reasons[group] = 'GROUP_CARRIER_UNOCCUPIED_PUBLIC'
                used.add(target)

        for native, provisional_id in provisional.items():
            if native in outputs:
                continue
            target = previous.get(native)
            if (native in members and last_source_frame.get(native) == frame-1
                    and target is not None and target not in used):
                outputs[native] = target
                reasons[native] = 'CONTIGUOUS_SOURCE_LAST_PUBLIC'
            else:
                target = provisional_id
                # The old internal token remains a public fallback only for a
                # genuinely new or conflicting fragment; it is never dropped.
                while target in used:
                    target -= 1
                outputs[native] = target
                reasons[native] = 'NEW_OR_CONFLICTING_FRAGMENT_UNRESOLVED'
            used.add(outputs[native])
        assert set(outputs) == set(provisional) and len(set(outputs.values())) == len(outputs)
        return outputs, reasons


class MergeSplitManagerP(MergeSplitManager):
    def before(self, row, profiles):
        result = super().before(row, profiles)
        episode = self.active
        if episode and episode['id'] in self.bridge.engine.protected:
            spec = self.bridge.engine.protected[episode['id']]
            spec['outputs'], reasons = OutputIdentityPolicy.apply(
                episode, row, self.bridge.previous, self.last_source_frame, spec['outputs'])
            spec['publication_policy'] = reasons
            episode.setdefault('publication_policy', []).append(
                dict(frame=row['frame'], outputs=copy.deepcopy(spec['outputs']),
                     reasons=reasons, internal_group_token=episode['group_source'],
                     internal_anonymous_sources=[n for n in episode['member_sources']
                                                 if n != episode['group_source']]))
        return result


class GroupBridgeP(GroupBridge):
    """At a failed S0, transplant only this event's state from this branch's causal trial."""

    def local_fallback(self, view, episode):
        assert view['version'] == self.version and view['frame'] == episode['q']
        native = set(episode['member_sources']) | set(episode['post_roles']) | {episode['group_source']}
        observed = {o['id'] for o in view['observations']}
        native &= observed
        candidate = copy.deepcopy(self.engine)  # Own branch before this frame.
        candidate.protected.pop(episode['id'], None)
        candidate_ids, candidate_trace = candidate.step(
            view['frame'], view['now'], view['observations'], view['profiles'])
        outside = observed - native
        mapping = dict(view['mapping'])
        group_mapping = {n: candidate_ids[n] for n in native}
        mapping.update(group_mapping)
        outside_equal = all(candidate_ids[n] == view['mapping'][n] for n in outside)
        target = set(episode['public_ids']) | {k for k in group_mapping.values() if k >= 0}
        outside_targets = {view['mapping'][n] for n in outside}
        outside_alias_targets = {v['target'] for n, v in view['engine'].alias.items() if n not in native}
        safe = (outside_equal and not (target & outside_targets)
                and not (target & outside_alias_targets)
                and len(mapping) == len(set(mapping.values())))
        trial = copy.deepcopy(view['engine'])
        trial.protected.pop(episode['id'], None)
        if safe:
            # Public bank keys and native source keys are different domains even
            # when their integer spelling happens to be identical.
            for name, keys in (('bank', target), ('view_bank', target),
                               ('alias', native), ('birth', native), ('pending', native),
                               ('native_seen', native), ('native_runs', native),
                               ('recent_core', native), ('return_quarantine', native),
                               ('empty_quarantine', native)):
                dst, src = getattr(trial, name), getattr(candidate, name)
                for key in keys:
                    if key in src:
                        dst[key] = copy.deepcopy(src[key])
                    elif name not in ('bank', 'view_bank'):
                        dst.pop(key, None)  # Keep latent protected banks.
            trial.retired.difference_update(native)
            trial.retired.update(candidate.retired & native)
            status = 'LOCAL_FALLBACK_COMMITTED'
            chosen = mapping
        else:
            # Never copy B0 or an unsafe whole-state candidate. The legal current
            # branch mapping remains in the score, explicitly unresolved.
            status = 'LOCAL_FALLBACK_UNRESOLVED'
            chosen = dict(view['mapping'])
        assert len(chosen) == len(observed) == len(set(chosen.values()))
        trace = copy.deepcopy(view['trace'])
        trace['merge_split_local_fallback'] = dict(
            episode=episode['id'], status=status, candidate_source='OWN_BRANCH_PRE_FRAME',
            event_native_write_set=sorted(native), event_public_write_set=sorted(target),
            outside_mapping_and_ownership_equal=outside_equal,
            candidate_trace_events=len(candidate_trace.get('events', [])))
        transaction = dict(engine=trial, mapping=chosen, trace=trace, changes={}, anchors={})
        return transaction, trace['merge_split_local_fallback']
