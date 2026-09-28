"""Turn source-backed event facts into short, anonymous, causal evidence.

Only a source-contiguous clean fragment receives a line or local velocity.
Source/native handles stay in the returned private provenance, never the packet.
"""
from __future__ import annotations

import copy
import math
import statistics
from collections import defaultdict
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

MAX_ANONYMOUS_FRAGMENT_FRAMES = 15


def _source_item(row, native):
    return next((x for x in row["observations"] if x["id"] == native), None)


def _signature(row, native, observation):
    native_row = next((x for x in row.get("native", []) if x.get("id") == native), {})
    keys = ("alias_epoch", "identity_epoch", "generation", "track_generation", "alias_version")
    return tuple((key, observation.get(key, native_row.get(key))) for key in keys
                 if key in observation or key in native_row)


def _clean(observation):
    return bool(observation and observation.get("area", 0) > 0 and not observation.get("neighbors"))


def _profile(depth_row, native):
    return next((x for x in depth_row["observations"] if x["id"] == native), None)


def _round(value, digits=3):
    return None if value is None else round(value, digits)


def _depth_fact(fact_id, frame, now, depth_row, native, contact):
    value = _profile(depth_row, native)
    if value is None:
        return {"status": "UNKNOWN", "reason": "NO_ALIGNED_PROFILE"}
    assert depth_row["frame"] == frame and depth_row["time"] == now
    result = {"fact_id": f"D-{fact_id}", "source_fact_ids": [fact_id],
              "source": "raw_depth_profile_stream", "unit": "pipeline_mm_unverified_water_surface",
              "sensor_available": depth_row.get("sensor_available"), "synchronized": True,
              "contact_or_mixed_risk": contact, "overlap_pixels": value.get("overlap_pixels")}
    for part in ("core", "whole"):
        p = value.get(part) or {}
        result[part] = {key: p.get(key) for key in ("median", "mad", "n", "valid_fraction")}
    return result


def _fit(facts, field, value_key, prefix):
    """OLS on one fragment only; every missing/invalid sample stays UNKNOWN."""
    if field == "velocity":
        values = [x["center_px"] for x in facts]
    else:
        values = []
        for x in facts:
            depth = x["depth"]
            part = depth.get(field) or {}
            if (depth.get("status") == "UNKNOWN" or not depth.get("sensor_available")
                    or not depth.get("synchronized") or depth.get("contact_or_mixed_risk")
                    or (depth.get("overlap_pixels") or 0) > 0 or (part.get("n") or 0) < 16
                    or (part.get("valid_fraction") or 0) < .2 or part.get("median") is None):
                return {"status": "UNKNOWN", "reason": "MISSING_OR_QUALITY_DEPTH_IN_FRAGMENT"}
            values.append(part[value_key])
    times = [x["time_seconds"] for x in facts]
    if len(times) < 3 or len(set(times)) < 3:
        return {"status": "UNKNOWN", "reason": "FEWER_THAN_THREE_DISTINCT_CLEAN_TIMES", "samples": len(times)}
    if any(b <= a or b - a > .2 for a, b in zip(times, times[1:])):
        return {"status": "UNKNOWN", "reason": "NONCONTIGUOUS_CLEAN_TIMES"}
    t0 = sum(times) / len(times)
    den = sum((t - t0) ** 2 for t in times)
    if field == "velocity":
        means = [sum(v[k] for v in values) / len(values) for k in (0, 1)]
        rates = [sum((t - t0) * (v[k] - means[k]) for t, v in zip(times, values)) / den
                 for k in (0, 1)]
        residual = math.sqrt(sum(sum((v[k] - means[k] - rates[k] * (t - t0)) ** 2
                                     for k in (0, 1)) for t, v in zip(times, values)) / len(values))
        speed = math.hypot(*rates)
        return {"fact_id": prefix, "status": "ESTIMATE", "source_fact_ids": [x["fact_id"] for x in facts],
                "method": "OLS_bbox_center_within_one_clean_fragment", "interval_seconds": [times[0], times[-1]],
                "velocity_px_per_s": [_round(x) for x in rates], "speed_px_per_s": _round(speed),
                "direction_radians": None if speed < 2 else _round(math.atan2(rates[1], rates[0]), 4),
                "direction_reason": "LOW_SPEED" if speed < 2 else None,
                "residual_rms_px": _round(residual), "samples": len(times)}
    mean = sum(values) / len(values)
    rate = sum((t - t0) * (v - mean) for t, v in zip(times, values)) / den
    residual = math.sqrt(sum((v - mean - rate * (t - t0)) ** 2
                             for t, v in zip(times, values)) / len(values))
    return {"fact_id": prefix, "status": "ESTIMATE", "source_fact_ids": [x["depth"]["fact_id"] for x in facts],
            "method": "OLS_median_within_one_clean_fragment", "interval_seconds": [times[0], times[-1]],
            "rate_pipeline_mm_per_s": _round(rate), "residual_rms_mm": _round(residual), "samples": len(times)}


