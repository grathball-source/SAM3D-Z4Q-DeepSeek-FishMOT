# DS19 封存后 joint 失败案例复盘

仅解释既有封存结果，不是新测试。每个固定dataset按原帧选择MIXED_RETURN最早的真实joint COMMIT且bank判定WRONG/UNSCORABLE；未选最好案例。无失败提交不等于关联正确，H0、fallback、无split另列；以下计数可能重叠。

| 数据 | joint COMMIT | bank正确/错误/不可评分 | H0 | fallback | 无split | 选择状态 |
|---|---:|---|---:|---:|---:|---|
| Feeding | 0 | 0/0/0 | 20 | 20 | 17 | NO_FAILED_COMMITTED_JOINT_RESTORE_OBSERVED |
| fishsa_development_8400 | 0 | 0/0/0 | 9 | 9 | 4 | NO_FAILED_COMMITTED_JOINT_RESTORE_OBSERVED |
| fishsa_validation_2888 | 0 | 0/0/0 | 7 | 7 | 5 | NO_FAILED_COMMITTED_JOINT_RESTORE_OBSERVED |
| L3 | 0 | 0/0/0 | 4 | 4 | 7 | NO_FAILED_COMMITTED_JOINT_RESTORE_OBSERVED |
| LW | 0 | 0/0/0 | 10 | 10 | 12 | NO_FAILED_COMMITTED_JOINT_RESTORE_OBSERVED |

实际深度、原mask与已发布持久ID的参考anchor/merge确认/q/q+5全景和ROI留private/failure_visuals；ROI保留所有邻鱼/残片，来源不是GT。q+5只用于封存后诊断，未进入预测。
真实路径、字节数、SHA见PRIVATE_FAILURE_VISUALS.json；公共JSON/Markdown仅数字、来源元数据和解释，无RGB、私有像素或GT raster。
顺序置信度为未校准代理，weak带仅描述，不改决策门。缺少显式原始choice影响字段时保持UNKNOWN；本复盘不产生新评分、不调参数、不开始下一试验。
