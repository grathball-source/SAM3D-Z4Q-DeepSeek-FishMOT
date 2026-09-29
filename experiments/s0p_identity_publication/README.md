# S0-P 身份发布与事件局部回退

固定审查基点 `9eca43e8ee35bbbc2949bcefb5ddbc653361d666`。本轮只改变原 MS1-S0 共用的公开 ID 发布政策和失败事件回退边界；v4 预测触发、进入前参考、q、数值权重、深度、模型 prompt 和 8400 帧源不变。**新模型 HTTP 为 0**，本目录不包含新的 B-VLM 成绩。

最终结果先读 [FINAL_REVIEW.md](FINAL_REVIEW.md)。独立全段结果在 [run_8400_v2/public/](run_8400_v2/public/)；初次全段尝试及其 seal 和评分保留在 [run_8400/public/](run_8400/public/)，精确源码在 [attempt1_source/](attempt1_source/)。原 V7 paid 与 recovery 目录只读。

## 关键入口

- [manager_p.py](manager_p.py)：`OutputIdentityPolicy` 将内部 group/residual token 与公开 ID 分离；`GroupBridgeP.local_fallback` 只提交本事件写集，不能安全移植时延续当前分支合法的公开连续标签并记录 `UNRESOLVED`。
- [replay_p.py](replay_p.py)：B0 与 HOLD-P 各自真实状态全 8400 帧回放；每帧先决策和 commit，后通过唯一出口首次发布。
- [score_p.py](score_p.py)：核对 seal、输入哈希、逐帧发布哈希后，沿用原 TrackEval 与原 0.5 IoU 阈值评分；负 ID 和所有 mask 照常纳入。
- [test_p.py](test_p.py) 与 [F2145_SLICE.json](F2145_SLICE.json)：F2145 真实前缀和五项直接回归。
- [reference_audit.py](reference_audit.py)：无 GT 重新构建当前状态的 q 参考并封存，再独立读取已曝光 GT 作末端/共识分列核验。
- [state_audit.py](state_audit.py)：真实回放 299 个 active 帧的组外状态同帧比较。
- [figures.py](figures.py)：仅以预测源 bbox 中心及实际首次发布 ID 画 SVG；没有原 RGB、mask raster 或 GT 栅格。
- [RESTRICTED_INVENTORY.json](run_8400_v2/public/RESTRICTED_INVENTORY.json)：本机受限依赖的实际绝对路径、字节数及 SHA256。

## 复现

需要清单中同 SHA 的本机开发源与旧 V7 recovery 公开结果，以及 Python 3.12、NumPy、SciPy、pycocotools 和仓库既有 TrackEval。在新的检出中运行，产物采用独占新建，不覆盖已有 seal：

```powershell
$py = 'E:/CAU/D-MOT/tools/X-AnyLabeling/runtime/Scripts/python.exe'
& $py experiments/s0p_identity_publication/test_p.py
& $py experiments/s0p_identity_publication/replay_p.py
& $py experiments/s0p_identity_publication/score_p.py
& $py experiments/s0p_identity_publication/reference_audit.py prepare
& $py experiments/s0p_identity_publication/reference_audit.py score
& $py experiments/s0p_identity_publication/state_audit.py
& $py experiments/s0p_identity_publication/figures.py
& $py experiments/s0p_identity_publication/inventory.py
```

`test_p.py` 的真实切片输出 `F2145_SLICE.json` 已存在时会校验相同结果。最终脚本默认输出 `run_8400_v2/`，因此复现需要新检出。初次尝试的冻结源码 SHA 与 `attempt1_source/` 精确一致，需在独立检出替换到本目录的原文件名后才能复跑初次尝试。它的结果不能当成最终结果，也不能覆盖。原 V7 paid 的 16 START/15 END 与 F5927-S0 未知保持原状；recovery 是 0 新 HTTP 的旧响应恢复回放。

私有源、GT raster、像素、API wire、provider file IDs、凭据不进入 Git。源文件和产物的来源与受限复现依赖以清单为准。历史零事件试跑存在旧源码覆盖限制，不能靠本次源码精确复现其当时的执行状态，也没有改旧 freeze。
