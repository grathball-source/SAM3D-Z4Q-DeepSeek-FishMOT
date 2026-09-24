"""Independent post-seal TrackEval score for the Q-rule scope correction."""
import argparse
import gzip
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
from pycocotools import mask as mu

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "online/closed_loop_2888"))
from score import metrics, rle  # noqa: E402


def sha(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def rows(path):
    with gzip.open(path, "rt") as handle:
        yield from map(json.loads, handle)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=("development", "validation"), required=True)
    parser.add_argument("--assignments", type=Path, required=True)
    parser.add_argument("--truth", type=Path, required=True)
    args = parser.parse_args()
    seal = json.loads((HERE / f"OUTPUT_SEAL_QRULE_SCOPEFIX_{args.split}.json").read_text())
    path = HERE / f"PREDICTIONS_QRULE_SCOPEFIX_{args.split}.jsonl.gz"
    assert seal["status"] == "PREDICTIONS_SCOPEFIX_SEALED_AWAITING_GT" and not seal["GT_read"]
    assert sha(path) == seal["predictions_sha256"]
    original = json.loads((HERE / f"METRICS_{args.split}.json").read_text())
    assert sha(args.assignments) == original["input_hashes"]["assignments"]
    assert sha(args.truth) == original["input_hashes"]["truth"]
    gt, pred, sims = [], {"B0": [], "Q-rule-scopefix": []}, {"B0": [], "Q-rule-scopefix": []}
    frames = 0
    for assignment, row, truth in zip(rows(args.assignments), rows(path), rows(args.truth), strict=True):
        frames += 1
        assert assignment["frame"] == row["frame"] == frames
        assert row["global_frame"] == truth["global_frame_id"]
        gids = [int(x["id"]) for x in truth["gt_grid"]]
        gt.append(gids)
        keys = sorted(assignment["masks"])
        lookup = {k: i for i, k in enumerate(keys)}
        matrix = (mu.iou([rle(x["rle"]) for x in truth["gt_grid"]],
                         [rle(assignment["masks"][k]) for k in keys], [0] * len(keys))
                  if gids and keys else np.zeros((len(gids), len(keys))))
        for arm, field in (("B0", "B0"), ("Q-rule-scopefix", "Q_rule_scopefix")):
            objects = row[field]
            assert [x["mask"] for x in objects] == [x["mask"] for x in assignment["variants"]["N0"]]
            pred[arm].append([int(x["id"]) for x in objects])
            sims[arm].append(matrix[:, [lookup[x["mask"]] for x in objects]])
    result = metrics(gt, pred, sims)
    assert frames == seal["frames"]
    assert all(abs(result["B0"][k] - v) < 1e-8 for k, v in original["metrics"]["B0"].items())
    output = dict(status="POST_SEAL_SCOPEFIX_SCORE", split=args.split, metrics=result,
                  scopefix_seal_sha256=sha(HERE / f"OUTPUT_SEAL_QRULE_SCOPEFIX_{args.split}.json"),
                  truth_sha256=sha(args.truth), API_calls=0)
    out = HERE / f"METRICS_QRULE_SCOPEFIX_{args.split}.json"
    assert not out.exists()
    out.write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps(output))


if __name__ == "__main__":
    main()
