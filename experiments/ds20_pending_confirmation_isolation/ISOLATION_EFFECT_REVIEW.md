# DS20 LW确认隔离的实际影响复盘

本审查只读取已封存正式trace、预测来源数值与独立评分；未修改控制器、旧封存或重新回放。LW事务local帧比原始帧大1；下文除SWITCH表外均为local帧。

## 不是简单晚一帧

旧ACTIVITY_RETURN在3268–3272把n144→133确认到5并提交。新ACTIVITY_ISOLATED在3269记录IDENTITY_VERSION_CHANGED：输入身份版本由首次公开前的None/None变为144/1，独立语义键从1重新开始，3272只有4次。3273真实n144 neighbors=[1]，路由记录CURRENT_QUALITY_OR_CONTACT_RISK，原D1不再产生该候选，确认中断。3276、3278再次接触；3283–3286又达到1/2/3/4，但3287原矩阵改选普通144→54，protected确认清除。后续还有接触和候选迁移，不能用单帧延迟解释最后状态。

n145首次发布为145在3305；3338–3342原完整proposal矩阵连续选择145→133，source/identity版本与精确旧anchor3110未变，计数1..5，3342实际stage/commit。新结果因此是另一个来源n145的返回，延迟37帧；旧n144返回延迟4帧。模型调用为0，候选成本/深度权重/5次确认/窗口未调整。[逐帧trace](run/LW/public/TRANSACTIONS.part003.jsonl.gz)

## 物理评分与性能边界

旧n144→133及新n145→133的query/实际bank/public原点关系均UNKNOWN，独立评分都是UNSCORABLE。不能称新返回错误，也不能称旧返回正确。[实际返回评分](run/LW/public/LOCAL_RETURN_AUDIT.json)

| 对照 | IDF1 | HOTA | AssA | IDSW | FP | FN |
|---|---:|---:|---:|---:|---:|---:|
| ACTIVITY_RETURN | 60.613534 | 66.273266 | 77.331389 | 8 | 16493 | 28 |
| ACTIVITY_ISOLATED | 60.613534 | 66.270067 | 77.323924 | 9 | 16493 | 28 |

新−旧：IDF1=0、HOTA−0.003199、AssA−0.007465、IDSW+1，FP/FN不变。组合深度MIXED两列指标仍相同。[完整同源指标](run/LW/public/METRICS.json)

## 唯一新增切换的真实状态链

| 原始帧 | 参考ID | 当前native | 公共ID切换 | 新增/消除 |
|---:|---:|---:|---|---|
| 3427 | 1 | 150 | 150→144 | 新增1；消除0 |

实际自动审计显示local3428的D1以旧anchor3348:n144/public144，五次确认后持久提交150→144。新分支保留n144自己的bank；旧分支早前已把n144归到133，旧分支没有150→144提交。这解释了新增切换的状态传递路径，而不是把最后输出文件换号。该自动动作的bank及public原点评分仍UNSCORABLE。[真实自动提交](run/LW/public/AUTOMATIC_RECONNECT_AUDIT.json)；[逐次SWITCH](run/LW/public/SWITCHES.json)

来源真实路径、字节、SHA及所选原始JSON行SHA均在[审查记录](ISOLATION_EFFECT_REVIEW.json)。源码、预测和评分不变。本报告是冻结结果的原因诊断，不授权事后调参或重新回放。
