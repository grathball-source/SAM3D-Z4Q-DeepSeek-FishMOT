# DS17 深度混合与Feeding切换：完整复盘

## 主判定

**已完成六分支、八片段、20098帧/分支的真实状态回放与独立评分。DS17没有可靠的新深度提点，并暴露两个明确的关联接口错误；冻结此版本。**

混合层记录、真实来源与逐发布记录可保留作诊断。当前版本不适合替换原Z4Q；不能将本轮失败外推为完整历史、深度或上下关系无效。

新增模型推理、smoke、训练、SAM3推理、补全服务和费用全部0。没有读取v3、选择新GT锚点、修改旧封存、改写已发布历史或少评任何ID。

## 真实主比较

|数据|分支|IDF1|HOTA|AssA|IDSW|FP|FN|
|---|---|---:|---:|---:|---:|---:|---:|
|Feeding1471|SAM3_NATIVE|80.976760|79.964056|71.530499|108|487|985|
|Feeding1471|Z4Q_FROZEN|81.716806|79.859851|71.341782|132|487|985|
|Feeding1471|MIXED_ORDER|81.351851|79.548663|70.797975|130|487|985|
|fishsa_development_8400|SAM3_NATIVE|91.313288|73.346143|69.186768|5|194|323|
|fishsa_development_8400|Z4Q_FROZEN|99.333472|77.829488|77.907638|6|194|323|
|fishsa_development_8400|MIXED_ORDER|92.002662|74.490791|71.364050|7|194|323|
|fishsa_validation_2888|SAM3_NATIVE|76.456444|66.435529|55.196059|8|298|423|
|fishsa_validation_2888|Z4Q_FROZEN|80.697587|69.243869|60.074321|9|298|423|
|fishsa_validation_2888|MIXED_ORDER|80.413685|68.954661|59.571269|11|298|423|
|L3|SAM3_NATIVE|72.426787|75.362607|94.259655|1|14677|0|
|L3|Z4Q_FROZEN|74.745256|77.171558|98.839045|2|14677|0|
|L3|MIXED_ORDER|74.745256|77.171558|98.839045|2|14677|0|
|LW|SAM3_NATIVE|60.613534|66.369067|77.555121|7|16493|28|
|LW|Z4Q_FROZEN|64.329395|68.991721|83.805597|10|16493|28|
|LW|MIXED_ORDER|64.329395|68.979125|83.774998|8|16493|28|

所有六臂、四个Feeding分段及所有相对差值见RESULTS.md。8400相对原Z4Q：IDF1 −7.330810、HOTA −3.338696、AssA −6.543589，IDSW +1；这些损失在ACTIVITY_ORDER已出现，MIXED_ORDER未增加或减少该段损失。

Feeding相对ACTIVITY_ORDER：IDF1 −0.364954、HOTA −0.514405、AssA −0.913151，IDSW −1。相对NATIVE：IDF1 +0.375092、HOTA −0.415393、AssA −0.732524，IDSW +22。IDF1局部上涨不足以称稳定身份提点。

## 掩码混合深度的实际处理

每个原mask的whole和冻结adaptive core同时记录完整原aligned有效像素分布与去共享/去重的原生source分布。层由当前实测深度间隙定义，保留全部层的点数、比例、median/MAD、空间范围、来源哈希；原scalar不替换成最近层或最大层。潜在混合及来源/覆盖不足使该关联测量UNKNOWN，原mask、残片和实测证据均保留。

全段whole潜在混合10510、core8320。Feeding whole潜在混合11.8369%，ownership拒绝40.8361%；core潜在混合4.2976%。两类拒绝必须分开。背景、弯曲鱼体和另一条鱼均可能形成层；同一模式也可能混入深度接近的两鱼。当前实现没有给层分配物理身份。

30mm间隙、至少16独立点/20%比例、15mm尺度下限/60mm上限全部在调用前冻结。它会漏掉小比例污染或连续/近邻双层。core虽提高单层覆盖，也不能普遍消除混合，FishSA8400中core混合提示数甚至高于whole；不能只凭侵蚀后的有效比例1就认证深度准确。

## Feeding为何多切换而没有稳定增益

旧NATIVE108→Z4Q132的逐时刻分解为新增24、消除0；24条均是D1_DELAYED真实提交：15物理WRONG、8正确但晚改号、1不可评分。其source在提交前连续发布6–135帧，晚恢复旧ID也会产生一次真实切换。旧次序分支逐帧等于原Z4Q、零group提交，不能把常驻重接损害归因到新次序模块。F468是phase=birth，不是D1。

本轮ACTIVITY131、MIXED130；MIXED相对ACTIVITY实际新增12、消除13。MIXED仍有15次错误自动提交及8次正确但晚改号，当前提交的whole/core都已被标为单层可用。单层深度接近无法鉴别不同鱼。

具体取舍：阻止F190 n30→8错误；F374的n70→67延到F375后物理判定变为正确；但ACTIVITY F1466正确n176→167被迁移为F1464错误→126，正确n174→163被迁移为F1474错误→167。F186也从F1712错误→166改为F1682正确→132。全部是本分支真实alias/bank后续状态的变化，不是手工改输出。

最后706帧MIXED相对ACTIVITY损失IDF1 −0.771956/HOTA −1.198727/AssA −2.105477，IDSW反而+1。筛掉不可靠深度会改变clean_time/历史、竞争资格、确认序列和后续alias，效果不止当前一条边。完整分支差异不能冒充同状态单边反事实。

## 确切工程错误与保留的工程收益

