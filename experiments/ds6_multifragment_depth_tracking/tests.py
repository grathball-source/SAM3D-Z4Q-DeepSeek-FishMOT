"""Focused DS6 synthetic checks; no reference pixels or tracking-score gate."""
from __future__ import annotations

import copy
import importlib.util
import math
import os
import socket
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.update(CUDA_VISIBLE_DEVICES='', OMP_NUM_THREADS='1',
                  OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common import ROOT, DS1, artifact, write_new
import measurement
import association
import numpy as np
measurement.cv2.setNumThreads(1)
from depth_state import DepthState, predict
from depth_score import geometry_choice, log_t4
from merge_split_manager import choice_mapping

spec = importlib.util.spec_from_file_location('ds6_inherited_ds1_tests', DS1/'tests.py')
old_tests = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old_tests)
sys.path.insert(0, str(HERE))


def piece(z, n=32, mad=2., key='p0'):
    return dict(piece_id=key, n=n, fraction=1., median=float(z), mad=float(mad),
                scale_mm=max(15., 1.4826*mad), qualified=True, identity='UNKNOWN')


def observed(z=1000., components=None):
    components = [piece(z)] if components is None else copy.deepcopy(components)
    return dict(fact_id='S/F6/n:10/F6', core=dict(median=float(z), mad=2.),
                core_usable=bool(components), pieces=components,
                qualified_piece_count=sum(p['qualified'] for p in components))


def history(z=1000., times=(.1, .2, .3, .4)):
    values = old_tests.fragment(list(times), [z]*len(times))
    return dict(values, cutoff_frame=5, acquired_interval_seconds=.1)


def event():
    return dict(old_tests.episode(), q=6)


class MeasurementChecks(unittest.TestCase):
    def scene(self, multimodal):
        depth = np.full((80, 100), 1200., dtype='f4')
        mask = np.zeros(depth.shape, bool)
        mask[30:38, 40:50] = True
        depth[mask] = 1000.
        if multimodal:
            depth[30:38, 40:42] = 800.
        return depth, {7: mask}, mask.astype('u2')

    def measured_scene(self, multimodal):
        depth, masks, occupancy = self.scene(multimodal)
        before = depth.copy(), masks[7].copy(), occupancy.copy()
        with patch.object(measurement, 'admission',
                          side_effect=lambda f, d: (d.copy(), {'synthetic': True})):
            result, _ = measurement.measure_frame(depth, masks, occupancy, 'S', 1, 701)
        self.assertTrue(np.array_equal(depth, before[0]))
        self.assertTrue(np.array_equal(masks[7], before[1]))
        self.assertTrue(np.array_equal(occupancy, before[2]))
        return result[7]

    def test_multiple_surfaces_no_largest_history(self):
        fact = self.measured_scene(True)
        self.assertEqual(fact['filter']['status'], 'AVAILABLE')
        self.assertEqual(fact['core']['n'], 80)
        self.assertEqual(sorted((p['n'], p['median']) for p in fact['pieces']),
                         [(16, 800.), (64, 1000.)])
        self.assertEqual(fact['qualified_piece_count'], 2)
        self.assertTrue(fact['core_usable'])
        self.assertFalse(fact['history_usable'])
        self.assertIsNone(fact['history_core']['median'])
        self.assertEqual(fact['surface_identity'], 'UNKNOWN')
        self.assertTrue(all(p['identity'] == 'UNKNOWN' for p in fact['pieces']))
        before = copy.deepcopy(fact)
        adapted = measurement.history_measurement(fact)
        self.assertEqual(fact, before)
        self.assertEqual(adapted['pieces'], fact['pieces'])
        self.assertFalse(adapted['core_usable'])
        self.assertIsNone(adapted['core']['median'])
        state = DepthState('S', 'D5')
        state.update(7, adapted, 1, .1, 8, 1, 1, 'SOURCE_OBSERVATION')
        self.assertEqual(state.updates, 0)
        self.assertEqual(state.live[7]['cache'][0]['measurement']['pieces'], fact['pieces'])

    def test_one_piece_history_alias_is_explicit(self):
        fact = self.measured_scene(False)
        self.assertEqual(fact['qualified_piece_count'], 1)
        self.assertTrue(fact['history_usable'])
        adapted = measurement.history_measurement(fact)
        self.assertEqual(adapted['core']['median'], 1000.)
        self.assertEqual(adapted['core']['piece_id'], fact['pieces'][0]['piece_id'])
        self.assertEqual(adapted['measurement_kind'], 'UNAMBIGUOUS_F6_GRAPH_PIECE_FOR_HISTORY')

    def test_actual_graph_gap_holes_and_scale(self):
        depth = np.full((4, 10), 1000., dtype='f4')
        depth[:, 5:] = 1100.
        selected = np.ones(depth.shape, bool)
        graph = measurement.pieces(depth, selected, 'S', [10, 20, 20, 24])
        self.assertEqual(sorted(p['n'] for p in graph), [20, 20])
        self.assertTrue(all(p['qualified'] for p in graph))
        self.assertEqual(sum(p['n'] for p in graph), 40)
        depth[1, 2] = 0.
        selected[1, 2] = False
        before = depth.copy(), selected.copy()
        graph = measurement.pieces(depth, selected, 'S', [10, 20, 20, 24])
        self.assertEqual(sum(p['n'] for p in graph), 39)
        self.assertTrue(np.array_equal(depth, before[0]))
        self.assertTrue(np.array_equal(selected, before[1]))
        self.assertEqual(measurement.pieces(depth, np.zeros_like(selected), 'S', [0]*4), [])
        gradient = (1000.+15.*np.arange(32, dtype='f4')).reshape(1, -1)
        graph = measurement.pieces(gradient, np.ones(gradient.shape, bool), 'G', [0, 0, 32, 1])
        self.assertEqual(len(graph), 1)
        self.assertGreater(graph[0]['scale_mm'], 60.)
        self.assertFalse(graph[0]['qualified'])

    def test_native_admission_not_aligned_range(self):
        depth = np.array([[900., 6100., 1000., 0., 1000.]], 'f4')
        native = np.array([[6000., 1000., 5000., 0., 5000.1]], 'f4')
        index = np.array([[0, 1, 2, -1, 4]], 'i4')
        opened, fields = [], []

        class Sensor:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def __getitem__(self, key):
                fields.append(key)
                if key != 'source_index': raise AssertionError(key)
                return index

        def load(path):
            opened.append(Path(path).name)
            return Sensor() if Path(path).suffix == '.npz' else native

        before = depth.copy()
        with patch.object(measurement.np, 'load', side_effect=load), \
             patch.object(measurement, 'sha', return_value='synthetic'):
            clean, info = measurement.admission(701, depth)
        self.assertEqual(opened, ['000701.npz', '000701.npy'])
        self.assertEqual(fields, ['source_index'])
        self.assertTrue(np.array_equal(depth, before))
        self.assertEqual(clean.tolist(), [[0., 6100., 1000., 0., 0.]])
        self.assertEqual(info['suspect_n'], 2)
        self.assertEqual(info['sensor_valid_range'], 'UNKNOWN')


