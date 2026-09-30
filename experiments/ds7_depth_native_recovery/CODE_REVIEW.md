# DS7 冻结前代码审查

**PASS：未发现仍阻断切片的代码问题。** 5 项纯内存检查全部通过；没有打开人工标签，没有实际 GT 评分。

## 已补齐

评分先校验全四段五分支 seal、全部列出产物、源/code/access 摘要、旧 DS6 seal；之后核验帧、时间、mask、整数唯一 ID，P0 原生等价与 D2 旧逐帧等价。负 ID 不过滤。q 首次公开映射与预测、ledger、selected mapping、transaction 相互绑定；冻结样本与 raw/restored 实际 fact、key、z、MAD 及历史版本绑定。生成器 head 与 evaluator 内存生成逐字一致。

## 解释边界

- paired post 缺测时所有边共同无信息；可用 pre 行同时比较两个 post，used_edges 可为 0/2/4。
- 60 mm 为推断单点观测的假定 sigma。WLS 不加额外 floor，拟合可压低预测尺度；样本相关性未校准。9:1 只比较 H1/H2，不是校准概率。
- staged CORRECT、first-public CORRECT、NOT_STAGED、UNKNOWN 分列。正确的未改号映射不能称新修复 native 错误。legacy physical 字段只是实际 bank anchor 的 RGB 身份对应，不是深度表面或 mm 真值。
- P2 是已有 RGB/下一帧支持的离线 v2 诊断；原始 P1、P2 超过 native、P2 对 P1 的增量及全冻结成功规则分别报告。
- DS7 row 模型的 legacy depth_joint_available 可为空；用 used_edges 报告证据，不把空值当 0。

实际切片/全段仍须运行无 GT 验证。所有预测和访问 seal 完成后才能评分。
