# DS34：双端短片段与有限延迟事件联合恢复

## 1. 主判定与分层边界

**COMPLETE_TRIAL_MIXED_IMPROVEMENT_AND_REGRESSION**。固定八套来源共20,098帧，四个分支全部继续自己的真实状态至段末；全部预测和访问记录先封存，随后独立统一评分。EVENT_RGB/EVENT_RGBD真实联合stage次数为 `{"EVENT_RGB": 8, "EVENT_RGBD": 8}`；EVENT_RGBD实际启用深度权重的窗口为4，相对EVENT_RGB改变发布的帧数为0。本报告按真实结果填写，不把工程通过、一次CHOICE或宽尺度覆盖写成性能收益。

- 工程：实际预览、原子stage/commit、未发布suffix回放、一次首次发布和全部mask/残片保留均有封存证据；原SAM3/原Z4Q逐帧控制及官方指标与DS33严格一致。
- 输入：固定原SAM3、原始深度、真实RGB/时间戳/实际标定和DS18来源质量；精确bank anchor、独立source generation/public epoch、匿名GROUP/post分开。隐藏的producer身份版本与水下物理标定精度仍UNKNOWN。
- 方法：原Z4Q组外策略保留；事件保护/几何/轮廓/深度和局部回退共同影响结果。EVENT_RGBD−Z4Q不能全记为深度收益；EVENT_RGBD−EVENT_RGB才是本轮深度模块整体增量。
- 证据：本轮是既有曝光数据上的探索性试验，L3/LW为弱参考诊断；没有新的盲测泛化结论。DEFER、无分离、无历史、缺测、非法候选与不可评分均保留，不能算安全通过。

基点 `cdec46035f730e7166e175f8df5aab2a9f3deb31`。新增大模型HTTP=0、smoke=0、训练=0、SAM3推理=0、深度补全服务=0、费用=0美元。内部事件和候选不是大模型调用。

## 2. 冻结方法和实际科学范围

沿用原V4预测扫描与两鱼保护范围：首次疑似立即保护，合并只记录匿名GROUP；持续native及新source可进入真实两候选联合映射。最后可靠pre来自实际bank anchor的同版本连续片段，30帧缓存、最近10点真实时间OLS/WLS，immutable anchor最多12秒；风险切断live，不能删除仍未改变的anchor来源，也不能按public整数拼接另一source。

q是首次两个分离候选。当前与后续观测在关联前保持匿名，采用首个满足固定规则的3帧连续raw-clean片段，最长等待30帧或10秒/EOF。先选择完整H1/H2物理bijection，再在本分支q−1checkpoint上真实stage/commit并回放q至cutoff，随后第一次发布q；q状态只能使用q实际观测，未来测量不写进q bank。已经发布的历史不改写。失败使用本事件写集的局部回退，保住组外状态和先前修复；不存在整套复制B0 engine的回退。

轮廓用真实pre最后3帧与post固定3帧的所有短端点对，已安装OpenCV DIS MEDIUM前后向RGB灰度对应；没有从旧anchor一路长链传播到重现端。RGB可靠性由双向误差、纹理和光度判断；深度原源去重独立约束测量质量。两个新分支采用相同RGB轮廓传播，深度以独立候选代价参与完整解释。post反向回到q只作候选无关连续性诊断，不参与身份分数。未进行RAFT-3D训练/推理，也没有补画或分割mask。

深度使用同一片段真实DS18 whole/core质量与DS1原时间WLS预测，原源去重、混层/共享/缺失均可追溯；比较预测与当前深度的背景归一化t4代价。整个2×2比较共同可用才启用冻结权重0.25，否则共同无信息；未知和宽尺度不使某条边自动少罚。二维真实回归运动权重0.25、轮廓权重0.25、联合margin0.10保持冻结。真实depth时间重复不报3D速度；RGB对应和可靠点支持仍不是鱼的物理身份或遮挡真值。

V4初始群组需要既有前帧source和面积历史，不能宣称覆盖所有新ID群组；多事件同时相交仍在原单活动组范围。源原先已错号、未观察的producer reset/串鱼、末帧GT缺失均不能靠public整数或模型假设填真值。详细边界见DATA_CONTRACT。

## 3. 完整指标

百分指标单位%，差值为百分点。IDSW/FP/FN是全段完整计数，任何ID和mask均未排除。Feeding四段以独立身份命名空间合池，不能与FishSA/L3/LW混成一个总体标题。

