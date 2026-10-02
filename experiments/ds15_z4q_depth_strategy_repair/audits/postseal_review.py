"""Independent completed-output review; no predictor imports or raw GT reads."""
from collections import Counter
from pathlib import Path
import gzip
import hashlib
import json

HERE = Path(__file__).resolve().parent
RUN = HERE.parent / 'run'
ARMS = ('SAM3_NATIVE', 'Z4Q_FROZEN', 'R12_RAW', 'Z4Q_SHARED', 'Z4Q_DEPTH')
STATE_ARMS = ARMS[1:]
SEGMENTS = {'feeding_000000_000199': (0, 199), 'feeding_000351_000555': (351, 555),
    'feeding_000701_001060': (701, 1060), 'feeding_001201_001906': (1201, 1906),
    'fishsa_development_8400': (1, 8400), 'fishsa_validation_2888': (9301, 12188),
    'L3': (0, 3709), 'LW': (0, 3628)}
# The six successful original actions were established in the prefreeze audit.
# These constants identify actions to check; they never enter a predictor.
ORIGINAL_ACTIONS = {'fishsa_development_8400': [(1327, 6, 0), (3902, 7, 0), (8054, 8, 2)],
    'fishsa_validation_2888': [(9580, 6, 2), (11488, 8, 3), (12150, 11, 5)]}
FIELDS = ('IDF1', 'HOTA', 'AssA', 'IDSW', 'FP', 'FN')


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def rows(path):
    with gzip.open(path, 'rt', encoding='utf-8') as handle:
        yield from (json.loads(line) for line in handle)


