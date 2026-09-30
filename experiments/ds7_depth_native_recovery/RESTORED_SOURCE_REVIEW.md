# DS7 保存修复深度来源复核

## 结论与可用范围

三个真实 native v2 文件存在、完整且 SHA256 与原验收一致，覆盖全局帧 0–1906。当前数据包的 1471 帧均能由 `index` 精确定位，并与 `color_index`、RGB/深度时间戳及 `delta_us` 绑定一致。选择这些原生文件作为本轮保存修复深度输入。

来源名：`SAVED_NATIVE_V2_REPROJECTED_OFFLINE_RGB_FUTURE_SUPPORTED`。v2 生成代码不读取人工实例标签，但使用当前 RGB，以及清洗阶段的前后帧深度和 RGB。因此它是既有修复深度的离线诊断输入；本轮只读当前行不使上游恢复自动成为在线因果算法。

## 真正的 v2 文件

根路径：`E:/CAU/D-MOT/tools/depth_restoration_feeding_20260929/full_v2/`。

| 文件 | 帧数 | bytes | SHA256 |
|---|---:|---:|---|
| depth_restored_v2_01.h5 | 900 | 454302078 | 1476b8e7ab97ebea085e91cc9c1331a5daa54ec4c1084f7a12c4170cb620fd52 |
| depth_restored_v2_02.h5 | 900 | 447218898 | 63c48b95d5eb01e44baf48b23cd3abf043cd2abe61682d2e7d6000d6d105bf38 |
| depth_restored_v2_03.h5 | 107 | 52394247 | 571ab176bb33a45480fd2e0a55de7717390728e48a1ccdf92e401c506185a92e |

原验收检查全部 1907 帧：37005051 个推断像素观测，其中 22928 个替换原非零值；验收范围是保存内容、来源与流程一致性，没有真实缺失区深度准确性结论。

## 未来依赖不能靠掩码消除

实际来源为 `E:/CAU/D-MOT/tools/depth_restoration_feeding_20260929/run_v2.py:67`：先调用 `clean(original, dep(i-1), dep(i+1), rgb, rgb_at(i-1), rgb_at(i+1), g)`，随后第 68 行将清洗后的完整稀疏深度输入 LingBot。`clean_v2.py` 的 reason bit 2 与 8 依赖后帧；bit 8 在保存报告中没有实际触发。

当前 1471 帧的生成报告记录：405 帧实际触发 temporal bit 2，共 3612 个像素观测；原非零替换 11931 个，原零值补全 26212748 个。1469 个非首尾帧具有调用后帧清洗的代码条件。这些是报告元数据统计，并非重新执行模型或逐帧重新判断清洗。

删除 reason bit 2/8 或 p3 无法得到因果等价深度：清洗改变模型的整幅输入，p2 原零值估计也可能受影响。保存文件没有“不使用未来帧”这一反事实推断。2000 mm 是该场景审阅/推断接受策略，不能称为设备量程。

## v3 与遮挡竞争

`E:/CAU/D-MOT/tools/depth_restoration_feeding_20260929/postfill.py` 明确读取 `label_source` 和 `rgb_original` 并构造人工实例区域后执行后填充。来源名应为 `PUBLISHED_V3_GT_ASSISTED_POSTFILL_OFFLINE`；不能作为无 GT 主分支。

数值切片选择固定边界/历史异常帧 0、351、766、1201、1906，另加入 v3 报告中后填点最多的 1858 帧以诊断投影竞争。该病例选择不参与正式效果评分或参数选择。

| 帧 | 已发布 p4 winner | p4 遮住的 v2 有效点 | 直接删 p4 后与 v2 不同的点 |
|---:|---:|---:|---:|
| 0 | 25 | 5 | 5 |
| 351 | 0 | 0 | 0 |
| 766 | 0 | 0 | 0 |
| 1201 | 0 | 0 | 0 |
| 1858 | 29 | 5 | 5 |
| 1906 | 0 | 0 | 0 |

六帧中，native v3 先将 `postfill_mask` 对应值归零均与真实 native v2 完全相同；已发布图的非 p4 深度和 source_index 也完全相同。直接删已投影 p4 会失去光栅化时未保存的 v2 次近来源，应命名为 `ALIGNED_V3_DROP_P4_LOSSY_DIAGNOSTIC`。本轮直接读取真实 v2，避免通过 GT 衍生的 postfill mask 重建。

## 当前读取器与冻结方案

新 `restored_source.py` 初始化只读取三个 H5 的 5 个一维索引/时间字段和数组形状。实际访问审计为 15 次元数据读取、0 次图数组读取。调用 F0/F766/F1906 时，各只读取相应原生行的 `depth_mm`、`original_depth_mm`、`filled_mask`、`invalidated_reason`，共 12 次图数组读取；没有后帧图、RGB、标签或 v3 读取。

保留原测量为 p1，原零值模型估计为 p2，原非零替换为 p3。使用 `AlignedFeeding_v1/calibration.json` 的 recorded_profiles；与 v2 run_config 的 calibration 完全一致。复用 `E:/CAU/D-MOT/tools/depth_restoration/geometry.py` 和 `build_aligned_dataset.py`，保持 recorded R，按 RGB 像素中心缩放内参，以最近正 camera-Z 竞争、等深度取最小 native index，返回完整 360×640 网格。上述两个模块的导入没有构造读取标签的 Context，也没有执行 color_label/make_frame。

`RestoredDepth.paths()` 为静态冻结入口，包含三个 H5、v2 run_config/verification、当前 calibration/manifest、两个投影代码文件。`__call__(global_frame)` 返回 depth、provenance、可公开的来源元数据；逐像素 source_index 留在实例的 `current_source_index`，不写入公开报告。

六帧的 `original_depth_mm` 与当前 raw native 完全一致，原测量按同一 recorded 几何重投影后的 depth/source_index 与保存的 raw aligned 完全一致。此处证明来源和既定投影的可复现性，物理配准准确性仍未知。

## 未知边界及最小下一步

鱼表面真实米制深度、补全区域真实准确性、原始极远值的硬件机制、独立物理标定误差、移除未来条件后的模型结果以及跟踪收益均未由该审计确定。

本轮可直接执行已保存 native v2 的离线诊断跟踪，冻结原文件哈希并保留 RGB/未来支持标签，与同源 raw 输入作封存对照。若研究结论需要在线因果恢复，需另建不使用未来帧的清洗与推断产物；本次没有运行或排程该服务/模型。

公开 JSON 仅包含路径、哈希、大小、时间/属性摘要与纯数字统计；没有逐像素坐标、GT/RLE 或原始数组内容。旧实验、数据与原生成代码均只读。