| 来源 | 分支 | IDF1 | HOTA | AssA | IDSW | FP | FN |
| --- | --- | --- | --- | --- | --- | --- | --- |
| feeding_000000_000199 | SAM3_NATIVE | 92.8898 | 91.3625 | 88.0859 | 10 | 76 | 143 |
| feeding_000000_000199 | Z4Q_FROZEN | 92.1256 | 90.4837 | 86.3997 | 12 | 76 | 143 |
| feeding_000000_000199 | EVENT_RGB | 92.8898 | 91.2436 | 87.8567 | 11 | 76 | 143 |
| feeding_000000_000199 | EVENT_RGBD | 92.8898 | 91.2436 | 87.8567 | 11 | 76 | 143 |
| feeding_000351_000555 | SAM3_NATIVE | 82.9273 | 78.5828 | 72.1827 | 22 | 148 | 201 |
| feeding_000351_000555 | Z4Q_FROZEN | 82.8910 | 78.1478 | 71.4299 | 24 | 148 | 201 |
| feeding_000351_000555 | EVENT_RGB | 82.8910 | 78.4434 | 71.9711 | 24 | 148 | 201 |
| feeding_000351_000555 | EVENT_RGBD | 82.8910 | 78.4434 | 71.9711 | 24 | 148 | 201 |
| feeding_000701_001060 | SAM3_NATIVE | 77.4280 | 75.5450 | 65.0066 | 36 | 154 | 278 |
| feeding_000701_001060 | Z4Q_FROZEN | 75.6368 | 73.5609 | 61.6422 | 42 | 154 | 278 |
| feeding_000701_001060 | EVENT_RGB | 75.6368 | 73.4129 | 61.4037 | 44 | 154 | 278 |
| feeding_000701_001060 | EVENT_RGBD | 75.6368 | 73.4129 | 61.4037 | 44 | 154 | 278 |
| feeding_001201_001906 | SAM3_NATIVE | 78.8400 | 78.7272 | 68.0893 | 40 | 109 | 363 |
| feeding_001201_001906 | Z4Q_FROZEN | 81.5259 | 79.8925 | 70.1131 | 54 | 109 | 363 |
| feeding_001201_001906 | EVENT_RGB | 79.7864 | 79.1912 | 68.8916 | 51 | 109 | 363 |
| feeding_001201_001906 | EVENT_RGBD | 79.7864 | 79.1912 | 68.8916 | 51 | 109 | 363 |
| fishsa_development_8400 | SAM3_NATIVE | 91.3133 | 73.3461 | 69.1868 | 5 | 194 | 323 |
| fishsa_development_8400 | Z4Q_FROZEN | 99.3335 | 77.8295 | 77.9076 | 6 | 194 | 323 |
| fishsa_development_8400 | EVENT_RGB | 92.0404 | 74.5266 | 71.4327 | 5 | 194 | 323 |
| fishsa_development_8400 | EVENT_RGBD | 92.0404 | 74.5266 | 71.4327 | 5 | 194 | 323 |
| fishsa_validation_2888 | SAM3_NATIVE | 76.4564 | 66.4355 | 55.1961 | 8 | 298 | 423 |
| fishsa_validation_2888 | Z4Q_FROZEN | 80.6976 | 69.2439 | 60.0743 | 9 | 298 | 423 |
| fishsa_validation_2888 | EVENT_RGB | 75.8191 | 64.7960 | 52.5842 | 11 | 298 | 423 |
| fishsa_validation_2888 | EVENT_RGBD | 75.8191 | 64.7960 | 52.5842 | 11 | 298 | 423 |
| L3 | SAM3_NATIVE | 72.4268 | 75.3626 | 94.2597 | 1 | 14677 | 0 |
| L3 | Z4Q_FROZEN | 74.7453 | 77.1716 | 98.8390 | 2 | 14677 | 0 |
| L3 | EVENT_RGB | 74.7453 | 77.1716 | 98.8390 | 2 | 14677 | 0 |
| L3 | EVENT_RGBD | 74.7453 | 77.1716 | 98.8390 | 2 | 14677 | 0 |
| LW | SAM3_NATIVE | 60.6135 | 66.3691 | 77.5551 | 7 | 16493 | 28 |
| LW | Z4Q_FROZEN | 64.3294 | 68.9917 | 83.8056 | 10 | 16493 | 28 |
| LW | EVENT_RGB | 58.6873 | 65.2203 | 74.8936 | 10 | 16493 | 28 |
| LW | EVENT_RGBD | 58.6873 | 65.2203 | 74.8936 | 10 | 16493 | 28 |
| Feeding four-segment pooled | SAM3_NATIVE | 80.9768 | 79.9641 | 71.5305 | 108 | 487 | 985 |
| Feeding four-segment pooled | Z4Q_FROZEN | 81.7168 | 79.8599 | 71.3418 | 132 | 487 | 985 |
| Feeding four-segment pooled | EVENT_RGB | 80.9869 | 79.6503 | 70.9835 | 130 | 487 | 985 |
| Feeding four-segment pooled | EVENT_RGBD | 80.9869 | 79.6503 | 70.9835 | 130 | 487 | 985 |

L3/LW参考为未独立审查的预测辅助标注，保持弱参考标签。FishSA沿用原参考raster/版本，Feeding640、L3/LW1080p polygon，CLEAR/Identity IoU0.5和HOTA19alpha数学不变。

### 同源原生、原Z4Q及深度增量的完整差值

