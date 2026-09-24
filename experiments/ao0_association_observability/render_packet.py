"""Private RGB/predicted-mask packet, strictly at or before the AO0 query."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
from pycocotools import mask as mu

HERE = Path(__file__).resolve().parent
FRAMES = (1300, 1321, 1322, 1343, 1359, 1419, 1484, 1490, 1498)
CONTACT = (1322, 1343, 1359, 1419)
FISH = (("R-A", 1300, 1), ("R-A", 1321, 1), ("R-B", 1300, 4), ("R-B", 1321, 4),
        ("C-X", 1484, 1), ("C-X", 1490, 1), ("C-X", 1498, 1),
        ("C-Y", 1484, 4), ("C-Y", 1490, 4), ("C-Y", 1498, 4))


def sha(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def selected(path):
    result = {}
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for item in map(json.loads, handle):
            if item["frame"] in FRAMES:
                result[item["frame"]] = item
    assert set(result) == set(FRAMES)
    return result


def fitted(image, width=300, height=220):
    h, w = image.shape[:2]
    scale = min(width / w, height / h)
    resized = cv2.resize(image, (max(1, round(w * scale)), max(1, round(h * scale))))
    canvas = np.full((height, width, 3), 235, np.uint8)
    top, left = (height - resized.shape[0]) // 2, (width - resized.shape[1]) // 2
    canvas[top:top + resized.shape[0], left:left + resized.shape[1]] = resized
    return canvas


def main(args):
    assert args.private_output.is_dir() and args.private_output != HERE
    observations, masks = selected(args.observations), selected(args.masks)
    manifest = [json.loads(line) for line in (args.dataset / "manifest.jsonl").read_text().splitlines()]
    rgb = {}
    records = []
    for frame in FRAMES:
        global_frame = observations[frame]["global_frame"]
        assert global_frame <= 10798 and global_frame == masks[frame]["frame"] + 9300
        source = manifest[global_frame - 2]
        assert source["frame_id"] + 1 == global_frame
        path = args.dataset / source["rgb_original"]
        assert sha(path) == source["source_rgb_sha256"]
        image = cv2.imread(str(path))
        assert image is not None
        rgb[frame] = cv2.resize(image, (640, 360))
        records.append(dict(frame=frame, global_frame=global_frame, time=observations[frame]["time"],
                            RGB_sha256=sha(path), private_RGB_path=str(path)))
    full = np.full((3 * 250, 4 * 300, 3), 245, np.uint8)
    for index, (label, frame, native) in enumerate(FISH):
        obs = next(x for x in observations[frame]["observations"] if x["id"] == native)
        key = f"n:{native}"
        encoded = masks[frame]["masks"][key]
        mask = mu.decode(dict(size=encoded["size"], counts=encoded["counts"].encode("ascii"))).astype(bool)
        assert int(mask.sum()) == int(obs["area"])
        x1, y1, x2, y2 = map(int, obs["box"])
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        dx, dy = max(60, int((x2 - x1) * 1.4)), max(45, int((y2 - y1) * 1.4))
        xa, xb = max(0, cx - dx), min(640, cx + dx)
        ya, yb = max(0, cy - dy), min(360, cy + dy)
        crop = rgb[frame][ya:yb, xa:xb].copy()
        region = mask[ya:yb, xa:xb]
        crop[region] = (crop[region] * .65 + np.array([0, 0, 255]) * .35).astype(np.uint8)
        tile = fitted(crop)
        row, col = divmod(index, 4)
        full[row * 250 + 30:row * 250 + 250, col * 300:(col + 1) * 300] = tile
        relative = observations[frame]["time"] - observations[1322]["time"]
        cv2.putText(full, f"{label} f{frame} t{relative:+.2f}s", (col * 300 + 8, row * 250 + 20),
                    cv2.FONT_HERSHEY_SIMPLEX, .55, (0, 0, 0), 1, cv2.LINE_AA)
        records.append(dict(role=label, frame=frame, mask_key=key, predicted_mask_area=int(mask.sum()),
                            source_RLE_sha256=hashlib.sha256(json.dumps(encoded, sort_keys=True).encode()).hexdigest(),
                            crop_xyxy=[xa, ya, xb, yb]))
    box = [next(x for x in observations[frame]["observations"] if x["id"] == native)["box"]
           for frame in CONTACT for native in (1, 4)]
    bounds = [max(0, int(min(b[0] for b in box)) - 45), max(0, int(min(b[1] for b in box)) - 35),
              min(640, int(max(b[2] for b in box)) + 45), min(360, int(max(b[3] for b in box)) + 35)]
    interaction = np.full((2 * 300, 2 * 480, 3), 245, np.uint8)
    for index, frame in enumerate(CONTACT):
        xa, ya, xb, yb = bounds
        local = rgb[frame][ya:yb, xa:xb].copy()
        for native in (1, 4):
            encoded = masks[frame]["masks"][f"n:{native}"]
            mask = mu.decode(dict(size=encoded["size"], counts=encoded["counts"].encode("ascii"))).astype(bool)
            region = mask[ya:yb, xa:xb]
            local[region] = (local[region] * .7 + np.array([0, 0, 255]) * .3).astype(np.uint8)
        row, col = divmod(index, 2)
        interaction[row * 300 + 30:row * 300 + 300, col * 480:(col + 1) * 480] = fitted(local, 480, 270)
        relative = observations[frame]["time"] - observations[1322]["time"]
        cv2.putText(interaction, f"contact f{frame} t{relative:+.2f}s", (col * 480 + 8, row * 300 + 20),
                    cv2.FONT_HERSHEY_SIMPLEX, .55, (0, 0, 0), 1, cv2.LINE_AA)
    paths = [args.private_output / "ao0_whole_fish.png", args.private_output / "ao0_interaction_local.png"]
    assert not any(path.exists() for path in paths)
    assert cv2.imwrite(str(paths[0]), full) and cv2.imwrite(str(paths[1]), interaction)
    output = dict(status="REAL_RGB_PREDICTED_MASK_QUERY_CUTOFF", reviewer_labels_only=True,
                  cutoff_frame=1498, local_contact_xyxy=bounds, records=records,
                  private_images=[dict(path=str(path), bytes=path.stat().st_size, sha256=sha(path)) for path in paths],
                  GT_read=False, future_read=False, pixel_files_not_for_Git=True)
    index_path = HERE / "VISUAL_INPUT_INDEX.json"
    assert not index_path.exists()
    index_path.write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps(dict(image_count=len(paths), frame_count=len(FRAMES), cutoff=1498)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for name in ("observations", "masks", "dataset", "private-output"):
        parser.add_argument("--" + name, type=Path, required=True)
    main(parser.parse_args())
