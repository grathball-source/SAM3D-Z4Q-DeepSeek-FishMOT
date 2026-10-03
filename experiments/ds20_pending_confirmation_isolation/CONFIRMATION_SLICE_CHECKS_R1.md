# DS20 真实确认隔离切片

只读三个实际源前缀，不读 GT、metrics、RGB，不重新关联，不手工认证观测。

判定：**FAIL**。六列保留全部原 mask 与唯一公开 ID；四归档列逐帧精确复现 DS19。

检查 8380 条隔离分支记录：普通确认自然推进；私有事件 proposal 前后普通 pending 一致。

## feeding_000000_000199 / source38

保护候选 target16 与普通 target7分别存储。普通自然提交 local195；
与冻结无局部返回控制的确认时刻一致=True；实际公开 mapping/alias 一致=True。

提交后旧事件确认依实际 source/identity/alias 状态失效；各个精确语义键、计数、原因及首次发布可逐帧回查 JSON。物理正确性尚未评分。

## LW / source32

保护候选 target7 与普通 target24分别存储。普通自然提交 local952；
与冻结无局部返回控制的确认时刻一致=True；实际公开 mapping/alias 一致=True。

提交后旧事件确认依实际 source/identity/alias 状态失效；各个精确语义键、计数、原因及首次发布可逐帧回查 JSON。物理正确性尚未评分。

## L3 / ACTIVITY_ISOLATED

local3025 / original3024自然返回，原候选确认数=[5]。
真实 stage/commit 后更新当前 bank，首次本帧发布并下一帧继续自身 alias；匹配归档原自然返回。不是物理正确率或深度提点。

## L3 / MIXED_ISOLATED

local3025 / original3024自然返回，原候选确认数=[5]。
真实 stage/commit 后更新当前 bank，首次本帧发布并下一帧继续自身 alias；匹配归档原自然返回。不是物理正确率或深度提点。

## 边界

本检查是源、状态与发布回归，不是模型或科研资格筛选。prefix 不是完整正式段的 seal；后续正式冻结与全段评分单列。

失败详情数量：2。
