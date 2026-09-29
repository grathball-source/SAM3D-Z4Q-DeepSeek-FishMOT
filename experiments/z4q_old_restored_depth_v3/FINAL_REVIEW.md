# OLD SAM3 + 修复深度 v3：405 帧同源诊断

**判定：工程/封存/评分通过；修复深度使旧 Z4Q 的 IDSW 36→35，IDF1 +0.0184、HOTA +0.0310、AssA +0.0351 点，但仍低于同源 NATIVE，逐边规则仍无增量。** 这是含标注辅助且使用前后帧修复深度的**曝光诊断**，不能当作无 GT、因果在线跟踪提点或物理身份正确性证明。

## 冻结输入和流程

沿用 `SOURCE_OLD` 的保存 SAM3 预测，两段原始帧 0–199、351–555 分别从空 Bridge 状态开始，总计 405 帧。两套控制器一为原冻结 Z4Q，一为上一轮逐边 PX；NATIVE 是同一 mask 的原生 ID。原预测 JSON、mask RLE、时间戳、来源 generation、规则配置和参考均未更换。唯一输入变化是从 `E:/CAU/D-MOT/data/AlignedFeeding_v1/depth_restored_rgb_640x360/NNNNNN.npz` 的 `depth_mm` 重新计算每个原生掩码的 whole/core 统计，再同时供给两个控制器。

该 NPZ 的 `provenance` 仅用于事后数值来源统计；控制器**没有读取** `instance_id`、`fish_interior_mask`、RGB 或人工参考。v3 中 `provenance=4` 是人工标注辅助的小孔估计；其基础 v2 LingBot 修复使用完整 1907 帧的前后时间参考，所以即使去掉这五个标签补孔像素，本次深度也不是过去帧独占的因果输入。数据集自带的恢复核验确认流水线一致性，不能证明鱼体深度物理准确。

六个真实切片输入测试先重算旧原始深度统计并验证非深度字段不变；然后 [`FREEZE.json`](public/FREEZE.json)封存代码、两套来源清单、六份旧派生输入和 405 个修复深度文件的真实路径/字节/SHA。两段状态回放的预测、动作、首次发布和 [`SEAL.json`](public/feeding_000000_000199/SEAL.json) 全部落盘后，评分器才读取编辑参考。独立评分回归了同源 NATIVE 原封存指标。第一次 200 帧尝试的封存哈希接口错误保留在 `public/FAILED_ATTEMPT_1`，未评分、不混入本结果；修正后重新冻结并从起点完成两段。顺序及退出码见 [`EXECUTION_LOG.md`](EXECUTION_LOG.md)。新增模型 HTTP、SAM3 推理和训练均为 **0**。

## 全段指标

IDF1/HOTA/AssA 为百分数；HOTA/AssA 沿用 TrackEval 多 IoU 阈值平均，IDSW/FP/FN 沿用 CLEAR 0.5。`RAW-Z4Q` 来自只读旧封存；修复深度两分支为本轮真实状态回放，完整每段/合并值在 [`METRICS.json`](public/METRICS.json)。

| 同源 OLD，0–199 + 351–555 | IDF1 | HOTA | AssA | IDSW | FP | FN |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| NATIVE（原始 ID） | 87.8376 | 85.1875 | 81.6094 | 32 | 224 | 344 |
| RAW-Z4Q（旧原始深度） | 87.4426 | 84.5234 | 80.3627 | 36 | 224 | 344 |
| Z4Q + 修复深度 v3 | 87.4610 | 84.5544 | 80.3979 | 35 | 224 | 344 |
| PX + 修复深度 v3 | 87.4610 | 84.5544 | 80.3979 | 35 | 224 | 344 |

修复深度相对旧原始深度 Z4Q：**IDF1 +0.0184、HOTA +0.0310、AssA +0.0351 点、IDSW −1、FP/FN 不变**。第一段 IDF1/IDSW 不变，HOTA/AssA +0.0314/+0.0600；第二段 IDF1/HOTA/AssA +0.0362/+0.0294/+0.0095，IDSW 24→23。修复后的 PX 相对同源 NATIVE 仍为 **IDF1 −0.3766、HOTA −0.6331、AssA −1.2115 点、IDSW +3**。PX 与本轮冻结 Z4Q 的 405 帧公开映射和所有指标完全相同，776 次候选边检查、**0 次否决**。这是深度共同输入的变化，不是逐边机制的贡献。

