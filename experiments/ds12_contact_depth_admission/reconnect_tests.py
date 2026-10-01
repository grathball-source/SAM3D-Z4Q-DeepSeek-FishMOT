"""Focused DS12 admission/mixture regressions with actual source certificates; no GT."""
from __future__ import annotations

import copy
import importlib.util
import io
import math
import os
import sys
import unittest
from pathlib import Path

os.environ.update(CUDA_VISIBLE_DEVICES='', OMP_NUM_THREADS='1',
                  OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import numpy as np
from scipy.special import logsumexp
from scipy.stats import t
from common import write_new, artifact
from contact_measurement import measure_contact, _digest
from reconnect import (choose, qualification, geometry_forecast, _legacy, _density,
                       _mixture, admission_hash, validate_admission_body)

SEGMENT = 'SYNTHETIC'


def candidate(source=7, public=None, z=1000., x=29., count=10):
    public = source if public is None else public
    key = [SEGMENT, 'R12_RAW_SENSOR_SUPPORT', 1, public, 1]
    geometry = [dict(frame=i+1, time=i*.1, source=source, source_generation=1,
        public_id=public, public_epoch=1, center=[x,14.], bbox=[x-10.,4.,x+10.,24.],
        area=400, neighbors=[], observation_class='SOURCE_OBSERVATION') for i in range(count)]
    samples = [dict(frame=p['frame'], time=p['time'], z_mm=z, mad_mm=2.,
        source='RAW_SENSOR_ADAPTIVE', fact_id=f'{SEGMENT}/F{p["frame"]}/n:{source}/adaptive/raw',
        version_key=key, observation_class='SOURCE_OBSERVATION') for p in geometry]
    return dict(public=public,source=source,eligible=True,reasons=[],bank_anchor_version=key,
        anchor=dict(frame=count,native_id=source,canonical_id=public,mask=f'n:{source}'),
        reference_anchor=dict(frame=count,time=geometry[-1]['time'],native_id=source,
            canonical_id=public,source_generation=1,public_epoch=1,mask=f'n:{source}'),
        risk_interval=dict(reference_frame=count,reference_time=geometry[-1]['time'],
            last_appearance_frame=count,disappearance_frame=count+1,query_frame=11,query_time=1.,
            full_gap_seconds=1.-geometry[-1]['time'],observed_risk_frames=[],missing_interval_frames=[],
            identity_continuity='UNKNOWN',path_between_reference_and_query='UNOBSERVED_NOT_INTERPOLATED'),
        anonymous_risk_observations=[],geometry_history=geometry,
        frozen_depth=dict(key=key,samples=samples,source=source,public=public,
                          cutoff_frame=count,acquired_interval_seconds=.1))


def measurement(source,z=1000.,cohort=None,mad=2.):
    return dict(native=source,source='RAW_SENSOR_ADAPTIVE' if cohort is None else 'RESTORED_V2_'+cohort.upper(),
        fact_id=f'{SEGMENT}/F11/n:{source}/adaptive/'+('raw' if cohort is None else 'v2/'+cohort),
        cohort=cohort or 'RAW',core=dict(area=40,n=40,valid_fraction=1.,median=z,mad=mad),core_usable=True)


def fixture(mode='RAW_DEPTH',second_z=1000.,provenance=None):
    depth=np.full((40,72),2200.,dtype='f4')
    mask=np.zeros(depth.shape,bool);mask[4:24,4:24]=True;mask[4:24,34:54]=True
    neighbor=np.zeros(depth.shape,bool);neighbor[4:24,24:27]=True
    depth[4:24,4:24]=1000.;depth[4:24,34:54]=second_z
    index=np.arange(depth.size,dtype='i4').reshape(depth.shape)
    q=dict(frame=11,time=1.,source=100,center=[29.,14.],bbox=[4.,4.,54.,24.],
        area=int(mask.sum()),neighbors=[200],quality=True,observation_class='BIRTH_UNASSIGNED')
    cohort=None if mode=='RAW_DEPTH' else 'retained'
    measured={100:measurement(100,cohort=cohort),200:measurement(200,1700.,cohort),
              201:measurement(201,2200.,cohort)}
    binding=dict(frame=11,global_frame=11,time=1.,measurement_fact_ids={str(n):m['fact_id'] for n,m in measured.items()})
    if mode=='RESTORED_DEPTH' and provenance is None:provenance=np.ones(depth.shape,'u1')
    certificates=measure_contact(depth,index,{100:mask,200:neighbor},SEGMENT,11,11,
        source_binding=binding,provenance=provenance,native_depth=depth.copy())
    return q,[candidate()],measured,dict(n=230400,median=2500.,mad=100.),certificates


def select(q,c,m,f,cert,mode='RAW_DEPTH'):
    return choose(q,c,m,f,mode,SEGMENT,contact_certificates=cert)


def resign(cert):
    cert['certificate_sha256']=_digest(cert)
    return cert


class ContactSelectorTests(unittest.TestCase):
    def test_clean_complete_output_is_frozen_ds11_and_ignores_contact_input(self):
        for mode in ('RAW_DEPTH','RESTORED_DEPTH','DEPTH_ZERO'):
            q,c,m,f,cert=fixture('RAW_DEPTH' if mode=='DEPTH_ZERO' else mode)
            q['neighbors']=[]
            expected=_legacy.choose(q,c,m,f,mode,SEGMENT)
            self.assertEqual(choose(q,c,m,f,mode,SEGMENT),expected)
            cert[100]['certificate_sha256']='bad'
            self.assertEqual(select(q,c,m,f,cert,mode),expected)
            self.assertNotIn('admission_body',expected[1])

    def test_actual_contact_certificate_admits_and_preserves_risk_facts(self):
        q,c,m,f,cert=fixture()
        selected,d=select(q,c,m,f,cert)
        self.assertEqual(selected,7)
        self.assertTrue(d['accepted'])
        self.assertEqual(d['query'],q)
        self.assertEqual(d['query']['neighbors'],[200])
        self.assertEqual(d['admission_body']['certificate'],cert[100])
        self.assertEqual(d['admission_body']['selected_target'],7)
        self.assertTrue(validate_admission_body(d['admission_body'],query=q,mode='RAW_DEPTH',segment=SEGMENT))
        self.assertEqual(d['admission_body_sha256'],admission_hash(d['admission_body']))
        self.assertEqual(d['admission_body']['body_sha256'],d['admission_body_sha256'])
        self.assertEqual(d['candidates']['OLD:7']['qualification'],c[0])
        self.assertEqual(d['candidates']['OLD:7']['geometry_forecast'],geometry_forecast(c[0]['geometry_history'],q['time'],SEGMENT))

    def test_both_density_mixtures_match_installed_normalized_student_t(self):
        q,c,m,f,cert=fixture(second_z=1600.)
        _,d=select(q,c,m,f,cert)
        edge=d['candidates']['OLD:7']['depth'];forecast=d['candidates']['OLD:7']['depth_forecast']
        pieces=cert[100]['qualified_components']
        signal_terms=[t.logpdf(p['median_mm'],df=4,loc=forecast['mu_mm'],
            scale=math.hypot(forecast['scale_mm'],p['scale_mm']))+math.log(p['weight']) for p in pieces]
        expected_signal=float(logsumexp(signal_terms))
        expected_background=float(logsumexp([math.log(p['weight'])+
            _density._background_logdensity(d['background']['depth'],p['median_mm'],p['scale_mm']) for p in pieces]))
        self.assertAlmostEqual(edge['raw_log_density'],expected_signal,places=13)
        self.assertAlmostEqual(edge['background_log_density'],expected_background,places=13)
        expected_lr=float(logsumexp([math.log(.9)+expected_signal-expected_background,math.log(.1)]))
        self.assertAlmostEqual(edge['log_lr'],expected_lr,places=13)
        per_piece_lr=[float(logsumexp([math.log(.9)+a-b,math.log(.1)])) for a,b in zip(
            [x-math.log(p['weight']) for x,p in zip(signal_terms,pieces)],
            [_density._background_logdensity(d['background']['depth'],p['median_mm'],p['scale_mm']) for p in pieces])]
        self.assertGreater(abs(edge['log_lr']-sum(per_piece_lr)/len(per_piece_lr)),1e-4)

    def test_no_candidate_specific_closest_or_largest_component(self):
        q,c,m,f,cert=fixture(second_z=1700.)
        c.append(candidate(8,z=1700.))
        _,d=select(q,c,m,f,cert)
        for edge in (d['candidates']['OLD:7']['depth'],d['candidates']['OLD:8']['depth']):
            self.assertEqual([p['component_id'] for p in edge['components']],
                [p['component_id'] for p in cert[100]['qualified_components']])
            self.assertEqual([p['weight'] for p in edge['components']],[.5,.5])
        self.assertEqual(d['candidates']['OLD:7']['depth']['background_log_density'],
                         d['candidates']['OLD:8']['depth']['background_log_density'])
        self.assertEqual(sum(v['posterior'] for v in d['candidates'].values()),1.)
        self.assertTrue(all(v['log_prior']==-math.log(3) for v in d['candidates'].values()))

    def test_mixture_order_and_whole_set_replication_invariance(self):
        terms=[-3.2,-4.5];pieces=[dict(weight=.5),dict(weight=.5)]
        expected=_mixture(terms,pieces)
        self.assertAlmostEqual(_mixture(terms[::-1],pieces[::-1]),expected)
        self.assertAlmostEqual(_mixture(terms*2,[dict(weight=.25) for _ in range(4)]),expected)
        q,c,m,f,cert=fixture(second_z=1700.)
        c.append(candidate(8,z=1700.,x=200.))
        first=select(q,c,m,f,cert)
        reverse=copy.deepcopy(cert)
        reverse[100]['components'].reverse();reverse[100]['qualified_components'].reverse();resign(reverse[100])
        second=select(q,c[::-1],dict(reversed(list(m.items()))),f,reverse)
        self.assertEqual(first[0],second[0])
        for label in first[1]['candidates']:
            for key in ('geometry_log_lr','depth_log_lr','log_score','posterior'):
                self.assertAlmostEqual(first[1]['candidates'][label][key],second[1]['candidates'][label][key],places=13)

    def test_missing_bad_future_or_foreign_certificate_is_common_zero(self):
        q,c,m,f,cert=fixture()
        cases=[{}]
        for edit in ({'native':101},{'frame':12},{'time':1.1},{'segment':'FOREIGN'},
                     {'source':'NATIVE_V2_INFERRED_CONTACT_CORE'},{'mask_area':799},
                     {'source_measurement_fact_id':'FOREIGN'},{'no_future_frame_read':False}):
            altered=copy.deepcopy(cert);altered[100].update(edit);resign(altered[100]);cases.append(altered)
        broken=copy.deepcopy(cert);broken[100]['qualified_components'][0]['weight']=.9;resign(broken[100]);cases.append(broken)
        for bad in cases:
            with self.subTest(case=bad.get(100,{}).get('source_measurement_fact_id')):
                target,d=select(q,c,m,f,bad)
                self.assertIsNone(target)
                self.assertTrue(d['all_candidate_query_depth_common_uninformative'])
                self.assertTrue(all(not e['depth']['used'] and e['depth_log_lr']==0. for e in d['candidates'].values()))
                self.assertFalse(validate_admission_body(d['admission_body']))

    def test_inferred_only_retained_exclusion_and_zero_never_commit(self):
        for mode in ('RESTORED_DEPTH','DEPTH_ZERO'):
            provenance=np.full((40,72),2,'u1')
            q,c,m,f,cert=fixture('RESTORED_DEPTH',provenance=provenance)
            target,d=select(q,c,m,f,cert,mode)
            self.assertIsNone(target)
            self.assertFalse(d['depth_used'])
            self.assertEqual(d['depth_assignment']['components'],[])
            self.assertTrue(all(e['depth_log_lr']==0. for e in d['candidates'].values()))

    def test_retained_piece_not_blocked_by_unusable_inferred_scalar_binding(self):
        q,c,m,f,cert=fixture('RESTORED_DEPTH')
        m[100]=measurement(100,cohort='inferred',mad=60./1.4826)
        m[100]['core_usable']=False
        cert[100]['source_binding']['measurement_fact_ids']['100']=m[100]['fact_id']
        cert[100]['source_measurement_fact_id']=m[100]['fact_id'];resign(cert[100])
        target,d=select(q,c,m,f,cert,'RESTORED_DEPTH')
        self.assertEqual(target,7)
        self.assertEqual(d['depth_assignment']['actual_state_fact_id'],m[100]['fact_id'])
        self.assertEqual(d['depth_assignment']['measurement_fact_id'],cert[100]['fact_id'])
        self.assertEqual(d['admission_body']['certificate']['mode'],'RESTORED_DEPTH')

    def test_quality_area_class_and_initial_frame_still_reject(self):
        q,c,m,f,cert=fixture()
        for edit in ({'quality':False},{'area':63},{'observation_class':'QUALITY_OR_CONTACT_RISK'}):
            target,d=select(dict(q,**edit),c,m,f,cert)
            self.assertIsNone(target)
            self.assertFalse(d['depth_used'])
        target,d=select(dict(q,frame=1),[],m,f,cert)
        self.assertIsNone(target)
        self.assertEqual(d['reason'],'SEGMENT_INITIAL_FRAME_NOT_ASSOCIATED')

    def test_history_reserved_and_claim_reasons_remain_unscored(self):
        q,c,m,f,cert=fixture()
        for reason in ('GROUP_RESERVED','PUBLIC_ALIAS_CLAIMED','CURRENT_PUBLIC_OCCUPIED'):
            bad=copy.deepcopy(c[0]);bad.update(eligible=False,reasons=[reason])
            target,d=select(q,[bad],m,f,cert)
            self.assertIsNone(target)
            self.assertEqual(set(d['candidates']),{'NEW'})
            self.assertEqual(d['unscored_candidates'][0]['selector_reasons'],[reason])
        bad=copy.deepcopy(c[0]);bad['geometry_history'][-1]['neighbors']=[8]
        self.assertTrue(qualification(bad,q,SEGMENT))
        target,d=select(q,[bad],m,f,cert)
        self.assertIsNone(target)
        self.assertEqual(len(d['unscored_candidates']),1)

    def test_dummy_margin_positive_depth_and_public_dedup_unchanged(self):
        q,c,m,f,cert=fixture()
        _,d=select(q,c+[copy.deepcopy(c[0])],m,f,cert)
        self.assertEqual(d['unique_physical_candidates'],2)
        self.assertEqual(len(d['duplicate_public_facts_not_extra_prior_votes']),1)
        c.append(candidate(8))
        target,d=select(q,c,m,f,cert)
        self.assertIsNone(target)
        self.assertEqual(d['margin'],0.)
        c=[candidate(z=100000.)]
        target,d=select(q,c,m,f,cert)
        self.assertIsNone(target)
        self.assertLess(d['candidates']['OLD:7']['depth_log_lr'],0.)
        self.assertGreater(d['candidates']['OLD:7']['geometry_log_lr'],math.log(9))

    def test_body_tamper_and_inputs_are_not_mutated_or_added_to_past(self):
        q,c,m,f,cert=fixture()
        snapshot=copy.deepcopy((q,c,m,f,cert))
        _,d=select(q,c,m,f,cert)
        self.assertEqual((q,c,m,f,cert),snapshot)
        bad=copy.deepcopy(d['admission_body']);bad['query']['neighbors']=[]
        bad['body_sha256']=admission_hash(bad)
        self.assertFalse(validate_admission_body(bad))
        bad=copy.deepcopy(d['admission_body']);bad['qualified_components'][0]['median_mm']+=1.
        bad['body_sha256']=admission_hash(bad)
        self.assertFalse(validate_admission_body(bad))
        facts=d['candidates']['OLD:7']['depth_forecast']['sample_frames']
        self.assertEqual(facts,list(range(1,11)))
        self.assertNotIn(q['frame'],facts)


class ContactTransactionTests(unittest.TestCase):
    @staticmethod
    def fixture():
        # Explicit file import prevents old module search paths selecting an
        # earlier experiment's controller with the same Python module name.
        spec=importlib.util.spec_from_file_location('ds12_checked_contact_controller',HERE/'controller.py')
        controller=importlib.util.module_from_spec(spec);spec.loader.exec_module(controller)
        from test_ne import CONFIG, observation
        q,c,m,f,cert=fixture()
        bridge=controller.DepthNativeBridge(CONFIG)
        for frame in range(1,11):
            bridge.commit_once(bridge.preview(frame,(frame-1)*.1,
                [observation(7,19),observation(9,200)],{}))
        bridge.engine.alias[200]=dict(target=9,anchor=copy.deepcopy(bridge.engine.bank[9]['anchor']),
            commit_frame=10,source='F9_EVENT_NUMERIC',transaction_version=10)
        current=observation(100,4)
        current.update(box=q['bbox'],area=q['area'],neighbors=list(q['neighbors']))
        observations=[current,observation(200,200)]
        profiles={o['id']:dict(frame=11,id=o['id'],mask=o['mask'],
            core=m[o['id']]['core'],whole=m[o['id']]['core']) for o in observations}
        view=bridge.preview(11,1.,observations,profiles)
        view['contact_certificates']=cert
        c[0]['anchor']=copy.deepcopy(bridge.engine.bank[7]['anchor'])
        target,detail=select(q,c,m,f,cert)
        assert target==7
        return controller,bridge,view,{100:c[0]},detail['admission_body'],m

    def test_actual_contact_stage_then_first_publish_preserves_outside_alias_and_masks(self):
        _,bridge,view,candidates,body,_=self.fixture()
        snapshot=copy.deepcopy(bridge.engine.__dict__);version=bridge.version
        alias=copy.deepcopy(bridge.engine.alias[200])
        tx,error=bridge.stage_birth_reconnect(view,{100:7},candidates,{100:body})
        self.assertIsNone(error)
        self.assertIsNotNone(tx)
        self.assertEqual(bridge.engine.__dict__,snapshot)
        self.assertEqual(bridge.version,version)
        self.assertEqual(view['observations'][0]['neighbors'],[200])
        self.assertEqual(tx['mapping'],{100:7,200:9})
        self.assertEqual(tx['trace']['ds12_birth_reconnect']['admission_bodies']['100'],body)
        ids,trace=bridge.commit_once(view,tx)
        self.assertEqual(ids,{100:7,200:9})
        self.assertEqual(bridge.engine.alias[200],alias)
        self.assertEqual(bridge.engine.alias[100]['target'],7)
        self.assertEqual(trace['publication_effects']['new_source_publications'][100],7)
        self.assertEqual(set(ids),{o['id'] for o in view['observations']})
        self.assertEqual(len(ids),len(set(ids.values())))
        with self.assertRaises(AssertionError):bridge.commit_once(view,tx)

    def test_contact_stage_bad_binding_reserved_claim_and_occupied_reject_atomically(self):
        for problem in ('body_hash','neighbors','actual_certificate','stale','group','alias','occupied'):
            with self.subTest(problem=problem):
                _,bridge,view,candidates,body,_=self.fixture()
                if problem=='body_hash':body['body_sha256']='bad'
                if problem=='neighbors':
                    body['query']['neighbors']=[];body['body_sha256']=admission_hash(body)
                if problem=='actual_certificate':view['contact_certificates']={}
                if problem=='stale':view['version']-=1
                if problem=='group':bridge.engine.protected['GROUP']=dict(member_public=[7,8])
                if problem=='alias':bridge.engine.alias[333]=dict(target=7,anchor=candidates[100]['anchor'])
                if problem=='occupied':view['mapping'][200]=7
                snapshot=copy.deepcopy(bridge.engine.__dict__)
                tx,error=bridge.stage_birth_reconnect(view,{100:7},candidates,{100:body})
                self.assertIsNone(tx)
                self.assertIsNotNone(error)
                self.assertEqual(bridge.engine.__dict__,snapshot)

    def test_admitted_current_contact_stays_risk_and_never_enters_clean_history(self):
        controller,bridge,view,candidates,body,measured=self.fixture()
        from depth_state import DepthState
        manager=controller.DepthNativeManager('R12_RAW',bridge,{},dict(max_episode_seconds=10.),{})
        raw=DepthState(SEGMENT,'R12_RAW_SENSOR_SUPPORT')
        tx,error=bridge.stage_birth_reconnect(view,{100:7},candidates,{100:body})
        self.assertIsNone(error)
        ids,_=bridge.commit_once(view,tx)
        raw.update(100,measured[100],11,1.,ids[100],bridge.epochs[100],
            manager._generation(100,11),'QUALITY_OR_CONTACT_RISK')
        row=dict(frame=11,time=1.,observations=view['observations'])
        manager.after(row,view['profiles'])
        self.assertFalse(raw.live[100]['samples'])
        self.assertEqual(raw.live[100]['latest_fragment'],[])
        self.assertEqual(raw.live[100]['cache'][-1]['observation_class'],'QUALITY_OR_CONTACT_RISK')
        self.assertFalse(manager.clean.get(100))
        self.assertEqual(manager.risk[100][-1]['neighbors'],[200])
        self.assertEqual(body['query']['neighbors'],[200])


def main():
    stream=io.StringIO()
    suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(cls)
        for cls in (ContactSelectorTests,ContactTransactionTests))
    result=unittest.TextTestRunner(stream=stream,verbosity=2).run(
        suite)
    print(stream.getvalue(),end='')
    report=dict(status='PASS' if result.wasSuccessful() else 'FAIL',pass_all=result.wasSuccessful(),
        tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),
        sources=[artifact(HERE/'reconnect.py'),artifact(HERE/'reconnect_tests.py'),
                 artifact(HERE/'contact_measurement.py')],
        no_GT=True,new_model_http=0,cost_usd=0,
        scope='Actual synthetic source certificates; fixed normalized mixture; frozen clean output exact; real atomic contact transaction and risk-history checks')
    if '--write-new' in sys.argv:write_new(HERE/'RECONNECT_CHECKS.json',report)
    if not result.wasSuccessful():raise SystemExit(1)


if __name__=='__main__':main()
