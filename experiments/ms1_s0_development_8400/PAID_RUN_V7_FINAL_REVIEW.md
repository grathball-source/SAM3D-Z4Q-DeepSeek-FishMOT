# MS1-S0 开发集 V7 真实调用与 8400 帧恢复回放

## 判定与边界

**工程输入及逐帧恢复回放完成；原始同步运行在第 16 个推理 START 后中断，结果未知；当前冻结版本没有可观察的 VLM 增量。** 这是已曝光开发集的事件级试验，不是盲测，也不是完整的 8/8 模型能力判定。不得把 F5927 的未知结果写成 `DEFER`、错误或正确；不得补发原请求或把本轮无增量外推为完整事件历史关联无效。

预测驱动 V4 扫描在开发集找出 15 个疑似点，真实运行启动 13 个事件，9 个出现首个分离帧 q。确认顺序最早的 8 个固定事件被选中，包含用户指出的 ID 1/7 交互 F5927（合并确认 F5928，首分离 F5939）。事件选择、锚点、q 和图像只用预测掩码、来源、历史和深度，不用 GT。M 只生成可推翻的假设；S0 仅有首分离帧的 X/Y 单点 post，post 速度为 UNKNOWN。M/S0 图像是原预测 mask 的匿名几何图，无原始 RGB 纹理。

## 原始调用与恢复路径

2026-09-28 20:14:40 +08:00，在第一次请求前写出 [FREEZE.json](run_development_v7_paid/public/FREEZE.json)，绑定代码、输入、8 个事件、预算策略及评分门槛。20:14:48 开始正式调用。官方 `deepseek-flash` 通过 Files API 上传 81 张几何 PNG（720,475 字节），随后有 **16 个推理 START、15 个完整 END、0 次重试、0 次 smoke**。8 个 M 均返回；7 个 S0 返回并解析；F5927-S0 于 20:27:16 写下 START 后原进程退出，没有 END、原始响应或公开响应。它的服务端是否收到或计费无法确认，记作 **open START / HTTP 结果未知**，未伪造 END。[INTERRUPTION_RECORD.json](run_development_v7_paid/public/INTERRUPTION_RECORD.json)与原 [CALL_LEDGER.jsonl](run_development_v7_paid/public/CALL_LEDGER.jsonl)保留这一状态。原运行只发布到 F5914，未生成预测 seal，不能对它单独评分。进程退出根因没有错误栈，不能从现有证据确定。

为保留已获授权的真实返回、且不重复调用，[replay_v7_recovery.py](replay_v7_recovery.py)从冻结源重新运行三个独立状态分支，按顺序逐字节校验 16 个原请求包、原 START body 哈希、15 个 response/raw 哈希；前 15 次使用原始模型内容，最后一次保持未知并执行冻结的数值/B0 局部回退。恢复过程**新增推理 HTTP 为 0**。它写出独立 [RECOVERY_PROVENANCE.json](run_development_v7_recovery/public/RECOVERY_PROVENANCE.json)和 [PREDICTIONS_SEALED.json](run_development_v7_recovery/public/PREDICTIONS_SEALED.json)，未覆盖原目录。恢复预测与原运行中断前已首次发布的 **5914/5914 帧**逐行哈希和事件发布映射一致，见 [RECOVERY_PREFIX_CHECK.json](run_development_v7_recovery/public/RECOVERY_PREFIX_CHECK.json)。这证明恢复前缀忠实；F5915–F8400 属于按相同状态机、已收响应及未知回退完成的离线恢复，不能称为不中断的在线同步运行。