| 来源 | 比较 | ΔIDF1 | ΔHOTA | ΔAssA | ΔIDSW | ΔFP | ΔFN |
| --- | --- | --- | --- | --- | --- | --- | --- |
| feeding_000000_000199 | SAM3_NATIVE → EVENT_RGB | +0.0000 | -0.1189 | -0.2292 | +1 | +0 | +0 |
| feeding_000000_000199 | SAM3_NATIVE → EVENT_RGBD | +0.0000 | -0.1189 | -0.2292 | +1 | +0 | +0 |
| feeding_000000_000199 | Z4Q_FROZEN → EVENT_RGB | +0.7641 | +0.7599 | +1.4571 | -1 | +0 | +0 |
| feeding_000000_000199 | Z4Q_FROZEN → EVENT_RGBD | +0.7641 | +0.7599 | +1.4571 | -1 | +0 | +0 |
| feeding_000000_000199 | EVENT_RGB → EVENT_RGBD | +0.0000 | +0.0000 | +0.0000 | +0 | +0 | +0 |
| feeding_000351_000555 | SAM3_NATIVE → EVENT_RGB | -0.0362 | -0.1394 | -0.2116 | +2 | +0 | +0 |
| feeding_000351_000555 | SAM3_NATIVE → EVENT_RGBD | -0.0362 | -0.1394 | -0.2116 | +2 | +0 | +0 |
| feeding_000351_000555 | Z4Q_FROZEN → EVENT_RGB | +0.0000 | +0.2956 | +0.5411 | +0 | +0 | +0 |
| feeding_000351_000555 | Z4Q_FROZEN → EVENT_RGBD | +0.0000 | +0.2956 | +0.5411 | +0 | +0 | +0 |
| feeding_000351_000555 | EVENT_RGB → EVENT_RGBD | +0.0000 | +0.0000 | +0.0000 | +0 | +0 | +0 |
| feeding_000701_001060 | SAM3_NATIVE → EVENT_RGB | -1.7913 | -2.1321 | -3.6029 | +8 | +0 | +0 |
| feeding_000701_001060 | SAM3_NATIVE → EVENT_RGBD | -1.7913 | -2.1321 | -3.6029 | +8 | +0 | +0 |
| feeding_000701_001060 | Z4Q_FROZEN → EVENT_RGB | +0.0000 | -0.1480 | -0.2384 | +2 | +0 | +0 |
| feeding_000701_001060 | Z4Q_FROZEN → EVENT_RGBD | +0.0000 | -0.1480 | -0.2384 | +2 | +0 | +0 |
| feeding_000701_001060 | EVENT_RGB → EVENT_RGBD | +0.0000 | +0.0000 | +0.0000 | +0 | +0 | +0 |
| feeding_001201_001906 | SAM3_NATIVE → EVENT_RGB | +0.9464 | +0.4639 | +0.8023 | +11 | +0 | +0 |
| feeding_001201_001906 | SAM3_NATIVE → EVENT_RGBD | +0.9464 | +0.4639 | +0.8023 | +11 | +0 | +0 |
| feeding_001201_001906 | Z4Q_FROZEN → EVENT_RGB | -1.7395 | -0.7013 | -1.2215 | -3 | +0 | +0 |
| feeding_001201_001906 | Z4Q_FROZEN → EVENT_RGBD | -1.7395 | -0.7013 | -1.2215 | -3 | +0 | +0 |
| feeding_001201_001906 | EVENT_RGB → EVENT_RGBD | +0.0000 | +0.0000 | +0.0000 | +0 | +0 | +0 |
| fishsa_development_8400 | SAM3_NATIVE → EVENT_RGB | +0.7271 | +1.1804 | +2.2460 | +0 | +0 | +0 |
| fishsa_development_8400 | SAM3_NATIVE → EVENT_RGBD | +0.7271 | +1.1804 | +2.2460 | +0 | +0 | +0 |
| fishsa_development_8400 | Z4Q_FROZEN → EVENT_RGB | -7.2931 | -3.3029 | -6.4749 | -1 | +0 | +0 |
| fishsa_development_8400 | Z4Q_FROZEN → EVENT_RGBD | -7.2931 | -3.3029 | -6.4749 | -1 | +0 | +0 |
| fishsa_development_8400 | EVENT_RGB → EVENT_RGBD | +0.0000 | +0.0000 | +0.0000 | +0 | +0 | +0 |
| fishsa_validation_2888 | SAM3_NATIVE → EVENT_RGB | -0.6373 | -1.6395 | -2.6119 | +3 | +0 | +0 |
| fishsa_validation_2888 | SAM3_NATIVE → EVENT_RGBD | -0.6373 | -1.6395 | -2.6119 | +3 | +0 | +0 |
| fishsa_validation_2888 | Z4Q_FROZEN → EVENT_RGB | -4.8785 | -4.4479 | -7.4901 | +2 | +0 | +0 |
| fishsa_validation_2888 | Z4Q_FROZEN → EVENT_RGBD | -4.8785 | -4.4479 | -7.4901 | +2 | +0 | +0 |
| fishsa_validation_2888 | EVENT_RGB → EVENT_RGBD | +0.0000 | +0.0000 | +0.0000 | +0 | +0 | +0 |
| L3 | SAM3_NATIVE → EVENT_RGB | +2.3185 | +1.8090 | +4.5794 | +1 | +0 | +0 |
| L3 | SAM3_NATIVE → EVENT_RGBD | +2.3185 | +1.8090 | +4.5794 | +1 | +0 | +0 |
| L3 | Z4Q_FROZEN → EVENT_RGB | +0.0000 | +0.0000 | +0.0000 | +0 | +0 | +0 |
| L3 | Z4Q_FROZEN → EVENT_RGBD | +0.0000 | +0.0000 | +0.0000 | +0 | +0 | +0 |
| L3 | EVENT_RGB → EVENT_RGBD | +0.0000 | +0.0000 | +0.0000 | +0 | +0 | +0 |
| LW | SAM3_NATIVE → EVENT_RGB | -1.9262 | -1.1488 | -2.6616 | +3 | +0 | +0 |
| LW | SAM3_NATIVE → EVENT_RGBD | -1.9262 | -1.1488 | -2.6616 | +3 | +0 | +0 |
| LW | Z4Q_FROZEN → EVENT_RGB | -5.6421 | -3.7714 | -8.9120 | +0 | +0 | +0 |
| LW | Z4Q_FROZEN → EVENT_RGBD | -5.6421 | -3.7714 | -8.9120 | +0 | +0 | +0 |
| LW | EVENT_RGB → EVENT_RGBD | +0.0000 | +0.0000 | +0.0000 | +0 | +0 | +0 |
| Feeding four-segment pooled | SAM3_NATIVE → EVENT_RGB | +0.0101 | -0.3138 | -0.5470 | +22 | +0 | +0 |
| Feeding four-segment pooled | SAM3_NATIVE → EVENT_RGBD | +0.0101 | -0.3138 | -0.5470 | +22 | +0 | +0 |
| Feeding four-segment pooled | Z4Q_FROZEN → EVENT_RGB | -0.7299 | -0.2096 | -0.3582 | -2 | +0 | +0 |
| Feeding four-segment pooled | Z4Q_FROZEN → EVENT_RGBD | -0.7299 | -0.2096 | -0.3582 | -2 | +0 | +0 |
| Feeding four-segment pooled | EVENT_RGB → EVENT_RGBD | +0.0000 | +0.0000 | +0.0000 | +0 | +0 | +0 |

相对较弱原Z4Q的提升不自动表示超过同源SAM3；恢复到原Z4Q只是止损。出现指标涨跌时分别报告，不用净IDSW掩盖新增错误。

## 4. 事件、真实提交、深度和弃权

| 来源 | 分支 | 疑似episode | q窗口 | 无分离 | 联合stage | stage首帧异Z4Q | 数值局部回退 | depth λ>0 | contour λ>0 | 实际flow对 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| feeding_000000_000199 | EVENT_RGB | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| feeding_000000_000199 | EVENT_RGBD | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| feeding_000351_000555 | EVENT_RGB | 6 | 3 | 3 | 0 | 0 | 3 | 0 | 0 | 0 |
| feeding_000351_000555 | EVENT_RGBD | 6 | 3 | 3 | 0 | 0 | 3 | 0 | 0 | 0 |
| feeding_000701_001060 | EVENT_RGB | 6 | 3 | 3 | 1 | 1 | 2 | 0 | 0 | 25 |
| feeding_000701_001060 | EVENT_RGBD | 6 | 3 | 3 | 1 | 1 | 2 | 0 | 0 | 25 |
| feeding_001201_001906 | EVENT_RGB | 7 | 6 | 1 | 1 | 1 | 5 | 0 | 0 | 20 |
| feeding_001201_001906 | EVENT_RGBD | 7 | 6 | 1 | 1 | 1 | 5 | 0 | 0 | 20 |
| fishsa_development_8400 | EVENT_RGB | 12 | 8 | 4 | 1 | 1 | 7 | 0 | 0 | 35 |
| fishsa_development_8400 | EVENT_RGBD | 12 | 8 | 4 | 1 | 1 | 7 | 1 | 0 | 35 |
| fishsa_validation_2888 | EVENT_RGB | 11 | 7 | 4 | 2 | 2 | 5 | 0 | 0 | 54 |
| fishsa_validation_2888 | EVENT_RGBD | 11 | 7 | 4 | 2 | 2 | 5 | 1 | 0 | 54 |
| L3 | EVENT_RGB | 11 | 5 | 6 | 0 | 0 | 5 | 0 | 0 | 0 |
| L3 | EVENT_RGBD | 11 | 5 | 6 | 0 | 0 | 5 | 0 | 0 | 0 |
| LW | EVENT_RGB | 20 | 10 | 10 | 3 | 3 | 7 | 0 | 0 | 93 |
| LW | EVENT_RGBD | 20 | 10 | 10 | 3 | 3 | 7 | 2 | 0 | 93 |

