"""Bind the four sealed answers to sent facts and postseal local identity GT."""
from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PUBLIC = HERE.parent / "public"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def endpoint(segment):
    last = segment["observations"][-1]
    velocity = segment["velocity"]
    return {
        "source_fact_id": last["fact_id"], "source_frame": last["source_frame"],
        "time_seconds": last["source_time_seconds"],
        "observation_count": len(segment["observations"]),
        "center_px": last["bbox_center_px"], "bbox_px": last["bbox_px"],
        "depth_fact_id": last["depth"]["fact_id"],
        "whole_depth_mm": last["depth"]["whole"]["median"],
        "whole_depth_mad_mm": last["depth"]["whole"]["mad"],
        "whole_depth_valid_fraction": last["depth"]["whole"]["valid_fraction"],
        "core_depth_mm": last["depth"]["core"]["median"],
        "core_depth_mad_mm": last["depth"]["core"]["mad"],
        "core_depth_valid_fraction": last["depth"]["core"]["valid_fraction"],
        "velocity_fact_id": velocity.get("fact_id"),
        "velocity_px_per_s": velocity.get("velocity_px_per_s"),
        "speed_px_per_s": velocity.get("speed_px_per_s"),
        "velocity_status": velocity["epistemic_type"],
    }


def depth_distance(hypothesis, endpoints, kind):
    values = []
    for role in ("X", "Y"):
        pre = endpoints[hypothesis[role]][f"{kind}_depth_mm"]
        post = endpoints[role][f"{kind}_depth_mm"]
        if pre is None or post is None:
            return None
        values.append({"post_role": role, "pre_role": hypothesis[role],
                       "absolute_mm": abs(post - pre)})
    return {"edges": values, "sum_absolute_mm": sum(x["absolute_mm"] for x in values)}


