# DS22：局部背景相对深度提取

用户在DS21复盘结束后下达“开始”，授权执行原 `NEXT_STEP_PLAN.md` 中的一个测量表示实验。基点 `bc1526e89e16040f270639c7620ecb67570775f0`。

保留全部90次原Z4Q持久动作及精确原参考；复用同一原始深度、mask和source index。新增测量与支持解释，不改跟踪状态，不生成新跟踪成绩。原Z4Q维持性能参照。新模型HTTP、smoke、费用、训练、SAM3及补全服务均为0，无GPU或服务器作业。

使用 `E:/researchsoftware/anaconda3/envs/D-MOT/python.exe`。实际顺序：通过execute运行run initialize、checks、run freeze、run measure、run join、INDEPENDENT_REVIEW、visualize；生成报告及受限清单后提交、普通push main并读取远端ref与公开blob核验。原source/seal只读；输出使用独占路径，不在原目录重跑覆盖。复现需新输出目录及相同原数据依赖。

只有私有可视化保存像素，公开数据保留数值事实、源绑定、统计、代码、真实日志与报告。背景、鱼体归属及身份真值均不由残差支持认证。
