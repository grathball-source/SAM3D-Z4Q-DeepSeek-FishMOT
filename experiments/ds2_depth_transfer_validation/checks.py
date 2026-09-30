"""Numerical, frozen-state, real prefix and full exposed-regression checks."""
import copy
import gzip
import hashlib
import importlib.util
import json
import os
import socket
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from adapter import HERE, DS1, frozen, predict, dynamic_choice, zero_drift_predict, zero_drift_choice
runner_spec=importlib.util.spec_from_file_location('ds2_runner',HERE/'runner.py')
runner=importlib.util.module_from_spec(runner_spec); runner_spec.loader.exec_module(runner)
from prepare import write_new, digest

spec=importlib.util.spec_from_file_location('ds1_unit_checks',DS1/'tests.py')
old_tests=importlib.util.module_from_spec(spec); spec.loader.exec_module(old_tests)


class DriftChecks(unittest.TestCase):
    def test_only_wls_mean(self):
        f=old_tests.fragment([0.,.1,.2,.4],[980.,990.,1000.,1020.])
        a,b=predict(f,1.),zero_drift_predict(f,1.)
        self.assertEqual(a['status'],'WLS_LINEAR_TIME')
        self.assertAlmostEqual(a['mu_mm']-b['mu_mm'],a['slope_mm_s']*.6)
        for k in a:
            if k!='mu_mm': self.assertEqual(a[k],b[k],k)
        self.assertNotEqual(b['slope_mm_s'],0.)
        self.assertEqual(predict(f,.4)['mu_mm'],zero_drift_predict(f,.4)['mu_mm'])
        for count in (0,1,2):
            g=old_tests.fragment([.1,.2][:count],[1000.,1010.][:count])
            self.assertEqual(predict(g,.6),zero_drift_predict(g,.6))
        self.assertIs(dynamic_choice.__globals__['predict'],predict)
        self.assertIsNot(dynamic_choice.__globals__,zero_drift_choice.__globals__)

    def test_scores_missing_and_reordering(self):
        e=old_tests.episode()
        f={'A':old_tests.fragment([.1,.2,.3,.4],[980.,990.,1000.,1010.]),
           'B':old_tests.fragment([.1,.2,.3,.4],[1200.]*4)}
        m={10:old_tests.measurement(1030),20:old_tests.measurement(1200)}
        full=dict(n=100,median=1100.,mad=20.)
        a,da=dynamic_choice(e,f,m,full); b,db=zero_drift_choice(e,f,m,full)
        self.assertEqual(da['background'],db['background'])
        for ca,cb in zip(da['candidates'],db['candidates']):
            self.assertEqual(ca['geometry'],cb['geometry'])
            for pa,pb in zip(ca['pairs'],cb['pairs']):
                for k in ('source','measurement_fact_id','observation_mm','observation_scale_mm'):
                    self.assertEqual(pa[k],pb[k])
                self.assertEqual(pa['prediction']['scale_mm'],pb['prediction']['scale_mm'])
        mapping=frozen.choice_mapping(e,b)
        e['post_roles']=dict(reversed(list(e['post_roles'].items())))
        c,_=zero_drift_choice(e,f,m,full)
        self.assertEqual(mapping,frozen.choice_mapping(e,c))
        for item in m.values(): item['core_usable']=False
        for scorer in (dynamic_choice,zero_drift_choice):
            c,d=scorer(e,f,m,dict(n=0,median=None,mad=None))
            self.assertEqual(c,frozen.geometry_choice(e)[0])
            self.assertEqual(d['used_edges'],0)
            self.assertTrue(all(x['observation_mm']!=0 for ca in d['candidates'] for x in ca['pairs']))


def values(path):
    return list(frozen.rows(path))


def guards(limit):
    opened=[]
    fields=[]
    original_open=Path.open; original_load=runner.np.load
    original_field=runner.np.lib.npyio.NpzFile.__getitem__
    def open_guard(path,*a,**kw):
        assert 'labels_640x360' not in str(path) and 'labels_source' not in str(path),'GT before seals'
        return original_open(path,*a,**kw)
    def load_guard(path,*a,**kw):
        frame=int(Path(path).stem); opened.append(frame)
        assert limit is None or frame<=limit,'future raw depth read'
        return original_load(path,*a,**kw)
    def field_guard(sensor,key):
        fields.append(key); assert key=='depth_mm'
        return original_field(sensor,key)
    def forbidden(*a,**kw): raise AssertionError('network forbidden in runner')
    return opened,fields,(patch.object(Path,'open',open_guard),patch.object(runner.np,'load',load_guard),
        patch.object(runner.np.lib.npyio.NpzFile,'__getitem__',field_guard),
        patch.object(socket.socket,'connect',forbidden),patch.dict(os.environ,{'DEEPSEEK_API_KEY':''}))


