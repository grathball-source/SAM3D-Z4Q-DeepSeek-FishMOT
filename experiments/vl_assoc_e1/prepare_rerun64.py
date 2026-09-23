"""Freeze all 120 E1 rerun request hashes without sending or reading GT."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from preflight_e1 import body, read, sha

HERE = Path(__file__).resolve().parent
RUN = HERE / "api_rerun_20260923_default64k"
DEFAULT_OUTPUT = 65536
PRICE_INPUT = .30
PRICE_OUTPUT = 1.20


def encoded(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")


def save(name, value):
    (RUN / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    assert not RUN.exists(), "rerun directory already exists; never overwrite"
    config = read(HERE / "CONFIG.json")
    old = read(HERE / "COST_PLAN_FINAL.json")
    freeze = read(HERE / "FREEZE.json")
    assert config["allow_api"] is False and config["max_tokens"] == 8192
    assert freeze["status"] == "READY_FOR_E1_API" and freeze["model_calls"] == 0
    assert len(freeze["file_sha256"]) == 235
    for name, expected in freeze["file_sha256"].items():
        assert sha(HERE / name) == expected, name
    prompt = (HERE / "PROMPT.txt").read_text(encoding="utf-8")
    requests = []
    for old_row in old["requests"]:
        manifest = read(HERE / "request_manifest" / old_row["request"])
        packet_path = HERE / "packets" / manifest["packet_file"]
        assert sha(packet_path) == manifest["packet_sha256"]
        image_info = manifest["image"]
        image = HERE / "images" / image_info["file"] if image_info else None
        if image:
            assert sha(image) == image_info["sha256"]
        payload = body(read(packet_path), image, config, prompt)
        assert payload.pop("max_tokens") == 8192
        wire = encoded(payload)
        reserve = (old_row["input_tokens_upper"] * PRICE_INPUT + DEFAULT_OUTPUT * PRICE_OUTPUT) / 1e6
        requests.append(dict(request=old_row["request"], payload_sha256=hashlib.sha256(wire).hexdigest(),
                             payload_bytes=len(wire), image_sha256=old_row["image_sha256"],
                             input_tokens_upper=old_row["input_tokens_upper"], reserved_peak_usd=reserve))
    assert len(requests) == 120 and len({x["request"] for x in requests}) == 120
    formal = sum(x["reserved_peak_usd"] for x in requests)
    smoke = old["smoke_peak_worst_usd"] + 2 * (DEFAULT_OUTPUT - 8192) * PRICE_OUTPUT / 1e6
    total = formal + smoke
    assert total < 20., (formal, smoke, total)
    RUN.mkdir()
    plan = dict(status="PRECALL_BUDGET_PASS_NEW_AUTHORIZATION_REQUIRED", model=config["model"],
                formal_calls=120, smoke_calls_max=2, total_calls_max=122,
                assumptions=dict(max_tokens_field="OMITTED",
                                 provider_default_thinking_output_tokens=DEFAULT_OUTPUT,
                                 peak_uncached_input_USD_per_million=PRICE_INPUT,
                                 peak_output_USD_per_million=PRICE_OUTPUT,
                                 input_tokens_upper="unchanged frozen one-byte-per-token plus image upper bound"),
                formal_peak_worst_usd=formal, smoke_peak_worst_usd=smoke,
                combined_peak_worst_usd=total, authorized_cap_usd=20., requests=requests)
    save("COST_PLAN.json", plan)
    save("REQUEST_FREEZE.json", dict(status="RERUN_REQUESTS_FROZEN_BEFORE_API",
                                     old_freeze_sha256=sha(HERE / "FREEZE.json"),
                                     cost_plan_sha256=sha(RUN / "COST_PLAN.json"),
                                     executor_sha256=sha(HERE / "e1_execute.py"),
                                     runner_sha256=sha(HERE / "run_phase.sh"),
                                     note="Original 24 events and call schedule; no old responses reused; max_tokens omitted."))
    print("PASS_RERUN_REQUEST_FREEZE_NO_API", len(requests), round(total, 6))


if __name__ == "__main__":
    main()
