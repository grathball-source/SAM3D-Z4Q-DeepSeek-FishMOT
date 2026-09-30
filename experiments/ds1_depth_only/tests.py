"""Direct state/statistics/causality checks; no GT or model service."""
import copy
import gzip
import json
import math
import os
import socket
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import replay
from depth_measurement import statistics
from depth_state import DepthState,predict
from depth_score import dynamic_choice,geometry_choice,log_t4

sys.path.insert(0,str(replay.NE1))
from test_ne import protected_fixture,observation


def measurement(z=1000.,valid=True):
    return dict(core_usable=valid,source='RAW_SENSOR_OR_ALIGNED_RAW',fact_id='S/F1/n:1',
                core=dict(n=100,valid_fraction=1.,median=z,mad=2.))


def fragment(times,zs):
    return dict(samples=[dict(frame=i+1,time=t,z_mm=z,mad_mm=2.,fact_id=f'F{i+1}')
                         for i,(t,z) in enumerate(zip(times,zs))])


def episode():
    def sample(frame,time,x,z):
        return dict(frame=frame,time=time,center=[x,10.],bbox=[x-10,0,x+10,20],
                    source_generation=1,public_epoch=1,core=measurement(z)['core'])
    return dict(pre={'A':[sample(i,i/10,0,1000) for i in range(1,5)],
                     'B':[sample(i,i/10,100,1200) for i in range(1,5)]},
                post_roles={10:[sample(6,.6,1,1000)],20:[sample(6,.6,101,1200)]},
                public_ids=[1,2],temporary_choice='H1')


