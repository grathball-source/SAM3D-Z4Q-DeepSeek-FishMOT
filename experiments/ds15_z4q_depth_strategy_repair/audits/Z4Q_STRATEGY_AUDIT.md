# DS15 原 Z4Q 与 DS14 策略审计

2026-10-02。只读检查 DS14 完成产物、原 Z4Q 源码和历史封存结果；本审计不生成新预测、不读原始 GT 栅格、不调用模型或服务器。另编写独立 `baseline_check.py`，只允许全部新预测封存后核对原版基线。Ponytail full：复用真实旧控制器和输入，不重新实现一套“近似 Z4Q”。

## 已核实结论

DS14 的 R12_RAW 并非“旧 Z4Q 加上一个更好的深度公式”。其底座是 NE1 原生优先事件层：旧 Z4Q 常驻 **D1_DELAYED 和 BIRTH_REFINE 两种继承均在分配前被 veto**，而新 R12 出生只在首次 native 出现时有一次机会、活动组期间又禁止提交。原版支持延迟重试、接触伙伴排歧和近期存活者核心证据的能力被移出了实际决策范围。

第二个独立问题是新组恢复可凭一条旧身份的证据把两个身份整体交换。8400 的 F4524 错改持续 3877 帧；原生本来正确。R12 新出生已采用局部水平预测，但组选择实际仍调用 DS9 的旧 WLS。不能把“当前 raw 深度存在”当作“两条身份历史均存在、且深度支持这次交换”。

原版也不是所有来源均有效。Feeding SOURCE_OLD 前 405 帧，原 Z4Q 比同源原生 IDF1 低 0.3950 点、IDSW 多 4；其六次接受重接按字面历史锚点事后分为 0 同鱼、4 异鱼、2 UNKNOWN。恢复旧路径应作为真实对照，再用来源合格的深度矛盾约束检查能否止损，不能无条件宣称会在 Feeding 提点。

## 同源历史成绩与本轮范围

每格为 IDF1 / HOTA / AssA / IDSW，前三项为百分数。原版为 **Z4Q_STABLE**，包括合格原生返回保护；不是较早 Z4Q、QR、I3 或 VLM 分支。

| 八个独立片段 | DS14 同源 SAM3_NATIVE | DS14 R12_RAW | 历史封存 Z4Q_STABLE / Z4Q_FROZEN |
|---|---|---|---|
| Feeding 0–199，200 帧 | 92.889759 / 91.362522 / 88.085877 / 10 | 同原生 | 92.125617 / 90.483748 / 86.399664 / 12 |
| Feeding 351–555，205 帧 | 82.927271 / 78.582844 / 72.182690 / 22 | 同原生 | 82.891042 / 78.147798 / 71.429933 / 24 |
| Feeding 701–1060，360 帧 | 77.428039 / 75.545022 / 65.006580 / 36 | 同原生 | 未找到这段原版封存成绩；DS15 须真实回放 |
| Feeding 1201–1906，706 帧 | 78.839951 / 78.727248 / 68.089322 / 40 | 78.950986 / 78.903622 / 68.394290 / 37 | 未找到这段原版封存成绩；DS15 须真实回放 |
| FishSA 开发 global1–8400 | 91.313288 / 73.346143 / 69.186768 / 5 | 81.101807 / 67.894067 / 59.284350 / 7 | 99.333472 / 77.829488 / 77.907638 / 6 |
| FishSA 已曝光验证 global9301–12188，2888 帧 | 76.456444 / 66.435529 / 55.196059 / 8 | 77.829601 / 66.602491 / 55.476116 / 10 | 80.697587 / 69.243869 / 60.074321 / 9 |
| L3，3710 帧，弱参考 | 72.426787 / 75.362607 / 94.259655 / 1 | 62.838603 / 68.214192 / 77.225991 / 3 | 74.745256 / 77.171558 / 98.839045 / 2 |
| LW，3629 帧，弱参考 | 60.613534 / 66.369067 / 77.555121 / 7 | 同原生 | 64.329395 / 68.991721 / 83.805597 / 10 |

