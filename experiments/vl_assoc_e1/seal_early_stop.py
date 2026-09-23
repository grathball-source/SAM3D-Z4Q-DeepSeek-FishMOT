"""Seal a stopped E1 run before any independent GT scoring."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from preflight_e1 import read, sha

HERE = Path(__file__).resolve().parent
RUN = HERE / "api_run_20260923"


def rows(path):
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]


def main():
    assert (RUN / "formal_exit_code.txt").read_text().strip() == "143"
    assert not (RUN / "DECISIONS_SEALED.json").exists()
    assert not (RUN / "EARLY_STOP_SEALED.json").exists()
    auth = read(RUN / "RUN_AUTHORIZATION.json")
    assert sha(HERE / "FREEZE.json") == auth["frozen_freeze_sha256"]
    ledger = rows(RUN / "CALL_LEDGER.jsonl")
    decisions = rows(RUN / "DECISIONS.jsonl")
    starts = {x["id"]: x for x in ledger if x["phase"] == "start"}
    completes = {x["id"]: x for x in ledger if x["phase"] == "complete"}
    assert len(starts) == 37 and len(completes) == 36
    assert set(starts) - set(completes) == {"F000035"}
    assert len(decisions) == 34 and [x["id"] for x in decisions] == [f"F{x:06d}" for x in range(1, 35)]
    assert all(x["id"] in completes for x in decisions)
    invalid = [x["id"] for x in decisions if not x["response_valid"]]
    assert len(invalid) == 7 and 120 - len(invalid) < 114
    assert all(x["response_valid"] == completes[x["id"]]["valid"] for x in decisions)
    plan = {x["request"]: x for x in read(HERE / "COST_PLAN_FINAL.json")["requests"]}
    response_hashes = {}
    for ident, start in starts.items():
        public = read(RUN / "requests" / f"{ident}.json")
        private_path = RUN / "private_api" / "requests" / f"{ident}.json"
        assert sha(private_path) == public["payload_sha256"] == start["payload_sha256"]
        assert private_path.stat().st_size == public["payload_bytes"]
        if ident.startswith("F"):
            frozen = plan[public["arm"]]
            assert public["payload_sha256"] == frozen["payload_sha256"]
            assert public["image_sha256"] == frozen["image_sha256"]
        if ident not in completes:
            assert not (RUN / "responses" / f"{ident}.json").exists()
            continue
        response_path = RUN / "responses" / f"{ident}.json"
        response = read(response_path)
        assert sha(RUN / "private_api" / "responses" / f"{ident}.json") == \
               response["private_raw_response_sha256"] == completes[ident]["private_raw_response_sha256"]
        assert sha(response_path) == completes[ident]["public_response_sha256"]
        response_hashes[response_path.name] = sha(response_path)
    assert len(response_hashes) == 36
    complete_upper = sum(x["charged_upper_usd"] for x in completes.values())
    pending_upper = starts["F000035"]["reserve_upper_usd"]
    seal = dict(status="STOP_VALIDITY_GATE_UNATTAINABLE_SEALED_BEFORE_GT",
                formal_calls_completed=34, formal_calls_started=35,
                technical_smoke_calls=2, invalid_formal=7,
                valid_rate_ceiling_if_all_remaining_valid=113 / 120,
                unresolved_request="F000035", unresolved_outcome="UNKNOWN_CHARGE_RESERVED",
                estimated_completed_upper_usd=complete_upper,
                estimated_total_upper_usd=complete_upper + pending_upper,
                E1_GT_read=False, freeze_sha256=sha(HERE / "FREEZE.json"),
                authorization_sha256=sha(RUN / "RUN_AUTHORIZATION.json"),
                ledger_sha256=sha(RUN / "CALL_LEDGER.jsonl"),
                decisions_sha256=sha(RUN / "DECISIONS.jsonl"),
                response_sha256=response_hashes,
                sealed_at_utc=datetime.now(timezone.utc).isoformat())
    with (RUN / "EARLY_STOP_SEALED.json").open("x", encoding="utf-8") as handle:
        json.dump(seal, handle, indent=2)
        handle.write("\n")
    print("SEALED_EARLY_STOP_NO_GT", len(decisions), len(invalid), round(complete_upper + pending_upper, 6))


if __name__ == "__main__":
    main()
