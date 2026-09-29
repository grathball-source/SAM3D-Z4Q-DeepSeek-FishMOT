# PX-A：冻结 anchor 来源保留与原始深度同源回放

2026-09-29；固定审查基点 `85f71d854f8d9b0bcc6d7bf1d200d1a01dd8de08`。**工程合同通过；真实候选排斥与指标 `NO_EFFECT / STOP`。** 本轮确实修好了旧 PX 的历史 anchor 查询丢失，但没有一条被检查的 source→target 边具备同版本的五帧合格共现，因此真实 veto **0**、发布变化 **0**。停止这个冻结 PX-A 规则，不根据事后 GT 放宽资格或增加第二条规则。这不否定完整历史关联的一般研究假设。

## 输入、顺序与隔离

先读取 `origin/main`，其 SHA 与指定基点相同。附件 `targeted_results.json`（3378 字节，SHA-256 `32c5b3a4d554d99fca9bf7d02b655ac23c65b8cb65bb9a52dd366cea207ce1d8`）只给出简化 Engine 上的反例，没有被当作真实效果。PX-A 在 [独立引擎副本](source/co_visibility_exclusion.py) 中实现并通过 13 项直接相关检查，其中包含实际 `PairwiseStableReturn` 的目标失效与保持原 anchor、D1 的真实 F159 一条矩阵边、BirthRefine 的真实 F468 一条矩阵边、preview 隔离。随后从段首到 F159 跑真实无 GT 切片，封存 [代码/输入/评分](public/FREEZE.json)，再运行两套来源各两个完整段，四个 [预测 seal](public/RUN_SUMMARY.json) 完成后才独立评分。每段空状态启动，四个处理序列共 810 帧；实际唯一原帧是共享的 405 帧。模型 HTTP、费用、新 SAM3 推理、训练均为 **0**。

输入是 B0-R 原 manifest 的保存 SAM3 预测、原始深度 profile 和 mask；`SOURCE_OLD` 与 `SOURCE_BASELINE` 第一段相同，第二段保存预测不同。只做各来源内部比较。v3 的含标注/未来帧修复深度、旧模型答案、年龄 ONEFIX 都没有进入本轮。旧 PX、v3、B0-R、ONEFIX 的代码、预测和 seal 保持只读。保存的分批 SAM3 预测不证明前端是在线零前瞻。

## 修复范围与真实因果链

旧 `finish` 在目标本帧质量/交互不合格时，将当前 `runs[target]` 与 `public_lineage[target]` 同时删除；若 bank 仍引用先前的 anchor，后续查询错误地变成 `target_anchor_lineage_unknown`。新状态分为：`live_segments`（当前 source 的连续、合格、同 generation 版本）、`anchor_registry`（真实登记过的 bank anchor 的不可变来源版本、时间与 generation）、`pair_witnesses`（真实分离 mask 的连续共现帧）。registry 键包含本次来源/段 namespace、public、native、anchor frame、mask token；检查须与 bank 当前 anchor 精确一致。历史记录因当前目标失效或消失而保留，只在实际换锚/改绑或超过原 12 秒时失效。source 的质量、交互、缺帧和 generation 边界依然由 `_continuing` 拦截，出生无历史仍是 `NO_EXCLUSION_EVIDENCE`。五帧、12 秒、面积、深度、邻接、7×7 分离和 D1/BirthRefine 的单边矩阵 hook 未放宽；dummy、其他候选不变。

实际 F159：target public 16 的旧 anchor F15 可被 PX-A 查询到，然而 native 26 的 source 连续版本为 `UNKNOWN`，故 **无 veto**；实际发布仍为 26→16。更早的 F157 30→4 是首个同状态“旧缓存未知、新 registry 可查”真实边：目标 anchor F150 来源于 F141 开始的版本，source 30 有当前版本，但两版本没有合格 pair，仍 **无 veto**。图见 [F159](public/cases/SOURCE_OLD_F159_native26_target16.svg) 与 [F157](public/cases/SOURCE_OLD_F157_native30_target4.svg)。它们是实际预测框的几何示意，**不是原 RGB 或 mask 视觉核验**。

