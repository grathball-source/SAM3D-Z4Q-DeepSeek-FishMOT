# DS9：H0联合证据真实完整回放

## 主判定与分层

**未达到利用深度超过同源native的冻结目标，停止此冻结版本。**
工程链与方法指标分列；不把更多合格点、归一化后验或测试PASS当成深度有效。六枝均完整1471帧、各自真实状态，所有预测/访问seal后才独立官方TrackEval与参考核验。

## 本轮修改

仅替换事件选择器：显式合法原生/既有alias H0，按物理映射去重；几何与深度含尺度归一化项和共同背景。几何均值沿原实际运动，past同版本下一点残差只估计一致性代理。保留DS8实际core提取、深度质量、风险历史、触发/q/参考以及首发布事务。
J0为几何；J1原始深度；J2真实v2；ZERO完全删除深度似然且必须逐帧等于J0；PERMUTE仅错配当前两个post用于打分的深度，state仍接收原量。每次候选先关联/局部stage，后首次写当前帧；失败/H0继续自己的合法状态。没有改最终预测文件回填。

## 完整同源主表

|分支|IDF1|HOTA|AssA|IDSW|FP|FN|
|---|---:|---:|---:|---:|---:|---:|
|SAM3_NATIVE|80.976760|79.964056|71.530499|108|487|985|
|J0_GEOMETRY|80.976760|80.012049|71.615763|106|487|985|
|J1_RAW_DEPTH|80.976760|80.012049|71.615763|106|487|985|
|J2_RESTORED_DEPTH|80.976760|80.012049|71.615763|106|487|985|
|J2_DEPTH_ZERO|80.976760|80.012049|71.615763|106|487|985|
|J2_DEPTH_PERMUTE|80.703044|79.689085|71.044915|110|487|985|

|对照|ΔIDF1|ΔHOTA|ΔAssA|ΔIDSW|
|---|---:|---:|---:|---:|
|J0_GEOMETRY−SAM3_NATIVE|+0.000000|+0.047993|+0.085265|-2|
|J1_RAW_DEPTH−SAM3_NATIVE|+0.000000|+0.047993|+0.085265|-2|
|J2_RESTORED_DEPTH−SAM3_NATIVE|+0.000000|+0.047993|+0.085265|-2|
|J2_DEPTH_ZERO−SAM3_NATIVE|+0.000000|+0.047993|+0.085265|-2|
|J2_DEPTH_PERMUTE−SAM3_NATIVE|-0.273716|-0.274971|-0.485583|+2|
|J1_RAW_DEPTH−J0_GEOMETRY|+0.000000|+0.000000|+0.000000|+0|
|J2_RESTORED_DEPTH−J0_GEOMETRY|+0.000000|+0.000000|+0.000000|+0|
|J2_RESTORED_DEPTH−J2_DEPTH_ZERO|+0.000000|+0.000000|+0.000000|+0|
|J2_RESTORED_DEPTH−J2_DEPTH_PERMUTE|+0.273716|+0.322964|+0.570848|-4|
|J2_RESTORED_DEPTH−J1_RAW_DEPTH|+0.000000|+0.000000|+0.000000|+0|

pooled是在原TrackEval协议按segment命名空间合并计算，非四段率的平均；全部mask、残片、负ID都计分。每段成绩、深度覆盖、switch ledger、支持层详见run/METRICS.json、EVENT_AUDIT及SWITCH_LEDGER。

## 首发布与实际动作

|枝|q数|真实COMMIT|首发布正确/错误/不可评分|
|---|---:|---:|---|
|J0_GEOMETRY|19|2|{'UNSCORABLE_OR_NO_BIJECTION': 4, 'CORRECT': 11, 'WRONG': 4}|
|J1_RAW_DEPTH|19|2|{'UNSCORABLE_OR_NO_BIJECTION': 4, 'CORRECT': 11, 'WRONG': 4}|
|J2_RESTORED_DEPTH|19|2|{'UNSCORABLE_OR_NO_BIJECTION': 4, 'CORRECT': 11, 'WRONG': 4}|
|J2_DEPTH_ZERO|19|2|{'UNSCORABLE_OR_NO_BIJECTION': 4, 'CORRECT': 11, 'WRONG': 4}|
|J2_DEPTH_PERMUTE|19|4|{'UNSCORABLE_OR_NO_BIJECTION': 4, 'CORRECT': 9, 'WRONG': 6}|

实际选择、H0实际map、去重先验、每边density/background、残差fact、深度fact错配、首发布与局部事务都在逐事件JSON中。COMMIT表示相对当前合法映射实际改变；stage NO_ID_CHANGE不是新增恢复。首发布正确不等于修复了进入前旧错号；实际bank参考、进入前已错/未知和片段共识分列。

