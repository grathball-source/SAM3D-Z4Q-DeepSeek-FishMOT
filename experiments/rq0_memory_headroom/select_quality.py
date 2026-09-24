"""Freeze prediction-only reference-write sampling before any RQ0 GT read."""
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
from bridge import stream  # noqa: E402
from quality_gate import ReferenceAdmission  # noqa: E402


def sha(path):
    with open(path, "rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def select(args):
    config_path = ROOT / "online/closed_loop_2888/z4q_source/CONFIG.json"
    engine = ReferenceAdmission(json.loads(config_path.read_text()))
    last_contact = {}
    all_rows = []
    with gzip.open(args.writes, "wt", encoding="utf-8") as handle:
        for row, profiles in stream(args.observations, args.depth):
            frame = row["frame"]
            ids, _ = engine.step(frame, row["time"], row["observations"], profiles)
            by_native = {o["id"]: o for o in row["observations"]}
            for obs in row["observations"]:
                if obs.get("neighbors"):
                    last_contact[ids[obs["id"]]] = frame
            for write in engine.write_audit:
                obs = by_native[write["native_id"]]
                area = float(obs["area"])
                box = obs["box"]
                box_area = max(1., (box[2] - box[0]) * (box[3] - box[1]))
                age = frame - last_contact.get(write["public_id"], -100000)
                item = dict(split=args.split, frame=frame, global_frame=row["global_frame"],
                            native_id=write["native_id"], public_id=write["public_id"],
                            observation_key=write["observation_key"], area=area, box=box,
                            box_fill=area / box_area, presence=obs.get("presence"),
                            score_birth=obs.get("score_birth"), contact_age_frames=age,
                            bank_fields=write["bank_fields"], view_bank=write["view_bank"],
                            recent_core=write["recent_core"])
                handle.write(json.dumps(item, separators=(",", ":")) + "\n")
                if 1 <= age <= 150:
                    # Ranking is for blinded human review, not the online gate.
                    item["sampling_risk"] = (2 if age <= 30 else 1) + (1 - min(1., item["box_fill"]))
                    all_rows.append(item)
            engine.write_audit.clear(); engine.read_audit.clear()
    all_rows.sort(key=lambda x: (-x["sampling_risk"], x["frame"], x["native_id"]))
    chosen, last_by_public = [], {}
    for item in all_rows:
        k = item["public_id"]
        if item["frame"] - last_by_public.get(k, -100000) < 45:
            continue
        chosen.append(item)
        last_by_public[k] = item["frame"]
        if len(chosen) == args.limit:
            break
    result = dict(status="PREDICTION_ONLY_SELECTION_FROZEN", split=args.split,
                  total_B0_allowed_writes=sum(1 for _ in gzip.open(args.writes, "rt")),
                  contact_risk_writes=len(all_rows), selected=chosen,
                  selection_policy="top sampling_risk among B0-allowed writes 1-150 frames after predicted contact; 45-frame spacing per public; no GT",
                  inputs={name: sha(path) for name, path in (("observations", args.observations),
                          ("depth", args.depth), ("config", config_path))},
                  writes_sha256=sha(args.writes), GT_read=False, API_calls=0)
    assert not args.output.exists()
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: result[k] for k in ("status", "split", "total_B0_allowed_writes", "contact_risk_writes")}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=("development", "validation"), required=True)
    parser.add_argument("--observations", type=Path, required=True)
    parser.add_argument("--depth", type=Path, required=True)
    parser.add_argument("--writes", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=48)
    select(parser.parse_args())


if __name__ == "__main__":
    main()
