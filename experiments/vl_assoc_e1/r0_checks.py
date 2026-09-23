"""R0 engineering checks on the server, with original streams read-only and no GT."""
from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OLD = ROOT / "online/closed_loop_2888"
sys.path.insert(0, str(HERE / "r0_source"))
sys.path.insert(1, str(OLD))
from bridge import Bridge, read, rows, stream  # noqa: E402
from policy import compile_view, state_for  # noqa: E402
from runner import RepairedRunner  # noqa: E402
from scoring import association_relation_audit, followup_horizons  # noqa: E402
import fixture_tests as old_tests  # noqa: E402


def epoch_checks(config):
    bridge = Bridge(config)
    engine = SimpleNamespace(alias={})
    assert bridge.next_epochs({7: 2}, engine) == {7: 1}
    bridge.previous, bridge.epochs, bridge.previous_alias = {7: 2}, {7: 1}, {7: None}
    assert bridge.next_epochs({7: 2}, engine) == {7: 1}
    assert bridge.next_epochs({7: 3}, engine) == {7: 2}
    engine.alias[7] = dict(target=2, commit_frame=12)
    assert bridge.next_epochs({7: 2}, engine) == {7: 2}
    bridge.previous_alias[7] = bridge.alias_signature(engine, 7)
    assert bridge.next_epochs({7: 2}, engine) == {7: 1}
    engine.alias.pop(7)
    assert bridge.next_epochs({7: 2}, engine) == {7: 2}
    bridge.previous = {}
    assert bridge.next_epochs({7: 2}, engine) == {7: 2}
    return ["new_native", "same_mapping", "public_change", "alias_change", "alias_revocation", "reappearance"]


def atomic_checks(config):
    sample = RepairedRunner(config, "B0")
    old_tests.seed(sample)
    row = [old_tests.obj(9, 900., 3.), old_tests.obj(2, 850., 40.)]
    before = copy.deepcopy(vars(sample.bridge.engine))
    view = sample.bridge.preview(22, 22 / 30, row, old_tests.profiles(22, row))
    assert vars(sample.bridge.engine) == before, "preview polluted authoritative state"
    bad, reason = sample.bridge.stage(view, {9: 2})
    assert bad is None and reason == "occupied_target"
    assert vars(sample.bridge.engine) == before, "failed stage polluted authoritative state"
    sample.bridge.commit_once(view)
    try:
        sample.bridge.commit_once(view)
    except AssertionError as exc:
        assert "already committed or stale" in str(exc)
    else:
        raise AssertionError("duplicate commit accepted")
    stale, reason = sample.bridge.stage(view, {9: 1})
    assert stale is None and reason == "stale_snapshot"
    return ["preview_isolated", "failed_stage_rollback", "duplicate_commit_rejected", "stale_snapshot_rejected"]


def scoring_checks():
    gt = {1: {1: "GT4", 2: "GT5"}, 2: {3: "GT4", 4: "GT5"},
          3: {5: "GT4", 6: "GT5"}, 4: {7: "GT4"}}
    b0 = {1: {1: 10, 2: 20}, 2: {3: 11, 4: 21},
          3: {5: 10, 6: 21}, 4: {7: 10}}
    branch = copy.deepcopy(b0)
    branch[3][5] = 21  # Wrong link to GT5, even though GT4 has fragmented B0 IDs.
    branch[4][7] = 21  # A correct commit frame alone would miss later damage.
    result = association_relation_audit(b0, branch, gt)
    assert result["scorable_pairs"] > 0 and result["harms"]
    assert {x["current_gt"] for x in result["harms"]} == {"GT4"}
    assert any(x["error"] == "wrong_different_GT" for x in result["harms"])
    assert any(x["frame"] == 4 for x in result["harms"])
    missing = copy.deepcopy(gt)
    missing[3].pop(5)
    assert association_relation_audit(b0, branch, missing)["unscorable_pairs"] > 0
    missed = copy.deepcopy(branch)
    missed[3].pop(5)
    assert association_relation_audit(b0, missed, gt)["unscorable_pairs"] > 0
    duplicate = copy.deepcopy(branch)
    duplicate[3][6] = duplicate[3][5]
    assert association_relation_audit(b0, duplicate, gt)["harms"]
    full_gt = {f: {1: "GT4", 2: "GT5"} for f in range(1, 171)}
    full_branch = {f: {1: 10, 2: 20} for f in full_gt}
    full_branch[120][2] = 10
    windows = followup_horizons(1, "GT4", 10, full_branch, full_gt)
    assert windows["30"]["stable"] and windows["90"]["stable"]
    assert not windows["150"]["stable"] and windows["150"]["errors"]
    short = followup_horizons(160, "GT4", 10, full_branch, full_gt)
    assert short["30"]["truncated"] and not short["30"]["stable"]
    assert short["remainder"]["stable"]
    return ["fragmented_GT4_GT5_included", "wrong_link", "later_harm", "missing_GT_retained",
            "missed_prediction_unscorable", "duplicate_identity_harm", "fixed_followup_windows", "right_censoring"]


