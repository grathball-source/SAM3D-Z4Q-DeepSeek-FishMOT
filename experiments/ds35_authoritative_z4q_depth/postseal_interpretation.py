"""Interpret sealed measurements and final scores; no new forecasts or association."""
from common import *
from datetime import datetime,timezone
from statistics import mean,median

def main():
    from verify_inputs import verify_all
    verify_all()
    metrics=read(RUN/'METRICS.json')
    completion=read(HERE/'SCORER_SERIALIZATION_COMPLETION.json')
    assert completion['status']=='PASS'
    review=read(HERE/'POSTSEAL_MEASUREMENT_REVIEW.json')
    latency={}
    for name in SEGMENTS:
        ledger=list(rows(RUN/name/'public/PUBLISH_LEDGER.jsonl'))
        seconds=[r['receive_to_first_publish_seconds'] for r in ledger]
        summary=read(RUN/name/'public/RUN_SUMMARY.json')
        latency[name]=dict(frames=len(ledger),elapsed_replay_seconds=summary['elapsed_seconds'],
            first_publication_delay_frames_min=min(r['actual_delay_frames'] for r in ledger),
            first_publication_delay_frames_max=max(r['actual_delay_frames'] for r in ledger),
            receive_to_first_publish_seconds_mean=mean(seconds),
            receive_to_first_publish_seconds_median=median(seconds),
            receive_to_first_publish_seconds_max=max(seconds),
            scope='CPU saved-mask replay only; excludes upstream SAM3/sensor acquisition. '
                'Includes all four arms and provenance logging; no API. EOF flush included.')
    cases=[]
    for name in SEGMENTS:
        for event in read(RUN/name/'public/EVENTS.json')['DEPTH_OVERRIDE']:
            d=event.get('joint_decision',{})
            if not d.get('common_weights',{}).get('depth'):continue
            forecasts={}
            for candidate in d['scores']:
                for edge in candidate['edges']:
                    for row in edge['depth_rows']:
                        for public,p in row['detail']['forecasts'].items():
                            key=(row['frame'],public)
                            value=dict(post_frame=row['frame'],public=public,
                                model=p['status'],samples=p['samples'],sample_frames=p['sample_frames'],
                                sample_fact_ids=p['sample_fact_ids'],delta_seconds=p['delta_seconds'],
                                scale_mm=p['scale_mm'],time_scale_seconds=p['time_scale_seconds'],
                                slope_mm_s=p['slope_mm_s'],mu_mm=p['mu_mm'],
                                model_scale_is_not_calibrated_physical_accuracy=True)
                            if key in forecasts:assert forecasts[key]==value
                            forecasts[key]=value
            values=list(forecasts.values())
            cases.append(dict(segment=name,event=event['id'],q=event['q'],cutoff=event['decision_cutoff'],
                pre_counts={k:len(v) for k,v in d['pre_frames'].items()},
                reason=d['reason'],forecast_scale_range_mm=[min(p['scale_mm'] for p in values),max(p['scale_mm'] for p in values)],
                extrapolation_gap_range_seconds=[min(p['delta_seconds'] for p in values),max(p['delta_seconds'] for p in values)],
                forecasts=values,source=artifact(RUN/name/'public/EVENTS.json'),
                staged=event['restore']['staged']))
    write_new(HERE/'POSTSEAL_INTERPRETATION.json',dict(status='POSTSEAL_DESCRIPTIVE_ANALYSIS_ONLY',
        created_utc=datetime.now(timezone.utc).isoformat(),cases=cases,latency=latency,
        measurements=artifact(HERE/'POSTSEAL_MEASUREMENT_REVIEW.json'),metrics=artifact(RUN/'METRICS.json'),
        scorer_adapter=artifact(HERE/'SCORER_SERIALIZATION_COMPLETION.json'),helper=artifact(__file__),
        association_parameters_and_frozen_trial_unchanged=True,new_forecasts_or_rescored_choices=False,
        next_step_unstarted=True,new_model_http=0,cost_usd=0))
    counts=review['counts']
    table=['| 来源 | 事件 / q | pre点数 A/B | 外推间隔 s | 预测尺度 mm | 未提交原因 |',
        '| --- | --- | --- | --- | --- | --- |']
    for c in cases:
        table.append('| '+c['segment']+' | '+c['event']+' / '+str(c['q'])+' | '+
            '/'.join(str(c['pre_counts'][r]) for r in ('A','B'))+' | '+
            '–'.join(f'{v:.4f}' for v in c['extrapolation_gap_range_seconds'])+' | '+
            '–'.join(f'{v:.3f}' for v in c['forecast_scale_range_mm'])+' | '+c['reason']+' |')
    content=['# DS35 封存后解释与评分适配补充',
        '本说明在正式预测封存后产生。未修改冻结的runner、关联、门槛、参考、mask、q、代码或旧结果；没有新的方法试验。正式完整指标见FINAL_REVIEW.md。',
        '## 为什么新增提交为零',
        f'自动事件{counts["events"]}个；有首分离q为{counts["with_q"]}个；完整端点成本{counts["complete_endpoint_cost"]}个；'
        f'共同深度可用{counts["common_depth_available"]}个；最终合格提案与真实新增提交均0。'
        '这组递减计数是本轮冻结入口的有效支持范围，不能解释为整个视频没有深度、全部事件都无歧义或方法已被证伪。',
        '\n'.join(table),
        '开发和验证两个病例的十点拟合跨度约0.3秒，但查询在约0.9–5.7秒之后；封存预测尺度已超60mm门槛。'
        'LW两个病例只有1或2点，不能把没有测得的速度写成0，也不能跨身份风险补历史。'
        '表中的尺度来自旧WLS不确定性模型，未标定为真实物理误差；宽尺度并不证明当前传感器测量本身不可靠。'
        '本轮新增门槛确实排除了所有共同深度病例，因此不能声称测试了可靠深度实际提交后的真实效果。',
        f'930个纳入pre测量中，深度可用823个；{counts["partial_depth_pre_with_at_least_three_valid_points"]}个pre片段同时有合格和不合格深度点，'
        f'其中{counts["partial_depth_pre_without_observed_mixture_or_ownership_risk"]}个未记录混层/独立来源占用风险。'
        '此计数含未形成q的片段，只是观测机会；未重新拟合、跳过风险或增加可提交事件。'
        '普通深度缺测和身份来源风险应分别审查，不能把过滤测量用于连接风险两端。',
        '## 工程止损与科研结果分开',
        '原Z4Q继续运行自己的完整bank、alias、epoch和provenance；独立事件缓存不再阻断原BirthRefine/D1。'
        '失败保留本分支已经推进的状态。八段20,098帧的深度关闭分支逐帧复现原Z4Q，深度开启分支也没有新提交或发布变化。'
        '相对DS34恢复的成绩属于共用机制止损，新增深度增量为0。原Z4Q在Feeding的更多IDSW和HOTA/AssA退化仍保留，不能被IDF1净提升掩盖。',
        '全部首次发布实际延迟0–30帧，序列尾部EOF收齐；逐来源CPU回放耗时、实际收到保存观测到首次发布的均值/中位/最大值列于POSTSEAL_INTERPRETATION.json的latency。'
        '这不包括SAM3或传感器采集时间，也不是实时部署测量。',
        '## 追加评分适配及真实失败记录',
        '冻结score.py在LW MS1-F2896复算时失败；独立逐字段诊断发现两侧实际序列化内容完全一致。'
        'Python整数对象键3/106按数值排序，封存JSON字符串键按字典序排序，使原digest比较不同。'
        '追加score_serialized_v2.py仅将复算结果经过发布器等价JSON序列化后比较，保留选择、候选列表顺序、物理mapping、支持关系和全部数值。'
        '五项检查验证真实多位ID案例与choice/候选顺序/物理mapping/测量事实篡改拒绝，随后重新检查全部八段，再读取参考独立评分。'
        '旧冻结评分器、失败日志和seal保持不变；数学仍为原CLEAR/Identity/HOTA。'
        '追加检查的首次语法错误、过度转换混合键的失败测试夹具与失败JSON也保留；通过版写入独立V2结果。'
        '首次失败日志的终端GBK解码错误仅影响失败文本显示；原stderr文件与退出记录完整，后续在UTF-8终端环境执行。',
        '## 唯一未启动下一步',
        '沿用原Z4Q权威底座，在真实错误关联处审查局部双鱼原始深度的可区分性：同版本连续片段内区分缺测与混层，'
        '检查短跨度WLS外推尺度是否有因果观测支持，并与另一鱼及背景分布比较。先确定现有证据和不确定性模型是否支持区分，'
        '再决定下一次关联改动；不直接压低尺度或门槛凑提交。本步骤尚未启动。']
    with (HERE/'POSTSEAL_INTERPRETATION.md').open('x',encoding='utf-8',newline='\n') as output:
        output.write('\n\n'.join(content)+'\n')
    print('Postseal interpretation and scorer repair documented',len(cases),flush=True)

if __name__=='__main__':main()
