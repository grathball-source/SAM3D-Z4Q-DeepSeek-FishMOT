"""Necessary source, spatial-chain and original-state checks; no method qualification gate."""
from common import *
import unittest,copy
from history import History,Sources,combine
from relative_controller import OrderBridge
from association import self_check
from source_checks import run_checks

class Checks(unittest.TestCase):

    def test_real_controller_preview_does_not_mutate_original(self):
        from runner import engine_state
        branch = OrderBridge(read(CONFIG_PATH))
        before = digest(engine_state(branch.engine))
        o = dict(id=1, mask='n:1', area=100, box=[1, 1, 11, 11], presence=1.0, score_birth=1.0, neighbors=[], depth=dict(n=100, valid_fraction=1.0, median=700.0, mad=0.0))
        view = branch.preview(1, 0.0, [o], {})
        self.assertEqual(before, digest(engine_state(branch.engine)))
        branch.commit_once(view)
        self.assertEqual(branch.previous, {1: 1})
        with self.assertRaises(AssertionError):
            branch.commit_once(view)

    def test_history_risk_break_retains_exact_old_anchor(self):

        class Engine:
            retired = set()

            def quality(self, o):
                return True
        e = Engine()
        h = History('test')
        mapping = {1: 1}
        epochs = {1: 1}

        def row(f, neighbors):
            return dict(frame=f, time=f / 30, observations=[dict(id=1, mask='n:1', box=[0, 0, 10, 10], area=100, neighbors=neighbors)])
        e.bank = {1: dict(anchor=dict(frame=1, native_id=1, canonical_id=1, mask='n:1'))}
        h.observe(row(1, []), mapping, epochs, e)
        old_key = next(iter(h.anchors))
        h.observe(row(2, [2]), mapping, epochs, e)
        self.assertNotIn(1, h.live)
        self.assertIn(old_key, h.anchors)
        self.assertEqual(h.frames[2]['objects'][1]['observation_class'], 'ANONYMOUS_RISK_OBSERVATION')
        e.bank[1]['anchor']['frame'] = 3
        h.observe(row(3, []), mapping, epochs, e)
        self.assertEqual(len(h.live[1]), 1)

    def test_generation_gap_and_epoch_change(self):
        h = History('test')
        h.previous[1] = dict(frame=1, generation=2)
        self.assertEqual(h.current_version(1, 3, {1: 7}, {1: 9}), [1, 3, 7, 9])

    def test_actual_two_matrix_hooks_preserve_original_preview(self):
        from bridge import stream
        from runner import engine_state

        class Veto:

            def __init__(self, row, selected):
                self.row = row
                self.selected = selected

            def check(self, e, o, k, a, rule):
                return dict(veto=(rule, o['id'], k) == self.selected, status='TEST_ONLY_SYNTHETIC_REFUTATION', reason='TEST_ONLY')

            def __deepcopy__(self, memo):
                return self
        for name, end, rule, source in [('feeding_000000_000199', 160, 'D1_DELAYED', 26), ('feeding_000351_000555', 118, 'BIRTH_REFINE', 63)]:
            branch = OrderBridge(read(CONFIG_PATH))
            base = input_dir(name)
            exercised = False
            for row, p in stream(base / 'observations.jsonl.gz', base / 'profiles.jsonl.gz'):
                before = digest(engine_state(branch.engine))
                view = branch.preview(row['frame'], row['time'], row['observations'], p)
                if row['frame'] == end:
                    actions = [x for x in view['trace']['events'] if x.get('kind') == 'reconnect' and x.get('accepted') and (('BIRTH_REFINE' if x.get('phase') == 'birth' else 'D1_DELAYED') == rule)]
                    if rule == 'D1_DELAYED':
                        actions = [x for x in actions if x['native_id'] == source]
                    self.assertTrue(actions, 'Real source does not exercise intended hook')
                    action = actions[0]
                    source = action['native_id']
                    target = action['canonical_id']
                    branch.engine.relative_context = Veto(row, (rule, source, target))
                    trial = branch.preview(row['frame'], row['time'], row['observations'], p)
                    self.assertEqual(before, digest(engine_state(branch.engine)))
                    checks = trial['trace']['edges' if rule == 'D1_DELAYED' else 'birth_checks']
                    blocked = [x for x in checks if x.get('native_id') == source and x.get('canonical_id') == target]
                    self.assertTrue(blocked and blocked[0]['edge_veto']['veto'])
                    self.assertNotEqual(trial['mapping'][source], target)
                    self.assertEqual(len(set(trial['mapping'].values())), len(trial['mapping']))
                    exercised = True
                    break
                branch.commit_once(view)
            self.assertTrue(exercised)

    def test_anonymous_spatial_chain(self):
        self.assertEqual(self_check()['status'],'PASS')
    def test_actual_source_and_mixture_contract(self):
        self.source_checks=run_checks()
        self.assertTrue(self.source_checks)
    def test_unchanged_partner_aggregate(self):
        self.assertFalse(combine([dict(status='CONFLICT'),dict(status='COMPATIBLE')])['veto'])
        self.assertTrue(combine([dict(status='CONFLICT'),dict(status='UNKNOWN')])['veto'])
        self.assertFalse(combine([dict(status='UNKNOWN')])['veto'])

if __name__=='__main__':
    from datetime import datetime,timezone
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Checks)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    write_new(HERE/'checks'/('CHECKS_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.json'),
        dict(status='PASS' if result.wasSuccessful() else 'FAIL',tests=result.testsRun,failures=len(result.failures),
        errors=len(result.errors),model_http=0,cost_usd=0,GT_read=False,synthetic_not_research_success=True))
    assert result.wasSuccessful()
