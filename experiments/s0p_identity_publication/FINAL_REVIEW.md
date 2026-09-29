# S0-P：身份发布与事件局部回退，开发集 8400 帧结果

## 分层判定

**共用跟踪机制工程收益成立；新的 VLM 增量未测试。** 最终 HOLD-P 在原开发集全 8400 帧以自身状态连续回放，IDSW **实测为 2**，相对原 B0 的 6 减少 4，相对旧封存 HOLD 的 18 减少 16。IDF1/HOTA/AssA 同时提升；FP/FN 不变。最初全段尝试暴露一个仍会发布未决 H1 预览的工程错误，初次 seal 和评分均保留；修正后重新全段封存、再独立评分。因为是在已曝光开发集上作工程纠错，这些性能数字不能视作前瞻、盲测或模型能力证据。

## 改了哪一处真实输出行为

原状态机把合并期间的内部匿名残片 `-1000000` 类 token 当成公开持久 ID。F2145 真实故障切片中，原 `n:4` 的公开 ID 在 F2144/F2145/F2146 为 `4→-1000001→4`，F2146 事件取消。修复后实际首次发布为 `4→4→4`；掩码集合和顺序未变，过去帧未改写。[F2145_SLICE.json](F2145_SLICE.json)与[前中后图](figures/F2145_cancelled.svg)记录原、B0 和 HOLD-P 的逐帧公开映射。

`OutputIdentityPolicy` 仅对同一 native source 连续存在、上一公开标签唯一且未占用的成员延续标签。匿名 group/residual 仍是内部证据类，不能进入个体 clean 历史；单个 group mask 只发布一条轨迹，另一个旧身份保留在 bank。真正新出现或发生占用冲突的残片使用记录明确的本地未决标签，不删除 mask，不在评分中忽略负数。合并载体改变时，连续可见的另一个成员先占用其上一公开 ID。事件 trigger、q、pre 参考和数值 `1.0/0.25/0.25` 权重均未调整。

当 q 的配对无法 stage 时，`GroupBridgeP.local_fallback` 从**当前 HOLD-P 分支**生成同帧因果候选，只允许事件 native/public 写集进入当前 `view.engine`。外部 bank、alias、epoch、provenance、previous 不取 B0 整套快照。若目标 bank 被组外 alias 依赖等情形挡住，记录 `LOCAL_FALLBACK_UNRESOLVED`，清理本事件保护，并首次发布当前分支上一帧合法、唯一的连续标签；不把仅用于检查占用的临时 H1 当成已作出的决定。F4519 和 F5927 两次均按此未决路径继续，F5927-S0 的原模型 HTTP 结果仍为 **UNKNOWN**，没有被改写成 DEFER、错误或正确。

## 完整指标

先验证 8400 帧 seal、逐帧唯一发布、每行 SHA、输入哈希和原 B0 归档一致性，之后才打开已曝光 GT。使用原 TrackEval、原 IoU 0.5 规则和所有预测 mask/ID。表中 IDF1/HOTA/AssA 为百分数，差值为百分点。

| 分支 | IDF1 | HOTA | AssA | IDSW | FP | FN |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| B0 原 Z4Q，独立重放 | 99.333472 | 77.829488 | 77.907638 | 6 | 194 | 323 |
| OLD-HOLD，原 V7 封存恢复回放 | 99.317579 | 77.848487 | 77.947244 | 18 | 194 | 323 |
| **HOLD-P，本轮修复** | **99.474526** | **77.953763** | **78.157296** | **2** | **194** | **323** |
| HOLD-P − B0 | +0.141054 | +0.124275 | +0.249658 | −4 | 0 | 0 |
| HOLD-P − OLD-HOLD | +0.156947 | +0.105276 | +0.210052 | −16 | 0 | 0 |

OLD-HOLD 与本轮 B0 都重新用同一 IoU 矩阵评分，并分别与旧封存指标及归档 B0 完整指标核对；没有重新运行旧 HOLD 状态或重问模型。HOLD-P 相对 B0 有 78 帧公开 ID 不同，相对旧 HOLD 有 155 帧不同。完整精度见 [METRICS.json](run_8400_v2/public/METRICS.json)与[评分来源](run_8400_v2/public/SCORE_PROVENANCE.json)。

## 每次切换与事件结论

[SWITCH_AUDIT.json](run_8400_v2/public/SWITCH_AUDIT.json)按原 CLEAR 匹配规则逐条列出 GT、帧、from/to、native mask、IoU、事件与状态。旧 HOLD 独有的 **16 次**负临时 ID 进入/退出均消失，其中 F2145、F5303、F6052 三个随后取消的事件合计消除 6 次。B0 的四次切换 F1274/F1327 与 F8035/F8054 仍被保护机制消除。本轮 **没有新添相对 B0 的切换**；剩余 2 次与 B0/旧 HOLD 共有：F5933 的 GT1 `0→1`（`n:1`，IoU 0.5891），F5939 的 GT1 `1→0`（`n:7`，IoU 0.9238）。因此 `6−4=2` 是封存后逐条核算的实测关系，并非执行前预设。不能把这两次共享切换解释为已解决的 F5927 物理身份；该事件进入前参考缺失。