旧状态查询与新分支实际效果由 [SOURCE_AUDIT.json](public/SOURCE_AUDIT.json) 分列。本次四段此前的公开映射从未分叉，故 1688 条同帧、同边的旧/新查询可直接对齐；它们不是 1688 个独立事件。旧 PX 的 573 条 `target_anchor_lineage_unknown` 中，新 registry 使 **561 条**精确 anchor 成为可查询，剩余 12 条仍无合格记录。新分支总计 1661 条 `REGISTERED`、27 条 `NEVER_REGISTERED`；其中 1113 条 source 不合格或不连续，563 条在 source 与 target 都可用后缺乏对应共现，12 条目标来源仍未知。**全部 1688 条检查的 `pair_status=NO_PAIR`**，故查询修复没有形成合法五帧 veto。缓存内其他版本曾有 pair witness，不能拿来排斥这些指定边。每次创建、live 中断、换锚/失效写在各段 `ACTION_LEDGER.jsonl`；当前目标失效不再删除仍被 bank 引用的未过期 anchor。

| 来源与段 | 检查边 | 旧未知→新可查 | 新目标从未登记 | 合格 pair 命中 | veto | 发布变化 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| OLD 0–199 | 168 | 51 | 0 | 0 | 0 | 0 |
| OLD 351–555 | 466 | 156 | 0 | 0 | 0 | 0 |
| BASELINE 0–199 | 168 | 51 | 0 | 0 | 0 | 0 |
| BASELINE 351–555 | 886 | 303 | 27 | 0 | 0 | 0 |

## 完整指标

IDF1/HOTA/AssA 是百分数；IDSW/FP/FN 是计数。两段合并使用原评分器重算，并非段分数平均。`ARCHIVED_PX` 是本基点的原始深度封存结果，`PX-A` 是本轮新状态真实回放。所有 mask、残片、正负公开 ID 都保留。

| 来源与段 | 分支 | IDF1 | HOTA | AssA | IDSW | FP | FN |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| OLD 0–199 | NATIVE | 92.8898 | 91.3625 | 88.0859 | 10 | 76 | 143 |
| OLD 0–199 | Z4Q_FROZEN | 92.1256 | 90.4837 | 86.3997 | 12 | 76 | 143 |
| OLD 0–199 | ARCHIVED_PX | 92.1256 | 90.4837 | 86.3997 | 12 | 76 | 143 |
| OLD 0–199 | PX-A | 92.1256 | 90.4837 | 86.3997 | 12 | 76 | 143 |
| OLD 351–555 | NATIVE | 82.9273 | 78.5828 | 72.1827 | 22 | 148 | 201 |
| OLD 351–555 | Z4Q_FROZEN | 82.8910 | 78.1478 | 71.4299 | 24 | 148 | 201 |
| OLD 351–555 | ARCHIVED_PX | 82.8910 | 78.1478 | 71.4299 | 24 | 148 | 201 |
| OLD 351–555 | PX-A | 82.8910 | 78.1478 | 71.4299 | 24 | 148 | 201 |
| **OLD 合并** | **NATIVE** | **87.8376** | **85.1875** | **81.6094** | **32** | **224** | **344** |
| OLD 合并 | Z4Q_FROZEN | 87.4426 | 84.5234 | 80.3627 | 36 | 224 | 344 |
| OLD 合并 | ARCHIVED_PX | 87.4426 | 84.5234 | 80.3627 | 36 | 224 | 344 |
| **OLD 合并** | **PX-A** | **87.4426** | **84.5234** | **80.3627** | **36** | **224** | **344** |
| BASELINE 0–199 | NATIVE | 92.8898 | 91.3625 | 88.0859 | 10 | 76 | 143 |
| BASELINE 0–199 | Z4Q_FROZEN | 92.1256 | 90.4837 | 86.3997 | 12 | 76 | 143 |
| BASELINE 0–199 | ARCHIVED_PX | 92.1256 | 90.4837 | 86.3997 | 12 | 76 | 143 |
| BASELINE 0–199 | PX-A | 92.1256 | 90.4837 | 86.3997 | 12 | 76 | 143 |
| BASELINE 351–555 | NATIVE | 79.7228 | 83.8347 | 74.4895 | 28 | 70 | 196 |
| BASELINE 351–555 | Z4Q_FROZEN | 80.9628 | 84.3781 | 75.5204 | 33 | 70 | 196 |
| BASELINE 351–555 | ARCHIVED_PX | 80.9628 | 84.3781 | 75.5204 | 33 | 70 | 196 |
| BASELINE 351–555 | PX-A | 80.9628 | 84.3781 | 75.5204 | 33 | 70 | 196 |
| **BASELINE 合并** | **NATIVE** | **86.2344** | **87.6345** | **81.2212** | **38** | **146** | **339** |
| BASELINE 合并 | Z4Q_FROZEN | 86.4832 | 87.4471 | 80.9081 | 45 | 146 | 339 |
| BASELINE 合并 | ARCHIVED_PX | 86.4832 | 87.4471 | 80.9081 | 45 | 146 | 339 |
| **BASELINE 合并** | **PX-A** | **86.4832** | **87.4471** | **80.9081** | **45** | **146** | **339** |

