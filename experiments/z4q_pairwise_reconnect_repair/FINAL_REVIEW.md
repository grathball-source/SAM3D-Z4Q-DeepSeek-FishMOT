# Z4Q-PX：逐候选历史排斥，全段真实回放

2026-09-29。审查基点 `3e4101b54e99dbf7cb246cdb673cc6e2becdfe35`。**工程接入、四段回放、封存与独立评分通过；研究判定 `NO_EFFECT / 当前冻结假设未修复 FEEDING 退化`。** 本轮没有真实候选边满足严格的历史排斥合同，拒绝边为 **0**；Z4Q_PAIRWISE 在两来源全部 810 个帧处理上与原 Z4Q_FROZEN 的发布映射逐帧相同。不能把合成测试 PASS 写成提点，也不能用 GT 补造共现。

## 输入、边界和执行顺序

复用 B0-R 已封存的真实预测、深度、mask 和两段参考：原始帧 0–199、351–555 各自从空状态开始。`SOURCE_OLD` 两段都来自旧 `ML/labels_raw`；`SOURCE_BASELINE` 第二段来自原 `2.baseline` 分段重处理源，205/205 个预测 JSON 与旧源不同；第一段相同。因此下面只能**在每套来源内部**比较。两个来源不是两个独立数据集。所有 mask、残片与正负公开 ID 都保留，四组在同一来源的 FP/FN 与实例数相同。没有 SAM3 新推理、训练、模型 HTTP 或费用。

顺序为：七项本轮合成/真实切片检查 → 从起点运行真实 F159 切片 → [`FREEZE.json`](public/FREEZE.json) 封存规则、评分代码、输入和切片 SHA → 两来源×两段各一次独立 Bridge 状态回放 → 四个 [`SEAL.json`](public/SOURCE_OLD/feeding_000000_000199/SEAL.json) 全部落地 → scorer 验证 body/动作/发布/代码/输入哈希后首次读取编辑参考 → [`METRICS.json`](public/METRICS.json) 与事后物理审计 → [`ACCEPTANCE.json`](public/ACCEPTANCE.json)。旧 B0/ONEFIX 的代码、seal、预测、指标和 GT 未写入。旧 ONEFIX 指标只作为归档对照，不与新状态拼接。

附件描述的 `co_visibility_exclusion.py` 与其 13 项合成测试文件未随本次可读附件提供。这里以附件文字合同实现隔离副本；本轮实际通过的是 [`TEST_REPORT.json`](public/TEST_REPORT.json) 的七项检查，不能追认附件声称的 13 项为本轮执行。

## 新规则究竟做了什么

控制器副本在 [`source/`](source/) 中；冻结引擎及旧 seal 不变。`D1_DELAYED` 的五帧确认路径和 `BIRTH_REFINE` 的出生首帧路径，在 Hungarian 矩阵入边前调用同一 `edge_veto`。若有证据，只把 source→该 old-target 一格设为不可用，保留同一 source 的其他 target 和 dummy；仅清理 `pending[source]` 对该 target 的确认。没有年龄 ONEFIX、`first_eligible` 伪造或 GT 分支。

证据缓存属于 Bridge 的 engine，`preview` 深拷贝后只有 `commit_once` 能写回。过去共现要求两个已有质量与深度合格、没有邻接/组/重复/残片风险的真实 mask，在既有 7×7 邻域尺度下分离；至少五个连续过去帧支持，保留十二秒。native 连续性、来源批次 generation、别名/风险边界构成显式版本。目标必须回查当前 bank anchor 的可认证 native→public 来源片段；无法解析或没有成对证据都只记 `NO_EXCLUSION_EVIDENCE`，不推断同鱼，不做排斥关系传递闭包。每条被检查边和原因均在各段 `ACTION_LEDGER.jsonl`。

## 全部正式指标

IDF1/HOTA/AssA 为百分数。HOTA/AssA 是多 IoU 阈值平均；CLEAR IDSW、IDF1 按项目的 0.5 门槛。每段行与合并行都是官方同口径重算，不是百分数算术平均。`ARCHIVED_ONEFIX` 是历史封存结果。

