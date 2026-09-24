"""Small AO1 contract regression, including the built five-case payload when configured."""
from __future__ import annotations

import json
import os
import re
import tempfile
import unittest
from pathlib import Path

import numpy as np

from build_full import candidate_options, continuity, predicted_runs
from build_input import digest, save_exact_crop, validate_frame


class Contracts(unittest.TestCase):
    def test_future_frame_and_timestamp_rejected(self):
        with self.assertRaisesRegex(AssertionError, "FUTURE_FRAME"):
            validate_frame(1499, {}, {}, [], Path("."), 1., cutoff_frame=1498)
        observation = dict(frame=1498, time=2., global_frame=10798)
        assignment = dict(frame=1498, time=2.)
        with self.assertRaises(AssertionError):
            validate_frame(1498, observation, assignment, [], Path("."), 1., cutoff_frame=1498)

    def test_exact_uncolored_rgb_roi(self):
        rgb = np.arange(6 * 9 * 3, dtype=np.uint8).reshape(6, 9, 3)
        mask = np.ones((2, 3), np.uint8)
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "crop.png"
            record = save_exact_crop(rgb, mask, [1, 0, 3, 2], output)
            self.assertEqual(record["rgb_xyxy"], [3, 0, 9, 6])
            self.assertTrue(record["pixel_exact"])
            self.assertFalse(record["colored"])

    def test_full_intermediate_certification_and_contact_risk(self):
        good = [dict(frame=f, native=1, public=2, epoch=3, contact=f == 2) for f in (1, 2, 3)]
        self.assertEqual(continuity(good)["contact_frames"], [2])
        self.assertTrue(continuity(good)["checked"])
        self.assertEqual(continuity(good[::2])["reason"], "MISSING_INTERMEDIATE")
        self.assertEqual(continuity([good[0], dict(good[1], epoch=4), good[2]])["reason"],
                         "IDENTITY_OR_EPOCH_CHANGE")
        self.assertEqual(continuity([good[0], dict(good[1], public=4), good[2]])["reason"],
                         "IDENTITY_OR_EPOCH_CHANGE")

    def test_right_edge_contact_is_censored(self):
        self.assertEqual(predicted_runs([False, True, True], 10),
                         [dict(start=11, end=12, right_censored=True)])
        self.assertEqual(predicted_runs([False, True, False], 10),
                         [dict(start=11, end=11, right_censored=False)])

    def test_candidate_permutation_preserves_physical_answer(self):
        hypotheses = [dict(id="A", mapping={"X": "A", "Y": "B"}),
                      dict(id="B", mapping={"X": "B", "Y": "A"})]
        for index in (0, 1):
            options, key = candidate_options(index, hypotheses, "B")
            winner = next(x for x in options if x["choice"] == key["answer"])
            self.assertEqual(winner["mapping"], hypotheses[1]["mapping"])
            self.assertEqual(len({tuple(sorted(x["mapping"].items())) for x in options}), 2)


