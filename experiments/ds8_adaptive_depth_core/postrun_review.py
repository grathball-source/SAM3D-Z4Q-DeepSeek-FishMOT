"""Read sealed DS7/DS8 evidence; compare q facts without GT or another replay."""
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
from itertools import zip_longest
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = {'DS7': HERE.parent/'ds7_depth_native_recovery'/'run', 'DS8': HERE/'run'}
ARMS = ('P1_RAW_DEPTH', 'P2_RESTORED_DEPTH')
PARAMETERS = ('depth_weight', 'minimum_depth_odds', 'inferred_scale_floor_mm',
              'raw_scale_floor_mm', 'history_frames', 'fit_observations',
              'min_points', 'min_fraction', 'max_raw_scale_mm')
STAT_FIELDS = ('area', 'n', 'valid_fraction', 'median', 'mad',
               'q10', 'q25', 'q75', 'q90')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def rows(path):
    opener = gzip.open if str(path).endswith('.gz') else open
    with opener(path, 'rt', encoding='utf-8') as stream:
        yield from (json.loads(line) for line in stream)


def artifact(path):
    path = Path(path)
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    return dict(path=path.as_posix(), bytes=path.stat().st_size, sha256=digest)


def fact(measurement):
    """Keep actual cohort MAD separate from the old interface's noise proxy."""
    core = measurement['core']
    cohort = measurement.get('cohort', 'RAW')
    actual = measurement.get('cohorts', {}).get(cohort, core)
    result = dict(native=measurement['native'], fact_id=measurement['fact_id'],
        source=measurement['source'], cohort=cohort,
        usable=measurement['core_usable'], roi_area=core['area'], n=core['n'],
        fraction=core['valid_fraction'], median_mm=core['median'],
        actual_mad_mm=actual['mad'], adapter_mad_mm=core['mad'],
        effective_noise_scale_mm=max(15., 1.4826*core['mad'])
            if core['mad'] is not None else None,
        cohorts=measurement.get('cohorts', {}))
    for name in ('roi', 'roi_geometry', 'geometry', 'adaptive_roi'):
        if name in measurement:
            result[name] = measurement[name]
    result['failure_flags'] = dict(
        area_lt16=core['area'] < 16, n_lt16=core['n'] < 16,
        fraction_lt_point2=core['valid_fraction'] < .2,
        median_missing_or_nonpositive=core['median'] is None or core['median'] <= 0,
        actual_scale_gt60=actual['mad'] is not None and
            max(15., 1.4826*actual['mad']) > 60.)
    return result


def sealed_run(root, bindings):
    master = read(root/'ALL_PREDICTIONS_SEALED.json')
    master_item = artifact(root/'ALL_PREDICTIONS_SEALED.json')
    score = read(root/'SCORING_SEALED.json')
    assert score['status'] == 'ALL_SEGMENTS_AND_EVENTS_SCORED'
    assert score['all_prediction_seal_sha256'] == master_item['sha256']
    assert master['frames'] == 1471
    bindings.extend((master_item, artifact(root/'SCORING_SEALED.json')))
    result = {}
    for segment, expected in master['seals'].items():
        public = root/segment/'public'
        seal_item = artifact(public/'PREDICTIONS_SEALED.json')
        assert seal_item['sha256'] == expected
        seal = read(public/'PREDICTIONS_SEALED.json')
        bindings.append(seal_item)
        for name in ('FREEZE.json', 'DEPTH_OBSERVATIONS.jsonl.gz', 'EVENTS.json',
                     'PUBLISH_LEDGER.jsonl', 'predictions.jsonl.gz', 'RUN_SUMMARY.json'):
            item = artifact(public/name)
            assert item['sha256'] == seal['artifacts_sha256'][name]
            bindings.append(item)
        events = read(public/'EVENTS.json')
        selected = {arm: {e['id']: e for e in events[arm]} for arm in ARMS}
        assert all(len(selected[a]) == len(events[a]) for a in ARMS)
        ledger = {row['frame']: row for row in rows(public/'PUBLISH_LEDGER.jsonl')}
        result[segment] = dict(public=public, freeze=read(public/'FREEZE.json'),
            events=selected, ledger=ledger, summary=read(public/'RUN_SUMMARY.json'))
    return result


def needed(events):
    frames, ids = set(), set()
    for by_id in events.values():
        for event in by_id.values():
            if event['q'] is None:
                continue
            frames.add(event['q'])
            for frozen in event['depth_frozen'].values():
                ids.update(s['fact_id'] for s in frozen['samples'])
    return frames, ids


