"""Independent post-seal scorer. Run on the lab host with frozen masks and GT."""
from __future__ import annotations

import gzip
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
from pycocotools import mask as mu

for alias, builtin in (("int", int), ("float", float), ("bool", bool)):
    if alias not in np.__dict__:
        setattr(np, alias, builtin)

TRACK_PATH = Path("/home/data2/xiongxiong/dmot-annotation/evaluation/TrackEval-12c8791b303e0a0b50f753af204249e622d0281a")
sys.path.insert(0, str(TRACK_PATH))
import trackeval  # noqa: E402

HERE = Path(__file__).resolve().parent
ASSIGN = Path("/home/data2/xiongxiong/d-mot/experiments/sam3_i3_validation_cpu16_20260915/run_validation_2888/assignments.jsonl.gz")
TRUTH = Path("/home/data2/xiongxiong/d-mot/experiments/sam3_i1_validation_20260915/truth.jsonl.gz")
MATCHES = Path("/home/xiongxiong/dmot-experiments/sam3_depth_return_guard_20260918/experiment/offline_matches_validation.jsonl.gz")
ASSIGN_SHA = "ea468964e4b287a3879dfb83b304dd64c83f055e9649d3155fa62c41b717a0fc"
TRUTH_SHA = "55d88b7edae92c993c4ed0a4340307e696bf7cdbcf853c38cd805d9ec50b6057"
MATCHES_SHA = "5c557ab0dd833e00b4b0d3a6eeec3cdd6e0669f11da4f5e6611619fe5928cbd1"
BASELINE = dict(IDF1=80.69758683623512, HOTA=69.24386895965796,
                AssA=60.07432145541481, IDSW=9, FP=298, FN=423)


