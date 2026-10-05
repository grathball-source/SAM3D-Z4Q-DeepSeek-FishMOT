"""Synthetic DS31 identity contracts; no data, GT, models or services."""
from common import *
import copy
from datetime import datetime, timezone
import unittest
import numpy as np
from pycocotools import mask as coco
from identity import Identity, match


def observation(native, x, area=400, neighbors=()):
    width = 20
    height = area // width
    return dict(id=native, mask=f'n:{native}', box=[x, 30, x+width, 30+height],
        area=area, presence=.99, score_birth=.99, neighbors=list(neighbors))


def inputs(frame, objects, usable=True):
    now = frame/10
    row = dict(frame=frame, global_frame=frame, time=now, observations=objects)
    masks, facts = {}, {}
    for o in objects:
        raster = np.zeros((120, 320), dtype=np.uint8)
        x0, y0, x1, y1 = o['box']
        raster[y0:y1, x0:x1] = 1
        rle = coco.encode(np.asfortranarray(raster))
        masks[o['mask']] = dict(size=rle['size'], counts=rle['counts'].decode('ascii'))
        native = o['id']
        view = dict(fact_id=f'S/F{frame}/n:{native}/core/raw',
            eligible_single=usable, quality_usable=usable,
            source_ownership_exclusive=True, source_population_unverified_n=0,
            status='SINGLE_COMPATIBLE_LAYER', reason='SYNTHETIC',
            mixture_flag=False, independent_mixture_flag=False, inclusive_mixture_flag=False,
            substantial_layer_count=1, inclusive_substantial_layer_count=1,
            summary=dict(n=o['area'], area=o['area'], valid_fraction=1.,
                         median=1000.+native, mad=2.),
            roi_definition='DS12_EXACT_L2_EXCLUSIVE_COMPONENT_ADAPTIVE_CORE',
            roi_binding=dict(sha256='a'*64), selected_source_index_binding=dict(sha256='b'*64))
        whole = copy.deepcopy(view)
        whole['fact_id'] = f'S/F{frame}/n:{native}/whole/raw'
        whole['roi_definition'] = 'ORIGINAL_FULL_MASK'
        facts[str(native)] = dict(schema='DS18_SAME_ROI_RAW_MEASUREMENT_V1',
            no_cross_ROI_certification=True, core=view, whole=whole,
            fact_id=f'S/F{frame}/n:{native}/mixed/raw', certificate_sha256='c'*64,
            native=native, frame=frame, time=now)
    packet = dict(objects=facts, full_frame=dict(n=1000, median=1100., mad=30.))
    return row, {}, dict(masks=masks), packet


def advance(branch, frame, objects, usable=True):
    return branch.commit(branch.preview(*inputs(frame, objects, usable)))


def warm(arm='PID_MOTION', suspects=None):
    branch = Identity(arm, suspects or {})
    for frame in range(1, 6):
        advance(branch, frame, [observation(1, 10), observation(2, 170)])
    assert all(branch.bank[k]['established'] for k in (1, 2))
    return branch


