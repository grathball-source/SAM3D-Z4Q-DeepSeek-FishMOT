# DS36 操作入口

先读PLAN.md和项目AGENTS.md。解释器`E:/researchsoftware/anaconda3/envs/D-MOT/python.exe`，沿用`E:/CAU/D-MOT/tools/jev_z4q_scene_v1_20260922/deps`。

顺序：`execute.py audit.py initialize` → `execute.py checks.py` → `execute.py audit.py freeze` → `execute.py audit.py measure` → `execute.py audit.py join` → `execute.py report.py` →实际检查可视化→交付。全部旧输入/seal只读，复现须新输出目录；不得在已完成目录重跑覆盖。错误、正确和不可评分全保留。

不调用模型、服务器、GPU、SAM3或深度补全；不读RGB/GT raster，不生成新跟踪预测。不确定性验证的未来目标只用于封存后的测量误差，不用于任何跟踪决策。private下的真实深度/mask像素不入Git。
