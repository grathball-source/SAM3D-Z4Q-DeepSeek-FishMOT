# DS32 最终报告：原 Z4Q 候选边上的可靠深度冲突否决

主判定：**NO_EFFECT_FULL_PUBLICATIONS_EQUAL_TO_ORIGINAL_Z4Q**。八段20098帧、三分支60294帧全部完成，181842张原始mask保留。工程检查通过与深度提点分开判断；实际指标如下。

## 本轮改动

保留原Z4Q的native返回优先、D1_DELAYED、BIRTH_REFINE、占用、alias、bank、pending、出生确认、隔离与首次发布事务。只在两条真实候选入口入矩阵前查询独立深度证据；仅删除存在可靠矛盾的一条原合法边，其余候选、原成本和dummy保持原值。不能把整行删除称单边；不能把原已非法边上的矛盾称新增保护。

证据独立保存live片段与精确anchor registry。只有原引擎实际写入的clean bank参考才注册，按保存源域、精确(frame/native/public/mask)、出现连续generation、public epoch和风险片段绑定。当前弱观测切断live，不删除未改变的冻结anchor。至少5个连续同版本有效点，保留30点，最近10点用原DS1真实时间WLS；不跨风险补点，不把当前q写进pre，不读未来帧。

使用同源原始深度的已封存DS18 adaptive exclusive-core与去重来源统计；whole/core任一混层、未认证/共享来源、少于16独立点、覆盖不足0.2、尺度超过60mm均UNKNOWN。候选当前有邻鱼时，只允许实际可靠且无混层的exclusive core提供证据；接触、匿名观测仍不能更新个体历史。质量通过不认证该像素一定属于正确鱼体。

固定否决条件：WLS预测和当前深度均有效且尺度≤60mm；abs(z−mu)>max(60mm,3×hypot(预测尺度,当前尺度))。12秒过期，尺度底噪15mm。预测尺度上限与系数3是预先冻结的保守工程假设，未经物理/统计标定，不能称3σ准确率。没有深度相似奖励或背景密度比；不假设上下关系永远不变。

无可靠矛盾时，逐帧验证本分支同一前状态的原控制器完整状态与输出一致。发生否决后继续自身真实状态，不复制外部B0，不只改最终输出。Native与原Z4Q的全预测和所有指标严格复现旧封存。

## 冻结、输入与工程证据

12/12直接相关状态/来源/两入口检查通过；真实200帧关闭模块、200帧启用模块、含F364的205帧切片通过。冻结前发现并修复BirthRefine邻接见证被无条件null，以及旧评分模块同名配置导入冲突；旧源码、检查收据、失败日志和切片只读保留，未评分或拼入正式结果。最终合同READY和FROZEN_CONTRACT_AUDIT绑定实际字节。

输入/代码/实际常数/评分在正式START前封存；全部正式预测与访问记录封存后，才读现有已曝光参考；本轮无可用单边反事实项，未运行反事实。START和评分均核验source manifest、输入、原始来源、DS18完整缓存、producer、旧预测seal、runtime与代码字节。没有GT挑选候选、q或history。

旧官方评分适配器为动态载入，未自动枚举到runtime.code；它在正式START前已有独立导入SHA。DS14数学另由DS1/postseal.py的AST提取clear_step，该源同样未自动枚举。score_checked在读GT前验证导入receipt、实际适配器及clear_step源均与已冻结Git BASE原blob一致，记录SCORING_BINDING_ACCEPTANCE；这一绑定边界及工程补齐如实保留，数学、参考或预测均未修改。

四段Feeding1471帧分属独立身份域汇总；8400与2888为既有已曝光开发/历史验证；L3/LW参考为未经独立验收的预测派生预标注，只作弱参考诊断。source generation仅认证保存片段内连续出现，缺少producer session/reset metadata，不能认证未标记的内部instance变化。本轮不是新的盲测。

## 完整指标