def sha(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def rows(path):
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        yield from map(json.loads, handle)


def rle(value):
    return dict(size=value["size"], counts=value["counts"].encode("ascii")
                if isinstance(value["counts"], str) else value["counts"])


def data_for(gt, pred, sims):
    gids = sorted({x for frame in gt for x in frame})
    pids = sorted({x for frame in pred for x in frame})
    gm, pm = ({x: i for i, x in enumerate(gids)}, {x: i for i, x in enumerate(pids)})
    return dict(num_timesteps=len(gt), num_gt_ids=len(gids), num_tracker_ids=len(pids),
        num_gt_dets=sum(map(len, gt)), num_tracker_dets=sum(map(len, pred)),
        gt_ids=[np.array([gm[x] for x in frame], int) for frame in gt],
        tracker_ids=[np.array([pm[x] for x in frame], int) for frame in pred],
        similarity_scores=sims)


def metrics(gt, predictions, similarities):
    out = {}
    for arm, pred in predictions.items():
        data = data_for(gt, pred, similarities[arm])
        clear = trackeval.metrics.CLEAR({"THRESHOLD": .5, "PRINT_CONFIG": False}).eval_sequence(data)
        identity = trackeval.metrics.Identity({"THRESHOLD": .5, "PRINT_CONFIG": False}).eval_sequence(data)
        hota = trackeval.metrics.HOTA({"PRINT_CONFIG": False}).eval_sequence(data)
        out[arm] = dict(IDF1=100 * identity["IDF1"],
                        HOTA=100 * float(np.mean(hota["HOTA"])),
                        AssA=100 * float(np.mean(hota["AssA"])),
                        DetA=100 * float(np.mean(hota["DetA"])),
                        IDSW=int(clear["IDSW"]), FP=int(clear["CLR_FP"]), FN=int(clear["CLR_FN"]))
    return out


def self_test():
    first = np.zeros((10, 10), dtype=np.uint8)
    second = first.copy()
    first[1:4, 1:4] = 1
    second[6:9, 6:9] = 1
    masks = [mu.encode(np.asfortranarray(x)) for x in (first, second)]
    similarity = mu.iou(masks, masks, [0, 0])
    gt = [[1, 2], [1, 2]]
    sims = {"B0": [similarity, similarity], "B1": [similarity, similarity]}
    result = metrics(gt, {"B0": [[1, 2], [1, 2]], "B1": [[1, 2], [2, 1]]}, sims)
    assert result["B0"]["IDF1"] > result["B1"]["IDF1"]
    assert result["B0"]["HOTA"] > result["B1"]["HOTA"]
    assert result["B0"]["FP"] == result["B1"]["FP"] == 0
    assert result["B0"]["FN"] == result["B1"]["FN"] == 0
    print(json.dumps(dict(status="PASS_NONIDENTICAL_SCORER_FIXTURE", metrics=result)))


def save(name, value):
    target = HERE / name
    assert not target.exists(), target
    target.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def full():
    seal = json.loads((HERE / "PREDICTIONS_SEALED.json").read_text(encoding="utf-8"))
    pred_path = HERE / "predictions_validation.jsonl.gz"
    trace_path = HERE / "transactions_validation.jsonl.gz"
    ledger_path = HERE / "CALL_LEDGER.jsonl"
    assert seal["status"] == "SEALED_AWAITING_INDEPENDENT_SCORING"
    assert sha(pred_path) == seal["predictions_sha256"]
    assert sha(trace_path) == seal["transactions_sha256"]
    assert sha(ledger_path) == seal["call_ledger_sha256"]
    assert sha(ASSIGN) == ASSIGN_SHA and sha(TRUTH) == TRUTH_SHA and sha(MATCHES) == MATCHES_SHA
    assert TRACK_PATH.is_dir()

    gt, pred, sims = [], {"B0": [], "B1": []}, {"B0": [], "B1": []}
    maps = {"B0": {}, "B1": {}}
    for index, (a, p, t) in enumerate(zip(rows(ASSIGN), rows(pred_path), rows(TRUTH), strict=True), 1):
        assert a["frame"] == p["frame"] == index
        assert p["global_frame"] == t["global_frame_id"] == 9300 + index
        assert p["time"] == a["time"]
        native = a["variants"]["N0"]
        native_keys = [x["mask"] for x in native]
        gt_ids = [int(x["id"]) for x in t["gt_grid"]]
        gt.append(gt_ids)
        keys = sorted(a["masks"])
        lookup = {key: i for i, key in enumerate(keys)}
        matrix = (mu.iou([rle(x["rle"]) for x in t["gt_grid"]],
                         [rle(a["masks"][key]) for key in keys], [0] * len(keys))
                  if gt_ids and keys else np.zeros((len(gt_ids), len(keys))))
        for arm in ("B0", "B1"):
            objects = p["variants"][arm]
            assert [x["mask"] for x in objects] == native_keys
            ids = [int(x["id"]) for x in objects]
            assert len(ids) == len(set(ids))
            pred[arm].append(ids)
            sims[arm].append(matrix[:, [lookup[x["mask"]] for x in objects]])
            maps[arm][index] = {int(x["mask"].split(":")[1]): int(x["id"]) for x in objects}
    assert len(gt) == seal["frames"] == 2888
    result = metrics(gt, pred, sims)
    for key, value in BASELINE.items():
        assert abs(result["B0"][key] - value) < 1e-8, (key, result["B0"][key], value)

    match_rows = {x["frame"]: x["native_to_gt"] for x in rows(MATCHES)}
    assert len(match_rows) == 2888
    fixed = {}
    for frame in range(1, 2889):
        for native, public in maps["B0"][frame].items():
            individual = match_rows[frame].get(str(native))
            if individual is not None and public not in fixed:
                fixed[public] = individual
    by_gt = {}
    for public, individual in fixed.items():
        by_gt.setdefault(individual, []).append(public)
    harms, improvements = [], []
    for frame in range(1, 2889):
        for native, public0 in maps["B0"][frame].items():
            individual = match_rows[frame].get(str(native))
            candidates = by_gt.get(individual, [])
            if len(candidates) != 1:
                continue
            expected = candidates[0]
            public1 = maps["B1"][frame][native]
            if public0 == expected and public1 != expected:
                harms.append(dict(frame=frame, native=native, gt=individual, expected=expected, B0=public0, B1=public1))
            if public0 != expected and public1 == expected:
                improvements.append(dict(frame=frame, native=native, gt=individual, expected=expected, B0=public0, B1=public1))
    transactions = []
    status_counts = {}
    for line in rows(trace_path):
        frame = line["frame"]
        record = line["variants"]["B1"]
        status = record["status"]
        status_counts[status] = status_counts.get(status, 0) + 1
        if status != "COMMIT":
            continue
        edges = []
        wrong = False
        unscorable = False
        for native_text, target in record["committed"].items():
            native = int(native_text)
            provenance = record["commit_provenance"][str(native)]
            anchor = provenance["anchor"]
            now_gt = match_rows[frame].get(str(native))
            old_gt = match_rows[anchor["frame"]].get(str(anchor["native_id"]))
            target_gt = fixed.get(int(target))
            if None in (now_gt, old_gt, target_gt):
                unscorable = True
            elif now_gt != old_gt or now_gt != target_gt:
                wrong = True
            edges.append(dict(native=native, target=target, current_gt=now_gt,
                              anchor_gt=old_gt, fixed_target_gt=target_gt))
        displaced = [int(n) for n in record["selected_proposal"].get("displaced", [])]
        displaced_results = []
        for native in displaced:
            individual = match_rows[frame].get(str(native))
            candidates = by_gt.get(individual, [])
            actual_public = maps["B1"][frame].get(native)
            if len(candidates) != 1 or actual_public is None:
                unscorable = True
                correct = None
            else:
                correct = actual_public == candidates[0]
                if not correct:
                    wrong = True
            displaced_results.append(dict(native=native, gt=individual,
                                          resulting_public=actual_public, correct=correct))
        verdict = "wrong" if wrong else "unscorable" if unscorable else "correct"
        transactions.append(dict(frame=frame, changes=record["committed"],
                                 verdict=verdict, edges=edges,
                                 displaced_results=displaced_results))

    difference_frames = sum(maps["B0"][f] != maps["B1"][f] for f in range(1, 2889))
    output = dict(status="SCORED_EXPOSED_VALIDATION", metrics=result,
                  difference_frames=difference_frames, transactions=transactions,
                  transaction_counts={k: sum(x["verdict"] == k for x in transactions)
                                      for k in ("correct", "wrong", "unscorable")},
                  status_counts=status_counts, incremental_harm_count=len(harms),
                  incremental_improvement_count=len(improvements),
                  exposure="EXPOSED_VALIDATION_FEASIBILITY_NOT_BLIND",
                  source_prediction_sha256=sha(pred_path))
    save("METRICS.json", output)
    save("FULL_TIMELINE_HARM_AUDIT.json", dict(harms=harms, improvements=improvements,
                                               fixed_public_identity=fixed,
                                               ambiguous_individuals={str(k): v for k, v in by_gt.items() if len(v) != 1}))
    print(json.dumps(dict(status=output["status"], metrics=result,
                          difference_frames=difference_frames, transactions=output["transaction_counts"],
                          harms=len(harms), improvements=len(improvements))))


if __name__ == "__main__":
    if sys.argv[1:] == ["--fixture"]:
        self_test()
    elif not sys.argv[1:]:
        full()
    else:
        raise SystemExit("usage: score.py [--fixture]")
