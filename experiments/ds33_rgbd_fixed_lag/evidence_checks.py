"""Direct synthetic source/observation/common-null checks; no GT or data reads."""
import copy
import json
import unittest
from types import SimpleNamespace

import numpy as np

from common import CFG, ROOT, module
from evidence import ContourMemory, WindowEvidence, endpoint_depth_usable

depth = module('ds33_evidence_checks_actual_ds31_depth', ROOT / 'experiments/ds31_persistent_identity_depth/depth.py')


def mask(x=4):
    value=np.zeros((32,64),bool);value[8:24,x:x+16]=True;return value


def row(frame, native=(3,), neighbors=(), bad=()):
    observations=[dict(id=n,mask=f'n:{n}',neighbors=list(neighbors) if n==3 else [],quality=n not in bad) for n in native]
    return dict(frame=frame,time=float(frame),observations=observations)


def quality(observation): return observation['quality']


def extract(frame,native=3):
    core=dict(fact_id=f'S/F{frame}/n:{native}/core/raw',eligible_single=True,quality_usable=True,
        source_ownership_exclusive=True,source_population_unverified_n=0,status='SINGLE_COMPATIBLE_LAYER',
        reason='SINGLE_LAYER',mixture_flag=False,independent_mixture_flag=False,inclusive_mixture_flag=False,
        substantial_layer_count=1,inclusive_substantial_layer_count=1,
        summary=dict(n=100,area=100,valid_fraction=1.,median=1200.,mad=2.),
        roi_definition='DS12_EXACT_L2_EXCLUSIVE_COMPONENT_ADAPTIVE_CORE',
        roi_binding=dict(sha256='a'*64),selected_source_index_binding=dict(sha256='b'*64))
    return depth.extract(dict(schema='DS18_SAME_ROI_RAW_MEASUREMENT_V1',no_cross_ROI_certification=True,
        core=core,whole=copy.deepcopy(core),fact_id=f'S/F{frame}/n:{native}/raw',
        certificate_sha256='c'*64,native=native,frame=frame,time=float(frame)))


def anchor(frame=1,native=1,public=1):
    return dict(frame=frame,native_id=native,mask=f'n:{native}',canonical_id=public)


def target(value=None, depth_available=True):
    value=mask() if value is None else value
    return dict(status='SOURCE_BOUND_CONTOUR_HYPOTHESIS',anchor=anchor(),namespace='branch',generation=1,
        public_epoch=0,mask=value.copy(),reliable=value.copy(),depth_mask=value.copy(),
        depth_summary=dict(status='AVAILABLE_CONDITIONAL_3D_SUPPORT' if depth_available else 'UNKNOWN'),
        target_bank_anchor=anchor(),action_reference_anchors=[anchor(frame=0)],anchor_depth_usable=True,
        anchor_depth_quality=extract(1,1)['quality'],anchor_depth_fact_binding=dict(fact_id='synthetic_pre'))


def request(q=10):
    return dict(frame=q,time=float(q),sources=[3],targets=[1])


def options():
    return [dict(id='KEEP',mapping={3:1}),dict(id='SELF',mapping={3:3})]


class IdentityPair:
    def warp_forward(self,value,quality=False):return value.copy()
    def point_support(self,value):return value.copy(),dict(status='AVAILABLE_CONDITIONAL_3D_SUPPORT')


def feed(evidence,frame,source_mask=None,neighbors=(),extra=None,bad=(),measure=None,pair=None):
    masks={3:mask() if source_mask is None else source_mask}
    if extra:masks.update(extra)
    actual=row(frame,tuple(masks),neighbors,bad)
    # DS14 profiles do not have neighbors or any authenticated public identity.
    profiles={n:dict(frame=frame) for n in masks}
    measured={3:extract(frame)} if measure is None else measure
    evidence.update(actual,masks,profiles,pair or IdentityPair(),measured,quality)


