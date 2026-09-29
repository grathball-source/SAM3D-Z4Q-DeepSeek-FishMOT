"""Read-only postseal audit of V7 request text and CLEAR identity switches."""
import json
import sys
from pathlib import Path

import numpy as np
from scipy.optimize import linear_sum_assignment

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
import score  # noqa: E402

PAID = ROOT/'run_development_v7_paid/public'
RECOVERED = ROOT/'run_development_v7_recovery/public'
ARMS = ('B0', 'B-HOLD-S0', 'B-VLM-S0')


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def after(text, marker, start=0):
    offset = text.index(marker, start) + len(marker)
    return json.JSONDecoder().raw_decode(text[offset:].lstrip())[0]


def verify_seal():
    seal = read(RECOVERED/'PREDICTIONS_SEALED.json')
    assert seal['status'] == 'SEALED_AWAITING_INDEPENDENT_SCORING'
    assert seal['mode'] == 'real_recovered' and seal['frames'] == seal['published_frames'] == 8400
    for filename, key in (('predictions_development.jsonl.gz', 'predictions_sha256'),
                          ('TRANSACTIONS.jsonl.gz', 'transactions_sha256'),
                          ('EVENTS.json', 'events_sha256'),
                          ('CALL_LEDGER.jsonl', 'call_ledger_sha256'),
                          ('PUBLISH_LEDGER.jsonl', 'publish_ledger_sha256')):
        assert score.digest(RECOVERED/filename) == seal[key]
    metrics = read(RECOVERED/'METRICS.json')
    assert metrics['prediction_sha256'] == seal['predictions_sha256']
    assert score.digest(score.GT) == score.GT_SHA
    return seal, metrics


def prompt_summary(seal):
    ledger = {}
    for line in (PAID/'CALL_LEDGER.jsonl').read_text(encoding='utf-8').splitlines():
        item = json.loads(line)
        ledger.setdefault(item['tag'], []).append(item['phase'])
    summary = []
    for episode in seal['selected_episodes']:
        for stage in ('M', 'S0'):
            tag = episode+'-'+stage
            packet = read(PAID/'requests'/f'{tag}.json')
            cutoff = int(packet['user'].split('当前证据截止：', 1)[1].splitlines()[0])
            event = next(x for x in read(RECOVERED/'EVENTS.json')['B-VLM-S0'] if x['id'] == episode)
            assert cutoff == (event['confirm_frame'] if stage == 'M' else event['q'])
            assert packet['images'] and max(x['frame'] for x in packet['images']) <= cutoff
            assert 'gt_grid' not in packet['user'] and '"public_id"' not in packet['user']
            summary.append(dict(tag=tag, system_chars=len(packet['system']),
                                user_chars=len(packet['user']), image_count=len(packet['images']),
                                evidence_cutoff_frame=cutoff, call_phases=ledger[tag]))
    assert len(summary) == 16
    assert sum(x['call_phases'] == ['START', 'END'] for x in summary) == 15
    assert next(x for x in summary if x['tag'] == 'MS1-F5927-S0')['call_phases'] == ['START']
    assert not (PAID/'responses/MS1-F5927-S0.json').exists()
    user = read(PAID/'requests/MS1-F5927-S0.json')['user']
    pre = user.index('【合并之前的原始参考】')
    post = user.index('【分离后的当前短片段】')
    a, b = after(user, 'A：', pre), after(user, 'B：', pre)
    x, y = after(user, 'X：', post), after(user, 'Y：', post)
    section = user.split('【合并期间实际观测】', 1)[1].lstrip()
    decoder = json.JSONDecoder()
    group, end = decoder.raw_decode(section)
    visibility, _ = decoder.raw_decode(section[end:].lstrip())
    pairwise = after(user, '【程序计算的时间对齐比较】')
    hypothesis = after(user, '【合并时模型给出的可选假设】')
    candidates = after(user, '【候选完整映射】')
    assert len(a['observations']) == 30 and len(b['observations']) == 0
    assert len(visibility['pre_risk_anonymous']) == 60
    assert len(group['group_measured']) == len(group['other_anonymous']) == 12
    assert len(x['observations']) == len(y['observations']) == 1
    assert x['motion']['status'] == y['motion']['status'] == 'UNKNOWN'
    assert pairwise == [] and hypothesis['type'] == 'MODEL_HYPOTHESIS'
    assert candidates == {'H1': {'A': 'X', 'B': 'Y', 'U': 'unchanged'},
                          'H2': {'A': 'Y', 'B': 'X', 'U': 'unchanged'}}
    example = dict(episode='MS1-F5927', cutoff_frame=5939,
                   A_pre_observations=len(a['observations']),
                   A_pre_frame_range=[a['observations'][0]['frame'], a['observations'][-1]['frame']],
                   A_last_center_px=a['observations'][-1]['center'],
                   A_pre_speed_px_per_second=a['motion']['speed_px_per_second'],
                   B_pre_observations=0, B_motion=b['motion']['status'],
                   anonymous_risk_observations=len(visibility['pre_risk_anonymous']),
                   group_measured_frames=len(group['group_measured']),
                   group_anonymous_observations=len(group['other_anonymous']),
                   X_center_px=x['observations'][0]['center'], Y_center_px=y['observations'][0]['center'],
                   post_motion='UNKNOWN', pairwise_candidates_with_measured_edges=len(pairwise),
                   M_hypothesis_included=True, S0_response='UNKNOWN_OPEN_START')
    return dict(requests=summary, f5927_s0=example)


