## 完整主表

|范围|分支|IDF1|HOTA|AssA|IDSW|FP|FN|
|---|---|---:|---:|---:|---:|---:|---:|
|Feeding1471|SAM3_NATIVE|80.976760|79.964056|71.530499|108|487|985|
|Feeding1471|Z4Q_FROZEN|81.716806|79.859851|71.341782|132|487|985|
|Feeding1471|DS16_ORDER|81.716806|79.859851|71.341782|132|487|985|
|Feeding1471|ACTIVITY_ORDER|81.901817|80.092360|71.759796|131|487|985|
|Feeding1471|MIXED_ORDER|81.245406|79.510342|70.726688|129|487|985|
|Feeding1471|MIXED_OFF|81.514053|79.932020|71.472973|128|487|985|
|fishsa_development_8400|SAM3_NATIVE|91.313288|73.346143|69.186768|5|194|323|
|fishsa_development_8400|Z4Q_FROZEN|99.333472|77.829488|77.907638|6|194|323|
|fishsa_development_8400|DS16_ORDER|99.333472|77.829488|77.907638|6|194|323|
|fishsa_development_8400|ACTIVITY_ORDER|99.212286|77.721707|77.691160|8|194|323|
|fishsa_development_8400|MIXED_ORDER|99.244072|77.750512|77.749014|8|194|323|
|fishsa_development_8400|MIXED_OFF|99.244072|77.750512|77.749014|8|194|323|
|fishsa_validation_2888|SAM3_NATIVE|76.456444|66.435529|55.196059|8|298|423|
|fishsa_validation_2888|Z4Q_FROZEN|80.697587|69.243869|60.074321|9|298|423|
|fishsa_validation_2888|DS16_ORDER|80.697587|69.243869|60.074321|9|298|423|
|fishsa_validation_2888|ACTIVITY_ORDER|80.691793|69.237986|60.064093|11|298|423|
|fishsa_validation_2888|MIXED_ORDER|80.413685|68.954661|59.571269|11|298|423|
|fishsa_validation_2888|MIXED_OFF|81.786842|69.116217|59.851590|13|298|423|
|L3|SAM3_NATIVE|72.426787|75.362607|94.259655|1|14677|0|
|L3|Z4Q_FROZEN|74.745256|77.171558|98.839045|2|14677|0|
|L3|DS16_ORDER|72.426787|75.362607|94.259655|1|14677|0|
|L3|ACTIVITY_ORDER|72.426787|75.362607|94.259655|1|14677|0|
|L3|MIXED_ORDER|72.426787|75.362607|94.259655|1|14677|0|
|L3|MIXED_OFF|62.838603|68.214192|77.225991|3|14677|0|
|LW|SAM3_NATIVE|60.613534|66.369067|77.555121|7|16493|28|
|LW|Z4Q_FROZEN|64.329395|68.991721|83.805597|10|16493|28|
|LW|DS16_ORDER|64.329395|68.995155|83.813941|9|16493|28|
|LW|ACTIVITY_ORDER|60.613534|66.270067|77.323924|9|16493|28|
|LW|MIXED_ORDER|60.613534|66.362048|77.538718|9|16493|28|
|LW|MIXED_OFF|60.613534|66.362048|77.538718|9|16493|28|

## MIXED_ORDER 真实差值

|范围|参照|ΔIDF1|ΔHOTA|ΔAssA|ΔIDSW|
|---|---|---:|---:|---:|---:|
|Feeding1471|vs_native|+0.268647|-0.453713|-0.803811|+21|
|Feeding1471|vs_original_z4q|-0.471399|-0.349509|-0.615094|-3|
|Feeding1471|vs_same_interface|-0.656411|-0.582017|-1.033108|-2|
|Feeding1471|ordinal_vs_off|-0.268647|-0.421677|-0.746284|+1|
|Feeding1471|vs_archived_ds17|-0.106445|-0.038320|-0.071287|-1|
|fishsa_development_8400|vs_native|+7.930784|+4.404369|+8.562246|+3|
|fishsa_development_8400|vs_original_z4q|-0.089400|-0.078975|-0.158624|+2|
|fishsa_development_8400|vs_same_interface|+0.031787|+0.028805|+0.057854|+0|
|fishsa_development_8400|ordinal_vs_off|+0.000000|+0.000000|+0.000000|+0|
|fishsa_development_8400|vs_archived_ds17|+7.241410|+3.259721|+6.384964|+1|
|fishsa_validation_2888|vs_native|+3.957241|+2.519132|+4.375209|+3|
|fishsa_validation_2888|vs_original_z4q|-0.283902|-0.289208|-0.503053|+2|
|fishsa_validation_2888|vs_same_interface|-0.278108|-0.283326|-0.492825|+0|
|fishsa_validation_2888|ordinal_vs_off|-1.373157|-0.161556|-0.280321|-2|
|fishsa_validation_2888|vs_archived_ds17|+0.000000|+0.000000|+0.000000|+0|
|L3|vs_native|+0.000000|+0.000000|+0.000000|+0|
|L3|vs_original_z4q|-2.318468|-1.808950|-4.579391|-1|
|L3|vs_same_interface|+0.000000|+0.000000|+0.000000|+0|
|L3|ordinal_vs_off|+9.588185|+7.148416|+17.033664|-2|
|L3|vs_archived_ds17|-2.318468|-1.808950|-4.579391|-1|
|LW|vs_native|+0.000000|-0.007019|-0.016404|+2|
|LW|vs_original_z4q|-3.715862|-2.629673|-6.266880|-1|
|LW|vs_same_interface|+0.000000|+0.091981|+0.214794|+0|
|LW|ordinal_vs_off|+0.000000|+0.000000|+0.000000|+0|
|LW|vs_archived_ds17|-3.715862|-2.617077|-6.236280|+1|