首帧与Z4Q的差异包含共同保护与先前自身修复，不能直接当作当前选择的独有作用。`preview_changes`只比较从未发布的内部临时H1；真实发布差异单独对照同源最终Native/Z4Q。stage即使首帧ID不变，也可能真实建立了后续alias；不能只数ID变化判断状态提交。

逐来源完整选择/状态/reason、缺测、数值fallback、来源窗口和证据计数写入RESULTS.json，原始EVENTS、FLOW、TRANSACTIONS和PUBLISH_LEDGER保持封存。逻辑fact与候选pair会共享测量，不能把行数当独立鱼事件数。可靠轮廓比例、宽深度区间覆盖不是物理准确率。

## 5. 物理参考与公共ID原始来源分开

下表只对实际联合stage评价物理恢复；无stage的回退、DEFER和无q顶层都为UNSCORABLE，保留观测映射诊断另列。literal q必须实际匹配该首帧；postfragment共识要求全部预先固定3帧各自唯一匹配同一GT，缺一帧或冲突即不可评分，不挑可评分子集。prefragment独立要求至少3个固定连续观测同一共识。

| 来源 | 分支 | 实际评分依据 | CORRECT | WRONG | UNSCORABLE |
| --- | --- | --- | --- | --- | --- |
| feeding_000000_000199 | EVENT_RGB | physical_counts_actual_joint_stages | 0 | 0 | 0 |
| feeding_000000_000199 | EVENT_RGB | physical_prefragment_joint_stages | 0 | 0 | 0 |
| feeding_000000_000199 | EVENT_RGB | postfragment_preanchor_joint_stages | 0 | 0 | 0 |
| feeding_000000_000199 | EVENT_RGB | postfragment_prefragment_joint_stages | 0 | 0 | 0 |
| feeding_000000_000199 | EVENT_RGB | public_reference_joint_stages | 0 | 0 | 0 |
| feeding_000000_000199 | EVENT_RGBD | physical_counts_actual_joint_stages | 0 | 0 | 0 |
| feeding_000000_000199 | EVENT_RGBD | physical_prefragment_joint_stages | 0 | 0 | 0 |
| feeding_000000_000199 | EVENT_RGBD | postfragment_preanchor_joint_stages | 0 | 0 | 0 |
| feeding_000000_000199 | EVENT_RGBD | postfragment_prefragment_joint_stages | 0 | 0 | 0 |
| feeding_000000_000199 | EVENT_RGBD | public_reference_joint_stages | 0 | 0 | 0 |
| feeding_000351_000555 | EVENT_RGB | physical_counts_actual_joint_stages | 0 | 0 | 0 |
| feeding_000351_000555 | EVENT_RGB | physical_prefragment_joint_stages | 0 | 0 | 0 |
| feeding_000351_000555 | EVENT_RGB | postfragment_preanchor_joint_stages | 0 | 0 | 0 |
| feeding_000351_000555 | EVENT_RGB | postfragment_prefragment_joint_stages | 0 | 0 | 0 |
| feeding_000351_000555 | EVENT_RGB | public_reference_joint_stages | 0 | 0 | 0 |
| feeding_000351_000555 | EVENT_RGBD | physical_counts_actual_joint_stages | 0 | 0 | 0 |
| feeding_000351_000555 | EVENT_RGBD | physical_prefragment_joint_stages | 0 | 0 | 0 |
| feeding_000351_000555 | EVENT_RGBD | postfragment_preanchor_joint_stages | 0 | 0 | 0 |
| feeding_000351_000555 | EVENT_RGBD | postfragment_prefragment_joint_stages | 0 | 0 | 0 |
| feeding_000351_000555 | EVENT_RGBD | public_reference_joint_stages | 0 | 0 | 0 |
| feeding_000701_001060 | EVENT_RGB | physical_counts_actual_joint_stages | 0 | 1 | 0 |
| feeding_000701_001060 | EVENT_RGB | physical_prefragment_joint_stages | 0 | 1 | 0 |
| feeding_000701_001060 | EVENT_RGB | postfragment_preanchor_joint_stages | 0 | 1 | 0 |
| feeding_000701_001060 | EVENT_RGB | postfragment_prefragment_joint_stages | 0 | 1 | 0 |
| feeding_000701_001060 | EVENT_RGB | public_reference_joint_stages | 0 | 1 | 0 |
| feeding_000701_001060 | EVENT_RGBD | physical_counts_actual_joint_stages | 0 | 1 | 0 |
| feeding_000701_001060 | EVENT_RGBD | physical_prefragment_joint_stages | 0 | 1 | 0 |
| feeding_000701_001060 | EVENT_RGBD | postfragment_preanchor_joint_stages | 0 | 1 | 0 |
| feeding_000701_001060 | EVENT_RGBD | postfragment_prefragment_joint_stages | 0 | 1 | 0 |
| feeding_000701_001060 | EVENT_RGBD | public_reference_joint_stages | 0 | 1 | 0 |
| feeding_001201_001906 | EVENT_RGB | physical_counts_actual_joint_stages | 1 | 0 | 0 |
| feeding_001201_001906 | EVENT_RGB | physical_prefragment_joint_stages | 1 | 0 | 0 |
| feeding_001201_001906 | EVENT_RGB | postfragment_preanchor_joint_stages | 1 | 0 | 0 |
| feeding_001201_001906 | EVENT_RGB | postfragment_prefragment_joint_stages | 1 | 0 | 0 |
| feeding_001201_001906 | EVENT_RGB | public_reference_joint_stages | 1 | 0 | 0 |
| feeding_001201_001906 | EVENT_RGBD | physical_counts_actual_joint_stages | 1 | 0 | 0 |
| feeding_001201_001906 | EVENT_RGBD | physical_prefragment_joint_stages | 1 | 0 | 0 |
| feeding_001201_001906 | EVENT_RGBD | postfragment_preanchor_joint_stages | 1 | 0 | 0 |
| feeding_001201_001906 | EVENT_RGBD | postfragment_prefragment_joint_stages | 1 | 0 | 0 |
| feeding_001201_001906 | EVENT_RGBD | public_reference_joint_stages | 1 | 0 | 0 |
| fishsa_development_8400 | EVENT_RGB | physical_counts_actual_joint_stages | 1 | 0 | 0 |
| fishsa_development_8400 | EVENT_RGB | physical_prefragment_joint_stages | 1 | 0 | 0 |
| fishsa_development_8400 | EVENT_RGB | postfragment_preanchor_joint_stages | 1 | 0 | 0 |
| fishsa_development_8400 | EVENT_RGB | postfragment_prefragment_joint_stages | 1 | 0 | 0 |
| fishsa_development_8400 | EVENT_RGB | public_reference_joint_stages | 1 | 0 | 0 |
| fishsa_development_8400 | EVENT_RGBD | physical_counts_actual_joint_stages | 1 | 0 | 0 |
| fishsa_development_8400 | EVENT_RGBD | physical_prefragment_joint_stages | 1 | 0 | 0 |
| fishsa_development_8400 | EVENT_RGBD | postfragment_preanchor_joint_stages | 1 | 0 | 0 |
| fishsa_development_8400 | EVENT_RGBD | postfragment_prefragment_joint_stages | 1 | 0 | 0 |
| fishsa_development_8400 | EVENT_RGBD | public_reference_joint_stages | 1 | 0 | 0 |
| fishsa_validation_2888 | EVENT_RGB | physical_counts_actual_joint_stages | 0 | 1 | 1 |
| fishsa_validation_2888 | EVENT_RGB | physical_prefragment_joint_stages | 0 | 1 | 1 |
| fishsa_validation_2888 | EVENT_RGB | postfragment_preanchor_joint_stages | 0 | 1 | 1 |
| fishsa_validation_2888 | EVENT_RGB | postfragment_prefragment_joint_stages | 0 | 1 | 1 |
| fishsa_validation_2888 | EVENT_RGB | public_reference_joint_stages | 0 | 2 | 0 |
| fishsa_validation_2888 | EVENT_RGBD | physical_counts_actual_joint_stages | 0 | 1 | 1 |
| fishsa_validation_2888 | EVENT_RGBD | physical_prefragment_joint_stages | 0 | 1 | 1 |
| fishsa_validation_2888 | EVENT_RGBD | postfragment_preanchor_joint_stages | 0 | 1 | 1 |
| fishsa_validation_2888 | EVENT_RGBD | postfragment_prefragment_joint_stages | 0 | 1 | 1 |
| fishsa_validation_2888 | EVENT_RGBD | public_reference_joint_stages | 0 | 2 | 0 |
| L3 | EVENT_RGB | physical_counts_actual_joint_stages | 0 | 0 | 0 |
| L3 | EVENT_RGB | physical_prefragment_joint_stages | 0 | 0 | 0 |
| L3 | EVENT_RGB | postfragment_preanchor_joint_stages | 0 | 0 | 0 |
| L3 | EVENT_RGB | postfragment_prefragment_joint_stages | 0 | 0 | 0 |
| L3 | EVENT_RGB | public_reference_joint_stages | 0 | 0 | 0 |
| L3 | EVENT_RGBD | physical_counts_actual_joint_stages | 0 | 0 | 0 |
| L3 | EVENT_RGBD | physical_prefragment_joint_stages | 0 | 0 | 0 |
| L3 | EVENT_RGBD | postfragment_preanchor_joint_stages | 0 | 0 | 0 |
| L3 | EVENT_RGBD | postfragment_prefragment_joint_stages | 0 | 0 | 0 |
| L3 | EVENT_RGBD | public_reference_joint_stages | 0 | 0 | 0 |
| LW | EVENT_RGB | physical_counts_actual_joint_stages | 2 | 1 | 0 |
| LW | EVENT_RGB | physical_prefragment_joint_stages | 0 | 0 | 3 |
| LW | EVENT_RGB | postfragment_preanchor_joint_stages | 2 | 1 | 0 |
| LW | EVENT_RGB | postfragment_prefragment_joint_stages | 0 | 0 | 3 |
| LW | EVENT_RGB | public_reference_joint_stages | 1 | 1 | 1 |
| LW | EVENT_RGBD | physical_counts_actual_joint_stages | 2 | 1 | 0 |
| LW | EVENT_RGBD | physical_prefragment_joint_stages | 0 | 0 | 3 |
| LW | EVENT_RGBD | postfragment_preanchor_joint_stages | 2 | 1 | 0 |
| LW | EVENT_RGBD | postfragment_prefragment_joint_stages | 0 | 0 | 3 |
| LW | EVENT_RGBD | public_reference_joint_stages | 1 | 1 | 1 |

