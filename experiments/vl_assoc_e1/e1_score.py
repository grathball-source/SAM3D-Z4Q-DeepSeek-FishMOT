"""Independent E1 scorer. This process alone opens E1 GT, after full decision seal."""
from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import json
import os
from collections import Counter
from pathlib import Path

from e1_protocol import decode, model_off, validate_packet, validate_response
from preflight_e1 import read, sha

HERE = Path(__file__).resolve().parent
RUN_ID = os.environ.get("E1_RUN_ID", "api_run_20260923")
assert RUN_ID in {"api_run_20260923", "api_rerun_20260923_default64k"}
RUN = HERE / RUN_ID


def lines(path):
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]


def gz_needed(path, needed):
    out = {}
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            if row["frame"] in needed:
                out[row["frame"]] = row
    assert set(out) == needed, (path, len(out), len(needed))
    return out


def verify_seal(partial=False):
    output = "PARTIAL_SUMMARY.json" if partial else "SUMMARY.json"
    assert not (RUN / output).exists(), "scoring already archived"
    seal = read(RUN / ("EARLY_STOP_SEALED.json" if partial else "DECISIONS_SEALED.json"))
    assert seal["status"] == ("STOP_VALIDITY_GATE_UNATTAINABLE_SEALED_BEFORE_GT" if partial else
                               "SEALED_BEFORE_INDEPENDENT_E1_SCORING")
    assert seal["technical_smoke_calls"] == 2
    assert (seal["formal_calls_completed"] == 34 and seal["formal_calls_started"] == 35
            if partial else seal["formal_calls"] == 120)
    assert seal["E1_GT_read"] is False
    assert seal["freeze_sha256"] == sha(HERE / "FREEZE.json")
    assert seal["authorization_sha256"] == sha(RUN / "RUN_AUTHORIZATION.json")
    assert seal["ledger_sha256"] == sha(RUN / "CALL_LEDGER.jsonl")
    assert seal["decisions_sha256"] == sha(RUN / "DECISIONS.jsonl")
    for name, expected in seal["response_sha256"].items():
        assert sha(RUN / "responses" / name) == expected
    assert len(seal["response_sha256"]) == (36 if partial else 122)
    ledger = lines(RUN / "CALL_LEDGER.jsonl")
    starts = {x["id"]: x for x in ledger if x["phase"] == "start"}
    completes = {x["id"]: x for x in ledger if x["phase"] == "complete"}
    if partial:
        assert len(starts) == 37 and len(completes) == 36
        assert set(starts) - set(completes) == {"F000035"}
        assert (RUN / "formal_exit_code.txt").read_text().strip() == "143"
    else:
        assert len(starts) == len(completes) == 122 and set(starts) == set(completes)
    plan_path = RUN / "COST_PLAN.json" if RUN_ID.endswith("default64k") else HERE / "COST_PLAN_FINAL.json"
    planned = {x["request"]: x for x in read(plan_path)["requests"]}
    assert len(planned) == 120
    for ident, start in starts.items():
        public = read(RUN / "requests" / f"{ident}.json")
        private_path = RUN / "private_api" / "requests" / f"{ident}.json"
        assert sha(private_path) == public["payload_sha256"] == start["payload_sha256"]
        assert private_path.stat().st_size == public["payload_bytes"]
        if ident.startswith("F"):
            plan = planned[public["arm"]]
            assert public["payload_sha256"] == plan["payload_sha256"]
            assert public["image_sha256"] == plan["image_sha256"]
        if ident in completes:
            response = read(RUN / "responses" / f"{ident}.json")
            assert response["private_raw_response_sha256"] == \
                   sha(RUN / "private_api" / "responses" / f"{ident}.json")
            assert completes[ident]["public_response_sha256"] == sha(RUN / "responses" / f"{ident}.json")
        else:
            assert not (RUN / "responses" / f"{ident}.json").exists()
    decisions = lines(RUN / "DECISIONS.jsonl")
    assert len(decisions) == len({x["id"] for x in decisions}) == (34 if partial else 120)
    assert all(x["id"].startswith("F") for x in decisions)
    return seal, decisions


