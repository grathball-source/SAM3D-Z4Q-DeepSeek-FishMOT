# DS11 出生重接独立封存复盘

本报告在全量 `SCORING_SEALED.json` 出现后生成。输入仅为已封存出生记录、实际事务/事件、测量缓存、`BIRTH_AUDIT` 的公开对象身份参考及正式指标；未新开 GT 文件、未追加回放或调整冻结方法。全部 105 个非首帧出生查询、两支分支的逐查询状态/候选理由/测量摘要与输入 SHA 见同目录 `POSTRUN_COMPONENT_REVIEW.json`。

## 1. 实际效果与分母

每支分支共记录 **207** 个 segment-first-ever source，其中 **102** 是四段初始帧现有对象，只登记而不关联；真正非初始出生查询 **105**。不能把 207 全部当恢复机会，也不能把 105 当 105 个真实新鱼。

| 分支 | IDF1 | HOTA | AssA | IDSW |
|---|---:|---:|---:|---:|
| 同源 SAM3_NATIVE | 80.97675951 | 79.96405590 | 71.53049876 | 108 |
| F9_RESTORED | 80.97675951 | 80.01204932 | 71.61576345 | 106 |
| R11_RAW | 80.97675951 | 80.01204932 | 71.61576345 | 106 |
| R11_RESTORED | 80.97675951 | 80.01204932 | 71.61576345 | 106 |

出生提交、出生恢复、出生新增错误均为 **0**，独立读取全部 1,471 条已封存预测，确认两支 R11 发布逐帧等于 F9。对 native 的 HOTA +0.04799342、AssA +0.08526469 和 IDSW −2 全来自既有 F9 组恢复；IDF1 未升。本轮没有出生深度增益，也不能把已有组收益归给新增出生模块。工程输入与封存通过不等于该新机制有效。

## 2. 全查询流向：正确候选没有被 9:1 单独挡住

| 非初始查询路径（每支相同） | 数量 | 实际含义 |
|---|---:|---|
| ACTIVE_GROUP_FRAME_BLOCKED | 47 | 未调用出生选择器，保护组事务优先 |
| KEEP_NATIVE / 当前质量或接触不合格 | 55 | 几何模型可保留匿名记录，但当前深度对所有候选共同无信息，禁止提交 |
| KEEP_NATIVE / 当前深度无信息 | 1 | F361/n70，RGB 参考本身不可评分 |
| KEEP_NATIVE / NEW 最优 | 2 | F845/n127、F1015/n138；均保持当前 native |
| 合计 | 105 | 没有 PROPOSED、log9 拒绝正确候选或 STAGE_REJECTED |

105 查询中，81 当前对象有唯一 RGB 轮廓 IoU 身份参考，24 低 IoU/歧义不能评分。只有 **5** 个出生对象同时通过 engine quality、面积≥64、无邻居：未阻断的 3 个是 F361、F845、F1015；另两个 F156/n30、F1805/n194 被组保护阻断。其余 **100** 处于当前质量/接触风险。

55 个明确选择器质量拒绝中，**53 仅有 neighbors**，另 **2** 同时面积<64、engine quality=False、neighbors 非空。该合并 reason 不能直接解释成低检测置信度，也不能解释成测量缺失。

## 3. 候选源为什么少：几何/原始支持、银行身份和可占用性各自缺一不可

每支 105 查询保留 **1,454** 条 absent-candidate 记录，**329** 合格、**1,125** 不合格。理由直方图为重叠计数，同一条候选可有多个原因，不能相加为对象数。

| 候选排除理由 | 条数 |
|---|---:|
| 无连续同版本风险前几何片段 | 812 |
| 无相同窗口原始深度认证片段 | 812 |
| 无实际银行锚点 | 656 |
| 从最后 joint-clean 点到当前的完整间隔不在固定 12 s 范围 | 651 |
| 实际 bank/source/version 不一致 | 98 |
| public 已被任一 alias 声明 | 68 |
| 组 public 保留 | 25 |
| public 当前占用 | 10 |

