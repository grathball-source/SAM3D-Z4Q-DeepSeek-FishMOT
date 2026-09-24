"""Frozen E1C D/A/M on precisely visible AO1 source observations; no GT."""
from __future__ import annotations

import argparse
import gzip
import json
import sys
from collections import defaultdict
from pathlib import Path

from build_full import continuity, write_json
from build_input import digest


def rows(path: Path):
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        yield from map(json.loads, handle)


def replay_metadata(repo: Path, observations: Path, depth: Path, needed: set[int], stop: int) -> dict[int, dict]:
    sys.path.insert(0, str(repo / "experiments/vl_assoc_e1/r0_source"))
    from bridge import Bridge, stream
    config = json.loads((repo / "online/closed_loop_2888/z4q_source/CONFIG.json").read_text())
    bridge = Bridge(config)
    selected = {}
    for observation, profiles in stream(observations, depth):
        frame = observation["frame"]
        if frame > stop:
            break
        view = bridge.preview(frame, observation["time"], observation["observations"], profiles)
        if frame in needed:
            selected[frame] = dict(observation=observation, profiles=profiles,
                                   mapping=view["mapping"], epochs=view["epochs"])
        bridge.commit_once(view)
    assert set(selected) == needed, sorted(needed - set(selected))[:20]
    return selected


def sample(view: dict, appearance: dict, frame: int, native: int, role: str, split: str) -> dict:
    observation = next(x for x in view["observation"]["observations"] if x["id"] == native)
    profile = view["profiles"][native]
    feature = next(x for x in appearance["obs"] if x["mask"] == f"n:{native}")
    assert observation["area"] == profile["area"] == feature["area"]
    assert appearance["time"] == view["observation"]["time"]
    return dict(sequence=split, frame=frame, source_time=view["observation"]["time"],
                native_id=native, mask_key=f"n:{native}", tracklet_epoch=view["epochs"][native],
                identity_hypothesis=role, neighbors_count=len(observation.get("neighbors", [])),
                box=observation["box"], center=feature.get("xy"), core=profile.get("core"),
                RGB_hist_48=feature.get("rgb_hist"))


def lineage(view_by_frame: dict[int, dict], frames: list[int], native: int) -> dict:
    assert frames
    checks = []
    for frame in range(min(frames), max(frames) + 1):
        view = view_by_frame[frame]
        if native not in view["mapping"]:
            continue
        observation = next(x for x in view["observation"]["observations"] if x["id"] == native)
        checks.append(dict(frame=frame, native=native, public=view["mapping"][native],
                           epoch=view["epochs"][native], contact=bool(observation.get("neighbors"))))
    return continuity(checks)


def node(role: str, samples: list[dict], views: dict[int, dict]) -> tuple[dict, dict]:
    samples = sorted(samples, key=lambda s: s["frame"])
    if not samples:
        return dict(label=role, samples=[]), dict(checked=False, reason="NO_SAMPLES")
    native_ids = {s["native_id"] for s in samples}
    if len(native_ids) != 1:
        return dict(label=role, samples=samples), dict(checked=False, reason="MULTIPLE_NATIVE")
    check = lineage(views, [s["frame"] for s in samples], samples[0]["native_id"])
    data = dict(label=role, samples=samples, start_frame=samples[0]["frame"],
                end_frame=samples[-1]["frame"], continuity_checked=check["checked"])
    return data, check


def extend(role: str, original: list[dict], source: dict, views: dict[int, dict],
           appearances: dict[int, dict]) -> list[dict]:
    """Add only same native/public/epoch frames on the appropriate side of trigger."""
    if not original:
        return original
    last = original[-1]
    native = last["native_id"]
    view = views[last["frame"]]
    target = (native, view["mapping"][native], view["epochs"][native])
    start, query = source["v2_window"]
    trigger = source["trigger_frame"]
    if role in ("A", "B"):
        candidates = range(max(start, last["frame"] + 1), trigger)
    else:
        candidates = range(max(start, trigger), query + 1)
    added = []
    for frame in candidates:
        row = views[frame]
        signature = (native, row["mapping"].get(native), row["epochs"].get(native))
        if signature != target or native not in row["profiles"]:
            if role in ("A", "B"):
                break
            added = []  # only the final uninterrupted current fragment can be used
            continue
        added.append(sample(row, appearances[frame], frame, native, role, source["split"]))
    combined = {s["frame"]: s for s in original + added}
    return [combined[f] for f in sorted(combined)]


