# DS38 — 真实候选覆盖与深度失败审计

主报告：FINAL_REVIEW.md；机制复盘：DEEP_REVIEW.md；单一后续计划：NEXT_STEP.md。

基点4163d007d9a030999a6c1f027f0bf50943787061。原始只读代码、缓存和封存在E:/CAU/SAM3D-Z4Q-DeepSeek-FishMOT；本轮独立输出和main交付在F:/CAU/deliveries/SAM3D-Z4Q-DeepSeek-FishMOT-DS37-20261007。DATA是E:/CAU/D-MOT/data/AlignedFeeding_v1的原始depth_mm。原输入与public/private产物的路径、字节、SHA在INPUT_PINS、各seal、FINAL_PRIVATE_INVENTORY与PUBLIC_ARTIFACT_MANIFEST中。

这是1471帧原Z4Q精确诊断回放，覆盖全部27次提交，没有运行新跟踪方法，没有新的IDF1/HOTA提点成绩。所有235个输入时刻/6289个观测、全部2019个分布比较/1309个次序记录保留。仅用旧曝光GT数字摘要事后评分身份关系，不读GT raster或新test。请求与费用0。

## 量测区别

主特征seal使用已存在DS36自适应core作局部分布诊断。原Z4Q profiles的固定腐蚀core在LEGACY_ROI补充中严格复现。两者不混同，补充是在已曝光结果上的量测验真，单独freeze/seal，不回写主特征。原profiles area/n/fraction/median/MAD/q25/q75全6289对象逐列相等。原像素加权与独立传感器来源去重分列。

原灰度图的黑色可能是低深度或缺失，原件保留。最终固定900–1400mm显示，缺失用洋红，来自原depth而非RGB。颜色仅区分匿名观测，不绑定跨帧身份。真实图/数组仅私有，公开SVG是汇总分布。固定显示范围仅用于查看，不是物理门槛。

## 复现

需固定基点的独立checkout、本文交付的代码与PLAN、完全相同的E-volume私有来源和现有D-MOT Python环境；新建空DS38输出，不覆盖已有结果。按顺序运行：audit.py initialize → checks.py → audit.py freeze → audit.py replay → audit.py measurements → audit.py join → report.py → deep_review.py → legacy_roi.py → fixed_visuals.py → finish.py。检查独立退出码，补充图的实际查看记录由操作者如实填写。输入/来源路径改变必须重新建立来源绑定，不能静默放宽旧哈希合同。

没有依赖安装、网络模型、训练、SAM3或深度补全步骤。运行library_threads=1，本地单CPU工作进程；无需服务器、GPU或DeepSeek key。失效与技术修复日志在IMPORT_REPAIR_LOG、CHECK_REPAIR_LOG；这些发生在正式freeze前、实际实验帧数0。

main交付：delivery.py prepare（需要真实查看记录）→明确暂存本轮公开范围→delivery.py index→普通commit/push→delivery.py remote→提交核验回执并普通push→delivery.py final。严格排除private，旧archive hash最终复核。
