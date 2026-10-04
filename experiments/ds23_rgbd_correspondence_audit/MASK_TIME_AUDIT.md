# DS23：独立mask坐标与时间来源审计

## 判定与范围

**固定输入来源合同PASS；真实光学配准准确度UNKNOWN。**

保留DS22全部171个既定端点、168个不同来源帧，不依据原关联结果筛选。本检查重新打开原SAM3预测和来源元数据，逐帧核对当前来源帧内全部N0掩码，共2,582个帧内掩码实例。发现的掩码、RGB帧编号、记录RGB时间不一致均为0。没有读取RGB像素、GT、annotation instance_id、修复深度或新模型结果。

实际执行记录：`EXECUTION_LOG.jsonl`中`mask_time_checks.py`，UTC 2026-10-04 06:41:07.487032至06:41:20.659865，即上海时间14:41:07至14:41:20；13.173313秒，exit 0，stderr 0字节。结果为`MASK_TIME_CHECKS.json`，不是引用旧测试成绩。

## 真实掩码链路

| 来源 | 原始掩码域 | 本轮实际输入域 | 进入640×360的真实步骤 | 本轮检查 |
| --- | --- | --- | --- | --- |
| Feeding四段，SOURCE_OLD | 原SAM3 `ML/labels_raw` JSON声明1920×1080 | 640×360 N0 RLE | FEEDING首次准备时，顶点`(p+0.5)/3-0.5`，四舍五入后fillPoly；后续DS14、DS22解码相同RLE | 52帧 / 53端点，1,389个掩码全部与同名原JSON重建值相同 |
| FishSA开发 / 验证 | 已保存640×360 N0 RLE | 640×360 N0 RLE | 解码原N0；没有执行1/3轮廓缩放 | 12帧 / 12端点，71个掩码全部与原assignment相同 |
| L3 | 原SAM3 `labels_raw` JSON声明1920×1080 | 640×360 N0 RLE | DS14首次准备中执行一次相同像素中心变换与fillPoly；后续解码 | 20帧 / 20端点，204个掩码全部相同 |
| LW | 原SAM3 `labels_raw` JSON声明1920×1080 | 640×360 N0 RLE | 与L3相同 | 84帧 / 86端点，918个掩码全部相同 |

每个polygon来源的实际原文件还满足`imagePath`文件名等于当前全局来源帧`{g:06d}.jpg`。全部掩码集合与原集合相同，逐位数组相同；既定171个端点再核对DS21原mask证书哈希。未拿只检查框宽高替代mask检查。

Feeding的SOURCE_OLD有独立历史来源合同：四段都使用最初`AnnotationFeeding_20260924/ML/labels_raw`，不是另一次baseline protocol的`segments_v2/v3/v4`分段重推理目录。本轮没有以另一预测目录代替冻结源。

1/3与1920/640、1080/360比例一致。此代码变换的是轮廓顶点中心；round引入至多半个目标像素的逐轴顶点量化。**round后的低分辨率fillPoly不等于先在1920×1080栅格化bitmap、再nearest缩小。** 轮廓离散、简化和孔洞表示会影响薄鱼体，但当前等价检查只证明冻结表示没有被再次缩放或改写，不能认证原SAM3轮廓完全贴合鱼体，也不能直接将两种栅格化方法的差异定为坐标错误。

当前本地SAM3导出代码`sam3_mask_polygons.py`使用external contours、没有内部孔洞表示；当前server方法直接输出轮廓点，未在`show_masks`路径再次乘原图宽高。它们不是本轮重新执行的前端；未证明当前代码字节等于2026-09-24原作业代码，因此只记录可追溯的表示限制，不将其推定为每个旧样本失败根因。

## 帧号、时间与因果边界

Feeding、L3、LW从原manifest的`frame=g`查RGB时间；本地段编号统一为`frame=g-start+1`。FishSA的三个编号域分开：原连续RGB的全局编号`g=source_color_index+1`；AlignedDataset存储`frame_id`按配对记录编排；另有`h5_row`。实际适配器检查所请求g、RGB记录时间、存储frame_id和h5_row，不能把`aligned frame_id=g-1`现象当作掩码错了一帧。本轮12个FishSA固定来源帧均与原N0 assignment、当前RGB元数据和旧深度来源绑定相同。原全局第一RGB未配对，在旧适配器中仍为缺测；本固定端点集合不包含它。

| 段 | 固定端点 / 来源帧 | 全native掩码 | depth比RGB晚1ms / 2ms的来源帧 |
| --- | ---: | ---: | ---: |
| Feeding 0–199 | 6 / 6 | 158 | 3 / 3 |
| Feeding 351–555 | 6 / 6 | 160 | 4 / 2 |
| Feeding 701–1060 | 12 / 12 | 320 | 8 / 4 |
| Feeding 1201–1906 | 29 / 28 | 751 | 17 / 11 |
| FishSA开发8400 | 6 / 6 | 36 | 0 / 6 |
| FishSA验证2888 | 6 / 6 | 35 | 2 / 4 |
| L3 | 20 / 20 | 204 | 8 / 12 |
| LW | 86 / 84 | 918 | 54 / 30 |
| 合计 | 171 / 168 | 2,582 | 96 / 72 |

