"""Postscore-only Feeding action audit; never changes prediction or scoring facts."""
from collections import Counter
from common import ARMS, HERE, RUN, SEGMENTS, artifact, read, rows, sha, write_new


FIELDS = ("IDF1", "HOTA", "AssA", "IDSW", "FP", "FN")


def comparison(switches, arm, base):
    a = {(x["gt_id"], x["frame"]): x for x in switches[arm]}
    b = {(x["gt_id"], x["frame"]): x for x in switches[base]}
    order = lambda k: (k[1], k[0])
    return dict(arm=arm, base=base, added=[a[k] for k in sorted(a.keys() - b.keys(), key=order)],
        removed=[b[k] for k in sorted(b.keys() - a.keys(), key=order)],
        common=len(a.keys() & b.keys()), net=len(a) - len(b),
        common_transition_changed=[dict(gt_id=k[0], frame=k[1], arm=a[k], base=b[k])
            for k in sorted(a.keys() & b.keys(), key=order)
            if (a[k]["from_public_id"], a[k]["to_public_id"]) !=
               (b[k]["from_public_id"], b[k]["to_public_id"])])


def compact_part(data):
    return {key: data.get(key) for key in ("fact_id", "status", "reason", "eligible_single", "mixture_flag",
        "independent_mixture_flag", "inclusive_mixture_flag", "quality_usable", "source_ownership_exclusive",
        "source_population_unverified_n", "within_mask_duplicate_pixels_excluded", "shared_source_pixels_excluded",
        "summary", "inclusive_summary", "layer_count", "inclusive_layer_count", "scalar_population_difference")}