预测扫描仍启动 13 个事件，4 个取消、9 个到达首次分离 q；7 个完成数值配对、2 个保持 `LOCAL_FALLBACK_UNRESOLVED`。所有 q 的证据仅到首个分离帧，post 各 1 点，post 速度依旧 UNKNOWN。q 帧先 stage/commit 或局部未决选择，后由唯一 append-only publisher 首次发布；各 q 的 publish ledger 只有一条哈希绑定记录。此离线 CPU 回放 q 帧接收到首次发布约 0.015–0.016 秒，不含 API 等待，不能称实时部署。[最早确认事件图](figures/F1152_first_confirmed.svg)展示 F1151、合并确认 F1153、首分离 F1274、F1275 三分支的真实发布标签，内部 token 与公开 ID 分栏。图只画来源 bbox 中心，不含像素或 GT raster。

首分离帧的**物理**核验独立于整段公共标签分数。当前参考的进入前末端锚点可评分 7 例，7 例所选数值配对正确；2 例不可评分。要求同版本连续至少 3 条已知观测的进入前片段共识可评分 4 例，4 例正确、5 例不可评分。两次未决不计为正确。直接 q GT、进入前末端、进入前共识和 q 后至多 10 帧的事后共识分别列在 [PHYSICAL_EVENT_AUDIT.json](run_8400_v2/public/PHYSICAL_EVENT_AUDIT.json)。公共 ID 改善不等同于新模型正确恢复物理身份。

本轮真实组外状态核验覆盖所有 **299 个 active 事件帧，299/299 逐域完全一致**：同帧自然预览与实际分支中，当前可见组外对象的 bank/view_bank、alias、pending、source run、epoch、provenance、previous 等相同。[OUTSIDE_STATE_AUDIT.json](run_8400_v2/public/OUTSIDE_STATE_AUDIT.json)保留逐帧比较摘要；合成例还验证 native/public 整数键碰撞、组外 native99 先前的分支修复和零 delta 提交不被组内失败覆盖。此结果证明本次实际回放没有整场 B0 reset 的组外状态污染；未逐项枚举未出现的所有 dormant 对象。

## 初次封存尝试、测试与调用边界

第一次 8400 帧回放同样 13 事件、0 新 HTTP，评分为 IDF1 99.466579、HOTA 77.941077、AssA 78.144324、IDSW 8、FP194/FN323。事后逐次切换揭示两个未决 q 把内部 H1 预览发布一帧，下一帧恢复连续公开标签，额外产生 6 次切换；这是无须 GT 身份判定即可复现的发布合同缺陷。首次结果、seal、score 与匹配冻结 SHA 的三份源码均保留在 `run_8400/` 和 `attempt1_source/`，没有覆盖。修复只在通用未决发布逻辑延续上一帧唯一标签，没有帧号或 GT 分支，也没有调整阈值、锚点、数值权重、prompt 或案例选择；第二次全段运行在 `run_8400_v2/`。由于修复发生在第一次 GT 评分之后，最终指标应按**暴露开发集上的工程回归结果**解读，不能宣称预注册的盲测提升。

五项直接单测、F2145 真实前缀、8400 帧归档 B0 完全一致、所有 mask 与顺序一致、每帧唯一公开 ID、q 发布唯一性、独立物理来源重放、299 帧组外状态检查均通过。mock H2 测试验证预览未写出，publisher 只首次写一条 H2，二次写同帧拒绝。原 S0 输入生成链及 q 截止规则未改；改变 q 之后数据不能改变已封存 q 决策。[TEST_REPORT.json](TEST_REPORT.json)和[ACCEPTANCE.json](run_8400_v2/public/ACCEPTANCE.json)列出证据。

原 V7 paid 试验的 16 START、15 END、F5927-S0 开始后未知没有变化；原恢复回放新增 0 HTTP。本轮所有新调用记录为空，**新推理 HTTP=0、新费用=USD 0**。旧模型 7 个有效返回与数值相同的历史事实保留，但本轮没有新模型调用、没有把旧 H1/H2 硬套进已改变状态，也没有“新 B-VLM”指标行。VLM 接口仍由原 stage_group_restore 和 prompt/packet 路径保留；共同机制的增益不能归因于 VLM。

## 受限数据、复现与唯一下一步

[RESTRICTED_INVENTORY.json](run_8400_v2/public/RESTRICTED_INVENTORY.json)逐项列出 OBS、深度 profiles、ASSIGN mask 数据、v4 触发扫描、归档 B0、已曝光 GT、native-to-GT 匹配与本轮私有 q 参考快照的**实际绝对路径、字节数和 SHA256**。需这些同 SHA 文件、仓库冻结源码及原依赖环境才能复现。Git 只含公开数值、轨迹 ID、几何中心、SVG、测试和日志；无凭据、provider file ID、私有 RGB、API wire 或 GT raster。原零事件试跑的历史源码覆盖限制无法精确消除，本轮未伪造其旧 freeze。

**下一步：** 在新的、事先封存且可评分的事件集上仅复测这套共用发布/局部回退机制，按进入前物理身份与整段公共 ID 两层分别验收，再决定是否需要新的 VLM 介入实验。
