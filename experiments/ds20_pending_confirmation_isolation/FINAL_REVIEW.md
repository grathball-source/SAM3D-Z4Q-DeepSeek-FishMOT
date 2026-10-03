# DS20 最终复盘：确认状态隔离与深度增量分列

主判定：**COMPLETE_CONFIRMATION_REPAIR_DEPTH_GOAL_NOT_ESTABLISHED**。

完整八段六列，每列20098帧，所有预测封存后统一评分；四个归档控制逐帧及完整指标精确复现DS19。
实际确认状态隔离审计覆盖40196个新分支帧，比较真实提交后字典、版本、精确anchor、普通优先级与publisher。工程通过不能替代深度增量或物理身份正确性。

## 主分支完整指标

| 数据 | IDF1 | HOTA | AssA | IDSW | FP | FN | IDF1−同源SAM3 | IDF1−原Z4Q | IDF1−旧MIXED_RETURN | IDF1−ACTIVITY_ISOLATED |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Feeding_pooled1471 | 81.245406 | 79.510342 | 70.726688 | 129 | 487 | 985 | +0.268647 | -0.471399 | +0.000000 | -0.656411 |
| fishsa_development_8400 | 99.244072 | 77.750512 | 77.749014 | 8 | 194 | 323 | +7.930784 | -0.089400 | +0.000000 | +0.031787 |
| fishsa_validation_2888 | 80.413685 | 68.954661 | 59.571269 | 11 | 298 | 423 | +3.957241 | -0.283902 | +0.000000 | -0.278108 |
| L3 | 74.745256 | 77.171558 | 98.839045 | 2 | 14677 | 0 | +2.318468 | +0.000000 | +0.000000 | +0.000000 |
| LW | 60.613534 | 66.362048 | 77.538718 | 9 | 16493 | 28 | +0.000000 | -3.715862 | +0.000000 | +0.000000 |

全部六列、八片段、Feeding独立ID域汇总和逐次新增/消除切换见RESULTS.md与run/POSTSCORE_SUMMARY.json。百分差值均为百分点，不跨数据集混成单一总分。

## 状态修复与真实切片

普通pending原样自然推进；事件边使用独立的事件代/来源代/身份版本/精确anchor/target键，私有proposal不借普通同目标计数。普通合法重接、换版、换锚、占用和原0.2/0.5秒窗口失效时切断事件进度。保留原矩阵、5次确认、出生窗、触发、q和实际局部事务。
首次公开造成实际身份版本变化时，旧事件键重新开始；这会影响自然接受时间，实际延迟必须报告，不能假设与DS19完全相同。已公开历史不回填，失败/timeout不整套复制B0。
4190帧真实前缀的两竞争窗和L3自然返回见CONFIRMATION_SLICE_CHECKS.md；完整确认进度、普通接受与消费见CONFIRMATION_AUDIT.md。

## 新分支显式局部返回

| 数据/分支 | 原帧 | source→public | bank物理 | 公共ID旧来源 | 保守判定 | 从首次发布延迟/帧 |
|---|---:|---|---|---|---|---:|
| L3/ACTIVITY_ISOLATED | 3024 | 47→9 | CORRECT | CONSISTENT_PUBLIC_ORIGIN | CORRECT | 134 |
| L3/MIXED_ISOLATED | 3024 | 47→9 | CORRECT | CONSISTENT_PUBLIC_ORIGIN | CORRECT | 134 |
| LW/ACTIVITY_ISOLATED | 3341 | 145→133 | UNSCORABLE | UNSCORABLE_PUBLIC_ORIGIN | UNSCORABLE | 37 |

## 深度结果与未完成边界

组合深度相对同底座活动列：出现正IDF1或HOTA差值的单位=['fishsa_development_8400', 'LW']；出现负差值的单位=['Feeding_pooled1471', 'fishsa_validation_2888']。完整有符号差值保留，不能选择最好数据或重复。
主分支首分离状态={'LOCAL_FALLBACK_COMMITTED': 50}；顺序证据状态={'MEASURED_PAIRED_ORDER': 18, 'UNKNOWN': 32}。fallback、UNKNOWN和不可评分不升级为成功。
当前共同几何/深度历史缺口、各对象latest片段不共时、未校准宽scale及whole/core中位数与局部遮挡关系的差异仍未修复；本轮只处理确认状态。深度表面身份真值未知，L3/LW预测派生弱参考不作盲测。D1无邻居范围不能称Birth路径全覆盖。

## 过程、可视化与交付

冻结前R1工程前缀因私有proposal借普通同目标旧计数的合同缺口被主动终止，三个经PID/命令核验的本任务进程和父流程全部落账；原源码、部分切片及日志保留，不评分、不混入R2。真实自然count1→4构造验证修复，10项正式单测通过。开发原型测试只有工具输出，没有持久stdout，不伪造日志；完整正式检查由execute记录。见ENGINEERING_PREFIX_ABORT.json、CONSTRUCTION_REVIEW.md。
正式回放/评分/audit/report退出码和耗时见EXECUTION_LOG.jsonl。最多六个本地CPU单线程片段作业，CUDA空；模型HTTP/smoke/训练/SAM3/补全服务/费用均0，不代表实时部署。
固定Feeding195、LW952、L33025及实际返回前中后深度/mask图为封存后诊断，未来列明确标注且不进入预测。公开图仅聚合数字；私有像素列RESTRICTED_ARTIFACTS真实路径/字节/SHA/依赖，GT raster、RGB、凭据不公开。
旧seal只读，公共代码/配置/测试/完整数字预测与事务/评分/报告同步main，远端ref与文件字节实际核验，更新HANDOFF。

## 唯一下一步

仅规划NEXT_STEP_PLAN.md中的一个后续步骤，不在本轮自动启动。
