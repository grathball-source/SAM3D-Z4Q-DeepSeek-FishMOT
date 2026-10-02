# DS17 状态策略封存后复盘

仅读取已封存标量trace与统一评分派生摘要。未读GT/RGB raster，未改冻结科学代码，未追加预测、评分、反事实或API。

## 主判定

已覆盖的状态隔离/原子发布检查通过，整体关联语义与性能未通过。L3恢复了被DS16活动冻结丢失的原正确自动重接；开发8400和验证2888又因匿名当前测量屏蔽丢失或延迟原正确Birth。不得将身份UNKNOWN当作测量UNKNOWN。

## 两次出生机会被消耗

- 开发F3902：原Z4Q/DS16将native7首次公开为0，评分派生CORRECT。ACTIVITY/MIXED/OFF因POST_UNASSIGNED将当前whole/core置不可用，首拒current_core_unavailable；n7登记birth后再无Birth机会。3907–3913七条D1边均partner_ambiguous，此后没有接回；3902–8400共4499帧公开7。
- 验证local2188/global11488：同一策略屏蔽native8当前core，原8→3 Birth派生CORRECT被阻断。新分支2233–2237积累五次D1，local2237/global11537实际接回3；49帧曾公开8。
- 两个q的raw scalar whole/core都有n>0与有效深度，混合测量均SINGLE_COMPATIBLE_LAYER；这是策略屏蔽，不是传感器缺失，也不证明物理身份已知。

## L3：活动修复的工程收益

bank9 clean anchor仍local2712；真实源9到2890仍有观测，新分支last_frame随真实活动到2890，DS16却冻在2872。contact5最后2854：旧last_seen-contact约0.596秒保留竞争5，新真实间隔约1.193秒排除过期竞争。3025/global3024原D1 source47→9得以保留；这不是S0也不是新增深度恢复。匿名recent_core保持未认证，native_runs继续真实更新。

## LW：为何ACTIVITY下降、MIXED回到原IDF1

主要可评分链是原local2515 source106→5。ACTIVITY2511–12目标5的partner margin为24.946/23.107毫米，小于required25；2513–14仅确认两次。2515目标5cost0.214441和目标92cost0.211113近同，唯一候选的全矩阵替代差约0.003327<0.15，原D1清空pending，此后未提交。ACTIVITY99→92@2395、105→92 Birth@2411使bank92最近真实占用至2460，仍在候选资格窗口。
MIXED两次上述alias未建立，bank92最后实际公开2310，2515已超过6秒候选窗口；目标5历史质量路径也使required降为20.817毫米（原权重/阈值未调整）。2511–15积五次，2515与原Z4Q/DS16同一时刻提交106→5。后1115帧ACTIVITY保持106，MIXED保持5，派生恢复CORRECT。MIXED的LW IDF1回到原64.329395，不是新增正确恢复，HOTA/AssA仍略低于原。MIXED_ORDER=OFF：这项收益不来自上下关系。
源80在ACTIVITY1888→42、MIXED1938→4以及其他资格/alias链也改变；这些恢复派生UNSCORABLE，不宣称物理改进。完整逐动作列表和候选表在JSON。

## 指标（同源、全部公开ID纳入）

|片段|分支|IDF1|HOTA|AssA|IDSW|FP|FN|
|---|---|---:|---:|---:|---:|---:|---:|
|fishsa_development_8400|SAM3_NATIVE|91.313288|73.346143|69.186768|5|194|323|
|fishsa_development_8400|Z4Q_FROZEN|99.333472|77.829488|77.907638|6|194|323|
|fishsa_development_8400|DS16_ORDER|99.333472|77.829488|77.907638|6|194|323|
|fishsa_development_8400|ACTIVITY_ORDER|92.002662|74.490791|71.364050|7|194|323|
|fishsa_development_8400|MIXED_ORDER|92.002662|74.490791|71.364050|7|194|323|
|fishsa_development_8400|MIXED_OFF|92.002662|74.490791|71.364050|7|194|323|
|fishsa_validation_2888|SAM3_NATIVE|76.456444|66.435529|55.196059|8|298|423|
|fishsa_validation_2888|Z4Q_FROZEN|80.697587|69.243869|60.074321|9|298|423|
|fishsa_validation_2888|DS16_ORDER|80.697587|69.243869|60.074321|9|298|423|
|fishsa_validation_2888|ACTIVITY_ORDER|80.413685|68.954661|59.571269|11|298|423|
|fishsa_validation_2888|MIXED_ORDER|80.413685|68.954661|59.571269|11|298|423|
|fishsa_validation_2888|MIXED_OFF|81.786842|69.116217|59.851590|13|298|423|
|L3|SAM3_NATIVE|72.426787|75.362607|94.259655|1|14677|0|
|L3|Z4Q_FROZEN|74.745256|77.171558|98.839045|2|14677|0|
|L3|DS16_ORDER|72.426787|75.362607|94.259655|1|14677|0|
|L3|ACTIVITY_ORDER|74.745256|77.171558|98.839045|2|14677|0|
|L3|MIXED_ORDER|74.745256|77.171558|98.839045|2|14677|0|
|L3|MIXED_OFF|62.838603|68.214192|77.225991|3|14677|0|
|LW|SAM3_NATIVE|60.613534|66.369067|77.555121|7|16493|28|
|LW|Z4Q_FROZEN|64.329395|68.991721|83.805597|10|16493|28|
|LW|DS16_ORDER|64.329395|68.995155|83.813941|9|16493|28|
|LW|ACTIVITY_ORDER|60.613534|66.285230|77.359310|8|16493|28|
|LW|MIXED_ORDER|64.329395|68.979125|83.774998|8|16493|28|
|LW|MIXED_OFF|64.329395|68.979125|83.774998|8|16493|28|

## 状态/事务边界

clean字段、view_bank与recent_core的冻结和活动last_seen/partners继续更新在真实trace中核查；缺失member没有凭空更新时间。公开映射逐帧一对一。stage仍核版本、generation、q、clean+view provenance及目标占用，先stage/commit后首次发布。局部fallback仅采纳本分支完整因果preview并释放本事件，不复制其他分支；它会保留preview里已经消耗的Birth，而不是无阻断Z4Q反事实。
事务只删除选中source的alias/pending/native_runs/recent_core，保留预留public bank；未观察到组外修复被整套覆盖。旧source bank可能在alias生效后作为不可占用候选留存：这是接口边界，不能凭合成PASS保证所有未来映射物理正确。source_activity内部source_version为UNKNOWN，不能将其冒充完整版本证书。

## 复现与证据

运行 `python -B experiments/ds17_mixed_depth_activity_repair/review_state_postscore.py` 仅重建一次新增报告；完成文件不覆盖。证据路径、字节和SHA、源码行、实际动作/发布、候选成本、匿名来源和测量均在STATE_POLICY_REVIEW.json。

下一机制须把匿名当前测量用于候选比较与把测量认证写入历史分开，保留原一次性Birth机会；本轮不修改或再跑该策略。