class BuiltPayload(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        required = ("AO1_SOURCE_MANIFEST", "AO1_NUMERIC", "AO1_PRIVATE_ROOT", "AO1_REPO")
        if not all(os.environ.get(x) for x in required):
            raise unittest.SkipTest("Set AO1_* paths to verify the actual built payload")
        cls.source = json.loads(Path(os.environ["AO1_SOURCE_MANIFEST"]).read_text())
        cls.numeric = json.loads(Path(os.environ["AO1_NUMERIC"]).read_text())
        cls.private = Path(os.environ["AO1_PRIVATE_ROOT"])
        cls.repo = Path(os.environ["AO1_REPO"])

    def test_five_frozen_cases_and_causal_source_sets(self):
        cases = self.source["cases"]
        self.assertEqual({x["case_id"] for x in cases}, {
            "AO0-V-GT2-GT6-1322", "P4218132a1659f1e2", "P04c303d9612421d6",
            "P175d295a01799fe5", "P1797ad89bd359331"})
        for case in cases:
            self.assertEqual(case["V0"]["source_frames"], case["V1"]["source_frames"])
            self.assertTrue(set(case["V1"]["source_frames"]) <= set(case["V2"]["source_frames"]))
            lo, hi = case["v2_window"]
            self.assertEqual(case["V2"]["full_window_frames"], hi-lo+1)
            self.assertEqual(hi, case["query_frame"])
            self.assertEqual(case["full_frame_fixed_roi_xyxy"], [0, 0, 1920, 1080])
            self.assertTrue(all(x["source_time"] <= case["query_time"]
                                for x in case["source_by_frame"]))
            self.assertTrue(all(x["crop_pixel_exact"] for x in case["V1"]["roles"]))
            self.assertTrue(all(x["v0_matched_original_rgb_views"] for x in case["V1"]["roles"]))
            self.assertTrue(all(all(view["pixel_exact"] for view in x["v0_matched_original_rgb_views"])
                                for x in case["V1"]["roles"]))
            if case["case_alias"] == "B01":
                self.assertEqual(len(case["V1"]["matched_interaction_views"]), 4)
            else:
                self.assertTrue(all({view["view"] for view in x["v0_matched_original_rgb_views"]}
                                    == {"close", "context"} for x in case["V1"]["roles"]))

    def test_numeric_consumes_visible_sources_and_v0_v1_equal(self):
        by_id = {x["case_id"]: x for x in self.source["cases"]}
        for case in self.numeric["cases"]:
            self.assertIn(case["case_id"], by_id)
            v0, v1, v2 = case["versions"]
            self.assertEqual(v0["pairwise"], v1["pairwise"])
            self.assertEqual(v0["decision"], v1["decision"])
            for version in (v0, v1, v2):
                self.assertTrue(set(version["numeric_consumed_frames"]) <=
                                set(version["source_frames"]))

    def test_review_bundle_has_no_answer_or_source_identity(self):
        forbidden = ("GT2", "GT6", "KEEP", "SWAP", "correct", "answer_origin",
                     "/home/", "\\\\", "P4218132", "P04c303", "P175d295", "P1797ad")
        for case in self.source["cases"]:
            root = self.private / "blind" / case["case_alias"]
            self.assertEqual(len(list(root.glob("*/card.json"))), 3)
            for card_path in root.glob("*/card.json"):
                card = json.loads(card_path.read_text())
                text = json.dumps(card)
                for token in forbidden:
                    self.assertNotIn(token, text)
                self.assertIsNone(re.search(r"\bB0\b", text))
                self.assertEqual(set(card["answer_choices"]), {"C1", "C2", "INSUFFICIENT"})
                if card["timeline"] is not None:
                    self.assertTrue(all(x["relative_seconds"] <= 0 for x in card["timeline"]))

    def test_old_ao0_seal_unchanged(self):
        manifest = json.loads((self.repo / "experiments/ao0_association_observability/ARTIFACT_MANIFEST.json").read_text())
        wanted = {"METRICS.json", "OUTPUT_ORACLE_validation.jsonl.gz", "STATE_PREDICTIONS_validation.jsonl.gz"}
        actual = {Path(row["relative_path"]).name: row for row in manifest["public_git_files"]
                  if Path(row["relative_path"]).name in wanted}
        self.assertEqual(set(actual), wanted)
        for name, row in actual.items():
            self.assertEqual(digest(self.repo / row["relative_path"]), row["sha256"], name)

    def test_actual_ao0_contact_scan_boundary(self):
        validation = self.repo / "experiments/ao0_association_observability/validation"
        clipped = json.loads((validation / "CONTACT_PROBE.json").read_text())
        wide = json.loads((validation / "CONTACT_PROBE_WIDE.json").read_text())
        self.assertEqual(clipped["contacts"][-1]["end"], clipped["scan_window"][1])
        self.assertEqual(clipped["contacts"][-1]["end"], 1380)
        self.assertEqual(wide["contacts"][-1]["end"], 1419)
        self.assertEqual(clipped["queries"][0]["query_frame"], 1498)
        self.assertEqual(wide["queries"][0]["query_frame"], 1498)


if __name__ == "__main__":
    unittest.main()
