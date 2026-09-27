"""Compact postseal counts of matched GT identity by public tracker ID."""
from __future__ import annotations

import argparse
import collections
import gzip
import hashlib
import json
from pathlib import Path


def sha(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def rows(path):
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        yield from map(json.loads, handle)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--old", type=Path, required=True)
    parser.add_argument("--matches", type=Path, required=True)
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    old_path = args.old / "predictions_validation.jsonl.gz"
    ablated_path = here / "predictions_b03_only.jsonl.gz"
    old_seal = json.loads((args.old / "PREDICTIONS_SEALED.json").read_text(encoding="utf-8"))
    ablated_seal = json.loads((here / "B03_ONLY_SEAL.json").read_text(encoding="utf-8"))
    assert sha(old_path) == old_seal["predictions_sha256"] == ablated_seal["source_prediction_sha256"]
    assert sha(ablated_path) == ablated_seal["predictions_sha256"]
    assert sha(args.matches) == "5c557ab0dd833e00b4b0d3a6eeec3cdd6e0669f11da4f5e6611619fe5928cbd1"
    counts = {arm: {window: collections.Counter() for window in ("pre_B03", "B03_to_pre_B04", "post_B04")}
              for arm in ("B0", "B03_ONLY", "B1")}
    available = collections.Counter()
    for matched, old, ablated in zip(rows(args.matches), rows(old_path), rows(ablated_path), strict=True):
        frame = old["frame"]
        assert matched["frame"] == ablated["frame"] == frame
        window = "pre_B03" if frame < 377 else "B03_to_pre_B04" if frame < 2638 else "post_B04"
        arms = {"B0": old["variants"]["B0"], "B1": old["variants"]["B1"],
                "B03_ONLY": ablated["variants"]["B03_ONLY"]}
        native = [x["mask"] for x in arms["B0"]]
        assert all([x["mask"] for x in objects] == native for objects in arms.values())
        available[window] += 1
        for arm, objects in arms.items():
            for item in objects:
                individual = matched["native_to_gt"].get(item["mask"].split(":")[1])
                if individual is not None:
                    counts[arm][window][(int(item["id"]), int(individual))] += 1
    assert available == {"pre_B03": 376, "B03_to_pre_B04": 2261, "post_B04": 251}
    output = {
        "status": "POSTSEAL_MATCHED_ID_COUNTS",
        "source_sha256": {"old_prediction": sha(old_path),
                          "b03_only_prediction": sha(ablated_path), "matches": sha(args.matches)},
        "frame_counts": dict(available),
        "counts": {arm: {window: [dict(public_id=public, gt_id=gt, matched_observations=n)
                                   for (public, gt), n in sorted(table.items())]
                         for window, table in windows.items()}
                   for arm, windows in counts.items()},
        "interpretation": "Matched native-mask counts, not TrackEval association scores or causal gains.",
    }
    target = here / "MATCHED_ID_COUNTS.json"
    with target.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(output, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps({"status": output["status"], "frames": dict(available)}))


if __name__ == "__main__":
    main()
