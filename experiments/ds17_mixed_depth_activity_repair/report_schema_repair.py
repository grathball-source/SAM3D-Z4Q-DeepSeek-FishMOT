"""Report-only EVENT_AUDIT container adapter; frozen facts and code stay intact."""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
FROZEN_REPORT = HERE / "postseal_report.py"
RECORD = HERE / "REPORT_SCHEMA_REPAIR.json"
EVENT_ARMS = ("DS16_ORDER", "ACTIVITY_ORDER", "MIXED_ORDER", "MIXED_OFF")


def artifact(path):
    return {"path": str(path.resolve()), "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def group_arm_view(value):
    """Select typed group-arm entries; no branch values or original objects change."""
    assert set(EVENT_ARMS).issubset(value["arms"])
    assert set(value["arms"]) == set(EVENT_ARMS) | {"automatic_reconnect"}
    assert all("group_events" in value["arms"][arm] for arm in EVENT_ARMS)
    adapted = dict(value)
    adapted["arms"] = {arm: value["arms"][arm] for arm in EVENT_ARMS}
    return adapted


def check_adapter():
    synthetic = {"segment": "SYNTHETIC_SCHEMA_CHECK_ONLY", "arms": {
        arm: {"group_events": [{"choice": "H2", "physical": "WRONG", "restore_status": "COMMIT"}],
              "birth_commits": []} for arm in EVENT_ARMS}}
    synthetic["arms"]["automatic_reconnect"] = {"Z4Q_FROZEN": [{"physical": "UNSCORABLE"}]}
    before = copy.deepcopy(synthetic)
    view = group_arm_view(synthetic)
    assert synthetic == before and set(view["arms"]) == set(EVENT_ARMS)
    assert all(view["arms"][arm] == before["arms"][arm] for arm in EVENT_ARMS)
    assert synthetic["arms"]["automatic_reconnect"] == before["arms"]["automatic_reconnect"]


def record_before_score():
    check_adapter()
    assert not (HERE / "run/METRICS.json").exists(), "Record repair before official scoring completes"
    value = {"status": "REPORT_CONTAINER_REPAIR_RECORDED_BEFORE_SCORING",
        "recorded_utc": datetime.now(timezone.utc).isoformat(),
        "frozen_report": artifact(FROZEN_REPORT), "adapter": artifact(Path(__file__)),
        "official_metrics_existed_at_recording": False,
        "gt_or_score_outputs_read_at_recording": False, "synthetic_schema_check": "PASS",
        "repair": {"file_type": "EVENT_AUDIT.json", "path": "arms",
            "selected_group_branches": list(EVENT_ARMS), "excluded_container_metadata": ["automatic_reconnect"],
            "group_facts_modified": False, "automatic_facts_modified": False,
            "automatic_facts_reported_from": "UNCHANGED_AUTOMATIC_RECONNECT_AUDIT.json",
            "other_reads": "EXACT_ORIGINAL_READ_FUNCTION"},
        "schema_review": {"automatic_origin_rule_applied_durable_keys": "MATCH_SCORER_SOURCE",
            "group_status_physical_restore_consensus_keys": "MATCH_SCORER_SOURCE",
            "mixed_whole_core_flags_and_layer_keys": "MATCH_FROZEN_MEASUREMENT_SOURCE",
            "q_order_evidence_restore_published_mapping_keys": "MATCH_FROZEN_RUNNER_SOURCE",
            "additional_key_adaptations": []},
        "prediction_parameter_candidate_rule_scoring_or_metric_changes": False}
    with RECORD.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print("REPORT_SCHEMA_REPAIR_RECORDED")


def run_report():
    record = json.loads(RECORD.read_text(encoding="utf-8"))
    assert record["frozen_report"] == artifact(FROZEN_REPORT)
    assert record["adapter"] == artifact(Path(__file__))
    check_adapter()
    spec = importlib.util.spec_from_file_location("ds17_frozen_postseal_report", FROZEN_REPORT)
    report = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(report)
    original_read = report.read

    def adapted_read(path):
        value = original_read(path)
        return group_arm_view(value) if Path(path).name == "EVENT_AUDIT.json" else value

    report.read = adapted_read
    # Frozen main retains the all-seal + completed-score gate before every GT-derived read.
    report.main()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", action="store_true", help="Generate report only after all seals and metrics exist")
    args = parser.parse_args()
    run_report() if args.run else record_before_score()
