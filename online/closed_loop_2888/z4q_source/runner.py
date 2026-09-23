"""Repaired causal runner. It never imports labels or infers a dataset split."""
from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass, field

from bridge import Bridge
from policy import compile_view, state_for, request, gate, clean_observation


def proposal_signature(proposal):
    return tuple(sorted((int(n), int(k)) for n, k in proposal['changes'].items()))


def episode_key(compiled):
    participants = tuple(sorted(int(n) for n in compiled['affected']))
    targets = tuple(sorted({int(k) for p in compiled['proposals'] for k in p['changes'].values()}))
    return participants, targets


def context_fingerprint(bridge, view, compiled):
    """Identity lineage only; ordinary measurements and anchor frame refreshes are excluded."""
    participants, targets = episode_key(compiled)
    owners = {k: next((n for n, public in view['mapping'].items() if public == k), None) for k in targets}
    references = {}
    for k in targets:
        h = bridge.engine.bank.get(k, {})
        a = h.get('anchor')
        references[k] = None if a is None else (a.get('canonical_id'), a.get('native_id'))
    return dict(
        participants=participants,
        participant_epochs=tuple((n, view.get('epochs', {}).get(n, bridge.epochs.get(n, 0))) for n in participants),
        target_owners=tuple(sorted(owners.items())),
        reference_attribution=tuple(sorted(references.items())),
        candidate_signatures=tuple(sorted(proposal_signature(p) for p in compiled['proposals'])),
    )


@dataclass
class Episode:
    checks: int = 0
    last_check_frame: int | None = None
    confirmation: dict | None = None
    fingerprint: dict | None = None
    invalidations: list = field(default_factory=list)


class EpisodeBook:
    def __init__(self, min_frame_gap=5, max_checks=3):
        self.min_frame_gap = min_frame_gap
        self.max_checks = max_checks
        self.episodes = {}

    @staticmethod
    def _change_reason(before, after):
        if before is None:
            return None
        if before['participant_epochs'] != after['participant_epochs']:
            return 'participant_epoch_changed'
        if before['target_owners'] != after['target_owners']:
            return 'target_occupancy_changed'
        if before['reference_attribution'] != after['reference_attribution']:
            return 'reference_attribution_changed'
        if before['candidate_signatures'] != after['candidate_signatures']:
            return 'candidate_set_changed'
        return None

    def synchronize(self, active, frame):
        active_keys = set(active)
        for key, episode in self.episodes.items():
            if key not in active_keys and episode.confirmation is not None:
                episode.invalidations.append(dict(frame=frame, reason='candidate_withdrawn'))
                episode.confirmation = None
                episode.fingerprint = None
        for key, fingerprint in active.items():
            episode = self.episodes.setdefault(key, Episode())
            reason = self._change_reason(episode.fingerprint, fingerprint)
            if reason and episode.confirmation is not None:
                episode.invalidations.append(dict(frame=frame, reason=reason))
                episode.confirmation = None
            episode.fingerprint = copy.deepcopy(fingerprint)

    def check_permission(self, key, frame):
        episode = self.episodes.setdefault(key, Episode())
        if episode.checks >= self.max_checks:
            return False, 'EPISODE_SEALED'
        if episode.last_check_frame == frame:
            return False, 'SAME_FRAME_NOT_NEW_OBSERVATION'
        if episode.last_check_frame is not None and frame - episode.last_check_frame < self.min_frame_gap:
            return False, 'WAIT_NEW_OBSERVATION'
        episode.checks += 1
        episode.last_check_frame = frame
        return True, 'CHECK_ALLOWED'

    def record(self, key, frame, fingerprint, proposal):
        episode = self.episodes[key]
        signature = proposal_signature(proposal)
        prior = episode.confirmation
        current = dict(frame=frame, signature=signature, fingerprint=copy.deepcopy(fingerprint))
        if (prior is not None and prior['signature'] == signature and
                prior['fingerprint'] == fingerprint and frame - prior['frame'] >= self.min_frame_gap):
            episode.confirmation = current
            return True, prior['frame']
        episode.confirmation = current
        return False, None

    def reject(self, key, frame, reason):
        episode = self.episodes[key]
        if episode.confirmation is not None:
            episode.invalidations.append(dict(frame=frame, reason=reason))
        episode.confirmation = None

    def audit(self):
        return {str(k): dict(checks=v.checks, last_check_frame=v.last_check_frame,
                            confirmation=v.confirmation, invalidations=v.invalidations)
                for k, v in self.episodes.items()}


