"""Score sealed B03-only state against frozen B0/B1 with the original scorer.

Run on the lab host after replay_b03_only.py has sealed predictions. The GT
and native-to-GT table are opened only after both prediction seals pass.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path


def load_scorer(path):
    spec = importlib.util.spec_from_file_location("frozen_z4q_score", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def delta(a, b):
    return {key: b[key] - a[key] for key in ("IDF1", "HOTA", "AssA", "DetA", "IDSW", "FP", "FN")}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--old", type=Path, required=True, help="original direct replay public directory")
    parser.add_argument("--scorer", type=Path, required=True, help="frozen original official score.py")
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    score = load_scorer(args.scorer)
    assert score.sha(args.scorer) == "6cb2b7e438e2e98367b86f39e36ac220f90a6036c3f522b0558cec9123a8d811"
    seal = json.loads((here / "B03_ONLY_SEAL.json").read_text(encoding="utf-8"))
    old_seal = json.loads((args.old / "PREDICTIONS_SEALED.json").read_text(encoding="utf-8"))
    pred_b03 = here / "predictions_b03_only.jsonl.gz"
    pred_old = args.old / "predictions_validation.jsonl.gz"
    events_path = here / "EVENTS.json"
    assert seal["status"] == "SEALED_POSTHOC_B03_ONLY_BEFORE_GT_SCORING"
    assert seal["frames"] == seal["mask_equal_frames"] == 2888
    assert seal["exact_b1_prefix_frames"] == 2637
    assert score.sha(pred_b03) == seal["predictions_sha256"]
    assert score.sha(pred_old) == seal["source_prediction_sha256"] == old_seal["predictions_sha256"]
    assert score.sha(events_path) == seal["source_events_sha256"]
    assert score.sha(score.ASSIGN) == score.ASSIGN_SHA
    assert score.sha(score.TRUTH) == score.TRUTH_SHA
    assert score.sha(score.MATCHES) == score.MATCHES_SHA

    gt = []
    predictions = {arm: [] for arm in ("B0", "B03_ONLY", "B1")}
    similarities = {arm: [] for arm in predictions}
    parity = {"b03_prefix_equal_b1": 0, "b03_later_diff_b1": 0, "all_masks_equal": 0}
    baseline_maps = {}
    for frame, (a, old, ablated, t) in enumerate(zip(
        score.rows(score.ASSIGN), score.rows(pred_old), score.rows(pred_b03),
        score.rows(score.TRUTH), strict=True,
    ), 1):
        assert a["frame"] == old["frame"] == ablated["frame"] == frame
        assert old["global_frame"] == ablated["global_frame"] == t["global_frame_id"] == 9300 + frame
        assert old["time"] == ablated["time"] == a["time"]
        native_keys = [x["mask"] for x in a["variants"]["N0"]]
        original = old["variants"]
        current = ablated["variants"]["B03_ONLY"]
        for objects in (original["B0"], original["B1"], current):
            assert [x["mask"] for x in objects] == native_keys
            assert len({int(x["id"]) for x in objects}) == len(objects)
        parity["all_masks_equal"] += 1
        if frame <= 2637:
            assert current == original["B1"]
            parity["b03_prefix_equal_b1"] += 1
        else:
            parity["b03_later_diff_b1"] += current != original["B1"]
        baseline_maps[frame] = {
            int(x["mask"].split(":")[1]): int(x["id"]) for x in original["B0"]
        }
        truth = t["gt_grid"]
        gt.append([int(x["id"]) for x in truth])
        keys = sorted(a["masks"])
        lookup = {key: i for i, key in enumerate(keys)}
        matrix = (score.mu.iou([score.rle(x["rle"]) for x in truth],
                               [score.rle(a["masks"][key]) for key in keys], [0] * len(keys))
                  if truth and keys else score.np.zeros((len(truth), len(keys))))
        for arm, objects in (("B0", original["B0"]), ("B1", original["B1"]),
                             ("B03_ONLY", current)):
            predictions[arm].append([int(x["id"]) for x in objects])
            similarities[arm].append(matrix[:, [lookup[x["mask"]] for x in objects]])
    assert len(gt) == 2888 and parity == {
        "b03_prefix_equal_b1": 2637, "b03_later_diff_b1": 251, "all_masks_equal": 2888}

    full = score.metrics(gt, predictions, similarities)
    prior = json.loads((args.old / "METRICS.json").read_text(encoding="utf-8"))["metrics"]
    for arm in ("B0", "B1"):
        for key, value in prior[arm].items():
            assert abs(full[arm][key] - value) < 1e-8, (arm, key, full[arm][key], value)
    windows = {}
    for name, lo, hi in (("pre_B03", 1, 376), ("B03_to_pre_B04", 377, 2637),
                         ("post_B04", 2638, 2888)):
        cut = slice(lo - 1, hi)
        windows[name] = {"frames": [lo, hi], "metrics": score.metrics(
            gt[cut], {arm: values[cut] for arm, values in predictions.items()},
            {arm: values[cut] for arm, values in similarities.items()})}

    matches = {x["frame"]: x["native_to_gt"] for x in score.rows(score.MATCHES)}
    assert len(matches) == 2888
    fixed = {}
    for frame in range(1, 2889):
        for native, public in baseline_maps[frame].items():
            person = matches[frame].get(str(native))
            if person is not None and public not in fixed:
                fixed[public] = person
    bindings = {}
    for event in json.loads(events_path.read_text(encoding="utf-8")):
        case, q = event["case"], event["frame"]
        references = {}
        for role in ("A", "B"):
            ref = event["references"][role]
            references[role] = {
                "frame": ref["anchor_frame"], "native": ref["native"],
                "branch_public": ref["public_id"],
                "local_gt": matches[ref["anchor_frame"]].get(str(ref["native"])),
                "fixed_public_gt": fixed.get(ref["public_id"]),
            }
        q_roles = {}
        for role in ("X", "Y"):
            native = event["q_native"][role]
            q_roles[role] = {"frame": q, "native": native,
                             "gt": matches[q].get(str(native))}
        bindings[case] = {"references": references, "q": q_roles,
                          "choice": event["choice"], "action": event["status"]}

    result = {
        "status": "POSTHOC_SEQUENTIAL_ABLATION_SCORED",
        "exposure": "EXPOSED_VALIDATION_DIAGNOSTIC_NOT_NEW_MODEL_TRIAL",
        "source": {"old_prediction_sha256": score.sha(pred_old),
                   "b03_only_prediction_sha256": score.sha(pred_b03),
                   "old_seal_sha256": score.sha(args.old / "PREDICTIONS_SEALED.json"),
                   "b03_only_seal_sha256": score.sha(here / "B03_ONLY_SEAL.json"),
                   "scorer_sha256": score.sha(args.scorer),
                   "assign_sha256": score.ASSIGN_SHA, "truth_sha256": score.TRUTH_SHA,
                   "matches_sha256": score.MATCHES_SHA},
        "parity": parity,
        "full": full,
        "full_deltas": {"B03_ONLY_minus_B0": delta(full["B0"], full["B03_ONLY"]),
                        "B1_minus_B03_ONLY": delta(full["B03_ONLY"], full["B1"]),
                        "B1_minus_B0": delta(full["B0"], full["B1"])},
        "windows": windows,
        "postseal_role_gt_binding": bindings,
        "fixed_public_identity": fixed,
        "note": "Full and window TrackEval scores are separate non-additive evaluations. B04 is conditional on B03; no standalone B04-from-B0 effect is claimed.",
    }
    target = here / "COUNTERFACTUAL_METRICS.json"
    with target.open("x", encoding="utf-8", newline="\n") as out:
        json.dump(result, out, ensure_ascii=False, indent=2, allow_nan=False)
        out.write("\n")
    print(json.dumps({"status": result["status"], "full": full,
                      "full_deltas": result["full_deltas"], "parity": parity}))


if __name__ == "__main__":
    main()
