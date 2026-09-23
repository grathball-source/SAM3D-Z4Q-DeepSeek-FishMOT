"""Independent post-seal relation audit; this is the only R0 process reading GT."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "r0_source"))
from scoring import association_relation_audit  # noqa: E402


def sha(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def rows(path):
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            yield json.loads(line)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--original", type=Path, required=True)
    ap.add_argument("--matches", type=Path, required=True)
    ap.add_argument("--trackeval", type=Path, required=True)
    args = ap.parse_args()
    assert json.loads((HERE / "REPLAY_AUDIT.json").read_text())["status"] == "PASS_ORIGINAL_REPLAY_NO_API_NO_GT"
    seal = json.loads((args.original / "PREDICTIONS_SEALED.json").read_text())
    assert sha(args.original / "predictions_validation.jsonl.gz") == seal["predictions_sha256"]
    assert sha(args.original / "transactions_validation.jsonl.gz") == seal["transactions_sha256"]
    assert sha(args.matches) == "5c557ab0dd833e00b4b0d3a6eeec3cdd6e0669f11da4f5e6611619fe5928cbd1"
    package = args.trackeval / "trackeval"
    assert package.is_dir()
    source_files = sorted(package.rglob("*.py"))
    assert source_files
    source_hashes = {str(path.relative_to(args.trackeval)).replace("\\", "/"): sha(path) for path in source_files}
    combined = hashlib.sha256(json.dumps(source_hashes, sort_keys=True).encode()).hexdigest()
    b0, b1, gt = {}, {}, {}
    for p, m in zip(rows(args.original / "predictions_validation.jsonl.gz"), rows(args.matches), strict=True):
        f = p["frame"]
        assert m["frame"] == f
        gt[f] = {int(x["native_id"]): x["gt_id"] for x in m["objects"] if x["gt_id"] is not None}
        for arm, output in (("B0", b0), ("B1", b1)):
            output[f] = {int(x["mask"].split(":")[1]): int(x["id"]) for x in p["variants"][arm]}
    assert len(gt) == len(b0) == len(b1) == 2888
    audit = association_relation_audit(b0, b1, gt)
    assert audit["scorable_by_gt"].get("4", 0) > 0 and audit["scorable_by_gt"].get("5", 0) > 0
    assert not audit["harms"] and not audit["improvements"]
    metrics = json.loads((args.original / "METRICS.json").read_text())
    assert metrics["metrics"]["B0"] == metrics["metrics"]["B1"]
    result = dict(status="PASS_POSTSEAL_RELATION_COVERAGE", prediction_sha256=seal["predictions_sha256"],
                  match_sha256=sha(args.matches), TrackEval_source_files=len(source_files),
                  TrackEval_source_tree_sha256=combined, TrackEval_key_hashes={k:v for k,v in source_hashes.items()
                                                  if k.endswith(("metrics/hota.py", "metrics/identity.py", "metrics/clear.py"))},
                  standard_TrackEval_metrics=metrics["metrics"],
                  relation_summary={k:v for k,v in audit.items() if k not in ("harms", "improvements", "unscorable")},
                  relation_harms=audit["harms"], relation_improvements=audit["improvements"],
                  unscorable_examples=audit["unscorable"][:20],
                  note="Identical sealed branches mean zero incremental harm, but GT4/GT5 are now included in the relation denominator.")
    target = HERE / "R0_SCORE_AUDIT.json"
    assert not target.exists(), target
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(result["status"], audit["scorable_pairs"], audit["scorable_by_gt"].get("4"), audit["scorable_by_gt"].get("5"))


if __name__ == "__main__":
    main()
