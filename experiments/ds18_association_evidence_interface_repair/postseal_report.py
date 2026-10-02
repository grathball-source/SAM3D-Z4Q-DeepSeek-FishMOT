"""Frozen post-seal report plan; consumes scalar scores, never predictions' GT inputs."""
from __future__ import annotations

from collections import Counter
from common import ARMS, HERE, RUN, SEGMENTS, artifact, read, rows, sha, write_new


FIELDS = ("IDF1", "HOTA", "AssA", "IDSW", "FP", "FN")


def switching(switches, arm, base):
    a = {(x["gt_id"], x["frame"]): x for x in switches[arm]}
    b = {(x["gt_id"], x["frame"]): x for x in switches[base]}
    assert len(a) == len(switches[arm]) and len(b) == len(switches[base])
    key = lambda item: (item[1], item[0])
    return dict(arm=arm, base=base, added=len(a.keys() - b.keys()), removed=len(b.keys() - a.keys()),
        common=len(a.keys() & b.keys()), net=len(a) - len(b),
        added_switches=[a[k] for k in sorted(a.keys() - b.keys(), key=key)],
        removed_switches=[b[k] for k in sorted(b.keys() - a.keys(), key=key)],
        common_transition_changed=[dict(gt_id=k[0], global_frame=k[1], arm_switch=a[k], base_switch=b[k])
            for k in sorted(a.keys() & b.keys(), key=key)
            if (a[k]["from_public_id"], a[k]["to_public_id"]) !=
               (b[k]["from_public_id"], b[k]["to_public_id"])])