| 来源与帧 | 分支 | IDF1 | HOTA | AssA | IDSW | FP | FN |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| OLD 0–199 | NATIVE | 92.8898 | 91.3625 | 88.0859 | 10 | 76 | 143 |
| OLD 0–199 | Z4Q_FROZEN | 92.1256 | 90.4837 | 86.3997 | 12 | 76 | 143 |
| OLD 0–199 | ARCHIVED_ONEFIX | 92.8898 | 91.3287 | 88.0206 | 10 | 76 | 143 |
| OLD 0–199 | Z4Q_PAIRWISE | 92.1256 | 90.4837 | 86.3997 | 12 | 76 | 143 |
| OLD 351–555 | NATIVE | 82.9273 | 78.5828 | 72.1827 | 22 | 148 | 201 |
| OLD 351–555 | Z4Q_FROZEN | 82.8910 | 78.1478 | 71.4299 | 24 | 148 | 201 |
| OLD 351–555 | ARCHIVED_ONEFIX | 82.9273 | 78.3245 | 71.7092 | 22 | 148 | 201 |
| OLD 351–555 | Z4Q_PAIRWISE | 82.8910 | 78.1478 | 71.4299 | 24 | 148 | 201 |
| **OLD 合并** | **NATIVE** | **87.8376** | **85.1875** | **81.6094** | **32** | **224** | **344** |
| OLD 合并 | Z4Q_FROZEN | 87.4426 | 84.5234 | 80.3627 | 36 | 224 | 344 |
| OLD 合并 | ARCHIVED_ONEFIX | 87.8376 | 85.0448 | 81.3397 | 32 | 224 | 344 |
| **OLD 合并** | **Z4Q_PAIRWISE** | **87.4426** | **84.5234** | **80.3627** | **36** | **224** | **344** |
| BASELINE 0–199 | NATIVE | 92.8898 | 91.3625 | 88.0859 | 10 | 76 | 143 |
| BASELINE 0–199 | Z4Q_FROZEN | 92.1256 | 90.4837 | 86.3997 | 12 | 76 | 143 |
| BASELINE 0–199 | ARCHIVED_ONEFIX | 92.8898 | 91.3287 | 88.0206 | 10 | 76 | 143 |
| BASELINE 0–199 | Z4Q_PAIRWISE | 92.1256 | 90.4837 | 86.3997 | 12 | 76 | 143 |
| BASELINE 351–555 | NATIVE | 79.7228 | 83.8347 | 74.4895 | 28 | 70 | 196 |
| BASELINE 351–555 | Z4Q_FROZEN | 80.9628 | 84.3781 | 75.5204 | 33 | 70 | 196 |
| BASELINE 351–555 | ARCHIVED_ONEFIX | 80.5616 | 84.4855 | 75.6502 | 29 | 70 | 196 |
| BASELINE 351–555 | Z4Q_PAIRWISE | 80.9628 | 84.3781 | 75.5204 | 33 | 70 | 196 |
| **BASELINE 合并** | **NATIVE** | **86.2344** | **87.6345** | **81.2212** | **38** | **146** | **339** |
| BASELINE 合并 | Z4Q_FROZEN | 86.4832 | 87.4471 | 80.9081 | 45 | 146 | 339 |
| BASELINE 合并 | ARCHIVED_ONEFIX | 86.6584 | 87.9328 | 81.7749 | 39 | 146 | 339 |
| **BASELINE 合并** | **Z4Q_PAIRWISE** | **86.4832** | **87.4471** | **80.9081** | **45** | **146** | **339** |

主比较 `PAIRWISE−同源NATIVE`：OLD 的 IDF1 **−0.3950**、HOTA **−0.6641**、AssA **−1.2466** 点、IDSW **+4**；BASELINE 的 IDF1 **+0.2489**、HOTA **−0.1874**、AssA **−0.3131** 点、IDSW **+7**。FP/FN 两源均差 0。`PAIRWISE−Z4Q_FROZEN` 全部指标恰为 0；不是独立增量。

## 边证据、实际动作与暴露案例

四段共检查 **1688** 条候选边，其中 `D1_DELAYED` 1416 条、`BIRTH_REFINE` 272 条。**拒绝 0 条，误拒 0 条，重新放开的原冻结边 0 条。**未命中原因：source 片段不合格/不连续 **1113**，target anchor 谱系未知 **573**，两端版本可见但不足五帧成对共现 **2**。这些是逐边检查次数，可能跨帧重复；不能当独立事件数。完整原因分来源/段见 [`ACCEPTANCE.json`](public/ACCEPTANCE.json)，逐边记录见四个动作日志。合成明确共现可以只拒一条边、留下 dummy；真实数据没有触发，不能把组件的合成能力当真实修复。

