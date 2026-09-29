# B0-R：同源 SAM3 → Z4Q 回归与单次修复试验

**主判定：FAIL（未完成对同源原生 SAM3 的全面回归修复）。** 工程回放、封存、状态反事实和评分均通过。旧保存源上，一个确定的有害 D1 别名重接类别解释了额外切换；唯一固定新策略消除了该源的 4 次额外 IDSW，但 HOTA/AssA 仍低于 NATIVE。原 baseline 保存源上同一策略也拦下了两次事后可确认的正确物理重接，最终 IDSW 仍比 NATIVE 多 1。此策略是有代价的 `NEW_HYPOTHESIS`，不是通用 bugfix 或方法已通过。

## 冻结范围和输入

审查基点与执行时 `origin/main` 均为 `bfa141da4ffcb11aa47773b601379d0da88384c4`，开始工作树干净。只在已保存的原始预测上进行本地 CPU 关联回放；**新增模型 HTTP 0、费用 USD 0、SAM3 新推理 0、训练 0**。原始帧 0–199 与 351–555 共 405 帧，各段从空控制器状态启动，跨段身份空间互不相交。`NATIVE` 原样发布同一 mask 的 native ID；`Z4Q_FROZEN` 是未改的 Bridge/StableReturn；`Z4Q_ONEFIX` 是仅含本轮保护条件的同一状态机。关闭增强的 `PASSTHROUGH` 已逐帧等于 `NATIVE`，没有把 `enabled=False` 当作未验证的 SAM3 等价物。

| 来源 | 原始帧 0–199 | 原始帧 351–555 | 两源第二段逐帧 JSON 差异 |
| --- | --- | --- | ---: |
| `SOURCE_OLD` | `AnnotationFeeding_20260924/ML/labels_raw` | 同左 | — |
| `SOURCE_BASELINE` | 与旧源相同 | 原 `2.baseline` protocol 指向的 `ML/segments_v2/resegmented_000351_001906/labels_raw` | 205/205 |

每帧原始/局部帧号、prediction JSON、native 数、原 RGB 哈希、配准深度路径/哈希、保存批次及来源目录见 [PredictionSourceManifest](public/PREDICTION_SOURCE_MANIFEST.json)；原始 RGB/缩放图、标签和全部受限路径、大小与 SHA-256 见 [受限目录](public/RESTRICTED_INVENTORY.json)。原保存 SAM3 前端按 20 帧分批，5 帧重叠，发布首个覆盖批次；F159 的所选批次覆盖 F150–169。这证明本轮是在**保存预测上的因果关联回放**，不能证明上游从原 RGB 到保存预测完全零前视，也不能称同步实时部署。人工修订参考的 `checked=false` 未独立终验；GT 只在四套输入/预测封存及 F159 双分支反事实封存后用于评分和诊断。

## 完整 TrackEval 结果

IDF1、HOTA、AssA 单位为百分数。所有原始 mask、残片和所有正负 ID 均参加 IoU 0.5 的统一评分；FP/FN 与实例数不随分支改变。合并行重新在独立段 ID 命名空间评分，不是两段百分数平均。原旧源的 NATIVE 与 B0 精确复现此前独立审计；原 baseline 来源的 NATIVE 精确复现原 baseline protocol 审计。机器可读的全部精度和差值见 [ONEFIX_METRICS.json](public/ONEFIX_METRICS.json)。

