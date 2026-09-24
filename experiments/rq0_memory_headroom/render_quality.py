"""Render private prediction-only RGB/mask QA sheets outside Git."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
from pycocotools import mask as mu


def sha(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def frame_rows(path, needed):
    result = {}
    with gzip.open(path, "rt") as handle:
        for line in handle:
            row = json.loads(line)
            if row["frame"] in needed:
                result[row["frame"]] = row
    assert set(result) == needed
    return result


def tile(item, source, mask):
    rgb = cv2.imread(str(source))
    assert rgb is not None
    rgb = cv2.resize(rgb, (mask.shape[1], mask.shape[0]))
    x1, y1, x2, y2 = map(int, item["box"])
    full = rgb.copy()
    cv2.rectangle(full, (x1, y1), (x2, y2), (0, 255, 255), 2)
    full = cv2.resize(full, (300, 200))
    cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
    span_x = max(80, int((x2 - x1) * 1.6))
    span_y = max(60, int((y2 - y1) * 1.6))
    xa, xb = max(0, cx - span_x), min(rgb.shape[1], cx + span_x)
    ya, yb = max(0, cy - span_y), min(rgb.shape[0], cy + span_y)
    crop = rgb[ya:yb, xa:xb].copy()
    region = mask[ya:yb, xa:xb].astype(bool)
    color = np.zeros_like(crop); color[:, :, 2] = 255
    crop[region] = (0.55 * crop[region] + 0.45 * color[region]).astype(np.uint8)
    crop = cv2.resize(crop, (300, 200))
    panel = np.full((240, 600, 3), 245, np.uint8)
    panel[30:230, :300] = full
    panel[30:230, 300:] = crop
    cv2.putText(panel, f'{item["split"]} f{item["frame"]} n{item["native_id"]} p{item["public_id"]}',
                (5, 20), cv2.FONT_HERSHEY_SIMPLEX, .5, (0, 0, 0), 1, cv2.LINE_AA)
    return panel


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--masks", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--private-output", type=Path, required=True)
    args = parser.parse_args()
    assert args.private_output.is_dir()
    selection = json.loads(args.selection.read_text())
    items = sorted(selection["selected"], key=lambda x: (x["frame"], x["native_id"]))
    masks = frame_rows(args.masks, {x["frame"] for x in items})
    manifest = [json.loads(line) for line in (args.dataset / "manifest.jsonl").read_text().splitlines()]
    tiles, records = [], []
    for item in items:
        global_frame = item["global_frame"]
        source = manifest[global_frame - 2]
        assert source["frame_id"] + 1 == global_frame
        rgb_path = args.dataset / source["rgb_original"]
        assert sha(rgb_path) == source["source_rgb_sha256"]
        key = f'n:{item["native_id"]}'
        encoded = masks[item["frame"]]["masks"][key]
        image_mask = mu.decode(dict(size=encoded["size"], counts=encoded["counts"].encode("ascii")))
        assert int(image_mask.sum()) == int(item["area"])
        tiles.append(tile(item, rgb_path, image_mask))
        records.append(dict(observation_key=item["observation_key"], global_frame=global_frame,
                            rgb_sha256=sha(rgb_path), mask_area=int(image_mask.sum())))
    sheets = []
    for i in range(0, len(tiles), 6):
        canvas = np.full((720, 1200, 3), 245, np.uint8)
        for j, panel in enumerate(tiles[i:i + 6]):
            y, x = divmod(j, 2)
            canvas[y * 240:(y + 1) * 240, x * 600:(x + 1) * 600] = panel
        path = args.private_output / f'{selection["split"]}_{i // 6:02d}.png'
        assert not path.exists()
        assert cv2.imwrite(str(path), canvas)
        sheets.append(dict(path=str(path), sha256=sha(path), observation_keys=[x["observation_key"] for x in items[i:i + 6]]))
    report = dict(split=selection["split"], selection_sha256=sha(args.selection),
                  mask_source_sha256=sha(args.masks), records=records, sheets=sheets,
                  GT_read=False, private_pixels_not_in_repo=True)
    path = args.private_output / f'{selection["split"]}_render_manifest.json'
    assert not path.exists()
    path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"split": selection["split"], "tiles": len(tiles), "sheets": len(sheets)}))


if __name__ == "__main__":
    main()
