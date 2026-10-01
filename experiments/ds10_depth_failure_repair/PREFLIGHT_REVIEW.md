# DS10 冻结前审查

主任务读取真实代码流，并由三个独立审查任务覆盖全部19q关联失败、原始/v2深度与ROI、以及不确定性/null与评分。方法按PLAN与CONFIG只冻结一个联合修复版本；主目标是超过同源native，纯几何不作晋级门槛。

实际诊断覆盖四个漏接回、四个无法形成bank双射/可见残余、两个错配控制，并保留全部19q数值统计。主任务实际查看F470/F764/F1805私有图，核对原始/v2/core/cohort/时间线与来源；不把图中假定的对应连为真实路径。图和GT诊断均来自旧已封存DS9，非新分支动作选择。

最小新depth均值/方差与object-null公式按CONFIG真实生效，EFFECTIVE_PARAMETERS直接取运行模块源码。原DepthState缓存、2D均值、测量、扫描/q、mask、参考、9倍门槛、source/epoch隔离和S0-P事务均未变。F9使用旧association源码/原公式，在真实slice和全段必须逐帧等于DS9.J2。新分支不等待人工、数值或模型先成功。

必要检查已通过：controller13、adaptive ROI10、measurement5、forecast11、association23、评分合同5，共67项。测试验证工程/数值，不代替完整性能。首次controller导入出现瞬时系统DLL加载拒绝；同解释器独立导入与唯一重跑成功，保留失败日志，未安装软件或改变系统安全策略。

source精度合同在预测前声明：仅float32 nextafter的dt_max相邻且全部实际操作阈值不变，其余typed值exact。source/forecast/KDE组件逐列引用校验，semantic污染不能仅凭hash不匹配拒绝；五项评分检查包含自洽seal污染。全部预测/访问seal后才评分。

两处修复共同试验，含query的KDE与past diffusion proxy不是校准身份后验/物理准确率；1/2点、无历史仍原值。v2上游含RGB与未来清理，只称曝光离线诊断。背景混入/像素所有权、第三鱼事件结构、触发外IDSW不被本次方法自动解决。

本机已有解释器/deps、单线程CPU，无服务器/GPU作业，无API/训练/SAM3/补全服务和费用。旧DS1–9共802个tracked文件已字节锁；原始源在runner冻结时再次核验。工作目录新DS10，不覆盖旧输出。准备直接真实最早切片验收，然后完整四段回放。
