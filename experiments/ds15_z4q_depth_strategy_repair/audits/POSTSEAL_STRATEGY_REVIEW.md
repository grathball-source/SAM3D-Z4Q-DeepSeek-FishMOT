# DS15 封存后策略复核：原始候选与清洁身份参考应分开

2026-10-02。独立复核读取全部预测/access封存、最终METRICS/SCORE_PROVENANCE及已完成评分审计；不读取原始GT，不重新预测，不调用模型、服务器或GPU。`postseal_review.py`实际运行退出0，用时9.71秒。原冻结策略、预测、评分与此前审计均未修改。详细逐源映射、别名状态、候选及评分证据在同目录 `POSTSEAL_ORIGINAL_ACTION_REVIEW.json`；其输入字节/SHA、完成评分和复核程序SHA均已记录。

## 1. 同源基线已经复现，当前新策略没有超过原Z4Q

原Z4Q六份档案、19032帧精确逐映射/掩码复现；另外两段Feeding缺旧档案，未伪造历史基线。八段20098帧全部原生/R12逐帧映射与事件、完整指标复现。所有mask和残片保持，五臂FP/FN相同。因此下面差异来自新分支真实状态，而非基线接线或评价协议换版。

| 数据单元 | 原生IDF1 | 原Z4Q IDF1 | R12 IDF1 | SHARED IDF1 | DEPTH IDF1 |
|---|---:|---:|---:|---:|---:|
| FishSA开发8400 | 91.313288 | 99.333472 | 81.101807 | 92.002662 | 92.002662 |
| FishSA验证2888 | 76.456444 | 80.697587 | 77.829601 | 76.641849 | 76.641849 |
| L3弱参考 | 72.426787 | 74.745256 | 62.838603 | 72.426787 | 72.426787 |
| LW弱参考 | 60.613534 | 64.329395 | 60.613534 | 60.613534 | 60.613534 |
| Feeding四段1471整体 | 80.976760 | 81.716806 | 81.029982 | 81.716806 | 81.820716 |

DEPTH相对原Z4Q，开发IDF1下降7.330810点，验证下降4.055737点，L3下降2.318468点，LW下降3.715862点；Feeding提高0.103911点。FishSA两段DEPTH和SHARED逐帧输出完全相同。L3/LW虽分别有28/46帧DEPTH相对SHARED改号，指标没有改善，新增出生均不可评分。

Feeding的DEPTH HOTA/AssA/IDSW为79.933998/71.473175/130，原Z4Q为79.859851/71.341782/132，原生为79.964056/71.530499/108。相对原Z4Q有小幅数值改善，但HOTA/AssA仍低于原生，IDSW多22；不能称达到预先声明的整体改善门槛。开发/验证/L3/LW相对原Z4Q的HOTA与AssA也均退化。

## 2. 六次原始恢复：四次保持，两次出生恢复彻底丢失

下表帧号均为原始global frame。原来的六次事件是历史审计中query与bank端点一致的恢复。此次更严格的公共身份起点审计将验证9580标为UNSCORABLE：query_vs_bank=SAME，但bank/public-origin与query/public-origin为UNKNOWN。因此六次在本次审计是**五次CORRECT、一次UNSCORABLE**，不能把UNKNOWN改写成已验证正确。

| 原始帧 | 源→旧public | 原规则 | SHARED/DEPTH首次发布 | 提交后alias | 本次原事件物理判定 |
|---:|---|---|---:|---:|---|
| 1327 | 6→0 | D1_DELAYED | 1327 | 0 | CORRECT |
| 3902 | 7→0 | BIRTH_REFINE | 全段没有恢复 | 全段无此alias | CORRECT |
| 8054 | 8→2 | D1_DELAYED | 8054 | 2 | CORRECT |
| 9580 | 6→2 | D1_DELAYED | 9580 | 2 | UNSCORABLE；query/bank一致 |
| 11488 | 8→3 | BIRTH_REFINE | 全段没有恢复 | 全段无此alias | CORRECT |
| 12150 | 11→5 | D1_DELAYED | 12150 | 5 | CORRECT |

四次保留的动作在原始帧就产生相同公开ID和持久别名，没有延迟到后续帧。两次丢失的出生并非稍晚重接：开发n7在3902–8400全部4499帧继续发布7而原Z4Q发布0；验证n8在11488–12188全部701帧继续发布8而原Z4Q发布3。别名缺失持续覆盖同样全段尾部。R12本来就关闭这六次自动恢复。

这意味着DS15把旧自动hook重新启用，仍未恢复原策略的全部能力。共同保护层改变了这些hook所需的源连续性与survivor证据，两个臂一起丢失原本有效的出生候选。

## 3. 开发F3902：recent core witness被保护状态抹掉

