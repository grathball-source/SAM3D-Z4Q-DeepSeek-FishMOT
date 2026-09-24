"""Freeze only the AO1 images and anonymous hypotheses that M1 will transmit."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
from pathlib import Path

import cv2

SYSTEM = ("You are comparing two anonymous fish identity-association hypotheses. "
          "A and B are earlier reference-observation roles; X and Y are current roles. "
          "Role names do not establish identity across time. Other objects keep the same "
          "mapping in both candidates. Choose the complete candidate better supported "
          "only by the images actually supplied, relative times, and image legends. "
          "Lighting, pose, and neighboring fish can alter appearance. INSUFFICIENT is "
          "allowed; no edge needs a numerical proof, and neither candidate is assumed "
          "to be a baseline. Never guess from legend, filename, or option position. "
          "Return only JSON with request_id, choice (C1/C2/INSUFFICIENT), evidence "
          "(at most three objects with image_id, region_or_time, observation, "
          "distinguishes_because), and a short limitation. region_or_time must be "
          "either {bbox_norm:[x0,y0,x1,y1]} with coordinates in [0,1], or "
          "{relative_seconds:number} matching that image's legend. Cite only sent images.")
SEED = 20260924
CAP = 65536
PRICE_IN, PRICE_OUT = .30, 1.20  # Peak USD / million tokens, official 2026-09-24.
ROOT = Path(__file__).resolve().parent


def sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def dump(path: Path, obj: object) -> None:
    assert not path.exists(), path
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def audit(repo: Path, case_id: str, split: str) -> dict:
    path = repo / f"experiments/vl_assoc_e1/CANDIDATE_AUDIT_{split}.jsonl"
    matches = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
               if case_id in line]
    assert len(matches) == 1 and matches[0]["packet_id"] == case_id
    return matches[0]


def image(file: Path, expected: str, image_id: str, tiles: list[dict], media: Path) -> dict:
    assert file.is_file() and sha(file) == expected, file
    pixels = cv2.imread(str(file), cv2.IMREAD_UNCHANGED)
    assert pixels is not None and pixels.ndim in (2, 3)
    height, width = pixels.shape[:2]
    assert width <= 8192 and height <= 8192
    extension = file.suffix.lower()
    assert extension in (".jpg", ".jpeg", ".png")
    destination = media / (expected + (".jpg" if extension == ".jpeg" else extension))
    if not destination.exists():
        os.link(file, destination)
    assert sha(destination) == expected
    for tile in tiles:
        x0, y0, x1, y1 = tile["bbox_norm"]
        assert 0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1
        assert tile["relative_seconds"] <= 0
    return dict(image_id=image_id, media_file=destination.name, sha256=expected,
                bytes=file.stat().st_size, width=width, height=height, tiles=tiles)


def tile(role: str, relative: float, bbox: list[float], view: str) -> dict:
    return dict(role=role, relative_seconds=round(relative, 3), bbox_norm=bbox, view=view)


def e1_p0(case: dict, blind: Path, repo: Path, media: Path) -> list[dict]:
    details = audit(repo, case["case_id"], case["split"])["visuals"]
    result = []
    for mode, file_index in (("static", 1), ("temporal", 2)):
        visual = details[mode]
        assert visual["width"] == 512 and visual["height"] == 160 * len(visual["rows"])
        legend = []
        for row in visual["rows"]:
            r = row["row"]
            assert 0 <= r < len(visual["rows"])
            for col, view in enumerate(("context", "close")):
                legend.append(tile(row["label"], row["source_time"] - case["query_time"],
                                   [col / 2, r / len(visual["rows"]), (col + 1) / 2,
                                    (r + 1) / len(visual["rows"])], view))
        file = blind / case["case_alias"] / case["V0"]["version_alias"] / f"sheet_{file_index}.png"
        result.append(image(file, case["V0"]["media"][file_index - 1]["review_sha256"],
                            f"I{file_index:03d}", legend, media))
    return result


def ao0_p0(case: dict, blind: Path, media: Path) -> list[dict]:
    base = blind / case["case_alias"] / case["V0"]["version_alias"]
    roles = case["V1"]["roles"]
    fish = [tile(row["role"], row["source_time"] - case["query_time"],
                 [(i % 4) / 4, (i // 4) / 3, ((i % 4) + 1) / 4,
                  ((i // 4) + 1) / 3], "fish_grid_cell") for i, row in enumerate(roles)]
    sources = {row["frame"]: row["source_time"] for row in case["source_by_frame"]}
    contacts = [tile("unlabeled_interaction", sources[row["frame"]] - case["query_time"],
                     [(i % 2) / 2, (i // 2) / 2, ((i % 2) + 1) / 2,
                      ((i // 2) + 1) / 2], "interaction_cell")
                for i, row in enumerate(case["V1"]["matched_interaction_views"])]
    assert len(fish) == 10 and len(contacts) == 4
    return [image(base / f"sheet_{i}.png", case["V0"]["media"][i - 1]["review_sha256"],
                  f"I{i:03d}", legend, media)
            for i, legend in ((1, fish), (2, contacts))]


def p1(case: dict, blind: Path, repo: Path, media: Path) -> list[dict]:
    base = blind / case["case_alias"] / case["V1"]["version_alias"]
    roles = case["V1"]["roles"]
    wanted: list[tuple[dict, dict, str]] = []
    if case["case_alias"] == "B01":
        for index, row in enumerate(roles):
            wanted.append((row, row["v0_matched_original_rgb_views"][0], "fish_grid_cell"))
    else:
        details = audit(repo, case["case_id"], case["split"])["visuals"]
        offset = 0 if case["split"] == "development" else 9300
        for mode in ("static", "temporal"):
            for original in details[mode]["rows"]:
                matches = [r for r in roles if r["role"] == original["label"] and
                           r["frame"] == original["global_frame"] - offset]
                assert len(matches) == 1
                row = matches[0]
                for view in ("context", "close"):
                    matched = [v for v in row["v0_matched_original_rgb_views"] if v["view"] == view]
                    assert len(matched) == 1
                    wanted.append((row, matched[0], f"{mode}_{view}"))
    output = []
    for row, view, label in wanted:
        output.append(image(base / view["review_file"], view["sha256"],
                            f"I{len(output) + 1:03d}",
                            [tile(row["role"], row["source_time"] - case["query_time"],
                                  [0, 0, 1, 1], label)], media))
    if case["case_alias"] == "B01":
        times = {x["frame"]: x["source_time"] for x in case["source_by_frame"]}
        for view in case["V1"]["matched_interaction_views"]:
            output.append(image(base / view["review_file"], view["sha256"],
                                f"I{len(output) + 1:03d}",
                                [tile("unlabeled_interaction", times[view["frame"]] - case["query_time"],
                                      [0, 0, 1, 1], "interaction_cell")], media))
    return output


def p2(case: dict, blind: Path, matched: list[dict], media: Path) -> list[dict]:
    output = [dict(item) for item in matched]
    base = blind / case["case_alias"] / case["V2"]["version_alias"]
    source = {x["frame"]: x for x in case["source_by_frame"]}
    start, end = case["v2_window"]
    assert end == case["query_frame"]
    for frame in range(start, end + 1):
        file = base / f"t{frame-start:04d}.jpg"
        row = source[frame]
        output.append(image(file, row["rgb_sha256"], f"I{len(output) + 1:03d}",
                            [tile("unlabeled_scene", row["source_time"] - case["query_time"],
                                  [0, 0, 1, 1], "whole_frame")], media))
    return output


def text_payload(model_request_id: str, options: list[dict], images: list[dict], no_image: bool) -> str:
    legend = [dict(image_id=x["image_id"], width=x["width"], height=x["height"], tiles=x["tiles"])
              for x in images]
    if no_image:
        legend = [dict(role=t["role"], relative_seconds=t["relative_seconds"],
                       view=t["view"], image_available=False)
                  for x in images for t in x["tiles"]]
    payload = dict(request_id=model_request_id, task="Compare both complete mappings at the last supplied time.",
                   candidates=options, image_legend=legend,
                   image_available=not no_image,
                   note="A location legend names an observation role, not its true cross-time identity.")
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def reserve(text: str, count: int) -> float:
    # A conservative upper bound: one token per UTF-8 byte plus 4K overhead;
    # every image may use 1024 tokens and all 65536 output tokens may be billed.
    return ((len((SYSTEM + text).encode()) + 4096 + count * 1024) * PRICE_IN + CAP * PRICE_OUT) / 1e6


def main(args: argparse.Namespace) -> None:
    source = json.loads(args.source.read_text(encoding="utf-8"))
    assert len(source["cases"]) == 5
    assert not args.out.exists()
    args.out.mkdir(parents=True)
    media = args.out / "media"
    media.mkdir()
    (args.out / "private").mkdir()
    (args.out / "public").mkdir()
    plans, audit_rows = [], []
    for case in source["cases"]:
        alias = case["case_alias"]
        assert alias in ("B01", "B02", "B03", "B04", "B05")
        versions = [
            ao0_p0(case, args.blind, media) if alias == "B01" else e1_p0(case, args.blind, args.repo, media),
            p1(case, args.blind, args.repo, media),
        ]
        versions.append(p2(case, args.blind, versions[1], media))
        assert len(versions[0]) == 2
        assert not any(x["media_file"].startswith("t") for x in versions[1])
        assert [x["sha256"] for x in versions[1]] == [x["sha256"] for x in versions[2][:len(versions[1])]]
        card_path = args.blind / alias / case["V0"]["version_alias"] / "card.json"
        card = json.loads(card_path.read_text(encoding="utf-8"))
        original_options = card["candidate_hypotheses"]
        assert [x["choice"] for x in original_options] == ["C1", "C2"]
        assert original_options[0]["mapping"] != original_options[1]["mapping"]
        selected = list(original_options)
        random.Random(SEED + int(alias[1:])).shuffle(selected)
        options = [dict(choice=f"C{i+1}", mapping=x["mapping"]) for i, x in enumerate(selected)]
        to_original = {f"C{i+1}": x["choice"] for i, x in enumerate(selected)}
        assert all(x["source_time"] <= case["query_time"] for x in case["source_by_frame"])
        audit_rows.append(dict(case_alias=alias, cutoff=case["query_frame"],
                               p0_images=len(versions[0]), p1_images=len(versions[1]),
                               p2_images=len(versions[2]), p2_window=case["v2_window"],
                               p1_only_matched_crops=True, v0_static_temporal_legends_separate=True))
        for index, images in enumerate(versions):
            arm = f"P{index}"
            request_id = f"Q{alias[1:]}{arm}"
            plans.append(dict(attempt_id=f"M{alias[1:]}{arm}", case_alias=alias, arm=arm,
                              model_request_id=request_id, images=images,
                              text=text_payload(request_id, options, images, False),
                              candidate_to_original=to_original))
        base = versions[2]
        plans.append(dict(attempt_id=f"D{alias[1:]}R", case_alias=alias, arm="P2_REPEAT",
                          model_request_id=f"Q{alias[1:]}P2", images=base,
                          text=text_payload(f"Q{alias[1:]}P2", options, base, False),
                          candidate_to_original=to_original))
        swapped = [dict(choice="C1", mapping=options[1]["mapping"]),
                   dict(choice="C2", mapping=options[0]["mapping"])]
        plans.append(dict(attempt_id=f"D{alias[1:]}S", case_alias=alias, arm="P2_PERMUTED",
                          model_request_id=f"Q{alias[1:]}S", images=base,
                          text=text_payload(f"Q{alias[1:]}S", swapped, base, False),
                          candidate_to_original={"C1":to_original["C2"],
                                                 "C2":to_original["C1"]}))
        plans.append(dict(attempt_id=f"D{alias[1:]}N", case_alias=alias, arm="P2_NO_IMAGE",
                          model_request_id=f"Q{alias[1:]}N", images=[],
                          text=text_payload(f"Q{alias[1:]}N", options, base, True),
                          candidate_to_original=to_original))
    rng = random.Random(SEED)
    main_calls = [x for x in plans if x["arm"] in ("P0", "P1", "P2")]
    diagnostics = [x for x in plans if x["arm"] not in ("P0", "P1", "P2")]
    rng.shuffle(main_calls)
    rng.shuffle(diagnostics)
    plans = main_calls + diagnostics
    assert len(plans) == 30 and len({x["attempt_id"] for x in plans}) == 30
    for item in plans:
        item["reserve_peak_usd"] = reserve(item["text"], len(item["images"]))
        item["text_sha256"] = hashlib.sha256(item["text"].encode()).hexdigest()
    # Reserve a full 10K input tokens for each technical smoke, independent
    # of the shorter research prompt used by reserve().
    smoke_reserve = 2 * ((10000 * PRICE_IN + CAP * PRICE_OUT) / 1e6)
    total = smoke_reserve + sum(x["reserve_peak_usd"] for x in plans)
    assert total <= 5, ("BUDGET_BLOCKED", total)
    assert max(len(x["images"]) for x in plans) <= 600
    for item in plans:
        raw = sum(x["bytes"] for x in item["images"])
        assert raw <= 200 * 1024 * 1024, (item["attempt_id"], raw)
        if len(item["images"]) >= 15:
            assert all(max(x["width"], x["height"]) <= 4096 for x in item["images"])
    private = args.out / "private"
    public = args.out / "public"
    dump(private / "PLAN.json", dict(system=SYSTEM, requests=plans, seed=SEED,
                                     media_root="media", max_tokens=CAP))
    dump(public / "REQUEST_MANIFEST.json", dict(status="FROZEN_BEFORE_INFERENCE", seed=SEED,
          requests=[dict(attempt_id=x["attempt_id"], case_alias=x["case_alias"], arm=x["arm"],
                         model_request_id=x["model_request_id"], text_sha256=x["text_sha256"],
                         image_count=len(x["images"]), image_sha256=[i["sha256"] for i in x["images"]],
                         image_legend=[dict(image_id=i["image_id"], tiles=i["tiles"]) for i in x["images"]],
                         candidate_to_original=x["candidate_to_original"],
                         reserve_peak_usd=x["reserve_peak_usd"]) for x in plans]))
    dump(public / "INPUT_ADAPTER_AUDIT.json", dict(status="PASS_FOR_FROZEN_INPUTS", cases=audit_rows,
          media_unique_files=len(list(media.iterdir())), no_score_key_read=True,
          old_media_unchanged=True, no_extra_P1_full_frames=True))
    dump(public / "PREFLIGHT.json", dict(status="PASS_WITHIN_USD5_CAP", model="deepseek-flash",
          research_calls=30, technical_smoke_max=2, image_count_total=sum(len(x["images"]) for x in plans),
          max_images_in_one_request=max(len(x["images"]) for x in plans),
          peak_input_usd_per_million=PRICE_IN, peak_output_usd_per_million=PRICE_OUT,
          output_cap=CAP, reserved_research_usd=sum(x["reserve_peak_usd"] for x in plans),
          reserved_two_smoke_usd=smoke_reserve, reserved_total_usd=total,
          no_drop_no_resize=True, file_api_required=True))
    (public / "PROMPT.txt").write_text(SYSTEM + "\n", encoding="utf-8")
    print(json.dumps(dict(status="READY", calls=30, unique_media=len(list(media.iterdir())),
                          reserve_usd=total, schedule=[x["attempt_id"] for x in plans])), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for name in ("source", "blind", "repo", "out"):
        parser.add_argument("--" + name, type=Path, required=True)
    main(parser.parse_args())
