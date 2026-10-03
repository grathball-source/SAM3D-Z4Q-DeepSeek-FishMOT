# DS19 真实 L3 前缀：source→proposal→stage→首次发布复核

只读已完成的 local1–3030 / original0–3029 前缀。未读 GT、metrics、RGB 或物理评分，未改源码或重跑预测。

发布链检查：**PASS**；完整 3030 帧、6 列发布与原始 source/cache/ledger 绑定通过。

实际局部提交记录：2 个 source（不同分支分别计），不是物理正确率。

## ACTIVITY_RETURN / MS1-F2873

原 D1_DELAYED 自然 5 次确认；local3025 / original3024 实际提交 source47→public9。

确认进度：local3021 count1, local3022 count2, local3023 count3, local3024 count4；最后确认由自然 accepted 原事件记录绑定。

source 首次实际发布 local2891 / original2890，public47；此前已公开=True，延迟 134 帧。不能称首次 source 发布前即恢复。

实际 live anchor={'frame': 3025, 'native_id': 47, 'mask': 'n:47', 'canonical_id': 9}；不可变进入 registry 中旧 anchor 仍等于原 candidate old_anchor；下一帧本分支 alias/public mapping 保持该提交。

此前缀 event q=None、end=None、status=MERGED；timeout 覆盖=False。未覆盖的以后 q/timeout 仍待完整段验证，不能用旧结果代替。

所有组外比对为真；matrix、确认、当前量测与旧参考来源均来自实际已运行记录。物理正确、进入前 public 标签是否已错以及完整段指标仍 UNKNOWN，等待全段预测封存后独立评分。

## MIXED_RETURN / MS1-F2873

原 D1_DELAYED 自然 5 次确认；local3025 / original3024 实际提交 source47→public9。

确认进度：local3021 count1, local3022 count2, local3023 count3, local3024 count4；最后确认由自然 accepted 原事件记录绑定。

source 首次实际发布 local2891 / original2890，public47；此前已公开=True，延迟 134 帧。不能称首次 source 发布前即恢复。

实际 live anchor={'frame': 3025, 'native_id': 47, 'mask': 'n:47', 'canonical_id': 9}；不可变进入 registry 中旧 anchor 仍等于原 candidate old_anchor；下一帧本分支 alias/public mapping 保持该提交。

此前缀 event q=None、end=None、status=MERGED；timeout 覆盖=False。未覆盖的以后 q/timeout 仍待完整段验证，不能用旧结果代替。

所有组外比对为真；matrix、确认、当前量测与旧参考来源均来自实际已运行记录。物理正确、进入前 public 标签是否已错以及完整段指标仍 UNKNOWN，等待全段预测封存后独立评分。

## 边界

帧编号公式：original = segment_start + local − 1。L3 segment_start=0，因此local3025对应原帧3024。confirmations是原算法接受事实；未accepted pending本身不是身份提交。

记录保留全部实态与路径/字节/SHA。公共发布的一对一/来源独占不证明物理单鱼；前缀工程通过也不证明深度增量。
