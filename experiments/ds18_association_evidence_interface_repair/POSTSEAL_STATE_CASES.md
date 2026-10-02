# DS18 封存后真实状态与发布病例审计

**状态隔离和来源检查不能替代关联性能：本报告只追真实决策、首次公开、后续自身状态及独立封存后判定。**

输入为八段六分支共 20,098 帧已封存产物。没有重新预测、反事实回放、测试或修改科学代码；没有读取 GT raster、RGB 或像素。物理判定仅在完整 METRICS/SCORE_PROVENANCE 门槛通过后读取公共独立评分摘要。

## 归因边界

- ACTIVITY_ORDER 的匿名当前有效测量与 pending Birth 是共用接口/状态修复，不能计为上下顺序增量。
- MIXED_ORDER−ACTIVITY_ORDER 包含测量资格筛选对整条关联状态链的影响。
- MIXED_ORDER−MIXED_OFF 才保持接口、混合筛选相同，仅改变冻结 ordinal 关联。
- 自动审计 applied_at_first_publication 表示当前决策帧输出采用该映射；延迟 Birth 的实际首次出现/公开必须读 actual_first_source_publication。
- 物理 query↔实际旧 bank 与 bank↔公共 ID 原始起源分列，不能将既有错误公共起源偶然换回当作正确物理恢复。

## 实际病例

### 开发 F3902 / native7

| 分支 | 当前源首次公开与后续变更（local 帧） | 真正接受动作 | 实际 bank 物理判定 / 公共起源 | 最终 alias |
|---|---|---|---|---|
| SAM3_NATIVE | 3902:7→7 | 无 | 无自动提交 | 无/原生 |
| Z4Q_FROZEN | 3902:7→0 | 3902 BIRTH_REFINE→0 | CORRECT / CONSISTENT_PUBLIC_ORIGIN | 0 |
| DS16_ORDER | 3902:7→0 | 3902 BIRTH_REFINE→0 | CORRECT / CONSISTENT_PUBLIC_ORIGIN | 0 |
| ACTIVITY_ORDER | 3902:7→7 → 3963:7→0 | 3963 BIRTH_REFINE→0 | CORRECT / CONSISTENT_PUBLIC_ORIGIN | 0 |
| MIXED_ORDER | 3902:7→7 → 3947:7→0 | 3947 BIRTH_REFINE→0 | CORRECT / CONSISTENT_PUBLIC_ORIGIN | 0 |
| MIXED_OFF | 3902:7→7 → 3947:7→0 | 3947 BIRTH_REFINE→0 | CORRECT / CONSISTENT_PUBLIC_ORIGIN | 0 |

首次全帧真实发布分歧（不是事后挑选的局部变化）：

- ACTIVITY_ORDER__minus__DS16_ORDER: local3902/global3902，{'7': {'arm': 7, 'base': 0}}。
- ACTIVITY_ORDER__minus__Z4Q_FROZEN: local3902/global3902，{'7': {'arm': 7, 'base': 0}}。
- MIXED_ORDER__minus__ACTIVITY_ORDER: local3947/global3947，{'7': {'arm': 0, 'base': 7}}。

q/目标帧的实际资格与状态：