| 来源 / 原始帧 | 分支 | IDF1 | HOTA | AssA | IDSW | FP | FN | GT/预测实例 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| OLD 0–199 | NATIVE | 92.8898 | 91.3625 | 88.0859 | 10 | 76 | 143 | 5399/5332 |
| OLD 0–199 | Z4Q_FROZEN | 92.1256 | 90.4837 | 86.3997 | 12 | 76 | 143 | 5399/5332 |
| OLD 0–199 | Z4Q_ONEFIX | 92.8898 | 91.3287 | 88.0206 | 10 | 76 | 143 | 5399/5332 |
| OLD 351–555 | NATIVE | 82.9273 | 78.5828 | 72.1827 | 22 | 148 | 201 | 5547/5494 |
| OLD 351–555 | Z4Q_FROZEN | 82.8910 | 78.1478 | 71.4299 | 24 | 148 | 201 | 5547/5494 |
| OLD 351–555 | Z4Q_ONEFIX | 82.9273 | 78.3245 | 71.7092 | 22 | 148 | 201 | 5547/5494 |
| **OLD 合并** | **NATIVE** | **87.8376** | **85.1875** | **81.6094** | **32** | **224** | **344** | **10946/10826** |
| **OLD 合并** | **Z4Q_FROZEN** | **87.4426** | **84.5234** | **80.3627** | **36** | **224** | **344** | **10946/10826** |
| **OLD 合并** | **Z4Q_ONEFIX** | **87.8376** | **85.0448** | **81.3397** | **32** | **224** | **344** | **10946/10826** |
| BASELINE 0–199 | NATIVE | 92.8898 | 91.3625 | 88.0859 | 10 | 76 | 143 | 5399/5332 |
| BASELINE 0–199 | Z4Q_FROZEN | 92.1256 | 90.4837 | 86.3997 | 12 | 76 | 143 | 5399/5332 |
| BASELINE 0–199 | Z4Q_ONEFIX | 92.8898 | 91.3287 | 88.0206 | 10 | 76 | 143 | 5399/5332 |
| BASELINE 351–555 | NATIVE | 79.7228 | 83.8347 | 74.4895 | 28 | 70 | 196 | 5547/5421 |
| BASELINE 351–555 | Z4Q_FROZEN | 80.9628 | 84.3781 | 75.5204 | 33 | 70 | 196 | 5547/5421 |
| BASELINE 351–555 | Z4Q_ONEFIX | 80.5616 | 84.4855 | 75.6502 | 29 | 70 | 196 | 5547/5421 |
| **BASELINE 合并** | **NATIVE** | **86.2344** | **87.6345** | **81.2212** | **38** | **146** | **339** | **10946/10753** |
| **BASELINE 合并** | **Z4Q_FROZEN** | **86.4832** | **87.4471** | **80.9081** | **45** | **146** | **339** | **10946/10753** |
| **BASELINE 合并** | **Z4Q_ONEFIX** | **86.6584** | **87.9328** | **81.7749** | **39** | **146** | **339** | **10946/10753** |

主比较：`SOURCE_OLD` ONEFIX−同源 NATIVE 为 IDF1 **0.0000**、HOTA **−0.1427**、AssA **−0.2697**、IDSW **0**；ONEFIX−同源 B0 为 **+0.3950/+0.5214/+0.9769**、IDSW **−4**。`SOURCE_BASELINE` ONEFIX−同源 NATIVE 为 **+0.4240/+0.2983/+0.5538**、IDSW **+1**；ONEFIX−同源 B0 为 **+0.1751/+0.4857/+0.8669**、IDSW **−6**。换来源后的正负变化不能并作一次算法因果收益。

## 净切换分解与真实动作

[完整 B0 trace](public/SOURCE_OLD/feeding_000000_000199/B0_ACTION_LEDGER.jsonl)在读 GT 前已逐帧封存，包含每个 mask 的 native→public、上一帧公开值、producer batch、质量/深度/几何、全部 edge/birth/返回检查、alias/bank/pending/retired/Bridge 状态差异及首次发布。第二段和第二来源有同样文件；[分解](public/BASELINE_SWITCH_DECOMPOSITION.json)、[事后逐切换与动作引用](public/POSTSEAL_CAUSE_REVIEW.json)提供可追溯索引。

同一 CLEAR 实现按 `(段, 原帧, GT ID)` 计切换发生位置：OLD 的 NATIVE/B0 为 32/36，**共同 32、新增 4、消除 0**；BASELINE 为 38/45，**共同 38、新增 7、消除 0**。如果连 `from/to public ID` 也纳入精确事件键，则 OLD 是共同 30、新增 6、消除 2；BASELINE 是共同 37、新增 8、消除 1。同帧同鱼的切换方向不同会同时进入“新增/消除”，所以净多 4 不等于未经分解的四个独立错误。ONEFIX 的发生位置相对 NATIVE：OLD 无独有切换、无消除；BASELINE 仅 F409 GT16 多一次，亦无消除。

