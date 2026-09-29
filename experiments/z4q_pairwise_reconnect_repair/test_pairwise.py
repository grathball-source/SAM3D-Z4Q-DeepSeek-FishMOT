"""Focused causal checks for the new edge exclusion cache."""
import copy
import inspect
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE / 'source'))
from co_visibility_exclusion import CoVisibilityExclusion, coco  # noqa: E402
from px_d1 import DepthRepair  # noqa: E402
from px_z2 import BirthRefine  # noqa: E402


def observation(n, x, generation='g', duplicate=False):
    m = np.zeros((64, 64), np.uint8)
    m[10:19, x:x+9] = 1
    rle = coco.encode(np.asfortranarray(m))
    return dict(id=n, mask=f'n:{n}', box=[x, 10, x+9, 19], area=81,
                neighbors=[], pairwise_generation=generation,
                pairwise_rle=dict(size=rle['size'], counts=rle['counts'].decode('ascii')),
                depth=dict(n=81, valid_fraction=1, median=1000, mad=1), score_birth=.9,
                duplicate=duplicate)


class Engine:
    def __init__(self):
        self.bank = {}
        self.alias = {}
        self.retired = set()

    def quality(self, o):
        return o['area'] >= 64

    def depth_valid(self, o):
        return o['depth']['n'] >= 5


def tick(cache, engine, frame, obs):
    cache.prepare(frame, frame/30, obs, engine)
    for o in obs:
        engine.bank[o['id']] = dict(anchor=dict(frame=frame, native_id=o['id'],
                                                canonical_id=o['id'], mask=o['mask']), areas=[81])
    cache.finish(frame, frame/30, obs, {o['id']: o['id'] for o in obs}, engine)


def main():
    checks = []
    cache, engine = CoVisibilityExclusion(5), Engine()
    for f in range(1, 6):
        tick(cache, engine, f, [observation(1, 1), observation(2, 30)])
    cache.prepare(6, .2, [observation(1, 1), observation(3, 48)], engine)
    anchor = engine.bank[2]['anchor']
    blocked = cache.check(1, 2, anchor, 'D1_DELAYED')
    assert blocked['veto'] and blocked['evidence_frames'] == [1, 2, 3, 4, 5]
    assert not cache.check(3, 2, anchor, 'BIRTH_REFINE')['veto']
    checks += ['confirmed_separate_pair_only_one_edge', 'newborn_without_history_not_blocked']
    sibling = copy.deepcopy(cache)
    sibling.pairs.clear()
    assert cache.check(1, 2, anchor, 'D1_DELAYED')['veto']
    checks.append('branch_cache_copy_on_write')

    duplicate, engine2 = CoVisibilityExclusion(5), Engine()
    for f in range(1, 6):
        tick(duplicate, engine2, f, [observation(1, 1), observation(2, 1)])
    duplicate.prepare(6, .2, [observation(1, 1)], engine2)
    assert not duplicate.check(1, 2, engine2.bank[2]['anchor'], 'D1_DELAYED')['veto']
    checks.append('duplicate_masks_not_distinct')

    changed, engine3 = CoVisibilityExclusion(5), Engine()
    for f in range(1, 6):
        generation = 'g' if f < 4 else 'next_batch'
        tick(changed, engine3, f, [observation(1, 1, generation), observation(2, 30, generation)])
    changed.prepare(6, .2, [observation(1, 1, 'next_batch')], engine3)
    assert not changed.check(1, 2, engine3.bank[2]['anchor'], 'D1_DELAYED')['veto']
    checks.append('source_generation_breaks_pair_streak')

    assert 'edge_veto' in inspect.getsource(DepthRepair.step)
    assert 'edge_veto' in inspect.getsource(BirthRefine.step)
    checks.append('both_real_assignment_paths_call_shared_hook')

    from run import MANIFEST, feed, new_bridge, read, state_sha
    item = read(MANIFEST)['segments']['SOURCE_OLD']['feeding_000000_000199']
    bridge = new_bridge()
    for row, profiles, assignment, obs in feed(item):
        if row['global_frame'] == 159:
            original = state_sha(bridge)
            preview = bridge.preview(row['frame'], row['time'], obs, profiles)
            assert state_sha(bridge) == original
            assert preview['mapping'][26] == 16
            trial = copy.deepcopy(bridge)
            hook = trial.engine.edge_veto
            def one_edge(frame, now, observation, public, anchor, origin_rule):
                result = hook(frame, now, observation, public, anchor, origin_rule)
                if (origin_rule, observation['id'], public) == ('D1_DELAYED', 26, 16):
                    result.update(veto=True, status='EXCLUDED', reason='TEST_ONLY_EXPLICIT_EDGE')
                return result
            trial.engine.edge_veto = one_edge
            limited_mapping, limited_trace = trial.engine.step(row['frame'], row['time'], obs, profiles)
            assert limited_mapping[26] == 26
            assert any(e['native_id'] == 26 and e['canonical_id'] == 16
                       and e['rejection'] == 'pairwise_history_conflict' for e in limited_trace['edges'])
            assert state_sha(bridge) == original
            checks.append('real_F159_single_edge_veto_keeps_dummy_and_preview_isolation')
            break
        view = bridge.preview(row['frame'], row['time'], obs, profiles)
        bridge.commit_once(view)
    print(json.dumps(dict(status='PASS', checks=checks), ensure_ascii=False))


if __name__ == '__main__':
    main()