事件`MS1-F3863`的成员source=[4,6]、public=[4,0]，suspect=3863，首次分离q=3902，post source=[7,4]。原Z4Q和两个新臂都保留target0的真实旧anchor：F3836/source6/public0。候选核心成本0.791542，总代价0.808762，仍低于dummy1。失败并非目标不可用、成本过高或深度hook否决。

原Z4Q的survivor source4有F3901真实recent core：689.062744mm，当前source4 core=690.254089mm。原native certificate run的last_frame=3901、count=3901、start_frame=1，qualified=True。当前source4对自身的core成本0.318899，对target0的cross成本2.757897；joint core margin=3.946989。它提供一个实际支持witness，出生候选的全局分配优势0.191238超过既有0.15，n7在首次发布前接到0。

新臂在每一保护帧恢复`native_runs`和`recent_core`，q前真实engine仍留source4 last_frame=3862、count=1717、start_frame=2146。`certificate`因此报`native_frame_gap/native_time_gap`，recent core relaxation无法提供F3901 witness；普通core历史也不可用，`core_history=None`。原BIRTH_REFINE明确拒绝：`partner_4_related_identity_unresolved`、`no_verified_local_survivor`。新深度hook为UNKNOWN、veto=False。H0局部回退采用这个已经缺少源witness的自身因果engine，所以继续n7→7。

随后D1也没有补回。仅F3907–3913出现七次target0候选，全部被原来的`partner_ambiguous`挡住：target0 whole history=837.164246mm，对public1的竞争margin=-7.425568mm。没有五次连续成功确认；此后也没有该target的持久提交。不能把启用D1当成能自动弥补丢掉出生witness的保证。

## 4. 验证F11488：source native-prior reservation被保护状态取消

事件`MS1-F2125`，local suspect=2125、q=2188，对应global11425–11488。成员source/public=[3,7]，post source=[7,8]。target3真实anchor仍为localF1935/source3，成本0.399308，在原Z4Q的全局分配优势0.600692。候选对target的core/whole比较在新臂完全相同。

这次并非recent core丢失，而是原**native-prior reservation**失效。survivor7已有core历史anchor1992；当前自身core成本0.944145<1，其joint core margin=0.018781，非负但低于0.15。原native run last_frame=2187、count=1970、start_frame=218，certificate qualified=True。旧Z3规则只在当前可靠、自身匹配、同一native run且近似平手时将`joint_core_opposed_or_ambiguous`转为`reserved_by_native_prior`。另一个survivor1已经给出正witness；该reservation移除survivor7的歧义阻断，原出生关联成功。

两个新臂的protected source7 run仍停在2124、count=1907，certificate因frame/time gap失效。相同survivor7被判`oppose_or_ambiguous`，候选留下`partner_7_joint_core_opposed_or_ambiguous`，尽管仍有一个其他witness。深度hook同样UNKNOWN、veto=False。全q采用本臂局部H0回退，n8首次发布8，之后未补回3。

随后D1在global11533起有63次target3边：11次`partner_ambiguous`，52次`depth_residual`；最初竞争margin=-3.567749mm。再次表明原出生近似平手的native保留作用不等同D1 whole-depth竞争规则，不能用延迟D1替代。

## 5. 代码关系与真实版本风险

关键接线位于`controller.py:28,128,140`：protected写集同时包含身份bank/view_bank/alias与native来源簿`birth/pending/native_seen/native_runs/recent_core/first_eligible`。完整因果clone执行当前帧后，受保护成员的这些字段都被恢复到上一真实engine。这保住了身份参考，却也使持续可见的源在旧Q certificate中表现为“没有上一帧记录”。`px_z3.py:17–35`要求last_frame=frame−1且间隔≤0.2秒；`px_z4.py:22–40`只有该certificate合格时才用recent isolated core；`px_z3.py:94`的native reservation也依赖它。局部回退`controller.py:159`只重新运行当前帧，不能重建已被连续丢弃的此前source witness。

证据层级必须分开：

- **source连续性**：上述survivor4与7在manager source_generation中仍为1，源流没有真实generation break；native certificate gap来自保护字段冻结。来源持续可见，并不自动证明它一直是一条独立鱼。
- **target身份/版本**：目标来源存在真实缺失与重现。开发source6在3878、3891重现，public_epoch从2→3→4，而bank anchor3836属于epoch2。验证source3在local2162–2163重现，epoch1→2，而bank anchor1935属于epoch1。清洁深度不能跨这些generation/epoch重新拼接。
- **清洁参考**：事件冻存的A/B参考是suspect之前的完整旧版本fragment；merged/group/risk数据属于匿名来源，不能因为旧Q曾用它们生成候选就追认成individual clean pre。

