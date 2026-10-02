"""Source continuity, immutable event reference and own-branch transaction checks."""
import copy
import importlib.util
import json
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    'ds16_controller_test_adapter', Path(__file__).with_name('controller.py'))
_controller = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_controller)
EventBridge, EventManager, ROOT = _controller.EventBridge, _controller.EventManager, _controller.ROOT


CONFIG = json.loads((ROOT/'online/closed_loop_2888/z4q_source/CONFIG.json').read_text())


def observation(native, x, depth=750.):
    return dict(id=native, mask=f'n:{native}', box=[x, 50., x+20., 70.], area=400,
                presence=.99, score_birth=.99, neighbors=[],
                depth=dict(n=400, valid_fraction=1., median=depth, mad=2.))


def profiles(frame, observations):
    return {o['id']:dict(id=o['id'], mask=o['mask'], frame=frame,
                        core=copy.deepcopy(o['depth']), whole=copy.deepcopy(o['depth']))
            for o in observations}


def warm():
    branch = EventBridge(CONFIG)
    for frame in range(1, 11):
        obs = [observation(1, 40.), observation(2, 100., 850.), observation(3, 200., 900.)]
        view = branch.preview(frame, frame/30., obs, profiles(frame, obs))
        assert branch.commit_once(view)[0] == {1:1, 2:2, 3:3}
    return branch


def protect(branch, suppressed):
    snapshot = {k:copy.deepcopy(branch.engine.bank[k]) for k in (1, 2)}
    branch.engine.protected['TEST'] = dict(episode='TEST', generation=11,
        member_public=[1, 2], member_sources=[1, 2], suppressed=suppressed,
        outputs={n:n for n in suppressed})
    return snapshot


def main():
    branch = warm()
    snapshot = protect(branch, [1])
    view_snapshot = copy.deepcopy(branch.engine.view_bank)
    before = copy.deepcopy(vars(branch.engine))
    obs = [observation(1, 41.), observation(3, 201., 900.)]
    view = branch.preview(11, 11/30., obs, profiles(11, obs))
    assert vars(branch.engine) == before and branch.version == 10
    assert all(view['engine'].bank[k] == snapshot[k] for k in (1, 2))
    assert all(view['engine'].view_bank[k] == view_snapshot[k] for k in (1, 2))
    assert view['engine'].native_seen[1] == 11
    assert view['engine'].native_runs[1]['last_frame'] == 11
    assert view['engine'].native_runs[1]['count'] == before['native_runs'][1]['count']+1
    assert 2 not in view['engine'].native_runs  # A real absence breaks the source run.
    assert view['engine'].recent_core[1]['anchor']['frame'] == 11
    assert view['engine'].bank[1]['anchor']['frame'] == 10
    assert view['engine'].birth == before['birth']
    branch.commit_once(view)
    cert = branch.engine.certificate(1, 12, 12/30., {1:observation(1, 42.)})
    assert cert['qualified'] and cert['run']['last_frame'] == 11

    # Anonymous group and unassigned post must not become trusted pre history.
    manager = EventManager('TEST', branch, {}, dict(max_episode_seconds=10.), {})
    manager.frame_class = {1:'GROUP_MEASUREMENT'}
    manager._history_update(dict(frame=11, time=11/30., observations=obs), profiles(11, obs))
    assert not manager.clean.get(1) and manager.risk[1][-1]['observation_class']=='GROUP_MEASUREMENT'
    post = [observation(1, 42.)]
    manager.frame_class = {1:'POST_UNASSIGNED'}
    manager._history_update(dict(frame=12, time=12/30., observations=post), profiles(12, post))
    assert not manager.clean.get(1) and manager.risk[1][-1]['observation_class']=='POST_UNASSIGNED'

    # Cancellation releases the references, preserving the actual source run.
    branch.engine.protected.pop('TEST')
    obs = [observation(1, 42.), observation(2, 102., 850.), observation(3, 202., 900.)]
    view = branch.preview(12, 12/30., obs, profiles(12, obs))
    assert view['engine'].native_runs[1]['start_frame']==1
    assert view['engine'].native_runs[1]['last_frame']==12
    assert view['engine'].bank[1]['anchor']['frame']==12
    branch.commit_once(view)

    # Restore/fallback must retain an unrelated already committed alias.
    branch = warm()
    branch.engine.alias[99] = dict(target=3,
        anchor=copy.deepcopy(branch.engine.bank[3]['anchor']), commit_frame=10,
        source='SYNTHETIC_OUTSIDE_COMMIT', transaction_version=10)
    snapshot = protect(branch, [1, 2])
    obs = [observation(1, 42.), observation(2, 102., 850.), observation(99, 202., 900.)]
    view = branch.preview(11, 11/30., obs, profiles(11, obs))
    episode = dict(id='TEST', generation=11, q=11, suspect_frame=11,
        member_sources=[1, 2], group_source=1, public_ids=[1, 2], bank_snapshot=snapshot,
        post_roles={o['id']:[dict(frame=11, time=11/30., center=[o['box'][0]+10., 60.])]
                    for o in obs if o['id'] in (1, 2)})
    before = copy.deepcopy(vars(branch.engine))
    transaction, error = branch.stage_group_restore(view, episode, {1:2, 2:1})
    assert error is None and transaction['mapping']=={1:2, 2:1, 99:3}
    assert vars(branch.engine)==before
    assert transaction['engine'].alias[99]==view['engine'].alias[99]
    assert transaction['engine'].bank[3]==view['engine'].bank[3]
    assert transaction['engine'].native_seen[99]==11
    transaction, error = branch.stage_group_restore(view, episode, {1:3, 2:2})
    assert transaction is None and error=='invalid_bijection' and vars(branch.engine)==before
    transaction, detail = branch.local_fallback(view, episode)
    assert detail['status']=='LOCAL_FALLBACK_COMMITTED'
    assert transaction['mapping']==view['mapping']=={1:1, 2:2, 99:3}
    assert transaction['engine'].alias[99]==view['engine'].alias[99]
    assert transaction['engine'].bank[3]==view['engine'].bank[3]
    assert not transaction['engine'].protected and vars(branch.engine)==before
    ids, _ = branch.commit_once(view, transaction)
    assert len(ids)==len(set(ids.values()))==len(obs) and branch.version==11

    # A real alias claiming a protected target survives the preview. An event
    # cannot steal that target from an observed owner outside its selected pair.
    branch = warm()
    branch.engine.alias[500] = dict(target=1,
        anchor=copy.deepcopy(branch.engine.bank[1]['anchor']), commit_frame=10,
        source='SYNTHETIC_EXISTING_ALIAS', transaction_version=10)
    snapshot = protect(branch, [100, 101])
    obs = [observation(100, 42.), observation(101, 102., 850.), observation(500, 200.)]
    view = branch.preview(11, 11/30., obs, profiles(11, obs))
    assert view['mapping'][500]==1 and view['engine'].alias[500]['target']==1
    episode = dict(id='TEST', generation=11, q=11, member_sources=[1, 2],
        group_source=1, public_ids=[1, 2], bank_snapshot=snapshot,
        post_roles={n:[dict(frame=11, time=11/30., center=[50., 60.])] for n in (100, 101)})
    before = copy.deepcopy(vars(branch.engine))
    transaction, error = branch.stage_group_restore(view, episode, {100:1, 101:2})
    assert transaction is None and error=='occupied_target' and vars(branch.engine)==before
    print('PASS: live actual native certificates; bank/view references immutable; preview pure; anonymous histories; cancellation continuous; atomic pair restore; own-branch fallback preserves outside alias.')


if __name__=='__main__':
    main()
