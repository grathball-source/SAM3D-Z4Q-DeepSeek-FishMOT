"""Small relation-contract tests; no GT raster or model call."""
import unittest

from relation_audit import no_unique_reason, segment, transitions


def observations(gt, publics):
    return [dict(gt_id=gt, frame=i + 1, public_id=p,
                 status="UNIQUE" if p is not None else "NO_UNIQUE_OBSERVATION")
            for i, p in enumerate(publics)]


class RelationAuditTests(unittest.TestCase):
    def test_global_public_renaming_changes_no_relation_event(self):
        source = {2: segment(observations(2, [1] * 10 + [4] * 10)),
                  6: segment(observations(6, [4] * 10 + [1] * 10))}
        renamed = {2: segment(observations(2, [9] * 10 + [8] * 10)),
                   6: segment(observations(6, [8] * 10 + [9] * 10))}
        a, b = transitions(source), transitions(renamed)
        self.assertEqual([(x["gt_id"], x["after_start"], x["after_duration"]) for x in a],
                         [(x["gt_id"], x["after_start"], x["after_duration"]) for x in b])

    def test_halfway_permanent_swap_is_visible_without_dominance(self):
        parts = {2: segment(observations(2, [1] * 50 + [4] * 50)),
                 6: segment(observations(6, [4] * 50 + [1] * 50))}
        self.assertEqual([(x["gt_id"], x["after_start"], x["after_duration"])
                          for x in transitions(parts)], [(2, 51, 50), (6, 51, 50)])

    def test_new_public_is_fragmentation_not_other_individual(self):
        change = transitions({2: segment(observations(2, [1] * 5 + [77] * 5))})
        self.assertEqual(len(change), 1)
        self.assertEqual((change[0]["gt_id"], change[0]["after_public"]), (2, 77))

    def test_missing_mixed_or_ambiguous_is_not_correct_or_error(self):
        parts = segment(observations(2, [1, None, None, 1]))
        self.assertEqual([x["status"] for x in parts],
                         ["UNIQUE", "NO_UNIQUE_OBSERVATION", "UNIQUE"])
        self.assertEqual(transitions({2: parts}), [])
        self.assertEqual(no_unique_reason([], []), "NO_MATCHED_PREDICTION")
        self.assertEqual(no_unique_reason([], [4]), "AMBIGUOUS_OR_MIXED_MASK")
        self.assertEqual(no_unique_reason([1, 2], []), "MULTIPLE_UNIQUE_MATCHES")

    def test_long_unknown_does_not_certify_one_interaction(self):
        parts = segment(observations(2, [1] * 3 + [None] * 100 + [4] * 3))
        self.assertEqual(parts[1]["count"], 100)
        self.assertEqual(transitions({2: parts})[0]["gap_frames"], 100)
        self.assertNotIn("interaction", transitions({2: parts})[0]["relation"].lower())


if __name__ == "__main__":
    unittest.main()
