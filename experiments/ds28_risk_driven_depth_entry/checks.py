"""Necessary source, null, measurement and actual state checks before freezing."""
from common import *
import unittest, copy, runpy
guard=runpy.run_path(str(ROOT/'experiments/ds20_pending_confirmation_isolation/guard.py'),run_name='ds28_preflight_guard')
from evidence import endpoint,pair,Context,Sources,raw_source
from history import History,anchor_key
import numpy as np
from measurement_checks import run_checks
from engine_checks import EngineChecks
from datetime import datetime,timezone

class EvidenceChecks(unittest.TestCase):
    def packet(self,z=700.,support=.8,qualified=1):
        f=dict(fact_id='synthetic',frame=1,reason='SYNTHETIC',original_roi_area=100,
            inclusive_independent_partition_agreement=True,inclusive_independent_support_agreement=True,
            substantial_unresolved_support_ids=[],summary=dict(n=100,valid_fraction=1),
            layers=[dict(support_id=str(i),qualified=True,z_mm=z,sigma_mm=5.,independent_n=int(100*support)) for i in range(qualified)])
        return dict(fact=f,maps=dict(selected_positions={str(i):np.arange(int(100*support)) for i in range(qualified)}),source_index=np.arange(100).reshape(10,10))
    def test_background_missing_multiple_support_common_null(self):
        for count in (0,2):self.assertEqual(endpoint(self.packet(qualified=count))['status'],'COMMON_NULL')
        p=self.packet();p['fact']['substantial_unresolved_support_ids']=['bg']
        self.assertEqual(endpoint(p)['status'],'COMMON_NULL')
        p=self.packet();p['fact']['inclusive_independent_support_agreement']=False
        self.assertEqual(endpoint(p)['status'],'COMMON_NULL')
    def test_source_overlap_and_null_mixture(self):
        a=self.packet();b=self.packet(1000.)
        self.assertEqual(pair(a,b)['probability_A_nearer'],.5)
        b['source_index']+=100
        result=pair(a,b)
        self.assertEqual(result['status'],'CONDITIONAL_ORDER_PROXY')
        self.assertLess(result['probability_A_nearer'],result['distribution_probability'])
        empty=self.packet(qualified=0)
        self.assertEqual(pair(a,empty)['probability_A_nearer'],.5)
    def test_risk_generation_epoch_and_frozen_anchor(self):
        class E:
            retired=set()
            def quality(self,o):return True
        e=E();h=History('synthetic');mapping={1:1};epochs={1:1}
        def row(f,neighbors):return dict(frame=f,time=f/30,observations=[dict(id=1,mask='n:1',box=[0,0,10,10],area=100,neighbors=neighbors)])
        e.bank={1:dict(anchor=dict(frame=1,native_id=1,canonical_id=1,mask='n:1'))}
        h.observe(row(1,[]),mapping,epochs,e);key=anchor_key(e.bank[1]['anchor'])
        h.observe(row(2,[2]),mapping,epochs,e)
        self.assertIn(key,h.anchors);self.assertNotIn(1,h.live)
        self.assertEqual(h.frames[2]['objects'][1]['observation_class'],'ANONYMOUS_RISK_OBSERVATION')
        self.assertEqual(h.current_version(1,4,mapping,epochs),[1,2,1,1])
        e.bank[1]['anchor']['frame']=3;h.observe(row(3,[]),mapping,{1:2},e)
        self.assertEqual(len(h.live[1]),1)
    def test_future_source_rejected_before_read(self):
        fake=object.__new__(Sources);fake.cutoff=5;fake.frames={1:None}
        for method,args in ((Sources.masks,(6,)),(Sources.arrays_at,(6,)),(Sources.packet,(ARMS[2],6,1))):
            with self.assertRaises(AssertionError):method(fake,*args)

if __name__=='__main__':
    measurements=run_checks()
    suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(c) for c in (EngineChecks,EvidenceChecks)])
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    output=dict(status='PASS' if result.wasSuccessful() else 'FAIL',tests=result.testsRun,measurement_checks=measurements,
        GT_RGB_future_restored_network=False,source_reads=raw_source.FIELD_READS,new_model_http=0,cost_usd=0)
    write_new(HERE/'checks'/('CHECKS_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.json'),output)
    if not result.wasSuccessful():raise SystemExit(1)