def main():
    # This gate precedes every score/GT-derived scalar read.
    seal_path, metric_path = RUN / "ALL_PREDICTIONS_SEALED.json", RUN / "METRICS.json"
    assert seal_path.exists() and metric_path.exists(), "All predictions must be sealed and scoring complete"
    seal = read(seal_path)
    assert seal["status"] == "ALL_PREDICTIONS_AND_ACCESS_SEALED"
    assert seal["frames"] == sum(stop - start + 1 for start, stop in SEGMENTS.values())
    metric = read(metric_path)
    assert metric["status"] == "SCORED_AFTER_ALL_SIX_ARMS_EIGHT_SEALS"
    assert metric["all_seal"] == artifact(seal_path)
    assert list(metric["feeding_pooled"]["metrics"]) == list(ARMS)
    sources = [artifact(seal_path), artifact(metric_path), artifact(RUN / "SCORE_PROVENANCE.json")]
    result = {}
    for name in SEGMENTS:
        public = RUN / name / "public"
        prediction_seal = read(public / "PREDICTIONS_SEALED.json")
        for filename, expected in prediction_seal["artifacts_sha256"].items():
            assert sha(public / filename) == expected, (name, filename)
        for filename in ("PREDICTIONS_SEALED.json", "METRICS.json", "SWITCHES.json", "AUTOMATIC_RECONNECT_AUDIT.json",
                         "EVENT_AUDIT.json", "ORDER_EVIDENCE.jsonl.gz", "MIXED_DEPTH.jsonl.gz", "TRANSACTIONS.jsonl.gz"):
            sources.append(artifact(public / filename))
        metrics = read(public / "METRICS.json")["metrics"]
        switches = read(public / "SWITCHES.json")
        auto = read(public / "AUTOMATIC_RECONNECT_AUDIT.json")
        events = read(public / "EVENT_AUDIT.json")
        comparisons = [switching(switches, arm, base) for base in ("SAM3_NATIVE", "ACTIVITY_ORDER") for arm in ARMS]
        auto_summary = {}
        for arm in ARMS[1:]:
            actions = auto["arms"].get(arm, [])
            auto_summary[arm] = dict(accepted=len(actions), physical_counts=dict(Counter(x["physical"] for x in actions)),
                actual_reference_physical_counts=dict(Counter(x['actual_reference_physical'] for x in actions)),
                prior_public_reference_counts=dict(Counter(x['prior_public_reference_status'] for x in actions)),
                incidental_public_origin_returns=sum(x['incidental_public_origin_return'] for x in actions),
                origin_counts=dict(Counter(x["origin_rule"] for x in actions)),
                applied_at_first_publication=sum(x["applied_at_first_publication"] for x in actions),
                durable_alias_after_commit=sum(x["durable_alias_after_commit"] for x in actions),
                actual_durable_commits=sum(x["durable_automatic_commit"] for x in actions), actions=actions)
        transaction_counts = {arm: dict(controller_event_kinds=Counter(), matrix_edge_rejections=Counter(),
                                       activity_reference_frames=0, activity_reference_status=Counter()) for arm in ARMS[1:]}
        for row in rows(public / "TRANSACTIONS.jsonl.gz"):
            counts = transaction_counts[row["arm"]]
            trace = row["controller_trace"]
            counts["controller_event_kinds"].update(x.get("kind", "UNKNOWN") for x in trace.get("events", []))
            counts["matrix_edge_rejections"].update(x.get("rejection") or "NONE" for x in trace.get("edges", []))
            separate = trace.get("activity_reference_separation")
            if separate:
                counts["activity_reference_frames"] += 1
                statuses = separate.get("reference_status", {})
                counts["activity_reference_status"].update(str(v) for v in statuses.values())
        mixed = {part: dict(status=Counter(), reason=Counter(), layer_counts=Counter(), eligible_single=0,
                           mixture_flag=0, independent_mixture_flag=0, inclusive_mixture_flag=0,
                           quality_usable=0, source_ownership_exclusive=0) for part in ("whole", "birth_core", "core")}
        observed = 0
        frame_count = 0
        for row in rows(public / "MIXED_DEPTH.jsonl.gz"):
            frame_count += 1
            for obj in row["objects"].values():
                observed += 1
                for part in ("whole", "birth_core", "core"):
                    data, count = obj[part], mixed[part]
                    count["status"][data["status"]] += 1
                    count["reason"][data.get("reason", "UNKNOWN")] += 1
                    count["layer_counts"][str(len(data.get("layers", [])))] += 1
                    for field in ("eligible_single", "mixture_flag", "independent_mixture_flag", "inclusive_mixture_flag",
                                  "quality_usable", "source_ownership_exclusive"):
                        count[field] += bool(data.get(field))
        assert frame_count == prediction_seal["frames"]
        for count in mixed.values():
            count["eligible_single_fraction"] = count["eligible_single"] / observed if observed else None
            count["mixture_flag_fraction"] = count["mixture_flag"] / observed if observed else None
        q_by_arm = {arm: dict(choices=Counter(), order_status=Counter(), order_reason=Counter(), eligible=0,
                             applied=0, restore_status=Counter(), rows=[]) for arm in ARMS[2:]}
        for row in rows(public / "ORDER_EVIDENCE.jsonl.gz"):
            arm = row["arm"]
            detail = row["detail"]
            evidence = detail.get("order_evidence", {})
            count = q_by_arm[arm]
            count["choices"][row["selected_choice"]] += 1
            count["order_status"][evidence.get("status", "UNKNOWN")] += 1
            count["order_reason"][evidence.get("reason", "UNKNOWN")] += 1
            count["eligible"] += bool(evidence.get("eligible"))
            count["applied"] += bool(evidence.get("applied"))
            count["restore_status"][row["restore"]["status"]] += 1
            count["rows"].append(dict(event=row["event"], frame=row["frame"], global_frame=row["global_frame"],
                choice=row["selected_choice"], restore=row["restore"], published_mapping=row["published_mapping"],
                order_evidence=evidence, prediction_row_sha256=row["prediction_row_sha256"]))
        group_summary = {}
        for arm in ARMS[2:]:
            data = events["arms"][arm]
            groups = data["group_events"]
            group_summary[arm] = dict(events=len(groups), event_status=dict(Counter(x["status"] for x in groups)),
                restore_status=dict(Counter(x.get("restore_status") or "NO_RESTORE" for x in groups)),
                literal_physical=dict(Counter(x["physical"] for x in groups)),
                first_public_pre_consensus=dict(Counter(x.get("first_public_pre_consensus_verdict", "NOT_AVAILABLE") for x in groups)),
                committed_pre_consensus=dict(Counter(x.get("committed_pre_consensus_verdict", "NOT_AVAILABLE") for x in groups)),
                events_full=groups)
        result[name] = dict(frames=prediction_seal["frames"], metrics=metrics,
            metric_deltas={base: {arm: {f: metrics[arm][f] - metrics[base][f] for f in FIELDS} for arm in ARMS}
                           for base in ("SAM3_NATIVE", "Z4Q_FROZEN", "DS16_ORDER", "ACTIVITY_ORDER", "MIXED_OFF")},
            switch_comparisons=comparisons, automatic_actions=auto_summary, transactions=transaction_counts,
            mixed_observation_count=observed, mixed_depth=mixed, q_details=q_by_arm, group_restores=group_summary)
    pooled = metric["feeding_pooled"]["metrics"]
    report = dict(status="POSTSEAL_SCORED_REPORT_COMPLETE", frames=metric["frames"], arms=list(ARMS),
        segments=result, feeding_pooled=metric["feeding_pooled"],
        feeding_pooled_deltas={base: {arm: {f: pooled[arm][f] - pooled[base][f] for f in FIELDS} for arm in ARMS}
                              for base in ("SAM3_NATIVE", "ACTIVITY_ORDER", "MIXED_OFF")},
        source_bindings=sources, generator=artifact(__file__), model_http=0, cost_usd=0,
        limitations=["Layer and mixture flags are raw measurement evidence, not GT fish-count or true depth-order certification",
            "Ordinal probabilities are uncalibrated; no physical accuracy inferred from wide scales",
            "Reference literal endpoint and pre-history consensus verdicts remain separate",
            "L3/LW labels are weak, unreviewed prediction-derived preannotations",
            "Added/removed switch counts are diagnostic; causal rule effectiveness requires these actual independent-state full replays"])
    write_new(RUN / "POSTSEAL_REPORT.json", report)
    lines = ["# DS18 全段封存后报告", "", "全部六臂、八段、20098 帧预测封存后独立评分。新增模型 HTTP=0、费用=0。", "",
             "## 完整指标", "", "|片段|分支|IDF1|HOTA|AssA|IDSW|FP|FN|", "|---|---|---:|---:|---:|---:|---:|---:|"]
    for name, segment in result.items():
        for arm, m in segment["metrics"].items():
            lines.append(f"|{name}|{arm}|{m['IDF1']:.6f}|{m['HOTA']:.6f}|{m['AssA']:.6f}|{m['IDSW']}|{m['FP']}|{m['FN']}|")
    lines += ["", "## 相对原生及相同活动修复底座的切换", "", "|片段|分支|参照|新增|消除|净值|", "|---|---|---|---:|---:|---:|"]
    for name, segment in result.items():
        for x in segment["switch_comparisons"]:
            if x["arm"] != x["base"]:
                lines.append(f"|{name}|{x['arm']}|{x['base']}|{x['added']}|{x['removed']}|{x['net']}|")
    lines += ["", "## 实际深度测量与恢复", "", "|片段|观测数|whole 单层可用|whole 混合提示|core 单层可用|core 混合提示|", "|---|---:|---:|---:|---:|---:|"]
    for name, s in result.items():
        w, c = s["mixed_depth"]["whole"], s["mixed_depth"]["core"]
        lines.append(f"|{name}|{s['mixed_observation_count']}|{w['eligible_single']}|{w['mixture_flag']}|{c['eligible_single']}|{c['mixture_flag']}|")
    lines += ["", "完整自动 D1/BIRTH accepted/首次发布/durable 数量、实际物理判定、矩阵拒绝原因、相对两底座的逐切换列表、q 次序有效性/选择、共同状态与组恢复在 JSON 分列。",
              "", "混合提示不等于 GT 认证的两鱼；标量深度及宽尺度不代表真实身份或深度准确率。literal endpoint 不可评分与 pre-history consensus 错误保持独立。L3/LW 为弱预标注，不能作为独立强泛化结论。", "",
              "此报告按冻结脚本直接生成，失败、零提交、fallback 和无事件均保留。未按指标修改输入、规则、门槛或选择样本。"]
    with (RUN / "POSTSEAL_REPORT.md").open("x", encoding="utf-8", newline="\n") as stream:
        stream.write("\n".join(lines) + "\n")
    print("POSTSEAL_REPORT_COMPLETE", metric["frames"])


if __name__ == "__main__":
    main()
