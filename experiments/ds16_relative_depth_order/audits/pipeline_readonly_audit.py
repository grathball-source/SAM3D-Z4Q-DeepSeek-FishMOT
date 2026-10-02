"""Independent postscore stream checks; no predictor, scorer rerun or GT raster read."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import *
from collections import Counter
from score import row_sha, order_records, verify_order_sources


def relation(first, second):
    if first.get('status') != 'UNIQUE_IOU_MATCH' or second.get('status') != 'UNIQUE_IOU_MATCH':
        return 'UNKNOWN'
    return 'SAME' if first['gt_id'] == second['gt_id'] else 'DIFFERENT'


def expected_pair(anchors, posts):
    old = {value['gt_id']: int(target) for target, value in anchors.items()
           if value.get('status') == 'UNIQUE_IOU_MATCH'}
    if (len(old) == len(anchors) == len(posts) == 2 and
            all(value.get('status') == 'UNIQUE_IOU_MATCH' and value['gt_id'] in old for value in posts.values()) and
            len({value['gt_id'] for value in posts.values()}) == 2):
        return {int(native): old[value['gt_id']] for native, value in posts.items()}
    return {}


def verdict(actual, expected):
    return 'UNSCORABLE' if not expected else 'CORRECT' if actual == expected else 'WRONG'


def check_segment(name, metric):
    start, stop = SEGMENTS[name]
    public = RUN / name / 'public'
    sealed = read(public / 'PREDICTIONS_SEALED.json')
    for filename, digest in sealed['artifacts_sha256'].items():
        assert sha(public / filename) == digest, (name, filename)
    frozen = read(public / 'FREEZE.json')
    for filename, digest in frozen['code_sha256'].items():
        assert sha(filename) == digest, filename
    source_check = verify_order_sources(public)
    ledger = {row['frame']: row for row in rows(public / 'PUBLISH_LEDGER.jsonl')}
    orders, events = order_records(public), read(public / 'EVENTS.json')
    assert set(orders) == {(arm, event['q']) for arm in ARMS[2:] for event in events[arm] if event['q'] is not None}
    transactions, births = iter(rows(public / 'TRANSACTIONS.jsonl.gz')), iter(rows(public / 'BIRTHS.jsonl.gz'))
    first_seen, actual_published, durable = {}, {}, {arm: 0 for arm in ARMS[1:]}
    frames = objects = 0
    for prediction, contact, assignment, old in zip(rows(public / 'predictions.jsonl.gz'),
            rows(public / 'CONTACT_CERTIFICATES.jsonl.gz'), rows(input_dir(name) / 'assignments.jsonl.gz'),
            rows(DS15 / 'run' / name / 'public/predictions.jsonl.gz'), strict=True):
        frame = prediction['frame']
        assert frame == frames + 1 and prediction['global_frame'] == start + frame - 1
        publication = ledger[frame]
        assert row_sha(prediction) == publication['prediction_row_sha256']
        assert row_sha(contact) == publication['contact_row_sha256']
        assert set(prediction['variants']) == set(ARMS)
        assert prediction['variants']['SAM3_NATIVE'] == assignment['variants']['N0'] == old['variants']['SAM3_NATIVE']
        assert prediction['variants']['Z4Q_FROZEN'] == old['variants']['Z4Q_FROZEN']
        keys = [item['mask'] for item in prediction['variants']['SAM3_NATIVE']]
        current = {arm: {int(item['mask'][2:]): item['id'] for item in prediction['variants'][arm]} for arm in ARMS}
        for native in current['SAM3_NATIVE']:
            first_seen.setdefault(native, frame)
        for arm in ARMS:
            assert [item['mask'] for item in prediction['variants'][arm]] == keys
            assert len(set(current[arm].values())) == len(keys)
        for arm in ARMS[1:]:
            transaction = next(transactions)
            assert transaction['frame'] == frame and transaction['arm'] == arm
            assert {int(native): target for native, target in transaction['actual_published_mapping'].items()} == current[arm]
            adopted = []
            for candidate in transaction['automatic_candidate_events']:
                action = candidate['event']; native, target = action['native_id'], action['canonical_id']
                assert candidate['applied_at_first_publication'] == (current[arm][native] == target)
                assert candidate['durable_alias_after_commit'] == (transaction['actual_alias_targets'].get(str(native)) == target)
                if candidate['applied_at_first_publication'] and candidate['durable_alias_after_commit'] and not candidate['overridden_by_explicit_transaction']:
                    adopted.append(candidate)
            assert adopted == transaction['durable_automatic_commits']
            durable[arm] += len(adopted)
        for arm in ARMS[2:]:
            birth = next(births)
            assert birth['frame'] == frame and birth['arm'] == arm
            assert row_sha(birth) == publication['birth_row_sha256'][arm]
            assert birth['prediction_row_sha256'] == publication['prediction_row_sha256']
            assert birth['status'] == 'ORIGINAL_Z4Q_AUTOMATIC_ONLY' and not birth['queries'] and not birth['changes']
            assert {int(native): target for native, target in birth['actual_mapping'].items()} == current[arm]
        decisions = {arm: row for (arm, query), row in orders.items() if query == frame}
        assert set(decisions) == set(publication['order_row_sha256'])
        for arm, decision in decisions.items():
            assert row_sha(decision) == publication['order_row_sha256'][arm]
            assert decision['prediction_row_sha256'] == publication['prediction_row_sha256']
            event = next(event for event in events[arm] if event['q'] == frame)
            assert decision['detail'] == event['numeric']['detail'] and decision['restore'] == event['restore']
            assert set(decision['published_mapping']) == set(event['post_first_observations'])
            assert all(current[arm][int(native)] == target for native, target in decision['published_mapping'].items())
        actual_published[frame] = current
        frames += 1; objects += len(keys)
    assert frames == stop - start + 1 and next(transactions, None) is None and next(births, None) is None

    # Re-evaluate identity diagnoses from the scorer's scalar unique-match records.
    # These records are not reopened GT raster/polygons and are not depth truth.
    matches = {row['frame']: {int(native): value for native, value in row['matches'].items()}
               for row in rows(public / 'REFERENCE_MATCHES.jsonl.gz')}
    def match(frame, native):
        return matches.get(frame, {}).get(int(native), dict(status='SOURCE_OR_REFERENCE_MISSING'))
    automatic = read(public / 'AUTOMATIC_RECONNECT_AUDIT.json')
    counts = {}
    for arm in ARMS[1:]:
        for action in automatic['arms'][arm]:
            native, target, frame = action['source'], action['target'], action['frame']
            anchor = action['actual_old_anchor']
            current = match(frame, native)
            bank = match(anchor['frame'], anchor['native_id']) if anchor else dict(status='MISSING_ANCHOR')
            origin = match(first_seen.get(target), target)
            relationships = dict(query_vs_bank=relation(current, bank), bank_vs_public_origin=relation(bank, origin),
                                 query_vs_public_origin=relation(current, origin))
            assert relationships == action['relations']
            adopted = actual_published[frame][arm][native] == target
            assert adopted == action['applied_at_first_publication']
            committed = adopted and action['durable_alias_after_commit'] and not action['overridden_by_explicit_transaction']
            physical = ('NOT_FIRST_PUBLISHED' if not adopted else 'NOT_DURABLE_AUTO_COMMIT' if not committed else
                        'WRONG' if 'DIFFERENT' in relationships.values() else 'UNSCORABLE' if 'UNKNOWN' in relationships.values() else 'CORRECT')
            assert physical == action['physical']
        counts[arm] = dict(Counter(action['physical'] for action in automatic['arms'][arm]))
        assert counts[arm] == automatic['counts'][arm]

    group = read(public / 'EVENT_AUDIT.json')['arms']
    group_counts = {}
    for arm in ARMS[2:]:
        for row in group[arm]['group_events']:
            if row['q'] is None:
                assert row['physical'] == 'NO_SPLIT'
                continue
            event = next(event for event in events[arm] if event['q'] == row['q'])
            posts = {int(native): match(row['q'], int(native)) for native in event['post_first_observations']}
            anchors = {int(target): match(anchor['frame'], anchor['native_id']) if anchor else dict(status='MISSING_ANCHOR')
                       for target, anchor in event['reference_anchors'].items()}
            expected = expected_pair(anchors, posts)
            actual = {native: actual_published[row['q']][arm][native] for native in posts}
            assert actual == {int(native): target for native, target in row['actual_first_public_mapping'].items()}
            assert expected == {int(native): target for native, target in row['expected_mapping'].items()}
            assert verdict(actual, expected) == row['first_public_physical']
            assert row['physical'] == (verdict(actual, expected) if row['restore_status'] == 'COMMIT' else 'NOT_COMMITTED')
            endpoint = {}; consensus = {}
            for role, target in zip(('A', 'B'), event['public_ids'], strict=True):
                history = event['pre_geometry_history'].get(role, [])
                assert all(point['frame'] < event['suspect_frame'] for point in history)
                endpoint[int(target)] = match(history[-1]['frame'], history[-1]['source']) if history else dict(status='MISSING_CLEAN_FRAGMENT')
                references = [match(point['frame'], point['source']) for point in history]
                known = [value['gt_id'] for value in references if value.get('status') == 'UNIQUE_IOU_MATCH']
                continuous = all(b['frame'] == a['frame'] + 1 for a, b in zip(history, history[1:]))
                versions = {(point.get('source'), point.get('source_generation'), point.get('public_id'), point.get('public_epoch')) for point in history}
                eligible = len(known) >= 3 and len(set(known)) == 1 and continuous and len(versions) == 1
                consensus[int(target)] = dict(status='UNIQUE_IOU_MATCH', gt_id=known[0]) if eligible else dict(status='UNSCORABLE_FRAGMENT_CONSENSUS')
            assert verdict(actual, expected_pair(endpoint, posts)) == row['first_public_clean_endpoint_verdict']
            assert verdict(actual, expected_pair(consensus, posts)) == row['first_public_pre_consensus_verdict']
        group_counts[arm] = dict(Counter(row['physical'] for row in group[arm]['group_events']))
        assert group_counts[arm] == group[arm]['group_physical_counts']
        assert not group[arm]['birth_commits'] and not group[arm]['birth_physical_counts']

    switches = read(public / 'SWITCHES.json')
    for arm in ARMS:
        assert len(switches[arm]) == metric[arm]['IDSW']
        assert metric[arm]['predictions'] == metric['SAM3_NATIVE']['predictions'] == objects
        assert (metric[arm]['FP'], metric[arm]['FN']) == (metric['SAM3_NATIVE']['FP'], metric['SAM3_NATIVE']['FN'])
        for switch in switches[arm]:
            frame = switch['frame'] - start + 1
            assert switch['segment'] == name and start <= switch['frame'] <= stop
            assert switch['from_public_id'] != switch['to_public_id']
            assert actual_published[frame][arm][switch['native_id']] == switch['public_id'] == switch['to_public_id']
            assert switch['native_mask'] == f"n:{switch['native_id']}" and switch['matched_iou'] >= .5
    return dict(status='PASS', frames=frames, masks=objects, q_decisions=len(orders), raw_source_contract=source_check,
        durable_automatic_commits=durable, automatic_physical_counts=counts, group_physical_counts=group_counts,
        metric_and_every_saved_switch_binding=True, metric_math_rerun=False, no_GT_raster_read=True,
        metrics=artifact(public / 'METRICS.json'), switches=artifact(public / 'SWITCHES.json'))


def main():
    assert (RUN / 'METRICS.json').exists() and (RUN / 'SCORE_PROVENANCE.json').exists(), 'Wait for completed official scoring'
    assert not (HERE / 'PIPELINE_READONLY_AUDIT.json').exists()
    seals = read(RUN / 'ALL_PREDICTIONS_SEALED.json')
    assert tuple(seals['arms']) == ARMS and seals['frames'] == 20098
    for name in SEGMENTS:
        verify_item(seals['seals'][name]); verify_item(seals['access_seals'][name])
    provenance = read(RUN / 'SCORE_PROVENANCE.json')
    assert provenance['reference_opened_after_all_seals'] and not provenance['GT_used_for_predictions']
    assert provenance['masked_or_ignored_ids'] == 0
    for key in ('scorer', 'scoring_freeze', 'prediction_parity'):
        verify_item(provenance[key])
    metrics = read(RUN / 'METRICS.json')
    assert metrics['status'] == 'SCORED_AFTER_ALL_SIX_ARMS_EIGHT_SEALS'
    old_metrics = read(DS15 / 'run/METRICS.json')
    result = {}
    for name in SEGMENTS:
        values = metrics['segments'][name]['metrics']
        for arm in ('SAM3_NATIVE', 'Z4Q_FROZEN'):
            assert values[arm] == old_metrics['segments'][name]['metrics'][arm]
        for base, comparisons in metrics['segments'][name]['deltas'].items():
            for arm, changes in comparisons.items():
                assert changes == {key: values[arm][key] - values[base][key] for key in changes}
        result[name] = check_segment(name, values)
        print('PASS', name, flush=True)
    pooled = metrics['feeding_pooled']['metrics']
    for arm in ('SAM3_NATIVE', 'Z4Q_FROZEN'):
        assert pooled[arm] == old_metrics['feeding_pooled']['metrics'][arm]
    for base, comparisons in metrics['feeding_pooled']['deltas'].items():
        for arm, changes in comparisons.items():
            assert changes == {key: pooled[arm][key] - pooled[base][key] for key in changes}
    old_lock = read(HERE / 'OLD_READONLY_LOCK.json')['files']
    for path, digest in old_lock.items():
        assert sha(ROOT / path) == digest, path
    output = dict(status='PASS_READONLY_POSTSCORE_AUDIT', frames=sum(row['frames'] for row in result.values()),
        masks=sum(row['masks'] for row in result.values()), old_unchanged_files=len(old_lock), segments=result,
        audit_code=artifact(__file__), official_metrics=artifact(RUN / 'METRICS.json'),
        no_predictor_or_metric_rerun=True, no_GT_raster_or_private_pixels_read=True,
        scalar_identity_matches_rechecked=True, physical_depth_order_truth='UNKNOWN', new_model_http=0, cost_usd=0)
    write_new(HERE / 'PIPELINE_READONLY_AUDIT.json', output)
    report = ['# DS16 只读评分与发布审计', '',
        '全部六臂、八段预测封存和正式评分完成后执行。只读重新检查日志、实际映射、深度来源统计和评分产生的'
        '标量身份匹配；未重跑预测或指标计算，未重新读取GT raster/私有像素，冻结源码及旧结果未改。', '',
        f"结论：PASS。{output['frames']}帧、{output['masks']}原始mask token；{len(old_lock)}个旧文件保持。", '',
        '## 核验', '',
        '- 每个mask、残片和公开ID完整保留，同帧ID唯一；native与原Z4Q逐帧及完整指标等于DS15。',
        '- 每个transaction/birth/contact/order/q首次发布与实际预测及行SHA对应；预览接受与真实durable提交分开。',
        '- 各pre/post次序深度事实逐列回查原始统计与来源/版本；置换只作用于打分绑定。',
        '- literal bank、clean端点和连续同版本共识物理判定重新核验；UNKNOWN/未提交/无分离不算正确。',
        '- 每条保存切换绑定真实发布映射，保存条数等于官方IDSW；FP/FN/检测数守恒，所有delta重算一致。', '',
        '工程和评分审计通过不代表次序信息有效。标量身份参考没有提供深度表面或局部遮挡次序真值；'
        'L3/LW仍为依赖预测的弱参考，所有数据仍属已曝光诊断。完整计数与artifact SHA见PIPELINE_READONLY_AUDIT.json。', '']
    with (HERE / 'PIPELINE_READONLY_AUDIT.md').open('x', encoding='utf-8', newline='\n') as target:
        target.write('\n'.join(report))
    print(json.dumps(dict(status=output['status'], frames=output['frames'], masks=output['masks'])))


if __name__ == '__main__':
    main()
