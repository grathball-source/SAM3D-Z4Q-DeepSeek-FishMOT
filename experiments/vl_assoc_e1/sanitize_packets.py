"""One-time prefreeze removal of native mask keys from model-visible packets."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from e1_protocol import permute_aliases, validate_packet

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    changed = {}
    for path in sorted((HERE / "packets").glob("P*.json")):
        if path.stem.endswith("_perm"):
            continue
        packet = json.loads(path.read_text(encoding="utf-8"))
        old = sha(path)
        count = 0
        for node in packet["history"] + packet["current"]:
            for sample in node["samples"]:
                assert sample.pop("feature_mask", None) is not None
                count += 1
        assert count > 0 and validate_packet(packet)
        write(path, packet)
        permuted, _ = permute_aliases(packet)
        perm_path = path.with_name(permuted["packet_id"] + ".json")
        assert perm_path.exists()
        write(perm_path, permuted)
        for manifest_path in (HERE / "request_manifest").glob(path.stem + "_*.json"):
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            assert manifest["packet_sha256"] in (old, sha(perm_path)) or manifest["packet_file"] == perm_path.name
            used = HERE / "packets" / manifest["packet_file"]
            manifest["packet_sha256"] = sha(used)
            write(manifest_path, manifest)
        changed[path.stem] = dict(removed_native_keys=count, packet_sha256=sha(path))
    assert len(changed) == 24
    for split in ("development", "validation"):
        path = HERE / f"CANDIDATE_AUDIT_{split}.jsonl"
        rows = [json.loads(s) for s in path.read_text(encoding="utf-8").splitlines()]
        for row in rows:
            row["request_sha256"] = changed[row["packet_id"]]["packet_sha256"]
        path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    target = HERE / "SANITIZATION_AUDIT.json"
    assert not target.exists()
    write(target, dict(status="PREFREEZE_NATIVE_ID_REMOVED", packets=len(changed), details=changed,
                       note="Visual pixels and causal rows unchanged; private candidate audit retains provenance."))
    print("PREFREEZE_NATIVE_ID_REMOVED", len(changed))


if __name__ == "__main__":
    main()
