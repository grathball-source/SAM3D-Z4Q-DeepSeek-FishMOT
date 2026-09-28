"""Explain postseal B04 score gain without treating a wrong reference edge as correct."""
from __future__ import annotations

import gzip
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
PUBLIC = HERE / "public"


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main():
    seal = read(PUBLIC / "PREDICTIONS_SEALED.json")
    score = read(PUBLIC / "METRICS.json")
    audit = read(PUBLIC / "PHYSICAL_REFERENCE_AUDIT.json")
    timeline = read(PUBLIC / "FULL_TIMELINE_HARM_AUDIT.json")
    event = next(x for x in read(PUBLIC / "EVENTS.json") if x["case"] == "B04")
    truth = next(x for x in audit["events"] if x["case"] == "B04")
    fixed = timeline["fixed_public_identity"]
    assert seal["predictions_sha256"] == score["source_prediction_sha256"] == audit["source_prediction_sha256"]
    assert event["status"] == "COMMIT" and truth["selected_reference_verdict"] == "WRONG"
    q = event["frame"]
    with gzip.open(PUBLIC / "predictions_validation.jsonl.gz", "rt", encoding="utf-8") as source:
        qrow = next(x for x in map(json.loads, source) if x["frame"] == q)

    def output(arm, role):
        native = event["q_native"][role]
        public = next(x["id"] for x in qrow["variants"][arm] if x["mask"] == f"n:{native}")
        return dict(public_id=public, long_run_canonical_gt=fixed.get(str(public)),
                    current_gt=truth["q_gt"][role],
                    canonical_match=fixed.get(str(public)) == truth["q_gt"][role])

    references = {role: dict(anchor_frame=event["references"][role]["anchor_frame"],
                             public_id=event["references"][role]["public_id"],
                             observed_gt=truth["reference_gt"][role],
                             long_run_canonical_gt=fixed.get(str(event["references"][role]["public_id"])),
                             canonical_match=fixed.get(str(event["references"][role]["public_id"])) ==
                                truth["reference_gt"][role]) for role in "AB"}
    q_outputs = {role: {arm: output(arm, role) for arm in ("B0", "B2")} for role in "XY"}
    assert all(not x["canonical_match"] for x in references.values())
    assert all(not x["B0"]["canonical_match"] and x["B2"]["canonical_match"]
               for x in q_outputs.values())
    assert not timeline["harms"] and len(timeline["improvements"]) == 495
    by_native = Counter(x["native"] for x in timeline["improvements"])
    output_data = dict(status="POSTSEAL_ACCIDENTAL_CANONICAL_ID_CORRECTION",
        source_prediction_sha256=seal["predictions_sha256"], event="B04", q=q,
        selected_reference_verdict=truth["selected_reference_verdict"],
        frozen_reference_public_to_GT=references, q_output=q_outputs,
        changed_frames=score["difference_frames"],
        object_frame_canonical_improvements=len(timeline["improvements"]),
        object_frame_canonical_harms=len(timeline["harms"]),
        improvement_counts_by_native={str(k): v for k, v in sorted(by_native.items())},
        interpretation="H1 contradicts the physical A/B reference GT. The B0 public IDs were already reversed relative to long-run GT at both frozen references; the wrong event-reference swap accidentally restores canonical output labels for 495 matched object-frames. This does not validate H1 as event identity continuity.")
    target = PUBLIC / "MECHANISM_AUDIT.json"
    assert not target.exists(), target
    target.write_text(json.dumps(output_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(dict(status=output_data["status"],
                          improved_object_frames=output_data["object_frame_canonical_improvements"])))


if __name__ == "__main__":
    main()
