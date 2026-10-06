"""Original Z4Q candidates, finite window filters, and complete own-state replay.

Load under a unique module name: the legacy dependency also owns ``controller``.
The compatible DS32 hooks name a deletion ``ds32_depth_conflict`` internally;
our explicit candidate_window_filter record distinguishes it from a depth claim.
"""
import copy
import itertools
import sys

from common import CFG, ROOT, CONFIG_PATH, digest, read
from bridge import Bridge, StableReturn as CanonicalStableReturn

sys.path.insert(0, str(ROOT / 'experiments/ds32_z4q_depth_conflict_veto/source'))
from ds32_return import StableReturn

EXTRA_FIELDS = frozenset(('candidate_checks', 'candidate_policy'))


def engine_state(engine):
    return {key: copy.deepcopy(value) for key, value in vars(engine).items()
            if key not in EXTRA_FIELDS}


def full_state(bridge):
    return dict(engine=engine_state(bridge.engine), version=bridge.version,
                previous=copy.deepcopy(bridge.previous), epochs=copy.deepcopy(bridge.epochs),
                provenance=copy.deepcopy(bridge.provenance))


def bridge_hash(bridge):
    return digest(full_state(bridge))


def phase(event):
    return 'BIRTH_REFINE' if event.get('phase') == 'birth' else 'D1_DELAYED'


class CandidateEngine(StableReturn):
    def __init__(self, config):
        super().__init__(config)
        self.candidate_checks = []
        self.candidate_policy = None

    def edge_veto(self, frame, now, observation, public, anchor, origin_rule,
                  original_terms, original_eligible):
        assert origin_rule in ('D1_DELAYED', 'BIRTH_REFINE')
        native = observation['id']
        policy = self.candidate_policy
        veto = bool(original_eligible and policy is not None and native in policy
                    and public != policy[native])
        check = dict(frame=frame, time=now, phase=origin_rule, native_id=native,
                     public_id=public, target_bank_anchor=copy.deepcopy(anchor),
                     action_reference_anchor=copy.deepcopy(original_terms.get('old_anchor', anchor)),
                     terms=copy.deepcopy(original_terms), original_eligible=bool(original_eligible),
                     veto=veto, reason='DS33_UNPUBLISHED_WINDOW_CANDIDATE_FILTER' if veto else None)
        self.candidate_checks.append(copy.deepcopy(check))
        return check


class CandidateBridge(Bridge):
    def __init__(self, config):
        super().__init__(config)
        self.engine = CandidateEngine(config)

    def preview(self, frame, now, observations, profiles, policy=None):
        """Compare against original Z4Q from this same prior, never external B0."""
        before = bridge_hash(self)
        prior = engine_state(self.engine)
        original = CanonicalStableReturn.__new__(CanonicalStableReturn)
        original.__dict__.update(copy.deepcopy(prior))
        original_ids, original_trace = original.step(frame, now, observations, profiles)
        trial = copy.deepcopy(self.engine)
        trial.candidate_checks = []
        assert trial.candidate_policy is None
        trial.candidate_policy = copy.deepcopy(policy)
        try:
            mapping, trace = trial.step(frame, now, observations, profiles)
        finally:
            trial.candidate_policy = None
        deletion = any(check['veto'] for check in trial.candidate_checks)
        if not deletion:
            assert mapping == original_ids, 'null filter changed original mapping'
            assert digest(engine_state(trial)) == digest(vars(original)), 'null filter changed original state'
        trace['candidate_checks'] = copy.deepcopy(trial.candidate_checks)
        trace['candidate_window_filter'] = dict(policy=copy.deepcopy(policy),
            deleted_edges=sum(check['veto'] for check in trial.candidate_checks),
            original_own_state_mapping=copy.deepcopy(original_ids),
            null_original_state_exact=not deletion)
        post_epochs = dict(self.epochs)
        for native, public in mapping.items():
            if self.previous.get(native) != public:
                post_epochs[native] = post_epochs.get(native, 0) + 1
        assert bridge_hash(self) == before, 'preview polluted authoritative state'
        return dict(version=self.version, frame=frame, now=now, observations=observations,
            profiles=profiles, engine=trial, mapping=mapping, trace=trace,
            epochs={n: self.epochs.get(n, 0) + (n not in self.previous) for n in mapping},
            prior_epochs=copy.deepcopy(self.epochs), post_epochs=post_epochs,
            checkpoint_sha256=before, original_mapping=original_ids,
            original_trace=original_trace, original_engine_sha256=digest(vars(original)))