### 1. 身份尚未确定被错误转换成测量不可用

当前POST_UNASSIGNED观测本可保留真实深度供候选比较；DS17为防个体污染把current core置空，而原引擎仍登记birth。开发F3902 n7→0、验证local2188/global11488 n8→3两次原成功BIRTH_REFINE均因此current_core_unavailable，随后不再是born，机会被永久消耗。开发n7从3902到8400共4499帧仍发布7，没有D1补回；验证直到local2237/global11537才D1补回3，晚49帧。

clean/view/recent_core隔离检查通过，但这种屏蔽策略未保住原关联功能。身份未知与测量质量未知应分开；禁止历史认证不应删除可用于当前合法关联的测量和待决候选。

L3则修复了旧整bank冻结的另一损害：真实native9活动应到local2890，旧DS16停在2872，陈旧partner5制造partner_ambiguous。新ACTIVITY在local3025让原D1 n47→9恢复，clean anchor仍是2712。整段IDF1回到原Z4Q74.745256，新增混合筛选对此无增量。

LW ACTIVITY失去原local2515 n106→5正确恢复，后1115帧仍106；MIXED改变竞争/历史资格后按原五次确认在2515恢复5，IDF1回到原Z4Q64.329395。两Mixed分支相同，此为保住原已有恢复；相对原Z4QHOTA仍−0.012596、AssA−0.030600。

### 2. 出生关联的core与筛选证书不是同一ROI

181842观测中181226（99.661%）旧profile core与adaptive证书的area/n/fraction/median/MAD至少一项不同，覆盖全部20098帧；whole统计完全一致。这是同帧同源的两种core算法未在接口统一，不是换数据。Birth实际读旧固定3像素侵蚀core，新证书却来自DS12自适应L2 core。统计相同也不足以证明像素集合相同。

LW local3064 n133：adaptive core107点、median783.68994/MAD10.01031；Birth实际旧core50点、median781.48065/MAD9.18744。该对象whole因8个共享source点而拒绝，没有潜在多层。MIXED发布107、ACTIVITY发布120；两者实际core历史都来自n120@2857，core cost相同。ACTIVITY对应whole也没有veto，因此不能把新增public107动作归因于删whole反证或物理层正确辨认。

### 3. 缺测语义在三条入口不相同

D1要求whole：缺测拒绝所有旧ID边并保留dummy，同时不更新clean历史。S0要求成对pre/post core：任一不合格，全候选ordinal logLR=0并H0。Birth要求core但whole是可选反证：whole清空可能移除explicit veto；本轮没有证明某个同状态否决被移除导致新增提交。原计划“UNKNOWN不令候选获利”未在该入口得到一般保证。

## 上下关系的实际贡献

MIXED_ORDER 50次q、18次次序可用、32次UNKNOWN，50次均H0，真正组恢复0提交。MIXED_OFF同资格，提交3次：Feeding一例pre共识不可评分，FishSA验证/L3两例pre共识WRONG。次序挡住了OFF中的两次可评分错误，但没有新增正确恢复，更没有超过原Z4Q。相对次序是候选约束，不是身份指纹；概率未校准，也没有认证每个深度层的遮挡上下归属。

## 验收、可视化与复现

23个直接相关检查、150真实前缀来源/原输出等价、真实L3状态切片、全部六臂20098帧和181842原mask守恒均完成。原NATIVE/Z4Q/DS16的完整输出与官方指标复现旧封存。预测/访问先封存再读参考；官方mask CLEAR/Identity .5与HOTA19alpha、原FishSA评分版本保持一致。没有忽略ID、复制共同mask或用GT指定动作。

完整报告容器适配只修复automatic_reconnect元信息被误作group分支的读取，记录在正式评分前；冻结report/scorer/预测未改。它没有改变选择、事实、评分或任何旧成绩。

27张本地真实depth/mask图：24张固定首次混合/首次分支发布差异、预定L3切片；另3张出生屏蔽及Feeding错误迁移的专项病例图，仅为封存后诊断，不参与预测触发。可公开METRIC_COMPARISON图仅来自汇总数值；私有像素不进入Git。图中n是native source、p是实际首次发布persistent ID；层图“ownership UNKNOWN”指层到物理鱼的归属未认证，SINGLE/UNKNOWN测量状态另示。

科学回放墙钟2308.314秒、评分771.001秒；原始逐作业退出/耗时见EXECUTION_LOG。源文件、私有切片/图真实路径、字节、SHA及依赖见RESTRICTED_ARTIFACTS。Git交付所有公开代码/配置/测试/日志/预测/指标/审计/报告；main远端ref与关键blob由release_verify实际读取。

本队列已暴露，L3/LW为弱预测预标注；没有独立泛化或真实深度层归属准确率。source_activity内部source_version保持UNKNOWN，不能冒充完整身份来源版本证书。旧保存SAM3前端零lookahead未在本轮重新认证；本轮关联无q之后输入。没有用v3/annotation instance_id恢复深度。

## 唯一下一步

执行一次“关联证据接口修复”：给每条实际使用的whole/core同ROI来源证书，分开测量质量与身份未知，保留待决Birth候选到原子关联完成；不把匿名观测写pre，也不消耗候选后永久丢弃。先复现真实3902/11488/3064链，再冻结同六臂同源全段验证。暂不扩展深度算法或搜索阈值，先得到可解释的输入与状态底座。详见NEXT_STEP_PLAN。

该下一步尚未执行。本轮失败停止的是DS17冻结版本；完整事件历史及分层相对深度的研究问题仍未被此输入合同完整检验。
