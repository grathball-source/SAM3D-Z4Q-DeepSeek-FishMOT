"""No GT/API: source compilation, full B0 parity, and real Bridge transaction semantics."""
from __future__ import annotations

import gzip
import importlib.util
import json
import sys
import copy
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("frozen_direct_replay_preflight",
                                              HERE.parent / "direct_history_replay/replay.py")
old = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old)
from compile import compile_event_evidence, render_overview  # noqa: E402


def source_fact_index():
    facts = old.read(old.SOURCE / "SOURCE_FACT_MANIFEST.json")["facts"]
    result = {case: {"by_observed": {}, "source_ids": set()} for case in old.read(HERE / "CONFIG.json")["cases_by_q"]}
    for x in facts:
        if x["case"] not in result:
            continue
        native = int(x["source_fact_id"].rsplit("-N", 1)[1])
        value = dict(frame=x["frame"], native=native, source_fact_id=x["source_fact_id"])
        result[x["case"]]["source_ids"].add(x["source_fact_id"])
        prior = result[x["case"]]["by_observed"].setdefault(x["observed_fact_id"], value)
        assert prior == value
    return result


def sources():
    observations = {x["frame"]: x for x in old.rows(old.OBS)}
    depth = {x["frame"]: x for x in old.rows(old.PROFILES)}
    assert list(observations) == list(depth) == list(range(1, 2889))
    assert all(observations[f]["time"] == depth[f]["time"] for f in observations)
    return observations, depth


def main():
    fixed = old.cases()
    lineage = source_fact_index()
    obs, depth = sources()
    refs = {case: {} for case in fixed}
    anchors = {}
    for case, item in fixed.items():
        for role, frame in item["anchors"].items():
            anchors.setdefault(frame, []).append((case, role, item["native"][role]))
    bridge = old.Bridge(old.read(old.Z4Q / "z4q_source/CONFIG.json"))
    packets, private, previews = {}, {}, {}
    count = 0
    for frame, archived in zip(range(1, 2889), old.rows(old.ARCHIVED), strict=True):
        row = obs[frame]
        profiles = {x["id"]: dict(x, frame=frame) for x in depth[frame]["observations"]}
        view = bridge.preview(frame, row["time"], row["observations"], profiles)
        for case in old.read(HERE / "CONFIG.json")["cases_by_q"]:
            item = fixed[case]
            if item["q"] != frame:
                continue
            packet, debug = compile_event_evidence(dict(item, case=case), obs, depth,
                dict(source_fact_by_observed=lineage[case]["by_observed"],
                     case_source_fact_ids=lineage[case]["source_ids"], view=view, refs=refs[case],
                     images=item["packet"]["IMAGE_INDEX"]))
            physical = old.hypotheses(packet, refs[case], view, item["native"])
            packets[case], private[case] = packet, debug
            previews[case] = dict(before=view["mapping"], physical=physical,
                                  references=refs[case])
            # Stage a real legal edit on an isolated copy, without selecting an action.
            stages = {}
            for choice in ("H1", "H2"):
                delta = old.changes(choice, physical, view["mapping"])
                if delta and physical[choice]["one_to_one"]:
                    trial, reason = bridge.stage(view, delta)
                    stages[choice] = {"changes": delta, "accepted": trial is not None,
                                      "reject_reason": reason,
                                      "mapping_changed": bool(trial and trial["mapping"] != view["mapping"])}
                    if trial is not None:
                        branch = copy.deepcopy(bridge)
                        changed, _ = branch.commit_once(view, trial)
                        assert changed == trial["mapping"] and changed != view["mapping"]
                        nxt = obs[frame + 1]
                        nxt_profiles = {x["id"]: dict(x, frame=frame + 1)
                                        for x in depth[frame + 1]["observations"]}
                        stages[choice]["next_frame_from_committed_branch"] = branch.preview(
                            frame + 1, nxt["time"], nxt["observations"], nxt_profiles)["mapping"]
                else:
                    stages[choice] = {"changes": delta, "accepted": not delta,
                                      "reject_reason": None if not delta else "occupied_target",
                                      "mapping_changed": False}
            previews[case]["stage_semantics"] = stages
        ids, _ = bridge.commit_once(view)
        for case, role, native in anchors.get(frame, []):
            refs[case][role] = dict(anchor_frame=frame, native=native,
                                    public_id=ids[native], epoch=bridge.epochs[native],
                                    branch_version=bridge.version)
        got = [dict(id=ids[x["id"]], mask=x["mask"]) for x in row["native"]]
        assert got == archived["variants"]["Z4Q_STABLE"], frame
        count += 1
    assert count == 2888 and len(packets) == 4
    result = {"status": "PASS_NO_MODEL_NO_GT", "frames": count,
              "input_sha256": {str(p): old.sha(p) for p in (old.OBS, old.PROFILES, old.ARCHIVED)},
              "cases": {case: dict(q=packets[case]["q_frame"],
                                    named={r: x["samples"] for r, x in packets[case]["named_fragments"].items()},
                                    anonymous_fragments=len(packets[case]["anonymous_clean_fragments"]),
                                    risk_observations=packets[case]["risk_observation_count"],
                                    stage_semantics=previews[case]["stage_semantics"])
                        for case in packets}}
    out = HERE / "preflight_output_v7"
    out.mkdir(exist_ok=True)
    for case, packet in packets.items():
        old.store(out / "packets" / (case + ".json"), packet)
        old.store(out / "private" / (case + ".json"), private[case])
        old.store(out / "previews" / (case + ".json"), previews[case])
        overview = render_overview(packet, out / "overviews" / (case + ".png"))
        old.store(out / "overviews" / (case + ".metadata.json"), overview)
    old.store(out / "REPORT.json", result)
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
