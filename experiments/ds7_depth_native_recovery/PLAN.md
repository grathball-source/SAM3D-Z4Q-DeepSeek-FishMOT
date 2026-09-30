# DS7：原生连续发布与来源分层深度恢复

## 假设与目标

H1：DS6 的原生差距首先包含临时 q 映射首次发布的损害；保留 native 或本分支真实已提交 event alias 可消除这类猜配。
H2：原始 core 的欠覆盖与恢复深度的填补混合造成弱证据；来源分层的测量可能提供可辨别的 q 配对证据。
H3：对每个 pre 角色同时比较两个可用 post，缺失的整行采用同一个无信息分布，可保留局部证据而不让缺失边占便宜。

唯一性能目标：同源 SAM3_NATIVE。预先规定成功需 pooled IDF1/HOTA/AssA 全部上升，IDSW 不增；P2 还须超过 P0 和 P1，才称本轮修复深度独立增量。工程 PASS、止损回 native、单个片段胜出不满足此主判定。P1 若超过 native 单列原始深度增量。没有可校准 mm GT，不能称物理深度准确。

## 变量与对照

全量沿用四段 0–199 / 351–555 / 701–1060 / 1201–1906，共1471帧，SOURCE_OLD原mask与预测扫描规则，首split帧q、原2D位置/运动、30帧/最近10点同版本WLS、深度权重0.25、保护和原子stage。
每分支独立继续自身状态；同源mask全部保留，ID同帧唯一，负数同样评分。

| 分支 | 发布/回退 | 深度 |
| --- | --- | --- |
| SAM3_NATIVE | 原生ID | 无 |
| D2_CORE_FROZEN | DS6旧原始core控制 | 原DS1 |
| P0_NATIVE_PRESERVE | 新保护与native/既有alias；不接受任何关联 | 无信息消融 |
| P1_RAW_DEPTH | 同P0底座，证据通过时stage | 原始core |
| P2_RESTORED_DEPTH | 同P1 | 真正native v2重投影，来源分层core |

D2须1471帧逐条复现DS6，用于工程回归。P0须无先前alias时全段等于native，这只证明止损。
控制器和扫描仍以原始profiles测量入bank，不把修复深度暗塞进触发或2D历史。P2修复值只进入独立DepthState和关联likelihood。合并group、post未指派与contact风险均不能认证为pre。

## 最小修复

1. 内部group/residual仍匿名并隔离，公开映射按自身已提交合法alias或native。不借另一个member ID给group carrier。q preview也用同一基准。
2. candidate选择后真实stage/commit，然后第一次publish。不使用临时H1判定“无改号”；分别记录内部preview、native、上一公开帧和本次commit差异。
3. core为原mask去重叠后7×7腐蚀。P2统计provenance1实测与2/3推断两组；不读取v3及其4类补孔。实测组通过既有n16/fraction0.2/scale≤60时优先使用，否则仅使用合格推断组，不把两组中位数混合。
4. 推断组增加60mm尺度下限（冻结的保守假设，非精度）。保留各来源n、median、MAD、差异和UNKNOWN；不因补满密度认证可靠。
5. 每个角色只有两个post都合格时才参与比较；缺预测整行共同0，post缺测全部共同0。仍含 Student-t 归一化常数和共同背景。严格比较完整H1/H2解释。
6. 深度最优与geometry+0.25depth最优一致，且深度似然odds≥9才允许恢复，否则自己的native/alias回退。9:1是先验改号成本假设，不称校准概率；不按结果调门槛。

## 输入与泄漏边界

用户本轮允许已有修复深度。使用真实full_v2三份native H5，按当前frame读取depth_mm/original_depth_mm/filled_mask/invalidated_reason并以记录标定重新投影；不使用v3及annotation补孔。实际v2清洗用了i+1的depth与RGB，故P2仍是已曝光开发集离线恢复诊断，不能证明仅过去帧上线提点。运行时禁读instance_id/fish_interior_mask/RGB/参考标签、v3与网络。原始P1单列。

## 顺序与资源

先归因、真实输入单测/状态单测和首合法事件切片，再冻结全部代码/配置/来源和评分条件，完整五分支回放。全部预测、状态、event和首次publish seal后才独立TrackEval与事后身份审计。失败、缺测、无事件与不可评分均保留。
本地CPU各数学库/OpenCV1线程，无GPU/服务/训练/SAM3/模型HTTP，费用0。预计全量10分钟内、公开数值产物约40MB；已有磁盘余量18GB，受限输入/图仅列路径字节SHA。
确定性无随机模型。pooled计分用(segment,id)隔离，IDF1为合并计数，HOTA/AssA官方多IoU阈值，IDSW/FP/FN官方CLEAR0.5。逐段表与逐事件账本保留。单录像曝光开发不进行独立泛化显著性检验。
完成后正常提交、push main并读取实际远端及关键文件；旧seal不改，不自动调参或加入模型。
