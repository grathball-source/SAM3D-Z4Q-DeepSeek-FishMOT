# DS18 总复盘与最终主判定

**COMPLETE_TRIAL_GOAL_NOT_ACHIEVED**：六臂八段全部预测和统一评分完成；工程来源合同通过，但共用恢复政策仍有实测缺陷，新增深度策略没有达到稳定超过同源原生与原Z4Q的目标。冻结版本停止，不滚动调参。

## 分层结论

- 工程执行：36项R5单测、150帧存储等价、五个实际因果前缀9619帧、ROI/source人口、评分契约、八段原生/原Z4Q及归档DS16逐帧等价通过。最终FINAL_CHECKS再次核验冻结代码、预测/记录seal和旧文件。通过不等于物理恢复正确或性能成功。
- 输入：每臂20098帧，六臂120588分支帧；181842个原生mask。原始depth/source_index与同源SAM3；没有v3/annotation depth、模型、RGB外观或新增未来帧。Feeding固定1471帧，不把其余436保存帧伪称缺失；旧保存SAM3前端零未来性未重新认证。
- 状态收益：开发段MIXED IDF1回到99.244072，追回DS17损失，但仍低于原Z4Q 99.333472；L3/LW原有效恢复仍未保住。止损不能当作深度独有贡献。
- 深度增量：MIXED−ACTIVITY IDF1为Feeding−0.656411、dev+0.031787、val−0.278108、L3/LW零；LW HOTA/AssA有小增量但IDF1无增量。这是来源、质量、混层和历史传播组合，不是纯深度分峰效果。
- 物理边界：混层不等于两鱼、单层不等于合格身份；弱置信度不是物理准确率。UNKNOWN/UNSCORABLE/未提交不算正确。L3/LW参考是未审查预测派生弱参考；所有片段重复曝光，不声称独立泛化。

完整六指标、30组成绩和实际差值见FINAL_REVIEW.md及run/METRICS.json；不得只用某一个IDF1微增或IDSW下降概括成功。

## 三个可证实的失败链

### 1. 共用身份保护可以挡住本来正确的重接

L3 local3025：原D1 47→9，残差44.4776mm/tolerance60mm，cost0.748384，实际bank及公共起源正确。新活动修复让alternative恢复为空；但受保护target门要求joint，事件始终q=None，资格先过期。此后47到末帧仍未接回。证据见POSTSEAL_STATE_L3_ADDENDUM.md。首次映射差异不必是首次内部状态差异；后续错误不可全部归到当前深度值。

dev7在3902先公开7；ACT3963、MIX3947才接回0，分别延迟61/45帧。val8 ACT2189接回3、MIX2237才接回3，分别延迟1/49帧。实际旧bank恢复正确也可能因先公开新号再晚到改号增加IDSW。pending缓存last_evaluation是最后held更新，不是最后一次调用，未把此记录缺陷误当指标根因。

### 2. 质量筛选不能一律当成可靠性提升

原whole有效180727次，本轮组合筛除55477次，其中潜在混层10510、共享来源37220，各原因可重叠。Birth固定core与S0 adaptive分别筛掉5588/6867次。原D1不加MAD上限，本轮whole同时增加60mm尺度及源独占性门，不能把所有差异归因于混层。

LW原帧226的231个whole点中仅3个共享源，fixed/adaptive合格，仍整列UNKNOWN；ACT原恢复不可评分，不能称挡住正确动作，但能确认准入人口显著变化。混层也可能是鱼/背景/弯曲鱼体，简单拒绝无法重建身份。

原D_balanced smooth=False，D1比较的是最后clean whole深度；15点历史用于MAD/tolerance。EMA只是记录状态，不能把当前算法描述成实际深度均值速度外推。

### 3. 上下顺序证据弱，硬准入与连续打分混在一起

MIXED共有95事件、50个q、3446条匿名GROUP观测。只有10/50个q事件的任一GROUP ROI含显著潜在混层；val/L3没有。当前ordinal没有使用GROUP层分布，而是pre与首分离core的概率比较。

50次q中18次顺序可用，全部弱，32次UNKNOWN；实际改变的S0提交为0。ORDER/OFF相同候选上下文首次分歧只有三处：Feeding原1239（pre不可评分，端点ORDER错/OFF对）、val11900（pre ORDER对/OFF错，端点不可评分）、L3原1420（ORDER对/OFF错）。关闭完整顺序使L3 IDF1下降9.588185；不能因为Feeding下降就取消全部顺序。后续alias传播不算新的独立顺序成功案例。

## Feeding逐次切换而非净值解释

MIXED相对ACTIVITY新增10、消除12、净−2；相对原Z4Q新增12、消除15、净−3。相对native仍+21次，IDF1仅+0.268647，而HOTA−0.453713/AssA−0.803811。相对原Z4Q三项均下降。

原Z4Q较native新增24次，均实际D1提交：15物理错、1不可评分、8物理正确但晚改公共号。MIXED actual-bank WRONG13/CORRECT8，考虑原有公共身份污染后严格联合WRONG14/CORRECT7。F1798 bank正确但先前公共起源错，不能叫本次完整身份恢复成功。逐动作完整链见POSTSEAL_FEEDING_SWITCH_REVIEW.json/md。

## 执行与交付例外全部保留

正式回放3421.533秒，评分1771.757秒；新增模型HTTP/smoke/训练/SAM3/补全/费用全部0。普通报告工作没有科学请求重试。

一次提前启动failure_visuals因SCORE_PROVENANCE尚未存在而失败，先于像素/预测读取；评分完成后原冻结helper正常执行。一个新增后评分Feeding报告helper首次遇到冻结baseline不含previous_mapping，修正报告容器后完成。两个失败exit/log及正确完成均保留EXECUTION_LOG；没有重跑正式预测、评分或改变科研参数。95事件合计的早期口头105笔误已纠正，逐段封存数据没有改动。

L3实际发布对照与Feeding迁移例已人工查看；图中n为native源、p为实际公开ID，颜色为实际深度，末列未来帧只用于封存后可视化。没有GT raster/RGB。全尺寸图32张留私有，PRIVATE_VISUALS/FAILURE_VISUALS和RESTRICTED_ARTIFACTS列真实路径/字节/SHA；公开仅指标图和数值证据。

LW原TRANSACTIONS gzip为179086513字节，GitHub单文件超限，原件和seal不改。原字节拆为62914560/62914560/53257393字节三块，逐块与合并SHA验证。fresh checkout先运行reconstruct_large_records.py，验证全部块后仅创建缺失原件；相同旧件只校验，不同旧件拒绝覆盖。PUBLIC_ARTIFACT_MANIFEST是完整逻辑产物；GIT_DELIVERY_MANIFEST是实际入Git文件。封存代码release_verify.py只支持直接大文件，此次用delivery-only packaged_release_verify.py做stage/实际远端所有blob及远端重建seal核验。

## 唯一下一步

只选择NEXT_STEP_PLAN.md中的“受保护旧身份事件局部重接事务”。状态/发布收益与同底座深度差值继续分列。专项报告中的顺序符号消融是未选候选，本轮及下一计划不同时启动多个修复方向。
