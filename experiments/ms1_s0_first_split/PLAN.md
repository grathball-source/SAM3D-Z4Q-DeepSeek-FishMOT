# MS1-S0：分离第一帧、首次发布前联合恢复旧ID

## 0. 本轮只回答一个问题

仓库：`grathball-source/SAM3D-Z4Q-DeepSeek-FishMOT`
固定审查基点：`70812be385cde8e08340b5f3940ab1c121b54ad0`
建议目录：`experiments/ms1_s0_first_split/`

目标从“先临时输出，分离5帧后作最终恢复”改为：第一次出现现有定义下的两个分离候选观测时，只使用截至该帧的完整进入前历史、合并过程和当前两个观测，在该帧任何持久ID对外发布之前完成一次联合关联。

这是新的决策时序协议。它不是声称当前MS1-R未遵循旧计划；旧计划明确规定等待5帧。

本轮为零分离后前视（post-split lookahead=0）的同步因果回放。可以暂停帧循环等API；不得称为实时低延迟部署。不得先读取后4帧，再把答案回填为第一帧的在线结果。不得先发布临时旧ID/新ID，稍后改历史输出来隐藏切换。

先fetch最新origin/main，阅读新增差异并锁定实际基点。旧MS1/MS1-R输入、响应、预测和seal只读。当前审查已经确认：原S在F2604，first split在F2600；两保护分支相同，物理片段对应H1错误，末帧A参考不可评分。不要用GT指定新的H2或替换有利锚点。

## 1. 复用哪些内容，不做什么

阅读当前：
- `merge_split_manager.py`：`before`、`numeric_choice`、`stage_group_restore`；
- `replay.py`：`manager.before -> preview -> infer -> commit_once -> predictions.write`；
- `event_packet.py`、`provider.py`、`score.py`、`test_ms1r.py`；
- 本次EVENTS、METRICS、PHYSICAL_EVENT_AUDIT、S响应及可视化清单。

复用修复后的group/post/个体历史隔离、native/public键域处理、OLS、深度质量、真实图像通路、简单H1/H2/DEFER解析和官方评分。

不扩大merge扫描，不改其空间/面积阈值，不训练、不加RGB外观、不回到两帧局部匹配、不新开质量门控/独立人工资格审查、不读取未曝光test GT。保留已有30帧历史缓存、最多10个连续有效点的历史估计、两帧merge确认、10秒事件超时。

## 2. 明确定义三种时间

- `split_first_frame`：现有因果条件第一次得到两个当前候选的帧；不能看后续是否持续5帧再回头挑它。
- `evidence_cutoff_frame`：本次模型实际可见的最大证据帧，必须等于`split_first_frame`。
- `first_publish_time_monotonic`：该帧结果第一次写出/发给下游的本地单调时钟。

原视频时间戳用于运动计算；本机monotonic用于延迟，不能拿采集日期与回放当天墙钟相减。

本轮选用严格的first-frame evidence方案，不实现5帧缓存回填方案。后者可另外研究，但不是本轮的“首帧因果匹配”。

## 3. 决策和发布必须一起前移

现代码把`length==1`临时数值对应写到`spec.outputs`，`length==5`才设置q。本轮不能只改CONFIG，必须修改实际控制流，去掉分离首帧先发布provisional mapping的路径。

建议状态：
`MERGED -> FIRST_SPLIT_DECISION_PENDING -> RESOLVED`

第一次出现原规则下的两个分离候选时：
1. 当下就绑定X/Y帧局部观测，不根据未来帧选择命名或排序。
2. 设置q=split_first_frame；post各只有当前这一个样本。
3. 保存当前分支事务前状态，构建输入；不发布该帧的provisional public ID。
4. 数值分支计算当前条件下的一次匹配；模型分支执行S0。
5. 验证完整一对一占用及episode版本，真实stage/commit。
6. 从选定状态第一次写出该帧预测，继而处理下一帧。

`preview`中为满足内部接口出现的占位映射必须明确不可见、不可进入正式历史；不能在`predictions`、UI、stream或外部callback中先发一次再覆盖。

M仍在merge确认时执行，不分配尚未出现的X/Y。S0为本事件唯一最终模型调用，不在第5帧再问一次作为默认纠错。此后如出现真实新交互，按原事件生命周期处理；不得通过永久锁住两个ID来掩盖后续关联错误。

