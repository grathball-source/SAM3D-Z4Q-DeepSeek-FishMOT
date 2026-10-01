# DS10 封存后来源与工程边界复核

## 结论

只读复核通过；未发现来源漂移、四枝缺帧、旧选择器复现失效、未来事件证据或未绑定的 kernel 事实。新深度规则实际生效，但完整跟踪主目标未达到。此复核没有读取标签栅格、RGB、v3、GT 源文件，没有调用评分器或重新回放；仅核查封存文件、哈希、公开预测与已封存评分账本。

## 封存、来源与完整覆盖

- 全四段分别 200, 205, 360, 706 帧，共 1471 帧；四枝共 5884 个 branch-frame；每枝 39208 个保留 mask/ID 对。每帧 mask 顺序一致，ID 全为整数且帧内唯一；负 ID 保留，四枝各 0 个负 ID 观测。
- 独立重算 5360 个不同文件的 SHA256；引用检查分项：`{'score_link': 1, 'score_output': 6, 'score_checks_code': 4, 'access': 2, 'old_readonly_lock': 802, 'new_segment_seal': 4, 'new_prediction_artifact': 40, 'frozen_code': 280, 'source_manifest': 12, 'source_artifact': 1527, 'original_source': 2942, 'old_segment_seal': 4, 'old_prediction_artifact': 40}`。每段的 70 项冻结 code/constants/checks 引用、全部 native depth、原 saved prediction/aligned depth、v2 H5 与来源配置、derived 输入和当前 metadata 均匹配 FREEZE。旧只读锁的 802 文件亦完全匹配。
- 4 个 prediction seal、40 个封存预测产物引用、6 个独立评分产物、ACCESS 与 ALL 绑定均匹配；每一行首次发布的 SHA256 共 1471 条均匹配。评分 provenance 中 evaluator 哈希及测试记录与当前代码一致。
- SAM3_NATIVE 的 1471 帧逐项等于原 SOURCE_OLD N0 和 DS9 native；F9_RESTORED 的 1471 帧逐项等于 DS9 J2_RESTORED_DEPTH。比较 frame/global_frame/time/mask/id，未用指标相等替代输出等价。
- 完整 DEPTH_OBSERVATIONS 1471 行与 DS9 做独立递归 typed 比较，objects/adaptive_raw/restored 各 39208 个对象。唯一差异 281 个 dt_max_px（adaptive_raw 133、restored 148），全部是预先冻结的 float32 相邻 nextafter 且 operative threshold 完全相同；最大差 9.53674316406e-07 pixel。完整差异清单保留在 VERIFICATION.json，本报告没有宽松化实际测量比较。其余 n/median/MAD/资格/cohort/source/surface/background/ROI 数值逐字段 exact。

| 原始段 | 帧数 | 三事件枝 state/transaction 行数 | RAW vs F9 改变帧 | restored vs F9 改变帧 |
|---|---:|---:|---:|---:|
| feeding_000000_000199 | 200 | 600 / 600 | 0 | 0 |
| feeding_000351_000555 | 205 | 615 / 615 | 0 | 0 |
| feeding_000701_001060 | 360 | 1080 / 1080 | 0 | 34 |
| feeding_001201_001906 | 706 | 2118 / 2118 | 0 | 0 |

## 全部事件证据与实际生效

- 三事件枝各 30 个事件，其中各 19 个 q（总 57），其余 11 个未形成 q 的事件保留；不是只审核成功或发生改变的 q。独立回查 848 个冻结样本与 1851 个实际 pre 几何观测；1152 个组内观测均不进入 clean depth history。
- frozen 样本 frame≤suspect−1 且 time<q；geometry forecast 引用 1257 个 pre fact 和 12930 个 calibration predictor fact，所有 predictor 严格早于各 target，target≤suspect−1<q。实际 q post 两个来源只取当前 q 首次观测，evidence_max_frame=q。
- robust local-level 共独立核对 266 条真实过去增量；两端 fact/source/time/median/MAD/Δt、截断噪声修正 rate、median diffusion、原 gap prior 下界和最终 variance 均重新计算一致。每个新状态的均值确为最后实际 z，slope=None；legacy WLS 全字段保留。
- 新 KDE 只取当前 q 所有合格、有限且正 median 的对象，按 source 等权，包含 query。共逐列核对 983 个组件事实及 76 个实际 query assignment，fact 中 frame 都等于 q；独立重算 70 个 query-specific 归一化 t4 log density，误差均<1e−12。另 6 个 assignment 属于 3 个 post-pair 不合格 branch-q（raw 的 F1027/F1745、restored 的 F1745），其深度边共同不可用；这些事件保留。所有已使用 role/source edge 共用该 source 的同一 null，没有 query 对应置换或 future q+1 引用。所有 38 个新枝 q 均达到≥3组件，未触发 whole-frame fallback。

