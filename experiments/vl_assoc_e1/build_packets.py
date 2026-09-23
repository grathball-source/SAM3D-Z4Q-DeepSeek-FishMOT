"""Freeze matched E1 packets and visual manifests from causal server inputs. No GT/API."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from pycocotools import mask as mask_api

from e1_protocol import digest, numeric_baseline, validate_packet

HERE = Path(__file__).resolve().parent


def rows(path):
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            yield json.loads(line)


def sha(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def source_rows(args, frames):
    kept = {}
    for ob, dep, feat, masks in zip(rows(args.observations), rows(args.depth),
                                    rows(args.appearance), rows(args.masks), strict=True):
        f = ob["frame"]
        if f in frames:
            assert (f, ob["time"]) == (dep["frame"], dep["time"]) == (masks["frame"], masks["time"])
            assert (ob["global_frame"], ob["time"]) == (feat["global_frame"], feat["time"])
            kept[f] = dict(ob=ob, dep=dep, feat=feat, masks=masks)
    assert set(kept) == frames, (len(frames), len(kept))
    return kept


def sample(record, native, label, query_time):
    ob = next((x for x in record["ob"]["observations"] if x["id"] == native), None)
    dep = next((x for x in record["dep"]["observations"] if x["id"] == native), None)
    feat = next((x for x in record["feat"]["obs"] if x["mask"] == f"n:{native}"), None)
    if ob is None or dep is None or feat is None:
        return None
    assert ob["area"] == dep["area"] == feat["area"]
    assert dep["mask"] == feat["mask"] == f"n:{native}"
    global_frame = record["ob"]["global_frame"]
    assert record["dep"]["evidence_max_global_frame"] <= global_frame
    return dict(label=label, local_frame=record["ob"]["frame"], global_frame=global_frame,
                source_time=record["ob"]["time"], relative_seconds=record["ob"]["time"] - query_time,
                box=ob["box"], center=feat.get("xy"), area=ob["area"],
                presence=ob.get("presence"), neighbors_count=len(ob.get("neighbors", [])),
                core=dep.get("core"), whole=dep.get("whole"),
                RGB_hist_48=feat.get("rgb_hist"), FPN_256_available=isinstance(feat.get("appearance"), list)
                                   and len(feat["appearance"]) == 256,
                FPN_candidate_mask_iou=feat.get("appearance_iou"),
                feature_source="active_identity_features_v1_matched_by_native_mask")


def pair_measurements(history, current):
    a, b = (history["samples"][-1] if history["samples"] else None,
            current["samples"][-1] if current["samples"] else None)
    D = A = M = None
    if a and b:
        da, db = a["core"], b["core"]
        if all(d is not None and d.get("n", 0) >= 16 and d.get("valid_fraction", 0) >= .2 and
               d.get("median") is not None and d.get("mad") is not None for d in (da, db)):
            D = abs(da["median"] - db["median"]) / (15 + 1.4826 * (da["mad"] + db["mad"]))
        ha, hb = a.get("RGB_hist_48"), b.get("RGB_hist_48")
        if isinstance(ha, list) and isinstance(hb, list) and len(ha) == len(hb) == 48:
            A = sum(abs(x-y) for x, y in zip(ha, hb)) * .5
        if len(history["samples"]) >= 2 and a["center"] and b["center"]:
            first = history["samples"][0]
            dt = a["source_time"] - first["source_time"]
            if dt > 0 and first["center"]:
                velocity = [(a["center"][i] - first["center"][i]) / dt for i in (0, 1)]
                gap = b["source_time"] - a["source_time"]
                predicted = [a["center"][i] + velocity[i] * gap for i in (0, 1)]
                diagonal = max(1., math.dist(a["box"][:2], a["box"][2:]))
                M = math.dist(predicted, b["center"]) / diagonal
    return dict(D=D, A=A, M=M)


def make_packet(event, records, split):
    query = records[event["query_frame"]]
    query_time = query["ob"]["time"]
    selected = event["selected"]
    identities = sorted(int(k) for k in event["refs"])
    identity_alias = {k: chr(65 + i) for i, k in enumerate(identities)}
    native_alias = {n: chr(88 + i) for i, n in enumerate(selected)}
    base_map = records[event["query_frame"]]["baseline_mapping"]
    # All generated whole maps have the same native domain and differ only locally.
    assert all({int(n) for n in x["whole"]} == set(base_map) for x in event["candidates"])
    for n in base_map:
        if n not in native_alias:
            native_alias[n] = "U" + str(len([a for a in native_alias.values() if a.startswith("U")]) + 1)
    other_ids = sorted(set(base_map.values()) - set(identities))
    identity_alias.update({k: "K" + str(i+1) for i, k in enumerate(other_ids)})
    history = []
    for k in identities:
        # The probe stores reference frames, while the frozen baseline prediction
        # stream supplies the native owner at each such frame.
        samples = []
        for f in event["refs"][str(k)]:
            owner = records[f]["owner_by_public"].get(k)
            if owner is not None:
                value = sample(records[f], owner, identity_alias[k], query_time)
                if value:
                    samples.append(value)
        history.append(dict(label=identity_alias[k], ownership="unverified_B0_history_hypothesis", samples=samples,
                            missing_reason=None if samples else "no_clean_causal_reference"))
    current = []
    for n in selected:
        frames = sorted({max(1, event["query_frame"]-14), max(1, event["query_frame"]-7), event["query_frame"]})
        samples = []
        for f in frames:
            value = sample(records[f], n, native_alias[n], query_time) if f in records else None
            if value:
                samples.append(value)
        current.append(dict(label=native_alias[n], samples=samples,
                            missing_reason=None if samples else "native_not_present_in_short_segment"))
    # Full mappings retain untouched observations; all labels are anonymous.
    whole_maps = [base_map] + [{int(n): int(k) for n, k in x["whole"].items()}
                               for x in event["candidates"] if x["executable"]]
    unique = {digest(mapping): mapping for mapping in whole_maps}
    ordered = sorted(unique.values(), key=digest)
    candidate_alias = {digest(mapping): "C" + str(i+1) for i, mapping in enumerate(ordered)}
    candidates = [dict(candidate_id=candidate_alias[digest(mapping)],
                       full_mapping={native_alias[n]: identity_alias[k] for n, k in sorted(mapping.items())})
                  for mapping in ordered]
    baseline_id = candidate_alias[digest(base_map)]
    pairwise, evidence = {}, {}
    for h in history:
        for c in current:
            key = h["label"] + ":" + c["label"]
            values = pair_measurements(h, c)
            pairwise[key] = values
            evidence_id = "E" + hashlib.sha256((event["episode_id"] + ":" + key).encode()).hexdigest()[:10]
            evidence[evidence_id] = dict(source_time=query_time, kind="causal_pair_measurements",
                                         pair=key, **values, missing=[k for k, v in values.items() if v is None],
                                         sources=[s["global_frame"] for s in h["samples"] + c["samples"]])
    packet_id = "P" + hashlib.sha256(event["episode_id"].encode()).hexdigest()[:16]
    packet = dict(schema="VL_ASSOC_RELATIVE_V1", packet_id=packet_id,
                  episode_id="EP" + hashlib.sha256(event["episode_id"].encode()).hexdigest()[:16],
                  split=split, query_time=query_time, evidence_cutoff=query_time,
                  snapshot_version=digest(dict(frame=event["query_frame"], mapping=base_map))[:16],
                  history=history, current=current,
                  fixed_observations={native_alias[n]: identity_alias[k] for n, k in base_map.items() if n not in selected},
                  pairwise=pairwise, evidence=evidence,
                  candidates=candidates,
                  limitations=["B0 history is an identity hypothesis, not GT",
                               "depth is an instantaneous range measurement, not permanent fish identity",
                               "RGB histogram and depth share the same predicted mask"])
    validate_packet(packet)
    assert baseline_id in {x["candidate_id"] for x in candidates}
    return packet, baseline_id, dict(native_alias=native_alias, identity_alias=identity_alias,
                                     baseline_public_by_native=base_map)


def render_sheet(packet, records, data, manifest, mode, destination, private):
    nodes = []
    for node in packet["history"]:
        samples = node["samples"][-1:] if mode == "static" else node["samples"]
        nodes.extend((node["label"], x) for x in samples)
    for node in packet["current"]:
        samples = node["samples"][-1:] if mode == "static" else node["samples"]
        nodes.extend((node["label"], x) for x in samples)
    tile_w, tile_h = 256, 160
    sheet = Image.new("RGB", (2*tile_w, len(nodes)*tile_h), "white")
    qa = []
    for row, (label, x) in enumerate(nodes):
        source = manifest[x["global_frame"] - 2]
        assert source["frame_id"] + 1 == x["global_frame"]
        rgb_path = data / source["rgb_original"]
        assert sha(rgb_path) == source["source_rgb_sha256"]
        rgb = cv2.cvtColor(cv2.imread(str(rgb_path)), cv2.COLOR_BGR2RGB)
        if label in {h["label"] for h in packet["history"]}:
            public = next(k for k, alias in private["identity_alias"].items() if alias == label)
            native = records[x["local_frame"]]["owner_by_public"][public]
        else:
            native = next(n for n, alias in private["native_alias"].items() if alias == label)
        encoded = records[x["local_frame"]]["masks"]["masks"][f"n:{native}"]
        mask = mask_api.decode(dict(size=encoded["size"], counts=encoded["counts"].encode("ascii")))
        assert int(mask.sum()) == x["area"] and rgb.shape[0] % mask.shape[0] == rgb.shape[1] % mask.shape[1] == 0
        sx, sy = rgb.shape[1] // mask.shape[1], rgb.shape[0] // mask.shape[0]
        ys, xs = np.where(mask)
        assert len(xs) >= 16
        x0, y0, x1, y1 = int(xs.min()*sx), int(ys.min()*sy), int((xs.max()+1)*sx), int((ys.max()+1)*sy)
        margin = 12*max(sx, sy)
        close = rgb[max(0,y0-margin):min(rgb.shape[0],y1+margin),
                    max(0,x0-margin):min(rgb.shape[1],x1+margin)]
        context_margin = 3*margin
        context = rgb[max(0,y0-context_margin):min(rgb.shape[0],y1+context_margin),
                      max(0,x0-context_margin):min(rgb.shape[1],x1+context_margin)]
        for col, crop in enumerate((context, close)):
            tile = Image.fromarray(crop)
            tile.thumbnail((tile_w, tile_h), Image.Resampling.LANCZOS)
            sheet.paste(tile, (col*tile_w + (tile_w-tile.width)//2,
                               row*tile_h + (tile_h-tile.height)//2))
        qa.append(dict(row=row, label=label, global_frame=x["global_frame"], source_time=x["source_time"],
                       RGB_sha256=source["source_rgb_sha256"], mask_sha256=hashlib.sha256(mask.tobytes()).hexdigest(),
                       native_mask_area=x["area"], mask_size=[mask.shape[1],mask.shape[0]],
                       RGB_size=[rgb.shape[1],rgb.shape[0]], crop_xyxy=[x0,y0,x1,y1]))
    assert qa, "no real pixels in visual packet"
    destination.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(destination)
    return dict(mode=mode, sha256=sha(destination), bytes=destination.stat().st_size,
                width=sheet.width, height=sheet.height, rows=qa,
                layout="each row: unmodified RGB context crop then unmodified RGB fish crop; no labels over pixels")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["development", "validation"], required=True)
    ap.add_argument("--observations", type=Path, required=True)
    ap.add_argument("--depth", type=Path, required=True)
    ap.add_argument("--appearance", type=Path, required=True)
    ap.add_argument("--masks", type=Path, required=True)
    ap.add_argument("--baseline", type=Path, required=True)
    ap.add_argument("--data", type=Path, required=True)
    args = ap.parse_args()
    probe = json.loads((HERE / f"EVENT_PROBE_V4_{args.split}.json").read_text(encoding="utf-8"))
    eligible = [e for e in probe["events"] if e.get("executable", 0) > 0]
    selected = sorted(eligible, key=lambda e: hashlib.sha256(e["episode_id"].encode()).hexdigest())[:12]
    needed = set()
    for e in selected:
        needed.update(range(max(1,e["query_frame"]-14), e["query_frame"]+1))
        needed.update(f for ff in e["refs"].values() for f in ff)
    records = source_rows(args, needed)
    owner_needed = {f for e in selected for ff in e["refs"].values() for f in ff} | {e["query_frame"] for e in selected}
    for line in rows(args.baseline):
        f = line["frame"]
        if f in owner_needed:
            records[f]["baseline_mapping"] = {int(x["mask"].split(":")[1]): x["id"]
                                               for x in line["variants"]["Z4Q_STABLE"]}
            records[f]["owner_by_public"] = {x["id"]: int(x["mask"].split(":")[1])
                                                   for x in line["variants"]["Z4Q_STABLE"]}
    assert all("owner_by_public" in records[f] for f in owner_needed)
    manifest = [json.loads(s) for s in (args.data / "manifest.jsonl").read_text(encoding="utf-8").splitlines()]
    packet_dir = HERE / "packets"
    image_dir = HERE / "images"
    request_dir = HERE / "request_manifest"
    for directory in (packet_dir, image_dir, request_dir):
        directory.mkdir(exist_ok=True)
    output, audit = [], []
    for event in selected:
        packet, baseline_id, private = make_packet(event, records, args.split)
        packet_path = packet_dir / f"{packet['packet_id']}.json"
        assert not packet_path.exists(), packet_path
        packet_path.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        visuals = {}
        for mode in ("static", "temporal"):
            visuals[mode] = render_sheet(packet, records, args.data, manifest, mode,
                                         image_dir / f"{packet['packet_id']}_{mode}.png", private)
        numeric = {name: numeric_baseline(packet, baseline_id, mod)
                   for name, mod in (("N", ("D","A","M")), ("D_only", ("D",)),
                                     ("A_only", ("A",)), ("M_only", ("M",)))}
        episode = dict(episode_id=packet["episode_id"], source_episode_id=event["episode_id"],
                       split=args.split, trigger_frame=event["trigger_frame"], query_frame=event["query_frame"],
                       query_time=packet["query_time"], baseline_candidate=baseline_id,
                       packet_id=packet["packet_id"], candidate_count=len(packet["candidates"]),
                       executable_nonbaseline=event["executable"], numeric=numeric,
                       source_aliases=private, visual_sha256={k:v["sha256"] for k,v in visuals.items()})
        output.append(episode)
        audit.append(dict(packet_id=packet["packet_id"], event=event, visuals=visuals,
                          request_sha256=sha(packet_path)))
        for arm in ("L-T", "L-V-static", "L-V-temporal", "L-V-temporal-repeat", "L-V-temporal-permuted"):
            mode = None if arm == "L-T" else "static" if arm == "L-V-static" else "temporal"
            request = dict(protocol="VL_ASSOC_RELATIVE_V1", arm=arm, packet_file=packet_path.name,
                           packet_sha256=sha(packet_path), snapshot_version=packet["snapshot_version"],
                           image=None if mode is None else dict(file=f"{packet['packet_id']}_{mode}.png",
                                                                 sha256=visuals[mode]["sha256"], bytes=visuals[mode]["bytes"]),
                           allow_api=False, status="FROZEN_INTENT_NOT_SENT")
            path = request_dir / f"{packet['packet_id']}_{arm}.json"
            assert not path.exists(), path
            path.write_text(json.dumps(request, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (HERE / f"EPISODES_{args.split}.jsonl").open("x", encoding="utf-8") as handle:
        for episode in output:
            handle.write(json.dumps(episode, ensure_ascii=False) + "\n")
    with (HERE / f"CANDIDATE_AUDIT_{args.split}.jsonl").open("x", encoding="utf-8") as handle:
        for item in audit:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")
    print(json.dumps(dict(split=args.split, eligible=len(eligible), selected=len(output),
                          packets=len(output), visual_sheets=2*len(output),
                          requests_frozen=5*len(output), API_calls=0), ensure_ascii=False))


if __name__ == "__main__":
    main()
