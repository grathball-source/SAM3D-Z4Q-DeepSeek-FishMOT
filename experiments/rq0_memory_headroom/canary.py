"""Prediction-only real-engine canary; no GT input or model transport."""
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
from quality_gate import ReferenceAdmission, StableReturn, digest  # noqa: E402


def rows(path):
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        yield from map(json.loads, handle)


def sha(path):
    with open(path, "rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def state(engine):
    return digest({k: v for k, v in vars(engine).items()
                   if k not in {"veto", "write_audit", "read_audit", "frame"}})


def find_anchor(config, obs_path, depth_path):
    engine = ReferenceAdmission(config)
    for row, profiles in stream(obs_path, depth_path):
        _, trace = engine.step(row["frame"], row["time"], row["observations"], profiles)
        for event in trace["events"]:
            anchor = event.get("old_anchor")
            if event.get("accepted") and isinstance(anchor, dict) and anchor.get("frame") is not None:
                return dict(anchor=anchor, reader_frame=row["frame"],
                            event_kind=event["kind"], event_native=event["native_id"],
                            event_public=event["canonical_id"])
        engine.write_audit.clear()
        engine.read_audit.clear()
    raise AssertionError("No real accepted association with old anchor")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=("development", "validation"), required=True)
    parser.add_argument("--observations", type=Path, required=True)
    parser.add_argument("--depth", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists()
    config_path = ROOT / "online/closed_loop_2888/z4q_source/CONFIG.json"
    config = json.loads(config_path.read_text())
    selected = find_anchor(config, args.observations, args.depth)
    anchor = selected["anchor"]
    target = (anchor["frame"], anchor["native_id"])
    baseline = StableReturn(config)
    allow = ReferenceAdmission(config)
    veto = ReferenceAdmission(config, lambda frame, obs: (frame, obs["id"]) == target)
    parity_frames = 0
    targeted_writes = []
    later_reads = []
    lifecycle = []
    for (row, profiles), archived in zip(stream(args.observations, args.depth), rows(args.baseline), strict=True):
        frame, now = row["frame"], row["time"]
        ids0, trace0 = baseline.step(frame, now, row["observations"], profiles)
        ids1, trace1 = allow.step(frame, now, row["observations"], profiles)
        ids2, _ = veto.step(frame, now, row["observations"], profiles)
        expected = archived["variants"]["Z4Q_STABLE"]
        actual = [dict(id=ids0[o["id"]], mask=o["mask"]) for o in row["native"]]
        assert actual == expected, (frame, "archived_B0")
        assert ids1 == ids0 and trace1 == trace0 and state(allow) == state(baseline), (frame, "ALLOW_parity")
        if frame <= selected["reader_frame"]:
            targeted_writes += [x for x in veto.write_audit if (x["frame"], x["native_id"]) == target]
            if frame > target[0]:
                k = anchor["canonical_id"]
                later_reads += [dict(frame=frame, allow=a, veto=b) for a, b in zip(
                    [x for x in allow.read_audit if x["public_id"] == k],
                    [x for x in veto.read_audit if x["public_id"] == k])
                    if a["reader"] == b["reader"] and a["reference"] != b["reference"]]
            if frame == target[0]:
                k = anchor["canonical_id"]
                lifecycle.append(dict(frame=frame, same_output=ids0 == ids2,
                                      same_last_seen=baseline.bank[k]["last_seen"] == veto.bank[k]["last_seen"],
                                      same_last_frame=baseline.bank[k]["last_frame"] == veto.bank[k]["last_frame"],
                                      reference_changed=digest(baseline.bank[k]) != digest(veto.bank[k])))
        allow.write_audit.clear(); allow.read_audit.clear()
        veto.write_audit.clear(); veto.read_audit.clear()
        parity_frames += 1
    assert len(targeted_writes) == 1 and targeted_writes[0]["veto"]
    assert targeted_writes[0]["bank_fields"] or targeted_writes[0]["view_bank"] or targeted_writes[0]["recent_core"]
    assert lifecycle and all(lifecycle[0][key] for key in ("same_output", "same_last_seen", "same_last_frame", "reference_changed"))
    assert later_reads, "VETO must have a later real reader with changed reference"
    result = dict(status="PASS", split=args.split, frames=parity_frames, selected=selected,
                  targeted_write=targeted_writes[0], lifecycle=lifecycle[0],
                  first_changed_reader=later_reads[0], changed_reader_count=len(later_reads),
                  inputs={name: sha(path) for name, path in (("observations", args.observations),
                          ("depth", args.depth), ("baseline", args.baseline), ("config", config_path))},
                  GT_read=False, API_calls=0)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({k: result[k] for k in ("status", "split", "frames", "selected", "changed_reader_count")}))


if __name__ == "__main__":
    main()
