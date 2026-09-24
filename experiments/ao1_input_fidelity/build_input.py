"""Build query-causal, pixel-faithful AO1 media from real RGB and predicted masks.

Media are private outputs. This module never reads GT or calls a model.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
from pycocotools import mask as mask_api


AO0_FRAMES = (1300, 1321, 1322, 1343, 1359, 1419, 1484, 1490, 1498)
AO0_ROLES = (("R1", 1300, 1), ("R2", 1300, 4),
             ("Q1", 1498, 1), ("Q2", 1498, 4))


def digest(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def selected(path: Path, frames: set[int]) -> dict[int, dict]:
    found = {}
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for row in map(json.loads, handle):
            if row["frame"] in frames:
                assert row["frame"] not in found
                found[row["frame"]] = row
    assert set(found) == frames, (path, sorted(frames - set(found)))
    return found


def validate_frame(frame: int, observation: dict, assignment: dict,
                   manifest: list[dict], dataset: Path, cutoff: float,
                   offset: int = 9300, cutoff_frame: int = 1498) -> tuple[np.ndarray, dict]:
    assert frame <= cutoff_frame, (frame, cutoff_frame, "FUTURE_FRAME")
    assert observation["frame"] == assignment["frame"] == frame
    assert observation["time"] == assignment["time"] <= cutoff
    global_frame = observation["global_frame"]
    assert global_frame == frame + offset and global_frame >= 2
    source = manifest[global_frame - 2]
    assert source["frame_id"] + 1 == global_frame
    assert abs(source["color_timestamp_us"] / 1e6 - observation["time"]) < .002
    path = dataset / source["rgb_original"]
    assert path.is_file() and digest(path) == source["source_rgb_sha256"]
    rgb = cv2.imread(str(path), cv2.IMREAD_COLOR)
    assert rgb is not None and rgb.shape == (1080, 1920, 3)
    return rgb, dict(frame=frame, global_frame=global_frame, source_time=observation["time"],
                     rgb_path=str(path), rgb_sha256=digest(path), rgb_size=[1920, 1080])


def decode_mask(assignment: dict, observation: dict, native: int) -> np.ndarray:
    encoded = assignment["masks"][f"n:{native}"]
    mask = mask_api.decode(dict(size=encoded["size"], counts=encoded["counts"].encode("ascii")))
    assert mask.shape == (360, 640)
    area = next(x["area"] for x in observation["observations"] if x["id"] == native)
    assert int(mask.sum()) == area
    return mask


def save_exact_crop(rgb: np.ndarray, mask: np.ndarray, xyxy: list[int], path: Path) -> dict:
    x0, y0, x1, y1 = xyxy
    assert 0 <= x0 < x1 <= 640 and 0 <= y0 < y1 <= 360
    source_xyxy = [x0 * 3, y0 * 3, x1 * 3, y1 * 3]
    sx0, sy0, sx1, sy1 = source_xyxy
    crop = rgb[sy0:sy1, sx0:sx1].copy()
    assert crop.size and np.array_equal(crop, rgb[sy0:sy1, sx0:sx1])
    assert cv2.imwrite(str(path), crop)
    decoded = cv2.imread(str(path), cv2.IMREAD_COLOR)
    assert decoded is not None and np.array_equal(decoded, crop)
    return dict(private_path=str(path), sha256=digest(path), bytes=path.stat().st_size,
                mask_xyxy=xyxy, rgb_xyxy=source_xyxy, crop_size=[crop.shape[1], crop.shape[0]],
                mask_area=int(mask.sum()), pixel_exact=True, colored=False, upsampled=False)


def pilot(args: argparse.Namespace) -> None:
    assert args.private_output.is_dir() and not any(args.private_output.iterdir())
    index = json.loads(args.ao0_index.read_text(encoding="utf-8"))
    by_role = {(r["role"], r["frame"]): r for r in index["records"] if "role" in r}
    frames = {frame for _, frame, _ in AO0_ROLES} | {1359}
    observations = selected(args.observations, frames)
    masks = selected(args.masks, frames)
    manifest = [json.loads(line) for line in (args.dataset / "manifest.jsonl").read_text().splitlines()]
    cutoff = observations[1498]["time"]
    assert cutoff == 1787709101.092
    results = []
    for role, frame, native in AO0_ROLES:
        rgb, source = validate_frame(frame, observations[frame], masks[frame], manifest, args.dataset,
                                     cutoff, cutoff_frame=1498)
        mask = decode_mask(masks[frame], observations[frame], native)
        old = by_role[("R-A" if role == "R1" else "R-B" if role == "R2" else
                       "C-X" if role == "Q1" else "C-Y", frame)]
        out = save_exact_crop(rgb, mask, old["crop_xyxy"], args.private_output / f"{role}.png")
        results.append(dict(role=role, native_mask_key=f"n:{native}", **source, **out))
    rgb, source = validate_frame(1359, observations[1359], masks[1359], manifest, args.dataset,
                                 cutoff, cutoff_frame=1498)
    for native in (1, 4):
        decode_mask(masks[1359], observations[1359], native)
    contact = save_exact_crop(rgb, decode_mask(masks[1359], observations[1359], 1),
                              index["local_contact_xyxy"], args.private_output / "contact.png")
    results.append(dict(role="CONTACT", **source, **contact))
    output = dict(status="PILOT_REAL_PIXEL_EXACT", query_frame=1498, query_time=cutoff,
                  source_mask_size=[640, 360], source_rgb_size=[1920, 1080], scale_xy=[3, 3],
                  frames=results, GT_read=False, external_model_api_calls=0)
    assert not args.public_output.exists()
    args.public_output.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(dict(status=output["status"], crops=len(results), query_time=cutoff)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--pilot", action="store_true", required=True)
    for name in ("observations", "masks", "dataset", "ao0-index", "private-output", "public-output"):
        parser.add_argument("--" + name, type=Path, required=True)
    pilot(parser.parse_args())
