"""Prediction-only contact registration and first eligible query under a fixed 15/150 rule."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "experiments/vl_assoc_e1/r0_source"))
from bridge import Bridge, stream  # noqa: E402


def probe(args):
    config = json.loads((ROOT / "online/closed_loop_2888/z4q_source/CONFIG.json").read_text())
    bridge = Bridge(config)
    contacts = []
    query = []
    current_contact = None
    streak = 0
    last_versions = None
    last_contact_end = None
    for row, profiles in stream(args.observations, args.depth):
        frame = row["frame"]
        view = bridge.preview(frame, row["time"], row["observations"], profiles)
        ids = view["mapping"]
        owners = {public: native for native, public in ids.items() if public in (args.public_a, args.public_b)}
        obs = {x["id"]: x for x in row["observations"]}
        pair_contact = any(ids.get(neighbor) in (args.public_a, args.public_b) and ids.get(neighbor) != ids[native]
                           for native in owners.values() for neighbor in obs[native].get("neighbors", []))
        if args.start <= frame <= args.end and pair_contact:
            if current_contact is None:
                current_contact = dict(start=frame, end=frame, public_ids=[args.public_a, args.public_b])
            else:
                current_contact["end"] = frame
        elif current_contact is not None:
            contacts.append(current_contact)
            last_contact_end = current_contact["end"]
            current_contact = None
            streak = 0
            last_versions = None
        if last_contact_end is not None and 0 < frame - last_contact_end <= 150:
            eligible = (len(owners) == 2 and all(bridge.engine.quality(obs[n]) and
                         not obs[n].get("neighbors") for n in owners.values()))
            versions = {p: (owners[p], view["epochs"][owners[p]]) for p in owners}
            if eligible and versions == last_versions:
                streak += 1
            elif eligible:
                streak = 1
            else:
                streak = 0
            last_versions = versions if eligible else None
            if streak == 15:
                query.append(dict(contact_end=last_contact_end, query_frame=frame, query_time=row["time"],
                                  native_and_epoch={str(p): list(versions[p]) for p in sorted(versions)},
                                  start_of_streak=frame - 14, evidence_cutoff_global_frame=row["global_frame"]))
                last_contact_end = None
        bridge.commit_once(view)
    if current_contact is not None:
        contacts.append(current_contact)
    result = dict(status="PREDICTION_ONLY_PROBE_GT_NOT_READ", public_ids=[args.public_a, args.public_b],
                  scan_window=[args.start, args.end], rule="first 15 consecutive eligible frames within 150 after registered pair contact end; same native and epoch; original quality; no contact",
                  contacts=contacts, queries=query, allow_api=False)
    assert not args.output.exists()
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(dict(contacts=contacts, queries=query)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for name in ("observations", "depth", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    for name in ("public-a", "public-b", "start", "end"):
        parser.add_argument("--" + name, type=int, required=True)
    probe(parser.parse_args())