def regression():
    output=HERE/'regression_405'; output.mkdir(exist_ok=False)
    accessed,fields,contexts=guards(None)
    with contexts[0],contexts[1],contexts[2],contexts[3],contexts[4], \
         patch.object(runner,'SEGMENTS',frozen.SEGMENTS), \
         patch.object(runner,'INPUT_ROOT',frozen.FEED/'private'):
        checked=[]
        for name,(start,stop) in frozen.SEGMENTS.items():
            runner.run_segment(name,output,stop_at=stop-start+1)
            a=values(output/name/'public/predictions.jsonl.gz')
            b=values(DS1/'run'/name/'public/predictions.jsonl.gz')
            assert len(a)==len(b)==stop-start+1
            hashes={}
            for now,old in (('SAM3_NATIVE','SAM3_NATIVE'),('D0_GEOMETRY','D0_GEOMETRY'),
                            ('D1_STATIC_LEGACY','D1_STATIC_LEGACY'),('D2_FROZEN','D2_DYNAMIC')):
                assert all(x['variants'][now]==y['variants'][old] for x,y in zip(a,b,strict=True)),(name,now)
                hashes[now]=hashlib.sha256(json.dumps([x['variants'][now] for x in a],separators=(',',':')).encode()).hexdigest()
            checked.append(dict(segment=name,frames=len(a),exact_branches=list(hashes),normalized_sha256=hashes))
    assert set(fields)=={'depth_mm'}
    write_new(HERE/'REGRESSION_405.json',dict(status='PASS',role='EXPOSED_REGRESSION_REFERENCE',
        fresh_state_replay=True,frames=405,checks=checked,GT_reads=0,network_enabled=False,
        runner_sha256=digest(HERE/'runner.py'),adapter_sha256=digest(HERE/'adapter.py'),
        outputs_sha256={str(p):digest(p) for p in output.rglob('*') if p.is_file()},new_model_http=0))


def causal():
    name='feeding_000351_000555'; q=65; original_rows=runner.rows
    accessed,fields,contexts=guards(415)
    original_extract=runner.extract_frame
    def altered_future(path):
        for row in original_rows(path):
            row=copy.deepcopy(row)
            if 'assignments' in str(path) and row['frame']>q:
                row['masks']={'n:9999':dict(size=[360,640],counts='INVALID_FUTURE')}
            yield row
    def missing(*a,**kw):
        full,m,masks,occ=original_extract(*a,**kw)
        full=dict(full,n=0,median=None,mad=None)
        for item in m.values(): item['core_usable']=False
        return full,m,masks,occ
    with tempfile.TemporaryDirectory(prefix='ds2_prefix_') as tmp, \
         contexts[0],contexts[1],contexts[2],contexts[3],contexts[4], \
         patch.object(runner,'SEGMENTS',frozen.SEGMENTS),patch.object(runner,'INPUT_ROOT',frozen.FEED/'private'):
        a,b,c=[Path(tmp)/x for x in ('a','b','missing')]
        runner.run_segment(name,a,stop_at=q)
        with patch.object(runner,'rows',altered_future): runner.run_segment(name,b,stop_at=q)
        aa=values(a/name/'public/predictions.jsonl.gz'); bb=values(b/name/'public/predictions.jsonl.gz')
        assert aa==bb and len(aa)==q
        assert json.loads((a/name/'public/COMMON_STATE_SHADOW.json').read_text())==json.loads((b/name/'public/COMMON_STATE_SHADOW.json').read_text())
        with patch.object(runner,'extract_frame',missing): runner.run_segment(name,c,stop_at=q)
        cc=values(c/name/'public/predictions.jsonl.gz')
        assert all(x['variants']['D2_FROZEN']==x['variants']['D3_ZERO_DRIFT_MATCHED_SCALE']==x['variants']['D0_GEOMETRY'] for x in cc)
        for folder in (a,b,c):
            led=[json.loads(x) for x in (folder/name/'public/PUBLISH_LEDGER.jsonl').read_text().splitlines()]
            assert [x['frame'] for x in led]==list(range(1,q+1))
    assert not any('provider' in k.lower() for k in sys.modules),'Provider imported'
    write_new(HERE/'CAUSAL_CHECKS.json',dict(status='PASS',prefix_frames=q,replays=3,
        future_mask_perturbation_equal=True,future_depth_reads=0,max_sensor_frame=max(accessed),
        fields=sorted(set(fields)),missing_D2_D3_equal_D0=True,network_blocked=True,key_empty=True,
        provider_modules_loaded=False,GT_reads=0))


if __name__=='__main__':
    suite=unittest.TestSuite((unittest.defaultTestLoader.loadTestsFromTestCase(old_tests.DepthTests),
                             unittest.defaultTestLoader.loadTestsFromTestCase(DriftChecks)))
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    assert result.wasSuccessful()
    if not (HERE/'UNIT_CHECKS.json').exists():
        write_new(HERE/'UNIT_CHECKS.json',dict(status='PASS',tests=result.testsRun))
    causal(); regression()
