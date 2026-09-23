"""Verify four old harm sheets against real RGB, predicted RLE and feature streams."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path

import cv2
from pycocotools import mask as mask_api

HERE = Path(__file__).resolve().parent
E1 = HERE.parent / "vl_assoc_e1"
IDS = ("P4218132a1659f1e2", "P04c303d9612421d6", "P175d295a01799fe5", "P1797ad89bd359331")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def needed(path, frames, offset=0):
    output = {}
    with gzip.open(path, "rt") as handle:
        for line in handle:
            row = json.loads(line)
            frame = row["frame"] if "frame" in row else row["global_frame"] - offset
            if frame in frames:
                output[frame] = row
    assert set(output) == frames
    return output


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--data", type=Path, required=True)
    p.add_argument("--old-images", type=Path, required=True)
    for split in ("development", "validation"):
        for field in ("masks", "baseline", "depth", "appearance"):
            p.add_argument(f"--{split}-{field}", type=Path, required=True)
    args = p.parse_args()
    manifest = [json.loads(x) for x in (args.data / "manifest.jsonl").read_text().splitlines()]
    audits = {x["packet_id"]: x for x in map(json.loads, (E1 / "CANDIDATE_AUDIT.jsonl").read_text().splitlines())}
    episodes = {x["packet_id"]: x for x in map(json.loads, (E1 / "EPISODES.jsonl").read_text().splitlines())}
    packets = {ident: json.loads((E1 / "packets" / f"{ident}.json").read_text()) for ident in IDS}
    output = []
    for split in ("development", "validation"):
        these = [ident for ident in IDS if episodes[ident]["split"] == split]
        frames = {row["global_frame"] - (9300 if split == "validation" else 0)
                  for ident in these for row in audits[ident]["visuals"]["temporal"]["rows"]}
        sources = {field: needed(getattr(args, f"{split}_{field}"), frames,
                                 9300 if split == "validation" else 0)
                   for field in ("masks", "baseline", "depth", "appearance")}
        for ident in these:
            packet, episode, audit = packets[ident], episodes[ident], audits[ident]
            alias_public = {v: int(k) for k, v in episode["source_aliases"]["identity_alias"].items()}
            alias_native = {v: int(k) for k, v in episode["source_aliases"]["native_alias"].items()}
            sheet_path = args.old_images / f"{ident}_temporal.png"
            assert sha(sheet_path) == audit["visuals"]["temporal"]["sha256"]
            sheet = cv2.imread(str(sheet_path))
            assert sheet is not None and [sheet.shape[1], sheet.shape[0]] == [512, audit["visuals"]["temporal"]["height"]]
            for visual in audit["visuals"]["temporal"]["rows"]:
                global_frame = visual["global_frame"]
                frame = global_frame - (9300 if split == "validation" else 0)
                source = manifest[global_frame - 2]
                assert source["frame_id"] + 1 == global_frame
                rgb = args.data / source["rgb_original"]
                assert sha(rgb) == visual["RGB_sha256"] == source["source_rgb_sha256"]
                image = cv2.imread(str(rgb))
                assert image is not None and [image.shape[1], image.shape[0]] == visual["RGB_size"]
                label = visual["label"]
                if label in alias_public:
                    public = alias_public[label]
                    owner = [int(x["mask"].split(":")[1]) for x in sources["baseline"][frame]["variants"]["Z4Q_STABLE"]
                             if x["id"] == public]
                    assert len(owner) == 1
                    native = owner[0]
                else:
                    native = alias_native[label]
                mask_key = f"n:{native}"
                encoded = sources["masks"][frame]["masks"][mask_key]
                mask = mask_api.decode(dict(size=encoded["size"], counts=encoded["counts"].encode("ascii")))
                assert hashlib.sha256(mask.tobytes()).hexdigest() == visual["mask_sha256"]
                assert int(mask.sum()) == visual["native_mask_area"]
                assert [mask.shape[1], mask.shape[0]] == visual["mask_size"]
                assert sources["masks"][frame]["time"] == visual["source_time"]
                dep = next(x for x in sources["depth"][frame]["observations"] if x["mask"] == mask_key)
                feat = next(x for x in sources["appearance"][frame]["obs"] if x["mask"] == mask_key)
                assert dep["area"] == feat["area"] == visual["native_mask_area"]
            output.append(dict(packet_id=ident, split=split, query_frame=episode["query_frame"],
                               sheet_sha256=audit["visuals"]["temporal"]["sha256"],
                               rows_verified=len(audit["visuals"]["temporal"]["rows"]),
                               result="RGB_MASK_DEPTH_APPEARANCE_SOURCE_BOUND"))
    result = dict(status="FOUR_OLD_HARM_VISUAL_SOURCES_VERIFIED", packet_count=len(output),
                  rows_verified=sum(x["rows_verified"] for x in output), items=output,
                  limits="Machine binding and human inspection of four temporal sheets; not new E1C packet QA or identity ground truth.")
    out = HERE / "PRIVATE_VISUAL_QA.json"
    assert not out.exists()
    out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
