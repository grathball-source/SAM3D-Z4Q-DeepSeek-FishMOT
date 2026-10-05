# DS30 最终报告：原Z4Q上的深度增量

主判定：**FULL_REPLAY_COMPLETE_NO_DEPTH_STATE_INCREMENT**。八段20098帧、三个独立真实状态分支，总60294分支帧。没有API、模型、GPU、训练、新SAM3或补全；费用0。

## 改动与工程边界

原Z4Q的engine/bank/alias/pending/出生与延迟恢复全部运行。事件管理器只操作旁路克隆；匿名GROUP/post和精确版本pre记录不再冻结或veto原状态。无深度、DEFER、stage失败时提交本分支完整原预览，禁止改用新几何H1或复制其他分支状态。每帧先决定、stage/commit再首次唯一发布；所有原mask与残片保留。

共享native深度来源逐点在两端排除，重新计算原层、连通支持、背景对比、尺度与质量；原量测保留，被排除点计共同无信息，原ROI分母不变。多支持边际化，不择峰。对齐相机Z与native传感器Z是不同坐标，不假设数值相等；深度支持不认证鱼体或永久上下关系。

原0.25深度权重、0.15联合margin与质量门槛不变；本轮事前增加深度自身margin也须≥0.15、且偏好与最终选择一致，避免极弱非零信号给新几何改号放行。仍须原Bridge.stage通过占用、质量、native-return与实际anchor检查。实际bank目标anchor改变则拒绝，不将冻结旧bank强行写回，不制造原候选。

9项必要单测通过；真实4524帧完整engine/previous/epochs/provenance/version与原Z4Q逐帧相同，F3902出生native7→public0保留，F4524为native1→1、native7→0，无额外交换。完整回放前全部运行/评分源码和参数冻结。初始切片与新增状态hash日志后的最终切片均保留，不以预检PASS冒称研究收益。

## 输入与评价边界

固定DS14八段原SAM3保存源、原始raw深度、原scan_v4和首分离q；不按GT改变锚/候选/触发，不使用v3、annotation实例输入、RGB或未来帧。Feeding四段独立ID域汇总1471帧；FishSA8400/2888已曝光开发/历史验证。L3/LW是未经独立验收的预测派生预标注，仅作弱参考诊断；不能当盲测/物理GT/跨域泛化。全部预测和访问seal后才沿旧官方TrackEval完整评分。

## 完整指标

|数据|分支|IDF1|HOTA|AssA|IDSW|FP|FN|
|---|---|---:|---:|---:|---:|---:|---:|
|feeding_000000_000199|SAM3_NATIVE|92.889759|91.362522|88.085877|10|76|143|
|feeding_000000_000199|Z4Q_FROZEN|92.125617|90.483748|86.399664|12|76|143|
|feeding_000000_000199|DEPTH_INCREMENT|92.125617|90.483748|86.399664|12|76|143|
|feeding_000351_000555|SAM3_NATIVE|82.927271|78.582844|72.182690|22|148|201|
|feeding_000351_000555|Z4Q_FROZEN|82.891042|78.147798|71.429933|24|148|201|
|feeding_000351_000555|DEPTH_INCREMENT|82.891042|78.147798|71.429933|24|148|201|
|feeding_000701_001060|SAM3_NATIVE|77.428039|75.545022|65.006580|36|154|278|
|feeding_000701_001060|Z4Q_FROZEN|75.636778|73.560905|61.642162|42|154|278|
|feeding_000701_001060|DEPTH_INCREMENT|75.636778|73.560905|61.642162|42|154|278|
|feeding_001201_001906|SAM3_NATIVE|78.839951|78.727248|68.089322|40|109|363|
|feeding_001201_001906|Z4Q_FROZEN|81.525935|79.892513|70.113143|54|109|363|
|feeding_001201_001906|DEPTH_INCREMENT|81.525935|79.892513|70.113143|54|109|363|
|fishsa_development_8400|SAM3_NATIVE|91.313288|73.346143|69.186768|5|194|323|
|fishsa_development_8400|Z4Q_FROZEN|99.333472|77.829488|77.907638|6|194|323|
|fishsa_development_8400|DEPTH_INCREMENT|99.333472|77.829488|77.907638|6|194|323|
|fishsa_validation_2888|SAM3_NATIVE|76.456444|66.435529|55.196059|8|298|423|
|fishsa_validation_2888|Z4Q_FROZEN|80.697587|69.243869|60.074321|9|298|423|
|fishsa_validation_2888|DEPTH_INCREMENT|80.697587|69.243869|60.074321|9|298|423|
|L3|SAM3_NATIVE|72.426787|75.362607|94.259655|1|14677|0|
|L3|Z4Q_FROZEN|74.745256|77.171558|98.839045|2|14677|0|
|L3|DEPTH_INCREMENT|74.745256|77.171558|98.839045|2|14677|0|
|LW|SAM3_NATIVE|60.613534|66.369067|77.555121|7|16493|28|
|LW|Z4Q_FROZEN|64.329395|68.991721|83.805597|10|16493|28|
|LW|DEPTH_INCREMENT|64.329395|68.991721|83.805597|10|16493|28|
|Feeding pooled 1471|SAM3_NATIVE|80.976760|79.964056|71.530499|108|487|985|
|Feeding pooled 1471|Z4Q_FROZEN|81.716806|79.859851|71.341782|132|487|985|
|Feeding pooled 1471|DEPTH_INCREMENT|81.716806|79.859851|71.341782|132|487|985|