def enumerate_options(view):
    """One actual accepted-action component, original legal edges and self/dummy only."""
    assert view['trace']['candidate_window_filter']['policy'] is None, 'risk request needs original policy'
    actions = [copy.deepcopy(event) for event in view['trace'].get('events', [])
               if event.get('kind') == 'reconnect' and event.get('accepted')]
    if not actions:
        return dict(status='NO_ACCEPTED_ACTION', request=None, options=[])
    checks = [copy.deepcopy(check) for check in view['trace'].get('candidate_checks', [])
              if check['original_eligible']]
    seeds = {event['native_id'] for event in actions}
    graph = {}
    for check in checks:
        graph.setdefault(check['native_id'], set()).add(check['public_id'])
    components = []
    remaining = set(seeds)
    while remaining:
        sources = {min(remaining)}
        targets = set()
        changed = True
        while changed:
            before = (set(sources), set(targets))
            targets.update(k for n in sources for k in graph.get(n, ()))
            sources.update(n for n, values in graph.items() if values & targets)
            changed = before != (sources, targets)
        components.append((sources, targets))
        remaining -= sources
    request = dict(frame=view['frame'], time=view['now'], checkpoint_frame=view['frame'] - 1,
        checkpoint_sha256=view['checkpoint_sha256'], original_mapping=copy.deepcopy(view['mapping']),
        original_actions=actions, components=[dict(sources=sorted(s), targets=sorted(t)) for s, t in components],
        accepted_reference_contract='old_anchor is actual action reference; target_bank_anchor is separate',
        candidate_edges=checks)
    keep = dict(id='KEEP', mapping=copy.deepcopy(view['mapping']), policy=None)
    if len(components) != 1:
        return dict(status='OVERLAPPING_OR_MULTIPLE_COMPONENTS', request=request, options=[keep])
    sources, targets = components[0]
    if len(sources) > CFG['max_joint_sources']:
        return dict(status='OUT_OF_SCOPE_MORE_THAN_TWO_SOURCES', request=request, options=[keep])
    ordered = sorted(sources)
    request.update(sources=ordered, targets=sorted(targets),
        outside_sources=sorted(set(view['mapping']) - sources),
        source_births={n:copy.deepcopy(view['engine'].birth.get(n)) for n in ordered},
        source_prior_epochs={n:view['prior_epochs'].get(n, 0) for n in ordered},
        source_epochs={n:view['post_epochs'].get(n, 0) for n in ordered})
    # Preserve a continuous outside source's occupied target even when a new
    # source's integer is spelled like an existing public identity.
    outside_targets = {k for n, k in view['mapping'].items() if n not in sources}
    choices = [sorted((graph.get(n, set()) | {n}) - outside_targets) for n in ordered]
    options = [keep]
    for values in itertools.product(*choices):
        wanted = dict(view['mapping'])
        wanted.update(zip(ordered, values))
        if len(set(wanted.values())) != len(wanted) or wanted == keep['mapping']:
            continue
        options.append(dict(id='ALT_' + str(len(options)), mapping=wanted,
                            policy={n:k for n, k in zip(ordered, values)}))
        if len(options) > 16:
            return dict(status='OUT_OF_SCOPE_MORE_THAN_SIXTEEN_OPTIONS', request=request, options=[keep])
    request['option_contracts'] = copy.deepcopy(options)
    return dict(status='REQUEST', request=request, options=options)


