# DS18 封存后深度机制分析

完成六臂八段、每臂20098帧的只读审计。读取封存的源统计、事务、顺序证据和公开评分判定；未直接读取 GT/raster、RGB 或修复深度，未重跑分支或改冻结参数。

## 实际测量人口

|ROI|全部观测|单层/来源/质量合格|原标量有效|原有效后筛除|潜在混层|共享来源|独立质量不足|
|---|---:|---:|---:|---:|---:|---:|---:|
|whole|181842|125250|180727|55477|10510|37220|18410|
|birth_core|181842|154995|160583|5588|6466|0|21259|
|core|181842|163218|170085|6867|8320|0|11757|

whole的原标量有效按原D1门槛（n≥16、fraction≥0.2、正深度，不加MAD上限）计算；fixed/adaptive按原core尺度门槛。混层、共享来源、覆盖与尺度可重叠，不能把旗标相加作为总拒绝数。whole的组合筛选同时加入实际源独占性和既有60mm质量尺度，不能把所有差异称为混层效果。

Birth真实fixed core与S0 adaptive core逐人口分别认证；没有用另一ROI的合格性替代当前标量。depth层代表匿名表面测量；多层不等于多条鱼，单层合格也不证明鱼身份。

## 实际上下顺序覆盖

|分支|q|可用|UNKNOWN|可用但弱|改变同候选几何选择|带实际改动S0提交|
|---|---:|---:|---:|---:|---:|---:|
|DS16_ORDER|50|22|28|21|3|0|
|ACTIVITY_ORDER|49|20|29|19|3|0|
|MIXED_ORDER|50|18|32|18|3|0|
|MIXED_OFF|51|19|32|19|0|3|

弱证据是原odds=9对应的pre概率位于0.1–0.9；这是测量置信度代理，不是身份准确率。MIXED_ORDER可用18例全部弱，S0实际改动提交为0。选择改变、事务提交与全段指标必须分开；H0/UNKNOWN没有算作安全。各臂q数会因此前真实状态与事件准入/生命周期分化而不同，触发规则未重新调节。

## 合并期间保留的匿名层分布

|段|事件|有q事件|group观测|有q且任一ROI混层的事件|whole混层|fixed混层|adaptive混层|
|---|---:|---:|---:|---:|---:|---:|---:|
|feeding_000000_000199|4|1|22|0|1|0|0|
|feeding_000351_000555|14|5|67|3|10|2|4|
|feeding_000701_001060|8|5|33|2|3|6|4|
|feeding_001201_001906|11|9|201|1|1|21|2|
|fishsa_development_8400|13|9|290|2|36|29|41|
|fishsa_validation_2888|12|7|164|0|0|0|0|
|L3|11|4|901|0|0|0|0|
|LW|22|10|1768|2|64|8|31|

MIXED_ORDER共有95事件、50个q、3446条group观测；10/50个有q事件在某个ROI存在潜在混层。val、L3的group观测未检出显著混层；三处ORDER/OFF首次不同选择对应的group也未检出混层。测量被保留为匿名GROUP证据，未写入A/B个体历史；本轮ordinal公式没有消费GROUP层分布。不能把“没有消费”称作层间身份恢复成功，也不能把两层直接解释成两条鱼，或假设该信息覆盖所有失败事件。

## 相同上下文的顺序影响与随后传播

|段/原帧|同输入上下文|ORDER/OFF|原因|ORDER首帧pre共识|OFF首帧pre共识|ORDER末clean端点|OFF末clean端点|
|---|---|---|---|---|---|---|---|
|feeding_001201_001906/1239|True|H0/H2|NO_POSITIVE_ORDINAL_SUPPORT_OR_PREFERENCE|UNSCORABLE|UNSCORABLE|WRONG|CORRECT|
|feeding_001201_001906/1732|False|H0/H0|H0_BEST|CORRECT|CORRECT|CORRECT|CORRECT|
|fishsa_validation_2888/11900|True|H0/H1|NO_POSITIVE_ORDINAL_SUPPORT_OR_PREFERENCE|CORRECT|WRONG|UNSCORABLE|UNSCORABLE|
|fishsa_validation_2888/12116|False|H0/H0|H0_BEST|CORRECT|CORRECT|CORRECT|CORRECT|
|L3/1420|True|H0/H1|INSUFFICIENT_JOINT_ODDS|CORRECT|WRONG|CORRECT|WRONG|
|L3/2582|False|H0/H0|H0_BEST|UNSCORABLE|UNSCORABLE|CORRECT|CORRECT|

首次相同上下文分歧只有三处。Feeding1239的pre p≈0.499457、顺序LR≈−0.000150，却触发正支持硬门；val11900为p≈0.731125、候选相对H0的顺序反证；L3原帧1420的顺序项使联合赔率落到冻结门槛下。随后两个分支即使同选H0，输出也可能不同，因为alias/参考已分化；这不是新一轮顺序因子效果。末点、pre共识与提交后q..q10诊断保留各自UNKNOWN/UNSCORABLE，不能择优使用答案。

## 同源完整指标差值