- ACTIVITY_ORDER: 发布7→7；匿名集合[4, 6, 7]；当前测量保留[4, 7]；缺失来源不更新时间[6]；required whole UNKNOWN=['partner_4_BIRTH_WHOLE_binding', 'partner_4_candidate_whole', 'partner_4_cross_whole', 'partner_4_identity_role_unresolved', 'partner_4_own_whole']。
- MIXED_ORDER: 发布7→7；匿名集合[4, 6, 7]；当前测量保留[4, 7]；缺失来源不更新时间[6]；required whole UNKNOWN=['partner_4_BIRTH_WHOLE_binding', 'partner_4_candidate_whole', 'partner_4_cross_whole', 'partner_4_identity_role_unresolved', 'partner_4_own_whole']。
- MIXED_OFF: 发布7→7；匿名集合[4, 6, 7]；当前测量保留[4, 7]；缺失来源不更新时间[6]；required whole UNKNOWN=['partner_4_BIRTH_WHOLE_binding', 'partner_4_candidate_whole', 'partner_4_cross_whole', 'partner_4_identity_role_unresolved', 'partner_4_own_whole']。
- DS16_ORDER 联合事件 q=1274：LOCAL_FALLBACK_COMMITTED / H0；首次实际发布参考判定WRONG，pre共识判定UNSCORABLE。
- DS16_ORDER 联合事件 q=3081：LOCAL_FALLBACK_COMMITTED / H0；首次实际发布参考判定CORRECT，pre共识判定CORRECT。
- DS16_ORDER 联合事件 q=3902：LOCAL_FALLBACK_COMMITTED / H0；首次实际发布参考判定CORRECT，pre共识判定CORRECT。
- ACTIVITY_ORDER 联合事件 q=1274：LOCAL_FALLBACK_COMMITTED / H0；首次实际发布参考判定WRONG，pre共识判定UNSCORABLE。
- ACTIVITY_ORDER 联合事件 q=3081：LOCAL_FALLBACK_COMMITTED / H0；首次实际发布参考判定CORRECT，pre共识判定CORRECT。
- ACTIVITY_ORDER 联合事件 q=3902：LOCAL_FALLBACK_COMMITTED / H0；首次实际发布参考判定WRONG，pre共识判定WRONG。
- MIXED_ORDER 联合事件 q=1274：LOCAL_FALLBACK_COMMITTED / H0；首次实际发布参考判定WRONG，pre共识判定UNSCORABLE。
- MIXED_ORDER 联合事件 q=3081：LOCAL_FALLBACK_COMMITTED / H0；首次实际发布参考判定CORRECT，pre共识判定CORRECT。
- MIXED_ORDER 联合事件 q=3902：LOCAL_FALLBACK_COMMITTED / H0；首次实际发布参考判定WRONG，pre共识判定WRONG。
- MIXED_OFF 联合事件 q=1274：LOCAL_FALLBACK_COMMITTED / H0；首次实际发布参考判定WRONG，pre共识判定UNSCORABLE。
- MIXED_OFF 联合事件 q=3081：LOCAL_FALLBACK_COMMITTED / H0；首次实际发布参考判定CORRECT，pre共识判定CORRECT。
- MIXED_OFF 联合事件 q=3902：LOCAL_FALLBACK_COMMITTED / H0；首次实际发布参考判定WRONG，pre共识判定WRONG。

开发源7在 q 的Birth实际固定7×7 core n=223、whole n=773，测量保持有效，但身份仍 POST_UNASSIGNED；S0的adaptive core为另一角色，不能混用。q禁止单边自动 alias，H0局部回退。旧公共0真实最后活动3893，clean anchor3836/native6；公共4确实活动到3902，但clean anchor3492已超过12秒。不能凭空给失踪native6更新时间。后续pending回看原3836参考，ACTIVITY3963、MIXED3947才提交，均晚于初次public7。

### 验证 local2188 / global11488 / native8

| 分支 | 当前源首次公开与后续变更（local 帧） | 真正接受动作 | 实际 bank 物理判定 / 公共起源 | 最终 alias |
|---|---|---|---|---|
| SAM3_NATIVE | 2188:8→8 | 无 | 无自动提交 | 无/原生 |
| Z4Q_FROZEN | 2188:8→3 | 2188 BIRTH_REFINE→3 | CORRECT / CONSISTENT_PUBLIC_ORIGIN | 3 |
| DS16_ORDER | 2188:8→3 | 2188 BIRTH_REFINE→3 | CORRECT / CONSISTENT_PUBLIC_ORIGIN | 3 |
| ACTIVITY_ORDER | 2188:8→8 → 2189:8→3 | 2189 BIRTH_REFINE→3 | CORRECT / CONSISTENT_PUBLIC_ORIGIN | 3 |
| MIXED_ORDER | 2188:8→8 → 2237:8→3 | 2237 D1_DELAYED→3 | CORRECT / CONSISTENT_PUBLIC_ORIGIN | 3 |
| MIXED_OFF | 2188:8→8 → 2237:8→3 | 2237 D1_DELAYED→3 | CORRECT / CONSISTENT_PUBLIC_ORIGIN | 3 |

