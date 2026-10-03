# DS19 局部 return 控制流与贡献边界复核

本文件仅基于真实源码、调用关系和输入合同复核。未读 GT、旧指标或本轮预测结果来调整选择，未运行正式回放、评分或模型服务。四段实际来源前缀由主执行任务独立运行；本文不预判其动作、正确性或收益。

核验 `controller.py`：32,583 字节，SHA256 `420aad60656d9084f7c7281c597d5039490a9f0aa3b221f02e855904b7241538`。旧 DS18 代码仅导入和复用，不修改。后续若源码变化，必须另记版本并重做绑定验收，不能沿用本摘要作为新版本证据。

## 1. 实際候选来自原控制流

`EventReturn.step` 调用冻结的 DS16 `EventReturn.step`，其真实 MRO 仍经过 StableReturn、QualityBirth、NativePrior、DS18 PendingBirth 与原 D1/Birth。没有在 manager 中根据期望 public ID 造候选，也没有以低代价代替 Hungarian 选择或原确认。

`EventBridge.preview` 保留普通 DS18 基线 clone；另外从同一帧前本分支 engine 克隆 proposal。只有 proposal 的 `edge_veto` 可将 `WAIT_JOINT_GROUP_TRANSACTION` 改为事件局部路由，其他原匿名、量测、来源、精确历史引用与 partner 门全部保留。两份 clone 均只推进当前帧一次，stage 不再调用 `step`。

实际资格子范围是：active event 中尚未恢复的公共成员；当前候选有合法当前测量和可验证 source version、来源独占、无当前 neighbors、质量合格；本帧不等于真实首分离 q；原矩阵、dummy、时限、深度代价、运动代价、margin 与确认自然通过。原事件成员、suppressed、GROUP、POST 或残片匿名角色仍不能直接作为 return 身份候选。

D1 沿用真实 `D_balanced`：5 次确认，depth scoring 使用最后一次 clean whole 深度，`smooth=False`；EMA 仍记录但不是 D1 的实际打分 z。原 source 出生 6 秒窗及 first_eligible 后 3 秒窗不延长，pending 连续条件仍是 .2 秒间隔/.5 秒确认跨度。Birth 保留其原单次匹配、whole/core、survivor 与 margin 门。当前无 neighbors 的局部 return 子范围，使 Birth 的 local 集合为空、historical active 伙伴被排除；其余 dormant 伙伴不能构成原 verified survivor，NativePrior 也没有 active partner 可恢复该条件。因此本轮局部身份出口实质限于 D1，不能宣称完整 Birth 出口已修复，更不能为了命中删去 `no_verified_local_survivor` 或邻居门。

## 2. 未 accepted 确认与身份提交分开

proposal 自然选中但未达到原确认时，仅在组外状态相等的情况下，把该 source 的原 `pending` 确认记录带入普通基线 clone。没有携带 alias、bank、view、clean 或身份认证，`identity_writes_before_stage=False`。source generation、旧 anchor 或 event generation 改变先切断这段确认；真实首次出生和 first_eligible 时间保持原值。

因此 `carried_original_confirmations` 是候选确认进度，既不是 return 事务，也不是恢复成功。只有 `stage_event_return` 返回新事务且唯一 `commit_once` 实际采用该事务后，才记录身份提交。stage 拒绝时保留普通基线状态，不能把潜在 proposal accepted 当作已发布结果。

## 3. 原子 stage 的真实写集

stage 重新检查 bridge version、event generation、未恢复 target、非匿名 source、当前 source/identity version、原 accepted 事实、当前量测绑定、精确旧 clean anchor、旧 view、不可变进入参考、公共占用与 latent alias 声明。`wanted` 必须与 proposal 实际 mapping 一致且全帧 public 一对一。

组外比对包含 mapping、bank/view、深度历史绑定/EMA 来源表、alias、出生、pending、native_seen、native_runs、recent_core、两种 quarantine、first_eligible、pending_birth、source_activity、retired 与不可变进入 registry。只在这些实际状态一致后，将本事件成功 source 的 native 键写集和目标 public 键写集移植到普通基线 clone。

native 数字与 public bank 数字分别处理。源 bank 只在它确是该 source 当前公开 bank、且没有组外当前或 latent alias 占用时可退休；不能仅按整数相同删除预留目标或无关 bank。stage 无整套 B0 engine/previous/provenance/epoch 复制。

