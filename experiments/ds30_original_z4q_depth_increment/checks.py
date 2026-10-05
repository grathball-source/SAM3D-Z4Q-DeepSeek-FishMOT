"""Source deduplication and real copy-on-write state checks, without references."""
from common import *
import copy,unittest,numpy as np,runpy
from datetime import datetime,timezone
runpy.run_path(str(ROOT/'experiments/ds20_pending_confirmation_isolation/guard.py'),run_name='ds30_check_guard')
from increment_controller import IncrementBridge,EvidenceBridge,branch_state
from bridge import Bridge
from history import History
from association import pair,choose,freeze_pre
from evidence import Sources
from measurement import Measurement
fixtures=module('ds30_synthetic_fixtures',ROOT/'experiments/ds25_contact_local_layers/source_checks.py')

def obs(n,x):return dict(id=n,mask=f'n:{n}',box=[x,0.,x+20.,20.],area=400,presence=.99,score_birth=.99,neighbors=[],depth=dict(n=400,valid_fraction=1.,median=700.,mad=2.))
def profiles(frame,objects):return {o['id']:dict(id=o['id'],frame=frame,mask=o['mask'],whole=copy.deepcopy(o['depth']),core=copy.deepcopy(o['depth'])) for o in objects}
def warm(cls=IncrementBridge):
    b=cls(read(CONFIG_PATH))
    for f in range(1,11):
        o=[obs(1,0),obs(2,100),obs(3,200)];b.commit_once(b.preview(f,f/30,o,profiles(f,o)))
    return b
def staged():
    b=warm();snapshot={k:copy.deepcopy(b.engine.bank[k]) for k in (1,2)}
    b.engine.alias[77]=dict(target=3,anchor=copy.deepcopy(b.engine.bank[3]['anchor']),commit_frame=10,source='OUTSIDE_REPAIR')
    o=[obs(101,0),obs(102,100),obs(77,200)];v=b.preview(11,11/30,o,profiles(11,o))
    e=dict(q=11,bank_snapshot=snapshot,post_roles={101:[{}],102:[{}]},public_ids=[1,2])
    return b,v,e