| 分支 | q 选择数 | 两 role forecast 状态（38） | 当前合格 KDE 对象数分布 | 与本分支 legacy WLS 均值不同的 role |
|---|---|---|---|---:|
| F9_RESTORED | {'H0': 16, 'H2': 3} | {'WLS_LINEAR_TIME': 20, 'NO_SLOPE_LAST_VALUE': 9, 'NO_HISTORY': 9} | 原 whole-frame null | 0 |
| D10_RAW | {'H0': 17, 'H2': 2} | {'ROBUST_LOCAL_LEVEL': 19, 'NO_SLOPE_LAST_VALUE': 10, 'NO_HISTORY': 9} | {26: 9, 24: 2, 27: 3, 23: 1, 22: 1, 25: 3} | 19 |
| D10_RESTORED | {'H0': 15, 'H1': 2, 'H2': 2} | {'ROBUST_LOCAL_LEVEL': 20, 'NO_SLOPE_LAST_VALUE': 9, 'NO_HISTORY': 9} | {27: 11, 24: 2, 26: 5, 25: 1} | 20 |

下表给全部发生 ROBUST_LOCAL_LEVEL 的真实角色；未修均值的短历史/UNKNOWN 角色仍计入上表，不能声称每个 q 都获得新信息。Δmean 是新均值减同一冻结事实的 legacy 均值，非物理误差。

| 枝 | 原始 q | role | n | legacy μ(mm) | last-real μ(mm) | Δμ(mm) | legacy scale→new scale(mm) |
|---|---:|---|---:|---:|---:|---:|---|
| D10_RAW | 398 | A | 4 | 1083.0098 | 907.7202 | -175.2896 | 325.5654 → 190.4851 |
| D10_RAW | 398 | B | 10 | 1177.9447 | 937.1479 | -240.7968 | 95.6255 → 66.5704 |
| D10_RAW | 415 | A | 3 | 677.1862 | 1065.9806 | 388.7944 | 367.1609 → 84.2779 |
| D10_RAW | 415 | B | 10 | 1019.0332 | 1072.6079 | 53.5747 | 100.4770 → 54.7131 |
| D10_RAW | 434 | A | 5 | 1092.7561 | 1164.4561 | 71.7000 | 190.5427 → 110.9783 |
| D10_RAW | 470 | B | 7 | 1559.6426 | 1174.9204 | -384.7222 | 171.2662 → 68.4934 |
| D10_RESTORED | 398 | A | 4 | 1089.5346 | 907.6278 | -181.9068 | 325.5654 → 190.4851 |
| D10_RESTORED | 398 | B | 10 | 1181.6069 | 937.0115 | -244.5954 | 95.6255 → 66.5704 |
| D10_RESTORED | 415 | B | 10 | 970.0645 | 1132.0656 | 162.0011 | 101.8822 → 75.5231 |
| D10_RESTORED | 434 | A | 5 | 1094.7599 | 1164.4561 | 69.6961 | 190.5427 → 110.9783 |
| D10_RESTORED | 470 | B | 10 | 1987.2708 | 1174.7549 | -812.5159 | 157.5214 → 48.2571 |
| D10_RESTORED | 519 | A | 3 | 1169.2396 | 1163.4443 | -5.7953 | 328.8584 → 85.6239 |
| D10_RESTORED | 519 | B | 10 | 926.4865 | 934.5801 | 8.0936 | 37.3262 → 28.0231 |
| D10_RAW | 764 | A | 10 | 894.4153 | 1073.7120 | 179.2967 | 115.2828 → 52.5758 |
| D10_RAW | 1027 | A | 10 | 940.1368 | 972.2418 | 32.1050 | 50.0499 → 42.3526 |
| D10_RAW | 1027 | B | 3 | 857.5755 | 1017.4977 | 159.9222 | 207.5896 → 99.4746 |
| D10_RAW | 1039 | A | 10 | 1188.7883 | 1188.8915 | 0.1031 | 79.8888 → 55.9035 |
| D10_RAW | 1039 | B | 3 | 878.2795 | 1045.5661 | 167.2866 | 1111.4395 → 238.5307 |
| D10_RESTORED | 764 | A | 9 | 925.1862 | 1072.6057 | 147.4195 | 116.9575 → 57.2543 |
| D10_RESTORED | 1027 | A | 10 | 936.4055 | 968.1923 | 31.7868 | 46.4880 → 37.6183 |
| D10_RESTORED | 1027 | B | 10 | 795.8316 | 1017.4977 | 221.6661 | 64.4051 → 31.7929 |
| D10_RESTORED | 1039 | A | 10 | 1189.1216 | 1188.8915 | -0.2301 | 79.9227 → 55.9035 |
| D10_RESTORED | 1039 | B | 3 | 878.8091 | 1044.7256 | 165.9165 | 1069.8700 → 238.1849 |
| D10_RAW | 1239 | B | 7 | 1111.5889 | 1155.7309 | 44.1420 | 78.7643 → 49.5309 |
| D10_RAW | 1390 | A | 8 | 1224.4474 | 1132.5797 | -91.8676 | 150.8596 → 66.7678 |
| D10_RAW | 1504 | A | 6 | 1252.0218 | 1172.9958 | -79.0259 | 577.7205 → 366.9387 |
| D10_RAW | 1719 | B | 10 | 1185.1779 | 1172.6409 | -12.5371 | 65.0380 → 45.7005 |
| D10_RAW | 1745 | A | 10 | 853.8694 | 855.9371 | 2.0677 | 63.7971 → 45.3065 |
| D10_RAW | 1745 | B | 10 | 1026.7704 | 1108.4567 | 81.6863 | 94.9544 → 56.7868 |
| D10_RAW | 1805 | A | 10 | 1115.7389 | 1140.8521 | 25.1132 | 249.5355 → 86.1867 |
| D10_RAW | 1805 | B | 7 | 1004.8009 | 953.8894 | -50.9115 | 176.8533 → 107.4600 |
| D10_RESTORED | 1239 | B | 7 | 1110.9196 | 1155.4020 | 44.4824 | 78.9483 → 49.6184 |
| D10_RESTORED | 1390 | A | 8 | 1228.6257 | 1132.5760 | -96.0497 | 149.7002 → 66.6790 |
| D10_RESTORED | 1504 | A | 6 | 1238.5693 | 1172.2081 | -66.3612 | 577.7205 → 366.9387 |
| D10_RESTORED | 1719 | B | 10 | 1184.9540 | 1172.4481 | -12.5059 | 65.0246 → 45.7526 |
| D10_RESTORED | 1745 | A | 10 | 853.6236 | 855.9371 | 2.3135 | 63.7971 → 45.3065 |
| D10_RESTORED | 1745 | B | 10 | 1027.8114 | 1108.4567 | 80.6453 | 94.8748 → 56.7868 |
| D10_RESTORED | 1805 | A | 10 | 1124.4185 | 1139.9512 | 15.5327 | 252.5464 → 86.3007 |
| D10_RESTORED | 1805 | B | 7 | 1027.1055 | 949.1839 | -77.9216 | 166.1986 → 107.3430 |

