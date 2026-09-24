"""One engineering scope correction: fixed Q-rule may veto only frozen B0 writes.

The rule threshold, inputs, oracle and quota arms are unchanged. Original
invalid Q-rule outputs remain sealed and are not silently overwritten.
"""
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


def rows(path):
    with gzip.open(path, "rt") as handle:
        yield from map(json.loads, handle)


def sha(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=("development", "validation"), required=True)
    parser.add_argument("--observations", type=Path, required=True)
    parser.add_argument("--depth", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    args = parser.parse_args()
    config = json.loads((ROOT / "online/closed_loop_2888/z4q_source/CONFIG.json").read_text())
    allowed = {x["observation_key"] for x in rows(HERE / f"REFERENCE_WRITES_{args.split}.jsonl.gz")}
    original_seal = json.loads((HERE / f"OUTPUT_SEAL_{args.split}.json").read_text())
    assert original_seal["status"] == "PREDICTIONS_SEALED_AWAITING_GT" and original_seal["GT_read"] is False
    assert sha(HERE / f"PREDICTIONS_{args.split}.jsonl.gz") == original_seal["predictions_sha256"]
    def rule(frame, obs):
        if f'{frame}:n:{obs["id"]}' not in allowed:
            return False
        box = obs["box"]
        fill = obs["area"] / max(1., (box[2] - box[0]) * (box[3] - box[1]))
        presence = obs.get("presence")
        return fill < .45 or (presence is not None and presence < .65)
    baseline = ReferenceAdmission(config)
    branch = ReferenceAdmission(config, rule)
    path = HERE / f"PREDICTIONS_QRULE_SCOPEFIX_{args.split}.jsonl.gz"
    assert not path.exists()
    frames = vetoes = changed = 0
    with gzip.open(path, "wt") as out:
        for (row, profiles), archived, original in zip(stream(args.observations, args.depth),
                                                       rows(args.baseline),
                                                       rows(HERE / f"PREDICTIONS_{args.split}.jsonl.gz"), strict=True):
            frame = row["frame"]
            ids0, _ = baseline.step(frame, row["time"], row["observations"], profiles)
            ids1, _ = branch.step(frame, row["time"], row["observations"], profiles)
            prediction0 = [dict(id=ids0[o["id"]], mask=o["mask"]) for o in row["native"]]
            prediction1 = [dict(id=ids1[o["id"]], mask=o["mask"]) for o in row["native"]]
            assert prediction0 == archived["variants"]["Z4Q_STABLE"] == original["variants"]["B0"]
            assert [x["mask"] for x in prediction1] == [x["mask"] for x in prediction0]
            for audit in branch.write_audit:
                if audit["veto"]:
                    assert audit["observation_key"] in allowed
                    vetoes += 1
            if prediction1 != prediction0:
                changed += 1
            out.write(json.dumps(dict(frame=frame, global_frame=row["global_frame"],
                                      B0=prediction0, Q_rule_scopefix=prediction1), separators=(",", ":")) + "\n")
            baseline.write_audit.clear(); baseline.read_audit.clear()
            branch.write_audit.clear(); branch.read_audit.clear()
            frames += 1
    seal = dict(status="PREDICTIONS_SCOPEFIX_SEALED_AWAITING_GT", split=args.split, frames=frames,
                correction="Intersect unchanged fixed Q-rule with frozen B0-allowed observation keys only",
                original_invalid_Qrule_seal_sha256=sha(HERE / f"OUTPUT_SEAL_{args.split}.json"),
                corrected_vetoes=vetoes, outside_B0_vetoes=0, changed_output_frames=changed,
                predictions_sha256=sha(path), code_sha256=sha(Path(__file__)), GT_read=False, API_calls=0)
    out = HERE / f"OUTPUT_SEAL_QRULE_SCOPEFIX_{args.split}.json"
    assert not out.exists()
    out.write_text(json.dumps(seal, indent=2) + "\n")
    print(json.dumps({k: seal[k] for k in ("status", "split", "frames", "corrected_vetoes", "outside_B0_vetoes", "changed_output_frames")}))


if __name__ == "__main__":
    main()
