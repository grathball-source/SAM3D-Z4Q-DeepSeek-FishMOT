"""Post-seal global relation census; supersedes first-anchor relation diagnostic only.

TrackEval scores and predictions are immutable. Global GT/public calibration is
retrospective analysis and is never sent to any quality gate.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from scipy.optimize import linear_sum_assignment

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ARMS = ("B0", "Q-rule", "Q-visible-oracle", "quota")


def sha(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def rows(path):
    with gzip.open(path, "rt") as handle:
        yield from map(json.loads, handle)


def _intervals(split, gt, observations, query_frames, bad_frames, last_frame):
    output = []
    active = None
    for item in observations + [dict(frame=last_frame + 2, status="END")]:
        signature = (item["status"], item.get("public_id"))
        if active and (item["frame"] != active["end"] + 1 or signature != active["signature"]):
            if active["status"] != "CORRECT":
                start, end = active["start"], active["end"]
                output.append(dict(split=split, gt_id=gt, start=start, end=end,
                                   duration_frames=end - start + 1, status=active["status"],
                                   observed_public_id=active["public_id"], expected_public_id=active["expected"],
                                   first_association_error=start if active["status"] == "ASSOCIATION_ERROR" else None,
                                   first_observable_bad_write=min((f for f in bad_frames if f <= start and start - f <= 150), default=None),
                                   old_candidate_flow="QUERY_COVERED" if any(start <= f <= end for f in query_frames) else "NO_TRIGGER_OR_NO_QUERY",
                                   covered_query_frames=[f for f in query_frames if start <= f <= end],
                                   right_censored=end == last_frame,
                                   recovery_frame=item["frame"] if item["status"] == "CORRECT" else None,
                                   first_native_id=active["native_id"]))
            active = None
        if item["status"] == "END":
            continue
        if active is None:
            active = dict(signature=signature, status=item["status"], public_id=item.get("public_id"),
                          expected=item.get("expected_public_id"), native_id=item.get("native_id"),
                          start=item["frame"], end=item["frame"])
        else:
            active["end"] = item["frame"]
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=("development", "validation"), required=True)
    parser.add_argument("--truth", type=Path, required=True)
    parser.add_argument("--matches", type=Path, required=True)
    args = parser.parse_args()
    seal = json.loads((HERE / f"OUTPUT_SEAL_{args.split}.json").read_text())
    pred_path = HERE / f"PREDICTIONS_{args.split}.jsonl.gz"
    assert seal["status"] == "PREDICTIONS_SEALED_AWAITING_GT" and sha(pred_path) == seal["predictions_sha256"]
    metric = json.loads((HERE / f"METRICS_{args.split}.json").read_text())
    assert metric["input_hashes"]["truth"] == sha(args.truth)
    assert metric["input_hashes"]["matches"] == sha(args.matches)
    frames = []
    cooccur = Counter()
    old_new = Counter()
    old_new_examples = []
    for pred, truth, match in zip(rows(pred_path), rows(args.truth), rows(args.matches), strict=True):
        frame = pred["frame"]
        assert pred["global_frame"] == truth["global_frame_id"] == match["global_frame"]
        maps = {arm: {int(x["mask"].split(":")[1]): int(x["id"]) for x in pred["variants"][arm]} for arm in ARMS}
        by_gt = defaultdict(list)
        for obj in match["objects"]:
            native = int(obj["native_id"])
            new = None if obj.get("ambiguity") else obj.get("gt_id")
            old = match["native_to_gt"].get(str(native))
            old_new["rows"] += 1
            if old != new:
                old_new["mismatch"] += 1
                if len(old_new_examples) < 30:
                    old_new_examples.append(dict(frame=frame, native_id=native, native_to_gt=old,
                                                 objects_gt_id=obj.get("gt_id"), ambiguity=obj.get("ambiguity")))
            if new is not None:
                by_gt[int(new)].append(native)
                cooccur[(int(new), maps["B0"][native])] += 1
            else:
                old_new["unknown"] += 1
        frames.append(dict(frame=frame, gt_ids=[int(x["id"]) for x in truth["gt_grid"]],
                           by_gt=dict(by_gt), maps=maps))
    expected_frames = 8400 if args.split == "development" else 2888
    assert len(frames) == expected_frames
    gt_ids = sorted({g for row in frames for g in row["gt_ids"]})
    public_ids = sorted({p for row in frames for p in row["maps"]["B0"].values()})
    weight = np.array([[cooccur[(g, p)] for p in public_ids] for g in gt_ids], dtype=int)
    rr, cc = linear_sum_assignment(-weight)
    global_map = {gt_ids[i]: public_ids[j] for i, j in zip(rr, cc) if weight[i, j] > 0}
    confidence = {g: cooccur[(g, p)] / max(1, sum(cooccur[(g, q)] for q in public_ids))
                  for g, p in global_map.items()}
    # A low-dominance global assignment is retained for transparency, but not
    # used to assert an individual relation error.
    certified = {g: p for g, p in global_map.items() if confidence[g] >= .8}
    statuses = {arm: defaultdict(list) for arm in ARMS}
    switch_counts = Counter()
    previous = {}
    for row in frames:
        frame = row["frame"]
        for g in row["gt_ids"]:
            natives = row["by_gt"].get(g, [])
            expected = certified.get(g)
            for arm in ARMS:
                public = row["maps"][arm].get(natives[0]) if len(natives) == 1 else None
                if len(natives) != 1:
                    status = "NO_UNIQUE_OBSERVATION"
                elif expected is None:
                    status = "UNKNOWN_GLOBAL_ID"
                else:
                    status = "CORRECT" if public == expected else "ASSOCIATION_ERROR"
                statuses[arm][g].append(dict(frame=frame, native_id=natives[0] if len(natives) == 1 else None,
                                              public_id=public, expected_public_id=expected, status=status))
            if len(natives) == 1:
                native, public = natives[0], row["maps"]["B0"][natives[0]]
                earlier = previous.get(g)
                if earlier and earlier["native"] != native:
                    switch_counts["native_changes"] += 1
                if earlier and earlier["public"] != public:
                    switch_counts["public_changes"] += 1
                    if public == certified.get(g):
                        switch_counts["self_recoveries"] += 1
                    elif public in certified.values() and public != certified.get(g):
                        switch_counts["exchanges_into_other_global_id"] += 1
                    else:
                        switch_counts["fragmentations_or_new_public"] += 1
                previous[g] = dict(native=native, public=public)
    old_queries = [json.loads(s)["query_frame"] for s in
                   (ROOT / f"experiments/vl_assoc_e1c/CANDIDATE_REACHABILITY_{args.split}.jsonl").read_text().splitlines()
                   if json.loads(s).get("query_frame") is not None]
    bad = [json.loads(s)["frame"] for s in (HERE / "QUALITY_LABELS.jsonl").read_text().splitlines()
           if json.loads(s)["split"] == args.split and json.loads(s)["label"] == "VISIBLY_UNUSABLE"]
    intervals = [item for g, observations in statuses["B0"].items()
                 for item in _intervals(args.split, g, observations, old_queries, bad, expected_frames)]
    intervals.sort(key=lambda x: (x["start"], x["end"], x["gt_id"]))
    # Conservative physical-event grouping: overlapping intervals and nearby
    # segments sharing a GT/public cannot count as independent interactions.
    clusters = []
    for item in intervals:
        close = [c for c in clusters if item["start"] <= c["end"] or
                 (item["start"] - c["end"] <= 30 and
                  (item["gt_id"] in c["gt"] or item["observed_public_id"] in c["public"]))]
        if close:
            cluster = close[0]
            cluster["end"] = max(cluster["end"], item["end"])
            cluster["gt"].add(item["gt_id"])
            cluster["public"].add(item["observed_public_id"])
        else:
            cluster = dict(id=len(clusters) + 1, end=item["end"], gt={item["gt_id"]},
                           public={item["observed_public_id"]})
            clusters.append(cluster)
        item["interaction_cluster"] = f'{args.split}:I{cluster["id"]}'
    census_path = HERE / f"FULL_SEQUENCE_ERROR_CENSUS_{args.split}_v2.jsonl"
    assert not census_path.exists()
    with census_path.open("x") as handle:
        for item in intervals:
            handle.write(json.dumps(item) + "\n")
    veto_frames = defaultdict(list)
    for audit in rows(HERE / f"REFERENCE_WRITE_READ_AUDIT_{args.split}.jsonl.gz"):
        if audit["kind"] == "VETO":
            veto_frames[audit["arm"]].append(audit["frame"])
    follow = []
    for arm in ARMS[1:]:
        for g in gt_ids:
            base, branch = statuses["B0"][g], statuses[arm][g]
            assert len(base) == len(branch)
            changed = [a["frame"] for a, b in zip(base, branch)
                       if a["status"] != b["status"] or a["public_id"] != b["public_id"]]
            horizons = {str(veto): {str(h): sum(veto <= f <= veto + h for f in changed) for h in (30, 90, 150)}
                        for veto in sorted(set(veto_frames[arm])) if arm != "Q-rule"}
            follow.append(dict(split=args.split, arm=arm, gt_id=g,
                               B0_error_frames=sum(x["status"] == "ASSOCIATION_ERROR" for x in base),
                               branch_error_frames=sum(x["status"] == "ASSOCIATION_ERROR" for x in branch),
                               B0_unknown_frames=sum(x["status"].startswith("UNKNOWN") or x["status"] == "NO_UNIQUE_OBSERVATION" for x in base),
                               branch_unknown_frames=sum(x["status"].startswith("UNKNOWN") or x["status"] == "NO_UNIQUE_OBSERVATION" for x in branch),
                               changed_frames=len(changed), first_changed_frame=min(changed, default=None),
                               last_changed_frame=max(changed, default=None),
                               per_veto_horizons=horizons, right_censored=bool(changed and changed[-1] == expected_frames)))
    follow_path = HERE / f"FOLLOWUP_AUDIT_{args.split}_v2.jsonl"
    assert not follow_path.exists()
    with follow_path.open("x") as handle:
        for item in follow:
            handle.write(json.dumps(item) + "\n")
    result = dict(status="RETROSPECTIVE_RELATION_DIAGNOSTIC_V2", split=args.split,
                  supersedes="first-anchor relation counts in METRICS_{split}.json only; TrackEval scores unchanged",
                  global_assignment=global_map, dominance=confidence, certified_at_0_8=certified,
                  calibration_uses_full_exposed_GT=True, never_used_by_gate=True,
                  old_new_crosswalk=dict(old_new), old_new_mismatch_examples=old_new_examples,
                  switch_counts=dict(switch_counts), interval_count=len(intervals), interaction_clusters=len(clusters),
                  status_counts={arm: dict(Counter(x["status"] for records in statuses[arm].values() for x in records))
                                 for arm in ARMS},
                  census_sha256=sha(census_path), followup_sha256=sha(follow_path),
                  inputs=dict(predictions_sha256=sha(pred_path), truth_sha256=sha(args.truth), matches_sha256=sha(args.matches)),
                  API_calls=0)
    out = HERE / f"RELATION_CENSUS_{args.split}_v2.json"
    assert not out.exists()
    out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: result[k] for k in ("split", "certified_at_0_8", "interval_count", "interaction_clusters", "status_counts")}))


if __name__ == "__main__":
    main()
