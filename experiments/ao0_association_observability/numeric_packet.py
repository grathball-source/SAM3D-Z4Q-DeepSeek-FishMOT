"""Existing E1C D/A/M comparison on AO0's same causal history/current fragments."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "experiments/vl_assoc_e1/r0_source"))
sys.path.insert(0, str(ROOT / "experiments/vl_assoc_e1c"))
from bridge import Bridge, stream  # noqa: E402
from contract import check_lineage, edge, numeric, validate_packet  # noqa: E402

FRAMES = (1300, 1310, 1321, 1484, 1490, 1498)


def sha(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def rows(path):
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        yield from map(json.loads, handle)


def node(label, frames, native, owners, feature, depth):
    samples = []
    for frame in frames:
        row, view, profiles = owners[frame]
        obs = next(x for x in row["observations"] if x["id"] == native)
        dep = next(x for x in depth[frame]["observations"] if x["id"] == native)
        appearance = next(x for x in feature[frame]["obs"] if x["mask"] == f"n:{native}")
        assert obs["area"] == dep["area"] == appearance["area"]
        samples.append(dict(sequence="validation", frame=frame, source_time=row["time"],
                            native_id=native, mask_key=f"n:{native}",
                            tracklet_epoch=view["epochs"][native], identity_hypothesis=label,
                            neighbors_count=len(obs.get("neighbors", [])), box=obs["box"],
                            center=appearance.get("xy"), core=dep.get("core"),
                            RGB_hist_48=appearance.get("rgb_hist")))
    result = dict(label=label, samples=samples, start_frame=frames[0], end_frame=frames[-1],
                  continuity_checked=all(samples[i]["frame"] < samples[i + 1]["frame"] and
                                         samples[i]["tracklet_epoch"] == samples[0]["tracklet_epoch"]
                                         for i in range(len(samples) - 1)))
    check_lineage(result, owners[1498][0]["time"])
    return result


def run(args):
    config = json.loads((ROOT / "online/closed_loop_2888/z4q_source/CONFIG.json").read_text())
    bridge = Bridge(config)
    owners = {}
    for row, profiles in stream(args.observations, args.depth):
        view = bridge.preview(row["frame"], row["time"], row["observations"], profiles)
        if row["frame"] in FRAMES:
            owners[row["frame"]] = (row, view, profiles)
        bridge.commit_once(view)
    assert set(owners) == set(FRAMES)
    features = {x["global_frame"] - 9300: x for x in rows(args.appearance) if x["global_frame"] - 9300 in FRAMES}
    depths = {x["frame"]: x for x in rows(args.depth) if x["frame"] in FRAMES}
    assert set(features) == set(depths) == set(FRAMES)
    history = [node("A", FRAMES[:3], 1, owners, features, depths),
               node("B", FRAMES[:3], 4, owners, features, depths)]
    current = [node("X", FRAMES[3:], 1, owners, features, depths),
               node("Y", FRAMES[3:], 4, owners, features, depths)]
    pairwise = {f'{h["label"]}:{c["label"]}': edge(h, c) for h in history for c in current}
    packet = dict(schema="VL_ASSOC_RECOVERY_V1", allow_api=False, packet_id="AO0-V-GT2-GT6-1322",
                  snapshot_version=str(owners[1498][1]["version"]), query_time=owners[1498][0]["time"],
                  evidence_cutoff=owners[1498][0]["time"], history=history, current=current,
                  fixed={}, candidates=[dict(id="KEEP", mapping={"X": "A", "Y": "B"}),
                                        dict(id="SWAP", mapping={"X": "B", "Y": "A"})],
                  B0="KEEP", pairwise=pairwise,
                  evidence={f'{pair}:{modality}': dict(source_time=owners[1498][0]["time"], pair=pair,
                               applicable=value["values"][modality] is not None)
                            for pair, value in pairwise.items() for modality in "DAM"})
    assert validate_packet(packet)
    decision = numeric(packet)
    result = dict(status="SAME_CAUSAL_PACKET_NUMERIC_DIAGNOSTIC", selected=decision,
                  pairwise={key: dict(values=value["values"], applicability=value["applicability"],
                                      mixed_mask=value["mixed_mask"], source_observations=value["source_observations"])
                            for key, value in pairwise.items()},
                  sample_frames=list(FRAMES), current_cutoff=packet["query_time"],
                  source_sha256={name: sha(path) for name, path in
                                 (("observations", args.observations), ("depth", args.depth),
                                  ("appearance", args.appearance))},
                  note="No learned weights, no GT, no numerical evidence invented; D/A/M are the existing E1C comparator. This is one exposed-case diagnostic, not a VLM result.")
    output = HERE / "NUMERIC_COMPARISON.json"
    assert not output.exists()
    output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps(dict(selected=decision, values={k: v["values"] for k, v in pairwise.items()})))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for name in ("observations", "depth", "appearance"):
        parser.add_argument("--" + name, type=Path, required=True)
    run(parser.parse_args())
