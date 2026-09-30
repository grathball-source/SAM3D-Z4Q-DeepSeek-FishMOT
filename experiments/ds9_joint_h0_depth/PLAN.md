# DS9：原生H0下的归一化联合事件关联

审查基点：a56e3cae72caffc34a19318a786c42649bbe16af。用户“开始下一步”执行DS8/NEXT_STEP_PLAN。一次冻结完整试验，无按GT调参、追加资格测试或滚动寻找提点。

## 假设与控制

显式保留当前合法身份H0后，归一化的几何/深度证据能否在合法首分离事件改变并改善原生映射？完整同源SOURCE_OLD四段1471帧：0–199、351–555、701–1060、1201–1906。全部已曝光，仅开发诊断；不称独立验证。

六枝各自真实状态：SAM3_NATIVE、J0_GEOMETRY、J1_RAW_DEPTH、J2_RESTORED_DEPTH、J2_DEPTH_ZERO、J2_DEPTH_PERMUTE。ZERO保留真实测量/历史，仅完全去掉深度似然，实际发布必须与J0逐帧一致。PERMUTE按当前两post的固定顺序交换仅供关联的深度观测，记录原始fact与使用到哪个候选；不能交换历史、几何、质量或state所接收的真实量。

冻结DS8原mask、自动预测scanner、触发、q、pre参考、generation/epoch风险切断、原30/10缓存、二维均值运动、depth WLS均值与尺度、adaptive exclusive core、测量质量及S0-P事务/发布。风险/群组与未选post不认证为个体历史。无GT选择片段或q。无未来post，无回填。原生返回和既有alias继续自身合法状态，H0不接回新ID，H1/H2才允许stage；共同mask及所有残片保留，公开ID同帧一对一。

## 固定似然与门槛

- H0是真实own-branch lawful preview中两个post的映射；H1/H2是两个旧reference的物理对应。完全相同映射去重，优先保留H0语义，先验在唯一物理映射上均匀，不把同一映射当多票。不另加经验改号先验。
- 几何均值严格等于旧numeric_choice逐边predicted_center_px：双方pre速度可用才用真实最近10点回归，均值外推仍min(gap,1秒)，否则两者取末点。post仅一帧，post速度UNKNOWN。
- 几何信号使用二维Student-t、df=4，必须含行列式归一化项。past同版本clean片段逐点下一点残差，历史prefix最多10，不能用q/post。至少3残差时取残差二阶矩，.5完整+.5对角，另加16px² I；不足时sigma=max(4px,0.1末bbox对角)。这些是预测一致性代理/固定假设，不是GT拟合或物理精度。
- Student-t shape取上述covariance/2（df4），再乘1+(actual gap/max(最近最多10点预测窗口的真实pre span,1/30秒))²。均值封顶不把真实gap改短；真实残差、样本、时间、版本与fact列出。
- 几何背景为640×360区域的统一密度；深度背景沿DS8当前whole median/MAD，scale>=60mm，信号沿原DepthState预测与实际post噪声合成。各模态.9信号+.1共同背景；比较正规化log likelihood ratio。不可关联H0边按共同背景，非免费零距离。
- depth信号Student-t df4。任一post缺深度时整个post深度模态共同无信息；pre某role缺时整行共同无信息。未知保留，不奖励某个缺测候选。大尺度含归一化惩罚；宽覆盖不等于准确。
- 联合几何与深度条件独立是冻结建模假设；两者normalized log likelihood相加，不沿用未归一化.25加权。归一化后验仅是本假设下的数值，不宣称已校准身份概率。
- 最佳唯一映射相对runner-up至少log9方可H1/H2，否则H0。H0最佳或只有一个唯一映射也保持H0。stage仍检查占用、版本、mask和局部原子写集；失败走自己局部fallback并继续全段。

归一化Student-t公式依照[SciPy官方文档](https://docs.scipy.org/doc/scipy-1.16.0/reference/generated/scipy.stats.multivariate_t.html)，实现与本地已安装SciPy核对，无新增依赖。

## 执行与判定

先必要数值/去重/缺失/置零/错配/发布/事务检查，以及真实自动最早可用事件source→association→首次publish切片。冻结所有代码、参数、来源与评分，然后六枝完整回放；全部预测和访问记录seal后才独立TrackEval和物理参考评分。测试不是能力结果，不要求人工/数值先涨分。

唯一跟踪目标：至少一个真实深度枝IDF1/HOTA/AssA均超过同源native且IDSW不增加。独立深度支持还需相对J0/置零/错配列出真实差值；几何同样收益只属共享机制。FP/FN、正确/错误/不可评分、进入前错号、实际改号、first publish、未stage与fallback、无事件/缺失、耗时全部保留。旧405帧及DS8仅对照，不混新得分。

v2上游曾用RGB与i±1清理：修复枝为含未来支持的离线诊断，非因果在线。禁止v3标注补孔、annotation instance_id、直接RGB、未来post、LLM/VLM及旧模型回答。新模型HTTP/smoke/训练/SAM3/补全服务/费用均0。不连接服务器、不安装环境。

无论结果提交所有本轮公开代码/配置/测试/日志/预测/指标/可视化/报告，非破坏性整合推送main并读取远端ref与关键文件实际核验；旧DS1–8tracked文件全字节锁。受限像素/GT/RLE输入/凭据不上Git，清单列路径、字节、SHA与复现依赖。单次冻结版本失败即停止，不放宽到命中。最后只规划一个下一步。
