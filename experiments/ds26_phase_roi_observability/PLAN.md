# DS26：阶段测量对象的固定配对审计

授权：用户在DS25唯一下一步计划入库后要求“启动”。基点 e76a5184aafa9780a46c93f2128264291707c4d6。

唯一变量是端点ROI。复用DS25同一测量函数与所有实际质量常数，逐个测量A/B原始SAM3 mask；不使用bbox或选择最优深度层。保留所有背景兼容、弱、噪声、缺失与inclusive/independent不一致。接触区间逐项引用并校验旧封存匿名fact，区域、源和数值完全不变。

固定全部15 anchor/partner/seed上下文、540原调用路径引用、532严格候选角色配对。378只是旧测量序列去重数，不能当候选配对数。全部119同步pre时刻纳入；每一实际q保留。原始预测选择不受新深度覆盖或GT影响。三段没有该测量上下文也明确报告，不造事件。

pre角色来源由旧实际bank anchor/public/version合同认证。post是原候选入口通过几何、质量、版本门槛的真实source mask；它不等于候选target的身份，不能因本轮测量而认证为clean身份历史。逐项保留其实际published public与q-frame bank anchor状态。群组和风险期间始终匿名，不拼接。

## 在测量前冻结的判定

1. 工程：来源、实际mask、q时间、全部旧fact引用、有效常数、旧seal和文件hash通过；无任何身份状态写入。
2. 输入：空ROI是否被实际mask覆盖替代、独立有效点/原面积、annulus背景样本、拟合不确定性、完整支持与缺失逐列配对。ROI变化同时改变分母和背景拟合，不能称传感器改善。
3. 匿名端点支持：仅原parent质量和partition/qualification一致、无substantial unresolved、恰一合格支持时报告sole proxy。既有两层status保留，不用于单鱼资格判定。多层不选峰。sole proxy也不认证鱼体或身份。
4. A/B在同一帧的shared native source另算。原点与合格支持共享分别保留；合格支持共享时不能形成两个独立角色证据。不做跨帧source index匹配。两端无共享且各sole proxy时仅报告实测差、合并sigma和无阈值符号；不新增身份veto。
5. 时间可观测性：原接触种子、全接触链逐项保持。端点变好不能补全隐藏鱼或建立连续身份。没有连续匿名链不沿用DS25 swapped endpoint veto。

先跑必要测量/来源单测和最早真实F432配对切片，随后冻结所有科学代码、cohort、源与判定。直接完整测量固定cohort，不要求正确答案或科研提点。全部测量封存后独立数值复核和私有深度/mask可视化。GT、RGB、annotation instance_id、修复v3、未来帧、网络、模型HTTP、训练、SAM3推理、补全、GPU、服务器和费用均为0。

本轮没有新的跟踪预测或IDF1/HOTA，不能复制旧成绩伪造新性能。结束后提交所有公开数字代码/记录/报告并正常push main，实际核验远端ref和文件；像素留私有并列路径/字节/SHA。旧seal只读。最终仅提出一个由实测决定的下一步，不自动开始。
