"""Read completed L3 source/publication records only; no reference or scoring."""
from common import *
import sys


def block_reference(event, args):
    if event != 'open' or not isinstance(args[0], (str, bytes, os.PathLike)):
        return
    path = str(args[0]).replace('\\', '/').lower()
    if any(x in path for x in ('metrics.json', 'reference_matches', 'event_audit',
            'automatic_reconnect_audit', 'local_return_audit', 'gt_raster',
            'labels_640x360', 'labels_original', 'labels_source', 'labels_recovered',
            'truth.jsonl', 'sealed_test', '/rgb/', '/rgb_640x360/', 'restoration/v3/')):
        raise RuntimeError('Reference/metric/pixel read is outside this review: '+path)


sys.addaudithook(block_reference)


def main():
    public = HERE/'slice_r1/L3/public'
    summary = read(public/'RUN_SUMMARY.json')
    access = read(public/'ACCESS.json')
    assert summary['frames'] == 3030 and access['status'] == 'NO_GT_RGB_RESTORED_NETWORK'
    scorer = module('ds19_source_only_publication_checks', HERE/'score.py')
    chain = scorer.verify_publication_sources(public)
    by_arm = {a:{} for a in EVENT_ARMS}
    commits = []
    files = ('predictions.jsonl.gz', 'PUBLISH_LEDGER.jsonl', 'TRANSACTIONS.jsonl.gz',
        'DEPTH_STATES.jsonl.gz', 'BIRTHS.jsonl.gz', 'ORDER_EVIDENCE.jsonl.gz',
        'EVENTS.json', 'RUN_SUMMARY.json', 'ACCESS.json', 'MIXED_DEPTH.jsonl.gz')
    evidence = [artifact(public/f) for f in files]
    with gzip.open(public/'TRANSACTIONS.jsonl.gz', 'rt', encoding='utf-8') as f:
        header = json.loads(next(f))
    if header.get('kind') == 'CHUNKED_JSONL_REFERENCE':
        evidence.extend(artifact(public/p['name']) for p in header['parts'])
    for transaction in rows(public/'TRANSACTIONS.jsonl.gz'):
        arm = transaction['arm']
        if arm not in EVENT_ARMS:
            continue
        trace = transaction['controller_trace']
        compact = dict(frame=transaction['frame'], global_frame=transaction['global_frame'],
            active_event=transaction['active_event'], signal=transaction['signal'],
            published_mapping=transaction['actual_published_mapping'],
            previous_mapping=transaction['previous_mapping'], epochs=transaction['epochs'],
            bank_anchors=transaction['bank_anchors'], aliases=transaction['actual_alias_targets'],
            original_proposals=trace.get('ds19_event_return_proposals'),
            separation=trace.get('activity_reference_separation'),
            reference_binding_state=trace.get('ds18_reference_binding_state'),
            stage=transaction.get('local_return_stage'), return_record=transaction.get('return_record'))
        by_arm[arm][transaction['frame']] = compact
        if compact['return_record']:
            commits.append((arm, compact['return_record']))
    events = read(public/'EVENTS.json')
    records = []
    for arm, commit in commits:
        assert commit['status'] == 'EVENT_LOCAL_RETURN_COMMITTED'
        frame = commit['frame']
        e = next(e for e in events[arm] if e['id'] == commit['event'])
        for action in commit['original_proposal_trace_events']:
            source, target = action['native_id'], action['canonical_id']
            confirmations = []
            for f, packet in by_arm[arm].items():
                if f > frame or packet['active_event'] != e['id']:
                    continue
                proposal = packet.get('original_proposals') or {}
                carried = proposal.get('carried_original_confirmations', {}).get(str(source))
                if carried and carried['target'] == target:
                    confirmations.append(dict(frame=f, global_frame=packet['global_frame'],
                        count=carried['count'], start_time=carried['start_time'], time=carried['time'],
                        pending_is_not_identity_commit=True))
            first = commit['actual_first_publication'][str(source)]
            original_global_first = SEGMENTS['L3'][0] + first['frame'] - 1
            assert by_arm[arm][first['frame']]['published_mapping'][str(source)] == first['public_id']
            following = by_arm[arm].get(frame+1)
            if following:
                assert following['published_mapping'][str(source)] == target
                assert following['aliases'][str(source)] == target
            entry = by_arm[arm][frame]['separation']['immutable_reference_registry']
            assert entry['references'][str(target)]['anchor'] == action['old_anchor']
            actual = by_arm[arm][frame]['bank_anchors'][str(target)]
            assert actual['frame'] == frame and actual['native_id'] == source and actual['canonical_id'] == target
            binding = action['association_evidence_bindings']
            assert action['association_evidence_sha256'] == scorer.evidence_digest(binding)
            records.append(dict(arm=arm, event=e['id'], generation=commit['generation'],
                source=source, target=target, commit_local_frame=frame,
                commit_original_frame=by_arm[arm][frame]['global_frame'],
                original_birth_local_frame=action['birth_frame'],
                original_birth_original_frame=SEGMENTS['L3'][0]+action['birth_frame']-1,
                origin_rule=action['origin_rule'], natural_confirmation_frames=confirmations,
                accepted_confirmations=action['confirmations'],
                original_candidate=action, commit=commit,
                first_actual_source_publication=dict(**first, original_frame=original_global_first),
                already_public_before_commit=first['frame']<frame,
                delay_since_first_source_publication_frames=frame-first['frame'],
                immutable_entry=entry, actual_live_anchor=actual,
                next_frame_own_state=following,
                actual_late_q_in_prefix=e['q'], event_end=e['end'], event_status=e['status'],
                timeout_covered_by_prefix=e['status']=='TIMEOUT',
                prefix_ends_before_future_event_outcome=e['end'] is None,
                actual_reference_physical='UNKNOWN_NOT_SCORED', prior_public_origin='UNKNOWN_NOT_SCORED'))
    output = dict(status='SOURCE_PUBLICATION_CHAIN_PASS', segment='L3', frames=summary['frames'],
        original_frames=[0,3029], GT_read=False, metrics_read=False, RGB_read=False,
        new_prediction=False, new_model_http=0, method_source=artifact(HERE/'controller.py'),
        helper=artifact(HERE/'review_real_return_slice.py'), publication_chain=chain,
        source_artifacts=evidence, commits=records,
        no_commit_is_valid_result=not records,
        scope='Real closed prefix; no desired mapping or physical correctness gate')
    write_new(HERE/'REAL_RETURN_SLICE_REVIEW.json', output)
    lines = ['# DS19 真实 L3 前缀：source→proposal→stage→首次发布复核', '',
        '只读已完成的 local1–3030 / original0–3029 前缀。未读 GT、metrics、RGB 或物理评分，未改源码或重跑预测。', '',
        f"发布链检查：**{chain['status']}**；完整 {chain['frames']} 帧、6 列发布与原始 source/cache/ledger 绑定通过。", '',
        f"实际局部提交记录：{len(records)} 个 source（不同分支分别计），不是物理正确率。", '']
    for r in records:
        lines += [f"## {r['arm']} / {r['event']}", '',
            f"原 {r['origin_rule']} 自然 {r['accepted_confirmations']} 次确认；local{r['commit_local_frame']} / original{r['commit_original_frame']} 实际提交 source{r['source']}→public{r['target']}。", '',
            '确认进度：'+', '.join(f"local{x['frame']} count{x['count']}" for x in r['natural_confirmation_frames'])+'；最后确认由自然 accepted 原事件记录绑定。', '',
            f"source 首次实际发布 local{r['first_actual_source_publication']['frame']} / original{r['first_actual_source_publication']['original_frame']}，public{r['first_actual_source_publication']['public_id']}；此前已公开={r['already_public_before_commit']}，延迟 {r['delay_since_first_source_publication_frames']} 帧。不能称首次 source 发布前即恢复。", '',
            f"实际 live anchor={r['actual_live_anchor']}；不可变进入 registry 中旧 anchor 仍等于原 candidate old_anchor；下一帧本分支 alias/public mapping 保持该提交。", '',
            f"此前缀 event q={r['actual_late_q_in_prefix']}、end={r['event_end']}、status={r['event_status']}；timeout 覆盖={r['timeout_covered_by_prefix']}。未覆盖的以后 q/timeout 仍待完整段验证，不能用旧结果代替。", '',
            '所有组外比对为真；matrix、确认、当前量测与旧参考来源均来自实际已运行记录。物理正确、进入前 public 标签是否已错以及完整段指标仍 UNKNOWN，等待全段预测封存后独立评分。', '']
    if not records:
        lines += ['前缀无局部提交。如实保留候选/拒绝日志，不要求目标映射或改变门槛以产生提交。', '']
    lines += ['## 边界', '',
        '帧编号公式：original = segment_start + local − 1。L3 segment_start=0，因此local3025对应原帧3024。confirmations是原算法接受事实；未accepted pending本身不是身份提交。', '',
        '记录保留全部实态与路径/字节/SHA。公共发布的一对一/来源独占不证明物理单鱼；前缀工程通过也不证明深度增量。']
    (HERE/'REAL_RETURN_SLICE_REVIEW.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    print('Source-only L3 publication review PASS', len(records), 'committed source records')


if __name__ == '__main__':
    main()
