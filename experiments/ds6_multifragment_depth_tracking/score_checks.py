"""Known synthetic scoring/reference/gate checks; never opens real reference files."""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

import evaluate as score
import event_audit
from common import HERE, SEGMENTS, ARMS, write_new, sha

helpers = event_audit.legacy_audit_helpers(score)


def polygon(identity, x0, y0, x1, y1):
    return dict(shape_type='polygon', group_id=identity,
                points=[[x0, y0], [x1, y0], [x1, y1], [x0, y1]])


def assignment(shapes):
    ids, masks = score.mask_rles(shapes)
    encoded = {f'n:{n}': dict(size=x['size'], counts=x['counts'].decode()) for n, x in zip(ids, masks)}
    return dict(variants={'N0': [dict(id=n, mask=f'n:{n}') for n in ids]}, masks=encoded)


class ScoringChecks(unittest.TestCase):
    def test_all_segments_required_before_reference(self):
        manifest = dict(status='ALL_FIVE_BRANCHES_FOUR_SEGMENTS_SEALED', frames=1471,
            arms=list(ARMS), seals={name: 'synthetic' for name in SEGMENTS},
            new_model_http=0, model_cost_usd=0)
        score.check_all_manifest(manifest)
        del manifest['seals'][next(iter(SEGMENTS))]
        with self.assertRaises(AssertionError):
            score.check_all_manifest(manifest)

    def test_access_gate_rejects_reference_path(self):
        audit = dict(status='NO_REFERENCE_OR_RESTORED_FILE_OPEN_DURING_PREDICTION',
            new_model_http=0, cost_usd=0,
            forbidden_path_tokens=['labels_640x360', 'depth_restored', 'restored_v3', 'sealed_test'],
            observed_data_paths=['E:/synthetic/data/depth_rgb_640x360/000000.npz'])
        score.check_access_audit(audit)
        audit['observed_data_paths'].append('E:\\synthetic\\data\\labels_640x360\\000000.json')
        with self.assertRaises(AssertionError):
            score.check_access_audit(audit)

    def test_polygon_union_and_known_iou(self):
        ids, masks = score.mask_rles([polygon(3, 0, 0, 9, 9), polygon(3, 10, 0, 19, 9)])
        self.assertEqual(ids, [3])
        self.assertEqual(int(score.coco.area(masks[0])), 200)
        _, half = score.mask_rles([polygon(4, 0, 0, 9, 9)])
        self.assertEqual(float(score.coco.iou(half, masks, [0])[0, 0]), .5)

    def test_unique_missing_ambiguous_and_shared_references(self):
        shapes = [polygon(7, 10, 10, 19, 19), polygon(9, 40, 40, 49, 49)]
        native = assignment([polygon(2, 10, 10, 19, 19)])
        got = helpers.match_sources(native, dict(shapes=shapes), [2, 99])
        self.assertEqual(got[2]['status'], 'UNIQUE_IOU_MATCH')
        self.assertEqual(got[2]['gt_id'], 7)
        self.assertEqual(got[99]['status'], 'SOURCE_MISSING')
        ambiguous = dict(shapes=[polygon(7, 10, 10, 19, 19), polygon(9, 10, 10, 19, 19)])
        self.assertEqual(helpers.match_sources(native, ambiguous, [2])[2]['status'],
                         'UNSCORABLE_LOW_OR_AMBIGUOUS_IOU')
        duplicate = assignment([polygon(2, 10, 10, 19, 19), polygon(4, 10, 10, 19, 19)])
        got = helpers.match_sources(duplicate, dict(shapes=shapes), [2, 4])
        self.assertTrue(all(x['status']=='UNSCORABLE_SHARED_GT_MATCH' for x in got.values()))

    def test_negative_ids_and_clear_switches_match_official(self):
        truth = [[7], [7], [], [7]]
        predictions = [[-5], [12], [12], [12]]
        sims = [score.np.ones((1, 1)), score.np.ones((1, 1)),
                score.np.zeros((0, 1)), score.np.ones((1, 1))]
        metric = score.metrics(truth, predictions, sims)
        self.assertEqual((metric['IDSW'], metric['FP'], metric['FN'], metric['predictions']), (1, 1, 0, 4))
        previous, step, switches = {}, {}, []
        for frame, (gt, pred, sim) in enumerate(zip(truth, predictions, sims), 1):
            step, new = helpers.clear_step(gt, ['n:2'], pred, sim, previous, step, frame)
            switches.extend(new)
        self.assertEqual(len(switches), metric['IDSW'])
        self.assertEqual(switches[0]['from_public_id'], -5)

    def test_pooled_identity_namespaces_do_not_collide(self):
        a = score.namespaced([-1, 9_999_999], 0)
        b = score.namespaced([-1, 9_999_999], 1)
        self.assertEqual(len(set(a+b)), 4)
        gt = [score.namespaced([1], 0), score.namespaced([1], 1)]
        pred = [score.namespaced([-1], 0), score.namespaced([9_999_999], 1)]
        metric = score.metrics(gt, pred, [score.np.ones((1, 1))]*2)
        self.assertEqual(metric['IDF1'], 100.)
        self.assertEqual(metric['IDSW'], 0)

    def test_masks_and_unique_public_ids_required(self):
        source = dict(variants={'N0': [dict(id=-2, mask='n:-2'), dict(id=4, mask='n:4')]})
        prediction = dict(variants={arm: copy.deepcopy(source['variants']['N0']) for arm in ARMS})
        score.check_objects(source, prediction)
        prediction['variants']['D5_MULTIFRAGMENT'][1]['id'] = -2
        with self.assertRaises(AssertionError):
            score.check_objects(source, prediction)
        prediction['variants']['D5_MULTIFRAGMENT'].pop()
        with self.assertRaises(AssertionError):
            score.check_objects(source, prediction)

    def test_legacy_equivalence_includes_time_and_alias(self):
        current = dict(frame=1, global_frame=0, time=.25,
            variants={arm: [dict(id=-2, mask='n:3')] for arm in ARMS})
        previous = dict(frame=1, global_frame=0, time=.25,
            variants={'SAM3_NATIVE': [dict(id=-2, mask='n:3')],
                      'D0_GEOMETRY': [dict(id=-2, mask='n:3')],
                      'D2_DYNAMIC': [dict(id=-2, mask='n:3')]})
        score.check_legacy_row(current, previous, 'D2_DYNAMIC')
        previous['time'] = .5
        with self.assertRaises(AssertionError):
            score.check_legacy_row(current, previous, 'D2_DYNAMIC')

    def test_actual_public_mapping_separate_from_unstaged_choice(self):
        anchors = {11: dict(status='UNIQUE_IOU_MATCH', gt_id=7),
                   12: dict(status='UNIQUE_IOU_MATCH', gt_id=8)}
        posts = {3: dict(status='UNIQUE_IOU_MATCH', gt_id=8),
                 4: dict(status='UNIQUE_IOU_MATCH', gt_id=7)}
        expected = event_audit.expected_mapping(anchors, posts)
        self.assertEqual(expected, {3: 12, 4: 11})
        restore = dict(status='LOCAL_FALLBACK_SYNTHETIC', mapping={'3': 11, '4': 12})
        _, selected, first = event_audit.mapping_outcome(restore, expected, expected)
        self.assertEqual((selected, first), ('NOT_STAGED', 'CORRECT'))
        posts[4]['status'] = 'UNSCORABLE_LOW_OR_AMBIGUOUS_IOU'
        self.assertEqual(event_audit.expected_mapping(anchors, posts), {})

    def test_fragment_cannot_join_across_q_version_change(self):
        key = ['synthetic', 'D5_MULTIFRAGMENT', 0, 11, 0]
        frozen = dict(source=2, public=11, key=key,
                      samples=[dict(frame=1), dict(frame=2)])
        event = dict(q=4, depth_frozen={'A': frozen})
        reference = dict(anchor_matches={11: dict(status='UNIQUE_IOU_MATCH', gt_id=7)},
            post_matches={3: dict(status='UNIQUE_IOU_MATCH', gt_id=7)})
        states = {(frame, 'D5_MULTIFRAGMENT'): dict(live={'2': dict(key=key, sample_frames=[1, 2])})
                  for frame in (1, 2)}
        states[(4, 'D5_MULTIFRAGMENT')] = dict(live={'3': dict(key=key, sample_frames=[])})
        states[(5, 'D5_MULTIFRAGMENT')] = dict(live={'3': dict(key=key[:-1]+[1], sample_frames=[5])})
        measurements = {4: dict(f6={'3': dict(qualified_piece_count=2,
            pieces=[dict(piece_id='synthetic/p0', qualified=True), dict(piece_id='synthetic/p1', qualified=True)])})}
        def known_match(frame, sources):
            return {source: dict(status='UNIQUE_IOU_MATCH', gt_id=7) for source in sources}
        result = event_audit.fragment_reference(event, reference, states, measurements,
            known_match, 'D5_MULTIFRAGMENT', 5)[0]
        self.assertEqual(result['pre_identity_reference'], 'UNIQUE_SAME_RGB_REFERENCE_ID')
        self.assertEqual(result['post_sample_frames'], [])
        self.assertEqual(result['post_stop_reason'], 'SOURCE_VERSION_CHANGE')
        self.assertEqual(result['surface_identity'], 'UNKNOWN')
        self.assertIsNone(result['physical_depth_reference_mm'])

    def test_unscorable_fragment_preserves_null_reference(self):
        event = dict(q=4, depth_frozen={'A': dict(source=2, public=11, key=None, samples=[])})
        result = event_audit.fragment_reference(event, {}, {}, {}, None, 'D5_MULTIFRAGMENT', 5)[0]
        self.assertEqual(result['pre_identity_reference'], 'UNKNOWN')
        self.assertEqual(result['surface_identity'], 'UNKNOWN')
        self.assertIsNone(result['physical_depth_reference_mm'])
        self.assertIn('NO_FROZEN_HISTORY', result['exclusions'])


def main():
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ScoringChecks)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    assert result.wasSuccessful()
    path = Path(sys.argv[1]) if len(sys.argv)>1 else HERE/'SCORE_CHECKS.json'
    write_new(path, dict(status='PASS_SYNTHETIC_ONLY', tests=result.testsRun, failures=0, errors=0,
        real_reference_files_read=0, new_model_http=0, physical_depth_gt=False,
        code_sha256={name: sha(HERE/name) for name in ('evaluate.py', 'event_audit.py', 'score_checks.py')}))


if __name__ == '__main__':
    main()