R12 相对原版的历史 IDF1 差为：FishSA8400 −18.231666 点、2888 −2.867986 点、L3 −11.906653 点、LW −3.715862 点。新 DS15 原版分支须先逐帧复现这些对应，才可把它们作为新同源差值。

Feeding 前 405 帧的原版合并 IDF1/HOTA/AssA/IDSW 为 **87.442586809 / 84.523401587 / 80.362738628 / 36**，同源原生为 **87.837589565 / 85.187479041 / 81.609371913 / 32**。DS14 全 1471 帧原生/R12 的 80.976760/81.029982 不能与前 405 帧原版 87.442587 直接相减。四段独立状态、互不相交身份命名空间，合并成绩须重新做整体统计，不能平均百分数。

权威指标入口：

- `E:/CAU/D-MOT/tools/sam3_depth_return_guard_20260918/completion_evidence/experiment/metrics_development.json` 和 `metrics_validation.json` 的 `Z4Q_STABLE`。
- `experiments/ne1_native_first_event_association/run/METRICS.json` 的 `segment_metrics[*].Z4Q_FROZEN` 和 `pooled_metrics.Z4Q_FROZEN`。
- `E:/CAU/D-MOT/tools/z4q_new_bags_20260923/results/{L3,LW}_metrics.json` 的 `metrics.mask`。
- 本轮完整原生/R12：`experiments/ds14_raw_multidataset/run/METRICS.json`。

I3 开发 R 的 IDF1 99.468545、IDSW2 属于另一身份/掩码层，其 FP195/FN328 与全 mask 原版 Z4Q 的 FP194/FN323 不同，且曾等待确认暂缓 4 个观测。不能借用为本轮全 mask 原版基线。I3 的独立深度置乱对关键 1×1 出生候选未实际扰动，亦不能用其分数证明深度独立因果贡献。

## 六次真实旧收益动作

`sam3_depth_return_guard_20260918/completion_evidence/experiment/TRANSACTION_AUDIT_{development,validation}.json` 中，以下六次 **Z4Q_STABLE** 接受重接的 `history_gt == current_gt`，verdict 均为 `consistent`。这是已曝光参考上的事后诊断，不是独立盲测；UNKNOWN 别名观测另列，不能当安全。

| 段 | global 提交帧 | 原生 source→旧 public | 原路径 | DS14 的对应机会 |
|---|---:|---|---|---|
| 开发 | 1327 | 6→0 | D1 延迟、5 次确认 | native6 在1274 首生，活动组阻止出生；后续 D1 被 veto |
| 开发 | 3902 | 7→0 | BirthRefine 首次发布继承 | native7 在3902 首生，活动组阻止出生；后续 D1 被 veto |
| 开发 | 8054 | 8→2 | D1 延迟、5 次确认 | native8 在8035 首生，活动组阻止出生；后续 D1 被 veto |
| 验证 | 9580 | 6→2 | D1 延迟、5 次确认 | DS14 没有常驻 D1 重试能力 |
| 验证 | 11488 | 8→3 | BirthRefine 首次发布继承 | 原版近期/伙伴证据与新 R12 出生资格不是同一策略 |
| 验证 | 12150 | 11→5 | D1 延迟、5 次确认 | 原版先重接，StableReturn 保留到末帧；R12 没有这条路径 |

开发的三个非初始出生在 DS14 `BIRTHS.jsonl.gz` 中逐条为 `ACTIVE_GROUP_FRAME_BLOCKED`，各有 0 个合格新 R12 历史候选；从 F1 的初始身份不能补造一次出生资格。DS14 F3902 自身事件的目标变为 public6，而原版目标为 public0，源于原版更早已接回6→0、DS14从未执行。不能把另一分支的后续“正确答案”直接灌入当前状态。

