# SLR-1：动态空间证据的LLM影子验证

2026-09-20用户授权设计并开始第一阶段。方案见PLAN.md；本目录独立于旧实验，正式Z4Q_STABLE不变。

本轮在Windows本地CPU构建证据包、运行确定性对照、检验因果性/匿名化/输出合法性。解释器E:/researchsoftware/anaconda3/envs/D-MOT/python.exe，最多4逻辑CPU、数值库1线程、CUDA为空。原图/预测/深度缓存只读。服务器仅检查资源；用户随后指定官方DeepSeek V4.1 Flash并在系统变量保存凭据，读取已确认。run_model.py执行真实请求，不把占位、模拟或本对话的判断当成正式LLM实验。

阶段入口：select_events.py（离线选择器）→ build_packets.py（禁止GT读入）→ run_baseline.py（同证据规则与语义检查）→ pipeline.py（run_model.py→独立evaluate.py）。STATUS.json记录实际进度；pipeline_exit_code.txt记录包装器退出。MODEL_CONFIG.json在真实调用前封存，模型正式调用与评分另起进程；结果未封存前不开展新评分。

固定36包：18事件各一个合并期快照和一个首分离快照，全部当前原生候选保留。oracle边界和历史目标选择是离线条件，不声称自动触发覆盖率或独立盲测。原18事件含已有成功对照；本轮不扩大事件或搜索门槛。