两套 B0 trace 中实际 `events` 只有 reconnect 候选：OLD 52 条、接受 6；BASELINE 67 条、接受 8。返回隔离、出生继承和冲突回滚在这些帧**没有提交事件**，不把它们写成当前退化原因。每个新增/消除事件的当前 trace、alias 写入、bank/previous/epoch 状态写入、最近相关动作及 UNKNOWN 绑定边界均留在日志；仅靠“最近相关”不宣称严格反事实因果。首个确认的有害动作 [F159](public/FIRST_HARMFUL_ACTION.json)：native 26 已连续 135 帧，D1 直到 F137 才允许其竞争老目标，F159 五次确认将其别名设为 16。实际候选 GT26、老锚点 GT16，且非批次边界。F190 native30→8（候选 GT7、锚点 GT8）同属此类；OLD F522 候选 GT6、老锚点 GT24，也明确错接。OLD F374 的老锚点不可评分；F194 候选及锚点均不可评分；F468 的字面老锚点 GT26 与候选 GT21 不同，不能把其公开 ID 偶然有利称作物理正确恢复。

OLD 没有能以“同一 GT 的老锚点→当前候选”或“消除 NATIVE 切换”证明的有益 B0 动作，明确记录为 [无已证实有益动作](public/FIRST_BENEFICIAL_ACTION.json)。另一来源的 F372 是最早可证实**物理同 GT**的 B0 重接，但它在该帧仍产生 CLEAR 切换，不能直接称为指标有益。F506 同样物理同 GT。ONEFIX 拦截两者，暴露保护策略的误拒风险。

## 单动作反事实和修复边界

F159 的 ALLOW/VETO 从同一实际 Bridge 决策前状态深拷贝，两个状态都真实运行到 F199；[双 seal](public/counterfactual_F159/PAIR_SEALED.json)先于 GT，之后 [独立评分](public/counterfactual_F159/POSTSEAL_SCORE.json)。单帧 VETO 与旧 B0 仅在 F159 的公开 ID 不同，第一段 IDF1/HOTA/AssA 分别 **92.1256→92.1443、90.4837→90.4992、86.3997→86.4292**，IDSW 仍 12。原规则 F160 再次接受错接，因此不能以这点局部收益冒充完整修复。固定策略、前置测试和代价详见 [REPAIR_DIFF.md](REPAIR_DIFF.md)。ONEFIX 各段从空状态重跑并首次发布自己的预测，绝非重写 B0 结果：相对 B0 公开映射不同的帧数 OLD 两段为 41/182，BASELINE 两段为 41/184。

## 旧模型结论、时延和局限

旧源 B-VLM 的归档合并指标仍为 **88.6092/85.3061/81.8530、IDSW35**，相对旧 B0 有小幅数值信号，但仍多于 NATIVE 的 32 次切换。[旧事件事实定位](public/ARCHIVED_VLM_FACTS.json)：原 F419 与 F519 的 H2 提交分别保留 `{21:21,2:2}`、`{50:50,24:24}` 原 native 对应；反驳当时 HOLD 的 H1 错配。它们不是新 ONEFIX 状态的模型答案，也不能无证据称作修复 SAM3 原生错误。本轮未复用旧回答、未产生新 VLM 成绩。

[首次发布与恢复时延](public/LATENCY_SUMMARY.json)按本地 CPU 回放时钟测量；B0/ONEFIX 的各段中位数约为 16/16 ms（第一段）及 31/31 ms（第二段）。每次接受重接也记录 birth→commit 帧数与确认跨度。这是文件回放处理延迟，**不是端到端实时 RGB→SAM3→控制器部署延迟**。事件几何及原始帧→native→实际公开 ID→事后 GT 的分层图见 [F159](public/cases/SOURCE_OLD_159_native26.svg)、[F190](public/cases/SOURCE_OLD_190_native30.svg)、[F372](public/cases/SOURCE_BASELINE_372_native28.svg)、[F409](public/cases/SOURCE_BASELINE_409_native30.svg)；图中没有 RGB、预测 mask 像素或 GT raster，未做像素目视复核。

验收 [TEST_REPORT.json](public/TEST_REPORT.json)：四个来源×片段 replay 的 810 行 mask/ID 顺序和一对一发布通过，NATIVE/PASSTHROUGH 完全相同，所有输入/代码/预测/首次发布 seal 哈希校验通过。GT 是已曝光、人工修订且 `checked=false` 的参考；205/205 第二段源差异说明只能**源内**因果比较。本轮没有新原生连续 SAM3 会话，也没有新数据集泛化验证。

**唯一下一步：** 在预先冻结的独立连续 SAM3 输入上检验“保护成熟 native”与“允许正确重接”的冲突，并继续报告同源 NATIVE 对照及物理/公开指标两层结果。