3902 的 Q 机制有实际证据：旧 dormant0 历史837.79mm；存活者 F3901 可靠 core689.06mm，F3902 当前690.25mm；新 source7 core808.66mm，target 成本0.7915、存活者自身成本0.3189、联合 core余量3.947、全局余量0.1912，通过旧0.15门。它支持7→0，并非依靠缺失角色的共同无信息似然。Q 的近期核心机制有条件使用存活者上个真实孤立 core，避免把 latent 伙伴抑制所导致的旧缺测当作无身份证据。

## 真实代码流差异

代码行号基于审计时文件；下列相对路径均以 `E:/CAU/SAM3D-Z4Q-DeepSeek-FishMOT` 为根。

| 环节 | 原 Z4Q_STABLE | DS14 R12_RAW |
|---|---|---|
| 执行器 | `online/closed_loop_2888/z4q_source/bridge.py:54` 的 `Bridge`；preview62、commit_once115；engine 为真正 `StableReturn` | `experiments/ds14_raw_multidataset/controller.py:22,33` 继承 NE1 `NativeFirstGroupBridgeP`；NE1 `ne_controller.py:32` 两规则入边一律 veto |
| 延迟重试 | `.../sam3_depth_failure_repair_20260917/repair_controller_r3.py:45` 起：missing≤6秒、clean≤12秒、5个clean；新源出生≤6秒、首合格后≤3秒；`pending`5次确认 | `experiments/ds14_raw_multidataset/runner.py:133` 新分支从 NE1 底座建立；D1 候选仍可计算，但不能接受；新 birth `birth_memory.py:79` 只首次见一次，blocked 也不重试 |
| 深度摘要 | D1 用最近真实 clean **whole** 中位数；`DepthIdentityBalance.z():34`，smooth=False；容差 `min(60,15+3sigma+3age)`，伙伴余量/自身原生连续性约束 | 新 group/birth 用独占自适应 core；group 实际 WLS 外推，birth 局部水平；不是“同样测量仅替换融合权重” |
| 出生伙伴验证 | `controller_z2.py:41` core＋whole veto＋当前存活者自身/交叉比较；89联合core余量、112至少一名合格存活者；148全局分配余量 | 新生对 OLD/NEW 归一化似然与证书；group 为H0/H1/H2两身份映射，但 `experiments/ds9_joint_h0_depth/association.py:254` 仅要求整体margin≥log9，无逐changed角色都合格的准入 |
| Q 近期 core | `controller_z4.py:22,75` 同原生连续run内存活者近期core≤0.2秒、risk≤30mm；证据和普通历史分开 | `experiments/ds14_raw_multidataset/controller.py:129` 在因果preview后恢复protected stores；group保护改变相关bank/alias/native_runs/recent_core更新窗口，不能认为共享后仍等于原版 |
| 历史 | 原 public bank保存clean whole15点、motion5点、面积、partner，缺测/接触时冻结；view_bank 保留ROI锚；近期core独立证据 | `experiments/ds1_depth_only/depth_state.py:16,45,80` 版本化native/public/epoch/generation，30帧缓存、连续latest fragment、最近10点；risk/version断开不拼接；birth还要求几何与sensor历史同一连续片段 |
| 组状态 | 原版没有额外MS1组事件事务；常驻继承每帧拥有真实独立状态 | `experiments/ds14_raw_multidataset/runner.py:172–195` 疑似时冻结成员并断开深度片段，首分离q一条post；`merge_split_manager.py:147` stage双身份，180新alias及q测量进入目标bank，后续沿错误映射继续 |
| 原生返回 | `controller_return.py:19,37,64` 合格native优先；不合格冲突保留alias并把原mask编号为−1−native，负ID完整评价 | 同父返回逻辑仍在；但原继承已关闭，真实能形成alias的主要路径不同，不能凭同一父类说策略相同 |

原版 CONFIG 的关键固定值：min_points16、valid_fraction0.2、risk floor15mm、budget60mm、history5次/12秒、whole veto margin15mm、assignment margin0.15、motion weight0.15、native连续5帧/0.2秒、Q recent core0.2秒/30mm。D1固定D_balanced有confirm5、smoothFalse，不因birth CONFIG换成WLS。

