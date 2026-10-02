"""State/read-contract checks; optional source-only L3 prefix (no GT or score)."""
import argparse
import copy
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path

_spec = importlib.util.spec_from_file_location('ds17_unique_test_controller',
                                             Path(__file__).with_name('controller.py'))
C = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(C)
CONFIG = json.loads((C.ROOT / 'online/closed_loop_2888/z4q_source/CONFIG.json').read_text())


def observation(native, x, depth=750., area=400):
    return dict(id=native, mask=f'n:{native}', box=[x, 50., x + 20., 70.], area=area,
                presence=.99, score_birth=.99, neighbors=[],
                depth=dict(n=area, valid_fraction=1., median=depth, mad=2.))


def profiles(frame, obs):
    return {o['id']: dict(id=o['id'], mask=o['mask'], frame=frame,
                         core=copy.deepcopy(o['depth']), whole=copy.deepcopy(o['depth'])) for o in obs}


def warm(cls=C.EventBridge):
    branch = cls(CONFIG)
    for frame in range(1, 11):
        obs = [observation(1, 40.), observation(2, 100., 850.), observation(3, 200., 840.)]
        view = branch.preview(frame, frame / 30., obs, profiles(frame, obs))
        assert branch.commit_once(view)[0] == {1: 1, 2: 2, 3: 3}
    return branch


def protect(branch, suppressed, frame=11):
    snapshot = {k: copy.deepcopy(branch.engine.bank[k]) for k in (1, 2)}
    branch.engine.protected['TEST'] = dict(episode='TEST', generation=frame,
        member_public=[1, 2], member_sources=[1, 2], suppressed=suppressed,
        outputs={n: n for n in suppressed})
    return snapshot


