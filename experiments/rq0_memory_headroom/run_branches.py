"""Four continuous no-API RQ0 branches; prediction-only until output seal."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "experiments/vl_assoc_e1/r0_source"))
from bridge import stream  # noqa: E402
from quality_gate import ReferenceAdmission  # noqa: E402

ARMS = ("B0", "Q-rule", "Q-visible-oracle", "quota")


def sha(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def rows(path):
    with gzip.open(path, "rt") as handle:
        yield from map(json.loads, handle)


def key(split, frame, native):
    return f"{split}:{frame}:{native}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=("development", "validation"), required=True)
    parser.add_argument("--observations", type=Path, required=True)
    parser.add_argument("--depth", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    args = parser.parse_args()
    config_path = ROOT / "online/closed_loop_2888/z4q_source/CONFIG.json"
    freeze = json.loads((HERE / "SOURCE_FREEZE.json").read_text())
    assert freeze["GT_read"] is False and freeze["status"] == "RQ0_PREDICTION_INPUTS_FROZEN_BEFORE_GT"
    for name, expected in freeze["files"].items():
        assert sha(HERE / name) == expected, name
    labels = [json.loads(line) for line in (HERE / "QUALITY_LABELS.jsonl").read_text().splitlines()]
    bad = {key(x["split"], x["frame"], x["native_id"]) for x in labels
           if x["split"] == args.split and x["label"] == "VISIBLY_UNUSABLE"}
    writes = list(rows(HERE / f"REFERENCE_WRITES_{args.split}.jsonl.gz"))
    ordered = sorted(writes, key=lambda x: hashlib.sha256(
        key(args.split, x["frame"], x["native_id"]).encode()).hexdigest())
    quota = {key(args.split, x["frame"], x["native_id"]) for x in ordered[:len(bad)]}
    def qrule(frame, obs):
        box = obs["box"]
        fill = obs["area"] / max(1., (box[2] - box[0]) * (box[3] - box[1]))
        presence = obs.get("presence")
        return fill < .45 or (presence is not None and presence < .65)
    engines = {
        "B0": ReferenceAdmission(json.loads(config_path.read_text())),
        "Q-rule": ReferenceAdmission(json.loads(config_path.read_text()), qrule),
        "Q-visible-oracle": ReferenceAdmission(json.loads(config_path.read_text()),
                                 lambda frame, obs: key(args.split, frame, obs["id"]) in bad),
        "quota": ReferenceAdmission(json.loads(config_path.read_text()),
                                 lambda frame, obs: key(args.split, frame, obs["id"]) in quota),
    }
    pred_path = HERE / f"PREDICTIONS_{args.split}.jsonl.gz"
    audit_path = HERE / f"REFERENCE_WRITE_READ_AUDIT_{args.split}.jsonl.gz"
    assert not pred_path.exists() and not audit_path.exists()
    counts = {arm: Counter() for arm in ARMS}
    frame_count = 0
    with gzip.open(pred_path, "wt") as predicted, gzip.open(audit_path, "wt") as audited:
        for (row, profiles), archived in zip(stream(args.observations, args.depth), rows(args.baseline), strict=True):
            frame = row["frame"]
            outputs, traces, reads = {}, {}, {}
            write_rows = {}
            for arm, engine in engines.items():
                ids, trace = engine.step(frame, row["time"], row["observations"], profiles)
                outputs[arm] = [dict(id=ids[o["id"]], mask=o["mask"]) for o in row["native"]]
                traces[arm] = trace
                reads[arm] = list(engine.read_audit)
                write_rows[arm] = list(engine.write_audit)
                counts[arm]["admitted"] += sum(not x["veto"] for x in engine.write_audit)
                counts[arm]["veto"] += sum(x["veto"] for x in engine.write_audit)
                engine.read_audit.clear(); engine.write_audit.clear()
            assert outputs["B0"] == archived["variants"]["Z4Q_STABLE"], (args.split, frame, "B0 mismatch")
            assert all([x["mask"] for x in outputs[arm]] == [x["mask"] for x in outputs["B0"]] for arm in ARMS)
            for arm in ARMS[1:]:
                if outputs[arm] != outputs["B0"]:
                    counts[arm]["changed_output_frames"] += 1
                if traces[arm].get("edges") != traces["B0"].get("edges") or traces[arm].get("birth_checks") != traces["B0"].get("birth_checks"):
                    counts[arm]["changed_association_frames"] += 1
                if reads[arm] != reads["B0"]:
                    counts[arm]["changed_reader_frames"] += 1
            predicted.write(json.dumps(dict(frame=frame, global_frame=row["global_frame"], time=row["time"],
                                            variants=outputs), separators=(",", ":")) + "\n")
            for arm in ARMS:
                for write in write_rows[arm]:
                    if write["veto"]:
                        audited.write(json.dumps(dict(arm=arm, kind="VETO", **write), separators=(",", ":")) + "\n")
                if arm != "B0" and (reads[arm] != reads["B0"] or traces[arm] != traces["B0"]):
                    audited.write(json.dumps(dict(arm=arm, kind="READ_OR_ASSOCIATION_CHANGE", frame=frame,
                                                  changed_reader=reads[arm] != reads["B0"],
                                                  changed_trace=traces[arm] != traces["B0"],
                                                  B0_reads=reads["B0"], branch_reads=reads[arm],
                                                  B0_edges=traces["B0"].get("edges"),
                                                  branch_edges=traces[arm].get("edges")), separators=(",", ":")) + "\n")
            frame_count += 1
    result = dict(status="PREDICTIONS_SEALED_AWAITING_GT", split=args.split, frames=frame_count,
                  counts={arm: dict(counts[arm]) for arm in ARMS}, visible_bad_keys=sorted(bad),
                  quota_keys=sorted(quota), predictions_sha256=sha(pred_path), audit_sha256=sha(audit_path),
                  code_sha256=sha(Path(__file__)), labels_sha256=sha(HERE / "QUALITY_LABELS.jsonl"),
                  source_freeze_sha256=sha(HERE / "SOURCE_FREEZE.json"), GT_read=False, API_calls=0)
    out = HERE / f"OUTPUT_SEAL_{args.split}.json"
    assert not out.exists()
    out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: result[k] for k in ("status", "split", "frames", "counts")}))


if __name__ == "__main__":
    main()
