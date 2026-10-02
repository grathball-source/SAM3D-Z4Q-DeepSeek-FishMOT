# DS17测量与缺测政策复盘

本文件在全部预测封存和统一评分来源记录完成后生成；只读原始测量缓存、封存公开日志与来源摘要。没有新GT像素、预测、参数或API调用。

## 主判定

**实际Birth core的同ROI认证合同FAIL；本轮仍交付真实完整成绩，不能把工程运行通过写成所有关联测量认证通过。** 全部20098帧、181842对象观测中，旧profile core与adaptive证书core的area/n/fraction/median/MAD至少一项不同181226次，覆盖全部20098帧；area不同181221次。whole统计全相同。两种core来自同帧、同原始深度和mask，但旧core固定3像素侵蚀，证书core采用精确L2自适应区域。相对次序的guard_raw与adaptive_raw人口一致；guard_inputs对Birth旧core只是另一ROI的筛选，不能完整认证实际被评分的core。统计相同也不构成像素集合相同的证明。

## 混合与来源质量分列

| 片段 | 观测 | whole潜在混合 | whole UNKNOWN | core潜在混合 | core UNKNOWN | 旧core统计不同 |
|---|---:|---:|---:|---:|---:|---:|
| feeding_000000_000199 | 5332 | 845 | 3254 | 295 | 264 | 5313 |
| feeding_000351_000555 | 5494 | 663 | 2441 | 199 | 296 | 5464 |
| feeding_000701_001060 | 9596 | 1444 | 4467 | 372 | 549 | 9558 |
| feeding_001201_001906 | 18786 | 1689 | 8455 | 819 | 742 | 18776 |
| fishsa_development_8400 | 50271 | 4129 | 4040 | 4365 | 2330 | 50255 |
| fishsa_validation_2888 | 17197 | 563 | 1071 | 927 | 903 | 17076 |
| L3 | 36927 | 104 | 8768 | 118 | 1069 | 36898 |
| LW | 38239 | 1073 | 13586 | 1225 | 4151 | 37886 |

whole潜在混合10510，UNKNOWN46082；core潜在混合8320，UNKNOWN10304。这是测量筛选覆盖，不是两鱼检测准确率。whole来源ownership不合格37220次、独立覆盖/宽尺度质量不合格18410次，两者可与混合重叠。mixed先判混合，故reason互斥计数与各flag非互斥计数必须区分。

原D1 whole门槛可用180727次中新增拒绝55477次；其中混合10472，shared/unverified来源34441。原adaptive core可用170085次中新增拒绝6867次。whole不合格而adaptive core合格44301次，逆向6333次。因此Mixed相对ACTIVITY是混合、来源、覆盖和MAD筛选的组合效果，不能单独归因混合检测。

## 三条路径的缺测语义

- **D1_DELAYED**：whole缺测使query不能进入任何旧ID边，dummy保留，没有某条旧ID边零代价获利。whole缺测还阻断clean_time、运动、面积、anchor、depth_history更新；真实last_seen/contact活动仍继续。这会改变后续候选历史、回接时刻与版本，不只是当前帧删一个depth项。
- **BIRTH_REFINE**：当前、目标及局部幸存者core为必要证据，缺core拒绝。whole为可选反证；`px_z2.py:36`的`if target is None:return None`使缺whole没有explicit target/competitor veto。代价仍来自core，但可失去否决条件。原PLAN的UNKNOWN不得令候选获利预期在此没有得到一般保证，需要公开这一偏离。
- **S0相对次序**：任一pre/post paired core不合格时，全候选ordinal logLR严格0且H0；MIXED_OFF也要求同样paired eligibility。whole不进入次序因子。弱次序保留冻结公式、odds9和正支持准入，不得把H0回退算成物理正确。

## 真实LW案例与有限归因

local F3064/global3063，native133的whole共有278有效pixel，其中8个source与其他mask共享；独立270点、覆盖0.909、无分离显著层，因此拒绝原因为source ownership，而非混合或低覆盖。adaptive core107点、median783.68994/MAD10.01031被认证；Birth实际使用旧core50点、median781.48065/MAD9.18744。MIXED_ORDER和MIXED_OFF都真实提交133→107；ACTIVITY同帧133→120。ACTIVITY当时没有同133→107边，分支既有bank/alias已分化，故只能记录**whole缺失条件下确有新增Birth提交**，不能证明某条同状态whole veto被删除导致此提交。此例不是ordinal独有收益，也不凭全段指标给它物理正确标签。

本轮预测、科学配置、原seal均保持只读。优先下一步是把身份活动与测量质量接口拆开，并为实际Birth ROI提供同ROI来源证书；不在本冻结版本追加搜索或重评分。