## 具体变化与物理边界

修复深度改变了 10,826 个原生观测中 10,529 个 whole/core 摘要，也改变了 188 帧公开映射：F194–F199 的 native38 不再接 old ID7，F374–F555 的 native70 不再接 old ID67。原始深度 PX 有五次 D1 延迟重接和一次 F468 出生重接；新 PX 为三次 D1 加一次出生重接。F194 与 F374 老锚/当前的 GT 关系都是 **UNKNOWN**，不能把两个取消动作自动判为正确物理身份恢复。切换账本具体是移除 F374 的一次切换，F461/F468 的两个旧切换各换成新标签切换，净 IDSW −1；逐帧映射和账本见 [`DELTA_AUDIT.json`](public/DELTA_AUDIT.json)、[`SWITCH_LEDGER.json`](public/SWITCH_LEDGER.json)。

F194 当前 native38 的原始/修复深度中位数均为 1186.17 mm；差异来自此前状态。旧原始深度在 F190 开始累计对 old ID7 的五帧 pending，并于 F194 接回；新深度没有这条 pending。F374 的证据更需要谨慎：old ID67 的 F361 锚，在修复深度下有 **34 个实测像素（中位 1166.86 mm）和 135 个 LingBot 填补像素（中位 826.14 mm）**，合并中位数 827.09 mm。native70 在 F370–F373 的修复深度中位数约 1164–1169 mm，到 F374 跌到 **835.58 mm**，F375 又回到 1165.17 mm；F374 掩码内实测 169 像素的中位数是 **1171.88 mm**，填补 128 像素的中位数是 **832.74 mm**。旧原始深度路径在 F374 达五次确认并接回；新路径到 F374 只累计一次，未提交。这个分层冲突提示填补值改变了候选历史和确认时序，不能仅凭少一次切换宣称深度识别了正确鱼。数值及来源见 [`F374_DEPTH_SOURCE.json`](public/F374_DEPTH_SOURCE.json)。

先前已确认物理错误的 F159 `26→16`、F190 `30→8`、F468 `80→21`、F522 `83→73` 仍发生；本轮事后锚/当前匹配均为不同 GT。F468 在 PX 日志继续明确为 `BIRTH_REFINE`、`phase=birth`，不能误归因 D1。[`EDGE_AUDIT.json`](public/EDGE_AUDIT.json)列所有提交及 776 次检查原因：511 次来源片段不合格或不连续，265 次目标锚谱系未知，无真实 veto。

## 标注辅助像素敏感性和交付边界

全 405 帧预测掩码并集内有 **5 个 `provenance=4` 像素**，分布于 F31/F91/F401/F408/F494。固定全段敏感性回放将所有这类像素置零，五帧输入摘要发生变化，但冻结 Z4Q 和 PX 的 **405 帧公开映射均完全不变**；本次分数变化不由这五个标签补孔像素驱动。该检查在评分后执行，只是诊断，不把 v3 变成因果或盲测输入。见 [`PROVENANCE4_SENSITIVITY.json`](public/PROVENANCE4_SENSITIVITY.json)。

[`ACCEPTANCE.json`](public/ACCEPTANCE.json)核验 405 帧双封存、发布哈希、NATIVE 与旧封存精确一致、PX 与冻结 Z4Q 逐帧一致、零 veto 和标注像素敏感性。所有受限预测、原始/修复深度、旧派生流及评分参考的真实路径、字节和 SHA 在 [`RESTRICTED_INVENTORY.json`](public/RESTRICTED_INVENTORY.json)；Git 只含 ID、数值、token、代码、日志和封存，不含 RGB、RLE 像素、GT raster 或凭据。人工参考 `checked=false`，两段及案例已曝光；仅 405 帧而非全部 FEEDING 视频。当前冻结深度输入的短暂中位数跳变尚未证明物理可信，不应直接部署。

分发文件的字节数与 SHA 列于 [`ARTIFACT_MANIFEST.json`](public/ARTIFACT_MANIFEST.json)；该清单不包含自身以避免循环哈希。

**下一步：**在新连续来源上预先冻结一个仅过去帧、无标注辅助的深度质量门槛，分别核验实测与推断值，再与同源 NATIVE 做完整状态与物理身份对照。
