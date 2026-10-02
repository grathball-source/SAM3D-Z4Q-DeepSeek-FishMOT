"""Protect event identity references while the original Z4Q source lifecycle runs.

Group/post measurements remain anonymous in the manager and DepthState. The
native proposal stores are not immutable identity references: freezing them
would manufacture source gaps and suppress the original birth recovery rules.
"""
import copy
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for path in (ROOT/'online/closed_loop_2888/z4q_source',
             Path('E:/CAU/D-MOT/tools/jev_z4q_scene_v1_20260922/deps')):
    if str(path) not in sys.path:
        sys.path.append(str(path))

# Load the original controller namespace before the old manager adapters.
from bridge import Bridge  # noqa: E402, F401

_spec = importlib.util.spec_from_file_location(
    'ds16_reused_ds15_controller',
    ROOT/'experiments/ds15_z4q_depth_strategy_repair/controller.py')
_adapter = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_adapter)
from ne_controller import StableReturn as OriginalReturn  # noqa: E402

EventManager = _adapter.DepthNativeManager


class EventReturn(OriginalReturn):
    """Original automatic candidate rules; protected references live in the bridge."""

    def __init__(self, config):
        super().__init__(config)
        self.protected = {}
        self.auto_edge_checks = []

    def edge_veto(self, frame, now, observation, public, anchor, origin_rule):
        check = dict(frame=frame, native_id=observation['id'], public_id=public,
                     origin_rule=origin_rule, veto=False,
                     reason='DS16_ORIGINAL_Z4Q_CANDIDATE_RETAINED')
        self.auto_edge_checks.append(check)
        return check

    def step(self, frame, now, observations, profiles=None):
        self.auto_edge_checks = []
        ids, trace = super().step(frame, now, observations, profiles)
        trace['ds16_original_automatic_edge_checks'] = copy.deepcopy(self.auto_edge_checks)
        return ids, trace


class EventBridge(_adapter.DepthNativeBridge):
    def __init__(self, config):
        super().__init__(config)
        self.engine = EventReturn(config)

    def preview(self, frame, now, observations, profiles):
        view = self.causal_view(frame, now, observations, profiles)
        if not self.engine.protected:
            return view
        episode, original = next(iter(self.engine.protected.items()))
        spec = copy.deepcopy(original)
        public = set(spec['member_public'])
        trial = view['engine']
        # These keys are public identities, never source integers. Aliases,
        # first_eligible, birth, pending and actual source continuity stay live.
        for name in ('bank', 'view_bank'):
            current, before = getattr(trial, name), getattr(self.engine, name)
            for key in public:
                current.pop(key, None)
                if key in before:
                    current[key] = copy.deepcopy(before[key])
        spec['outputs'] = {n:view['mapping'][n] for n in spec['suppressed']
                           if n in view['mapping']}
        trial.protected[episode] = spec
        sources = set(spec['member_sources']) | set(spec['suppressed'])
        view['trace']['merge_split_group'] = dict(
            episode=episode, suppressed=sorted(spec['suppressed']),
            outputs=copy.deepcopy(spec['outputs']), preview_only_not_published=True,
            publication_policy='OWN_BRANCH_CAUSAL_EVENT_ALIAS_OR_NATIVE',
            protected_public_banks_preserved=True,
            protected_identity_reference_stores=['bank', 'view_bank'],
            source_proposal_lifecycle='ACTUAL_CURRENT_ORIGINAL_Z4Q_NOT_FROZEN',
            visible_source_state={str(n):dict(
                native_seen=trial.native_seen.get(n),
                native_run=copy.deepcopy(trial.native_runs.get(n)),
                recent_core_anchor=copy.deepcopy(trial.recent_core.get(n, {}).get('anchor')))
                for n in sorted(sources & set(view['mapping']))},
            depth_history_policy='GROUP_AND_UNASSIGNED_POST_REMAIN_ANONYMOUS_EXTERNALLY')
        return view
