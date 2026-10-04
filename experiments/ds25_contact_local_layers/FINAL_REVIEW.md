# DS25最终复盘：接触局部匿名双层空间反证

## 主判定

**ENGINEERING_COMPLETE_NO_EFFECTIVE_LOCAL_CHAIN_NO_INCREMENT。** 完整8段、20,098帧、181,842个原mask的三分支独立状态回放、来源核验和统一评分完成。新增候选反证0次，发布改变0帧。所有表保留完整指标；原Z4Q相对Native的既有收益不归DS25。 新分支逐帧发布与原Z4Q相同，本轮没有发布层面的增量。 没有建立可靠的完整局部空间链，完整支持链在真实数据中未被实际连续检验，当前结果不能证明反证有效或其干预安全。

当前冻结版停止。不依据评分扩大ROI、放宽阈值、跨风险拼接速度或补写身份历史。有效性、物理身份正确性和曝光参考上的数值变化分别报告。

## 完整指标

IDF1/HOTA/AssA/DetA单位为百分数，差值为百分点；IDSW/FP/FN/GT/预测数为计数。Feeding汇总由四段共同评分计算，未平均分段指标。所有预测及访问先封存，随后加载原参考；未忽略负ID、残片、重复mask或任何公开ID。

### Feeding四段汇总（1,471帧）

| 分支 | IDF1 | HOTA | AssA | DetA | IDSW | FP | FN | GT | 预测数 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| SAM3_NATIVE | 80.976760 | 79.964056 | 71.530499 | 89.730606 | 108 | 487 | 985 | 39706 | 39208 |
| Z4Q_FROZEN | 81.716806 | 79.859851 | 71.341782 | 89.723353 | 132 | 487 | 985 | 39706 | 39208 |
| Z4Q_LOCAL_LAYERS | 81.716806 | 79.859851 | 71.341782 | 89.723353 | 132 | 487 | 985 | 39706 | 39208 |

### feeding_000000_000199（200帧）

| 分支 | IDF1 | HOTA | AssA | DetA | IDSW | FP | FN | GT | 预测数 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| SAM3_NATIVE | 92.889759 | 91.362522 | 88.085877 | 94.761881 | 10 | 76 | 143 | 5399 | 5332 |
| Z4Q_FROZEN | 92.125617 | 90.483748 | 86.399664 | 94.761881 | 12 | 76 | 143 | 5399 | 5332 |
| Z4Q_LOCAL_LAYERS | 92.125617 | 90.483748 | 86.399664 | 94.761881 | 12 | 76 | 143 | 5399 | 5332 |

### feeding_000351_000555（205帧）

| 分支 | IDF1 | HOTA | AssA | DetA | IDSW | FP | FN | GT | 预测数 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| SAM3_NATIVE | 82.927271 | 78.582844 | 72.182690 | 85.592837 | 22 | 148 | 201 | 5547 | 5494 |
| Z4Q_FROZEN | 82.891042 | 78.147798 | 71.429933 | 85.539519 | 24 | 148 | 201 | 5547 | 5494 |
| Z4Q_LOCAL_LAYERS | 82.891042 | 78.147798 | 71.429933 | 85.539519 | 24 | 148 | 201 | 5547 | 5494 |

### feeding_000701_001060（360帧）

| 分支 | IDF1 | HOTA | AssA | DetA | IDSW | FP | FN | GT | 预测数 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| SAM3_NATIVE | 77.428039 | 75.545022 | 65.006580 | 87.802338 | 36 | 154 | 278 | 9720 | 9596 |
| Z4Q_FROZEN | 75.636778 | 73.560905 | 61.642162 | 87.796089 | 42 | 154 | 278 | 9720 | 9596 |
| Z4Q_LOCAL_LAYERS | 75.636778 | 73.560905 | 61.642162 | 87.796089 | 42 | 154 | 278 | 9720 | 9596 |

### feeding_001201_001906（706帧）

| 分支 | IDF1 | HOTA | AssA | DetA | IDSW | FP | FN | GT | 预测数 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| SAM3_NATIVE | 78.839951 | 78.727248 | 68.089322 | 91.053475 | 40 | 109 | 363 | 19040 | 18786 |
| Z4Q_FROZEN | 81.525935 | 79.892513 | 70.113143 | 91.057488 | 54 | 109 | 363 | 19040 | 18786 |
| Z4Q_LOCAL_LAYERS | 81.525935 | 79.892513 | 70.113143 | 91.057488 | 54 | 109 | 363 | 19040 | 18786 |

### fishsa_development_8400（8400帧）

