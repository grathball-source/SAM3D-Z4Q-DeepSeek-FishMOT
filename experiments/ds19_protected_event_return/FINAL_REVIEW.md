# DS19 最终复盘：局部止损成立，深度提点未成立

## 主判定

**COMPLETE_TRIAL_PENDING_ISOLATION_GAP_DEPTH_GOAL_NOT_ACHIEVED**。一次冻结正式试验已完成八段六列，每列20098帧，共120588列帧。L3追回原Z4Q被保护逻辑挡住的恢复；没有新增超过原Z4Q的稳定深度收益。当前版本封存停止，不追加参数或选择更容易事件。

源、ROI、真实标量、版本、测量证据绑定、唯一发布和旧对照复现均通过；19项冻结前单测通过。评分后发现未accepted保护候选覆盖事件目标集之外普通候选的pending，完整确认隔离合同未通过。源与已accepted事务检查的PASS不能掩盖此工程缺口。正式完整数字结果保留为该实现的实际表现，不将它升级为无工程混杂的顺序方法有效/无效证明。

## 完整指标与主要比较

六列八段的IDF1/HOTA/AssA/IDSW/FP/FN及全部差值见 RESULTS.md、run/METRICS.json。下表为预先指定MIXED_RETURN；不能事后择优改为ACTIVITY_RETURN。百分指标差值单位为百分点。

| 数据 | IDF1 | HOTA | AssA | IDSW | FP | FN | IDF1−同源SAM3 | IDF1−原Z4Q | IDF1−ACTIVITY_RETURN |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Feeding_pooled1471 | 81.245406 | 79.510342 | 70.726688 | 129 | 487 | 985 | +0.268647 | -0.471399 | -0.656411 |
| fishsa_development_8400 | 99.244072 | 77.750512 | 77.749014 | 8 | 194 | 323 | +7.930784 | -0.089400 | +0.031787 |
| fishsa_validation_2888 | 80.413685 | 68.954661 | 59.571269 | 11 | 298 | 423 | +3.957241 | -0.283902 | -0.278108 |
| L3 | 74.745256 | 77.171558 | 98.839045 | 2 | 14677 | 0 | +2.318468 | +0.000000 | +0.000000 |
| LW | 60.613534 | 66.362048 | 77.538718 | 9 | 16493 | 28 | +0.000000 | -3.715862 | +0.000000 |

Feeding主表是四段1471帧独立ID域汇总；其他数据分别报告，不跨数据集混成一个总分。当前所有六列mask/count相同，FP/FN也实际相同。L3/LW参考是未经独立验收的预测派生预标注，不能称新盲测或物理深度真值。

## 本轮实际修了什么

受保护目标的原始D1候选在私有proposal中继续自然矩阵、margin、出生窗和5次确认。只有自然accepted、来源/版本/anchor/占用/组外写集检查通过后，才以事件局部事务提交真实alias、bank与epoch；进入参考仍不可变，未恢复成员保持匿名。late q、timeout、局部fallback不复制整套B0，不撤销已提交恢复。当前帧先commit再唯一发布，过去已发布的新号不改写。

该子范围要求来源独占、无当前邻居，实质覆盖D1；原Birth需要邻居见证，尚未由本路由覆盖。未accepted确认不是身份提交。测量、深度筛选、顺序、阈值、触发、q、二维运动和原输入保持冻结。

## 三笔显式局部返回，两件来源事件

| 数据/分支 | 原帧 | 来源→public | 相对首次来源发布延迟 | bank物理 | 公共ID原来源 |
|---|---:|---|---:|---|---|
| L3/ACTIVITY_RETURN | 3024 | 47→9 | 134帧 | CORRECT | CONSISTENT_PUBLIC_ORIGIN |
| L3/MIXED_RETURN | 3024 | 47→9 | 134帧 | CORRECT | CONSISTENT_PUBLIC_ORIGIN |
| LW/ACTIVITY_RETURN | 3271 | 144→133 | 4帧 | UNSCORABLE | UNSCORABLE_PUBLIC_ORIGIN |

L3 local3025/原3024：旧n9@local2712 whole=722.703186 mm，当前n47 whole=678.225586 mm，残差44.477600/tol60 mm，cost0.748384，原D1自然5次确认。n47首次公开于local2891为47，134帧后恢复9，跨local3175 TIMEOUT继续自身alias。完整IDF1 +2.318468/HOTA +1.808950/AssA +4.579391；IDSW却+1，因此不能用切换净数替代全段身份一致性。两分支均等于原Z4Q，是共同事务止损；MIXED−ACTIVITY=0。

LW ACTIVITY_RETURN的144→133在原3271提交，实际旧参考与当前观测均无法唯一匹配，维持UNSCORABLE。IDSW9→8而IDF1不变不能使该例变为正确。所有显式返回均为D1，不与automatic重复计数。

## 为什么深度没有产生联合恢复

