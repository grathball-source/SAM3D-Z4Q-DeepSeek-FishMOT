"""Parser regression fixtures; the live 25-response parity is checked by audit.py."""
import json
import unittest

import audit


SENT = [dict(image_id=f"G{i:03d}", kind="G", relative_seconds=float(i),
             observation_tokens=[f"f{i:03d}:o01"]) for i in (1, 2)]
CITES = [dict(image_id=x["image_id"], relative_seconds=x["relative_seconds"],
              observation_tokens=x["observation_tokens"], observation="one real observation") for x in SENT]


def payload(evidence=CITES):
    edge = dict(relation="SUPPORT", cue="RELATIVE_MOTION", evidence=evidence,
                gaps_or_assumptions="none", competing_explanation="rival")
    return dict(request_id="R", edges={key: dict(edge) for key in audit.score.EDGES})


class ParserRegression(unittest.TestCase):
    def test_nonlist_and_empty_evidence_is_invalid_not_unresolved(self):
        for evidence in (None, {}, "citation", []):
            with self.subTest(evidence=evidence):
                result = audit.parse(json.dumps(payload(evidence)), "R", SENT, set())
                self.assertEqual(result["choice"], "ABSTAIN")
                self.assertTrue(all(row["status"] == "INVALID_EVIDENCE" for row in result["edges"].values()))
                self.assertNotIn("UNRESOLVED", {row["relation"] for row in result["edges"].values()})
                self.assertEqual(len(audit.evidence_status(evidence, SENT)), 2)

    def test_unsent_image_token_and_nonfinite_time(self):
        for changed in (dict(image_id="G999"), dict(observation_tokens=["f001:o99"]),
                        dict(relative_seconds=float("nan")), dict(relative_seconds=float("inf"))):
            with self.subTest(changed=changed):
                citations = [dict(CITES[0], **changed), CITES[1]]
                result = audit.parse(json.dumps(payload(citations)), "R", SENT, set())
                self.assertTrue(all(row["status"] == "INVALID_EVIDENCE" for row in result["edges"].values()))

    def test_missing_and_duplicate_edges(self):
        value = payload()
        del value["edges"]["B-Y"]
        self.assertEqual(audit.parse(json.dumps(value), "R", SENT, set())["schema_reason"],
                         "NOT_EXACTLY_FOUR_EDGES")
        edge = json.dumps(payload()["edges"]["A-X"])
        duplicated = '{"request_id":"R","edges":{"A-X":' + edge + ',"A-X":' + edge + '}}'
        self.assertEqual(audit.parse(duplicated, "R", SENT, set())["schema_reason"],
                         "DUPLICATE_JSON_KEY")

    def test_valid_decoder_unchanged(self):
        value = payload()
        for edge in ("A-Y", "B-X"):
            value["edges"][edge]["relation"] = "CONTRADICT"
        result = audit.parse(json.dumps(value), "R", SENT, set())
        self.assertEqual(result["choice"], "STRAIGHT")
        self.assertTrue(all(row["status"] == "VALID" for row in result["edges"].values()))

    def test_claim_usage_does_not_fold_competitor_into_path(self):
        phrase = "A endpoint is f009:o06, while the early track that becomes X later is f009:o03"
        self.assertEqual(audit.claim_usage(phrase, "f009:o03", [], "A", 2), "COMPARISON_OBJECT")
        self.assertEqual(audit.claim_usage("The A track has moved to f014:o04", "f014:o04", [], "A", 1),
                         "PATH_STEP")
        same_frame = "At G031 the A-Y continuation is f031:o01 and X is f031:o05; two fish"
        self.assertEqual(audit.claim_usage(same_frame, "f031:o01", [], "A", 2), "PATH_STEP")
        self.assertEqual(audit.claim_usage(same_frame, "f031:o05", [], "A", 2), "COMPARISON_OBJECT")


if __name__ == "__main__":
    unittest.main()
