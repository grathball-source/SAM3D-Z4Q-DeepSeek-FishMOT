"""Postscore delivery only: explicit semantic failures and all complete metrics."""
from common import *
from collections import Counter

FIELDS=('IDF1','HOTA','AssA','IDSW','FP','FN')

def table(units):
    lines=['|数据|分支|IDF1|HOTA|AssA|IDSW|FP|FN|','|---|---|---:|---:|---:|---:|---:|---:|']
    for name,u in units.items():
        for arm,m in u.items():
            lines.append(f"|{name}|{arm}|{m['IDF1']:.6f}|{m['HOTA']:.6f}|{m['AssA']:.6f}|{m['IDSW']}|{m['FP']}|{m['FN']}|")
    return lines

def main():
    assert read(RUN/'SCORE_PROVENANCE.json')['reference_opened_after_all_seals']
    m=read(RUN/'METRICS.json');p=read(RUN/'POSTSEAL_REPORT.json')
    assert m['frames']==20098 and sum(x['mixed_observation_count'] for x in p['segments'].values())==181842
    required=['STATE_POLICY_REVIEW.json','MEASUREMENT_POLICY_REVIEW.json','FEEDING_NEW_REVIEW.json','ACTION_DEPTH_REVIEW.json','PRIVATE_VISUALS.json','FAILURE_VISUALS.json']
    assert all((HERE/x).exists() for x in required)
    units={n:x['metrics'] for n,x in m['segments'].items()}
    units['Feeding1471_pooled']=m['feeding_pooled']['metrics']
    main_units={'Feeding1471':m['feeding_pooled']['metrics']}
    main_units.update({n:m['segments'][n]['metrics'] for n in ('fishsa_development_8400','fishsa_validation_2888','L3','LW')})
    differences={n:{base:{f:u['MIXED_ORDER'][f]-u[base][f] for f in FIELDS}
        for base in ('SAM3_NATIVE','Z4Q_FROZEN','ACTIVITY_ORDER','MIXED_OFF')} for n,u in main_units.items()}
    depth_counts={view:{field:sum(s['mixed_depth'][view][field] for s in p['segments'].values())
        for field in ('eligible_single','mixture_flag','quality_usable','source_ownership_exclusive')}
        for view in ('whole','core')}
    q={}
    for arm in ARMS[2:]:
        choices=Counter();status=Counter()
        for s in p['segments'].values():
            choices.update(s['q_details'][arm]['choices']);status.update(s['q_details'][arm]['restore_status'])
        q[arm]=dict(queries=sum(choices.values()),choices=dict(choices),restore_status=dict(status),
            ordinal_eligible=sum(s['q_details'][arm]['eligible'] for s in p['segments'].values()))
    judgement=dict(main='COMPLETE_DIAGNOSTIC_TRIAL_SEMANTIC_CONTRACT_FAILURE_NO_RELIABLE_DEPTH_GAIN',
        replay_scoring_and_delivery='COMPLETE',raw_source_population_and_causality='PASS',
        protected_reference_activity_and_atomic_publication='CHECKS_PASS',
        actual_birth_core_same_roi_certificate='FAIL; 181226/181842 profile statistics differ',
        anonymous_measurement_and_identity_separation='FAIL; valid current depth blocked and birth opportunity consumed',
        mixture_increment='NOT_RELIABLE; Feeding declines; FishSA/L3 zero; LW restores original Z4Q benefit',
        ordinal_increment='PROTECTIVE_VS_OFF_IN_TWO_SCORABLE_WRONG_SWAPS; ZERO_NEW_ORDER_GROUP_COMMIT; NO_GAIN_OVER_ORIGINAL_Z4Q',
        frozen_version='STOP_DS17_NO_ROLLING_PARAMETER_OR_PROMPT_SEARCH',all_history_or_depth_theory='NOT_TESTED_OR_REJECTED_AS_A_WHOLE',
        model_http=0,smoke=0,cost_usd=0)
    write_new(HERE/'MAIN_JUDGEMENT.json',judgement)
    write_new(HERE/'SUMMARY.json',dict(status=judgement['main'],base_commit=read(HERE/'STRATEGY.json')['base_commit'],
        frames_per_arm=20098,arms=list(ARMS),total_branch_frame_outputs=120588,original_mask_observations=181842,
        total_published_mask_observations=1091052,main_metrics=main_units,differences=differences,measurement=depth_counts,event_q=q,
        all_prediction_seal=artifact(RUN/'ALL_PREDICTIONS_SEALED.json'),metrics=artifact(RUN/'METRICS.json'),
        official_scoring=artifact(RUN/'SCORE_PROVENANCE.json'),checks=artifact(HERE/'CHECKS.json'),
        reports=[artifact(HERE/x) for x in required],model_http=0,cost_usd=0,
        uncompleted=['Birth actual core ROI certification repair','Preserving anonymous valid depth and pending birth proposal',
            'Verified attribution of depth layers to individual fish','Complete source_activity identity-version certification','Independent strong-reference generalization'],
        public_sync='Follow release_verify.py; commit IDs and actual remote evidence recorded separately',
        restricted_artifacts='Actual pixel figures and raw sources stay local; true paths/bytes/SHA in RESTRICTED_ARTIFACTS.json'))
    lines=['# DS17 完整指标与差值','','六分支各自完整运行20098帧；全部预测与访问封存后统一官方TrackEval评分。模型HTTP与费用均0。旧原生/原Z4Q/DS16逐帧及指标一致。','','## 全部八段及Feeding合并表','',
        *table(units),'','## MIXED_ORDER实际增量','','百分点为绝对百分点；IDSW为次数差。L3/LW使用弱预标注，不与强参考混合成总分。','',
        '|数据|参照|ΔIDF1|ΔHOTA|ΔAssA|ΔIDSW|ΔFP|ΔFN|','|---|---|---:|---:|---:|---:|---:|---:|']
    for n,d in differences.items():
        for base,r in d.items():
            lines.append(f"|{n}|{base}|{r['IDF1']:+.6f}|{r['HOTA']:+.6f}|{r['AssA']:+.6f}|{r['IDSW']:+d}|{r['FP']:+d}|{r['FN']:+d}|")
    lines+=['','## 相对次序与实际组提交','','|分支|q数|次序可用|选择|实际restore状态|','|---|---:|---:|---|---|']
    for arm,r in q.items():lines.append(f"|{arm}|{r['queries']}|{r['ordinal_eligible']}|{r['choices']}|{r['restore_status']}|")
    lines+=['','所有mask保留，FP/FN在同片段各臂完全一致。literal末帧、连续pre片段共识、初始错号、当前物理恢复和输出指标分列；UNKNOWN/无q/未提交不算正确。详见POSTSEAL_REPORT、STATE_POLICY_REVIEW、FEEDING_NEW_REVIEW。']
    (HERE/'RESULTS.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
    main_table=table({n:{a:u[a] for a in ('SAM3_NATIVE','Z4Q_FROZEN','MIXED_ORDER')} for n,u in main_units.items()})
    review=[
        '# DS17 深度混合与Feeding切换：完整复盘',
        '',
        '## 主判定',
        '',
        '**已完成六分支、八片段、20098帧/分支的真实状态回放与独立评分。DS17没有可靠的新深度提点，并暴露两个明确的关联接口错误；冻结此版本。**',
        '',
        '混合层记录、真实来源与逐发布记录可保留作诊断。当前版本不适合替换原Z4Q；不能将本轮失败外推为完整历史、深度或上下关系无效。',
        '',
        '新增模型推理、smoke、训练、SAM3推理、补全服务和费用全部0。没有读取v3、选择新GT锚点、修改旧封存、改写已发布历史或少评任何ID。',
        '',
        '## 真实主比较',
        '',
        *main_table,
        '',
        '所有六臂、四个Feeding分段及所有相对差值见RESULTS.md。8400相对原Z4Q：IDF1 −7.330810、HOTA −3.338696、AssA −6.543589，IDSW +1；这些损失在ACTIVITY_ORDER已出现，MIXED_ORDER未增加或减少该段损失。',
        '',
        'Feeding相对ACTIVITY_ORDER：IDF1 −0.364954、HOTA −0.514405、AssA −0.913151，IDSW −1。相对NATIVE：IDF1 +0.375092、HOTA −0.415393、AssA −0.732524，IDSW +22。IDF1局部上涨不足以称稳定身份提点。',
        '',
        '## 掩码混合深度的实际处理',
        '',
        '每个原mask的whole和冻结adaptive core同时记录完整原aligned有效像素分布与去共享/去重的原生source分布。层由当前实测深度间隙定义，保留全部层的点数、比例、median/MAD、空间范围、来源哈希；原scalar不替换成最近层或最大层。潜在混合及来源/覆盖不足使该关联测量UNKNOWN，原mask、残片和实测证据均保留。',
        '',
        '全段whole潜在混合10510、core8320。Feeding whole潜在混合11.8369%，ownership拒绝40.8361%；core潜在混合4.2976%。两类拒绝必须分开。背景、弯曲鱼体和另一条鱼均可能形成层；同一模式也可能混入深度接近的两鱼。当前实现没有给层分配物理身份。',
        '',
        '30mm间隙、至少16独立点/20%比例、15mm尺度下限/60mm上限全部在调用前冻结。它会漏掉小比例污染或连续/近邻双层。core虽提高单层覆盖，也不能普遍消除混合，FishSA8400中core混合提示数甚至高于whole；不能只凭侵蚀后的有效比例1就认证深度准确。',
        '',
        '## Feeding为何多切换而没有稳定增益',
        '',
        '旧NATIVE108→Z4Q132的逐时刻分解为新增24、消除0；24条均是D1_DELAYED真实提交：15物理WRONG、8正确但晚改号、1不可评分。其source在提交前连续发布6–135帧，晚恢复旧ID也会产生一次真实切换。旧次序分支逐帧等于原Z4Q、零group提交，不能把常驻重接损害归因到新次序模块。F468是phase=birth，不是D1。',
        '',
        '本轮ACTIVITY131、MIXED130；MIXED相对ACTIVITY实际新增12、消除13。MIXED仍有15次错误自动提交及8次正确但晚改号，当前提交的whole/core都已被标为单层可用。单层深度接近无法鉴别不同鱼。',
        '',
        '具体取舍：阻止F190 n30→8错误；F374的n70→67延到F375后物理判定变为正确；但ACTIVITY F1466正确n176→167被迁移为F1464错误→126，正确n174→163被迁移为F1474错误→167。F186也从F1712错误→166改为F1682正确→132。全部是本分支真实alias/bank后续状态的变化，不是手工改输出。',
        '',
        '最后706帧MIXED相对ACTIVITY损失IDF1 −0.771956/HOTA −1.198727/AssA −2.105477，IDSW反而+1。筛掉不可靠深度会改变clean_time/历史、竞争资格、确认序列和后续alias，效果不止当前一条边。完整分支差异不能冒充同状态单边反事实。',
        '',
        '## 确切工程错误与保留的工程收益',
        '',
        '### 1. 身份尚未确定被错误转换成测量不可用',
        '',
        '当前POST_UNASSIGNED观测本可保留真实深度供候选比较；DS17为防个体污染把current core置空，而原引擎仍登记birth。开发F3902 n7→0、验证local2188/global11488 n8→3两次原成功BIRTH_REFINE均因此current_core_unavailable，随后不再是born，机会被永久消耗。开发n7从3902到8400共4499帧仍发布7，没有D1补回；验证直到local2237/global11537才D1补回3，晚49帧。',
        '',
        'clean/view/recent_core隔离检查通过，但这种屏蔽策略未保住原关联功能。身份未知与测量质量未知应分开；禁止历史认证不应删除可用于当前合法关联的测量和待决候选。',
        '',
        'L3则修复了旧整bank冻结的另一损害：真实native9活动应到local2890，旧DS16停在2872，陈旧partner5制造partner_ambiguous。新ACTIVITY在local3025让原D1 n47→9恢复，clean anchor仍是2712。整段IDF1回到原Z4Q74.745256，新增混合筛选对此无增量。',
        '',
        'LW ACTIVITY失去原local2515 n106→5正确恢复，后1115帧仍106；MIXED改变竞争/历史资格后按原五次确认在2515恢复5，IDF1回到原Z4Q64.329395。两Mixed分支相同，此为保住原已有恢复；相对原Z4QHOTA仍−0.012596、AssA−0.030600。',
        '',
        '### 2. 出生关联的core与筛选证书不是同一ROI',
        '',
        '181842观测中181226（99.661%）旧profile core与adaptive证书的area/n/fraction/median/MAD至少一项不同，覆盖全部20098帧；whole统计完全一致。这是同帧同源的两种core算法未在接口统一，不是换数据。Birth实际读旧固定3像素侵蚀core，新证书却来自DS12自适应L2 core。统计相同也不足以证明像素集合相同。',
        '',
        'LW local3064 n133：adaptive core107点、median783.68994/MAD10.01031；Birth实际旧core50点、median781.48065/MAD9.18744。该对象whole因8个共享source点而拒绝，没有潜在多层。MIXED发布107、ACTIVITY发布120；两者实际core历史都来自n120@2857，core cost相同。ACTIVITY对应whole也没有veto，因此不能把新增public107动作归因于删whole反证或物理层正确辨认。',
        '',
        '### 3. 缺测语义在三条入口不相同',
        '',
        'D1要求whole：缺测拒绝所有旧ID边并保留dummy，同时不更新clean历史。S0要求成对pre/post core：任一不合格，全候选ordinal logLR=0并H0。Birth要求core但whole是可选反证：whole清空可能移除explicit veto；本轮没有证明某个同状态否决被移除导致新增提交。原计划“UNKNOWN不令候选获利”未在该入口得到一般保证。',
        '',
        '## 上下关系的实际贡献',
        '',
        'MIXED_ORDER 50次q、18次次序可用、32次UNKNOWN，50次均H0，真正组恢复0提交。MIXED_OFF同资格，提交3次：Feeding一例pre共识不可评分，FishSA验证/L3两例pre共识WRONG。次序挡住了OFF中的两次可评分错误，但没有新增正确恢复，更没有超过原Z4Q。相对次序是候选约束，不是身份指纹；概率未校准，也没有认证每个深度层的遮挡上下归属。',
        '',
        '## 验收、可视化与复现',
        '',
        '23个直接相关检查、150真实前缀来源/原输出等价、真实L3状态切片、全部六臂20098帧和181842原mask守恒均完成。原NATIVE/Z4Q/DS16的完整输出与官方指标复现旧封存。预测/访问先封存再读参考；官方mask CLEAR/Identity .5与HOTA19alpha、原FishSA评分版本保持一致。没有忽略ID、复制共同mask或用GT指定动作。',
        '',
        '完整报告容器适配只修复automatic_reconnect元信息被误作group分支的读取，记录在正式评分前；冻结report/scorer/预测未改。它没有改变选择、事实、评分或任何旧成绩。',
        '',
        '27张本地真实depth/mask图：24张固定首次混合/首次分支发布差异、预定L3切片；另3张出生屏蔽及Feeding错误迁移的专项病例图，仅为封存后诊断，不参与预测触发。可公开METRIC_COMPARISON图仅来自汇总数值；私有像素不进入Git。图中n是native source、p是实际首次发布persistent ID；层图“ownership UNKNOWN”指层到物理鱼的归属未认证，SINGLE/UNKNOWN测量状态另示。',
        '',
        '科学回放墙钟2308.314秒、评分771.001秒；原始逐作业退出/耗时见EXECUTION_LOG。源文件、私有切片/图真实路径、字节、SHA及依赖见RESTRICTED_ARTIFACTS。Git交付所有公开代码/配置/测试/日志/预测/指标/审计/报告；main远端ref与关键blob由release_verify实际读取。',
        '',
        '本队列已暴露，L3/LW为弱预测预标注；没有独立泛化或真实深度层归属准确率。source_activity内部source_version保持UNKNOWN，不能冒充完整身份来源版本证书。旧保存SAM3前端零lookahead未在本轮重新认证；本轮关联无q之后输入。没有用v3/annotation instance_id恢复深度。',
        '',
        '## 唯一下一步',
        '',
        '执行一次“关联证据接口修复”：给每条实际使用的whole/core同ROI来源证书，分开测量质量与身份未知，保留待决Birth候选到原子关联完成；不把匿名观测写pre，也不消耗候选后永久丢弃。先复现真实3902/11488/3064链，再冻结同六臂同源全段验证。暂不扩展深度算法或搜索阈值，先得到可解释的输入与状态底座。详见NEXT_STEP_PLAN。',
        '',
        '该下一步尚未执行。本轮失败停止的是DS17冻结版本；完整事件历史及分层相对深度的研究问题仍未被此输入合同完整检验。',
    ]
    (HERE/'FINAL_REVIEW.md').write_text('\n'.join(review)+'\n',encoding='utf8')
    next_plan='''# 唯一下一步：关联证据接口修复与一次冻结回放

目标：保留原Z4Q已证实的合法恢复，使深度质量筛选与真实被比较的测量一致；先修本轮确定的工程根因。不得把恢复原基线称新深度提点。

1. 每条D1、Birth、S0实际输入绑定同一帧、ROI像素集合、source population和身份版本。旧固定core与adaptive core分别实测并签名；不以另一ROI合格代替当前ROI。保留所有层和未知，不删污染层、不换原depth/source。
2. 分开MEASUREMENT_VALID与IDENTITY_UNASSIGNED。group/post不写个体pre或recent_core，但允许当前合法实测与冻结旧参考比较；将一次性Birth提案留在事件待决事务中，stage失败不消耗候选，也不提前发布临时错误映射。保留真实活动时间、公开一对一和局部回退。
3. 缺whole不得默默删除候选反证：固定共同缺测语义，记录充分/不充分/冲突；不对某条边零代价优待。先在实际3902、11488、LW3064与Feeding错误/正确迁移链验证同ROI、待决候选、版本和状态读写，不要求GT指定正确动作。
4. 来源合同通过后一次性冻结同来源同六臂全段。逐帧复现原NATIVE/Z4Q，全部预测封存后独立评分；同时报告同源NATIVE、原Z4Q与相同状态底座。保留正确晚改号、物理错误、UNKNOWN及不可评分，禁止只看IDSW或挑最好重复。

不改trigger/q规则、原参考、2D运动、深度权重、候选物理含义，不永久锁ID、不按GT搜索阈值、不加模型/训练/SAM3推理/v3。若工程修复后仍无深度增量，交付真实全段并停止该冻结版本。此处仅规划，未自动启动DS18。
'''
    (HERE/'NEXT_STEP_PLAN.md').write_text(next_plan,encoding='utf8')
    (HERE/'README.md').write_text('# DS17\n\n先读 FINAL_REVIEW.md（分层判定及根因）、RESULTS.md（全部指标）、NEXT_STEP_PLAN.md（唯一下一步）。\n\n冻结科学代码只读；已完成六臂八段。新增API/费用0。公开数值与私有像素分开，复现方式及真实来源库存见 RESTRICTED_ARTIFACTS.json。远端交付证据见 REMOTE_VERIFICATION.json。\n',encoding='utf8')
    print('COMPLETE_REPORTS_WITH_EXPLICIT_SEMANTIC_FAILURES')

if __name__=='__main__':main()