| 分支 | IDF1 | HOTA | AssA | DetA | IDSW | FP | FN | GT | 预测数 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| SAM3_NATIVE | 91.313288 | 73.346143 | 69.186768 | 77.756638 | 5 | 194 | 323 | 50400 | 50271 |
| Z4Q_FROZEN | 99.333472 | 77.829488 | 77.907638 | 77.756638 | 6 | 194 | 323 | 50400 | 50271 |
| Z4Q_LOCAL_LAYERS | 99.333472 | 77.829488 | 77.907638 | 77.756638 | 6 | 194 | 323 | 50400 | 50271 |

### fishsa_validation_2888（2888帧）

| 分支 | IDF1 | HOTA | AssA | DetA | IDSW | FP | FN | GT | 预测数 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| SAM3_NATIVE | 76.456444 | 66.435529 | 55.196059 | 79.994919 | 8 | 298 | 423 | 17322 | 17197 |
| Z4Q_FROZEN | 80.697587 | 69.243869 | 60.074321 | 79.832735 | 9 | 298 | 423 | 17322 | 17197 |
| Z4Q_LOCAL_LAYERS | 80.697587 | 69.243869 | 60.074321 | 79.832735 | 9 | 298 | 423 | 17322 | 17197 |

### L3（3710帧）

| 分支 | IDF1 | HOTA | AssA | DetA | IDSW | FP | FN | GT | 预测数 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| SAM3_NATIVE | 72.426787 | 75.362607 | 94.259655 | 60.254015 | 1 | 14677 | 0 | 22250 | 36927 |
| Z4Q_FROZEN | 74.745256 | 77.171558 | 98.839045 | 60.254015 | 2 | 14677 | 0 | 22250 | 36927 |
| Z4Q_LOCAL_LAYERS | 74.745256 | 77.171558 | 98.839045 | 60.254015 | 2 | 14677 | 0 | 22250 | 36927 |

### LW（3629帧）

| 分支 | IDF1 | HOTA | AssA | DetA | IDSW | FP | FN | GT | 预测数 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| SAM3_NATIVE | 60.613534 | 66.369067 | 77.555121 | 56.796420 | 7 | 16493 | 28 | 21774 | 38239 |
| Z4Q_FROZEN | 64.329395 | 68.991721 | 83.805597 | 56.796420 | 10 | 16493 | 28 | 21774 | 38239 |
| Z4Q_LOCAL_LAYERS | 64.329395 | 68.991721 | 83.805597 | 56.796420 | 10 | 16493 | 28 | 21774 | 38239 |

L3/LW为未独立验收、预测衍生预标注的弱参考，单独诊断；其较大FP和得分变化不证明跨数据集泛化。其余也是既有曝光开发/验证片段，均不是新的盲测。

### 新分支相对两种基线的完整差值

| 来源 | 基线 | ΔIDF1 | ΔHOTA | ΔAssA | ΔDetA | ΔIDSW | ΔFP | ΔFN | ΔGT | Δ预测数 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Feeding_pooled | SAM3_NATIVE | +0.740046 | -0.104205 | -0.188717 | -0.007253 | +24 | +0 | +0 | +0 | +0 |
| Feeding_pooled | Z4Q_FROZEN | +0.000000 | +0.000000 | +0.000000 | +0.000000 | +0 | +0 | +0 | +0 | +0 |
| feeding_000000_000199 | SAM3_NATIVE | -0.764141 | -0.878774 | -1.686213 | +0.000000 | +2 | +0 | +0 | +0 | +0 |
| feeding_000000_000199 | Z4Q_FROZEN | +0.000000 | +0.000000 | +0.000000 | +0.000000 | +0 | +0 | +0 | +0 | +0 |
| feeding_000351_000555 | SAM3_NATIVE | -0.036229 | -0.435047 | -0.752757 | -0.053318 | +2 | +0 | +0 | +0 | +0 |
| feeding_000351_000555 | Z4Q_FROZEN | +0.000000 | +0.000000 | +0.000000 | +0.000000 | +0 | +0 | +0 | +0 | +0 |
| feeding_000701_001060 | SAM3_NATIVE | -1.791261 | -1.984117 | -3.364418 | -0.006250 | +6 | +0 | +0 | +0 | +0 |
| feeding_000701_001060 | Z4Q_FROZEN | +0.000000 | +0.000000 | +0.000000 | +0.000000 | +0 | +0 | +0 | +0 | +0 |
| feeding_001201_001906 | SAM3_NATIVE | +2.685983 | +1.165266 | +2.023821 | +0.004013 | +14 | +0 | +0 | +0 | +0 |
| feeding_001201_001906 | Z4Q_FROZEN | +0.000000 | +0.000000 | +0.000000 | +0.000000 | +0 | +0 | +0 | +0 | +0 |
| fishsa_development_8400 | SAM3_NATIVE | +8.020185 | +4.483345 | +8.720871 | +0.000000 | +1 | +0 | +0 | +0 | +0 |
| fishsa_development_8400 | Z4Q_FROZEN | +0.000000 | +0.000000 | +0.000000 | +0.000000 | +0 | +0 | +0 | +0 | +0 |
| fishsa_validation_2888 | SAM3_NATIVE | +4.241143 | +2.808340 | +4.878262 | -0.162185 | +1 | +0 | +0 | +0 | +0 |
| fishsa_validation_2888 | Z4Q_FROZEN | +0.000000 | +0.000000 | +0.000000 | +0.000000 | +0 | +0 | +0 | +0 | +0 |
| L3 | SAM3_NATIVE | +2.318468 | +1.808950 | +4.579391 | +0.000000 | +1 | +0 | +0 | +0 | +0 |
| L3 | Z4Q_FROZEN | +0.000000 | +0.000000 | +0.000000 | +0.000000 | +0 | +0 | +0 | +0 | +0 |
| LW | SAM3_NATIVE | +3.715862 | +2.622654 | +6.250476 | +0.000000 | +3 | +0 | +0 | +0 | +0 |
| LW | Z4Q_FROZEN | +0.000000 | +0.000000 | +0.000000 | +0.000000 | +0 | +0 | +0 | +0 | +0 |

