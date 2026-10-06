# DS34 评分后失败病例追溯

本分析在八来源预测、访问、输入及首次发布绑定全部封存、对应来源独立评分完成后追加。只读正式预测和评分派生的数值参考匹配；不重跑跟踪、不修改评分、不读取或发布 GT raster。病例选择用于事后诊断，未影响本轮触发、参考、q、门槛或选择。

## 主结论

最明显的退化不是深度错误直接否决了正确身份。两个事件分支在这里逐帧完全相同：共同的保护/回退机制没有保住原 Z4Q 的有效 BirthRefine 恢复，造成长期身份碎裂；随后另一个窗口在全部增强证据关闭时仍依据几何距离进行了错误联合交换。

| 来源 | Z4Q IDF1 / HOTA / AssA / IDSW | EVENT_RGB 与 EVENT_RGBD | 差值：EVENT−Z4Q |
| --- | --- | --- | --- |
| FishSA 开发 8400 | 99.3335 / 77.8295 / 77.9076 / 6 | 92.0404 / 74.5266 / 71.4327 / 5 | −7.2931 / −3.3029 / −6.4749 / −1 |
| FishSA 验证 2888 | 80.6976 / 69.2439 / 60.0743 / 9 | 75.8191 / 64.7960 / 52.5842 / 11 | −4.8785 / −4.4479 / −7.4901 / +2 |

百分指标单位为百分数，差值为百分点。完整指标仍以不变官方评分的 METRICS 为准。下文的持续帧数是实际发布映射差异长度，不是重新定义的错误数，也不是单事件 IDF1 因果分解。

## 1. 开发段 MS1-F3863：一次回退，长期碎裂

实际首次疑似 F3863，确认 F3864，首分离 q=3902，决策截止 F3909；q 在收到 F3932 时只首次发布一次，固定延迟 30 帧。原两身份是 public4 和 public0，原 source6 已经实际承接 public0。

q 的实际状态与发布：

- 原 Z4Q 通过真实 `phase=birth` 动作接受 source7→public0，引用 F3836/source6 的旧 anchor，cost=0.8087616422，assignment margin=0.1912383578，有一条实际 survivor witness。source4 的原 native certificate 在 F3901 仍合格。
- 新事件分支因 pre-A 的 F3492/source4 精确历史来源为 UNKNOWN_REFERENCE，返回 `DEFER / NO_PRE_HISTORY`。不能把该未知历史改写为合格参考。
- 实际执行 `LOCAL_FALLBACK_UNRESOLVED`，写集是 native[4,7]、public[0,4,7]。q 首次发布 source7→public7；source7 没有到 public0 的实际 alias。并非只改了最终输出文件。
- 此后 F3902–F8400 连续 4499 帧保持“Z4Q source7→0、事件分支 source7→7”。其中 4491 帧 source7 有唯一 IoU 匹配到同一物理参考 GT1，8 帧匹配未知，后者保留未知。
- F3902 对同一物理目标新增一次 0→7 的切换。后来其他事件也报告 source7 的相同差异，但它们没有重新写这条组外映射，不能把这 4499 帧损害重复归因给附近事件。

这里 public0 是合法的原身份整数，GT1 是评分参考；二者不是按整数相等建立关系。public7 本轮在 q 才首次出现，没有 strictly-pre-q 的公共来源参考。因此该 fallback 的正式物理 verdict 仍为 UNSCORABLE。可证实的是它丢失了原 Z4Q 对同一物理鱼的持续身份承接，不能称“新 public7 恢复成功”。

原 Z4Q 全段 6 次切换，事件分支 5 次：事件分支在 F3902 新增一次，同时在另一个正确恢复窗口消除了 F8035/F8054 两次往返。净少一次切换不能掩盖长时间身份碎裂，所以 IDF1 与 AssA 仍显著下降。

## 2. 验证段 MS1-F2125：回退 COMMITTED 不代表保住原恢复

首次疑似 local F2125（global F11425），q=2188（global F11488），截止 q+30=2218；q 在该截止帧首次发布。原 public3/public7 被保护。

- 原 Z4Q 在 q 真实 BirthRefine 接受 source8→public3，cost=0.3993077141，margin=0.6006922859，旧 anchor 为 local F1935/source3。有实际 survivor witness，持续 native7 被原 native prior 保留。
- 新分支三帧连续 clean 确认在截止前不足，返回 `DEFER / UNKNOWN_DEADLINE`；保留真实来源和未知，未挑选更晚或更容易的确认段。
- `LOCAL_FALLBACK_COMMITTED` 只表示本事件局部事务合法：其自己的 q 前状态所产生的选择是 source8→public8。实际没有安装 source8→public3 的 alias。
- local F2188–F2688 连续 501 帧保持这一差异；其中 500 帧 source8 唯一匹配同一物理参考 GT3，1 帧未知。q 新增 3→8 的切换。

