# DS35 最终复盘


主判定：**NO_DEPTH_OVERRIDE_ALL_PUBLICATIONS_EQUAL_TO_ORIGINAL_Z4Q**。八个同源片段、每分支20098帧完整真实状态回放，全部先封存再独立评分。


## 改了什么与保留边界


原Z4Q主引擎完整推进，疑似、合并、post pending、取消和缺测仅改变独立事件证据缓存。冻结pre不受匿名群组污染。本轮修复的是DS34共用机制的退化；原Z4Q本身仍可能有错误。新增深度必须全矩阵合格、三帧一致且有明确margin，并通过原生命周期和组外状态检查。失败保留自己的完整已推进状态，不从外部B0复制整套engine。没有几何单独提交、永久锁ID或只改输出文件。


冻结条件：12秒历史、10秒事件、原scan_v4及首分离q、原两候选/二维OLS/深度权重0.25、30帧首次发布缓冲；新增可靠门槛各pre≥3连续测量、预测scale≤60mm、加权深度margin≥0.10、3个post各支持同一映射。不是实时部署；q后证据不写入q测量。


## 完整指标

| 来源 | 分支 | IDF1 | HOTA | AssA | IDSW | FP | FN |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Feeding1471 | SAM3_NATIVE | 80.976760 | 79.964056 | 71.530499 | 108 | 487 | 985 |
| Feeding1471 | Z4Q_FROZEN | 81.716806 | 79.859851 | 71.341782 | 132 | 487 | 985 |
| Feeding1471 | DEPTH_OFF | 81.716806 | 79.859851 | 71.341782 | 132 | 487 | 985 |
| Feeding1471 | DEPTH_OVERRIDE | 81.716806 | 79.859851 | 71.341782 | 132 | 487 | 985 |
| Feeding1471 | ARCHIVED_DS34_EVENT_RGBD | 80.986897 | 79.650290 | 70.983535 | 130 | 487 | 985 |
| fishsa_development_8400 | SAM3_NATIVE | 91.313288 | 73.346143 | 69.186768 | 5 | 194 | 323 |
| fishsa_development_8400 | Z4Q_FROZEN | 99.333472 | 77.829488 | 77.907638 | 6 | 194 | 323 |
| fishsa_development_8400 | DEPTH_OFF | 99.333472 | 77.829488 | 77.907638 | 6 | 194 | 323 |
| fishsa_development_8400 | DEPTH_OVERRIDE | 99.333472 | 77.829488 | 77.907638 | 6 | 194 | 323 |
| fishsa_development_8400 | ARCHIVED_DS34_EVENT_RGBD | 92.040409 | 74.526556 | 71.432733 | 5 | 194 | 323 |
| fishsa_validation_2888 | SAM3_NATIVE | 76.456444 | 66.435529 | 55.196059 | 8 | 298 | 423 |
| fishsa_validation_2888 | Z4Q_FROZEN | 80.697587 | 69.243869 | 60.074321 | 9 | 298 | 423 |
| fishsa_validation_2888 | DEPTH_OFF | 80.697587 | 69.243869 | 60.074321 | 9 | 298 | 423 |
| fishsa_validation_2888 | DEPTH_OVERRIDE | 80.697587 | 69.243869 | 60.074321 | 9 | 298 | 423 |
| fishsa_validation_2888 | ARCHIVED_DS34_EVENT_RGBD | 75.819114 | 64.796015 | 52.584202 | 11 | 298 | 423 |
| L3 | SAM3_NATIVE | 72.426787 | 75.362607 | 94.259655 | 1 | 14677 | 0 |
| L3 | Z4Q_FROZEN | 74.745256 | 77.171558 | 98.839045 | 2 | 14677 | 0 |
| L3 | DEPTH_OFF | 74.745256 | 77.171558 | 98.839045 | 2 | 14677 | 0 |
| L3 | DEPTH_OVERRIDE | 74.745256 | 77.171558 | 98.839045 | 2 | 14677 | 0 |
| L3 | ARCHIVED_DS34_EVENT_RGBD | 74.745256 | 77.171558 | 98.839045 | 2 | 14677 | 0 |
| LW | SAM3_NATIVE | 60.613534 | 66.369067 | 77.555121 | 7 | 16493 | 28 |
| LW | Z4Q_FROZEN | 64.329395 | 68.991721 | 83.805597 | 10 | 16493 | 28 |
| LW | DEPTH_OFF | 64.329395 | 68.991721 | 83.805597 | 10 | 16493 | 28 |
| LW | DEPTH_OVERRIDE | 64.329395 | 68.991721 | 83.805597 | 10 | 16493 | 28 |
| LW | ARCHIVED_DS34_EVENT_RGBD | 58.687284 | 65.220291 | 74.893569 | 10 | 16493 | 28 |