def collect(old, new):
    """Stream all observations; retain only q/post and referenced pre facts."""
    facts = {'DS7': {}, 'DS8': {}}
    current = {'DS7': {}, 'DS8': {}}
    counts = {tag: {arm: Counter() for arm in ARMS} for tag in RUNS}
    comparison = {arm: Counter() for arm in ARMS}
    want = {tag: needed(run['events']) for tag, run in (('DS7', old), ('DS8', new))}
    streams = [rows(run['public']/'DEPTH_OBSERVATIONS.jsonl.gz') for run in (old, new)]
    for before, after in zip_longest(*streams):
        assert before is not None and after is not None
        for key in ('frame', 'global_frame', 'time', 'depth_sha256', 'timing'):
            assert before[key] == after[key], key
        assert before['objects'].keys() == after['objects'].keys()
        # This is the unchanged 7x7 raw measurement, not DS8's new adaptive ROI.
        for native, previous in before['objects'].items():
            baseline = after['objects'][native]
            assert previous['core_usable'] == baseline['core_usable']
            for region in ('whole', 'core'):
                assert all(previous[region][k] == baseline[region][k] for k in STAT_FIELDS)
        for tag, row in (('DS7', before), ('DS8', after)):
            tables = {'P1_RAW_DEPTH': row['objects'] if tag == 'DS7' else row['adaptive_raw'],
                      'P2_RESTORED_DEPTH': row['restored']}
            assert all(table.keys() == row['objects'].keys() for table in tables.values())
            if row['frame'] in want[tag][0]:
                current[tag][row['frame']] = dict(global_frame=row['global_frame'],
                    facts={arm: {n: fact(m) for n, m in table.items()}
                           for arm, table in tables.items()})
            for arm, table in tables.items():
                count = counts[tag][arm]
                count['frames'] += 1
                for measurement in table.values():
                    core = measurement['core']
                    count['object_frames'] += 1
                    count['usable'] += measurement['core_usable']
                    count['roi_area_sum'] += core['area']
                    count['finite_positive_n_sum'] += core['n']
                    count['selected_'+measurement.get('cohort', 'RAW')] += 1
                    if measurement['fact_id'] in want[tag][1]:
                        value = fact(measurement)
                        value['frame'] = row['frame']
                        value['global_frame'] = row['global_frame']
                        facts[tag][measurement['fact_id']] = value
        for arm, oldkey, newkey in (('P1_RAW_DEPTH', 'objects', 'adaptive_raw'),
                                    ('P2_RESTORED_DEPTH', 'restored', 'restored')):
            for native, previous in before[oldkey].items():
                now = after[newkey][native]
                comparison[arm]['new_usable'] += not previous['core_usable'] and now['core_usable']
                comparison[arm]['lost_usable'] += previous['core_usable'] and not now['core_usable']
                comparison[arm]['roi_grew'] += now['core']['area'] > previous['core']['area']
    for tag in RUNS:
        assert set(facts[tag]) == want[tag][1]
    return facts, current, counts, comparison


def event_view(event, arm, segment_data, facts, current):
    if event is None:
        return None
    base = dict(id=event['id'], suspect_frame=event['suspect_frame'],
                q=event['q'], status=event['status'])
    if event['q'] is None:
        return base
    q = event['q']
    row = current[q]
    detail = event['numeric']['detail']
    base.update(global_q=row['global_frame'], numeric_choice=event['numeric']['choice'],
        reason=detail['reason'], post_pair_usable=detail.get('post_pair_usable'),
        used_edges=detail.get('used_edges', 0), accepted=detail.get('accepted', False),
        gap=detail.get('depth_log_odds_gap'), minimum_gap=detail.get('minimum_log_odds'),
        depth_best=detail.get('depth_best'), total_best=detail.get('total_best'),
        selected_mapping=event['restore']['mapping'],
        transaction_changes=event['restore']['changes'],
        stage_error=event['restore']['stage_error'],
        decision_source=event['restore']['decision_source'],
        post={n: row['facts'][arm][n] for n in event['post_first_observations']}, history={})
    published = segment_data['ledger'][q]['event_publish'][arm]
    assert published['episode'] == event['id'] and published['q'] == q
    base['first_public_pair'] = published['first_public_pair']
    for role, frozen in event['depth_frozen'].items():
        samples = frozen['samples']
        values = [facts[s['fact_id']] for s in samples]
        for sample, value in zip(samples, values):
            assert sample['frame'] == value['frame'] <= frozen['cutoff_frame']
            assert sample['z_mm'] == value['median_mm']
            assert sample['mad_mm'] == value['adapter_mad_mm'] and value['usable']
        forecast = detail.get('forecasts', {}).get(role)
        fit = [facts[key] for key in forecast['sample_fact_ids']] if forecast else []
        if forecast:
            assert forecast['sample_fact_ids'] == [s['fact_id'] for s in samples[-10:]]
        base['history'][role] = dict(source=frozen['source'], public=frozen['public'],
            version_key=frozen['key'], cutoff=frozen['cutoff_frame'],
            frozen_samples=len(values), frozen_cohorts=dict(Counter(v['cohort'] for v in values)),
            fit_samples=len(fit) if forecast else None,
            fit_cohorts=dict(Counter(v['cohort'] for v in fit)), fit_facts=fit,
            forecast={key: forecast.get(key) for key in ('status', 'mu_mm', 'scale_mm',
                'slope_mm_s', 'delta_seconds', 'time_scale_seconds')} if forecast else None,
            row_used=any(e['used'] for key, e in detail.get('edges', {}).items()
                         if key.startswith(role+':')))
    return base