## 证据到行为的覆盖

共10,509次候选入边检查、17,785次伙伴比较。实际形成2,343个唯一帧×局部ROI事实，其中2个满足匿名双层测量规则。合格支持记录411条；这些支持可能在多个ROI或查询重复出现，不能换算成鱼数或事件数。

双层事实占已查询ROI事实的0.0854%；分母不覆盖全部20,098帧或所有交互。共有358个查询帧进入测量，15个种子签名。种子签名按片段、首次接触帧和原native对去重，仍不是独立物理交互事件。双层可用覆盖不能称物理准确率；背景归属、鱼数和支持身份始终UNKNOWN。

阶段表的TARGET_GATE以候选入边检查计数，其余阶段以伙伴比较计数；两种单位不能直接相加当作事件数。

### 各阶段记录

| 阶段 | 次数 |
|---|---:|
| UPSTREAM_PAIR_OR_ACQUIRED_SOURCE_BLOCK | 16864 |
| TARGET_GATE_BEFORE_PARTNER_COMPARISON | 1903 |
| LOCAL_MEASUREMENT_COVERAGE_FAILURE | 540 |
| NO_CONTACT_SEED_BEFORE_MEASUREMENT | 381 |

### 完整伙伴结果

| 结果 | 次数 |
|---|---:|
| UNKNOWN | 17785 |

### 上游与局部链失败原因

| 原因 | 次数 |
|---|---:|
| CURRENT_PARTNER_OR_PAIR_GEOMETRY_RISK | 7479 |
| NO_SUFFICIENT_SYNCHRONOUS_ANCHOR_PAIR | 5487 |
| PARTNER_CLAIM_GENERATION_OR_EPOCH_CHANGED | 3898 |
| EVERY_FRAME_REQUIRES_EXACTLY_TWO_QUALIFIED_LOCAL_LAYERS | 540 |
| NO_ACTUAL_GEOMETRY_CONTACT_SEED | 381 |

### 局部测量原因

| 原因 | 次数 |
|---|---:|
| EXACTLY_TWO_QUALIFIED_LOCAL_SUPPORTS_REQUIRED | 1424 |
| EMPTY_ORIGINAL_CONTACT_ROI | 510 |
| SUBSTANTIAL_NOISY_OR_UNRESOLVED_SUPPORT | 238 |
| INSUFFICIENT_INDEPENDENT_ROI_COVERAGE | 86 |
| BACKGROUND_RESIDUAL_TOO_BROAD | 74 |
| TWO_SPATIAL_PIECES_ARE_NOT_TWO_DEPTH_GAP_LAYERS | 9 |
| TWO_NOISE_QUALIFIED_ANONYMOUS_LOCAL_DEPTH_LAYERS; PHYSICAL_OWNERSHIP_UNKNOWN | 2 |

### 连续链首次不可用节点

| 阶段/测量原因 | 次数 |
|---|---:|
| PRE/EXACTLY_TWO_QUALIFIED_LOCAL_SUPPORTS_REQUIRED | 299 |
| PRE/INSUFFICIENT_INDEPENDENT_ROI_COVERAGE | 121 |
| PRE/SUBSTANTIAL_NOISY_OR_UNRESOLVED_SUPPORT | 103 |
| PRE/EMPTY_ORIGINAL_CONTACT_ROI | 17 |

连续链表按每次候选比较的第一个不可用节点计数；其后各帧测量仍完整保留。其余后续空间对应、端点归属、弱顺序或观察到近远反转的失败在伙伴原因表单列。

