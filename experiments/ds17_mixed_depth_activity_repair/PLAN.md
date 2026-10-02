# DS17 混合深度与活动状态修复：冻结前实验计划

## 问题与假设

单个预测 mask 可能包含两个鱼体深度，也可能包含背景或弯曲鱼体。原中位数/MAD可把少数污染层隐藏，且不能识别哪个层属于哪个旧身份。本轮先保留分层分布与来源，在无法归属时拒绝把该观测认证为单体深度；不把分层当成鱼体分割结果。

Feeding 旧DS16原生108次IDSW，原Z4Q/DEPTH_ORDER132次，IDF1只有+0.740046点、HOTA−0.104205点。净多24不是恰有24个新增错误；须逐次分解新增与消除，追到真实alias/D1_DELAYED/BIRTH_REFINE/返回隔离和源批次。DS16零group提交，不归因给新增上下关系模块。旧封存输出可事后诊断，新预测在全部封存前不读参考。

第二个已知工程问题：整bank冻结把 last_seen/contact/partners 也冻结，会制造竞争资格。保持清洁anchor/速度/深度不可变，真实可见source活动继续，失踪member不伪更新时间；group及未定post保持匿名，recent_core不能绕道认证；stage guard验证清洁参考，不因合法活动变化拒绝。

## 六分支

| 分支 | 状态 | mask深度筛选 | 分离选择 |
|---|---|---|---|
| SAM3_NATIVE | 原保存native | 原输入 | 原native |
| Z4Q_FROZEN | 原Z4Q | 原输入 | 原自动D1/出生路径 |
| DS16_ORDER | 只读DS16真实重放 | 原输入 | 原DS16上下关系 |
| ACTIVITY_ORDER | 清洁参考/活动分离 | 原scalar | 同一DS16上下关系 |
| MIXED_ORDER | 同上 | 新混合/来源质量筛选 | 同一DS16上下关系 |
| MIXED_OFF | 同上 | 同上 | 同一候选几何，上下因子0 |

每分支继续自己的真实状态，不修改最终输出文件冒充恢复。NATIVE/Z4Q/DS16逐帧复现各自旧封存。保留所有mask/残片、公开ID同帧一对一、S0先决定后首次发布、局部事务。

## 固定测量

复用原raw depth_mm、source_index、native sensor及原SAM3 masks。whole/core均保留原scalar所用的完整有效像素分布，同时另存排除共享source、去重后的独立来源分布；原scalar中含共享/不可核验来源则UNKNOWN。沿排序深度的相邻差>30mm形成层，所有层记录点数、比例、中位数/MAD、空间bbox/centroid及像素/source-index摘要。30=原15mm噪声下限的两倍，不在本轮搜索。

显著层要求至少16唯一source点、比例至少.2、尺度max(15,1.4826MAD)≤60；两显著层中位数差>max(30,两层尺度和)则潜在混合。质量不足与混合分列。UNKNOWN不会作为候选零成本奖励。单层保持旧scalar数值，不替换为最近/最大层，也不删除污染层伪造测量。

本规则不能可靠检出深度接近/连续双峰或不足20%的污染层；两个层也不能证明两个鱼。分层只提供当前观测质量与支持范围，不填补隐藏鱼深度、不用GT标记哪层归谁。

## 数据、指标、预算

固定原八段共20098帧：Feeding原四段1471、FishSA8400+2888、L3 3710、LW3629。原始深度；不读v3/未来恢复/annotation instance_id。不换SAM3源。Feeding各段身份命名空间分开；旧405帧未单独称新验证。L3/LW弱参考与暴露数据限制保留。

全表 IDF1/HOTA/AssA/IDSW/FP/FN。主比较包括同源NATIVE及原Z4Q；MIXED_ORDER−ACTIVITY_ORDER才是筛选增量，ACTIVITY_ORDER−DS16是共用状态贡献，MIXED_ORDER−MIXED_OFF是上下因子贡献。切换逐次重算、动作物理正确/错误/不可评分、无分离事件、缺测和拒绝原因保留。少IDSW或恢复到旧基线不叫提点。

本地CPU三作业各一线程。新模型HTTP、smoke、服务、训练、SAM3推理、费用均0。必要单测、真实L3与Feeding源切片通过后冻结代码/输入/常数/评分，再直接完成全段。全部预测与访问记录封存后统一原TrackEval评分。不因效果差调参追加版本。失败与零作用也交付main并真实核验远端。
