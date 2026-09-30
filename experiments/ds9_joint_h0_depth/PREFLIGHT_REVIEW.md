# DS9 独立实现预检

状态：**PASS_IMPLEMENTATION_REVIEW_WITH_BOUNDARIES**。没有发现需阻止当前固定试验的实现问题。必要合成检查、真实最早 q 切片与其验收仍由主流程执行；本审查没有重新运行测试、回放或评分，不等于实验收益验收。测试结果由独立的 CONTROLLER_CHECKS、MEASUREMENT_CHECKS、ADAPTIVE_CHECKS、ASSOCIATION_CHECKS、SCORE_CHECKS 等 JSON 及执行日志绑定，实际切片结果另由 REAL_SLICE_ACCEPTANCE 绑定。

基点：a56e3cae72caffc34a19318a786c42649bbe16af。审查时间：2026-09-30T18:54:44.512146+00:00。

范围：只读 NEXT_STEP_PLAN、DS9 PLAN/CONFIG、实际 association/runner/source/measurement/controller/guard，以及已封存 DS8 来源摘要。没有读取新 GT、RGB、深度像素、旧模型回答；没有网络、模型、训练、服务器或新补全调用。本文件只记录实现和建模边界，不按已曝光案例修改参数。

## 来源、ROI 与状态

- 同源 SOURCE_OLD 四段 0–199、351–555、701–1060、1201–1906，共 1471 帧。runner 验证局部 frame=index+1、global_frame=start+index，使用旧 SOURCE_MANIFEST/derived/source list；正式预测前重新检查源文件尺寸与 SHA。原 DS1–8 tracked 文件由 OLD_READONLY_LOCK 约束。
- adaptive_core.py、measurement.py、restored_source.py、controller.py、launch.py 与 DS8 **逐字节相同**。ROI 仍为当前预测 mask 的 exclusive component 距离规则，不用深度或参照挑像素。retained/inferred 仍分开，retained 优先；两组 fraction 均以真实几何 ROI 面积作分母。
- 保存的 native v2 H5 是真实输入，不采用 v3/p4 剔除后的投影。init 只读取 1D index/time metadata 和数组形状；__call__(global_frame) 只读取对应行的 depth_mm/original_depth_mm/filled_mask/invalidated_reason。 recorded geometry、RGB相机Z、近Z光栅/源索引及时间一致性检查沿旧实现。
- v2 在上游使用 RGB 和未来清理支持；本轮运行未读 RGB 不使其变成因果恢复。物理准确度、录制标定准确度和鱼体表面归属仍 UNKNOWN。native uint16 或复投影一致也不能证明实际距离正确。
- J0/J1 留实际 raw 测量历史，J2/其两个对照留实际 v2 测量历史。GEOMETRY 与 DEPTH_ZERO 的 association 分支完全不读取 frozen depth/当前 depth，因此即使保存的历史不同，选择器算术相同；全段 ZERO=J0 的发布一致性仍须正式检验。
- PERMUTE 只改变当前两个 post 的 depth 指派。几何点、pre 历史、whole 背景和 actual state 接收的测量不交换；原始 fact 与实际使用 fact 分别记录。双方 post 的质量门槛共同检查，任一缺测则整个 post 深度模态无信息，不能因交换得到资格。

## 几何预测与尺度

几何均值沿旧 numeric_choice：双方 pre velocity 可估计才用旧最近最多10点 OLS，否则两角色均用末点。均值外推仍 min(actual gap,1秒)；缩短均值预测不缩短用于尺度的真实 gap。单帧 post 的速度保持 UNKNOWN。

_fragment 只取 suspect_frame-1 以前、query 时间以前的连续 clean 尾段，碰到风险/邻接/帧缺口/时间非递增/source-generation-public-epoch 变化即截断，不拼接历史。校准的每个 target 残差仅使用其之前的 predictor prefix；另一角色也只使用 target 之前的 frame/time。不存在 q/post/GT 进入 geometry residual 的路径。

至少3残差时取未中心化第二矩 M=Σ rrᵀ/N，C=.5M+.5diag(M)+16I。它保留预测偏差的第二矩，不能描述为已去偏的物理测量方差。不足3残差时 C=σ²I，σ=max(4px,.1末bbox对角)。最近<=10预测窗口给真实 pre span，growth=1+(actual gap/max(span,1/30秒))²；最终 Student-t shape=growth*C/2。

二维 df4 Student-t 的实现含全部归一化项：

`log f = lgamma(3)-lgamma(2)-log(4π)-.5 log det(S)-3 log(1+δᵀS⁻¹δ/4)`。

