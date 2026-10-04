"""Focused tests of the genuine matrix hooks, dummy and branch state isolation."""
import copy
import inspect
import json
import unittest
import numpy as np
from common import CONFIG_PATH, HERE, digest, read
from bridge import Bridge
from soft_controller import CFG, SoftBridge, SoftReturn, engine_state


def observation(n, z=700., x=0., neighbors=()):
    return dict(id=n, mask=f'n:{n}', box=[x, 0., x+20., 20.], area=400,
        score_birth=.95, presence=.95, neighbors=list(neighbors),
        depth=dict(n=400, valid_fraction=1., median=z, mad=2.))


def profile(o, frame):
    sample=dict(median=o['depth']['median'], mad=2., n=400, valid_fraction=1.)
    return dict(id=o['id'], mask=o['mask'], frame=frame, whole=sample, core=sample)


class Evidence:
    def __init__(self, deltas, status='AVAILABLE'):
        self.deltas, self.status = deltas, status
    def __deepcopy__(self, memo):
        return self
    def check(self, engine, observation, k, anchor, phase):
        assert anchor == engine.bank[k]['anchor']
        return dict(delta_cost=self.deltas.get(k, 0.), status=self.status,
            reason='SYNTHETIC_COST_HOOK_ONLY_NOT_DEPTH_METHOD_EVIDENCE')


def seed(branch):
    for f in range(1, 21):
        obs=[observation(1, 700., 0.), observation(2, 704., 3.), observation(3, 850., 60.)]
        view=branch.preview(f, f/30, obs, {o['id']:profile(o, f) for o in obs})
        branch.commit_once(view)
    obs=[observation(1, 700., 0., (3,)), observation(2, 704., 3., (3,)),
         observation(3, 850., 60., (1, 2))]
    branch.commit_once(branch.preview(21, 21/30, obs, {o['id']:profile(o, 21) for o in obs}))