实际接受：OLD 为五次 `D1_DELAYED` 加一次 `BIRTH_REFINE`，事后实际锚/当前参考为同鱼 **0**、不同鱼 **4**、未知 **2**；BASELINE 八次均为 `D1_DELAYED`，同鱼 **3**、不同鱼 **4**、未知 **1**。详细来源、phase、确认数及 GT 边界在 [`EDGE_AUDIT.json`](public/EDGE_AUDIT.json)；GT 只用于所有预测封存后的分类。

| 暴露案例 | 新路径与实际结果 | 事后边界 |
| --- | --- | --- |
| OLD F159 `26→16` | D1 五次确认；过去 source/target 版本没有合格成对证据，照原 Z4Q 提交 | 当前 GT26、老锚 GT16，错误；非批次边界 |
| OLD F190 `30→8` | D1 保留 | 当前 GT7、老锚 GT8，错误 |
| OLD F522 `83→73` | source 版本有，target 锚谱系未知，保留 | 当前 GT6、老锚 GT24，错误 |
| BASELINE F372 `28→21`、F506 `41→21` | D1 均保留；年龄 ONEFIX 曾误拒 | 两者实际锚/当前同 GT21；F372 在首次改回旧号时仍有 IDSW |
| BASELINE F409 `30→16` | D1 保留，晚到的正确重接 | 锚/当前同 GT16，但已公开新号后的切换依然计入 IDSW |
| OLD F194 | PAIRWISE 跟原 B0 是 `38→7`；ONEFIX 全程则迁移为 `38→16` | 原锚/当前均不可评分；不拿旧预状态单测代替全程 |
| OLD F468 `80→21` | **`BIRTH_REFINE`、`phase=birth`、一次确认**；不能归因 D1 | 字面老锚 GT26、当前 GT21；未编造出生首帧的共现历史 |

F159 与 F372 的前/决策/后几何图为 [`F159`](public/cases/SOURCE_OLD_F159_native26.svg)、[`F372`](public/cases/SOURCE_BASELINE_F372_native28.svg)：只有来源预测框与首次发布 ID，事后 GT 是文字标注；没有 RGB、私有 mask 像素或 GT raster。F159 切片的决策前/后哈希和完整第一段最终哈希分开保存；决策后与 F199 终态确实不同。旧 `counterfactual.veto_preview` 是**整行 D1 资格过期**，并非单边 veto，旧报告的 `decision_post_state_sha256` 实为循环末尾 F199 状态。旧文件保持只读；新 [`diagnostic_safety.py`](diagnostic_safety.py) 的复制诊断使用 `try/finally` 恢复临时状态，异常测试见 [`DIAGNOSTIC_TEST_LOG.txt`](public/DIAGNOSTIC_TEST_LOG.txt)。新 PX 正式回放从未修改 `first_eligible`。

## 完整性、限制和下一步

[`ACCEPTANCE.json`](public/ACCEPTANCE.json)逐段验证 810 帧的原生 mask token、公开 ID 一对一、预测与旧冻结逐帧相同、来源/代码/发布/封存哈希及 F468 出生归因。四段源输入、私有预测、深度和编辑参考的真实路径/字节/SHA 在 [`RESTRICTED_INVENTORY.json`](public/RESTRICTED_INVENTORY.json)所引用的原始受限清单及本轮六份派生输入中；它们没有被复制到 Git。复现需要同一 D-MOT 环境、已保存的预标注/深度/人工参考和旧 B0-R 冻结输入；[`README.md`](README.md)列步骤。编辑参考 `checked=false` 且已曝光，结果不是盲测。此轮没有完整连续 SAM3 新会话，20 帧保存批次不证明上游零前视。

**结论分层：** 工程/来源/评分 `PASS`；严格逐边排斥在真实候选上 `NO_EFFECT`；同源 OLD 相对 NATIVE 仍退化，BASELINE 虽 IDF1 略升但 HOTA/AssA 下降且 IDSW 增加；当前冻结 PX 假设不能作为 FEEDING 修复。不能据此证明所有逐候选历史方法无效，也不能在这两段曝光数据上继续放松条件直到触发。

**唯一下一步：** 在新的、预先冻结的连续来源序列上采集能明确追踪 source/target 身份版本的独立共现证据，再检验逐边排斥相对同源 NATIVE 的物理正确性和整段指标。