15 个已返回推理合计输入 1,142,733 token、输出 133,371 token；按官方峰值费率且不扣缓存计算的已知上界为 **USD 0.5028651**。为未知的最后 START 再按单槽峰值预留 USD 0.3786432，总保守上界 **USD 0.8815083**；这不是账单或已证实收费。15 个返回的推理等待累计 692.625 秒，中位 31.828 秒；F5927-S0 没有可报告的响应时延。[官方 Files 文档](https://api-docs.deepseek.com/guides/files_api/)与[官方定价页](https://api-docs.deepseek.com/quick_start/pricing/)是路由和费率依据。

## 封存后整段指标

评分先验证 8400 帧预测、逐帧首次发布、来源哈希和 seal，然后读取 GT，沿用原 TrackEval 和归档 B0 校验。原 B0 完整指标精确复现。数值为百分数；括号内是相对 B0 变化。

| 分支 | IDF1 | HOTA | AssA | IDSW | FP / FN |
| --- | ---: | ---: | ---: | ---: | ---: |
| B0 原 Z4Q | 99.333472 | 77.829488 | 77.907638 | 6 | 194 / 323 |
| B-HOLD-S0 | 99.317579 (−0.015893) | 77.848487 (+0.018999) | 77.947244 (+0.039606) | 18 (+12) | 194 / 323 |
| B-VLM-S0 恢复回放 | 99.317579 (−0.015893) | 77.848487 (+0.018999) | 77.947244 (+0.039606) | 18 (+12) | 194 / 323 |

HOLD/VLM 相对 B0 均有 233 帧公开 ID 输出变化，VLM 相对 HOLD 为 **0 帧**，全部整段指标差为 0。共同的 HOTA/AssA 微幅变化来自身份保护和数值/回退机制，不能算 VLM 独有收益；IDF1 略降、IDSW 明显增加，也不能以 HOTA 单项微涨宣称提点。见 [METRICS.json](run_development_v7_recovery/public/METRICS.json)。

## 八个固定事件

“参考”按事后 GT 查进入前实际末端锚点；“连续共识”要求同版本连续片段至少三个已知 GT 观测。不可评分保持不可评分，不挑容易事件。数值和模型选择同一历史。`RESOLVE_NO_ID_CHANGE` 指模型 stage 没有额外 public bank 改号；保护机制仍可能相对 B0 改输出。

| 事件 | q | S0 原始选择 | 数值选择 | 模型额外状态动作 | 原始选择的末端参考 / 连续共识 |
| --- | ---: | --- | --- | --- | --- |
| F1152 | 1274 | H2 | H2 | 无改号 | 正确 / 不可评分 |
| F3078 | 3081 | H1 | H1 | 无改号 | 正确 / 正确 |
| F3863 | 3902 | H2 | H2 | 无改号 | 正确 / 正确 |
| F4057 | 4071 | H2 | H2 | 无改号 | 正确 / 不可评分 |
| F4485 | 4501 | H1 | H1 | 无改号 | 正确 / 正确 |
| F4519 | 4524 | H2 | 未解决 | 内部 COMMIT，public bank 变化 `7→0, 1→1`；首帧及整段公开预测与 HOLD 相同 | 不可评分 / 不可评分 |
| F5399 | 5436 | H2 | H2 | 无改号 | 正确 / 不可评分 |
| F5927 | 5939 | **未知，无返回** | 未解决 | 局部回退同帧 B0 状态，首帧 X/Y 公共 ID 为 0/1 | 不可评分 / 不可评分 |

因此，**7 个有返回的 S0 中**，6 个按末端参考可评分且均正确，1 个不可评分；连续共识只有 3 个可评分且均正确，4 个不可评分。没有观察到模型带来的公开 ID 或指标增量；同时，F4519 的内部提交缺少可评分的物理身份参考，不能把它当作成功恢复。F5927 的末端 B 参考缺失且 S0 结果未知，更不能借模型选择推断。模型原始选择、CALL 状态、数值回退与事后核验详见 [MODEL_EVENT_AUDIT.json](run_development_v7_recovery/public/MODEL_EVENT_AUDIT.json)和 [PHYSICAL_EVENT_AUDIT.json](run_development_v7_recovery/public/PHYSICAL_EVENT_AUDIT.json)。

## 验收、保密与复现

- 冻结前 16 个离线控制包通过截止帧、事实引用、图像和输入上界检查：[PREFLIGHT_V7.json](PREFLIGHT_V7.json)。原 V6 的完整测试报告仍为 `PASS`；本轮试图重跑该一次性测试脚本时，因其 `TEST_REPORT.json` 已存在而按防覆盖断言退出，没有修改旧报告。恢复新增的 5914 帧前缀检验通过，原封存代码和来源哈希由恢复程序核对。评分验证归档 B0 全指标精确一致。
- 原 16 个请求公开包、15 个安全化响应、Files 上传摘要与推理账本在 `run_development_v7_paid/public/`；完整恢复预测、事务、首帧发布、seal、指标和两级事件核验在 `run_development_v7_recovery/public/`。两组公开记录均需一起读取，不能把恢复 seal 误认为原同步运行的 seal。
- 真实 source/native 对应表、图像、原始 API body/response、provider file ID、GT raster 均留本机。受限产物的**真实绝对路径、字节数、SHA256**和复现依赖逐项列在 [RESTRICTED_INVENTORY_V7.json](RESTRICTED_INVENTORY_V7.json)，共 333 项；Git 不含受限像素、凭据或私有 wire。
- 在具有清单中同 SHA 输入和受限 API 记录的新工作目录中，以同一 Python 环境运行 `replay_v7_recovery.py real`、`verify_recovery_v7.py`、`score.full('run_development_v7_recovery')`、`postseal_event.run('run_development_v7_recovery')`、`model_event_audit_v7_recovery.py`。各输出独占新建，已存在时拒绝覆盖。原 `replay_v7.py real` 会重新发起请求，**不得用于复现本轮**。

## 下一步

停止对这八个已曝光事件追加请求或按结果改 prompt。下一次独立试验若要证明模型增量，应预先固定可评分的物理参考与触发集合，保留数值同信息对照，并在新的未曝光事件上验收；本报告不自动启动该试验。
