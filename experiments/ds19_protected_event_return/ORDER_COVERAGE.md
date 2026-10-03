# DS19 ordinal 覆盖与未恢复控制

这是封存后的既有 H0/fallback 诊断，不是错误 joint 提交或新测试。原失败选择为 0 案例/0 图；本控制另按每个 dataset 最早原帧 q 选择，不挑最好或最坏。

| 数据 | q决策 | ordinal可用 | p缺失 | weak代理 | order原因 |
|---|---:|---:|---:|---:|---|
| Feeding | 20 | 8 | 12 | 8 | {'VALID_SOFT_ORDER_EVIDENCE': 8, 'NO_SAME_FRAME_PRE_PAIR': 6, 'INVALID_CAUSAL_CLEAN_PRE_SOURCE_BINDING': 4, 'INVALID_OR_MISSING_CURRENT_PAIRED_DEPTH': 2} |
| fishsa_development_8400 | 9 | 3 | 6 | 3 | {'VALID_SOFT_ORDER_EVIDENCE': 3, 'NO_SAME_FRAME_PRE_PAIR': 4, 'INVALID_CAUSAL_CLEAN_PRE_SOURCE_BINDING': 2} |
| fishsa_validation_2888 | 7 | 3 | 4 | 3 | {'NO_SAME_FRAME_PRE_PAIR': 3, 'VALID_SOFT_ORDER_EVIDENCE': 3, 'INVALID_CAUSAL_CLEAN_PRE_SOURCE_BINDING': 1} |
| L3 | 4 | 2 | 2 | 2 | {'INVALID_CAUSAL_CLEAN_PRE_SOURCE_BINDING': 1, 'VALID_SOFT_ORDER_EVIDENCE': 2, 'NO_SAME_FRAME_PRE_PAIR': 1} |
| LW | 10 | 2 | 8 | 2 | {'NO_SAME_FRAME_PRE_PAIR': 2, 'INVALID_CAUSAL_CLEAN_PRE_SOURCE_BINDING': 5, 'VALID_SOFT_ORDER_EVIDENCE': 2, 'INVALID_OR_MISSING_CURRENT_PAIRED_DEPTH': 1} |

## 相同 return 底座的实际差值

下面仅为完整真实状态结果的 MIXED_RETURN−ACTIVITY_RETURN，公共局部 return 的止损不算深度独有增益。

| 数据 | ΔIDF1 | ΔHOTA | ΔAssA | ΔIDSW | ΔFP | ΔFN |
|---|---:|---:|---:|---:|---:|---:|
| Feeding | -0.6564107762881122 | -0.5868381028960385 | -1.0420563750753473 | -2 | 0 | 0 |
| fishsa_development_8400 | 0.03178671116806697 | 0.028805090836826253 | 0.057854181390553094 | 0 | 0 | 0 |
| fishsa_validation_2888 | -0.27810770879804636 | -0.2833255358700484 | -0.49282460833589425 | 0 | 0 | 0 |
| L3 | 0.0 | 0.0 | 0.0 | 0 | 0 | 0 |
| LW | 0.0 | 0.08878213779928501 | 0.20732871788879947 | 1 | 0 | 0 |

## feeding_000000_000199/MS1-F156

未恢复控制，原帧 q=170，实际 H0；bank 提交判定=NOT_COMMITTED，首帧 clean=WRONG，提交 pre-consensus=NOT_COMMITTED。未提交不能称正确或错误 joint 恢复。
原封存 order=MEASURED_PAIRED_ORDER/VALID_SOFT_ORDER_EVIDENCE，p(A更近)=0.4821423722284234；实际 best=H1，margin=0.08925128880563937，min log-odds=2.1972245773362196，决策原因=INSUFFICIENT_JOINT_ODDS；choice 影响=UNKNOWN_NO_EXPLICIT_SEALED_FIELD。
whole/birth_core/core 的实际 fact、layer、来源、quality、geometry/depth 原因及 bank/公共来源/片段共识关系见公共数字 JSON；不重新计算候选或门槛。
A: bank/public origin=SAME；进入前公共ID误号=NO_MATCHED_BANK_ORIGIN_CONFLICT；clean/public origin=SAME。
B: bank/public origin=SAME；进入前公共ID误号=NO_MATCHED_BANK_ORIGIN_CONFLICT；clean/public origin=SAME。

## fishsa_development_8400/MS1-F1152