## 主比较的真实差值

|数据|比较|ΔIDF1|ΔHOTA|ΔAssA|ΔIDSW|ΔFP|ΔFN|
|---|---|---:|---:|---:|---:|---:|---:|
|Feeding pooled 1471|DEPTH_INCREMENT−SAM3_NATIVE|+0.740046|-0.104205|-0.188717|+24|+0|+0|
|Feeding pooled 1471|DEPTH_INCREMENT−Z4Q_FROZEN|+0.000000|+0.000000|+0.000000|+0|+0|+0|
|fishsa_development_8400|DEPTH_INCREMENT−SAM3_NATIVE|+8.020185|+4.483345|+8.720871|+1|+0|+0|
|fishsa_development_8400|DEPTH_INCREMENT−Z4Q_FROZEN|+0.000000|+0.000000|+0.000000|+0|+0|+0|
|fishsa_validation_2888|DEPTH_INCREMENT−SAM3_NATIVE|+4.241143|+2.808340|+4.878262|+1|+0|+0|
|fishsa_validation_2888|DEPTH_INCREMENT−Z4Q_FROZEN|+0.000000|+0.000000|+0.000000|+0|+0|+0|
|L3|DEPTH_INCREMENT−SAM3_NATIVE|+2.318468|+1.808950|+4.579391|+1|+0|+0|
|L3|DEPTH_INCREMENT−Z4Q_FROZEN|+0.000000|+0.000000|+0.000000|+0|+0|+0|
|LW|DEPTH_INCREMENT−SAM3_NATIVE|+3.715862|+2.622654|+6.250476|+3|+0|+0|
|LW|DEPTH_INCREMENT−Z4Q_FROZEN|+0.000000|+0.000000|+0.000000|+0|+0|+0|

## 全部事件、准入与实际发布

正式q 50，非null深度 2，实际新增深度提交 0。已stage物理关系计数：{'NO_JOINT_COMMIT': 50}。未提交不能算正确/安全。没有实际修改时恢复原Z4Q只是止损，不能叫深度提点。

|数据|episode|确认merge|无q|q|深度提交|相对原Z4Q改变帧|无事务完整状态检查|
|---|---:|---:|---:|---:|---:|---:|---:|
|feeding_000000_000199|1|1|1|0|0|0|200|
|feeding_000351_000555|11|8|5|6|0|0|205|
|feeding_000701_001060|8|5|3|5|0|0|360|
|feeding_001201_001906|11|10|2|9|0|0|706|
|fishsa_development_8400|13|9|4|9|0|0|8400|
|fishsa_validation_2888|12|7|5|7|0|0|2888|
|L3|11|8|7|4|0|0|3710|
|LW|22|20|12|10|0|0|3629|

## 逐例输入与失败原因

