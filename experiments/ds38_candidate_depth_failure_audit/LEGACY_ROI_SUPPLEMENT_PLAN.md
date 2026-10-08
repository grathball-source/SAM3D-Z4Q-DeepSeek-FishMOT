# 原输入core的补充验真（事后诊断）

原DS38封存特征复用DS36自适应core；它与原Z4Q profiles中的固定腐蚀core不同。原控制流/输入/trace/完整状态仍严格复现，原特征与seal只读。为完整解释原门控，追加原ROI诊断，不能把两种core混称相同。

范围固定为已封存量测的235个时刻、全部6289个匿名mask。调用原SOURCE.exclusive_core与stats，逐列严格复现旧profiles whole/core的area/n/fraction/median/MAD/q25/q75；不因GT选择新frame、参考、片段、阈值或深度层。分别保留原正值像素人口、去重独立传感器人口，以及原生样本计数可能重复的区别。

所有原矩阵列/历史bank使用同一精确来源参考，新增完整原core Wasserstein诊断，原候选与动作不变。代码、ROI函数和既有量测seal先冻结，补充人口及比较另seal。原cohort/GT已经曝光，这个补充仅是事后量测审计，不称新的盲实验或模型成绩。无RGB、GT raster、训练、SAM3/API/补全、费用。实际人口数组保持私有。