## 新分支真实差值

| 来源 | 对照 | ΔIDF1(pp) | ΔHOTA(pp) | ΔAssA(pp) | ΔIDSW | ΔFP | ΔFN |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Feeding1471 | SAM3_NATIVE | +0.740046 | -0.104205 | -0.188717 | +24.000000 | +0.000000 | +0.000000 |
| Feeding1471 | Z4Q_FROZEN | +0.000000 | +0.000000 | +0.000000 | +0.000000 | +0.000000 | +0.000000 |
| Feeding1471 | DEPTH_OFF | +0.000000 | +0.000000 | +0.000000 | +0.000000 | +0.000000 | +0.000000 |
| fishsa_development_8400 | SAM3_NATIVE | +8.020185 | +4.483345 | +8.720871 | +1.000000 | +0.000000 | +0.000000 |
| fishsa_development_8400 | Z4Q_FROZEN | +0.000000 | +0.000000 | +0.000000 | +0.000000 | +0.000000 | +0.000000 |
| fishsa_development_8400 | DEPTH_OFF | +0.000000 | +0.000000 | +0.000000 | +0.000000 | +0.000000 | +0.000000 |
| fishsa_validation_2888 | SAM3_NATIVE | +4.241143 | +2.808340 | +4.878262 | +1.000000 | +0.000000 | +0.000000 |
| fishsa_validation_2888 | Z4Q_FROZEN | +0.000000 | +0.000000 | +0.000000 | +0.000000 | +0.000000 | +0.000000 |
| fishsa_validation_2888 | DEPTH_OFF | +0.000000 | +0.000000 | +0.000000 | +0.000000 | +0.000000 | +0.000000 |
| L3 | SAM3_NATIVE | +2.318468 | +1.808950 | +4.579391 | +1.000000 | +0.000000 | +0.000000 |
| L3 | Z4Q_FROZEN | +0.000000 | +0.000000 | +0.000000 | +0.000000 | +0.000000 | +0.000000 |
| L3 | DEPTH_OFF | +0.000000 | +0.000000 | +0.000000 | +0.000000 | +0.000000 | +0.000000 |
| LW | SAM3_NATIVE | +3.715862 | +2.622654 | +6.250476 | +3.000000 | +0.000000 | +0.000000 |
| LW | Z4Q_FROZEN | +0.000000 | +0.000000 | +0.000000 | +0.000000 | +0.000000 | +0.000000 |
| LW | DEPTH_OFF | +0.000000 | +0.000000 | +0.000000 | +0.000000 | +0.000000 | +0.000000 |



恢复原Z4Q成绩只称止损，不能把相对归档DS34的提升算新增深度收益。DEPTH_OFF完整状态与原Z4Q逐帧相等，深度增量只按DEPTH_OVERRIDE相对该同底座对照解释。


## 实际事件与提交


深度合格提案 0；实际新增提交 0；对原Z4Q改变发布帧 0。

