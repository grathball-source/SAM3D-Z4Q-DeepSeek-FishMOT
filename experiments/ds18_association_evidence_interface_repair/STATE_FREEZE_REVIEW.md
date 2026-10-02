# DS18 状态与正式冻结独立审查

**已覆盖的状态隔离、原子发布和来源合同检查通过；整体身份关联语义及跟踪性能仍未判定。** 当前正式全段正在运行，本审查没有读取任何未封存的正式预测、事务、指标、GT raster 或 RGB。

审查记录时间（UTC）：2026-10-02T17:11:40.721797+00:00。这是冻结之后追加的交付审计；没有修改冻结代码、配置或旧封存。

## 1. 当前冻结与最终测试的对应关系

独立逐字节计算全部八份正式 FREEZE 中的 code_sha256。每段列入 107 项源码、配置和预冻结证据，全部与当前磁盘一致；未发现缺文件或哈希漂移。八段合计 20,098 帧，六分支固定为 SAM3_NATIVE、Z4Q_FROZEN、DS16_ORDER、ACTIVITY_ORDER、MIXED_ORDER、MIXED_OFF。

| 关键文件 | 字节 | SHA256 |
|---|---:|---|
| controller.py | 42385 | `966ddf22e4ac41fccd3105b1d49036c666ee0a0de074541152c126c2e96c3d1a` |
| mixed_depth.py | 16681 | `12b7564afb69690dd85be60c2af88744c784e97d62ad5dcbacbb9c2458abfbb7` |
| test_controller.py | 17122 | `05b59e50a8f31f017a77f2d98c117b755745bf7da3909f0d6d8e03029e32e7bb` |

[CHECKS_R5.json](E:/CAU/SAM3D-Z4Q-DeepSeek-FishMOT/experiments/ds18_association_evidence_interface_repair/CHECKS_R5.json)：36 项测试，0 failures、0 errors，GT_read=false、model_http=0、cost_usd=0。其 actual_test_sources 的全部实际测试源哈希独立核对当前文件，并与八份正式 FREEZE 的哈希逐项一致。这里没有重新运行这些测试。

| 正式段 | 帧数 | FREEZE SHA256 |
|---|---:|---|
| feeding_000000_000199 | 200 | `2d4a940173e200ecf70846d19762c91faad86c47e1ce8cde5fdbd5a329e44e08` |
| feeding_000351_000555 | 205 | `822d0f337c12c573846256d2f57e7ab87592292169c1f55e5532a2f85ad4cde3` |
| feeding_000701_001060 | 360 | `950537baf39930c347373c0b75989cba269ee5b566cf15441db55f325737d0bf` |
| feeding_001201_001906 | 706 | `d0e4839c3bd23d79d473e2fbfa3aa1a546121d54e082e6d523d720e274fd9f97` |
| fishsa_development_8400 | 8400 | `9943bd80c45a20a07d6d5ce1f6193d8d44e9e1d735775478c5e8cb875155a797` |
| fishsa_validation_2888 | 2888 | `ae1e2cd71556c42d576492667eb2e8cfe9436a1e4955c0558b66c9ef871676a7` |
| L3 | 3710 | `9fc88112397548821c3a7ff42fe93138c705ef2a0b44a084a0f7bae786e7b57f` |
| LW | 3629 | `b420294dfff03e760e89c3adf10a831d750aaf503de4b7276804a3613b65b711` |

## 2. 匿名身份、当前测量与认证参考

controller.current_binding 按实际 role、同 ROI 原标量、当前 source_version、identity_version 与 frame 验证。identity_state 为 UNASSIGNED 不等于 measurement_valid=false；合格的当前测量保留用于比较，不能由它直接认证身份。MIXED 分支额外使用同 ROI 的 screened_eligible；ACTIVITY 不额外套用混层筛选。

GROUP/POST_UNASSIGNED/残片与 unresolved event sources 的 clean bank fields、view_bank 和 recent_core 参考继续冻结。实际观测的 last_seen、last_frame、partners、contact_time 与 source continuity 仍由原生命周期更新；没有观测的 member 不补写时间。历史查询绑定真实旧 anchor 的 source/frame/token/版本，不按 public 整数继承证书。