def _fragment(fragment_id, role, facts, q_time):
    assert facts and all(b["frame"] == a["frame"] + 1 for a, b in zip(facts, facts[1:]))
    fit_facts = [x for x in facts if x["time_seconds"] >= facts[-1]["time_seconds"] - .5]
    depth_summary = {}
    for part in ("core", "whole"):
        parts = [x["depth"].get(part, {}) for x in facts]
        measured = [(x["fact_id"], value["median"]) for x, value in zip(facts, parts)
                    if value.get("median") is not None and x["depth"].get("sensor_available")]
        valid = [value["valid_fraction"] for value in parts if value.get("valid_fraction") is not None]
        mads = [value["mad"] for value in parts if value.get("mad") is not None]
        depth_summary[part] = {
            "measured_frames": len(measured), "total_frames": len(facts),
            "sensor_unavailable_frames": sum(not x["depth"].get("sensor_available") for x in facts),
            "overlap_frames": sum((x["depth"].get("overlap_pixels") or 0) > 0 for x in facts),
            "median_valid_fraction": _round(statistics.median(valid)) if valid else None,
            "median_mad_pipeline_mm": _round(statistics.median(mads)) if mads else None,
            "first_measured": measured[0] if measured else None,
            "last_measured": measured[-1] if measured else None,
            "observed_first_to_last_change_pipeline_mm": _round(measured[-1][1] - measured[0][1])
                if len(measured) >= 2 else None,
            "source": "all measured rows of this fragment's observation series"}
    return {"fragment_id": fragment_id, "role": role, "identity_scope": "SOURCE_CONTIGUOUS_CLEAN_FRAGMENT_ONLY",
            "start_frame": facts[0]["frame"], "end_frame": facts[-1]["frame"],
            "start_time_seconds": facts[0]["time_seconds"], "end_time_seconds": facts[-1]["time_seconds"],
            "samples": len(facts), "age_at_q_seconds": _round(q_time - facts[-1]["time_seconds"]),
            "first_center_px": facts[0]["center_px"], "last_center_px": facts[-1]["center_px"],
            "first_fact_id": facts[0]["fact_id"], "last_fact_id": facts[-1]["fact_id"],
            "velocity": _fit(fit_facts, "velocity", None, f"V-{fragment_id}"),
            "depth_trend": {part: _fit(facts, part, "median", f"DT-{fragment_id}-{part}")
                            for part in ("core", "whole")},
            "depth_summary": depth_summary,
            "observations": facts}


def _fact_from_named(raw, source_rows, depth_rows, native):
    frame = raw["source_frame"]
    row = source_rows[frame]
    source = _source_item(row, native)
    assert _clean(source) and row["time"] == raw["source_time_seconds"]
    assert source["area"] == raw["area_px"] and not raw["neighbor_count"]
    center = [(source["box"][0] + source["box"][2]) / 2,
              (source["box"][1] + source["box"][3]) / 2]
    assert center == raw["bbox_center_px"]
    depth = _depth_fact(raw["fact_id"], frame, row["time"], depth_rows[frame], native, False)
    old = raw["depth"]
    assert old.get("epistemic_type") == "MEASUREMENT" and old["synchronized"]
    for part in ("core", "whole"):
        assert depth[part]["median"] == old[part]["median"]
    return {"fact_id": raw["fact_id"], "frame": frame, "time_seconds": row["time"],
            "center_px": center, "bbox_px": raw["bbox_px"], "area_px": raw["area_px"],
            "quality": {"presence": raw["quality"]["presence"], "risk": "CLEAN", "neighbor_count": 0},
            "depth": depth}


