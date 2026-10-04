"""Necessary semantic, numerical and state checks; no research acceptance gate."""
from common import *
import unittest,copy,math
import numpy as np
from evidence import pair_order,combine,representative
from history import History,measurement
from relative_controller import OrderBridge
from bridge import Bridge

def proxy(z):return dict(status='AVAILABLE_PROXY',z_mm=z,sigma_mm=22.,fact_id=f'synthetic/{z}')
def pre():return [dict(frame=f,time=f/30,A=proxy(700),B=proxy(1000)) for f in range(1,11)]

class Checks(unittest.TestCase):
    def test_opposite_order_refutes_one_hypothesis(self):
        a=pair_order(pre(),dict(A=proxy(1000),B=proxy(700)),11/30)
        b=pair_order(pre(),dict(A=proxy(700),B=proxy(1000)),11/30)
        self.assertTrue(a['veto']);self.assertFalse(b['veto'])
    def test_missing_unknown_not_advantage(self):
        x=pair_order(pre(),dict(A=dict(status='UNKNOWN'),B=proxy(1000)),11/30)
        self.assertEqual(x['status'],'UNKNOWN');self.assertFalse(x['veto'])
    def test_expired_pair_does_not_refute(self):self.assertFalse(pair_order(pre(),dict(A=proxy(1000),B=proxy(700)),20)['veto'])
    def test_pre_gap_rejected(self):
        p=pre();p.pop(3);self.assertEqual(pair_order(p,dict(A=proxy(1000),B=proxy(700)),11/30)['reason'],'PRE_GAP_OR_NONMONOTONIC_TIME')
    def test_reversal_is_unknown(self):
        p=pre();p[3]['A'],p[3]['B']=p[3]['B'],p[3]['A']
        self.assertEqual(pair_order(p,dict(A=proxy(1000),B=proxy(700)),11/30)['reason'],'CONFIDENT_PRE_ORDER_REVERSAL')
    def test_long_gap_diffuses_instead_of_certifying(self):
        self.assertEqual(pair_order(pre(),dict(A=proxy(1000),B=proxy(700)),8)['reason'],'WEAK_PROPAGATED_OR_CURRENT_ORDER')
    def test_conflicting_partners_keep_edge(self):
        self.assertFalse(combine([dict(status='CONFLICT'),dict(status='COMPATIBLE')])['veto'])
        self.assertTrue(combine([dict(status='CONFLICT'),dict(status='UNKNOWN')])['veto'])
    def test_no_background_support_stays_unknown(self):
        depth=np.full((90,140),1000.,'f4');index=np.arange(depth.size,dtype='i4').reshape(depth.shape)
        mask=np.zeros(depth.shape,bool);mask[30:55,35:85]=True
        from mixed_depth import array_binding
        binding=dict(global_frame=0,time=0.,actual_fields_read=['depth_mm','source_index'],native_fields_read=['current_native_depth_mm'],
            aligned_depth=array_binding(depth),aligned_source_index=array_binding(index),native_depth=array_binding(depth),GT_read=False,RGB_read=False,restored_read=False)
        fact,_=measurement.measure_local_background(depth,index,depth,{1:mask},1,'synthetic',1,0,0.,source_binding=binding,expected_source_binding=binding)
        self.assertEqual(representative(fact)['status'],'UNKNOWN')
        depth[mask]=700;binding['aligned_depth']=binding['native_depth']=array_binding(depth)
        fact,_=measurement.measure_local_background(depth,index,depth,{1:mask},1,'synthetic',1,0,0.,source_binding=binding,expected_source_binding=binding)
        self.assertEqual(representative(fact)['status'],'AVAILABLE_PROXY')
        f=copy.deepcopy(fact);f['components'].append(copy.deepcopy(f['components'][0]))
        self.assertEqual(representative(f)['reason'],'MULTIPLE_QUALIFIED_SUPPORTS_NO_PEAK_SELECTION')
    def test_real_controller_preview_does_not_mutate_original(self):
        from runner import engine_state
        branch=OrderBridge(read(CONFIG_PATH));before=digest(engine_state(branch.engine))
        o=dict(id=1,mask='n:1',area=100,box=[1,1,11,11],presence=1.,score_birth=1.,neighbors=[],depth=dict(n=100,valid_fraction=1.,median=700.,mad=0.))
        view=branch.preview(1,0.,[o],{})
        self.assertEqual(before,digest(engine_state(branch.engine)))
        branch.commit_once(view);self.assertEqual(branch.previous,{1:1})
        with self.assertRaises(AssertionError):branch.commit_once(view)
    def test_history_risk_break_retains_exact_old_anchor(self):
        class Engine:
            retired=set()
            def quality(self,o):return True
        e=Engine();h=History('test');mapping={1:1};epochs={1:1}
        def row(f,neighbors):return dict(frame=f,time=f/30,observations=[dict(id=1,mask='n:1',box=[0,0,10,10],area=100,neighbors=neighbors)])
        e.bank={1:dict(anchor=dict(frame=1,native_id=1,canonical_id=1,mask='n:1'))}
        h.observe(row(1,[]),mapping,epochs,e);old_key=next(iter(h.anchors))
        h.observe(row(2,[2]),mapping,epochs,e)
        self.assertNotIn(1,h.live);self.assertIn(old_key,h.anchors)
        self.assertEqual(h.frames[2]['objects'][1]['observation_class'],'ANONYMOUS_RISK_OBSERVATION')
        e.bank[1]['anchor']['frame']=3;h.observe(row(3,[]),mapping,epochs,e)
        self.assertEqual(len(h.live[1]),1)
    def test_generation_gap_and_epoch_change(self):
        h=History('test');h.previous[1]=dict(frame=1,generation=2)
        self.assertEqual(h.current_version(1,3,{1:7},{1:9}),[1,3,7,9])
    def test_real_raw_endpoint_and_future_read_rejection(self):
        import io
        from history import Sources
        name='feeding_000000_000199';base=input_dir(name)
        obs=next(r for r in rows(base/'observations.jsonl.gz') if r['frame']==160)
        assignment=next(r for r in rows(base/'assignments.jsonl.gz') if r['frame']==160)
        measured=next(r for r in rows(base/'DEPTH_OBSERVATIONS.jsonl.gz') if r['frame']==160)
        provider=Sources(name,io.StringIO())
        try:
            provider.add(obs,assignment,measured['raw_source_binding'])
            a=provider.measure(160,26)
            self.assertEqual(a['status'],'UNKNOWN')
            with self.assertRaises(AssertionError):provider.measure(161,26)
        finally:provider.close()
    def test_actual_two_matrix_hooks_preserve_original_preview(self):
        from bridge import stream
        from runner import engine_state
        class Veto:
            def __init__(self,row,selected):self.row=row;self.selected=selected
            def check(self,e,o,k,a,rule):
                return dict(veto=(rule,o['id'],k)==self.selected,status='TEST_ONLY_SYNTHETIC_REFUTATION',reason='TEST_ONLY')
            def __deepcopy__(self,memo):return self
        # Read genuine saved observations; injected evidence exercises control flow only.
        for name,end,rule,source in [('feeding_000000_000199',160,'D1_DELAYED',26),('feeding_000351_000555',118,'BIRTH_REFINE',63)]:
            branch=OrderBridge(read(CONFIG_PATH));base=input_dir(name);exercised=False
            for row,p in stream(base/'observations.jsonl.gz',base/'profiles.jsonl.gz'):
                before=digest(engine_state(branch.engine));view=branch.preview(row['frame'],row['time'],row['observations'],p)
                if row['frame']==end:
                    actions=[x for x in view['trace']['events'] if x.get('kind')=='reconnect' and x.get('accepted') and
                        ('BIRTH_REFINE' if x.get('phase')=='birth' else 'D1_DELAYED')==rule]
                    if rule=='D1_DELAYED':actions=[x for x in actions if x['native_id']==source]
                    self.assertTrue(actions,'Real source does not exercise intended hook')
                    action=actions[0];source=action['native_id'];target=action['canonical_id']
                    branch.engine.relative_context=Veto(row,(rule,source,target))
                    trial=branch.preview(row['frame'],row['time'],row['observations'],p)
                    self.assertEqual(before,digest(engine_state(branch.engine)))
                    checks=trial['trace']['edges' if rule=='D1_DELAYED' else 'birth_checks']
                    blocked=[x for x in checks if x.get('native_id')==source and x.get('canonical_id')==target]
                    self.assertTrue(blocked and blocked[0]['edge_veto']['veto'])
                    self.assertNotEqual(trial['mapping'][source],target)
                    self.assertEqual(len(set(trial['mapping'].values())),len(trial['mapping']))
                    exercised=True;break
                branch.commit_once(view)
            self.assertTrue(exercised)

if __name__=='__main__':
    from datetime import datetime,timezone
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Checks)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    write_new(HERE/'checks'/('CHECKS_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.json'),dict(status='PASS' if result.wasSuccessful() else 'FAIL',tests=result.testsRun,
        failures=len(result.failures),errors=len(result.errors),model_http=0,cost_usd=0,GT_read=False))
    assert result.wasSuccessful()
