"""DS10 local-level invariants; statistical engineering checks, no truth labels."""
import os
os.environ.update(CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
import copy
import io
import math
import sys
import time
import unittest
from common import HERE,artifact,write_new
from depth_state import DepthState,predict as old_predict
from forecast import predict,CFG


def frozen(n=5):
    return dict(key=['test','arm',1,9,0],source=9,public=9,cutoff_frame=n,
        acquired_interval_seconds=.05,samples=[dict(frame=i+1,time=.05*i,z_mm=1000.+2*i,
            mad_mm=2.,source='RAW',fact_id=f'test/F{i+1}/n:9/raw') for i in range(n)])


class ForecastTests(unittest.TestCase):
    def test_zero_one_two_points_exact_old_dict(self):
        for n in (0,1,2):
            data=frozen(n)
            self.assertEqual(predict(data,1.),old_predict(data,1.))
            self.assertNotIn('calibration',predict(data,1.))

    def test_last_real_mean_unknown_velocity_and_full_legacy_reference(self):
        data=frozen();saved=copy.deepcopy(data)
        result=predict(data,1.)
        self.assertEqual(data,saved)
        self.assertEqual(result['mu_mm'],1008.)
        self.assertIsNone(result['slope_mm_s'])
        self.assertEqual(result['legacy_reference'],old_predict(data,1.))
        self.assertEqual(result['sample_fact_ids'],old_predict(data,1.)['sample_fact_ids'])

    def test_three_points_changes_mean_but_has_no_diffusion_estimate(self):
        result=predict(frozen(3),1.);cal=result['calibration']
        self.assertEqual(result['mu_mm'],1004.)
        self.assertEqual(cal['legal_increment_count'],2)
        self.assertIsNone(cal['diffusion_rate_mm2_per_second'])
        self.assertEqual(cal['selected_process_variance_mm2'],cal['old_process_variance_mm2'])

    def test_measurement_noise_subtracted_and_old_gap_floor_retained(self):
        result=predict(frozen(),1.);cal=result['calibration']
        self.assertEqual(cal['diffusion_rate_mm2_per_second'],0.)
        self.assertEqual(cal['selected_process_variance_mm2'],cal['old_process_variance_mm2'])
        self.assertEqual(cal['last_measurement_sigma_mm'],15.)
        self.assertAlmostEqual(result['scale_mm']**2,225.+cal['old_process_variance_mm2'])
        for inc in cal['increments']:
            self.assertEqual(inc['excess_variance_mm2'],0.)

    def test_true_time_units_nonnegative_diffusion_and_larger_process(self):
        data=frozen()
        for i,s in enumerate(data['samples']):s['z_mm']=1000.+100*i
        result=predict(data,1.);cal=result['calibration']
        expected=(10000.-225.-225.)/.05
        self.assertAlmostEqual(cal['diffusion_rate_mm2_per_second'],expected)
        self.assertAlmostEqual(cal['diffusion_variance_at_query_mm2'],expected*.8)
        self.assertEqual(cal['selected_process_variance_mm2'],cal['diffusion_variance_at_query_mm2'])
        slow=copy.deepcopy(data)
        for s in slow['samples']:s['time']*=10.
        slower=predict(slow,10.)['calibration']
        self.assertAlmostEqual(slower['diffusion_rate_mm2_per_second'],expected/10.)
        self.assertAlmostEqual(slower['diffusion_variance_at_query_mm2'],cal['diffusion_variance_at_query_mm2'])

    def test_inferred_effective_60_floor_is_not_shrunk(self):
        data=frozen()
        for s in data['samples']:s.update(mad_mm=60./1.4826,source='RESTORED_V2_INFERRED')
        result=predict(data,1.);cal=result['calibration']
        self.assertAlmostEqual(cal['last_measurement_sigma_mm'],60.)
        self.assertGreaterEqual(result['scale_mm'],60.)
        self.assertTrue(all(abs(i['first_sigma_mm']-60.)<1e-12 for i in cal['increments']))

    def test_query_changes_only_actual_gap_not_past_diffusion_facts(self):
        data=frozen();first=predict(data,1.);later=predict(data,2.)
        self.assertEqual(first['mu_mm'],later['mu_mm'])
        self.assertEqual(first['calibration']['increments'],later['calibration']['increments'])
        self.assertEqual(first['calibration']['diffusion_rate_mm2_per_second'],later['calibration']['diffusion_rate_mm2_per_second'])
        self.assertGreater(later['scale_mm'],first['scale_mm'])

    def test_at_most_ten_samples_and_no_future_or_frame_join(self):
        data=frozen(15)
        for s in data['samples'][:5]:s['z_mm']=9000.
        result=predict(data,1.)
        self.assertEqual(result['samples'],10)
        self.assertEqual(result['sample_frames'],list(range(6,16)))
        invalid=frozen();invalid['samples'][-1]['time']=2.
        self.assertIsNone(predict(invalid,1.)['mu_mm'])
        invalid=frozen();invalid['samples'][2]['frame']=90
        self.assertIsNone(predict(invalid,1.)['mu_mm'])

    def test_nonfinite_samples_do_not_create_a_local_level_forecast(self):
        for key in ('time','z_mm','mad_mm'):
            data=frozen();data['samples'][2][key]=float('nan')
            self.assertIsNone(predict(data,1.)['mu_mm'])

    def test_risk_and_version_breaks_via_real_depth_state(self):
        measurement=dict(core_usable=True,source='RAW',fact_id='fact',core=dict(median=1000.,mad=2.))
        episode=dict(member_sources=[9,10],public_ids=[9,10])
        for changed in ('generation','epoch','public','risk'):
            state=DepthState('test','arm')
            for f in range(1,6):state.update(9,measurement,f,f/30,9,0,1,'SOURCE_OBSERVATION')
            if changed=='risk':
                state.update(9,measurement,6,.2,9,0,1,'GROUP_MEASUREMENT')
                self.assertFalse(state.live[9]['samples'])
                # Last completed fragment is retained, not joined through the group.
                state.update(9,measurement,7,7/30,9,0,1,'SOURCE_OBSERVATION')
            else:
                state.update(9,measurement,6,.2,99 if changed=='public' else 9,
                             1 if changed=='epoch' else 0,2 if changed=='generation' else 1,'SOURCE_OBSERVATION')
            fragment=state.freeze(episode,8)['A']
            self.assertLessEqual(len(fragment['samples']),1)
            self.assertEqual(predict(fragment,1.),old_predict(fragment,1.))

    def test_explicit_mixed_version_is_rejected(self):
        data=frozen();data['samples'][2]['version_key']=['test','arm',2,9,0]
        self.assertEqual(predict(data,1.)['status'],'INVALID_LOCAL_LEVEL_FRAGMENT')


def main():
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(ForecastTests)
    names=[x.id() for x in suite];buffer=io.StringIO();began=time.perf_counter()
    result=unittest.TextTestRunner(stream=buffer,verbosity=2).run(suite)
    print(buffer.getvalue())
    if not result.wasSuccessful():raise SystemExit(1)
    if '--write-new' in sys.argv:
        write_new(HERE/'FORECAST_CHECKS.json',dict(status='PASS',tests=result.testsRun,
            assertions=names,elapsed_seconds=time.perf_counter()-began,native_math_threads=1,
            code=[artifact(HERE/name) for name in ('forecast.py','forecast_tests.py','CONFIG.json')],
            old_predict_module_read_only=True,synthetic_only=True,gt_read=False,
            interpretation='Causal statistical engineering checks; not physical accuracy or tracking benefit.'))


if __name__=='__main__':main()
