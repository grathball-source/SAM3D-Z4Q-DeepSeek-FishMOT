# SLR-2 正式输入独立 QA

2026-09-20T15:34:30+08:00：通过。仅写本 QA 记录，未修改证据包、图像、原输入，未读取 GT。

- 144 请求逐项检查：历史选样和过去性、当前/过程谱系关系、深度因果来源、RGB 文件/帧号/哈希均通过。
- 历史检查 824 项；过程快照 720 项；谱系关系 4212 项；深度因果 1024 项；RGB 来源 304 项。
- 36 组原始/重排完整包在物理匿名化归一后完全相同，覆盖 history、current、recent、pairwise 数值、quality、evidence、options、baseline_option_id，超出原仅核对选项集合的检查。
- 0.25/0.50 秒各相对最新参考；因此更早两次观测间相邻差 0.234 秒不违反规则。所有历史源帧 ≤ pre ≤ query；图片历史 ≤ pre，当前图片 = query。
- 已使用 view_image 检查开发碎片图与验证图，见 JSON 的图片绝对路径和 SHA256。标签清楚，原始碎片保留，未见 native ID/全局帧号。
- 按当前 model_client 构造请求：文本最大 49,245 字节，图文最大 655,425 字节（含 base64）；单 PNG 最大 454,794 字节；最大尺寸 [896, 1136]。这不是模型 token 数。

需要主流程冻结补入的依赖：`E:\CAU\D-MOT\tools\sam3_depth_only_reconnect_20260916\rle_decode.py`，SHA256 `73a014fba5244f722e764df1f0f1a77cde08c8a12a04ebde3501335fb60f05c7`。它不在当前 SOURCE_HASHES 或 preparation code_hashes 中。

私有来源记录中的 source_depth_max_frame 均为空，是提取了不存在的观测级字段；真正来源字段位于 feature 行的 evidence_max_global_frame，本 QA 已逐项检查过去性。未发现未来证据，但后续勿把该空字段解释为已完成因果验证；以本 QA 为补充依据。