旧bank实际物理anchor和public严格早于q的首次实际发布来源分列；public整数等于GT整数没有意义。旧参考已错号时，偶然换回公共ID不能当物理身份恢复。EVENT_AUDIT逐edge同时保存literal-q、prefragment、postfragment、public-origin及原参考已错来源；评分映射按实际新物理候选，不按未置换H标签查答案。

### 事件alias的当前帧返回冲突处理

| 来源 | 分支 | 实际cascade帧 | 实际撤销event alias数 |
| --- | --- | --- | --- |
| feeding_000000_000199 | EVENT_RGB | 0 | 0 |
| feeding_000000_000199 | EVENT_RGBD | 0 | 0 |
| feeding_000351_000555 | EVENT_RGB | 0 | 0 |
| feeding_000351_000555 | EVENT_RGBD | 0 | 0 |
| feeding_000701_001060 | EVENT_RGB | 0 | 0 |
| feeding_000701_001060 | EVENT_RGBD | 0 | 0 |
| feeding_001201_001906 | EVENT_RGB | 0 | 0 |
| feeding_001201_001906 | EVENT_RGBD | 0 | 0 |
| fishsa_development_8400 | EVENT_RGB | 0 | 0 |
| fishsa_development_8400 | EVENT_RGBD | 0 | 0 |
| fishsa_validation_2888 | EVENT_RGB | 0 | 0 |
| fishsa_validation_2888 | EVENT_RGBD | 0 | 0 |
| L3 | EVENT_RGB | 0 | 0 |
| L3 | EVENT_RGBD | 0 | 0 |
| LW | EVENT_RGB | 0 | 0 |
| LW | EVENT_RGBD | 0 | 0 |