若第一次“两候选”随后又变成群组，保留当时真实输出并记录假分离/重入，不能利用后续信息取消已发布记录。新generation、预算和不重复调用规则要清楚；不重发同一S0选择较好结果。

## 4. 首帧的速度缺失不是“没有历史运动”

当前`numeric_choice`使用`all(pre_A, pre_B, post_X, post_Y都有速度)`控制历史位置预测。在首帧post只有一个点时，这会关闭已有pre速度。必须拆开：

- `pre_prediction_available`：两个pre片段都有合法历史OLS时，可用于预测当前位置；否则对两种候选采用一致的last-position策略并明确记录。
- `post_velocity_available`：当前单帧必然UNKNOWN，不伪造为零，不从q+1之后拿速度。
- `velocity_comparison_available`：只有双方前后速度都实际可用时才加入速度差项。
- 深度在全部竞争边同样满足既定质量条件时加入；未知不作为某条候选的零代价优势。

同样的历史预测点用于两个候选，保持现有尺度归一和冻结权重；不能因为想要H2而换拟合窗口/中心定义/深度通道。位置预测始终标为ESTIMATED，不写成遮挡内部的实测位置。

至少加入一个非GT的合成用例：两条历史直线正在交叉，pre速度已知，post各一条观测。检查历史外推未因缺post速度被禁用。它只验证接线，不能作为真实鱼场景有效性的结果。

## 5. S0仍是完整事件历史任务，不是两帧匹配

输入保留：
- 原冻结A/B进入前连续观测、OLS及误差、深度时序和质量；
- 原合并及前置风险区间的全部既有实际记录与匿名邻域；
- 当前first split帧X/Y的真实mask、位置、深度和质量；
- 仅基于pre估计到当前的数值比较；
- 原M公开结果，标MODEL_HYPOTHESIS，允许推翻；
- 两种完整映射H1/H2，其他鱼不变。

post_velocity必须UNKNOWN，post_samples必须1；不存在当前片段实测“重现后速度”。原模型看到的2601–2604、第五帧质量和最终分离确认字段不能进入S0。不要复用旧S回答或旧完整包。

M提示词与任务基本保持，S只增加/替换以下时序说明，不同时搜索新语气策略：

> 现在是本事件第一次出现两个分离候选的当前帧。请利用完整的合并前历史、合并过程和当前两个观测，联合选择H1/H2/DEFER。当前X/Y各只有一个观测，重现后速度未知；不要编造后续方向，也不要仅因post速度未知就忽略实际存在的pre运动。两条历史轨迹到当前的位置预测是带误差的估计，不是实测身份链。不能从群组中心的变化推出两条成员都作了同样运动。禁止使用当前帧之后的信息。只有choice必填，reason/evidence_refs可选，额外无关字段忽略。

允许DEFER，执行与数值分支相同的因果回退并首次发布，但必须记录MODEL_DEFER_NUMERIC_FALLBACK，不能把回退正确算成模型选对。

预算/服务失败同样局部回退，继续全段。若完整合法映射本身不可用，保留既定临时输出并记录本事件未实现“首帧恢复”；不能删掉该事件或伪造成功。

## 6. 最小必要测试，随后直接全段

A. 构造首帧数值占位H1、mock模型H2：正式publisher只能收到一次H2，不能收到H1再H2。
B. q==split_first_frame；替换q之后所有观测，S0实际请求字节不能变化。
C. 只修改后续是否保持分离，不得追溯改变已经作出的first split选择时刻。
D. post=1时保留pre预测，post速度未知不等于测量零。
E. 两个新/旧native均可原子恢复；零delta也释放组；非法或过期响应不污染状态。
F. post只含1点时`stage_group_restore`及history初始化正确，不伪造5点。
G. 关闭新模块逐帧复现B0；全部S0=DEFER时模型分支与同数值策略一致；mask不增删、不复制，未匹配残片也评分。
H. 任何已发布帧均append-only；全段输出中没有用后来答案改写旧记录。

测试直接围绕真假结果，不开展新的schema晋级平台、不等待人工判对或数值指标先成功。

## 7. 一次完整试验，三个分支

- B0：原Z4Q。
- B-HOLD-S0：相同保护，first split当帧用修正的因果数值策略提交后首次发布。
- B-VLM-S0：相同保护，first split当帧使用M+S0选择或显式数值回退。