def sha(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def artifact(path):
    return dict(path=str(path.resolve()), bytes=path.stat().st_size, sha256=sha(path))


def verify(item):
    assert artifact(Path(item['path'])) == {k: item[k] for k in ('path', 'bytes', 'sha256')}


def ready():
    required = [RUN / name for name in ('ALL_PREDICTIONS_SEALED.json', 'METRICS.json', 'SCORE_PROVENANCE.json')]
    assert all(path.is_file() for path in required), 'WAIT: all predictions and final scoring provenance required'
    seal, scored, provenance = [read(path) for path in required]
    assert seal['status'] in ('ALL_FIVE_BRANCHES_EIGHT_SEGMENTS_SEALED', 'ALL_PREDICTIONS_AND_ACCESS_SEALED')
    assert seal['frames'] == scored['frames'] == 20098 and tuple(seal['arms']) == ARMS
    assert set(seal['seals']) == set(seal['access_seals']) == set(scored['segments']) == set(SEGMENTS)
    assert scored['status'] == 'SCORED_AFTER_ALL_FIVE_ARMS_EIGHT_SEALS'
    assert provenance['reference_opened_after_all_seals'] and not provenance['GT_used_for_predictions']
    assert provenance['masked_or_ignored_ids'] == 0
    verify(scored['all_seal'])
    for key in ('scorer', 'scoring_freeze', 'prediction_parity'):
        verify(provenance[key])
    for name in SEGMENTS:
        for key in ('seals', 'access_seals'):
            verify(seal[key][name])
        public = RUN / name / 'public'
        segment = read(public / 'PREDICTIONS_SEALED.json')
        for filename in ('predictions.jsonl.gz', 'TRANSACTIONS.jsonl.gz', 'EVENTS.json'):
            assert sha(public / filename) == segment['artifacts_sha256'][filename]
        assert all((public / filename).is_file() for filename in (
            'METRICS.json', 'EVENT_AUDIT.json', 'AUTOMATIC_RECONNECT_AUDIT.json'))
    return scored


def mappings(row):
    return {arm: {int(item['mask'][2:]): item['id'] for item in objects}
            for arm, objects in row['variants'].items()}


def append_run(runs, frame, value):
    if runs and runs[-1]['value'] == value and runs[-1]['end'] + 1 == frame:
        runs[-1]['end'] = frame
    else:
        runs.append(dict(start=frame, end=frame, value=value))


def inspect(name):
    public = RUN / name / 'public'
    prediction_maps = {}
    changed = {arm: dict(frames=0, source_observations=0, first_frame=None) for arm in STATE_ARMS[1:]}
    for row in rows(public / 'predictions.jsonl.gz'):
        maps = mappings(row)
        prediction_maps[row['global_frame']] = maps
        for arm, count in changed.items():
            sources = [n for n in maps['Z4Q_FROZEN'] if maps[arm][n] != maps['Z4Q_FROZEN'][n]]
            count['frames'] += bool(sources)
            count['source_observations'] += len(sources)
            if sources and count['first_frame'] is None:
                count['first_frame'] = row['global_frame']

    automatic = read(public / 'AUTOMATIC_RECONNECT_AUDIT.json')
    event_audit = read(public / 'EVENT_AUDIT.json')['arms']
    cases = []
    for frame, source, target in ORIGINAL_ACTIONS.get(name, []):
        assert prediction_maps[frame]['Z4Q_FROZEN'][source] == target, (name, frame, 'original action mapping')
        old = [a for a in automatic['arms']['Z4Q_FROZEN'] if a['global_frame'] == frame and
               a['source'] == source and a['target'] == target and a['durable_automatic_commit']]
        assert len(old) == 1, (name, frame, 'original action commit')
        cases.append(dict(global_frame=frame, source=source, target=target,
            original_action=old[0], arms={arm: dict(at_original_frame=None, first_target_publication=None,
                first_durable_target_alias=None, source_mapping_runs=[], alias_runs=[],
                source_frames=0, publication_diff_vs_original=0, first_publication_diff=None,
                alias_diff_vs_original=0, first_alias_diff=None,
                original_target_alias_observed=0, original_target_alias_not_preserved=0,
                depth_check_counts=Counter(), depth_check_examples=[])
                for arm in STATE_ARMS}))

    tx_frames = {}
    alias_diff = {arm: dict(frames=0, first_frame=None) for arm in STATE_ARMS[1:]}
    depth_status, depth_reasons = Counter(), Counter()
    depth_vetoes = 0
    accepted_previews, durable_commits = Counter(), Counter()
    for tx in rows(public / 'TRANSACTIONS.jsonl.gz'):
        frame, arm = tx['global_frame'], tx['arm']
        accepted_previews[arm] += len(tx['automatic_candidate_events'])
        durable_commits[arm] += len(tx['durable_automatic_commits'])
        if arm == 'Z4Q_DEPTH':
            for check in tx['controller_trace'].get('ds15_auto_depth_checks', []):
                depth_status[check['depth_status']] += 1
                depth_reasons[check['reason']] += 1
                depth_vetoes += bool(check['veto'])
        tx_frames.setdefault(frame, {})[arm] = tx
        if len(tx_frames[frame]) != len(STATE_ARMS):
            continue
        batch = tx_frames.pop(frame)
        original = batch['Z4Q_FROZEN']
        for candidate, count in alias_diff.items():
            diff = batch[candidate]['actual_alias_targets'] != original['actual_alias_targets']
            count['frames'] += diff
            if diff and count['first_frame'] is None:
                count['first_frame'] = frame
        for case in cases:
            source, target = case['source'], case['target']
            original_alias = original['actual_alias_targets'].get(str(source))
            for current_arm, out in case['arms'].items():
                transaction = batch[current_arm]
                actual = prediction_maps[frame][current_arm].get(source)
                alias = transaction['actual_alias_targets'].get(str(source))
                if actual == target and out['first_target_publication'] is None:
                    out['first_target_publication'] = frame
                if alias == target and out['first_durable_target_alias'] is None:
                    out['first_durable_target_alias'] = frame
                if actual is not None:
                    out['source_frames'] += 1
                    append_run(out['source_mapping_runs'], frame, actual)
                    publication_diff = actual != prediction_maps[frame]['Z4Q_FROZEN'].get(source)
                    out['publication_diff_vs_original'] += publication_diff
                    if publication_diff and out['first_publication_diff'] is None:
                        out['first_publication_diff'] = frame
                if str(source) in original['actual_alias_targets'] or alias is not None:
                    append_run(out['alias_runs'], frame, alias)
                    difference = original_alias != alias
                    out['alias_diff_vs_original'] += difference
                    if difference and out['first_alias_diff'] is None:
                        out['first_alias_diff'] = frame
                if frame >= case['global_frame'] and original_alias == target:
                    out['original_target_alias_observed'] += 1
                    out['original_target_alias_not_preserved'] += alias != target
                if frame == case['global_frame']:
                    out['at_original_frame'] = dict(published=actual, durable_alias=alias,
                        active_event=transaction.get('active_event'), restore=transaction.get('restore'),
                        birth_candidate_checks=[check for check in transaction['controller_trace'].get('birth_checks', [])
                            if check.get('native_id') == source],
                        automatic_candidate_events=transaction['automatic_candidate_events'],
                        durable_automatic_commits=transaction['durable_automatic_commits'])
                for check in transaction['controller_trace'].get('ds15_auto_depth_checks', []):
                    if check['native_id'] == source and check['public_id'] == target:
                        out['depth_check_counts'][check['reason']] += 1
                        if len(out['depth_check_examples']) < 8 and (check['veto'] or
                                check['depth_status'] == 'SOURCE_BOUND_COMPARABLE'):
                            out['depth_check_examples'].append(dict(global_frame=frame, check=check))
    assert not tx_frames, 'Incomplete transaction frame'
    for case in cases:
        for arm, out in case['arms'].items():
            out['depth_check_counts'] = dict(out['depth_check_counts'])
            out['scored_automatic_actions'] = [a for a in automatic['arms'][arm]
                if a['source'] == case['source'] and a['target'] == case['target']]
            if arm in event_audit:
                out['scored_related_births'] = [b for b in event_audit[arm]['birth_commits']
                    if b['source'] == case['source']]
                out['scored_related_groups'] = [g for g in event_audit[arm]['group_events']
                    if str(case['source']) in g.get('actual_first_public_mapping', {})]
    return dict(original_actions=cases, changed_publication_vs_original=changed,
        durable_alias_state_diff_vs_original=alias_diff,
        automatic_depth_checks=dict(status=dict(depth_status), reason=dict(depth_reasons), vetoes=depth_vetoes),
        accepted_automatic_previews=dict(accepted_previews), durable_automatic_commits=dict(durable_commits),
        scored_automatic_counts=automatic['counts'],
        scored_event_counts={arm: {k: value[k] for k in ('group_physical_counts', 'birth_physical_counts')}
            for arm, value in event_audit.items() if arm in STATE_ARMS},
        inputs={filename: artifact(public / filename) for filename in (
            'predictions.jsonl.gz', 'TRANSACTIONS.jsonl.gz', 'AUTOMATIC_RECONNECT_AUDIT.json', 'EVENT_AUDIT.json')})


def main():
    scored = ready()
    outputs = [HERE / name for name in ('POSTSEAL_ORIGINAL_ACTION_REVIEW.json', 'POSTSEAL_ORIGINAL_ACTION_REVIEW.md')]
    assert not any(path.exists() for path in outputs), 'Append-only review'
    details = {name: inspect(name) for name in SEGMENTS}
    units = {name: value['metrics'] for name, value in scored['segments'].items() if not name.startswith('feeding_')}
    units['Feeding_pooled1471'] = scored['feeding_pooled']['metrics']
    report = dict(status='COMPLETED_OUTPUT_INDEPENDENT_REVIEW', raw_GT_reads=0, predictor_calls=0,
        scientific_files_changed=0, reviewed_original_successes=6, details=details,
        metric_differences={name: {base: {k: metrics['Z4Q_DEPTH'][k] - metrics[base][k] for k in FIELDS}
            for base in ('SAM3_NATIVE', 'Z4Q_FROZEN', 'Z4Q_SHARED')} for name, metrics in units.items()},
        completed_score=artifact(RUN / 'METRICS.json'), score_provenance=artifact(RUN / 'SCORE_PROVENANCE.json'),
        reviewer=artifact(Path(__file__)), physical_verdicts='Existing sealed scorer audits; no new GT or depth truth inference')
    with outputs[0].open('x', encoding='utf-8', newline='\n') as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write('\n')
    lines = ['# DS15 original-action preservation review', '',
        'Independent review of completed sealed predictions and scorer audits. No raw GT or predictor was opened.', '',
        '| Segment | Original global frame | Source→target | Arm | Published at original frame | Durable at original frame | First target publication | First durable alias | Publication differences for this source |',
        '|---|---|---|---|---|---|---|---|---|']
    for name, detail in details.items():
        for case in detail['original_actions']:
            for arm, out in case['arms'].items():
                at = out['at_original_frame']
                lines.append(f"| {name} | {case['global_frame']} | {case['source']}→{case['target']} | {arm} | "
                    f"{at['published']} | {at['durable_alias']} | {out['first_target_publication']} | "
                    f"{out['first_durable_target_alias']} | {out['publication_diff_vs_original']} |")
    lines += ['', 'Publication and durable state are separate. Full mapping/alias runs, active events, accepted candidates, '
        'actual commits, strong veto examples and scorer verdicts are retained in the JSON.', '',
        '## DEPTH metric differences', '', '| Unit | Compared with | ΔIDF1 | ΔHOTA | ΔAssA | ΔIDSW | ΔFP | ΔFN |',
        '|---|---|---|---|---|---|---|---|']
    for name, comparisons in report['metric_differences'].items():
        for base, delta in comparisons.items():
            values = [f'{delta[k]:+.6f}' if k in ('IDF1', 'HOTA', 'AssA') else f'{delta[k]:+d}' for k in FIELDS]
            lines.append('| ' + ' | '.join([name, base, *values]) + ' |')
    with outputs[1].open('x', encoding='utf-8', newline='\n') as handle:
        handle.write('\n'.join(lines) + '\n')
    print(json.dumps({name: {'changed': data['changed_publication_vs_original'],
        'automatic': data['scored_automatic_counts']} for name, data in details.items()}))


if __name__ == '__main__':
    main()
