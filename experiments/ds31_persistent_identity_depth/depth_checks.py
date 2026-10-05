"""Focused DS31 depth contracts; synthetic inputs, no GT, pixels or services."""
import copy
import math
import unittest

import depth


def fact(z=1000., mad=2., **changes):
    view = dict(fact_id='S/F1/n:1/core/raw', eligible_single=True, quality_usable=True,
        source_ownership_exclusive=True, source_population_unverified_n=0,
        status='SINGLE_COMPATIBLE_LAYER', reason='SINGLE_LAYER', mixture_flag=False,
        independent_mixture_flag=False, inclusive_mixture_flag=False,
        substantial_layer_count=1, inclusive_substantial_layer_count=1,
        summary=dict(n=100, area=100, valid_fraction=1., median=z, mad=mad),
        inclusive_summary=dict(n=100, area=100, valid_fraction=1., median=z, mad=mad),
        roi_definition='DS12_EXACT_L2_EXCLUSIVE_COMPONENT_ADAPTIVE_CORE',
        roi_binding=dict(sha256='a' * 64), selected_source_index_binding=dict(sha256='b' * 64))
    whole = copy.deepcopy(view)
    whole['fact_id'] = 'S/F1/n:1/whole/raw'
    whole['roi_definition'] = 'ORIGINAL_FULL_MASK'
    result = dict(schema='DS18_SAME_ROI_RAW_MEASUREMENT_V1', no_cross_ROI_certification=True,
        core=view, whole=whole, fact_id='S/F1/n:1/mixed/raw', certificate_sha256='c' * 64,
        native=1, frame=1, time=1.)
    result.update(changes)
    return result


def samples(z=1000., start=1., count=5, slope=0.):
    return [dict(frame=i + 1, time=start + i / 10., z_mm=z + slope * i / 10.,
                 mad_mm=2., fact_id=f'S/F{i+1}', version=[1, 1, 1, 0]) for i in range(count)]


class Checks(unittest.TestCase):
    def test_extract_uses_exact_independent_core_and_never_selects_peak(self):
        c = fact()
        c['core']['inclusive_summary']['median'] = 9000.
        c['core']['layers'] = [dict(median=8000.)]
        c['whole']['summary']['median'] = 7000.
        saved = copy.deepcopy(c)
        measured = depth.extract(c)
        self.assertTrue(measured['usable'])
        self.assertEqual((measured['z_mm'], measured['mad_mm']), (1000., 2.))
        self.assertEqual(measured['fact_id'], c['core']['fact_id'])
        self.assertEqual(c, saved)

    def test_core_or_whole_multilayer_blocks_individual_history(self):
        for part in ('core', 'whole'):
            for key, value in (('mixture_flag', True), ('independent_mixture_flag', True),
                               ('inclusive_mixture_flag', True), ('substantial_layer_count', 2)):
                c = fact()
                c[part][key] = value
                self.assertFalse(depth.extract(c)['usable'])

    def test_quality_source_missing_and_same_roi_contract(self):
        for key, value in (('eligible_single', False), ('source_ownership_exclusive', False),
                           ('source_population_unverified_n', 1)):
            c = fact()
            c['core'][key] = value
            self.assertFalse(depth.extract(c)['usable'])
        for key, value in (('n', 15), ('valid_fraction', .19), ('mad', 50.), ('median', None)):
            c = fact()
            c['core']['summary'][key] = value
            self.assertFalse(depth.extract(c)['usable'])
        c = fact()
        c['core']['roi_definition'] = 'ORIGINAL_EXCLUSIVE_MASK_CV2_ERODE_7X7_DEFAULT_BORDER_ONE_ITERATION'
        self.assertRaises(AssertionError, depth.extract, c)
        self.assertFalse(depth.extract(None)['usable'])

    def test_forecast_reuses_real_ds1_wls_and_preserves_slope(self):
        history = samples(slope=80.)
        now = 2.
        result = depth.forecast(history, now)
        original = depth._DS1.predict(dict(samples=history), now)
        self.assertTrue(result['usable'])
        for key in ('mu_mm', 'scale_mm', 'slope_mm_s', 'residual_mm', 'gamma', 'covariance_proxy'):
            self.assertEqual(result[key], original[key])
        self.assertAlmostEqual(result['slope_mm_s'], 80.)
        self.assertGreater(result['scale_mm'], depth.forecast(history, 1.5)['scale_mm'])
        self.assertIsNone(depth.forecast(samples(count=1), 1.1)['slope_mm_s'])

    def test_gap_epoch_invalid_or_expired_history_is_common_null(self):
        for change in ('gap', 'epoch', 'time', 'mad', 'risk'):
            history = samples()
            if change == 'gap': history[2]['frame'] += 1
            if change == 'epoch': history[2]['version'][-1] = 1
            if change == 'time': history[2]['time'] = history[1]['time']
            if change == 'mad': history[2]['mad_mm'] = -1.
            if change == 'risk': history[2]['usable'] = False
            self.assertFalse(depth.forecast(history, 2.)['usable'])
        self.assertFalse(depth.forecast(samples(), 14.)['usable'])
        self.assertFalse(depth.forecast(samples(), 1.)['usable'])
        self.assertFalse(depth.forecast([], 2.)['usable'])

    def test_all_candidate_history_required_and_all_null_costs_exact_zero(self):
        current = depth.extract(fact(time=2.))
        bg = dict(n=100, median=1100., mad=20.)
        for bank, measured, full in (({7: samples(), 8: []}, current, bg),
                ({7: samples(), 8: samples(1200.)}, depth.extract(None), bg),
                ({7: samples(), 8: samples(1200.)}, current, dict(n=0))):
            costs, detail = depth.costs(bank, measured, 2., full)
            self.assertEqual(costs, {7: 0., 8: 0.})
            self.assertFalse(detail['used'])

    def test_raw_shared_background_row_and_candidate_reordering(self):
        current = depth.extract(fact(time=2.))
        bank = {7: samples(), 8: samples(1200.)}
        bg = dict(n=100, median=1100., mad=20.)
        cost, detail = depth.costs(bank, current, 2., bg)
        other, reordered = depth.costs(dict(reversed(list(bank.items()))), current, 2., bg)
        self.assertTrue(detail['used'])
        self.assertEqual(cost, other)
        self.assertLess(cost[7], cost[8])
        self.assertEqual(detail['edges'][7]['log_background'], detail['edges'][8]['log_background'])
        for pid in bank:
            self.assertEqual(cost[pid], detail['edges'][pid]['raw_cost'])
        self.assertEqual(detail['dummy_cost_change'], 0.)
        self.assertEqual(reordered['external_depth_weight'], .25)
        self.assertFalse(reordered['costs_are_weighted'])

    def test_normalized_scale_penalty_and_contamination_limit(self):
        self.assertAlmostEqual(depth.log_t4(1000., 1000., 30.) -
                               depth.log_t4(1000., 1000., 300.), math.log(10.))
        a = math.log(.9) + depth.log_t4(1000., 1000., 1e12) - depth.log_t4(1000., 1100., 60.)
        b = math.log(.1)
        high = max(a, b)
        cost = -(high + math.log(math.exp(a - high) + math.exp(b - high)))
        self.assertAlmostEqual(cost, -math.log(.1), places=6)

    def test_future_measurement_rejected_without_history_mutation(self):
        bank = {7: samples()}
        saved = copy.deepcopy(bank)
        self.assertRaises(AssertionError, depth.costs, bank, depth.extract(fact(time=3.)),
                          2., dict(n=100, median=1100., mad=20.))
        self.assertEqual(bank, saved)


if __name__ == '__main__':
    unittest.main()