MIXED_RETURN自动95个episode中50个q、45个没有q；episode包括取消/超范围，不能全称真实合并事件。50个首分离决定全为H0+本分支fallback，实际ordinal joint COMMIT=0。32个UNKNOWN：16无同帧pre配对、13因果clean pre绑定拒绝、3当前paired depth缺失/非法。18个可用顺序均为未校准弱代理：11个H0本来最佳，5个joint odds不足，2个无正ordinal支持。

真实冻结值：Feeding最早q原170，pre仅一对，Δ=-42.778 mm、gap1.396 s，外推scale897.884 mm、p0.482142，H1 margin0.089251低于原log9=2.197225。开发q1274，Δ=-101.718 mm、gap9.596 s，scale6168.712 mm、p0.493817。尺度随间隔迅速变宽，使次序接近无信息；这是当前连续性/噪声模型行为，不证明真实鱼体上下关系变化，也不是物理准确率。

保留匿名GROUP混层资料不等于已把它用于有效个体顺序约束；整mask/core中位数顺序仍可能与接触处局部遮挡拓扑不同。这一轮没有更换表示或调尺度。PRE_PAIR_DIAGNOSIS逐字段保留实际拒绝原因，不将窗口缺口或真实风险强写为clean。

13个INVALID_PRE实际逐列失败都是GEOMETRY_FRAME_ABSENT，共199个历史点缺对应几何记录；11例在前次取消/回退/完成清空manager几何后，DepthState仍保留同key深度片段；2例风险后两种片段错位。这不等于13例深度源本身错版。16个NO_SAME_FRAME均为被选入最新A/B深度片段真正不共时，其中14例连几何也不共时，2例几何共时但深度片段不共时。不能跨风险拼接，也不能以GT挑更早好片段。

第二层审查区分真实风险与表示损失：两例风险后的错位来自实际POTENTIAL_MIXTURE被mixed门拒绝，旧深度不能与新几何拼接；另一方面Feeding MS1-F105和验证MS1-F457曾存过同帧合格历史，却被A/B各自较晚的不共时latest片段覆盖。按时间因果记录共同片段是尚未实现的表达问题，本轮不重选旧输入，也不据此预报新成绩。

fallback首次发布相对bank为30正确/10错误/10不可评分；相对pre片段共识为16/5/29。这些是原发布诊断，不是模型或ordinal提交成绩。五数据最早未恢复H0控制均生成真实深度/全部邻mask六列前中后图，没有错误joint提交可选，失败提交图为0；不补造失败。

## 未提交也会影响状态：确认竞争

Feeding local193，n38→保护16的count1写回pending，覆盖普通n38→7的count3；ORDER在local195正常接7，RETURN只有count2，195–200六帧仍发布38。它只有HOTA微变、没有显式local_return，不能算恢复收益。

LW local949–952，n32→保护7的确认反复覆盖普通目标24，导致ORDER在952接24、RETURN到957才接24，五帧差异而完整指标相同。只检查显式提交数会漏掉该副作用。逐次新/消除切换、共同帧转移变化和真实pending链见POST_SCORE_INTERPRETATION_REVIEW.json及POSTSCORE_SUMMARY.json。

## 耗时、复现与交付边界

正式六列回放2546.204秒；完整来源检查与评分2019.346秒。本地最多六个单线程片段作业，CUDA空；不代表实时部署。模型HTTP/smoke/训练/SAM3推理/补全服务/费用全部0。

旧5618个锁定文件未改，82冻结依赖与123正式封存文件完整。八段事务11块，最大73438610 bytes；完整记录不截断。SOURCE_OLD、原depth_mm/source_index与同源SAM3保存源及DS18封存当帧测量缓存均保留真实依赖。

初始化曾直接执行并成功，ENVIRONMENT_INITIAL与CONFIG_INHERITANCE保留；不伪造不存在的初始化stdout日志。冻结前第一次测试的序列化错误与后续成功记录保留。正式回放/评分一次通过；仅封存后控制绘图曾因无序读取失败，排序后重跑，日志及可反向核验的诊断源码副本见DIAGNOSTIC_RENDER_REPAIR。TrackEval可选BURST导入提示缺tabulate不影响本轮官方CLEAR/Identity/HOTA，旧四对照逐帧和数值完全相同。

公共交付包括代码、配置、测试、完整数字预测/事务/调用与耗时记录、逐事件评分、报告和聚合指标图。实际深度/mask图与原始私人输入仅列RESTRICTED_ARTIFACTS真实路径、字节、SHA和复现依赖，图不进入Git；不公开RGB、GT raster或凭据。远端提交/ref/blob结果写REMOTE_VERIFICATION，最终main在交付后再次实际核验。

## 唯一下一步

隔离受保护边与普通候选的确认进度，使未accepted事件proposal不能覆盖普通pending；保留原矩阵/阈值/出生窗与自然接受，再做一次同源冻结验证。具体范围见NEXT_STEP_PLAN.md。本轮没有执行该下一轮，没有自动加大模型。