| 来源 | 事件数 | 有q | 改变帧 | 原因分布 |
| --- | --- | --- | --- | --- |
| feeding_000000_000199 | 1 | 0 | 0 | {"UNKNOWN_EOF_EVENT_EVIDENCE_ONLY": 1} |
| feeding_000351_000555 | 6 | 3 | 0 | {"UNKNOWN_DEADLINE": 3, "CANCELLED": 2, "UNKNOWN_EOF_EVENT_EVIDENCE_ONLY": 1} |
| feeding_000701_001060 | 7 | 3 | 0 | {"UNKNOWN_DEADLINE": 2, "CANCELLED": 3, "CANCELLED_NO_PERSISTENT_COLLAPSE": 1, "COMMON_DEPTH_UNAVAILABLE": 1} |
| feeding_001201_001906 | 7 | 6 | 0 | {"UNKNOWN_DEADLINE": 5, "OUT_OF_SCOPE": 1, "COMMON_DEPTH_UNAVAILABLE": 1} |
| fishsa_development_8400 | 12 | 8 | 0 | {"UNKNOWN_DEADLINE": 6, "CANCELLED": 4, "NO_COMPLETE_ENDPOINTS": 1, "DEPTH_FORECAST_TOO_UNCERTAIN": 1} |
| fishsa_validation_2888 | 11 | 7 | 0 | {"UNKNOWN_DEADLINE": 4, "CANCELLED": 2, "CANCELLED_NO_PERSISTENT_COLLAPSE": 2, "DEPTH_FORECAST_TOO_UNCERTAIN": 1, "COMMON_DEPTH_UNAVAILABLE": 1, "UNKNOWN_POST_SOURCE_BREAK": 1} |
| L3 | 11 | 5 | 0 | {"CANCELLED_NO_PERSISTENT_COLLAPSE": 2, "UNKNOWN_DEADLINE": 5, "CANCELLED": 1, "OUT_OF_SCOPE": 2, "TIMEOUT": 1} |
| LW | 20 | 10 | 0 | {"UNKNOWN_DEADLINE": 4, "TIMEOUT": 1, "NO_COMPLETE_ENDPOINTS": 1, "OUT_OF_SCOPE": 6, "CANCELLED": 2, "UNKNOWN_POST_SOURCE_BREAK": 1, "COMMON_DEPTH_UNAVAILABLE": 2, "TOO_FEW_CONTIGUOUS_PRE_DEPTH_OBSERVATIONS": 2, "UNKNOWN_EOF_EVENT_EVIDENCE_ONLY": 1} |



详细原始选择/未提交原因/第一帧实际映射/物理参考、公共起源与切换均保存在RESULTS、各EVENTS/TRANSACTIONS/PUBLISH_LEDGER/EVENT_AUDIT/SWITCHES。物理preanchor、prefragment、postfragment和公共起源独立列出。未提交与UNKNOWN不记作恢复正确。


## 工程证据与输入限制


14项状态/可靠性测试、6项真实来源与自洽hash篡改、2项真实切片发现的空评估回归检查通过。首次评分检查发现mask digest适配不同（带dtype/shape头与只哈数组）；已在正式冻结前恢复原规范，失败日志保留。第一次开发前缀在缺失pre返回空scores时读取不存在的模态权重导致异常；已在冻结前修复，失败前缀保留不评分，重跑写入新目录。真实前缀验收保住开发q3902的7→0与验证q2188的8→3原BirthRefine，并在q2689弱增强证据时不提交几何交换；这属于工程证据。正式每帧输入/质量证书/实际mask、事件每个纳入观测版本、重算选择、全部状态与第一次发布绑定均在访问GT前验证。


使用原始深度，whole/core混层、来源互斥、数量/覆盖、WLS预测尺度逐项保留。非零和高有效覆盖不等于物理表面身份。无RGB关联、无场景流、无轮廓补画。上游SAM3保存源的未来上下文与未记载producer reset保持UNKNOWN。L3/LW参考是弱预测派生，不称盲测或跨域物理身份正确。


## 费用、复现与同步


新增模型HTTP=0、费用=0，无API key/smoke/GPU/训练/SAM3/补全服务。精确代码、输入、实际常数、环境、评分门槛见RUNTIME_FREEZE与各FREEZE；START/END、完整预测/访问seal和日志见run。公开只同步数值预测token与记录；私有原始RGB、depth、mask、GT raster不公开。私有可视化实际路径/字节/SHA和复现依赖列于PRIVATE_INVENTORY。科学commit及实际origin/main/全部公开文件核验见交付收据；不force push、不覆盖旧seal。


## 未完成项


本轮没有新增盲测、三维物理精度标定、不可见轮廓恢复或模型调用。深度未达到性能目标时保留负结论，不用工程PASS替代方法收益。


## 唯一未执行下一步


在保留本轮原Z4Q权威状态的底座上，先统计真实错误关联处能否形成可区分的局部双鱼原始深度证据；按缺测、混层、宽预测及深度重叠分解信息上限，证据足够才设计下一次关联改变。该步骤未启动。