旧 DS17 是只读归档诊断列，不混入本轮六臂。恢复原 Z4Q 的提升叫止损；相同接口底座上的增量才可归于本轮组合质量策略。少切换不等于更高 IDF1/HOTA/AssA。

## 真实动作与边界

MIXED_ORDER 原自动 accepted=76，实际首次发布且 durable=76；实际bank参考相对物理判定 {'WRONG': 13, 'CORRECT': 14, 'UNSCORABLE': 49}；进入前公共身份语义 {'CONSISTENT_PUBLIC_ORIGIN': 24, 'UNSCORABLE_PUBLIC_ORIGIN': 50, 'PREEXISTING_PUBLIC_ORIGIN_MISMATCH': 2}；严格bank+公共起源联合判定 {'WRONG': 14, 'CORRECT': 12, 'UNSCORABLE': 50}；偶然回到公共起源但不符合实际bank的次数=0，不算物理恢复。组 q=50；实际提交的 pre 共识判定 {'NOT_COMMITTED': 50, 'NOT_AVAILABLE': 45}。未知、不可评分与未提交没有算作正确。

所有新增/消除切换、D1/BIRTH 来源、逐候选拒绝/缺测、group q 当前首帧映射与 literal/pre 共识分列见 run/POSTSEAL_REPORT.json、各段 AUTOMATIC_RECONNECT_AUDIT.json、EVENT_AUDIT.json 与 TRANSACTIONS.jsonl.gz。

工程单测/真实前缀/实际 ROI 来源核对独立于指标。统计签名认证采样来源，不证明鱼身份；上下关系因子仍是有条件、未校准的代理。Feeding 是固定四段共1471帧，其余436保存帧未纳入。FishSA 旧开发/验证已曝光；L3/LW 为未审查预标注，不能称跨数据集强泛化。

全部 mask、残片与 ID 都评分；每个分支继续自己状态。所有预测与访问封存后才评分，没有GT选动作或事后改历史。私有 depth/mask 可视化不进入 Git，完整本地路径/字节/SHA 见 PRIVATE_VISUALS.json 和 RESTRICTED_ARTIFACTS.json。

## 复现与封存

测量事实与历史事实记录在内部验证后只读共享，150帧真实预测/证据与优化前完全一致；普通JSON输入仍完整验签。这是正常分支防写污染约束，不是隔离同进程恶意Python程序。第一次慢速工程前缀及后续LW旧存储前缀在正式冻结前终止，部分输出与日志保留在受限清单；四个已完成真实前缀保留，LW由最终存储版本重新回放。同样科学逻辑，仅存储优化，没有GT评分、模型调用或正式版本择优。

MIXED_DEPTH.jsonl.gz 是含完整分块SHA/字节数的JSONL引用；实际全量行在同目录MIXED_DEPTH.part*.jsonl.gz。common.rows验证每块后读取，未截断证据。

实际新bank参考的恢复正确性、进入前公共ID起源是否已污染、严格联合判定分列。统一TrackEval评分公式未改变；移除“mask相同就必然FP/FN相等”的错误验收假设，记录真实FP/FN。官方CLEAR优先历史匹配，可因ID变化改变匹配数量；合成数学反例保存在EVALUATION_MASK_INVARIANT_CHECK.json，未读取真实GT。
复用受限 DS14 来源与现有依赖，在全新输出目录依次运行 tests、source_population_check、check_prefix、check_real_slices、freeze、orchestrate、baseline_check、score、ds16_full_parity、postseal_report、visualize_postseal、build_report。不能覆盖旧目录/旧seal。EXECUTION_LOG.jsonl 保存实际命令、退出、耗时与完整日志摘要。

本冻结版本完成后停止。下一步只在 NEXT_STEP_PLAN.md 规划；不自动调用大模型、训练或再次调参。