## 已封存官方指标与完整切换账本

指标取已封存 METRICS.json；本复核没有重评分。pooled 是完整帧集合加段内 identity namespace 的直接 TrackEval，不是段指标平均。IDSW/FP/FN/GT/predictions 的 pooled 整数均独立核实为分段之和。

| 枝 | IDF1(%) | HOTA(%) | AssA(%) | IDSW | FP / FN |
|---|---:|---:|---:|---:|---|
| SAM3_NATIVE | 80.97675951 | 79.96405590 | 71.53049876 | 108 | 487 / 985 |
| F9_RESTORED | 80.97675951 | 80.01204932 | 71.61576345 | 106 | 487 / 985 |
| D10_RAW | 80.97675951 | 80.01204932 | 71.61576345 | 106 | 487 / 985 |
| D10_RESTORED | 80.89058976 | 79.89084769 | 71.40121276 | 108 | 487 / 985 |

D10_RAW 全部 1471 帧等于 F9：IDF1 与 native 相同，HOTA/AssA 的小增量和 −2 IDSW 是已存在旧 F9 行为，不能算本轮联合深度修复新增收益。D10_RESTORED 相对 F9 只改变 34 帧，逐行实查 prediction.global_frame 为原始 F1027–F1060（第三段 local frame 327–360）；三 rate 下降且 +2 IDSW。相对 native 三 rate 均下降，IDSW 相同。冻结的 native 三 rate 严格提升且 IDSW 不增加的目标为 false。

| 枝 | 各段 IDSW（0/351/701/1201起段） | ledger 条数 | 与 native 全 tuple 比较移除 / 增加 |
|---|---|---:|---|
| SAM3_NATIVE | 10 / 22 / 36 / 40 | 108 | 0 / 0 |
| F9_RESTORED | 10 / 22 / 36 / 38 | 106 | 3 / 1 |
| D10_RAW | 10 / 22 / 36 / 38 | 106 | 3 / 1 |
| D10_RESTORED | 10 / 22 / 38 / 38 | 108 | 3 / 3 |

每个切换 ledger 项均唯一；local/global frame、native mask 和 to_public_id 与该枝实际首次发布的预测一致；每段及 pooled 条数严格等于封存官方 CLEAR IDSW。下列是 native 对照的全部不同 switch tuple（tuple 含段/frame/gt/native mask/from/to，所以不能把它直接当净新增错误数）：

