"""Read-only re-audit of sealed E1 responses; never invokes a provider or GT."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

E1 = Path(__file__).resolve().parents[1] / "vl_assoc_e1"
sys.path.insert(0, str(E1))
from e1_protocol import decode, validate_response  # noqa: E402


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(run: Path, private: Path | None) -> dict:
    seal = json.loads((run / "DECISIONS_SEALED.json").read_text())
    decisions = {x["id"]: x for x in map(json.loads, (run / "DECISIONS.jsonl").read_text().splitlines())}
    assert len(decisions) == 120 and len(seal["response_sha256"]) == 122
    assert sha(run / "DECISIONS.jsonl") == seal["decisions_sha256"]
    assert sha(run / "CALL_LEDGER.jsonl") == seal["ledger_sha256"]
    episodes = {x["packet_id"]: x for x in map(json.loads, (E1 / "EPISODES.jsonl").read_text().splitlines())}
    rows = []
    for ident, decision in sorted(decisions.items()):
        response_path = run / "responses" / f"{ident}.json"
        assert sha(response_path) == seal["response_sha256"][response_path.name]
        response = json.loads(response_path.read_text())
        original_id = decision["packet_id"]
        permuted = decision["arm"].endswith("permuted")
        packet = json.loads((E1 / "packets" / f'{original_id}{"_perm" if permuted else ""}.json').read_text())
        baseline = episodes[original_id]["baseline_candidate"]
        if permuted:
            maps = json.loads((E1 / "PERMUTATION_MAPS.json").read_text())
            # The archived decision already expresses its selected choice in original aliases.
            baseline = next(k for k, v in maps[original_id].items() if v == baseline)
        try:
            content = json.loads(response["content"])
        except (ValueError, TypeError):
            content = None
        format_valid, format_reason = validate_response(packet, content)
        transport_valid = response["finish_reason"] == "stop"
        strict_valid = transport_valid and format_valid
        decoded = decode(packet, content, baseline) if strict_valid else {"status": "INVALID", "selected": baseline}
        semantic_flags = []
        if isinstance(content, dict) and isinstance(content.get("comparisons"), list):
            declared = content.get("applicability", {})
            modality = {"DEPTH": "depth", "APPEARANCE": "appearance", "MOTION": "motion"}
            for item in content["comparisons"]:
                if not isinstance(item, dict):
                    continue
                used = modality.get(item.get("reason_code"))
                if used and declared.get(used) != "APPLICABLE" and item.get("relation") in ("LEFT_BETTER", "RIGHT_BETTER"):
                    semantic_flags.append("DIRECTION_FROM_DECLARED_NONAPPLICABLE_" + used)
        private_verified = None
        if private is not None:
            request = json.loads((run / "requests" / f"{ident}.json").read_text())
            private_verified = (sha(private / "requests" / f"{ident}.json") == request["payload_sha256"]
                                and sha(private / "responses" / f"{ident}.json") == response["private_raw_response_sha256"])
            assert private_verified, ident
        rows.append(dict(id=ident, packet_id=decision["packet_id"], arm=decision["arm"],
                         finish_reason=response["finish_reason"], strict_valid=strict_valid,
                         format_reason=format_reason, policy_status=decision["status"],
                         policy_consistent=(decision["response_valid"] == strict_valid and
                                            decision["status"] == decoded["status"]),
                         semantic_flags=sorted(set(semantic_flags)), private_hash_bound=private_verified))
    assert all(x["policy_consistent"] for x in rows), [x for x in rows if not x["policy_consistent"]]
    return dict(base_commit="12c6dcf60df86deedc71c719b867d56e8ab53838", formal=120,
                strict_valid=sum(x["strict_valid"] for x in rows), invalid_reasons=dict(Counter(
                    x["format_reason"] for x in rows if not x["strict_valid"])),
                policy_consistent=sum(x["policy_consistent"] for x in rows),
                semantic_flags=dict(Counter(flag for x in rows for flag in x["semantic_flags"])),
                private_bound=sum(x["private_hash_bound"] is True for x in rows),
                note="Semantic flags are mechanical contradictions only; other valid answers are not validated as true associations.",
                rows=rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, default=E1 / "api_rerun_20260923_default64k")
    parser.add_argument("--private", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.run, args.private)
    assert not args.output.exists()
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "rows"}))


if __name__ == "__main__":
    main()