这里由当前真实观测和alias占用经过原单轮冲突仲裁后仍存在的重复触发，仅局部撤销与本分支DS34关联的alias链，让原Z4Q当前帧仲裁继续运行；日志为`ds34_event_return_cascade`和`DS34_CURRENT_FRAME_EVENT_RETURN_CASCADE`。`actual_qualified_returns`可为空，这项安全处理没有新增“canonical native必须另行合格返回”的资格门槛。原低质量native quarantine已使重复为空时不撤销alias。这属于共同状态安全处理，不是新的深度身份贡献，也不认证物理鱼恢复。未读取未来返回、未复制B0 bank、未回填已发布历史；全部当前帧实际撤销记录和原始trigger详情保存在RESULTS中。

### 原常驻继承动作（不能全记为本轮事件新贡献）

| 来源 | 分支 | 原动作来源 | 实际动作 | 物理正确/错/不可评 | 公共来源正确/错/不可评 |
| --- | --- | --- | --- | --- | --- |
| feeding_000000_000199 | Z4Q_FROZEN | D1_DELAYED | 3 | 0/2/1 | 0/2/1 |
| feeding_000000_000199 | Z4Q_FROZEN | BIRTH_REFINE | 0 | 0/0/0 | 0/0/0 |
| feeding_000000_000199 | EVENT_RGB | D1_DELAYED | 2 | 0/1/1 | 0/1/1 |
| feeding_000000_000199 | EVENT_RGB | BIRTH_REFINE | 0 | 0/0/0 | 0/0/0 |
| feeding_000000_000199 | EVENT_RGBD | D1_DELAYED | 2 | 0/1/1 | 0/1/1 |
| feeding_000000_000199 | EVENT_RGBD | BIRTH_REFINE | 0 | 0/0/0 | 0/0/0 |
| feeding_000351_000555 | Z4Q_FROZEN | D1_DELAYED | 2 | 0/1/1 | 1/1/0 |
| feeding_000351_000555 | Z4Q_FROZEN | BIRTH_REFINE | 1 | 0/1/0 | 0/0/1 |
| feeding_000351_000555 | EVENT_RGB | D1_DELAYED | 2 | 0/1/1 | 1/1/0 |
| feeding_000351_000555 | EVENT_RGB | BIRTH_REFINE | 0 | 0/0/0 | 0/0/0 |
| feeding_000351_000555 | EVENT_RGBD | D1_DELAYED | 2 | 0/1/1 | 1/1/0 |
| feeding_000351_000555 | EVENT_RGBD | BIRTH_REFINE | 0 | 0/0/0 | 0/0/0 |
| feeding_000701_001060 | Z4Q_FROZEN | D1_DELAYED | 6 | 2/4/0 | 2/4/0 |
| feeding_000701_001060 | Z4Q_FROZEN | BIRTH_REFINE | 0 | 0/0/0 | 0/0/0 |
| feeding_000701_001060 | EVENT_RGB | D1_DELAYED | 7 | 2/5/0 | 2/5/0 |
| feeding_000701_001060 | EVENT_RGB | BIRTH_REFINE | 0 | 0/0/0 | 0/0/0 |
| feeding_000701_001060 | EVENT_RGBD | D1_DELAYED | 7 | 2/5/0 | 2/5/0 |
| feeding_000701_001060 | EVENT_RGBD | BIRTH_REFINE | 0 | 0/0/0 | 0/0/0 |
| feeding_001201_001906 | Z4Q_FROZEN | D1_DELAYED | 14 | 6/8/0 | 6/8/0 |
| feeding_001201_001906 | Z4Q_FROZEN | BIRTH_REFINE | 1 | 0/1/0 | 0/1/0 |
| feeding_001201_001906 | EVENT_RGB | D1_DELAYED | 12 | 4/8/0 | 3/9/0 |
| feeding_001201_001906 | EVENT_RGB | BIRTH_REFINE | 1 | 0/1/0 | 0/1/0 |
| feeding_001201_001906 | EVENT_RGBD | D1_DELAYED | 12 | 4/8/0 | 3/9/0 |
| feeding_001201_001906 | EVENT_RGBD | BIRTH_REFINE | 1 | 0/1/0 | 0/1/0 |
| fishsa_development_8400 | Z4Q_FROZEN | D1_DELAYED | 2 | 2/0/0 | 2/0/0 |
| fishsa_development_8400 | Z4Q_FROZEN | BIRTH_REFINE | 1 | 1/0/0 | 1/0/0 |
| fishsa_development_8400 | EVENT_RGB | D1_DELAYED | 1 | 1/0/0 | 1/0/0 |
| fishsa_development_8400 | EVENT_RGB | BIRTH_REFINE | 0 | 0/0/0 | 0/0/0 |
| fishsa_development_8400 | EVENT_RGBD | D1_DELAYED | 1 | 1/0/0 | 1/0/0 |
| fishsa_development_8400 | EVENT_RGBD | BIRTH_REFINE | 0 | 0/0/0 | 0/0/0 |
| fishsa_validation_2888 | Z4Q_FROZEN | D1_DELAYED | 2 | 2/0/0 | 1/0/1 |
| fishsa_validation_2888 | Z4Q_FROZEN | BIRTH_REFINE | 1 | 1/0/0 | 1/0/0 |
| fishsa_validation_2888 | EVENT_RGB | D1_DELAYED | 1 | 1/0/0 | 0/0/1 |
| fishsa_validation_2888 | EVENT_RGB | BIRTH_REFINE | 0 | 0/0/0 | 0/0/0 |
| fishsa_validation_2888 | EVENT_RGBD | D1_DELAYED | 1 | 1/0/0 | 0/0/1 |
| fishsa_validation_2888 | EVENT_RGBD | BIRTH_REFINE | 0 | 0/0/0 | 0/0/0 |
| L3 | Z4Q_FROZEN | D1_DELAYED | 10 | 1/0/9 | 1/0/9 |
| L3 | Z4Q_FROZEN | BIRTH_REFINE | 0 | 0/0/0 | 0/0/0 |
| L3 | EVENT_RGB | D1_DELAYED | 9 | 1/0/8 | 1/0/8 |
| L3 | EVENT_RGB | BIRTH_REFINE | 0 | 0/0/0 | 0/0/0 |
| L3 | EVENT_RGBD | D1_DELAYED | 9 | 1/0/8 | 1/0/8 |
| L3 | EVENT_RGBD | BIRTH_REFINE | 0 | 0/0/0 | 0/0/0 |
| LW | Z4Q_FROZEN | D1_DELAYED | 47 | 1/0/46 | 1/0/46 |
| LW | Z4Q_FROZEN | BIRTH_REFINE | 0 | 0/0/0 | 0/0/0 |
| LW | EVENT_RGB | D1_DELAYED | 38 | 0/0/38 | 0/0/38 |
| LW | EVENT_RGB | BIRTH_REFINE | 2 | 0/0/2 | 0/0/2 |
| LW | EVENT_RGBD | D1_DELAYED | 38 | 0/0/38 | 0/0/38 |
| LW | EVENT_RGBD | BIRTH_REFINE | 2 | 0/0/2 | 0/0/2 |