所以“使用原数值策略回退”在当前原型中不等于“取消这段保护后，仍能得到原 Z4Q 的完整恢复”。回退来自已经经历保护的自身状态，不能无证据宣称它复现未受干预的 Z4Q。该差异在正式预测已发生，不是评分标签置换问题。

## 3. 验证段 MS1-F2681：证据关闭后，几何单独作出错误交换

实际 q=2689（global F11989），决策截止 F2710，q 在 F2719 首次发布。实际选 H2，并把两个 alias 写入引擎：source5→public8、source8→public5；继续自己的状态。q 写入只使用 q 的当前观测，未把 q+21 深度或速度写回 q bank。

H1 原映射的 cost=2.8470896605，H2 交换 cost=2.6281853895，胜出差为 0.2189042710，超过冻结 margin0.10。该窗口的共同权重是：motion=0、contour=0、depth=0。

- pre-A 是 source5 的十点合格片段；pre-B/source8 只有 F2621 一个合格时刻，因此没有可靠的双端运动比较。
- 轮廓项未能在全矩阵取得共同合格支持，全部关闭；不能把未合格的跨缺口光流当真实鱼体路径。
- 当前 source8 的三个确认深度片段均被记为 POTENTIAL_MIXTURE，core 不是可认证的单层，故全矩阵共同深度权重归零。原始非零深度和观测 neighbors 为空仍不足以保证不混层。
- 后续三个 source clean 观测确实一致，但它们只证明“当前匿名 source 连续”，不证明它应该归属于哪个旧身份。

独立评分显示，q 的 source5 物理匹配 GT5，却被接到参考 GT3 的 public8；source8 物理匹配 GT3，却被接到参考 GT5 的 public5。literal-q/preanchor、固定 postfragment/preanchor 与公共来源检查均为 WRONG；prefragment 中 source8 只有单点的边仍保留 UNSCORABLE，另一边错误足以使整个联合结果 WRONG。两个旧参考的公共来源本来正确，此次不是纠正早已错号。

该 stage 在 global F11989 新增两次切换。source8→public5 相对原 Z4Q 的 source8→public3 持续至验证段末（200 帧）；source5→public8 在后续可见段继续存在，未通过重画过去或永久锁 ID 隐藏。

## 能证实的机制和仍未知的部分

事务账本、q 首次发布、后缀完整状态 hash 与后续 alias 足以把以上差异绑定到实际本事件 fallback/stage 写集。并非因为事件在附近就归因。

静态真实控制流进一步显示，保护期间原两成员的 bank、view_bank、native_runs、recent_core 等被隔离并恢复旧版本；回退候选从这条已经受保护的自身分支状态计算。它无法自动获得未受干预 Z4Q 在群组期间累计的 survivor/native 资格证据。开发段还存在原 member source6 的 latent alias→public0，而 inherited fallback 当前可见 native 写集不包含缺席 source6，因而会把该既有 ownership 当作安全限制。

这是有源码和真实状态差异支持的机制解释。正式 fallback 仅封存 candidate_trace_events=0，未封存完整 candidate birth rejection 列表；本分析没有运行新的 ALLOW/VETO 全段反事实，因此精确到“哪个候选子门槛最先拒绝”的答案是 UNKNOWN，不能编造单边失败原因，也不能把全部 −7.2931 点精确归于一个事件。

## 唯一未启动下一步

先验证一个最小的“原 Z4Q 有效恢复保真”修复：身份参考继续保护，匿名观测与原数值恢复候选保留各自合法来源；未知或增强项全关闭时，局部回退须在自身事件写集内承接合法的原恢复，不仅依赖已经受保护而退化的候选状态。先对上面两条 lost-BirthRefine 真实切片和 geometry-only 错交换建立可追溯检查，再冻结全段。该计划尚未执行，也不预报收益。

## 可复查产物

- `POSTSEAL_FAILURE_CASES.json`：逐来源完整指标、所有最长映射差异、q/pre/group/cutoff 的四分支实际发布、完整状态 hash/alias/epoch、引用与独立物理审计、switch occurrence、源文件 pins。
- `postseal_extra_visuals.py`：仅事后分析和渲染，预测/评分均只读。
- `POSTSEAL_EXTRA_PRIVATE_VISUALS.json`：三张真实病例图的私有路径、字节、SHA，以及实际 RGB/raw depth/原 mask/prediction 绑定和复现依赖。
- 三图位于 `private/postseal_extra_cases/`，包含四分支相同实际像素与原 SAM3 掩码，在 pre-A/pre-B/首次疑似/最后 group/q/决策截止六个实际时刻显示首次发布 ID。所有残片保留；未绘制或读取 GT raster；PRIVATE 像素不得提交公共仓库。
