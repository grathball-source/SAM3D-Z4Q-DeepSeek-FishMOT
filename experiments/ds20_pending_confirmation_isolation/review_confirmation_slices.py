"""Source-only review of the real pending competition and retained local return."""
import guard
from common import *
from collections import Counter
from audit_confirmation import audit_segment
import argparse

CASES = (
    dict(segment='feeding_000000_000199', source=38, target=7, protected=16,
         start=190, stop=200, isolated='ACTIVITY_ISOLATED', old='ACTIVITY_RETURN', order='ACTIVITY_ORDER'),
    dict(segment='LW', source=32, target=24, protected=7,
         start=947, stop=960, isolated='MIXED_ISOLATED', old='MIXED_RETURN', order='MIXED_ORDER'))
WINDOWS = {'feeding_000000_000199': (190, 200), 'LW': (947, 960), 'L3': (3018, 3030)}


def ordinary_events(transaction, native):
    return [e for e in transaction['controller_trace'].get('events', [])
            if e.get('kind') == 'reconnect' and e.get('native_id') == native]


def compact(transaction, native):
    trace = transaction['controller_trace']
    proposals = trace.get('ds19_event_return_proposals') or {}
    return dict(frame=transaction['frame'], original_frame=transaction['global_frame'],
        arm=transaction['arm'], event=transaction.get('active_event'),
        ordinary_events=ordinary_events(transaction, native),
        actual_public=transaction['actual_published_mapping'].get(str(native)),
        actual_alias=transaction['actual_alias_targets'].get(str(native)),
        proposal_checks=[c for c in proposals.get('checks', []) if c.get('native_id') == native],
        accepted_protected_proposals=[e for e in proposals.get('accepted', [])
                                       if e.get('native_id') == native],
        carried_pending=proposals.get('carried_original_confirmations', {}).get(str(native)),
        isolation=trace.get('ds20_pending_isolation'),
        stage=transaction.get('local_return_stage'), return_record=transaction.get('return_record'))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='CONFIRMATION_SLICE_CHECKS.json')
    args = parser.parse_args()
    output_path = (HERE/args.output).resolve()
    assert output_path.parent == HERE.resolve() and output_path.suffix == '.json'
    assert not output_path.exists() and not output_path.with_suffix('.md').exists(), 'review outputs are exclusive'
    prefix = read(HERE/'PREFIX_CHECKS.json')
    publication = read(HERE/'REAL_PREFIX_SOURCE_CHECKS.json')
    assert prefix['status'] == publication['status'] == 'PASS'
    sources = (HERE/'review_confirmation_slices.py', HERE/'controller.py', HERE/'runner.py',
               HERE/'common.py', HERE/'guard.py', HERE/'score.py', HERE/'audit_confirmation.py',
               HERE/'report.py')
    before = {str(p): sha(p) for p in sources}
    adapter = module('ds20_source_confirmation_review_controller', HERE/'controller.py')
    new = {}; old = {}; artifacts = []; invalidations = Counter(); store_rows = 0
    issues = []; key_examples = []; all_commits = []; progress = {}; publications = {}
    actual_pending_checks = {}; actual_window_restarts = []; ordinary_counts_not_imported = []
    for name in WINDOWS:
        record = prefix['checks'][name]
        public = Path(record['predictions']['path']).resolve().parent
        assert (public.name == 'public' and public.parent.name == name
                and public.parents[2] == HERE.resolve()
                and public.parents[1].name.startswith('slice_'))
        actual_pending_checks[name] = audit_segment(name, public, expected_frames=record['frames'])
        for key in ('predictions', 'access', 'events', 'source_manifest'):
            verify_item(record[key])
        new[name] = {}
        path = public/'TRANSACTIONS.jsonl.gz'
        artifacts.append(artifact(path))
        for transaction in rows(path):
            arm, frame = transaction['arm'], transaction['frame']
            if WINDOWS[name][0] <= frame <= WINDOWS[name][1]:
                new[name][arm, frame] = transaction
            if arm not in ISOLATED_ARMS:
                continue
            audit = transaction['controller_trace']['ds20_pending_isolation']
            publications[name, arm, frame] = {key: transaction[key] for key in (
                'actual_published_mapping', 'actual_alias_targets')}
            store_rows += 1
            if audit['ordinary_pending_after'] != audit['ordinary_pending_after_proposal']:
                issues.append(dict(segment=name, arm=arm, frame=frame,
                    failure='EVENT_PROPOSAL_CHANGED_ORDINARY_PENDING'))
            assert audit['independent_confirmation_store']
            assert audit['original_matrix_confirmation_and_windows_unchanged']
            after = audit['event_confirmations_after']
            loaded = set(audit['proposal_loaded_confirmations'])
            ordinary_counts_not_imported.extend(dict(segment=name, arm=arm, frame=frame, record=record)
                for record in audit['ordinary_protected_confirmations_not_imported'])
            if after:
                progress.setdefault((name, arm), []).append(dict(frame=frame, confirmations=after))
            keys = [r['key'] for r in after]
            assert len(keys) == len(set(keys)), (name, arm, frame)
            ordinary_accepted = set(audit['ordinary_accepted_sources'])
            for confirmation in after:
                identity, pending = confirmation['identity'], confirmation['pending']
                assert set(identity) == {'event', 'generation', 'native', 'public', 'origin_rule',
                    'source_version', 'identity_version', 'anchor'}
                assert confirmation['key'] == adapter.M._digest(identity)
                assert pending['target'] == identity['public'] and pending['count'] >= 1
                assert pending['frame'] <= frame and identity['anchor']['frame'] < frame
                assert identity['origin_rule'] == 'D1_DELAYED'
                if confirmation['key'] not in loaded and pending['count'] != 1:
                    issues.append(dict(segment=name, arm=arm, frame=frame,
                        failure='FRESH_EVENT_KEY_IMPORTED_ORDINARY_COUNT', confirmation=confirmation))
                if identity['native'] in ordinary_accepted:
                    issues.append(dict(segment=name, arm=arm, frame=frame,
                        failure='ORDINARY_ACCEPTED_SOURCE_RETAINED_EVENT_CONFIRMATION',
                        confirmation=confirmation))
                if len(key_examples) < 6:
                    key_examples.append(dict(segment=name, arm=arm, frame=frame,
                                             confirmation=confirmation))
            proposals = transaction['controller_trace'].get('ds19_event_return_proposals') or {}
            for action in proposals.get('accepted', []):
                if action['origin_rule'] != 'D1_DELAYED':
                    continue
                prior = [r for r in audit['event_confirmations_before'] if r['key'] in loaded
                    and r['identity']['event'] == transaction['active_event']
                    and r['identity']['native'] == action['native_id']
                    and r['identity']['public'] == action['canonical_id']
                    and r['identity']['origin_rule'] == action['origin_rule']]
                if len(prior) != 1 or action['confirmations'] != prior[0]['pending']['count']+1:
                    issues.append(dict(segment=name, arm=arm, frame=frame,
                        failure='EVENT_ACCEPTED_WITHOUT_PRIOR_INDEPENDENT_CONFIRMATION',
                        action=action, actual_loaded_prior=prior))
            for invalidated in audit['invalidated']:
                invalidations[invalidated['reason']] += 1
                if invalidated.get('key') in keys:
                    renewed = next(r for r in after if r['key'] == invalidated['key'])
                    fresh = (invalidated['reason'] == 'ORIGINAL_CONFIRMATION_WINDOW_EXPIRED'
                        and renewed['pending']['count'] == 1 and renewed['pending']['frame'] == frame
                        and renewed['pending']['start_time'] == renewed['pending']['time'])
                    if fresh:
                        actual_window_restarts.append(dict(segment=name, arm=arm, frame=frame,
                            invalidated=invalidated, fresh_confirmation=renewed))
                    else:
                        issues.append(dict(segment=name, arm=arm, frame=frame,
                            failure='INVALIDATED_EXACT_KEY_RETAINED', record=invalidated))
                if 'identity' in invalidated:
                    assert invalidated['key'] == adapter.M._digest(invalidated['identity'])
            commit = transaction.get('return_record')
            if commit:
                all_commits.append(dict(segment=name, arm=arm, transaction=transaction))
        old[name] = {}
        old_public = DS19/'run'/name/'public'
        path = old_public/'TRANSACTIONS.jsonl.gz'
        seal = read(old_public/'PREDICTIONS_SEALED.json')
        assert sha(path) == seal['artifacts_sha256'][path.name]
        artifacts.append(artifact(path))
        for transaction in rows(path):
            if transaction['frame'] > record['frames']:
                break
            if WINDOWS[name][0] <= transaction['frame'] <= WINDOWS[name][1]:
                old[name][transaction['arm'], transaction['frame']] = transaction
    cases = []
    for spec in CASES:
        name, native, isolated = spec['segment'], spec['source'], spec['isolated']
        selected = []; mismatches = []; invalidated_by_ordinary = []; expected_actions = []; actual_actions = []
        accepted_confirmation_lifecycle = []; lifecycle_valid = True
        for frame in range(spec['start'], spec['stop']+1):
            actual = new[name][isolated, frame]
            archived = old[name][spec['old'], frame]
            ordinary = old[name][spec['order'], frame]
            a, b, c = compact(actual, native), compact(archived, native), compact(ordinary, native)
            selected.append(dict(isolated=a, archived_coupled=b, archived_no_local_return=c))
            if a['actual_public'] != c['actual_public'] or a['actual_alias'] != c['actual_alias']:
                mismatches.append(dict(frame=frame, actual=a['actual_public'], ordinary=c['actual_public'],
                    actual_alias=a['actual_alias'], ordinary_alias=c['actual_alias']))
            for event in c['ordinary_events']:
                if event.get('accepted') and event['canonical_id'] == spec['target']:
                    expected_actions.append(dict(frame=frame, action=event))
            for event in a['ordinary_events']:
                if event.get('accepted') and event['canonical_id'] == spec['target']:
                    actual_actions.append(dict(frame=frame, action=event))
                    audit = a['isolation']
                    prior = [r for r in audit['event_confirmations_before']
                             if r['identity']['native'] == native]
                    remaining = [r for r in audit['event_confirmations_after']
                                 if r['identity']['native'] == native]
                    exited = [r for r in audit['invalidated']
                              if (r.get('identity') or {}).get('native') == native]
                    recorded_exit_keys = {r['key'] for r in exited}
                    valid = not remaining and all(r['key'] in recorded_exit_keys for r in prior)
                    lifecycle_valid &= valid
                    accepted_confirmation_lifecycle.append(dict(frame=frame,
                        source=native, ordinary_target=event['canonical_id'],
                        event_confirmations_before_accept=prior,
                        event_confirmations_after_accept=remaining,
                        actual_exits_this_frame=exited,
                        status=('EXISTING_EXACT_KEY_INVALIDATED' if prior else
                                'NO_EVENT_CONFIRMATION_PRESENT_AT_ORDINARY_ACCEPT'),
                        no_old_event_confirmation_survives=valid))
            invalidated_by_ordinary.extend(dict(frame=frame, record=r)
                for r in a['isolation']['invalidated'] if
                (r.get('identity') or {}).get('native') == native and r['reason'] in (
                    'ORDINARY_SOURCE_ALREADY_RECONNECTED', 'IDENTITY_VERSION_CHANGED',
                    'SOURCE_RETIRED_BY_ORDINARY_LIFECYCLE', 'ORDINARY_RECONNECT_ACCEPTED_THIS_FRAME'))
        same_confirmation = [(r['frame'], r['action']['confirmations']) for r in actual_actions] == [
            (r['frame'], r['action']['confirmations']) for r in expected_actions]
        if mismatches or not same_confirmation or not expected_actions or not lifecycle_valid:
            issues.append(dict(segment=name, source=native, failure='REAL_COMPETITION_NOT_ISOLATED',
                mismatches=mismatches, actual_actions=actual_actions, expected_actions=expected_actions,
                actual_source_version_invalidation=invalidated_by_ordinary,
                actual_accepted_confirmation_lifecycle=accepted_confirmation_lifecycle))
        cases.append(dict(**spec, actual_trace_rows=selected,
            actual_ordinary_confirmations=actual_actions, archived_ordinary_confirmations=expected_actions,
            actual_source_version_invalidations=invalidated_by_ordinary,
            actual_accepted_confirmation_lifecycle=accepted_confirmation_lifecycle,
            no_event_confirmation_survives_ordinary_accept=lifecycle_valid,
            published_mapping_and_alias_match_ordinary_control=not mismatches,
            natural_confirmation_timing_matches_ordinary_control=same_confirmation,
            physical_identity='UNKNOWN_NOT_SCORED'))
    retained = []
    for item in all_commits:
        if item['segment'] != 'L3':
            continue
        transaction = item['transaction']; commit = transaction['return_record']; frame = transaction['frame']
        arm = item['arm']; archived_arm = 'ACTIVITY_RETURN' if arm == 'ACTIVITY_ISOLATED' else 'MIXED_RETURN'
        archived = old['L3'][archived_arm, frame].get('return_record')
        assert commit['status'] == 'EVENT_LOCAL_RETURN_COMMITTED'
        if not archived or commit['selected'] != archived['selected']:
            issues.append(dict(segment='L3', arm=arm, frame=frame,
                failure='NATURAL_RETURN_CHANGED', actual=commit, archived=archived))
        confirmations = []
        for packet in progress.get(('L3', arm), []):
            if packet['frame'] >= frame:
                continue
            for record in packet['confirmations']:
                identity = record['identity']
                if (identity['event'] == commit['event'] and
                        commit['selected'].get(str(identity['native'])) == identity['public']):
                    confirmations.append(dict(frame=packet['frame'], confirmation=record))
        for action in commit['original_proposal_trace_events']:
            source, target = action['native_id'], action['canonical_id']
            assert action['accepted'] and action['edge_veto']['event_return_routed']
            assert transaction['actual_published_mapping'][str(source)] == target
            assert transaction['actual_alias_targets'][str(source)] == target
            assert transaction['bank_anchors'][str(target)]['frame'] == frame
            if frame < prefix['checks']['L3']['frames']:
                following = publications['L3', arm, frame+1]
                assert following['actual_published_mapping'][str(source)] == target
                assert following['actual_alias_targets'][str(source)] == target
            assert source in transaction['controller_trace']['ds20_pending_isolation']['confirmation_consumed_by_commit']
        retained.append(dict(segment='L3', arm=arm, frame=frame, original_frame=transaction['global_frame'],
            actual_return=commit, actual_confirmation_progress=confirmations,
            original_candidate_count=[a['confirmations'] for a in commit['original_proposal_trace_events']],
            matching_archived_return=archived, physical_identity='UNKNOWN_NOT_SCORED'))
    if {r['arm'] for r in retained} != set(ISOLATED_ARMS):
        issues.append(dict(segment='L3', failure='ARCHIVED_NATURAL_RETURN_NOT_RETAINED_IN_BOTH_ARMS',
                          actual_committed_arms=[r['arm'] for r in retained]))
    stable = all(sha(p) == before[str(p)] for p in sources)
    if not stable:
        issues.append(dict(failure='REVIEW_SOURCES_CHANGED_DURING_EXECUTION'))
    output = dict(status='PASS' if not issues else 'FAIL', GT_read=False, metrics_read=False,
        new_association=False, new_model_http=0, cost_usd=0, method='REAL_CURRENT_SOURCE_AND_SEPARATE_CONFIRMATION_STORE',
        prefix_record=artifact(HERE/'PREFIX_CHECKS.json'), publication_record=artifact(HERE/'REAL_PREFIX_SOURCE_CHECKS.json'),
        source_artifacts=artifacts, actual_test_sources=before, source_stable_during_tests=stable,
        isolated_trace_rows_checked=store_rows, version_anchor_key_examples=key_examples,
        actual_pending_state_checks=actual_pending_checks,
        original_window_expiry_actual_fresh_restarts=actual_window_restarts,
        actual_ordinary_protected_counts_not_imported=ordinary_counts_not_imported,
        actual_invalidation_reasons=dict(invalidations), competition_cases=cases,
        retained_natural_returns=retained, failures=issues,
        qualification='Engineering regression only; no physical mapping grades or performance claims')
    write_new(output_path, output)
    lines = ['# DS20 真实确认隔离切片', '',
        '只读三个实际源前缀，不读 GT、metrics、RGB，不重新关联，不手工认证观测。', '',
        f"判定：**{output['status']}**。六列保留全部原 mask 与唯一公开 ID；四归档列逐帧精确复现 DS19。", '',
        f'检查 {store_rows} 条隔离分支记录：普通确认自然推进；私有事件 proposal 前后普通 pending 一致。', '']
    for case in cases:
        frames = ', '.join(str(r['frame']) for r in case['actual_ordinary_confirmations'])
        lines += [f"## {case['segment']} / source{case['source']}", '',
            f"保护候选 target{case['protected']} 与普通 target{case['target']}分别存储。普通自然提交 local{frames}；",
            f"与冻结无局部返回控制的确认时刻一致={case['natural_confirmation_timing_matches_ordinary_control']}；实际公开 mapping/alias 一致={case['published_mapping_and_alias_match_ordinary_control']}。", '',
            '普通接受后事件确认必须为空；接受前存在精确旧 key 时才要求实际失效记录。已提前退出或从未存入的确认如实标注，不补造失效日志。语义键、计数、原因及首次发布可逐帧回查 JSON。物理正确性尚未评分。', '']
    for result in retained:
        lines += [f"## L3 / {result['arm']}", '',
            f"local{result['frame']} / original{result['original_frame']}自然返回，原候选确认数={result['original_candidate_count']}。",
            '真实 stage/commit 后更新当前 bank，首次本帧发布并下一帧继续自身 alias；匹配归档原自然返回。不是物理正确率或深度提点。', '']
    lines += ['## 边界', '',
        '本检查是源、状态与发布回归，不是模型或科研资格筛选。prefix 不是完整正式段的 seal；后续正式冻结与全段评分单列。', '',
        f'失败详情数量：{len(issues)}。', '']
    with output_path.with_suffix('.md').open('x', encoding='utf-8', newline='\n') as handle:
        handle.write('\n'.join(lines))
    print('Confirmation slice review', output['status'], 'isolated rows', store_rows,
          'natural L3 returns', len(retained), 'failures', len(issues))
    assert not issues, f'{len(issues)} failures; see {output_path.name}'


if __name__ == '__main__':
    main()