class Checks(unittest.TestCase):
    def test_readonly_observer_and_no_info_full_state(self):
        b,baseline=warm(),warm(Bridge);self.assertEqual(digest(branch_state(b)),digest(branch_state(baseline)))
        s=EvidenceBridge(read(CONFIG_PATH));s.sync(b);s.engine.protected['SYNTHETIC']=dict(member_sources=[1,2])
        s.engine.bank[1]['anchor']['frame']=1
        for f in range(11,15):
            o=[obs(1,0),obs(2,100),obs(3,200)]
            b.commit_once(b.preview(f,f/30,o,profiles(f,o)))
            baseline.commit_once(baseline.preview(f,f/30,o,profiles(f,o)))
            self.assertEqual(digest(branch_state(b)),digest(branch_state(baseline)))
    def test_atomic_pair_and_other_fish_preserved(self):
        b,v,e=staged();before=digest(branch_state(b));vp=digest(vars(v['engine']))
        tx,error=b.stage_group_restore(v,e,{101:2,102:1});self.assertIsNone(error)
        self.assertEqual(tx['mapping'],{101:2,102:1,77:3})
        self.assertEqual(tx['engine'].alias[77],v['engine'].alias[77]);self.assertEqual(tx['engine'].bank[3],v['engine'].bank[3])
        self.assertEqual(digest(branch_state(b)),before);self.assertEqual(digest(vars(v['engine'])),vp)
        ids,_=b.commit_once(v,tx)
        with self.assertRaises(AssertionError):b.commit_once(v,tx)
        o=[obs(101,0),obs(102,100),obs(77,200)]
        self.assertEqual(b.commit_once(b.preview(12,.4,o,profiles(12,o)))[0],ids)
    def test_failed_transaction_and_changed_anchor_no_pollution(self):
        b,v,e=staged();before=digest(branch_state(b))
        self.assertEqual(b.stage_group_restore(v,e,{101:2,102:2})[1],'invalid_bijection')
        e['bank_snapshot'][1]['anchor']['frame']=5
        self.assertEqual(b.stage_group_restore(v,e,{101:2,102:1})[1],'actual_target_anchor_changed_since_pre')
        self.assertEqual(digest(branch_state(b)),before)
        expected=copy.deepcopy(b);Bridge.commit_once(expected,v);b.commit_once(v)
        self.assertEqual(digest(branch_state(b)),digest(branch_state(expected)))
    def test_shared_points_remeasured_not_whole_layer_discarded(self):
        producer=Measurement('DEPTH_INCREMENT');arrays=fixtures._fixture();depth,index,sensor,masks,_=arrays
        pa=np.flatnonzero(masks[1]);pb=np.flatnonzero(masks[2]);index.ravel()[pb[0]]=index.ravel()[pa[0]]
        binding=fixtures._binding(producer,arrays);shared=index.ravel()[pa[:1]]
        packets=[]
        for n in (1,2):
            f,m=producer.measure_region(depth,index,sensor,masks,masks[n],'SYNTHETIC',1,0,0.,source_binding=binding,excluded_native_sources=shared)
            self.assertEqual(f['original_roi_area'],1200);self.assertEqual(f['joint_shared_aligned_pixel_n'],1)
            self.assertEqual(f['summary']['n'],1199);self.assertTrue(f['qualified_support_ids'])
            used=np.concatenate([m['selected_positions'][s] for s in f['qualified_support_ids']])
            self.assertFalse(np.isin(index.ravel()[used],shared).any())
            packets.append(dict(fact=f,maps=m,source_index=index))
        p=pair(*packets);self.assertGreater(p['probability_A_nearer'],.9)
        self.assertAlmostEqual(p['common_null_weight'],1-(1199/1200)**2)
        self.assertAlmostEqual(p['probability_A_nearer']+pair(*packets[::-1])['probability_A_nearer'],1.)
    def test_all_shared_or_missing_common_null(self):
        producer=Measurement('DEPTH_INCREMENT');arrays=fixtures._fixture();depth,index,sensor,masks,_=arrays
        binding=fixtures._binding(producer,arrays);packets=[]
        for n in (1,2):
            f,m=producer.measure_region(depth,index,sensor,masks,masks[n],'SYNTHETIC',1,0,0.,source_binding=binding,excluded_native_sources=index[masks[n]])
            self.assertEqual(f['original_roi_missing_n'],0);self.assertEqual(f['summary']['n'],0)
            packets.append(dict(fact=f,maps=m,source_index=index))
        self.assertEqual(pair(*packets)['probability_A_nearer'],.5)
    def test_anonymous_empty_neighbors_and_registry(self):
        b=warm();h=History('synthetic');o=[obs(1,0),obs(2,100)]
        h.observe(dict(frame=10,time=10/30,observations=o),{1:1,2:2},{1:1,2:1},b.engine)
        e=dict(public_ids=[1,2],bank_snapshot={k:copy.deepcopy(b.engine.bank[k]) for k in (1,2)})
        prior=freeze_pre(h,e)
        h.observe(dict(frame=11,time=11/30,observations=o),{1:1,2:2},{1:1,2:1},b.engine,{1,2})
        self.assertEqual(freeze_pre(h,e),prior);self.assertFalse(h.live)
    def test_future_rejected(self):
        s=object.__new__(Sources);s.cutoff=5;s.frames={1:None}
        for method,args in ((Sources.masks,(6,)),(Sources.arrays_at,(6,)),(Sources.packet,('DEPTH_INCREMENT',6,1))):
            with self.assertRaises(AssertionError):method(s,*args)
    def test_missing_reference_is_defer_not_geometry_commit(self):
        pre={r:dict(samples=[]) for r in ('A','B')};e=dict(post_roles={1:[{}],2:[{}]},public_ids=[1,2])
        choice,d=choose(e,pre,dict(frame=2,time=.06,observations=[obs(1,0),obs(2,100)]),None,'DEPTH_INCREMENT')
        self.assertEqual(choice,'DEFER');self.assertFalse(d['depth_used'])
    def test_complete_geometry_without_depth_is_still_defer(self):
        pre={r:dict(samples=[dict(frame=1,time=.03,box=[x,0,x+20,20],version=[n,1,n,1],native=n)]) for r,n,x in [('A',1,0),('B',2,100)]}
        empty=dict(fact=dict(fact_id='SYNTHETIC_NULL',frame=1,reason='MISSING',layers=[],original_roi_area=100),maps={},source_index=np.empty((0,0)))
        class Null:
            def unique_pair(self,*args):return empty,empty,dict(shared_unique_sources=0,remeasured=False)
        e=dict(post_roles={101:[{}],102:[{}]},public_ids=[1,2])
        choice,d=choose(e,pre,dict(frame=2,time=.06,observations=[obs(101,0),obs(102,100)]),Null(),'DEPTH_INCREMENT')
        self.assertEqual(d['geometry_choice'],'H1');self.assertEqual(choice,'DEFER');self.assertFalse(d['depth_used'])
if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Checks))
    write_new(HERE/'checks'/('CHECKS_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.json'),
        dict(status='PASS' if result.wasSuccessful() else 'FAIL',tests=result.testsRun,synthetic_not_research_success=True,new_model_http=0,cost_usd=0))
    if not result.wasSuccessful():raise SystemExit(1)