class AssociationChecks(unittest.TestCase):
    def context(self):
        e = event()
        frozen = {'A': history(1000.), 'B': history(1200.)}
        measured = {10: observed(1000., [piece(1000.), piece(1040., key='p1')]),
                    20: observed(1200., [piece(1200.), piece(1240., key='p1')])}
        return e, frozen, measured, dict(n=200, median=1100., mad=20.)

    def test_equal_normalized_mixture_retains_all_surfaces(self):
        m = observed(1200., [piece(800., n=16), piece(1200., n=64, key='p1')])
        forecast = dict(mu_mm=800., scale_mm=15.)
        bg = dict(mu_mm=1100., scale_mm=60.)
        value = association.edge(forecast, m, bg, True)
        self.assertEqual(len(value['components']), 2)
        self.assertEqual([p['prior_weight'] for p in value['components']], [.5, .5])
        self.assertEqual([p['median_mm'] for p in value['components']], [800., 1200.])
        logs = [log_t4(z, 800., math.hypot(15., 15.))-log_t4(z, 1100., 60.)
                for z in (800., 1200.)]
        expected = float(np.logaddexp.reduce(logs)-math.log(2))
        self.assertAlmostEqual(value['log_mixture_ratio'], expected, places=13)

    def test_replicating_all_pieces_does_not_lower_cost(self):
        _, _, measured, _ = self.context()
        forecast = dict(mu_mm=1000., scale_mm=20.)
        bg = dict(mu_mm=1100., scale_mm=60.)
        first = association.edge(forecast, measured[10], bg, True)
        duplicated = copy.deepcopy(measured[10])
        duplicated['pieces'] *= 3
        duplicated['qualified_piece_count'] *= 3
        second = association.edge(forecast, duplicated, bg, True)
        self.assertAlmostEqual(first['cost'], second['cost'], places=12)
        self.assertAlmostEqual(sum(p['prior_weight'] for p in second['components']), 1.)
        measured[10]['pieces'].reverse()
        third = association.edge(forecast, measured[10], bg, True)
        self.assertAlmostEqual(first['cost'], third['cost'], places=12)

    def test_full_mass_singleton_scalar_equals_mixture(self):
        e, frozen, _, full = self.context()
        measured = {10: observed(1000.), 20: observed(1200.)}
        a, da = association.choose(e, frozen, measured, full, False)
        b, db = association.choose(e, frozen, measured, full, True)
        self.assertEqual(a, b)
        self.assertEqual(da['used_edges'], 4)
        self.assertEqual(db['used_edges'], 4)
        for choice in ('H1', 'H2'):
            self.assertEqual(da['candidates'][choice]['total_cost'], db['candidates'][choice]['total_cost'])
        plain = geometry_choice(e)[1]
        self.assertEqual([da['candidates'][p['choice']]['geometry_cost'] for p in plain['candidates']],
                         [p['geometry'] for p in plain['candidates']])

    def test_any_missing_joint_edge_exact_geometry(self):
        for missing in ('A', 'B', 'X', 'Y', 'BACKGROUND'):
            for multi in (False, True):
                with self.subTest(missing=missing, multi=multi):
                    e, frozen, measured, full = self.context()
                    if missing in ('A', 'B'): frozen[missing]['samples'] = []
                    elif missing == 'X': measured[10]['core_usable'] = False
                    elif missing == 'Y': measured[20]['qualified_piece_count'] = 0
                    else: full = dict(n=0, median=None, mad=None)
                    choice, details = association.choose(e, frozen, measured, full, multi)
                    geometry, plain = geometry_choice(e)
                    self.assertEqual(choice, geometry)
                    self.assertFalse(details['joint_available'])
                    self.assertEqual(details['used_edges'], 0)
                    self.assertTrue(all(v['cost'] == 0. for v in details['edges'].values()))
                    for p in plain['candidates']:
                        self.assertEqual(details['candidates'][p['choice']]['total_cost'], p['geometry'])

    def test_piece_and_candidate_permutation_preserve_physical_mapping(self):
        for multi in (False, True):
            e, frozen, measured, full = self.context()
            first, da = association.choose(e, frozen, measured, full, multi)
            physical = choice_mapping(e, first)
            measured = dict(reversed(list(measured.items())))
            for m in measured.values(): m['pieces'].reverse()
            e['post_roles'] = dict(reversed(list(e['post_roles'].items())))
            second, db = association.choose(e, frozen, measured, full, multi)
            self.assertEqual(choice_mapping(e, second), physical)
            self.assertEqual(da['used_edges'], db['used_edges'])
            self.assertEqual(da['history_cutoff_frames'], db['history_cutoff_frames'])

    def test_logspace_is_finite_with_wide_modes(self):
        m = observed(1000., [piece(1.), piece(1e12, key='p1')])
        value = association.edge(dict(mu_mm=1e9, scale_mm=1e8), m,
                                 dict(mu_mm=1100., scale_mm=60.), True)
        self.assertTrue(math.isfinite(value['cost']))
        self.assertTrue(math.isfinite(value['log_mixture_ratio']))


