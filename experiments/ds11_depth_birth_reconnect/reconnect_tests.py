"""Focused birth selector and real copy-on-write transaction checks; no GT."""
from __future__ import annotations

import copy
import importlib.util
import io
import math
import os
import sys
import unittest
from unittest.mock import patch
from pathlib import Path

os.environ.update(CUDA_VISIBLE_DEVICES='', OMP_NUM_THREADS='1',
                  OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common import ROOT, write_new, artifact
from reconnect import choose, qualification, geometry_forecast, CFG, _density
_controller_spec=importlib.util.spec_from_file_location('ds11_birth_real_controller',HERE/'controller.py')
_controller=importlib.util.module_from_spec(_controller_spec)
_controller_spec.loader.exec_module(_controller)
DepthNativeBridge=_controller.DepthNativeBridge
DepthNativeManager=_controller.DepthNativeManager
from birth_memory import BirthMemory
from depth_state import DepthState
_runner_spec=importlib.util.spec_from_file_location('ds11_birth_actual_runner',HERE/'runner.py')
_runner=importlib.util.module_from_spec(_runner_spec)
_runner_spec.loader.exec_module(_runner)
from test_ne import CONFIG as ENGINE_CONFIG, observation
from scipy.stats import multivariate_t, t
import numpy as np
import cv2
cv2.setNumThreads(1)

SEGMENT = 'SYNTHETIC'


def candidate(source=7, public=None, z=1000., x=10., count=10):
    public = source if public is None else public
    key = [SEGMENT, 'R11_RAW_SENSOR_SUPPORT', 1, public, 1]
    geometry = [dict(frame=i+1, time=i*.1, source=source, source_generation=1,
        public_id=public, public_epoch=1, center=[x, 10.], bbox=[x-10., 0., x+10., 20.],
        area=400, neighbors=[], observation_class='SOURCE_OBSERVATION') for i in range(count)]
    samples = [dict(frame=p['frame'], time=p['time'], z_mm=z, mad_mm=2.,
        source='RAW_SENSOR_ADAPTIVE', fact_id=f'{SEGMENT}/F{p["frame"]}/n:{source}/adaptive/raw',
        version_key=key, observation_class='SOURCE_OBSERVATION') for p in geometry]
    return dict(public=public, source=source, eligible=True, reasons=[], bank_anchor_version=key,
        anchor=dict(frame=count, native_id=source, canonical_id=public, mask=f'n:{source}'),
        reference_anchor=dict(frame=count,time=geometry[-1]['time'],native_id=source,
            canonical_id=public,source_generation=1,public_epoch=1,mask=f'n:{source}'),
        risk_interval=dict(reference_frame=count,reference_time=geometry[-1]['time'],
            last_appearance_frame=count,disappearance_frame=count+1,query_frame=11,query_time=1.,
            full_gap_seconds=1.-geometry[-1]['time'],observed_risk_frames=[],missing_interval_frames=[],
            identity_continuity='UNKNOWN',path_between_reference_and_query='UNOBSERVED_NOT_INTERPOLATED'),
        anonymous_risk_observations=[],
        geometry_history=geometry, frozen_depth=dict(key=key, samples=samples,
            source=source, public=public, cutoff_frame=count, acquired_interval_seconds=.1))


def measurement(source, z=1000., cohort=None, mad=2.):
    return dict(native=source, source='RAW_SENSOR_ADAPTIVE' if cohort is None else 'RESTORED_V2_'+cohort.upper(),
        fact_id=f'{SEGMENT}/F11/n:{source}/adaptive/'+('raw' if cohort is None else 'v2/'+cohort),
        cohort=cohort or 'RAW', core=dict(area=40, n=40, valid_fraction=1., median=z, mad=mad),
        core_usable=True)


def selector_fixture(cohort=None):
    q = dict(frame=11, time=1., source=100, center=[10.,10.], bbox=[0.,0.,20.,20.],
        area=400, neighbors=[], quality=True, observation_class='BIRTH_UNASSIGNED')
    measurements = {100:measurement(100, cohort=cohort), 200:measurement(200, 1700., cohort),
                    201:measurement(201, 2200., cohort)}
    return q, [candidate()], measurements, dict(n=230400, median=2500., mad=100.)


def select(q, candidates, measurements, full, mode='RAW_DEPTH'):
    return choose(q, candidates, measurements, full, mode, SEGMENT)


def transaction_fixture(outside_alias=False, new=(100,)):
    bridge = DepthNativeBridge(ENGINE_CONFIG)
    for frame in range(1,5):
        bridge.commit_once(bridge.preview(frame, 1.+frame*.1,
            [observation(7),observation(8,100),observation(9,200)], {}))
    if outside_alias:
        bridge.engine.alias[199] = dict(target=9,
            anchor=copy.deepcopy(bridge.engine.bank[9]['anchor']), commit_frame=4,
            source='F9_EVENT_NUMERIC', transaction_version=4)
    observations = [observation(n, i*100+3) for i,n in enumerate(new)]
    observations.append(observation(199 if outside_alias else 9,201))
    view = bridge.preview(5,1.5,observations,{})
    certified = {n:dict(eligible=True, public=k, source=k,
        anchor=copy.deepcopy(bridge.engine.bank[k]['anchor']),
        reference_anchor=copy.deepcopy(bridge.engine.bank[k]['anchor']))
        for n,k in zip(new,(7,8))}
    return bridge, view, certified


class SelectorTests(unittest.TestCase):
    def test_supported_birth_keeps_new_dummy_and_normalized_unique_prior(self):
        q,c,m,f = selector_fixture()
        selected,d = select(q,c,m,f)
        self.assertEqual(selected,7)
        self.assertEqual(d['selected_mapping'],{100:7})
        self.assertEqual(set(d['candidates']),{'NEW','OLD:7'})
        self.assertAlmostEqual(sum(v['posterior'] for v in d['candidates'].values()),1.)
        self.assertTrue(all(v['log_prior']==-math.log(2) for v in d['candidates'].values()))
        self.assertGreater(d['margin'], math.log(9))
        self.assertGreater(d['candidates']['OLD:7']['depth_log_lr'],0.)
        self.assertEqual(d['candidates']['OLD:7']['geometry_forecast']['post_velocity_status'],'UNKNOWN_AT_BIRTH')

    def test_positive_depth_required_even_with_strong_geometry(self):
        q,c,m,f = selector_fixture()
        c[0]['frozen_depth']['samples'] = [dict(p,z_mm=100000.) for p in c[0]['frozen_depth']['samples']]
        selected,d = select(q,c,m,f)
        self.assertIsNone(selected)
        self.assertGreater(d['candidates']['OLD:7']['geometry_log_lr'],math.log(9))
        self.assertLess(d['candidates']['OLD:7']['depth_log_lr'],0.)
        self.assertEqual(d['reason'],'NONPOSITIVE_DEPTH_SUPPORT')

    def test_multiple_equal_supported_candidates_preserve_new(self):
        q,c,m,f = selector_fixture()
        c.append(candidate(8))
        selected,d = select(q,c,m,f)
        self.assertIsNone(selected)
        self.assertEqual(d['margin'],0.)
        self.assertEqual(d['selected'],'NEW')
        self.assertEqual(d['unique_physical_candidates'],3)

    def test_public_dedup_and_candidate_order_no_extra_votes(self):
        q,c,m,f = selector_fixture()
        c.append(candidate(8,z=1900.,x=200.))
        first = select(q,c,m,f)
        duplicate = select(q,list(reversed(c))+[copy.deepcopy(c[0])],dict(reversed(list(m.items()))),f)
        self.assertEqual(first[0],duplicate[0])
        self.assertEqual(first[1]['candidates'],duplicate[1]['candidates'])
        self.assertEqual(len(duplicate[1]['duplicate_public_facts_not_extra_prior_votes']),1)
        conflict = copy.deepcopy(c[0]); conflict['geometry_history'][0]['center'][0] += 1.
        with self.assertRaisesRegex(ValueError,'conflicting qualified histories'):
            select(q,[c[0],conflict],m,f)

    def test_retained_allowed_inferred_missing_zero_common_no_commit(self):
        q,c,m,f = selector_fixture('retained')
        self.assertEqual(select(q,c,m,f,'RESTORED_DEPTH')[0],7)
        cases=[]
        inferred=copy.deepcopy(m);inferred[100]=measurement(100,cohort='inferred',mad=60./1.4826)
        cases.append((inferred,'RESTORED_DEPTH'))
        wrong_source=copy.deepcopy(inferred);cases.append((wrong_source,'RAW_DEPTH'))
        missing=copy.deepcopy(m);missing[100]['core_usable']=False;cases.append((missing,'RESTORED_DEPTH'))
        nonfinite=copy.deepcopy(m);nonfinite[100]['core']['median']=float('inf');cases.append((nonfinite,'RESTORED_DEPTH'))
        cases.append((m,'DEPTH_ZERO'))
        for facts,mode in cases:
            with self.subTest(mode=mode,source=facts[100]['source']):
                selected,d = select(q,c,facts,f,mode)
                self.assertIsNone(selected)
                self.assertTrue(d['all_candidate_query_depth_common_uninformative'])
                self.assertTrue(all(v['depth_log_lr']==0. and not v['depth']['used']
                                    for v in d['candidates'].values()))

    def test_current_quality_contact_area_class_and_initial_frame(self):
        q,c,m,f = selector_fixture()
        for edit in ({'quality':False},{'neighbors':[8]},{'area':63},{'observation_class':'GROUP_OBSERVATION'}):
            selected,d = select(dict(q,**edit),c,m,f)
            self.assertIsNone(selected)
            self.assertEqual(d['reason'],'CURRENT_QUALITY_CONTACT_OR_CLASS_INELIGIBLE')
        selected,d=select(dict(q,frame=1),[],m,f)
        self.assertIsNone(selected)
        self.assertEqual(d['reason'],'SEGMENT_INITIAL_FRAME_NOT_ASSOCIATED')

    def test_excluded_facts_retained_with_reasons(self):
        q,c,m,f=selector_fixture()
        c[0].update(eligible=False,reasons=['PUBLIC_ALIAS_CLAIMED'])
        selected,d=select(q,c,m,f)
        self.assertIsNone(selected)
        self.assertEqual(set(d['candidates']),{'NEW'})
        self.assertEqual(d['unscored_candidates'][0]['selector_reasons'],['PUBLIC_ALIAS_CLAIMED'])
        self.assertEqual(d['unscored_candidates'][0]['frozen_depth'],c[0]['frozen_depth'])

    def test_history_version_risk_time_source_and_anchor_boundaries(self):
        q,c,m,f=selector_fixture()
        variants=[]
        bad=copy.deepcopy(c[0]);bad['geometry_history'][3]['public_epoch']=2;variants.append(bad)
        bad=copy.deepcopy(c[0]);bad['geometry_history'][3]['neighbors']=[8];variants.append(bad)
        bad=copy.deepcopy(c[0]);bad['frozen_depth']['samples'][3]['frame']+=1;variants.append(bad)
        bad=copy.deepcopy(c[0]);bad['frozen_depth']['samples'][3]['source']='RESTORED_V2_INFERRED';variants.append(bad)
        bad=copy.deepcopy(c[0]);bad['frozen_depth']['samples'][3]['version_key']=[];variants.append(bad)
        bad=copy.deepcopy(c[0]);bad['frozen_depth']['cutoff_frame']=q['frame'];variants.append(bad)
        bad=copy.deepcopy(c[0]);bad['geometry_history'][3]['time']=q['time'];variants.append(bad)
        bad=copy.deepcopy(c[0]);bad['reference_anchor']['frame']-=1;variants.append(bad)
        bad=copy.deepcopy(c[0]);bad['geometry_history'][3]['center'][0]=float('nan');variants.append(bad)
        bad=copy.deepcopy(c[0]);bad['frozen_depth']['samples'][3]['mad_mm']=50.;variants.append(bad)
        variants.append(candidate(count=2))
        for bad in variants:
            with self.subTest(source=bad['source'],history=len(bad['geometry_history'])):
                self.assertTrue(qualification(bad,q,SEGMENT))
                selected,d=select(q,[bad],m,f)
                self.assertIsNone(selected)
                self.assertEqual(len(d['unscored_candidates']),1)
        self.assertTrue(qualification(c[0],dict(q,time=13.),SEGMENT))

    def test_risk_before_disappearance_preserves_fragment_and_full_gap(self):
        q,c,m,f=selector_fixture()
        q.update(frame=15,time=1.4)
        old=c[0]
        old['anchor']['frame']=12
        old['risk_interval'].update(last_appearance_frame=12,disappearance_frame=13,
            query_frame=15,query_time=1.4,full_gap_seconds=1.4-.9,
            observed_risk_frames=[11,12],missing_interval_frames=[13,14])
        old['anonymous_risk_observations']=[dict(frame=i,time=(i-1)*.1,
            observation_class='QUALITY_OR_CONTACT_RISK',bbox=[0.,0.,20.,20.],area=400,
            neighbors=[8],source_generation=1,public_epoch=1,version_key=old['frozen_depth']['key'],
            fact_id=f'{SEGMENT}/F{i}/anonymous-risk') for i in (11,12)]
        self.assertFalse(qualification(old,q,SEGMENT))
        _,d=select(q,c,m,f)
        forecast=d['candidates']['OLD:7']['depth_forecast']
        self.assertAlmostEqual(forecast['calibration']['actual_gap_seconds'],.5)
        self.assertEqual(forecast['sample_frames'],list(range(1,11)))
        self.assertGreater(forecast['calibration']['old_process_variance_mm2'],225.)
        self.assertEqual(d['candidates']['OLD:7']['qualification']['risk_interval']['identity_continuity'],'UNKNOWN')
        bad=copy.deepcopy(old);bad['anonymous_risk_observations'][0]['public_epoch']=2
        self.assertIn('ANONYMOUS_RISK_FACT_VERSION_OR_CAUSALITY_MISMATCH',qualification(bad,q,SEGMENT))
        bad=copy.deepcopy(old);bad['bank_anchor_version'][-1]=2
        self.assertTrue(qualification(bad,q,SEGMENT))
        earlier=copy.deepcopy(old);earlier['anchor']['frame']=3
        self.assertFalse(qualification(earlier,q,SEGMENT))

    def test_single_object_ols_cap_actual_gap_and_residual_causality(self):
        history=candidate()['geometry_history']
        for p in history:p['center']=[2.+10.*p['time'],4.-2.*p['time']]
        forecast=geometry_forecast(history,2.9,SEGMENT)
        np.testing.assert_allclose(forecast['mu_px'],[21.,.2],atol=1e-12)
        self.assertAlmostEqual(forecast['actual_gap_seconds'],2.)
        self.assertEqual(forecast['capped_mean_gap_seconds'],1.)
        self.assertAlmostEqual(forecast['growth_factor'],1.+(2./.9)**2)
        np.testing.assert_allclose(forecast['shape_px2'],np.asarray(forecast['inflated_covariance_px2'])/2.)
        self.assertEqual(forecast['calibration']['residual_count'],9)
        for residual in forecast['calibration']['residuals']:
            self.assertTrue(all(p['frame']<residual['target']['frame'] and p['time']<residual['target']['time']
                for p in residual['predictor_facts']))
        self.assertEqual(forecast['pre_facts'][-1]['frame'],10)

    def test_normalized_densities_and_shared_null_match_scipy(self):
        q,c,m,f=selector_fixture()
        _,d=select(q,c,m,f)
        old=d['candidates']['OLD:7'];geo=old['geometry_forecast'];dep=old['depth_forecast']
        expected_geo=multivariate_t.logpdf(q['center'],loc=geo['mu_px'],shape=geo['shape_px2'],df=4)
        self.assertAlmostEqual(old['geometry']['raw_log_density'],expected_geo,places=12)
        sigma=old['depth']['combined_scale_mm']
        expected_depth=t.logpdf(m[100]['core']['median'],df=4,loc=dep['mu_mm'],scale=sigma)
        self.assertAlmostEqual(old['depth']['raw_log_density'],expected_depth,places=12)
        bg=d['background']['depth'];terms=[]
        for component in bg['components']:
            terms.append(t.logpdf(1000.,df=4,loc=component['median_mm'],
                scale=math.hypot(component['base_scale_mm'],15.)))
        expected_bg=float(np.logaddexp.reduce(terms)-math.log(len(terms)))
        self.assertAlmostEqual(old['depth']['background_log_density'],expected_bg,places=12)
        self.assertEqual(old['depth']['background_log_density'],d['candidates']['NEW']['depth']['background_log_density'])

    def test_no_input_mutation_current_q_never_enters_past(self):
        q,c,m,f=selector_fixture()
        before=copy.deepcopy((q,c,m,f))
        _,first=select(q,c,m,f)
        shifted=copy.deepcopy(m);shifted[100]['core']['median']+=100.
        _,second=select(q,c,shifted,f)
        self.assertEqual((q,c,m,f),before)
        for key in ('geometry_forecast','depth_forecast'):
            self.assertEqual(first['candidates']['OLD:7'][key],second['candidates']['OLD:7'][key])
        self.assertLess(max(first['candidates']['OLD:7']['depth_forecast']['legacy_reference']['sample_frames']),q['frame'])


class TransactionTests(unittest.TestCase):
    def test_stage_is_readonly_then_single_first_publish_and_alias_persists(self):
        bridge,view,candidates=transaction_fixture()
        before=copy.deepcopy(bridge.engine.__dict__);version=bridge.version
        tx,error=bridge.stage_birth_reconnect(view,{100:7},candidates)
        self.assertIsNone(error)
        self.assertEqual(bridge.engine.__dict__,before)
        self.assertEqual(bridge.version,version)
        self.assertEqual(bridge.previous,{7:7,8:8,9:9})
        ids,trace=bridge.commit_once(view,tx)
        self.assertEqual(ids,{100:7,9:9})
        self.assertEqual(bridge.provenance[100]['source'],'DS11_DEPTH_BIRTH_RECONNECT')
        self.assertEqual(bridge.engine.alias[100]['target'],7)
        self.assertEqual(bridge.provenance[100]['anchor'],candidates[100]['anchor'])
        self.assertEqual(trace['publication_effects']['new_source_publications'][100],7)
        with self.assertRaises(AssertionError):bridge.commit_once(view,tx)
        following,_=bridge.commit_once(bridge.preview(6,1.6,[observation(100,4),observation(9,202)],{}))
        self.assertEqual(following,ids)
        self.assertEqual(set(ids),{o['id'] for o in view['observations']})
        self.assertEqual(len(set(ids.values())),len(ids))

    def test_noaction_preserves_native_and_existing_outside_alias(self):
        bridge,view,candidates=transaction_fixture(outside_alias=True)
        alias=copy.deepcopy(bridge.engine.alias[199])
        ids,_=bridge.commit_once(view)
        self.assertEqual(ids,{100:100,199:9})
        self.assertEqual(bridge.engine.alias[199],alias)
        self.assertEqual(len(ids),len(set(ids.values())))

    def test_reconnect_preserves_outside_alias_and_mask_count(self):
        bridge,view,candidates=transaction_fixture(outside_alias=True)
        alias=copy.deepcopy(bridge.engine.alias[199])
        tx,error=bridge.stage_birth_reconnect(view,{100:7},candidates)
        self.assertIsNone(error)
        ids,_=bridge.commit_once(view,tx)
        self.assertEqual(ids,{100:7,199:9})
        self.assertEqual(bridge.engine.alias[199],alias)
        self.assertEqual(set(ids),{o['id'] for o in view['observations']})

    def test_target_claim_anchor_quality_and_stale_rejections_are_atomic(self):
        for kind in ('alias','occupied','anchor','missing_bank','quality','ineligible','stale'):
            with self.subTest(kind=kind):
                bridge,view,candidates=transaction_fixture()
                if kind=='alias':bridge.engine.alias[333]=dict(target=7,anchor=candidates[100]['anchor'])
                if kind=='occupied':
                    view=bridge.preview(5,1.5,[observation(100),observation(7),observation(9,201)],{})
                if kind=='anchor':candidates[100]['anchor']['frame']=1
                if kind=='missing_bank':bridge.engine.bank.pop(7)
                if kind=='quality':view['observations'][0]['neighbors']=[9]
                if kind=='ineligible':candidates[100]['eligible']=False
                if kind=='stale':view['version']-=1
                before=copy.deepcopy(bridge.engine.__dict__)
                tx,error=bridge.stage_birth_reconnect(view,{100:7},candidates)
                self.assertIsNone(tx)
                self.assertIsNotNone(error)
                self.assertEqual(bridge.engine.__dict__,before)

    def test_any_active_group_and_duplicate_target_batch_rejected(self):
        bridge,view,candidates=transaction_fixture(new=(100,101))
        candidates[101]=dict(candidates[100])
        before=copy.deepcopy(bridge.engine.__dict__)
        tx,error=bridge.stage_birth_reconnect(view,{100:7,101:7},candidates)
        self.assertIsNone(tx)
        self.assertEqual(error,'occupied_target')
        self.assertEqual(bridge.engine.__dict__,before)
        bridge.engine.protected['ACTIVE']=dict(member_public=[7,8])
        tx,error=bridge.stage_birth_reconnect(view,{100:7},candidates)
        self.assertIsNone(tx)
        self.assertEqual(error,'active_group_reserved')
        tx,error=bridge.stage_birth_reconnect(view,{100:7,101:8,102:9},candidates)
        self.assertIsNone(tx)
        self.assertEqual(error,'active_group_reserved')
        bridge.engine.protected.clear()
        tx,error=bridge.stage_birth_reconnect(view,{100:7,101:8,102:9},candidates)
        self.assertIsNone(tx)
        self.assertEqual(error,'existing_transaction_capacity_exceeded')

    def test_actual_memory_keeps_pre_risk_joint_fragment_and_first_ever_ledger(self):
        bridge=DepthNativeBridge(ENGINE_CONFIG)
        manager=DepthNativeManager('R11_RAW',bridge,{},dict(max_episode_seconds=10.),{})
        memory=BirthMemory(SEGMENT)
        raw=DepthState(SEGMENT,'R11_RAW_SENSOR_SUPPORT')
        def tick(frame,observations):
            row=dict(frame=frame,time=frame*.1,observations=observations)
            facts={o['id']:measurement(o['id']) for o in observations}
            profiles={n:dict(frame=frame,id=n,mask=f'n:{n}',core=v['core'],whole=v['core'])
                      for n,v in facts.items()}
            manager.before(row,profiles)
            view=bridge.preview(frame,row['time'],observations,profiles)
            queries=memory.before(row,profiles,manager,raw,view)
            ids,_=bridge.commit_once(view)
            classes={o['id']:'QUALITY_OR_CONTACT_RISK' if o.get('neighbors') else 'SOURCE_OBSERVATION'
                     for o in observations}
            for o in observations:
                n=o['id']
                raw.update(n,facts[n],frame,row['time'],ids[n],bridge.epochs[n],
                    manager._generation(n,frame),classes[n])
            memory.after(row,profiles,manager,raw,ids,classes,facts)
            manager.after(row,profiles)
            return queries
        initial=tick(1,[observation(7),observation(9,200)])
        self.assertEqual({q['source'] for q in initial},{7,9})
        self.assertEqual(memory.first_seen,{7:1,9:1})
        for frame in range(2,5):self.assertFalse(tick(frame,[observation(7),observation(9,200)]))
        for frame in (5,6):
            risky=observation(7);risky['neighbors']=[9]
            self.assertFalse(tick(frame,[risky,observation(9,200)]))
        queries=tick(7,[observation(100),observation(9,200)])
        self.assertEqual(len(queries),1)
        old=next(c for c in queries[0]['candidates'] if c['source']==7)
        self.assertTrue(old['eligible'],old['reasons'])
        self.assertEqual([p['frame'] for p in old['geometry_history']],[1,2,3,4])
        self.assertEqual([p['frame'] for p in old['frozen_depth']['samples']],[1,2,3,4])
        self.assertEqual([p['frame'] for p in old['anonymous_risk_observations']],[5,6])
        self.assertEqual(old['reference_anchor']['frame'],4)
        self.assertEqual(old['last_seen_frame'],6)
        self.assertFalse(qualification(old,queries[0]['query_observation'],SEGMENT))
        before=copy.deepcopy(old)
        returned=tick(8,[observation(7),observation(9,200)])
        self.assertFalse(any(q['source']==7 for q in returned))
        self.assertEqual(memory.first_seen[7],1)
        self.assertEqual(old,before)
        self.assertNotIn(7,memory.disappeared)

    def test_actual_batch_collision_capacity_and_two_legal_atomic_edits(self):
        # The decision is stubbed only here: this checks the real batch planner
        # and stage lifecycle, independently of the already checked densities.
        for scenario in ('collision','capacity','two_legal'):
            with self.subTest(scenario=scenario):
                sources=(100,101,102) if scenario=='capacity' else (100,101)
                bridge,view,certified=transaction_fixture(new=sources)
                if scenario=='capacity':
                    certified[102]=dict(eligible=True,public=9,source=9,
                        anchor=copy.deepcopy(bridge.engine.bank[9]['anchor']),
                        reference_anchor=copy.deepcopy(bridge.engine.bank[9]['anchor']))
                queries=[dict(source=n,query_observation=dict(source=n,frame=5,time=1.5),
                    candidates=[copy.deepcopy(c) for c in certified.values()]) for n in sources]
                def decision(query,*args):
                    target=7 if scenario=='collision' else certified[query['source']]['public']
                    return target,dict(selected=f'OLD:{target}',synthetic_batch_gate=True)
                previous=copy.deepcopy(bridge.previous)
                with patch.object(_runner,'birth_choice',decision):
                    tx,changes,status=_runner.plan_births(bridge,view,queries,{}, {},'RAW_DEPTH',SEGMENT)
                self.assertEqual(bridge.previous,previous)
                if scenario=='two_legal':
                    self.assertEqual(status,'COMMIT')
                    self.assertEqual(changes,{100:7,101:8})
                    self.assertTrue(all(q['status']=='COMMIT' for q in queries))
                    ids,_=bridge.commit_once(view,tx)
                    self.assertEqual(ids,{100:7,101:8,9:9})
                else:
                    self.assertIsNone(tx)
                    self.assertFalse(changes)
                    expected='TARGET_COLLISION_REJECTED' if scenario=='collision' else 'BATCH_CAPACITY_REJECTED'
                    self.assertTrue(all(q['status']==expected for q in queries))
                    ids,_=bridge.commit_once(view)
                    self.assertEqual(ids,{o['id']:o['id'] for o in view['observations']})
                self.assertEqual(set(ids),{o['id'] for o in view['observations']})
                self.assertEqual(len(ids),len(set(ids.values())))

    def test_batch_initial_disabled_group_frames_never_call_selector_or_stage(self):
        for flag,status in (({'disabled':True},'F9_CONTROL_DISABLED'),
                            ({'group_blocked':True},'ACTIVE_GROUP_FRAME_BLOCKED'),
                            ({'initial':True},'INITIAL_FRAME_NOT_ASSOCIATED')):
            bridge,view,candidates=transaction_fixture()
            if flag.pop('initial',False):view=dict(view,frame=1)
            queries=[dict(source=100,query_observation=dict(source=100),candidates=[candidates[100]])]
            with patch.object(_runner,'birth_choice',side_effect=AssertionError('selector should not run')):
                tx,changes,_=_runner.plan_births(bridge,view,queries,{}, {},'RAW_DEPTH',SEGMENT,**flag)
            self.assertIsNone(tx)
            self.assertFalse(changes)
            self.assertEqual(queries[0]['status'],status)


if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    capture=io.StringIO()
    result=unittest.TextTestRunner(stream=capture,verbosity=2).run(suite)
    print(capture.getvalue(),flush=True)
    checks=dict(status='PASS' if result.wasSuccessful() else 'FAIL',pass_all=result.wasSuccessful(),tests_run=result.testsRun,
        failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),
        log=capture.getvalue(),scope='SYNTHETIC_SELECTOR_AND_REAL_BRIDGE_ATOMIC_TRANSACTION_NO_GT',
        module_sources=[artifact(HERE/name) for name in ('reconnect.py','reconnect_tests.py','controller.py','birth_memory.py','forecast.py','runner.py','CONFIG.json')],
        existing_density_source=artifact(ROOT/'experiments/ds10_depth_failure_repair/association.py'),
        old_files_written=False,new_GT_reads=0,HTTP_calls=0)
    if '--write-new' in sys.argv:write_new(HERE/'RECONNECT_CHECKS.json',checks)
    if '--retry-write-new' in sys.argv:write_new(HERE/'RECONNECT_CHECKS_RETRY.json',checks)
    raise SystemExit(0 if result.wasSuccessful() else 1)
