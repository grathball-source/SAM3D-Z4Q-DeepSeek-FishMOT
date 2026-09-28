# MS1-R：修正合并组的观测/状态隔离，直接完成三分支回放

## 本轮目标

仓库：`grathball-source/SAM3D-Z4Q-DeepSeek-FishMOT`
审查基点：`a5c640d17500c58400b57ef11279a10a6387832b`
建议目录：`experiments/ms1r_observation_state_repair/`

只做一项工作：把已实现的 MS1 合并—分离机制修到“群组不是个体、有效测量不等于有效身份”的一致状态，再跑完整 2888 帧 B0 / B-HOLD-R / B-VLM-R。不要新开两帧匹配、RGB外观、训练、DAA、人工资格考试或新提示词搜索分支。

当前 MS1 的真实结果保留：B-HOLD 与 B-VLM 在全部 2888 帧相同；相对 B0 有真实数值上涨，但没有模型增量。末帧 A 参考未唯一匹配 GT；全冻结片段共识判 H1 错误必须仍标为事后片段诊断，而不是“末帧真值已知”。旧 seal、预测、请求、响应和评分只读。

## 1. 先读实际实现，复用而非重建

- `experiments/merge_split_identity_memory/FINAL_REVIEW.md`
- `merge_split_manager.py`, `source_scan.py`, `event_packet.py`, `replay.py`
- `score.py`, `test_ms1.py`, `provider.py`
- `run_ms1_20260928/public/EVENTS.json`
- `run_ms1_20260928/public/requests/MS1-F2586-S.json`
- `run_ms1_20260928/public/PHYSICAL_EVENT_AUDIT.json`
- 原 Z4Q 的 bank/alias/clean/latent_merge 更新代码

先确认最新 origin/main；若有新的改动，阅读并非破坏性整合，不覆盖其他工作。

## 2. 范围固定：本轮不靠扩大触发范围获得漂亮结果

保留原预测驱动 source_scan 的事件逻辑与空间容差、area/presence 判据、30帧缓存、2帧确认、5帧post和10秒超时；不按GT或已知错误帧改触发器，不将普通bbox交叉全部变成merge。

可以重放已经冻结的 prediction-only 扫描，也可用未改变的算法重建并校验同一事件集。不得把 F2586 写成生产触发条件。该帧仅用于真实回归测试。

明确当前事件是“经过既定质量筛选后，一个可用mask加小残片”，不是“原始输出严格只剩一个mask”。残片始终计入原mask集合。触发覆盖率未测得，不能将一次事件说成所有遮挡。

不因只有一个事件而自动扩展数据或追调门槛。该段的局限写进结果即可。

## 3. 修复真实状态与本地历史的一致性

### 3.1 群组观测不能进入任何个体历史

当前 ProtectedStableReturn 保护实际 bank，但 `_history_update()` 只按 area/neighbors/quality 判 clean，没有排除 active group。修复后：

- active MERGED 的共同mask只进入 group store；即使 neighbors=[]、area很大，也不能写入 self.clean/self.last_clean 的成员参考。
- SPLIT_PENDING 的 X/Y 只进入临时 post store；最终恢复之前，不将临时对应写成可信 A/B 历史。
- manager 的历史与 engine.bank 的历史适用范围明确分开，但不能互相矛盾。
- 每个观测保留 SOURCE_OBSERVATION / GROUP_MEASUREMENT / POST_UNASSIGNED 等实际类别。
- 原公共身份、source generation、观测时间与真实测量时间分别记录；同native但epoch/generation改变时切断身份片段，不跨变化拼接。
- 取消、超时、第三对象介入、恢复失败后释放组状态，不把群组或未定post片段作为下一事件的干净前史。
- 真正的旧参考保留，不能通过替换成有利GT锚点来修复。

### 3.2 不混用 native 与 public 的字典键

`stage_group_restore()` 当前清理新source bank时，可能删除预留public目标bank。修复这个确定的键域问题：

