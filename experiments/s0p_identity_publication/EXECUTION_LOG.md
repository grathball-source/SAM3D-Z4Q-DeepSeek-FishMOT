# S0-P 执行记录（2026-09-29）

1. 核对仓库工作树干净，HEAD 与 `origin/main` 均为固定基点 `9eca43e8ee35bbbc2949bcefb5ddbc653361d666`。读取用户附件、项目规则、原 V7 报告、源码、旧恢复 seal、评分器和逐次 IDSW 审计。没有连接实验室服务器、训练或模型服务。
2. 在新目录实现 `OutputIdentityPolicy` 与当前分支事件写集 `local_fallback`；未改旧 V7 文件。五项直接测试中的初版四项通过，真实 F2145 前缀复现旧 `n:4→-1000001` 和修复 `n:4→4`，并保存完整 F2144–F2147 切片。
3. 首次独立 8400 帧预测写入 `run_8400/public/`，13 个事件，0 新 HTTP，封存后评分 IDSW 8。逐条切换发现 F4519/F5927 的 `UNRESOLVED` 仍发布一帧临时 H1 预览，属于未满足本轮发布合同的工程错误。没有以 GT 选择 H1/H2。
4. 保留首次 seal、指标及与 freeze/score provenance SHA 完全一致的 `attempt1_source/`。补充通用“未决 q 延续上一帧唯一公开标签”逻辑与回归测试；五项单测和 F2145 真实切片通过。
5. 在 `run_8400_v2/public/` 再次从头连续运行 8400 帧 B0/HOLD-P：13 个事件、0 HTTP、全部预测及事务先封存。独立评分原 B0、旧封存 HOLD 与 HOLD-P，结果分别 IDSW 6/18/2；FP/FN 均 194/323，完整指标见 `METRICS.json`。
6. 无 GT 重新回放当前机制、逐帧比对全部 HOLD-P 预测，并封存 9 个 q 的私有来源参考；其后读取已曝光 GT，输出锚点、连续片段和 q 的分列物理核验。独立组外状态回放 299/299 同帧完全一致。生成 F2145 与最早确认事件 F1152 的 geometry-only 实际发布 SVG。
7. 校验受限依赖路径/字节/SHA、原 V7 只读来源、最终 freeze 与当前源码、每帧唯一发布及关键图文件；所有公开代码、配置、测试、日志、完整预测和报告准备非破坏性同步 main。实际 commit/push/ref 核验记录写在最终 `SYNC_VERIFICATION.json`，不修改预测 seal。

原 V7 paid 的 `16 START / 15 END / F5927-S0 UNKNOWN` 和 0 HTTP 恢复回放始终只读。本轮新 `CALL_LEDGER.jsonl` 为 0 字节；没有把旧响应按事件名用于新状态。