def switches():
    previous = {arm: {} for arm in ARMS}
    previous_step = {arm: {} for arm in ARMS}
    changes = {arm: [] for arm in ARMS}
    count = 0
    for assignment, prediction, truth in zip(score.rows(score.ASSIGN),
                                             score.rows(RECOVERED/'predictions_development.jsonl.gz'),
                                             score.rows(score.GT), strict=True):
        frame = prediction['frame']
        count += 1
        assert frame == count == assignment['frame'] == truth['global_frame_id']
        masks = [x['mask'] for x in prediction['variants']['B0']]
        gt_ids = [int(x['id']) for x in truth['gt_grid']]
        similarity = (score.coco.iou([score.rle(x['rle']) for x in truth['gt_grid']],
                                     [score.rle(assignment['masks'][key]) for key in masks],
                                     [0]*len(masks)) if gt_ids and masks else np.zeros((len(gt_ids), len(masks))))
        for arm in ARMS:
            tracker_ids = [int(x['id']) for x in prediction['variants'][arm]]
            if not gt_ids or not tracker_ids:
                continue  # CLEAR preserves the last matched ID across gaps.
            matrix = 1000*np.array([[tracker_ids[j] == previous_step[arm].get(g)
                                     for j in range(len(tracker_ids))] for g in gt_ids], float) + similarity
            matrix[similarity < .5-np.finfo(float).eps] = 0
            matched_rows, matched_cols = linear_sum_assignment(-matrix)
            now = {}
            for i, j in zip(matched_rows, matched_cols):
                if matrix[i, j] <= np.finfo(float).eps:
                    continue
                gt, current = gt_ids[i], tracker_ids[j]
                old = previous[arm].get(gt)
                if old is not None and old != current:
                    changes[arm].append(dict(frame=frame, gt_id=gt, from_public_id=old,
                                             to_public_id=current, native_mask=masks[j],
                                             matched_iou=float(similarity[i, j])))
                now[gt] = current
                previous[arm][gt] = current
            previous_step[arm] = now
    assert count == 8400
    assert [len(changes[arm]) for arm in ARMS] == [6, 18, 18]
    assert changes['B-HOLD-S0'] == changes['B-VLM-S0']
    return changes


def explain(changes):
    key = lambda x: (x['frame'], x['gt_id'], x['from_public_id'], x['to_public_id'])
    baseline = {key(x) for x in changes['B0']}
    hold = {key(x) for x in changes['B-HOLD-S0']}
    added = [x for x in changes['B-HOLD-S0'] if key(x) not in baseline]
    removed = [x for x in changes['B0'] if key(x) not in hold]
    shared = [x for x in changes['B0'] if key(x) in hold]
    assert (len(added), len(removed), len(shared)) == (16, 4, 2)
    events = read(RECOVERED/'EVENTS.json')['B-HOLD-S0']
    excursions = []
    for enter in added:
        if enter['to_public_id'] >= 0:
            continue
        exits = [x for x in added if x['gt_id'] == enter['gt_id']
                 and x['from_public_id'] == enter['to_public_id']
                 and x['to_public_id'] == enter['from_public_id'] and x['frame'] > enter['frame']]
        assert len(exits) == 1
        leave = exits[0]
        matching_events = [e for e in events if e['suspect_frame'] <= enter['frame']
                           and e['end'] == leave['frame']]
        assert len(matching_events) == 1
        event = matching_events[0]
        excursions.append(dict(episode=event['id'], event_status=event['status'],
                               gt_id=enter['gt_id'], original_public_id=enter['from_public_id'],
                               temporary_public_id=enter['to_public_id'],
                               temporary_entry_frame=enter['frame'], return_frame=leave['frame']))
    assert len(excursions) == 8
    assert sum(x['event_status'] == 'CANCELLED' for x in excursions) == 3
    assert all(x['to_public_id'] < 0 or x['from_public_id'] < 0 for x in added)
    return dict(extra_switches=added, baseline_switches_removed=removed,
                switches_shared_with_baseline=shared, temporary_id_excursions=excursions,
                arithmetic=dict(B0=6, added=16, removed=4, HOLD=18, VLM=18,
                                model_increment=0, net_change=12))


def main():
    seal, metrics = verify_seal()
    prompts = prompt_summary(seal)
    changes = switches()
    assert all(metrics['metrics'][arm]['IDSW'] == len(changes[arm]) for arm in ARMS)
    result = dict(status='POSTSEAL_READ_ONLY_AUDIT', source_prediction_sha256=seal['predictions_sha256'],
                  no_new_model_calls=True, model_request_content=prompts,
                  per_branch_switches=changes, cause=explain(changes))
    out = HERE/'PROMPT_AND_IDSW_AUDIT.json'
    if out.exists():
        assert read(out) == result, 'existing audit differs; original result left unchanged'
    else:
        with out.open('x', encoding='utf-8') as handle:
            json.dump(result, handle, ensure_ascii=False, indent=2)
            handle.write('\n')
    print(json.dumps(dict(status=result['status'], request_count=len(prompts['requests']),
                          switch_counts={arm:len(changes[arm]) for arm in ARMS},
                          arithmetic=result['cause']['arithmetic'],
                          f5927_B_pre=prompts['f5927_s0']['B_pre_observations'])))


if __name__ == '__main__':
    main()
