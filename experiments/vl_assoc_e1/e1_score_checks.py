"""Synthetic-only scorer check; never opens real E1 GT."""
import copy

from e1_score import candidate_correctness, hist_truth, query_truth


def main():
    packet = dict(history=[dict(label=x, samples=[dict(local_frame=1)]) for x in ("A", "B")],
                  current=[dict(label=x) for x in ("X", "Y")],
                  candidates=[dict(candidate_id="C1", full_mapping={"X":"A", "Y":"B"}),
                              dict(candidate_id="C2", full_mapping={"X":"B", "Y":"A"})])
    episode = dict(query_frame=2, source_aliases=dict(identity_alias={"10":"A", "20":"B"},
                                                      native_alias={"1":"X", "2":"Y"}))
    baseline = {1: dict(variants={"Z4Q_STABLE":[dict(id=10,mask="n:1"),dict(id=20,mask="n:2")]})}
    matches = {1: dict(objects=[dict(native_id=1,gt_id=4,ambiguity=False),
                                dict(native_id=2,gt_id=5,ambiguity=False)]),
               2: dict(objects=[dict(native_id=1,gt_id=5,ambiguity=False),
                                dict(native_id=2,gt_id=4,ambiguity=False)])}
    history, old_reasons = hist_truth(packet, episode, baseline, matches)
    current, new_reasons = query_truth(packet, episode, matches)
    assert not old_reasons and not new_reasons
    assert candidate_correctness(packet, history, current) == {"C1":False,"C2":True}
    mixed = copy.deepcopy(packet)
    mixed["history"][0]["samples"].append(dict(local_frame=0))
    baseline[0] = baseline[1]
    matches[0] = dict(objects=[dict(native_id=1,gt_id=9,ambiguity=False),
                               dict(native_id=2,gt_id=5,ambiguity=False)])
    assert "mixed_history_A" in hist_truth(mixed, episode, baseline, matches)[1]
    matches[2]["objects"][1]["gt_id"] = 5
    assert "duplicated_GT_at_query" in query_truth(packet, episode, matches)[1]
    print("PASS_E1_SCORER_SYNTHETIC_NO_REAL_GT")


if __name__ == "__main__":
    main()