def reasons(history: dict, current: dict, values: dict) -> dict:
    hs = [s for s in history["samples"] if not s["neighbors_count"]]
    cs = [s for s in current["samples"] if not s["neighbors_count"]]
    common = []
    if not history["samples"]:
        common.append("HISTORY_MISSING")
    if not current["samples"]:
        common.append("CURRENT_MISSING")
    if history["samples"] and not hs:
        common.append("HISTORY_ALL_NEIGHBOR_RISK")
    if current["samples"] and not cs:
        common.append("CURRENT_ALL_NEIGHBOR_RISK")
    if any(s["neighbors_count"] for s in history["samples"] + current["samples"]):
        common.append("PREDICTED_NEIGHBOR_RISK_NOT_PROVEN_MIXED")
    return {mod: ([] if value is not None else common + [
        "DEPTH_CORE_OR_PAIR_UNAVAILABLE" if mod == "D" else
        "RGB_HIST_OR_PAIR_UNAVAILABLE" if mod == "A" else
        "MOTION_HISTORY_OR_CURRENT_UNAVAILABLE"])
            for mod, value in values.items()}


def compare(source: dict, appearances: dict[int, dict], views: dict[int, dict],
            card: dict, version: str, baseline: str, contract) -> dict:
    vrows = source["V1"]["roles"]
    by_role = defaultdict(list)
    visible = set(source[version]["source_frames"])
    assert set(source["V0"]["source_frames"]) == set(source["V1"]["source_frames"])
    for r in vrows:
        assert r["frame"] in visible
        native = int(r["native_mask_key"].split(":")[1])
        by_role[r["role"]].append(sample(views[r["frame"]], appearances[r["frame"]],
                                         r["frame"], native, r["role"], source["split"]))
    if version == "V2":
        for role in ("A", "B", "X", "Y"):
            by_role[role] = extend(role, sorted(by_role[role], key=lambda x: x["frame"]),
                                   source, views, appearances)
    nodes, checks = {}, {}
    for role in ("A", "B", "X", "Y"):
        nodes[role], checks[role] = node(role, by_role[role], views)
    valid = all(checks[x]["checked"] for x in nodes)
    pairwise = {}
    for h in ("A", "B"):
        for c in ("X", "Y"):
            key = f"{h}:{c}"
            edge = contract.edge(nodes[h], nodes[c])
            pairwise[key] = dict(**edge, rejection_reasons=reasons(nodes[h], nodes[c], edge["values"]))
    packet = dict(candidates=[dict(id=x["choice"], mapping=x["mapping"]) for x in card["candidate_hypotheses"]],
                  history=[nodes["A"], nodes["B"]], current=[nodes["X"], nodes["Y"]],
                  pairwise=pairwise, B0=baseline)
    decision = contract.numeric(packet) if valid else dict(selected=baseline, status="UNVERIFIED_LINEAGE_NO_DECISION")
    consumed = sorted({s["frame"] for row in nodes.values() for s in row["samples"]})
    assert set(consumed) <= visible
    return dict(version=version, source_frames=sorted(visible), numeric_consumed_frames=consumed,
                visible_not_numeric_consumed=sorted(visible-set(consumed)), nodes=nodes,
                continuity=checks, pairwise=pairwise, decision=decision,
                complete_candidate_comparable_modality=[mod for mod in "DAM" if all(
                    pairwise[f"{h}:{c}"]["values"][mod] is not None
                    for h in ("A", "B") for c in ("X", "Y"))])


