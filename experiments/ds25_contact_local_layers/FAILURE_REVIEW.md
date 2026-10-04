# DS25 预测封存后独立失效审计

只读全部封存的测量、候选比较与 INPUT_REVIEW；未读 GT、指标，未改变核心模块或旧实验。所有数字区分唯一 ROI fact、段×帧、候选引用和参考上下文，不把重复 fact 当成鱼或独立事件。

全20,098帧有10509次候选检查、17785次伙伴比较；真实veto 0、发布改变0。2343个唯一frame×ROI fact，涉及1807个段×帧。

## 测量资格失败

| 唯一 fact 主原因 | 数量 |
|---|---:|
| BACKGROUND_RESIDUAL_TOO_BROAD | 74 |
| EMPTY_ORIGINAL_CONTACT_ROI | 510 |
| EXACTLY_TWO_QUALIFIED_LOCAL_SUPPORTS_REQUIRED | 1424 |
| INSUFFICIENT_INDEPENDENT_ROI_COVERAGE | 86 |
| SUBSTANTIAL_NOISY_OR_UNRESOLVED_SUPPORT | 238 |
| TWO_NOISE_QUALIFIED_ANONYMOUS_LOCAL_DEPTH_LAYERS; PHYSICAL_OWNERSHIP_UNKNOWN | 2 |
| TWO_SPATIAL_PIECES_ARE_NOT_TWO_DEPTH_GAP_LAYERS | 9 |

合格支持数量分布：{"0": 1943, "1": 389, "2": 11}。层数量不等于物理鱼数。

空ROI 510；独立点数不足575；独立coverage不足542；背景平面不可用510。以下次级诊断可重叠，不可相加当作互斥主原因。

有背景兼容支持的fact 1707，有substantial背景兼容支持1460，全部测量支持均背景兼容1026。存在低于独立点下限的碎片862、低于原ROI比例的碎片956、同gap层存在多个空间碎片1346。这些观测不能直接指出哪条鱼漏失。

inclusive/independent分组不一致0、资格不一致0；substantial未决支持238。两个合格空间支持可能仍同属一个gap层，不能称已看见两条鱼。

## 首尾前史、种子和当前

| 阶段 | 引用次数 | 唯一 fact | 引用的合格支持数量分布 |
|---|---:|---:|---|
| first_pre | 540 | 15 | {"0": 371, "1": 169} |
| last_pre | 540 | 15 | {"0": 312, "1": 228} |
| seed | 540 | 15 | {"0": 490, "1": 50} |
| current | 540 | 378 | {"0": 532, "1": 8} |

实际测量链引用540次；完整fact序列去重后378，anchor/partner/seed参考上下文去重后15。这些上下文仍不是独立生物事件。所有测量引用60341次，对应2343个唯一fact，重复引用57998次。

最早不合格节点的引用阶段：{"first_pre": 540}。链要求每个节点合格；单独种子或当前可测不能弥补前史缺口。

## 上游范围与结论

原版本、当前几何和同步前史门阻止16864/17785次伙伴比较（94.82%）。其余接触种子与测量失效见JSON逐段原因。本次表示没有修复上游覆盖。

全部UNKNOWN保留原候选。零veto/零改变只说明此冻结表示未取得可用反证，不能证明身份路径正确、深度物理准确或干预安全。不要扩大窗口、放宽资格、按历史近远选层或拼接风险观测追求命中。

## 阶段 ROI 诊断的支持与边界

current 的 378 个唯一端点 fact 中，247 个（65.34%）ROI 为空；首 pre、尾 pre 各有 2/15 为空。这支持接触窗口与远处 clean 端点不是同一测量对象。但 15 个唯一 seed fact 全部没有双合格层，端点 ROI 校正本身不能使原逐帧双层链成立。独立/inclusive 的分组及资格不一致均为 0，也不能把失效归为这两种人口不一致。

固定时间顺序真实来源例：Feeding 351–555 的 local q82，native73→public30、partner66、seed23；首 pre F14 ROI392/n372/0层，尾 pre F22 ROI660/n490/1层，seed F23 ROI734/n576/1层，当前 F82 ROI0/n0/0层。q110、native72→1、partner68、seed85 的首 pre F66 ROI1/n1，seed F85 ROI807/n767，current F110 ROI130/n130，均0合格层。例子未按 GT 或效果选取，不据此推断真实鱼身份。

## 唯一下一方向

先做同一预测参考上下文的只读阶段 ROI 配对测量：clean pre/post 分别绑定各自实际 clean mask 的前景来源，contact 继续保留原局部匿名混合支持。保持原始来源、参考/版本/q、两个矩阵政策与资格阈值，检查端点空 ROI 是否减少，同时完整报告 seed 仍缺双层的范围。

这只检验测量对象是否适合阶段，不能宣称连续身份恢复。如果不再具备原逐帧匿名双层链，旧“交换端点即 veto”的比较不能当作物理身份依据直接沿用。此建议只规划，不启动新状态介入，不按 GT 选例，不降低资格追求命中。

每段、全部主因与次级诊断、首尾/种子/当前引用、逐链引用和来源哈希见FAILURE_REVIEW.json。
