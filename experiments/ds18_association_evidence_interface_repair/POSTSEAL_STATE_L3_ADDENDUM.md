# DS18 L3 共用身份门槛丢失原正确重接：追加审计

**实际活动字段修复仍生效，但新增受保护target的joint-only身份门槛阻断了原正确D1，整体语义和性能未通过。**

完全封存与总SCORE_PROVENANCE通过后，只读真实事务及公共独立评分摘要；未读取GT raster、RGB、私有像素，未重跑测试/预测/反事实。

## 真实读取链

- native47在local2891/global2890首次公开47。原Z4Q在local3025/global3024，由D1_DELAYED首次写出47→9并持续到末帧；独立实际bank物理判定CORRECT，公共起源CONSISTENT。
- 原edge读旧anchor2712/native9；history depth722.703186，query678.225586，residual44.477600mm、原tolerance60mm，motion cost0.047272、totalcost0.748384，原alternative为空。
- DS16曾因冻结活动使partner5进入alternative（残差39.550781），产生partner_ambiguous。DS18 ACTIVITY/MIXED的alternative恢复为空，证明活动修复没有失效。
- 但DS18新的edge_veto随后在写alias/bank之前命中WAIT_JOINT_GROUP_TRANSACTION；不是current measurement缺失，也不是source47身份匿名：此帧anonymous仅[6,9]。原因是candidate target公共9仍被active event保护。
- 公共6真实活动推进3025；失踪公共9最后真实活动2890，clean/view冻结anchor2712。没有凭空给失踪9更新时间，也没有把group深度写作个体clean。
- MS1-F2873在2873疑似、2874确认，member sources[6,9]，至3175 TIMEOUT始终q=None。联合stage出口从未产生；原6秒出生/返回资格先消失，超时释放不能凭空恢复旧资格。
- 所有新分支native47到3710仍公开47；并非晚接回。该损失属于共用身份stage政策，不能归给mixed测量质量或ordinal顺序。

## 实际整段指标

| 分支 | IDF1 | HOTA | AssA | IDSW | FP | FN |
|---|---:|---:|---:|---:|---:|---:|
| SAM3_NATIVE | 72.426787 | 75.362607 | 94.259655 | 1 | 14677 | 0 |
| Z4Q_FROZEN | 74.745256 | 77.171558 | 98.839045 | 2 | 14677 | 0 |
| DS16_ORDER | 72.426787 | 75.362607 | 94.259655 | 1 | 14677 | 0 |
| ACTIVITY_ORDER | 72.426787 | 75.362607 | 94.259655 | 1 | 14677 | 0 |
| MIXED_ORDER | 72.426787 | 75.362607 | 94.259655 | 1 | 14677 | 0 |
| MIXED_OFF | 62.838603 | 68.214192 | 77.225991 | 3 | 14677 | 0 |

这是同源完整段真实结果；L3参考为已有预测派生弱参考，不能上升为独立人工GT。少一个IDSW与较低IDF1/HOTA/AssA同时成立，不能仅用IDSW减小称成功。

## 可追溯性与范围

JSON绑定封存预测、事务、事件、独立自动判定、指标及controller真实路径/字节/SHA；保存3025/3072/3175/3176/末帧实态、pending实际退休与公开映射，未修改此前POSTSEAL_STATE_CASES报告。
复现：`python experiments/ds18_association_evidence_interface_repair/review_state_l3_postscore.py`，只读报告脚本，无科研运行。