def publication_difference(old, new):
    result = Counter()
    for a, b in zip_longest(rows(old['public']/'predictions.jsonl.gz'),
                            rows(new['public']/'predictions.jsonl.gz')):
        assert a is not None and b is not None
        assert (a['frame'], a['global_frame']) == (b['frame'], b['global_frame'])
        for arm in ('SAM3_NATIVE', 'D2_CORE_FROZEN', 'P0_NATIVE_PRESERVE', *ARMS):
            before = {x['mask']: x['id'] for x in a['variants'][arm]}
            after = {x['mask']: x['id'] for x in b['variants'][arm]}
            assert before.keys() == after.keys()
            changed = sum(before[k] != after[k] for k in before)
            result[arm+'_changed_frames'] += changed > 0
            result[arm+'_changed_object_publications'] += changed
            if arm not in ARMS:
                assert changed == 0, (arm, a['global_frame'])
    return result


def main():
    targets = [HERE/'POSTRUN_REVIEW.json', HERE/'POSTRUN_REVIEW.md']
    assert not any(path.exists() for path in targets), 'Preserve an existing review.'
    bindings = [artifact(Path(__file__))]
    runs = {tag: sealed_run(root, bindings) for tag, root in RUNS.items()}
    assert runs['DS7'].keys() == runs['DS8'].keys()
    configs = {tag: read(root.parent/'CONFIG.json') for tag, root in RUNS.items()}
    assert all(configs['DS7'][k] == configs['DS8'][k] for k in PARAMETERS)
    report = dict(schema='DS8_POSTRUN_ROI_REVIEW_V1', created_utc=datetime.now(timezone.utc).isoformat(),
        scope='Sealed numeric facts and publications only; no GT, image arrays, model, API, replay or tuning.',
        unchanged_decision_parameters={k: configs['DS8'][k] for k in PARAMETERS},
        semantics='ActualMAD comes from selected cohorts; inferred core.mad is an assumed noise adapter. '
                  'ROI area counts geometric pixels; n counts positive finite depth. '
                  'Identity differences describe publication changes, not GT-confirmed improvements.',
        bindings=bindings, segments={}, events=[])
    lines = ['# DS8 对 DS7 的封存后 ROI 复核', '',
        '只读封存观测、事件和实际发布；没有 GT、像素重算、回放或阈值选择。', '',
        'inferred 的实测 MAD 取 cohorts 字段，core.mad 保留为噪声适配代理。', '',
        '| 段 / arm / event | 全局 q DS7→DS8 | post 可用 DS7→DS8 | history A/B DS7→DS8 | gap DS7→DS8 | choice DS7→DS8 | 发布 pair 改变 |',
        '|---|---|---|---|---|---|---|']
    for segment in runs['DS7']:
        old, new = runs['DS7'][segment], runs['DS8'][segment]
        for key in ('original_frames', 'source_list_sha256', 'scan_sha256',
                    'derived_inputs', 'restored_sources', 'current_metadata'):
            assert old['freeze'][key] == new['freeze'][key], key
        facts, current, counts, comparison = collect(old, new)
        report['segments'][segment] = dict(
            measurement_counts={tag: {a: dict(c) for a, c in by_arm.items()}
                                for tag, by_arm in counts.items()},
            eligibility_changes={a: dict(c) for a, c in comparison.items()},
            publication_changes=dict(publication_difference(old, new)),
            state_updates={tag: data['summary']['state'] for tag, data in (('DS7', old), ('DS8', new))})
        for arm in ARMS:
            for event_id in sorted(old['events'][arm].keys() | new['events'][arm].keys()):
                before = old['events'][arm].get(event_id)
                after = new['events'][arm].get(event_id)
                if all(event is None or event['q'] is None for event in (before, after)):
                    continue
                views = {tag: event_view(event, arm, data, facts[tag], current[tag])
                         for tag, event, data in (('DS7', before, old), ('DS8', after, new))}
                left, right = views['DS7'], views['DS8']
                aligned = bool(left and right and left.get('global_q') == right.get('global_q')
                               and left.get('global_q') is not None)
                changes = dict(same_q=aligned,
                    numeric_choice_changed=(left or {}).get('numeric_choice') != (right or {}).get('numeric_choice'),
                    first_public_pair_changed=(left or {}).get('first_public_pair') != (right or {}).get('first_public_pair'))
                if aligned:
                    common = left['post'].keys() & right['post'].keys()
                    changes['posts'] = {n: dict(
                        roi_area_delta=right['post'][n]['roi_area']-left['post'][n]['roi_area'],
                        finite_n_delta=right['post'][n]['n']-left['post'][n]['n'],
                        new_usable=not left['post'][n]['usable'] and right['post'][n]['usable'],
                        lost_usable=left['post'][n]['usable'] and not right['post'][n]['usable'],
                        cohort_changed=left['post'][n]['cohort'] != right['post'][n]['cohort']) for n in common}
                reasons = []
                if not right or right.get('q') is None:
                    reasons.append('NO_DS8_Q; event lifecycle differs, no paired q comparison')
                elif right['reason'] == 'NO_NUMERIC_PAIR':
                    reasons.append('NO_NUMERIC_PAIR before depth forecast evaluation')
                else:
                    if not right['post_pair_usable']:
                        reasons.append('POST_PAIR_UNUSABLE; see source-specific n/fraction/actualMAD')
                    if any(h['forecast'] and h['forecast']['mu_mm'] is None for h in right['history'].values()):
                        reasons.append('AT_LEAST_ONE_HISTORY_ROW_UNAVAILABLE')
                    if right['gap'] is not None and right['gap'] < right['minimum_gap']:
                        reasons.append('DEPTH_GAP_BELOW_PRESET_LOG9')
                    if right['depth_best'] != right['total_best']:
                        reasons.append('DEPTH_AND_TOTAL_CHOICES_DISAGREE')
                    if right['accepted']:
                        reasons.append('NUMERIC_ACCEPTED; inspect actual transaction and publication')
                report['events'].append(dict(segment=segment, arm=arm, event=event_id,
                    views=views, changes=changes, DS8_reasons=reasons))
                def cell(view):
                    if not view or view.get('q') is None:
                        return ('—',)*5
                    post = f"{sum(p['usable'] for p in view['post'].values())}/{len(view['post'])}"
                    history = '/'.join(str(view['history'][role]['fit_samples']) for role in ('A', 'B'))
                    gap = f"{view['gap']:.6f}" if view['gap'] is not None else '—'
                    return str(view['global_q']), post, history, gap, view['numeric_choice']
                a, b = cell(left), cell(right)
                values = ' | '.join(f'{x}→{y}' for x, y in zip(a, b))
                lines.append(f"| {segment} / {arm} / {event_id} | {values} | {changes['first_public_pair_changed']} |")
    report['passed'] = True
    lines.extend(['', '每个 q 的前段 fit 事实与当前 post 的 ROI 面积、真实 n/MAD、来源组、'
        '噪声适配值、角色预测、选择和实际 first_public_pair 均在同名 JSON。', '',
        '没有匹配 q 的事件单独标记生命周期变化；它们不作为纯 ROI 数值配对。'
        '本报告未使用 GT 判定物理鱼表面或身份正确性。', ''])
    with targets[0].open('x', encoding='utf-8') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
    with targets[1].open('x', encoding='utf-8') as stream:
        stream.write('\n'.join(lines))
    print(json.dumps({'passed': True, 'artifacts': [artifact(p) for p in targets]}))


if __name__ == '__main__':
    main()
