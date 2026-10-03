# DS20 S0证据与实际发布复核

仅复核全部封存数值输入与实际发布，不读GT、指标、RGB或GT raster，不重新关联、修复或改阈值。

MIXED_ISOLATED共有95个自动事件：50个q，45个无q；全部逐例保留。
q选择={'H0': 50}；恢复状态={'LOCAL_FALLBACK_COMMITTED': 50}；S0联合COMMIT=0。这不含另一路原D1事件局部返回。

| 段 | 事件 | q | 无q | 可用顺序 | UNKNOWN |
|---|---:|---:|---:|---:|---:|
| feeding_000000_000199 | 4 | 1 | 3 | 1 | 0 |
| feeding_000351_000555 | 14 | 5 | 9 | 1 | 4 |
| feeding_000701_001060 | 8 | 5 | 3 | 2 | 3 |
| feeding_001201_001906 | 11 | 9 | 2 | 4 | 5 |
| fishsa_development_8400 | 13 | 9 | 4 | 3 | 6 |
| fishsa_validation_2888 | 12 | 7 | 5 | 3 | 4 |
| L3 | 11 | 4 | 7 | 2 | 2 |
| LW | 22 | 10 | 12 | 2 | 8 |

## 数值输入限制

顺序原因：{'VALID_SOFT_ORDER_EVIDENCE': 18, 'NO_SAME_FRAME_PRE_PAIR': 16, 'INVALID_CAUSAL_CLEAN_PRE_SOURCE_BINDING': 13, 'INVALID_OR_MISSING_CURRENT_PAIRED_DEPTH': 3}。联合决定原因：{'INSUFFICIENT_JOINT_ODDS': 5, 'NO_SAME_FRAME_PRE_PAIR': 16, 'INVALID_CAUSAL_CLEAN_PRE_SOURCE_BINDING': 13, 'H0_BEST': 11, 'INVALID_OR_MISSING_CURRENT_PAIRED_DEPTH': 3, 'NO_POSITIVE_ORDINAL_SUPPORT_OR_PREFERENCE': 2}。

前史逐列核验：受影响事件={'GEOMETRY_FRAME_ABSENT': 13}；失败采样字段计数={'GEOMETRY_FRAME_ABSENT': 199}。
这些事实区分深度本身缺测与几何/深度片段、时间、来源版本未对齐；不把历史中存在深度自动认证成可用身份历史。

可用顺序有18例，其中18例仍处在原9:1门槛对应的0.1–0.9弱代理区间。
当前配对深度被拒的实际状态={'POTENTIAL_MIXTURE': 2, 'UNKNOWN': 1}；混合层被保留为观测事实，没有冒充单鱼身份深度。

尺度、真实采样跨度、q间隔、候选ordinal贡献与实际FACT/SHA逐例列于JSON；它们是未标定的噪声/连续性代理，不能当作物理准确率或拓扑上下关系真值。

## 与同轮ACTIVITY_ISOLATED比较

同event且同q共46例，原始选择不同0例；完整当帧实际publisher不同15例。
事件/q或候选源不同的情况单列，不把底座状态差异归为本次ordinal恢复。H0保留自己当前映射，不能算安全或物理正确。

输入原因计数与只读DS19相同=True。确认隔离修复没有同时解决这些前史合同与顺序强度限制。

## 一个下一步

将进入风险前的几何与深度共同合格片段作为同一来源包冻结；两模态共享实际source generation、identity epoch、帧和时间绑定。缺测、混合层与风险仍匿名，不跨风险拼历史，不按GT换锚，不放宽当前门槛。随后仅做一次冻结同源全段验证。

这是数值输入/发布诊断，不是科研PASS或物理恢复正确率；完整指标与独立物理评分由主报告另列。