| 枝 | 相对 native | 原始 frame | GT参考ID | native mask | from→to public |
|---|---|---:|---:|---|---|
| F9_RESTORED | removed | 1239 | 4 | n:167 | 136 → 167 |
| F9_RESTORED | removed | 1347 | 4 | n:170 | 167 → 170 |
| F9_RESTORED | removed | 1745 | 2 | n:190 | 188 → 190 |
| F9_RESTORED | added | 1347 | 4 | n:170 | 136 → 170 |
| D10_RAW | removed | 1239 | 4 | n:167 | 136 → 167 |
| D10_RAW | removed | 1347 | 4 | n:170 | 167 → 170 |
| D10_RAW | removed | 1745 | 2 | n:190 | 188 → 190 |
| D10_RAW | added | 1347 | 4 | n:170 | 136 → 170 |
| D10_RESTORED | removed | 1239 | 4 | n:167 | 136 → 167 |
| D10_RESTORED | removed | 1347 | 4 | n:170 | 167 → 170 |
| D10_RESTORED | removed | 1745 | 2 | n:190 | 188 → 190 |
| D10_RESTORED | added | 1027 | 1 | n:137 | 137 → 95 |
| D10_RESTORED | added | 1027 | 25 | n:95 | 95 → 137 |
| D10_RESTORED | added | 1347 | 4 | n:170 | 136 → 170 |

## 解释与输入边界

- 新错误发生在 F1027：source n:137 的 adaptive raw ROI 有 88 像素，62 个有效值（0.704545），median=1120.846252mm、实际 MAD=42.935547mm；n/fraction 均通过，因 1.4826×MAD≈63.66mm>60mm 拒绝，故 raw post pair 不合格、used_edges=0、H0。v2 同一 ROI 的 retained 62 点仍拒绝，转选 inferred 20 点（0.227273），median=1172.022705mm、actual_selected_mad=0.213257mm；实际传入 core.mad=40.469445569 是适配到假定 sigma≈60mm 的有效值，不是实测 MAD。provenance_counts 为 0:6、1:62、2:20、3:0。v2 post pair 合格后 used_edges=4、选择 H1 并真实 COMMIT；不能把这次来源变化描述成旧 fixed-7 core 完全无样本。
- 同一 F1027 B 历史 raw 只有 3 点（span≈0.067s），v2 有 10 点（span≈0.299s），最后 z 均为 1017.497681mm、到 q 缺口≈0.432s；原 gap process 下界分别 9579.096931 与 694.686292mm²。v2 10 点中包含过去 inferred 点，噪声修正增量 median 为 0，仍保留原过程下界。观测资格使历史跨度改变，并不证明该历史属于同一物理表面或具有对应的时间置信度；这属于输入及未校准代理的限制，并非本轮漏运行预测规则。
- 预测进程访问审计绑定 1471 次 NPZ 字段读取，仅 depth_mm/source_index；没有直接读取 GT/RGB/v3 或访问网络。扫描/来源/时间索引有预加载，因果声明仅适用于关联使用的实际 frame/time，不能扩大为从未读过任何未来文件 bytes。
- restored 是原已曝光 native-v2，包含上游 RGB 和未来清理支持；在 q 取当前 depth observation 不会把该上游来源变成在线纯因果深度。raw 与 restored 结论须分列。
- kernel 的 core_usable 只代表统计资格；并非鱼体深度表面所有权的证明。query 被包含于拟合 null，t4 likelihood/posterior 是条件 plug-in 对比，未校准为 Bayesian 身份概率；尺度与 diffusion 也是代理，不能称物理毫米精度改善。
- EVENT_AUDIT 的 physical/anchor/expected mapping 是现有 RGB polygon 在 actual bank anchor 的身份参考。它不是深度表面或物理 depth GT；无法双射、无 q、未确认、进入前错误、not staged 仍保留。CORRECT 同时包括 COMMIT 与 RESOLVE_NO_ID_CHANGE；报告实际纠错时只能引用 correct_commits，并另列无 ID 改变的正确解析。
- 本轮 mean 与 null 联合改变，四臂不能识别各自独立贡献；raw 与 F9 输出相同也不能推出深度理论无效。此处仅给实际工程验收和冻结目标判定，不引入新实验、阈值搜索或评分补丁。

封存锚点：

- ALL_PREDICTIONS_SEALED SHA256：`f6202c2e0cf696612ae71e743925850f1be80bd1b6ee35e196aee65584ad52e4`
- SCORING_SEALED SHA256：`ee7c6bbebbc0a05088f83c8ff40acae0cc78ec0379e9eb8cee20517bb9fb4bce`
- METRICS SHA256：`5723acc98afe77cbe8f28aa632b6377230b616a965b7f9c70353e1ef413d4b6e`
- VERIFICATION SHA256：`5ad5bf732bee09130543ccefa8b7bba7b7677cf6983782a69c0848373f0661b9`