这里的两类 812 是同一 joint-support 合同的两个方面，不是两批独立损失。保存某个旧 scalar、旧 mask、同整数 native 或同 generation 都不能自动补齐 clean/raw 支持、实际银行版本和未占用所有权。风险后事实保留为匿名证据，未跨风险插入拟合；gap 从真实历史末点计算而非从消失帧重新计时。

## 4. 原生错误可达范围与当前接触证据

正式 native 108 次 IDSW 中，**72** 精确发生在这些非初始 first-ever-source 出生帧，**36** 不在出生第一帧；这是时间/source 账本交集，不是 oracle 可恢复成绩。105 查询中 **51** 至少有一个同鱼历史 RGB 参考，**26** 有当前工程合格的同鱼候选（合计 28 条同鱼候选边）。其中 **25** 的 source 原始身份、pre 全片段、reference 与实际 bank 参考一致；F1000/n137→68 则有同 native 物理身份漂移。

26 个查询全部也是实际 native 出生 IDSW，且 **全部面积≥64、engine quality=True、neighbors 非空**：

- 14 没有 active-group 阻断，但被当前接触规则拒绝。
- 12 被 active-group 全帧阻断，其中 10 是该组最终角色之外的 source，2 属于组的 member/carrier/post。
- 原始 adaptive exclusive core **25/26 usable**；唯一不合格 F192/n39：n=21、fraction=0.125、MAD=44.01184 mm，样本比例与尺度均不合格。
- v2 选择的 core 26/26 usable，但 **retained 只有 24/26**。F165/n34、F192/n39 选 inferred；推断点在本出生合同中仍共同无信息且不得提交。F165 原始 n=22、fraction=0.20952 通过，不能因 v2 inferred 就说原始无样本。

### 26 个有 eligible 同鱼参考的查询：当前原始/retained 支持

| 全局帧/source | 组阻断 | raw n/fraction | raw usable | v2 cohort / usable | 几何片数 / ROI≥16片数 |
|---|---|---|---|---|---|
| F65/n29 | 否 | 42 / 0.9130 | 是 | retained / 是 | 1 / 1 |
| F162/n32 | 是 | 132 / 0.9778 | 是 | retained / 是 | 1 / 1 |
| F165/n34 | 是 | 22 / 0.2095 | 是 | inferred / 是 | 2 / 1 |
| F192/n39 | 是 | 21 / 0.1250 | 否 | inferred / 是 | 1 / 1 |
| F470/n81 | 是 | 25 / 0.2232 | 是 | retained / 是 | 2 / 2 |
| F486/n83 | 否 | 143 / 0.9662 | 是 | retained / 是 | 1 / 1 |
| F746/n117 | 否 | 247 / 0.9611 | 是 | retained / 是 | 1 / 1 |
| F800/n120 | 否 | 126 / 0.6923 | 是 | retained / 是 | 1 / 1 |
| F826/n123 | 否 | 68 / 0.9577 | 是 | retained / 是 | 1 / 1 |
| F961/n131 | 否 | 149 / 0.9371 | 是 | retained / 是 | 1 / 1 |
| F968/n132 | 否 | 151 / 0.9152 | 是 | retained / 是 | 1 / 1 |
| F1000/n137 | 否 | 138 / 0.9928 | 是 | retained / 是 | 1 / 1 |
| F1043/n143 | 否 | 111 / 1.0000 | 是 | retained / 是 | 2 / 2 |
| F1236/n166 | 是 | 64 / 0.9552 | 是 | retained / 是 | 1 / 1 |
| F1280/n168 | 是 | 128 / 0.9922 | 是 | retained / 是 | 2 / 2 |
| F1416/n173 | 是 | 147 / 0.9866 | 是 | retained / 是 | 1 / 1 |
| F1431/n175 | 是 | 132 / 1.0000 | 是 | retained / 是 | 1 / 1 |
| F1443/n176 | 是 | 70 / 0.4545 | 是 | retained / 是 | 1 / 1 |
| F1444/n177 | 是 | 149 / 0.9551 | 是 | retained / 是 | 1 / 1 |
| F1487/n178 | 是 | 115 / 0.9746 | 是 | retained / 是 | 1 / 1 |
| F1501/n180 | 是 | 54 / 0.5143 | 是 | retained / 是 | 1 / 1 |
| F1639/n185 | 否 | 52 / 0.9811 | 是 | retained / 是 | 1 / 1 |
| F1671/n187 | 否 | 127 / 0.9769 | 是 | retained / 是 | 1 / 1 |
| F1705/n189 | 否 | 70 / 0.6087 | 是 | retained / 是 | 1 / 1 |
| F1856/n196 | 否 | 154 / 0.9872 | 是 | retained / 是 | 1 / 1 |
| F1886/n198 | 否 | 73 / 0.8295 | 是 | retained / 是 | 1 / 1 |

