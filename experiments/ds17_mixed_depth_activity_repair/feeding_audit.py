"""Post-seal scalar audit of DS16 Feeding; never replay or read GT pixels."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
OLD = REPO / "experiments/ds16_relative_depth_order/run"
SOURCE = Path("E:/CAU/D-MOT/data/AnnotationFeeding_20260924")
ARMS = ("SAM3_NATIVE", "Z4Q_FROZEN", "DEPTH_ORDER", "ORDER_OFF")


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def rows(path):
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        return [json.loads(line) for line in stream]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def binding(path):
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": sha(path)}


def origin_rule(action):
    return "BIRTH_REFINE" if action.get("phase") == "birth" else "D1_DELAYED"


def batch_context(frame, batches):
    owner = next((b for b in batches if b["writes_from"] <= frame <= b["end"]), None)
    nearest = min(batches[1:], key=lambda b: abs(frame - b["writes_from"]))
    return {"original_frame": frame, "exporting_batch": owner,
            "nearest_new_source_boundary": nearest["writes_from"],
            "distance_frames": frame - nearest["writes_from"],
            "at_new_source_boundary": frame == nearest["writes_from"],
            "in_any_inference_overlap": any(b["start"] <= frame < b["writes_from"] for b in batches[1:]),
            "interpretation": "SOURCE_SCHEDULE_CORRELATION_ONLY_NOT_IDENTITY_OR_CAUSAL_PROOF"}


def compare(switches, arm, base):
    left = {(x["gt_id"], x["frame"]): x for x in switches[arm]}
    right = {(x["gt_id"], x["frame"]): x for x in switches[base]}
    assert len(left) == len(switches[arm]) and len(right) == len(switches[base])
    added = sorted(left.keys() - right.keys(), key=lambda k: (k[1], k[0]))
    removed = sorted(right.keys() - left.keys(), key=lambda k: (k[1], k[0]))
    common = sorted(left.keys() & right.keys(), key=lambda k: (k[1], k[0]))
    changed = [k for k in common if (left[k]["from_public_id"], left[k]["to_public_id"]) !=
               (right[k]["from_public_id"], right[k]["to_public_id"])]
    return {"arm": arm, "base": base, "added": len(added), "removed": len(removed),
            "common": len(common), "net": len(added) - len(removed),
            "common_public_transition_changed": len(changed),
            "added_keys": added, "removed_keys": removed, "common_keys": common,
            "common_public_transition_changed_keys": changed}


def depth_summary(depth, local, native):
    obj = depth.get(local, {}).get("adaptive_raw", {}).get(str(native))
    if not obj:
        return {"status": "MISSING_LOGGED_STATISTICS", "physical_surface_identity": "UNKNOWN"}
    return {key: obj.get(key) for key in ("fact_id", "source", "whole", "core", "core_usable",
                                        "physical_surface_identity", "roi_geometry")}


def frame_state(global_frame, arm, predictions, transactions, references, offset, involved):
    pred = predictions.get(global_frame)
    if pred is None:
        return {"global_frame": global_frame, "status": "OUTSIDE_SEGMENT"}
    mapping = {int(x["mask"][2:]): int(x["id"]) for x in pred["variants"][arm]}
    tx = transactions.get((arm, global_frame), {})
    trace = tx.get("controller_trace", {})
    alias = {int(k): int(v) for k, v in tx.get("actual_alias_targets", {}).items()}
    matches = references.get(global_frame - offset + 1, {})
    return {"global_frame": global_frame, "actual_mapping": mapping,
            "involved_native_mapping": {n: mapping.get(n) for n in sorted(involved)},
            "actual_alias_targets": alias, "controller_events": trace.get("events", []),
            "native_return_checks": trace.get("native_return_checks", []),
            "birth_checks": trace.get("birth_checks", []),
            "return_quarantine": trace.get("return_quarantine", {}),
            "controller_alias_records": trace.get("aliases", {}),
            "event_signal": tx.get("signal"), "active_event": tx.get("active_event"),
            "restore": tx.get("restore"), "automatic_adoption": tx.get("automatic_candidate_events", []),
            "involved_unique_reference_matches": {n: matches.get(str(n)) for n in sorted(involved)},
            "reference_match_semantics": "POSTSEAL_UNIQUE_IOU_MATCHER_NOT_FULL_CLEAR_MATCH_HISTORY"}


def previous_unique_match(gt, before, mapping_arm, predictions, references, offset):
    for frame in range(before - 1, offset - 1, -1):
        mapping = {int(x["mask"][2:]): x["id"] for x in predictions[frame]["variants"][mapping_arm]}
        hits = [{"native_id": int(n), "public_id": mapping.get(int(n)), "match": match}
                for n, match in references.get(frame - offset + 1, {}).items()
                if match.get("status") == "UNIQUE_IOU_MATCH" and match.get("gt_id") == gt]
        if hits:
            return {"global_frame": frame, "candidates": hits,
                    "status": "UNIQUE_STORED_MATCH" if len(hits) == 1 else "MULTIPLE_STORED_MATCHES",
                    "semantics": "INDEPENDENT_REFERENCE_MATCHER_NOT_ASSERTED_PREVIOUS_CLEAR_MATCH"}
    return {"status": "NO_PRIOR_UNIQUE_REFERENCE_MATCH"}


def activity(predictions, arm, source, frame, offset):
    present = [f for f in sorted(predictions) if f <= frame and
               any(int(x["mask"][2:]) == source for x in predictions[f]["variants"][arm])]
    prior = [f for f in present if f < frame]
    contiguous = 0
    for f in range(frame - 1, offset - 1, -1):
        if f not in prior:
            break
        contiguous += 1
    recent = list(range(max(offset, frame - 10), frame))
    return {"first_seen_in_segment": min(present), "left_censored_at_segment_start": min(present) == offset,
            "elapsed_frames_since_first_seen": frame - min(present),
            "consecutive_present_frames_before_commit": contiguous,
            "preceding_window_frames": len(recent), "present_frames_in_preceding_window": sum(f in prior for f in recent),
            "qualification": "RAW_NATIVE_PRESENCE_ONLY_NOT_CLEAN_IDENTITY_OR_GENERATION_CERTIFICATION"}


def audit_segment(folder, batches, sources):
    public = folder / "public"
    seal_path = public / "PREDICTIONS_SEALED.json"
    seal = read(seal_path)
    for name, expected in seal["artifacts_sha256"].items():
        assert sha(public / name) == expected, (folder.name, name)
    for name in ("PREDICTIONS_SEALED.json", "METRICS.json", "SWITCHES.json", "AUTOMATIC_RECONNECT_AUDIT.json",
                 "REFERENCE_MATCHES.jsonl.gz", "TRANSACTIONS.jsonl.gz", "DEPTH_OBSERVATIONS.jsonl.gz", "EVENT_AUDIT.json"):
        sources.append(binding(public / name))
    offset = seal["original_frames"][0]
    metrics = read(public / "METRICS.json")["metrics"]
    switches = read(public / "SWITCHES.json")
    predictions = {row["global_frame"]: row for row in rows(public / "predictions.jsonl.gz")}
    transactions = {(row["arm"], row["global_frame"]): row for row in rows(public / "TRANSACTIONS.jsonl.gz")}
    references = {row["frame"]: row["matches"] for row in rows(public / "REFERENCE_MATCHES.jsonl.gz")}
    depth = {row["frame"]: row for row in rows(public / "DEPTH_OBSERVATIONS.jsonl.gz")}
    auto = read(public / "AUTOMATIC_RECONNECT_AUDIT.json")
    event_audit = read(public / "EVENT_AUDIT.json")
    pairs = [(arm, "SAM3_NATIVE") for arm in ARMS[1:]] + [("DEPTH_ORDER", "Z4Q_FROZEN"), ("ORDER_OFF", "Z4Q_FROZEN")]
    comparisons = [compare(switches, arm, base) for arm, base in pairs]
    indices = {arm: {(x["gt_id"], x["frame"]): x for x in switches[arm]} for arm in ARMS}
    allkeys = sorted(set().union(*(set(v) for v in indices.values())), key=lambda k: (k[1], k[0]))
    audit = []
    for gt, frame in allkeys:
        involved = {x["native_id"] for arm in ARMS if (x := indices[arm].get((gt, frame)))}
        involved.update(int(x[k]) for arm in ARMS if (x := indices[arm].get((gt, frame)))
                        for k in ("from_public_id", "to_public_id"))
        arm_details = {}
        for arm in ARMS:
            switch = indices[arm].get((gt, frame))
            direct = [x for x in auto["arms"].get(arm, []) if switch and
                      x["global_frame"] == frame and x["source"] == switch["native_id"] and
                      x["actual_first_public_id"] == switch["to_public_id"]]
            if direct:
                reason = "DIRECT_" + direct[0]["origin_rule"] + "_FIRST_PUBLISHED_DURABLE_COMMIT"
            elif switch and arm == "SAM3_NATIVE":
                reason = "SOURCE_NATIVE_HANDOFF_OR_EXISTING_NATIVE_TRACK_ERROR"
            elif switch:
                now = transactions[arm, frame]
                prev = transactions.get((arm, frame - 1), {})
                aliases = now.get("actual_alias_targets", {})
                oldaliases = prev.get("actual_alias_targets", {})
                reason = ("ALIAS_CHANGED_WITHOUT_NEW_ACCEPTED_ACTION" if aliases != oldaliases else
                          "PERSISTENT_ALIAS_ON_SOURCE_HANDOFF" if str(switch["native_id"]) in aliases else
                          "SOURCE_NATIVE_HANDOFF_WITH_BRANCH_HISTORY")
            else:
                reason = "NO_CLEAR_SWITCH_AT_THIS_GT_TIME"
            arm_details[arm] = {"clear_switch": switch, "reason": reason, "direct_automatic_actions": direct,
                                "previous_unique_reference": previous_unique_match(gt, frame, arm, predictions, references, offset),
                                "before_current_after": [frame_state(f, arm, predictions, transactions, references, offset, involved)
                                                         for f in (frame - 1, frame, frame + 1)]}
        audit.append({"gt_id": gt, "global_frame": frame, "batch_context": batch_context(frame, batches),
                      "arms": arm_details})
    actions = {}
    for arm in ARMS[1:]:
        entries = []
        for action in auto["arms"][arm]:
            frame, source, target = action["global_frame"], action["source"], action["target"]
            local = frame - offset + 1
            original = action["actual_controller_action"]
            anchor = action.get("actual_old_anchor") or original.get("old_anchor") or {}
            anchor_native, anchor_frame = anchor.get("native_id"), anchor.get("frame")
            lifetime = [f for (a, f), tx in transactions.items() if a == arm and f >= frame and
                        int(tx.get("actual_alias_targets", {}).get(str(source), -1)) == target]
            entries.append({**action, "source_presence": activity(predictions, arm, source, frame, offset),
                            "batch_context": batch_context(frame, batches),
                            "source_first_seen_batch": batch_context(activity(predictions, arm, source, frame, offset)["first_seen_in_segment"], batches),
                            "actual_logged_query_depth": depth_summary(depth, local, source),
                            "actual_logged_anchor_depth": depth_summary(depth, anchor_frame, anchor_native) if anchor_frame and anchor_native else None,
                            "mixed_depth_causation": "UNKNOWN_RAW_PIXEL_COMPONENTS_NOT_INSPECTED",
                            "alias_same_target_present_until_global": max(lifetime) if lifetime else None,
                            "alias_remaining_in_final_state": bool(lifetime and max(lifetime) == max(predictions)),
                            "exact_switches_at_action": [x for x in switches[arm] if x["frame"] == frame and x["native_id"] == source],
                            "target_was_current_raw_native": any(int(x["mask"][2:]) == target for x in predictions[frame]["variants"]["SAM3_NATIVE"]),
                            "public_bank_anchor_native_differs_from_public_integer": anchor_native != target})
        actions[arm] = entries
    groups = {arm: {"events": len(event_audit["arms"][arm]["group_events"]),
                    "restore_counts": dict(Counter(x.get("restore_status") or x["status"] for x in event_audit["arms"][arm]["group_events"])),
                    "commits": sum(x.get("restore_status") == "COMMIT" for x in event_audit["arms"][arm]["group_events"])}
              for arm in ("DEPTH_ORDER", "ORDER_OFF")}
    mapping_equal = {arm: all(row["variants"][arm] == row["variants"]["Z4Q_FROZEN"] for row in predictions.values())
                     for arm in ("DEPTH_ORDER", "ORDER_OFF")}
    return {"segment": folder.name, "frames": seal["frames"], "metrics": {a: metrics[a] for a in ARMS},
            "comparisons": comparisons, "automatic_actions": actions, "group_events": groups,
            "published_sequence_exactly_equal_to_Z4Q_FROZEN": mapping_equal, "switch_action_audit": audit}


def markdown(report):
    lines = ["# DS17 前置：旧 DS16 Feeding 逐切换原因审计", "", "仅追加只读诊断。旧预测/评分/封存保持不变；GT 仅使用已封存后评分产生的标量匹配。", "",
             "## 主结论", "", "四段共 1471 帧，原生 108 次 IDSW；冻结 Z4Q 与 DEPTH_ORDER 均 132 次。逐 GT/时刻匹配为新增 24、消除 0、共同 108；共同切换还有 15 条公共 from/to 改变。",
             "", "24 个新增切换全部绑定同帧、同 source 的 D1_DELAYED 实际提交及首次发布：15 个旧物理判定 WRONG、8 个 CORRECT、1 个 UNSCORABLE。正确重接也会新增切换，因为该 source 的新公共 ID 已先发布，随后才改回旧 ID。不能把 IDSW 增量全部解释为错误恢复。",
             "", "DEPTH_ORDER 在四段逐帧与冻结 Z4Q 完全相同，没有组恢复提交；新增相对次序模块不能为常驻自动继承的损害背锅。ORDER_OFF 最后一段有独立真实状态变化，合计 130 次：相对原生新增 23、消除 1。", "",
             "## 同源完整指标", "", "|片段|分支|IDF1|HOTA|AssA|IDSW|FP|FN|", "|---|---|---:|---:|---:|---:|---:|---:|"]
    for segment in report["segments"]:
        for arm, m in segment["metrics"].items():
            lines.append(f"|{segment['segment']}|{arm}|{m['IDF1']:.6f}|{m['HOTA']:.6f}|{m['AssA']:.6f}|{m['IDSW']}|{m['FP']}|{m['FN']}|")
    lines += ["", "## 全部新增与消除", "", "按 GT 标量和切换时刻匹配，不按整段净数反推动作。F 为原录像 0 基帧号；候选来源、alias、bank anchor 及帧前中后映射见同名 JSON。", "", "|片段|分支相对 NATIVE|新增|消除|共同|共同 from/to 改变|", "|---|---|---:|---:|---:|---:|"]
    for seg in report["segments"]:
        for x in seg["comparisons"][:3]:
            lines.append(f"|{seg['segment']}|{x['arm']}|{x['added']}|{x['removed']}|{x['common']}|{x['common_public_transition_changed']}|")
    lines += ["", "### 冻结 Z4Q 新增 24 次：实际 D1 提交", "", "|片段|F|GT|公开ID|source|旧物理判定|提交前连续存在帧|深度残差/容差 mm|", "|---|---:|---:|---|---:|---|---:|---:|"]
    for seg in report["segments"]:
        added = {tuple(x) for x in seg["comparisons"][0]["added_keys"]}
        for action in seg["automatic_actions"]["Z4Q_FROZEN"]:
            for switch in action["exact_switches_at_action"]:
                if (switch["gt_id"], switch["frame"]) not in added:
                    continue
                actual = action["actual_controller_action"]
                residual, tolerance = actual.get("residual_mm"), actual.get("tolerance_mm")
                measurement = f"{residual:.3f}/{tolerance:.3f}" if residual is not None and tolerance is not None else "UNKNOWN"
                lines.append(f"|{seg['segment']}|{switch['frame']}|{switch['gt_id']}|{switch['from_public_id']}→{switch['to_public_id']}|{action['source']}|{action['physical']}|{action['source_presence']['consecutive_present_frames_before_commit']}|{measurement}|")
    lines += ["", "## 因果边界与来源", "",
              "- `kind=reconnect` 不等于 D1：F468 的 `phase=birth` 明确来自 BIRTH_REFINE。它对应共同原生切换，其来源参考物理不同；不是本轮 24 个新增 D1 中的一条。",
              "- 四段自动提交共 27 次：17 WRONG、8 CORRECT、2 UNSCORABLE。未新增 IDSW 的动作仍可损害整段身份一致性；不得由新增数量推断总错误动作数。",
              "- 原始 SAM3 20 帧批次、5 帧重叠、步长 15。真实导出代码跳过已有帧，首批写 0–19，后续从 batch_start+5 写到 batch_end；当前四段使用 root `ML/labels_raw`，不是后来分段重跑的 v2/v3/v4 来源。批次匹配只做重叠 IoU，编号不是身份认证。",
              "- 每条切换都列批次边界距离及实际导出批次。批次可能提供新 source 和错号，但大量 D1 追加改号发生在批次内部；不能把所有新增切换归于边界。",
              "- 活动记录只证明 source 连续出现/已发布，不能自动认证 clean 身份；参考 anchor、generation 与 public 整数必须分别验证。旧 alias 持久携带前次映射，并可影响共同切换及后续 bank 来源。",
              "- 日志中的 small residual、valid_fraction、whole/core 分位数不是上下鱼混合的像素证明。本审计不读取原始像素；混合深度归因为 UNKNOWN，不声称排除了混合。",
              "- 本次为可追溯状态/发布诊断，没有运行新的 ALLOW/VETO 反事实。已有旧 F159 实际反事实可作局部支持，不能代替所有动作的全段因果验证。", "",
              "## 一个通用修复假设", "",
              "在同一因果状态中区分已连续活动且已公开的 source、真正重新出现待分配的 source，以及仍在活动的旧公共身份所有者。让两条常驻继承入口在写 bank/alias 之前使用相同活动证据；不以 native 年龄整行封禁、不以 GT 指定边，不永久锁 ID。针对已发布 source 的追加身份改写与当前活跃身份抢占保守拒绝；不确定时保留原映射。其全段结果由 DS17 新冻结试验验证，不能预报提点。", "",
              "## 复现", "", "用现有 D-MOT Python 执行 `experiments/ds17_mixed_depth_activity_repair/feeding_audit.py`；仅读取 DS16 seal、标量评分、真实 trace、测量统计与原始批次元数据。完整文件路径/字节/SHA 和全部逐条证据在 JSON 中。新增模型 HTTP=0、费用=0。"]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=HERE)
    args = parser.parse_args()
    allseal = OLD / "ALL_PREDICTIONS_SEALED.json"
    assert read(allseal)["status"] == "ALL_PREDICTIONS_AND_ACCESS_SEALED"
    protocol_path, batches_path = SOURCE / "full_protocol.json", SOURCE / "ML/full_report.json"
    protocol, batch_report = read(protocol_path), read(batches_path)
    assert protocol["batch_size"] == 20 and protocol["overlap"] == 5
    batches = []
    for i, row in enumerate(batch_report["batch_matches"]):
        start, end = map(int, row["batch"].split(".")[0].split("-"))
        batches.append({"name": row["batch"], "start": start, "end": end,
                        "writes_from": start if i == 0 else start + protocol["overlap"],
                        "overlap_id_matches": row["matches"]})
    sources = [binding(p) for p in (allseal, OLD / "METRICS.json", protocol_path, batches_path,
                                    Path("E:/CAU/D-MOT/tools/prelabel_feeding_20260924/postprocess.py"),
                                    Path("E:/CAU/D-MOT/tools/prelabel_new_bags_20260919/postprocess.py"))]
    segments = [audit_segment(p, batches, sources) for p in sorted(OLD.glob("feeding_*"))]
    sums = {arm: {field: sum(segment["metrics"][arm][field] for segment in segments)
                  for field in ("IDSW", "FP", "FN")} for arm in ARMS}
    pooled = read(OLD / "METRICS.json")["feeding_pooled"]["metrics"]
    report = {"status": "COMPLETED_READONLY_POSTSEAL_CAUSE_AUDIT", "scope_frames": sum(x["frames"] for x in segments),
              "arms": ARMS, "model_http": 0, "cost_usd": 0, "raw_pixel_inspection": False,
              "gt_access": "EXISTING_POSTSEAL_SCALAR_MATCHES_AND_SCORED_SWITCHES_ONLY",
              "mixed_depth_causation": "UNKNOWN", "source_origin": str(SOURCE / "ML/labels_raw"),
              "source_protocol": protocol, "original_batch_metadata": batches,
              "full_metric_sums": sums, "pooled_metrics": {a: pooled[a] for a in ARMS},
              "segments": segments, "source_bindings": sources,
              "safety": {"old_artifacts_modified": False, "new_replay_or_rescore": False,
                         "gt_driven_rules_or_sample_selection": False}, "generator": binding(Path(__file__))}
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "FEEDING_CAUSE_AUDIT.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.output / "FEEDING_CAUSE_AUDIT.md").write_text(markdown(report), encoding="utf-8")
    print(json.dumps({"status": report["status"], "frames": report["scope_frames"], "sums": sums,
                      "json": str(args.output / "FEEDING_CAUSE_AUDIT.json")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