| 片段 | 候选检查 | 伙伴比较 | ROI事实 | 可用双层事实 | veto | 改变帧 |
|---|---:|---:|---:|---:|---:|---:|
| feeding_000000_000199 | 168 | 334 | 0 | 0 | 0 | 0 |
| feeding_000351_000555 | 466 | 1460 | 523 | 0 | 0 | 0 |
| feeding_000701_001060 | 1345 | 4500 | 166 | 0 | 0 | 0 |
| feeding_001201_001906 | 1469 | 3206 | 436 | 1 | 0 | 0 |
| fishsa_development_8400 | 13 | 20 | 0 | 0 | 0 | 0 |
| fishsa_validation_2888 | 85 | 153 | 0 | 0 | 0 | 0 |
| L3 | 843 | 977 | 316 | 0 | 0 | 0 |
| LW | 6120 | 7135 | 902 | 1 | 0 | 0 |

## 独立失败分层：测量对象与支持链

FAILURE_REVIEW.json/md独立读取封存预测与测量记录，不读GT或评分。其来源摘要在RESULTS与REPORT_PROVENANCE中绑定；下列次级诊断可重叠，不能相加当作事件总数。

### 唯一ROI事实的合格支持数

| 合格支持记录数 | 次数 |
|---|---:|
| 0 | 1943 |
| 1 | 389 |
| 2 | 11 |

两个合格空间支持的11个事实中，9个属于同一原始深度gap组的不同空间件；最终只有2个AVAILABLE_TWO_LAYERS事实。不能把空间片数、raw modes或合格支持数当作两鱼标签。

| 次级事实诊断（可重叠） | 唯一事实数 |
|---|---:|
| 原始ROI面积为0 | 510 |
| 至少一个支持与局部背景代理兼容 | 1707 |
| 全部有效支持与局部背景代理兼容 | 1026 |
| 有重大噪声或未解决支持 | 238 |
| inclusive/独立源分组不一致 | 0 |
| inclusive/独立源支持资格不一致 | 0 |

### 固定参考上下文的阶段观测

540次序列引用对应378条去重事实序列、15个anchor/partner/seed参考上下文。60,341次测量引用中，2,343个事实唯一，57,998次为重复引用；这些上下文不是独立生物交互事件。

| 阶段 | 引用次数 | 唯一事实 | 空ROI | 0合格支持 | 1合格支持 | 2合格支持 | 可用双层事实 |
|---|---:|---:|---:|---:|---:|---:|---:|
| first_pre | 540 | 15 | 2 | 12 | 3 | 0 | 0 |
| last_pre | 540 | 15 | 2 | 9 | 6 | 0 | 0 |
| seed | 540 | 15 | 0 | 10 | 5 | 0 | 0 |
| current | 540 | 378 | 247 | 370 | 8 | 0 | 0 |

上游原伙伴门挡住16,864/17,785次比较（94.82%），没有为测量绕过这些门。

当前端点247/378个唯一ROI为空（65.34%）。这是冻结实现采用有界接触窗口测量clean端点时的测量对象错位证据；已核验实现确实按该窗口计算，不能改称端点拷贝失败或声明与执行不一致。

修正clean端点ROI也不能自动建立连续链：固定种子及端点事实均未有两个合格支持；contact阶段的层可观测性仍须单独验证。独立源与inclusive一致性门在本次未出现分歧，不能解释零完整链。没有连续空间链时不能复用swapped-endpoint veto来认证身份。

### 两个固定时间顺序案例

| 片段/query | 候选native→public | 伙伴 | seed帧 | 阶段 | local帧 | ROI面积 | 独立点 | 合格支持 |
|---|---|---:|---:|---|---:|---:|---:|---:|
| feeding_000351_000555/82 | 73→30 | 66 | 23 | first_pre | 14 | 392 | 372 | 0 |
| feeding_000351_000555/82 | 73→30 | 66 | 23 | last_pre | 22 | 660 | 490 | 1 |
| feeding_000351_000555/82 | 73→30 | 66 | 23 | seed | 23 | 734 | 576 | 1 |
| feeding_000351_000555/82 | 73→30 | 66 | 23 | current | 82 | 0 | 0 | 0 |
| feeding_000351_000555/110 | 72→1 | 68 | 85 | first_pre | 66 | 1 | 1 | 0 |
| feeding_000351_000555/110 | 72→1 | 68 | 85 | last_pre | 73 | 96 | 87 | 0 |
| feeding_000351_000555/110 | 72→1 | 68 | 85 | seed | 85 | 807 | 767 | 0 |
| feeding_000351_000555/110 | 72→1 | 68 | 85 | current | 110 | 130 | 130 | 0 |