PX-A 相对同源归档 PX：两来源的 IDF1/HOTA/AssA/IDSW/FP/FN 全部 **Δ0**。相对同源 NATIVE：OLD 合并 IDF1 **−0.3950**、HOTA **−0.6641**、AssA **−1.2466** 个百分点、IDSW **+4**；BASELINE 合并 IDF1 **+0.2489**、HOTA **−0.1874**、AssA **−0.3131**、IDSW **+7**。FP/FN 两来源均无差。BASELINE 的单项 IDF1 高于 native 不能抵消其 HOTA/AssA 与切换退化，更不能归于 PX-A。

## 物理审计与边界

因为本轮没有改动边、拒绝边或发布变化，**本轮没有可归因的正确/错误恢复，也没有新增延迟切换**。事后 [EDGE_AUDIT.json](public/EDGE_AUDIT.json) 保留旧规则的动作：SOURCE_OLD 的 F159/F190/F468/F522 anchor 与当前 GT 匹配关系为 `DIFFERENT_GT`，F194/F374 为 `UNKNOWN`；SOURCE_BASELINE 的 F372/F409/F506 为 `SAME_GT`，F159/F190/F464/F522 为 `DIFFERENT_GT`，F194 为 `UNKNOWN`。F468 明确是 `BIRTH_REFINE` 出生路径；本轮没有用 F194/F468 的 GT 改门槛或指定动作。`SAME_GT` 是事后 anchor/current 关系，不单独证明长期 public ID 全正确。完整 CLEAR 切换逐条在 [SWITCH_LEDGER.json](public/SWITCH_LEDGER.json)。

工程来源、状态复制、两矩阵 hook、预测封存与评分通过；五帧共现对实际候选的覆盖为零，研究层结论限于这两个共享原帧的 FEEDING 保存源。未验证新连续 SAM3 前端、未证明零前瞻、未测试新的 VLM、未证明 v3 深度可因果使用，亦未证明历史/深度关联理论无效。受限输入的真实路径、大小与 SHA 在 [RESTRICTED_INVENTORY.json](public/RESTRICTED_INVENTORY.json)；Git 中只有 token、数值、哈希、几何示意和公开日志，没有 RGB/深度/GT raster、原始 RLE 或凭据。

**唯一下一步：**在独立连续 SAM3 来源上预注册并测量“实际重接候选中可追溯五帧合格共现”的覆盖率，再决定是否重新试验这条排斥机制。
