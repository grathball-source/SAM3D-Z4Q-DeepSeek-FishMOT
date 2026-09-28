"""Postseal physical-reference audit; never used to select or gate an action."""
from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PUBLIC = HERE / "public"
MATCHES = Path("/home/xiongxiong/dmot-experiments/sam3_depth_return_guard_20260918/experiment/offline_matches_validation.jsonl.gz")
MATCHES_SHA = "5c557ab0dd833e00b4b0d3a6eeec3cdd6e0669f11da4f5e6611619fe5928cbd1"


def sha(path):
    with Path(path).open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main():
    seal = read(PUBLIC / "PREDICTIONS_SEALED.json")
    metrics = read(PUBLIC / "METRICS.json")
    assert seal["status"] == "SEALED_AWAITING_INDEPENDENT_SCORING"
    assert metrics["source_prediction_sha256"] == seal["predictions_sha256"]
    assert sha(MATCHES) == MATCHES_SHA
    events = read(PUBLIC / "EVENTS.json")
    matches = {x["frame"]: x["native_to_gt"] for x in
               map(json.loads, gzip.open(MATCHES, "rt", encoding="utf-8"))}
    assert len(matches) == 2888
    results = []
    for event in events:
        case, q = event["case"], event["frame"]
        request = read(PUBLIC / "requests" / f"{case}.json")
        assert request["q_frame"] == q
        ref_gt = {role: matches[value["anchor_frame"]].get(str(value["native"]))
                  for role, value in event["references"].items()}
        q_gt = {role: matches[q].get(str(event["q_native"][role])) for role in "XY"}
        hypotheses = {}
        for hypothesis in request["hypotheses"]:
            mapping = {role: hypothesis["mapping"][role] for role in "XY"}
            edges = {role: dict(reference_role=mapping[role],
                                reference_gt=ref_gt[mapping[role]], current_gt=q_gt[role],
                                correct=(None if ref_gt[mapping[role]] is None or q_gt[role] is None
                                         else ref_gt[mapping[role]] == q_gt[role]))
                     for role in "XY"}
            values = [x["correct"] for x in edges.values()]
            verdict = "UNSCORABLE" if None in values else "CORRECT" if all(values) else "WRONG"
            hypotheses[hypothesis["id"]] = dict(verdict=verdict, edges=edges)
        choice = event["choice"]
        model_verdict = hypotheses[choice]["verdict"] if choice in hypotheses else (
            "DEFER" if choice == "DEFER" else "INVALID_OR_UNSENT")
        results.append(dict(case=case, q=q, status=event["status"], choice=choice,
                            reference_gt=ref_gt, q_gt=q_gt, hypotheses=hypotheses,
                            selected_reference_verdict=model_verdict))
    bank = metrics["transactions"]
    assert len(bank) == sum(x["status"] == "COMMIT" for x in events)
    output = dict(status="POSTSEAL_EXPOSED_VALIDATION_PHYSICAL_REFERENCE_AUDIT",
                  source_prediction_sha256=seal["predictions_sha256"],
                  matches_sha256=MATCHES_SHA,
                  method="GT identity at frozen A/B observation anchors compared with GT at q-local X/Y; independent of internal Bridge target-bank anchor",
                  events=results,
                  committed_reference_counts={name: sum(x["status"] == "COMMIT" and
                      x["selected_reference_verdict"] == name for x in results)
                      for name in ("CORRECT", "WRONG", "UNSCORABLE")},
                  frozen_scorer_bank_anchor_counts=metrics["transaction_counts"],
                  frozen_scorer_bank_anchor_transactions=bank,
                  note="Official TrackEval metrics are unchanged. Bank-anchor provenance is a distinct internal-state check, not the frozen event-reference truth label.")
    target = PUBLIC / "PHYSICAL_REFERENCE_AUDIT.json"
    assert not target.exists(), target
    target.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(dict(status=output["status"],
                          selected=[(x["case"], x["choice"], x["status"],
                                     x["selected_reference_verdict"]) for x in results],
                          commits=output["committed_reference_counts"])))


if __name__ == "__main__":
    main()