|数据|分支|IDF1|HOTA|AssA|IDSW|FP|FN|
|---|---|---:|---:|---:|---:|---:|---:|
|feeding_000000_000199|SAM3_NATIVE|92.889759|91.362522|88.085877|10|76|143|
|feeding_000000_000199|Z4Q_FROZEN|92.125617|90.483748|86.399664|12|76|143|
|feeding_000000_000199|Z4Q_DEPTH_VETO|92.125617|90.483748|86.399664|12|76|143|
|feeding_000351_000555|SAM3_NATIVE|82.927271|78.582844|72.182690|22|148|201|
|feeding_000351_000555|Z4Q_FROZEN|82.891042|78.147798|71.429933|24|148|201|
|feeding_000351_000555|Z4Q_DEPTH_VETO|82.891042|78.147798|71.429933|24|148|201|
|feeding_000701_001060|SAM3_NATIVE|77.428039|75.545022|65.006580|36|154|278|
|feeding_000701_001060|Z4Q_FROZEN|75.636778|73.560905|61.642162|42|154|278|
|feeding_000701_001060|Z4Q_DEPTH_VETO|75.636778|73.560905|61.642162|42|154|278|
|feeding_001201_001906|SAM3_NATIVE|78.839951|78.727248|68.089322|40|109|363|
|feeding_001201_001906|Z4Q_FROZEN|81.525935|79.892513|70.113143|54|109|363|
|feeding_001201_001906|Z4Q_DEPTH_VETO|81.525935|79.892513|70.113143|54|109|363|
|fishsa_development_8400|SAM3_NATIVE|91.313288|73.346143|69.186768|5|194|323|
|fishsa_development_8400|Z4Q_FROZEN|99.333472|77.829488|77.907638|6|194|323|
|fishsa_development_8400|Z4Q_DEPTH_VETO|99.333472|77.829488|77.907638|6|194|323|
|fishsa_validation_2888|SAM3_NATIVE|76.456444|66.435529|55.196059|8|298|423|
|fishsa_validation_2888|Z4Q_FROZEN|80.697587|69.243869|60.074321|9|298|423|
|fishsa_validation_2888|Z4Q_DEPTH_VETO|80.697587|69.243869|60.074321|9|298|423|
|L3|SAM3_NATIVE|72.426787|75.362607|94.259655|1|14677|0|
|L3|Z4Q_FROZEN|74.745256|77.171558|98.839045|2|14677|0|
|L3|Z4Q_DEPTH_VETO|74.745256|77.171558|98.839045|2|14677|0|
|LW|SAM3_NATIVE|60.613534|66.369067|77.555121|7|16493|28|
|LW|Z4Q_FROZEN|64.329395|68.991721|83.805597|10|16493|28|
|LW|Z4Q_DEPTH_VETO|64.329395|68.991721|83.805597|10|16493|28|
|Feeding pooled 1471|SAM3_NATIVE|80.976760|79.964056|71.530499|108|487|985|
|Feeding pooled 1471|Z4Q_FROZEN|81.716806|79.859851|71.341782|132|487|985|
|Feeding pooled 1471|Z4Q_DEPTH_VETO|81.716806|79.859851|71.341782|132|487|985|

## 主比较真实差值

|数据|比较|ΔIDF1|ΔHOTA|ΔAssA|ΔIDSW|ΔFP|ΔFN|
|---|---|---:|---:|---:|---:|---:|---:|
|Feeding pooled 1471|Z4Q_DEPTH_VETO−SAM3_NATIVE|+0.740046|-0.104205|-0.188717|+24|+0|+0|
|Feeding pooled 1471|Z4Q_DEPTH_VETO−Z4Q_FROZEN|+0.000000|+0.000000|+0.000000|+0|+0|+0|
|fishsa_development_8400|Z4Q_DEPTH_VETO−SAM3_NATIVE|+8.020185|+4.483345|+8.720871|+1|+0|+0|
|fishsa_development_8400|Z4Q_DEPTH_VETO−Z4Q_FROZEN|+0.000000|+0.000000|+0.000000|+0|+0|+0|
|fishsa_validation_2888|Z4Q_DEPTH_VETO−SAM3_NATIVE|+4.241143|+2.808340|+4.878262|+1|+0|+0|
|fishsa_validation_2888|Z4Q_DEPTH_VETO−Z4Q_FROZEN|+0.000000|+0.000000|+0.000000|+0|+0|+0|
|L3|Z4Q_DEPTH_VETO−SAM3_NATIVE|+2.318468|+1.808950|+4.579391|+1|+0|+0|
|L3|Z4Q_DEPTH_VETO−Z4Q_FROZEN|+0.000000|+0.000000|+0.000000|+0|+0|+0|
|LW|Z4Q_DEPTH_VETO−SAM3_NATIVE|+3.715862|+2.622654|+6.250476|+3|+0|+0|
|LW|Z4Q_DEPTH_VETO−Z4Q_FROZEN|+0.000000|+0.000000|+0.000000|+0|+0|+0|

## 真实候选、状态和发布变化