BirthRefine的kind也可为reconnect，明确以phase=birth区分BIRTH_REFINE和D1_DELAYED；按最终实际published transaction而非未选中试运行统计。

## 6. 每次切换的新增和消除

| 来源 | 比较 | 新增完整record | 消除完整record | 净IDSW | 新增GT/帧occurrence | 消除GT/帧occurrence |
| --- | --- | --- | --- | --- | --- | --- |
| feeding_000000_000199 | SAM3_NATIVE_TO_EVENT_RGB | 1 | 0 | 1 | 1 | 0 |
| feeding_000000_000199 | SAM3_NATIVE_TO_EVENT_RGBD | 1 | 0 | 1 | 1 | 0 |
| feeding_000000_000199 | Z4Q_FROZEN_TO_EVENT_RGB | 0 | 1 | -1 | 0 | 1 |
| feeding_000000_000199 | Z4Q_FROZEN_TO_EVENT_RGBD | 0 | 1 | -1 | 0 | 1 |
| feeding_000000_000199 | EVENT_RGB_TO_EVENT_RGBD | 0 | 0 | 0 | 0 | 0 |
| feeding_000351_000555 | SAM3_NATIVE_TO_EVENT_RGB | 4 | 2 | 2 | 2 | 0 |
| feeding_000351_000555 | SAM3_NATIVE_TO_EVENT_RGBD | 4 | 2 | 2 | 2 | 0 |
| feeding_000351_000555 | Z4Q_FROZEN_TO_EVENT_RGB | 2 | 2 | 0 | 1 | 1 |
| feeding_000351_000555 | Z4Q_FROZEN_TO_EVENT_RGBD | 2 | 2 | 0 | 1 | 1 |
| feeding_000351_000555 | EVENT_RGB_TO_EVENT_RGBD | 0 | 0 | 0 | 0 | 0 |
| feeding_000701_001060 | SAM3_NATIVE_TO_EVENT_RGB | 9 | 1 | 8 | 8 | 0 |
| feeding_000701_001060 | SAM3_NATIVE_TO_EVENT_RGBD | 9 | 1 | 8 | 8 | 0 |
| feeding_000701_001060 | Z4Q_FROZEN_TO_EVENT_RGB | 3 | 1 | 2 | 2 | 0 |
| feeding_000701_001060 | Z4Q_FROZEN_TO_EVENT_RGBD | 3 | 1 | 2 | 2 | 0 |
| feeding_000701_001060 | EVENT_RGB_TO_EVENT_RGBD | 0 | 0 | 0 | 0 | 0 |
| feeding_001201_001906 | SAM3_NATIVE_TO_EVENT_RGB | 22 | 11 | 11 | 12 | 1 |
| feeding_001201_001906 | SAM3_NATIVE_TO_EVENT_RGBD | 22 | 11 | 11 | 12 | 1 |
| feeding_001201_001906 | Z4Q_FROZEN_TO_EVENT_RGB | 14 | 17 | -3 | 5 | 8 |
| feeding_001201_001906 | Z4Q_FROZEN_TO_EVENT_RGBD | 14 | 17 | -3 | 5 | 8 |
| feeding_001201_001906 | EVENT_RGB_TO_EVENT_RGBD | 0 | 0 | 0 | 0 | 0 |
| fishsa_development_8400 | SAM3_NATIVE_TO_EVENT_RGB | 2 | 2 | 0 | 1 | 1 |
| fishsa_development_8400 | SAM3_NATIVE_TO_EVENT_RGBD | 2 | 2 | 0 | 1 | 1 |
| fishsa_development_8400 | Z4Q_FROZEN_TO_EVENT_RGB | 3 | 4 | -1 | 1 | 2 |
| fishsa_development_8400 | Z4Q_FROZEN_TO_EVENT_RGBD | 3 | 4 | -1 | 1 | 2 |
| fishsa_development_8400 | EVENT_RGB_TO_EVENT_RGBD | 0 | 0 | 0 | 0 | 0 |
| fishsa_validation_2888 | SAM3_NATIVE_TO_EVENT_RGB | 4 | 1 | 3 | 3 | 0 |
| fishsa_validation_2888 | SAM3_NATIVE_TO_EVENT_RGBD | 4 | 1 | 3 | 3 | 0 |
| fishsa_validation_2888 | Z4Q_FROZEN_TO_EVENT_RGB | 4 | 2 | 2 | 3 | 1 |
| fishsa_validation_2888 | Z4Q_FROZEN_TO_EVENT_RGBD | 4 | 2 | 2 | 3 | 1 |
| fishsa_validation_2888 | EVENT_RGB_TO_EVENT_RGBD | 0 | 0 | 0 | 0 | 0 |
| L3 | SAM3_NATIVE_TO_EVENT_RGB | 1 | 0 | 1 | 1 | 0 |
| L3 | SAM3_NATIVE_TO_EVENT_RGBD | 1 | 0 | 1 | 1 | 0 |
| L3 | Z4Q_FROZEN_TO_EVENT_RGB | 0 | 0 | 0 | 0 | 0 |
| L3 | Z4Q_FROZEN_TO_EVENT_RGBD | 0 | 0 | 0 | 0 | 0 |
| L3 | EVENT_RGB_TO_EVENT_RGBD | 0 | 0 | 0 | 0 | 0 |
| LW | SAM3_NATIVE_TO_EVENT_RGB | 5 | 2 | 3 | 3 | 0 |
| LW | SAM3_NATIVE_TO_EVENT_RGBD | 5 | 2 | 3 | 3 | 0 |
| LW | Z4Q_FROZEN_TO_EVENT_RGB | 5 | 5 | 0 | 2 | 2 |
| LW | Z4Q_FROZEN_TO_EVENT_RGBD | 5 | 5 | 0 | 2 | 2 |
| LW | EVENT_RGB_TO_EVENT_RGBD | 0 | 0 | 0 | 0 | 0 |