def main():
    scored_path = HERE / "COUNTERFACTUAL_METRICS.json"
    scored = read(scored_path)
    events_path = PUBLIC / "EVENTS.json"
    events = read(events_path)
    assert [x["case"] for x in events] == ["B03", "B01", "B05", "B04"]
    result = {"status": "POSTSEAL_CLAIM_AND_PHYSICAL_MAPPING_AUDIT",
              "source_sha256": {"events": sha(events_path), "postseal_score": sha(scored_path)},
              "cases": {}}
    old_prediction = PUBLIC / "predictions_validation.jsonl.gz"
    ablated_prediction = HERE / "predictions_b03_only.jsonl.gz"
    result["source_sha256"].update({"old_prediction": sha(old_prediction),
                                     "b03_only_prediction": sha(ablated_prediction)})
    permutation = {"pre_frames_same": 0, "middle_frames_swap_1_5": 0,
                   "tail_frames_b1_vs_b03_only_swap_4_5": 0, "masks_equal_frames": 0}
    with gzip.open(old_prediction, "rt", encoding="utf-8") as old_rows, \
            gzip.open(ablated_prediction, "rt", encoding="utf-8") as ablated_rows:
        for original_text, ablated_text in zip(old_rows, ablated_rows, strict=True):
            original, ablated = json.loads(original_text), json.loads(ablated_text)
            frame = original["frame"]
            assert frame == ablated["frame"]
            b0, b1 = original["variants"]["B0"], original["variants"]["B1"]
            only = ablated["variants"]["B03_ONLY"]
            assert [x["mask"] for x in b0] == [x["mask"] for x in b1] == [x["mask"] for x in only]
            permutation["masks_equal_frames"] += 1
            if frame < 377:
                assert b0 == b1 == only
                permutation["pre_frames_same"] += 1
            elif frame < 2638:
                assert b1 == only
                assert all(y["id"] == {1: 5, 5: 1}.get(x["id"], x["id"])
                           for x, y in zip(b0, only, strict=True))
                permutation["middle_frames_swap_1_5"] += 1
            else:
                assert all(y["id"] == {4: 5, 5: 4}.get(x["id"], x["id"])
                           for x, y in zip(only, b1, strict=True))
                permutation["tail_frames_b1_vs_b03_only_swap_4_5"] += 1
    assert permutation == {"pre_frames_same": 376, "middle_frames_swap_1_5": 2261,
                           "tail_frames_b1_vs_b03_only_swap_4_5": 251,
                           "masks_equal_frames": 2888}
    result["permutation_parity"] = permutation
    for event in events:
        case, q = event["case"], event["frame"]
        packet_path = PUBLIC / "requests" / f"{case}.json"
        response_path = PUBLIC / "responses" / f"{case}.json"
        packet, response = read(packet_path), read(response_path)
        binding = scored["postseal_role_gt_binding"][case]
        assert packet["q_frame"] == q and response["choice"] == event["choice"]
        assert response["parse_status"] == "VALID"
        ends = {role: endpoint(packet["PRE_HISTORY"][role]) for role in ("A", "B")}
        ends.update({role: endpoint(packet["POST_HISTORY_TO_Q"][role]) for role in ("X", "Y")})
        for role in ("A", "B"):
            assert ends[role]["source_frame"] == binding["references"][role]["frame"]
        for role in ("X", "Y"):
            assert ends[role]["source_frame"] == binding["q"][role]["frame"] == q
        hypotheses = {}
        for item in packet["hypotheses"]:
            mapping = {role: item["mapping"][role] for role in ("X", "Y")}
            local_matches = {role: binding["q"][role]["gt"] ==
                             binding["references"][mapping[role]]["local_gt"]
                             for role in ("X", "Y")}
            assert all(binding["q"][role]["gt"] is not None and
                       binding["references"][mapping[role]]["local_gt"] is not None
                       for role in ("X", "Y"))
            hypotheses[item["id"]] = {
                "mapping": mapping, "local_gt_edge_matches": local_matches,
                "complete_local_gt_match": all(local_matches.values()),
                "whole_depth_endpoint_distance": depth_distance(mapping, ends, "whole"),
                "core_depth_endpoint_distance": depth_distance(mapping, ends, "core"),
            }
        assert set(hypotheses) == {"H1", "H2"}
        assert sum(x["complete_local_gt_match"] for x in hypotheses.values()) == 1
        chosen = event["choice"]
        reason = json.loads(response["content"])["reason"]
        result["source_sha256"][case] = {"packet": sha(packet_path), "response": sha(response_path)}
        result["cases"][case] = {
            "q": q, "trigger_frame": packet["trigger"]["frame"],
            "trigger_scope": packet["trigger"]["scope"],
            "model_choice": chosen, "action": event["status"],
            "model_reason": reason,
            "chosen_complete_local_gt_match": hypotheses[chosen]["complete_local_gt_match"],
            "endpoint_facts": ends,
            "pre_to_q_gap_seconds": {role: packet["q_time_seconds"] - ends[role]["time_seconds"]
                                     for role in ("A", "B")},
            "interaction_rows": len(packet["INTERACTION_TABLE"]["rows"]),
            "identity_reappearance": packet["first_identity_reappearance"],
            "per_object_loss": packet["per_object_loss"],
            "per_handle_clean_return": packet["per_handle_clean_return"],
            "relative_motion": packet["relative_motion"],
            "hypotheses": hypotheses,
            "postseal_role_gt_binding": binding,
        }
    values = result["cases"].values()
    result["summary"] = {
        "raw_choices_correct_local": sum(x["chosen_complete_local_gt_match"] for x in values),
        "raw_choices_wrong_local": sum(not x["chosen_complete_local_gt_match"] for x in values),
        "committed_wrong_local": sum(x["action"] == "COMMIT" and
                                      not x["chosen_complete_local_gt_match"] for x in values),
        "keep_wrong_local": sum(x["action"] == "KEEP" and
                                 not x["chosen_complete_local_gt_match"] for x in values),
    }
    assert result["summary"] == {"raw_choices_correct_local": 1,
                                  "raw_choices_wrong_local": 3,
                                  "committed_wrong_local": 2,
                                  "keep_wrong_local": 1}
    target = HERE / "CLAIM_AND_MAPPING_AUDIT.json"
    with target.open("x", encoding="utf-8", newline="\n") as out:
        json.dump(result, out, ensure_ascii=False, indent=2, allow_nan=False)
        out.write("\n")
    print(json.dumps(result["summary"]))


if __name__ == "__main__":
    main()
