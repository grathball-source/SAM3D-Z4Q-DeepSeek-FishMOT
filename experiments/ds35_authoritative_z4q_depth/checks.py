"""Relevant evidence and actual-state contracts, not metric qualification."""
from common import *
import copy, unittest
from association import gate, DEPTH
from observer import EvidenceBridge, branch_state, History, LagBuffer
from transaction import DepthBridge

def detail():
    forecasts={1:dict(scale_mm=20.),2:dict(scale_mm=20.)}
    scores=[]
    for choice,order in [('H1',[10,20]),('H2',[20,10])]:
        edges=[]
        for public,native in zip((1,2),order):
            values={1:0. if native==10 else 1.,2:0. if native==20 else 1.}
            rows=[dict(costs=values,detail=dict(used=True,forecasts=copy.deepcopy(forecasts))) for _ in range(3)]
            edges.append(dict(public=public,native=native,depth_cost=values[public],geometry=.2,depth_rows=rows))
        scores.append(dict(choice=choice,edges=edges))
    return dict(status='CHOOSE',choice='H1',common_weights=dict(depth=.25),pre_frames={'A':[1,2,3],'B':[1,2,3]},scores=scores)

class Engine:
    def __init__(self):
        for f in ('alias','birth','pending','native_seen','native_runs','recent_core','return_quarantine','empty_quarantine','first_eligible','bank','view_bank'):setattr(self,f,{})
        self.retired=set()
        self.bank={1:dict(anchor=dict(frame=1,native_id=1,canonical_id=1,mask='n:1')),
                   2:dict(anchor=dict(frame=1,native_id=2,canonical_id=2,mask='n:2')),
                   90:dict(anchor=dict(frame=1,native_id=9,canonical_id=90,mask='n:9'))}
        self.alias[9]=dict(target=90,source='PRIOR_OWN_REPAIR')
    def quality(self,o):return o.get('quality',True)
    def step(self,f,t,observations,profiles):
        mapping={o['id']:self.alias.get(o['id'],{}).get('target',o['id']) for o in observations}
        return mapping,dict(events=[],native_return_checks=[])

def bridge():
    b=DepthBridge.__new__(DepthBridge);b.engine=Engine();b.version=2;b.previous={10:10,20:20,9:90};b.epochs={10:1,20:1,9:2};b.provenance={9:dict(source='PRIOR_OWN_REPAIR',target=90)}
    return b

def event():
    return dict(id='TEST',q=3,member_sources=[1,2],group_source=1,public_ids=[1,2],
        post_generations={10:1,20:1},bank_snapshot={1:dict(anchor=dict(frame=1,native_id=1,canonical_id=1,mask='n:1')),
        2:dict(anchor=dict(frame=1,native_id=2,canonical_id=2,mask='n:2'))},
        post_roles={n:[dict(frame=3,time=.3,source=n,source_generation=1)] for n in (10,20)})