def replay_option(checkpoint, window, request, option):
    """Actual preview/commit for every cached frame; invalid plans never touch caller state."""
    before = bridge_hash(checkpoint)
    try:
        assert isinstance(checkpoint, CandidateBridge), 'own CandidateBridge checkpoint required'
        assert checkpoint.version == request['checkpoint_frame']
        assert before == request['checkpoint_sha256'], 'checkpoint does not match actual request prior'
        assert option in request['option_contracts'], 'option was not in actual candidate set'
        frames = list(window)
        assert frames and frames[0][0]['frame'] == request['frame']
        assert frames[0][0]['time'] == request['time']
        assert frames[-1][0]['frame'] <= request['frame'] + CFG['lag_frames'], 'replay exceeds frozen future window'
        chosen = copy.deepcopy(checkpoint)
        baseline = copy.deepcopy(checkpoint)
        replayed = []
        previous_time = None
        sources = set(request['sources'])
        for index, (original_row, profiles) in enumerate(frames):
            row = copy.deepcopy(original_row)
            frame, now = row['frame'], row['time']
            assert frame == request['frame'] + index, 'noncontinuous replay frame'
            assert previous_time is None or now > previous_time, 'nonincreasing replay time'
            previous_time = now
            assert set(profiles) == {o['id'] for o in row['observations']}
            assert all(profile['frame'] == frame for profile in profiles.values())
            ids0, _ = baseline.commit_once(baseline.preview(frame, now, row['observations'], profiles))
            view = chosen.preview(frame, now, row['observations'], profiles, option['policy'])
            ids, trace = chosen.commit_once(view)
            assert chosen.engine.candidate_policy is None
            if index == 0:
                assert ids == option['mapping'], 'original lifecycle cannot submit expected first mapping'
            outside = {o['id'] for o in row['observations']} - sources
            assert all(ids[n] == ids0[n] for n in outside), 'outside mapping changed'
            assert len(ids) == len(set(ids.values())) == len(row['native'])
            assert set(ids) == {o['id'] for o in row['native']}
            row.update(mapping=ids, trace=trace, engine_state_sha256=digest(engine_state(chosen.engine)))
            replayed.append((row, copy.deepcopy(chosen)))
        assert bridge_hash(checkpoint) == before
        return dict(status='VALID_CANDIDATE', state=chosen, replayed_rows=replayed,
            trace=dict(option_id=option['id'], frames=len(replayed), checkpoint_sha256=before,
                       selected_state_sha256=bridge_hash(chosen), outside_mappings_preserved=True,
                       filtering_scope='UNPUBLISHED_WINDOW_ONLY', direct_alias_writes=False))
    except (AssertionError, KeyError, ValueError, TypeError) as error:
        assert bridge_hash(checkpoint) == before, 'failed replay mutated original checkpoint'
        return dict(status='INVALID_CANDIDATE', state=None, replayed_rows=[],
                    trace=dict(option_id=option.get('id'), reason=str(error), checkpoint_unchanged=True))


