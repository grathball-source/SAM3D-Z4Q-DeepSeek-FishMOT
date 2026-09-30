# DS6 多深度片段的完整跟踪性能试验

## 冻结问题与假设

DS5说明：掩码内可能出现多个原始深度表面；最大点数的表面不一定属于目标，低MAD也不能证明身份。这里验证一个最小改变：保留匿名深度片段，使用进入前同版本连续历史，在首分离帧联合比较两种映射。物理表面归属仍是UNKNOWN，不作为运行或评分的资格门。

## 输入与范围

SOURCE_OLD原始SAM3预测、原始depth_mm与source_index/native深度来源检查、NE1原生优先与S0-P首次发布。固定全部四段0–199、351–555、701–1060、1201–1906，共1471帧。它们均已用于开发或审计；本轮是暴露开发集性能试验，不是盲测或跨录像泛化。复用已逐字节/逐帧核验的观测、profile、assignment、scan缓存，重新独立运行所有分支。原producer批次未来支持情况UNKNOWN；本轮控制器与深度选择只读当前及过去。

当前manifest后加深度修复元数据，旧DS1整体manifest哈希已改变。INPUT_REVIEW保留此事实；逐帧原预测、raw NPZ、时刻、掩码与缓存绑定重新通过。新冻结绑定当前manifest，绝不打开v3或annotation instance_id。

## 五分支与因果对照

| 分支 | 作用 |
|---|---|
| SAM3_NATIVE | 原生同源公开身份与全部原mask |
| D0_GEOMETRY | 现有NE1/S0-P保护与二维数值关联；公共控制器仍保留原depth质量规则 |
| D2_CORE_FROZEN | DS1原core测量、DepthState和dynamic_choice；严格对照旧输出 |
| D4_F6_SCALAR | F6选点、保守单片pre历史与共同缺测模型；q用F6整体median/MAD |
| D5_MULTIFRAGMENT | 与D4相同规则、独立自身状态；q用合格匿名片段等权混合似然 |

主表必须包含同源SAM3与D5−D0/D2/D4。D5−D4在相同事件状态下只隔离q多片似然；实际状态分叉后全段差异包含此前选择延续。因此同时保存D5自身状态上的scalar影子结果。D4−D2同时改变选点、历史认证和缺测策略，不能归因单一滤波参数。D0不是端到端无深度系统。

## 固定算法

复用DS4 F6函数体，fresh isolated globals，不改旧模块或常量。原native>5000mm为SUSPECT并仅在工作副本移除；不是传感器有效量程认证。背景annulus5–20px、邻鱼margin3、5次Huber IRLS、background floor1mm、contrast≥max(30mm,3sigma)、3×3closing仅作support，foreground与dominance规则均冻结。

只对实际F6 selected原始有效点构建8邻接depth图；边差≤30mm。每片保留计数、selected点比例、median/MAD、位置、可追溯fact/piece引用；资格n≥16、fraction≥.2、max(15mm,1.4826MAD)≤60mm。closing不填补测量点。碎片标签是匿名测量解释，不是身份。

两个新分支pre只有恰好一个合格片才进入原DepthState；多片全部事实保留但该时刻历史值UNKNOWN，中断当前连续片段。缓存30帧、同generation/public/epoch、最近连续片最多10点、原真实时间WLS与外推尺度；不跨风险、缺失、group、未提交post凑样本。保留原最近已完成片段的窗口规则。合并只写group；选映射前post只写pending。

q两当前观测与A/B预测必须共同可用，否则四条深度边全用共同无信息cost=0，准确回到几何。共同raw全帧背景及深度权重.25不变。D4观察整体F6 selected scalar，D5对各合格片等权归一Student-t4 likelihood ratio，再含共同10%无信息混合。不能选最大、最近片当真值；不能因为多片数量或未知获利。大尺度保留normalized density的尺度惩罚。

## 状态与执行

不改变trigger、q、候选物理含义、旧参考、二维运动、depth权重、占用、事务与发布。各分支继续自己的live/bank/epoch/public状态，无常驻D1_DELAYED/BIRTH_REFINE继承。首分离帧先stage/commit，再唯一首次发布；不读q之后帧或改过去预测。

先进行片段/缺测/来源版本/风险/真实时间/候选排列必要单测，运行真实B01式最早合法source→measurement→score→stage→publisher切片。切片不读GT、不作为研究晋级问答。随后直接运行所有四段五分支。不要求人工先判对、数值先提点或表面标签先齐全。

全体预测、状态、事件、发布ledger、源和代码绑定封存后才评分。每段和整体官方TrackEval IDF1/HOTA/AssA/IDSW/FP/FN；pooled用隔离段身份命名空间，禁止平均率代替总体。所有mask保留、一帧public ID一对一。记录恢复正确/错误/锚点不可评分、进入前原ID是否已错、首帧发布、深度覆盖、缺测、实际状态改变和耗时。实际测量QA保存在private，公开数字图无像素/GT raster。

## 判定及停止

工程通过不等于深度有效。预定义支持收益：D5整段优于D0与同源SAM3的IDF1/HOTA/AssA，IDSW不增加；逐事件保留全部成功、失败与不可评分。D5−D4评估多片表示增量；差异为零则如实零作用。复用暴露数据没有独立泛化结论。不因降分滚动换阈值、换片段、放宽来源、补造事件或自动加入模型。

新增模型HTTP/smoke/训练/SAM3推理/补全服务/费用全部0，不需要key。失败也完成可执行全段与报告，非破坏性提交并正常push origin/main，实际读取远端ref与关键文件。受限产物列真实路径/字节/SHA/复现依赖；旧DS1–DS5 seal与源只读。