首次全帧真实发布分歧（不是事后挑选的局部变化）：

- ACTIVITY_ORDER__minus__DS16_ORDER: local2188/global11488，{'8': {'arm': 8, 'base': 3}}。
- ACTIVITY_ORDER__minus__Z4Q_FROZEN: local2188/global11488，{'8': {'arm': 8, 'base': 3}}。
- MIXED_ORDER__minus__ACTIVITY_ORDER: local2189/global11489，{'8': {'arm': 8, 'base': 3}}。
- MIXED_ORDER__minus__MIXED_OFF: local2600/global11900，{'1': {'arm': 1, 'base': 4}, '4': {'arm': 4, 'base': 1}}。

q/目标帧的实际资格与状态：

- ACTIVITY_ORDER: 发布8→8；匿名集合[3, 7, 8]；当前测量保留[7, 8]；缺失来源不更新时间[3]；required whole UNKNOWN=['partner_7_identity_role_unresolved']。
- MIXED_ORDER: 发布8→8；匿名集合[3, 7, 8]；当前测量保留[7, 8]；缺失来源不更新时间[3]；required whole UNKNOWN=['partner_1_BIRTH_CORE_binding', 'partner_1_BIRTH_WHOLE_binding', 'partner_1_cross_whole', 'partner_1_own_whole', 'partner_7_identity_role_unresolved']。
- MIXED_OFF: 发布8→8；匿名集合[3, 7, 8]；当前测量保留[7, 8]；缺失来源不更新时间[3]；required whole UNKNOWN=['partner_1_BIRTH_CORE_binding', 'partner_1_BIRTH_WHOLE_binding', 'partner_1_cross_whole', 'partner_1_own_whole', 'partner_7_identity_role_unresolved']。
- DS16_ORDER 联合事件 q=463：LOCAL_FALLBACK_COMMITTED / H0；首次实际发布参考判定CORRECT，pre共识判定CORRECT。
- DS16_ORDER 联合事件 q=2188：LOCAL_FALLBACK_COMMITTED / H0；首次实际发布参考判定CORRECT，pre共识判定CORRECT。
- DS16_ORDER 联合事件 q=2600：LOCAL_FALLBACK_COMMITTED / H0；首次实际发布参考判定UNSCORABLE，pre共识判定CORRECT。
- ACTIVITY_ORDER 联合事件 q=463：LOCAL_FALLBACK_COMMITTED / H0；首次实际发布参考判定CORRECT，pre共识判定CORRECT。
- ACTIVITY_ORDER 联合事件 q=2188：LOCAL_FALLBACK_COMMITTED / H0；首次实际发布参考判定WRONG，pre共识判定WRONG。
- ACTIVITY_ORDER 联合事件 q=2600：LOCAL_FALLBACK_COMMITTED / H0；首次实际发布参考判定UNSCORABLE，pre共识判定CORRECT。
- MIXED_ORDER 联合事件 q=463：LOCAL_FALLBACK_COMMITTED / H0；首次实际发布参考判定CORRECT，pre共识判定CORRECT。
- MIXED_ORDER 联合事件 q=2188：LOCAL_FALLBACK_COMMITTED / H0；首次实际发布参考判定WRONG，pre共识判定WRONG。
- MIXED_ORDER 联合事件 q=2600：LOCAL_FALLBACK_COMMITTED / H0；首次实际发布参考判定UNSCORABLE，pre共识判定CORRECT。
- MIXED_OFF 联合事件 q=463：LOCAL_FALLBACK_COMMITTED / H0；首次实际发布参考判定CORRECT，pre共识判定CORRECT。
- MIXED_OFF 联合事件 q=2188：LOCAL_FALLBACK_COMMITTED / H0；首次实际发布参考判定WRONG，pre共识判定WRONG。
- MIXED_OFF 联合事件 q=2600：COMMIT / H1；首次实际发布参考判定UNSCORABLE，pre共识判定WRONG。