案例按固定预测上下文列示，无GT选区、无以评分挑层；q82当前窗口为空，同时seed23只有一个合格支持。q110当前窗口非空而支持仍不可用，故不能把全部失败归为空端点。

## 实际动作与严格物理判定

严格CORRECT要求当前目标、实际bank参考和公开ID出生来源三者全部一致；任一明确不同记WRONG，有未决参考且没有明确不同记UNSCORABLE。未形成真实发布及持久alias的动作单列NOT_DURABLE。实际bank端点正确性与公开ID既有来源错位分别保留，数值涨分不自动等于物理身份恢复。

| 分支 | 严格正确 | 严格错误 | 不可评分 | 未持久提交 |
|---|---:|---:|---:|---:|
| Z4Q_FROZEN | 15 | 17 | 58 | 0 |
| Z4Q_LOCAL_LAYERS | 15 | 17 | 58 | 0 |

原Z4Q的90条实际动作已与旧DS24封存记录逐项复现。本轮保留原边90条，丢失原时点动作0条，新增或时点改变的原控制器动作0条。局部模块只否决候选，不直接提交新身份；后续新增动作不全部称为“深度恢复成功”。丢失动作中的直接同边反证和后续状态/分配变化分开记录，延迟的同源同目标动作保留具体时点。

### 反证边及直接阻止的原动作

| 被否决边物理判定 | 次数 |
|---|---:|
| 无记录 | 0 |
| 直接丢失原动作严格判定 | 次数 |
|---|---:|
| 无记录 | 0 |

被否决的CORRECT边为潜在误杀；只有原分支确实提交该边时才是直接丢失原恢复。零veto不能证明安全，UNSCORABLE不能转为正确。

### 原90条动作逐项去向