所有168个固定来源帧的配对depth timestamp都晚于当前RGB timestamp，96帧晚1ms、72帧晚2ms。元数据`delta_us=RGB-depth`为-1000或-2000，旧来源绑定中的delta也逐帧相等；RGB事实时间与原RGB微秒时间转换一致。**没有读取后来RGB帧，不等于传感器样本时间严格不晚于RGB时刻。** 这是原存档的近时刻RGB-D配对；若将来要称严格实时因果，必须按配对深度实际到达时刻等待并记延迟，或另设已经到达的深度政策。此次未更换配对、不重选传感器帧，不改q。

旧关联参考时间早于请求时间，本轮沿用实际旧参考，不跨风险或按公共整数重新接历史。Feeding20帧/重叠5帧SAM3生产协议以及其他原保存前端的上游lookahead，不能由本次仅查当前帧的局部检查认证为没有lookahead；其完整端到端严格实时性仍UNKNOWN。

本结果排除了当前固定集合中可检查的重复缩放、原RGB编号查错、段编号偏移和记录RGB时间绑定错误。1–2ms传感器不同步对移动边界的真实位移没有在此用假定速度换算；没有证据证明它解释DS22大面积背景兼容。实际光学/水下投影、标定误差、前端分割偏差与传感器本身边界不一致，仍需DS23其余空间审计区分，不能由PASS推出某一种原因。

## 可复现来源

`MASK_TIME_CHECKS.json`列出162个实际原预测/元数据文件的路径、字节和SHA：156个原SAM3 polygon JSON、2份原FishSA N0 assignment、4份来源manifest；另记录实际导入source的路径/字节/SHA。公开记录不含轮廓点数组或RLE像素内容。

| 已读实际代码或生产元数据 | 关键位置 | SHA256 |
| --- | --- | --- |
| `experiments/ds16_relative_depth_order/source.py`（实际导入） | 15–20解码N0；50–57转换轮廓；60–126深度源/时间；135–148原源选择 | `19404334ab98ca3fac749ba04f7a0098820764c8fef9a9e8db72ac1ff1e8c97c` |
| `experiments/ds14_raw_multidataset/prepare_inputs.py` | 39–66：L3/LW尺寸断言与转换；其他源复用原N0 | `32fcf94c4c22fe2e08f722e37944d31edfb07cd4ff8ba3578dba4ab09be571b2` |
| `experiments/feeding_first_two_s0p/prepare.py` | 22原SOURCE_OLD路径；45–55轮廓转换；59–108来源帧与记录RGB时间 | `50b35914abc8681a10717d5077bcce3af4a05a7d73fc91ec58148ee0d987f877` |
| `experiments/ds2_depth_transfer_validation/cohort.py` | 8–10沿用FEED原RAW；75–109原SOURCE_OLD两新段准备 | `2bf3a222356794f688d1c5d4d84f907cd3741e403b977fc1151265745038f658` |
| `experiments/ds20_pending_confirmation_isolation/common.py` | 41–47段域；48之后将DS18/DS16等加入搜索路径 | `452eec1e457979edb0ddda7d4b88c2f7915a7510bba67c652c4d6a63915e6bb9` |
| `E:/CAU/D-MOT/tools/sam3_occlusion_identity_20260915/evidence_20260915_complete/collector/observer.py` | 22–25：logits bilinear、align_corners=False到360×640；135–144当前帧一致与prefetch排除；214–215记录时间 | `698e2c33c75f8d423d02c0c16c67d46620dbbd45a30d5c65f5d5390e7e69cccb` |
| `E:/CAU/D-MOT/tools/sam3_occlusion_identity_20260915/i3_evidence_20260915_complete/identity_cpu10_20260915/run_parallel.py` | 81–96：原N0掩码复制、原时间传递；没有将G/I3结果当N0 | `c89223163b998f037b05a2df191d1b22c958476e44e415c868f3242aaf4f4930` |
| `E:/CAU/D-MOT/data/AnnotationFeeding_20260924/full_protocol.json` | 原1008模型输入、20帧batch、5帧重叠；不是原图轮廓尺寸 | `9595f9e6171bf01bff164f39974be0525267939294807fe7737f8f9e2b5c2b0c` |
| `E:/CAU/D-MOT/tools/X-AnyLabeling-Server/app/models/segment_anything_3_video.py`（当前本地版本） | 1151之后转换；1232之后mask轮廓直接输出 | `87d8a68c2f7279cc9be4248a6e40bc09d45b0c647bb3cbde45445640e2e3d47d` |
| `E:/CAU/D-MOT/tools/X-AnyLabeling-Server/app/models/sam3_mask_polygons.py`（当前本地版本） | external contours与最多2px简化；内部孔洞不表示 | `0214867ad7a451c43b3947995449f09a070f2b73b3d7b5c3e2a40bbba48ffe6b` |

复现命令：原D-MOT Python执行本目录`mask_time_checks.py`，依赖当前冻结DS21/DS22特征与原私有mask来源；输出目录必须全新，不覆盖本轮已存在JSON、旧seal或旧评分。模型HTTP、费用、新tracker replay、新IDF1/HOTA均为0/NOT_RUN。
