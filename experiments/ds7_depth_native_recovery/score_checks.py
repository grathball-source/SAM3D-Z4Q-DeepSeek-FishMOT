"""Small synthetic scoring checks; never open dataset reference labels."""
import ast
import copy
import unittest
import evaluate as score
import event_audit as audit
from common import HERE, ARMS, sha, write_new


class ScoreChecks(unittest.TestCase):
    def test_ids_masks_and_negative_ids(self):
        objects = [{'mask': 'n:1', 'id': -7}, {'mask': 'n:2', 'id': 8}]
        assignment = {'variants': {'N0': objects}}
        prediction = {'variants': {a: copy.deepcopy(objects) for a in ARMS}}
        self.assertEqual(score.check_objects(assignment, prediction), ['n:1', 'n:2'])
        for bad in (True, 1.2, 8):
            altered = copy.deepcopy(prediction)
            altered['variants']['P1_RAW_DEPTH'][0]['id'] = bad
            with self.assertRaises(AssertionError):
                score.check_objects(assignment, altered)
        altered = copy.deepcopy(prediction)
        altered['variants']['P2_RESTORED_DEPTH'].reverse()
        with self.assertRaises(AssertionError):
            score.check_objects(assignment, altered)

    def test_first_publisher_selected_and_fallback_binding(self):
        arm = 'P1_RAW_DEPTH'
        restore = dict(status='COMMIT', mapping={1: 8, 2: -7}, changes={1: 8, 2: -7},
                       baseline_preview_mapping={1: -7, 2: 8})
        event = dict(id='E1', q=2, suspect_frame=1, evidence_cutoff_frame=2,
                     post_first_observations={'1': {'frame': 2}, '2': {'frame': 2}},
                     restore=restore, numeric={'choice': 'H2', 'detail': {}})
        prediction = {2: {'variants': {arm: [{'mask': 'n:1', 'id': 8}, {'mask': 'n:2', 'id': -7}]}}}
        publish = {2: {'event_publish': {arm: dict(episode='E1', q=2, post_sample_count=1,
                                                  first_public_pair={'1': 8, '2': -7})}}}
        transaction = {(2, arm): dict(restore=restore, actual_published_mapping={'1': 8, '2': -7})}
        states = {(2, arm): {'live': {}}}
        self.assertEqual(score.check_q_binding(event, arm, prediction, publish, transaction, states), {1: 8, 2: -7})
        corrupt = copy.deepcopy(publish)
        corrupt[2]['event_publish'][arm]['first_public_pair']['1'] = -7
        with self.assertRaises(AssertionError):
            score.check_q_binding(event, arm, prediction, corrupt, transaction, states)
        restore.update(status='LOCAL_FALLBACK_COMMITTED', mapping=None, changes={},
                       baseline_preview_mapping={1: 8, 2: -7})
        self.assertEqual(score.check_q_binding(event, arm, prediction, publish, transaction, states), {1: 8, 2: -7})
        restore['baseline_preview_mapping'][1] = -7
        with self.assertRaises(AssertionError):
            score.check_q_binding(event, arm, prediction, publish, transaction, states)

    def test_not_staged_and_unknown_are_separate(self):
        expected = {1: 8, 2: -7}
        restore = dict(status='LOCAL_FALLBACK_COMMITTED', mapping=None)
        self.assertEqual(audit.mapping_outcome(restore, expected, expected), ({}, 'NOT_STAGED', 'CORRECT'))
        restore = dict(status='RESOLVE_NO_ID_CHANGE', mapping=expected)
        self.assertEqual(audit.mapping_outcome(restore, expected, {}),
                         (expected, 'UNSCORABLE_OR_NO_BIJECTION', 'UNSCORABLE_OR_NO_BIJECTION'))
        anchors = {8: {'status': 'UNIQUE_IOU_MATCH', 'gt_id': 'fish_a'},
                   -7: {'status': 'UNIQUE_IOU_MATCH', 'gt_id': 'fish_b'}}
        posts = {1: {'status': 'UNIQUE_IOU_MATCH', 'gt_id': 'fish_b'},
                 2: {'status': 'AMBIGUOUS_IOU_MATCH', 'gt_id': 'fish_a'}}
        self.assertEqual(audit.expected_mapping(anchors, posts), {})

    def test_fragment_unknown_has_no_physical_mm_truth(self):
        event = dict(q=2, depth_frozen={'A': dict(source=1, public=-7, key=['s', 'a', 1, -7], samples=[])})
        def must_not_match(*args):
            raise AssertionError('no reference needed for absent frozen history')
        result = audit.fragment_reference(event, {}, {}, {}, must_not_match, 'P1_RAW_DEPTH', 3)[0]
        self.assertEqual(result['pre_identity_reference'], 'UNKNOWN')
        self.assertEqual(result['surface_identity'], 'UNKNOWN')
        self.assertIsNone(result['physical_depth_reference_mm'])
        self.assertIn('NO_FROZEN_HISTORY', result['exclusions'])

    def test_score_layers_and_generator_match(self):
        pooled = {a: dict(IDF1=80., HOTA=70., AssA=60., IDSW=10) for a in ARMS}
        pooled['P1_RAW_DEPTH'] = dict(IDF1=81., HOTA=71., AssA=61., IDSW=10)
        pooled['P2_RESTORED_DEPTH'] = pooled['P1_RAW_DEPTH'].copy()
        result = score.support_layers(pooled)
        self.assertTrue(result['P1_raw_tracking_support'])
        self.assertTrue(result['P2_offline_tracking_support'])
        self.assertFalse(result['P2_restored_increment_vs_raw'])
        self.assertFalse(result['P2_full_frozen_rule'])
        tree = ast.parse((HERE/'build_evaluation.py').read_text(encoding='utf-8'))
        tree.body = [n for n in tree.body if not isinstance(n, ast.Expr)]
        namespace = {'__name__': 'generator_memory_check'}
        exec(compile(tree, str(HERE/'build_evaluation.py'), 'exec'), namespace)
        self.assertEqual(namespace['head']+namespace['body']+namespace['tail'],
                         (HERE/'evaluate.py').read_text(encoding='utf-8'))


def main():
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ScoreChecks))
    assert result.wasSuccessful()
    write_new(HERE/'SCORE_CHECKS.json', dict(status='PASS', tests=result.testsRun,
        scope='synthetic memory fixtures only; no dataset reference access or GT scoring',
        failures=len(result.failures), errors=len(result.errors), new_model_http=0,
        code_sha256={n: sha(HERE/n) for n in ('evaluate.py', 'event_audit.py', 'build_evaluation.py', 'score_checks.py')}))


if __name__ == '__main__':
    main()
