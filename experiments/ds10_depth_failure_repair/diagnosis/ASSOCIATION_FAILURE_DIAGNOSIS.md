# DS9真实关联失败复盘：全部19个q与完整ID切换记录

本报告只读DS9封存事件、既有评分、RGB身份审计和切换记录；不重放、不重新评分、不改旧规则或seal。GT仅用于已曝光数据的诊断，不进入任何新选择规则。当前用户目标是超过同源SAM3_NATIVE，纯几何比较只作机制说明，不作为成功门槛。

## 核心结论

DS9 J2有19次首分离决策：9次保持原生正确身份、2次接回原生丢失的旧身份、4次漏掉已有bank一一对应的接回、4次当前post根本不是原bank两条鱼，无法评分为两边恢复。不能把19次H0或缺测全部算成关联失败。

Native共108次CLEAR IDSW，J2为106次；FP487/FN985/DetA89.730606不变。IDF1两者均80.97675951，按固定GT39706、predictions39208可还原全局IDTP均为31951。消除局部switch不必增加全局最优身份匹配的IDTP；具体每条track对全局Hungarian的抵消分量在既有摘要中未列，不能自行编造归因。HOTA/AssA略升，不能称已达到本轮用户的完整目标。

### 先区分事件覆盖和真正能接回的错误

只有8条native switch发生在19个q时点，其中7条在实际post source上，但只有6条属于有bank双射的恢复候选；另2条分别为F470的组外n81/GT4和F1280与bank另一鱼无关的错误post n168/GT5。其余100条在q之外，不是当前首分离选择器的直接决定。下面还把q外分成实际事件窗口内和触发窗口外；窗口内的其他鱼错号不因此成为该事件的合法member。

F1239接回167→136、F1745接回190→188，另一边分别128与9保持；两个native switch真正消除，未新增物理switch事件。但F1239接回的GT4在F1347再次发生native新ID：native为167→170，J2为136→170，同一物理switch仍然存在，只改变其from标签。恢复一次不等于后续身份持续。

F470特别需要单列：bank参考希望82→1，但CLEAR此前GT9的public已经是24，q记录24→82。进入事件前source1与bank仍是同一RGB参考，不代表群组期间GT9从未被carrier24覆盖。此时接回bank1也可能仍产生24→1的CLEAR切换，不能承诺消除当前switch。q同时另有n81/GT4的20→81错号，超出本事件两post。

## 全部19个q病例表

表中μ/σ仅为预测统计量，不能认证鱼体表面或mm准确度。A/B是该事件冻结角色；正确/错误均相对实际bank锚点RGB身份。背景模型、均匀候选先验、几何和log9均来自原冻结方法。

