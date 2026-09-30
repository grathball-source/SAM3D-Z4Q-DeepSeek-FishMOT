"""Numerical/source tests independent of labels and eventual scores."""
from common import *
import numpy as np
from measurement import measure_restored
from association import choose
from restored_source import RestoredDepth
from depth_measurement import statistics
def fake_episode():
    pre=[dict(frame=1,time=0.,center=[10.,10.],bbox=[0,0,20,20],source_generation=1,
              public_epoch=1,core=dict(n=30,valid_fraction=1.,median=800.,mad=1.))]
    return dict(pre={'A':pre,'B':[dict(pre[0],center=[40.,10.],bbox=[30,0,50,20])]},
        post_roles={1:[dict(frame=2,time=.033,center=[10.,10.],bbox=[0,0,20,20],core=pre[0]['core'])],
                    2:[dict(frame=2,time=.033,center=[40.,10.],bbox=[30,0,50,20],core=pre[0]['core'])]},
        temporary_choice='H1',q=2)
def frozen(z):
    return dict(samples=[dict(time=0.,frame=1,z_mm=z,mad_mm=1.,fact_id='pre')],
                acquired_interval_seconds=.033,cutoff_frame=1)
checks=[]
def test(name,fn):fn();checks.append(name)
def cohorts():
    depth=np.full((360,640),800.,'f4');p=np.ones(depth.shape,'u1')
    region=np.zeros(depth.shape,bool);region[100:140,100:140]=1
    p[100:140,120:140]=2;depth[100:140,120:140]=1200.
    _,m=measure_restored(depth,p,{1:region},region.astype('u2'),'s',1)
    assert m[1]['cohort']=='retained' and m[1]['core']['median']==800.
    assert m[1]['cohorts']['inferred']['median']==1200.
    p[region]=2
    depth[region]=1200.
    _,m=measure_restored(depth,p,{1:region},region.astype('u2'),'s',1)
    assert m[1]['cohort']=='inferred' and 1.4826*m[1]['core']['mad']>=60.-1e-10
def row_missing():
    episode=fake_episode()
    measured={n:dict(core=dict(median=z,mad=1.),core_usable=True,fact_id=f'post{n}') for n,z in [(1,800.),(2,1200.)]}
    full=dict(n=1000,median=1100.,mad=80.)
    _,d=choose(episode,{'A':frozen(800.),'B':dict(samples=[],cutoff_frame=1)},measured,full)
    assert d['used_edges']==2 and d['edges']['B:1']['cost']==d['edges']['B:2']['cost']==0.
    measured[2]['core_usable']=False
    c,d=choose(episode,{'A':frozen(800.),'B':frozen(1200.)},measured,full)
    assert c=='UNRESOLVED' and d['used_edges']==0
def permutation():
    episode=fake_episode()
    measured={n:dict(core=dict(median=z,mad=1.),core_usable=True,fact_id=f'post{n}') for n,z in [(1,800.),(2,1200.)]}
    hist={'A':frozen(800.),'B':frozen(1200.)};full=dict(n=1000,median=1100.,mad=80.)
    c,d=choose(episode,hist,measured,full)
    episode['post_roles']=dict(reversed(list(episode['post_roles'].items())))
    c2,d2=choose(episode,hist,measured,full)
    assert c=='H1' and c2=='H2'
    assert d['depth_log_odds_gap']==d2['depth_log_odds_gap']
def actual_source():
    source=RestoredDepth()
    cases=[]
    for f in (0,398,419,519,1821,1906):
        dep,p,meta=source(f)
        assert dep.shape==p.shape==(360,640) and np.all(np.isfinite(dep))
        assert np.all(np.isin(p,[0,1,2,3])) and np.all(p[dep==0]==0)
        assert meta['index']==f and meta['future_support']=='UPSTREAM_I_PLUS_1_OFFLINE'
        cases.append(dict(frame=f,n=int((dep>0).sum()),counts={str(k):int((p==k).sum()) for k in range(4)},source=meta))
    source.close();write_new(HERE/'REAL_INPUT_CHECKS.json',cases)
test('cohorts_never_mix_and_estimate_has_uncertainty',cohorts)
test('missing_pre_whole_row_common_and_missing_post_common_all',row_missing)
test('candidate_order_physical_equivalence',permutation)
test('six_real_v2_inputs_no_v3_or_annotation_array',actual_source)
write_new(HERE/'UNIT_CHECKS.json',dict(status='PASS',checks=checks))
print('PASS',checks)
