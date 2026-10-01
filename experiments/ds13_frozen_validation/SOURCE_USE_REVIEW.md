# 来源使用记录审查

本轮只读审查，未修改旧数据或解析GT/原始像素。旧公开产物只另做字节哈希。下列引用用于区分真实开发、固定评价和源生成。

| 来源 | 核查证据 | 分类 |
|---|---|---|
| Feeding405帧 | `experiments/feeding_first_two_s0p/FINAL_REVIEW.md`第14/54行，`b0_same_source_regression_repair/FINAL_REVIEW.md`第3/7行 | 真实迁移guard/ONEFIX新规则开发 |
| Feeding405帧 | `z4q_anchor_evidence_retention/FINAL_REVIEW.md`第7行，`ne1_native_first_event_association/FINAL_REVIEW.md`第7行 | 新anchor合同/native-first架构开发 |
| Feeding1066帧 | `ds2_depth_transfer_validation/cohort.py`第54行、后续DS3–DS12计划/结果 | 原DS2新验证，此后已用于测量/关联开发 |
| Feeding1471帧 | `ds6_multifragment_depth_tracking/common.py`四段，DS12正式FREEZE/RESULTS | 现有全部四段已曝光开发 |
| Feeding1907帧 | 本机`tools/prelabel_feeding_20260924/README.md`，恢复README | 一次源生成/恢复本身不自动等于关联调参 |
| L3/LW | 本机`tools/z4q_new_bags_20260923/README.md`第10行，`run.py`第27/99–100行 | 冻结旧规则全段评价；没有找到反馈修改DS规则的记录 |
| L3/LW | `tools/z4q_new_bags_20260923/audit_switches.py`第19–24行、`tools/annotation/render_new_bags_events.py`第14–22行 | 事后选案例归因曝光；不自动等于阈值调参 |
| L3/LW前端 | `tools/prelabel_new_bags_20260919/README.md` | 手工镜面ROI、OOM后批长90→60；raw保留完整候选 |

不能按相同数字帧号将8400/2888旧FishSA实验混入Feeding或L3/LW。Feeding旧生产支持范围来自DS2 cohort，外部完整调参记录UNKNOWN。L3/LW不被标成已调参或sealed test；它们的问题是本轮三分支的v2输入未齐、用途与弱参考边界尚未明确。

runner依赖审查确认：科学kernel可原样复用，但新数据入口不能假装已有DS10 cache或v2；当前接触与历史群组ROI必须分别保持冻结。数据迁移适配还未实现/验收，不提前写工程PASS。
