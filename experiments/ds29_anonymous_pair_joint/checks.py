"""Focused checks of the new uncertainty contract and actual transactional engine."""
from common import *
import copy,unittest,runpy,numpy as np
from datetime import datetime,timezone
guard=runpy.run_path(str(ROOT/'experiments/ds20_pending_confirmation_isolation/guard.py'),run_name='ds29_check_guard')
from association import pair,freeze_pre,choose
from joint_controller import JointBridge,engine_state
from bridge import Bridge
from history import History
from evidence import Sources

def packet(values=(700.,),weights=(.8,),offset=0):
    layers=[];positions={};start=0
    for i,(z,w) in enumerate(zip(values,weights)):
        size=int(round(w*100));layers.append(dict(support_id=str(i),qualified=True,independent_n=size,z_mm=z,sigma_mm=5.))
        positions[str(i)]=np.arange(start,start+size);start+=size
    return dict(fact=dict(fact_id='SYNTHETIC',frame=1,reason='SYNTHETIC',original_roi_area=100,layers=layers,
        inclusive_independent_partition_agreement=True,inclusive_independent_support_agreement=True),
        maps=dict(selected_positions=positions),source_index=np.arange(100).reshape(10,10)+offset)

def obs(n,x,z=700.):return dict(id=n,mask=f'n:{n}',box=[x,0.,x+20.,20.],area=400,presence=.99,score_birth=.99,neighbors=[],depth=dict(n=400,valid_fraction=1.,median=z,mad=2.))
def profiles(frame,observations):return {o['id']:dict(id=o['id'],mask=o['mask'],frame=frame,core=copy.deepcopy(o['depth']),whole=copy.deepcopy(o['depth'])) for o in observations}
def warm(cls=JointBridge):
    b=cls(read(CONFIG_PATH))
    for f in range(1,11):
        objects=[obs(1,0),obs(2,100,850),obs(3,200,900)]
        b.commit_once(b.preview(f,f/30,objects,profiles(f,objects)))
    return b

def protected():
    b=warm();b.engine.alias[77]=dict(target=3,anchor=copy.deepcopy(b.engine.bank[3]['anchor']),commit_frame=10,source='OUTSIDE_REPAIR')
    snapshot={k:copy.deepcopy(b.engine.bank[k]) for k in (1,2)}
    b.engine.protected['TEST']=dict(episode='TEST',generation=11,member_public=[1,2],member_sources=[1,2],suppressed=[101,102],outputs={101:1,102:2})
    b.engine.observation_frame=11;b.engine.observation_classes={101:'POST_UNASSIGNED',102:'POST_UNASSIGNED'}
    objects=[obs(101,0),obs(102,100,850),obs(77,200,900)]
    view=b.preview(11,11/30,objects,profiles(11,objects))
    episode=dict(id='TEST',generation=11,q=11,public_ids=[1,2],member_sources=[1,2],group_source=101,bank_snapshot=snapshot,
        post_roles={n:[dict(frame=11,time=11/30,center=[0.,0.])] for n in (101,102)})
    return b,view,episode