| 片段 | global/local | 原source→target | 入口 | 严格物理 | 实际bank参考 | 公开来源 | 本轮去向 |
|---|---|---|---|---|---|---|---|
| L3 | 297/298 | 12→13 | D1_DELAYED | UNSCORABLE | UNSCORABLE | UNKNOWN | 保留原边 |
| L3 | 547/548 | 16→14 | D1_DELAYED | UNSCORABLE | UNSCORABLE | UNKNOWN | 保留原边 |
| L3 | 930/931 | 23→13 | D1_DELAYED | UNSCORABLE | UNSCORABLE | UNKNOWN | 保留原边 |
| L3 | 1086/1087 | 25→2 | D1_DELAYED | UNSCORABLE | UNSCORABLE | UNKNOWN | 保留原边 |
| L3 | 1515/1516 | 33→15 | D1_DELAYED | UNSCORABLE | UNSCORABLE | UNKNOWN | 保留原边 |
| L3 | 1628/1629 | 34→15 | D1_DELAYED | UNSCORABLE | UNSCORABLE | UNKNOWN | 保留原边 |
| L3 | 2911/2912 | 46→43 | D1_DELAYED | UNSCORABLE | UNSCORABLE | UNKNOWN | 保留原边 |
| L3 | 3024/3025 | 47→9 | D1_DELAYED | CORRECT | CORRECT | SAME | 保留原边 |
| L3 | 3388/3389 | 50→39 | D1_DELAYED | UNSCORABLE | UNSCORABLE | UNKNOWN | 保留原边 |
| L3 | 3687/3688 | 57→48 | D1_DELAYED | UNSCORABLE | UNSCORABLE | UNKNOWN | 保留原边 |
| LW | 114/115 | 14→9 | D1_DELAYED | UNSCORABLE | UNSCORABLE | UNKNOWN | 保留原边 |
| LW | 152/153 | 13→9 | D1_DELAYED | UNSCORABLE | UNSCORABLE | UNKNOWN | 保留原边 |
| LW | 312/313 | 19→12 | D1_DELAYED | UNSCORABLE | UNSCORABLE | UNKNOWN | 保留原边 |
| LW | 354/355 | 21→18 | D1_DELAYED | UNSCORABLE | UNSCORABLE | UNKNOWN | 保留原边 |
| LW | 827/828 | 30→24 | D1_DELAYED | UNSCORABLE | UNSCORABLE | UNKNOWN | 保留原边 |
| LW | 951/952 | 32→24 | D1_DELAYED | UNSCORABLE | UNSCORABLE | UNKNOWN | 保留原边 |
| LW | 1024/1025 | 38→2 | D1_DELAYED | UNSCORABLE | UNSCORABLE | UNKNOWN | 保留原边 |
| LW | 1194/1195 | 44→24 | D1_DELAYED | UNSCORABLE | UNSCORABLE | UNKNOWN | 保留原边 |
| LW | 1234/1235 | 49→37 | D1_DELAYED | UNSCORABLE | UNSCORABLE | UNKNOWN | 保留原边 |
| LW | 1237/1238 | 48→39 | D1_DELAYED | UNSCORABLE | UNSCORABLE | UNKNOWN | 保留原边 |
| LW | 1320/1321 | 54→43 | D1_DELAYED | UNSCORABLE | UNSCORABLE | UNKNOWN | 保留原边 |
| LW | 1328/1329 | 53→40 | D1_DELAYED | UNSCORABLE | UNSCORABLE | UNKNOWN | 保留原边 |
| LW | 1330/1331 | 50→42 | D1_DELAYED | UNSCORABLE | UNSCORABLE | UNKNOWN | 保留原边 |
| LW | 1483/1484 | 61→4 | D1_DELAYED | UNSCORABLE | UNSCORABLE | SAME | 保留原边 |
| LW | 1507/1508 | 63→43 | D1_DELAYED | UNSCORABLE | UNSCORABLE | UNKNOWN | 保留原边 |
| LW | 1552/1553 | 64→4 | D1_DELAYED | UNSCORABLE | UNSCORABLE | SAME | 保留原边 |
| LW | 1638/1639 | 67→24 | D1_DELAYED | UNSCORABLE | UNSCORABLE | UNKNOWN | 保留原边 |
| LW | 1722/1723 | 71→62 | D1_DELAYED | UNSCORABLE | UNSCORABLE | UNKNOWN | 保留原边 |
| LW | 1887/1888 | 80→42 | D1_DELAYED | UNSCORABLE | UNSCORABLE | UNKNOWN | 保留原边 |
| LW | 2064/2065 | 87→83 | D1_DELAYED | UNSCORABLE | UNSCORABLE | UNKNOWN | 保留原边 |
| LW | 2200/2201 | 91→42 | D1_DELAYED | UNSCORABLE | UNSCORABLE | UNKNOWN | 保留原边 |
| LW | 2220/2221 | 94→85 | D1_DELAYED | UNSCORABLE | UNSCORABLE | UNKNOWN | 保留原边 |
| LW | 2329/2330 | 98→86 | D1_DELAYED | UNSCORABLE | UNSCORABLE | UNKNOWN | 保留原边 |
| LW | 2389/2390 | 103→86 | D1_DELAYED | UNSCORABLE | UNSCORABLE | UNKNOWN | 保留原边 |
| LW | 2432/2433 | 101→92 | D1_DELAYED | UNSCORABLE | UNSCORABLE | UNKNOWN | 保留原边 |
| LW | 2436/2437 | 104→42 | D1_DELAYED | UNSCORABLE | UNSCORABLE | UNKNOWN | 保留原边 |
| LW | 2459/2460 | 107→99 | D1_DELAYED | UNSCORABLE | UNSCORABLE | UNKNOWN | 保留原边 |
| LW | 2514/2515 | 106→5 | D1_DELAYED | CORRECT | CORRECT | SAME | 保留原边 |
| LW | 2531/2532 | 109→93 | D1_DELAYED | UNSCORABLE | UNSCORABLE | UNKNOWN | 保留原边 |
| LW | 2692/2693 | 112→99 | D1_DELAYED | UNSCORABLE | UNSCORABLE | UNKNOWN | 保留原边 |
| LW | 2709/2710 | 114→92 | D1_DELAYED | UNSCORABLE | UNSCORABLE | UNKNOWN | 保留原边 |
| LW | 2765/2766 | 116→92 | D1_DELAYED | UNSCORABLE | UNSCORABLE | UNKNOWN | 保留原边 |
| LW | 2788/2789 | 118→93 | D1_DELAYED | UNSCORABLE | UNSCORABLE | UNKNOWN | 保留原边 |
| LW | 2822/2823 | 120→99 | D1_DELAYED | UNSCORABLE | UNSCORABLE | UNKNOWN | 保留原边 |
| LW | 2883/2884 | 124→93 | D1_DELAYED | UNSCORABLE | UNSCORABLE | UNKNOWN | 保留原边 |
| LW | 2905/2906 | 123→115 | D1_DELAYED | UNSCORABLE | UNSCORABLE | UNKNOWN | 保留原边 |
| LW | 2974/2975 | 129→99 | D1_DELAYED | UNSCORABLE | UNSCORABLE | UNKNOWN | 保留原边 |
| LW | 2981/2982 | 130→42 | D1_DELAYED | UNSCORABLE | UNSCORABLE | UNKNOWN | 保留原边 |
| LW | 2998/2999 | 128→99 | D1_DELAYED | UNSCORABLE | UNSCORABLE | UNKNOWN | 保留原边 |
| LW | 3052/3053 | 132→93 | D1_DELAYED | UNSCORABLE | UNSCORABLE | UNKNOWN | 保留原边 |
| LW | 3080/3081 | 134→42 | D1_DELAYED | UNSCORABLE | UNSCORABLE | UNKNOWN | 保留原边 |
| LW | 3119/3120 | 139→42 | D1_DELAYED | UNSCORABLE | UNSCORABLE | UNKNOWN | 保留原边 |
| LW | 3272/3273 | 143→42 | D1_DELAYED | UNSCORABLE | UNSCORABLE | UNKNOWN | 保留原边 |
| LW | 3306/3307 | 142→43 | D1_DELAYED | UNSCORABLE | UNSCORABLE | UNKNOWN | 保留原边 |
| LW | 3325/3326 | 144→133 | D1_DELAYED | UNSCORABLE | UNSCORABLE | UNKNOWN | 保留原边 |
| LW | 3427/3428 | 150→133 | D1_DELAYED | UNSCORABLE | UNSCORABLE | UNKNOWN | 保留原边 |
| LW | 3491/3492 | 151→148 | D1_DELAYED | UNSCORABLE | UNSCORABLE | UNKNOWN | 保留原边 |
| feeding_000000_000199 | 159/160 | 26→16 | D1_DELAYED | WRONG | WRONG | SAME | 保留原边 |
| feeding_000000_000199 | 190/191 | 30→8 | D1_DELAYED | WRONG | WRONG | SAME | 保留原边 |
| feeding_000000_000199 | 194/195 | 38→7 | D1_DELAYED | UNSCORABLE | UNSCORABLE | UNKNOWN | 保留原边 |
| feeding_000351_000555 | 374/24 | 70→67 | D1_DELAYED | UNSCORABLE | UNSCORABLE | UNKNOWN | 保留原边 |
| feeding_000351_000555 | 468/118 | 80→21 | BIRTH_REFINE | WRONG | WRONG | UNKNOWN | 保留原边 |
| feeding_000351_000555 | 522/172 | 83→73 | D1_DELAYED | WRONG | WRONG | SAME | 保留原边 |
| feeding_000701_001060 | 834/134 | 118→99 | D1_DELAYED | WRONG | WRONG | SAME | 保留原边 |
| feeding_000701_001060 | 849/149 | 119→70 | D1_DELAYED | WRONG | WRONG | SAME | 保留原边 |
| feeding_000701_001060 | 897/197 | 127→106 | D1_DELAYED | WRONG | WRONG | SAME | 保留原边 |
| feeding_000701_001060 | 905/205 | 123→117 | D1_DELAYED | CORRECT | CORRECT | SAME | 保留原边 |
| feeding_000701_001060 | 969/269 | 129→91 | D1_DELAYED | WRONG | WRONG | SAME | 保留原边 |
| feeding_000701_001060 | 1043/343 | 132→120 | D1_DELAYED | CORRECT | CORRECT | SAME | 保留原边 |
| feeding_001201_001906 | 1360/160 | 170→167 | D1_DELAYED | CORRECT | CORRECT | SAME | 保留原边 |
| feeding_001201_001906 | 1390/190 | 172→126 | BIRTH_REFINE | WRONG | WRONG | SAME | 保留原边 |
| feeding_001201_001906 | 1404/204 | 168→136 | D1_DELAYED | WRONG | WRONG | SAME | 保留原边 |
| feeding_001201_001906 | 1463/263 | 177→158 | D1_DELAYED | CORRECT | CORRECT | SAME | 保留原边 |
| feeding_001201_001906 | 1466/266 | 174→163 | D1_DELAYED | CORRECT | CORRECT | SAME | 保留原边 |
| feeding_001201_001906 | 1466/266 | 176→167 | D1_DELAYED | CORRECT | CORRECT | SAME | 保留原边 |
| feeding_001201_001906 | 1516/316 | 178→119 | D1_DELAYED | WRONG | WRONG | SAME | 保留原边 |
| feeding_001201_001906 | 1615/415 | 181→166 | D1_DELAYED | CORRECT | CORRECT | SAME | 保留原边 |
| feeding_001201_001906 | 1681/481 | 188→125 | D1_DELAYED | WRONG | WRONG | SAME | 保留原边 |
| feeding_001201_001906 | 1712/512 | 186→166 | D1_DELAYED | WRONG | WRONG | SAME | 保留原边 |
| feeding_001201_001906 | 1751/551 | 183→125 | D1_DELAYED | WRONG | WRONG | SAME | 保留原边 |
| feeding_001201_001906 | 1799/599 | 187→164 | D1_DELAYED | WRONG | WRONG | SAME | 保留原边 |
| feeding_001201_001906 | 1821/621 | 194→149 | D1_DELAYED | CORRECT | CORRECT | SAME | 保留原边 |
| feeding_001201_001906 | 1888/688 | 193→158 | D1_DELAYED | WRONG | WRONG | SAME | 保留原边 |
| feeding_001201_001906 | 1893/693 | 197→167 | D1_DELAYED | WRONG | WRONG | SAME | 保留原边 |
| fishsa_development_8400 | 1327/1327 | 6→0 | D1_DELAYED | CORRECT | CORRECT | SAME | 保留原边 |
| fishsa_development_8400 | 3902/3902 | 7→0 | BIRTH_REFINE | CORRECT | CORRECT | SAME | 保留原边 |
| fishsa_development_8400 | 8054/8054 | 8→2 | D1_DELAYED | CORRECT | CORRECT | SAME | 保留原边 |
| fishsa_validation_2888 | 9580/280 | 6→2 | D1_DELAYED | UNSCORABLE | CORRECT | UNKNOWN | 保留原边 |
| fishsa_validation_2888 | 11488/2188 | 8→3 | BIRTH_REFINE | CORRECT | CORRECT | SAME | 保留原边 |
| fishsa_validation_2888 | 12150/2850 | 11→5 | D1_DELAYED | CORRECT | CORRECT | SAME | 保留原边 |

