"""Exposed-GT identity timeline; never used by the online association engine."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path


def sha(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def rows(path):
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        yield from map(json.loads, handle)


def segment(rows_for_gt):
    """Group only consecutive, equally observed relations; UNKNOWN is not an event."""
    result = []
    for item in rows_for_gt:
        signature = (item["status"], item["public_id"])
        if result and item["frame"] == result[-1]["end"] + 1 and signature == result[-1]["signature"]:
            result[-1]["end"] = item["frame"]
            result[-1]["count"] += 1
        else:
            result.append(dict(gt_id=item["gt_id"], start=item["frame"], end=item["frame"],
                               count=1, status=item["status"], public_id=item["public_id"],
                               signature=signature))
    for value in result:
        del value["signature"]
    return result


def transitions(segments):
    """Temporal changes, not absolute ID errors or physical-interaction counts."""
    out = []
    for gt, parts in segments.items():
        previous = None
        for part in parts:
            if part["status"] != "UNIQUE":
                continue
            if previous and previous["public_id"] != part["public_id"]:
                out.append(dict(gt_id=gt, before_public=previous["public_id"],
                                after_public=part["public_id"], before_end=previous["end"],
                                after_start=part["start"], gap_frames=part["start"] - previous["end"] - 1,
                                after_duration=part["count"], after_end=part["end"],
                                relation="PUBLIC_CHANGE_NOT_YET_CAUSALLY_ATTRIBUTED"))
            previous = part
    return sorted(out, key=lambda x: (x["after_start"], x["gt_id"]))


def no_unique_reason(unique_matches, ambiguous_matches):
    if len(unique_matches) > 1:
        return "MULTIPLE_UNIQUE_MATCHES"
    if ambiguous_matches:
        return "AMBIGUOUS_OR_MIXED_MASK"
    return "NO_MATCHED_PREDICTION"


def audit(predictions, truth, matches, output):
    source_sha = {name: sha(path) for name, path in
                  (("predictions", predictions), ("truth", truth), ("matches", matches))}
    timeline = []
    cooccurrence = Counter()
    observed = Counter()
    unknown_reasons = Counter()
    for pred, gt, match in zip(rows(predictions), rows(truth), rows(matches), strict=True):
        frame = pred["frame"]
        assert pred["global_frame"] == gt["global_frame_id"] == match["global_frame"]
        assert frame == match["frame"]
        native_to_public = {int(x["mask"].split(":")[1]): int(x["id"])
                            for x in pred["variants"]["B0"]}
        by_gt = defaultdict(list)
        ambiguous_by_gt = defaultdict(list)
        for obj in match["objects"]:
            native = int(obj["native_id"])
            gt_id = None if obj.get("ambiguity") else obj.get("gt_id")
            if gt_id is not None and native in native_to_public:
                by_gt[int(gt_id)].append(obj)
            if obj.get("ambiguity"):
                for candidate in obj.get("candidate_gt_ids", []):
                    ambiguous_by_gt[int(candidate)].append(native)
        for entity in gt["gt_grid"]:
            gt_id = int(entity["id"])
            choices = by_gt[gt_id]
            if len(choices) == 1:
                obj = choices[0]
                native = int(obj["native_id"])
                public = native_to_public[native]
                status = "UNIQUE"
                cooccurrence[(gt_id, public)] += 1
                observed[gt_id] += 1
                quality = obj.get("iou")
                mask = obj.get("mask", f"n:{native}")
            else:
                native = public = quality = mask = None
                status = "NO_UNIQUE_OBSERVATION"
                unknown_reasons[no_unique_reason(choices, ambiguous_by_gt[gt_id])] += 1
            timeline.append(dict(frame=frame, global_frame=pred["global_frame"],
                                 time=pred["time"], gt_id=gt_id, status=status,
                                 native_id=native, mask_key=mask, public_id=public,
                                 match_iou=quality,
                                 ambiguity=no_unique_reason(choices, ambiguous_by_gt[gt_id])
                                           if status != "UNIQUE" else None))
    assert {name: sha(path) for name, path in
            (("predictions", predictions), ("truth", truth), ("matches", matches))} == source_sha
    by_gt = defaultdict(list)
    for item in timeline:
        by_gt[item["gt_id"]].append(item)
    segments = {str(g): segment(items) for g, items in sorted(by_gt.items())}
    changes = transitions(segments)
    public_ids = sorted({p for _, p in cooccurrence})
    matrix = {str(g): {str(p): cooccurrence[g, p] for p in public_ids} for g in sorted(by_gt)}
    output.mkdir(parents=True, exist_ok=True)
    paths = [output / name for name in ("RELATION_TIMELINE.jsonl.gz", "RELATION_SEGMENTS.json", "RELATION_SUMMARY.json")]
    assert not any(path.exists() for path in paths), "AO0 outputs are immutable; choose a new directory"
    with gzip.open(paths[0], "wt", encoding="utf-8") as handle:
        for item in timeline:
            handle.write(json.dumps(item, separators=(",", ":")) + "\n")
    paths[1].write_text(json.dumps(segments, indent=2) + "\n", encoding="utf-8")
    summary = dict(status="EXPOSED_GT_RELATION_DIAGNOSTIC_ONLY", input_sha256=source_sha,
                   rows=len(timeline), unique_by_gt=dict(observed),
                   cooccurrence=matrix, transitions=changes, no_unique_reasons=dict(unknown_reasons),
                   note="Public names have no intrinsic GT meaning; transitions survive any global bijective renaming. UNKNOWN never certifies a physical interaction.")
    paths[2].write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(dict(rows=len(timeline), transitions=len(changes),
                          gt2_segments=segments.get("2"), gt6_segments=segments.get("6"))))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for name in ("predictions", "truth", "matches", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    audit(args.predictions, args.truth, args.matches, args.output)
