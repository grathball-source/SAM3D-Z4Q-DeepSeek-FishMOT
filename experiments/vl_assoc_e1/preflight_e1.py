"""No-network E1 packet, media, transport, and pairing preflight."""
from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

from e1_protocol import (decode, model_off, numeric_baseline, pairs,
                         permute_aliases, validate_packet)

HERE = Path(__file__).resolve().parent
ARMS = ("L-T", "L-V-static", "L-V-temporal", "L-V-temporal-repeat",
        "L-V-temporal-permuted")


def sha(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def lines(path):
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]


def body(packet, image_path, config, prompt):
    content = [dict(type="text", text=json.dumps(packet, ensure_ascii=False,
                                                  separators=(",", ":"), allow_nan=False))]
    if image_path:
        encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
        content.append(dict(type="image_url", image_url=dict(url="data:image/png;base64," + encoded)))
    return dict(model=config["model"],
                messages=[dict(role="system", content=prompt), dict(role="user", content=content)],
                thinking=config["thinking"], reasoning_effort=config["reasoning_effort"],
                response_format=config["response_format"], max_tokens=config["max_tokens"])


def main():
    config, auth = read(HERE / "CONFIG.json"), read(HERE / "API_AUTHORIZATION.json")
    assert config["allow_api"] is False and auth["allow_api"] is False
    prompt = (HERE / "PROMPT.txt").read_text(encoding="utf-8")
    episodes = lines(HERE / "EPISODES_development.jsonl") + lines(HERE / "EPISODES_validation.jsonl")
    audits = lines(HERE / "CANDIDATE_AUDIT_development.jsonl") + lines(HERE / "CANDIDATE_AUDIT_validation.jsonl")
    assert len(episodes) == len(audits) == 24
    assert len({x["packet_id"] for x in episodes}) == 24
    assert {x["split"] for x in episodes} == {"development", "validation"}
    assert sum(x["split"] == "development" for x in episodes) == 12
    assert sum(x["split"] == "validation" for x in episodes) == 12
    audit_by_packet = {x["packet_id"]: x for x in audits}
    rows, call_plan, schedule, checks = [], [], [], []
    for episode in episodes:
        pid = episode["packet_id"]
        packet_path = HERE / "packets" / (pid + ".json")
        packet = read(packet_path)
        assert validate_packet(packet) and packet["split"] == episode["split"]
        assert packet["packet_id"] == pid and packet["episode_id"] == episode["episode_id"]
        assert all("feature_mask" not in s for n in packet["history"] + packet["current"] for s in n["samples"])
        assert packet["query_time"] == episode["query_time"]
        assert audit_by_packet[pid]["request_sha256"] == sha(packet_path)
        assert episode["candidate_count"] == len(packet["candidates"])
        assert episode["executable_nonbaseline"] >= 1
        assert not ({"gt_id", "native_to_gt", "ground_truth"} & set(packet))
        base = episode["baseline_candidate"]
        assert model_off(packet, base)["selected"] == base
        assert numeric_baseline(packet, base)["selected"] == episode["numeric"]["N"]["selected"]
        assert len(pairs(packet)) >= 1
        mapping_set = {tuple(sorted(c["full_mapping"].items())) for c in packet["candidates"]}
        assert len(mapping_set) == len(packet["candidates"])
        all_nodes = packet["history"] + packet["current"]
        assert all(s["source_time"] <= packet["query_time"] for n in all_nodes for s in n["samples"])
        for arm in ARMS:
            manifest_path = HERE / "request_manifest" / f"{pid}_{arm}.json"
            manifest = read(manifest_path)
            assert manifest["arm"] == arm and manifest["allow_api"] is False
            assert manifest["status"] == "FROZEN_INTENT_NOT_SENT"
            used_packet = HERE / "packets" / manifest["packet_file"]
            assert sha(used_packet) == manifest["packet_sha256"]
            actual_packet = read(used_packet)
            assert validate_packet(actual_packet)
            assert manifest["snapshot_version"] == packet["snapshot_version"]
            if arm.endswith("permuted"):
                perm, back = permute_aliases(packet)
                assert perm == actual_packet
                assert len(back) == len(packet["candidates"])
            else:
                assert used_packet == packet_path
            visual = manifest["image"]
            image_path = None
            if visual:
                image_path = HERE / "images" / visual["file"]
                assert sha(image_path) == visual["sha256"]
                assert image_path.stat().st_size == visual["bytes"]
                mode = "static" if arm == "L-V-static" else "temporal"
                qa = audit_by_packet[pid]["visuals"][mode]
                assert qa["sha256"] == visual["sha256"] and qa["bytes"] == visual["bytes"]
                expected = [s for n in all_nodes for s in (n["samples"][-1:] if mode == "static" else n["samples"])]
                assert len(qa["rows"]) == len(expected)
                for row, sample in zip(qa["rows"], expected, strict=True):
                    assert row["label"] == sample["label"]
                    assert row["global_frame"] == sample["global_frame"]
                    assert row["source_time"] == sample["source_time"] <= packet["query_time"]
                    assert row["native_mask_area"] >= 16
                    assert row["mask_size"] == [640, 360] and row["RGB_size"] == [1920, 1080]
            assert (arm == "L-T") == (image_path is None)
            request = body(actual_packet, image_path, config, prompt)
            wire = json.dumps(request, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
            assert len(wire) < 48 * 1024 * 1024
            text_tokens_upper = len(used_packet.read_bytes()) + len(prompt.encode("utf-8")) + 2048
            input_tokens_upper = text_tokens_upper + (1024 if image_path else 0)
            reserved = (input_tokens_upper * .30 + config["max_tokens"] * 1.20) / 1e6
            call_plan.append(dict(request=manifest_path.name, payload_sha256=hashlib.sha256(wire).hexdigest(),
                                  payload_bytes=len(wire), packet_sha256=sha(used_packet),
                                  image_sha256=sha(image_path) if image_path else None,
                                  input_tokens_upper=input_tokens_upper,
                                  reserved_peak_usd=reserved))
        assert read(HERE / "request_manifest" / f"{pid}_L-V-temporal.json")["image"] == \
               read(HERE / "request_manifest" / f"{pid}_L-V-temporal-repeat.json")["image"] == \
               read(HERE / "request_manifest" / f"{pid}_L-V-temporal-permuted.json")["image"]
        # Fixed per-event randomized order for the three primary model arms.
        order = sorted(ARMS[:3], key=lambda arm: hashlib.sha256((pid + ":" + arm + ":E1-order-v1").encode()).hexdigest())
        schedule.append(dict(packet_id=pid, main_order=order, diagnostics=list(ARMS[3:])))
        rows.append(dict(packet_id=pid, episode_id=episode["episode_id"], split=episode["split"],
                         query_frame=episode["query_frame"], query_time=episode["query_time"],
                         candidates=len(packet["candidates"]), B0=base,
                         N=episode["numeric"]["N"]["selected"],
                         D_only=episode["numeric"]["D_only"]["selected"],
                         A_only=episode["numeric"]["A_only"]["selected"],
                         M_only=episode["numeric"]["M_only"]["selected"],
                         L_T="PENDING_NO_AUTHORIZATION", L_V_static="PENDING_NO_AUTHORIZATION",
                         L_V_temporal="PENDING_NO_AUTHORIZATION",
                         repeat="PENDING_NO_AUTHORIZATION", permuted="PENDING_NO_AUTHORIZATION",
                         GT_scoring="NOT_OPENED_BEFORE_DECISION_SEAL"))
    assert len(call_plan) == 120
    assert sum(x["N"] != x["B0"] for x in rows) >= 1
    assert sum(x["candidates"] > 1 for x in rows) == 24
    assert all(x["payload_bytes"] < 48 * 1024 * 1024 for x in call_plan)
    formal = sum(x["reserved_peak_usd"] for x in call_plan)
    smoke = 2 * max(x["reserved_peak_usd"] for x in call_plan)
    assert formal + smoke < config["max_estimated_usd"]
    checks += ["24_causal_packets", "candidate_complete_unique", "same_cutoff_all_arms",
               "real_image_content_blocks", "visual_row_legend_alignment", "image_byte_hashes",
               "repeat_identical", "alias_permutation_only", "model_off_B0", "numeric_N_active",
               "fixed_arm_order", "no_GT_in_packets", "budget_and_body_limit", "zero_network_calls"]
    def combined(pattern):
        return "".join((HERE / pattern.format(split)).read_text(encoding="utf-8")
                       for split in ("development", "validation"))
    (HERE / "EPISODES.jsonl").write_text(combined("EPISODES_{}.jsonl"), encoding="utf-8")
    (HERE / "CANDIDATE_AUDIT.jsonl").write_text(combined("CANDIDATE_AUDIT_{}.jsonl"), encoding="utf-8")
    (HERE / "CALL_SCHEDULE.json").write_text(json.dumps(schedule, indent=2) + "\n", encoding="utf-8")
    cost = dict(status="PRECALL_BUDGET_PASS_NO_AUTHORIZATION", model=config["model"],
                official_vision_url="https://api-docs.deepseek.com/guides/vision/",
                official_pricing_url="https://api-docs.deepseek.com/quick_start/pricing/",
                assumptions=dict(peak_uncached_input_USD_per_million=.30,
                                 peak_output_USD_per_million=1.20, image_tokens_upper_per_image=1024,
                                 text_token_upper="one UTF-8 byte per token plus 2048 overhead",
                                 max_output_tokens=config["max_tokens"]),
                formal_calls=len(call_plan), smoke_calls_max=2, total_calls_max=122,
                formal_peak_worst_usd=formal, smoke_peak_worst_usd=smoke,
                combined_peak_worst_usd=formal+smoke,
                authorization_cap_usd=config["max_estimated_usd"], within_cap=True,
                actual_calls=0, actual_cost_usd=0, actual_latency_seconds=None,
                requests=call_plan)
    (HERE / "COST_PLAN_FINAL.json").write_text(json.dumps(cost, indent=2) + "\n", encoding="utf-8")
    (HERE / "EVENT_RESULTS.json").write_text(json.dumps(dict(status="NOT_SCORED_NO_MODEL_DECISIONS",
                                                rows=rows), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    freeze_paths = [HERE / x for x in ("CONFIG.json", "PROMPT.txt", "API_AUTHORIZATION.json",
                                      "EPISODE_PROTOCOL.md", "PROTOCOL_DIFF.md", "e1_protocol.py",
                                      "event_probe.py", "build_packets.py", "preflight_e1.py",
                                      "sanitize_packets.py", "ASSET_INVENTORY.json",
                                      "EVENT_PROBE_V4_development.json", "EVENT_PROBE_V4_validation.json",
                                      "EPISODES.jsonl", "CANDIDATE_AUDIT.jsonl",
                                      "SANITIZATION_AUDIT.json", "PERMUTATION_MAPS.json",
                                      "CALL_SCHEDULE.json", "COST_PLAN_FINAL.json")]
    freeze_paths += sorted((HERE / "packets").glob("*.json"))
    freeze_paths += sorted((HERE / "request_manifest").glob("*.json"))
    freeze_paths += sorted((HERE / "images").glob("*.png"))
    hashes = {str(p.relative_to(HERE)).replace("\\", "/"): sha(p) for p in freeze_paths}
    freeze = dict(status="READY_FOR_E1_API", base_commit=config["base_commit"],
                  allow_api=False, model_calls=0, input_files=len(hashes), file_sha256=hashes,
                  checks=checks, note="No GT was read for E1; image files remain server-private.")
    (HERE / "FREEZE.json").write_text(json.dumps(freeze, indent=2) + "\n", encoding="utf-8")
    (HERE / "E1_PREFLIGHT.json").write_text(json.dumps(dict(status="READY_FOR_E1_API",
                                                  checks=checks, packets=24, manifests=120,
                                                  images=48, numeric_changed=sum(x["N"] != x["B0"] for x in rows),
                                                  API_calls=0), indent=2) + "\n", encoding="utf-8")
    print("READY_FOR_E1_API", len(rows), len(call_plan), round(formal+smoke, 4))


if __name__ == "__main__":
    main()