- 对 bank/view_bank 的键按 public identity处理，对 alias/pending/native_runs 等按实际native/source处理；不得简单复用同一个整数集合清理所有字典。
- 在 trial 中先保存所有目标bank，再清理新source的临时记录；任何预留目标不得被删除。
- 在 source==target 的旧native返回、两个新native、只有一个新native、source/public数值碰撞时均可构造一致的事务。
- 保持现有唯一性、过期episode/generation拒绝、失败不变更原分支、零delta也释放保护。
- 组外对象及其alias不应因整数相同被删除或接管。

### 3.3 临时残片标签

当前每帧为小残片新建负ID，会人为改变轨迹数量/碎片化。新版本为同一事件内同一残片source-generation使用稳定且不冲突的临时ID；raw mask一个不增不减，未匹配残片仍进评分。记录这一输出策略修复及其影响，不把共同策略收益算给VLM。

## 4. 修复“测量摘要”，不发明可靠身份

### 4.1 真实十点回归

把用于 event packet 和 numeric_choice 的首尾割线改为对最近最多10个连续合格观测的带截距最小二乘拟合，使用真实时间戳。至少提供：

- 实际样本帧/时间、样本数和跨度；
- vx、vy、speed；
- 每轴与二维位置残差；
- 预测所用时间间隔、采用的预测模型及不确定性；
- 少于3点或时间不合法时 UNKNOWN，不伪装成测量零速度。

原 source_scan 的短时预测公式在本轮保持不变，以免同时更改事件集合；明确它与本轮关联证据估计不是同一个试验因素。不能把“模型输入更好”与“多触发了事件”混在一起。

位置、速度、时间、深度必须来自实际记录。不要为了让匀速模型更符合某个答案而拟合跨风险轨迹；不声称OLS就是真实鱼速。

### 4.2 给出观测退化，不以 neighbors=[] 代替质量

复用已有真实 mask，报告连通片块数、最大片块比例、mask质心、bbox中心及二者偏移、原深度有效像素数和比例。它们作为测量诊断，不是个体身份特征。

- 不删除较小连通块来人为补出完整鱼体；也不按GT判定哪个块属于A。
- 不把“源码连续、neighbors=[]”描述为“已验证个体连续”。
- 本轮不凭该单个案例调一套新的面积/跳变门槛；向模型提供原观测、质量诊断和回归残差，保留 UNKNOWN。
- 对原源没有的 sensor/synchronization/epoch信息注明未提供，不能自行写成已认证。
- 核心深度可用性至少复用已有有效采样规则，并记录 n、valid_fraction、MAD和混合状态。一个像素的 valid_fraction=1 不能被表述成充分可靠深度。
- 不能把未校准的管线深度解释为距水面深度，也不要求鱼跨遮挡保持恒定深度。
- 数值候选在共同可比的有效模态集合上比较；某条边缺失运动或深度不能获得更低代价优势。

原冻结身份参考没有改变时沿用原角色含义；如因来源变化无法绑定，标记不可评分，不悄悄沿用旧答案。

## 5. 保留两阶段模型，避免把M输出截断成半个JSON

沿用 MS1 的系统任务与 M/S 决策逻辑，不调成更激进、不强制选H。

- M阶段只分析，原始响应完整保存。M也应收到已缓存的合并前匿名风险区间；不能只给最后clean参考和确认时的group，而静默漏掉已发生的过渡观测。S继续保留同一实际风险区间。
- S再次提供原始pre、group、post事实。
- 不用 `m_hypothesis[:1000]` 截原始字符串。解析后按固定字段投影保留 merge_assessment / possible_continuations / watch_for_after_split / uncertainty，每字段的确定性长度处理写清；不丢全部不确定性。正常短响应可整体传入。
- 无法解析M时传null，不停止S、不把半截JSON作为证据。
- 邻鱼与小残片在同一固定场景中用统一中性匿名样式呈现；不能图中删掉，又让模型替输入证明不存在第三成员。它们只是上下文，不参与A/B永久身份绑定。
- 增加一句固定输入约定：无邻居、非零面积和同source只表示预测观测属性，不保证可见完整鱼体或跨时身份。
- S仍只消费唯一H1/H2/DEFER；多余字段不阻断。DEFER/格式问题走预定数值回退，原始选择与回退后动作分列。
- 几何图来自实际mask，不发RGB颜色纹理，不沿native跨合并画身份线。