class StateChecks(unittest.TestCase):
    def test_versions_generation_public_epoch_native_and_segment(self):
        for public, epoch, generation in ((8, 1, 1), (7, 2, 1), (7, 1, 2)):
            with self.subTest(public=public, epoch=epoch, generation=generation):
                state = DepthState('S', 'D5')
                state.update(1, old_tests.measurement(), 1, .1, 7, 1, 1, 'SOURCE_OBSERVATION')
                state.update(1, old_tests.measurement(1200), 2, .2, public, epoch, generation, 'SOURCE_OBSERVATION')
                self.assertEqual([s['frame'] for s in state.live[1]['latest_fragment']], [2])
                old = state.freeze(dict(member_sources=[1, 2], public_ids=[7, 9]), 3, {1:1}, {1:1})
                self.assertEqual(old['A']['samples'], [])
                self.assertEqual(old['B']['samples'], [])
        first, second = DepthState('S1', 'D4'), DepthState('S2', 'D5')
        first.update(1, old_tests.measurement(), 1, .1, 7, 1, 1, 'SOURCE_OBSERVATION')
        self.assertEqual(second.live, {})
        self.assertIsNot(first.live, second.live)

    def test_risk_group_post_and_frozen_cutoff_do_not_join(self):
        for risky in ('QUALITY_OR_CONTACT_RISK', 'ANONYMOUS_RESIDUAL',
                      'UNRESOLVED_EVENT_OBSERVATION', 'GROUP_MEASUREMENT', 'POST_UNASSIGNED'):
            with self.subTest(risky=risky):
                state = DepthState('S', 'D5')
                for frame in (1, 2):
                    state.update(1, old_tests.measurement(), frame, frame/10, 7, 1, 1, 'SOURCE_OBSERVATION')
                frozen = state.freeze(dict(member_sources=[1, 2], public_ids=[7, 8]), 3)
                before = copy.deepcopy(frozen)
                state.update(1, old_tests.measurement(9000), 3, .3, 7, 1, 1, risky)
                self.assertEqual(state.updates, 2)
                self.assertEqual(list(state.live[1]['samples']), [])
                state.update(1, old_tests.measurement(1100), 4, .4, 7, 1, 1, 'RESTORED_POST')
                self.assertEqual([s['frame'] for s in state.live[1]['samples']], [4])
                self.assertEqual(state.updates, 3)
                self.assertEqual(frozen, before)
                self.assertEqual(frozen['A']['cutoff_frame'], 2)

    def test_invalid_multi_surface_breaks_and_window_expires(self):
        state = DepthState('S', 'D5')
        state.update(1, old_tests.measurement(), 1, .1, 7, 1, 1, 'SOURCE_OBSERVATION')
        state.update(1, old_tests.measurement(valid=False), 2, .2, 7, 1, 1, 'SOURCE_OBSERVATION')
        e = dict(member_sources=[1, 2], public_ids=[7, 8])
        self.assertEqual([s['frame'] for s in state.freeze(e, 3)['A']['samples']], [1])
        self.assertEqual(state.freeze(e, 32)['A']['samples'], [])
        state.update(1, old_tests.measurement(1200), 3, .3, 7, 1, 1, 'SOURCE_OBSERVATION')
        self.assertEqual([s['frame'] for s in state.live[1]['latest_fragment']], [3])

    def test_actual_time_wls_and_singleton_unknown_slope(self):
        times = [1e9+t for t in (0., .07, .15, .32, .51)]
        fragment = old_tests.fragment(times, [1000.+80.*(t-times[-1]) for t in times])
        forecast = predict(fragment, times[-1]+1.5)
        self.assertEqual(forecast['status'], 'WLS_LINEAR_TIME')
        self.assertAlmostEqual(forecast['slope_mm_s'], 80., places=6)
        self.assertAlmostEqual(forecast['mu_mm'], 1120., places=5)
        self.assertEqual(forecast['delta_seconds'], 1.5)
        self.assertGreater(forecast['scale_mm'], predict(fragment, times[-1]+.1)['scale_mm'])
        short = dict(old_tests.fragment([1.], [1000.]), acquired_interval_seconds=.1)
        forecast = predict(short, 1.5)
        self.assertEqual(forecast['status'], 'NO_SLOPE_LAST_VALUE')
        self.assertIsNone(forecast['slope_mm_s'])
        self.assertEqual(forecast['fallback'], 'OBSERVED_ACQUISITION_INTERVAL')


