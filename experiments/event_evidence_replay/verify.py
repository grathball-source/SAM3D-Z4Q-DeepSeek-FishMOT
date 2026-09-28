"""Postseal chain, metrics, parity and restricted-artifact verification."""
from __future__ import annotations

import gzip
import json
from pathlib import Path

import replay as run

HERE = Path(__file__).resolve().parent
PUBLIC = HERE / "public"
OLD = run.old


def lines(path):
    return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines()]


def gzrows(path):
    with gzip.open(path, "rt", encoding="utf-8") as source:
        yield from map(json.loads, source)


def save_or_check(path, value):
    if Path(path).exists():
        assert OLD.read(path) == value, path
    else:
        OLD.store(path, value)


def main():
    config = OLD.read(HERE / "CONFIG.json")
    freeze, seal, score, physical = (OLD.read(PUBLIC / name) for name in
        ("FREEZE.json", "PREDICTIONS_SEALED.json", "METRICS.json", "PHYSICAL_REFERENCE_AUDIT.json"))
    assert freeze["review_base"] == config["review_base"]
    assert freeze["status"] == "FROZEN_BEFORE_FIRST_INFERENCE"
    assert all(OLD.sha(HERE / name) == expected for name, expected in freeze["code_sha256"].items())
    assert all(OLD.sha(path) == expected for path, expected in freeze["source_sha256"].items())
    assert OLD.sha(OLD.OLD / "public/REQUESTS_LOGICAL.json") == freeze["source_logical_sha256"]
    assert freeze["max_http"] == config["max_inference_http"] == 4
    assert freeze["total_reserve_peak_usd"] < freeze["max_usd"] == 4
    assert seal["status"] == "SEALED_AWAITING_INDEPENDENT_SCORING"
    assert seal["frames"] == 2888 and seal["HTTP_attempts"] == 4
    assert seal["peak_no_cache_upper_usd"] < 4
    assert OLD.sha(PUBLIC / "predictions_validation.jsonl.gz") == seal["predictions_sha256"]
    assert OLD.sha(PUBLIC / "transactions_validation.jsonl.gz") == seal["transactions_sha256"]
    assert OLD.sha(PUBLIC / "CALL_LEDGER.jsonl") == seal["call_ledger_sha256"]
    adapter = OLD.read(PUBLIC / "SCORE_ADAPTER.json")
    assert score["source_prediction_sha256"] == seal["predictions_sha256"]
    assert adapter["metrics_sha256"] == OLD.sha(PUBLIC / "METRICS.json")
    assert adapter["scorer_sha256"] == score["score_source_sha256"] == OLD.sha(
        OLD.Z4Q / "score.py")
    assert physical["source_prediction_sha256"] == seal["predictions_sha256"]
    provenance = OLD.read(PUBLIC / "SCORE_PROVENANCE.json")
    assert provenance["metrics_sha256"] == OLD.sha(PUBLIC / "METRICS.json")
    assert provenance["physical_reference_audit_sha256"] == OLD.sha(
        PUBLIC / "PHYSICAL_REFERENCE_AUDIT.json")
    visuals = OLD.read(PUBLIC / "VISUAL_MANIFEST.json")
    assert len(visuals) == 8
    assert all(OLD.sha(HERE / image["path"]) == image["sha256"] and
               (HERE / image["path"]).stat().st_size == image["bytes"]
               for image in visuals)
    ledger = lines(PUBLIC / "CALL_LEDGER.jsonl")
    schedule = [x["case"] for x in freeze["schedule"]]
    assert [(x["phase"], x["case"]) for x in ledger] == [pair for case in schedule
        for pair in (("START", case), ("END", case))]
    uploads = lines(HERE / "private_api/UPLOAD_LEDGER.jsonl")
    assert [(x["phase"], x["case"]) for x in uploads] == [pair for case in schedule
        for pair in (("START", case), ("END", case))]
    ids = OLD.file_ids() | {x["sha256"]: x["file_id"] for x in uploads if x["phase"] == "END"}
    responses = []
    for case, (start, end) in zip(schedule, zip(ledger[::2], ledger[1::2], strict=True), strict=True):
        packet = OLD.read(PUBLIC / "requests" / f"{case}.json")
        assert packet["q_frame"] == next(x["q"] for x in freeze["schedule"] if x["case"] == case)
        overview = packet["IMAGE_INDEX"][-1]
        assert OLD.sha(PUBLIC / "overviews" / f"{case}.png") == overview["sha256"] == freeze["overview_sha256"][case]
        assert overview["bytes"] == (PUBLIC / "overviews" / f"{case}.png").stat().st_size
        source_packet = dict(packet, IMAGE_INDEX=packet["IMAGE_INDEX"][:-1])
        assert OLD.digest(OLD.wire(source_packet)) == freeze["compiled_source_packet_sha256"][case]
        assert all(x["frame"] <= packet["q_frame"] for x in packet["IMAGE_INDEX"])
        binding = OLD.read(PUBLIC / "request_bindings" / f"{case}.json")
        body_path = HERE / "private_api" / f"{case}.body.json"
        body = OLD.read(body_path)
        assert body["model"] == "deepseek-flash"
        assert body["messages"][1]["content"][0]["text"] == OLD.wire(packet).decode()
        assert [x["file_id"] for x in body["messages"][1]["content"][1:]] == [
            ids[x["sha256"]] for x in packet["IMAGE_INDEX"]]
        assert OLD.sha(body_path) == OLD.digest(OLD.wire(body) + b"\n")
        assert OLD.digest(OLD.wire(body)) == binding["body_sha256"] == start["body_sha256"]
        assert OLD.digest(OLD.wire(packet)) == binding["packet_sha256"]
        assert binding["media_sha256"] == [x["sha256"] for x in packet["IMAGE_INDEX"]]
        assert binding["reserve_peak_usd"] == start["reserve_peak_usd"] == freeze["reserve_peak_usd"][case]
        response_path = PUBLIC / "responses" / f"{case}.json"
        result = OLD.read(response_path)
        assert OLD.sha(response_path) == end["response_sha256"]
        assert result["raw_private_sha256"] == OLD.sha(HERE / "private_api" / f"{case}.raw.json")
        assert result["choice"] in ("H1", "H2", "DEFER") and result["parse_status"] == "VALID"
        assert result["returned_model"] == "deepseek-flash"
        assert result["charge_peak_upper_usd"] == end["charge_peak_upper_usd"]
        responses.append(result)
    assert abs(sum(x["charge_peak_upper_usd"] for x in responses) -
               seal["peak_no_cache_upper_usd"]) < 1e-9
    events = OLD.read(PUBLIC / "EVENTS.json")
    assert [(x["case"], x["frame"]) for x in events] == [(x["case"], x["q"]) for x in freeze["schedule"]]
    assert [x["choice"] for x in events] == [x["choice"] for x in responses]
    assert sum(x["status"] == "COMMIT" for x in events) == 1
    assert [x["frame"] for x in events if x["status"] == "COMMIT"] == [2638]
    assert physical["committed_reference_counts"] == {"CORRECT": 0, "WRONG": 1, "UNSCORABLE": 0}
    count, different = 0, []
    for row, archived in zip(gzrows(PUBLIC / "predictions_validation.jsonl.gz"),
                             OLD.rows(OLD.ARCHIVED), strict=True):
        count += 1
        assert row["frame"] == count
        b0, b2 = row["variants"]["B0"], row["variants"]["B2"]
        assert b0 == archived["variants"]["Z4Q_STABLE"]
        assert [x["mask"] for x in b0] == [x["mask"] for x in b2]
        assert len({x["id"] for x in b2}) == len(b2)
        if b0 != b2:
            different.append(count)
    assert count == 2888 and different == list(range(2638, 2889))
    assert score["difference_frames"] == len(different) == 251
    original = OLD.read(HERE.parent / "direct_history_replay/public/METRICS.json")["metrics"]
    for name, value in score["metrics"]["B0"].items():
        assert abs(value - original["B0"][name]) < 1e-8
    assert score["metrics"]["B2"]["FP"] == score["metrics"]["B0"]["FP"]
    assert score["metrics"]["B2"]["FN"] == score["metrics"]["B0"]["FN"]
    for forbidden in (b"file-api-", b"Bearer ", b"DEEPSEEK_API_KEY"):
        assert all(forbidden not in path.read_bytes() for path in PUBLIC.rglob("*") if path.is_file())
    summary = dict(status="COMPLETE_EXPOSED_METRIC_GAIN_WITH_WRONG_EVENT_REFERENCE_COMMIT",
                   review_base=config["review_base"], frames=count, HTTP_attempts=4,
                   choices={x["case"]: x["choice"] for x in events},
                   statuses={x["case"]: x["status"] for x in events},
                   committed=1, committed_physical_reference_correct=0,
                   committed_physical_reference_wrong=1, changed_frames=len(different),
                   metrics=dict(B0=score["metrics"]["B0"],
                                archived_B1=original["B1"], B2=score["metrics"]["B2"]),
                   delta_B2_minus_B0={k: score["metrics"]["B2"][k] - score["metrics"]["B0"][k]
                                      for k in ("IDF1", "HOTA", "AssA", "IDSW", "FP", "FN")},
                   peak_usage_based_usd=seal["peak_no_cache_upper_usd"],
                   provider_invoice="UNAVAILABLE")
    save_or_check(PUBLIC / "SUMMARY.json", summary)
    restricted = sorted(set(
        [p for p in (HERE / "private_api").rglob("*") if p.is_file()] +
        [p for p in (HERE / "preflight_output_v7/private").rglob("*") if p.is_file()] +
        [OLD.OBS, OLD.PROFILES, OLD.ARCHIVED,
         OLD.OLD / "send/UPLOAD_LEDGER.jsonl"] +
        [OLD.OLD / "private/media" / name for name in {
            x["media_file"] for case in schedule
            for x in OLD.read(PUBLIC / "requests" / f"{case}.json")["IMAGE_INDEX"][:-1]}]),
        key=lambda p: str(p))
    inventory = [dict(path=str(p.resolve()), bytes=p.stat().st_size, sha256=OLD.sha(p))
                 for p in restricted]
    save_or_check(PUBLIC / "RESTRICTED_INVENTORY.json", dict(
        status="LOCAL_RESTRICTED_NO_GIT", count=len(inventory),
        total_bytes=sum(x["bytes"] for x in inventory), files=inventory,
        reproduction="Use frozen old H-D images/metadata, actual local observations/depth streams, B2 compiler, private Files upload IDs and one new authorization; official TrackEval and exposed validation GT are read postseal on the lab host."))
    save_or_check(PUBLIC / "ACCEPTANCE.json", dict(status="VERIFIED_METRIC_GAIN_WRONG_CAUSAL_ASSOCIATION",
        checks=["CODE_SOURCE_AND_PRICE_FREEZE", "FOUR_START_END_BODY_RESPONSE_CHAINS",
                "PREDICTION_SEAL_BEFORE_SCORE", "B0_EXACT_2888_AND_MASK_PARITY",
                "REAL_STAGE_AND_NEXT_FRAME_STATE", "OFFICIAL_TRACKEVAL",
                "FROZEN_REFERENCE_GT_POSTSEAL", "NO_PUBLIC_SECRETS_OR_PRIVATE_PIXELS"],
        predictions_sha256=seal["predictions_sha256"], metrics_sha256=OLD.sha(PUBLIC / "METRICS.json"),
        physical_audit_sha256=OLD.sha(PUBLIC / "PHYSICAL_REFERENCE_AUDIT.json")))
    print(json.dumps(dict(status=summary["status"], delta=summary["delta_B2_minus_B0"],
                          restricted=len(inventory))))


if __name__ == "__main__":
    main()
