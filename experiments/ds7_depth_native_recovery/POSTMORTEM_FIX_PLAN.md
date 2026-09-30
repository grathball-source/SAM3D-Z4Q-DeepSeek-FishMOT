# DS7复盘后的实际修复与当前执行范围

## 已执行：DS7发布与来源修复

DS6五个q的十条新增IDSW来自猜配后的preview：旧NO_ID_CHANGE比较的是内部preview，实际公开交换了持续source身份。DS7保持匿名pre/group/post及bank保护，公开与q预览使用本分支合法native或已提交event alias，未获准映射从本分支因果当前步释放。接受映射仍走原子事务，组外alias、所有mask和身份占用保留。动作日志分列合法baseline、前帧公开ID及native差异。

原始实测与v2模型估计分层；实测合格优先，推断单独使用，不混合中位数。P0/P1/P2在全部1471帧公开预测精确等于native，19个q均无accept。IDF1/HOTA/AssA为80.9768/79.9641/71.5305，IDSW108。这完成共同底座止损，没有实现深度超过native。

## 实际阻断：固定核心ROI

38条q-post中24 retained、0 inferred、14 NONE；14条均n<16，13条固定7×7独占core面积已小于16，12条不排除重叠的7×7腐蚀面积也小于16。原mask面积271–460像素、内切圆直径代理7.21–10.20像素；固定ROI内没有足够像素时，更多补孔无法满足冻结资格。该结论针对预测mask采样几何，不认证鱼体深度表面。

F1280新增较老inferred历史点属于两点LAST_VALUE历史，没有参加WLS均值；预测均值来自较新retained点，尺度未变。F1745的8.36/8.15候选odds不足9，不能据其曝光答案放宽门槛。完整测量、历史与逐q阻断见[测量复盘](POSTRUN_MEASUREMENT_REVIEW.json)和[失败复盘](POSTRUN_FAILURE_REVIEW.md)。

## 已启动：DS8只改变ROI

当前唯一完整试验见[DS8 PLAN](../ds8_adaptive_depth_core/PLAN.md)。先排除当前SAM3 mask重叠，逐8连通片计算精确L2距离，distance≥max(1.5,min(3.0,0.5×该片最大distance))。全部片保留，图外补零，不填洞。公式只由当前mask几何确定，depth与GT不参与选区。

继续同源四段1471帧、39208原对象及native/D2/P0/P1/P2完整对照。触发、首次q、二维项、发布和事务、历史版本、实测/推断分层及缺测模型保持DS7；n≥16、fraction≥0.2、尺度≤60mm、推断60mm假定、depth权重0.25和候选gap≥log9全部不变。固定9:1不因已曝光GT降至8:1。

预测全封存后独立评分。主目标仍为P2相对同源native的IDF1/HOTA/AssA都上升且IDSW不增，同时报告相对P0/P1和DS7的差异及所有失败、弃权和真实状态动作。自适应几何与采样增加本身不是收益；最终判断和未来一步由DS8封存报告给出。

## 边界

真正v2修复深度上游使用RGB及前后帧，是已曝光开发集离线诊断；没有使用v3标注补孔，但不构成因果在线、盲测或跨录像泛化。独立物理表面/mm真值仍缺失。L3/LW及旧来源条件差异只是跨实验归纳假设，本轮未通过同源隔离实验验证其退化归因。DS7冻结代码、输入、预测、seal和metrics保持原件。