def checks():
    new, original = warm(), warm(C.Bridge)
    for name in ('bank', 'view_bank', 'alias', 'birth', 'pending', 'native_seen', 'native_runs', 'recent_core'):
        assert getattr(new.engine, name) == getattr(original.engine, name), name
    before = copy.deepcopy(vars(new.engine))
    snapshot = protect(new, [1])
    before = copy.deepcopy(vars(new.engine))
    obs = [observation(1, 41., 799.), observation(3, 201., 840.)]
    obs[0]['neighbors'] = [3]
    view = new.preview(11, 11 / 30., obs, profiles(11, obs))
    trial = view['engine']
    assert vars(new.engine) == before
    for k in (1, 2):
        assert C.clean_reference(trial.bank[k]) == C.clean_reference(snapshot[k])
        assert trial.view_bank[k] == new.engine.view_bank[k]
    assert trial.bank[1]['last_seen'] == 11 / 30. and trial.bank[1]['last_frame'] == 11
    assert trial.bank[1]['partners'][3] == 11 / 30.
    assert trial.bank[2]['last_seen'] == snapshot[2]['last_seen']
    assert trial.source_activity[2]['frame'] == 10  # No fabricated disappearance update.
    assert trial.source_activity[1]['received_association_observation']['depth']['median'] == 799.
    assert not trial.source_activity[1]['identity_measurement_certified']
    assert trial.recent_core[1] == new.engine.recent_core[1]
    assert trial.native_runs[1]['last_frame'] == 11 and 2 not in trial.native_runs
    assert trace_or(view)['anonymous_current_depth_blocked'] == [1]
    new.commit_once(view)
    assert new.engine.bank[1]['anchor']['frame'] == 10
    assert new.engine.certificate(1, 12, 12 / 30., {1: observation(1, 42.)})['qualified']

    # Live activity no longer causes the old whole-bank guard to reject a valid S0.
    branch = warm()
    branch.engine.alias[99] = dict(target=3, anchor=copy.deepcopy(branch.engine.bank[3]['anchor']),
                                  commit_frame=10, source='OUTSIDE_COMMIT')
    snapshot = protect(branch, [1, 2])
    branch.engine.observation_frame = 11
    branch.engine.observation_classes = {1: 'POST_UNASSIGNED', 2: 'POST_UNASSIGNED'}
    obs = [observation(1, 42.), observation(2, 102., 850.), observation(99, 202., 840.)]
    view = branch.preview(11, 11 / 30., obs, profiles(11, obs))
    episode = dict(id='TEST', generation=11, q=11, suspect_frame=11,
        member_sources=[1, 2], group_source=1, public_ids=[1, 2], bank_snapshot=snapshot,
        post_roles={n: [dict(frame=11, time=11 / 30., center=[50., 60.])] for n in (1, 2)})
    before, original_episode = copy.deepcopy(vars(branch.engine)), copy.deepcopy(episode)
    transaction, error = branch.stage_group_restore(view, episode, {1: 2, 2: 1})
    assert error is None and transaction['mapping'] == {1: 2, 2: 1, 99: 3}
    assert episode == original_episode and vars(branch.engine) == before
    assert transaction['engine'].alias[99] == view['engine'].alias[99]
    assert transaction['engine'].bank[3] == view['engine'].bank[3]
    assert all(transaction['engine'].bank[k]['anchor']['frame'] == 11 for k in (1, 2))
    corrupt = copy.deepcopy(view)
    corrupt['engine'].bank[1]['depth_history'].append((11 / 30., 123.))
    assert branch.stage_group_restore(corrupt, episode, {1: 2, 2: 1}) == (None, 'protected_reference_changed')
    corrupt_view = copy.deepcopy(view)
    corrupt_view['engine'].view_bank[1]['core']['anchor']['native_id'] = 999
    assert branch.stage_group_restore(corrupt_view, episode, {1: 2, 2: 1}) == (None, 'protected_view_provenance_changed')
    stale = copy.deepcopy(episode)
    stale['generation'] += 1
    assert branch.stage_group_restore(view, stale, {1: 2, 2: 1}) == (None, 'stale_generation')
    assert branch.stage_group_restore(view, episode, {1: 3, 2: 2}) == (None, 'invalid_bijection')
    fallback, detail = branch.local_fallback(view, episode)
    assert fallback['mapping'] == view['mapping'] and not fallback['engine'].protected
    assert fallback['engine'].bank[3] == view['engine'].bank[3]
    assert fallback['engine'].alias[99] == view['engine'].alias[99]
    assert detail['unassigned_q_not_certified_as_pre'] and vars(branch.engine) == before
    assert fallback['engine'].recent_core[1] == branch.engine.recent_core[1]

    # A new pending source has activity but no invented clean reference.
    branch = warm()
    protect(branch, [101, 102])
    obs = [observation(101, 42.), observation(102, 102., 850.)]
    view = branch.preview(11, 11 / 30., obs, profiles(11, obs))
    for n in (101, 102):
        assert view['engine'].bank[n]['last_seen'] == 11 / 30.
        assert view['engine'].bank[n]['clean_time'] is None
        assert not view['engine'].bank[n]['depth_history']
        assert 'anchor' not in view['engine'].bank[n]
        assert n not in view['engine'].recent_core
    assert not any(e.get('accepted') for e in view['trace'].get('events', []) if e.get('kind') == 'reconnect')

    # Actual residual observations advance last_seen beyond an obsolete contact.
    # A missing competitor cannot be reserved using its absent current observation.
    pair = [warm(C.EventBridge), warm(C.FrozenEventBridge)]
    for branch in pair:
        obs = [observation(1, 40.), observation(2, 100., 850.), observation(3, 200., 840.)]
        obs[1]['neighbors'], obs[2]['neighbors'] = [3], [2]
        branch.commit_once(branch.preview(11, 11 / 30., obs, profiles(11, obs)))
        protect(branch, [1, 2], frame=12)
    for frame in range(12, 47):
        obs = [observation(1, 40.), observation(2, 100., 850., area=50), observation(3, 200., 840.)]
        obs[1]['neighbors'] = [1]
        for branch in pair:
            branch.commit_once(branch.preview(frame, frame / 30., obs, profiles(frame, obs)))
    assert pair[0].engine.bank[2]['last_frame'] == 46
    assert pair[1].engine.bank[2]['last_frame'] == 11
    results = []
    for frame in range(47, 52):
        obs = [observation(1, 40.), observation(4, 105., 840.)]
        ps = profiles(frame, obs)
        ps.pop(4)  # Missing birth core remains missing; D1 has its actual whole depth.
        frame_result = []
        for branch in pair:
            view = branch.preview(frame, frame / 30., obs, ps)
            ids, trace = branch.commit_once(view)
            edge = next(e for e in trace['edges'] if e['native_id'] == 4 and e['canonical_id'] == 2)
            frame_result.append(dict(mapping=ids, edge=edge))
        results.append(frame_result)
    assert results[-1][0]['mapping'][4] == 2
    assert results[-1][1]['mapping'][4] == 4
    assert results[-1][1]['edge']['rejection'] == 'partner_ambiguous'
    assert all(p['id'] != 3 for p in results[-1][0]['edge']['alternatives'])
    print('PASS: original no-event state, live real activity, no missing-source timestamps, '
          'immutable clean/view/recent refs, anonymous depth excluded from individual association, '
          'semantic reference guard, atomic stage, outside-safe fallback, pending-source refs, '
          'actual-contact recency synthetic regression.')