class DepthTests(unittest.TestCase):
    def test_positive_finite_only(self):
        import numpy as np
        result=statistics(np.array([0.,np.nan,np.inf,-1.,1000.,1100.]),np.ones(6,bool))
        self.assertEqual(result['n'],2)
        self.assertEqual(result['median'],1050.)

    def test_wls_irregular_epoch_times(self):
        times=[1e9+x for x in (0.,.07,.15,.32,.51)]
        frozen=fragment(times,[1000+80*(t-times[-1]) for t in times])
        result=predict(frozen,times[-1]+1.5)
        self.assertEqual(result['status'],'WLS_LINEAR_TIME')
        self.assertAlmostEqual(result['slope_mm_s'],80.,places=6)
        self.assertAlmostEqual(result['mu_mm'],1120.,places=5)
        self.assertEqual(result['delta_seconds'],1.5)
        self.assertGreater(result['scale_mm'],predict(frozen,times[-1]+.1)['scale_mm'])
        self.assertLess(max(abs(x) for x in result['residual_mm']),1e-6)

    def test_short_history_and_acquisition_time(self):
        frozen=fragment([1.],[1000.])
        frozen['acquired_interval_seconds']=.1
        result=predict(frozen,1.5)
        self.assertIsNone(result['slope_mm_s'])
        self.assertEqual(result['fallback'],'OBSERVED_ACQUISITION_INTERVAL')
        self.assertEqual(result['time_scale_seconds'],.1)
        self.assertEqual(predict(dict(samples=[]),2.)['status'],'NO_HISTORY')

    def test_risk_preserves_one_fragment_without_joining(self):
        state=DepthState('S','D2')
        for frame in (1,2,3):
            state.update(1,measurement(),frame,frame/10,7,1,1,'SOURCE_OBSERVATION')
        state.update(1,measurement(valid=False),4,.4,7,1,1,'SOURCE_OBSERVATION')
        e=dict(member_sources=[1,2],public_ids=[7,8])
        frozen=state.freeze(e,5,{1:1},{1:1})
        self.assertEqual([x['frame'] for x in frozen['A']['samples']],[1,2,3])
        state.update(1,measurement(),5,.5,7,1,1,'SOURCE_OBSERVATION')
        self.assertEqual([x['frame'] for x in state.live[1]['samples']],[5])
        state.update(1,measurement(),6,.6,7,2,1,'SOURCE_OBSERVATION')
        self.assertEqual([x['frame'] for x in state.live[1]['latest_fragment']],[6])
        self.assertEqual(state.freeze(e,7,{1:1},{1:1})['A']['samples'],[])

    def test_group_and_post_do_not_change_frozen_individuals(self):
        state=DepthState('S','D2')
        state.update(1,measurement(),1,.1,7,1,1,'SOURCE_OBSERVATION')
        e=dict(member_sources=[1,2],public_ids=[7,8])
        frozen=state.freeze(e,2)
        before=copy.deepcopy(frozen)
        state.update(1,measurement(9000),2,.2,7,1,1,'GROUP_MEASUREMENT')
        state.update(1,measurement(8000),3,.3,7,1,1,'POST_UNASSIGNED')
        self.assertEqual(frozen,before)
        self.assertEqual(state.updates,1)
        state.update(1,measurement(1100),3,.3,7,1,1,'RESTORED_POST')
        self.assertEqual([x['frame'] for x in state.live[1]['samples']],[3])

    def test_missing_depth_matches_geometry_and_one_post(self):
        e=episode()
        frozen={role:fragment([.1,.2,.3,.4],[1000]*4) for role in ('A','B')}
        measured={n:measurement(valid=False) for n in (10,20)}
        choice,detail=dynamic_choice(e,frozen,measured,dict(n=0,median=None,mad=None))
        geometry,plain=geometry_choice(e)
        self.assertEqual(choice,geometry)
        self.assertEqual([x['total'] for x in detail['candidates']],
                         [x['geometry'] for x in plain['candidates']])
        self.assertEqual(detail['used_edges'],0)
        measured[10]=measurement()
        _,detail=dynamic_choice(e,frozen,measured,dict(n=100,median=1100.,mad=20.))
        self.assertEqual(detail['used_edges'],2)

    def test_student_t_scale_and_contamination_limit(self):
        self.assertGreater(log_t4(1000,1000,15),log_t4(1000,1000,1000))
        from depth_score import _logaddexp
        cost=-_logaddexp(math.log(.9)+log_t4(1000,1000,1e12)-log_t4(1000,1100,60),math.log(.1))
        self.assertAlmostEqual(cost,-math.log(.1),places=6)

    def test_candidate_reorder_preserves_physical_mapping(self):
        e=episode()
        frozen={'A':fragment([.1,.2,.3,.4],[1000]*4),'B':fragment([.1,.2,.3,.4],[1200]*4)}
        measured={10:measurement(1000),20:measurement(1200)}
        choice,_=dynamic_choice(e,frozen,measured,dict(n=100,median=1100.,mad=20.))
        before=replay.choice_mapping(e,choice)
        e['post_roles']=dict(reversed(list(e['post_roles'].items())))
        choice,_=dynamic_choice(e,frozen,measured,dict(n=100,median=1100.,mad=20.))
        self.assertEqual(replay.choice_mapping(e,choice),before)

    def test_failed_preview_atomic_and_local_fallback(self):
        bridge,view,e=protected_fixture(with_outside=True)
        saved=copy.deepcopy(bridge.engine.__dict__)
        transaction,error=bridge.stage_group_restore(view,e,{100:8,101:8})
        self.assertIsNone(transaction)
        self.assertEqual(bridge.engine.__dict__,saved)
        outside=copy.deepcopy(view['engine'].bank[9])
        fallback,detail=bridge.local_fallback(view,e)
        self.assertEqual(fallback['engine'].bank[9],outside)
        self.assertTrue(detail['outside_mapping_and_ownership_equal'])

    def test_single_post_atomic_first_publish(self):
        bridge,view,e=protected_fixture()
        transaction,error=bridge.stage_group_restore(view,e,{100:8,101:7})
        self.assertIsNone(error)
        ids,_=bridge.commit_once(view,transaction)
        self.assertEqual(ids,{100:8,101:7})
        self.assertRaises(AssertionError,bridge.commit_once,view,transaction)


