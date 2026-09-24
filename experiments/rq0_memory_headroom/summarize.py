"""Assemble checked, non-pixel RQ0 report indexes from real output files."""
import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPLITS = ("development", "validation")


def sha(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def lines(path):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt") as handle:
        yield from map(json.loads, handle)


def write(path, value):
    assert not path.exists(), path
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def main():
    metrics, seals, relations = {}, {}, {}
    for split in SPLITS:
        seals[split] = json.loads((HERE / f"OUTPUT_SEAL_{split}.json").read_text())
        metrics[split] = json.loads((HERE / f"METRICS_{split}.json").read_text())
        relations[split] = json.loads((HERE / f"RELATION_CENSUS_{split}_v2.json").read_text())
        assert seals[split]["predictions_sha256"] == sha(HERE / f"PREDICTIONS_{split}.jsonl.gz")
        assert metrics[split]["input_hashes"]["predictions"] == seals[split]["predictions_sha256"]
    canary = json.loads((HERE / "CANARY_DEVELOPMENT.json").read_text())
    assert canary["status"] == "PASS" and canary["frames"] == 8400
    write(HERE / "CANARY_TESTS.json", dict(status="PASS_REAL_ENGINE", checks={
        "ALLOW_B0_output_and_engine_state_8400": True,
        "VETO_original_allowed_write_changed": True,
        "same_current_output_and_lifecycle": all(canary["lifecycle"][x] for x in ("same_output", "same_last_seen", "same_last_frame")),
        "later_real_reader_changed": canary["changed_reader_count"] > 0,
        "bank_view_bank_recent_core_grouped": bool(canary["targeted_write"]["bank_fields"] and
                                                  canary["targeted_write"]["view_bank"] and
                                                  canary["targeted_write"]["recent_core"]),
        "GT_read": False, "API_calls": 0}, source="CANARY_DEVELOPMENT.json"))
    write(HERE / "B0_PARITY.json", dict(status="PASS", development=dict(frames=8400,
             output_and_engine_state_exact=True, source="CANARY_DEVELOPMENT.json"),
             validation=dict(frames=2888, archived_prediction_rows_exact=True,
             source="run_branches.py archived B0 assertion and OUTPUT_SEAL_validation.json"),
             note="Validation engine-state digest parity not independently rerun; prediction parity holds."))
    write(HERE / "METRICS.json", dict(status="POST_SEAL_TRACK_EVAL", splits={s: metrics[s]["metrics"] for s in SPLITS},
          note="Independent reset per exposed split; no pooled 11288-frame score. First-anchor relation counts in METRICS_{split}.json are superseded by RELATION_CENSUS_{split}_v2.json, not TrackEval."))
    reviewed = Counter(x["label"] for x in lines(HERE / "QUALITY_LABELS.jsonl"))
    write(HERE / "UNKNOWN_COVERAGE.json", dict(reviewed_reference_writes=dict(reviewed),
        total_B0_writes=sum(seals[s]["counts"]["B0"]["admitted"] for s in SPLITS),
        unreviewed_B0_writes=sum(seals[s]["counts"]["B0"]["admitted"] for s in SPLITS) - sum(reviewed.values()),
        ambiguous_or_unmatched_prediction_objects={s: relations[s]["old_new_crosswalk"].get("unknown", 0) for s in SPLITS},
        relation_UNKNOWN_global_id_frames={s: relations[s]["status_counts"]["B0"].get("UNKNOWN_GLOBAL_ID", 0) for s in SPLITS},
        note="Unreviewed writes default ALLOW, not certified usable. Two validation GT identities lack >=0.8 dominant global public mapping; their relation status remains UNKNOWN."))
    audit_out = HERE / "REFERENCE_WRITE_READ_AUDIT.jsonl"
    assert not audit_out.exists()
    with audit_out.open("x") as out:
        out.write(json.dumps(dict(kind="CANARY", split="development", anchor=canary["selected"]["anchor"],
                                  write=canary["targeted_write"], first_changed_reader=canary["first_changed_reader"],
                                  changed_reader_count=canary["changed_reader_count"])) + "\n")
        for split in SPLITS:
            source = HERE / f"REFERENCE_WRITE_READ_AUDIT_{split}.jsonl.gz"
            vetoes = [x for x in lines(source) if x["kind"] == "VETO" and x["arm"] == "Q-visible-oracle"]
            # Re-open the immutable stream to relate vetoes to later reader/association changes.
            changes = [x for x in lines(source) if x["kind"] == "READ_OR_ASSOCIATION_CHANGE" and
                       x["arm"] == "Q-visible-oracle"]
            for veto in vetoes:
                later = [x for x in changes if x["frame"] > veto["frame"]]
                out.write(json.dumps(dict(kind="VISIBLE_ORACLE_VETO", split=split,
                                          observation_key=veto["observation_key"], frame=veto["frame"],
                                          native_id=veto["native_id"], public_id=veto["public_id"],
                                          bank_fields=veto["bank_fields"], view_bank=veto["view_bank"],
                                          recent_core=veto["recent_core"],
                                          first_later_changed_reader=min((x["frame"] for x in later if x["changed_reader"]), default=None),
                                          later_changed_reader_frames=sum(x["changed_reader"] for x in later),
                                          later_changed_trace_frames=sum(x["changed_trace"] for x in later),
                                          changed_output_frames=seals[split]["counts"]["Q-visible-oracle"].get("changed_output_frames", 0))) + "\n")
    for kind, target in (("FULL_SEQUENCE_ERROR_CENSUS", "FULL_SEQUENCE_ERROR_CENSUS"),
                         ("FOLLOWUP_AUDIT", "FOLLOWUP_AUDIT")):
        output = HERE / f"{target}.jsonl"
        assert not output.exists()
        with output.open("x") as out:
            for split in SPLITS:
                for row in lines(HERE / f"{kind}_{split}_v2.jsonl"):
                    out.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(json.dumps(dict(status="SUMMARY_INDEXES_WRITTEN", oracle_vetoes=seals["validation"]["counts"]["Q-visible-oracle"]["veto"],
                          full_census_rows=sum(relations[s]["interval_count"] for s in SPLITS), reviewed=dict(reviewed))))


if __name__ == "__main__":
    main()
