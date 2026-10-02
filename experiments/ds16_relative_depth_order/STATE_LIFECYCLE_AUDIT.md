# DS16 两处真实来源生命周期审计

本审计只读本轮已经封存的真实预测、控制器trace、事件历史、DepthState与发布账本；未读取GT、RGB或原始像素，未重跑预测，未改冻结文件或旧实验。

## 真实动作

| 片段与q | 原Z4Q动作 | 四个新分支实际结果 | 来源证据 |
|---|---|---|---|
| 开发F3902 | native7 → public0；原参考F3836/native6 | STATE_FIXED、OFF、ORDER、PERMUTE全部首次发布且保持alias | n4 run到3901/count3901；recent core anchor3901；联合margin 3.9469889322916663 |
| 验证local2188/global11488 | native8 → public3；原参考local1935/native3 | 四分支全部首次发布且保持alias | n7 run到2187/count1970；native reservation=true；联合margin 0.0187813494873047 |

两处动作的目标anchor、cost与assignment_margin与同源原Z4Q一致；不以接受候选代替实际发布，持久alias和无事务覆盖均已核验。

## 参考与当前来源隔离

- 开发3863–3901共39帧×4分支：n4的native_seen/run逐帧推进；public4 anchor固定F3492、public0 anchor固定F3836。
- 验证2125–2187共63帧×4分支：n7的来源run逐帧推进，start=218；public3 anchor固定1935、public7 anchor固定1992。recent_core缺失保持缺失。
- 共408条保护帧分支记录全部核验。群组载体在保护期间为GROUP_MEASUREMENT，q为POST_UNASSIGNED，DepthState可信样本数始终0。来源连续性没有被当作新的可信个体pre历史。
- 本审计能由真实日志直接证明bank anchor未变；完整bank/view_bank字节一致性由冻结前单测覆盖，不能凭仅含anchor的日志扩大此声明。

## 归因边界

两例的A/B可信深度片段没有同时刻交集。OFF、ORDER、PERMUTE均记录UNKNOWN:NO_SAME_FRAME_PRE_PAIR，选H0并局部回退，显式恢复changes为空。
最终恢复来自原Z4Q的BIRTH_REFINE，属于共用来源生命周期修复。它不能作为上下次序独有提点证据；本审计没有判定物理身份正确性，也没有生成整段科研指标。

## 真实封存绑定

| 片段 | TRANSACTIONS字节 | SHA-256 |
|---|---:|---|
| fishsa_development_8400 | 595782 | a53f30e3c073ccb430ea7ca4ca9a86bb50ebdf606fe87ae80ff33b135e79cfe9 |
| fishsa_validation_2888 | 239686 | 0aa8668938bcc8741fa1ec7485b16277540b4a33ae1054b63ab9d0e1d9582e35 |

所有六类输入文件的完整hash均与实际PREDICTIONS_SEALED.json一致；q预测与次序记录的逐行hash均与发布账本一致。完整来源路径、字节、SHA、逐帧来源与匿名分类见JSON。

## 逐项自核

- 8次新分支自动动作均确认实际首次发布、持久alias与一对一映射。
- 408条保护帧的参考anchor和实际来源推进逐条核验；q及所有群组帧的匿名分类与可信样本数逐条核验。
- 原动作anchor/cost/margin、预测行、次序行、发布账本和真实seal绑定全部通过。
- 工程修复与ordinal增量分开；UNKNOWN、物理身份未评分和缺失recent_core均如实保留。

审计JSON：E:\CAU\SAM3D-Z4Q-DeepSeek-FishMOT\experiments\ds16_relative_depth_order\STATE_LIFECYCLE_AUDIT.json；365720字节；SHA-256 `9b1eaaf4b3dea1a8557353cf5648192c8ba22439c4a1179865c00a14e4236881`。
