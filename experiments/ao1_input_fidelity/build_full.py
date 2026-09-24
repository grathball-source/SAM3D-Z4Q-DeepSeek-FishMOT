"""Freeze five paired, anonymous AO1 input bundles without GT or model calls."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import shutil
from pathlib import Path

import cv2
import numpy as np

from build_input import decode_mask, digest, save_exact_crop, selected, validate_frame

HERE = Path(__file__).resolve().parent
NEGATIVES = ("P4218132a1659f1e2", "P04c303d9612421d6",
             "P175d295a01799fe5", "P1797ad89bd359331")
AO0_ID = "AO0-V-GT2-GT6-1322"
AO0_FISH = (("A", 1300, 1), ("A", 1321, 1), ("B", 1300, 4), ("B", 1321, 4),
            ("X", 1484, 1), ("X", 1490, 1), ("X", 1498, 1),
            ("Y", 1484, 4), ("Y", 1490, 4), ("Y", 1498, 4))
VERSION_ALIASES = (("P2", "P1", "P3"), ("P3", "P2", "P1"),
                   ("P1", "P3", "P2"), ("P2", "P3", "P1"), ("P3", "P1", "P2"))


def lines(path: Path):
    with path.open(encoding="utf-8") as handle:
        yield from map(json.loads, handle)


def audit_case(repo: Path, packet_id: str, split: str) -> dict:
    path = repo / f"experiments/vl_assoc_e1/CANDIDATE_AUDIT_{split}.jsonl"
    matches = [r for r in lines(path) if r["packet_id"] == packet_id]
    assert len(matches) == 1
    return matches[0]


def predicted_runs(flags: list[bool], first_frame: int) -> list[dict]:
    """A contact at the scan's right edge is censored, never a completed episode."""
    runs = []
    start = None
    for i, active in enumerate(flags):
        if active and start is None:
            start = first_frame + i
        elif not active and start is not None:
            runs.append(dict(start=start, end=first_frame + i - 1, right_censored=False))
            start = None
    if start is not None:
        runs.append(dict(start=start, end=first_frame + len(flags) - 1, right_censored=True))
    return runs


def continuity(rows: list[dict]) -> dict:
    """Certify every intermediate frame, native, public and epoch; retain contact risk."""
    if not rows:
        return dict(checked=False, reason="EMPTY", contact_frames=[])
    frames = [r["frame"] for r in rows]
    expected = list(range(frames[0], frames[-1] + 1))
    complete = frames == expected
    same = len({(r.get("native"), r.get("public"), r.get("epoch")) for r in rows}) == 1
    missing = [f for f in expected if f not in set(frames)]
    return dict(checked=complete and same, reason="OK" if complete and same else
                "MISSING_INTERMEDIATE" if not complete else "IDENTITY_OR_EPOCH_CHANGE",
                missing_frames=missing, contact_frames=[r["frame"] for r in rows if r.get("contact")])


def candidate_options(case_index: int, original: list[dict], correct_original: str) -> tuple[list[dict], dict]:
    assert len(original) == 2 and {x["id"] for x in original} == {"A", "B"}
    order = ("A", "B") if case_index % 2 else ("B", "A")
    options = [dict(choice=f"C{i+1}", mapping=next(x["mapping"] for x in original if x["id"] == source))
               for i, source in enumerate(order)]
    assert options[0]["mapping"] != options[1]["mapping"]
    reverse = {x["choice"]: order[i] for i, x in enumerate(options)}
    answer = next(choice for choice, source in reverse.items() if source == correct_original)
    return options, dict(answer=answer, source_choice_by_blind=reverse)