验证 q 时公共3活动最后2163/clean1935，公共7活动2188/clean1992；缺失source3没有被group更新时间。ACTIVITY在2189合法Birth，mixed筛选使该路径继续UNKNOWN，改由2237 D1；不能把不同路径/不同延迟合并成一次及时S0恢复。

### LW local3064 / global3063 / native133

| 分支 | 当前源首次公开与后续变更（local 帧） | 真正接受动作 | 实际 bank 物理判定 / 公共起源 | 最终 alias |
|---|---|---|---|---|
| SAM3_NATIVE | 3064:133→133 | 无 | 无自动提交 | 无/原生 |
| Z4Q_FROZEN | 3064:133→133 | 无 | 无自动提交 | 无/原生 |
| DS16_ORDER | 3064:133→133 | 无 | 无自动提交 | 无/原生 |
| ACTIVITY_ORDER | 3064:133→133 | 无 | 无自动提交 | 无/原生 |
| MIXED_ORDER | 3064:133→133 → 3076:133→129 | 3076 D1_DELAYED→129 | UNSCORABLE / UNSCORABLE_PUBLIC_ORIGIN | 129 |
| MIXED_OFF | 3064:133→133 → 3076:133→129 | 3076 D1_DELAYED→129 | UNSCORABLE / UNSCORABLE_PUBLIC_ORIGIN | 129 |

首次全帧真实发布分歧（不是事后挑选的局部变化）：

- ACTIVITY_ORDER__minus__DS16_ORDER: local128/global127，{'13': {'arm': 9, 'base': 13}}。
- ACTIVITY_ORDER__minus__Z4Q_FROZEN: local128/global127，{'13': {'arm': 9, 'base': 13}}。
- MIXED_ORDER__minus__ACTIVITY_ORDER: local227/global226，{'19': {'arm': 19, 'base': 12}}。

q/目标帧的实际资格与状态：