## 输入、工程与证据边界

当前测量逐帧与DS8来源/抽取对照；native同源逐帧一致；ZERO与几何逐帧一致；所有旧678 tracked文件字节锁；所有预测、代码、来源、实际publisher和score封存绑定。
v2来自真实已有full_v2，而非v3含标注补孔；其上游含RGB与未来i±1清理。J2仅已曝光离线开发诊断，不能宣称因果在线、独立录像泛化或鱼体表面/mm准确度。背景whole统计、MAD、噪声floor和条件独立只是冻结模型假设，不是物理真值或校准身份概率。
完整来源/扫描/时间索引预加载；新选择器只用截至q的合法片段/current post。native HDF5底层I/O并非Python路径audit全覆盖；静态reader按当前图像行取值。既有v2未来支持单独揭示。
真实六枝全段回放总墙钟794.054s，各段runner计时之和779.586s，含IO/重投影/状态/日志，不含新SAM3且不称实时部署。新模型HTTP/smoke/训练/SAM3/补全服务=0，费用0。

## 未完成边界与一个下一步

未完成：未建立独立鱼体表面/mm真值、v2因果等价或独立未曝光录像验证。该单次冻结试验不自动扩触发、调阈值、接入大模型或训练。
唯一下一步已写入NEXT_STEP_PLAN.md：用同版本连续真实过去的下一点残差校准深度过程不确定性；仅规划，未启动。

## 交付与复现

代码、CONFIG/PLAN、必要测试、真实slice链路、执行日志、六枝预测/metrics/事件/切换和数值图随main正常推送。私有像素/源RLE/GT/凭据不发布，RESTRICTED_INVENTORY列实际路径、字节、SHA与复现依赖；REMOTE_VERIFICATION记录实际ref及关键文件读取。旧archive/seal只读。

## 封存后实际归因与工程例外

**微小收益属于共同几何机制，深度独立增量为0。** J0/J1/J2/ZERO完整发布逐帧相同（不仅指标相同）。IDF1与native相同；HOTA +0.047993、AssA +0.085265个百分点、IDSW 108→106。F1239把新source167接回旧ID136，F1745把190接回188，另一条边保持；两次实际首发布依原anchor参考为正确，进入前参考同anchor，无借旧错号偶然换回。
F1239 depth只在已足够的geometry margin上附加raw约0.013296/v2约0.003422；F1745 depth边完全无信息。F434某深度候选虽被选择，却因残片写集guard不提交，且其参考不可评分，不能算恢复。
错配控制在F519/F1027把原本正确的两个native ID双边交换成错误，额外损害使IDSW110。故错配有害，但原始/修复/置零/geometry都同效，不证明深度必要性。全部19q/枝与no-q事件保留，完整候选、风险、缺测与相同state比较见ASSOCIATION_POSTRUN.json。

第一次冻结evaluate在读GT前因DS8逐字段严格metadata比较失败，原文件、预测与失败日志保持只读。随后全1471帧/39208对象审计仅有281个 dt_max_px 的float32 1 ULP差异（最大4.76837158203125e-7px）；全部双方值>6，实际ROI阈值都clamp3px。threshold、samples/n、median/MAD、资格、背景、来源和其它typed字段严格相同。未认证ROI bitmap字节相同，也未确定底层runtime浮点差异根因。
新增独立score_float_adapter.py在读GT前另行封存，只在副本接纳上述无作用诊断值、最后全dict其余strict exact；原scorer、研究门槛、物理mapping真值、来源与预测全不改。5项最小检查拒绝实际中位数/threshold/大差异篡改。原严格验收FAIL与追加精度例外后评分成功分列，不能写成原严格比较PASS。当前281均经独立float32位距离认证为1；该adapter的spacing上界在未见的2次幂边界不作通用一ULP保证，下一新冻结版本可用nextafter精确邻点检查，本轮不改已seal代码。
正式评分绑定：SOURCE_FLOAT_AUDIT、FLOAT_SCORE_ADAPTER_FROZEN/ACCEPTANCE、APPENDED_SCORE_PROVENANCE_SEALED。必要HOTA/Identity/CLEAR评分完整；可选BURST的tabulate导入提示不影响本轮三项，未安装依赖。

工程链通过限定追加精度验收；输入为原始或含上游RGB/未来清理的离线v2；独立深度收益未建立，停止当前冻结版本。唯一下一步已经具体规划于NEXT_STEP_PLAN.md，未执行。新模型HTTP/训练/SAM3/补全服务与费用0；旧678 tracked文件保持字节不变。
