# SLR-2：空间证据摘要与实际RGB增量验证

本轮由2026-09-20用户“请复盘，然后给出下一轮计划，然后开始实验”授权。REVIEW.md解释旧轮失败，PLAN.md为调用前冻结协议。独立于engineering_r3，所有旧结果及原始输入只读。

本地解释器 E:/researchsoftware/anaconda3/envs/D-MOT/python.exe。最多4逻辑CPU、库1线程、无GPU，无服务器作业。prepare.py→input_checks.py→run_baseline.py→contract_checks.py/evaluation_checks.py→vision_smoke.py→pipeline.py（run_model.py后独立evaluate.py）。MODEL_FREEZE.json冻结代码/协议/数据，MODEL_ACCEPTANCE.json封存全量输出后才离线评分。START标记防止无意重启重复收费；失败保留全部产物，不删除标记重新抽样。

状态入口STATUS.json、LAUNCH_STATUS.md及logs/server_connection/spatial_llm_stage2_20260920.json；实际完成以pipeline_exit_code.txt=0、验收哈希及RESULTS.md为准，进程启动不等于实验完成。官方deepseek-flash密钥沿用Windows系统变量，不写进文件。研究产物含模型原始响应，分享时须保护研究数据；不包含认证头或密钥。