- ACTIVITY_ORDER: 发布133→133；匿名集合[]；当前测量保留[]；缺失来源不更新时间[]；required whole UNKNOWN=['partner_107_candidate_whole', 'partner_98_candidate_whole', 'partner_98_own_whole']。
- MIXED_ORDER: 发布133→133；匿名集合[]；当前测量保留[]；缺失来源不更新时间[]；required whole UNKNOWN=['competitor_107_whole', 'competitor_129_whole', 'partner_107_candidate_whole', 'partner_109_BIRTH_WHOLE_binding', 'partner_109_candidate_whole', 'partner_109_cross_whole', 'partner_109_own_whole', 'partner_130_candidate_whole', 'partner_131_candidate_whole', 'query_BIRTH_WHOLE_binding', 'target_whole_comparison']。
- MIXED_OFF: 发布133→133；匿名集合[]；当前测量保留[]；缺失来源不更新时间[]；required whole UNKNOWN=['competitor_107_whole', 'competitor_129_whole', 'partner_107_candidate_whole', 'partner_109_BIRTH_WHOLE_binding', 'partner_109_candidate_whole', 'partner_109_cross_whole', 'partner_109_own_whole', 'partner_130_candidate_whole', 'partner_131_candidate_whole', 'query_BIRTH_WHOLE_binding', 'target_whole_comparison']。
- DS16_ORDER 联合事件 q=1156：LOCAL_FALLBACK_COMMITTED / H0；首次实际发布参考判定UNSCORABLE，pre共识判定UNSCORABLE。
- DS16_ORDER 联合事件 q=1276：LOCAL_FALLBACK_COMMITTED / H0；首次实际发布参考判定CORRECT，pre共识判定UNSCORABLE。
- DS16_ORDER 联合事件 q=2029：LOCAL_FALLBACK_COMMITTED / H0；首次实际发布参考判定UNSCORABLE，pre共识判定UNSCORABLE。
- DS16_ORDER 联合事件 q=2909：LOCAL_FALLBACK_COMMITTED / H0；首次实际发布参考判定CORRECT，pre共识判定CORRECT。
- ACTIVITY_ORDER 联合事件 q=1156：LOCAL_FALLBACK_COMMITTED / H0；首次实际发布参考判定UNSCORABLE，pre共识判定UNSCORABLE。
- ACTIVITY_ORDER 联合事件 q=1276：LOCAL_FALLBACK_COMMITTED / H0；首次实际发布参考判定CORRECT，pre共识判定UNSCORABLE。
- ACTIVITY_ORDER 联合事件 q=2909：LOCAL_FALLBACK_COMMITTED / H0；首次实际发布参考判定UNSCORABLE，pre共识判定CORRECT。
- MIXED_ORDER 联合事件 q=1156：LOCAL_FALLBACK_COMMITTED / H0；首次实际发布参考判定UNSCORABLE，pre共识判定UNSCORABLE。
- MIXED_ORDER 联合事件 q=1276：LOCAL_FALLBACK_COMMITTED / H0；首次实际发布参考判定CORRECT，pre共识判定UNSCORABLE。
- MIXED_ORDER 联合事件 q=2029：LOCAL_FALLBACK_COMMITTED / H0；首次实际发布参考判定UNSCORABLE，pre共识判定UNSCORABLE。
- MIXED_ORDER 联合事件 q=2909：LOCAL_FALLBACK_COMMITTED / H0；首次实际发布参考判定CORRECT，pre共识判定CORRECT。
- MIXED_OFF 联合事件 q=1156：LOCAL_FALLBACK_COMMITTED / H0；首次实际发布参考判定UNSCORABLE，pre共识判定UNSCORABLE。
- MIXED_OFF 联合事件 q=1276：LOCAL_FALLBACK_COMMITTED / H0；首次实际发布参考判定CORRECT，pre共识判定UNSCORABLE。
- MIXED_OFF 联合事件 q=2029：LOCAL_FALLBACK_COMMITTED / H0；首次实际发布参考判定UNSCORABLE，pre共识判定UNSCORABLE。
- MIXED_OFF 联合事件 q=2909：LOCAL_FALLBACK_COMMITTED / H0；首次实际发布参考判定CORRECT，pre共识判定CORRECT。

LW3064是自动 Birth 评估帧，不是S0。没有分支在该帧提交native133。ACTIVITY直到3161原Birth窗到期仍不接受；MIXED在3076由D1→129，不能称“3064 Birth被修复”。更早的pending-Birth13→9、19候选迁移和99/105→92改变活动/占用链：native106在ACTIVITY2488→92，而mixed保持106。必须由整段同源指标判断，不能只展示133局部动作。

### Feeding 末段 local264 / global1464 / native176

| 分支 | 当前源首次公开与后续变更（local 帧） | 真正接受动作 | 实际 bank 物理判定 / 公共起源 | 最终 alias |
|---|---|---|---|---|
| SAM3_NATIVE | 243:176→176 | 无 | 无自动提交 | 无/原生 |
| Z4Q_FROZEN | 243:176→176 → 266:176→167 | 266 D1_DELAYED→167 | CORRECT / CONSISTENT_PUBLIC_ORIGIN | 167 |
| DS16_ORDER | 243:176→176 → 266:176→167 | 266 D1_DELAYED→167 | CORRECT / CONSISTENT_PUBLIC_ORIGIN | 167 |
| ACTIVITY_ORDER | 243:176→176 → 266:176→167 | 266 D1_DELAYED→167 | CORRECT / CONSISTENT_PUBLIC_ORIGIN | 167 |
| MIXED_ORDER | 243:176→176 → 264:176→126 | 264 D1_DELAYED→126 | WRONG / CONSISTENT_PUBLIC_ORIGIN | 126 |
| MIXED_OFF | 243:176→176 → 266:176→136 | 266 D1_DELAYED→136 | CORRECT / CONSISTENT_PUBLIC_ORIGIN | 136 |

