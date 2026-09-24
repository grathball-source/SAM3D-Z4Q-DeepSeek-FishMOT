"""Read-only B0 mapping parity for AO1 lineage metadata, not a new RQ0 run."""
from __future__ import annotations

import argparse
import gzip
import json
import sys
from pathlib import Path

from build_full import write_json
from build_input import digest


def rows(path):
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        yield from map(json.loads, handle)


def check(repo: Path, observation: Path, depth: Path, baseline: Path, stop: int) -> dict:
    sys.path.insert(0, str(repo / "experiments/vl_assoc_e1/r0_source"))
    from bridge import Bridge, stream
    config = json.loads((repo / "online/closed_loop_2888/z4q_source/CONFIG.json").read_text())
    bridge = Bridge(config)
    count = 0
    for (record, profiles), archived in zip(stream(observation, depth), rows(baseline), strict=True):
        if record["frame"] > stop:
            break
        view = bridge.preview(record["frame"], record["time"], record["observations"], profiles)
        actual = [dict(id=view["mapping"][item["id"]], mask=item["mask"])
                  for item in record["native"]]
        assert actual == archived["variants"]["B0"], record["frame"]
        bridge.commit_once(view)
        count += 1
    assert count == stop
    return dict(compared_frames=count, parity=True, baseline_sha256=digest(baseline),
                observation_sha256=digest(observation), depth_sha256=digest(depth))


def main(args):
    expected = json.loads((args.repo / "experiments/rq0_memory_headroom/RUN_RECORD.json").read_text())[
        "sealed_prediction_sha256"]
    assert digest(args.dev_baseline) == expected["development"]
    assert digest(args.val_baseline) == expected["validation"]
    manifest = json.loads(args.source_manifest.read_text())
    stop = {split: max(x["query_frame"] for x in manifest["cases"] if x["split"] == split)
            for split in ("development", "validation")}
    result = {"development": check(args.repo, args.dev_observations, args.dev_depth,
                                    args.dev_baseline, stop["development"]),
              "validation": check(args.repo, args.val_observations, args.val_depth,
                                   args.val_baseline, stop["validation"])}
    write_json(args.output, dict(status="B0_METADATA_PARITY_PASS", splits=result,
                                  intervention=False, GT_read=False, model_calls=0))
    print(json.dumps({k: v["compared_frames"] for k, v in result.items()}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for name in ("repo", "source-manifest", "output", "dev-observations", "dev-depth", "dev-baseline",
                 "val-observations", "val-depth", "val-baseline"):
        parser.add_argument("--" + name, type=Path, required=True)
    main(parser.parse_args())
