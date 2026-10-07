# DS37：原Z4Q候选边上的稳定深度水平与因果漂移尺度

读PLAN.md。复用原八个同源片段20,098帧、原始深度和原SAM3保存源；不新增模型HTTP、费用、训练、SAM3推理、补全、GPU或服务器作业。

四分支各自运行：SAM3_NATIVE、Z4Q_FROZEN、Z4Q_WLS_VETO、Z4Q_LEVEL_VETO。后两者共用DS32真实矩阵入口、独立不可变anchor来源与发布事务，只改变深度预测。旧源码和seal只读。全部预测和访问记录封存后，独立读取已有曝光参考评分。

必要单测/真实切片→freeze.py→orchestrate.py→score.py→postseal.py。execute.py隔离旧模块名；Python使用E:/researchsoftware/anaconda3/envs/D-MOT/python.exe，既有deps在E:/CAU/D-MOT/tools/jev_z4q_scene_v1_20260922/deps。

原始深度/mask图只留private，真实路径、字节、SHA与复现依赖另列。公开代码、日志、数值记录、预测、指标、报告及不含私有像素的图全部普通提交/push main并核验实际远端。