完整原/新动作、真实bank锚点、三组关系、所有被否决边、延迟替代和新增动作见RESULTS.json及ACTUAL_AUTOMATIC_ACTIONS.json；原始逐边证据保留在各段ACTION_AUDIT/ORDER_CHECKS，不改写旧输出。

## 增量、限制与复现

原生SAM3是主要比较，原Z4Q是同源机制增量比较。各段及Feeding汇总的相对Native/原Z4Q差值已全部列出；原Z4Q既有收益不计入DS25。局部测量可用、完整唯一空间链、真实候选veto、首发改变和物理可评分纠错属于不同层次。仅在曝光参考上变好、只修复既有公开ID错位，或只减少某较弱分支损害，不能宣称深度独立身份能力已证实。

两层原始支持不等于两条鱼；同一弯曲鱼体、背景、共享投影和掩码混合均可能导致层或空间片。相邻空间双射与df4噪声概率仍是未校准条件代理；观察到真实近远穿越时退回UNKNOWN，source_index不跨帧认证身份。当前完整八段不能证明其他场景或水下物理标定已成立。覆盖不足或零介入只约束本冻结表示，不能称深度理论被否定，也不能称完整局部空间链的物理身份能力已被检验。

来源与公式审计PASS，逐帧ledger/事务/候选入口、完整测量引用、独立源及inclusive统计均核对。公开审计重算空间计数的分数与双射，不冒称重新计算私有像素交集；来源/像素绑定和冻结生产代码另由协议检查保护。