def main():
    suite = unittest.TestSuite()
    for checks in (MeasurementChecks, AssociationChecks, StateChecks):
        suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(checks))
    # Read the inherited actual assertions: failed staging must leave engine intact;
    # successful q commits one bijection and a second commit raises.
    for name in ('test_failed_preview_atomic_and_local_fallback',
                 'test_single_post_atomic_first_publish'):
        suite.addTest(old_tests.DepthTests(name))
    began = time.perf_counter()
    with patch.object(socket.socket, 'connect', side_effect=AssertionError('DS6 checks offline')):
        result = unittest.TextTestRunner(verbosity=2).run(suite)
    record = dict(status='PASS' if result.wasSuccessful() else 'FAIL',
                  passed=result.wasSuccessful(), tests=result.testsRun,
                  seconds=time.perf_counter()-began, failures=len(result.failures),
                  errors=len(result.errors), skipped=len(result.skipped),
                  opencv_threads=measurement.cv2.getNumThreads(), native_math_threads=1,
                  actual_functions=['measurement.pieces', 'measurement.admission',
                                    'measurement.measure_frame', 'measurement.history_measurement',
                                    'association.edge', 'association.choose',
                                    'DS1.DepthState', 'DS1.predict', 'inherited publication/atomic fixtures'],
                  synthetic_only=True, GT_reads=0, network_api=0, tracking_metrics_asserted=False,
                  inputs=[artifact(p) for p in (HERE/'tests.py', HERE/'measurement.py',
                          HERE/'association.py', HERE/'common.py', HERE/'CONFIG.json',
                          DS1/'tests.py', DS1/'depth_state.py', DS1/'depth_score.py')],
                  failure_details=[dict(test=str(test), trace=trace)
                                   for test, trace in result.failures+result.errors])
    # Leave failures in output for repair; write the exclusive acceptance only after success.
    if result.wasSuccessful(): write_new(HERE/'UNIT_CHECKS.json', record)
    else: print(record, file=sys.stderr)
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