额外DS12出生路径没有兜底：`birth_memory.py:79–80`先记录first-ever source；该q的query被`runner.py:117,199,247`的ACTIVE_GROUP_FRAME_BLOCKED拦住，之后不重试首次出生。候选同时被exact-bank/version、group reservation、alias claim及clean-fragment合同阻断。这里不能简单撤掉保护或放宽版本，因为目标确有真实重现/epoch变化。`first_eligible`冻结也不能解释两条首次BIRTH_REFINE失败的根因：BIRTH_REFINE在第一次源出生立即运行，其失败直接来自survivor certificate/witness；随后D1的资格与竞争另行决定。

## 6. 这次新增深度具体做了什么

全部八段DEPTH实际自动候选检查10850次：3219次SOURCE_BOUND_COMPARABLE，7631次UNKNOWN，**深度否决0次**。因此两个FishSA出生丢失、其他原自动动作丢失，以及上述能力下降都不能归因于新自动反证veto。

原Z4Q→SHARED→DEPTH的持久自动提交数：FishSA开发3→2→2，验证3→2→2，L3 10→9→9，LW47→38→38，Feeding四段分别3→3→3、3→3→3、6→6→6、15→15→14。未出现仅preview接受但非持久提交的重复成功计数。

新增深度臂仅有一次字面bank端点CORRECT的组事务：Feeding第四段localq39/global1239，source167→public136，另一个source128保留128；其连续pre-fragment共识判定UNSCORABLE，不能扩称完整身份连续性已验证。它使该段565帧一个source不同于SHARED，并减少一次后续原自动错误提交。

具体状态传播：原global1404的自动source168→public136被评分为WRONG，该提交在DEPTH不再发生。原global1360/source170→167、1466/source176→167的两次CORRECT链，在DEPTH改接136且仍CORRECT；global1893/source197的WRONG链也从167换到136。因此一条组别名改变了后续目标占用和继承命名空间，不能将后续错误减少解释成自动反证veto生效。

新增出生共三次：L3 global668/source19→18、global734/source21→20，LW global2064/source88→85，**全部UNSCORABLE**，没有证实新增物理恢复。Feeding没有额外深度出生提交。其原自动提交仍有16次WRONG、8次CORRECT、2次UNSCORABLE；原/SHARED为17次WRONG、8次CORRECT、2次UNSCORABLE。原生ID优先和原深度公式并不能保证Feeding正确。L3/LW弱参考也不足以验证广泛源身份。

## 7. 下一版最小、合法的修复方向

本冻结版本应按失败结果保留，不能用已知GT选择帧、强制3902/11488动作或重跑挑选改善值。下一版要修复的是共同保护层的职责范围。

1. **每个新臂保留自己的旧Z4Q候选来源簿。** 实际当前/过去source observation继续按旧规则更新native-run及recent-core候选证据；用明确的source/generation/时间来记录。该簿仅解释原自动候选，不写入新方法的A/B clean history，不将GROUP或merged core认证为独立身份。不得复制另一个臂的Z4Q输出/engine。把“源连续性certificate”明确标为旧候选假设，不称物理身份认证。

2. **保护清洁身份参考的合同维持。** suspect之前的同版本fragment、exact bank anchor、真实generation/public-epoch break、风险不拼接和12秒期限继续执行。target旧身份有真实缺失/重现时，不把最近源观测自动接到旧clean endpoint；UNKNOWN保持为UNKNOWN。原候选可能有风险，应由单独旧规则与新合格反证检验，不因保留候选就宣称清洁身份史有效。

3. **在同一次q首次发布前解决旧候选与组事务。** 原自动规则的候选应使用其完整因果来源证据生成，再与extra group/birth mapping做一个本臂、单版本的原子决定；旧候选构成合法H0发布基线，额外改号继续执行逐改变身份的深度支持、唯一性、占用与claim检查。候选接受后记录actual alias、past target anchor和对其他旧source claim的生命周期处理，确保当前所有mask/残片保留且公开ID唯一。组释放不能把已有有效旧候选抹回native，再寄希望于未来D1。

4. **下一版先验验收只检查机制。** 用合成持续source在GROUP期间的native-run保持、真实source gap/generation break、recent-core候选与clean-history分离、近似平手native reservation、受保护q候选/组竞争、failed-stage clone purity与单次原子publication等少量语义检查。全八段、原同源基线和完整动作审计仍须预先固定；完成后才能评价，不能按这六条GT事件逐条强制。

这是一项来源记账与事务接线修复。它有机会恢复丢失的原能力，同时仍需面对旧原策略在Feeding的错误继承。当前证据没有支持继续调深度门槛、扩大历史拼接或把匿名merged深度直接并入个体参考。

## Independent conclusion

The exact original baseline passed. DS15 retains four of six historically endpoint-consistent FishSA recoveries and loses both first-source birth recoveries. Shared protection freezes native source evidence needed by the original Q witness/reservation rules. The new automatic depth guard vetoes no edge. The depth arm does not meet the declared overall improvement target. A later version should separate legacy source candidate evidence from certified identity references, then resolve and commit one causal mapping before first publication.
