"""E1C research-hypothesis comparison contract; no API transport or GT."""
from __future__ import annotations

import itertools
import math
from collections import defaultdict
from statistics import median

MODALITY = {"D": "depth", "A": "appearance", "M": "motion"}


def check_lineage(node, cutoff):
    samples = node["samples"]
    assert samples and all(s["source_time"] <= cutoff for s in samples)
    assert [s["source_time"] for s in samples] == sorted(s["source_time"] for s in samples)
    assert len({(s["sequence"], s["native_id"], s["tracklet_epoch"]) for s in samples}) == 1
    assert len({s["identity_hypothesis"] for s in samples}) == 1
    assert len({(s["sequence"], s["frame"], s["native_id"], s["mask_key"]) for s in samples}) == len(samples)
    assert all(s["mask_key"] == f'n:{s["native_id"]}' and s["identity_hypothesis"] is not None
               for s in samples)
    assert all(samples[i]["frame"] < samples[i + 1]["frame"] for i in range(len(samples) - 1))
    assert node["start_frame"] <= samples[0]["frame"] and node["end_frame"] >= samples[-1]["frame"]
    assert node["continuity_checked"] is True


def _good_core(s):
    d = s.get("core")
    return d if (d and d.get("n", 0) >= 16 and d.get("valid_fraction", 0) >= .2 and
                 d.get("median") is not None and d.get("mad") is not None) else None


def edge(history, current):
    """All clean causal samples, not merely each segment's final observation."""
    hs = [s for s in history["samples"] if not s.get("neighbors_count")]
    cs = [s for s in current["samples"] if not s.get("neighbors_count")]
    values = {}
    depth = [abs(a["median"] - b["median"]) / (15 + 1.4826 * (a["mad"] + b["mad"]))
             for h in hs for c in cs if (a := _good_core(h)) and (b := _good_core(c))]
    values["D"] = median(depth) if depth else None
    appearance = [sum(abs(x-y) for x, y in zip(a, b)) * .5 for h in hs for c in cs
                  if isinstance((a := h.get("RGB_hist_48")), list) and
                  isinstance((b := c.get("RGB_hist_48")), list) and len(a) == len(b) == 48]
    values["A"] = median(appearance) if appearance else None
    motion = []
    if len(hs) >= 2 and hs[0].get("center") and hs[-1].get("center"):
        first, last = hs[0], hs[-1]
        dt = last["source_time"] - first["source_time"]
        if dt > 0:
            v = [(last["center"][i] - first["center"][i]) / dt for i in (0, 1)]
            diag = max(1., math.dist(last["box"][:2], last["box"][2:]))
            for c in cs:
                if c.get("center") and c["source_time"] >= last["source_time"]:
                    prediction = [last["center"][i] + v[i] * (c["source_time"] - last["source_time"])
                                  for i in (0, 1)]
                    motion.append(math.dist(prediction, c["center"]) / diag)
    values["M"] = median(motion) if motion else None
    return dict(values=values, applicability={MODALITY[k]: "APPLICABLE" if v is not None else "UNRELIABLE"
                                             for k, v in values.items()},
                mixed_mask="APPLICABLE" if len(hs) == len(history["samples"]) and
                len(cs) == len(current["samples"]) else "UNRELIABLE",
                source_observations=[(s["sequence"], s["frame"], s["native_id"], s["mask_key"])
                                     for s in hs + cs])


def validate_packet(packet):
    assert packet["schema"] == "VL_ASSOC_RECOVERY_V1" and packet["allow_api"] is False
    cutoff = packet["evidence_cutoff"]
    assert cutoff == packet["query_time"]
    assert 1 <= len(packet["history"]) <= 2 and 1 <= len(packet["current"]) <= 2
    for node in packet["history"] + packet["current"]:
        check_lineage(node, cutoff)
    candidates = packet["candidates"]
    assert 2 <= len(candidates) <= 5 and packet["B0"] in {c["id"] for c in candidates}
    domains = [{*c["mapping"]} for c in candidates]
    assert len(set(map(frozenset, domains))) == 1
    assert all(len(set(c["mapping"].values())) == len(c["mapping"]) for c in candidates)
    assert len({tuple(sorted(c["mapping"].items())) for c in candidates}) == len(candidates)
    assert all(c["mapping"].items() >= packet["fixed"].items() for c in candidates)
    assert all(e["source_time"] <= cutoff for e in packet["evidence"].values())
    return True


