"""Read-only L3 addendum: sealed source transactions and public postscore scalars."""
from common import HERE,RUN,ARMS,artifact,read,rows,sha,write_new
from collections import Counter

def main():
    m=read(RUN/'METRICS.json');p=read(RUN/'SCORE_PROVENANCE.json')
    assert m['status']=='SCORED_AFTER_ALL_SIX_ARMS_EIGHT_SEALS'
    assert m['all_seal']==artifact(RUN/'ALL_PREDICTIONS_SEALED.json')
    assert p['scientific_source_and_runtime_verified'] and p['reference_opened_after_all_seals']
    public=RUN/'L3/public';seal=read(public/'PREDICTIONS_SEALED.json')
    for filename in ('predictions.jsonl.gz','TRANSACTIONS.jsonl.gz','EVENTS.json'):
        assert sha(public/filename)==seal['artifacts_sha256'][filename]
    names=('PREDICTIONS_SEALED.json','predictions.jsonl.gz','TRANSACTIONS.jsonl.gz',
        'EVENTS.json','AUTOMATIC_RECONNECT_AUDIT.json','METRICS.json')
    sources=[artifact(public/x) for x in names]+[artifact(RUN/'SCORE_PROVENANCE.json'),
        artifact(RUN/'METRICS.json'),artifact(HERE/'controller.py')]
    audit=read(public/'AUTOMATIC_RECONNECT_AUDIT.json');events=read(public/'EVENTS.json')
    event={arm:[{k:x.get(k) for k in ('id','suspect_frame','confirm_frame','q','end','status',
        'member_sources','public_ids','group_source','restore')} for x in events[arm] if x['id']=='MS1-F2873']
        for arm in ARMS[2:]}
    publication={arm:[] for arm in ARMS};last={};times={};first_difference=None
    for row in rows(public/'predictions.jsonl.gz'):
        times[row['frame']]=row['time'];current={}
        for arm in ARMS:
            value=next((x['id'] for x in row['variants'][arm] if x['mask']=='n:47'),None)
            current[arm]=value
            if last.get(arm,'UNSEEN')!=value:
                publication[arm].append(dict(frame=row['frame'],global_frame=row['global_frame'],public=value))
            last[arm]=value
        if first_difference is None and current['ACTIVITY_ORDER']!=current['Z4Q_FROZEN']:
            first_difference=dict(frame=row['frame'],global_frame=row['global_frame'],mapping=current)
    selected={arm:[] for arm in ARMS[1:]};reason_counts={arm:Counter() for arm in ARMS[1:]}
    retirements={};final={}
    for row in rows(public/'TRANSACTIONS.jsonl.gz'):
        arm=row['arm'];f=row['frame'];trace=row['controller_trace'];s=trace.get('activity_reference_separation',{})
        checks=[x for x in trace.get('ds16_original_automatic_edge_checks',[]) if x.get('native_id')==47]
        for check in checks:reason_counts[arm][check.get('reason','UNKNOWN')]+=1
        pending=trace.get('pending_birth',{}).get('47')
        if pending and pending.get('retired_reason') and arm not in retirements:
            retirements[arm]=dict(frame=f,global_frame=row['global_frame'],pending=pending)
        if f in (3025,3072,3175,3176,3710):
            own=dict(frame=f,global_frame=row['global_frame'],time=times[f],
                actual_mapping47=row['actual_published_mapping'].get('47'),
                actual_alias47=row.get('actual_alias_targets',{}).get('47'),
                active_event=row.get('active_event'),signal=row.get('signal'),
                edges=[x for x in trace.get('edges',[]) if x.get('native_id')==47],
                evidence_gate_checks=checks,pending=pending,
                anonymous_native_keys=s.get('anonymous_native_keys'),
                activity=s.get('public_activity'),reference_status=s.get('reference_status'),
                local_fallback=trace.get('merge_split_local_fallback'),
                actual_bank9_anchor=row.get('bank_anchors',{}).get('9'))
            selected[arm].append(own)
        final[arm]=dict(frame=f,alias47=row.get('actual_alias_targets',{}).get('47'),
            published47=row['actual_published_mapping'].get('47'),bank9=row.get('bank_anchors',{}).get('9'))
    correct=[x for x in audit['arms']['Z4Q_FROZEN'] if x['source']==47]
    assert len(correct)==1 and correct[0]['frame']==3025 and correct[0]['actual_reference_physical']=='CORRECT'
    keys=('frame','global_frame','source','target','origin_rule','actual_reference_physical',
        'prior_public_reference_status','relations','query_match','bank_match','actual_old_anchor')
    result=dict(status='POSTSCORE_L3_SHARED_GATE_DIVERGENCE',source_only_transactions=True,
        no_gt_pixels_read=True,no_new_prediction_or_test=True,helper=artifact(__file__),sources=sources,
        first_source47_publication_difference=first_difference,publication47=publication,
        original_accepted_action={k:correct[0][k] for k in keys},event=event,
        selected_actual_transactions=selected,gate_reason_counts={k:dict(v) for k,v in reason_counts.items()},
        first_actual_pending_retirement=retirements,final_actual_state=final,
        metrics=read(public/'METRICS.json')['metrics'],
        conclusion='Original depth edge and real source activity are restored, but the new common protected-target joint-only gate blocks the actual correct D1 edge. The automatic event never reaches split q and times out after association windows. This is shared state/identity policy failure, not mixed-depth or ordinal evidence increment.')
    write_new(HERE/'POSTSEAL_STATE_L3_ADDENDUM.json',result)
    lines=['# DS18 L3 共用身份门槛丢失原正确重接：追加审计','',
        '**实际活动字段修复仍生效，但新增受保护target的joint-only身份门槛阻断了原正确D1，整体语义和性能未通过。**','',
        '完全封存与总SCORE_PROVENANCE通过后，只读真实事务及公共独立评分摘要；未读取GT raster、RGB、私有像素，未重跑测试/预测/反事实。','',
        '## 真实读取链','',
        '- native47在local2891/global2890首次公开47。原Z4Q在local3025/global3024，由D1_DELAYED首次写出47→9并持续到末帧；独立实际bank物理判定CORRECT，公共起源CONSISTENT。',
        '- 原edge读旧anchor2712/native9；history depth722.703186，query678.225586，residual44.477600mm、原tolerance60mm，motion cost0.047272、totalcost0.748384，原alternative为空。',
        '- DS16曾因冻结活动使partner5进入alternative（残差39.550781），产生partner_ambiguous。DS18 ACTIVITY/MIXED的alternative恢复为空，证明活动修复没有失效。',
        '- 但DS18新的edge_veto随后在写alias/bank之前命中WAIT_JOINT_GROUP_TRANSACTION；不是current measurement缺失，也不是source47身份匿名：此帧anonymous仅[6,9]。原因是candidate target公共9仍被active event保护。',
        '- 公共6真实活动推进3025；失踪公共9最后真实活动2890，clean/view冻结anchor2712。没有凭空给失踪9更新时间，也没有把group深度写作个体clean。',
        '- MS1-F2873在2873疑似、2874确认，member sources[6,9]，至3175 TIMEOUT始终q=None。联合stage出口从未产生；原6秒出生/返回资格先消失，超时释放不能凭空恢复旧资格。',
        '- 所有新分支native47到3710仍公开47；并非晚接回。该损失属于共用身份stage政策，不能归给mixed测量质量或ordinal顺序。','',
        '## 实际整段指标','',
        '| 分支 | IDF1 | HOTA | AssA | IDSW | FP | FN |','|---|---:|---:|---:|---:|---:|---:|']
    for arm in ARMS:
        value=result['metrics'][arm]
        lines.append('| '+arm+' | '+' | '.join(f"{value[x]:.6f}" if x in ('IDF1','HOTA','AssA') else str(value[x]) for x in ('IDF1','HOTA','AssA','IDSW','FP','FN'))+' |')
    lines.extend(['','这是同源完整段真实结果；L3参考为已有预测派生弱参考，不能上升为独立人工GT。少一个IDSW与较低IDF1/HOTA/AssA同时成立，不能仅用IDSW减小称成功。','',
        '## 可追溯性与范围','',
        'JSON绑定封存预测、事务、事件、独立自动判定、指标及controller真实路径/字节/SHA；保存3025/3072/3175/3176/末帧实态、pending实际退休与公开映射，未修改此前POSTSEAL_STATE_CASES报告。',
        '复现：`python experiments/ds18_association_evidence_interface_repair/review_state_l3_postscore.py`，只读报告脚本，无科研运行。',''])
    with (HERE/'POSTSEAL_STATE_L3_ADDENDUM.md').open('x',encoding='utf-8',newline='\n') as out:out.write('\n'.join(lines))

if __name__=='__main__':main()
