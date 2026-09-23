"""Prediction-only causal E1C event/candidate probe. No API or GT imports."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import itertools
import json
import math
import sys
from collections import Counter, deque
from pathlib import Path

HERE = Path(__file__).resolve().parent
E1 = HERE.parent / "vl_assoc_e1"
ROOT = HERE.parents[1]
sys.path.insert(0, str(E1 / "r0_source"))
from bridge import read, stream  # noqa: E402
from runner import RepairedRunner  # noqa: E402


def rows(path):
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            yield json.loads(line)


def pairs(observations):
    ids = {o["id"] for o in observations}
    return {tuple(sorted((o["id"], n))) for o in observations for n in o.get("neighbors", [])
            if n in ids and n != o["id"]}


def refs(history, identity):
    chosen = []
    for row in reversed(history):
        if identity in row["mapping"] and row["quality"].get(identity, False) and (not chosen or chosen[-1] - row["frame"] >= 5):
            chosen.append(row["frame"])
        if len(chosen) == 3:
            break
    return sorted(chosen)


def near(o, center, radius):
    box = o["box"]
    return math.dist(((box[0] + box[2]) / 2, (box[1] + box[3]) / 2), center) <= radius


def make_candidates(runner, view, episode, observations, tracklets):
    mapping = view["mapping"]
    ids = episode["identities"]
    owners = {public: native for native, public in mapping.items() if public in ids}
    if len(owners) == 2:
        selected = sorted(owners.values())
        plans = [{selected[0]: mapping[selected[1]], selected[1]: mapping[selected[0]]}]
        kind = "SWAP"
    elif len(owners) == 1:
        missing = next(x for x in ids if x not in owners)
        current = [o for o in observations if o["id"] not in owners.values() and
                   mapping[o["id"]] not in ids and near(o, episode["center"], episode["radius"]) and
                   o["area"] >= 64 and not o.get("neighbors")]
        current.sort(key=lambda o: (math.dist(((o["box"][0] + o["box"][2]) / 2,
                                               (o["box"][1] + o["box"][3]) / 2), episode["center"]), o["id"]))
        selected = [owners[next(iter(owners))]] + [o["id"] for o in current[:2]]
        plans = [{o["id"]: missing} for o in current[:2]]
        kind = "RESTORE_MISSING_ID"
    else:
        return "NO_CURRENT_OWNER", [], [], owners
    output = []
    for changes in plans:
        whole = dict(mapping)
        whole.update(changes)
        staged, reason = runner.bridge.stage(view, changes)
        if any(mapping[n] != whole[n] for n in mapping if n not in changes):
            raise AssertionError("nonparticipant changed")
        output.append(dict(kind=kind, changes=changes, whole=whole, executable=staged is not None,
                           excluded_reason=reason, target_unoccupied=len(set(whole.values())) == len(whole),
                           tracklets={str(n): tracklets[n] for n in selected}))
    return kind, selected, output, owners


def probe(args):
    offset = 0 if args.split == "development" else 9300
    runner = RepairedRunner(read(ROOT / "online/closed_loop_2888/z4q_source/CONFIG.json"), "B0")
    history = deque(maxlen=120)
    active = {}
    last_pairs = set()
    pair_generation = Counter()
    last_trigger = {}
    native_last = {}
    native_public = {}
    native_neighbors = {}
    native_generation = Counter()
    audits = []
    for (row, profiles), archived in zip(stream(args.observations, args.depth, None, 1 + offset), rows(args.baseline), strict=True):
        frame, now = row["frame"], row["time"]
        view = runner.bridge.preview(frame, now, row["observations"], profiles)
        mapping = view["mapping"]
        assert [dict(id=mapping[o["id"]], mask=o["mask"]) for o in row["native"]] == archived["variants"]["Z4Q_STABLE"]
        current_pairs = pairs(row["observations"])
        by_id = {o["id"]: o for o in row["observations"]}
        for n, o in by_id.items():
            neighbors = bool(o.get("neighbors"))
            if (native_last.get(n) != frame - 1 or native_public.get(n) != mapping[n] or
                    native_neighbors.get(n) != neighbors):
                native_generation[n] += 1
            native_last[n], native_public[n], native_neighbors[n] = frame, mapping[n], neighbors
        for pair in sorted(current_pairs - last_pairs):
            ids = tuple(sorted(mapping[n] for n in pair))
            if len(set(ids)) != 2 or now - last_trigger.get(ids, -1e9) < 6:
                continue
            last_trigger[ids] = now
            pair_generation[ids] += 1
            boxes = [by_id[n]["box"] for n in pair]
            center = tuple(sum((b[i] + b[i + 2]) / 2 for b in boxes) / 2 for i in (0, 1))
            radius = max(60., 2 * max(math.dist(b[:2], b[2:]) for b in boxes))
            key = (ids, pair_generation[ids])
            active[key] = dict(episode_id=f"{args.split}:{ids[0]}-{ids[1]}:{pair_generation[ids]}",
                               trigger_frame=frame, trigger_time=now, identities=ids, center=center,
                               radius=radius, refs={str(k): refs(history, k) for k in ids},
                               separation_frame=None)
        for key, ep in list(active.items()):
            if now - ep["trigger_time"] > 6:
                audits.append(dict(episode_id=ep["episode_id"], trigger_frame=ep["trigger_frame"],
                                   status="NO_QUERY_6S"))
                del active[key]
                continue
            owners = {public: native for native, public in mapping.items() if public in ep["identities"]}
            if len(owners) == 2 and tuple(sorted(owners.values())) in current_pairs:
                ep["separation_frame"] = None
                continue
            if ep["separation_frame"] is None:
                ep["separation_frame"] = frame
            if frame - ep["separation_frame"] < 15:
                continue
            kind, selected, proposals, owners = make_candidates(runner, view, ep, row["observations"], native_generation)
            audits.append(dict(episode_id=ep["episode_id"], split=args.split, trigger_frame=ep["trigger_frame"],
                               query_frame=frame, global_frame=row["global_frame"], query_time=now,
                               evidence_cutoff=now, status="QUERY" if proposals else kind,
                               kind=kind, identities=ep["identities"], owners=owners,
                               refs=ep["refs"], selected=selected, candidates=proposals,
                               generated=len(proposals), executable=sum(x["executable"] for x in proposals),
                               excluded=dict(Counter(x["excluded_reason"] for x in proposals if not x["executable"]))))
            del active[key]
        last_pairs = current_pairs
        history.append(dict(frame=frame, mapping={v: n for n, v in mapping.items()},
                            quality={mapping[o["id"]]: o["area"] >= 64 and not o.get("neighbors")
                                     for o in row["observations"]}))
        runner.bridge.commit_once(view)
    for ep in active.values():
        audits.append(dict(episode_id=ep["episode_id"], trigger_frame=ep["trigger_frame"], status="NO_QUERY_END_OF_SPLIT"))
    summary = dict(split=args.split, total=len(audits), statuses=dict(Counter(x["status"] for x in audits)),
                   kinds=dict(Counter(x.get("kind") for x in audits if x.get("kind"))),
                   executable_by_kind=dict(Counter(x["kind"] for x in audits if x.get("executable", 0) > 0)),
                   excluded=dict(sum((Counter(x.get("excluded", {})) for x in audits), Counter())))
    return summary, audits


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=("development", "validation"), required=True)
    parser.add_argument("--observations", type=Path, required=True)
    parser.add_argument("--depth", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    summary, audits = probe(args)
    assert not args.output.exists()
    with args.output.open("x", encoding="utf-8") as handle:
        for item in audits:
            handle.write(json.dumps(item, ensure_ascii=False, allow_nan=False) + "\n")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