**片数边界：**26 个对象中 22 个 exclusive mask 为一片、4 个为两片；23 个只有一个几何 ROI≥16 的片、3 个有两个。overlap 已排除 0–50 个 mask 像素。冻结 `pieces.samples` 是几何 ROI 像素数，不是该片有效深度 n；当前只有整个 ROI 的 n/fraction/MAD，没有每片深度统计或深度图连接资格。因此所有“qualified depth pieces”均为 **UNKNOWN**，不能把几何单片、独占或低 MAD 称作已认证鱼体表面。

这些事实支持继续检验当前接触风险的测量合同，而不支持“25 个必能修”。即使全部数值进入选择器，深度是否偏向正确 public、能否战胜 NEW/其他历史、能否通过 log9、实际原子提交和全段身份指标是否改善，均未在本轮测试。两处有两个同鱼旧 public，仍存在历史片段竞争；公开 GT 关系只用于复盘，不能成为新提取/资格规则。

## 5. 关键查询：拒配、保护范围与历史错误分开

### F845/n127：这是正确拒配，不是门槛过高

当前 mask 唯一 RGB 参考 GT9，IoU 0.967419。两个 eligible 历史候选：n70/public70 的 reference GT26、全 pre 同 GT26；n106/public106 的 reference GT7、全 pre 同 GT7。两者都不是当前 GT9。native 账本确有 68→127 的 IDSW，但正确旧身份 68 没有成为此处合格 absent 同鱼候选；对错误的 70/106 强行选胜者不能修该错误。该帧 lawful preview 仍有 source68→public68；旧 public68 并非未占用目标。其当前物理对象未新查 GT，不能仅凭历史 bank GT9 断言该时刻错鱼；本轮单个新source→未占用public接口也不能解决占用冲突。

| v2 当前联合分解 | geometry log LR | depth log LR | log score（含统一 prior） |
|---|---:|---:|---:|
| NEW | 0 | 0 | −1.09861229 |
| OLD:70 | −2.10686690 | −0.58531538 | −3.79079457 |
| OLD:106 | −0.68138060 | −0.36304712 | −2.14304000 |

NEW posterior=0.704411；NEW 胜最近 runner 1.044428。原始与 v2 retained 当前 median **1196.324890 mm**、MAD **7.995789 mm** 完全相同；全帧对象 null 略不同，raw 两条 depth LR 为 −0.594980、−0.373135，仍 NEW。当前 query 保存的旧 profile 7×7 core/whole 统计不是本轮 adaptive association 观测，不能混写。n70/n106 真实历史跨度仅 0.199/0.166 s，完整 gap 4.585/3.422 s，depth scale 达 346.433/309.943 mm；规范化模型对宽模型惩罚是机制事实，不能据此按本例答案缩尺度。

### F1015/n138：没有 active group，当前对象不能评分

真实事务 `active_event=None`，状态 KEEP_NATIVE/NEWbest，不能把它放入 activegroup 漏恢复表。当前 mask 参考 best IoU=0，身份 **UNKNOWN**；raw 与 v2 retained median=1164.533936、MAD=1.676025 mm 相同。候选 68 的近风险前 reference 是 GT1、实际 bank 原锚点是 GT9，source 原始与近 reference 已 DIFFERENT，虽然 native generation/public epoch 没变。其 geometry LR +0.492791、depth LR −0.854982，合计仍负，NEW 胜。该例揭示银行版本合法与物理同鱼认证的区别，不能把 UNKNOWN 当恢复成功或失败。