|范围|参照|ΔIDF1|ΔHOTA|ΔAssA|ΔIDSW|ΔFP|ΔFN|
|---|---|---:|---:|---:|---:|---:|---:|
|Feeding1471|SAM3_NATIVE|+0.268647|-0.453713|-0.803811|+21|+0|+0|
|Feeding1471|Z4Q_FROZEN|-0.471399|-0.349509|-0.615094|-3|+0|+0|
|Feeding1471|ACTIVITY_ORDER|-0.656411|-0.582017|-1.033108|-2|+0|+0|
|Feeding1471|MIXED_OFF|-0.268647|-0.421677|-0.746284|+1|+0|+0|
|fishsa_development_8400|SAM3_NATIVE|+7.930784|+4.404369|+8.562246|+3|+0|+0|
|fishsa_development_8400|Z4Q_FROZEN|-0.089400|-0.078975|-0.158624|+2|+0|+0|
|fishsa_development_8400|ACTIVITY_ORDER|+0.031787|+0.028805|+0.057854|+0|+0|+0|
|fishsa_development_8400|MIXED_OFF|+0.000000|+0.000000|+0.000000|+0|+0|+0|
|fishsa_validation_2888|SAM3_NATIVE|+3.957241|+2.519132|+4.375209|+3|+0|+0|
|fishsa_validation_2888|Z4Q_FROZEN|-0.283902|-0.289208|-0.503053|+2|+0|+0|
|fishsa_validation_2888|ACTIVITY_ORDER|-0.278108|-0.283326|-0.492825|+0|+0|+0|
|fishsa_validation_2888|MIXED_OFF|-1.373157|-0.161556|-0.280321|-2|+0|+0|
|L3|SAM3_NATIVE|+0.000000|+0.000000|+0.000000|+0|+0|+0|
|L3|Z4Q_FROZEN|-2.318468|-1.808950|-4.579391|-1|+0|+0|
|L3|ACTIVITY_ORDER|+0.000000|+0.000000|+0.000000|+0|+0|+0|
|L3|MIXED_OFF|+9.588185|+7.148416|+17.033664|-2|+0|+0|
|LW|SAM3_NATIVE|+0.000000|-0.007019|-0.016404|+2|+0|+0|
|LW|Z4Q_FROZEN|-3.715862|-2.629673|-6.266880|-1|+0|+0|
|LW|ACTIVITY_ORDER|+0.000000|+0.091981|+0.214794|+0|+0|+0|
|LW|MIXED_OFF|+0.000000|+0.000000|+0.000000|+0|+0|+0|

Mixed−Activity是混层/来源/质量与历史传播的组合效应；Mixed−Off包含顺序打分与正LR/H0门，不是纯连续打分消融。完整预测与全部ID统一评分，FP/FN也按官方CLEAR实际结果保留。恢复原Z4Q是止损；L3/LW为弱参考，重复曝光片段不能称独立泛化。

## 首次分歧的实际机制

- Feeding159/375：MIXED新增D1提交；ACTIVITY分别被事件保护/匿名partner门阻止。不能解释为MIXED数值残差更好。
- Feeding849：MIXED丢失当前whole的D1准入；1413双方有合法边，但旧参考统计与确认链不同。
- 开发3947：MIXED在不同survivor参考状态下Birth提交；val11489：MIXED因partner fixed/whole UNKNOWN没有Birth提交。
- L3原帧547：目标历史和运动范围已因筛选变更；LW原帧226：原本合法的Birth因所需whole UNKNOWN阻止。LW当前whole有231点，仅3点共享来源，fixed/adaptive都合格，未检出混层；所需whole采用整个人口的独占来源门，不是按污染比例渐减置信度。该ACTIVITY恢复的实际旧anchor与公开源都UNSCORABLE，不能称“阻止正确恢复”。

L3原帧1420的ORDER首帧端点与pre共识均CORRECT，OFF交换提交WRONG；OFF相对ORDER的IDF1下降9.588185、HOTA下降7.148416。val11900的OFF首帧pre共识和提交后片段为WRONG，尽管完整IDF1高于ORDER；Feeding1239则末clean端点ORDER WRONG/OFF CORRECT而pre共识不可评分。不同证据方向必须并列。

原D1的D_balanced smooth=False，关联z(h)取最后clean whole，15点历史用于MAD/tolerance；EMA是记录与核验的状态，不是本轮D1实际深度均值预测。

## 一个下一步候选（尚未启动）

针对本轮18个可用pre次序全部弱、极接近0.5的符号仍可形成硬否决，建议下一个冻结诊断实验只分开“连续顺序证据”和“正支持/H0符号硬准入”，保留本轮测量、状态和联合log9门，用真实同源完整回放评估。不能直接取消整个顺序因子：L3已显示取消后的错误交换与完整指标下降。移除符号准入也可能放过val11900的错误交换，因此这只是明确机制的候选，不是提点承诺。必须保留三例的末点/pre共识判定，分别保留避免错误、阻碍正确与不可评分，不能按GT挑事件或滚动搜索门槛。主任务最终只选择一个计划；本审计没有启动新实验。

来源统计/所有候选、首分歧与后续映射链在POSTSEAL_DEPTH_MECHANISM_COUNTS.json；完整指标、物理分层、依赖SHA在POSTSEAL_DEPTH_ANALYSIS.json。