def fixed_b0_replay(source, config):
    runner = RepairedRunner(config, "B0")
    count = 0
    provenance = None
    for (row, profiles), old in zip(
        stream(source / "inputs/observations_validation.jsonl.gz",
               source / "inputs/features_validation.jsonl.gz", 2888, 9301),
        rows(source / "inputs/predictions_validation_archived.jsonl.gz"), strict=True
    ):
        if row["frame"] == 241:
            view = runner.bridge.preview(row["frame"], row["time"], row["observations"], profiles)
            state = state_for(runner.bridge, view, compile_view(runner.bridge, view))
            provenance = [x for x in state["native_decision_provenance"] if x["depth_mm"]["history_depth"] is not None]
            assert provenance and all(x["depth_history_source"] and
                                      x["depth_history_source"]["anchor"] for x in provenance)
            old_request = read(OLD / "requests/R000010.json")
            old_state = json.loads(old_request["messages"][1]["content"])["state"]
            assert any(x["anchor"] is None and x["depth_mm"]["history_depth"] is not None
                       for x in old_state["native_decision_provenance"])
            assert len(state["H0"]["full_mapping"]) == len(old_state["H0"]["full_mapping"])
        ids, _, record = runner.step(row, profiles)
        predicted = [dict(id=ids[o["id"]], mask=o["mask"]) for o in row["native"]]
        assert predicted == old["variants"]["Z4Q_STABLE"], row["frame"]
        assert record["committed"] is None
        count += 1
    assert count == 2888
    return dict(frames=count, R000010_depth_source_count=len(provenance))


def main(source):
    config = read(OLD / "z4q_source/CONFIG.json")
    checks = []
    checks += epoch_checks(config)
    checks += atomic_checks(config)
    checks += scoring_checks()
    old_tests.legal_single_reconnect(config)
    old_tests.legal_atomic_swap(config)
    old_tests.candidate_withdrawal_and_occupancy(config)
    old_tests.episode_invalidation_contract()
    old_tests.native_return(config)
    old_tests.input_contract(config)
    checks += ["original_single_reconnect", "original_atomic_swap", "original_three_check_budget",
               "original_native_return", "original_input_contract"]
    replay = fixed_b0_replay(source, config)
    result = dict(status="PASS_R0_ENGINEERING_NO_API_NO_GT", checks=checks,
                  fixed_B0=replay, API_calls=0,
                  source_hashes={name: hashlib.sha256((HERE / "r0_source" / name).read_bytes()).hexdigest()
                                 for name in ("bridge.py", "policy.py", "runner.py", "scoring.py")})
    target = HERE / "TEST_REPORT_FINAL.json"
    assert not target.exists(), target
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(result["status"], len(checks), replay["frames"])


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: r0_checks.py ORIGINAL_SIDE_DIRECTORY")
    main(Path(sys.argv[1]).resolve())
