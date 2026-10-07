# DS37 稳定深度水平＋因果漂移尺度：完整同源回放

主判定：**NO_PUBLICATION_OR_METRIC_INCREMENT_STOP_FROZEN_VERSION**。完整20,098帧、四分支自身状态回放与官方评分完成。新增模型HTTP/smoke、费用、训练、SAM3推理、深度补全、GPU和服务器作业均0。

## 改了什么与工程边界

保留原Z4Q全部二维/深度候选规则和状态事务；在真实D1_DELAYED/BIRTH_REFINE矩阵入口只增加可靠深度冲突单边否决。WLS对照逐帧复现旧DS32发布、原物理状态及完整深度来源状态。新分支使用同一精确anchor、连续版本和质量门槛，将短窗速度均值外推改为十点加权稳定水平；尺度由过去dz²/dt的median与225mm²/s先验共同增长，保留15mm测量floor。不除样本数、不clip大尺度、不挑峰、不跨风险/版本、不把接近认证为同鱼。公式/每点出处/原WLS斜率/实际dt均留在事务与EDGE_AUDIT。

20项必要检查通过，真实F159 source→query→状态→首次发布及关闭模块复现完成。哈希路径和递归不可变source标准JSON字节缓存保持160帧所有科学trace逐行一致。只缓存被冻结sample完整内容，容器/engine每次重新读取；每500帧对照完整标准序列化，WLS每帧与旧档完整状态SHA核验。首次0帧源码哈希误拦截及v2未评分部分保留；随后修正“有效历史被旧WLS负外推连带判无效”的工程耦合。原WLS负预测保持负值/不可用诊断，新稳定水平独立有效，版本/时间/质量检查不变。v3输入/代码/评分重新冻结，四个来源工作进程均从帧1开始，不复用旧部分状态/输出。未按GT或指标调参数。详见REPORT_NOTES。工程通过不等于深度有效。

## 全部真实指标

|来源/帧数|分支|IDF1|HOTA|AssA|IDSW|FP|FN|

|---|---|---:|---:|---:|---:|---:|---:|

|feeding_000000_000199 / 200|SAM3_NATIVE|92.889759|91.362522|88.085877|10|76|143|

|feeding_000000_000199 / 200|Z4Q_FROZEN|92.125617|90.483748|86.399664|12|76|143|

|feeding_000000_000199 / 200|Z4Q_WLS_VETO|92.125617|90.483748|86.399664|12|76|143|

|feeding_000000_000199 / 200|Z4Q_LEVEL_VETO|92.125617|90.483748|86.399664|12|76|143|

|feeding_000351_000555 / 205|SAM3_NATIVE|82.927271|78.582844|72.182690|22|148|201|

|feeding_000351_000555 / 205|Z4Q_FROZEN|82.891042|78.147798|71.429933|24|148|201|

|feeding_000351_000555 / 205|Z4Q_WLS_VETO|82.891042|78.147798|71.429933|24|148|201|

|feeding_000351_000555 / 205|Z4Q_LEVEL_VETO|82.891042|78.147798|71.429933|24|148|201|

|feeding_000701_001060 / 360|SAM3_NATIVE|77.428039|75.545022|65.006580|36|154|278|

|feeding_000701_001060 / 360|Z4Q_FROZEN|75.636778|73.560905|61.642162|42|154|278|

|feeding_000701_001060 / 360|Z4Q_WLS_VETO|75.636778|73.560905|61.642162|42|154|278|

|feeding_000701_001060 / 360|Z4Q_LEVEL_VETO|75.636778|73.560905|61.642162|42|154|278|

|feeding_001201_001906 / 706|SAM3_NATIVE|78.839951|78.727248|68.089322|40|109|363|

|feeding_001201_001906 / 706|Z4Q_FROZEN|81.525935|79.892513|70.113143|54|109|363|

|feeding_001201_001906 / 706|Z4Q_WLS_VETO|81.525935|79.892513|70.113143|54|109|363|

|feeding_001201_001906 / 706|Z4Q_LEVEL_VETO|81.525935|79.892513|70.113143|54|109|363|