class Checks(unittest.TestCase):
    def test_native_return_does_not_reclaim_persistent_alias(self):
        branch = warm()
        mapping, _ = advance(branch, 6, [observation(101, 12), observation(102, 172)])
        self.assertEqual(mapping, {101: 1, 102: 2})
        self.assertEqual(branch.bank[1]['anchor']['native_id'], 101)
        mapping, _ = advance(branch, 7, [observation(101, 14), observation(1, 270)])
        self.assertEqual(mapping[101], 1)
        self.assertNotEqual(mapping[1], 1)
        self.assertEqual(len(set(mapping.values())), 2)
        self.assertEqual(branch.bank[1]['anchor']['native_id'], 101)
        self.assertEqual(branch.sources[101]['pid'], 1)
        self.assertNotEqual(branch.sources[1]['pid'], 1)
        mapping, _ = advance(branch, 8, [observation(101, 16), observation(1, 272)])
        self.assertEqual(mapping[101], 1)

    def test_generation_and_risk_break_clean_fragments(self):
        branch = warm()
        before = copy.deepcopy(branch.bank[1])
        advance(branch, 6, [observation(1, 12, neighbors=[2]), observation(2, 172, neighbors=[1])])
        for field in ('motion', 'depth', 'anchor', 'rle'):
            self.assertEqual(branch.bank[1][field], before[field])
        advance(branch, 7, [observation(1, 12), observation(2, 172)])
        self.assertEqual([s['frame'] for s in branch.bank[1]['motion']], [7])
        self.assertEqual([s['frame'] for s in branch.bank[1]['depth']], [7])
        advance(branch, 8, [observation(2, 172)])
        old_generation = branch.sources[1]['generation']
        advance(branch, 9, [observation(1, 12), observation(2, 172)])
        self.assertEqual(branch.sources[1]['generation'], old_generation+1)
        self.assertEqual([s['frame'] for s in branch.bank[1]['motion']], [9])
        self.assertEqual([s['frame'] for s in branch.bank[1]['depth']], [9])
        self.assertEqual(branch.bank[1]['motion'][0]['version'], [1, old_generation+1, 1])

    def test_group_without_neighbors_never_updates_member_references(self):
        hit = {6: [dict(sources=[1, 2], group=1)]}
        branch = warm(suspects=hit)
        saved = {k: copy.deepcopy(branch.bank[k]) for k in (1, 2)}
        mapping, trace = advance(branch, 6, [observation(1, 10, area=800)])
        self.assertEqual(mapping, {1: 1})
        self.assertEqual(trace['risk_sources'], [1, 2])
        self.assertEqual({k: branch.bank[k] for k in (1, 2)}, saved)
        mapping, _ = advance(branch, 7, [observation(1, 10, area=800)])
        self.assertEqual(mapping, {1: 1})
        self.assertEqual({k: branch.bank[k] for k in (1, 2)}, saved)

    def test_anonymous_group_source_is_not_promoted_to_individual_bank(self):
        branch = warm(suspects={6: [dict(sources=[1, 2], group=99)]})
        saved = {k: copy.deepcopy(branch.bank[k]) for k in (1, 2)}
        for frame in range(6, 10):
            mapping, trace = advance(branch, frame, [observation(99, 10, area=800)])
            self.assertEqual({k: branch.bank[k] for k in (1, 2)}, saved)
            group_pid = mapping[99]
            self.assertFalse(branch.sources[99]['established'])
            self.assertTrue(group_pid not in branch.bank or
                not branch.bank[group_pid]['motion'] and not branch.bank[group_pid]['depth'])
            self.assertIn(99, trace['risk_sources'])

    def test_first_split_decides_before_publish_and_keeps_residual_occupancy(self):
        branch = warm(suspects={6: [dict(sources=[1, 2], group=1)]})
        merged=observation(1,10,area=3600);merged['box']=[10,30,192,50]
        advance(branch, 6, [merged])
        objects = [observation(1, 10, area=80), observation(101, 12), observation(102, 172)]
        before = digest(branch.state())
        view = branch.preview(*inputs(7, objects))
        self.assertEqual(digest(branch.state()), before)
        self.assertEqual(view['mapping'][102], 2)
        self.assertEqual(view['mapping'][1], 1)
        self.assertNotIn(view['mapping'][101], (1, 2))
        # Frozen DS31 policy keeps the existing residual claim. Its target is
        # therefore excluded, rather than pretending both fish were restored.
        self.assertNotIn(1, view['trace']['candidate_pids'])
        self.assertIn(1, view['trace']['risk_sources'])
        self.assertEqual(set(view['mapping']), {1, 101, 102})
        self.assertEqual(len(set(view['mapping'].values())), 3)
        self.assertTrue(view['trace']['decided_before_first_publish'])
        self.assertTrue(view['trace']['all_masks_retained'])
        self.assertTrue(view['trace']['first_split_events'])
        mapping, _ = branch.commit(view)
        self.assertEqual(mapping, view['mapping'])
        mapping, _ = advance(branch, 8, objects)
        self.assertEqual(set(mapping), {1, 101, 102})
        self.assertEqual(len(set(mapping.values())), 3)

    def test_clear_suspect_is_never_reported_as_confirmed_merge(self):
        branch = warm(suspects={6: [dict(sources=[1, 2], group=1)]})
        objects = [observation(1, 10), observation(2, 170)]
        advance(branch, 6, objects)
        mapping, trace = advance(branch, 7, objects)
        self.assertEqual(mapping, {1: 1, 2: 2})
        self.assertIsNone(branch.events[0]['confirm_frame'])
        self.assertFalse(any(a['previous_pid'] != a['target'] for a in trace['actions']))

    def test_unknown_depth_exactly_preserves_motion_mapping_and_state(self):
        branches = [warm(arm) for arm in ('PID_MOTION', 'PID_DEPTH')]
        # Both targets remain feasible; the different overlaps avoid exact ties.
        for branch in branches:
            branch.bank[2]['last']['box'] = [70, 30, 90, 50]
            branch.bank[2]['motion'] = [dict(s, center=[80., 40.]) for s in branch.bank[2]['motion']]
        for frame in range(6, 9):
            objects = [observation(101, 25), observation(102, 60)]
            values = [advance(branch, frame, objects, usable=False) for branch in branches]
            self.assertEqual(values[0][0], values[1][0])
            self.assertEqual(digest(branches[0].state()), digest(branches[1].state()))
            self.assertEqual(values[0][1]['cost'], values[1][1]['cost'])
            self.assertTrue(all(not r.get('used', False) for r in values[1][1]['depth_rows']))

    def test_preview_is_atomic_and_double_commit_rejected(self):
        branch = warm()
        args = inputs(6, [observation(101, 12), observation(102, 172)])
        args_before = digest(args)
        before = digest(branch.state())
        first, second = branch.preview(*args), branch.preview(*args)
        self.assertEqual(digest(branch.state()), before)
        self.assertEqual(digest(args), args_before)
        self.assertEqual(first['mapping'], second['mapping'])
        self.assertEqual(digest(first['trial'].state()), digest(second['trial'].state()))
        branch.commit(first)
        committed = digest(branch.state())
        with self.assertRaises(AssertionError): branch.commit(first)
        with self.assertRaises(AssertionError): branch.commit(second)
        self.assertEqual(digest(branch.state()), committed)

    def test_non_tie_candidate_and_observation_order_invariant(self):
        branches = [warm(), warm()]
        branches[1].bank = dict(reversed(list(branches[1].bank.items())))
        branches[1].sources = dict(reversed(list(branches[1].sources.items())))
        objects = [observation(101, 12), observation(102, 172)]
        a = advance(branches[0], 6, objects)
        b = advance(branches[1], 6, list(reversed(objects)))
        self.assertEqual(a[0], {101: 1, 102: 2})
        self.assertEqual(a[0], b[0])
        self.assertEqual(digest(branches[0].state()), digest(branches[1].state()))
        self.assertTrue(all(x['margin']>.15 for x in a[1]['actions']))

    def test_motion_zero_iou_search_and_global_dummy_occupancy(self):
        branch = warm()
        mapping, trace = advance(branch, 6, [observation(101, 35)])
        self.assertEqual(mapping[101], 1)
        action = trace['actions'][0]
        self.assertEqual(action['geometry']['mask_iou'], 0.)
        self.assertLess(action['geometry']['distance_px'], action['geometry']['radius_px'])
        chosen, detail = match(np.array([[.1], [.3]]), np.ones((2, 1), dtype=bool))
        self.assertEqual([(i, j) for i, j, _ in chosen], [(0, 0)])
        self.assertEqual(detail['dummy_cost'], 1.)

    def test_unreliable_current_observation_cannot_claim_old_identity(self):
        for condition in ('score', 'area'):
            branch = warm()
            current = observation(101, 12, area=60 if condition == 'area' else 400)
            if condition == 'score': current['score_birth'] = .1
            self.assertFalse(branch.clean(current, 1))
            before = copy.deepcopy(branch.bank[1])
            mapping, trace = advance(branch, 6, [current])
            self.assertNotEqual(mapping[101], 1, condition)
            self.assertFalse(any(a['target'] == 1 for a in trace['actions']), condition)
            self.assertEqual(branch.bank[1], before)


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Checks))
    path = HERE/'checks'/('CHECKS_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.json')
    write_new(path, dict(status='PASS' if result.wasSuccessful() else 'FAIL', tests=result.testsRun,
        failures=[dict(test=str(test), detail=detail) for test, detail in result.failures],
        errors=[dict(test=str(test), detail=detail) for test, detail in result.errors],
        synthetic_not_research_success=True, no_external_inputs=True, new_model_http=0, cost_usd=0))
    print(path)
    if not result.wasSuccessful(): raise SystemExit(1)
