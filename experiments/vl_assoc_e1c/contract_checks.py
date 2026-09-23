"""Deterministic E1C contract tests; no API and no real GT."""
import copy
import json
from pathlib import Path

from contract import check_lineage, decode, edge, numeric, validate_packet, validate_response


def sample(frame, native, identity, depth, x, *, epoch=1, neighbor=0, hist=None):
    return dict(sequence="S", frame=frame, source_time=float(frame), native_id=native,
                mask_key=f"n:{native}", tracklet_epoch=epoch, identity_hypothesis=identity,
                core=dict(n=100, valid_fraction=1., median=depth, mad=1.),
                RGB_hist_48=hist if hist is not None else [1.] + [0.] * 47,
                center=[float(x), 0.], box=[x - 5., -5., x + 5., 5.], neighbors_count=neighbor)


def node(label, samples):
    return dict(label=label, samples=samples, start_frame=samples[0]["frame"],
                end_frame=samples[-1]["frame"], continuity_checked=True)


def packet():
    history = [node("A", [sample(1, 1, "A", 100, 1), sample(2, 1, "A", 100, 2)]),
               node("B", [sample(1, 2, "B", 200, 10), sample(2, 2, "B", 200, 11)])]
    current = [node("X", [sample(3, 1, "A", 100, 3), sample(4, 1, "A", 100, 4)]),
               node("Y", [sample(3, 3, "K", 200, 12), sample(4, 3, "K", 200, 13)])]
    pairwise = {f"{h['label']}:{c['label']}": edge(h, c) for h in history for c in current}
    evidence = {f"E{a}{b}{m}": dict(source_time=4., pair=f"{a}:{b}",
                                     applicable=pairwise[f"{a}:{b}"]["values"][m] is not None)
                for a in "AB" for b in "XY" for m in "DAM"}
    return dict(schema="VL_ASSOC_RECOVERY_V1", allow_api=False, packet_id="TEST", snapshot_version="v1",
                query_time=4., evidence_cutoff=4., history=history, current=current,
                fixed={}, candidates=[dict(id="C1", mapping={"X": "A", "Y": "K"}),
                                      dict(id="C2", mapping={"X": "A", "Y": "B"})], B0="C1",
                pairwise=pairwise, evidence=evidence, null_cost={"D": 1., "A": 1., "M": 1.})


def run():
    tests = []
    def check(name, condition):
        assert condition, name
        tests.append(name)
    p = packet()
    check("complete_recovery_candidate", validate_packet(p))
    check("same_multiframe_edge_for_numeric_and_model", numeric(p)["selected"] == "C2")
    response = dict(schema=p["schema"], packet_id="TEST", snapshot_version="v1",
                    comparisons=[dict(left="C1", right="C2", relation="RIGHT_BETTER", evidence_ids=["EBYD"])])
    check("legal_model_preference_changes_choice", decode(p, response)["selected"] == "C2")
    off = copy.deepcopy(response)
    off["comparisons"][0]["relation"] = "UNOBSERVABLE"
    off["comparisons"][0]["evidence_ids"] = []
    check("model_off_keeps_B0", decode(p, off)["selected"] == "C1")
    invalid = copy.deepcopy(response)
    invalid["comparisons"][0]["evidence_ids"] = ["UNKNOWN"]
    check("fabricated_evidence_rejected", validate_response(p, invalid)[0] is False)
    irrelevant = copy.deepcopy(p)
    irrelevant["evidence"]["EZZ"] = dict(source_time=4., pair="Z:Z", applicable=True)
    cited = copy.deepcopy(response)
    cited["comparisons"][0]["evidence_ids"] = ["EZZ"]
    check("irrelevant_citation_rejected", validate_response(irrelevant, cited)[0] is False)
    inapplicable = copy.deepcopy(response)
    inapplicable["comparisons"][0]["evidence_ids"] = ["EAXM"]
    p["evidence"]["EAXM"]["applicable"] = False
    check("inapplicable_direction_semantic_fallback", decode(p, inapplicable)["status"] == "SEMANTIC_FALLBACK")
    p["evidence"]["EAXM"]["applicable"] = True
    damaged = copy.deepcopy(p["current"][1])
    damaged["samples"][1]["tracklet_epoch"] = 2
    try:
        check_lineage(damaged, 4.)
    except AssertionError:
        tests.append("epoch_crossing_rejected")
    else:
        raise AssertionError("epoch_crossing_rejected")
    switched = copy.deepcopy(p["current"][1])
    switched["samples"][1]["identity_hypothesis"] = "B"
    try:
        check_lineage(switched, 4.)
    except AssertionError:
        tests.append("public_identity_switch_rejected")
    else:
        raise AssertionError("public_identity_switch_rejected")
    conflicting = copy.deepcopy(p)
    conflicting["pairwise"]["B:Y"]["values"] = {"D": 0., "A": 2., "M": None}
    conflicting["null_cost"] = {"D": 1., "A": 1., "M": None}
    check("P421_D_A_conflict_tie_keeps_B0", numeric(conflicting)["status"] == "TIE_KEEP")
    no_data = copy.deepcopy(p)
    no_data["pairwise"] = {}
    no_data["null_cost"] = {}
    check("missing_modalities_keep_B0", numeric(no_data)["status"] == "NO_EVIDENCE_KEEP")
    mixed = copy.deepcopy(p["current"][1])
    mixed["samples"][0]["neighbors_count"] = 1
    check("mixed_mask_flags_unreliable", edge(p["history"][1], mixed)["mixed_mask"] == "UNRELIABLE")
    duplicate = copy.deepcopy(p)
    duplicate["candidates"][1]["mapping"] = dict(X="A", Y="A")
    try:
        validate_packet(duplicate)
    except AssertionError:
        tests.append("occupied_identity_rejected")
    else:
        raise AssertionError("occupied_identity_rejected")
    result = dict(status="PASS", count=len(tests), tests=tests, API_calls=0, GT_read=False)
    out = Path(__file__).with_name("EVIDENCE_CONTRACT_TESTS.json")
    out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    run()