|fishsa_development_8400 / 8400|SAM3_NATIVE|91.313288|73.346143|69.186768|5|194|323|

|fishsa_development_8400 / 8400|Z4Q_FROZEN|99.333472|77.829488|77.907638|6|194|323|

|fishsa_development_8400 / 8400|Z4Q_WLS_VETO|99.333472|77.829488|77.907638|6|194|323|

|fishsa_development_8400 / 8400|Z4Q_LEVEL_VETO|99.333472|77.829488|77.907638|6|194|323|

|fishsa_validation_2888 / 2888|SAM3_NATIVE|76.456444|66.435529|55.196059|8|298|423|

|fishsa_validation_2888 / 2888|Z4Q_FROZEN|80.697587|69.243869|60.074321|9|298|423|

|fishsa_validation_2888 / 2888|Z4Q_WLS_VETO|80.697587|69.243869|60.074321|9|298|423|

|fishsa_validation_2888 / 2888|Z4Q_LEVEL_VETO|80.697587|69.243869|60.074321|9|298|423|

|L3 / 3710|SAM3_NATIVE|72.426787|75.362607|94.259655|1|14677|0|

|L3 / 3710|Z4Q_FROZEN|74.745256|77.171558|98.839045|2|14677|0|

|L3 / 3710|Z4Q_WLS_VETO|74.745256|77.171558|98.839045|2|14677|0|

|L3 / 3710|Z4Q_LEVEL_VETO|74.745256|77.171558|98.839045|2|14677|0|

|LW / 3629|SAM3_NATIVE|60.613534|66.369067|77.555121|7|16493|28|

|LW / 3629|Z4Q_FROZEN|64.329395|68.991721|83.805597|10|16493|28|

|LW / 3629|Z4Q_WLS_VETO|64.329395|68.991721|83.805597|10|16493|28|

|LW / 3629|Z4Q_LEVEL_VETO|64.329395|68.991721|83.805597|10|16493|28|

Feeding四段独立ID命名空间汇总（1471帧）：

|分支|IDF1|HOTA|AssA|IDSW|FP|FN|

|---|---:|---:|---:|---:|---:|---:|

|SAM3_NATIVE|80.976760|79.964056|71.530499|108|487|985|

|Z4Q_FROZEN|81.716806|79.859851|71.341782|132|487|985|

|Z4Q_WLS_VETO|81.716806|79.859851|71.341782|132|487|985|

|Z4Q_LEVEL_VETO|81.716806|79.859851|71.341782|132|487|985|

## LEVEL相对同源参照的真实差值

|来源|相对参照|ΔIDF1|ΔHOTA|ΔAssA|ΔIDSW|ΔFP|ΔFN|

|---|---|---:|---:|---:|---:|---:|---:|

|feeding_000000_000199|SAM3_NATIVE|-0.764141|-0.878774|-1.686213|+2|+0|+0|

|feeding_000000_000199|Z4Q_FROZEN|+0.000000|+0.000000|+0.000000|+0|+0|+0|

|feeding_000000_000199|Z4Q_WLS_VETO|+0.000000|+0.000000|+0.000000|+0|+0|+0|

|feeding_000351_000555|SAM3_NATIVE|-0.036229|-0.435047|-0.752757|+2|+0|+0|

|feeding_000351_000555|Z4Q_FROZEN|+0.000000|+0.000000|+0.000000|+0|+0|+0|

|feeding_000351_000555|Z4Q_WLS_VETO|+0.000000|+0.000000|+0.000000|+0|+0|+0|

|feeding_000701_001060|SAM3_NATIVE|-1.791261|-1.984117|-3.364418|+6|+0|+0|

|feeding_000701_001060|Z4Q_FROZEN|+0.000000|+0.000000|+0.000000|+0|+0|+0|

|feeding_000701_001060|Z4Q_WLS_VETO|+0.000000|+0.000000|+0.000000|+0|+0|+0|

|feeding_001201_001906|SAM3_NATIVE|+2.685983|+1.165266|+2.023821|+14|+0|+0|