def hist_truth(packet, episode, baseline, matches):
    public_by_alias = {alias: int(public) for public, alias in
                       episode["source_aliases"]["identity_alias"].items()}
    histories, reasons = {}, []
    for node in packet["history"]:
        public = public_by_alias[node["label"]]
        source_gts = []
        if not node["samples"]:
            reasons.append("empty_history_" + node["label"])
        for sample in node["samples"]:
            frame = sample["local_frame"]
            owners = [int(x["mask"].split(":")[1]) for x in baseline[frame]["variants"]["Z4Q_STABLE"]
                      if x["id"] == public]
            assert len(owners) <= 1
            if not owners:
                reasons.append("missing_B0_owner_" + node["label"])
                continue
            obj = next((x for x in matches[frame]["objects"] if x["native_id"] == owners[0]), None)
            if obj is None or obj["gt_id"] is None or obj.get("ambiguity"):
                reasons.append("unmatched_history_" + node["label"])
            else:
                source_gts.append(obj["gt_id"])
        if len(set(source_gts)) > 1:
            reasons.append("mixed_history_" + node["label"])
        if len(source_gts) != len(node["samples"]):
            reasons.append("incomplete_history_" + node["label"])
        if source_gts and len(set(source_gts)) == 1:
            histories[node["label"]] = source_gts[0]
    if len(histories) == 2 and len(set(histories.values())) < 2:
        reasons.append("histories_same_GT")
    return histories, sorted(set(reasons))


def query_truth(packet, episode, matches):
    native_by_alias = {alias: int(native) for native, alias in
                       episode["source_aliases"]["native_alias"].items()}
    match = matches[episode["query_frame"]]
    truth, reasons = {}, []
    for node in packet["current"]:
        native = native_by_alias[node["label"]]
        obj = next((x for x in match["objects"] if x["native_id"] == native), None)
        if obj is None or obj["gt_id"] is None or obj.get("ambiguity"):
            reasons.append("unmatched_query_" + node["label"])
        else:
            truth[node["label"]] = obj["gt_id"]
    if len(truth) != len(packet["current"]):
        reasons.append("incomplete_query")
    if len(set(truth.values())) != len(truth):
        reasons.append("duplicated_GT_at_query")
    return truth, sorted(set(reasons))


def candidate_correctness(packet, histories, current):
    result = {}
    for candidate in packet["candidates"]:
        mapping = candidate["full_mapping"]
        assigned = {history: current[observation] for observation, history in mapping.items()
                    if history in histories and observation in current}
        result[candidate["candidate_id"]] = (set(assigned) == set(histories) and
                                             all(assigned[h] == gt for h, gt in histories.items()))
    return result