旧MS1-R的第五帧版本仅作归档参照，不新调用、不与新响应拼接。新方案相对旧方案包含时机与首帧所需的接口/数值适配，不宣称是完全独立的单因素延迟效应。

所有分支使用同一预测驱动merge机会，独立状态连续回放2888帧；首个split候选只基于当时的几何，不读取GT。保留旧扫描和自动选择最早事件规则，不硬编码F2600；它仅作当前数据回归。

本轮建议独立授权：官方deepseek-flash，最早8个可用merge事件，每个M/S0各一次，最多16次推理HTTP，总费用≤4美元。用户将本含额度指令下达给Work时适用于这一批；本次Chat没有调用API，旧额度不延续。实际只有一个事件就只有两次，不凑满次数。不新增付费资格smoke、不重复择优。

并发1，同步因果回放；执行前核对实际服务参数和费率，沿用成功的图像传输与预算日志。服务调用耗时多少就如实报告多少，不以隐藏等待或延迟播放宣称实时。

## 8. 评价优先回答“首次输出正确了吗”

封存所有预测/发布日志后，独立使用已曝光GT评分，不读未曝光test GT。

每事件新增：
- merge_suspect/merge_confirm/first_split/frame_q；
- model_max_evidence_frame，post_sample_count；
- 首次公开的X/Y物理映射与公共ID，决策来源（模型/回退）；
- first_split_pair_correct：二者相对进入前参考是否都正确；
- 首次输出到第一次正确且保持的恢复延迟（帧）；未恢复/不可评分单列；
- 首次输出后该事件相关的实际ID变更，及是否重新合并；
- 原始视频时间与本机request/response/publish monotonic时间；
- API耗时、该帧接收至首次发布延迟；不得拿视频日期与本机时钟相减。

评价区分两种“原ID”：
1. 进入本次事件时的物理成员及所携public ID；
2. 全段固定诊断/官方轨迹对应中的长期身份。
进入前已经错号，事件后一次错误物理对应可能偶然提高长期分数。两种结果并列，不能用其中一种替代另一种。

末帧A参考不能唯一匹配时保持UNSCORABLE；按既有冻结pre片段作事后共识时单独报告，不把它写成末帧直接真值。first split当前GT要实际取q=split_first，不再直接复用q+4的结论。后续GT可用于事后随访，不能回到请求或动作。

完整表仍须有IDF1/HOTA/AssA/IDSW/FP/FN，B-VLM-S0−B0与B-VLM-S0−B-HOLD-S0。同时保留帧数和mask集合、模型原始回答和解析结果、已发布预测原始版本。

一个合并事件不代表多个独立恢复机会。代码实现“先决策后发布”仅是工程符合；首帧答错仍然失败，等待API之后显示也不等于实时。只与B0相等不是提点；模型不超过数值分支就明确无模型增量。

不要为了减少切换而永久锁住错误ID；后续任何真实改动都照常纳入指标。

## 9. 可视化和交付

对真实事件输出三列联系表/视频：进入前、合并、first split（重点）、后1/2/4帧和后续。标出首次实际输出ID、决策来源、证据截止和发布延迟。画面只能使用该分支实际发布记录，不能用最终ID重画之前已发帧。

GT事后审计图单独标记，不给模型。公开几何图，私有RGB/GT raster保持既有权限。

必要产物：CONFIG、SOURCE_MANIFEST、EVENTS、CALL_LEDGER、实际请求/响应、PUBLISH_LEDGER、TRANSACTIONS、完整预测seal、FIRST_SPLIT_RESULTS、全段METRICS、latency、可视化清单、测试和FINAL_REVIEW。

本轮结论从PASS / FAIL / STOP / INCONCLUSIVE / ENGINEERING_FAILURE中选主标签，同时区分工程时序、首次身份正确性、长期指标、模型增量与墙钟速度。不要用一个PASS同时替代五种结论。

任务结束所有代码、配置、测试、关键调用记录、逐事件结果和完整报告必须提交，非破坏性整合并push origin/main，实际核验远端SHA和必要文件。失败同样同步。不得force push或覆盖旧seal；不得公开凭据、provider file IDs、私有wire、私有RGB/GT raster。受限产物记录真实路径、大小、hash、复现依赖。

最终只规划一个下一步。本轮不自动展开异步实时系统、5帧缓冲回填、新模型或新数据集搜索。
