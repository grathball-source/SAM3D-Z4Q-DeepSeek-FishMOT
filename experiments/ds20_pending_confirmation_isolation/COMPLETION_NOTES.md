# DS20交付补充：工程完成，深度提点目标未成立

正式八段六列完成：每列20098帧，120588列帧，全部预测与访问记录先封存后独立评分。四个归档控制逐帧及指标精确复现；40196个新分支帧的真实确认状态审计通过。10项直接状态单测、真实4190帧/列前缀及来源检查通过。冻结源码、旧实验和seal保持原字节。模型HTTP、smoke、费用、训练、SAM3与补全服务均0。

## 结果解释

主分支MIXED_ISOLATED五个单位的IDF1/HOTA/AssA/IDSW/FP/FN与旧MIXED_RETURN完全相同。Feeding、开发、验证、LW仍低于原Z4Q，L3持平；相对SAM3的既有收益不算本轮新增深度贡献。完整同源六列与全部逐次切换在RESULTS.md及run/POSTSCORE_SUMMARY.json。

组合深度相对ACTIVITY_ISOLATED在开发有小差值、LW有HOTA差值，但Feeding与验证下降。46个同event/同q/同候选源对照的S0原始选择完全相同；另4个q不构成同输入配对。15例完整publisher不同中只有4例事件pair自身不同，11例仅组外映射不同，不能归为本次顺序深度提交。50个q全部H0回退，顺序联合提交0；95事件中45个没有q也完整保留。见FAILURE_EVIDENCE_REVIEW.json/md。

32个UNKNOWN来自16个无同帧pre配对、13个几何/深度来源未对齐、3个当前配对深度被拒；13例共199条检查采样缺少几何引用，不是199个独立事件。其余18例仍是弱未标定代理，传播尺度中位441.18毫米。此结论是来源与数值输入诊断，不是深度物理准确率或“完整历史关联无效”的理论判定。

## 确认隔离的真实副作用

Feeding195与LW952的普通确认竞争延迟消除；L3两新列保留3025的自然返回。新活动列的LW返回则从旧144→133/local3272变为145→133/local3342。首次公开使实际身份版本变化，确认重新计数，随后接触风险和候选迁移多次中断；不是简单晚一帧。之后原D1真实提交150→144，新增原帧3427的一次切换、消除0，IDSW8→9。旧、新局部返回及后续自动动作的物理评分均UNSCORABLE，不能改写成错误或正确。64条真实trace及11个来源哈希另验证通过，见ISOLATION_EFFECT_REVIEW.md/json与ISOLATION_EFFECT_SOURCE_CHECK.json。

## 可视化与受限产物

PRIVATE_VISUALS.json列10张真实深度/mask与实际发布前中后图，全部明确为封存后诊断，未来列不进入预测，无RGB或GT raster。人工查看了聚合METRIC_COMPARISON.png与LW_frame3342_actual_publication_ROI.png：标题帧与实际发布对应，后者真实显示新活动列n145:p133、旧活动列n144:p133；不据图推断未知物理身份。其他图有程序来源/ROI/帧/哈希绑定，不冒称逐图人工验收。

公开聚合图不含私有像素。私有原始深度、mask、工程切片及图像留在真实本地路径；RESTRICTED_ARTIFACTS.json列字节、SHA、依赖与复现方式。科学脚本采用exclusive输出；另建独立实验目录和新输出复现，禁止在此已封存目录补写或覆盖。原输入及DS18完整缓存需保留，同源源包和旧代码依赖不可换成另一预测源。

PUBLIC_CONTENT_AUDIT.json完整检查281个已关闭公开文件、362009条JSONL记录和分块哈希，最大73439211字节；新增诊断和追加ledger由PUBLIC_CONTENT_SUPPLEMENT.json补查。其自身输出、在途日志及最终typed delivery receipts由实际暂存/远端字节验证覆盖。最终交付清单与HANDOFF更新由finalize_delivery.py生成，实际远端证明在REMOTE_VERIFICATION.json；最终再读取main及全部清单文件，不只凭push成功推断同步。

## 仅一个下一步

共同冻结进入风险前真实合格的几何/深度来源片段，保持版本、时间、片段与mask/fact引用一致，缺失仍UNKNOWN；一次冻结同源全段验证，包含同源SAM3、原Z4Q和共享来源底座对照。详见NEXT_STEP_PLAN.md。本轮不自动启动，也不追加第二修复、模型或阈值搜索。
