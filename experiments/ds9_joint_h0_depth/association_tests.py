"""Focused DS9 normalization, lawful H0, missingness and causal-prefix checks."""
import os
os.environ.update(CUDA_VISIBLE_DEVICES='', OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
import copy
import io
import math
import sys
import time
import unittest
import numpy as np
from scipy.stats import multivariate_t, t
from common import HERE, artifact, write_new
from association import choose, log_t4_2d, CFG
from depth_score import log_t4
from merge_split_manager import numeric_choice


def observation(frame, now, source, center, public):
    return dict(frame=frame, time=now, source=source, center=list(center),
        bbox=[center[0]-5, center[1]-5, center[0]+5, center[1]+5], area=100,
        neighbors=[], source_generation=1, public_id=public, public_epoch=0,
        observation_class='SOURCE_OBSERVATION', core=None)


def fixture():
    times = [0., .04, .09, .15, .22]
    pre = {role: [observation(i+1, now, native, (x+20*now, 100.), public)
                  for i, now in enumerate(times)]
           for role, native, x, public in [('A',11,100.,1),('B',12,400.,2)]}
    q, now = 8, .32
    posts = {21:[observation(q,now,21,(106.4,100.),21)],
             22:[observation(q,now,22,(406.4,100.),22)]}
    episode = dict(q=q, suspect_frame=6, pre=pre, post_roles=posts,
                   public_ids=[1,2], temporary_choice='H1')
    frozen = {role:dict(key=['test','arm',1,public,0], samples=[
        dict(frame=i+1,time=time_value,z_mm=depth,mad_mm=2.,source='RAW',
             fact_id=f'test/F{i+1}/n:{native}/raw') for i,time_value in enumerate(times)],
        source=native,public=public,cutoff_frame=5,acquired_interval_seconds=.07)
        for role,native,public,depth in [('A',11,1,1000.),('B',12,2,1500.)]}
    measured = {source:dict(fact_id=f'test/F8/n:{source}/raw', core_usable=True,
        core=dict(n=100,median=depth,mad=2.,valid_fraction=1.),cohort='retained',source='RAW')
        for source,depth in [(21,1000.),(22,1500.)]}
    full = dict(n=1000,median=2000.,mad=100.)
    return episode,frozen,measured,full,{21:21,22:22}


def run(data, mode='RAW_DEPTH'):
    return choose(*data, mode, 'test')


class AssociationTests(unittest.TestCase):
    def test_normalized_2d_and_1d_match_installed_scipy(self):
        for shape in ([[8.,0.],[0.,8.]], [[11.,3.],[3.,7.]], [[1e9,0.],[0.,1e9]]):
            for point in ([0.,0.], [3.,-7.], [1e4,2e4]):
                self.assertAlmostEqual(log_t4_2d(point,[1.,2.],shape),
                    multivariate_t.logpdf(point,loc=[1.,2.],shape=shape,df=4),places=11)
        for scale in (15.,60.,1e6):
            self.assertAlmostEqual(log_t4(1050.,1000.,scale),
                t.logpdf(1050.,df=4,loc=1000.,scale=scale),places=12)

    def test_covariance_shape_and_uncentered_residual_formula(self):
        data=fixture()
        data[0]['pre']['A'][2]['center'][0]+=3.
        _,detail=run(data)
        forecast=detail['geometry_forecasts']['A']
        residual=np.asarray([r['residual_px'] for r in forecast['calibration']['residuals']])
        moment=residual.T@residual/len(residual)
        covariance=.5*moment+.5*np.diag(np.diag(moment))+16.*np.eye(2)
        np.testing.assert_allclose(forecast['covariance_px2'],covariance)
        np.testing.assert_allclose(forecast['shape_px2'],covariance*forecast['growth_factor']/2.)

    def test_mean_exactly_old_numeric_and_joint_pair_availability(self):
        for short_other in (False,True):
            data=fixture()
            if short_other:data[0]['pre']['B']=data[0]['pre']['B'][-2:]
            _,legacy=numeric_choice(data[0])
            _,detail=run(data)
            for hypothesis in legacy['scores']:
                order=(21,22) if hypothesis['choice']=='H1' else (22,21)
                for role,source,edge in zip(('A','B'),order,hypothesis['edges']):
                    self.assertEqual(detail['edges'][f'{role}:{source}']['geometry']['predicted_center_px'],
                                     edge['predicted_center_px'])
            if short_other:
                self.assertTrue(all(g['mean_mode']=='LAST_MEASURED_POSITION_ONLY'
                                    for g in detail['geometry_forecasts'].values()))

    def test_actual_gap_growth_not_capped_mean_and_window_span(self):
        data=fixture()
        for series in data[0]['post_roles'].values():series[0]['time']=4.
        _,detail=run(data)
        forecast=detail['geometry_forecasts']['A']
        self.assertEqual(forecast['capped_mean_gap_seconds'],1.)
        self.assertEqual(forecast['actual_gap_seconds'],3.78)
        self.assertAlmostEqual(forecast['growth_factor'],1.+(3.78/.22)**2)
        self.assertEqual(forecast['real_pre_span_definition'],'LATEST_AT_MOST_TEN_PREDICTOR_OBSERVATIONS')

    def test_long_fragment_growth_uses_last_ten_real_times(self):
        data=fixture();episode=data[0]
        for role,native,public,x in [('A',11,1,100.),('B',12,2,400.)]:
            episode['pre'][role]=[observation(i+1,.04*i,native,(x+i,100.),public) for i in range(20)]
        episode.update(q=23,suspect_frame=21)
        for series in episode['post_roles'].values():series[0].update(frame=23,time=.9)
        _,detail=run(data,'GEOMETRY')
        forecast=detail['geometry_forecasts']['A']
        self.assertEqual(forecast['samples'],20)
        self.assertAlmostEqual(forecast['real_pre_span_seconds'],.36)
        self.assertTrue(all(len(r['predictor_facts'][role])<=10
            for r in forecast['calibration']['residuals'] for role in ('A','B')))

    def test_source_order_changes_labels_but_not_physical_mapping_scores(self):
        original=fixture();reordered=copy.deepcopy(original)
        reordered[0]['post_roles']=dict(reversed(list(reordered[0]['post_roles'].items())))
        choice,detail=run(original)
        other_choice,other=run(reordered)
        self.assertEqual(detail['selected_mapping'],other['selected_mapping'])
        self.assertEqual({choice,other_choice},{'H1','H2'})
        scores=lambda d:{tuple(sorted(c['mapping'].items())):c['log_score'] for c in d['candidates'].values()}
        self.assertEqual(scores(detail),scores(other))

    def test_lawful_h0_new_native_and_uniform_unique_prior(self):
        _,detail=run(fixture())
        self.assertEqual(detail['baseline_mapping'],{21:21,22:22})
        self.assertEqual(detail['unique_physical_candidates'],3)
        for pair in detail['candidates']['H0']['pairs']:
            self.assertFalse(pair['associated'])
            self.assertEqual(pair['geometry']['log_lr'],0.)
            self.assertEqual(pair['depth']['log_lr'],0.)
            self.assertEqual(pair['geometry']['mixture_log_density'],-math.log(230400))
        for candidate in detail['candidates'].values():
            self.assertEqual(candidate['log_prior'],-math.log(3))
        self.assertAlmostEqual(sum(c['posterior'] for c in detail['candidates'].values()),1.)

    def test_dedup_h0_represents_same_map_without_double_vote(self):
        data=list(fixture());data[4]={21:1,22:2}
        choice,detail=run(data)
        self.assertEqual(choice,'H0')
        self.assertEqual(detail['unique_physical_candidates'],2)
        self.assertEqual(detail['candidates']['H0']['labels'],['H0','H1'])
        self.assertEqual(detail['hypotheses']['H1']['canonical'],'H0')
        self.assertTrue(all(c['log_prior']==-math.log(2) for c in detail['candidates'].values()))

    def test_only_lawful_physical_map_keeps_h0(self):
        data=fixture();data[0]['public_ids']=[]
        choice,detail=run(data)
        self.assertEqual(choice,'H0');self.assertEqual(detail['unique_physical_candidates'],1)
        self.assertIsNone(detail['margin']);self.assertFalse(detail['accepted'])

    def test_missing_post_disables_entire_depth_and_missing_pre_only_row(self):
        data=fixture();data[2][21]['core_usable']=False
        _,detail=run(data)
        self.assertEqual(detail['used_edges'],0)
        self.assertTrue(all(e['depth']['log_lr']==0. for e in detail['edges'].values()))
        data=fixture();data[1]['A']['samples']=[]
        _,detail=run(data)
        self.assertEqual(detail['used_edges'],2)
        for source in (21,22):
            self.assertEqual(detail['edges'][f'A:{source}']['depth']['log_lr'],0.)
            self.assertTrue(detail['edges'][f'B:{source}']['depth']['used'])

    def test_geometry_and_zero_identical_even_inaccessible_depth(self):
        class Forbidden(dict):
            def __getitem__(self,key):raise AssertionError('ZERO accessed depth')
            def get(self,*args):raise AssertionError('ZERO accessed depth')
        episode,_,_,_,baseline=fixture()
        geo=choose(episode,Forbidden(),Forbidden(),Forbidden(),baseline,'GEOMETRY','test')
        zero=choose(episode,Forbidden(),Forbidden(),Forbidden(),baseline,'DEPTH_ZERO','test')
        self.assertEqual(geo,zero)

    def test_permutation_scoring_copy_preserves_actual_facts_and_state(self):
        data=fixture();snapshot=copy.deepcopy(data)
        _,raw=run(data);_,permuted=run(data,'DEPTH_PERMUTE')
        self.assertEqual(data,snapshot)
        for source,opposite in ((21,22),(22,21)):
            assignment=permuted['depth_assignment'][str(source)]
            self.assertEqual(assignment['assigned_depth_source'],opposite)
            self.assertEqual(assignment['measurement_fact_id'],data[2][opposite]['fact_id'])
            self.assertEqual(assignment['actual_state_fact_id'],data[2][source]['fact_id'])
        self.assertEqual(raw['geometry_forecasts'],permuted['geometry_forecasts'])
        self.assertEqual(raw['depth_forecasts'],permuted['depth_forecasts'])
        self.assertEqual(raw['edges']['A:21']['depth']['raw_log_density'],
                         permuted['edges']['A:22']['depth']['raw_log_density'])

    def test_one_point_post_unknown_and_future_not_used(self):
        data=fixture();before=run(data)
        for role in ('A','B'):
            future=copy.deepcopy(data[0]['pre'][role][-1]);future.update(frame=99,time=9.,center=[999.,999.])
            data[0]['pre'][role].append(future)
            future_depth=copy.deepcopy(data[1][role]['samples'][-1]);future_depth.update(frame=99,time=9.,z_mm=9999.)
            data[1][role]['samples'].append(future_depth)
        for source in (21,22):
            future=copy.deepcopy(data[0]['post_roles'][source][0]);future.update(frame=99,time=9.,center=[999.,999.])
            data[0]['post_roles'][source].append(future)
        self.assertEqual(before,run(data))
        self.assertTrue(all(g['post_velocity_status']=='UNKNOWN_AT_Q'
                            for g in before[1]['geometry_forecasts'].values()))

    def test_same_version_clean_contiguous_history_not_joined(self):
        for key,value in [('public_id',99),('public_epoch',2),('source_generation',2),
                          ('observation_class','GROUP_MEASUREMENT'),('neighbors',[99])]:
            data=fixture();data[0]['pre']['A'][-2][key]=value
            _,detail=run(data)
            self.assertEqual(detail['geometry_forecasts']['A']['samples'],1)
            self.assertEqual(detail['geometry_forecasts']['A']['calibration']['residual_count'],0)

    def test_large_covariance_has_density_normalization_penalty(self):
        narrow=log_t4_2d([0.,0.],[0.,0.],np.eye(2)*8.)
        broad=log_t4_2d([0.,0.],[0.,0.],np.eye(2)*800.)
        self.assertAlmostEqual(narrow-broad,math.log(100.))

    def test_score_is_normalized_joint_and_odds_gate(self):
        choice,detail=run(fixture())
        self.assertEqual(choice,'H1');self.assertTrue(detail['accepted'])
        self.assertGreaterEqual(detail['margin'],math.log(9.))
        for candidate in detail['candidates'].values():
            self.assertAlmostEqual(candidate['log_score'],candidate['log_prior']+
                candidate['geometry_log_lr']+candidate['depth_log_lr'])
            self.assertAlmostEqual(candidate['log_joint_density'],candidate['log_prior']+
                candidate['geometry_log_likelihood']+candidate['depth_log_likelihood'])


def main():
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(AssociationTests)
    names=[case.id() for case in suite]
    buffer=io.StringIO();began=time.perf_counter()
    result=unittest.TextTestRunner(stream=buffer,verbosity=2).run(suite)
    print(buffer.getvalue())
    if not result.wasSuccessful():raise SystemExit(1)
    if '--write-new' in sys.argv:
        write_new(HERE/'ASSOCIATION_CHECKS.json',dict(status='PASS',tests=result.testsRun,
            assertions=names,elapsed_seconds=time.perf_counter()-began,
            code=[artifact(HERE/name) for name in ('association.py','association_tests.py','CONFIG.json')],
            installed_scipy_normalization_reference=True,native_math_threads=1,
            synthetic_only=True,gt_read=False,old_results_used_for_parameters=False,new_model_http=0,
            interpretation='Engineering invariants under fixed model; not calibrated identity probability or tracking benefit.'))


if __name__=='__main__':main()