def main():
    required = (RUN / "ALL_PREDICTIONS_SEALED.json", RUN / "METRICS.json", RUN / "SCORE_PROVENANCE.json")
    assert all(p.exists() for p in required), "All predictions and independent full scoring must be complete"
    sealed, metrics, provenance = (read(p) for p in required)
    assert sealed["status"] == "ALL_PREDICTIONS_AND_ACCESS_SEALED"
    assert metrics["status"] == "SCORED_AFTER_ALL_SIX_ARMS_EIGHT_SEALS"
    assert provenance["reference_opened_after_all_seals"] and not provenance["GT_used_for_predictions"]
    assert metrics["all_seal"] == artifact(required[0])
    sources = [artifact(p) for p in required]
    results = {}
    for name in SEGMENTS:
        if not name.startswith("feeding_"):
            continue
        public = RUN / name / "public"
        seal = read(public / "PREDICTIONS_SEALED.json")
        for filename, expected in seal["artifacts_sha256"].items():
            assert sha(public / filename) == expected
        for filename in ("PREDICTIONS_SEALED.json", "METRICS.json", "SWITCHES.json", "AUTOMATIC_RECONNECT_AUDIT.json",
                         "EVENT_AUDIT.json", "TRANSACTIONS.jsonl.gz", "MIXED_DEPTH.jsonl.gz", "DEPTH_OBSERVATIONS.jsonl.gz"):
            sources.append(artifact(public / filename))
        scalar = read(public / "METRICS.json")["metrics"]
        switches = read(public / "SWITCHES.json")
        automatic = read(public / "AUTOMATIC_RECONNECT_AUDIT.json")["arms"]
        event_audit = read(public / "EVENT_AUDIT.json")["arms"]
        predictions = {x["global_frame"]: x for x in rows(public / "predictions.jsonl.gz")}
        transactions = {(x["arm"], x["global_frame"]): x for x in rows(public / "TRANSACTIONS.jsonl.gz")}
        measurements = {x["global_frame"]: x for x in rows(public / "DEPTH_OBSERVATIONS.jsonl.gz")}
        mix = {x["global_frame"]: x for x in rows(public / "MIXED_DEPTH.jsonl.gz")}
        offset = seal["original_frames"][0]
        comparisons = [comparison(switches, arm, base) for base in ("SAM3_NATIVE", "ACTIVITY_ORDER") for arm in ARMS]
        automatic_details = {}
        for arm in ARMS[1:]:
            values = []
            for action in automatic.get(arm, []):
                f, n, target = action["global_frame"], action["source"], action["target"]
                exact = [x for x in switches[arm] if x["frame"] == f and x["native_id"] == n and x["to_public_id"] == target]
                prior = []
                for frame in range(f - 1, offset - 1, -1):
                    found = next((x for x in predictions[frame]["variants"][arm] if int(x["mask"][2:]) == n), None)
                    if not found:
                        break
                    prior.append(dict(frame=frame, public_id=found["id"]))
                literal = action["physical"]
                kind = "WRONG_PHYSICAL_MAPPING" if literal == "WRONG" else (
                    "CORRECT_PHYSICAL_BUT_ALREADY_PUBLISHED_ID_CHANGE" if literal == "CORRECT" and exact else
                    "CORRECT_PHYSICAL_NO_EXTRA_CLEAR_SWITCH" if literal == "CORRECT" else literal)
                cert = mix[f]["objects"][str(n)]
                raw = measurements[f]["adaptive_raw"][str(n)]
                values.append(dict(action=action, category=kind, exact_switches=exact,
                    consecutive_source_publications_before_action=len(prior), preceding_public_ids=prior[:10],
                    current_scalar_core_usable=raw["core_usable"],
                    current_core_guard_would_disable=bool(raw["core_usable"] and not cert["core"]["eligible_single"]),
                    current_mixed_whole=compact_part(cert["whole"]), current_mixed_core=compact_part(cert["core"])))
            automatic_details[arm] = dict(accepted=len(values), physical_counts=dict(Counter(x["action"]["physical"] for x in values)),
                origin_counts=dict(Counter(x["action"]["origin_rule"] for x in values)),
                category_counts=dict(Counter(x["category"] for x in values)),
                durable_commits=sum(x["action"]["durable_automatic_commit"] for x in values), values=values)
        action_keys = {arm: {(x["global_frame"], x["source"], x["target"], x["origin_rule"]): x
                            for x in automatic.get(arm, []) if x["durable_automatic_commit"]} for arm in ARMS[1:]}
        changed_actions = {}
        for arm, base in (("ACTIVITY_ORDER", "DS16_ORDER"), ("MIXED_ORDER", "ACTIVITY_ORDER"), ("MIXED_OFF", "MIXED_ORDER")):
            new, old = action_keys[arm], action_keys[base]
            sort = lambda k: (k[0], k[1], k[2], k[3])
            changed_actions[arm + "_vs_" + base] = dict(
                added=[new[k] for k in sorted(new.keys() - old.keys(), key=sort)],
                removed=[old[k] for k in sorted(old.keys() - new.keys(), key=sort)],
                note="Actual independent-state action difference, not an isolated edge counterfactual")
        coverage = {part: dict(total=0, statuses=Counter(), reasons=Counter(), quality_usable=0,
            source_ownership_exclusive=0, potential_layers=0, independent_layers=0, inclusive_layers=0,
            eligible_single=0, rejection_only_source_ownership=0, rejection_insufficient_coverage_or_broad_scale=0)
            for part in ("whole", "core")}
        old_core_usable = core_disabled = 0
        for frame, row in mix.items():
            raw = measurements[frame]["adaptive_raw"]
            for n, obj in row["objects"].items():
                old_core_usable += bool(raw[n]["core_usable"])
                core_disabled += bool(raw[n]["core_usable"] and not obj["core"]["eligible_single"])
                for part in ("whole", "core"):
                    d, c = obj[part], coverage[part]
                    c["total"] += 1
                    c["statuses"][d["status"]] += 1
                    c["reasons"][d["reason"]] += 1
                    c["quality_usable"] += bool(d["quality_usable"])
                    c["source_ownership_exclusive"] += bool(d["source_ownership_exclusive"])
                    c["potential_layers"] += bool(d["mixture_flag"])
                    c["independent_layers"] += bool(d["independent_mixture_flag"])
                    c["inclusive_layers"] += bool(d["inclusive_mixture_flag"])
                    c["eligible_single"] += bool(d["eligible_single"])
                    c["rejection_only_source_ownership"] += d["reason"] == "ORIGINAL_SCALAR_INCLUDES_SHARED_OR_UNVERIFIED_NATIVE_SOURCES"
                    c["rejection_insufficient_coverage_or_broad_scale"] += d["reason"] == "INSUFFICIENT_INDEPENDENT_COVERAGE_OR_BROAD_SCALAR_SUPPORT"
        divergent_switches = []
        for c in comparisons:
            for status in ("added", "removed"):
                owner = c["arm"] if status == "added" else c["base"]
                for switch in c[status]:
                    f, n = switch["frame"], switch["native_id"]
                    direct = [v for v in automatic_details.get(owner, {}).get("values", []) if
                              v["action"]["global_frame"] == f and v["action"]["source"] == n and
                              v["action"]["actual_first_public_id"] == switch["to_public_id"]]
                    tx = transactions.get((owner, f), {})
                    group = [x for x in event_audit.get(owner, {}).get("group_events", []) if x.get("q") == f - offset + 1]
                    divergent_switches.append(dict(arm=c["arm"], base=c["base"], change=status, owner=owner,
                        switch=switch, direct_automatic_actions=direct,
                        group_q_audit=group, actual_event_restore=tx.get("restore"),
                        actual_alias_targets=tx.get("actual_alias_targets", {}),
                        actual_controller_events=tx.get("controller_trace", {}).get("events", []),
                        reason="DIRECT_AUTOMATIC_ACTION" if direct else "GROUP_FIRST_PUBLICATION" if tx.get("restore") else
                               "SOURCE_HANDOFF_WITH_BRANCH_ALIAS_HISTORY_OR_NATIVE", category_boundary="No attribution invented when direct action absent"))
        groups = {arm: dict(events=len(event_audit[arm]["group_events"]),
            restore_status=dict(Counter(x.get("restore_status") or "NO_SPLIT" for x in event_audit[arm]["group_events"])),
            committed_literal=dict(Counter(x["physical"] for x in event_audit[arm]["group_events"])),
            committed_pre_consensus=dict(Counter(x.get("committed_pre_consensus_verdict") or "NO_SPLIT" for x in event_audit[arm]["group_events"])),
            values=event_audit[arm]["group_events"]) for arm in ARMS[2:]}
        results[name] = dict(frames=seal["frames"], metrics=scalar,
            deltas={base: {arm: {f: scalar[arm][f] - scalar[base][f] for f in FIELDS} for arm in ARMS}
                    for base in ("SAM3_NATIVE", "Z4Q_FROZEN", "ACTIVITY_ORDER", "MIXED_OFF")},
            switch_comparisons=comparisons, divergent_switch_audit=divergent_switches,
            automatic_actions=automatic_details, changed_automatic_actions=changed_actions, group_restores=groups,
            mixed_coverage=coverage, original_core_usable=old_core_usable,
            original_usable_core_disabled_by_guard=core_disabled)
    report = dict(status="POSTSCORE_FEEDING_NEW_REVIEW_COMPLETE", frames=sum(x["frames"] for x in results.values()),
        pooled=metrics["feeding_pooled"], segments=results, source_bindings=sources, helper=artifact(__file__),
        physical_mixture_fish_count_and_true_depth_order="UNKNOWN", GT_used_for_new_rules=False,
        limitations=["Potential separated depth layers are not certified different fish",
                     "Source ownership/coverage rejection is not a detected mixture",
                     "Lower IDSW need not increase IDF1/HOTA/AssA", "No isolated action counterfactual in this report"],
        old_prediction_score_seals_modified=False, model_http=0, cost_usd=0)
    write_new(HERE / "FEEDING_NEW_REVIEW.json", report)
    lines = ["# DS17 Feeding 新分支：封存后实际结果审计", "", "所有新预测封存、统一评分及来源记录完成后读取。新增模型 HTTP=0、费用=0。", "",
        "## 同源1471帧 pooled 完整指标", "", "|分支|IDF1|HOTA|AssA|IDSW|FP|FN|", "|---|---:|---:|---:|---:|---:|---:|"]
    for arm, m in report["pooled"]["metrics"].items():
        lines.append(f"|{arm}|{m['IDF1']:.6f}|{m['HOTA']:.6f}|{m['AssA']:.6f}|{m['IDSW']}|{m['FP']}|{m['FN']}|")
    lines += ["", "## 每段实际增删切换", "", "|片段|分支|参照|新增|消除|共同|净值|", "|---|---|---|---:|---:|---:|---:|"]
    for name, segment in results.items():
        for c in segment["switch_comparisons"]:
            if c["arm"] in ("ACTIVITY_ORDER", "MIXED_ORDER", "MIXED_OFF") and c["arm"] != c["base"]:
                lines.append(f"|{name}|{c['arm']}|{c['base']}|{len(c['added'])}|{len(c['removed'])}|{c['common']}|{c['net']}|")
    lines += ["", "## 自动动作与物理判定", "", "|片段|分支|D1/BIRTH accepted|实际durable|物理错误|物理正确但晚改号|不可评分|", "|---|---|---:|---:|---:|---:|---:|"]
    for name, segment in results.items():
        for arm in ("DS16_ORDER", "ACTIVITY_ORDER", "MIXED_ORDER", "MIXED_OFF"):
            a = segment["automatic_actions"][arm]
            c = a["category_counts"]
            lines.append(f"|{name}|{arm}|{a['accepted']}|{a['durable_commits']}|{c.get('WRONG_PHYSICAL_MAPPING',0)}|{c.get('CORRECT_PHYSICAL_BUT_ALREADY_PUBLISHED_ID_CHANGE',0)}|{c.get('UNSCORABLE',0)}|")
    lines += ["", "## 层与来源质量分开", "", "|片段|部位|观测|单层可用|潜在多层|来源ownership拒绝|覆盖不足或宽尺度拒绝|", "|---|---|---:|---:|---:|---:|---:|"]
    for name, segment in results.items():
        for part, c in segment["mixed_coverage"].items():
            lines.append(f"|{name}|{part}|{c['total']}|{c['eligible_single']}|{c['potential_layers']}|{c['rejection_only_source_ownership']}|{c['rejection_insufficient_coverage_or_broad_scale']}|")
    lines += ["", "逐条 switch 增删、实际 D1/BIRTH 提交、当前 whole/core 源测量、组首帧发布与 literal/pre-consensus 判定、独立状态自动动作差异见 JSON。",
        "", "潜在多层只说明当前实测分布有分离层，不能认证两条鱼或上下关系恒定；ownership/coverage 拒绝必须单列，不能把它说成发现混合鱼体。正确晚重接可增加 IDSW；减少 IDSW 也可能放弃有益恢复，必须同时看 IDF1、HOTA 和 AssA。此审计不按 GT 改规则或样本。"]
    with (HERE / "FEEDING_NEW_REVIEW.md").open("x", encoding="utf-8", newline="\n") as stream:
        stream.write("\n".join(lines) + "\n")
    print("FEEDING_NEW_REVIEW_COMPLETE", report["frames"])


if __name__ == "__main__":
    main()
