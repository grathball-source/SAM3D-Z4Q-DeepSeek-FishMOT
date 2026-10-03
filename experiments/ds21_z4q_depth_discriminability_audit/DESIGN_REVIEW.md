# DS21 静态设计审查

本文件只审查既有封存报告、真实源码和本轮 `PLAN.md`。未执行新预测、状态回放或评分，未读 GT raster、未调用模型或服务器。下面的旧结果不是 DS21 新运行结果；新的统计以冻结审计实际输出为准。

## 范围与问题

本轮仅审计原 Z4Q 的深度判别性，复用 DS20 八个同源片段：Feeding 四段、FishSA 开发/曝光验证、L3、LW。原预测、状态事务、来源、原始深度及旧评分均只读。没有新跟踪性能，也不自动延续 DS20 的完整共同历史修复试验。

完整保留原 `D1_DELAYED` 候选边、`BIRTH_REFINE` 检查、accepted 动作、拒绝和未确认记录。不能只检查事后错误动作；正确、错误、不可评分均进入交叉表。没有精确旧 anchor 的边保留 UNBOUND/UNKNOWN，不能按 public 整数补造历史来源。原记录未保存的 generation、身份版本、dummy 成本或替代候选历史，也不能凭假设补齐。

## 原 Z4Q 已经使用深度

真实源码 `online/closed_loop_2888/z4q_source/source/sam3_depth_failure_repair_20260917/repair_controller_r3.py` 的 D1 比较最后 clean whole 中位数；15点深度历史用于 MAD/tolerance，另有运动、伙伴竞争和自然五次确认。原 `smooth=False`，不能描述成实际使用 EMA 或深度均值速度外推。

`controller_z2.py` 的 Birth 比较 fixed core，使用 whole 反证、survivor 自身/交叉 core 联合比较和全局 assignment margin；`controller_z3.py`/`controller_z4.py` 还使用真实 native 连续性与 recent core。把这些已有标量重新计算、改成符号或重新整理成表，不是新增测量信息。

DS18 固定的 independent source、共享采样、层分布和质量事实，可以作为额外测量特征分析。但质量特征通过，只能认证实际采样人口和可靠性条件，不能认证物理鱼身份。

## 审计应回答的三个不同问题

### 1. 额外质量筛选会筛掉什么

按已经冻结的 DS18 资格，分别报告 current-only、historical-anchor-only、both。需要逐 ROI 绑定原比较标量：D1 whole、Birth fixed core、S0 adaptive core 不得互相借合格证书。

每张表同时列出原正确、错误、不可评分动作；缺测和绑定失败另列。共享源、混层、背景可能混入或大 MAD，是测量风险。它们不证明原候选是一条错误鱼，也不允许把 UNKNOWN 当成安全拒绝。

本表只是“若采用测量筛选，会影响哪些旧动作”的回顾性假设检查。它不是实际 edge-veto，不是局部状态反事实，也不能据此算新的 IDSW 或 IDF1。

### 2. 额外信息是否真的排斥了错误候选

候选排歧必须在同一次真实候选上下文内讨论：原候选及 dummy 保持，测量选择和质量规则对全部候选一致。只有精确 current 与 old-anchor 测量绑定成立，才能报告数值冲突/兼容；原替代历史缺失时，应明确无法证明完整排歧。

“错误边具有反证”与“正确替代边可被选中”分开。如果只是原错误边测量不可靠，而没有合法竞争者支持，最多说明一个质量限制或可能的否决机会，不能称已经具备身份恢复能力。原候选外的事后正确鱼不得补进矩阵。

不从事后标签选择深度峰、ROI、参考片段或门槛。描述原残差、风险、成本、margin、age 和确认数的分布，不拟合新的诊断阈值。即使一个额外特征在这些曝光动作中分离了正确/错误，也只是后续最小试验依据，不能直接宣称提点。

### 3. 相对顺序有没有被真实测到

应区分“ROI 内存在多个深度层”“每层属于哪条鱼”“风险期间相对顺序持续”三件事。分峰、两个 native 同时出现或 pre/post 中位数差，均不能同时证明后两项。

当前 `experiments/ds16_relative_depth_order/order_association.py` 使用 pre 与首分离 core 中位数的成对概率，没有使用 GROUP 的层分布；其顺序保持是显式假设和未标定代理。弱概率、宽尺度、缺少共时历史和混合 mask 必须保留，不能写成物理上下关系真值。

本轮可以报告原 Birth core/whole/survivor 支持的实际一致性，以及 DS18 当前/旧参考的层和来源事实。不把这些事实扩展成未测得的遮挡拓扑或层到鱼的身份绑定。

## 失败来源与评分语义

应区分：正确目标未入候选、候选存在但错误继承、物理正确但公开后晚改、旧 bank/公共身份起源已经不一致，以及不可评分。原封存资料不足以完整归因时保持 UNKNOWN，不建立新的事件扫描或重跑状态来补齐。

旧动作的 literal bank 关系与严格 bank＋public-origin 关系分列。单次查询匹配、回到旧公共整数、少一次切换或保留了 fallback，都不能单独证明完整物理恢复正确。

GT 派生旧物理标签只在新 FEATURES 封存后加入；这是一条可审计的运行顺序，不使已曝光数据变成盲测。L3/LW 是未审查预测派生弱参考，应与较强参考单位分列。新性能字段保持 null/NOT_RUN；旧 SAM3、原 Z4Q 和 DS20 指标明确标为 historical。

## 可视化与结束边界

按 PLAN 的固定 census 为每个单位/物理等级选择最早实际动作，无该等级则记录缺失。显示实际旧 anchor、commit 前、commit 和有界 commit 后帧，保留所有局部 mask 和实际公开 ID。未来列只做封存后诊断，不进入 measurement 特征；图像不能补充未知物理身份。

先完成全动作测量封存和标签交叉表，再讨论一个后续行动。工程绑定通过、可用率增加或错误边被过滤，均不预报整段提点；不扩大为新资格平台、阈值搜索、完整多臂回放或模型调用。若证据仍不足，直接报告不足并交付。

## 静态来源

- `experiments/ds20_pending_confirmation_isolation/FINAL_REVIEW.md`、`FAILURE_EVIDENCE_REVIEW.md`、`COMPLETION_NOTES.md`。
- `experiments/ds18_association_evidence_interface_repair/PLAN.md`、`FINAL_REVIEW.md`、`CAUSAL_SYNTHESIS.md`。
- `experiments/ds15_z4q_depth_strategy_repair/audits/POSTSEAL_STRATEGY_REVIEW.md`。
- 原 Z4Q 的 `repair_controller_r3.py`、`controller_z2.py`、`controller_z4.py`，以及 `experiments/ds16_relative_depth_order/order_association.py`。
- 本轮 `README.md` 与 `PLAN.md`。

本静态审查未运行 DS21 的 audit/checks。后续实际字段与 semantic 检查审查应以最终冻结源码和真实执行输出为依据，不能把本文件当作运行 PASS。
