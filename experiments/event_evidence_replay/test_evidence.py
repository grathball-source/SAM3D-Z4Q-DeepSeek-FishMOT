"""Source, time, provenance and branch semantics checks before inference."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import replay as run
from compile import compile_event_evidence

HERE = Path(__file__).resolve().parent
OLD = run.old
source_fact_index = run.source_fact_index
sources = run.sources
PACKETS = HERE / "preflight_output_v7/packets"


def main():
    config = OLD.read(HERE / "CONFIG.json")
    fixed = OLD.cases()
    packets = {case: OLD.read(PACKETS / f"{case}.json") for case in config["cases_by_q"]}
    preflight = OLD.read(HERE / "preflight_output_v7/REPORT.json")
    assert preflight["status"] == "PASS_NO_MODEL_NO_GT" and preflight["frames"] == 2888
    for case, packet in packets.items():
        q = fixed[case]["q"]
        assert packet["q_frame"] == q and len(packet["IMAGE_INDEX"]) == 11
        assert {x["id"] for x in packet["hypotheses"]} == {"H1", "H2"}
        assert packet["raw_source"]["model_view_is_compiled_not_information_equivalent"]
        facts = set()
        for fragment in [*packet["named_fragments"].values(),
                         *packet["anonymous_clean_fragments"]]:
            rows = fragment["observations"]
            assert len(rows) == fragment["samples"]
            assert rows[0][1] == fragment["start_frame"] and rows[-1][1] == fragment["end_frame"]
            assert all(y[1] == x[1] + 1 and y[2] > x[2] for x, y in zip(rows, rows[1:]))
            assert all(x[1] <= q and x[6] in ("CLEAN", "ANONYMOUS_CLEAN_ISLAND") for x in rows)
            assert fragment["identity_scope"] == "SOURCE_CONTIGUOUS_CLEAN_FRAGMENT_ONLY"
            facts.update(x[0] for x in rows)
            facts.update("D-" + x[0] for x in rows)
            for derived in (fragment["velocity"], *fragment["depth_trend"].values()):
                if derived["status"] == "ESTIMATE":
                    assert set(derived["source_fact_ids"]).issubset(facts)
                    facts.add(derived["fact_id"])
        for interval in packet["risk_intervals"]:
            assert interval["identity_scope"] == "ANONYMOUS_RISK_OBSERVATIONS_NO_EDGES"
            assert all(x[1] <= q and x[6] in ("CONTACT_RISK", "ZERO_AREA")
                       for x in interval["observations"])
            facts.update(x[0] for x in interval["observations"])
        assert sum(x["observation_count"] for x in packet["risk_intervals"]) == packet["risk_observation_count"]
        assert (sum(x["samples"] for x in packet["anonymous_clean_fragments"]) +
                packet["risk_observation_count"] ==
                len(fixed[case]["packet"]["INTERACTION_TABLE"]["rows"]))
        assert all(x["observed_fact_id"] in facts for x in packet["current_other_roles"])
        for h in packet["hypotheses"]:
            assert set(h["mapping"]) == {"X", "Y", "U1", "U2", "U3", "U4"}
            assert h["epistemic_type"] == "HYPOTHESIS_NOT_OBSERVED_PATH"
            for edge in h["edge_comparisons"].values():
                assert set(edge["source_fact_ids"]).issubset(facts)
                assert edge["gap_to_post_start_seconds"] > 0
                for part in ("core", "whole"):
                    cue = edge["depth_endpoint_weak_cue"][part]
                    if cue["status"] != "UNKNOWN":
                        assert cue["status"] == "DESCRIPTIVE_ONLY_NOT_IDENTITY_PROOF"
                        assert set(cue["source_fact_ids"]).issubset(facts)
        assert all(x["frame"] <= q for x in packet["IMAGE_INDEX"])
        assert "SRC-F" not in OLD.wire(packet).decode()
    assert packets["B01"]["named_fragments"]["A"]["velocity"]["status"] == "UNKNOWN"
    assert packets["B05"]["named_fragments"]["Y"]["velocity"]["status"] == "UNKNOWN"
    b03 = packets["B03"]["relative_motion"]
    assert b03["pre_raw_different_times"]["raw_B_minus_A_px_at_different_times"] == [37.0, -3.5]
    assert b03["pre_aligned_estimate"]["relative_position_B_minus_A_px"] == [35.538, 5.102]
    assert b03["pre_aligned_estimate"]["interpretation"] == "PROJECTED_ESTIMATE_NOT_OBSERVED_SAME_TIME_ORDER"
    assert OLD.parse_choice('{"preferred_hypothesis":"H1","version":2,"reason":"test"}', "stop") == ("H1", "VALID")
    assert OLD.parse_choice('{"preferred_hypothesis":"H1","choice":"H2"}', "stop")[0] is None
    assert OLD.parse_choice('{"preferred_hypothesis":"H1","preferred_hypothesis":"H2"}', "stop")[0] is None

    # A q+1 mutation cannot change a q packet; a source mutation within q must fail.
    obs, depth = sources()
    lineage = source_fact_index()
    case = "B03"
    preview = OLD.read(HERE / "preflight_output_v7/previews/B03.json")
    view = {"mapping": {int(k): v for k, v in preview["before"].items()}}
    refs = preview["references"]
    physical = OLD.hypotheses(packets[case], refs, view, fixed[case]["native"])
    renamed = copy.deepcopy(packets[case])
    for h in renamed["hypotheses"]:
        h["id"] = {"H1": "H2", "H2": "H1"}[h["id"]]
    permuted = OLD.hypotheses(renamed, refs, view, fixed[case]["native"])
    assert physical["H1"]["full"] == permuted["H2"]["full"]
    assert physical["H2"]["full"] == permuted["H1"]["full"]
    context = dict(source_fact_by_observed=copy.deepcopy(lineage[case]["by_observed"]),
                   case_source_fact_ids=lineage[case]["source_ids"], view=view, refs=refs,
                   images=fixed[case]["packet"]["IMAGE_INDEX"])
    original, _ = compile_event_evidence(dict(fixed[case], case=case), obs, depth, context)
    assert OLD.wire(original) == OLD.wire(packets[case])
    after = dict(obs)
    after[fixed[case]["q"] + 1] = {"time": -123, "observations": [], "frame": fixed[case]["q"] + 1}
    unchanged, _ = compile_event_evidence(dict(fixed[case], case=case), after, depth, context)
    assert OLD.wire(unchanged) == OLD.wire(original)
    altered = dict(obs)
    anchor = fixed[case]["anchors"]["A"]
    altered[anchor] = copy.deepcopy(obs[anchor])
    target = next(x for x in altered[anchor]["observations"] if x["id"] == fixed[case]["native"]["A"])
    target["area"] += 1
    try:
        compile_event_evidence(dict(fixed[case], case=case), altered, depth, context)
    except AssertionError:
        pass
    else:
        raise AssertionError("source mutation was accepted")
    assert all(any(v.get("mapping_changed") and v.get("next_frame_from_committed_branch")
                       for v in preflight["cases"][case]["stage_semantics"].values())
               for case in config["cases_by_q"])
    report = dict(status="PASS_NO_MODEL_NO_GT", checks=[
        "2888_EXACT_B0", "FOUR_REAL_STAGE_AND_NEXT_FRAME_STATE", "RISK_SPLIT_AND_ANONYMOUS_RETENTION",
        "B01_B05_UNKNOWN_VELOCITY", "B03_OBSERVED_VS_PROJECTED_TIME_ALIGNMENT",
        "SOURCE_FACT_REFERENCES", "CURRENT_U_BINDING", "Q_PLUS_ONE_INVARIANCE",
        "SOURCE_TAMPER_REJECTED", "CANDIDATE_REORDER_PHYSICAL_BINDING",
        "TOLERANT_BUT_UNAMBIGUOUS_PARSER"],
        source_preflight_sha256=OLD.sha(HERE / "preflight_output_v7/REPORT.json"))
    (HERE / "TEST_REPORT.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