proposal 中自然 accepted 的目标保留原 loop 当帧真实 clean/view 输出，其他未恢复成员继续冻结。没有在 DS18 恢复旧 clean 后人工拼出速度、深度或锚点。进入前 registry 始终保留原两个成员参考；live 参考的合法推进和不可变进入参考分列。commit 后真实 mapping/epoch 一次生效，并由原参考登记链重新绑定实际来源。

## 4. 持续 group、晚 q 与 timeout

engine 持久记录 `event_returns`，manager 成功后同步 `returned_members` 与 `returned_sources`。冻结 manager 每帧重建保护 spec 时，私有 step clone 先按已提交记录裁剪：只保护尚未恢复的旧 public/member source。原 source/reference 与触发规则不改。

返回 source 在当前帧/后续帧若仍是独立 SOURCE，按新实际映射与 epoch 继续记录；如果后来实际成为 GROUP/residual/POST，匿名风险类别仍生效，它的 live clean 暂停更新，不因为有 returned 记录就认证 group 深度。不存在永久 public ID 锁：原 native-return 冲突/隔离生命周期仍运行。

真实晚 q 仍由原掩码几何规则产生；不 fake q、不提前读取后续帧。q 的当前 POST 量测保持原 `IDENTITY_UNASSIGNED` 输入合同，历史已提交 alias 与 public bank 则继续保留。joint 事务只能保持本事件此前合法 return 的 source→public 对应，并核对实际 source version/所有权；不一致时拒绝联合完成并采用本分支自身 fallback。source generation 或 alias 后续合法变化不能被旧 returned 记录强行改回。

timeout 仅释放剩余事件保护、清理尚待决证据。先前实际提交的 alias/live bank 与组外修复不回滚；返回 source 若此时仍承担真实 group，其风险类别保留，不能在超时帧认证为 clean 个体。

## 5. 记录字段与独立评分

- `trace.ds19_event_return_proposals`：真实路由门、原 accepted 潜在候选、未 accepted 确认运输；不计身份成功。
- `transaction.return_record`：stage 状态、event/generation/frame/q、`restored_sources`、selected、剩余 public、native/public 写集、组外检查与原 proposal 事实。
- `trace.ds19_event_local_return`：唯一 commit 后转为 `EVENT_LOCAL_RETURN_COMMITTED`，追加实际 mapping、epoch、bridge version、实际首次 source 发布；这是评分读取的提交记录。
- `episode.returned_members/returned_sources`：旧 anchor、真实 source version、当时 identity version、原 candidate、首次 source 发布与提交时刻；保存历史事实，不当作永远正确的身份真值。
- 原 candidate 保留 `association_evidence_bindings` 及 hash、旧真实参考、D1/Birth 来源、matrix 代价/margin、原确认与时限；额外 accepted 记录不能缺失对应来源链。

LOCAL_RETURN 独立物理审计；其原 accepted reconnect 在 automatic 汇总中标记被显式事务采用，不能再算一次 automatic gain。首次公开的是 native 新号后再恢复，必须报告真实延迟，不能称出生首发即恢复；此前已发布帧不改写。

公共 ID 的源起始标签、实际旧 bank 物理对应、当前 return 物理对应，以及最终 IDF1/HOTA/AssA/IDSW 应分别报告。UNKNOWN/不可评分不算正确，source/mask 不重复不证明物理单鱼。组外状态相等和工程单测也不证明深度有效。

## 6. 主效应边界

ACTIVITY_RETURN−ACTIVITY_ORDER 与 MIXED_RETURN−MIXED_ORDER 是同一个共享身份出口修复效果，包含后续各分支真实状态传播。追回原 Z4Q 收益只能称止损。

MIXED_RETURN−ACTIVITY_RETURN 才是在修复后共同底座上的组合深度策略差值；既包含深度来源/质量/混层准入，也包含分支状态传播，不是纯粹深度标量或上下顺序的局部因果效应。新增模块不改既有顺序符号门、权重、q 或 core，也不能将共同事务收益记为新增 depth 独有提点。

未命中、全部拒绝、仅确认无提交、前缀正确但整段降分，均是允许且必须交付的真实结果。必要工程检查通过后应完成一次冻结全段；不得按 GT 或指标回调候选、时间窗、路由门或深度参数直至命中。