## 6. 一次完整回放，不再资格评审

三条全段分支：

1. B0：旧冻结Z4Q；
2. B-HOLD-R：修复后的组保护和数值恢复；
3. B-VLM-R：相同组保护/实际观测，仅分离选择由M/S模型辅助。

旧MS1只作归档参照。B-VLM-R需要新模型响应；输入已变，不能沿用旧H1响应冒充新结果。

修复测试通过即可运行；不要求人工先判对、数值分支先提点、schema无多余字段或独立新事件数量达到某个晋级值。

预算建议：原时间顺序最多前8个合格事件，每事件M/S各一次，官方deepseek-flash总推理HTTP≤16、费用≤4美元。用户把本含额度规格下达给Work时是本轮授权；旧预算、旧密钥存在不是授权。无需新增付费smoke或重复投票。保持已验证的API图像路径和模型参数，执行时核对实际费率；若真实输入条件未变导致仍仅一个事件，就只调用两次，不补造事件。

当前q、事件选择、回复选择和状态更新均不能使用GT或未来帧。同步回放就报告同步墙钟，不称实时。

## 7. 最小测试（在同一执行任务内完成）

- active group 的 neighbors=[]观测仍不能进入成员clean/last_clean；连续group→split→下一episode回归。
- old sources=[10,20]、reserved publics=[1,2]、return sources=[1,2] 的目标bank不被清理；组外alias键值碰撞也不影响其他鱼。
- source generation/public epoch改变能够切断本地历史；原始观测完整保留。
- 相同首尾、不同中间样本的十点输入，回归结果或残差应响应差异。
- 单像素深度不当成充分可靠；缺失模态对候选公平。
- M长响应保留有效结构与不确定性，S不消费截断JSON。
- 原模块关闭B0精确复现；全部S=DEFER时两保护分支一致；一个mask不复制；组状态失败原子性与零delta释放。

不得把原MS1“只有一个候选在2586”当作新通用测试的唯一真值。source_scan保持时可单列真实数据回归。

## 8. 评分、视觉和交付

完整预测封存后评分，原TrackEval和源GT不变。表中必须有：
IDF1、HOTA、AssA、IDSW、FP、FN，及 B-VLM-R−B0、B-VLM-R−B-HOLD-R。

同时分开：
- 末帧参考是否唯一可评分；
- 整个冻结片段的事后一致性推断；
- 相对进入前物理身份是否正确；
- 原先公共ID是否已错，是否发生偶然标签修正。

片段共识不能让未匹配末帧变成“GT直接确认”。token→source必须从发送时私有绑定表获得，并与重建排序交叉检查；不能假定bbox排序恒等。

记录差异从哪一帧开始、临时标签/数值暂配/最终事务各自作用；q时零delta不写成零事务。不能把B-HOLD共同改进算成VLM独有收益。

实际查看并生成一个三分支合并前/中/后对照，至少包括退化前参考、最后参考、首次保护、合并中、首次分離、q和之后。需要查看原RGB可作为postscore QA，但不能送进本轮模型或伪装成模型原来已见。

数值上涨、物理映射与VLM增量分别结论。无增量就如实写无增量；未完成或零调用也保留全段输出和原因。不要通过GT事后更改动作，或重试模型直到答对。

## 9. main 同步是完成条件

全部本轮代码、配置、测试、请求/响应关键记录、事件、预测seal、完整指标和报告提交，非破坏性整合并push origin/main；完成后实际读取远端SHA和关键文件核验。FAIL/STOP/INCONCLUSIVE也必须同步。不得force push、覆盖旧seal、公开凭据/provider IDs/私有RGB/GT raster。

更新最新HANDOFF与实验入口，报告未同步受限产物的真实路径、大小、哈希和用途。

最终只规划一个下一步，不自动开始第三成员触发扩展、新数据收集、第二种模型或另一个实验分支。
