# MS1-S0 开发集全段事件扫描复盘

本目录先完成验证段 MS1-S0 的**开发集 8400 帧离线扩展和漏检修复**，基点 `101827e9fc87c393d26b10bc405d7efe4fb33c89`。原始分割、深度、参考和旧封存只读。下面的 V6 描述属于上一轮无 API 控制，不能解释为 DeepSeek 实验结果。

2026-09-28 新授权的 V7 使用同一固定扫描器和最早八个事件真实调用。原同步运行有 16 个 START、15 个 END，最后 F5927-S0 结果未知且原预测未封存；随后零新增 HTTP 的 8400 帧记录响应恢复回放已封存、评分。**模型相对数值分支 0 帧、0 指标增量；该结果包含未知请求的冻结回退，不能称为完整 8/8 模型判定。** 入口：[PAID_RUN_V7_FINAL_REVIEW.md](PAID_RUN_V7_FINAL_REVIEW.md)、[PAID_RUN_V7_EXECUTION_LOG.md](PAID_RUN_V7_EXECUTION_LOG.md)、[原始中断记录](run_development_v7_paid/public/INTERRUPTION_RECORD.json)、[恢复预测 seal](run_development_v7_recovery/public/PREDICTIONS_SEALED.json)、[模型逐事件核验](run_development_v7_recovery/public/MODEL_EVENT_AUDIT.json)、[V7 受限清单](RESTRICTED_INVENTORY_V7.json)。

## 入口和分层

- [FINAL_REVIEW.md](FINAL_REVIEW.md)：结论、漏检根因、F5927 证据、指标与限制。
- [dry_run_v6/public/TRIGGER_AUDIT.json](dry_run_v6/public/TRIGGER_AUDIT.json)：全部 15 个疑似点的启动、确认、首分离和选择状态。
- [dry_run_v6/public/F5927_GEOMETRY_AUDIT.json](dry_run_v6/public/F5927_GEOMETRY_AUDIT.json)：ID 1/7 事件的真实预测掩码面积及转移比例，不含像素。
- [dry_run_v6/public/PREDICTIONS_SEALED.json](dry_run_v6/public/PREDICTIONS_SEALED.json)：8400 帧预测、事务、发布和调用账本的封存哈希。
- [dry_run_v6/public/METRICS.json](dry_run_v6/public/METRICS.json)：封存后 TrackEval 整段评分。
- [dry_run_v6/public/PHYSICAL_EVENT_AUDIT.json](dry_run_v6/public/PHYSICAL_EVENT_AUDIT.json)：封存后参考锚点与连续片段共识的分列核验。
- [dry_run_v6/public/TEST_REPORT.json](dry_run_v6/public/TEST_REPORT.json)：因果首分离和状态回退回归。
- [RESTRICTED_INVENTORY.json](RESTRICTED_INVENTORY.json)：779 项本地受限输入/产物的绝对路径、字节和 SHA256。掩码图片、GT 栅格、私有 token 对应表留在本机。

`run_development_8400/` 是原扫描器的零触发封存，**已被判为工程漏检**；`dry_run_corrected/`、`dry_run_v2/`、`dry_run_v3/`、`dry_run_v4/`、`dry_run_v5/` 是逐步诊断与修复的保留记录。`BUDGET_PREFLIGHT_CORRECTED.json` 属于“只有一个事件”的过时估算，不能用于启动调用。没有旧响应进入本轮。

## 复现

需要 Windows 上仓库原路径、清单中同 SHA 的本地开发/验证输入、Python 3.12、NumPy、SciPy 及仓库已有 TrackEval。执行解释器可使用 `E:/CAU/D-MOT/tools/X-AnyLabeling/runtime/Scripts/python.exe`。以下命令从仓库根目录执行，并在新目录或新检出中运行，因为产物采用独占新建，不覆盖任何旧封存：

```powershell
$py = 'E:/CAU/D-MOT/tools/X-AnyLabeling/runtime/Scripts/python.exe'
& $py experiments/ms1_s0_development_8400/source_scan_v4.py
& $py experiments/ms1_s0_development_8400/replay_v6.py dry
& $py experiments/ms1_s0_development_8400/score.py dry_run_v6
& $py experiments/ms1_s0_development_8400/postseal_event.py dry_run_v6
& $py experiments/ms1_s0_development_8400/build_trigger_audit.py
& $py experiments/ms1_s0_development_8400/build_f5927_geometry_audit.py
& $py experiments/ms1_s0_development_8400/test_v6.py
```

验证集扫描回归使用 `source_scan_v4.scan(validation_observations, validation_assignments, private_output)`；输入路径和哈希列在受限清单。源选择、事件确认和 q 均只读预测流。评分脚本核对 seal 与逐帧发布记录后才打开 GT。直接调用 `replay_v6.py real` 受 `CONFIG_V6.json` 中零 HTTP 额度与授权标志阻断。

## 保密边界

Git 忽略 `private_source/`、`private_api/` 和图片；公开 JSON 只含数值、事件状态、路径与哈希。没有上传 RGB、原始 mask、GT raster、DeepSeek 凭据或 provider file ID。公开 `dry_packets/` 使用帧局部匿名 token；其实际源对应表留在 `private_api/`。