完整record包含具体旧/新public；同GT同帧发生但public不同可以同时算新增和消除而净差0。SWITCHES和SWITCH_CHANGES保留全部原记录、same-GT/frame对应关系，不用净差推断错误个数。

## 7. 延迟、耗时和UNKNOWN

| 来源 | 发布帧延迟min/median/max | 真实数据秒median/p95/max | 接收到首发墙钟秒median/p95/max |
| --- | --- | --- | --- |
| feeding_000000_000199 | 0/30/30 | 0.997/0.997/0.997 | 4.389/6.610/6.788 |
| feeding_000351_000555 | 0/30/30 | 0.997/0.997/0.997 | 7.758/12.895/14.410 |
| feeding_000701_001060 | 0/30/30 | 0.997/0.997/0.997 | 6.052/20.691/22.404 |
| feeding_001201_001906 | 0/30/30 | 0.997/0.997/0.998 | 6.915/14.962/20.362 |
| fishsa_development_8400 | 0/30/30 | 1.000/1.000/1.000 | 1.821/3.107/25.296 |
| fishsa_validation_2888 | 0/30/30 | 1.000/1.000/1.000 | 1.784/4.259/18.193 |
| L3 | 0/30/30 | 0.994/0.995/1.336 | 5.847/8.675/16.767 |
| LW | 0/30/30 | 0.996/0.996/0.998 | 8.340/14.389/42.206 |

统一首次发布最长30帧，末尾EOF不足则刷新；真实时间戳不均匀，不能把30帧统一写成1秒，不能称实时部署。四臂共同全段编排耗时1590.908秒，评分耗时1335.394秒，真实exit0。每臂实际FLOW秒数是记录工作量，与同时运行的端到端墙钟不同。

UNKNOWN包括：无独立pre片段、source/generation断裂、未确认分离、共享或混层深度、少量原源点、重复depth timestamp、可靠轮廓不足、无公共历史来源、literal-q GT缺失、三帧参考冲突及弱参考未审查。它们保持UNKNOWN/UNSCORABLE，不改成DEFER模型错误，也不算保护成功。没有新大模型介入。

## 8. 失败机制的实际证据和解释边界

性能增益与退化的逐来源完整差值见第3节，阶段原因见RESULTS内reason_counts/fallback_reasons。若深度权重启用却EVENT_RGBD−EVENT_RGB发布和指标没有变化，只能说此固定输入/候选/代价下未产生增量；不能说深度文件全缺，也不能推广为任何深度方法无效。若q候选因实际旧成员/residual占用或后续alias冲突不可提交，则是合法事务/候选范围限制，与depth是否能识别鱼分开。

双端短片段避免累计长链误差，但合并可污染掩码、单体质量和motion；清晰的source连续存在也不认证物理鱼连续。原Z4Q的常驻出生/返回继承和本分支先前修复能继续影响后续状态。观察到何种原因，只能从真实候选、实际选择、stage拒绝、局部回退和封存后GT关系追溯；不按结果滚动调阈值，不用GT回填或选更容易片段。

## 9. 复现、产物与main同步

源码、实际生效参数和所有动态官方数学/二进制依赖在RUNTIME_FREEZE冻结。全部预测/访问/seal、原始来源、真实body/flow、完整状态/alias/epoch、q至cutoff replay和首次发布hash先验收再开参考。测试仅验证协议/状态/数值，不代替完整性能试验；人工先判对或数值先提点都不是启动条件。

解释器 `E:/researchsoftware/anaconda3/envs/D-MOT/python.exe`，CPU本地运行，安装环境与原输入SHA见ENVIRONMENT/冻结manifest。复现需固定DS14原SAM3、原始native/aligned depth/source_index、真实RGB/标定及DS18质量包，另起新目录按同样检查、冻结、完整回放、封存和评分，不覆盖旧seal。报告生成不改科学源码、选择、预测或评分。

公开数值图见visuals/FULL_METRICS.svg和EVENT_TIMELINE.svg；病例使用实际pre/合并/q/确认帧的本地私有RGB和深度，不公开像素或GT raster。真实路径/字节/SHA和复现依赖见PRIVATE_INVENTORY、PRIVATE_VISUALS_INVENTORY.json及private病例索引。原始响应旧实验只读，本轮未读key、不产生provider file IDs。

所有本轮代码、配置、测试、公开日志/预测/指标/报告/数值图由main普通提交和非force push交付；私有像素只登记真实清单。实际提交SHA、origin/main远端ref及关键blob必须在REMOTE_VERIFICATION实读核验，最终回复单列；报告不能用未知或自引用commit代替远端证据。

## 10. 唯一下一步（未启动）

**按本轮真实错误与不可提交事件，对最主要的一种来源或状态瓶颈做单一修复假设，再冻结完整同源复验；保留原Z4Q和全部mask，仅可靠深度证据产生合法新映射时提交。** 具体优先瓶颈由封存后的逐事件诊断确定，不继续使用已证实无作用的门槛而不检查证据，也不在本轮封存版本上滚动试到通过。本轮结束不自动启动另一轮或加入大模型。
