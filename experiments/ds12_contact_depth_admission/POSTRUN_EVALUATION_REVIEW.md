# DS12 封存后独立评估复核

## 结论

**冻结的完整目标成立。** R12_RAW 与 R12_RESTORED 各有1次满足 query→clean、actual bank→clean、旧 source 初始→clean 三项 SAME 的出生 COMMIT；同一新枝的 pooled IDF1/HOTA/AssA 均严格超过同源 SAM3_NATIVE，IDSW 从108降至105。两枝恢复的是同一事件，不能算两次独立恢复。

只读封存结果、预测、事务和已有事后 RGB 身份参考；未新读 GT/深度像素，未回放/再调用 TrackEval，未修改冻结源码、预测或 seal。

## 全量及封存一致性

7项评分 artifact、48项分段预测 artifact、76个冻结代码文件 SHA256 通过；ALL、ACCESS、SCORING 绑定一致。四段200/205/360/706帧，共1471帧，每枝39208个预测对象。native/F9逐项复现DS11；raw/rest全量发布相同。mask引用顺序保留，每帧整数ID唯一，真实事务映射匹配发布。

既有封存 VERIFICATION 在GT评分前完成101个出生帧包、5430个对象证书、9850个组件的实际源重算，typed exact，无容差或例外。本复核核验该记录及seal，没有重复源重算。

## 指标与旧收益分离

| 分支 | IDF1 | HOTA | AssA | IDSW |
|---|---:|---:|---:|---:|
| SAM3_NATIVE | 80.976760 | 79.964056 | 71.530499 | 108 |
| F9_RESTORED | 80.976760 | 80.012049 | 71.615763 | 106 |
| R12_RAW | 81.029982 | 80.047159 | 71.677872 | 105 |
| R12_RESTORED | 81.029982 | 80.047159 | 71.677872 | 105 |

新枝相对native为 **+0.053222/+0.083103/+0.147373个百分点，IDSW−3**；相对F9新增 **+0.053222/+0.035110/+0.062108个百分点，IDSW−1**。FP=487、FN=985、DetA均未变。Pooled直接在全帧上评分，不是分段百分比平均；IDSW/FP/FN/GT/预测数与分段之和一致。

这是固定已曝光序列的观测增益，未计算置信区间或统计显著性，不能称泛化或显著性已证实。

前三段完全无发布和指标变化。末段native/F9/R12的IDSW为40/38/37；全量108/106/105。按segment、global frame、RGB GT identity逐切换核对：

- 旧F9：F1239，GT4，n167→public136；F1745，GT2，n190→public188。两次旧群组收益在两新枝共同保留。
- 新birth：F1886，GT4，n198→public176，额外消除一次176→198切换。
- 无新增切换事件。F1347的切换仍存在，起点因旧F9从167改为136，不能误算成新增或额外消除。

EVENT_AUDIT每枝2次正确group COMMIT是旧F9共同收益；本轮nochange为0，不属于新增birth。

## 新出生与实际首次发布

唯一新birth为末段local686/global1886，n198首次发布前选择并提交176。admission body、真实事务、publisher首次ID与hash一致。真实neighbors=[157]；提交后仍为QUALITY_OR_CONTACT_RISK，当前帧未加入身份/birth raw pre样本。

相对F9仅 **F1886–F1906（local686–706）21帧、mask n:198 的198→176** 改变；其他mask没有新增变化。相对native仍有263个变化帧，因为新21帧与旧F9变化帧集合重叠，不能把21直接加到263。

每新枝固定105个非首帧真正首次出生、102个段首身份记录。47个非首帧出生被活动群组阻断；58个进入选择，其中57保留、1提交。不能只以唯一提交为覆盖率或总体正确率的分母。

## RGB身份资格与测量事实

既有BIRTH_AUDIT显示query、clean末端、actual bank、旧source初始均唯一匹配RGB GT4。clean和bank为local657/global1857；旧source176最初为local243/global1443。选中pre片19/19点唯一匹配GT4，首/末/多数均SAME。本轮严格certified_physical_restore_count与endpoint_mapping_correct_commit均为每新枝1，F9为0；定义仍需分列。

当前合格组件2片：n=28/45，几何面积34/54，fraction=0.823529/0.833333，median=1142.852661/1148.069458mm，实际MAD=7.947266/7.514526mm，scale各15mm，固定等权0.5。raw与retained-v2本次组件数值相同。最后clean到query约0.964秒，风险间身份连续性仍UNKNOWN。

此资格证明来源与测量统计通过。RGB polygon身份对应没有提供深度毫米真值，也不证明独占像素属于真实鱼体表面。

## 独立深度贡献的边界

深度项确实生效：正确OLD:176的depth log LR为raw **+0.235869**、restored **+0.281580**；联合margin **4.052215/4.097925**，门槛仍log9=2.197225。归一化contrast不是校准身份概率。

但geometry log LR=3.816346。只检查已记录geometry列，OLD:176已经首选，领先第二名OLD:125约3.045129，超过log9。这不是新控制器回放；它表明不能把身份判别收益全部归功于深度。DS12没有同触发geometry-only、depth-zero或置乱枝，**深度相对解除接触硬门/几何的独立增量未由此四枝设计识别**。

可报告“冻结的接触证书与联合出生重接模块新增一次正确恢复并提升指标”。不能报告“补全优于原深度”“深度独立决定身份”或“物理深度/表面真值已证实”。raw/rest全部输出同值，补全额外收益为0。

## 工程与完成边界

预正式OpenCV float32 DT失败切片保留；正式是最近零点整数坐标、整数平方判定与float64元数据，strict scorer未放宽。FREEZE branch_policy的“R11 arms”仅静态残留，实际分支/模式/输出为R12；未改冻结原件。

完整联合目标取BIRTH_AUDIT.frozen_support_rule_met；METRICS.frozen_support_rule_met仅是跟踪门。未提交/不可评类别均保留。此复核确认实验目标与封存输出一致，不替代尚由根代理处理的最终交付、Git提交/push或远端验证。
