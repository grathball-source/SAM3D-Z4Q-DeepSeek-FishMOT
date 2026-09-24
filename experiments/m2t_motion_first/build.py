"""Build M2-T anonymous mask-time packets from the sealed AO1 sources, never GT."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import os
import random
from pathlib import Path

import cv2
import numpy as np
from pycocotools import mask as mask_api

SEED = 20260924_2
CAP = 65536
PRICE_IN, PRICE_OUT = 0.30, 1.20
ARMS = ("G-SEQ", "G-SEQ-REPEAT", "G+AP", "G+AP-REPEAT", "G-END")
EDGES = ("A-X", "A-Y", "B-X", "B-Y")


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def encoded(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()


def save(path: Path, value: object) -> None:
    assert not path.exists(), path
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def stream_rows(path: Path, wanted: set[int]) -> dict[int, dict]:
    found = {}
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for row in map(json.loads, stream):
            frame = row["frame"]
            if frame in wanted:
                assert frame not in found
                found[frame] = row
    assert set(found) == wanted, (path, sorted(wanted - set(found)))
    return found


def uniform_frames(start: int, end: int) -> list[int]:
    assert start <= end
    length = end - start + 1
    count = min(32, length)
    if count == 1:
        return [start]
    frames = sorted({start + ((end - start) * i + (count - 1) // 2) // (count - 1)
                     for i in range(count)})
    assert len(frames) == count and frames[0] == start and frames[-1] == end
    return frames


def case_frames(case: dict) -> tuple[list[int], list[int], list[int]]:
    start, end = case["v2_window"]
    assert end == case["query_frame"]
    sampled = uniform_frames(start, end)
    endpoint = sorted({row["frame"] for row in case["V1"]["roles"]})
    assert max(endpoint) <= end
    return sorted(set(sampled) | set(endpoint)), sampled, endpoint


def decode_all(observation: dict, assignment: dict, source: dict) -> dict[str, np.ndarray]:
    assert observation["frame"] == assignment["frame"] == source["frame"]
    assert observation["time"] == assignment["time"] == source["source_time"]
    source_hashes = {x["mask_key"]: x["rle_sha256"] for x in source["predicted_masks"]}
    assert source_hashes.keys() == {key for key in assignment["masks"] if key.startswith("n:")}
    areas = {f'n:{row["id"]}': row["area"] for row in observation["observations"]}
    masks = {}
    for key, rle in assignment["masks"].items():
        if not key.startswith("n:"):
            continue
        assert hashlib.sha256(json.dumps(rle, sort_keys=True).encode()).hexdigest() == source_hashes[key]
        mask = mask_api.decode(dict(size=rle["size"], counts=rle["counts"].encode("ascii")))
        assert mask.shape == (360, 640)
        if key in areas:
            assert int(mask.sum()) == areas[key]
        masks[key] = mask.astype(bool)
    return masks


def bounds(mask: np.ndarray) -> tuple[int, int, int, int] | None:
    yy, xx = np.nonzero(mask)
    return (int(xx.min()), int(yy.min()), int(xx.max()) + 1, int(yy.max()) + 1) if len(xx) else None


def fixed_roi(case: dict, frames: list[int], masks: dict[int, dict[str, np.ndarray]]) -> list[int]:
    participating = {row["native_mask_key"] for row in case["V1"]["roles"]}
    boxes = [box for frame in frames for key in participating
             if key in masks[frame] for box in [bounds(masks[frame][key])] if box]
    assert boxes, (case["case_alias"], "NO_PARTICIPATING_PREDICTION")
    x0, y0 = min(x[0] for x in boxes), min(x[1] for x in boxes)
    x1, y1 = max(x[2] for x in boxes), max(x[3] for x in boxes)
    pad_x, pad_y = math.ceil(.2 * (x1 - x0)), math.ceil(.2 * (y1 - y0))
    roi = [max(0, x0 - pad_x), max(0, y0 - pad_y), min(640, x1 + pad_x), min(360, y1 + pad_y)]
    assert roi[0] < roi[2] and roi[1] < roi[3]
    for role in case["V1"]["roles"]:
        box = bounds(masks[role["frame"]][role["native_mask_key"]])
        assert box and roi[0] <= box[0] and roi[1] <= box[1] and box[2] <= roi[2] and box[3] <= roi[3]
    return roi


def aliases(cases: list[dict]) -> dict[str, dict[str, str]]:
    combinations = [(False, False), (True, False), (False, True), (True, True), (False, False)]
    random.Random(SEED).shuffle(combinations)
    result = {}
    for case, (swap_history, swap_current) in zip(cases, combinations, strict=True):
        mapping = {"A": "B" if swap_history else "A", "B": "A" if swap_history else "B",
                   "X": "Y" if swap_current else "X", "Y": "X" if swap_current else "Y"}
        result[case["case_alias"]] = mapping  # visible alias -> original AO1 role
    return result


def candidate_map(card: dict, visible_to_original: dict[str, str]) -> dict[str, str]:
    options = card["candidate_hypotheses"]
    assert len(options) == 2 and {x["choice"] for x in options} == {"C1", "C2"}
    expected = {}
    for label, pairing in (("STRAIGHT", {"X": "A", "Y": "B"}),
                           ("CROSSED", {"X": "B", "Y": "A"})):
        physical = {visible_to_original[current]: visible_to_original[history]
                    for current, history in pairing.items()}
        matches = [x["choice"] for x in options if all(x["mapping"][cur] == ref
                                                     for cur, ref in physical.items())]
        assert len(matches) == 1, (label, physical, options)
        expected[label] = matches[0]
    assert expected["STRAIGHT"] != expected["CROSSED"]
    return expected


def render_frame(frame: int, ordinal: int, roi: list[int], masks: dict[str, np.ndarray],
                 original_to_visible: dict[str, str], roles: list[dict], time: float,
                 query_time: float, media: Path) -> tuple[dict, dict, dict]:
    x0, y0, x1, y1 = roi
    height, width = y1 - y0, x1 - x0
    canvas = np.full((height, width, 3), 255, np.uint8)
    found = []
    for key, whole in masks.items():
        crop = whole[y0:y1, x0:x1]
        box = bounds(crop)
        if box:
            found.append((key, crop, box))
    found.sort(key=lambda item: ((item[2][0] + item[2][2]), (item[2][1] + item[2][3]), item[0]))
    for _, crop, _ in found:
        canvas[crop] = (172, 172, 172)
    public_obs, private_obs = [], []
    for i, (key, crop, box) in enumerate(found, 1):
        contours, _ = cv2.findContours(crop.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(canvas, contours, -1, (72, 72, 72), 1)
        token = f"f{ordinal:03d}:o{i:02d}"
        yy, xx = np.nonzero(crop)
        cx, cy = float(xx.mean()), float(yy.mean())
        label_roles = [original_to_visible[row["role"]] for row in roles
                       if row["frame"] == frame and row["native_mask_key"] == key]
        cv2.putText(canvas, token, (max(1, int(cx) - 28), max(12, int(cy))),
                    cv2.FONT_HERSHEY_SIMPLEX, .30, (0, 0, 0), 1, cv2.LINE_AA)
        entry = dict(token=token, center_norm=[round(cx / width, 5), round(cy / height, 5)],
                     bbox_norm=[round(box[0] / width, 5), round(box[1] / height, 5),
                                round(box[2] / width, 5), round(box[3] / height, 5)],
                     area_fraction=round(int(crop.sum()) / (width * height), 6),
                     endpoint_roles=sorted(label_roles))
        public_obs.append(entry)
        private_obs.append(dict(**entry, native_mask_key=key, mask_pixels=int(whole.sum())))
    assert np.array_equal(canvas[:, :, 0], canvas[:, :, 1]) and np.array_equal(canvas[:, :, 1], canvas[:, :, 2])
    ok, buffer = cv2.imencode(".png", canvas)
    assert ok
    raw = buffer.tobytes()
    image_hash = hashlib.sha256(raw).hexdigest()
    target = media / (image_hash + ".png")
    if not target.exists():
        target.write_bytes(raw)
    assert digest(target) == image_hash
    image_id = f"G{ordinal:03d}"
    image = dict(image_id=image_id, kind="G", media_file=target.name, sha256=image_hash,
                 bytes=len(raw), width=width, height=height, relative_seconds=round(time - query_time, 3),
                 observation_tokens=[x["token"] for x in public_obs])
    visible = dict(image_id=image_id, frame_token=f"f{ordinal:03d}",
                   relative_seconds=round(time - query_time, 3), observations=public_obs,
                   no_interpolation=True, no_persistent_identity=True)
    private = dict(frame=frame, source_time=time, image_sha256=image_hash,
                   observations=private_obs)
    return image, visible, private


def appearance(case: dict, alias: dict[str, str], blind: Path, media: Path,
               source: dict[int, dict]) -> list[dict]:
    base = blind / case["case_alias"] / case["V1"]["version_alias"]
    original_to_visible = {old: new for new, old in alias.items()}
    output = []
    for i, row in enumerate(case["V1"]["roles"]):
        file = base / f"r{i:02d}.png"
        assert digest(file) == row["crop_sha256"] and row["crop_pixel_exact"]
        original = source[row["frame"]]
        assert digest(Path(original["rgb_path"])) == original["rgb_sha256"]
        rgb = cv2.imread(original["rgb_path"], cv2.IMREAD_COLOR)
        crop = cv2.imread(str(file), cv2.IMREAD_COLOR)
        x0, y0, x1, y1 = row["rgb_xyxy"]
        assert np.array_equal(rgb[y0:y1, x0:x1], crop)
        target = media / (row["crop_sha256"] + ".png")
        if not target.exists():
            os.link(file, target)
        assert digest(target) == row["crop_sha256"]
        output.append(dict(image_id=f"AP{i+1:03d}", kind="AP", media_file=target.name,
                           sha256=row["crop_sha256"], bytes=target.stat().st_size,
                           width=crop.shape[1], height=crop.shape[0],
                           relative_seconds=round(row["source_time"] - case["query_time"], 3),
                           endpoint_role=original_to_visible[row["role"]]))
    return output


def numeric_motion(case: dict, alias: dict[str, str], masks: dict[int, dict[str, np.ndarray]],
                   roi: list[int]) -> dict:
    original_to_visible = {old: new for new, old in alias.items()}
    samples = {role: [] for role in ("A", "B", "X", "Y")}
    for row in case["V1"]["roles"]:
        mask = masks[row["frame"]][row["native_mask_key"]]
        yy, xx = np.nonzero(mask)
        samples[original_to_visible[row["role"]]].append((row["source_time"],
                                                            np.array([xx.mean(), yy.mean()])))
    counts = {role: len({x[0] for x in rows}) for role, rows in samples.items()}
    if any(n < 3 for n in counts.values()):
        return dict(status="UNAVAILABLE", reason="FEWER_THAN_THREE_DISTINCT_TIMES", counts=counts)
    fitted = {}
    for role, values in samples.items():
        values.sort(key=lambda x: x[0])
        times = np.array([x[0] for x in values], dtype=float)
        points = np.stack([x[1] for x in values])
        relative = times - times[0]
        centered = relative - relative.mean()
        denom = float(np.dot(centered, centered))
        assert denom > 0
        velocity = (centered[:, None] * (points - points.mean(axis=0))).sum(axis=0) / denom
        fitted[role] = dict(t_first=float(times[0]), t_last=float(times[-1]),
                            p_first=points[0], p_last=points[-1], velocity=velocity)
    diagonal = math.hypot(roi[2] - roi[0], roi[3] - roi[1])
    costs = {}
    for old in ("A", "B"):
        for current in ("X", "Y"):
            a, b = fitted[old], fitted[current]
            dt = b["t_first"] - a["t_last"]
            assert dt > 0, (case["case_alias"], old, current, dt)
            residual = (np.linalg.norm(b["p_first"] - a["p_last"] - a["velocity"] * dt) +
                        np.linalg.norm(a["p_last"] - b["p_first"] + b["velocity"] * dt))
            costs[f"{old}-{current}"] = float(residual / (2 * diagonal))
    straight, crossed = costs["A-X"] + costs["B-Y"], costs["A-Y"] + costs["B-X"]
    choice = "TIE" if straight == crossed else "STRAIGHT" if straight < crossed else "CROSSED"
    return dict(status="AVAILABLE", counts=counts, edge_costs=costs,
                candidate_costs={"STRAIGHT": straight, "CROSSED": crossed}, choice=choice,
                definition="Least-squares last-reference and first-current velocities; true dt; no middle frames; ROI diagonal")


def build_case(case: dict, alias: dict[str, str], rows: dict[str, dict[int, dict]],
               blind: Path, out: Path) -> dict:
    frames, sampled, endpoint = case_frames(case)
    source = {x["frame"]: x for x in case["source_by_frame"]}
    assert set(frames) <= set(source) and max(frames) == case["query_frame"]
    masks = {}
    for frame in frames:
        observed = rows[case["split"]]["observations"][frame]
        assignment = rows[case["split"]]["masks"][frame]
        frozen = source[frame]
        assert frozen["source_time"] <= case["query_time"] and frame <= case["query_frame"]
        assert assignment["time"] == frozen["assignment_time"]
        masks[frame] = decode_all(observed, assignment, frozen)
    roi = fixed_roi(case, frames, masks)
    reverse = {old: new for new, old in alias.items()}
    images, visible, private = [], [], []
    for ordinal, frame in enumerate(frames, 1):
        image, model_row, audit_row = render_frame(frame, ordinal, roi, masks[frame], reverse,
                                                   case["V1"]["roles"], source[frame]["source_time"],
                                                   case["query_time"], out / "sender/media")
        images.append(image)
        visible.append(model_row)
        private.append(audit_row)
    ap = appearance(case, alias, blind, out / "sender/media", source)
    original_to_visible = {old: new for new, old in alias.items()}
    card_path = blind / case["case_alias"] / case["V0"]["version_alias"] / "card.json"
    candidates = candidate_map(json.loads(card_path.read_text(encoding="utf-8")), alias)
    endpoint_set = set(endpoint)
    assert all(role in {r for frame in visible for obs in frame["observations"]
                        for r in obs["endpoint_roles"]} for role in ("A", "B", "X", "Y"))
    records = []
    for arm in ARMS:
        has_middle = arm != "G-END"
        g_images = [image for image, frame in zip(images, frames, strict=True)
                    if has_middle or frame in endpoint_set]
        g_rows = [row for row, frame in zip(visible, frames, strict=True)
                  if has_middle or frame in endpoint_set]
        for i, row in enumerate(g_rows):
            row = dict(row)
            row["delta_previous_seconds"] = (None if i == 0 else
                round(row["relative_seconds"] - g_rows[i-1]["relative_seconds"], 3))
            g_rows[i] = row
        edge_order = list(EDGES)
        random.Random(SEED + int(case["case_alias"][1:])).shuffle(edge_order)
        request_id = f"M2T-{case['case_alias']}"
        core = dict(request_id=request_id, task="Jointly evaluate all four anonymous temporal identity edges.",
                    edge_order=edge_order, scene_frames=g_rows,
                    endpoint_roles={role: [dict(image_id=row["image_id"], token=obs["token"],
                                                relative_seconds=row["relative_seconds"])
                                            for row in g_rows for obs in row["observations"]
                                            if role in obs["endpoint_roles"]]
                                    for role in ("A", "B", "X", "Y")},
                    note="Local o tokens reset every frame; equal indices do not mean the same fish. "
                         "Predicted-mask proximity is occlusion risk, not proven physical contact. "
                         "No unseen intermediate observations may be inferred as continuous visibility.")
        core_text = encoded(core).decode()
        use_ap = arm in ("G+AP", "G+AP-REPEAT")
        ap_text = (encoded(dict(appearance_reference_only=True,
                                note="These RGB crops are the original frozen endpoint appearance, not verified identity markers. Static marks alone cannot decide an edge.",
                                images=[dict(image_id=x["image_id"], endpoint_role=x["endpoint_role"],
                                             relative_seconds=x["relative_seconds"]) for x in ap])).decode()
                   if use_ap else None)
        records.append(dict(attempt_id=f"{case['case_alias']}-{arm}", case_alias=case["case_alias"],
                            arm=arm, request_id=request_id, core_text=core_text, ap_text=ap_text,
                            images=g_images + (ap if use_ap else [])))
    assert records[0]["core_text"] == records[1]["core_text"]
    assert records[2]["core_text"] == records[3]["core_text"] == records[0]["core_text"]
    assert records[0]["images"] == records[1]["images"]
    assert records[2]["images"] == records[3]["images"]
    assert records[0]["images"] == records[2]["images"][:len(records[0]["images"])], "G_PLUS_AP_CHANGED_G"
    assert all(image["kind"] == "G" for image in records[4]["images"])
    numeric = numeric_motion(case, alias, masks, roi)
    return dict(case_alias=case["case_alias"], query_frame=case["query_frame"],
                query_time=case["query_time"], split=case["split"], original_case_id=case["case_id"],
                roi_mask_xyxy=roi, roi_rgb_xyxy=[v * 3 for v in roi],
                sampled_window_frames=sampled, endpoint_frames=endpoint, all_frames=frames,
                alias_to_AO1_role=alias, candidate_to_AO1_choice=candidates,
                source_rows=[dict(frame=frame, source_time=source[frame]["source_time"],
                                  rgb_path=source[frame]["rgb_path"], rgb_sha256=source[frame]["rgb_sha256"],
                                  predicted_masks=source[frame]["predicted_masks"])
                             for frame in frames],
                g_images=images, ap_images=ap, private_token_ledger=private,
                visible_frames=visible, numeric_motion=numeric, requests=records)


def reserve(request: dict) -> float:
    text_bytes = len(request["core_text"].encode()) + len((request["ap_text"] or "").encode())
    return ((text_bytes + 4096 + 1024 * len(request["images"])) * PRICE_IN +
            CAP * PRICE_OUT) / 1e6


def schedule(requests: list[dict]) -> list[dict]:
    remaining = list(requests)
    output = []
    rng = random.Random(SEED)
    dependencies = {"G-SEQ-REPEAT": "G-SEQ", "G+AP-REPEAT": "G+AP"}
    while remaining:
        completed = {(x["case_alias"], x["arm"]) for x in output}
        eligible = [x for x in remaining if x["arm"] not in dependencies or
                    (x["case_alias"], dependencies[x["arm"]]) in completed]
        chosen = rng.choice(eligible)
        output.append(chosen)
        remaining.remove(chosen)
    return output


def main(args: argparse.Namespace) -> None:
    source_path = args.source
    source = json.loads(source_path.read_text(encoding="utf-8"))
    cases = [x for x in source["cases"] if args.case == "ALL" or x["case_alias"] == args.case]
    assert len(cases) == (5 if args.case == "ALL" else 1)
    assert not args.out.exists()
    (args.out / "sender/media").mkdir(parents=True)
    (args.out / "sender/public").mkdir()
    (args.out / "private").mkdir()
    (args.out / "public").mkdir()
    wanted = {split: set() for split in ("development", "validation")}
    for case in cases:
        wanted[case["split"]].update(case_frames(case)[0])
    rows = {}
    for split in ("development", "validation"):
        if wanted[split]:
            rows[split] = dict(observations=stream_rows(args.dev_observations if split == "development" else args.val_observations, wanted[split]),
                               masks=stream_rows(args.dev_masks if split == "development" else args.val_masks, wanted[split]))
    mapping = aliases(source["cases"])
    built = [build_case(case, mapping[case["case_alias"]], rows, args.blind, args.out) for case in cases]
    requests = schedule([req for case in built for req in case["requests"]])
    for req in requests:
        req["reserve_peak_usd"] = reserve(req)
        assert len(req["images"]) <= 600
        assert sum(x["bytes"] for x in req["images"]) <= 200 * 1024 * 1024
        if len(req["images"]) >= 15:
            assert all(max(x["width"], x["height"]) <= 4096 for x in req["images"])
    smoke_reserve = ((10000 + 1024) * PRICE_IN + CAP * PRICE_OUT) / 1e6
    total = smoke_reserve + sum(x["reserve_peak_usd"] for x in requests)
    if args.case == "ALL":
        assert len(requests) == 25 and total <= 3, ("BUDGET_BLOCKED", total)
    save(args.out / "sender/PLAN.json", dict(model="deepseek-flash", max_tokens=CAP,
                                               seed=SEED, requests=requests))
    save(args.out / "public/SOURCE_MANIFEST.json", dict(status="FROZEN_BEFORE_MODEL",
         review_base="a27720ff313a27037eb5cbdd9d629506911af7d2", ao1_source_sha256=digest(source_path),
         cases=[{key: value for key, value in row.items() if key not in
                 ("private_token_ledger", "visible_frames", "requests")}
                for row in built]))
    save(args.out / "private/TOKEN_LEDGER.json", {row["case_alias"]: row["private_token_ledger"] for row in built})
    save(args.out / "public/NUMERIC_MOTION.json", {row["case_alias"]: row["numeric_motion"] for row in built})
    save(args.out / "public/REQUEST_MANIFEST.json", dict(status="FROZEN_LOGICAL_REQUESTS",
         seed=SEED, schedule=[x["attempt_id"] for x in requests],
         requests=[dict(attempt_id=x["attempt_id"], case_alias=x["case_alias"], arm=x["arm"],
                        request_id=x["request_id"], core_text_sha256=hashlib.sha256(x["core_text"].encode()).hexdigest(),
                        ap_text_sha256=hashlib.sha256(x["ap_text"].encode()).hexdigest() if x["ap_text"] else None,
                        images=[dict(image_id=i["image_id"], kind=i["kind"], sha256=i["sha256"],
                                     relative_seconds=i["relative_seconds"],
                                     observation_tokens=i.get("observation_tokens", [])) for i in x["images"]],
                        reserve_peak_usd=x["reserve_peak_usd"]) for x in requests]))
    save(args.out / "public/PREFLIGHT.json", dict(status="PASS" if total <= 3 else "BUDGET_BLOCKED",
         cases=len(cases), formal_requests=len(requests), technical_smoke_max=1,
         max_inference_attempts=26, cap_usd=3, reserve_usd=total, research_reserve_usd=total-smoke_reserve,
         smoke_reserve_usd=smoke_reserve, unique_media=len(list((args.out / "sender/media").iterdir())),
         no_GT_read=True, no_model_calls=True))
    save(args.out / "public/INPUT_AUDIT.json", dict(status="REAL_SOURCE_CHECKED",
         cases=[dict(case_alias=row["case_alias"], roi_mask_xyxy=row["roi_mask_xyxy"],
                     sampled_count=len(row["sampled_window_frames"]), endpoint_count=len(row["endpoint_frames"]),
                     g_count=len(row["g_images"]), ap_count=len(row["ap_images"]),
                     g_end_count=len(next(x for x in row["requests"] if x["arm"] == "G-END")["images"]),
                     q=row["query_frame"], geometry_grayscale=True, fixed_roi=True,
                     native_ids_hidden_from_messages=True)
                for row in built]))
    print(json.dumps(dict(cases=len(cases), requests=len(requests), reserve_usd=total,
                          media=len(list((args.out / "sender/media").iterdir())))), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=("ALL", "B01", "B02", "B03", "B04", "B05"), required=True)
    for name in ("source", "blind", "dev-observations", "dev-masks", "val-observations", "val-masks", "out"):
        parser.add_argument("--" + name, type=Path, required=True)
    main(parser.parse_args())