未恢复控制，原帧 q=1274，实际 H0；bank 提交判定=NOT_COMMITTED，首帧 clean=WRONG，提交 pre-consensus=NOT_COMMITTED。未提交不能称正确或错误 joint 恢复。
原封存 order=MEASURED_PAIRED_ORDER/VALID_SOFT_ORDER_EVIDENCE，p(A更近)=0.49381684280403404；实际 best=H0，margin=2.236354250215788，min log-odds=2.1972245773362196，决策原因=H0_BEST；choice 影响=UNKNOWN_NO_EXPLICIT_SEALED_FIELD。
whole/birth_core/core 的实际 fact、layer、来源、quality、geometry/depth 原因及 bank/公共来源/片段共识关系见公共数字 JSON；不重新计算候选或门槛。
A: bank/public origin=SAME；进入前公共ID误号=NO_MATCHED_BANK_ORIGIN_CONFLICT；clean/public origin=SAME。
B: bank/public origin=SAME；进入前公共ID误号=NO_MATCHED_BANK_ORIGIN_CONFLICT；clean/public origin=SAME。

## fishsa_validation_2888/MS1-F457

未恢复控制，原帧 q=9763，实际 H0；bank 提交判定=NOT_COMMITTED，首帧 clean=CORRECT，提交 pre-consensus=NOT_COMMITTED。未提交不能称正确或错误 joint 恢复。
原封存 order=UNKNOWN/NO_SAME_FRAME_PRE_PAIR，p(A更近)=None；实际 best=H0，margin=1.1476910581296602，min log-odds=2.1972245773362196，决策原因=NO_SAME_FRAME_PRE_PAIR；choice 影响=UNKNOWN_NO_EXPLICIT_SEALED_FIELD。
whole/birth_core/core 的实际 fact、layer、来源、quality、geometry/depth 原因及 bank/公共来源/片段共识关系见公共数字 JSON；不重新计算候选或门槛。
A: bank/public origin=SAME；进入前公共ID误号=NO_MATCHED_BANK_ORIGIN_CONFLICT；clean/public origin=SAME。
B: bank/public origin=SAME；进入前公共ID误号=NO_MATCHED_BANK_ORIGIN_CONFLICT；clean/public origin=SAME。

## L3/MS1-F226

未恢复控制，原帧 q=243，实际 H0；bank 提交判定=NOT_COMMITTED，首帧 clean=UNSCORABLE，提交 pre-consensus=NOT_COMMITTED。未提交不能称正确或错误 joint 恢复。
原封存 order=UNKNOWN/INVALID_CAUSAL_CLEAN_PRE_SOURCE_BINDING，p(A更近)=None；实际 best=H2，margin=0.18910423967971157，min log-odds=2.1972245773362196，决策原因=INVALID_CAUSAL_CLEAN_PRE_SOURCE_BINDING；choice 影响=UNKNOWN_NO_EXPLICIT_SEALED_FIELD。
whole/birth_core/core 的实际 fact、layer、来源、quality、geometry/depth 原因及 bank/公共来源/片段共识关系见公共数字 JSON；不重新计算候选或门槛。
A: bank/public origin=SAME；进入前公共ID误号=NO_MATCHED_BANK_ORIGIN_CONFLICT；clean/public origin=SAME。
B: bank/public origin=SAME；进入前公共ID误号=NO_MATCHED_BANK_ORIGIN_CONFLICT；clean/public origin=UNKNOWN。

## LW/MS1-F218

未恢复控制，原帧 q=222，实际 H0；bank 提交判定=NOT_COMMITTED，首帧 clean=CORRECT，提交 pre-consensus=NOT_COMMITTED。未提交不能称正确或错误 joint 恢复。
原封存 order=UNKNOWN/NO_SAME_FRAME_PRE_PAIR，p(A更近)=None；实际 best=H0，margin=0.6284643886896952，min log-odds=2.1972245773362196，决策原因=NO_SAME_FRAME_PRE_PAIR；choice 影响=UNKNOWN_NO_EXPLICIT_SEALED_FIELD。
whole/birth_core/core 的实际 fact、layer、来源、quality、geometry/depth 原因及 bank/公共来源/片段共识关系见公共数字 JSON；不重新计算候选或门槛。
A: bank/public origin=SAME；进入前公共ID误号=NO_MATCHED_BANK_ORIGIN_CONFLICT；clean/public origin=SAME。
B: bank/public origin=SAME；进入前公共ID误号=NO_MATCHED_BANK_ORIGIN_CONFLICT；clean/public origin=SAME。

已生成 10 张真实深度/原mask/已发布ID控制图（全景与ROI），仅在 private/unrestored_control_visuals。所有邻鱼和残片保留，q+5仅封存后诊断。真实路径、字节数、SHA及来源绑定见 PRIVATE_UNRESTORED_CONTROL_VISUALS.json。
顺序 p 和宽尺度均为未校准代理，不等于物理准确率或已证明上下不变；UNKNOWN 不算成功。新增推理 HTTP=0、费用=0。
