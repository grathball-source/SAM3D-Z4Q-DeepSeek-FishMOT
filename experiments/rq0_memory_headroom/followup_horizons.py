"""All-individual 30/90/150 and remaining output follow-up after vetoes."""
import gzip
import json
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = json.loads((HERE.parent / "vl_assoc_e1c/RUN_RECORD.json").read_text())["sources"]
ARMS = ("Q-rule", "Q-visible-oracle", "quota")


def rows(path):
    with gzip.open(path, "rt") as handle:
        yield from map(json.loads, handle)


output = HERE / "FOLLOWUP_HORIZONS.jsonl"
assert not output.exists()
with output.open("x") as out:
    for split in ("development", "validation"):
        match_path = Path(SOURCE["exposed_matches"].replace("{development,validation}", split))
        prediction_path = HERE / f"PREDICTIONS_{split}.jsonl.gz"
        vetoes = defaultdict(set)
        for audit in rows(HERE / f"REFERENCE_WRITE_READ_AUDIT_{split}.jsonl.gz"):
            if audit["kind"] == "VETO":
                vetoes[audit["arm"]].add(audit["frame"])
        changes = defaultdict(list)
        individuals = set()
        for match, prediction in zip(rows(match_path), rows(prediction_path), strict=True):
            frame = prediction["frame"]
            maps = {arm: {int(x["mask"].split(":")[1]): x["id"] for x in prediction["variants"][arm]}
                    for arm in ("B0",) + ARMS}
            by_gt = defaultdict(list)
            for obj in match["objects"]:
                if obj.get("gt_id") is not None and not obj.get("ambiguity"):
                    by_gt[int(obj["gt_id"])].append(int(obj["native_id"]))
                    individuals.add(int(obj["gt_id"]))
            for gt, natives in by_gt.items():
                if len(natives) != 1:
                    continue
                native = natives[0]
                for arm in ARMS:
                    if maps[arm][native] != maps["B0"][native]:
                        changes[(arm, gt)].append(frame)
        for arm in ARMS:
            origins = sorted(vetoes[arm])
            if arm == "Q-rule" and origins:
                origins = origins[:1]  # thousands of later vetoes share one continuous state; no additive event claims
            for gt in sorted(individuals):
                changed = changes[(arm, gt)]
                for origin in origins or [None]:
                    out.write(json.dumps(dict(split=split, arm=arm, gt_id=gt, veto_origin=origin,
                                              branch_output_different_frames=len(changed),
                                              within_30=sum(origin is not None and origin <= f <= origin + 30 for f in changed),
                                              within_90=sum(origin is not None and origin <= f <= origin + 90 for f in changed),
                                              within_150=sum(origin is not None and origin <= f <= origin + 150 for f in changed),
                                              remaining_after_150=sum(origin is not None and f > origin + 150 for f in changed),
                                              right_censored=bool(changed and changed[-1] == (8400 if split == "development" else 2888)),
                                              note="Q-rule reports only first veto as one continuous intervention, not additive per-veto effects." if arm == "Q-rule" else None)) + "\n")
print(json.dumps(dict(status="ALL_INDIVIDUAL_HORIZONS_RECORDED", rows=sum(1 for _ in output.open()))))
