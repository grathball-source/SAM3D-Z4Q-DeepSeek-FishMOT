"""Finish the frozen alias-permuted request and conservative no-call budget."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from e1_protocol import permute_aliases

HERE = Path(__file__).resolve().parent


def sha(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def main():
    maps = {}
    for packet_path in sorted((HERE / "packets").glob("P*.json")):
        if packet_path.stem.endswith("_perm"):
            continue
        packet = json.loads(packet_path.read_text(encoding="utf-8"))
        permuted, back = permute_aliases(packet)
        target = packet_path.with_name(permuted["packet_id"] + ".json")
        assert not target.exists(), target
        target.write_text(json.dumps(permuted, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        maps[packet["packet_id"]] = back
        manifest_path = HERE / "request_manifest" / f"{packet['packet_id']}_L-V-temporal-permuted.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest["allow_api"] is False and manifest["status"] == "FROZEN_INTENT_NOT_SENT"
        assert manifest["packet_sha256"] == sha(packet_path)
        manifest.update(packet_file=target.name, packet_sha256=sha(target))
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    map_path = HERE / "PERMUTATION_MAPS.json"
    assert not map_path.exists(), map_path
    map_path.write_text(json.dumps(maps, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifests = sorted((HERE / "request_manifest").glob("*.json"))
    assert len(manifests) == 120
    calls = []
    prompt_path = HERE / "PROMPT.txt"
    prompt_length = len(prompt_path.read_text(encoding="utf-8"))
    image_requests = 0
    for path in manifests:
        manifest = json.loads(path.read_text(encoding="utf-8"))
        assert manifest["allow_api"] is False
        packet_path = HERE / "packets" / manifest["packet_file"]
        assert sha(packet_path) == manifest["packet_sha256"]
        image = manifest["image"]
        if image:
            visual_path = HERE / "images" / image["file"]
            assert sha(visual_path) == image["sha256"] and visual_path.stat().st_size == image["bytes"]
            image_requests += 1
        # One UTF-8 character per token is intentionally conservative for text.
        text_tokens_upper = len(packet_path.read_text(encoding="utf-8")) + prompt_length + 2048
        image_tokens_upper = 1024 if image else 0  # Official per-image upper bound.
        input_tokens_upper = text_tokens_upper + image_tokens_upper
        reserved_usd = (input_tokens_upper * .30 + 8192 * 1.20) / 1e6
        calls.append(dict(request=path.name, input_tokens_upper=input_tokens_upper,
                          image_tokens_upper=image_tokens_upper, max_output_tokens=8192,
                          reserved_peak_usd=reserved_usd))
    total = sum(x["reserved_peak_usd"] for x in calls)
    smoke_reserve = 2 * max(x["reserved_peak_usd"] for x in calls)
    plan = dict(status="PRECALL_BUDGET_PASS_NO_AUTHORIZATION", model="deepseek-flash",
                official_vision_url="https://api-docs.deepseek.com/guides/vision/",
                official_pricing_url="https://api-docs.deepseek.com/quick_start/pricing/",
                assumptions=dict(peak_uncached_input_USD_per_million=.30,
                                 peak_output_USD_per_million=1.20,
                                 image_tokens_upper_per_image=1024,
                                 text_token_upper="one UTF-8 character per token plus 2048 overhead",
                                 max_output_tokens=8192),
                formal_calls=len(calls), image_requests=image_requests,
                smoke_calls_max=2, total_calls_max=122,
                formal_peak_worst_usd=total, smoke_peak_worst_usd=smoke_reserve,
                combined_peak_worst_usd=total + smoke_reserve,
                authorization_cap_usd=5.0, within_cap=total + smoke_reserve <= 5.,
                requests=calls)
    target = HERE / "COST_PLAN.json"
    assert not target.exists(), target
    target.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    assert plan["within_cap"]
    print("FROZEN_REQUESTS_NO_API", len(calls), "peak_worst_usd", round(total+smoke_reserve, 4))


if __name__ == "__main__":
    main()