### 输入与源码不是主要混淆源

复制到 `online/closed_loop_2888/z4q_source/source/` 的六份controller与 `E:/CAU/D-MOT/tools` 对应原件逐字节相同。原CONFIG SHA为 `c61977b03dff6cba903b1b3fd4d3b84cab22525681e604460d2f876b6d6698af`；StableReturn SHA为 `233f180ff8a6a14f43a0e133606281644f0257b4a4d303794ac007df84d563b6`。

DS14 FishSA和Feeding共六段 `SOURCE_MANIFEST.raw_profile_changed_objects==0`；准备时whole/fixed core逐对象重算并与既有profile相等，保存2D几何/score/presence/neighbors/原生顺序均不改。FishSA依赖的开发/验证 assignment SHA分别 `49fc127d359566da392f401a68a304cc213d8e3ac702ad93e91894309200708b` / `ea468964e4b287a3879dfb83b304dd64c83f055e9649d3155fa62c41b717a0fc`，与原Z4Q features中来源固定值一致。旧assignment额外未发布proposal RLE不属于N0，未作为预测输入。

这里的profile相等只说明原版whole/fixed core可复用；R12真正消费的是另算的adaptive core及状态，不能据此说两策略使用同一测量摘要。L3/LWprofile由原polygon重新构建，counter0没有旧profile逐项比较含义；须通过新原版逐帧映射对照验证真实adapter等价。

L3/LW沿相同原BAG标定、raw native NPY、pixel中心、nearest-Z配准和5ms缺测约束；旧 `Geometry.align` 与DS14带source index的 `rasterize` 不应凭相似代码假定输出控制器一定逐帧同一。`baseline_check.py` 会拒绝任何原版public/mask差异。

Feeding SOURCE_BASELINE第二段有205/205个预测JSON与SOURCE_OLD不同，检测FP/FN也不同；不能混用其原生HOTA或原版分数。FishSA当前aligned标签包的metadata改写与F9398标签版本差异在DS14追加修复中已明确：验证分数使用原baseline `inputs.zip` 的GT与SHA，原full1080 raster后nearest640口径；不得用更新包换参考。评分代码错误不解释完成的原生逐字段精确回归后的科学退化。

## DS15 五臂冻结设计与收益归因

本轮母任务预定五个独立状态分支，沿相同20098帧、8片段、全部181842保存mask，不使用GT择触发/候选/深度，不补跑SAM，不调用LLM。

| 分支 | 用途与实际差异 |
|---|---|
| SAM3_NATIVE | 同源原native ID、全部mask，工程和效果基准 |
| Z4Q_FROZEN | 真正原StableReturn＋原CONFIG，常驻D1/BIRTH都启用；无新group/birth干预；先逐帧复现六段档案 |
| R12_RAW | 独立精确复现DS14冻结路径，旧规则仍禁用；核对旧错误及效果都真实复现 |
| Z4Q_SHARED | 旧自动继承启用，使用新共享protected/event状态；所有新组决定H0、新R12 birth关闭；观察共享状态自身是否改变原版能力 |
| Z4Q_DEPTH | 同共享状态＋旧自动继承；只在来源/版本/实际bank绑定的clean历史和当前raw core合格时，深度矛盾LR≤−log9拒绝旧候选；UNKNOWN保持旧资格；新group用局部水平、逐changed角色正支持chosen对alternate、缺角色回H0、仍守log9联合余量；新R12首次出生保留当前证书和活动组限制 |

先看 Z4Q_FROZEN−SAM3_NATIVE 是原能力；Z4Q_SHARED−Z4Q_FROZEN 是共享状态的净影响；Z4Q_DEPTH−Z4Q_SHARED 是**整套深度guard/组恢复/新增出生的组合效应**，不能宣称分别分离了三个组件。Z4Q_DEPTH−R12_RAW还包括恢复旧策略，不是单一深度公式增量。所有臂独立状态延续，不把另一臂bank/GT正确答案复制进来。