|q|原生/实际J2结果|参考应接回的两边|J2选择/事务|depth边|A历史点数 μ/σ mm|B历史点数 μ/σ mm|机制分类|
|---:|---|---|---|---:|---|---|---|
|398|UNKNOWN / UNSCORABLE_OR_NO_BIJECTION|UNKNOWN|H0 / LOCAL_FALLBACK_COMMITTED|4|4 / 1089.53/325.57|10 / 1181.61/95.63|post与bank不是同一两鱼，不可评分|
|415|正确 / CORRECT|70→70, 30→30|H0 / LOCAL_FALLBACK_COMMITTED|4|2 / 1065.98/145.23|10 / 970.06/101.88|原生正确，保持|
|419|正确 / CORRECT|21→21, 2→2|H0 / LOCAL_FALLBACK_COMMITTED|2|1 / 1158.70/257.80|0 / UNKNOWN|原生正确，保持|
|434|UNKNOWN / UNSCORABLE_OR_NO_BIJECTION|UNKNOWN|H2 / LOCAL_FALLBACK_COMMITTED|2|5 / 1094.76/190.54|0 / UNKNOWN|post与bank不是同一两鱼，不可评分|
|470|错误 / WRONG|82→1, 24→24|H0 / LOCAL_FALLBACK_COMMITTED|2|0 / UNKNOWN|10 / 1987.27/157.52|有参考的接回遗漏|
|519|正确 / CORRECT|50→50, 24→24|H0 / LOCAL_FALLBACK_COMMITTED|4|3 / 1169.24/328.86|10 / 926.49/37.33|原生正确，保持|
|764|错误 / WRONG|95→95, 118→100|H0 / LOCAL_FALLBACK_COMMITTED|4|9 / 925.19/116.96|2 / 1181.42/544.09|有参考的接回遗漏|
|787|正确 / CORRECT|108→108, 101→101|H0 / LOCAL_FALLBACK_COMMITTED|0|0 / UNKNOWN|0 / UNKNOWN|原生正确，保持|
|1027|正确 / CORRECT|137→137, 95→95|H0 / LOCAL_FALLBACK_COMMITTED|4|10 / 936.41/46.49|10 / 795.83/64.41|原生正确，保持|
|1039|正确 / CORRECT|119→119, 108→108|H0 / LOCAL_FALLBACK_COMMITTED|4|10 / 1189.12/79.92|3 / 878.81/1069.87|原生正确，保持|
|1239|错误 / CORRECT|167→136, 128→128|H2 / COMMIT|4|1 / 1163.15/303.27|7 / 1110.92/78.95|原生断号，已接回|
|1263|正确 / CORRECT|164→164, 162→162|H0 / LOCAL_FALLBACK_COMMITTED|4|2 / 1174.75/559.49|2 / 1165.46/559.57|原生正确，保持|
|1280|UNKNOWN / UNSCORABLE_OR_NO_BIJECTION|UNKNOWN|H0 / LOCAL_FALLBACK_COMMITTED|4|1 / 1191.09/589.47|2 / 1013.52/423.71|post与bank不是同一两鱼，不可评分|
|1359|正确 / CORRECT|88→88, 163→163|H0 / LOCAL_FALLBACK_COMMITTED|0|0 / UNKNOWN|0 / UNKNOWN|原生正确，保持|
|1390|错误 / WRONG|157→157, 172→170|H0 / LOCAL_FALLBACK_COMMITTED|4|8 / 1228.63/149.70|1 / 1161.67/363.35|有参考的接回遗漏|
|1504|UNKNOWN / UNSCORABLE_OR_NO_BIJECTION|UNKNOWN|H0 / LOCAL_FALLBACK_COMMITTED|2|6 / 1238.57/577.72|0 / UNKNOWN|post与bank不是同一两鱼，不可评分|
|1719|正确 / CORRECT|177→177, 159→159|H0 / LOCAL_FALLBACK_COMMITTED|2|0 / UNKNOWN|10 / 1184.95/65.02|原生正确，保持|
|1745|错误 / CORRECT|190→188, 9→9|H2 / COMMIT|0|10 / 853.62/63.80|10 / 1027.81/94.87|原生断号，已接回|
|1805|错误 / WRONG|194→149, 151→151|H0 / LOCAL_FALLBACK_COMMITTED|4|10 / 1124.42/252.55|7 / 1027.11/166.20|有参考的接回遗漏|

## 完整切换覆盖分类

|分支|q两post|q其他source|事件窗口内但不在q|全部事件窗口外|
|---|---:|---:|---:|---:|
|SAM3_NATIVE|7|1|37|63|
|J2_RESTORED_DEPTH|5|1|37|63|

## 四个漏接回事件：失败机制与预测-only修复上界

这四次正确候选均为H1，相对H0只新增一条旧角色→新source关联；另一条相同role/source边的geometry、depth和prior精确抵消。H0新增source边使用共同背景LR0。设新增边得到不可能的理想预测：μ直接等于当前观测，forecast σ仅15mm；保留真实post噪声与原背景。归一化t4峰值为 Γ(2.5)/[Γ(2)√(4π)×combined_sigma]，因此下列是对任何仅改forecast的保守最优上界。它不是新算法，绝不输入GT或理想μ到选择器。

|q|正确−H0的geometry|当前depth差|当前joint差|理想预测depth最大LR|joint最大上界|log9是否可达|
|---:|---:|---:|---:|---:|---:|---|
|470|-0.185912|0.000000|-0.185912|1.026985|0.841073|不能，低于2.197225|
|764|0.552097|-1.590263|-1.038167|0.904196|1.456293|不能，低于2.197225|
|1390|0.994005|-0.895782|0.098223|1.707191|2.701196|理论可达但历史不足|
|1805|0.755392|-1.116539|-0.361147|1.036313|1.791705|不能，低于2.197225|