自动 Birth/D1 候选入矩阵之前，匿名当前 source 对任何目标都禁止单边身份写入；受保护旧 target 必须 WAIT_JOINT_GROUP_TRANSACTION。匿名 POST 也不能作为事件外 Birth 的个体 survivor 或 D1 reservation。只给原子双 post bijection stage 开放事件身份认证，不能先写错误 alias/bank 再仅修输出。

Birth 的 target、纳入 partner/survivor 与 motion 合格 competitor 的 required whole 缺测为 UNKNOWN_NO_COMMIT，保留 dummy 和其他完整候选；已测 whole 反证保持原规则。S0 whole 标为 NOT_USED，core 缺测用共同无信息模型。没有把测量 UNKNOWN 或身份 UNKNOWN 改成零代价优待。

## 3. Pending Birth 时间与候选语义

真实 Birth 表仍由原 DepthRepair 在 source 初次实际出现时记录，不删除或重置它来伪造新出生。pending 保留 original_birth_frame/time；重评沿用原 6 秒窗口与既有 first_eligible 的 3 秒限制。source generation 改变、事件 generation 不兼容或过期会退休；退休提案不复活。

pending targets 仅在 first_proposal_frame 记录初始合法旧参考；后续出现的新 target 或新 anchor 不会自动加入。重评与首次出生分开计数：birth_counts.births 只增真实新 source，pending_evaluations 记录重评。合法重接输出显式 BIRTH_REFINE、original_birth_frame、evaluation_frame、public_at_frame、source_previously_published 与 actual_first_source_publication，不把 q 之后重接伪称首帧从未发布。

单元检查覆盖 protected q 保留有效 scalar、拒绝单边 alias、保留 pending 和原 birth、来源版本变化拒绝、固定候选不扩张，以及局部释放后在原时间窗内真实 Birth 重评。该合成例验证事务合同，不要求真实 F3902 或 F11488 必须恢复旧动作。

## 4. 联合 stage、唯一发布与局部回退

继承的 _stage_episode 逐一比较 immutable clean snapshot、view provenance、episode generation、q 与 bridge version。stage_group_restore 使用原两源到两旧 public 的 bijection、当前真实 mask、occupancy 与原子事务；选定以后才认证当前 q 参考、绑定实际 mapping/epoch。当前 R5 直接覆盖联合 stage 成功、组外状态保留、同一 view 不能重复 commit/publish，以及来源/锚点篡改和 pending source generation 变化拒绝。stale episode、occupancy 等沿用实现具有显式守卫，本轮最终测试未单独穷尽这些组合，不能将源码检查冒称每个拒绝分支均已执行。

local_fallback 只采用本分支当前 causal preview，移除本事件保护；不复制 B0 的 engine、previous、provenance、epochs，也不第二次 step 改出另一个首发映射。组外 alias/bank 与先前本分支状态保留；pending 与未认证 q 来源也保留。失败不需要吞掉 mask 或改写已发布历史。

readonly 优化仅共享已验证测量证书与历史事实值。外层事实 map、bank/view_bank、alias、pending、source_versions、identity_versions 等仍按标准 deepcopy 克隆。普通 mutation 被拒绝；测试用 JSON 可写副本替换事实记录仍能检查非法来源和签名。它不是抵御同进程恶意 Python base-class builtin 调用的安全边界。

## 5. 真实前缀与优化版本的证据关系

[REAL_SLICE_CHECKS.json](E:/CAU/SAM3D-Z4Q-DeepSeek-FishMOT/experiments/ds18_association_evidence_interface_repair/REAL_SLICE_CHECKS.json) 记录五个预指定真实前缀，共 9,619 帧：开发至 local/global3902、验证至 local2188/global11488、Feeding 首段至191/global190、Feeding1201–1906段至274/global1474、LW至3064/global3063。均保留同源 native/original Z4Q parity、全部 mask 与一对一发布；不按 GT 指定正确映射。

