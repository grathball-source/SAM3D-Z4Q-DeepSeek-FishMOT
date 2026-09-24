"""Answer-free M2-T engineering regressions; run on the source host."""
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

import build
import score

RUN = None


class ContractTests(unittest.TestCase):
    def test_integer_sampling_and_query_guard(self):
        self.assertEqual(len(build.uniform_frames(1262, 1498)), 32)
        self.assertEqual(build.uniform_frames(5, 7), [5, 6, 7])
        with self.assertRaises(AssertionError):
            build.case_frames(dict(v2_window=[10, 12], query_frame=11, V1={'roles': []}))

    def test_grayscale_no_cross_frame_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            mask = np.zeros((360, 640), dtype=bool)
            mask[20:40, 60:90] = True
            image, public, private = build.render_frame(3, 1, [0, 0, 120, 80], {'n:99': mask},
                {'A': 'A'}, [], 12.0, 13.0, Path(temp))
            raw = cv2.imread(str(Path(temp) / image['media_file']))
            self.assertTrue(np.array_equal(raw[:, :, 0], raw[:, :, 1]))
            self.assertTrue(np.array_equal(raw[:, :, 1], raw[:, :, 2]))
            self.assertNotIn('n:99', json.dumps(public))
            self.assertIn('n:99', json.dumps(private))

    def test_decoder_off_permutation_and_symmetry(self):
        empty = {edge: dict(status='VALID', relation='UNRESOLVED') for edge in score.EDGES}
        self.assertEqual(score.decode(empty), 'ABSTAIN')
        straight = {edge: dict(status='VALID', relation='SUPPORT' if edge in ('A-X', 'B-Y')
                               else 'CONTRADICT') for edge in score.EDGES}
        self.assertEqual(score.decode(straight), 'STRAIGHT')
        swapped = {edge: straight[{'A-X':'A-Y','A-Y':'A-X','B-X':'B-Y','B-Y':'B-X'}[edge]]
                   for edge in score.EDGES}
        self.assertEqual(score.decode(swapped), 'CROSSED')
        straight['A-Y'] = dict(status='INVALID_EVIDENCE', relation='CONTRADICT')
        self.assertEqual(score.decode(straight), 'ABSTAIN')

    def test_citation_rejection(self):
        sent = [dict(image_id='G001', kind='G', relative_seconds=-2.0,
                     observation_tokens=['f001:o01'])]
        valid = dict(image_id='G001', observation_tokens=['f001:o01'],
                     relative_seconds=-2.0, observation='fish moved')
        self.assertIsNone(score.evidence_status([valid], sent)[0])
        for change in (dict(image_id='G999'), dict(observation_tokens=['n:1']),
                       dict(relative_seconds=2.0)):
            self.assertIsNotNone(score.evidence_status([dict(valid, **change)], sent)[0])
        edge = dict(relation='SUPPORT', cue='RELATIVE_MOTION', evidence=[valid],
                    gaps_or_assumptions='', competing_explanation='')
        payload = dict(request_id='test', edges={name: edge for name in score.EDGES})
        parsed = score.parse(json.dumps(payload), 'test', sent, set())
        self.assertTrue(parsed['schema_valid'])
        self.assertEqual(parsed['choice'], 'ABSTAIN')
        self.assertTrue(all(x['status'] == 'INVALID_EVIDENCE' for x in parsed['edges'].values()))
        del payload['edges']['B-Y']
        self.assertFalse(score.parse(json.dumps(payload), 'test', sent, set())['schema_valid'])

    def test_legal_four_edge_response_changes_choice(self):
        sent = [dict(image_id=f'G{i:03d}', kind='G', relative_seconds=float(i),
                     observation_tokens=[f'f{i:03d}:o01']) for i in (1, 2)]
        citations = [dict(image_id=x['image_id'], observation_tokens=x['observation_tokens'],
                          relative_seconds=x['relative_seconds'], observation='observed position change')
                     for x in sent]
        edges = {name: dict(relation='SUPPORT' if name in ('A-X', 'B-Y') else 'CONTRADICT',
                            cue='RELATIVE_MOTION', evidence=citations,
                            gaps_or_assumptions='none established', competing_explanation='other path')
                 for name in score.EDGES}
        parsed = score.parse(json.dumps(dict(request_id='R', edges=edges)), 'R', sent, set())
        self.assertTrue(parsed['schema_valid'])
        self.assertEqual(parsed['choice'], 'STRAIGHT')
        self.assertTrue(all(x['status'] == 'VALID' for x in parsed['edges'].values()))
        self.assertEqual(score.parse(json.dumps(dict(request_id='R', edges=edges)), 'wrong', sent, set())['choice'], 'ABSTAIN')

    def test_frozen_real_inputs(self):
        if RUN is None:
            self.skipTest('no real run path')
        source = build.json.loads((RUN / 'public/SOURCE_MANIFEST.json').read_text())
        plan = build.json.loads((RUN / 'sender/PLAN.json').read_text())
        self.assertEqual(len(source['cases']), 5)
        self.assertEqual(len(plan['requests']), 25)
        self.assertNotIn('SCORE_KEY', (RUN / 'sender/PLAN.json').read_text())
        self.assertFalse((RUN / 'sender/SCORE_KEY.json').exists())
        for case in source['cases']:
            self.assertEqual(len(case['sampled_window_frames']), 32)
            self.assertEqual(max(case['all_frames']), case['query_frame'])
            self.assertTrue(set(case['endpoint_frames']) <= set(case['all_frames']))
            self.assertEqual(len(case['g_images']), len(case['all_frames']))
            self.assertGreaterEqual(len(case['ap_images']), 4)
            roi = case['roi_mask_xyxy']
            self.assertTrue(0 <= roi[0] < roi[2] <= 640 and 0 <= roi[1] < roi[3] <= 360)
            for image in case['g_images']:
                path = RUN / 'sender/media' / image['media_file']
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), image['sha256'])
                rgb = cv2.imread(str(path))
                self.assertTrue(np.array_equal(rgb[:, :, 0], rgb[:, :, 1]))
                self.assertTrue(np.array_equal(rgb[:, :, 1], rgb[:, :, 2]))
            arms = {x['arm']: x for x in plan['requests'] if x['case_alias'] == case['case_alias']}
            self.assertEqual(arms['G-SEQ']['core_text'], arms['G+AP']['core_text'])
            self.assertEqual(arms['G-SEQ']['core_text'], arms['G-SEQ-REPEAT']['core_text'])
            self.assertEqual(arms['G+AP']['ap_text'], arms['G+AP-REPEAT']['ap_text'])
            self.assertEqual(arms['G-SEQ']['images'], arms['G-SEQ-REPEAT']['images'])
            self.assertEqual(arms['G+AP']['images'], arms['G+AP-REPEAT']['images'])
            self.assertEqual(arms['G-SEQ']['images'], arms['G+AP']['images'][:len(arms['G-SEQ']['images'])])
            self.assertEqual(set(x['image_id'] for x in arms['G-END']['images']),
                             {image['image_id'] for image, frame in zip(case['g_images'], case['all_frames'])
                              if frame in case['endpoint_frames']})
            bodies = RUN / 'sender/private/bodies'
            if bodies.exists():
                def body(arm):
                    return (bodies / (case['case_alias'] + '-' + arm + '.json')).read_bytes()
                self.assertEqual(body('G-SEQ'), body('G-SEQ-REPEAT'))
                self.assertEqual(body('G+AP'), body('G+AP-REPEAT'))
                seq_content = json.loads(body('G-SEQ'))['messages'][1]['content']
                ap_content = json.loads(body('G+AP'))['messages'][1]['content']
                self.assertEqual(seq_content, ap_content[:len(seq_content)])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', type=Path)
    options, rest = parser.parse_known_args()
    RUN = options.run
    unittest.main(argv=[__file__, *rest])
