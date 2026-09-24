"""Sealed non-GT checks of the real AO0 vertical slice."""
import gzip
import json
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent


def rows(name):
    with gzip.open(HERE / name, "rt", encoding="utf-8") as handle:
        yield from map(json.loads, handle)


class CounterfactualTests(unittest.TestCase):
    def test_atomic_and_complete(self):
        action = json.loads((HERE / "STATE_ACTION.json").read_text())
        seal = json.loads((HERE / "COUNTERFACTUAL_SEAL.json").read_text())
        self.assertTrue(action["stage_accepted"])
        self.assertIsNone(action["stage_rejection"])
        self.assertEqual(action["state_action"], "COMMITTED")
        self.assertFalse(seal["GT_read"])
        changed = 0
        for oracle, state in zip(rows("OUTPUT_ORACLE_validation.jsonl.gz"),
                                 rows("STATE_PREDICTIONS_validation.jsonl.gz"), strict=True):
            self.assertEqual(oracle["frame"], state["frame"])
            self.assertEqual(oracle["B0"], oracle["KEEP"])
            self.assertEqual([x["mask"] for x in oracle["B0"]],
                             [x["mask"] for x in oracle["SWAP"]])
            self.assertEqual(oracle["SWAP"], state["STATE"])
            if oracle["frame"] < seal["query_frame"]:
                self.assertEqual(oracle["B0"], state["STATE"])
            else:
                changed += oracle["B0"] != state["STATE"]
        self.assertEqual(changed, seal["state_changed_frames"])
        self.assertEqual(changed, 1391)

    def test_select_quality_spacing_defect_is_preserved_not_rerun(self):
        # Existing RQ0 risk sorting visits frame 100 before frame 10. Its
        # one-sided difference rejects the earlier item despite a 90-frame gap.
        source = (HERE.parent / "rq0_memory_headroom" / "select_quality.py").read_text()
        self.assertIn('item["frame"] - last_by_public.get(k, -100000) < 45', source)
        ranked = [(100, 2.0), (10, 1.0)]
        last = -100000
        chosen_old = []
        for frame, _ in ranked:
            if frame - last < 45:
                continue
            chosen_old.append(frame)
            last = frame
        self.assertEqual(chosen_old, [100])
        self.assertGreaterEqual(abs(10 - 100), 45)


if __name__ == "__main__":
    unittest.main()