该策略的针对性在于：保留已经验证的常驻机会，阻止当前F4524式“缺失角色历史仍交换整对”，统一新group/birth深度接线，且来源不足时不凭假定深度否定旧能力。阈值沿旧log9，没有从GT搜索新数字。

风险仍明确：原版Feeding四个已知wrong锚若没有合格新矛盾证据，会依设计继续被接受；UNKNOWN保持不能被称安全。共享组保护可能改变Q recent_core/alias时序，未必保留3902成功。逐changed角色支持门可能放弃单角色足以确定、但另一角色历史缺失的真实恢复；只提高native止损不能称超过原版。raw core可混鱼/背景、mean和尺度是未校准测量模型，插件LR也不是物理正确概率。需要全段而不是只挑F4524检验。

## 精确原版回放与封存后基线校验

最小原版wrapper是复用 `online/closed_loop_2888/z4q_source/bridge.py:54` 的 `Bridge(config)`，每帧 `view=bridge.preview(frame,time,observations,profiles)`，`bridge.commit_once(view,None)`，按当前native引用导出所有 `{id:mapping[native],mask}`；不要替换成NE1类、不要 `enabled=False`、不要安装新group管理器。每段空状态，负placeholder保留，配置与六controller源码哈希冻结。

`baseline_check.py` 只在 `run/ALL_PREDICTIONS_SEALED.json` 存在、arms5/frames20098/8个单段seal完整且预测SHA一致后读取新预测和旧档案。核对六段 **19032帧**的完整有序mask/native/public映射、FishSA/Feeding时间戳与global frame、旧档案固定SHA；再记录六项固定旧metric期望。未找到历史原版档案的Feeding后1066帧写UNKNOWN，不能制作一个假的旧全1471成绩。

规范档案：

- FishSA：`E:/CAU/D-MOT/tools/sam3_depth_return_guard_20260918/completion_evidence/experiment/predictions_{development,validation}.jsonl.gz`，variant `Z4Q_STABLE`；SHA分别 `18793b53c7f751b149d0bbaa01f307b6c86a48f9c831edb761fe87e2b2a9a8cb` / `9a95ed32e184d2e37c185104df184c943733c00d2cbed8b3e85967e8728dbdef`。
- Feeding前两段：`experiments/ne1_native_first_event_association/run/<segment>/public/predictions.jsonl.gz`，variant `Z4Q_FROZEN`；SHA分别 `888c5f78804d6f8b69acc1f84b7f5f5ef819711ab2e3cee6543946b5c5dc7ba8` / `62d99809c392d17fe772ce25bc45cee0464708a2ea59082019d09113fbd5f0af`。
- L3/LW：`E:/CAU/D-MOT/tools/z4q_new_bags_20260923/results/{L3,LW}_predictions.jsonl.gz`，数组 `native_ids/public_ids`；SHA分别 `302234416f202d8793d97e6539cf91957ba2fe5b41654b78ea950075f10c2522` / `f31792aa477a004a610b74ca16b994ff8c58ce0e77e21fdb4512ba59b193a03b`。

评分必须在全部seal后，使用DS14修正后的同一参考与栅格协议，逐字段复现同源native/R12，完整IDSW/FP/FN和每次物理锚点正确/错误/UNKNOWN分列。L3/LW恢复版预标注仍未独立人工终验，部分几何依赖预测、两相机时间重叠97.882秒；FishSA已用于开发，Feeding保存20帧批/5重叠、L3/LW60帧批/10重叠。新控制器的逐帧因果性不证明上游前端零lookahead，更不代表跨录像盲测。

本审计完成时，只执行checker语法和“缺allseal必拒绝”的守卫检查，PASS；未执行其完整原版对照、未生成新预测或GT评分。新实验真实结果与最终验收须由母任务另行记录。
