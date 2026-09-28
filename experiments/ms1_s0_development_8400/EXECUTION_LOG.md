# 执行记录（2026-09-28）

工作目录：`E:/CAU/SAM3D-Z4Q-DeepSeek-FishMOT`；固定审查基点 `101827e9fc87c393d26b10bc405d7efe4fb33c89`。本地 CPU/已归档预测输入，无新服务器/GPU 作业。Python：`E:/CAU/D-MOT/tools/X-AnyLabeling/runtime/Scripts/python.exe`；SciPy 1.18.1、NumPy 2.5.3。旧实验目录只读。

1. 原 `source_scan.py` 跑完整 8400 帧，仅依赖全局掉数和恰好两个软前驱，得到 0 资格事件。封存为 `run_development_8400/`，随后根据用户指出的 ID 1/7 交互判定为漏检，未作为无事件结论或模型测试。
2. 逐帧检查预测掩码，确认 F5927 起 ID 1 面积塌缩、ID 7 增长，F5933 承载源编号转到 ID 1，F5939 首次重新出现两个足量候选。原扫描器在 F5933 的软兼容前驱数为 5。
3. v2–v5 依次调试局部扫描、首分离面积条件和未解决状态回退，所有尝试各存独立目录。v3/v4 中的探索性数值差异未用于选择事件。v4 对开发集最终 15 疑似点、验证段 16 疑似点；验证段 F2617 通过直接消失路径。v4 对开发集最终扫描文件 SHA256 为 `9aa8e33e35d7f6ba26bab72c8af2ab4bff7e4139c98bd37be6dd8ca0ed42f62b`。
4. `replay_v6.py dry`：8400 帧、三套独立控制器，退出码 0；13 个事件、9 个 q、最早 8 个模型位置；0 次 HTTP，$0。封存预测 SHA256 `1ff1e9801cda5430cd7e03bc1cde9fd4e7b7b4835e14715934565b55bfb73e77`。首分离前先完成阶段判定和提交，未解决事件回退到同帧 B0 完整状态。
5. `score.py dry_run_v6`：退出码 0；校验源与封存输出、逐帧发布记录后调用 TrackEval，B0 完整指标与归档精确一致。`postseal_event.py dry_run_v6`：退出码 0；分列锚点正确性与连续片段共识，保留不可评分。
6. `build_trigger_audit.py`、`build_f5927_geometry_audit.py` 和 `test_v6.py` 均退出码 0。测试检查 F5932 不可作为 q、F5939 首次发布和下一帧未解决状态与 B0 一致、q 之后资料不能改变 S0 请求。扫描器补充观测/掩码时间戳一致性断言后，再跑开发与验证全段，扫描文件 SHA 与原 v4 输出逐字节相同。`build_restricted_inventory.py` 生成 779 项本地受限路径/字节/SHA；私有像素未提交。

最后的工程与研究边界见 `FINAL_REVIEW.md`。用户对先前“只有一个事件”的估算提出反对并要求重新扫描；因此过时的两次请求预算文件只是历史记录，没有启动任何官方 DeepSeek 推理。
