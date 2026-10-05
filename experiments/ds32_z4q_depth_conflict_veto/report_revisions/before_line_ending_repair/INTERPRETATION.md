### 分层结论

工程通过：两条真实矩阵入口、来源/状态/首次发布与评分封存链跑通。输入是实际同源SAM3和原始深度；观察来源连续性只按当前合同认证，不等于物理身份已认证。深度增量未观察到：全段10509条查询，1552条原合法候选，0条可靠矛盾/实际删边，三分支中的本轮版与原Z4Q所有发布和六项指标完全一致。

1552条原合法候选分解：728条预测过宽，698条连续可靠历史不足，115条精确anchor未注册/已改变，1条当前深度不可靠；只有10条进入实际残差比较，全部位于LW弱参考段，均无冲突。其余8957条原非法候选不算新增保护。9508条当前质量可用与4071条WLS查询不能当成可靠否决覆盖率。

实际原接受动作90次，按各段现有参考为17错误、16正确、57不可评分；16正确包含2次弱参考判定。全部17错误位于Feeding，15次D1_DELAYED、2次BIRTH_REFINE。14次被预测尺度上限挡住，2次分别仅有1/2点，1次anchor未注册；没有一次进入可靠冲突检验。额外bank参考逐例独立核验也均为不同物理参考；F1390的原打分参考与额外bank参考不同，不能无条件移用原判定。

14次错误WLS的实际拟合跨度只有0.166–0.299秒，预测尺度94.051–1067.153mm。全部原合法WLS查询的拟合跨度中位数0.299秒，预测尺度中位数406.827mm。这里尺度是未标定的不确定性代理；短窗斜率与过程项外推到数秒以后，已无法满足本轮≤60mm合同。这揭示短窗预测在实际重接时距上未提供可用否决证据；更窄尺度是否物理合理仍UNKNOWN，不能证明正确物理区间应该只有60mm，也不能靠截断尺度制造可靠性。

F159错误边native26→public16：0.299秒历史外推4.817秒，尺度378.332mm；当前实际core深度1190.704mm，预测1185.651mm，事后诊断差仅5.053mm。它说明宽尺度不是唯一障碍，错误候选的当前实测深度也可接近目标预测均值；目标鱼在q的实际深度未据此认证。F468是BIRTH_REFINE，0.299秒外推2.725秒，尺度224.808mm；不能因kind=reconnect误写成D1。

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