def validate_response(packet, response):
    """Return format validity and decision-grounding validity separately."""
    if not isinstance(response, dict) or set(response) != {"schema", "packet_id", "snapshot_version", "comparisons"}:
        return False, False, "FIELDS"
    if (response["schema"], response["packet_id"], response["snapshot_version"]) != (
            packet["schema"], packet["packet_id"], packet["snapshot_version"]):
        return False, False, "BINDING"
    ids = sorted(c["id"] for c in packet["candidates"])
    required = set(itertools.combinations(ids, 2))
    mappings = {candidate["id"]: candidate["mapping"] for candidate in packet["candidates"]}
    historical = {node["label"] for node in packet["history"]}
    seen = set()
    grounded = True
    for item in response["comparisons"]:
        if not isinstance(item, dict) or set(item) != {"left", "right", "relation", "evidence_ids"}:
            return False, False, "COMPARISON_FIELDS"
        pair = (item["left"], item["right"])
        if pair not in required or pair in seen or item["relation"] not in (
                "LEFT_BETTER", "RIGHT_BETTER", "INDISTINGUISHABLE", "UNOBSERVABLE"):
            return False, False, "PAIRS"
        seen.add(pair)
        evidence_ids = item["evidence_ids"]
        if not isinstance(evidence_ids, list) or any(e not in packet["evidence"] for e in evidence_ids):
            return False, False, "EVIDENCE_IDS"
        legal_edges = {f"{identity}:{native}" for candidate_id in pair
                       for native, identity in mappings[candidate_id].items() if identity in historical}
        if any(packet["evidence"][e]["pair"] not in legal_edges for e in evidence_ids):
            return False, False, "IRRELEVANT_EVIDENCE"
        if item["relation"] in ("LEFT_BETTER", "RIGHT_BETTER"):
            grounded &= bool(evidence_ids) and any(packet["evidence"][e]["applicable"] for e in evidence_ids)
    if seen != required:
        return False, False, "INCOMPLETE"
    return True, bool(grounded), "VALID" if grounded else "UNGROUNDED_DIRECTION"


def decode(packet, response):
    formatted, grounded, reason = validate_response(packet, response)
    if not formatted or not grounded:
        return dict(selected=packet["B0"], status="FORMAT_FALLBACK" if not formatted else "SEMANTIC_FALLBACK",
                    reason=reason)
    beats = defaultdict(set)
    for item in response["comparisons"]:
        if item["relation"] == "LEFT_BETTER":
            beats[item["left"]].add(item["right"])
        elif item["relation"] == "RIGHT_BETTER":
            beats[item["right"]].add(item["left"])
    ids = sorted(c["id"] for c in packet["candidates"])
    winners = [candidate for candidate in ids if len(beats[candidate]) == len(ids) - 1]
    selected = winners[0] if len(winners) == 1 else packet["B0"]
    return dict(selected=selected, status="MODEL_CHANGE" if selected != packet["B0"] else "KEEP",
                reason="STRICT_WINNER" if len(winners) == 1 else "NO_UNIQUE_WINNER")


def numeric(packet):
    """Same complete candidates and multi-frame edge values as the model packet."""
    scores = defaultdict(list)
    ids = [c["id"] for c in packet["candidates"]]
    histories = {h["label"] for h in packet["history"]}
    for modality in MODALITY:
        candidate_values = {}
        for candidate in packet["candidates"]:
            assigned = {identity: native for native, identity in candidate["mapping"].items() if identity in histories}
            values = []
            for history in histories:
                if history not in assigned:
                    value = packet.get("null_cost", {}).get(modality)
                else:
                    edge = packet["pairwise"].get(f"{history}:{assigned[history]}")
                    value = None if edge is None else edge["values"][modality]
                if value is None:
                    break
                values.append(value)
            if len(values) != len(histories):
                break
            candidate_values[candidate["id"]] = sum(values) / len(values)
        if len(candidate_values) != len(ids):
            continue
        for candidate, distance in candidate_values.items():
            scores[candidate].append(1 + sum(other < distance for other in candidate_values.values()))
    if any(not scores[c] for c in ids):
        return dict(selected=packet["B0"], status="NO_EVIDENCE_KEEP")
    means = {candidate: sum(scores[candidate]) / len(scores[candidate]) for candidate in ids}
    minimum = min(means.values())
    winners = [candidate for candidate in ids if means[candidate] == minimum]
    if len(winners) != 1:
        return dict(selected=packet["B0"], status="TIE_KEEP", scores=means)
    chosen = winners[0]
    return dict(selected=chosen, status="UNIQUE_KEEP" if chosen == packet["B0"] else "CHANGE", scores=means)