def case_spec(case_index: int, repo: Path, old_e1: Path, ao0_index: dict) -> dict:
    if case_index == 0:
        records = ao0_index["records"]
        lookup = {(r["role"], r["frame"]): r for r in records if "role" in r}
        source_rows = []
        for role, frame, native in AO0_FISH:
            old_label = ("R-A" if role == "A" else "R-B" if role == "B" else
                         "C-X" if role == "X" else "C-Y")
            old = lookup[(old_label, frame)]
            source_rows.append(dict(role=role, frame=frame, native=native,
                                    mask_xyxy=old["crop_xyxy"], expected_mask_area=old["predicted_mask_area"]))
        source_frames = sorted({r["frame"] for r in source_rows} | {1322, 1343, 1359, 1419})
        old_media = [Path(x["path"]) for x in json.loads((repo / "experiments/ao0_association_observability/ARTIFACT_MANIFEST.json").read_text())["private_AO0_generated_images"]]
        old_hashes = [x["sha256"] for x in json.loads((repo / "experiments/ao0_association_observability/ARTIFACT_MANIFEST.json").read_text())["private_AO0_generated_images"]]
        hypotheses = [dict(id="A", mapping={"X": "A", "Y": "B", "U1": "K1", "U2": "K2",
                                               "U3": "K3", "U4": "K4"}),
                      dict(id="B", mapping={"X": "B", "Y": "A", "U1": "K1", "U2": "K2",
                                               "U3": "K3", "U4": "K4"})]
        return dict(case_id=AO0_ID, split="validation", trigger=1322, query=1498,
                    query_time=1787709101.092, rows=source_rows, source_frames=source_frames,
                    v0_media=old_media, v0_hashes=old_hashes, v0_ao0=True,
                    hypotheses=hypotheses, correct_original="B", old_packet=None)
    packet_id = NEGATIVES[case_index - 1]
    split = "development" if case_index == 1 else "validation"
    audit = audit_case(repo, packet_id, split)
    packet_path = old_e1 / "experiments/vl_assoc_e1/packets" / f"{packet_id}.json"
    packet = json.loads(packet_path.read_text())
    assert packet["packet_id"] == packet_id and packet["split"] == split
    visual = audit["visuals"]["temporal"]
    source_rows = [dict(role=r["label"], frame=r["global_frame"] - (0 if split == "development" else 9300),
                        native=None, rgb_xyxy=r["crop_xyxy"], expected_mask_sha256=r["mask_sha256"],
                        expected_rgb_sha256=r["RGB_sha256"], expected_mask_area=r["native_mask_area"])
                   for r in visual["rows"]]
    source_frames = sorted({r["frame"] for r in source_rows})
    old_media = [old_e1 / "experiments/vl_assoc_e1/images" / f"{packet_id}_{mode}.png"
                 for mode in ("static", "temporal")]
    old_hashes = [audit["visuals"][mode]["sha256"] for mode in ("static", "temporal")]
    assert len(packet["candidates"]) == 2
    hypotheses = [dict(id=x["candidate_id"], mapping=x["full_mapping"])
                  for x in packet["candidates"]]
    assert {x["id"] for x in hypotheses} == {"C1", "C2"}
    hypotheses = [dict(id="A" if x["id"] == "C1" else "B", mapping=x["mapping"]) for x in hypotheses]
    correct = "A" if packet_id == "P1797ad89bd359331" else "B"
    return dict(case_id=packet_id, split=split, trigger=audit["event"]["trigger_frame"],
                query=audit["event"]["query_frame"], query_time=audit["event"]["query_time"],
                rows=source_rows, source_frames=source_frames, v0_media=old_media,
                v0_hashes=old_hashes, v0_ao0=False, hypotheses=hypotheses,
                correct_original=correct, old_packet=str(packet_path), old_packet_sha256=digest(packet_path))


def projected_mask(assignment: dict, observation: dict, native: int, rgb_xyxy: list[int]) -> np.ndarray:
    mask = decode_mask(assignment, observation, native)
    x0, y0, x1, y1 = rgb_xyxy
    up = cv2.resize(mask, (1920, 1080), interpolation=cv2.INTER_NEAREST)
    return up[y0:y1, x0:x1]