df4 的 covariance=2*shape，故 shape=C/2 与固定规则一致。shrinkage、16px² floor、bbox稀疏尺度和增长公式均为事前固定代理；不能把 past next-point prediction consistency 说成经实测标定的真实鱼体定位误差。

## H0、共同背景与联合选择

- H0 来自此分支自身 lawful preview 的真实两个 post 映射，不接回新ID。H1/H2 为两个旧 reference 的两种映射。以 source→public 的完整映射去重，H0 优先代表重复项；uniform prior=-log(唯一映射数)，重复标签不增票。这里的“物理映射”是候选对应关系命名，并未获得物理身份认证。
- H0 的无旧reference边明确使用共同背景：geometry log density=-log(640*360)，depth 使用相同的 whole t4 背景；LR=0 是背景基线，**不是零距离/免费完美匹配**。H0若已有合法旧alias，关联角色使用同一边模型。
- geometry 与 depth 信号都为 `.9*signal+.1*background`。depth background 沿 DS8 whole median/MAD、scale>=60mm；每个候选使用同一组当前观测的背景密度。候选 LR 与完整 log density 的排序等价，因为共同背景之和与候选无关。
- pre某role缺测时该整行使用共同无信息模型；任一post缺测时当前整对的深度模态共同无信息。大尺度含 Student-t 的归一化惩罚，未知没有某一候选的独占零代价奖励。
- depth 预测仍由旧 DepthState/predict 产生，post误差与预测 scale 用 hypot 合成；inferred core.mad 是 `60/1.4826` 的假定噪声适配下限，不是实测 MAD。当前 actual MAD 仍保留在 cohort 字段。
- 联合 score 为 log_prior+geometry_LR+depth_LR，无额外 .25 权重。最佳唯一映射相对 runner-up>=log9 且代表非H0，才提出 H1/H2；H0最佳、单一映射或间隔不足均选择H0。stage 仍在真正发布前检查占用、版本及原子写集；拒绝后 own-branch fallback 继续自身状态，不发布临时猜配。

## 必须保留的解释边界

归一化 posterior 是在当前去重候选、统一先验、`.9/.1` 混合和 geometry/depth 条件独立假设下的建模值；不是已校准身份正确概率。whole深度背景也不是物理认证的 tank surface。候选 ranking 与真正 stage admission 是两层检查，不能把数值 accepted 当作真实发布改变。

source guard 阻止显式 GT/RGB/v3 路径、网络连接及 NPZ 非 depth_mm/source_index 字段。Python audit 记录不覆盖所有原生 HDF5 底层 I/O；这里依赖被绑定的当前行 reader 实现和真实源哈希，不能把路径摘要夸大成所有底层访问均被独立观察。

正式结果只按 sealed predictions、access audit、official metrics 和 actual first-public/transaction 核验。主目标为真实深度枝同时超过同源 native 的 IDF1/HOTA/AssA 且 IDSW 不增，并另列相同 geometry、ZERO、PERMUTE 差值。geometry 独自有同样收益不能归于深度；曝光的1471帧也不能称独立泛化证据。不降低 log9、不修改资格、不追加研究分支。

## 读取版本绑定

以下 SHA 绑定本次实际读取源码。后续正式 FREEZE 应同时保存这些文件与本审查；若相关实现改变，需要明确记录差异。

| 文件 | SHA-256 |
|---|---|
| CONFIG.json | 647c423d4d12d674a115accb2800b44c6c46b3b83bd46fa36e698009b3f16164 |
| PLAN.md | cfe327e55cf54196007dd5d0d084d94f30146d8922de7a0a89ce79ee0c69928a |
| runner.py | b0a262ea0aad251c079ad299552b2ea487b87b7a9c48dbed4804660ec1e50c22 |
| association.py | 9166718e8331866dec1c1565fe9b82aa0c10bd21625b164a39d99be56b780169 |
| adaptive_core.py | 83a0cceb0646f2835fcf879764f0b11e10e2af9d9e4983ec9718f7399b0f213b |
| measurement.py | d559242ce7ba513b721dc5ce51a7bd44c2b5e42528effedcaa7aed811d4ab861 |
| restored_source.py | 384bf38e3c5d8671ae2b888e4dd66319bbcc5804c1e09c81eecec7a22a681937 |
| controller.py | 9862e0e17a7cf9708ec964552291d8b1de9e84d97558317d2dd4619f96653cdb |
| launch.py | d64e7910cd56b3a8c72325dbd59c4866b12f591e96b7ec568b97e8e08166404c |

DS8 ALL_PREDICTIONS_SEALED SHA：52909ad9821b9ed5ff0b918648196174677455d2372b782af4f42c79330f0658，与其 SCORING_SEALED 指向一致。DS8 仅作已冻结来源和约束参考，原件未改。
