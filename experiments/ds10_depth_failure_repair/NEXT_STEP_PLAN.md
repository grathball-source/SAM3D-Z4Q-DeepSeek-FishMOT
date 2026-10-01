# 下一步唯一计划：来源感知的时间支持与置信度

状态：**仅规划，尚未创建新冻结版本或启动新实验。**

## 依据与可证伪假设

DS10_RESTORED 在 F1027 将原生正确 pair 交换，新增两条 IDSW，抹掉既有两次纠错的 IDSW 净收益并降低 IDF1/HOTA/AssA。恢复后的 B 历史从原始合格3点延长至10点，last z相同，但时间 span 从.067s增至.299s；相同.432s gap的旧 process 下界从9579.097降至694.686mm²，预测 scale 从99.475降至31.793mm。当前另一 post 仅 inferred 可用，sigma60并不能认证其物理表面归属。该证据说明“补出更多连续测量”可能同时创造未经认证的更强时间支持。

假设：恢复事实的数量与连贯性可以提高可用性，却不应直接认证独立传感器的时间支持；使用同版本真实传感器合格片段认证 forecast，并让当前 inferred post 在身份决策中共同无信息，可减少这种错误增信。

这是来源/置信度假设，不是恢复深度物理准确已证实，也不是关于 F1027 答案的选择规则。若全量结果只消除本次新增错误、回到 F9，仍不能声称深度超过原生。四个漏修事件和触发范围外100条原生 switch 可能完全不受此机制帮助；不承诺提点。

### 对四个漏恢复是否有帮助：目前没有支持性证据

全q的已封存原始分支已经显示：F470待恢复A为0点；F764待恢复B为2点；F1390待恢复B为1点；F1805待恢复A为10点，且原始/恢复的span同为.299s。它们当前正确候选相对H0的原始joint差分别为−.185912、−.966824、+.147425、+.589654，均没有到log9。该来源合同不会为前三处创造历史、斜率或跨缺口样本；最后一处也没有F1027那种恢复补点造成的时间span差。

因此当前证据支持优先修复错误增信，**没有证据表明来源认证本身可以新增这四处正确恢复**。新RESTORED分支仍使用retained当前量值与冻结KDE，其最终score会有来源/量值组合差，未经完整冻结运行前结果标UNKNOWN；不能借这种未知承诺收益。若没有新的正确恢复，它仅属于工程/置信度止损修复。

## 冻结前只选这一套来源合同

1. **预测时间支持仅由原始传感器资格认证。** 对当前角色的同一 segment/source generation/public ID/epoch，只使用严格过去、相同版本、clean、帧相邻的原始 adaptive core `core_usable` 连续片段，最近≤10点。缺测、风险、group、post、版本断裂仍切断；不跨缺口连接，不延长窗口，不按 GT 或当前吻合程度选点。
2. **forecast 的均值、计数、last time、span、noise与diffusion使用这个认证原始片段。** 保留 DS10 robust local-level 公式、真实时间单位、n≤2的旧预测逐字段 fallback、n≥3最后真实值以及 diffusion≥3 increments。保持15mm测量 floor与原 gap-growth process 下界。没有认证历史则维持 UNKNOWN。避免同一恢复结果既增加历史span又让process缩小。原始值也不因此被认证为鱼体表面，只认证传感器来源和实际过去时间。
3. **v2 retained/inferred 事实完整保留为独立旁证。** 保留它们的 source/fact/cohort、测量与匿名片段；不伪称不存在、不改mask、不覆盖原始数值。恢复补点不能增加认证历史样本数或span，不能让预测过程不确定性比认证原始片段更小。
4. **当前 inferred 的唯一策略：整个 paired depth 模态共同无信息。** 只有两 post 都按既有量值资格合格、且当前都不属于 inferred，才允许当前 depth likelihood 参与；任一 post为inferred/NONE/不合格时，所有候选、两角色、四边的depth LR共同为0。原始分支仍按既有两post资格合同。不得只禁某个候选或某个角色，以免缺失候选获益。inferred60mm floor与来源记录保留，但不把这个假设floor当身份概率校准。
5. **其余关联模型保持 DS10。** H0合法baseline、物理mapping去重、uniform unique priors、Student t4归一化、.9/.1混合、KDE公式/全当前组件/包含query、log9、geometry均值与残差尺度、trigger/q、状态保护、事务fallback、group外alias与原子guard全保持。当前depth被禁用时不使用KDE改变任何候选分数。保持KDE组件来源可追溯；这一试验不另改null或删inferred组件，以免再同时检验第二处背景改动。

本合同允许 retained query 作为原冻结恢复分支的离线观测参与，但它不增加过去认证历史。retained 的空间表面正确性仍 UNKNOWN，KDE仍是query-inclusive plug-in contrast；来源合同不能替代物理RGB-D配准/独立深度表面验证。

## 最小实现与工程检查

在新目录复制已封存版本，增加明确的 sensor-certified history及当前paired资格字段。新decision/scorer源码、全部规则和参数在运行前一次冻结，不改DS10原件。标出所有过去认证点的原始fact/time/version、被排除恢复事实及原因，以及当前paired资格；保存完整原有匿名恢复事实。

必要检查仅针对此修改：恢复补点不能改变认证span/process；RAW资格缺口必须切断；相同版本和帧时间因果；n≤2旧fallback严格一致；query/未来改变不影响pre forecast；current单边inferred四边共同0；candidate/source顺序不影响；raw/retained/inferred原事实不改；H0/alias/原子发布和mask唯一性继续满足。禁止用F1027已知GT设置阈值或特判事件，也不在失败后加第二套策略。

## 一次完整检验与判读

计划使用相同完整1471帧、4段、SOURCE_OLD masks、同源native与既有恢复输入；新源码封存后完整运行一次。最小分支为 SAM3_NATIVE、冻结DS10_RESTORED、来源合同RAW、来源合同RESTORED。旧分支是机制对照，不设置必须超过它或纯几何的晋级门槛；原生一致性和全部封存后评分仍为工程前提。

唯一机制的增量成功条件为：**至少新增一处实际正确的bank恢复提交，同时完整四段pooled IDF1、HOTA、AssA都超过同源native，且不增加IDSW。** 消除F1027错误只是止损，不算提点。报告全部q和全部switch ledger：正确/错误COMMIT、NOCHANGE、guard拒绝、H0/fallback、进入前已错与UNKNOWN分别列出；恢复事实保留数量和被资格切断数量作为代价。不能只报告去掉F1027后的成绩，不能事后筛帧；旧恢复版本的联合mean/null贡献仍未被单独识别。

若只止住新增错误而无IDF1增益，应报告“来源合同减少风险，仍未达到原生目标”。若降低可用性而丢失正确恢复，应计入完整代价。若仍发生同类错误，证伪当前来源置信度假设，保留全部原件，不在本轮降log9、补斜率、修改trigger或按答案继续调参。