[REAL_SLICE_SOURCE_SCORER.json](E:/CAU/SAM3D-Z4Q-DeepSeek-FishMOT/experiments/ds18_association_evidence_interface_repair/REAL_SLICE_SOURCE_SCORER.json) 独立回查 actual accepted D1/Birth 的当前和真实过去测量、实际 whole last15 与 EMA/partner EMA 全部贡献。五段自动来源合同分别通过；开发/验证各3、Feeding两前缀5/16、LW100个 accepted action 是新三分支合计的预冻结来源检查计数，**不是独立事件数、正式结果或正确恢复数**。全部相关报告明确 GT_read=false。

四个较早完成的长前缀使用 readonly certificate 版本，LW 因存储性能在冻结前改为最终 readonly record 版本重跑；停止、非零退出和存储重启有独立记录，没有把旧失败隐藏成一次成功。ACCESS 是数据读取记录，不包含完整 loaded-code 运行哈希，因此不能声称五个长前缀都独立执行了最终 byte-identical 模块。

最终存储优化的边界由 [IMMUTABLE_RECORD_EQUIVALENCE.json](E:/CAU/SAM3D-Z4Q-DeepSeek-FishMOT/experiments/ds18_association_evidence_interface_repair/IMMUTABLE_RECORD_EQUIVALENCE.json) 给出：开发、Feeding、L3 各50帧，共150真实帧，对所有科学行与 canonical JSON逐字节相等，并独立检查 mutable clone、untrusted JSON 与原始测量。它证明已覆盖帧的等价，不能扩大为五个长前缀或全段的穷尽证明。最终R5测试直接绑定当前 controller/measurement SHA。

[SCORER_CONTRACT_FINAL_CHECKS.json](E:/CAU/SAM3D-Z4Q-DeepSeek-FishMOT/experiments/ds18_association_evidence_interface_repair/SCORER_CONTRACT_FINAL_CHECKS.json) 区分 bank 物理参考与 public-origin 既有错号；当前 frozen score.py SHA `b0d14f4c89fde39544e992896445b85268238d9dd50dde1910a2cf19e0680a29`。prefix 源核验报告保存其 completion disk SHA，最终 source-verifier AST 未改变；该报告没有冒称覆盖当时未使用的整个 GT grading 模块。正式结果只用当前冻结整模块在预测封存后评分。

## 6. 交付边界

当前状态/来源证据足以支持按本冻结规格继续完成实验。不能由工程 PASS 推出深度提点、正确身份恢复、相对原 Z4Q 提升、完整数据集泛化或真实部署实时性。完整实验尚需逐段退出成功、完整预测/事务封存、来源评分与统一 GT 后评分、结果报告和远端 main 核验。

本审查没有新增推理 HTTP、训练、SAM3 推理、补全服务或费用。没有查看正式 run 下的 predictions/TRANSACTIONS/metrics，仅核对正式 FREEZE metadata 与已有预冻结证据。

## 证据文件摘要

| 已有证据 | SHA256 |
|---|---|
| CHECKS_R5.json | `b1e4986644b894e410f16e2cb90413da6af8e8042f8cfa9d9ce9a0a1322fd1e9` |
| IMMUTABLE_RECORD_EQUIVALENCE.json | `1bbefca870c0bdf6919f5407f45fe656307651c832e97ae9b27096897f4c7942` |
| IMMUTABLE_RECORDS_REVIEW.json | `2d7ecefaa6da23644b8141aed347bcf4b41aac522210cfdd213181d083075eb7` |
| REAL_SLICE_CHECKS.json | `1fd6df185390f118827aeedfdeba4c683e622a51a889466f84a2e106ba83cee2` |
| REAL_SLICE_SOURCE_SCORER.json | `37bebf5eb56174d612f27464fc46acac337818108e2f90f11d36dd8ec3d5555f` |
| SCORER_CONTRACT_FINAL_CHECKS.json | `00ab45e31bbe19f4784598fe44c44d7dd56304ddf658ab654419a367745d29de` |
| EVALUATION_MASK_INVARIANT_CHECK.json | `b961990eb4e9e5e8ec943ac1a8490955bceff052f9ab619e575884e4fbdccff6` |
| IMMUTABLE_RECORD_PROFILE.json | `39c357218df4840826b9b5a55c89554b5f2de02ff71791927b25340d76d3f441` |