新增模型HTTP、smoke、训练、SAM3推理、深度补全服务与费用全部0。仅四个单线程本地作业回放既有保存mask；各段耗时见RUN_SUMMARY、并发墙钟见EXECUTION_LOG，评分耗时另列。既有SAM3推理不计入本轮回放，不能称实时部署。

查询截止为q；仅读当前配对或此前已经取得的原始数据。sensor delta_us保留，配对可能晚于RGB时间约1–2ms，不能宣称严格同时、零等待或上游SAM3完全无前视。无获授权片段未完成；旧seal/数据/状态只读。

主要证据：RUNTIME_FREEZE.json、run/ALL_PREDICTIONS_SEALED.json、INPUT_REVIEW.json、FAILURE_REVIEW.json/md、run/METRICS.json、各段PUBLISH_LEDGER/TRANSACTIONS/ORDER_CHECKS/MEASUREMENTS/ANONYMOUS_RISK/ACTION_AUDIT、REPORT_PROVENANCE.json。私有图片及参考像素不进入公开报告；具体可视化是否生成、检查与远端交付以相应最终清单为准。

## 唯一下一步（未实施）

阶段ROI只读配对测量：先核验实际能观测哪一层

独立封存审计显示当前端点247/378个唯一ROI为空，但15个真实接触种子均不足两个合格层。接触窗口与clean端点的测量对象错位有证据；修正端点仍不能自动恢复缺失的合并期双层。先停止这一冻结空间链，避免把无覆盖当成可靠身份约束。

固定本轮15个预测anchor/partner/seed参考上下文和原始depth，按阶段配对比较：clean pre/post各自绑定实际合格mask的前景支持；接触期保留同一匿名local区域。只检验深度来源、背景兼容、独立点、单层/双层和时序可观测性，逐对象报告UNKNOWN及测量对象变化，不启动新的身份回放或声称提点。

不换reference、source generation、q或候选，不使用GT挑区域/层，不放宽质量阈值、不改变两个矩阵及事务规则，不新增模型/训练/补全。所有像素私有。没有完整连续空间链时，不能沿用本轮swapped-endpoint veto来认证身份；待真实配对证据决定是否值得另立恢复假设。