|数据|查询边|原合法删边|原非法冗余冲突|同前状态提交变化|相对Z4Q发布改变帧|新增切换记录|消除切换记录|
|---|---:|---:|---:|---:|---:|---:|---:|
|feeding_000000_000199|168|0|0|0|0|0|0|
|feeding_000351_000555|466|0|0|0|0|0|0|
|feeding_000701_001060|1345|0|0|0|0|0|0|
|feeding_001201_001906|1469|0|0|0|0|0|0|
|fishsa_development_8400|13|0|0|0|0|0|0|
|fishsa_validation_2888|85|0|0|0|0|0|0|
|L3|843|0|0|0|0|0|0|
|LW|6120|0|0|0|0|0|0|

全段计数：{"hook_edges": 10509, "raw_conflicts": 0, "redundant_conflicts": 0, "legal_edges_deleted": 0, "changed_frames": 0, "original_own_state_null_checks": 20098, "veto_frames": 0, "selected_commit_changes": 0}。hook边、可靠矛盾、原非法冗余矛盾、入矩阵删边、真实提交变化及首次发布变化分列；删边可能本来就不会被选中，不能算成功恢复。

原合法实际删边按其真实额外bank参考及各段现有参考核验：{"feeding_000000_000199": {}, "feeding_000351_000555": {}, "feeding_000701_001060": {}, "feeding_001201_001906": {}, "fishsa_development_8400": {}, "fishsa_validation_2888": {}, "L3": {}, "LW": {}}。L3/LW仅有弱参考，不认证物理身份真值。BirthRefine原打分参考与额外bank参考分别记录，不默认为同一个。正确/有害/不可评分不合并，进入前public已错也不能靠整数换回冒充物理恢复。

原Z4Q逐次切换覆盖：{"original_switches": 159, "NOT_ACCEPTED_AT_THIS_ROUND_TWO_ENTRANCES": 125, "NATIVE_SWITCH_FRAME_PRESENT": 127, "NOT_ACCEPTED_AT_THIS_ROUND_TWO_ENTRANCES|NATIVE_SWITCH_FRAME_PRESENT": 125, "ACCEPTED_D1_OR_BIRTH_CURRENT_NATIVE_PUBLIC": 34, "NO_NATIVE_SWITCH_SAME_FRAME": 32, "ACCEPTED_D1_OR_BIRTH_CURRENT_NATIVE_PUBLIC|NO_NATIVE_SWITCH_SAME_FRAME": 32, "ACCEPTED_D1_OR_BIRTH_CURRENT_NATIVE_PUBLIC|NATIVE_SWITCH_FRAME_PRESENT": 2}。逐次按实际global_frame对齐；原生对应同时绑定gt_id。没有本帧D1/Birth接受提交，只能说明不在本轮两个入口的当帧接受范围，不能推断没有查询、没有先前alias影响或没有关联因果。逐次当前native/public、查询原因和状态分支见ANALYSIS_POSTSEAL。

新增/消除切换为逐次实际CLEAR匹配记录差，净差不能当新增错误数；整数标签变化可能改变同一物理切换的记录键，需结合SWITCHES/真实发布及REFERENCE_MATCHES解释。FP/FN不删除任何mask或残片。查询可用性、未建立/换锚/过期与所有null原因见ANALYSIS_POSTSEAL及逐帧TRANSACTIONS。

## 单边真实状态反事实与固定回归点

### 分层结论

工程通过：两条真实矩阵入口、来源/状态/首次发布与评分封存链跑通。输入是实际同源SAM3和原始深度；观察来源连续性只按当前合同认证，不等于物理身份已认证。深度增量未观察到：全段10509条查询，1552条原合法候选，0条可靠矛盾/实际删边，三分支中的本轮版与原Z4Q所有发布和六项指标完全一致。

1552条原合法候选分解：728条预测过宽，698条连续可靠历史不足，115条精确anchor未注册/已改变，1条当前深度不可靠；只有10条进入实际残差比较，全部位于LW弱参考段，均无冲突。其余8957条原非法候选不算新增保护。9508条当前质量可用与4071条WLS查询不能当成可靠否决覆盖率。

实际原接受动作90次，按各段现有参考为17错误、16正确、57不可评分；16正确包含2次弱参考判定。全部17错误位于Feeding，15次D1_DELAYED、2次BIRTH_REFINE。14次被预测尺度上限挡住，2次分别仅有1/2点，1次anchor未注册；没有一次进入可靠冲突检验。额外bank参考逐例独立核验也均为不同物理参考；F1390的原打分参考与额外bank参考不同，不能无条件移用原判定。