class EvidenceChecks(unittest.TestCase):
    def test_three_raw_clean_after_contact_not_profiles_or_candidate_labels(self):
        evidence=WindowEvidence(request(),{1:target()},False)
        feed(evidence,10,neighbors=[8]);self.assertFalse(evidence.samples[-1]['clean'])
        self.assertEqual(evidence.assess(options())['status'],'WAIT')
        for f in (11,12):
            feed(evidence,f);self.assertEqual(evidence.assess(options())['status'],'WAIT')
        feed(evidence,13);result=evidence.assess(options())
        self.assertEqual(result['confirmation_frames'],[11,12,13])
        self.assertEqual(result['status'],'DECIDED');self.assertEqual(result['selected_option'],'KEEP')
        comparison=evidence.samples[-1]['comparisons']['3:1']
        self.assertTrue(comparison['anonymous_raw_current_observation'])
        self.assertTrue(comparison['candidate_identity_not_certified_by_confirmation'])
        self.assertTrue(comparison['propagated_contour_is_hypothesis'])
        self.assertEqual(comparison['actual_current_observation']['native'],3)

    def test_depth_missing_any_edge_is_common_null_not_candidate_reward(self):
        rich=WindowEvidence(request(),{1:target()},True)
        rgb=WindowEvidence(request(),{1:target()},False)
        for f in (10,11,12):feed(rich,f);feed(rgb,f)
        self.assertEqual(rich.assess(options())['depth_common_component_weight'],CFG['depth_weight'])
        # One target's unavailable depth nulls depth for every option, preserving RGB scores.
        rich.samples[-1]['comparisons']['3:1']['depth_available']=False
        actual,expected=rich.assess(options()),rgb.assess(options())
        self.assertEqual(actual['depth_common_component_weight'],0.)
        self.assertEqual(actual['scores'],expected['scores'])
        self.assertEqual(actual['selected_option'],expected['selected_option'])
        req=request();req['targets']=[1,2]
        evidence=WindowEvidence(req,{1:target(),2:target(depth_available=False)},True)
        for f in (10,11,12):feed(evidence,f)
        self.assertEqual(evidence.assess(options())['depth_common_component_weight'],0.)

    def test_missing_or_empty_depth_quality_never_available(self):
        actual=row(10);measured=extract(10)
        self.assertTrue(endpoint_depth_usable(measured,actual,3))
        for key in tuple(measured['quality']):
            if key in ('core_status','core_reason','physical_surface_identity'):continue
            weakened=copy.deepcopy(measured);weakened['quality'].pop(key)
            self.assertFalse(endpoint_depth_usable(weakened,actual,3))
        for measured in (None,depth.extract(None),dict(usable=True,frame=10,time=10.,native=3,quality={})):
            self.assertFalse(endpoint_depth_usable(measured,actual,3))
        evidence=WindowEvidence(request(),{1:target()},True)
        for f in (10,11,12):feed(evidence,f,measure={3:depth.extract(None)})
        self.assertEqual(evidence.assess(options())['depth_common_component_weight'],0.)
        empty=target();empty['depth_mask'][:]=False
        evidence=WindowEvidence(request(),{1:empty},True);feed(evidence,10)
        self.assertFalse(evidence.samples[-1]['comparisons']['3:1']['depth_available'])
        self.assertIsNone(evidence.samples[-1]['comparisons']['3:1']['depth_affinity'])

    def test_exact_bank_anchor_does_not_substitute_action_reference(self):
        memory=ContourMemory('branch');bank=anchor();actual=row(1,(1,))
        branch=SimpleNamespace(engine=SimpleNamespace(bank={1:dict(anchor=bank)},quality=quality),previous={1:1},epochs={1:0})
        memory.advance(actual,None);memory.observe(actual,{1:mask()},branch,{1:extract(1,1)})
        now=row(2);memory.advance(now,IdentityPair())
        req=request(q=2);req['candidate_edges']=[dict(public_id=1,action_reference_anchor=anchor(frame=0))]
        capture=memory.capture(req,branch,IdentityPair())[1]
        self.assertEqual(capture['anchor'],bank);self.assertEqual(capture['target_bank_anchor'],bank)
        self.assertEqual(capture['action_reference_anchors'],[anchor(frame=0)])
        self.assertNotEqual(capture['anchor'],capture['action_reference_anchors'][0])
        self.assertTrue(capture['anchor_depth_usable'])
        self.assertEqual(capture['anchor_depth_fact_binding']['frame'],1)
        self.assertEqual(capture['anchor_depth_fact_binding']['native'],1)
        self.assertEqual(memory.capture(req,branch,IdentityPair())[1]['status'],'SOURCE_BOUND_CONTOUR_HYPOTHESIS')
        changed=copy.deepcopy(branch);changed.engine.bank[1]['anchor']=anchor(frame=0)
        self.assertEqual(memory.capture(req,changed,IdentityPair())[1]['status'],'UNKNOWN')

    def test_missing_or_mixed_pre_depth_is_common_null_but_RGB_remains(self):
        for pre_measure in (None,extract(1,1)):
            if pre_measure:pre_measure['quality']['whole_multilayer']=True;pre_measure['usable']=False
            memory=ContourMemory('branch');actual=row(1,(1,))
            branch=SimpleNamespace(engine=SimpleNamespace(bank={1:dict(anchor=anchor())},quality=quality),previous={1:1},epochs={1:0})
            memory.advance(actual,None);memory.observe(actual,{1:mask()},branch,{1:pre_measure})
            memory.advance(row(2),IdentityPair());captured=memory.capture(request(q=2),branch,IdentityPair())
            self.assertEqual(captured[1]['status'],'SOURCE_BOUND_CONTOUR_HYPOTHESIS')
            self.assertFalse(captured[1]['anchor_depth_usable'])
            evidence=WindowEvidence(request(q=2),captured,True)
            for f in (2,3,4):feed(evidence,f)
            result=evidence.assess(options())
            self.assertEqual(result['depth_common_component_weight'],0.)
            self.assertEqual(result['status'],'DECIDED');self.assertEqual(result['selected_option'],'KEEP')

    def test_memory_current_contact_or_bad_quality_does_not_certify_anchor(self):
        for neighbors,bad in (([8],()),((),(3,))):
            memory=ContourMemory('branch');actual=row(1,neighbors=neighbors,bad=bad)
            branch=SimpleNamespace(engine=SimpleNamespace(bank={3:dict(anchor=anchor(1,3,3))},quality=quality),previous={3:3},epochs={3:0})
            memory.advance(actual,None);memory.observe(actual,{3:mask()},branch)
            self.assertEqual(memory.tracks,{})

    def test_SELF_requires_clean_actual_elsewhere_with_reliable_overlap(self):
        for neighbors,bad,trusted in (([8],(),True),((),(8,),True),((),(),False)):
            evidence=WindowEvidence(request(),{1:target()},False)
            if not trusted:
                # Plain propagated shape overlaps other mask; reliable portion does not.
                evidence.targets[1]['reliable']=mask(36)
            for f in (10,11,12):
                masks={3:mask(36),8:mask()};actual=row(f,(3,8),bad=bad)
                if neighbors:actual['observations'][1]['neighbors']=[9]
                evidence.update(actual,masks,{n:dict(frame=f) for n in masks},IdentityPair(),{3:extract(f)},quality)
            scores={s['id']:s for s in evidence.assess(options())['scores']}
            self.assertFalse(scores['SELF']['available'])
        evidence=WindowEvidence(request(),{1:target()},False)
        for f in (10,11,12):feed(evidence,f,source_mask=mask(36),extra={8:mask()})
        result=evidence.assess(options());self.assertEqual(result['selected_option'],'SELF')

    def test_UNKNOWN_old_anchor_never_favors_SELF(self):
        evidence=WindowEvidence(request(),{1:dict(status='UNKNOWN',reason='NO_EXACT_ANCHOR')},True)
        for f in (10,11,12):feed(evidence,f,source_mask=mask(36),extra={8:mask()})
        result=evidence.assess(options())
        self.assertEqual(result['status'],'UNKNOWN_KEEP');self.assertEqual(result['depth_common_component_weight'],0.)

    def test_missing_source_breaks_generation_and_does_not_join_reappearance(self):
        evidence=WindowEvidence(request(),{1:target()},False);feed(evidence,10)
        evidence.update(row(11,()),{}, {},IdentityPair(),{},quality)
        for f in (12,13,14):feed(evidence,f)
        self.assertTrue(evidence.broken)
        self.assertEqual(evidence.assess(options())['status'],'WAIT')

    def test_cutoff_q_plus_30_and_current_fact_binding(self):
        evidence=WindowEvidence(request(),{1:target()},True)
        for f in range(10,41):feed(evidence,f)
        self.assertEqual(evidence.assess(options())['evidence_max_frame'],40)
        before=json.dumps(evidence.numeric(),sort_keys=True)
        self.assertRaises(AssertionError,feed,evidence,41)
        self.assertEqual(json.dumps(evidence.numeric(),sort_keys=True),before)
        evidence=WindowEvidence(request(),{1:target()},True)
        self.assertRaises(AssertionError,feed,evidence,10,measure={3:extract(11)})
        self.assertEqual(evidence.samples,[])

    def test_caller_targets_and_numeric_are_detached_from_window_state(self):
        targets={1:target()};evidence=WindowEvidence(request(),targets,False)
        evidence.targets[1]['mask'][0,0]=True
        self.assertFalse(targets[1]['mask'][0,0])
        feed(evidence,10);record=evidence.numeric();record['samples'][0]['clean']=False
        self.assertTrue(evidence.samples[0]['clean'])
        json.dumps(evidence.numeric(),allow_nan=False)


if __name__=='__main__':unittest.main(verbosity=2)