def _fact_from_event(raw, source_rows, depth_rows, native):
    frame = raw["frame"]
    row = source_rows[frame]
    source = _source_item(row, native)
    assert source is not None and row["time"] == raw["time_seconds"]
    center = [(source["box"][0] + source["box"][2]) / 2,
              (source["box"][1] + source["box"][3]) / 2]
    assert center == [raw["center_x_px"], raw["center_y_px"]]
    assert source["area"] == raw["area_px"]
    contact = not _clean(source)
    expected_risk = ("ZERO_AREA" if source["area"] == 0 else
                     "CONTACT_RISK" if source.get("neighbors") else "ANONYMOUS_CLEAN_ISLAND")
    assert raw["risk"] == expected_risk, (raw["fact_id"], frame, native, raw["risk"], expected_risk)
    assert len(source.get("neighbors", [])) == raw["neighbor_count"]
    depth = _depth_fact(raw["fact_id"], frame, row["time"], depth_rows[frame], native, contact)
    assert depth["core"]["median"] == raw["depth_median_pipeline_mm"]
    assert depth["core"]["valid_fraction"] == raw["depth_valid_fraction"]
    return {"fact_id": raw["fact_id"], "frame": frame, "time_seconds": row["time"],
            "center_px": center, "area_px": raw["area_px"],
            "quality": {"risk": raw["risk"],
                        "neighbor_count": raw["neighbor_count"]}, "depth": depth}


def _edge(pre, post):
    a, b, q = pre["observations"][-1], post["observations"][0], post["observations"][-1]
    gap = b["time_seconds"] - a["time_seconds"]
    assert gap > 0
    answer = {"source_fragment": pre["fragment_id"], "target_fragment": post["fragment_id"],
              "source_fact_ids": [a["fact_id"], b["fact_id"], q["fact_id"]],
              "gap_to_post_start_seconds": _round(gap),
              "distance_to_post_start_px": _round(math.dist(a["center_px"], b["center_px"])),
              "distance_to_q_px": _round(math.dist(a["center_px"], q["center_px"])),
              "motion_comparison": {"status": "UNKNOWN"},
              "depth_endpoint_weak_cue": {}}
    av, bv = pre["velocity"], post["velocity"]
    if av["status"] == bv["status"] == "ESTIMATE":
        x, y = av["velocity_px_per_s"], bv["velocity_px_per_s"]
        if av["speed_px_per_s"] >= 2 and bv["speed_px_per_s"] >= 2:
            cos = max(-1, min(1, sum(xi * yi for xi, yi in zip(x, y)) /
                                   (math.hypot(*x) * math.hypot(*y))))
            angle = _round(math.degrees(math.acos(cos)))
        else:
            angle = None
        answer["motion_comparison"] = {"status": "DESCRIPTIVE_ONLY_NOT_A_PATH_VETO",
                                        "source_velocity_fact_ids": [av["fact_id"], bv["fact_id"]],
                                        "velocity_difference_px_per_s": _round(math.dist(x, y)),
                                        "angle_difference_degrees": angle,
                                        "angle_reason": "LOW_SPEED" if angle is None else None}
    for part in ("core", "whole"):
        x, y = a["depth"].get(part, {}), q["depth"].get(part, {})
        if x.get("median") is None or y.get("median") is None:
            answer["depth_endpoint_weak_cue"][part] = {"status": "UNKNOWN"}
        else:
            answer["depth_endpoint_weak_cue"][part] = {
                "status": "DESCRIPTIVE_ONLY_NOT_IDENTITY_PROOF",
                "source_fact_ids": [a["depth"]["fact_id"], q["depth"]["fact_id"]],
                "absolute_q_difference_pipeline_mm": _round(abs(y["median"] - x["median"])),
                "start_mad_mm": x["mad"], "q_mad_mm": y["mad"],
                "start_valid_fraction": x["valid_fraction"], "q_valid_fraction": y["valid_fraction"]}
    return answer


def _compact_fragment(fragment):
    """Keep every observation, but transmit a columnar series instead of repeated keys."""
    out = dict(fragment)
    out["observation_columns"] = ["fact_id", "frame", "time_seconds", "center_x_px",
        "center_y_px", "area_px", "risk", "core_pipeline_mm", "core_mad_mm", "core_n",
        "core_valid_fraction", "whole_pipeline_mm", "whole_mad_mm", "whole_n",
        "whole_valid_fraction", "sensor_available", "overlap_pixels"]
    out["depth_fact_id_rule"] = "D-{fact_id}; each depth sample comes from same frame/source observation"
    out["observations"] = [[fact["fact_id"], fact["frame"], fact["time_seconds"],
        *fact["center_px"], fact["area_px"], fact["quality"]["risk"],
        *[fact["depth"].get(part, {}).get(key) for part in ("core", "whole")
          for key in ("median", "mad", "n", "valid_fraction")],
        fact["depth"].get("sensor_available"), fact["depth"].get("overlap_pixels")]
        for fact in fragment["observations"]]
    return out