def direct_checks():
    """Exercise installed real Engine on synthetic measurements, never data/GT."""
    def observation(native, z=1000., x=10., neighbors=()):
        return dict(id=native, mask=f'n:{native}', box=[x, 10., x+10., 20.], area=100,
            score_birth=.9, presence=.9, neighbors=list(neighbors),
            depth=dict(n=100, valid_fraction=1., median=z, mad=1.))
    def row(frame, objects):
        value = dict(frame=frame, global_frame=frame, time=frame/10., observations=objects,
                     native=[dict(id=o['id'], mask=o['mask']) for o in objects])
        profiles = {o['id']:dict(id=o['id'], mask=o['mask'], frame=frame,
                    core=copy.deepcopy(o['depth']), whole=copy.deepcopy(o['depth'])) for o in objects}
        return value, profiles
    branch = CandidateBridge(read(CONFIG_PATH))
    original = Bridge(read(CONFIG_PATH))
    for frame in range(1, 7):
        objects = [observation(1, neighbors=(2,) if frame == 6 else ()),
                   observation(2, 1400., 50., (1,) if frame == 6 else ())]
        value, profiles = row(frame, objects)
        ids, _ = branch.commit_once(branch.preview(frame, value['time'], objects, profiles))
        native, _ = original.commit_once(original.preview(frame, value['time'], objects, profiles))
        assert ids == native and full_state(branch) == full_state(original)
    checkpoint = copy.deepcopy(branch)
    value, profiles = row(7, [observation(3, neighbors=(2,)), observation(2, 1400., 50., (3,))])
    view = branch.preview(7, .7, value['observations'], profiles)
    candidates = enumerate_options(view)
    assert candidates['status'] == 'REQUEST'
    assert candidates['options'][0]['mapping'][3] == 1
    self_option = next(option for option in candidates['options'] if option['mapping'][3] == 3)
    keep = replay_option(checkpoint, [(value, profiles)], candidates['request'], candidates['options'][0])
    altered = replay_option(checkpoint, [(value, profiles)], candidates['request'], self_option)
    assert keep['status'] == altered['status'] == 'VALID_CANDIDATE'
    assert keep['state'].engine.alias[3]['target'] == 1
    assert 3 not in altered['state'].engine.alias and 1 in altered['state'].engine.bank
    assert keep['state'].previous[3] == 1 and altered['state'].previous[3] == 3
    assert checkpoint.version == 6 and 3 not in checkpoint.engine.alias
    invalid = copy.deepcopy(self_option)
    invalid['mapping'][3] = 99
    rejected = replay_option(checkpoint, [(value, profiles)], candidates['request'], invalid)
    assert rejected['status'] == 'INVALID_CANDIDATE'
    beyond = copy.deepcopy(value)
    beyond['frame'] = value['frame'] + CFG['lag_frames'] + 1
    rejected_future = replay_option(checkpoint, [(value, profiles), (beyond, profiles)],
                                    candidates['request'], self_option)
    assert rejected_future['status'] == 'INVALID_CANDIDATE'
    assert rejected_future['trace']['reason'] == 'replay exceeds frozen future window'
    delayed = copy.deepcopy(checkpoint)
    delayed.engine.birth_enabled = False
    confirmations = delayed.engine.cfg['confirm']
    for frame in range(7, 7 + confirmations - 1):
        first, profiles1 = row(frame, [observation(3), observation(2, 1400., 50.)])
        pending = delayed.preview(frame, first['time'], first['observations'], profiles1)
        assert enumerate_options(pending)['status'] == 'NO_ACCEPTED_ACTION'
        delayed.commit_once(pending)
        assert delayed.engine.pending[3]['count'] == frame - 6
    decision_frame = 7 + confirmations - 1
    second, profiles2 = row(decision_frame, [observation(3), observation(2, 1400., 50.)])
    view2 = delayed.preview(decision_frame, second['time'], second['observations'], profiles2)
    options2 = enumerate_options(view2)
    assert options2['status'] == 'REQUEST'
    assert phase(options2['request']['original_actions'][0]) == 'D1_DELAYED'
    self2 = next(option for option in options2['options'] if option['mapping'][3] == 3)
    delayed_replay = replay_option(delayed, [(second, profiles2)], options2['request'], self2)
    assert delayed_replay['status'] == 'VALID_CANDIDATE'
    assert delayed_replay['state'].previous[3] == 3 and 3 not in delayed_replay['state'].engine.alias
    assert delayed_replay['state'].engine.candidate_policy is None
    assert delayed.engine.pending[3]['count'] == confirmations - 1
    # Policy is released at the end of the cached window: the original rule is
    # allowed to propose its edge again. A local alternative is not an ID lock.
    third, profiles3 = row(decision_frame + 1, [observation(3), observation(2, 1400., 50.)])
    resume = delayed_replay['state'].preview(third['frame'], third['time'], third['observations'], profiles3)
    assert any(check['original_eligible'] and check['public_id'] == 1 and not check['veto']
               for check in resume['trace']['candidate_checks'])
    return dict(status='PASS', checks=['REAL_ENGINE_NULL_FULL_STATE', 'REAL_BIRTH_EDGE_AND_DUMMY_REPLAY',
        'NO_DIRECT_ALIAS_WRITE_FILTER_CLEARED', 'INVALID_OPTION_ATOMIC_CHECKPOINT',
        'FROZEN_FUTURE_WINDOW_ENFORCED', 'REAL_D1_ORIGINAL_CONFIRMATIONS_RETAINED',
        'POST_WINDOW_ORIGINAL_CANDIDATE_RESUMES'], count=7, model_http=0)


if __name__ == '__main__':
    import json
    print(json.dumps(direct_checks(), indent=2))