14次错误WLS的实际拟合跨度只有0.166–0.299秒，预测尺度94.051–1067.153mm。全部原合法WLS查询的拟合跨度中位数0.299秒，预测尺度中位数406.827mm。这里尺度是未标定的不确定性代理；短窗斜率与过程项外推到数秒以后，已无法满足本轮≤60mm合同。这揭示短窗预测在实际重接时距上未提供可用否决证据；更窄尺度是否物理合理仍UNKNOWN，不能证明正确物理区间应该只有60mm，也不能靠截断尺度制造可靠性。

F159错误边native26→public16：0.299秒历史外推4.817秒，尺度378.332mm；当前实际core深度1190.704mm，预测1185.651mm，事后诊断差仅5.053mm。它说明宽尺度不是唯一障碍，错误身份也可能处于近似深度。F468是BIRTH_REFINE，0.299秒外推2.725秒，尺度224.808mm；不能因kind=reconnect误写成D1。

可绑定的16条错误目标片段均没有“仅UNRELIABLE_CURRENT_DEPTH中断”的前置断点，另1条无法绑定。两个短历史错误来自真实接触后新片段；不可跨接触取旧点。纯软件深度断点只出现在其他正确/不可评分动作，不能预报只续接缺测历史就能解决这17次错误；UNRELIABLE_CURRENT_DEPTH本身也不等于传感器空洞。

原Z4Q的159次CLEAR切换中，34次有当帧对应D1/Birth接受，125次无这两入口的当帧接受；后125次均有native同gt_id/global_frame切换。该事实仅描述覆盖，不能推断无查询、无更早alias影响，或全部为SAM3根因。净切换差与每次新增/消除记录分开。

F364原Z4Q本来就保留native30/66，本轮未新增修复；F3902原Birth native7→public0动作及当帧映射完整保留。没有可靠矛盾触发，ALLOW/VETO反事实未运行，这是证据边界；没有伪造一个“成功保护”样例。

### 全部17条错误边：运行事实与事后诊断分列

下表帧为global_frame。当前值来自实际exclusive-core测量；mu/尺度来自预测，不是观测。事后差仅对已存在且usable的预测与实际观测计算；运行在宽尺度/短历史等处早停，原运行残差及阈值仍为缺失。本表不代表曾执行放宽阈值试验。完整来源、两参考、断点与fact_id见INTERPRETATION_FACTS/ANALYSIS_POSTSEAL。

|来源|帧|阶段|native→public|原运行原因|当前mm|预测mu mm|预测尺度mm|事后差mm|
|---|---:|---|---|---|---:|---:|---:|---:|
|feeding_000000_000199|159|D1_DELAYED|26→16|TARGET_FORECAST_TOO_BROAD|1190.704|1185.651|378.332|5.053|
|feeding_000000_000199|190|D1_DELAYED|30→8|TARGET_FORECAST_TOO_BROAD|954.737|1080.551|568.363|UNKNOWN|
|feeding_000351_000555|468|BIRTH_REFINE|80→21|TARGET_FORECAST_TOO_BROAD|1149.741|1082.950|224.808|66.791|
|feeding_000351_000555|522|D1_DELAYED|83→73|TARGET_FORECAST_TOO_BROAD|1105.538|1358.898|356.818|253.360|
|feeding_000701_001060|834|D1_DELAYED|118→99|TARGET_INSUFFICIENT_CONTIGUOUS_HISTORY|1175.746|UNKNOWN|UNKNOWN|UNKNOWN|
|feeding_000701_001060|849|D1_DELAYED|119→70|TARGET_FORECAST_TOO_BROAD|987.012|606.827|620.934|380.186|
|feeding_000701_001060|897|D1_DELAYED|127→106|TARGET_FORECAST_TOO_BROAD|1177.522|1345.774|731.924|UNKNOWN|
|feeding_000701_001060|969|D1_DELAYED|129→91|TARGET_ANCHOR_CHANGED_OR_UNREGISTERED_REFERENCE|979.744|UNKNOWN|UNKNOWN|UNKNOWN|
|feeding_001201_001906|1390|BIRTH_REFINE|172→126|TARGET_FORECAST_TOO_BROAD|1090.206|1080.101|277.804|10.105|
|feeding_001201_001906|1404|D1_DELAYED|168→136|TARGET_FORECAST_TOO_BROAD|1160.652|685.448|745.856|475.203|
|feeding_001201_001906|1516|D1_DELAYED|178→119|TARGET_INSUFFICIENT_CONTIGUOUS_HISTORY|1172.094|UNKNOWN|UNKNOWN|UNKNOWN|
|feeding_001201_001906|1681|D1_DELAYED|188→125|TARGET_FORECAST_TOO_BROAD|1158.544|1003.033|750.013|155.510|
|feeding_001201_001906|1712|D1_DELAYED|186→166|TARGET_FORECAST_TOO_BROAD|1045.387|2124.102|700.949|1078.714|
|feeding_001201_001906|1751|D1_DELAYED|183→125|TARGET_FORECAST_TOO_BROAD|1136.206|966.806|935.238|169.400|
|feeding_001201_001906|1799|D1_DELAYED|187→164|TARGET_FORECAST_TOO_BROAD|1152.735|1208.446|1067.153|55.712|
|feeding_001201_001906|1888|D1_DELAYED|193→158|TARGET_FORECAST_TOO_BROAD|1145.672|1103.591|285.555|42.081|
|feeding_001201_001906|1893|D1_DELAYED|197→167|TARGET_FORECAST_TOO_BROAD|1154.961|1194.381|94.051|39.421|

