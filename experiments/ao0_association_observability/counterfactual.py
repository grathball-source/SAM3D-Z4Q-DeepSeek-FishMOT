"""One frozen AO0 case: output-only relation oracle vs real Bridge.stage/commit."""
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
from bridge import Bridge, stream  # noqa: E402


def sha(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def rows(path):
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        yield from map(json.loads, handle)


def stage_diagnostics(bridge, view, changes):
    obs = {o["id"]: o for o in view["observations"]}
    result = dict(preview_version=view["version"], bridge_version=bridge.version,
                  original_mapping=view["mapping"], desired_mapping=dict(view["mapping"], **{}),
                  target_checks={})
    result["desired_mapping"].update(changes)
    result["unique_target_occupancy"] = len(set(result["desired_mapping"].values())) == len(result["desired_mapping"])
    for native, target in changes.items():
        anchor = bridge.engine.bank.get(target, {}).get("anchor")
        return_checks = [c for c in view["trace"].get("native_return_checks", [])
                         if c["native_id"] == target and c.get("qualified")]
        result["target_checks"][str(native)] = dict(target_public=target,
            original_quality=bool(bridge.engine.quality(obs[native])),
            current_neighbors=obs[native].get("neighbors", []),
            anchor=anchor, past_anchor=bool(anchor and anchor["frame"] < view["frame"]),
            qualified_native_return=return_checks)
    return result


def run(args):
    manifest = json.loads(args.manifest.read_text())["first_case"]
    query = manifest["query_frame"]
    assert manifest["output_oracle_id_domain"] == [1, 4]
    expected = manifest["input_provenance"]
    assert sha(args.baseline) == expected["RQ0_B0_predictions_sha256"]
    assert sha(args.observations) == expected["observations_sha256"]
    assert sha(args.depth) == expected["depth_sha256"]
    config = json.loads((ROOT / "online/closed_loop_2888/z4q_source/CONFIG.json").read_text())
    bridge = Bridge(config)
    oracle = HERE / "OUTPUT_ORACLE_validation.jsonl.gz"
    state = HERE / "STATE_PREDICTIONS_validation.jsonl.gz"
    action_path = HERE / "STATE_ACTION.json"
    seal_path = HERE / "COUNTERFACTUAL_SEAL.json"
    assert not any(p.exists() for p in (oracle, state, action_path, seal_path))
    action = None
    changed_oracle = changed_state = 0
    frames = 0
    with gzip.open(oracle, "wt", encoding="utf-8") as oracle_file, gzip.open(state, "wt", encoding="utf-8") as state_file:
        for (row, profiles), archived in zip(stream(args.observations, args.depth), rows(args.baseline), strict=True):
            frame = row["frame"]
            view = bridge.preview(frame, row["time"], row["observations"], profiles)
            baseline = archived["variants"]["B0"]
            if frame <= query:
                preview = [dict(id=view["mapping"][o["id"]], mask=o["mask"]) for o in row["native"]]
                assert preview == baseline, (frame, "real bridge prequery parity")
            transaction = None
            if frame == query:
                assert row["global_frame"] == manifest["query_global_frame"]
                assert row["time"] == manifest["query_time_seconds"]
                assert view["mapping"][1] == 1 and view["mapping"][4] == 4
                assert [1, view["epochs"][1]] == manifest["query_native_epoch"]["public_1"]
                assert [4, view["epochs"][4]] == manifest["query_native_epoch"]["public_4"]
                changes = {1: 4, 4: 1}
                diagnostics = stage_diagnostics(bridge, view, changes)
                transaction, reason = bridge.stage(view, changes)
                action = dict(query_frame=query, proposed_changes=changes,
                              stage_accepted=transaction is not None, stage_rejection=reason,
                              diagnostics=diagnostics, state_action="COMMITTED" if transaction else "STATE_ACTION_BLOCKED")
            ids, trace = bridge.commit_once(view, transaction)
            state_objects = [dict(id=ids[o["id"]], mask=o["mask"]) for o in row["native"]]
            oracle_objects = [dict(id=({1: 4, 4: 1}.get(x["id"], x["id"]) if frame >= query else x["id"]),
                                   mask=x["mask"]) for x in baseline]
            assert [x["mask"] for x in baseline] == [x["mask"] for x in oracle_objects] == [x["mask"] for x in state_objects]
            assert len({x["id"] for x in oracle_objects}) == len(oracle_objects)
            assert len({x["id"] for x in state_objects}) == len(state_objects)
            changed_oracle += oracle_objects != baseline
            changed_state += state_objects != baseline
            oracle_file.write(json.dumps(dict(frame=frame, global_frame=row["global_frame"],
                                              B0=baseline, KEEP=baseline, SWAP=oracle_objects), separators=(",", ":")) + "\n")
            state_file.write(json.dumps(dict(frame=frame, global_frame=row["global_frame"],
                                             B0=baseline, STATE=state_objects,
                                             trace_edges=trace.get("edges") if frame == query else None), separators=(",", ":")) + "\n")
            frames += 1
    assert frames == 2888 and action is not None
    action["changed_output_frames"] = changed_state
    action["all_objects_followup_required"] = True
    action_path.write_text(json.dumps(action, indent=2, default=str) + "\n")
    seal = dict(status="PREDICTIONS_SEALED_BEFORE_GT_SCORE", frames=frames, query_frame=query,
                output_oracle_changed_frames=changed_oracle, state_changed_frames=changed_state,
                manifest_sha256=sha(args.manifest), baseline_sha256=sha(args.baseline),
                output_oracle_sha256=sha(oracle), state_predictions_sha256=sha(state),
                action_sha256=sha(action_path), GT_read=False, allow_api=False)
    seal_path.write_text(json.dumps(seal, indent=2) + "\n")
    print(json.dumps(dict(action=action["state_action"], rejection=action["stage_rejection"],
                          output_oracle_changed_frames=changed_oracle, state_changed_frames=changed_state)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for name in ("manifest", "baseline", "observations", "depth"):
        parser.add_argument("--" + name, type=Path, required=True)
    run(parser.parse_args())