首次全帧真实发布分歧（不是事后挑选的局部变化）：

- MIXED_ORDER__minus__MIXED_OFF: local39/global1239，{'167': {'arm': 167, 'base': 136}}。
- ACTIVITY_ORDER__minus__DS16_ORDER: local190/global1390，{'172': {'arm': 172, 'base': 126}}。
- ACTIVITY_ORDER__minus__Z4Q_FROZEN: local190/global1390，{'172': {'arm': 172, 'base': 126}}。
- MIXED_ORDER__minus__ACTIVITY_ORDER: local213/global1413，{'172': {'arm': 172, 'base': 126}}。

q/目标帧的实际资格与状态：

- ACTIVITY_ORDER: 发布176→176；匿名集合[132, 159]；当前测量保留[132, 159]；缺失来源不更新时间[]；required whole UNKNOWN=无。
- MIXED_ORDER: 发布176→126；匿名集合[132, 159]；当前测量保留[132, 159]；缺失来源不更新时间[]；required whole UNKNOWN=无。
- MIXED_OFF: 发布176→176；匿名集合[132, 159]；当前测量保留[132, 159]；缺失来源不更新时间[]；required whole UNKNOWN=无。
- DS16_ORDER 联合事件 q=39：LOCAL_FALLBACK_COMMITTED / H0；首次实际发布参考判定WRONG，pre共识判定UNSCORABLE。
- DS16_ORDER 联合事件 q=190：LOCAL_FALLBACK_COMMITTED / H0；首次实际发布参考判定WRONG，pre共识判定UNSCORABLE。
- ACTIVITY_ORDER 联合事件 q=39：LOCAL_FALLBACK_COMMITTED / H0；首次实际发布参考判定WRONG，pre共识判定UNSCORABLE。
- ACTIVITY_ORDER 联合事件 q=190：LOCAL_FALLBACK_COMMITTED / H0；首次实际发布参考判定WRONG，pre共识判定UNSCORABLE。
- MIXED_ORDER 联合事件 q=39：LOCAL_FALLBACK_COMMITTED / H0；首次实际发布参考判定WRONG，pre共识判定UNSCORABLE。
- MIXED_ORDER 联合事件 q=190：LOCAL_FALLBACK_COMMITTED / H0；首次实际发布参考判定WRONG，pre共识判定UNSCORABLE。
- MIXED_OFF 联合事件 q=39：COMMIT / H2；首次实际发布参考判定CORRECT，pre共识判定UNSCORABLE。
- MIXED_OFF 联合事件 q=190：LOCAL_FALLBACK_COMMITTED / H0；首次实际发布参考判定WRONG，pre共识判定UNSCORABLE。

末段176在243首次public176。264 MIXED_ORDER的D1→126不是joint S0；当时活动group属于公共132/159，native176不在该匿名集合。上游native172原190 Birth→126被阻后，ACTIVITY213 D1才→126；mixed又阻了该动作。MIXED_OFF更早39的分离选择导致170后续→136，继而176→136。264的候选及真实旧参考已随分支状态改变，不能强套原bank答案或归为独立一次正确深度恢复。

## 共用修复与深度增量的整段差值

| 段 | ACTIVITY IDF1 | MIXED IDF1 | ACTIVITY−DS17 ACTIVITY | ACTIVITY−Z4Q | MIXED−ACTIVITY | MIXED−OFF |
|---|---:|---:|---:|---:|---:|---:|
| feeding_000000_000199 | 92.889759 | 92.125617 | +0.764141 | +0.764141 | -0.764141 | +0.000000 |
| feeding_000351_000555 | 82.927271 | 82.872928 | +0.036229 | +0.036229 | -0.054343 | +0.000000 |
| feeding_000701_001060 | 75.636778 | 75.667840 | +0.000000 | +0.000000 | +0.031062 | +0.000000 |
| feeding_001201_001906 | 81.684556 | 80.531909 | +0.158621 | +0.158621 | -1.152646 | -0.560461 |
| fishsa_development_8400 | 99.212286 | 99.244072 | +7.209623 | -0.121187 | +0.031787 | +0.000000 |
| fishsa_validation_2888 | 80.691793 | 80.413685 | +0.278108 | -0.005794 | -0.278108 | -1.373157 |
| L3 | 72.426787 | 72.426787 | -2.318468 | -2.318468 | +0.000000 | +9.588185 |
| LW | 60.613534 | 60.613534 | +0.000000 | -3.715862 | +0.000000 | +0.000000 |

