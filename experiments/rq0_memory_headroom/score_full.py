"""Independent post-seal TrackEval and full exposed-sequence relation audit."""
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

ARMS = ("B0", "Q-rule", "Q-visible-oracle", "quota")


def sha(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def rows(path):
    with gzip.open(path, "rt") as handle:
        yield from map(json.loads, handle)


def intervals(statuses, split, old_queries, risks, last_frame):
    output = []
    for gt, entries in sorted(statuses.items()):
        active = None
        for item in entries + [dict(frame=last_frame + 2, status="END")]:
            signature = (item["status"], item.get("public_id"))
            if active and (item["frame"] != active["end"] + 1 or signature != active["signature"]):
                if active["status"] != "CORRECT":
                    start, end = active["start"], active["end"]
                    query = [x for x in old_queries if start <= x <= end]
                    preceding = [x for x in risks if x["frame"] <= start and start - x["frame"] <= 150]
                    output.append(dict(split=split, gt_id=gt, start=start, end=end,
                                       duration_frames=end - start + 1, status=active["status"],
                                       observed_public_id=active["public_id"], expected_public_id=active["expected"],
                                       first_association_error=start if active["status"] == "ASSOCIATION_ERROR" else None,
                                       first_observable_risk=min((x["frame"] for x in preceding), default=None),
                                       old_candidate_flow="QUERY_COVERED" if query else "NO_TRIGGER_OR_NO_QUERY",
                                       covered_query_frames=query, right_censored=end == last_frame,
                                       recovery_frame=item["frame"] if item["status"] == "CORRECT" else None))
                active = None
            if item["status"] == "END":
                continue
            if active is None:
                active = dict(signature=signature, status=item["status"], public_id=item.get("public_id"),
                              expected=item.get("expected_public_id"), start=item["frame"], end=item["frame"])
            else:
                active["end"] = item["frame"]
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=("development", "validation"), required=True)
    parser.add_argument("--assignments", type=Path, required=True)
    parser.add_argument("--truth", type=Path, required=True)
    parser.add_argument("--matches", type=Path, required=True)
    args = parser.parse_args()
    seal = json.loads((HERE / f"OUTPUT_SEAL_{args.split}.json").read_text())
    pred_path = HERE / f"PREDICTIONS_{args.split}.jsonl.gz"
    assert seal["status"] == "PREDICTIONS_SEALED_AWAITING_GT" and not seal["GT_read"]
    assert sha(pred_path) == seal["predictions_sha256"]
    assert sha(HERE / f"REFERENCE_WRITE_READ_AUDIT_{args.split}.jsonl.gz") == seal["audit_sha256"]
    labels = [json.loads(s) for s in (HERE / "QUALITY_LABELS.jsonl").read_text().splitlines()]
    risks = [x for x in labels if x["split"] == args.split and x["label"] == "VISIBLY_UNUSABLE"]
    old_queries = [json.loads(s)["query_frame"] for s in
                   (ROOT / f"experiments/vl_assoc_e1c/CANDIDATE_REACHABILITY_{args.split}.jsonl").read_text().splitlines()
                   if json.loads(s).get("query_frame") is not None]
    gt, pred, sims = [], {a: [] for a in ARMS}, {a: [] for a in ARMS}
    status_by_gt = defaultdict(list)
    branch_status = {a: defaultdict(list) for a in ARMS}
    fixed, inverse = {}, {}
    cross = Counter()
    cross_examples = []
    relation_counts = Counter()
    last_frame = 0
    for assignment, prediction, truth, match in zip(rows(args.assignments), rows(pred_path), rows(args.truth), rows(args.matches), strict=True):
        frame = prediction["frame"]
        last_frame = frame
        assert assignment["frame"] == match["frame"] == frame
        assert prediction["global_frame"] == truth["global_frame_id"] == match["global_frame"]
        native_keys = [x["mask"] for x in assignment["variants"]["N0"]]
        gt_ids = [int(x["id"]) for x in truth["gt_grid"]]
        gt.append(gt_ids)
        keys = sorted(assignment["masks"])
        lookup = {k: i for i, k in enumerate(keys)}
        matrix = (mu.iou([rle(x["rle"]) for x in truth["gt_grid"]],
                         [rle(assignment["masks"][k]) for k in keys], [0] * len(keys))
                  if gt_ids and keys else np.zeros((len(gt_ids), len(keys))))
        maps = {}
        for arm in ARMS:
            objects = prediction["variants"][arm]
            assert [x["mask"] for x in objects] == native_keys
            pred[arm].append([int(x["id"]) for x in objects])
            sims[arm].append(matrix[:, [lookup[x["mask"]] for x in objects]])
            maps[arm] = {int(x["mask"].split(":")[1]): int(x["id"]) for x in objects}
        old = match["native_to_gt"]
        current = defaultdict(list)
        for obj in match["objects"]:
            n = int(obj["native_id"])
            old_gt = old.get(str(n))
            new_gt = obj.get("gt_id") if not obj.get("ambiguity") else None
            if old_gt != new_gt:
                cross["binding_disagreement"] += 1
                if len(cross_examples) < 30:
                    cross_examples.append(dict(split=args.split, frame=frame, native_id=n,
                                               native_to_gt=old_gt, objects_gt_id=obj.get("gt_id"),
                                               ambiguity=obj.get("ambiguity"), iou=obj.get("iou")))
            cross["object_rows"] += 1
            if new_gt is not None:
                current[int(new_gt)].append(n)
                if int(new_gt) not in inverse and maps["B0"].get(n) not in fixed:
                    fixed[maps["B0"][n]] = int(new_gt)
                    inverse[int(new_gt)] = maps["B0"][n]
            else:
                cross["unknown_object_rows"] += 1
        for individual in gt_ids:
            natives = current.get(individual, [])
            expected = inverse.get(individual)
            for arm in ARMS:
                if len(natives) != 1:
                    status, public = ("NO_UNIQUE_OBSERVATION", None)
                elif expected is None:
                    status, public = ("UNKNOWN_INITIAL_ID", maps[arm].get(natives[0]))
                else:
                    public = maps[arm].get(natives[0])
                    status = "CORRECT" if public == expected else "ASSOCIATION_ERROR"
                entry = dict(frame=frame, status=status, public_id=public, expected_public_id=expected,
                             native_id=natives[0] if len(natives) == 1 else None)
                branch_status[arm][individual].append(entry)
                relation_counts[(arm, status)] += 1
                if arm == "B0":
                    status_by_gt[individual].append(entry)
    expected_frames = 8400 if args.split == "development" else 2888
    assert last_frame == expected_frames == len(gt)
    scored = metrics(gt, pred, sims)
    if args.split == "validation":
        historical = dict(IDF1=80.69758683623512, HOTA=69.24386895965796,
                          AssA=60.07432145541481, IDSW=9, FP=298, FN=423)
        assert all(abs(scored["B0"][k] - v) < 1e-8 for k, v in historical.items())
    census = intervals(status_by_gt, args.split, old_queries, risks, last_frame)
    census_path = HERE / f"FULL_SEQUENCE_ERROR_CENSUS_{args.split}.jsonl"
    assert not census_path.exists()
    with census_path.open("x") as handle:
        for item in census:
            handle.write(json.dumps(item) + "\n")
    veto_frames = {}
    for audit in rows(HERE / f"REFERENCE_WRITE_READ_AUDIT_{args.split}.jsonl.gz"):
        if audit["kind"] == "VETO":
            veto_frames[audit["arm"]] = min(audit["frame"], veto_frames.get(audit["arm"], audit["frame"]))
    follow = []
    for arm in ARMS[1:]:
        for individual in sorted(set(branch_status["B0"]) | set(branch_status[arm])):
            base = branch_status["B0"].get(individual, [])
            test = branch_status[arm].get(individual, [])
            assert len(base) == len(test)
            changed = [x["frame"] for x, y in zip(base, test) if x["status"] != y["status"] or x["public_id"] != y["public_id"]]
            origin = veto_frames.get(arm)
            follow.append(dict(split=args.split, arm=arm, gt_id=individual,
                               B0_assoc_error_frames=sum(x["status"] == "ASSOCIATION_ERROR" for x in base),
                               branch_assoc_error_frames=sum(x["status"] == "ASSOCIATION_ERROR" for x in test),
                               B0_unknown_frames=sum(x["status"] != "CORRECT" and x["status"] != "ASSOCIATION_ERROR" for x in base),
                               branch_unknown_frames=sum(x["status"] != "CORRECT" and x["status"] != "ASSOCIATION_ERROR" for x in test),
                               changed_frames=len(changed), first_changed_frame=changed[0] if changed else None,
                               last_changed_frame=changed[-1] if changed else None,
                               first_veto_frame=origin,
                               horizon_changed_frames={str(h): sum(origin is not None and origin <= x <= origin + h for x in changed)
                                                       for h in (30, 90, 150)},
                               remaining_changed_frames=sum(origin is not None and x > origin + 150 for x in changed)))
    follow_path = HERE / f"FOLLOWUP_AUDIT_{args.split}.jsonl"
    assert not follow_path.exists()
    with follow_path.open("x") as handle:
        for item in follow:
            handle.write(json.dumps(item) + "\n")
    output = dict(split=args.split, frames=last_frame, metrics=scored,
                  relation_counts={arm: {status: relation_counts[(arm, status)] for status in
                                           ("CORRECT", "ASSOCIATION_ERROR", "NO_UNIQUE_OBSERVATION", "UNKNOWN_INITIAL_ID")}
                                   for arm in ARMS},
                  fixed_public_to_gt=fixed, fixed_mapping_note="First unique unambiguous match per GT/public within each exposed split; relation diagnostic, not TrackEval and not injected into gates.",
                  old_new_scoring_crosswalk=dict(cross), crosswalk_examples=cross_examples,
                  census_intervals=len(census), census_sha256=sha(census_path), followup_sha256=sha(follow_path),
                  input_hashes={name: sha(path) for name, path in (("assignments", args.assignments),
                                ("truth", args.truth), ("matches", args.matches), ("predictions", pred_path))},
                  GT_read="exposed_split_only_post_prediction_seal", API_calls=0)
    result_path = HERE / f"METRICS_{args.split}.json"
    assert not result_path.exists()
    result_path.write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps({"split": args.split, "metrics": scored, "census_intervals": len(census),
                      "crosswalk": dict(cross)}))


if __name__ == "__main__":
    main()
