"""Read the exposed AO1 answer key only after M1 outputs are sealed."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, data: object) -> None:
    assert not path.exists(), path
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def canonical(request: dict, response: dict, correct: str) -> dict:
    decision = response["decision"]
    choice = decision["choice"] if decision else None
    original = request["candidate_to_original"].get(choice, choice)
    usable = bool(decision and decision["usable_decision"])
    status = ("INVALID" if not usable else "ABSTAIN" if choice == "INSUFFICIENT" else
              "CORRECT" if original == correct else "WRONG")
    return dict(attempt_id=request["attempt_id"], arm=request["arm"],
                raw_choice=choice, canonical_choice=original, status=status,
                transport_valid=response["transport_valid"],
                decision_valid=bool(decision and decision["decision_valid"]),
                usable_decision=usable,
                grounding_format_valid=bool(decision and decision["grounding_format_valid"]),
                grounding_reason=decision["grounding_reason"] if decision else None,
                grounding_semantics="UNKNOWN_NOT_INDEPENDENTLY_VERIFIED",
                citations=decision.get("evidence") if decision else None,
                finish_reason=response["finish_reason"],
                latency_seconds=response["latency_seconds"], usage=response["usage"],
                returned_model=response["returned_model"],
                charged_upper_usd=response["charged_upper_usd"])


def main(args: argparse.Namespace) -> None:
    run = args.run
    seal = load(run / "public/DECISIONS_SEALED.json")
    assert seal["status"] == "ALL_30_CALLS_SEALED_BEFORE_SCORING"
    manifest = load(run / "public/REQUEST_MANIFEST.json")
    requests = manifest["requests"]
    assert len(requests) == len(seal["attempts"]) == 30
    scored = load(args.score_key)
    answers = {x["case_alias"]: x["private_score_answer"] for x in scored["cases"]}
    assert set(answers) == {"B01", "B02", "B03", "B04", "B05"}
    results = {}
    for request in requests:
        ident = request["attempt_id"]
        response = load(run / "public/responses" / (ident + ".json"))
        results[ident] = canonical(request, response, answers[request["case_alias"]])
    out = args.out
    assert not out.exists()
    out.mkdir(parents=True)
    event_rows = []
    for alias in sorted(answers):
        selected = {x["arm"]: results[x["attempt_id"]] for x in requests if x["case_alias"] == alias}
        assert len(selected) == 6
        baseline = answers[alias] if alias != "B01" else ("C2" if answers[alias] == "C1" else "C1")
        first = {arm: selected[arm] for arm in ("P0", "P1", "P2")}
        simulated = {arm: (baseline if row["status"] == "ABSTAIN" else row["canonical_choice"]
                           if row["usable_decision"] else None)
                     for arm, row in first.items()}
        repeat = selected["P2_REPEAT"]
        permuted = selected["P2_PERMUTED"]
        no_image = selected["P2_NO_IMAGE"]
        event_rows.append(dict(case_alias=alias, case_role="AO0_POSITIVE" if alias == "B01" else
                               "OLD_HARM_NEGATIVE", answer_canonical=answers[alias],
                               baseline_canonical=baseline, first=first,
                               abstain_B0_fallback_simulated=simulated,
                               repeat=repeat, permutation=permuted, no_image=no_image,
                               repeat_same_as_first=(repeat["canonical_choice"] == first["P2"]["canonical_choice"]
                                   if repeat["usable_decision"] and first["P2"]["usable_decision"] else None),
                               permutation_same_as_first=(permuted["canonical_choice"] == first["P2"]["canonical_choice"]
                                   if permuted["usable_decision"] and first["P2"]["usable_decision"] else None),
                               no_image_visual_attribution=("UNKNOWN_INVALID" if not no_image["usable_decision"] or
                                                            not first["P2"]["usable_decision"] else
                                                            "UNRESOLVED" if no_image["canonical_choice"] == first["P2"]["canonical_choice"]
                                                            else "DIFFERENT_CHOICE_NOT_CAUSAL_PROOF")))
    (out / "EVENT_RESULTS.jsonl").write_text("".join(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n"
                                                  for row in event_rows), encoding="utf-8")
    arm_counts = {arm: dict(Counter(row["first"][arm]["status"] for row in event_rows))
                  for arm in ("P0", "P1", "P2")}
    all_valid = sum(row["decision_valid"] for row in results.values())
    main_usable = sum(row["first"][arm]["usable_decision"] for row in event_rows for arm in ("P0", "P1", "P2"))
    repeat_agreement = [row["repeat_same_as_first"] for row in event_rows]
    perm_agreement = [row["permutation_same_as_first"] for row in event_rows]
    positive = event_rows[0]
    negative = event_rows[1:]
    stability = positive["repeat_same_as_first"] is True and positive["permutation_same_as_first"] is True
    stable_negative = all(row["first"]["P2"]["status"] in ("CORRECT", "ABSTAIN") and
                          row["repeat"]["status"] in ("CORRECT", "ABSTAIN") and
                          row["permutation"]["status"] in ("CORRECT", "ABSTAIN") for row in negative)
    cites_real = (positive["first"]["P2"]["grounding_format_valid"] and
                  bool(positive["first"]["P2"]["citations"]))
    if main_usable != 15 or all_valid < 29:
        verdict = "ENGINEERING_FAILURE_OR_INCONCLUSIVE_TECHNICAL"
    elif positive["first"]["P2"]["status"] == "CORRECT" and stability and stable_negative and cites_real:
        verdict = "TENTATIVE_SINGLE_EVENT_VLM_CHOICE_SIGNAL_NOT_METHOD_PASS"
    elif positive["first"]["P2"]["status"] == "CORRECT" and not stability:
        verdict = "INCONCLUSIVE_UNSTABLE"
    else:
        verdict = "FAIL_STOP_THIS_FROZEN_VLM_INTERFACE"
    ledger = [json.loads(line) for line in (run / "public/CALL_LEDGER.jsonl").read_text().splitlines()]
    ends = [x for x in ledger if x["phase"] == "END"]
    total_upper = sum(x["charged_upper_usd"] for x in ends)
    unknown_count = sum(not x["transport_valid"] for x in ends)
    summary = dict(status=verdict, research_calls=30, inference_http_attempts=len(ends),
                   research_decision_valid=all_valid, research_decision_valid_rate=all_valid / 30,
                   main_usable=main_usable, main_arm_counts=arm_counts,
                   repeat_agreement_all_five=sum(x is True for x in repeat_agreement),
                   repeat_both_usable=sum(x is not None for x in repeat_agreement),
                   permutation_agreement_all_five=sum(x is True for x in perm_agreement),
                   permutation_both_usable=sum(x is not None for x in perm_agreement),
                   no_image_counts=dict(Counter(row["no_image"]["status"] for row in event_rows)),
                   no_image_same_choice=sum(row["no_image"]["usable_decision"] and row["first"]["P2"]["usable_decision"] and
                                            row["no_image"]["canonical_choice"] == row["first"]["P2"]["canonical_choice"]
                                            for row in event_rows),
                   unique_positive_case_count=1, negative_case_count=4,
                   research_latency_sum_seconds=sum(x["latency_seconds"] for x in results.values()),
                   research_latency_max_seconds=max(x["latency_seconds"] for x in results.values()),
                   charged_peak_price_upper_usd=total_upper, uncertain_charge_count=unknown_count,
                   visual_semantics="UNKNOWN_NOT_INDEPENDENTLY_VERIFIED",
                   new_idf1_hota_computed=False)
    write(out / "SUMMARY.json", summary)
    failures = [f"# Frozen M1 failure cases\n\nTechnical/scientific decision: `{verdict}`.\n\n"]
    for row in event_rows:
        failures.append(f"- {row['case_alias']}: first P0/P1/P2 = " +
                        "/".join(row["first"][arm]["status"] for arm in ("P0", "P1", "P2")) +
                        f"; repeat={row['repeat']['status']}; permutation={row['permutation']['status']}; "
                        f"no-image={row['no_image']['status']}. Citations and raw choices are in EVENT_RESULTS.jsonl.\n")
    (out / "FAILURE_CASES.md").write_text("".join(failures), encoding="utf-8")
    (out / "RESULTS.md").write_text(
        "# M1 real DeepSeek VLM pilot\n\n" +
        f"Fixed base `bdf1ba5`; 5 exposed cases, 30 research attempts and {len(ends)-30} technical smoke attempts. "
        f"Outcome: **{verdict}**. All old predictions/scores stayed unchanged.\n\n" +
        f"Main usable bound choices: {main_usable}/15; decision-valid: {all_valid}/30. "
        f"First-arm counts: `{json.dumps(arm_counts)}`. "
        f"Repeat agreement {summary['repeat_agreement_all_five']}/5 overall and "
        f"{summary['repeat_agreement_all_five']}/{summary['repeat_both_usable']} both-usable; "
        f"permutation {summary['permutation_agreement_all_five']}/5 overall and "
        f"{summary['permutation_agreement_all_five']}/{summary['permutation_both_usable']} both-usable. "
        f"No-image status counts: `{json.dumps(summary['no_image_counts'])}`.\n\n" +
        f"Peak-price upper accounting including uncertain attempts: USD {total_upper:.6f}; "
        f"unknown-charge attempts {unknown_count}. This is not the provider invoice. "
        "Visual grounding semantics remain UNKNOWN without independent pixel review; format is separate. "
        "No offline association answer is a new IDF1/HOTA measurement or E2 authorization. "
        "See EVENT_RESULTS.jsonl for every first, repeat, permuted, and image-off decision.\n", encoding="utf-8")
    next_step = ("Freeze an independent, previously unexposed set of recoverability interactions for validation; "
                 "do not retune or replay these five exposed cases." if verdict.startswith("TENTATIVE") else
                 "Audit this frozen pilot's failures and stop this interface; do not retune on these same five cases.")
    (out / "NEXT_DECISION.md").write_text(f"# One next step\n\n{next_step}\n", encoding="utf-8")
    print(json.dumps(dict(status=verdict, usable=main_usable, valid=all_valid, cost_upper_usd=total_upper)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--score-key", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    main(parser.parse_args())
