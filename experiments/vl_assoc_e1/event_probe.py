"""Causal contact episodes and complete candidate reachability, without GT/API."""
from __future__ import annotations

import argparse
import gzip
import itertools
import json
import math
import sys
from collections import Counter, deque
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE / "r0_source"))
from bridge import read, stream  # noqa: E402
from runner import RepairedRunner  # noqa: E402


def rows(path):
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            yield json.loads(line)


def contact_pairs(observations):
    by_id = {o["id"]: o for o in observations}
    return {tuple(sorted((n, m))) for n, o in by_id.items() for m in o.get("neighbors", []) if m in by_id and n != m}


def selected_observations(episode, current, mapping, first_seen):
    owners = [n for n, k in mapping.items() if k in episode["identities"]]
    if len(owners) != 2:
        return None, "MISSING_ANCHOR_OWNER"
    center = episode["contact_center"]
    radius = episode["contact_radius"]
    others = [o["id"] for o in current if o["id"] not in owners and
              first_seen[o["id"]] >= episode["trigger_frame"] and
              math.dist(((o["box"][0] + o["box"][2]) / 2,
                         (o["box"][1] + o["box"][3]) / 2), center) <= radius]
    selected = sorted(owners + others)
    if len(selected) > 3:
        return None, "OUT_OF_SCOPE_CURRENT_MORE_THAN_3"
    return selected, None


def candidates(bridge, view, selected):
    base = view["mapping"]
    generated = []
    for left, right in itertools.combinations(selected, 2):
        changes = {left: base[right], right: base[left]}
        whole = dict(base)
        whole.update(changes)
        assert len(whole) == len(set(whole.values()))
        staged, reason = bridge.stage(view, changes)
        generated.append(dict(changes=changes, whole=whole, executable=staged is not None,
                              excluded_reason=reason))
    assert len(generated) <= 4
    return generated


def spaced_reference_frames(history, identity):
    chosen = []
    for row in reversed(history):
        if (identity in row["mapping"] and row["quality"].get(identity, False) and
                (not chosen or chosen[-1] - row["frame"] >= 5)):
            chosen.append(row["frame"])
        if len(chosen) == 3:
            break
    return sorted(chosen)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["development", "validation"], required=True)
    ap.add_argument("--observations", type=Path, required=True)
    ap.add_argument("--depth", type=Path, required=True)
    ap.add_argument("--baseline", type=Path, required=True)
    args = ap.parse_args()
    offset = 0 if args.split == "development" else 9300
    runner = RepairedRunner(read(ROOT / "online/closed_loop_2888/z4q_source/CONFIG.json"), "B0")
    history = deque(maxlen=120)
    active = {}
    first_seen = {}
    last_pairs = set()
    generations = Counter()
    last_trigger = {}
    audits = []
    baseline_rows = rows(args.baseline)
    for (row, profiles), archived in zip(stream(args.observations, args.depth, None, 1 + offset), baseline_rows, strict=True):
        frame, now = row["frame"], row["time"]
        view = runner.bridge.preview(frame, now, row["observations"], profiles)
        mapping = view["mapping"]
        assert [dict(id=mapping[o["id"]], mask=o["mask"]) for o in row["native"]] == archived["variants"]["Z4Q_STABLE"]
        pairs = contact_pairs(row["observations"])
        by_id = {o["id"]: o for o in row["observations"]}
        for native in by_id:
            first_seen.setdefault(native, frame)
        for pair in sorted(pairs - last_pairs):
            if len({mapping[n] for n in pair}) != 2:
                continue
            ids = tuple(sorted(mapping[n] for n in pair))
            if now - last_trigger.get(ids, -1e9) < 6:
                continue
            last_trigger[ids] = now
            generations[ids] += 1
            boxes = [by_id[n]["box"] for n in pair]
            center = tuple(sum((b[i] + b[i+2]) / 2 for b in boxes) / 2 for i in (0, 1))
            radius = max(60., 2 * max(math.dist(b[:2], b[2:]) for b in boxes))
            key = (ids, generations[ids])
            active[key] = dict(episode_id=f"{args.split}:{ids[0]}-{ids[1]}:{generations[ids]}",
                               trigger_frame=frame, trigger_time=now, identities=ids,
                               contact_center=center, contact_radius=radius,
                               refs={str(k): spaced_reference_frames(history, k) for k in ids},
                               separation_frame=None)
        for key, episode in list(active.items()):
            if now - episode["trigger_time"] > 6:
                audits.append(dict(episode_id=episode["episode_id"], trigger_frame=episode["trigger_frame"],
                                   status="NO_QUERY_6S"))
                del active[key]
                continue
            owners = {k: n for n, k in mapping.items() if k in episode["identities"]}
            if len(owners) < 2:
                continue
            owner_pair = tuple(sorted(owners.values()))
            if owner_pair in pairs:
                episode["separation_frame"] = None
                continue
            if episode["separation_frame"] is None:
                episode["separation_frame"] = frame
            if frame - episode["separation_frame"] < 15:
                continue
            selected, reason = selected_observations(episode, row["observations"], mapping, first_seen)
            generated = [] if selected is None else candidates(runner.bridge, view, selected)
            audits.append(dict(episode_id=episode["episode_id"], trigger_frame=episode["trigger_frame"],
                               query_frame=frame, global_frame=row["global_frame"],
                               query_time=now, evidence_cutoff=now, status=reason or "QUERY",
                               selected=selected, generated=len(generated),
                               executable=sum(x["executable"] for x in generated),
                               excluded=dict(Counter(x["excluded_reason"] for x in generated if not x["executable"])),
                               candidates=generated, refs=episode["refs"]))
            del active[key]
        last_pairs = pairs
        history.append(dict(frame=frame, mapping={v: n for n, v in mapping.items()},
                            quality={mapping[o["id"]]: o["area"] >= 64 and not o.get("neighbors")
                                     for o in row["observations"]}))
        runner.bridge.commit_once(view)
    for episode in active.values():
        audits.append(dict(episode_id=episode["episode_id"], trigger_frame=episode["trigger_frame"],
                           status="NO_QUERY_END_OF_SPLIT"))
    summary = dict(split=args.split, total=len(audits), statuses=dict(Counter(x["status"] for x in audits)),
                   with_nonbaseline=sum(x.get("generated", 0) > 0 for x in audits),
                   with_executable=sum(x.get("executable", 0) > 0 for x in audits),
                   exclusions=dict(sum((Counter(x.get("excluded", {})) for x in audits), Counter())))
    target = HERE / f"EVENT_PROBE_V4_{args.split}.json"
    assert not target.exists(), target
    target.write_text(json.dumps(dict(summary=summary, events=audits), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
