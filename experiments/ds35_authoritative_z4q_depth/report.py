"""Full sourcewise outcome, actual contribution and limits after independent scoring."""
from common import *
from collections import Counter
from verify_inputs import verify_all

def table(header,values):
    return '| '+' | '.join(header)+' |\n| '+' | '.join('---' for _ in header)+' |\n'+''.join('| '+' | '.join(map(str,row))+' |\n' for row in values)

def main():
    verify_all();m=read(RUN/'METRICS.json');segments={};all_reasons=Counter();stages=changed=eligible=0
    for name,packet in m['segments'].items():
        public=RUN/name/'public';events=read(public/'EVENTS.json')['DEPTH_OVERRIDE'];counts=Counter();underlying=Counter();actual=[]
        for e in events:
            d=e.get('joint_decision',{});r=e.get('restore',{})
            counts[d.get('reason',e['status'])]+=1
            if d.get('original_evidence_reason'):underlying[d['original_evidence_reason']]+=1
            eligible+=bool(d.get('depth_gate',{}).get('eligible'));stages+=bool(r.get('staged'))
            actual.append(dict(event=e['id'],suspect=e['suspect_frame'],q=e.get('q'),cutoff=e.get('decision_cutoff'),
                raw_choice=d.get('choice'),raw_proposal_mapping=d.get('proposal_mapping'),reason=d.get('reason'),depth_gate=d.get('depth_gate'),
                staged=r.get('staged',False),stage_error=r.get('error'),actual_first_mapping=e.get('actual_first_mapping'),
                first_published_mapping=e.get('first_published_mapping'),first_publish_at=e.get('first_publish_at_arrival_frame'),
                changes_against_own_q=r.get('changes',{}),physical_verdict=next((a for a in packet_audits(m,name) if a['event']==e['id']),None)))
        changes=sum(p['variants']['DEPTH_OVERRIDE']!=p['variants']['Z4Q_FROZEN'] for p in rows(public/'predictions.jsonl.gz'))
        changed+=changes;all_reasons.update(counts)
        segments[name]=dict(events=len(events),with_q=sum(e.get('q') is not None for e in events),reasons=dict(counts),
            underlying_endpoint_reasons=dict(underlying),changed_publication_frames=changes,actual_events=actual,summary=read(public/'RUN_SUMMARY.json'))
    status=('NO_DEPTH_OVERRIDE_ALL_PUBLICATIONS_EQUAL_TO_ORIGINAL_Z4Q' if changed==0 else
        'DEPTH_OVERRIDE_COMPLETE_SOURCEWISE_GAIN_AND_REGRESSION_REQUIRE_SEPARATE_INTERPRETATION')
    sections=[('Feeding1471',m['feeding_pooled'])]+[(n,m['segments'][n]) for n in SEGMENTS if not n.startswith('feeding_')]
    result=dict(status=status,frames=20098,engineering='PASS_ORIGINAL_AUTHORITY_AND_COMPLETE_OWN_FALLBACK',
        depth_gain='NOT_ESTABLISHED' if changed==0 else 'SEE_SOURCEWISE_OFFICIAL_METRICS_AND_PHYSICAL_AUDITS',
        eligible_depth_proposals=eligible,actual_new_commits=stages,changed_publication_frames=changed,
        reason_counts=dict(all_reasons),segments=segments,new_model_http=0,cost_usd=0)
    write_new(HERE/'RESULTS.json',result)
    metrics_rows=[]
    for n,p in sections:
        for a in ARMS:
            v=p['metrics'][a];metrics_rows.append([n,a]+[f'{v[k]:.6f}' if k in ('IDF1','HOTA','AssA') else v[k] for k in ('IDF1','HOTA','AssA','IDSW','FP','FN')])
        v=p['archived_DS34'];metrics_rows.append([n,'ARCHIVED_DS34_EVENT_RGBD']+[f'{v[k]:.6f}' if k in ('IDF1','HOTA','AssA') else v[k] for k in ('IDF1','HOTA','AssA','IDSW','FP','FN')])
    differences=[]
    for n,p in sections:
        for baseline in ('SAM3_NATIVE','Z4Q_FROZEN','DEPTH_OFF'):
            v=p['metrics']['DEPTH_OVERRIDE'];oldv=p['metrics'][baseline]
            differences.append([n,baseline]+[f'{v[k]-oldv[k]:+.6f}' for k in ('IDF1','HOTA','AssA','IDSW','FP','FN')])
    lines=['# DS35 最终复盘',f'\n主判定：**{status}**。八个同源片段、每分支20098帧完整真实状态回放，全部先封存再独立评分。',
        '\n## 改了什么与保留边界',
        '\n原Z4Q主引擎完整推进，疑似、合并、post pending、取消和缺测仅改变独立事件证据缓存。冻结pre不受匿名群组污染。'
        '本轮修复的是DS34共用机制的退化；原Z4Q本身仍可能有错误。新增深度必须全矩阵合格、三帧一致且有明确margin，并通过原生命周期和组外状态检查。'
        '失败保留自己的完整已推进状态，不从外部B0复制整套engine。没有几何单独提交、永久锁ID或只改输出文件。',
        '\n冻结条件：12秒历史、10秒事件、原scan_v4及首分离q、原两候选/二维OLS/深度权重0.25、30帧首次发布缓冲；'
        '新增可靠门槛各pre≥3连续测量、预测scale≤60mm、加权深度margin≥0.10、3个post各支持同一映射。不是实时部署；q后证据不写入q测量。',
        '\n## 完整指标',table(['来源','分支','IDF1','HOTA','AssA','IDSW','FP','FN'],metrics_rows),
        '\n## 新分支真实差值',table(['来源','对照','ΔIDF1(pp)','ΔHOTA(pp)','ΔAssA(pp)','ΔIDSW','ΔFP','ΔFN'],differences),
        '\n恢复原Z4Q成绩只称止损，不能把相对归档DS34的提升算新增深度收益。DEPTH_OFF完整状态与原Z4Q逐帧相等，深度增量只按DEPTH_OVERRIDE相对该同底座对照解释。',
        '\n## 实际事件与提交',f'\n深度合格提案 {eligible}；实际新增提交 {stages}；对原Z4Q改变发布帧 {changed}。',
        table(['来源','事件数','有q','改变帧','原因分布'],[[n,s['events'],s['with_q'],s['changed_publication_frames'],json.dumps(s['reasons'],ensure_ascii=False)] for n,s in segments.items()]),
        '\n详细原始选择/未提交原因/第一帧实际映射/物理参考、公共起源与切换均保存在RESULTS、各EVENTS/TRANSACTIONS/PUBLISH_LEDGER/EVENT_AUDIT/SWITCHES。'
        '物理preanchor、prefragment、postfragment和公共起源独立列出。未提交与UNKNOWN不记作恢复正确。',
        '\n## 工程证据与输入限制',
        '\n14项状态/可靠性测试、6项真实来源与自洽hash篡改、2项真实切片发现的空评估回归检查通过。首次评分检查发现mask digest适配不同（带dtype/shape头与只哈数组）；已在正式冻结前恢复原规范，失败日志保留。'
        '第一次开发前缀在缺失pre返回空scores时读取不存在的模态权重导致异常；已在冻结前修复，失败前缀保留不评分，重跑写入新目录。'
        '真实前缀验收保住开发q3902的7→0与验证q2188的8→3原BirthRefine，并在q2689弱增强证据时不提交几何交换；这属于工程证据。'
        '正式每帧输入/质量证书/实际mask、事件每个纳入观测版本、重算选择、全部状态与第一次发布绑定均在访问GT前验证。',
        '\n使用原始深度，whole/core混层、来源互斥、数量/覆盖、WLS预测尺度逐项保留。非零和高有效覆盖不等于物理表面身份。'
        '无RGB关联、无场景流、无轮廓补画。上游SAM3保存源的未来上下文与未记载producer reset保持UNKNOWN。L3/LW参考是弱预测派生，不称盲测或跨域物理身份正确。',
        '\n## 费用、复现与同步',
        '\n新增模型HTTP=0、费用=0，无API key/smoke/GPU/训练/SAM3/补全服务。精确代码、输入、实际常数、环境、评分门槛见RUNTIME_FREEZE与各FREEZE；START/END、完整预测/访问seal和日志见run。'
        '公开只同步数值预测token与记录；私有原始RGB、depth、mask、GT raster不公开。私有可视化实际路径/字节/SHA和复现依赖列于PRIVATE_INVENTORY。'
        '科学commit及实际origin/main/全部公开文件核验见交付收据；不force push、不覆盖旧seal。',
        '\n## 未完成项',
        '\n本轮没有新增盲测、三维物理精度标定、不可见轮廓恢复或模型调用。深度未达到性能目标时保留负结论，不用工程PASS替代方法收益。',
        '\n## 唯一未执行下一步',
        '\n在保留本轮原Z4Q权威状态的底座上，先统计真实错误关联处能否形成可区分的局部双鱼原始深度证据；按缺测、混层、宽预测及深度重叠分解信息上限，证据足够才设计下一次关联改变。该步骤未启动。']
    (HERE/'FINAL_REVIEW.md').write_text('\n\n'.join(lines)+'\n',encoding='utf-8',newline='\n')
    write_new(HERE/'REPORT_VALIDATION.json',dict(status='PASS',official_metrics=artifact(RUN/'METRICS.json'),result=artifact(HERE/'RESULTS.json'),
        original_controls_exact=True,no_depth_gain_claim_without_changed_state=True,old_results_readonly=True,new_model_http=0,cost_usd=0))
    print(status,'commits',stages,'changed frames',changed,flush=True)

def packet_audits(m,name):return m['event_audits'][name]['event_arms']['DEPTH_OVERRIDE']
if __name__=='__main__':main()
