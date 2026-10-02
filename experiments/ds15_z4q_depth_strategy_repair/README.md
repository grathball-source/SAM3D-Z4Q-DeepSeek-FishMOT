# DS15 Z4Q与深度策略修复

用户要求深度比较原Z4Q与R12，取长补短后直接开始实验。审查基点95f1a83172d6b90f36ff8bd5a7d948e74b42ae80。只有本地CPU因果回放，无模型HTTP、训练、SAM3推理、补全、服务器或GPU作业，费用0。

来源固定为DS14完整20098帧：FishSA8400与2888分别初始化，Feeding原四段1471、L3 3710、LW3629各自初始化。原始raw深度、原保存mask、原二维几何、原触发扫描、原首分离q规则、原观测质量/候选/交易/首次发布规则保持。Feeding另436帧已存在但未纳入；L3/LW预标注依赖预测，仅弱参考诊断，所有来源已曝光，不能称盲测或跨独立录像泛化。

先阅读audits/三个独立审计，PLAN.md和STRATEGY.json。新实验五臂SAM3_NATIVE/Z4Q_FROZEN/R12_RAW/Z4Q_SHARED/Z4Q_DEPTH；原版Bridge单独执行无manager，旧R12必须逐帧/事件精确复现。SHARED与新深度版共用保护、匿名证据、同版本参考保留和局部事务；SHARED只用原Z4Q自动候选，没有额外事件/出生改号。新深度版保留原自动规则，只有有证据的单条候选可被深度否决，UNKNOWN保留原候选；额外事件改号逐身份验证深度偏好，不能让一条身份或几何优势强制交换两条身份。

30帧实时缓存与完整冻结参考分开：仅保持既有latest_fragment，不合并风险段/版本，12秒到期后失效。全q仅当前首分离帧；风险/残片保留，组只写GROUP，POST在决定前不能进入pre。旧深度版参考仍严格按其原代码冻结，不回写旧结果。研究参数、同源输入、程序与评分门槛全冻结之后运行，所有8个预测/access封存之后才评分。

解释性旧CONFIG复制字节不作为本轮启用声明；实际生效的常数及五臂在STRATEGY/common/hybrid/group_association中，可由冻结SHA验证。其他controller/forecast/birth/certificate等复用不可变源码。准备数据引用DS14/private，新增私有切片/像素放本轮private或slice；公开数字输出在run/*/public，原像素/RLE/GT不提交。

运行现有D-MOT解释器与已安装TrackEval依赖；execute.py记录所有命令/出口和日志。check_prefix.py进行真实50帧无GT等价/状态检查；freeze.py冻结八段；orchestrate.py运行全部并汇总seal；baseline_check.py仅封存后比较旧Z4Q档案；score.py读取原DS14最终原版GT版本/协议，评分所有mask、全部ID和残片。普通失败如实封存/记录，不覆盖旧seal。所有代码、日志、完整指标、病例可视化和报告最终提交main并实际push/核验远端。
