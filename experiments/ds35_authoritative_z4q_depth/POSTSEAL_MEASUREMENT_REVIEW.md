# DS35 封存后深度可用性复盘

本程序在八段预测与访问全部封存之后新增，只读数值证书与事件记录。未读取GT或像素，未改关联、门槛、评分及封存代码。

## 真实计数

```json

{
  "counts": {
    "events": 75,
    "with_q": 42,
    "complete_endpoint_cost": 9,
    "common_depth_available": 4,
    "eligible_proposals": 0,
    "actual_commits": 0,
    "pre_references": 150,
    "unknown_pre_references": 6,
    "pre_samples": 930,
    "pre_usable_depth_points": 823,
    "partial_depth_pre_with_at_least_three_valid_points": 8,
    "partial_depth_pre_without_observed_mixture_or_ownership_risk": 5
  },
  "decision_reasons": {
    "UNKNOWN_EOF_EVENT_EVIDENCE_ONLY": 3,
    "UNKNOWN_DEADLINE": 29,
    "CANCELLED": 14,
    "CANCELLED_NO_PERSISTENT_COLLAPSE": 5,
    "COMMON_DEPTH_UNAVAILABLE": 5,
    "OUT_OF_SCOPE": 9,
    "NO_COMPLETE_ENDPOINTS": 2,
    "DEPTH_FORECAST_TOO_UNCERTAIN": 2,
    "UNKNOWN_POST_SOURCE_BREAK": 2,
    "TIMEOUT": 2,
    "TOO_FEW_CONTIGUOUS_PRE_DEPTH_OBSERVATIONS": 2
  },
  "forecast_reasons": {
    "INVALID_OR_UNRELIABLE_HISTORY": 24,
    "WLS_LINEAR_TIME": 48,
    "NO_SLOPE_LAST_VALUE": 30,
    "EXPIRED_OR_NONCAUSAL_HISTORY": 6
  }
}

```

计数分别区分：自动事件、有首分离q、能构建完整端点成本、共同深度可用、深度门槛通过及真实提交。它们不等价。

## 缺测与身份风险边界

有至少3个有效深度点、同时有不合格深度点的合格连续pre片段：8；其中未发现混层或来源占用风险者：5。

这只是下一轮候选机制的观测机会，不运行新的WLS，不把不合格点改为有效，不把混层/来源风险当成普通缺测并跳过，也不跨身份版本或风险连接两端。

未知pre来源不能靠换锚变成合格；宽预测、相近深度和混合掩码不提供独立身份认证。恢复原Z4Q是止损，不是新增深度收益。

逐事件pre有效数量、失败理由、共同权重、预测状态与门槛实值均在JSON中保留。正式指标以独立METRICS为准。
