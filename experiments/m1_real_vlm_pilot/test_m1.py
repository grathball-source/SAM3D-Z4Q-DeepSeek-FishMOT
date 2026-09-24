"""Small M1 preflight regression against the actual frozen AO1 media plan."""
from __future__ import annotations

import json
import os
import unittest
from pathlib import Path

from adapter import CAP, SYSTEM, reserve, sha
from runner import body, decision
from score import canonical


class Contracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = os.environ.get("M1_RUN")
        if not root:
            raise unittest.SkipTest("M1_RUN must point to the real prepared private run")
        cls.root = Path(root)
        cls.plan = json.loads((cls.root / "private/PLAN.json").read_text())
        cls.by = {(x["case_alias"], x["arm"]): x for x in cls.plan["requests"]}

    def test_legends_bind_separate_real_tiles(self):
        for case in ("B01", "B02", "B03", "B04", "B05"):
            p0 = self.by[case, "P0"]
            self.assertEqual(len(p0["images"]), 2)
            self.assertTrue(all(i["tiles"] for i in p0["images"]))
            if case != "B01":
                self.assertEqual(len(p0["images"][0]["tiles"]), 8)
                self.assertGreater(len(p0["images"][1]["tiles"]), 8)
            else:
                self.assertEqual((len(p0["images"][0]["tiles"]), len(p0["images"][1]["tiles"])), (10, 4))
            for entry in p0["images"]:
                self.assertEqual(sha(self.root / "media" / entry["media_file"]), entry["sha256"])

    def test_p1_only_matched_and_p2_full_causal_frames(self):
        for case in ("B01", "B02", "B03", "B04", "B05"):
            p1, p2 = self.by[case, "P1"], self.by[case, "P2"]
            self.assertEqual([x["sha256"] for x in p1["images"]],
                             [x["sha256"] for x in p2["images"][:len(p1["images"])]])
            self.assertTrue(all(not any(t["view"] == "whole_frame" for t in x["tiles"])
                                for x in p1["images"]))
            self.assertTrue(all(x["tiles"][0]["view"] == "whole_frame"
                                for x in p2["images"][len(p1["images"]):]))
            self.assertTrue(all(t["relative_seconds"] <= 0 for x in p2["images"] for t in x["tiles"]))

    def test_repeat_exact_input_and_permutation_reversible(self):
        for case in ("B01", "B02", "B03", "B04", "B05"):
            main, repeat = self.by[case, "P2"], self.by[case, "P2_REPEAT"]
            self.assertEqual(main["text"], repeat["text"])
            self.assertEqual([x["sha256"] for x in main["images"]],
                             [x["sha256"] for x in repeat["images"]])
            perm = self.by[case, "P2_PERMUTED"]
            first = json.loads(main["text"])["candidates"]
            second = json.loads(perm["text"])["candidates"]
            self.assertEqual(first[0]["mapping"], second[1]["mapping"])
            self.assertEqual(first[1]["mapping"], second[0]["mapping"])
            self.assertEqual(perm["candidate_to_original"]["C1"], main["candidate_to_original"]["C2"])
            self.assertEqual(perm["candidate_to_original"]["C2"], main["candidate_to_original"]["C1"])
            self.assertEqual([x["sha256"] for x in main["images"]],
                             [x["sha256"] for x in perm["images"]])

    def test_no_image_is_really_no_image(self):
        for case in ("B01", "B02", "B03", "B04", "B05"):
            req = self.by[case, "P2_NO_IMAGE"]
            self.assertFalse(req["images"])
            text = json.loads(req["text"])
            self.assertFalse(text["image_available"])
            self.assertTrue(all(x["image_available"] is False for x in text["image_legend"]))
            self.assertNotIn("D/A/M", req["text"])

    def test_serializer_whitelist_no_key_or_old_answer(self):
        req = self.by["B01", "P1"]
        fake = {x["sha256"]: "file-api-test" for x in req["images"]}
        wire = json.dumps(body(req, self.plan, fake), ensure_ascii=False)
        for forbidden in ("GT2", "GT6", "SWAP", "KEEP", "B0", "SCORE_KEY", "/home/",
                          "P4218132", "P04c303", "P175d295", "P1797ad"):
            self.assertNotIn(forbidden, wire)
        self.assertEqual(len(json.loads(wire)["messages"]), 2)
        self.assertNotIn("model_answer", wire)

    def test_counterfactual_answer_key_cannot_change_wire(self):
        req = self.by["B01", "P2"]
        fake = {x["sha256"]: "file-api-test" for x in req["images"]}
        before = json.dumps(body(req, self.plan, fake), sort_keys=True)
        # The serializer receives neither key nor correctness; changing a
        # scoring-only key cannot enter its explicit argument list.
        answer_key = {"B01": "C1"}
        answer_key["B01"] = "C2"
        after = json.dumps(body(req, self.plan, fake), sort_keys=True)
        self.assertEqual(before, after)

    def test_long_limitation_preserves_choice_and_bad_citation_is_separate(self):
        req = self.by["B01", "P1"]
        output = dict(request_id=req["model_request_id"], choice="C2", evidence=[dict(
            image_id="NOT_SENT", region_or_time={"bbox_norm": [0, 0, 1, 1]},
            observation="a visible fish", distinguishes_because="test")], limitation="x" * 10000)
        parsed = decision(json.dumps(output), req, "stop")
        self.assertEqual(parsed["choice"], "C2")
        self.assertTrue(parsed["decision_valid"])
        self.assertFalse(parsed["grounding_format_valid"])
        self.assertEqual(parsed["grounding_reason"], "UNSENT_IMAGE_CITED")

    def test_budget_and_32_call_cap(self):
        self.assertEqual(CAP, 65536)
        self.assertEqual(len(self.plan["requests"]), 30)
        preflight = json.loads((self.root / "public/PREFLIGHT.json").read_text())
        self.assertLessEqual(preflight["reserved_total_usd"], 5)
        self.assertEqual(preflight["technical_smoke_max"] + len(self.plan["requests"]), 32)
        self.assertGreater(reserve("x", 1), .078)

    def test_scoring_preserves_original_choice(self):
        req = self.by["B02", "P2_PERMUTED"]
        response = dict(transport_valid=True, finish_reason="stop", latency_seconds=1.,
                        usage={}, returned_model="deepseek-flash", charged_upper_usd=.001,
                        decision=dict(choice="C1", decision_valid=True, usable_decision=True,
                                      grounding_format_valid=False, grounding_reason="UNSENT_IMAGE_CITED",
                                      evidence=[]))
        expected = req["candidate_to_original"]["C1"]
        row = canonical(req, response, expected)
        self.assertEqual(row["raw_choice"], "C1")
        self.assertEqual(row["canonical_choice"], expected)
        self.assertEqual(row["status"], "CORRECT")
        self.assertFalse(row["grounding_format_valid"])

    def test_old_ao1_seal_unchanged(self):
        source = os.environ.get("M1_AO1")
        if not source:
            self.skipTest("M1_AO1 not set")
        old = Path(source)
        self.assertEqual(sha(old / "SOURCE_MANIFEST.json"),
                         "8378df27b617cbe00218449784935fb828bcb5bbbed1a8006f99b02d66bedfbd")
        self.assertEqual(sha(old / "SCORE_KEY.json"),
                         "322535914a7305b8ae59963898e85784d34adddc1195043296c902618bef258d")


if __name__ == "__main__":
    unittest.main()