完整IDF1/HOTA/AssA/IDSW/FP/FN及上述各同源差值在JSON metrics表，未仅选保留病例。L3/LW使用既有预测派生弱参考，不上升为独立人工真值性能。

## pending 日志与残余工程边界

dev native6的Birth cache最后held/UNKNOWN更新1314，但1327仍实际进行Birth评估且由D1接受6→0；此后bank/view clean推进到3836/native6。pending不参与匿名集合、reference_status或clean注册，因此休眠记录没有继续冻结该已提交别名。该源最后公开活动3893，与q3902失踪源不更新时间一致。

pending的evaluation_frame是日志snapshot帧；last_evaluation_frame只由remember_birth在held/UNKNOWN更新，不一定等于最后真正尝试。这里订正source-only cache文字中的“实际最后重评”简写：应以birth_checks/accepted事务读取真实尝试。D1接受后未清理Birth cache、源缺失/被retired后不主动退休旧cache，导致终态PENDING字符串和真实资格不能等同；窗口每次有资格重评时仍按原birth/first_eligible检查。

| 段 | 分支 | RETIRED cache | PENDING cache | 未退休但已过原窗 | 其中已有alias |
|---|---|---:|---:|---:|---:|
| fishsa_development_8400 | ACTIVITY_ORDER | 0 | 2 | 2 | 2 |
| fishsa_development_8400 | MIXED_ORDER | 0 | 2 | 2 | 2 |
| fishsa_development_8400 | MIXED_OFF | 0 | 2 | 2 | 2 |
| fishsa_validation_2888 | ACTIVITY_ORDER | 1 | 0 | 0 | 0 |
| fishsa_validation_2888 | MIXED_ORDER | 1 | 1 | 1 | 1 |
| fishsa_validation_2888 | MIXED_OFF | 1 | 1 | 1 | 1 |
| LW | ACTIVITY_ORDER | 29 | 55 | 55 | 21 |
| LW | MIXED_ORDER | 33 | 58 | 58 | 20 |
| LW | MIXED_OFF | 33 | 58 | 58 | 20 |
| feeding_001201_001906 | ACTIVITY_ORDER | 14 | 11 | 8 | 5 |
| feeding_001201_001906 | MIXED_ORDER | 13 | 19 | 14 | 9 |
| feeding_001201_001906 | MIXED_OFF | 13 | 17 | 12 | 9 |

另有初次候选循环的资格顺序边界：初次某个候选产生pending后，同帧后续尚未登记的候选暂报PENDING_TARGET_ANCHOR_CHANGED，随后才加入同帧初始targets；这不是实际换锚证据。LW3064该类candidate同时有独立whole UNKNOWN/其他失败，本报告不臆断其造成性能变化。

## 复现与证据绑定

只读source提取：`python experiments/ds18_association_evidence_interface_repair/review_state_cases.py --source`。统一评分完成后报告：`python experiments/ds18_association_evidence_interface_repair/complete_state_cases_postscore.py`。脚本均用新增文件写入，不覆盖旧报告；已有输出时应在独立报告目录复现，不能重跑科学预测或评分。

JSON sources逐一保存真实路径、字节和SHA，包括所有病例封存预测、真实事务、独立自动/事件判定和reference_matches，report_helper绑定实际报告代码。公开产物仅标量、时间、token与来源摘要，不含私有像素。
