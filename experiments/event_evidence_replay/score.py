"""Score sealed B2 through the unchanged official B0/B1 TrackEval implementation.

The temporary B1 name is solely an adapter for the frozen scorer's arm key.
"""
from __future__ import annotations

import gzip
import importlib.util
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = Path(os.environ.get("Z4Q_SCORE_PATH", HERE.parents[1] / "online/closed_loop_2888/score.py"))


def sha(path):
    import hashlib
    with Path(path).open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def save(path, value):
    path = Path(path)
    assert not path.exists(), path
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def alias_gzip(source_path, target_path):
    with gzip.open(source_path, "rt", encoding="utf-8") as source, gzip.open(
            target_path, "wt", encoding="utf-8") as target:
        for line in source:
            item = json.loads(line)
            assert set(item["variants"]) == {"B0", "B2"}
            item["variants"]["B1"] = item["variants"].pop("B2")
            target.write(json.dumps(item, separators=(",", ":")) + "\n")


def main():
    public = HERE / "public"
    seal = json.loads((public / "PREDICTIONS_SEALED.json").read_text(encoding="utf-8"))
    assert seal["status"] == "SEALED_AWAITING_INDEPENDENT_SCORING" and seal["frames"] == 2888
    assert sha(public / "predictions_validation.jsonl.gz") == seal["predictions_sha256"]
    assert sha(public / "transactions_validation.jsonl.gz") == seal["transactions_sha256"]
    assert sha(public / "CALL_LEDGER.jsonl") == seal["call_ledger_sha256"]
    alias = HERE / "score_alias"
    alias.mkdir(exist_ok=False)
    for name in ("predictions_validation.jsonl.gz", "transactions_validation.jsonl.gz"):
        alias_gzip(public / name, alias / name)
    alias_seal = dict(seal, predictions_sha256=sha(alias / "predictions_validation.jsonl.gz"),
                      transactions_sha256=sha(alias / "transactions_validation.jsonl.gz"))
    save(alias / "PREDICTIONS_SEALED.json", alias_seal)
    (alias / "CALL_LEDGER.jsonl").write_bytes((public / "CALL_LEDGER.jsonl").read_bytes())
    spec = importlib.util.spec_from_file_location("frozen_z4q_score", SOURCE)
    scorer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scorer)
    scorer.HERE = alias
    scorer.full()
    result = json.loads((alias / "METRICS.json").read_text(encoding="utf-8"))
    assert set(result["metrics"]) == {"B0", "B1"}
    result["metrics"]["B2"] = result["metrics"].pop("B1")
    result["source_prediction_sha256"] = seal["predictions_sha256"]
    result["score_alias_prediction_sha256"] = alias_seal["predictions_sha256"]
    result["score_source_sha256"] = sha(SOURCE)
    result["arm_alias_contract"] = "B2 renamed B1 only in a postseal copy for unchanged official scorer"
    save(public / "METRICS.json", result)
    timeline = json.loads((alias / "FULL_TIMELINE_HARM_AUDIT.json").read_text(encoding="utf-8"))
    for group in ("harms", "improvements"):
        for item in timeline[group]:
            item["B2"] = item.pop("B1")
    save(public / "FULL_TIMELINE_HARM_AUDIT.json", timeline)
    save(public / "SCORE_ADAPTER.json", dict(
        source_prediction_sha256=seal["predictions_sha256"],
        alias_prediction_sha256=alias_seal["predictions_sha256"],
        source_transaction_sha256=seal["transactions_sha256"],
        alias_transaction_sha256=alias_seal["transactions_sha256"],
        scorer_sha256=sha(SOURCE), metrics_sha256=sha(public / "METRICS.json")))
    print(json.dumps(dict(status=result["status"], metrics=result["metrics"],
                          difference_frames=result["difference_frames"],
                          transactions=result["transaction_counts"])))


if __name__ == "__main__":
    main()