def response_audit(decisions, episodes, partial=False):
    aliases = read(HERE / "PERMUTATION_MAPS.json")
    by_packet = {}
    valid_count = 0
    flip_effect = 0
    for row in decisions:
        pid, arm = row["packet_id"], row["arm"]
        manifest = read(HERE / "request_manifest" / f"{pid}_{arm}.json")
        packet = read(HERE / "packets" / manifest["packet_file"])
        assert validate_packet(packet)
        original_base = episodes[pid]["baseline_candidate"]
        baseline = ({v:k for k,v in aliases[pid].items()}[original_base]
                    if arm.endswith("permuted") else original_base)
        response = read(RUN / "responses" / f"{row['id']}.json")
        assert row["response_sha256"] == sha(RUN / "responses" / f"{row['id']}.json")
        try:
            output = json.loads(response["content"])
        except (TypeError, ValueError):
            output = None
        valid, reason = validate_response(packet, output)
        valid = valid and response["finish_reason"] == "stop"
        assert valid == row["response_valid"], (row["id"], reason)
        decoded = (decode(packet, output, baseline) if valid else
                   dict(selected=baseline, status="INVALID", reason=reason))
        selected = aliases[pid][decoded["selected"]] if arm.endswith("permuted") else decoded["selected"]
        assert (selected, decoded["status"]) == (row["selected_original"], row["status"])
        assert model_off(packet, baseline)["selected"] == baseline
        valid_count += valid
        by_packet.setdefault(pid, {})[arm] = row
        if arm == "L-V-temporal" and valid and len(packet["candidates"]) == 2:
            flipped = copy.deepcopy(output)
            comparison = flipped["comparisons"][0]
            if comparison["relation"] in ("LEFT_BETTER", "RIGHT_BETTER"):
                comparison["relation"] = ("RIGHT_BETTER" if comparison["relation"] == "LEFT_BETTER"
                                          else "LEFT_BETTER")
                assert validate_response(packet, flipped)[0]
                other = decode(packet, flipped, baseline)["selected"]
                flip_effect += other != decoded["selected"]
    if partial:
        assert len(by_packet) == 7 and sorted(len(x) for x in by_packet.values()) == [4, 5, 5, 5, 5, 5, 5]
    else:
        assert len(by_packet) == 24 and all(len(x) == 5 for x in by_packet.values())
    return by_packet, valid_count, flip_effect


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--partial-stop", action="store_true")
    for flag in ("dev_baseline", "val_baseline", "dev_matches", "val_matches"):
        ap.add_argument("--" + flag.replace("_", "-"), type=Path, required=True)
    args = ap.parse_args()
    partial = args.partial_stop
    seal, decisions = verify_seal(partial)  # Do not open GT above this line.
    episodes = {x["packet_id"]: x for split in ("development", "validation")
                for x in lines(HERE / f"EPISODES_{split}.jsonl")}
    assert len(episodes) == 24
    by_packet, valid_responses, flip_effect = response_audit(decisions, episodes, partial)
    paths = dict(development=(args.dev_baseline, args.dev_matches),
                 validation=(args.val_baseline, args.val_matches))
    truth_sources = {}
    lookup = {}
    for split, (baseline_path, match_path) in paths.items():
        selected = [x for x in episodes.values() if x["split"] == split and x["packet_id"] in by_packet]
        if not selected:
            continue
        needed = {sample["local_frame"] for ep in selected
                  for node in read(HERE / "packets" / f"{ep['packet_id']}.json")["history"]
                  for sample in node["samples"]}
        needed |= {ep["query_frame"] for ep in selected}
        baseline = gz_needed(baseline_path, needed)
        matches = gz_needed(match_path, needed)
        assert all(baseline[f]["global_frame"] == matches[f]["global_frame"] for f in needed)
        truth_sources[split] = dict(baseline_sha256=sha(baseline_path),
                                    offline_matches_sha256=sha(match_path), frames_read=len(needed))
        lookup[split] = (baseline, matches)
    if "validation" in truth_sources:
        assert truth_sources["validation"]["offline_matches_sha256"] == \
               read(HERE / "R0_SCORE_AUDIT.json")["match_sha256"]
    results, unscorable = [], []
    for pid, episode in episodes.items():
        if pid not in by_packet:
            continue
        packet = read(HERE / "packets" / f"{pid}.json")
        baseline, matches = lookup[episode["split"]]
        hist, old_reasons = hist_truth(packet, episode, baseline, matches)
        now, new_reasons = query_truth(packet, episode, matches)
        reasons = sorted(set(old_reasons + new_reasons))
        scorable = not reasons and len(hist) == 2 and len(now) == len(packet["current"])
        correctness = candidate_correctness(packet, hist, now) if scorable else None
        arm_rows = by_packet[pid]
        selections = {arm: arm_rows[arm]["selected_original"] for arm in arm_rows}
        base_id = episode["baseline_candidate"]
        numeric = episode["numeric"]["N"]["selected"]
        correct = (dict(B0=correctness[base_id], N=correctness[numeric],
                        **{arm: correctness[choice] for arm, choice in selections.items()})
                   if scorable else None)
        result = dict(packet_id=pid, split=episode["split"], query_frame=episode["query_frame"],
                      candidate_count=len(packet["candidates"]), executable_nonbaseline=episode["executable_nonbaseline"],
                      scorable=scorable, unscorable_reasons=reasons,
                      history_GT=hist, query_GT=now, candidate_correct=correctness,
                      B0=base_id, N=numeric, selected=selections,
                      response_valid={arm: arm_rows[arm]["response_valid"] for arm in arm_rows},
                      correct=correct,
                      opportunity=bool(scorable and any(correctness[x] for x in correctness if x != base_id)
                                       and not correctness[base_id]),
                      nonparticipant_mapping_preserved=all(c["full_mapping"].items() >= packet["fixed_observations"].items()
                                                           for c in packet["candidates"]))
        assert result["nonparticipant_mapping_preserved"]
        results.append(result)
        if not scorable:
            unscorable.append(dict(packet_id=pid, reasons=reasons))
    scorable = [x for x in results if x["scorable"]]
    main = "L-V-temporal"
    correct_counts = {arm: sum(x["correct"][arm] for x in scorable)
                      for arm in ("B0", "N", "L-T", "L-V-static", main)}
    new_harm = sum(x["correct"]["B0"] and x["selected"][main] != x["B0"] and
                   not x["correct"][main] for x in scorable)
    agreement = {arm: sum(x["response_valid"][main] and x["response_valid"].get(arm, False) and
                          x["selected"][main] == x["selected"][arm] for x in results)
                 for arm in ("L-V-temporal-repeat", "L-V-temporal-permuted")}
    model_change = sum(x["selected"][main] != x["B0"] for x in results)
    validity_gate = .90 if RUN_ID.endswith("default64k") else .95
    validity_name = "valid_rate_ge_90" if RUN_ID.endswith("default64k") else "valid_rate_ge_95"
    gates = dict(formal_complete=len(decisions) == 120,
                 scorable_ge_8=len(scorable) >= 8,
                 improvement_opportunities_ge_2=sum(x["opportunity"] for x in results) >= 2,
                 temporal_minus_N_ge_2=correct_counts[main] - correct_counts["N"] >= 2,
                 no_new_B0_correct_harm=new_harm == 0,
                 repeat_agreement_ge_90=agreement["L-V-temporal-repeat"] / 24 >= .9,
                 alias_agreement_ge_90=agreement["L-V-temporal-permuted"] / 24 >= .9,
                 nonzero_real_model_influence=model_change > 0 and flip_effect > 0)
    gates[validity_name] = valid_responses / 120 >= validity_gate
    conclusion = ("ENGINEERING_FAILURE" if not gates["formal_complete"] or not gates[validity_name] else
                  "INCONCLUSIVE" if not gates["scorable_ge_8"] or not gates["improvement_opportunities_ge_2"] else
                  "PASS" if all(gates.values()) else "FAIL")
    summary = dict(research_conclusion=("INCONCLUSIVE" if RUN_ID.endswith("default64k") else conclusion),
                   exploratory_gate_outcome=(conclusion if RUN_ID.endswith("default64k") else None),
                   confirmatory_blind=(not RUN_ID.endswith("default64k")),
                   engineering_status=("STOPPED_EARLY_VALIDITY_GATE" if partial else "SCORED_SEALED_E1"),
                   base_commit=read(HERE / "CONFIG.json")["base_commit"],
                   formal_calls=len(decisions), formal_calls_started=(35 if partial else 120),
                   smoke_calls=2, response_valid=valid_responses,
                   scorable=len(scorable), unscorable=len(unscorable),
                   improvement_opportunities=sum(x["opportunity"] for x in results),
                   correct_counts=correct_counts, new_B0_correct_harm=new_harm,
                   repeat_agreement=agreement, model_changes_from_B0=model_change,
                   legal_preference_flip_effect=flip_effect, gates=gates,
                   estimated_peak_upper_usd=seal["estimated_total_upper_usd"] if partial else seal["estimated_peak_upper_usd"],
                   truth_sources=truth_sources,
                   note="Offline correct-choice counts are not IDF1/HOTA or a continuous tracking gain.")
    prefix = "PARTIAL_" if partial else ""
    (RUN / f"{prefix}EVENT_RESULTS.json").write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (RUN / f"{prefix}SUMMARY.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (RUN / f"{prefix}UNSCORABLE.json").write_text(json.dumps(unscorable, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(conclusion, "scorable", len(scorable), "temporal", correct_counts[main], "N", correct_counts["N"])


if __name__ == "__main__":
    main()