def baseline_choice(source: dict, card: dict, repo: Path) -> str:
    if source["case_id"].startswith("AO0-"):
        mapping = {"X": "A", "Y": "B"}
        return next(x["choice"] for x in card["candidate_hypotheses"]
                    if all(x["mapping"][k] == v for k, v in mapping.items()))
    episode = next(r for r in rows_plain(repo / "experiments/vl_assoc_e1/EPISODES.jsonl")
                   if r["packet_id"] == source["case_id"])
    packet = json.loads(Path(source["original_packet_path"]).read_text())
    baseline_mapping = next(x["full_mapping"] for x in packet["candidates"]
                            if x["candidate_id"] == episode["baseline_candidate"])
    return next(x["choice"] for x in card["candidate_hypotheses"] if x["mapping"] == baseline_mapping)


def rows_plain(path: Path):
    with path.open(encoding="utf-8") as handle:
        yield from map(json.loads, handle)


def main(args: argparse.Namespace) -> None:
    sys.path.insert(0, str(args.repo / "experiments/vl_assoc_e1c"))
    import contract
    source_manifest = json.loads(args.source_manifest.read_text())
    output = []
    for split, ob_path, depth_path, feat_path in (
        ("development", args.dev_observations, args.dev_depth, args.dev_appearance),
        ("validation", args.val_observations, args.val_depth, args.val_appearance),
    ):
        cases = [x for x in source_manifest["cases"] if x["split"] == split]
        # Include the gaps between older references and the visible window so
        # continuity can reject a missing/changed intermediate, never certify
        # lineage from only sampled endpoints.
        needed = {f for case in cases
                  for f in range(min(case["V1"]["source_frames"]), case["query_frame"] + 1)}
        stop = max(needed)
        views = replay_metadata(args.repo, ob_path, depth_path, needed, stop)
        appearances = {row["global_frame"]-(0 if split == "development" else 9300): row
                       for row in rows(feat_path)
                       if row["global_frame"]-(0 if split == "development" else 9300) in needed}
        assert set(appearances) == needed
        for case in cases:
            alias = case["case_alias"]
            version = case["V0"]["version_alias"]
            card = json.loads((args.private_root / "blind" / alias / version / "card.json").read_text())
            # Historical packet is read only to bind the pre-existing B0 candidate.
            if case["case_id"].startswith("AO0-"):
                baseline = baseline_choice(case, card, args.repo)
            else:
                original_packet = args.old_e1 / "experiments/vl_assoc_e1/packets" / f"{case['case_id']}.json"
                assert digest(original_packet) == case["original_packet_sha256"]
                case["original_packet_path"] = str(original_packet)
                baseline = baseline_choice(case, card, args.repo)
            versions = [compare(case, appearances, views, card, v, baseline, contract)
                        for v in ("V0", "V1", "V2")]
            assert versions[0]["numeric_consumed_frames"] == versions[1]["numeric_consumed_frames"]
            assert versions[0]["pairwise"] == versions[1]["pairwise"]
            assert versions[0]["decision"] == versions[1]["decision"]
            output.append(dict(case_alias=alias, case_id=case["case_id"], split=split,
                               fixed_baseline_choice=baseline, versions=versions,
                               v0_v1_identical_numeric=True))
            print(json.dumps(dict(case=alias, V0=versions[0]["decision"],
                                  V2=versions[2]["decision"])), flush=True)
    write_json(args.public_output, dict(status="SAME_SOURCE_FROZEN_DAM_NO_GT", cases=output,
              source_hashes={name: digest(path) for name, path in (
                  ("development_observations", args.dev_observations), ("development_depth", args.dev_depth),
                  ("development_appearance", args.dev_appearance),
                  ("validation_observations", args.val_observations), ("validation_depth", args.val_depth),
                  ("validation_appearance", args.val_appearance))},
              note="V0/V1 share visible source frames; V2 adds causal frames. Historical ownership is a B0 hypothesis, not GT."))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for name in ("repo", "old-e1", "private-root", "source-manifest", "public-output",
                 "dev-observations", "dev-depth", "dev-appearance",
                 "val-observations", "val-depth", "val-appearance"):
        parser.add_argument("--" + name, type=Path, required=True)
    main(parser.parse_args())
