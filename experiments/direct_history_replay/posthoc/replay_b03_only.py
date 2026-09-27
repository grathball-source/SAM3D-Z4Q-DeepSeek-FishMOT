"""Post hoc sequential ablation: keep the sealed B03 edit, omit B04.

This replay consumes only the original causal streams and sealed decisions. It
does not read GT, call a model, or modify the original experiment.
"""
from __future__ import annotations

import gzip
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN = HERE.parent
ROOT = RUN.parents[1]
Z4Q = ROOT / "online/closed_loop_2888"
sys.path.insert(0, str(Z4Q / "z4q_source"))
sys.path.insert(0, str(Z4Q))
sys.path.insert(0, str(RUN))
from bridge import Bridge, read, rows, sha, stream  # noqa: E402
from preflight import OBS, PROFILES  # noqa: E402
from replay import no_truth  # noqa: E402


def main():
    old = RUN / "public"
    old_seal = read(old / "PREDICTIONS_SEALED.json")
    old_pred = old / "predictions_validation.jsonl.gz"
    assert old_seal["frames"] == 2888 and old_seal["HTTP_attempts"] == 4
    assert sha(old_pred) == old_seal["predictions_sha256"]
    assert sha(OBS) == "3fc24d623ca3af22520dc7333ba07ad1479bc766425a2c548b1a13aa922a2e87"
    assert sha(PROFILES) == "91a154246748146896ac846f0bdd934bb67be874fe823124263650e88ad62f0e"
    events = read(old / "EVENTS.json")
    assert [(x["case"], x["frame"]) for x in events] == [
        ("B03", 377), ("B01", 1498), ("B05", 2580), ("B04", 2638)]
    b03, b04 = events[0], events[-1]
    assert b03["status"] == b04["status"] == "COMMIT"
    assert b03["changes"] == {"1": 5, "5": 1}
    assert b04["changes"] == {"1": 4, "4": 5}

    target = HERE / "predictions_b03_only.jsonl.gz"
    seal_path = HERE / "B03_ONLY_SEAL.json"
    assert not target.exists() and not seal_path.exists()
    bridge = Bridge(read(Z4Q / "z4q_source/CONFIG.json"))
    sys.addaudithook(no_truth)
    prefix_equal = 0
    mask_equal = 0
    difference_from_b1 = 0
    count = 0
    with gzip.open(target, "xt", encoding="utf-8") as out:
        for (row, profiles), prior in zip(
            stream(OBS, PROFILES, 2888, 9301), rows(old_pred), strict=True
        ):
            frame = row["frame"]
            assert frame == prior["frame"] and row["global_frame"] == prior["global_frame"]
            view = bridge.preview(frame, row["time"], row["observations"], profiles)
            transaction = None
            if frame == b03["frame"]:
                transaction, reason = bridge.stage(
                    view, {int(n): public for n, public in b03["changes"].items()}
                )
                assert reason is None and transaction is not None
            ids, _ = bridge.commit_once(view, transaction)
            current = [{"id": ids[x["id"]], "mask": x["mask"]} for x in row["native"]]
            original = prior["variants"]["B1"]
            assert [x["mask"] for x in current] == [x["mask"] for x in original]
            mask_equal += 1
            if frame < b04["frame"]:
                assert current == original, frame
                prefix_equal += 1
            difference_from_b1 += current != original
            out.write(json.dumps({
                "frame": frame, "global_frame": row["global_frame"], "time": row["time"],
                "variants": {"B03_ONLY": current},
            }, separators=(",", ":")) + "\n")
            count += 1
    assert count == mask_equal == 2888 and prefix_equal == 2637
    assert difference_from_b1 > 0
    seal = {
        "status": "SEALED_POSTHOC_B03_ONLY_BEFORE_GT_SCORING",
        "frames": count,
        "b03_commit_frame": b03["frame"],
        "b04_omitted_frame": b04["frame"],
        "exact_b1_prefix_frames": prefix_equal,
        "mask_equal_frames": mask_equal,
        "different_from_b1_frames": difference_from_b1,
        "source_prediction_sha256": sha(old_pred),
        "source_events_sha256": sha(old / "EVENTS.json"),
        "source_observations_sha256": sha(OBS),
        "source_profiles_sha256": sha(PROFILES),
        "source_bridge_sha256": sha(Z4Q / "z4q_source/bridge.py"),
        "replay_code_sha256": sha(Path(__file__)),
        "predictions_sha256": sha(target),
    }
    with seal_path.open("x", encoding="utf-8", newline="\n") as out:
        json.dump(seal, out, ensure_ascii=False, indent=2)
        out.write("\n")
        out.flush()
        os.fsync(out.fileno())
    print(json.dumps(seal, ensure_ascii=False))


if __name__ == "__main__":
    main()