class EngineChecks(unittest.TestCase):
    def test_disabled_and_unknown_preserve_full_scientific_state(self):
        for unknown in (None, Evidence({}, 'UNKNOWN')):
            original=Bridge(read(CONFIG_PATH)); new=SoftBridge(read(CONFIG_PATH))
            seed(original); seed(new); new.engine.soft_context=unknown
            for f in range(22, 30):
                obs=[observation(9, 703., 1.5), observation(3, 850., 60.)]
                profiles={o['id']:profile(o, f) for o in obs}
                a=original.preview(f, f/30, obs, profiles)
                b=new.preview(f, f/30, obs, profiles)
                self.assertEqual(a['mapping'], b['mapping'])
                self.assertEqual(digest(vars(a['engine'])), digest(engine_state(b['engine'])))
                original.commit_once(a); new.commit_once(b)
                self.assertEqual(original.epochs, new.epochs)
                self.assertEqual(original.previous, new.previous)
                self.assertTrue(all(c['applied_delta_cost']==0 for c in b['trace']['depth_soft_checks']))

    def test_both_true_assignment_paths_choose_and_continue_actual_state(self):
        for phase in ('BIRTH_REFINE', 'D1_DELAYED'):
            branch=SoftBridge(read(CONFIG_PATH)); seed(branch)
            branch.engine.soft_context=Evidence({1:-.15, 2:.15})
            for f in range(22, 27):
                obs=[observation(9, 703., 1.5, (3,) if phase=='BIRTH_REFINE' and f==22 else ()),
                     observation(3, 850., 60.)]
                profiles={o['id']:profile(o, f) for o in obs} if phase=='BIRTH_REFINE' else {}
                view=branch.preview(f, f/30, obs, profiles)
                ids,tr=branch.commit_once(view)
                if phase=='D1_DELAYED':
                    self.assertEqual(ids[9], 1 if f==26 else 9)
                else:
                    self.assertEqual(ids[9], 1)
                if f==22:
                    checks=[c for c in tr['depth_soft_checks'] if c['origin_rule']==phase]
                    self.assertEqual({c['public_id'] for c in checks}, {1,2})
                    self.assertTrue(any(c['applied_delta_cost']!=0 for c in checks))
                    key='birth_checks' if phase=='BIRTH_REFINE' else 'edges'
                    self.assertTrue(all(e['cost']==e['cost_effective'] for e in tr[key] if 'cost_effective' in e))
            self.assertEqual(branch.engine.alias[9]['target'], 1)
            self.assertNotIn(9, branch.engine.bank)
            obs=[observation(9, 703., 1.5), observation(3, 850., 60.)]
            self.assertEqual(branch.commit_once(branch.preview(27, .9, obs, {}))[0][9],1)

    def test_dummy_invalid_edges_and_noncompetitive_edges_unchanged(self):
        engine=SoftReturn(read(CONFIG_PATH))
        engine.bank={k:dict(anchor=dict(frame=1,native_id=k,canonical_id=k,mask=f'n:{k}')) for k in (1,2,3)}
        engine.soft_context=Evidence({1:-.15,2:.15,3:-.15})
        matrix=np.array([[.88, .94, 1e6, 1.]])
        terms={(0,j):dict(native_id=9,canonical_id=j+1,cost=float(matrix[0,j])) for j in (0,1)}
        engine.apply_depth_soft(matrix,terms,2,.1,'D1_DELAYED',[observation(9)])
        self.assertEqual(matrix[0,2],1e6);self.assertEqual(matrix[0,3],1.)
        self.assertAlmostEqual(matrix[0,0],.73);self.assertAlmostEqual(matrix[0,1],1.09)
        self.assertEqual(len(engine.soft_cost_checks),2)
        matrix=np.array([[.2,.6,1.]])
        terms={(0,j):dict(native_id=9,canonical_id=j+1,cost=float(matrix[0,j])) for j in (0,1)}
        before=matrix.copy();engine.soft_cost_checks=[]
        engine.apply_depth_soft(matrix,terms,2,.1,'BIRTH_REFINE',[observation(9)])
        np.testing.assert_array_equal(matrix,before);self.assertEqual(engine.soft_cost_checks,[])

    def test_permutation_preserves_physical_edge_costs(self):
        def run(order):
            engine=SoftReturn(read(CONFIG_PATH))
            engine.bank={k:dict(anchor=dict(frame=1,native_id=k,canonical_id=k,mask=f'n:{k}')) for k in order}
            engine.soft_context=Evidence({1:-.1,2:.1})
            cost={1:.5,2:.55};matrix=np.array([[*(cost[k] for k in order),1.]])
            terms={(0,j):dict(native_id=9,canonical_id=k,cost=cost[k]) for j,k in enumerate(order)}
            engine.apply_depth_soft(matrix,terms,2,.1,'D1_DELAYED',[observation(9)])
            return {k:float(matrix[0,j]) for j,k in enumerate(order)}
        self.assertEqual(run([1,2]),run([2,1]))

    def test_unknown_nonzero_and_unbounded_cost_are_rejected(self):
        engine=SoftReturn(read(CONFIG_PATH))
        engine.bank={k:dict(anchor=dict(frame=1,native_id=k,canonical_id=k,mask=f'n:{k}')) for k in (1,2)}
        for evidence in (Evidence({1:.01},'UNKNOWN'),Evidence({1:.151}),Evidence({1:float('nan')})):
            engine.soft_context=evidence
            matrix=np.array([[.5,.55,1.]])
            terms={(0,j):dict(native_id=9,canonical_id=j+1,cost=float(matrix[0,j])) for j in (0,1)}
            with self.assertRaises(AssertionError):
                engine.apply_depth_soft(matrix,terms,2,.1,'D1_DELAYED',[observation(9)])

    def test_preview_preserves_authoritative_engine_and_epochs(self):
        branch=SoftBridge(read(CONFIG_PATH));seed(branch)
        branch.engine.soft_context=Evidence({1:-.15,2:.15})
        before=digest(dict(engine=engine_state(branch.engine),previous=branch.previous,
                           epochs=branch.epochs,provenance=branch.provenance,version=branch.version))
        obs=[observation(9,703.,1.5,(3,)),observation(3,850.,60.)]
        profiles={o['id']:profile(o,22) for o in obs}
        view=branch.preview(22,22/30,obs,profiles)
        self.assertEqual(view['mapping'][9],1)
        self.assertEqual(before,digest(dict(engine=engine_state(branch.engine),previous=branch.previous,
                           epochs=branch.epochs,provenance=branch.provenance,version=branch.version)))
        other=copy.deepcopy(branch);other.engine.bank[1]['areas'].clear()
        self.assertTrue(branch.engine.bank[1]['areas'])
        branch.commit_once(view)
        self.assertEqual(branch.previous[9],1);self.assertEqual(branch.engine.alias[9]['target'],1)

    def test_original_parameters_and_isolated_hierarchy(self):
        engine=SoftReturn(read(CONFIG_PATH))
        self.assertEqual(engine.cfg['confirm'],5)
        self.assertEqual(engine.birth_config['risk_floor_mm'],15.)
        self.assertEqual(engine.birth_config['risk_budget_mm'],60.)
        self.assertEqual(engine.birth_config['assignment_margin'],.15)
        self.assertEqual(engine.birth_config['motion_weight'],.15)
        self.assertEqual(CFG['competition_window'],.15);self.assertEqual(CFG['soft_weight'],.15)
        for cls in engine.__class__.__mro__[1:6]:
            self.assertEqual(__import__('pathlib').Path(inspect.getfile(cls)).parent,HERE/'source')
        self.assertIn('sam3_depth_identity_balance_20260917',inspect.getfile(engine.__class__.__mro__[6]))
        self.assertFalse(engine.edge_veto(1,.1,observation(9),1,None,'D1_DELAYED')['veto'])


def main():
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(EngineChecks)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    print(json.dumps(dict(status='PASS' if result.wasSuccessful() else 'FAIL',
        checks=result.testsRun,failures=len(result.failures),errors=len(result.errors),
        scope='Synthetic genuine controller flow and state checks; no depth efficacy claim',
        API_HTTP=0,GT_read=False),ensure_ascii=False))
    if not result.wasSuccessful():raise SystemExit(1)

if __name__=='__main__':main()
