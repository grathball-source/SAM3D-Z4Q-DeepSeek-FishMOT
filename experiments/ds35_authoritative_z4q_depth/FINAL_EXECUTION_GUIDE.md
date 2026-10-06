# DS35 最终执行入口

本文件是封存后追加说明；冻结 README、源码和所有旧 seal 保持原字节。先读 FINAL_REVIEW.md 和 POSTSEAL_INTERPRETATION.md，再看逐事件 RESULTS.json、run/METRICS.json 与远端核验收据。

## 实际评分入口

原 score.py 在 LW MS1-F2896 的整数键/JSON字符串键规范化上失败，尚未读取评分参考。正式完整评分使用追加的 **score_serialized_v2.py**，仅统一复算决策的 JSON 表示，再调用冻结 score.py 的全部来源、状态、首次发布检查和原指标数学。所有八段重新检查后才访问参考。

DECISION_BINDING_DIAGNOSIS.json 保存真实源复算逐字段无差异的证据；SCORER_SERIALIZATION_REPAIR.json 记录改动范围；CHECKS_SCORER_SERIALIZATION_V2.json 是通过版，V1 的失败代码、JSON与日志独立保留。SCORER_SERIALIZATION_COMPLETION.json 绑定适配器、评分冻结与实际完整指标。原 SCORE_PROVENANCE 记录被冻结评分模块，适配器完成记录是必要的补充，不能忽略。

## 复现顺序与依赖

使用现有 D-MOT Python 和记录的 deps，提供 PRIVATE_INVENTORY/RUNTIME_FREEZE/各 FREEZE 所列的精确受限输入与哈希。原始 SOURCE_OLD SAM3 mask、原始 depth/source_index、DS18来源证书和原评分参考版本不能互换；可视化另外需要原 RGB/标定。代码使用 Windows 的绝对来源路径，迁移机器需要在新试验目录重新建立路径绑定，不能改既有 seal 后称精确复现。

在独立新输出目录运行冻结检查、真实工程切片、输入冻结与 orchestrate；全部预测和访问/START/END封存之后，运行：

1. diagnose_decision_binding.py（真实源重新生成失败病例的决策，逐字段诊断，不读参考）。
2. checks_scorer_serialization_v2.py（真实封存案例与事实/映射/选择篡改检查）。
3. score_serialized_v2.py（完整来源门槛通过后独立评分）。
4. report.py、postseal_measurement_review.py、postseal_interpretation.py。
5. post_visuals.py、postseal_depth_gate_visuals.py；render_public_svg_v2.py 与实际图片检查；仅检查后记录 VISUAL_ACCEPTANCE。首版renderer把Edge启动器返回误当成PNG已生成，失败记录保留，V2实际等待完整PNG。
6. delivery.py 的 prepare/index/remote/final（实际 Git 提交、非 force 推送与远端全部公开 blob 核验）。

所有输出采用新建模式。已完成目录不能直接重跑这些步骤；不得删除旧 seal、重写已有成绩或追加新模型调用。本轮最终公开文件清单见 PUBLIC_ARTIFACT_MANIFEST，受限图像实际路径/字节/SHA与复现依赖见 PRIVATE_INVENTORY。原始私有像素不进入 Git。

## 解释边界

DEPTH_OFF 必须在每帧完整状态上复现原 Z4Q；深度增量只按 DEPTH_OVERRIDE 相对该同底座对照解释。独立事件证据、有限30帧首次发布缓冲、局部事务和自身分支继续运行均保留。没有光流、场景流、轮廓补画或模型请求；这不是实时部署。本轮是否提点只由真实新提交和封存后统一指标判断。