def compile_event_evidence(raw_event, source_observations, source_depth, branch_context):
    """Compile one q-causal packet; the returned debug map must stay private."""
    packet = raw_event["packet"]
    case, q, trigger = raw_event["case"], packet["q_frame"], packet["trigger"]["frame"]
    native = raw_event["native"]
    lineage = branch_context["source_fact_by_observed"]
    q_time = packet["q_time_seconds"]
    assert q_time == source_observations[q]["time"] and q <= 2888
    named, private = {}, {"case": case, "fact_to_source": {}, "fragment_to_native": {}}
    for section, roles in (("PRE_HISTORY", "AB"), ("POST_HISTORY_TO_Q", "XY")):
        for role in roles:
            old = packet[section][role]
            facts = []
            signatures = []
            for obs in old["observations"]:
                binding = lineage[obs["fact_id"]]
                assert binding["frame"] == obs["source_frame"]
                assert binding["native"] == native[role]
                f = obs["source_frame"]
                facts.append(_fact_from_named(obs, source_observations, source_depth, native[role]))
                signatures.append(_signature(source_observations[f], native[role],
                                             _source_item(source_observations[f], native[role])))
                private["fact_to_source"][obs["fact_id"]] = binding["source_fact_id"]
            assert facts and all(b["frame"] == a["frame"] + 1 for a, b in zip(facts, facts[1:]))
            assert len(set(signatures)) == 1, (case, role, "IDENTITY_VERSION_CHANGE")
            assert facts[-1]["frame"] == old["anchor_frame"] if role in "AB" else facts[-1]["frame"] == q
            name = f"{case}-{role}-F{facts[0]['frame']}-{facts[-1]['frame']}"
            named[role] = _fragment(name, role, facts, q_time)
            private["fragment_to_native"][name] = native[role]

    cols = packet["INTERACTION_TABLE"]["columns"]
    all_event = []
    for row in packet["INTERACTION_TABLE"]["rows"]:
        item = dict(zip(cols, row, strict=True))
        binding = lineage.get(item["fact_id"])
        if binding is None:
            # The later trial changed anonymous O labels to frame-local T labels.
            # Bind by measured source geometry, never by a hypothesized identity.
            f = item["frame"]
            candidates = []
            for source in source_observations[f]["observations"]:
                center = [(source["box"][0] + source["box"][2]) / 2,
                          (source["box"][1] + source["box"][3]) / 2]
                if (center == [item["center_x_px"], item["center_y_px"]]
                        and source["area"] == item["area_px"]):
                    candidates.append(source["id"])
            assert len(candidates) == 1, (case, item["fact_id"], candidates)
            n = candidates[0]
            source_id = f"SRC-F{f}-N{n}"
            assert source_id in branch_context["case_source_fact_ids"]
            binding = {"frame": f, "native": n, "source_fact_id": source_id}
            lineage[item["fact_id"]] = binding
        assert binding["frame"] == item["frame"] and item["frame"] <= q
        fact = _fact_from_event(item, source_observations, source_depth, binding["native"])
        all_event.append((fact, binding["native"]))
        private["fact_to_source"][fact["fact_id"]] = binding["source_fact_id"]
    assert len(all_event) == len(packet["INTERACTION_TABLE"]["rows"])

    by_native = defaultdict(list)
    risk = []
    for fact, n in all_event:
        if fact["quality"]["risk"] != "ANONYMOUS_CLEAN_ISLAND":
            risk.append(fact)
        else:
            by_native[n].append(fact)
    anonymous = []
    for n, values in sorted(by_native.items()):
        current = []
        prior_signature = None
        for fact in sorted(values, key=lambda x: x["frame"]):
            f = fact["frame"]
            sig = _signature(source_observations[f], n, _source_item(source_observations[f], n))
            if current and (f != current[-1]["frame"] + 1 or
                            fact["time_seconds"] <= current[-1]["time_seconds"] or
                            fact["time_seconds"] - current[-1]["time_seconds"] > .2 or
                            sig != prior_signature or len(current) >= MAX_ANONYMOUS_FRAGMENT_FRAMES or
                            current[-1]["frame"] < trigger <= f):
                name = f"{case}-S{len(anonymous) + 1:03d}"
                anonymous.append(_fragment(name, None, current, q_time))
                private["fragment_to_native"][name] = n
                current = []
            current.append(fact)
            prior_signature = sig
        if current:
            name = f"{case}-S{len(anonymous) + 1:03d}"
            anonymous.append(_fragment(name, None, current, q_time))
            private["fragment_to_native"][name] = n
    anonymous.sort(key=lambda x: (x["start_frame"], x["fragment_id"]))

    risk_intervals = []
    for fact in sorted(risk, key=lambda x: (x["frame"], x["fact_id"])):
        if not risk_intervals or fact["frame"] > risk_intervals[-1]["end_frame"] + 1:
            risk_intervals.append({"interval_id": f"{case}-R{len(risk_intervals) + 1:03d}",
                                   "identity_scope": "ANONYMOUS_RISK_OBSERVATIONS_NO_EDGES",
                                   "start_frame": fact["frame"], "end_frame": fact["frame"],
                                   "observations": []})
        interval = risk_intervals[-1]
        interval["end_frame"] = fact["frame"]
        interval["observations"].append([fact["fact_id"], fact["frame"], fact["time_seconds"],
                                         *fact["center_px"], fact["area_px"],
                                         fact["quality"]["risk"],
                                         *[fact["depth"][part][key] for part in ("core", "whole")
                                           for key in ("median", "mad", "n", "valid_fraction")],
                                         fact["depth"].get("sensor_available"),
                                         fact["depth"].get("overlap_pixels")])
    for interval in risk_intervals:
        interval["start_time_seconds"] = source_observations[interval["start_frame"]]["time"]
        interval["end_time_seconds"] = source_observations[interval["end_frame"]]["time"]
        interval["observation_count"] = len(interval["observations"])
        interval["columns"] = ["fact_id", "frame", "time_seconds", "center_x_px", "center_y_px",
                               "area_px", "risk_reason", "core_pipeline_mm", "core_mad", "core_n", "core_valid_fraction",
                               "whole_pipeline_mm", "whole_mad", "whole_n", "whole_valid_fraction",
                               "sensor_available", "overlap_pixels"]

    a, b = named["A"]["observations"][-1], named["B"]["observations"][-1]
    raw_relative = {"A": {"fact_id": a["fact_id"], "time_seconds": a["time_seconds"],
                          "center_px": a["center_px"]},
                    "B": {"fact_id": b["fact_id"], "time_seconds": b["time_seconds"],
                          "center_px": b["center_px"]},
                    "raw_B_minus_A_px_at_different_times": [_round(y - x) for x, y in zip(a["center_px"], b["center_px"])],
                    "time_gap_seconds": _round(b["time_seconds"] - a["time_seconds"]),
                    "interpretation": "DIFFERENT_TIMES_NOT_SIMULTANEOUS_ORDER"}
    av, bv = named["A"]["velocity"], named["B"]["velocity"]
    aligned = {"status": "UNKNOWN", "reason": "LOCAL_FRAGMENT_VELOCITY_UNAVAILABLE"}
    if av["status"] == bv["status"] == "ESTIMATE":
        align_time = max(a["time_seconds"], b["time_seconds"])
        ap = [a["center_px"][k] + av["velocity_px_per_s"][k] *
              (align_time - a["time_seconds"]) for k in (0, 1)]
        bp = [b["center_px"][k] + bv["velocity_px_per_s"][k] *
              (align_time - b["time_seconds"]) for k in (0, 1)]
        aligned = {"fact_id": f"RELATIVE-PRE-{case}", "status": "ESTIMATE",
                   "source_fact_ids": [a["fact_id"], b["fact_id"], av["fact_id"], bv["fact_id"]],
                   "aligned_time_seconds": align_time,
                   "relative_position_B_minus_A_px": [_round(bp[k] - ap[k]) for k in (0, 1)],
                   "relative_velocity_B_minus_A_px_per_s": [
                       _round(bv["velocity_px_per_s"][k] - av["velocity_px_per_s"][k])
                       for k in (0, 1)],
                   "method": "constant_velocity_projection_from_short_clean_fragment_OLS",
                   "max_projection_gap_seconds": _round(max(align_time - a["time_seconds"],
                                                             align_time - b["time_seconds"])),
                   "fit_residual_rms_px": {"A": av["residual_rms_px"],
                                           "B": bv["residual_rms_px"]},
                   "interpretation": "PROJECTED_ESTIMATE_NOT_OBSERVED_SAME_TIME_ORDER"}
    other = sorted(n for n in branch_context["view"]["mapping"] if n not in (native["X"], native["Y"]))
    assert len(other) == 4
    all_facts = {x["fact_id"] for segment in [*named.values(), *anonymous]
                 for x in segment["observations"]} | {x["fact_id"] for x in risk}
    current_others = []
    for i, n in enumerate(other, 1):
        matches = [key for key, value in lineage.items()
                   if value["frame"] == q and value["native"] == n and key in all_facts]
        assert len(matches) == 1, (case, q, n, matches)
        current_others.append({"role": f"U{i}", "observed_fact_id": matches[0],
                               "assignment_token": f"K{i}", "identity_scope": "CURRENT_B2_ASSIGNMENT_ONLY"})
    candidates = []
    for h in packet["hypotheses"]:
        mapping = {r: h["mapping"][r] for r in "XY"}
        edge_facts = {r: _edge(named[mapping[r]], named[r]) for r in "XY"}
        depth_totals = {}
        for part in ("core", "whole"):
            values = [edge_facts[r]["depth_endpoint_weak_cue"][part].get(
                "absolute_q_difference_pipeline_mm") for r in "XY"]
            depth_totals[part] = None if any(v is None for v in values) else _round(sum(values))
        candidates.append({"id": h["id"], "mapping": mapping | {f"U{i}": f"K{i}" for i in range(1, 5)},
                           "epistemic_type": "HYPOTHESIS_NOT_OBSERVED_PATH", "edge_comparisons": edge_facts,
                           "weak_endpoint_depth_sum_pipeline_mm": depth_totals})
    assert {x["id"] for x in candidates} == {"H1", "H2"}
    h1, h2 = sorted(candidates, key=lambda x: x["id"])
    disagree = (h1["weak_endpoint_depth_sum_pipeline_mm"]["core"] is not None and
                h2["weak_endpoint_depth_sum_pipeline_mm"]["core"] is not None and
                h1["weak_endpoint_depth_sum_pipeline_mm"]["whole"] is not None and
                h2["weak_endpoint_depth_sum_pipeline_mm"]["whole"] is not None and
                (h1["weak_endpoint_depth_sum_pipeline_mm"]["core"] < h2["weak_endpoint_depth_sum_pipeline_mm"]["core"]) !=
                (h1["weak_endpoint_depth_sum_pipeline_mm"]["whole"] < h2["weak_endpoint_depth_sum_pipeline_mm"]["whole"]))
    model_packet = {
        "request_id": f"EVENT-EVIDENCE-B2-{case}", "q_frame": q, "q_time_seconds": q_time,
        "coordinate_system": "full_640x360_mask_px; x_right; y_down; same_ROI_images",
        "trigger": packet["trigger"],
        "role_contract": "A/B pre-risk reference fragments; X/Y q-local fragments. Short segments are source-connected observations, never certified identities across risk. Risk observations are anonymous and have no identity edges. U roles are other current objects. Candidate mappings are hypotheses, not observed trajectories.",
        "reference_binding": {r: {"anchor_frame": branch_context["refs"][r]["anchor_frame"],
                                  "identity_scope": "BRANCH_FROZEN_REFERENCE_AT_ANCHOR"} for r in "AB"},
        "named_fragments": {r: _compact_fragment(x) for r, x in named.items()},
        "anonymous_clean_fragments": [_compact_fragment(x) for x in anonymous],
        "risk_intervals": risk_intervals,
        "relative_motion": {"pre_raw_different_times": raw_relative,
                            "pre_aligned_estimate": aligned,
                            "post_q_observed": packet["relative_motion"]["post"]},
        "event_boundaries": {"per_object_loss": packet["per_object_loss"],
                             "per_handle_clean_return": packet["per_handle_clean_return"],
                             "first_identity_reappearance": packet["first_identity_reappearance"],
                             "joint_clean_pair_streak": packet["joint_clean_pair_streak"],
                             "entry_side": packet["entry_side"]},
        "current_other_roles": current_others, "hypotheses": candidates,
        "depth_contract": "Actual source profiles; pipeline mm has unverified water-surface reference. Per-frame valid fraction measures availability, not identity stability. Endpoint differences are weak descriptive cues and may conflict between core and whole.",
        "source_version_metadata": "UNAVAILABLE_IN_SOURCE_STREAM; no version-based cross-risk identity claim",
        "core_whole_candidate_order_disagrees": disagree,
        "unknowns": packet["unknowns"],
        "risk_observation_count": len(risk), "clean_observation_count": sum(x["samples"] for x in anonymous),
        "raw_source": {"old_case": case, "old_q": q,
                       "full_fact_archive": "direct_history_replay/public/requests/" + case + ".json",
                       "model_view_is_compiled_not_information_equivalent": True},
        "IMAGE_INDEX": copy.deepcopy(branch_context["images"]),
    }
    private["q_native"] = native
    private["reference_public"] = {r: branch_context["refs"][r]["public_id"] for r in "AB"}
    private["current_other_native"] = {f"U{i}": n for i, n in enumerate(other, 1)}
    assert all(x["frame"] <= q for x in model_packet["IMAGE_INDEX"])
    assert all(x["frame"] <= q for s in [*named.values(), *anonymous]
               for x in s["observations"])
    assert sum(x["observation_count"] for x in risk_intervals) == len(risk)
    return model_packet, private


