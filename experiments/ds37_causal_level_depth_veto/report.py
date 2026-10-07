"""Result-only report after the frozen replay, score and mechanism audit."""
from common import *
from collections import Counter
from datetime import datetime, timezone
import statistics

def main():
    from score import verify_all
    verify_all();assert read(RUN/'COMPLETE.json')['frames']==20098
    metric=read(RUN/'METRICS.json');audit=read(RUN/'MECHANISM_AUDIT.json');changed=audit['totals']['Z4Q_LEVEL_VETO']['changed_frames']
    deletions=audit['totals']['Z4Q_LEVEL_VETO']['legal_edges_deleted'];states=audit['actual_same_prior_publication_changes']
    verdict='NO_DEPTH_STATE_OR_METRIC_INCREMENT_STOP_FROZEN_VERSION' if changed==0 else 'COMPLETE_EXPOSED_FROZEN_TRIAL_SEPARATE_PER_SOURCE_DELTA'
    counters=Counter();physical=Counter();switch_changes={};latency={};seconds={};mechanism={}
    for name in SEGMENTS:
        p=RUN/name/'public';summary=read(p/'RUN_SUMMARY.json');seconds[name]=summary['elapsed_seconds']
        raw=[v['receive_to_first_publish_seconds'] for v in rows(p/'PUBLISH_LEDGER.jsonl')]
        latency[name]=dict(frames=len(raw),median_seconds=statistics.median(raw),maximum_seconds=max(raw),
                           includes_original_plus_two_veto_branches=True,live_deployment_claim=False)
        for label,count in read(p/'ACTION_AUDIT.json')['counts']['Z4Q_LEVEL_VETO'].items():physical[label]+=count
        switch_changes[name]=read(p/'SWITCH_CHANGES.json')['Z4Q_LEVEL_VETO']
        for label,count in read(p/'VETO_AUDIT.json')['active_deletions']['Z4Q_LEVEL_VETO'].items():counters[label]+=count
        mechanism[name]=audit['segments'][name]
    accepted=read(RUN/'ORIGINAL_ACTION_FOLLOWUP.json')
    grades={}
    for grade in ('CORRECT','WRONG','UNSCORABLE'):
        actions=[v for v in accepted['actions'] if v['physical']==grade]
        edges=[q for a in actions for q in a['depth_edges']['Z4Q_LEVEL_VETO']]
        grades[grade]=dict(original_actions=len(actions),matching_query_edges=len(edges),
            query_reason_counts=dict(Counter(e['reason'] for e in edges)),
            vetoed_edges=sum(e['veto'] for e in edges),
            actual_public_kept=sum(a['matching_final_public']['Z4Q_LEVEL_VETO'] for a in actions))
    initial=read(HERE/'launch_failure_zero_frames_v1/RUNTIME_FREEZE.json');frozen=read(HERE/'RUNTIME_FREEZE.json')
    assert initial['effective_depth_config']==frozen['effective_depth_config']
    changed_code=[p for p,h in initial['code'].items() if p in frozen['code'] and h!=frozen['code'][p]]
    assert set(changed_code)<={str((HERE/p).resolve()) for p in ('guard.py','predictor.py','adapter.py','evidence.py','runner.py','checks.py','freeze.py','accept.py','orchestrate.py','PLAN.md','report.py','delivery.py')}
    result=dict(status=verdict,engineering='PASS_FULL_20098_FRAME_OWN_STATE_FOUR_BRANCH_REPLAY_AND_OFFICIAL_SCORING',
        input='SAME_SAVED_SOURCE_RAW_DEPTH; PHYSICAL_SURFACE_IDENTITY_AND_SENSOR_CALIBRATION_UNKNOWN',
        depth_increment='NO_PUBLICATION_INCREMENT' if changed==0 else 'SEE_ALL_SAME_SOURCE_DELTAS',
        frames=20098,arms=ARMS,metrics=metric,mechanism=audit,actual_legal_depth_deletions=deletions,
        same_prior_publication_changed_frames=states,changed_frames_against_Z4Q=changed,
        actual_deletion_physical_counts=dict(counters),accepted_action_physical_counts=dict(physical),
        original_action_followup_by_grade=grades,switch_changes=switch_changes,
        timing=dict(segment_seconds=seconds,publication_latency=latency,total_source_worker_seconds=sum(seconds.values())),
        initial_zero_frame_engineering_failure_preserved=True,policy_parameters_unchanged_on_restart=True,
        unscored_partial_source_validation_failure_preserved=True,formal_v3_restarted_from_frame1=True,
        weak_sources=['L3','LW'],independent_blind_validation=False,
        no_extra_model_HTTP_or_smoke=True,model_http=0,cost_usd=0,
        unfinished=['Depth performance above same-source original Z4Q is not established'] if changed==0 else [],
        next_step='Audit real original-Z4Q wrong accepted edges with paired competing candidate depth distributions before choosing a different depth representation; do not reduce the conflict gate solely to hit these labels.')
    write_new(HERE/'RESULTS.json',result)
    lines=['# DS37 稳定深度水平＋因果漂移尺度：完整同源回放',
        f'主判定：**{verdict}**。完整20,098帧、四分支自身状态回放与官方评分完成。新增模型HTTP/smoke、费用、训练、SAM3推理、深度补全、GPU和服务器作业均0。',
        '## 改了什么与工程边界',
        '保留原Z4Q全部二维/深度候选规则和状态事务；在真实D1_DELAYED/BIRTH_REFINE矩阵入口只增加可靠深度冲突单边否决。WLS对照逐帧复现旧DS32发布、原物理状态及完整深度来源状态。新分支使用同一精确anchor、连续版本和质量门槛，将短窗速度均值外推改为十点加权稳定水平；尺度由过去dz²/dt的median与225mm²/s先验共同增长，保留15mm测量floor。不除样本数、不clip大尺度、不挑峰、不跨风险/版本、不把接近认证为同鱼。公式/每点出处/原WLS斜率/实际dt均留在事务与EDGE_AUDIT。',
        '20项必要检查通过，真实F159 source→query→状态→首次发布及关闭模块复现完成。哈希路径和递归不可变source标准JSON字节缓存保持160帧所有科学trace逐行一致。只缓存被冻结sample完整内容，容器/engine每次重新读取；每500帧对照完整标准序列化，WLS每帧与旧档完整状态SHA核验。首次0帧源码哈希误拦截及v2未评分部分保留；随后修正“有效历史被旧WLS负外推连带判无效”的工程耦合。原WLS负预测保持负值/不可用诊断，新稳定水平独立有效，版本/时间/质量检查不变。v3输入/代码/评分重新冻结，四个来源工作进程均从帧1开始，不复用旧部分状态/输出。未按GT或指标调参数。详见REPORT_NOTES。工程通过不等于深度有效。',
        '## 全部真实指标',
        '|来源/帧数|分支|IDF1|HOTA|AssA|IDSW|FP|FN|',
        '|---|---|---:|---:|---:|---:|---:|---:|']
    for name in SEGMENTS:
        for arm in ARMS:
            m=metric['segments'][name]['metrics'][arm]
            lines.append(f'|{name} / {metric["segments"][name]["frames"]}|{arm}|{m["IDF1"]:.6f}|{m["HOTA"]:.6f}|{m["AssA"]:.6f}|{m["IDSW"]}|{m["FP"]}|{m["FN"]}|')
    lines.extend(['Feeding四段独立ID命名空间汇总（1471帧）：',
        '|分支|IDF1|HOTA|AssA|IDSW|FP|FN|','|---|---:|---:|---:|---:|---:|---:|'])
    for arm in ARMS:
        m=metric['feeding_pooled']['metrics'][arm];lines.append(f'|{arm}|{m["IDF1"]:.6f}|{m["HOTA"]:.6f}|{m["AssA"]:.6f}|{m["IDSW"]}|{m["FP"]}|{m["FN"]}|')
    lines.extend(['## LEVEL相对同源参照的真实差值',
        '|来源|相对参照|ΔIDF1|ΔHOTA|ΔAssA|ΔIDSW|ΔFP|ΔFN|','|---|---|---:|---:|---:|---:|---:|---:|'])
    for name in SEGMENTS:
        for base in ARMS[:-1]:
            d=metric['segments'][name]['deltas'][base]
            lines.append(f'|{name}|{base}|{d["IDF1"]:+.6f}|{d["HOTA"]:+.6f}|{d["AssA"]:+.6f}|{d["IDSW"]:+}|{d["FP"]:+}|{d["FN"]:+}|')
    lines.extend(['## 因果链与物理诊断',
        f'LEVEL实际删除{deletions}条原合法边；当前决策相对同一自身前态原策略改变发布{states}帧；相对独立原Z4Q改变{changed}帧。实际删除物理结果{dict(counters)}。LEVEL实际持久动作物理结果{dict(physical)}，这是整个原Z4Q＋否决分支的动作，不把原Z4Q恢复算成新增深度提交。',
        '|来源|合法查询边|WLS双深度可用边|LEVEL双深度可用边|LEVEL原始冲突|LEVEL实际删除|LEVEL改帧|',
        '|---|---:|---:|---:|---:|---:|---:|---:|'])
    for name in SEGMENTS:
        w,l=[mechanism[name]['counters'][a] for a in VETO_ARMS]
        lines.append(f'|{name}|{l.get("original_eligible_edges",0)}|{w.get("both_depth_usable_edges",0)}|{l.get("both_depth_usable_edges",0)}|{l.get("raw_conflicts",0)}|{l.get("legal_edges_deleted",0)}|{l.get("changed_frames",0)}|')
    lines.extend(['双深度可用边的分母包含原不合法边，合法性与信息可用性分列；全部缺失与被拒原因见MECHANISM_AUDIT。原始冲突不等于实际矩阵删除，更不等于选中动作改变。每次切换新增/消除/common逐条重新匹配，SWITCH_CHANGES保留完整记录，没有用净差冒充错误次数。',
        '原持久动作的事后正确/错误/不可评分与LEVEL来源解释：\n```json\n'+json.dumps(grades,ensure_ascii=False,indent=2)+'\n```',
        '原动作的评分reference与当前depth bank anchor可能不是同一帧，两个引用分别记录，不能无条件沿用旧答案。UNSCORABLE保持缺失，不叫安全保护成功。全部预测、实际START/访问/事务seal后才读取既有曝光GT/弱参考；不读GT raster或新的留出test。',
        '## 真实可视化、耗时和复现',
        'visuals/METRICS.svg和ELIGIBLE_CONFLICTS.svg为公开数值图。所有实际LEVEL矩阵删除、原Z4Q错误动作以及每来源最早可靠合法控制生成真实raw depth/已发布ID的anchor、决策前、当前、后一帧对照。后一帧只用于封存后展示，未进入当前决策，也没有修改过去发布。原像素只在private/cases；PRIVATE_VISUALS/PRIVATE_INVENTORY列真实路径、字节、SHA、原始depth与保存mask绑定和复现依赖，未公开RGB/GT raster。',
        f'来源工作进程累计{sum(seconds.values()):.3f}秒（四个来源并行CPU工作进程，不能当作端到端wall time）。每来源处理和三控制流程合计首次发布延迟见RESULTS.timing，未测实际在线系统，也不称实时部署。',
        '以当前代码的空输出目录及本轮固定基点提供相同私有DS14原观测/mask/原始深度、DS18证书和只读旧DS32/DS31封存；运行必要checks及真实slice、freeze、orchestrate。已运行目录不能覆盖。全部评分数学、包括动态导入的DS1 clear_step源码在START前绑定。',
        '## 分层判定与未完成项',
        '工程：全段、旧对照精确复现、单边/dummy/版本/preview/首次发布、全部seal与独立评分通过。输入：原depth同ROI、source去重、量测质量与版本可追溯；单mask表面物理身份、producer reset与传感器标定仍UNKNOWN。深度增量：只按同源真实指标与实际状态修改判断，旧WLS零作用仍保留。',
        'L3/LW使用未独立确认的预测派生参考，只能弱诊断；FishSA开发/验证是同录像曝光来源，Feeding也是已曝光片段，不能称新盲测或跨数据集泛化提升。数值尺度不是已标定概率，宽尺度覆盖不叫物理准确率。未完成边界：'+('; '.join(result['unfinished']) or '见逐源指标及来源限制')+'。',
        '## 唯一下一步（未启动）',result['next_step'],
        '## main交付',
        '代码、配置、必要测试及失败记录、完整公开日志/预测/逐边结果/指标/报告和聚合图普通提交到main，之后实际push并核验远端ref与每个公开blob。具体commit和远端SHA由REMOTE_VERIFICATION记录，私有像素不在Git。'])
    with (HERE/'FINAL_REVIEW.md').open('x',encoding='utf-8',newline='\n') as f:f.write('\n\n'.join(lines)+'\n')
    write_new(HERE/'REPORT_VALIDATION.json',dict(status='PASS_ALL_EIGHT_SOURCES_FOUR_ARMS_ALL_METRICS_REAL_ACTIONS_AND_BOUNDARIES',
        results=artifact(HERE/'RESULTS.json'),report=artifact(HERE/'FINAL_REVIEW.md'),code=artifact(__file__),
        written_utc=datetime.now(timezone.utc).isoformat(),model_http=0,cost_usd=0))
    print(json.dumps(dict(status=verdict,frames=20098,legal_deletions=deletions,changed_frames=changed)),flush=True)

if __name__=='__main__':main()