|feeding_001201_001906|Z4Q_FROZEN|+0.000000|+0.000000|+0.000000|+0|+0|+0|

|feeding_001201_001906|Z4Q_WLS_VETO|+0.000000|+0.000000|+0.000000|+0|+0|+0|

|fishsa_development_8400|SAM3_NATIVE|+8.020185|+4.483345|+8.720871|+1|+0|+0|

|fishsa_development_8400|Z4Q_FROZEN|+0.000000|+0.000000|+0.000000|+0|+0|+0|

|fishsa_development_8400|Z4Q_WLS_VETO|+0.000000|+0.000000|+0.000000|+0|+0|+0|

|fishsa_validation_2888|SAM3_NATIVE|+4.241143|+2.808340|+4.878262|+1|+0|+0|

|fishsa_validation_2888|Z4Q_FROZEN|+0.000000|+0.000000|+0.000000|+0|+0|+0|

|fishsa_validation_2888|Z4Q_WLS_VETO|+0.000000|+0.000000|+0.000000|+0|+0|+0|

|L3|SAM3_NATIVE|+2.318468|+1.808950|+4.579391|+1|+0|+0|

|L3|Z4Q_FROZEN|+0.000000|+0.000000|+0.000000|+0|+0|+0|

|L3|Z4Q_WLS_VETO|+0.000000|+0.000000|+0.000000|+0|+0|+0|

|LW|SAM3_NATIVE|+3.715862|+2.622654|+6.250476|+3|+0|+0|

|LW|Z4Q_FROZEN|+0.000000|+0.000000|+0.000000|+0|+0|+0|

|LW|Z4Q_WLS_VETO|+0.000000|+0.000000|+0.000000|+0|+0|+0|

## 因果链与物理诊断

LEVEL实际删除2条原合法边；当前决策相对同一自身前态原策略改变发布0帧；相对独立原Z4Q改变0帧。实际删除物理结果{'DIFFERENT_CORRECT_CONFLICT': 2}。LEVEL实际持久动作物理结果{'WRONG': 17, 'UNSCORABLE': 57, 'CORRECT': 16}，这是整个原Z4Q＋否决分支的动作，不把原Z4Q恢复算成新增深度提交。

|来源|合法查询边|WLS双深度可用边|LEVEL双深度可用边|LEVEL原始冲突|LEVEL实际删除|LEVEL改帧|

|---|---:|---:|---:|---:|---:|---:|---:|

|feeding_000000_000199|31|0|46|12|0|0|

|feeding_000351_000555|46|0|37|16|0|0|

|feeding_000701_001060|156|0|257|83|0|0|

|feeding_001201_001906|328|24|714|149|2|0|

|fishsa_development_8400|11|0|7|0|0|0|

|fishsa_validation_2888|14|0|85|0|0|0|

|L3|135|1|431|4|0|0|

|LW|831|109|1207|0|0|0|

双深度可用边的分母包含原不合法边，合法性与信息可用性分列；全部缺失与被拒原因见MECHANISM_AUDIT。原始冲突不等于实际矩阵删除，更不等于选中动作改变。每次切换新增/消除/common逐条重新匹配，SWITCH_CHANGES保留完整记录，没有用净差冒充错误次数。

