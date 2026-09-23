"""VL_ASSOC_RELATIVE_V1: complete-hypothesis comparison, no arbitrary ID edits."""
from __future__ import annotations

import hashlib
import itertools
import json
import copy
from collections import defaultdict

RELATIONS = {"LEFT_BETTER", "RIGHT_BETTER", "INDISTINGUISHABLE", "UNOBSERVABLE"}
APPLICABILITY = {"APPLICABLE", "UNRELIABLE", "UNKNOWN"}
REASONS = {"DEPTH", "APPEARANCE", "MOTION", "MULTI_CUE", "QUALITY_LIMIT", "INSUFFICIENT"}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def pairs(packet):
    return list(itertools.combinations(sorted(x["candidate_id"] for x in packet["candidates"]), 2))


def validate_packet(packet):
    assert packet["schema"] == "VL_ASSOC_RELATIVE_V1"
    assert packet["evidence_cutoff"] == packet["query_time"]
    ids = [c["candidate_id"] for c in packet["candidates"]]
    assert len(ids) == len(set(ids)) and 2 <= len(ids) <= 5
    source_times = [sample["source_time"] for node in packet["history"] + packet["current"]
                    for sample in node["samples"]]
    assert source_times and max(source_times) <= packet["query_time"]
    labels = {node["label"] for node in packet["current"]} | set(packet["fixed_observations"])
    for candidate in packet["candidates"]:
        mapping = candidate["full_mapping"]
        assert set(mapping) == labels and len(set(mapping.values())) == len(mapping)
    assert len(packet["history"]) <= 2 and len(packet["current"]) <= 3
    assert all(item["source_time"] <= packet["query_time"] for item in packet["evidence"].values())
    return True


def validate_response(packet, response):
    if not isinstance(response, dict) or set(response) != {"schema", "packet_id", "snapshot_version", "comparisons", "applicability"}:
        return False, "INVALID_FIELDS"
    if (response["schema"] != packet["schema"] or response["packet_id"] != packet["packet_id"] or
            response["snapshot_version"] != packet["snapshot_version"]):
        return False, "VERSION_OR_PACKET_MISMATCH"
    comparisons = response["comparisons"]
    if not isinstance(comparisons, list) or len(comparisons) != len(pairs(packet)):
        return False, "INCOMPLETE_PAIRS"
    seen = set()
    for item in comparisons:
        if not isinstance(item, dict) or set(item) != {"left", "right", "relation", "evidence_ids", "reason_code", "short_explanation"}:
            return False, "INVALID_COMPARISON_FIELDS"
        pair = (item["left"], item["right"])
        if pair not in pairs(packet) or pair in seen or item["relation"] not in RELATIONS:
            return False, "INVALID_PAIR_OR_RELATION"
        seen.add(pair)
        if (item["reason_code"] not in REASONS or
                not isinstance(item["short_explanation"], str) or len(item["short_explanation"]) > 80):
            return False, "INVALID_REASON"
        evidence = item["evidence_ids"]
        if (not isinstance(evidence, list) or any(e not in packet["evidence"] for e in evidence) or
                (item["relation"] in {"LEFT_BETTER", "RIGHT_BETTER"} and not evidence)):
            return False, "INVALID_EVIDENCE_REFERENCE"
    applicability = response["applicability"]
    if (not isinstance(applicability, dict) or set(applicability) !=
            {"appearance", "motion", "depth", "mixed_mask"} or
            any(value not in APPLICABILITY for value in applicability.values())):
        return False, "INVALID_APPLICABILITY"
    return True, "VALID"


def decode(packet, response, baseline_id):
    valid, reason = validate_response(packet, response)
    if not valid:
        return dict(selected=baseline_id, status="INVALID", reason=reason)
    beats = defaultdict(set)
    ties = unreachable = False
    for item in response["comparisons"]:
        left, right = item["left"], item["right"]
        if item["relation"] == "LEFT_BETTER":
            beats[left].add(right)
        elif item["relation"] == "RIGHT_BETTER":
            beats[right].add(left)
        elif item["relation"] == "INDISTINGUISHABLE":
            ties = True
        else:
            unreachable = True
    winner = next((candidate for candidate in sorted(x["candidate_id"] for x in packet["candidates"])
                   if len(beats[candidate]) == len(packet["candidates"]) - 1), None)
    if winner is None:
        return dict(selected=baseline_id, status="FALLBACK",
                    reason="UNOBSERVABLE" if unreachable else "TIE" if ties else "CYCLE")
    return dict(selected=winner, status="KEEP" if winner == baseline_id else "MODEL_CHANGE", reason="STRICT_WINNER")


def numeric_baseline(packet, baseline_id, modalities=("D", "A", "M")):
    """Equal-weight ranks of available D/A/M distances for the full mapping."""
    per_candidate = {}
    for candidate in packet["candidates"]:
        mapping = candidate["full_mapping"]
        by_identity = {identity: observation for observation, identity in mapping.items()}
        distances = {}
        for modality in modalities:
            values = []
            for history in packet["history"]:
                observation = by_identity.get(history["label"])
                edge = packet["pairwise"].get(history["label"] + ":" + observation) if observation else None
                if edge is None or edge[modality] is None:
                    values = []
                    break
                values.append(edge[modality])
            if values:
                distances[modality] = sum(values) / len(values)
        per_candidate[candidate["candidate_id"]] = distances
    scores = defaultdict(list)
    for modality in modalities:
        available = [(values[modality], candidate) for candidate, values in per_candidate.items()
                     if modality in values]
        if len(available) != len(per_candidate):
            continue
        for distance, candidate in available:
            scores[candidate].append(1 + sum(other < distance for other, _ in available))
    if not scores or any(len(scores[c]) == 0 for c in per_candidate):
        return dict(selected=baseline_id, status="NUMERIC_FALLBACK", scores=dict(scores))
    means = {candidate: sum(ranks) / len(ranks) for candidate, ranks in scores.items()}
    best = min(means.values())
    winners = [candidate for candidate, score in means.items() if score == best]
    return dict(selected=winners[0] if len(winners) == 1 else baseline_id,
                status="NUMERIC_CHANGE" if len(winners) == 1 and winners[0] != baseline_id else "NUMERIC_FALLBACK",
                scores=means)