该冻结版本结束。工程PASS和原Z4Q既有优势不是本轮深度收益；没有有效否决边，因此可靠冲突的精度/召回及因果反事实收益仍不可估计。

## 耗时与复现

|数据|回放秒数|平均发布秒数|p95秒数|最大秒数|
|---|---:|---:|---:|---:|
|feeding_000000_000199|39.201|0.184789|0.309666|0.338585|
|feeding_000351_000555|91.236|0.433735|0.619003|0.718465|
|feeding_000701_001060|143.541|0.387267|0.585130|0.742401|
|feeding_001201_001906|738.563|1.034658|1.413029|1.509496|
|fishsa_development_8400|5826.692|0.690647|1.141168|1.435658|
|fishsa_validation_2888|1418.203|0.488063|0.745935|0.917605|
|L3|5090.456|1.367034|2.212245|3.003036|
|LW|2781.250|0.761464|1.248662|1.574053|

统一评分501.308秒。发布耗时是保存观测下同机三分支共享CPU回放时间，不含SAM3推理，不称实时部署。实际命令、退出状态与计时见独立EXECUTION_LOG。模型HTTP、smoke、GPU、训练、SAM3新推理、补全与费用全部0。

两张可公开数值SVG来自本轮实际指标、深度事实/候选与发布记录，实际检查后交付；不绘制假设身份或不可见轮廓。受限输入真实路径、字节、SHA及依赖记录在RESTRICTED_ARTIFACTS，像素/凭据不入Git。代码、测试、配置、数值预测、日志和报告全部main普通提交与推送，REMOTE_VERIFICATION实际读取远端ref和每个公开blob；最后再次核验包含收据的main。

## 未完成边界与唯一下一步

本轮冻结版本结束。没有新盲测、物理深度精度认证、producer session版本认证、合并mask硬拆分、RGB外观/光流、未来补回或大模型。本轮代码/报告交付完整，不将工程PASS、弱参考改善或原Z4Q既有收益称深度增量。

唯一下一步：**校准适配真实重接时距的深度预测均值与不确定性，再验证同一原Z4Q候选边否决。尚未启动。**

依据是17条原错误边中14条因0.166–0.299秒短窗外推导致尺度过宽；F159同时显示异鱼也能近深度。下一轮只改深度预测/不确定性，不接管原Z4Q身份，不以降低60mm门槛或截断尺度来强行获得命中。

1. 按来源元数据和时间顺序固定开发校准/验收区间。对真实同版本clean片段作因果前缀预测，在实际0.03–12秒时距上记录后续测量误差；未持续独立可见的区间保留UNKNOWN，不拿假设路径当测量，不使用GT选择更好锚点或调到错边被拒。
2. 将鱼体内部空间深度散布、代表深度的测量误差、短窗斜率不确定性和长间隔运动风险分开。比较适配真实时间跨度、受历史支持的深度模型，短片段不自动认证长期线性速度；不跨接触、丢失、匿名或身份版本风险凑点。source连续校准仅证明观测一致性，不等于物理身份认证。
3. 校准完成后只冻结一套预测模型与否决规则，保留原实际anchor、两条入口、成本、dummy和发布事务。仍对全部固定来源完整回放；输出封存后逐边评分，报告错边召回、正确边误否决、实际提交及整段指标。若无法区分正确/错误边，明确停止该版本，不靠逐轮放宽追求命中。

本计划不预报提点，不自动启动、不增加模型/API、训练或SAM3推理。