def trace_or(view):
    return view['trace']['activity_reference_separation']


def real_l3():
    """Source-only prefix, fixed H0 release for all split decisions; no metrics."""
    base = C.ROOT / 'experiments/ds14_raw_multidataset/private/L3'
    def load(path):
        with gzip.open(path, 'rt', encoding='utf8') as f:
            yield from (json.loads(x) for x in f)
    assignments = {r['frame']: r for r in load(base / 'assignments.jsonl.gz')}
    suspects = {r['frame']: r for r in json.loads((base / 'scan_v4.json').read_text())['suspects']}
    branches = {'ORIGINAL': C.Bridge(CONFIG), 'DS16_PROTECTION': C.FrozenEventBridge(CONFIG),
                'DS17_STATE_ONLY': C.EventBridge(CONFIG)}
    managers = {arm: cls(arm, branches[arm], suspects, dict(max_episode_seconds=10.), assignments)
                for arm, cls in [('DS16_PROTECTION', C.FrozenEventManager),
                                 ('DS17_STATE_ONLY', C.EventManager)]}
    selected = {}
    for row, pr in zip(load(base / 'observations.jsonl.gz'), load(base / 'profiles.jsonl.gz'), strict=True):
        frame, now = row['frame'], row['time']
        assert (frame, row['global_frame'], now) == (pr['frame'], pr['global_frame'], pr['time'])
        ps = {o['id']: dict(o, frame=frame) for o in pr['observations']}
        for arm, branch in branches.items():
            manager = managers.get(arm)
            if manager:
                manager.before(row, ps)
            view = branch.preview(frame, now, row['observations'], ps)
            transaction = None
            if manager and manager.active and manager.active['q'] == frame:
                transaction, _ = branch.local_fallback(view, manager.active)
                manager.finish(frame, 'STATE_ONLY_FIXED_H0_RELEASE')
            ids, trace = branch.commit_once(view, transaction)
            if manager:
                manager.after(row, ps)
            if frame in (2872, 2890, 3021, 3025):
                selected[f'{arm}/F{frame}'] = dict(mapping=ids,
                    bank9_activity={k: copy.deepcopy(branch.engine.bank.get(9, {}).get(k)) for k in C.ACTIVITY_FIELDS},
                    bank9_reference=C.clean_reference(branch.engine.bank.get(9, {})),
                    native47_edges=[e for e in trace.get('edges', []) if e.get('native_id') == 47],
                    actual_automatic_actions=[e for e in trace.get('events', []) if e.get('accepted')],
                    active_event=manager.active['id'] if manager and manager.active else None,
                    activity_reference_separation=trace.get('activity_reference_separation'))
        if frame == 3025:
            break
    hashes = {}
    for name in ('observations.jsonl.gz', 'profiles.jsonl.gz', 'assignments.jsonl.gz', 'scan_v4.json'):
        p = base / name
        with p.open('rb') as f:
            hashes[name] = dict(path=str(p), bytes=p.stat().st_size,
                                sha256=hashlib.file_digest(f, 'sha256').hexdigest())
    print(json.dumps(dict(status='SOURCE_ONLY_REAL_L3_PREFIX_COMPLETE', frames=3025,
        split_policy='FIXED_H0_CAUSAL_RELEASE_NOT_A_RESEARCH_ASSOCIATION_RESULT',
        sources=hashes, actual_slices=selected, GT_read=False, scoring=False,
        new_model_http=0, cost_usd=0), ensure_ascii=False, allow_nan=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--real-l3', action='store_true')
    args = parser.parse_args()
    checks()
    if args.real_l3:
        real_l3()