def render_overview(packet, target):
    """Geometry-only same-ROI view; lines never cross source fragment boundaries."""
    roi = packet["IMAGE_INDEX"][0]["roi_full_mask_xyxy"]
    assert all(x["roi_full_mask_xyxy"] == roi for x in packet["IMAGE_INDEX"])
    x0, y0, x1, y1 = roi
    scale = 2
    w, h = (x1 - x0) * scale, (y1 - y0) * scale
    top = 60
    image = Image.new("RGB", (3 * w, h + top), "#f7f8fa")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    for i, title in enumerate(("PRE: clean fragments", "RISK: anonymous points", "POST: clean fragments")):
        left = i * w
        draw.rectangle((left, top, left + w - 1, top + h - 1), outline="#8c939b", width=2)
        draw.text((left + 8, 6), title, fill="#111827", font=font)
        draw.text((left + 8, 24), f"ROI {x0},{y0},{x1},{y1}; x right, y down", fill="#344054", font=font)
        draw.text((left + 8, 40), f"trigger F{packet['trigger']['frame']}; q F{packet['q_frame']}",
                  fill="#344054", font=font)

    def xy(p, panel):
        return (int(panel * w + (p[0] - x0) * scale), int(top + (p[1] - y0) * scale))

    trigger = packet["trigger"]["frame"]
    fragments = [*packet["named_fragments"].values(), *packet["anonymous_clean_fragments"]]
    for index, segment in enumerate(fragments):
        role = segment["role"]
        panel = 0 if role in ("A", "B") or segment["end_frame"] < trigger else 2
        # Segment IDs, rather than pre/post role colors, determine the neutral palette.
        color = (48 + (index * 71) % 150, 55 + (index * 47) % 135, 68 + (index * 31) % 145)
        points = [xy((obs[3], obs[4]), panel) for obs in segment["observations"]]
        if len(points) > 1:
            draw.line(points, fill=color, width=2)
        for px, py in (points[0], points[-1]):
            draw.ellipse((px - 3, py - 3, px + 3, py + 3), fill=color)
        label = (role or segment["fragment_id"].split("-")[-1]) + f" F{segment['start_frame']}-{segment['end_frame']}"
        draw.text((points[-1][0] + 3, points[-1][1] - 9), label, fill=color, font=font)
    for interval in packet["risk_intervals"]:
        for row in interval["observations"]:
            px, py = xy((row[3], row[4]), 1)
            draw.ellipse((px - 2, py - 2, px + 2, py + 2), fill="#667085")
    target = Path(target)
    assert not target.exists(), target
    target.parent.mkdir(parents=True, exist_ok=True)
    image.save(target, format="PNG")
    return {"image_id": packet["request_id"] + "-OVERVIEW", "frame": packet["q_frame"],
            "time_seconds": packet["q_time_seconds"], "width": image.width, "height": image.height,
            "roi_full_mask_xyxy": roi, "full_to_image": "three_same_ROI_panels;scale=2;offset=panel_width*panel",
            "pixel_source": "geometry_only_from_source_facts_no_private_RGB",
            "segment_ids": [x["fragment_id"] for x in fragments],
            "risk_interval_ids": [x["interval_id"] for x in packet["risk_intervals"]]}