class Checks(unittest.TestCase):
    def test_common_depth_gate(self):self.assertTrue(gate(detail())['eligible'])
    def test_disabled_never_commits(self):self.assertEqual(gate(detail(),False)['reason'],'DEPTH_DISABLED')
    def test_missing_depth_not_geometry_commit(self):
        d=detail();d['common_weights']['depth']=0.;self.assertFalse(gate(d)['eligible'])
    def test_one_point_pre_unknown(self):
        d=detail();d['pre_frames']['B']=[3];self.assertFalse(gate(d)['eligible'])
    def test_large_forecast_not_reward(self):
        d=detail();d['scores'][0]['edges'][0]['depth_rows'][0]['detail']['forecasts'][1]['scale_mm']=61.;self.assertFalse(gate(d)['eligible'])
    def test_weak_depth_no_override(self):
        d=detail();d['scores'][1]['edges'][0]['depth_cost']=.01;d['scores'][1]['edges'][1]['depth_cost']=.01;self.assertFalse(gate(d)['eligible'])
    def test_each_post_support_not_voting(self):
        d=detail();d['scores'][0]['edges'][0]['depth_rows'][2]['costs']={1:4.,2:0.};self.assertFalse(gate(d)['eligible'])
    def test_depth_joint_disagree(self):
        d=detail();d['choice']='H2';self.assertFalse(gate(d)['eligible'])
    def test_observer_deepcopy(self):
        b=bridge();s=EvidenceBridge.__new__(EvidenceBridge);s.engine=Engine();s.engine.protected={'e':dict(x=1)}
        old=digest(branch_state(b));s.sync(b);s.engine.bank[1]['anchor']['frame']=99;s.previous[10]=1
        self.assertEqual(digest(branch_state(b)),old);self.assertIn('e',s.engine.protected);self.assertFalse(hasattr(b.engine,'protected'))
    def test_joint_atomic_and_outside_repair(self):
        b=bridge();e=event();view=b.preview(3,.3,[dict(id=n,neighbors=[],mask='n:'+str(n)) for n in (10,20,9)],{})
        before=digest(branch_state(b));t,err=b.stage_event(view,e,{10:2,20:1});self.assertIsNone(err);self.assertIsNotNone(t)
        self.assertEqual(digest(branch_state(b)),before);b.commit_once(view,t)
        self.assertEqual(b.previous,{10:2,20:1,9:90});self.assertEqual(b.engine.alias[9]['source'],'PRIOR_OWN_REPAIR');self.assertIn(90,b.engine.bank)
    def test_single_edge_failure_no_pollution(self):
        b=bridge();e=event();obs=[dict(id=n,neighbors=[],quality=(n!=20),mask='n:'+str(n)) for n in (10,20,9)]
        view=b.preview(3,.3,obs,{});old=digest(branch_state(b));p=digest(dict(view,engine=vars(view['engine'])))
        t,err=b.stage_event(view,e,{10:2,20:1});self.assertIsNone(t);self.assertEqual(err,'current_quality_or_contact')
        self.assertEqual(digest(branch_state(b)),old);self.assertEqual(digest(dict(view,engine=vars(view['engine']))),p)
        b.commit_once(view);self.assertEqual(b.previous,view['mapping']);self.assertEqual(b.engine.alias[9]['target'],90)
    def test_outside_alias_ownership(self):
        b=bridge();b.engine.alias[99]=dict(target=2);v=b.preview(3,.3,[dict(id=n,neighbors=[]) for n in (10,20,9)],{})
        t,err=b.stage_event(v,event(),{10:2,20:1});self.assertIsNone(t);self.assertEqual(err,'UNSELECTED_OR_LATENT_ALIAS_OWNERSHIP')
    def test_future_q_observation_rejected(self):
        b=bridge();v=b.preview(3,.3,[dict(id=n,neighbors=[]) for n in (10,20,9)],{});e=event();e['post_roles'][10][0]['time']=.4
        self.assertIsNone(b.stage_event(v,e,{10:2,20:1})[0])
    def test_depth_version_and_gap_rejected(self):
        samples=[dict(frame=i,time=i/30,version=[1,1,1,1],usable=True,z_mm=800.,mad_mm=2.) for i in (1,2,3)]
        self.assertTrue(DEPTH.forecast(samples,.2)['usable']);samples[2]['frame']=4
        self.assertFalse(DEPTH.forecast(samples,.2)['usable']);samples[2]['frame']=3;samples[2]['version']=[1,2,1,1]
        self.assertFalse(DEPTH.forecast(samples,.2)['usable'])

if __name__=='__main__':
    r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Checks))
    assert r.wasSuccessful();write_new(HERE/'CHECKS_FINAL.json',dict(status='PASS',tests=r.testsRun,
        scope='Depth reliability, immutable observer, actual original-lifecycle atomic stage and rejected state, outside repair and source version',new_model_http=0,cost_usd=0))