class Checks(unittest.TestCase):
    def test_mixed_all_supports_marginalized(self):
        a=packet((700,1100),(.4,.4));b=packet((900,),(.8,),100)
        result=pair(a,b);self.assertEqual(len(result['combinations']),2)
        self.assertAlmostEqual(result['probability_A_nearer'],.5)
        self.assertAlmostEqual(result['common_null_weight'],.36)
    def test_missing_and_shared_source_common_null(self):
        a=packet();self.assertEqual(pair(a,packet((),(),100))['probability_A_nearer'],.5)
        self.assertEqual(pair(a,packet((1000,),(.8,)))['probability_A_nearer'],.5)
        weak=packet();weak['fact']['inclusive_independent_support_agreement']=False
        self.assertEqual(pair(weak,packet((1000,),(.8,),100))['probability_A_nearer'],.5)
    def test_order_swap_complements_probability(self):
        a=packet();b=packet((1000,),(.8,),100)
        self.assertAlmostEqual(pair(a,b)['probability_A_nearer']+pair(b,a)['probability_A_nearer'],1.)
    def test_atomic_new_native_pair_with_outside_repair(self):
        b,view,e=protected();before=digest(vars(b.engine));tx,error=b.stage_group_restore(view,e,{101:2,102:1})
        self.assertIsNone(error);self.assertEqual(tx['mapping'],{101:2,102:1,77:3})
        self.assertEqual(tx['engine'].bank[3],view['engine'].bank[3]);self.assertEqual(tx['engine'].alias[77],view['engine'].alias[77])
        self.assertEqual(digest(vars(b.engine)),before)
        ids,_=b.commit_once(view,tx);self.assertEqual(ids[101],2);self.assertEqual(b.engine.alias[101]['target'],2)
        with self.assertRaises(AssertionError):b.commit_once(view,tx)
        objects=[obs(101,0),obs(102,100,850),obs(77,200,900)]
        self.assertEqual(b.commit_once(b.preview(12,.4,objects,profiles(12,objects)))[0],ids)
    def test_failed_stage_and_local_fallback_do_not_cover_outside(self):
        b,v,e=protected();before=digest(vars(b.engine))
        self.assertEqual(b.stage_group_restore(v,e,{101:2,102:2})[1],'invalid_bijection')
        corrupt=copy.deepcopy(v);corrupt['engine'].bank[1]['anchor']['frame']=5
        self.assertEqual(b.stage_group_restore(corrupt,e,{101:2,102:1})[1],'protected_reference_changed')
        tx,detail=b.local_fallback(v,e)
        self.assertFalse(tx['engine'].protected);self.assertEqual(tx['mapping'],v['mapping'])
        self.assertEqual(tx['engine'].alias[77],v['engine'].alias[77]);self.assertEqual(digest(vars(b.engine)),before)
    def test_group_neighbours_empty_not_clean(self):
        b,v,e=protected()
        for k in (1,2):self.assertEqual(v['engine'].bank[k]['anchor'],e['bank_snapshot'][k]['anchor'])
        for n in (101,102):self.assertNotIn('anchor',v['engine'].bank[n]);self.assertEqual(v['engine'].bank[n]['depth_history'],[])
    def test_no_event_exact_original_state(self):
        original,new=warm(Bridge),warm()
        self.assertEqual(digest(vars(original.engine)),digest(engine_state(new.engine)))
        self.assertEqual(original.previous,new.previous)
    def test_future_rejected_before_raw_read(self):
        fake=object.__new__(Sources);fake.cutoff=5;fake.frames={1:None}
        for method,args in ((Sources.masks,(6,)),(Sources.arrays_at,(6,)),(Sources.packet,('JOINT_DEPTH',6,1))):
            with self.assertRaises(AssertionError):method(fake,*args)
    def test_risk_break_preserves_exact_anchor_registry(self):
        b=warm();h=History('synthetic');o=[obs(1,0),obs(2,100,850)]
        h.observe(dict(frame=10,time=10/30,observations=o),{1:1,2:2},{1:1,2:1},b.engine)
        e=dict(public_ids=[1,2],bank_snapshot={k:copy.deepcopy(b.engine.bank[k]) for k in (1,2)})
        prior=freeze_pre(h,e);o[0]['neighbors']=[2];o[1]['neighbors']=[1]
        h.observe(dict(frame=11,time=11/30,observations=o),{1:1,2:2},{1:1,2:1},b.engine)
        self.assertEqual(freeze_pre(h,e),prior);self.assertNotIn(1,h.live)
        self.assertEqual(h.current_version(1,13,{1:1},{1:2}),[1,2,1,2])
    def test_null_equals_geometry_and_candidate_reorder_physical_invariant(self):
        pre={r:dict(samples=[dict(frame=1,time=.03,box=[x,0,x+20,20],version=[n,1,n,1],native=n)],status='SYNTHETIC') for r,n,x in [('A',1,0),('B',2,100)]}
        row=dict(frame=2,time=.06,observations=[obs(101,2),obs(102,98)])
        e=dict(post_roles={101:[{}],102:[{}]},public_ids=[1,2])
        class Null:
            def packet(self,arm,f,n):return packet((),(),n*100)
        a,da=choose(e,pre,row,Null(),'JOINT_GEOMETRY');b,db=choose(e,pre,row,Null(),'JOINT_DEPTH')
        self.assertEqual(a,b);self.assertEqual(da['candidates'],db['candidates'])
        rev=dict(e,post_roles={102:[{}],101:[{}]});c,dc=choose(rev,pre,row,Null(),'JOINT_DEPTH')
        self.assertEqual(db['candidates'][b]['mapping'],dc['candidates'][c]['mapping'])

if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Checks))
    write_new(HERE/'checks'/('CHECKS_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.json'),dict(
        status='PASS' if result.wasSuccessful() else 'FAIL',tests=result.testsRun,new_model_http=0,cost_usd=0))
    if not result.wasSuccessful():raise SystemExit(1)

