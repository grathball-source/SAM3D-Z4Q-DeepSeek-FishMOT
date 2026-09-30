# DS9 独立后封存来源与结果审查

状态：**工程执行完成；固定跟踪目标未达；无 raw/v2 深度实际输出增量**。

审查时间：2026-09-30T19:39:52.379983+00:00。范围是已封存预测、访问记录、评分及追加工程精度 provenance。没有再回放、评分、测试或模型调用，没有读取原始 GT/RGB/深度像素。旧文件、PREFLIGHT、研究代码、预测及评分真值均未修改；本文件是新增只读审查结果，不追加研究分支或新参数建议。

## 绑定和发布事实

独立核对四段的 40 项 sealed 产物 SHA、63 个唯一 frozen 代码文件 SHA，以及 678 个旧 DS1–8 tracked 文件 SHA，全部一致。全段结束状态与执行日志对应 1471 帧、六枝、0 新模型 HTTP/费用。PREFLIGHT SHA 仍为 c38335e9…，其读取版本表的 CONFIG/PLAN/runner/association/来源/ROI/controller/guard 全部与当前已冻结版本匹配。

四段各七类 source/native/v2/metadata 绑定（共28组）与 DS8 FREEZE 完全一致：SOURCE_MANIFEST、source list、derived inputs、scan、restored source、current metadata、native depth sources。原始传感文件在正式冻结和封存验证中校验；此次独立审查检查绑定及 sealed 实际结果，不重新从原始像素生成测量。

逐帧读取全1471帧实际预测，确认：

- SAM3_NATIVE 与 DS8 的原生预测完全相同。
- **J0_GEOMETRY = J1_RAW_DEPTH = J2_RESTORED_DEPTH = J2_DEPTH_ZERO，逐帧每个公开身份和 mask token 均完全相同**，不只是汇总指标相同。
- 六枝保留相同的原生 mask 序列与全部残片，同帧公开 ID 一对一。
- 95 个 q 的 first_public_pair 都与该帧实际封存预测对应，post_sample_count=1；不是 preview 映射代替实际首次发布。
- J0/raw/v2/ZERO 对原生有相同的263帧、263对象公开身份变化；PERMUTE 为334帧、405对象变化。

## 实际身份改动

四条共同结果枝每枝只有两次真正 COMMIT，均在 feeding_001201_001906：

| 全局 q | 实际改变 | first-public 另一 source | sealed 对应参照 |
|---:|---|---|---|
| F1239 | native167 → public136 | native128 → public128 | CORRECT |
| F1745 | native190 → public188 | native9 → public9 | CORRECT |

两次改变均属于共同 geometry/H0 机制，raw 与 v2 没有独立多恢复一个身份。每枝另有17次 local fallback，0次 RESOLVE_NO_ID_CHANGE。19个首分离 q 的 first-public 参照为11 CORRECT、4 WRONG、4不可评分；另外4个 NO_SPLIT、7个 UNCONFIRMED 全部保留。

PERMUTE 还在 F519 提交 50↔24、F1027 提交 137↔95，两次均被封存参照判 WRONG；它仍包含上述两个共同正确 COMMIT。错配对照实际产生扰动和负作用，证明这次控制有效且模型会对错误对应敏感；**不能据此声称真实深度对 geometry 有正增量**，因为真实深度与 geometry/ZERO 输出完全相同。

CORRECT/WRONG 引用 EVENT_AUDIT 已封存的 RGB 多边形身份对应及真实 bank anchors。它们不是鱼体表面像素 GT，也不是物理深度 mm 真值。本审查不发布 GT 身份编号，不用参照选择像素或修改门槛。

## 固定目标判定

| 分支 | IDF1 | HOTA | AssA | IDSW |
|---|---:|---:|---:|---:|
| SAM3_NATIVE | 80.97675951 | 79.96405590 | 71.53049876 | 108 |
| J0_GEOMETRY | 80.97675951 | 80.01204932 | 71.61576345 | 106 |
| J1_RAW_DEPTH | 80.97675951 | 80.01204932 | 71.61576345 | 106 |
| J2_RESTORED_DEPTH | 80.97675951 | 80.01204932 | 71.61576345 | 106 |
| J2_DEPTH_ZERO | 80.97675951 | 80.01204932 | 71.61576345 | 106 |
| J2_DEPTH_PERMUTE | 80.70304382 | 79.68908486 | 71.04491529 | 110 |

raw/v2 相对 native：IDF1变化0，HOTA +0.04799342，AssA +0.08526469，IDSW -2。相对同一 geometry 或 ZERO 的全部这些指标变化均0；raw 与 v2 互相也为0。FP=487、FN=985，六枝相同。

固定目标要求真实深度枝同时提高 native 的 IDF1/HOTA/AssA 且 IDSW不增；IDF1没有提高，因此 frozen_support_rule_met=false 是正确判定。可报告共同几何机制的两次正确接回、HOTA/AssA小幅提高与2次 IDSW减少；不能报告“深度已超过同源native”或“补全深度改善跟踪”。PERMUTE 的负结果也不能代替真实深度相对 ZERO 的增量。

