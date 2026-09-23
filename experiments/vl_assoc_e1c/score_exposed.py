"""Independent post-freeze scorer of exposed development/validation event candidates."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
E1 = HERE.parent / "vl_assoc_e1"
EXPECTED = {
    "development": ("18793b53c7f751b149d0bbaa01f307b6c86a48f9c831edb761fe87e2b2a9a8cb",
                    "34091028d1e33fde29f89246a91543867d6e0c16d960775725dc4008d9d9977f"),
    "validation": ("9a95ed32e184d2e37c185104df184c943733c00d2cbed8b3e85967e8728dbdef",
                   "5c557ab0dd833e00b4b0d3a6eeec3cdd6e0669f11da4f5e6611619fe5928cbd1"),
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_needed(path, needed):
    result = {}
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            if row["frame"] in needed:
                result[row["frame"]] = row
    assert set(result) == needed
    return result


def unique_truth(frame, native):
    ob = next((x for x in frame["objects"] if x["native_id"] == native), None)
    return None if ob is None or ob.get("ambiguity") or ob.get("gt_id") is None else ob["gt_id"]


def score_event(e, baseline, matches):
    if e.get("query_frame") is None:
        return dict(**e, scorable=False, reasons=[e["status"]], B0_error=None, recovery_opportunity=False)
    frame = e["query_frame"]
    old_gt, reasons = {}, []
    for public in e["identities"]:
        gts = []
        references = e["refs"][str(public)]
        if not references:
            reasons.append(f"NO_HISTORY_{public}")
        for ref in references:
            owners = [int(x["mask"].split(":")[1]) for x in baseline[ref]["variants"]["Z4Q_STABLE"] if x["id"] == public]
            if len(owners) != 1:
                reasons.append(f"HISTORY_OWNER_{public}")
                continue
            gt = unique_truth(matches[ref], owners[0])
            if gt is None:
                reasons.append(f"HISTORY_GT_{public}")
            else:
                gts.append(gt)
        if len(gts) != len(references) or len(set(gts)) != 1:
            reasons.append(f"HISTORY_INCONSISTENT_{public}")
        else:
            old_gt[public] = gts[0]
    if len(set(old_gt.values())) != len(old_gt):
        reasons.append("HISTORIES_SAME_GT")
    current_map = {int(x["mask"].split(":")[1]): x["id"] for x in baseline[frame]["variants"]["Z4Q_STABLE"]}
    current_gt = {native: unique_truth(matches[frame], native) for native in current_map}
    present = {public: [n for n, gt in current_gt.items() if gt == expected]
               for public, expected in old_gt.items()}
    if any(len(natives) > 1 for natives in present.values()):
        reasons.append("DUPLICATED_QUERY_GT")
    if any(current_gt.get(n) is None for n in e.get("selected", [])):
        reasons.append("QUERY_GT_MISSING")
    scorable = not reasons and len(old_gt) == 2
    def correctness(mapping):
        if not scorable:
            return None
        # A true historical identity currently absent has no association to restore.
        for public, natives in present.items():
            if natives and mapping.get(natives[0]) != public:
                return False
        for native, public in mapping.items():
            if public in old_gt and current_gt.get(native) is not None and current_gt[native] != old_gt[public]:
                return False
        return True
    base_ok = correctness(current_map)
    candidates = [dict(changes=c["changes"], executable=c["executable"],
                       correct=correctness({int(k): v for k, v in c["whole"].items()}),
                       excluded_reason=c["excluded_reason"]) for c in e["candidates"]]
    recovery = (scorable and e["kind"] == "RESTORE_MISSING_ID" and base_ok is False and
                any(c["executable"] and c["correct"] for c in candidates))
    return dict(episode_id=e["episode_id"], split=e["split"], trigger_frame=e["trigger_frame"],
                query_frame=frame, status=e["status"], kind=e["kind"], identities=e["identities"],
                selected=e["selected"], owners=e["owners"], refs=e["refs"],
                history_GT=old_gt, query_GT=current_gt, present_native_by_history=present,
                scorable=scorable, reasons=sorted(set(reasons)), B0_error=None if base_ok is None else not base_ok,
                candidates=candidates, recovery_opportunity=recovery)


def main():
    p = argparse.ArgumentParser()
    for split in ("development", "validation"):
        for name in ("baseline", "matches"):
            p.add_argument(f"--{split}-{name}", type=Path, required=True)
    args = p.parse_args()
    freeze = json.loads((HERE / "EXPOSURE_MANIFEST.json").read_text())
    assert freeze["GT_read"] is False and freeze["status"] == "E1C_A_PREDICTION_ONLY_FROZEN"
    for name, expected in freeze["files"].items():
        assert sha(HERE / name) == expected, name
    all_rows = []
    for split in ("development", "validation"):
        candidates = [json.loads(s) for s in (HERE / f"CANDIDATE_REACHABILITY_{split}.jsonl").read_text().splitlines()]
        query = [x for x in candidates if x.get("query_frame") is not None]
        needed = {x["query_frame"] for x in query} | {f for x in query for ff in x["refs"].values() for f in ff}
        baseline_path = getattr(args, f"{split}_baseline")
        matches_path = getattr(args, f"{split}_matches")
        assert (sha(baseline_path), sha(matches_path)) == EXPECTED[split]
        baseline = load_needed(baseline_path, needed)
        matches = load_needed(matches_path, needed)
        all_rows.extend(score_event(e, baseline, matches) for e in candidates)
    out = HERE / "ERROR_COVERAGE.jsonl"
    assert not out.exists()
    with out.open("x") as handle:
        for row in all_rows:
            handle.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
    summary = dict(events=len(all_rows), query=sum(x.get("query_frame") is not None for x in all_rows),
                   scorable=sum(x["scorable"] for x in all_rows), B0_errors=sum(x["B0_error"] is True for x in all_rows),
                   recovery_opportunities=sum(x.get("recovery_opportunity", False) for x in all_rows),
                   recovery_ids=[x["episode_id"] for x in all_rows if x.get("recovery_opportunity")],
                   reason_counts=dict(Counter(r for x in all_rows for r in x["reasons"])))
    (HERE / "EVENT_FUNNEL.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