### F156：n30/n31 确实是组外，但放开组外不能证明收益

全局 F156 对应 local157，active `MS1-F155`（members 2/16，carrier2，尚无 q/post）。n30、n31 都在组外。n30 quality=True、area332、neighbors=[]、当前参考 GT7；eligible 候选4/8/12的参考分别GT4/8/12，都不同鱼。n31 area51、quality=False、neighbors=[11]，当前 RGB 参考不可评分。全帧阻断确实扩大了范围，但这两条不是已证明存在合法正确候选的干预机会。

### F1805/n194：这是当前组真正 post，不能当组外放开

全局 F1805 对应 local605，active `MS1-F572`，members149/151，carrier151，实际 q/post 为194/151。n194 当前参考GT19，正确同鱼 public149 被 GROUP_PUBLIC_RESERVED 排除；这正属于保护事务写集。剩下 eligible 候选119/125/178分别GT15/6/5，都不同鱼。出生组禁止与旧 F9 H0/fallback 是不同判定路径；不能让出生模块绕过组原子事务去抢 public149。

47 个被阻断出生中，39 在最终 member/carrier/post 之外、8 在内；其中45当前仍有质量/接触风险，只有 F156/n30 与 F1805/n194 几何clean。最终角色集合用于封存后的范围诊断，没有回写决策或利用未来证据作当时资格。

## 6. 唯一下一步候选：当前接触风险的独占传感器核心证据合同

**状态：仅提出，未启动；可证伪假设。**本轮证据支持把一个机制作为下一版：为 first-ever birth 的当前接触对象增加可追溯的 exclusive 原始传感器核心证据路径。过去历史仍必须 joint-clean/raw/same-version；当前接触测量始终匿名，不能写入 pre、延長历史或制造身份连续。

该方向处理 26 例真正候选与当前接触门之间的空交集。25 raw/24 retained 的现有数值支持使它值得验证；它不是简单删 neighbors 或把冻结质量定义改成 True，也不承诺提升。

具体冻结合同应在新源码完成后明确：

1. 保留 engine quality、面积≥64、RAW/retained 来源、独占 ROI 的来源和实际 n/fraction/MAD；绑定 q/source/mask/fact、epochs、当前无共享采样像素等事实。没有像素表面标签时，所谓 source certificate 只认证数值来源和支持，不认证真实鱼体或毫米准确性。
2. 选择器和真实 copy-on-write stage 都复验同一窄范围 source certificate；保留原观察的 neighbors/风险事实，不伪造旧 Bridge.stage 已接受接触。alias/current occupation、exact bank/version、最多两编辑、批量 target 冲突及原 native lifecycle guards 不变。
3. 不放开 active-group 全帧规则，不添加延迟重试、新 trigger、扩大历史或窗口。inferred query 仍共同无信息/no commit；测量15/60 floors、OLD+NEW、归一化 null、均匀 distinct priors、positive depth LR、log9 均保持。
4. 对所有触发一次全量冻结实验；这 26 例只是已曝光的诊断子集，不能只挑它们运行或凭身份参考定义新资格。保留 native/F9/raw/restored 对照和全部失败，无须纯几何晋级门槛。

**增量成功条件：**至少一条真实正确新出生 bank 恢复，且全段 IDF1/HOTA/AssA 超过同源 SAM3_NATIVE、IDSW 不增加；旧组收益、单病例命中、错误配对止损和工程通过都不算新增深度提点。若只放出更多数值但仍 NEW/错配、事务拒绝或全段指标未升，就明确失败，不再用已知答案改门槛。

物理 surface、绝对深度 MM、RGB-D 空间配准均未独立认证。exclusive mask 中的 raw 共识仍可能是背景/别的鱼；source68 证明合法版本也不能保证历史物理身份。以上未知是本机制真实风险，不构成深度理论无效的结论。