def real_checks():
    """Two real causal-prefix replays, with future masks corrupted and all model/GT access blocked."""
    name='feeding_000351_000555'
    q=65  # Actual earliest complete prediction-selected slice, not a GT selection.
    original_rows=replay.rows
    original_load=replay.np.load
    original_open=Path.open
    original_extract=replay.extract_frame
    original_getitem=replay.np.lib.npyio.NpzFile.__getitem__
    accessed=[]
    fields=[]
    class ForbiddenProvider:
        def infer(self,*args,**kwargs):
            raise AssertionError('model inference forbidden')
    stub=types.ModuleType('provider_v7')
    stub.Provider=ForbiddenProvider
    def guard_open(path,*args,**kwargs):
        assert 'labels_640x360' not in str(path) and 'labels_source' not in str(path),'GT read before seal'
        return original_open(path,*args,**kwargs)
    def guard_load(path,*args,**kwargs):
        accessed.append(int(Path(path).stem))
        assert int(Path(path).stem)<=415,'future sensor read'
        return original_load(path,*args,**kwargs)
    def guard_field(sensor,key):
        fields.append(key)
        assert key=='depth_mm','annotation or repaired plane read'
        return original_getitem(sensor,key)
    def missing_extract(*args,**kwargs):
        full,measured,masks,occupancy=original_extract(*args,**kwargs)
        full=dict(full,n=0,median=None,mad=None)
        for item in measured.values():
            item['core_usable']=False
        return full,measured,masks,occupancy
    def forbidden_network(*args,**kwargs):
        raise AssertionError('prediction network forbidden')
    def future_rows(path):
        for row in original_rows(path):
            row=copy.deepcopy(row)
            if 'assignments' in str(path) and row['frame']>q:
                row['masks']={'n:999999':dict(size=[360,640],counts='INVALID_FUTURE_MASK')}
            yield row
    with tempfile.TemporaryDirectory(prefix='ds1_causal_') as tmp, \
         patch.dict(os.environ,{'DEEPSEEK_API_KEY':''}), \
         patch.dict(sys.modules,{'provider_v7':stub}), \
         patch.object(Path,'open',guard_open),patch.object(replay.np,'load',guard_load), \
         patch.object(replay.np.lib.npyio.NpzFile,'__getitem__',guard_field), \
         patch.object(socket.socket,'connect',forbidden_network):
        a,b,c=Path(tmp)/'a',Path(tmp)/'b',Path(tmp)/'missing'
        a.mkdir(); b.mkdir(); c.mkdir()
        replay.run_segment(name,a,slice_mode=True)
        with patch.object(replay,'rows',future_rows):
            replay.run_segment(name,b,slice_mode=True)
        def values(path):
            with gzip.open(path,'rt',encoding='utf-8') as handle:
                return list(map(json.loads,handle))
        aa=values(a/name/'public/predictions.jsonl.gz')
        bb=values(b/name/'public/predictions.jsonl.gz')
        assert aa==bb and len(aa)==q
        old=values(replay.NE1/'run'/name/'public/predictions.jsonl.gz')
        assert all(x['variants']['D1_STATIC_LEGACY']==y['variants']['EVENT_NUM'] for x,y in zip(aa,old))
        assert all(x['variants']['SAM3_NATIVE']==y['variants']['SAM3_NATIVE'] for x,y in zip(aa,old))
        with patch.object(replay,'extract_frame',missing_extract):
            replay.run_segment(name,c,slice_mode=True)
        cc=values(c/name/'public/predictions.jsonl.gz')
        assert all(x['variants']['D2_DYNAMIC']==x['variants']['D0_GEOMETRY'] for x in cc)
        assert all([v['mask'] for v in x['variants']['D2_DYNAMIC']]==
                   [v['mask'] for v in x['variants']['SAM3_NATIVE']] for x in cc)
        assert set(fields)=={'depth_mm'}
        print('REAL_CHECKS PASS: future cutoff; GT/model/network/key blocked; only depth_mm; D1/native exact; missing D2=D0, all masks retained',flush=True)
    return dict(status='PASS',frames_each=q,future_sensor_accesses=0,
                actual_sensor_max_original_frame=max(accessed),new_model_http=0)


if __name__=='__main__':
    if '--real' in sys.argv:
        print(json.dumps(real_checks()))
    else:
        unittest.main()