- **F470**：应恢复82→1，但A没有任何可用depth历史。B的旧WLS预测μ1987.27mm、斜率+921.04mm/s；当前两post仅1179.15/1158.64mm。这个均值外推已偏离当前观测，scale157.52mm中过程项只占8.48%，并非单纯“process过宽”。正确边A既无历史，其geometry LR也为负；只改process或WLS都不能跨越上界。群组carrier造成的此前public混用还限制即时IDSW修复。
- **F764**：应恢复118→100。对应B只有2点，保留末测量μ1181.42mm，与post1175.78mm接近；但σ544.09mm使深度新增边LR为−1.590263。99.91%的方差来自gap/pre-span过程项，但短历史不可凭GT答案收缩。即便理想σ15，整幅背景在1175.78mm附近密度很高，最大joint仍1.456293，无法到log9。
- **F1390**：应恢复172→170，B只有1点；旧末值μ1161.67mm，当前post1090.21mm，sigma363.35mm。正确候选虽最佳，joint margin仅0.098218。理想上界允许过门槛，但单点并不能证实真实速度、过去过程率或新的μ，所以必须保留short fallback，不能按GT造出新历史。
- **F1805**：应恢复194→149，A的WLS均值1124.42mm对当前1140.28mm并非严重偏差；但σ252.55mm，过程项只有8.04%，WLS均值传播σ242.18mm。pre拟合残差仅约3–5mm，不能因此直接把所有不确定性降到这个量。正确新增边depth LR为−1.116539，把geometry的+0.755392变为joint−0.361147。只改process不能处理主要传播项；即便μ/σ理想，whole-pixel背景限制仍使joint上界1.791705。

## 无法评分与事务拒绝不是同一个问题

F398/F434/F1280/F1504均有原member继续作为两post之外的residual，分别为59/3/88/132。根据封存RGB参考，当前post第二条鱼与原bank第二角色不一致：F434的新72是GT19，bank3是GT16；F1280的新168是GT5，bank88是GT26；F1504的新180是GT15，bank132是GT8。故不是两鱼真的分离后深度排错那么简单。原post提取仅依据上一group的mask覆盖/邻近和现有quality，可能把第三鱼当split source；guard正确阻止两身份硬写。

F434的深度让H2超过log9，实际却要把仍在场的source3身份移交给别的post；stage被visible-member-residual guard拒绝，发布依旧native/自身alias。绕过guard会把统计信号支持错误事件结构当作恢复。其余三个本身没有接受。新修复继续保留这些UNKNOWN和guard，不从GT筛去某个source，也不暗中扩大两member事务。

## 历史身份与物理深度来源边界

19个q的pre-entry角色均与各自实际bank锚点RGB参考一致。38个冻结depth角色中有30个有历史，既有逐sample参考审计均为同一RGB参考；8个无历史仍UNKNOWN，未发现可用pre depth片段跨到了其他RGB鱼身份。这个结论不能推广到group期间public归属或深度物理表面：F470的CLEAR历史就已不同于bank目标，mask内depth也可能取到水箱表面或错位表面。既有audit不含物理surface/mm真值。

## 最有证据的最小对应修复

需要同时处理两项明确深度模型问题，而不是降低log9或只把σ变小：

1. 足够同版本clean历史时用robust local-level末次真实z，移除短窗WLS斜率长期外推及其均值协方差传播；保留15/60测量floor，原gap增长过程项作为下限，并用过去非负增量扩散率保留动态不稳定证据。n≤2、无历史、版本/risk断开继续原predict/fallback，斜率未知不能写成0。
2. H0代表“当前已经检测到的鱼，但未知旧身份”，其depth null应使用当帧已有合格object测量的等权归一化t4混合，而不是整幅大部分tank像素的median/MAD。所有core_usable当前对象纳入，含query自身、不leaveout，每对象一票；按既有cohort保留15/60有效噪声，少于3component回到原whole-frame null。不能按GT/目标身份/面积挑component。

这是两项深度修复的一个联合版本，不能声称单次试验拆清各自收益。query-inclusive KDE给定当前facts时归一化，但属于数据自适应plug-in identity contrast，不是已校准Bayesian后验；合格mask仍可能采到背景，不能认证物理鱼体。完整4枝SAM3_NATIVE/F9_RESTORED/D10_RAW/D10_RESTORED单次冻结对照，保留所有帧、所有失败、GT仅封存后评分；主目标仅看真实深度枝相对sameNative的IDF1/HOTA/AssA和IDSW，不附加“必须胜纯几何”门槛。

### 尚不能承诺

上述修复不创造F470的缺失A历史，不改F1390的单点fallback，不处理触发窗口外大部分错号，也不保证全段IDTP提高。null和forecast只是因果统计模型，源空间配准、鱼体表面及mm准确度仍UNKNOWN。若最终不提点，必须按新真实逐事件发布和完整评分报告，不用改号数/可用像素数替代跟踪收益。
