# DS35：原 Z4Q 权威状态与深度事件提案隔离

先读 PLAN.md、DATA_CONTRACT.md、项目 AGENTS.md。使用已有 CPU 环境和原冻结输入，不安装依赖。

解释器：E:/researchsoftware/anaconda3/envs/D-MOT/python.exe；依赖：E:/CAU/D-MOT/tools/jev_z4q_scene_v1_20260922/deps。

流程：checks.py → guard.py prefix 真实切片 → acceptance.py → freeze.py → orchestrate.py → score.py → report.py → post_visuals.py → delivery.py。各次用 execute_unique.py 保存真实退出码和日志。正式八段全部封存后才允许评分。旧目录只读，输出目录只创建不覆盖。

关闭新增深度时按全部状态逐帧验证原 Z4Q；缺证据或失败直接保留自己的原分支，没有整套外部 B0 复制。该版本有30帧首次发布缓冲，属于离线有限延迟回放，不是实时部署，也不是 S0。

新模型 HTTP、smoke、GPU、SAM3 推理、训练、补全服务与费用均为0。私有图像仅用于封存后的可视化，不进入关联。