class RepairedRunner:
    """One branch owns one real engine; a committed transaction persists."""
    def __init__(self, config, arm, response_provider=None, initialization='empty_native_state'):
        assert arm in {'B0', 'B1', 'B2'}
        assert initialization == 'empty_native_state'
        self.arm = arm
        self.initialization = initialization
        self.bridge = Bridge(config)
        self.responses = response_provider
        self.episodes = EpisodeBook(min_frame_gap=5, max_checks=3)
        self.records = []

    def _final_validate(self, view, compiled, proposal, fingerprint):
        refreshed = compile_view(self.bridge, view)
        candidates = {proposal_signature(p): p for p in refreshed.get('proposals', [])}
        selected = candidates.get(proposal_signature(proposal))
        if selected is None:
            return None, 'candidate_withdrawn_before_stage'
        if context_fingerprint(self.bridge, view, refreshed) != fingerprint:
            return None, 'identity_context_changed_before_stage'
        occupied = set(selected['after'].values())
        observations = {o['id']: o for o in view['observations']}
        if not all(clean_observation(self.bridge.engine, observations[n], k, occupied, view['now'])
                   for n, k in selected['changes'].items()):
            return None, 'current_observation_not_stage_qualified'
        if any(refreshed['claims'][n]['status'] == 'SUPPORTED_CURRENT' for n in selected['changes']):
            return None, 'protected_claim'
        if any(not refreshed['claims'][n]['contradiction'] for n in selected['displaced']):
            return None, 'displaced_claim_without_traceable_contradiction'
        return self.bridge.stage(view, selected['changes'])

    def step(self, frame_record, profiles, feature_history=None):
        f, now, observations = frame_record['frame'], frame_record['time'], frame_record['observations']
        view = self.bridge.preview(f, now, observations, profiles)
        transaction = None
        record = dict(frame=f, global_frame=frame_record.get('global_frame'), arm=self.arm,
                      status='NATIVE', request=None, response_kind=None)
        if self.arm == 'B0':
            self.episodes.synchronize({}, f)
        else:
            compiled = compile_view(self.bridge, view)
            record.update(compile_status=compiled['status'], proposals=copy.deepcopy(compiled.get('proposals', [])))
            if compiled['status'] == 'READY':
                key = episode_key(compiled)
                fingerprint = context_fingerprint(self.bridge, view, compiled)
                self.episodes.synchronize({key: fingerprint}, f)
                allowed, status = self.episodes.check_permission(key, f)
                record['status'] = status
                if allowed:
                    state = state_for(self.bridge, view, compiled, feature_history)
                    model_request = request(state, self.arm)
                    record['request'] = model_request
                    response = self.responses(model_request, dict(frame=f, compiled=compiled, view=view))
                    record['response_kind'] = response.get('_source')
                    proposal, gate_status = gate(response['answers'], compiled)
                    record.update(status=gate_status, answers=response['answers'])
                    if proposal is None:
                        self.episodes.reject(key, f, gate_status)
                    else:
                        record['selected_proposal'] = copy.deepcopy(proposal)
                        confirmed, first = self.episodes.record(key, f, fingerprint, proposal)
                        record['status'] = 'SECOND_CONFIRMATION' if confirmed else 'FIRST_CONFIRMATION'
                        record['first_confirmation_frame'] = first
                        if confirmed:
                            transaction, error = self._final_validate(view, compiled, proposal, fingerprint)
                            record.update(status='COMMIT' if transaction else 'STAGE_REJECTED', stage_error=error)
            else:
                self.episodes.synchronize({}, f)
                record['status'] = compiled['status']
        ids, trace = self.bridge.commit_once(view, transaction)
        record.update(final_mapping=copy.deepcopy(ids), native_trace=copy.deepcopy(trace),
                      committed=None if transaction is None else copy.deepcopy(transaction['changes']),
                      episode_audit=self.episodes.audit())
        self.records.append(record)
        return ids, trace, record


def fixture_response(request_payload, context):
    """Deterministic high-support response. Never valid as model evidence."""
    proposal = next(k for k in request_payload['state']['alternatives'])
    choices = list(request_payload['questions']['select']['criteria'])
    probabilities = {k: .01 for k in choices}
    probabilities[proposal] = .98
    if len(choices) == 2:
        probabilities[proposal] = .99
    answers = {'select': dict(type='choice', choice=proposal, probabilities=probabilities, confidence=.99)}
    for key, question in request_payload['questions'].items():
        if key != 'select':
            answers[key] = dict(type=question['type'], noul=.99)
    return dict(_source='ENGINEERING_FIXTURE', answers=answers)


def request_digest(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