## 初次 strict compare STOP 与追加工程精度评分

初次冻结 evaluate 的执行 exit=1，止于 DS9/DS8 提取对象整字典精确等式；这次最初 strict comparison **未 PASS**。其日志和原 evaluate 均保留且由 FLOAT_SCORE_ADAPTER_FROZEN 绑定。预测、研究代码、阈值、数据源和真值没有被修改。

独立 SOURCE_FLOAT_AUDIT 覆盖全部1471帧、39208对象，唯一281处差异是 `roi_geometry.pieces[].dt_max_px`：adaptive_raw138处、restored143处。所有其他 typed structure、selected/area/n/median/actualMAD/adapterMAD/cohort/资格/背景/来源事实完全一致。不是用普遍数值容差放过测量差异。

本次额外用标准库 float32 pack/bit 比较独立验证281处全部为 exact float32 的相邻可表示值，bit距离=1；值域6.08276224–7.81025028px，最大绝对差4.76837158e-7px，均使真实 ROI threshold clamp为3px。ROI面积、component samples 与全部操作性字段精确相同。

只读 adapter 在 deep copy 中把这些已认证非操作性诊断 metadata 对齐到旧值，再要求整字典严格相等。它只替换原 scorer 的 source extraction 比较函数；原研究代码和官方 scoring 真值/预测不变。随后原 scorer 完成、adapter exit=0，SCORING_SEALED 和 APPENDED_SCORE_PROVENANCE_SEALED 完整绑定原失败、例外条件、独立 diff、接受清单与正式评分。因此这应报告为 **postseal 工程精度例外后评分完成**，不能称初次 strict check 成功。

静态一般化边界：adapter 的 max(spacing(x),spacing(y)) 谓词在float32的2次幂附近不能单独作为普适“最多相邻1ULP”的证明。当前281处均在上述6.08–7.81区间且有独立bit相邻证明，**本轮没有2ULP被接受的事实**。此限制只是未来复用规则的适用范围；不改变本次已认证结果，也不修改冻结 adapter 或增加试验。

## 解释边界

v2仍是保存的 RGB/未来支持离线诊断来源，不是新因果补全。native/v2 的真实表面归属、标定物理精度和深度误差仍 UNKNOWN。inferred 实测 MAD 与60/1.4826噪声适配代理保持不同含义。normalized联合后验也只在固定的候选、先验、`.9/.1`与条件独立模型下成立；log9是对 runner-up，不是对所有替代合计，也不是认证的90%身份正确概率。

Python访问日志及源哈希没有越界的证据，冻结 reader 仍只取当前行；Python audit 本身不覆盖所有原生HDF5底层访问。1471帧已经曝光，同一录像的结果是开发机制证据；本轮没有独立录像、因果深度、训练或SAM3前端端到端运行。单次CPU回放耗时不能称SAM3端到端实时性能。

本固定版本到此结束；下一步仅由主报告统一记录既定的唯一计划，本审查不另开研究线路。

## 关键 seal / 审查摘要 SHA

| 文件 | SHA-256 |
|---|---|
| run/ALL_PREDICTIONS_SEALED.json | 4f7d545df4a6eaae9d46ddd0ff683978cd42fce4af3e0315c9c74c14ebb4cf33 |
| run/ACCESS_SEALED.json | 3ea122935c182ee6ff60c607d6aafdc6e5efffd3b43a08e3f75a77965b26be5b |
| run/SCORING_SEALED.json | ab8bf81c8f3200c81f8227af79c06cf0ece34b55995af36204bf4e9e181a2675 |
| APPENDED_SCORE_PROVENANCE_SEALED.json | 241a53ac6768faddda8e3bfd61a1d7c3d599898cfaf0e3ab8e10256e0a643222 |
| run/METRICS.json | da5059355b891c6162324e9e3d485f5e674fe2e4ca2e05ad93875179fdd6b533 |
| run/VERIFICATION.json | a412a35d10d4366cc979bb49dcf5a284af7ed3ab552b043fcf54b163d0e229fa |
| run/EVENT_AUDIT.json | e988caf3ec8fe5363a395d1271b16724fa46a0b61928266831481369098d2ef5 |
| SOURCE_FLOAT_AUDIT.json | de56783cc06c1e004fe275e9525664ca8a3443de3ff82af86318170c8e979ea1 |
| FLOAT_SCORE_ADAPTER_FROZEN.json | cecf16f7e77046e0542fe27ef7ecd496b213a102253737ba20185312591997a1 |
| FLOAT_SCORE_ADAPTER_ACCEPTANCE.json | e95c6adce494dcab05a73a349a8dc32dd552f5d513d0df15d140165fbd0dd487 |
| PREFLIGHT_REVIEW.md | c38335e9e20ab47bfd70832fd70b88cbc793ef9222a655a142507f5cb33d2d60 |