原持久动作的事后正确/错误/不可评分与LEVEL来源解释：
```json
{
  "CORRECT": {
    "original_actions": 16,
    "matching_query_edges": 16,
    "query_reason_counts": {
      "TARGET_INSUFFICIENT_CONTIGUOUS_HISTORY": 7,
      "NO_RELIABLE_DEPTH_CONFLICT_KEEP_ORIGINAL_EDGE": 8,
      "TARGET_FORECAST_TOO_BROAD": 1
    },
    "vetoed_edges": 0,
    "actual_public_kept": 16
  },
  "WRONG": {
    "original_actions": 17,
    "matching_query_edges": 17,
    "query_reason_counts": {
      "NO_RELIABLE_DEPTH_CONFLICT_KEEP_ORIGINAL_EDGE": 8,
      "CURRENT_DEPTH_UNRELIABLE": 2,
      "TARGET_FORECAST_TOO_BROAD": 4,
      "TARGET_INSUFFICIENT_CONTIGUOUS_HISTORY": 2,
      "TARGET_ANCHOR_CHANGED_OR_UNREGISTERED_REFERENCE": 1
    },
    "vetoed_edges": 0,
    "actual_public_kept": 17
  },
  "UNSCORABLE": {
    "original_actions": 57,
    "matching_query_edges": 57,
    "query_reason_counts": {
      "TARGET_ANCHOR_CHANGED_OR_UNREGISTERED_REFERENCE": 5,
      "TARGET_FORECAST_TOO_BROAD": 5,
      "NO_RELIABLE_DEPTH_CONFLICT_KEEP_ORIGINAL_EDGE": 22,
      "TARGET_INSUFFICIENT_CONTIGUOUS_HISTORY": 24,
      "CURRENT_DEPTH_UNRELIABLE": 1
    },
    "vetoed_edges": 0,
    "actual_public_kept": 57
  }
}
```

原动作的评分reference与当前depth bank anchor可能不是同一帧，两个引用分别记录，不能无条件沿用旧答案。UNSCORABLE保持缺失，不叫安全保护成功。全部预测、实际START/访问/事务seal后才读取既有曝光GT/弱参考；不读GT raster或新的留出test。

## 真实可视化、耗时和复现

visuals/METRICS.svg和ELIGIBLE_CONFLICTS.svg为公开数值图。所有实际LEVEL矩阵删除、原Z4Q错误动作以及每来源最早可靠合法控制生成真实raw depth/已发布ID的anchor、决策前、当前、后一帧对照。后一帧只用于封存后展示，未进入当前决策，也没有修改过去发布。原像素只在private/cases；PRIVATE_VISUALS/PRIVATE_INVENTORY列真实路径、字节、SHA、原始depth与保存mask绑定和复现依赖，未公开RGB/GT raster。

来源工作进程累计8952.893秒（四个来源并行CPU工作进程，不能当作端到端wall time）。每来源处理和三控制流程合计首次发布延迟见RESULTS.timing，未测实际在线系统，也不称实时部署。

以当前代码的空输出目录及本轮固定基点提供相同私有DS14原观测/mask/原始深度、DS18证书和只读旧DS32/DS31封存；运行必要checks及真实slice、freeze、orchestrate。已运行目录不能覆盖。全部评分数学、包括动态导入的DS1 clear_step源码在START前绑定。

## 分层判定与未完成项

工程：全段、旧对照精确复现、单边/dummy/版本/preview/首次发布、全部seal与独立评分通过。输入：原depth同ROI、source去重、量测质量与版本可追溯；单mask表面物理身份、producer reset与传感器标定仍UNKNOWN。深度增量：只按同源真实指标与实际状态修改判断，旧WLS零作用仍保留。

L3/LW使用未独立确认的预测派生参考，只能弱诊断；FishSA开发/验证是同录像曝光来源，Feeding也是已曝光片段，不能称新盲测或跨数据集泛化提升。数值尺度不是已标定概率，宽尺度覆盖不叫物理准确率。未完成边界：Depth performance above same-source original Z4Q is not established。

## 唯一下一步（未启动）

Audit real original-Z4Q wrong accepted edges with paired competing candidate depth distributions before choosing a different depth representation; do not reduce the conflict gate solely to hit these labels.

## 候选、状态与发布分层

STATE_EFFECT_REVIEW独立逐行回查了全部实际事务。零发布增量不代表完整engine状态不变；原engine的pending和诊断计数也属于状态。原合法边的真实删除、同前态状态SHA改变、未确认提议改变、已确认持久提交和发布分别计数。不能用零改帧推出零状态作用。详细真实数字和逐边出处见STATE_EFFECT_REVIEW与DEEP_REVIEW。

## main交付

代码、配置、必要测试及失败记录、完整公开日志/预测/逐边结果/指标/报告和聚合图普通提交到main，之后实际push并核验远端ref与每个公开blob。具体commit和远端SHA由REMOTE_VERIFICATION记录，私有像素不在Git。