def model_off(packet, baseline_id):
    response = dict(schema=packet["schema"], packet_id=packet["packet_id"],
                    snapshot_version=packet["snapshot_version"],
                    applicability={key: "UNKNOWN" for key in ("appearance", "motion", "depth", "mixed_mask")},
                    comparisons=[dict(left=left, right=right, relation="UNOBSERVABLE", evidence_ids=[],
                                      reason_code="INSUFFICIENT", short_explanation="")
                                 for left, right in pairs(packet)])
    return decode(packet, response, baseline_id)


def permute_aliases(packet):
    """Change only text aliases and candidate ordering; image order is untouched."""
    out = copy.deepcopy(packet)
    history = [x["label"] for x in out["history"]]
    current = [x["label"] for x in out["current"]]
    candidates = sorted(x["candidate_id"] for x in out["candidates"])
    labels = {a: b for names in (history, current, candidates) for a, b in zip(names, reversed(names))}
    for label in out["fixed_observations"]:
        labels.setdefault(label, label)
    for label in out["fixed_observations"].values():
        labels.setdefault(label, label)
    def pair_key(key):
        a, b = key.split(":")
        return labels[a] + ":" + labels[b]
    for node in out["history"] + out["current"]:
        node["label"] = labels[node["label"]]
        for sample in node["samples"]:
            sample["label"] = node["label"]
    out["fixed_observations"] = {labels[k]: labels[v] for k, v in out["fixed_observations"].items()}
    out["pairwise"] = {pair_key(k): v for k, v in out["pairwise"].items()}
    for evidence in out["evidence"].values():
        evidence["pair"] = pair_key(evidence["pair"])
    for candidate in out["candidates"]:
        candidate["candidate_id"] = labels[candidate["candidate_id"]]
        candidate["full_mapping"] = {labels[k]: labels[v] for k, v in candidate["full_mapping"].items()}
    out["candidates"].reverse()
    out["packet_id"] += "_perm"
    validate_packet(out)
    return out, {labels[c]: c for c in candidates}


def synthetic_check():
    packet = dict(schema="VL_ASSOC_RELATIVE_V1", packet_id="synthetic", snapshot_version="v1",
                  query_time=1., evidence_cutoff=1.,
                  history=[dict(label=k, samples=[dict(source_time=0.)]) for k in ("A", "B")],
                  current=[dict(label=k, samples=[dict(source_time=1.)]) for k in ("X", "Y")],
                  fixed_observations={},
                  evidence={"E1": dict(source_time=1., pair="A:X")},
                  pairwise={a + ":" + b: dict(D=0.1 if (a, b) in (("A", "X"), ("B", "Y")) else 2.,
                                               A=0.1 if (a, b) in (("A", "X"), ("B", "Y")) else 2.,
                                               M=0.1 if (a, b) in (("A", "X"), ("B", "Y")) else 2.)
                            for a in ("A", "B") for b in ("X", "Y")},
                  candidates=[dict(candidate_id="C1", full_mapping={"X": "A", "Y": "B"}),
                              dict(candidate_id="C2", full_mapping={"X": "B", "Y": "A"})])
    assert validate_packet(packet)
    assert model_off(packet, "C2")["selected"] == "C2"
    response = dict(schema=packet["schema"], packet_id="synthetic", snapshot_version="v1",
                    applicability={key: "APPLICABLE" for key in ("appearance", "motion", "depth", "mixed_mask")},
                    comparisons=[dict(left="C1", right="C2", relation="LEFT_BETTER", evidence_ids=["E1"],
                                      reason_code="MULTI_CUE", short_explanation="")])
    assert decode(packet, response, "C2")["selected"] == "C1"
    response["comparisons"][0]["relation"] = "RIGHT_BETTER"
    assert decode(packet, response, "C2")["selected"] == "C2"
    response["comparisons"][0]["evidence_ids"] = []
    assert decode(packet, response, "C2")["status"] == "INVALID"
    assert numeric_baseline(packet, "C2")["selected"] == "C1"
    absent = copy.deepcopy(packet)
    absent["pairwise"] = {key: dict(D=None, A=None, M=None) for key in packet["pairwise"]}
    assert numeric_baseline(absent, "C2")["selected"] == "C2"
    assert numeric_baseline(absent, "C2")["status"] == "NUMERIC_FALLBACK"
    permuted, back = permute_aliases(packet)
    assert [x["source_time"] for n in permuted["history"] + permuted["current"] for x in n["samples"]] == \
           [x["source_time"] for n in packet["history"] + packet["current"] for x in n["samples"]]
    assert back[numeric_baseline(permuted, back["C2"])["selected"]] == "C1"
    return True


if __name__ == "__main__":
    assert synthetic_check()
    print("PASS_E1_PROTOCOL_SYNTHETIC_NO_API")