|诊断项|数量|
|---|---:|
|bottleneck/EXPIRED_OR_UNKNOWN_GEOMETRY|1|
|bottleneck/INSUFFICIENT_OR_OPPOSED_DEPTH_OR_TOTAL_MARGIN|2|
|bottleneck/MISSING_EXACT_REFERENCE|5|
|bottleneck/NO_SYNCHRONOUS_PRE|32|
|bottleneck/PRE_CURRENT_OR_AGE_COMMON_NULL|10|
|non_null_depth|2|
|paired_comparisons_remeasured|4|
|q|50|
|raw_DEFER|50|
|real_prefix_exact_publications|4524|
|reason/DEPTH_NOT_DECISIVE_OR_OPPOSES_SELECTED_KEEP_ORIGINAL|2|
|reason/NO_DEPTH_INCREMENT_KEEP_COMPLETE_ORIGINAL_STATE|42|
|reason/UNKNOWN_GEOMETRY|1|
|reason/UNKNOWN_REFERENCE|5|
|stage/DEFER|50|

INPUT_DIAGNOSIS保留每个q的实际pre区间、概率、年龄衰减、深度margin、原始选择、stage错误与首次发布。它区分缺少精确参考、无共时pre、过期几何、共同null、深度/总代价不足和原事务边界；不能把这些全部解释为深度理论无效。

SHARED_SOURCE_DIAGNOSIS仅重测旧DS29输入失败，不作为当前正式q/成绩：Feeding原F398共享1来源后顺序概率约0.770602；L3局部F1421共享20来源后约0.692289。这证实“整支持作废”已修复，不证明顺序方向正确，更不保证当前事件可提交。正式事件使用本分支的新真实参考，不强套旧状态答案。

实际量测producer为本轮unique_supports.py，复用DS25方程而新增共享来源排除和完整重测，不是只改CONFIG或原函数完全不变。原始118个事实与重测8个事实分别保留；不存在实际多合格层，不能以合成多层测试称真实混层已充分验证。

### 为什么不是简单降低门槛就能提点

两个非零案例的深度自身代价间隔仅0.038728/0.052970，均小于冻结0.15，而且偏好均与总代价赢家相反。Feeding原F398：深度偏好H1（50→50、30→59），几何偏好H2；物理参考事后核验30→59为DIFFERENT，该建议整体WRONG。public59仍由可见native59发布，旧成员残片未进入当前两候选，直接建议还违反一对一占用；public50实际bank anchor在q之前也已由F10变为F37。L3局部F1421：深度偏好H2（6→6、9→9），相对弱参考CORRECT，但原Z4Q本来已经同样发布，没有需要新增的修改。

这些是事后对未提交建议的物理/占用诊断，不是新的stage结果或反事实全段指标。不能称降低margin一定能提点，也不能把两个建议全部当深度错误。多数事件的输入历史缺口仍未修复；恢复原Z4Q解决了上一轮共用机制退化，当前深度关联能力仍未得到实际增量证明。细节在ACTIONABILITY_AUDIT。

EVENTS保留所有group/residual及无q；TRANSACTIONS绑定实际自动动作、bank anchor、alias、完整branch状态hash和无事务时原预览hash；PUBLISH_LEDGER绑定决定/事务/实际预测。SWITCHES与SWITCH_CHANGES重算每次切换，新增/消除分别保留，不把净增数当新增错误数。JOINT_ACTION_AUDIT区分原始选择、stage、实际发布、相对实际pre参考的物理关系与进入前public原来源。

## 可视化与耗时

PRIVATE_VISUALS是原始深度/mask与三个分支实际合并前、中、q、q+2发布图；首q/首有效深度/首选择变化按时间显示，失败图在封存评分后选择。q+2只作事后解释，不读未来决策、不回填输出。未使用RGB或GT raster，私有像素不入Git。

正式分段耗时见RUN_SUMMARY；统一评分441.817秒，逐帧实际接收到首次发布延迟见PUBLISH_LEDGER。这是离线CPU保存mask回放，不称实时部署。原始资料、私有图、字节/SHA与本机解释器/deps及复现顺序见RESTRICTED_ARTIFACTS。所有公开成果main非force同步，实际远端ref/每文件hash核验见REMOTE_VERIFICATION。

## 结束与未完成边界

当前冻结版本结束，不滚动调整门槛或挑更容易事件；共同机制修复不等于深度有效。不证明永久深度上下关系，不覆盖未管理并发交互，不将弱预标注当独立GT。唯一下一步：审计原Z4Q全部实际错误及全部候选/事件的覆盖与深度可执行性，定位真正可改变的错误；不能为产生提交直接降门槛。详见NEXT_STEP_PLAN，本轮未执行该后续计划。
