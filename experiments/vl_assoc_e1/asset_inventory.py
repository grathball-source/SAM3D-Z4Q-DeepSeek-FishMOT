"""Verify the actual server media and feature streams; never copy raw pixels to Git."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path

import cv2
from pycocotools import mask as mask_api

HERE = Path(__file__).resolve().parent


def digest(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def rows(path):
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            yield json.loads(line)


def summarize(split, observations, depth, appearance, masks, offset, manifest, data):
    counts = Counter()
    first = last = None
    sample = None
    for ob, dep, feat, assignment in zip(rows(observations), rows(depth), rows(appearance), rows(masks), strict=True):
        frame, global_frame = ob["frame"], ob["global_frame"]
        assert global_frame == frame + offset
        assert (frame, global_frame, ob["time"]) == (dep["frame"], dep["global_frame"], dep["time"])
        assert (frame, ob["time"]) == (assignment["frame"], assignment["time"])
        assert (global_frame, ob["time"]) == (feat["global_frame"], feat["time"])
        assert dep["evidence_max_global_frame"] <= global_frame
        ids = {x["id"] for x in ob["observations"]}
        assert ids == {x["id"] for x in dep["observations"]}
        by_mask = {x["mask"]: x for x in feat["obs"]}
        assert {f"n:{n}" for n in ids} == set(by_mask), (split, frame, "feature_mask_coverage")
        assert {f"n:{n}" for n in ids} <= set(assignment["masks"]), (split, frame, "native_mask_missing")
        counts["extra_non_native_masks"] += len(set(assignment["masks"]) - {f"n:{n}" for n in ids})
        counts["frames"] += 1
        counts["observations"] += len(ids)
        if global_frame == 1:
            counts["RGB_unpaired_first_frame"] += 1
        else:
            source = manifest[global_frame - 2]
            assert source["frame_id"] + 1 == global_frame
            assert abs(source["color_timestamp_us"] / 1e6 - ob["time"]) < .002
            assert (data / source["rgb_original"]).is_file()
            counts["RGB_available_frames"] += 1
        for n in ids:
            x = by_mask[f"n:{n}"]
            assert x["area"] == next(o["area"] for o in ob["observations"] if o["id"] == n)
            counts["feature_id_differs_from_native"] += x["id"] != n
            counts["FPN_256_available"] += isinstance(x.get("appearance"), list) and len(x["appearance"]) == 256
            counts["RGB_hist_48_available"] += isinstance(x.get("rgb_hist"), list) and len(x["rgb_hist"]) == 48
        if first is None:
            first = global_frame
        last = global_frame
        if frame in {2, 190, 241, 2888} or (split == "development" and frame in {4200, 8400}):
            source = manifest[global_frame - 2]
            rgb = data / source["rgb_original"]
            assert rgb.is_file() and digest(rgb) == source["source_rgb_sha256"]
            image = cv2.imread(str(rgb), cv2.IMREAD_COLOR)
            assert image is not None
            native = min(ids)
            encoded = assignment["masks"][f"n:{native}"]
            mask = mask_api.decode(dict(size=encoded["size"], counts=encoded["counts"].encode("ascii")))
            assert mask.ndim == 2 and tuple(encoded["size"]) == mask.shape
            assert image.shape[0] % mask.shape[0] == image.shape[1] % mask.shape[1] == 0
            actual_area = int(mask.sum())
            expected_area = next(x["area"] for x in ob["observations"] if x["id"] == native)
            assert actual_area == expected_area
            counts["RGB_hash_verified_frames"] += 1
            counts["mask_decoded_aligned_frames"] += 1
            sample = dict(global_frame=global_frame, RGB_size=[image.shape[1], image.shape[0]],
                          mask_size=[mask.shape[1], mask.shape[0]],
                          scale_xy=[image.shape[1] // mask.shape[1], image.shape[0] // mask.shape[0]],
                          sample_mask_area=actual_area)
    return dict(split=split, first_global_frame=first, last_global_frame=last, **counts,
                sample=sample, source_sha256={name: digest(path) for name, path in
                                      (("observations", observations), ("depth", depth),
                                       ("appearance", appearance), ("masks", masks))})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--dev-observations", type=Path, required=True)
    parser.add_argument("--dev-depth", type=Path, required=True)
    parser.add_argument("--dev-appearance", type=Path, required=True)
    parser.add_argument("--dev-masks", type=Path, required=True)
    parser.add_argument("--val-observations", type=Path, required=True)
    parser.add_argument("--val-depth", type=Path, required=True)
    parser.add_argument("--val-appearance", type=Path, required=True)
    parser.add_argument("--val-masks", type=Path, required=True)
    args = parser.parse_args()
    manifest_path = args.data / "manifest.jsonl"
    manifest = [json.loads(line) for line in manifest_path.read_text(encoding="utf-8").splitlines()]
    assert len(manifest) >= 12187
    result = dict(status="VERIFIED_SERVER_ASSETS", manifest_sha256=digest(manifest_path),
                  development=summarize("development", args.dev_observations, args.dev_depth,
                                        args.dev_appearance, args.dev_masks, 0, manifest, args.data),
                  validation=summarize("validation", args.val_observations, args.val_depth,
                                       args.val_appearance, args.val_masks, 9300, manifest, args.data),
                  FPN_provenance="existing active_identity_features_v1, 256D whole mask candidate",
                  RGB_hist_provenance="existing active_identity_features_v1, 48 bins whole predicted mask",
                  HSV_provenance="SLR-2 body mask HSV extractor source only; not present in these feature streams",
                  visual_QA_scope="source pixel, hash, grid and mask area verified at listed sample frames; no human image review yet")
    target = HERE / "ASSET_INVENTORY.json"
    assert not target.exists(), target
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(result["status"], result["development"]["frames"], result["validation"]["frames"])


if __name__ == "__main__":
    main()