def outline(rgb: np.ndarray, mask: np.ndarray, xyxy: list[int], destination: Path) -> dict:
    x0, y0, x1, y1 = xyxy
    image = rgb[y0:y1, x0:x1].copy()
    contours, _ = cv2.findContours((mask > 0).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(image, contours, -1, (255, 255, 255), 2)
    assert cv2.imwrite(str(destination), image)
    return dict(path=str(destination), sha256=digest(destination), bytes=destination.stat().st_size,
                auxiliary_only=True, contour_color="white_same_for_every_role")


def write_json(path: Path, data: dict) -> None:
    assert not path.exists(), path
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def build_case(index: int, spec: dict, args: argparse.Namespace, manifest: list[dict]) -> tuple[dict, dict, dict]:
    offset = 0 if spec["split"] == "development" else 9300
    window_start = max(2 if offset == 0 else 1, spec["trigger"] - 60)
    window = list(range(window_start, spec["query"] + 1))
    sample_frames = set(window) | set(spec["source_frames"])
    observations = selected(args.dev_observations if offset == 0 else args.val_observations, sample_frames)
    masks = selected(args.dev_masks if offset == 0 else args.val_masks, sample_frames)
    assert observations[spec["query"]]["time"] == spec["query_time"]
    assert max(spec["source_frames"]) <= spec["query"]
    alias = f"B{index+1:02d}"
    version_names = dict(zip(("V0", "V1", "V2"), VERSION_ALIASES[index]))
    options, answer = candidate_options(index, spec["hypotheses"], spec["correct_original"])
    case_dir = args.private_root / "blind" / alias
    for version in ("V0", "V1", "V2"):
        (case_dir / version_names[version]).mkdir(parents=True, exist_ok=False)
    source_info = {}
    copied = {}
    for frame in sorted(sample_frames):
        rgb, source = validate_frame(frame, observations[frame], masks[frame], manifest,
                                     args.dataset, spec["query_time"], offset=offset,
                                     cutoff_frame=spec["query"])
        source["predicted_masks"] = [
            dict(mask_key=key, native_id=int(key[2:]),
                 rle_sha256=hashlib.sha256(json.dumps(encoded, sort_keys=True).encode()).hexdigest())
            for key, encoded in sorted(masks[frame]["masks"].items()) if key.startswith("n:")]
        source["assignment_time"] = masks[frame]["time"]
        source_info[frame] = source
        if frame in window:
            target = case_dir / version_names["V2"] / f"t{frame-window_start:04d}.jpg"
            shutil.copyfile(source["rgb_path"], target)
            assert digest(target) == source["rgb_sha256"]
            copied[frame] = dict(review_file=target.name, sha256=digest(target), bytes=target.stat().st_size)
        if frame in spec["source_frames"]:
            target = case_dir / version_names["V1"] / f"s{spec['source_frames'].index(frame):03d}.jpg"
            shutil.copyfile(source["rgb_path"], target)
            assert digest(target) == source["rgb_sha256"]
            if frame not in window:
                older = case_dir / version_names["V2"] / f"older_s{spec['source_frames'].index(frame):03d}.jpg"
                shutil.copyfile(source["rgb_path"], older)
                assert digest(older) == source["rgb_sha256"]
        del rgb
    role_records = []
    for row_index, row in enumerate(spec["rows"]):
        frame = row["frame"]
        rgb, _ = validate_frame(frame, observations[frame], masks[frame], manifest,
                                args.dataset, spec["query_time"], offset=offset,
                                cutoff_frame=spec["query"])
        if row["native"] is None:
            candidates = []
            for key in masks[frame]["masks"]:
                if key.startswith("n:"):
                    native = int(key[2:])
                    mask = decode_mask(masks[frame], observations[frame], native)
                    if hashlib.sha256(mask.tobytes()).hexdigest() == row["expected_mask_sha256"]:
                        candidates.append((native, mask))
            assert len(candidates) == 1, (spec["case_id"], row_index, candidates)
            native, mask = candidates[0]
            xyxy = row["rgb_xyxy"]
            assert source_info[frame]["rgb_sha256"] == row["expected_rgb_sha256"]
        else:
            native = row["native"]
            mask = decode_mask(masks[frame], observations[frame], native)
            xyxy = [coordinate * 3 for coordinate in row["mask_xyxy"]]
        assert int(mask.sum()) == row["expected_mask_area"]
        x0, y0, x1, y1 = xyxy
        crop = rgb[y0:y1, x0:x1].copy()
        assert crop.size
        name = f"r{row_index:02d}"
        target = case_dir / version_names["V1"] / f"{name}.png"
        assert cv2.imwrite(str(target), crop)
        assert np.array_equal(cv2.imread(str(target), cv2.IMREAD_COLOR), crop)
        aux = case_dir / version_names["V1"] / f"{name}_outline.png"
        aux_info = outline(rgb, projected_mask(masks[frame], observations[frame], native, xyxy), xyxy, aux)
        matched = []
        if spec["v0_ao0"]:
            matched.append(dict(view="AO0_fish_tile", rgb_xyxy=xyxy, review_file=f"{name}.png",
                                sha256=digest(target), pixel_exact=True))
        else:
            # Archived E1 V0 has two tiles per row: original RGB mask bbox
            # expanded by 36 px and 108 px, then shrunk to 256x160. Preserve
            # precisely those two spatial fields before comparing fidelity.
            for view_name, margin in (("close", 36), ("context", 108)):
                region = [max(0, x0-margin), max(0, y0-margin),
                          min(1920, x1+margin), min(1080, y1+margin)]
                xa, ya, xb, yb = region
                raw = rgb[ya:yb, xa:xb].copy()
                match_file = case_dir / version_names["V1"] / f"{name}_{view_name}.png"
                assert cv2.imwrite(str(match_file), raw)
                assert np.array_equal(cv2.imread(str(match_file), cv2.IMREAD_COLOR), raw)
                matched.append(dict(view=view_name, rgb_xyxy=region, review_file=match_file.name,
                                    sha256=digest(match_file), pixel_exact=True))
        for suffix in (".png", "_outline.png"):
            shutil.copyfile(case_dir / version_names["V1"] / f"{name}{suffix}",
                            case_dir / version_names["V2"] / f"{name}{suffix}")
        for extra in matched:
            if extra["review_file"] != f"{name}.png":
                shutil.copyfile(case_dir / version_names["V1"] / extra["review_file"],
                                case_dir / version_names["V2"] / extra["review_file"])
        role_records.append(dict(role=row["role"], frame=frame, source_time=source_info[frame]["source_time"],
                                 native_mask_key=f"n:{native}", rgb_xyxy=xyxy,
                                 rgb_crop_size=[crop.shape[1], crop.shape[0]], crop_pixel_exact=True,
                                 crop_sha256=digest(target), auxiliary=aux_info,
                                 v0_matched_original_rgb_views=matched,
                                 mask_area=int(mask.sum()), contact_risk=bool(next(
                                     x["neighbors"] for x in observations[frame]["observations"]
                                     if x["id"] == native)) if "neighbors" in next(
                                     x for x in observations[frame]["observations"] if x["id"] == native) else False))
    interaction_views = []
    if spec["v0_ao0"]:
        ao0_index = json.loads((args.repo / "experiments/ao0_association_observability/VISUAL_INPUT_INDEX.json").read_text())
        region = [n*3 for n in ao0_index["local_contact_xyxy"]]
        xa, ya, xb, yb = region
        for frame in (1322, 1343, 1359, 1419):
            rgb, _ = validate_frame(frame, observations[frame], masks[frame], manifest,
                                    args.dataset, spec["query_time"], offset=offset,
                                    cutoff_frame=spec["query"])
            raw = rgb[ya:yb, xa:xb].copy()
            filename = f"interaction_{frame-1322:03d}.png"
            destination = case_dir / version_names["V1"] / filename
            assert cv2.imwrite(str(destination), raw)
            assert np.array_equal(cv2.imread(str(destination), cv2.IMREAD_COLOR), raw)
            shutil.copyfile(destination, case_dir / version_names["V2"] / filename)
            interaction_views.append(dict(frame=frame, rgb_xyxy=region, review_file=filename,
                                          sha256=digest(destination), pixel_exact=True))
    v0_records = []
    for i, (source_path, expected) in enumerate(zip(spec["v0_media"], spec["v0_hashes"], strict=True)):
        assert source_path.is_file() and digest(source_path) == expected
        target = case_dir / version_names["V0"] / f"sheet_{i+1}.png"
        if spec["v0_ao0"]:
            image = cv2.imread(str(source_path), cv2.IMREAD_COLOR)
            assert image is not None
            if i == 0:
                for y in (0, 250, 500):
                    image[y:y+30, :] = 245
            else:
                for y in (0, 300):
                    image[y:y+30, :] = 245
            assert cv2.imwrite(str(target), image)
            modified = "frame_and_role_text_header_redacted_only"
        else:
            shutil.copyfile(source_path, target)
            modified = "byte_identical"
        v0_records.append(dict(original_path=str(source_path), original_sha256=expected,
                               review_file=target.name, review_sha256=digest(target),
                               bytes=target.stat().st_size, blind_change=modified))
    # Reviewer cards contain neither source paths nor original IDs, B0, GT, or answer.
    role_card = [dict(tile=f"r{i:02d}", role=r["role"], relative_seconds=round(r["source_time"]-spec["query_time"], 3),
                      matched_main_crops=[x["review_file"] for x in r["v0_matched_original_rgb_views"]],
                      separate_location_guide=f"r{i:02d}_outline.png")
                 for i, r in enumerate(role_records)]
    for version in ("V0", "V1", "V2"):
        directory = case_dir / version_names[version]
        card = dict(case=alias, version=version_names[version], answer_choices=["C1", "C2", "INSUFFICIENT"],
                    candidate_hypotheses=options,
                    instructions="Compare complete mappings using visible evidence only. Cite tile/time/region and why it distinguishes the two; INSUFFICIENT is valid. Do not infer an answer from opaque names.",
                    roles=role_card,
                    visible_media=([x["review_file"] for x in v0_records] if version == "V0" else
                                   sorted(p.name for p in directory.iterdir() if p.is_file())),
                    timeline=([dict(image=copied[f]["review_file"], relative_seconds=round(source_info[f]["source_time"]-spec["query_time"], 3))
                               for f in window] if version == "V2" else None))
        # V0's role indices refer to its original row order; new role crops are only V1/V2.
        if version == "V0":
            card["roles"] = [dict(tile=f"row{i:02d}", role=r["role"],
                                  relative_seconds=round(r["source_time"]-spec["query_time"], 3))
                             for i, r in enumerate(role_records)]
        write_json(directory / "card.json", card)
    source_set = dict(case_id=spec["case_id"], case_alias=alias, split=spec["split"],
                      query_frame=spec["query"], query_time=spec["query_time"],
                      trigger_frame=spec["trigger"], v2_window=[window_start, spec["query"]],
                      V0=dict(version_alias=version_names["V0"], source_frames=spec["source_frames"], media=v0_records),
                      V1=dict(version_alias=version_names["V1"], source_frames=spec["source_frames"],
                              roles=role_records, matched_interaction_views=interaction_views),
                      V2=dict(version_alias=version_names["V2"], source_frames=sorted(sample_frames),
                              full_window_frames=len(window), older_reference_frames=sorted(set(spec["source_frames"])-set(window))),
                      full_frame_fixed_roi_xyxy=[0, 0, 1920, 1080],
                      coordinate_transform=dict(predicted_mask=[640, 360], original_rgb=[1920, 1080], scale_xy=[3, 3]),
                      source_by_frame=[source_info[f] for f in sorted(sample_frames)],
                      original_packet_sha256=spec.get("old_packet_sha256"))
    answer_record = dict(case_alias=alias, original_case_id=spec["case_id"],
                         version_aliases=version_names, candidate_mapping=options,
                         private_score_answer=answer["answer"], answer_origin="AO0 exposed oracle" if index == 0 else
                         "frozen E1 harm case adjudication", original_choice=spec["correct_original"])
    qa = dict(case_alias=alias, status="PASS", query_cutoff_checked=True,
              real_rgb_frames=len(sample_frames), v0_v1_same_source_frames=True,
              original_pixel_exact_crops=len(role_records), source_frames=spec["source_frames"],
              full_window_frames=len(window), older_reference_frames=source_set["V2"]["older_reference_frames"],
              v0_original_and_blind_copy=v0_records,
              total_private_bytes=sum(p.stat().st_size for p in case_dir.rglob("*") if p.is_file()))
    return source_set, answer_record, qa


def main(args: argparse.Namespace) -> None:
    assert args.private_root.is_dir() and not (args.private_root / "blind").exists()
    assert args.public_output.is_dir() and not any(args.public_output.iterdir())
    manifest = [json.loads(line) for line in (args.dataset / "manifest.jsonl").read_text().splitlines()]
    ao0_index = json.loads((args.repo / "experiments/ao0_association_observability/VISUAL_INPUT_INDEX.json").read_text())
    sources, answers, qa = [], [], []
    for index in range(5):
        spec = case_spec(index, args.repo, args.old_e1, ao0_index)
        source, answer, check = build_case(index, spec, args, manifest)
        sources.append(source)
        answers.append(answer)
        qa.append(check)
        print(json.dumps(dict(case=source["case_alias"], status=check["status"],
                              V1_sources=len(source["V1"]["source_frames"]),
                              V2_sources=len(source["V2"]["source_frames"]))), flush=True)
    write_json(args.public_output / "SOURCE_MANIFEST.json", dict(status="FROZEN_BEFORE_REVIEW",
               source_image_manifest_sha256=digest(args.dataset / "manifest.jsonl"),
               source_stream_sha256={name: digest(path) for name, path in (
                   ("development_observations", args.dev_observations),
                   ("development_predicted_masks", args.dev_masks),
                   ("validation_observations", args.val_observations),
                   ("validation_predicted_masks", args.val_masks))},
               cases=sources, no_GT_raster_read=True, external_model_api_calls=0))
    write_json(args.public_output / "SCORE_KEY.json", dict(status="ISOLATED_NOT_IN_BLIND_BUNDLE", cases=answers))
    write_json(args.public_output / "INPUT_QA.json", dict(status="PASS_FOR_BUILT_INPUTS", cases=qa,
               blind_root=str(args.private_root / "blind"), Work_visual_QA_not_independent_review=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for name in ("repo", "old-e1", "dataset", "private-root", "public-output",
                 "dev-observations", "dev-masks", "val-observations", "val-masks"):
        parser.add_argument("--" + name, type=Path, required=True)
    main(parser.parse_args())
