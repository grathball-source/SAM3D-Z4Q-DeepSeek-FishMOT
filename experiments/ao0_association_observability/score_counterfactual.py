"""Independent post-seal TrackEval plus all-GT relation follow-up, exposed split only."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from pycocotools import mask as mu

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "online/closed_loop_2888"))
from score import metrics, rle  # noqa: E402


def sha(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def rows(path):
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        yield from map(json.loads, handle)


def score(args):
    manifest = json.loads((HERE / "CASE_MANIFEST.json").read_text())["first_case"]
    seal = json.loads((HERE / "COUNTERFACTUAL_SEAL.json").read_text())
    assert seal["status"] == "PREDICTIONS_SEALED_BEFORE_GT_SCORE" and seal["GT_read"] is False
    assert sha(HERE / "CASE_MANIFEST.json") == seal["manifest_sha256"]
    assert sha(HERE / "OUTPUT_ORACLE_validation.jsonl.gz") == seal["output_oracle_sha256"]
    assert sha(HERE / "STATE_PREDICTIONS_validation.jsonl.gz") == seal["state_predictions_sha256"]
    assert sha(args.truth) == manifest["input_provenance"]["exposed_truth_sha256"]
    correction = json.loads((HERE / "CASE_MANIFEST_CORRECTION.json").read_text())
    assert correction["original_case_manifest_sha256"] == seal["manifest_sha256"]
    assert manifest["input_provenance"]["exposed_matches_sha256"] == correction["incorrect_original_value"]
    assert sha(args.matches) == correction["correct_source_value"]
    gt, pred, sims = [], {arm: [] for arm in ("B0", "KEEP", "SWAP", "STATE")}, {}
    sims = {arm: [] for arm in pred}
    follow = {arm: defaultdict(lambda: Counter()) for arm in ("SWAP", "STATE")}
    anchors = {}
    query = manifest["query_frame"]
    for assignment, truth, match, oracle, state in zip(rows(args.assignments), rows(args.truth),
            rows(args.matches), rows(HERE / "OUTPUT_ORACLE_validation.jsonl.gz"),
            rows(HERE / "STATE_PREDICTIONS_validation.jsonl.gz"), strict=True):
        frame = oracle["frame"]
        assert assignment["frame"] == match["frame"] == state["frame"] == frame
        assert truth["global_frame_id"] == oracle["global_frame"] == state["global_frame"]
        gt_ids = [int(x["id"]) for x in truth["gt_grid"]]
        gt.append(gt_ids)
        keys = sorted(assignment["masks"])
        lookup = {key: i for i, key in enumerate(keys)}
        matrix = (mu.iou([rle(x["rle"]) for x in truth["gt_grid"]],
                         [rle(assignment["masks"][key]) for key in keys], [0] * len(keys))
                  if gt_ids and keys else np.zeros((len(gt_ids), len(keys))))
        objects = {"B0": oracle["B0"], "KEEP": oracle["KEEP"],
                   "SWAP": oracle["SWAP"], "STATE": state["STATE"]}
        native_keys = [x["mask"] for x in assignment["variants"]["N0"]]
        maps = {}
        for arm, values in objects.items():
            assert [x["mask"] for x in values] == native_keys
            pred[arm].append([int(x["id"]) for x in values])
            sims[arm].append(matrix[:, [lookup[x["mask"]] for x in values]])
            maps[arm] = {int(x["mask"].split(":")[1]): int(x["id"]) for x in values}
        by_gt = defaultdict(list)
        for obj in match["objects"]:
            if obj.get("gt_id") is not None and not obj.get("ambiguity"):
                by_gt[int(obj["gt_id"])].append(int(obj["native_id"]))
        if frame == manifest["pre_intervention_relation_anchor_frame"]:
            anchors = {g: maps["B0"][n[0]] for g, n in by_gt.items() if len(n) == 1}
            assert anchors[2] == 1 and anchors[6] == 4
        if frame >= query:
            elapsed = frame - query
            horizons = [str(h) for h in (30, 90, 150) if elapsed < h]
            if elapsed >= 150:
                horizons.append("remaining")
            for g in gt_ids:
                natives = by_gt[g]
                for arm in follow:
                    count = follow[arm][g]
                    for horizon in horizons:
                        count[horizon + ":GT_present"] += 1
                        if len(natives) != 1:
                            count[horizon + ":NO_UNIQUE_OBSERVATION"] += 1
                            continue
                        native = natives[0]
                        b0, test = maps["B0"][native], maps[arm][native]
                        count[horizon + ":unique"] += 1
                        count[horizon + ":changed_from_B0"] += b0 != test
                        if g in anchors:
                            count[horizon + ":B0_anchor_match"] += b0 == anchors[g]
                            count[horizon + ":branch_anchor_match"] += test == anchors[g]
                        else:
                            count[horizon + ":UNKNOWN_ANCHOR"] += 1
    assert len(gt) == 2888
    result = metrics(gt, pred, sims)
    historical = dict(IDF1=80.69758683623512, HOTA=69.24386895965796,
                      AssA=60.07432145541481, IDSW=9, FP=298, FN=423)
    assert all(abs(result["B0"][k] - value) < 1e-8 for k, value in historical.items())
    assert result["KEEP"] == result["B0"]
    report = dict(status="EXPOSED_POSTSEAL_SCORE", split="validation", query_frame=query,
                  official_TrackEval=result, anchor_frame=manifest["pre_intervention_relation_anchor_frame"],
                  anchor_public_by_gt=anchors, all_object_followup={arm: {str(g): dict(counts)
                           for g, counts in sorted(by_gt.items())} for arm, by_gt in follow.items()},
                  horizon_definition="30/90/150 are cumulative [q,q+h-1]; remaining is [q+150,end]",
                  right_censored={str(h): query + h - 1 > 2888 for h in (30, 90, 150)},
                  note="Anchor relation is exposed-GT diagnostic, not the official TrackEval identity assignment.",
                  source_sha256={"assignments": sha(args.assignments), "truth": sha(args.truth),
                                 "matches": sha(args.matches), "oracle": seal["output_oracle_sha256"],
                                 "state": seal["state_predictions_sha256"]},
                  metadata_correction_sha256=sha(HERE / "CASE_MANIFEST_CORRECTION.json"), API_calls=0)
    path = HERE / "METRICS.json"
    assert not path.exists()
    path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for name in ("assignments", "truth", "matches"):
        parser.add_argument("--" + name, type=Path, required=True)
    score(parser.parse_args())
