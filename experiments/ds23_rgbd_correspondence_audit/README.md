# DS23：固定RGB-D空间对应审计

用户在DS22结束后下达“开始”，执行其唯一下一步。审查基点 `1ff8896254cde32efa79927fe95af29b8ac4937c`。本轮复用全部90次原动作、171个唯一端点和168个真实源帧，原参考及原mask不变。原输入、代码、seal和结果只读。

核查：原SAM3坐标与RGB网格、原始深度点重投影与保存的源索引/相机Z、像素中心公式、实际RGB字节/缩放、时间配对，以及mask轮廓到同帧深度/RGB边缘的描述统计。RGB仅供私有输入诊断，不作为跟踪外观。深度边缘不等于鱼边界，RGB边缘也不是GT。

本地CPU一作业一数值线程，既有Python环境及依赖；不访问服务器/GPU。不运行跟踪、不生成预测或新IDF1/HOTA、不读GT raster/instance_id/v3、不做偏移搜索；新模型HTTP、smoke、训练、SAM3、补全服务和费用均为0。

`E:/researchsoftware/anaconda3/envs/D-MOT/python.exe -B` 依次通过复用的execute记录 initialize、必要checks、freeze、audit、review。完整测量封存后再汇总。私有图片不进Git，公开数值、来源路径/字节/SHA、真实日志和报告提交并普通push main，实际读取远端ref及关键blob核验。

复现必须使用新输出目录，保留原数据及精确源索引；禁止覆写本轮与旧seal。源代码独立审查文件说明当前软件合同与水下物理对齐精度的不同边界。
