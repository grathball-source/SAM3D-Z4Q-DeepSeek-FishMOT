"""Focused real-controller checks; synthetic observations, no GT or services."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import io
import json
import os
import sys
import time
import unittest
from pathlib import Path

os.environ.update(CUDA_VISIBLE_DEVICES='', OMP_NUM_THREADS='1',
                  OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('ds7_native_controller', HERE/'controller.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
DepthNativeBridge, DepthNativeManager = module.DepthNativeBridge, module.DepthNativeManager

import numpy as np
import cv2
cv2.setNumThreads(1)
from pycocotools import mask as coco
from test_ne import CONFIG, observation


def protect(bridge, post, episode_id='TEST', members=(7, 8), targets=(7, 8), q=2):
    episode = dict(id=episode_id, generation=q, q=q, member_sources=list(members),
        group_source=members[0], public_ids=list(targets),
        bank_snapshot={k:copy.deepcopy(bridge.engine.bank[k]) for k in targets},
        post_roles={n:[dict(frame=q, time=1.+.1*(q-1), center=[10.,10.])]
                    for n in post})
    bridge.engine.protected[episode_id] = dict(episode=episode_id, generation=q,
        member_public=list(targets), member_sources=list(members),
        suppressed=list(post), outputs=dict(zip(post, targets)))
    return episode


def fixture(outside=False, alias_outside=False, post=(100,101)):
    bridge = DepthNativeBridge(CONFIG)
    initial = [observation(7,0), observation(8,100)]
    if outside or alias_outside:
        initial.append(observation(9,200))
    bridge.commit_once(bridge.preview(1,1.,initial,{}))
    observations = [observation(post[0],3), observation(post[1],103)]
    if outside:
        observations.append(observation(9,201))
    if alias_outside:
        bridge.engine.alias[199] = dict(target=9,
            anchor=copy.deepcopy(bridge.engine.bank[9]['anchor']), commit_frame=1,
            source='MS1_GROUP_RESTORE', transaction_version=1)
        observations.append(observation(199,201))
    episode = protect(bridge, post)
    view = bridge.preview(2,1.1,observations,{})
    return bridge, view, episode


def encoded(observations):
    result = {}
    for o in observations:
        x1,y1,x2,y2 = map(int,o['box'])
        image = np.zeros((360,640),np.uint8)
        image[y1:y2,x1:x2] = 1
        rle = coco.encode(np.asfortranarray(image))
        rle['counts'] = rle['counts'].decode('ascii')
        result[o['mask']] = rle
    return dict(masks=result)


def manager_sequence(new_carrier=False):
    initial = [observation(7,0), observation(8,100), observation(9,200)]
    group = dict(observation(7,0),box=[0.,0.,120.,20.],area=2400)
    third = dict(group, id=100, mask='n:100') if new_carrier else group
    last = ([observation(100,0), observation(8,100), observation(9,200)]
            if new_carrier else [observation(7,0), observation(100,100), observation(9,200)])
    records = [initial, [group,observation(9,200)],
               [third,observation(9,200)], last]
    assignments = {i:encoded(o) for i,o in enumerate(records,1)}
    bridge = DepthNativeBridge(CONFIG)
    suspects = {2:dict(sources=[7,8],group=7,donor=8,
                       donor_reference_area=400,group_reference_area=400)}
    manager = DepthNativeManager('P0',bridge,suspects,
                                dict(max_episode_seconds=10.),assignments)
    return bridge, manager, records


class ControllerTests(unittest.TestCase):
    def test_no_event_native_equivalence_and_all_masks(self):
        bridge = DepthNativeBridge(CONFIG)
        for frame in range(1,5):
            observations = [observation(7,frame),observation(8,100+frame)]
            if frame > 1:
                observations.append(observation(100,200))
            ids,trace = bridge.commit_once(bridge.preview(frame,frame/10.,observations,{}))
            self.assertEqual(ids,{o['id']:o['id'] for o in observations})
            self.assertEqual(len(ids),len(set(ids.values())))
            self.assertFalse(bridge.engine.alias)
            self.assertFalse(trace['publication_effects']['overrides_against_native'])

    def test_real_manager_protects_banks_and_noaction_matches_native(self):
        bridge,manager,records = manager_sequence()
        protected = None
        for frame,observations in enumerate(records,1):
            row = dict(frame=frame,time=1.+frame/10.,observations=observations)
            manager.before(row,{})
            episode = manager.active
            if frame == 2:
                protected = copy.deepcopy(episode['bank_snapshot'])
            view = bridge.preview(frame,row['time'],observations,{})
            if episode:
                for k,bank in protected.items():
                    self.assertEqual(view['engine'].bank[k],bank)
                self.assertEqual(view['engine'].protected[episode['id']]['outputs'],
                    {n:view['mapping'][n] for n in view['engine'].protected[episode['id']]['suppressed']})
                self.assertTrue(all(s['frame']==1 for s in episode['pre']['A']))
            transaction = None
            if episode and episode['q'] == frame:
                self.assertEqual(frame,4)
                transaction,_ = bridge.local_fallback(view,episode)
                manager.finish(frame,'LOCAL_FALLBACK_COMMITTED')
            ids,_ = bridge.commit_once(view,transaction)
            self.assertEqual(ids,{o['id']:o['id'] for o in observations})
            manager.after(row,{})
        self.assertFalse(bridge.engine.protected)
        self.assertFalse(bridge.engine.alias)

    def test_new_group_carrier_does_not_borrow_member_public(self):
        bridge,manager,records = manager_sequence(new_carrier=True)
        for frame,observations in enumerate(records[:3],1):
            row = dict(frame=frame,time=1.+frame/10.,observations=observations)
            manager.before(row,{})
            view = bridge.preview(frame,row['time'],observations,{})
            if frame == 3:
                self.assertEqual(manager.active['group_source'],100)
                self.assertEqual(view['mapping'][100],100)
                self.assertEqual(bridge.engine.protected[manager.active['id']]['outputs'][100],100)
            bridge.commit_once(view)
            manager.after(row,{})

    def test_q_preview_is_lawful_then_h2_first_publish_once(self):
        bridge,view,episode = fixture(outside=True)
        self.assertEqual(view['mapping'],{100:100,101:101,9:9})
        previous = dict(bridge.previous)
        transaction,error = bridge.stage_group_restore(view,episode,{100:8,101:7})
        self.assertIsNone(error)
        self.assertEqual(bridge.previous,previous)
        self.assertEqual(transaction['changes'],{100:8,101:7})
        ids,trace = bridge.commit_once(view,transaction)
        self.assertEqual(ids,{100:8,101:7,9:9})
        self.assertEqual(trace['publication_effects']['overrides_against_native'],{100:8,101:7})
        self.assertEqual(bridge.provenance[100]['source'],'F9_EVENT_NUMERIC')
        self.assertEqual({n:v['target'] for n,v in bridge.engine.alias.items()}, {100:8,101:7})
        with self.assertRaises(AssertionError):
            bridge.commit_once(view,transaction)
        next_ids,_ = bridge.commit_once(bridge.preview(3,1.2,
            [observation(100,5),observation(101,105),observation(9,202)],{}))
        self.assertEqual(next_ids,ids)

    def test_continuous_swap_is_real_change_not_nochange(self):
        bridge,view,episode = fixture(post=(7,8))
        self.assertEqual(view['mapping'],{7:7,8:8})
        transaction,error = bridge.stage_group_restore(view,episode,{7:8,8:7})
        self.assertIsNone(error)
        self.assertEqual(transaction['changes'],{7:8,8:7})
        ids,trace = bridge.commit_once(view,transaction)
        self.assertEqual(trace['publication_effects']['existing_source_changes_against_previous'],ids)

    def test_true_nochange_is_separate_from_new_source_publication(self):
        bridge,view,episode = fixture(post=(7,8))
        transaction,error = bridge.stage_group_restore(view,episode,{7:7,8:8})
        self.assertIsNone(error)
        self.assertFalse(transaction['changes'])
        ids,trace = bridge.commit_once(view,transaction)
        self.assertEqual(ids,{7:7,8:8})
        self.assertFalse(trace['publication_effects']['existing_source_changes_against_previous'])
        self.assertFalse(trace['publication_effects']['new_source_publications'])
        self.assertFalse(trace['publication_effects']['overrides_against_native'])

    def test_invalid_stage_is_atomic_and_fallback_is_own_causal_state(self):
        bridge,view,episode = fixture(outside=True)
        saved = copy.deepcopy(bridge.engine.__dict__)
        transaction,error = bridge.stage_group_restore(view,episode,{100:8,101:8})
        self.assertIsNone(transaction)
        self.assertEqual(error,'invalid_bijection')
        self.assertEqual(bridge.engine.__dict__,saved)
        outside = copy.deepcopy(view['engine'].bank[9])
        fallback,detail = bridge.local_fallback(view,episode)
        self.assertFalse(detail['copies_other_branch'])
        self.assertEqual(fallback['mapping'],view['mapping'])
        self.assertEqual(fallback['engine'].bank[9],outside)
        self.assertFalse(fallback['engine'].protected)
        self.assertFalse(fallback['changes'])
        ids,_ = bridge.commit_once(view,fallback)
        self.assertEqual(ids,{100:100,101:101,9:9})

    def test_fallback_keeps_outside_committed_alias(self):
        bridge,view,episode = fixture(alias_outside=True)
        alias = copy.deepcopy(bridge.engine.alias[199])
        outside = copy.deepcopy(view['engine'].bank[9])
        self.assertEqual(view['mapping'][199],9)
        fallback,_ = bridge.local_fallback(view,episode)
        self.assertEqual(fallback['engine'].alias[199],alias)
        self.assertEqual(fallback['engine'].bank[9],outside)
        ids,_ = bridge.commit_once(view,fallback)
        self.assertEqual(ids,{100:100,101:101,199:9})

    def test_occupied_outside_native_target_is_rejected_atomically(self):
        bridge,view,episode = fixture()
        observations = [observation(100,3),observation(101,103),observation(7,200)]
        view = bridge.preview(2,1.1,observations,{})
        saved = copy.deepcopy(bridge.engine.__dict__)
        transaction,error = bridge.stage_group_restore(view,episode,{100:7,101:8})
        self.assertIsNone(transaction)
        self.assertEqual(error,'occupied_target')
        self.assertEqual(bridge.engine.__dict__,saved)
        fallback,_ = bridge.local_fallback(view,episode)
        self.assertEqual(fallback['mapping'],{100:100,101:101,7:7})
        self.assertEqual(len(fallback['mapping']),len(set(fallback['mapping'].values())))

    def test_member_alias_qualified_native_return_uses_full_legal_lifecycle(self):
        bridge,_,_ = fixture()
        bridge.engine.protected.clear()
        bridge.engine.alias[100] = dict(target=7,
            anchor=copy.deepcopy(bridge.engine.bank[7]['anchor']),commit_frame=1,
            source='MS1_GROUP_RESTORE',transaction_version=1)
        episode = protect(bridge,(100,101),members=(100,8))
        view = bridge.preview(2,1.1,
            [observation(100,3),observation(101,103),observation(7,200)],{})
        self.assertEqual(view['mapping'],{100:100,101:101,7:7})
        # Protected member facts stay frozen even when a legal outside return
        # changes the current publication. On release the causal veto persists.
        self.assertEqual(view['engine'].alias[100]['target'],7)
        self.assertTrue(view['trace']['native_return_checks'][0]['qualified'])
        transaction,error = bridge.stage_group_restore(view,episode,{100:7,101:8})
        self.assertIsNone(transaction)
        self.assertEqual(error,'occupied_target')
        fallback,_ = bridge.local_fallback(view,episode)
        self.assertNotIn(100,fallback['engine'].alias)
        self.assertEqual(fallback['mapping'],view['mapping'])

    def test_low_quality_co_visible_native_keeps_incumbent_alias_and_mask(self):
        bridge,_,_ = fixture()
        bridge.engine.protected.clear()
        bridge.engine.alias[100] = dict(target=7,
            anchor=copy.deepcopy(bridge.engine.bank[7]['anchor']),commit_frame=1,
            source='MS1_GROUP_RESTORE',transaction_version=1)
        episode = protect(bridge,(100,101),members=(100,8))
        low = dict(observation(7,200),area=20)
        view = bridge.preview(2,1.1,[observation(100,3),observation(101,103),low],{})
        self.assertEqual(view['mapping'],{100:7,101:101,7:-8})
        self.assertEqual(len(view['mapping']),3)
        fallback,_ = bridge.local_fallback(view,episode)
        self.assertEqual(fallback['engine'].alias[100]['target'],7)
        ids,_ = bridge.commit_once(view,fallback)
        self.assertEqual(ids,view['mapping'])
        self.assertEqual(len(set(ids.values())),3)

    def test_stale_stage_and_fallback_rejected(self):
        bridge,view,episode = fixture()
        bridge.commit_once(view)
        transaction,error = bridge.stage_group_restore(view,episode,{100:8,101:7})
        self.assertIsNone(transaction)
        self.assertEqual(error,'stale_episode')
        with self.assertRaises(AssertionError):
            bridge.local_fallback(view,episode)

    def test_preview_is_pure_and_frozen_keys_keep_separate_domains(self):
        bridge,view,episode = fixture(alias_outside=True)
        saved = copy.deepcopy(bridge.engine.__dict__)
        again = bridge.preview(2,1.1,view['observations'],{})
        self.assertEqual(bridge.engine.__dict__,saved)
        self.assertEqual(again['mapping'],view['mapping'])
        for k,bank in episode['bank_snapshot'].items():
            self.assertEqual(again['engine'].bank[k],bank)
        self.assertEqual(again['engine'].alias[199]['target'],9)


def main():
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ControllerTests)
    names = [test.id() for test in suite]
    buffer = io.StringIO()
    began = time.perf_counter()
    result = unittest.TextTestRunner(stream=buffer,verbosity=2).run(suite)
    print(buffer.getvalue())
    if not result.wasSuccessful():
        raise SystemExit(1)
    if '--write-new' in sys.argv:
        paths = [HERE/'controller.py',HERE/'controller_tests.py']
        report = dict(status='PASS',tests=result.testsRun,assertions=names,
            elapsed_seconds=time.perf_counter()-began,
            real_controller_functions=True,synthetic_observations=True,
            old_files_changed=False,new_tracker_performance_run=False,
            gt_or_rgb_read=False,new_model_http=0,
            native_math_threads=1,opencv_threads=cv2.getNumThreads(),
            modules={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
            provenance_note='New accepted transaction provenance is F9_EVENT_NUMERIC; inherited old sources remain unchanged.',
            interpretation='Engineering invariants only; no proof of correct depth-surface identity or tracking benefit.')
        with (HERE/'CONTROLLER_CHECKS.json').open('x',encoding='utf-8',newline='\n') as handle:
            json.dump(report,handle,ensure_ascii=False,indent=2,allow_nan=False)
            handle.write('\n')


if __name__ == '__main__':
    main()
