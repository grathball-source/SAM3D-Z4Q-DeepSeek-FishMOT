"""Postseal scored evidence and logged-matrix analysis; never replays a tracker."""
from common import *
from collections import Counter

PID_ARMS = ARMS[2:]
PHYSICAL = ('CORRECT', 'WRONG', 'UNSCORABLE')


def action_key(a):
    return a['arm'], a['frame'], a['source'], a['target']


def ordered(records):
    return sorted(records, key=lambda a: (a.get('global_frame', a['frame']),
                                         a.get('source', a.get('native_id', -1)), a.get('target', -1)))


def physical_counts(records):
    counts = Counter(a['physical'] for a in records)
    return {key: counts[key] for key in PHYSICAL}


def ranges(frames):
    out = []
    for frame in frames:
        if out and frame == out[-1][1] + 1:
            out[-1][1] = frame
        else:
            out.append([frame, frame])
    return out


def first(records, predicate=lambda _: True):
    return next((record for record in ordered(records) if predicate(record)), None)


def evidence(path, **selector):
    return dict(path=str(path.resolve()), **selector)


def switch_difference(baseline, current):
    # Identical full CLEAR records, matching the frozen scorer's definition.
    old = {digest(row): row for row in baseline}
    new = {digest(row): row for row in current}
    assert len(old) == len(baseline) and len(new) == len(current)
    return dict(added=ordered([new[k] for k in new.keys() - old.keys()]),
                eliminated=ordered([old[k] for k in old.keys() - new.keys()]),
                common=len(old.keys() & new.keys()))


def analyze_segment(name, result, match, np, pins):
    p = RUN / name / 'public'
    files = {filename: p / filename for filename in
             ('ACTION_AUDIT.json', 'SWITCHES.json', 'SWITCH_CHANGES.json',
              'REFERENCE_MATCHES.jsonl.gz', 'EVENTS.json', 'TRANSACTIONS.jsonl.gz')}
    for path in files.values():
        if not path.is_file():
            raise FileNotFoundError(path)
        pins.append(artifact(path))
    seal = read(p / 'PREDICTIONS_SEALED.json')
    for filename in ('EVENTS.json', 'TRANSACTIONS.jsonl.gz'):
        assert sha(files[filename]) == seal['artifacts_sha256'][filename], filename
    start, stop = SEGMENTS[name]
    assert result['frames'] == stop - start + 1
    matches = {row['frame']: row['matches'] for row in rows(files['REFERENCE_MATCHES.jsonl.gz'])}
    assert set(matches) == set(range(1, result['frames'] + 1))
    actions = read(files['ACTION_AUDIT.json'])['actions']
    action_index = {action_key(a): i for i, a in enumerate(actions)}
    assert len(action_index) == len(actions)
    origin_path = p / 'ORIGIN_ACTION_AUDIT.json'
    origins = {}
    if origin_path.is_file():
        pins.append(artifact(origin_path))
        origins = {action_key(a): (i, a) for i, a in enumerate(read(origin_path)['records'])}

    def endpoint(frame, source):
        return dict(local_frame=frame, global_frame=start + frame - 1, native_source=source,
                    match=matches.get(frame, {}).get(str(source), {'status': 'SOURCE_OR_REFERENCE_MISSING'}),
                    evidence=evidence(files['REFERENCE_MATCHES.jsonl.gz'], frame=frame, native_source=source))

    def enriched(a):
        out = dict(a, evidence=evidence(files['ACTION_AUDIT.json'], action_index=action_index[action_key(a)]),
                   query_match=endpoint(a['frame'], a['source']),
                   actual_reference_match=endpoint(a['reference']['frame'], a['reference']['native_id']))
        if action_key(a) in origins:
            index, origin = origins[action_key(a)]
            assert origin['physical'] == a['physical'] and origin['mapping_changed'] == a['mapping_changed']
            out['public_origin'] = dict(first_public_origin=origin['first_public_origin'],
                                        relations=origin['relations'],
                                        initial_public_origin_mismatch=origin['initial_public_origin_mismatch'],
                                        evidence=evidence(origin_path, record_index=index))
        else:
            out['public_origin'] = dict(status='NOT_AUDITED_FOR_THIS_ACTION')
        return out

    changed = [enriched(a) for a in actions if a['mapping_changed']]
    actual = {}
    for arm in PID_ARMS:
        all_arm = [a for a in actions if a['arm'] == arm]
        true_changes = ordered([a for a in changed if a['arm'] == arm])
        by_source = {}
        for source in sorted({a['source'] for a in true_changes}):
            source_actions = [a for a in true_changes if a['source'] == source]
            by_source[str(source)] = dict(changed_actions=len(source_actions), physical=physical_counts(source_actions),
                                          first_changed_action=source_actions[0])
        actual[arm] = dict(all_accepted_edges=len(all_arm), same_pid_recertifications=len(all_arm)-len(true_changes),
                           changed_pid_actions=len(true_changes), physical=physical_counts(true_changes),
                           per_native_source=by_source, changed_records=true_changes,
                           first_examples={kind: first(true_changes, lambda a, k=kind: a['physical'] == k)
                                           for kind in PHYSICAL})

    action_lookup = {action_key(a): a for a in actions}
    matrix_counts = Counter(dict.fromkeys((
        'frames_checked', 'unlocked_observation_rows', 'zero_feasible_old_pid_rows',
        'one_feasible_old_pid_rows', 'multiple_feasible_old_pid_rows',
        'geometry_accepted_edges', 'depth_accepted_edges', 'active_depth_rows',
        'frames_with_modified_cost', 'frames_with_changed_accepted_edges',
        'added_accepted_edges', 'removed_accepted_edges', 'replaced_source_targets',
        'added_actual_pid_changes', 'added_same_pid_recertifications',
        'removed_target_still_published', 'removed_target_not_published',
        'geometry_accepted_rows_suppressed_to_dummy', 'geometry_accepted_rows_suppressed_by_margin',
    ), 0))
    matrix_records = []
    trajectory_frames = []
    trajectory_sources = Counter()
    first_divergence = None
    motion = None
    seen = {arm: 0 for arm in PID_ARMS}
    for tx in rows(files['TRANSACTIONS.jsonl.gz']):
        arm, frame = tx['arm'], tx['frame']
        if arm not in PID_ARMS:
            continue
        seen[arm] += 1
        assert frame == seen[arm] and tx['global_frame'] == start + frame - 1
        if arm == 'PID_MOTION':
            motion = tx
            continue
        assert motion is not None and motion['frame'] == frame
        t = tx['controller_trace']
        sources, candidates = t['unlocked_sources'], t['candidate_pids']
        shape = len(sources), len(candidates)
        geometry = np.asarray(t['geometry_cost'], float).reshape(shape)
        depth = np.asarray(t['cost'], float).reshape(shape)
        feasible = np.asarray(t['feasible'], bool).reshape(shape)
        geo_selected, geo_detail = match(geometry, feasible)
        depth_selected, depth_detail = match(depth, feasible)
        geo = {sources[i]: candidates[j] for i, j, _ in geo_selected}
        selected = {sources[i]: candidates[j] for i, j, _ in depth_selected}
        assert selected == {a['source']: a['target'] for a in t['actions']}, (name, frame)
        assert all(tx['mapping'][str(source)] == target for source, target in selected.items())
        depth_raw_real = {sources[pair['row']]: dict(pair, target=candidates[pair['col']])
                          for pair in depth_detail['pairs']}
        geo_raw_real = {sources[pair['row']]: dict(pair, target=candidates[pair['col']])
                        for pair in geo_detail['pairs']}
        matrix_counts['frames_checked'] += 1
        matrix_counts['unlocked_observation_rows'] += len(sources)
        row_edges = feasible.sum(axis=1)
        matrix_counts['zero_feasible_old_pid_rows'] += int((row_edges == 0).sum())
        matrix_counts['one_feasible_old_pid_rows'] += int((row_edges == 1).sum())
        matrix_counts['multiple_feasible_old_pid_rows'] += int((row_edges >= 2).sum())
        matrix_counts['geometry_accepted_edges'] += len(geo)
        matrix_counts['depth_accepted_edges'] += len(selected)
        matrix_counts['active_depth_rows'] += sum(bool(d.get('active')) for d in t['depth_rows'])
        matrix_counts['frames_with_modified_cost'] += bool(np.any(geometry != depth))
        ge = set(geo.items())
        de = set(selected.items())
        added, removed = de-ge, ge-de
        replaced = [source for source in geo.keys() & selected.keys() if geo[source] != selected[source]]
        matrix_counts['added_accepted_edges'] += len(added)
        matrix_counts['removed_accepted_edges'] += len(removed)
        matrix_counts['replaced_source_targets'] += len(replaced)
        if added or removed:
            matrix_counts['frames_with_changed_accepted_edges'] += 1
            added_records = []
            for source, target in sorted(added):
                a = action_lookup[('PID_DEPTH', frame, source, target)]
                matrix_counts['added_actual_pid_changes' if a['mapping_changed'] else 'added_same_pid_recertifications'] += 1
                record = enriched(a)
                i, j = sources.index(source), candidates.index(target)
                record['same_state_matrix'] = dict(geometry_cost=float(geometry[i, j]), depth_cost=float(depth[i, j]),
                                                   geometry_raw_real_assignment=geo_raw_real.get(source),
                                                   depth_raw_real_assignment=depth_raw_real[source])
                added_records.append(record)
            removed_records = []
            for source, target in sorted(removed):
                published = tx['mapping'][str(source)]
                retained = target == published
                matrix_counts['removed_target_still_published' if retained else 'removed_target_not_published'] += 1
                raw = depth_raw_real.get(source)
                if source in selected:
                    suppression = 'REPLACED_BY_OTHER_ACCEPTED_EDGE'
                elif raw is None:
                    suppression = 'DUMMY_IN_MINIMUM_COST_ASSIGNMENT'
                    matrix_counts['geometry_accepted_rows_suppressed_to_dummy'] += 1
                else:
                    assert not raw['accepted']
                    suppression = 'REAL_EDGE_REJECTED_BY_GLOBAL_MARGIN'
                    matrix_counts['geometry_accepted_rows_suppressed_by_margin'] += 1
                i, j = sources.index(source), candidates.index(target)
                removed_records.append(dict(source=source, geometry_target=target, actual_published_pid=published,
                                            rejected_geometry_target_still_published=retained,
                                            actual_accepted_target=selected.get(source),
                                            depth_assignment_effect=suppression, depth_raw_real_assignment=raw,
                                            geometry_raw_real_assignment=geo_raw_real[source],
                                            geometry_cost=float(geometry[i, j]), depth_cost=float(depth[i, j]),
                                            physical='UNSCORABLE_COUNTERFACTUAL_REFERENCE_NOT_RECORDED',
                                            query_match=endpoint(frame, source)))
            matrix_records.append(dict(frame=frame, global_frame=tx['global_frame'], added=added_records,
                                       removed=removed_records,
                                       geometry_best_total_cost=geo_detail['best_cost'], depth_best_total_cost=depth_detail['best_cost'],
                                       replacements=[dict(source=n, geometry_target=geo[n], actual_depth_target=selected[n])
                                                     for n in sorted(replaced)],
                                       evidence=evidence(files['TRANSACTIONS.jsonl.gz'], arm=arm, frame=frame),
                                       protected_pids=t.get('protected_pids', []),
                                       occupied_member_targets=t.get('occupied_member_targets', []),
                                       group_records=t.get('group_records', [])))
        different = [dict(source=int(n), motion_pid=motion['mapping'][n], depth_pid=target)
                     for n, target in tx['mapping'].items() if motion['mapping'][n] != target]
        if different:
            trajectory_frames.append(tx['global_frame'])
            trajectory_sources.update(x['source'] for x in different)
            if first_divergence is None:
                first_divergence = dict(frame=frame, global_frame=tx['global_frame'], mapping_differences=different,
                                        evidence=evidence(files['TRANSACTIONS.jsonl.gz'], frame=frame, arms=list(PID_ARMS)))
    assert all(n == result['frames'] for n in seen.values())
    assert trajectory_frames == result['depth_vs_motion_changed_frames']
    assert matrix_counts['unlocked_observation_rows'] == sum(matrix_counts[key] for key in
        ('zero_feasible_old_pid_rows', 'one_feasible_old_pid_rows', 'multiple_feasible_old_pid_rows'))
    assert matrix_counts['geometry_accepted_edges'] + matrix_counts['added_accepted_edges'] - matrix_counts['removed_accepted_edges'] == matrix_counts['depth_accepted_edges']
    assert matrix_counts['removed_accepted_edges'] == sum(matrix_counts[key] for key in
        ('replaced_source_targets', 'geometry_accepted_rows_suppressed_to_dummy', 'geometry_accepted_rows_suppressed_by_margin'))
    assert matrix_counts['added_accepted_edges'] == matrix_counts['added_actual_pid_changes'] + matrix_counts['added_same_pid_recertifications']

    switches = read(files['SWITCHES.json'])
    saved_changes = read(files['SWITCH_CHANGES.json'])
    for arm in ARMS:
        assert len(switches[arm]) == result['metrics'][arm]['IDSW']

    def switch_example(row, arm, role):
        if row is None:
            return None
        local = row['frame'] - start + 1
        same_frame = [a for a in changed if a['arm'] == arm and a['frame'] == local and a['source'] == row['native_id']]
        return dict(switch=row, meaning=role, query_match=endpoint(local, row['native_id']),
                    contemporaneous_changed_actions=same_frame,
                    evidence=evidence(files['SWITCHES.json'], arm=arm, global_frame=row['frame'], gt_id=row['gt_id']),
                    cause='NOT_INFERRED_FROM_TEMPORAL_COINCIDENCE')

    switch_comparisons = {}
    for arm, baseline in [('PID_MOTION', 'Z4Q_FROZEN'), ('PID_DEPTH', 'Z4Q_FROZEN'), ('PID_DEPTH', 'PID_MOTION')]:
        change = switch_difference(switches[baseline], switches[arm])
        if baseline == 'Z4Q_FROZEN':
            assert {digest(x) for x in change['added']} == {digest(x) for x in saved_changes[arm]['added']}
            assert {digest(x) for x in change['eliminated']} == {digest(x) for x in saved_changes[arm]['eliminated']}
            assert change['common'] == saved_changes[arm]['common']
        assert len(change['added'])-len(change['eliminated']) == result['metrics'][arm]['IDSW']-result['metrics'][baseline]['IDSW']
        switch_comparisons[arm+'_minus_'+baseline] = dict(
            added_count=len(change['added']), eliminated_count=len(change['eliminated']), common_count=change['common'],
            net_idsw=len(change['added'])-len(change['eliminated']), added=change['added'], eliminated=change['eliminated'],
            first_added=switch_example(first(change['added']), arm, 'ADDED_NUMERIC_CLEAR_SWITCH_NOT_AUTOMATIC_PHYSICAL_FAILURE'),
            first_eliminated=switch_example(first(change['eliminated']), baseline, 'ELIMINATED_BASELINE_SWITCH_NOT_AUTOMATIC_PHYSICAL_RECOVERY'),
            evidence=evidence(files['SWITCH_CHANGES.json']) if baseline == 'Z4Q_FROZEN' else evidence(files['SWITCHES.json']))
    events = read(files['EVENTS.json'])
    event_summary = {arm: dict(count=len(events[arm]), statuses=dict(Counter(e['status'] for e in events[arm])),
                              q_count=sum(e['q'] is not None for e in events[arm]),
                              confirmed_count=sum(e['confirm_frame'] is not None for e in events[arm]),
                              evidence=evidence(files['EVENTS.json'], arm=arm)) for arm in PID_ARMS}
    return dict(reference_status=result['reference_status'], frames=result['frames'], metrics=result['metrics'],
                depth_minus_motion=result['depth_minus_motion'], deltas_vs_controls=result['deltas'],
                actual_actions=actual, events=event_summary,
                origin_audit_status='AVAILABLE' if origin_path.is_file() else 'NOT_PRESENT',
                same_state_depth=dict(counts=dict(matrix_counts), records=matrix_records,
                                      counter_definitions=dict(
                                          state='Both matrices use the actual PID_DEPTH branch state and feasible edges at that frame; geometry accepted counts are not PID_MOTION trajectory counts.',
                                          feasible_rows='Frozen hard geometry/quality edges; zero/one/multiple categories partition unlocked rows.',
                                          suppression='Among geometry-accepted rows with no depth-accepted edge: raw Hungarian dummy versus real edge rejected by deletion margin.',
                                          removed_publication='Compare rejected geometry target with actual current publication; no claim about unlogged previous PID.',
                                      ),
                                      first_added=first(matrix_records, lambda r: bool(r['added'])),
                                      first_removed=first(matrix_records, lambda r: bool(r['removed'])),
                                      first_replaced=first(matrix_records, lambda r: bool(r['replacements']))),
                cross_arm_trajectory=dict(divergent_frames=len(trajectory_frames), global_frame_ranges=ranges(trajectory_frames),
                                          changed_source_frame_pairs=sum(trajectory_sources.values()),
                                          per_native_source=dict(trajectory_sources), first_divergence=first_divergence),
                switch_comparisons=switch_comparisons)


def main():
    seal_path, metric_path = RUN/'ALL_PREDICTIONS_SEALED.json', RUN/'METRICS.json'
    if not seal_path.is_file() or not metric_path.is_file():
        raise RuntimeError('All prediction/access seals and completed scored metrics are required before analysis')
    sealed, metrics = read(seal_path), read(metric_path)
    assert sealed['status'] == 'ALL_PREDICTIONS_AND_ACCESS_SEALED'
    assert metrics['status'] == 'SCORED_AFTER_ALL_EIGHT_PREDICTION_AND_ACCESS_SEALS'
    assert sealed['frames'] == metrics['frames'] == sum(b-a+1 for a, b in SEGMENTS.values()) == 20098
    assert tuple(sealed['arms']) == ARMS and set(metrics['segments']) == set(SEGMENTS)
    assert metrics['all_seal'] == artifact(seal_path)
    pins = [artifact(seal_path), artifact(metric_path)]
    for name in SEGMENTS:
        verify_item(sealed['seals'][name])
        verify_item(sealed['access_seals'][name])
        pins.extend([sealed['seals'][name], sealed['access_seals'][name]])
    frozen = read(HERE/'RUNTIME_FREEZE.json')
    for filename in ('identity.py', 'CONFIG.json'):
        path = HERE/filename
        assert sha(path) == frozen['code'][str(path.resolve())]
        pins.append(artifact(path))
    # Only solve already recorded matrices. No Identity object, step, or reference raster read.
    from identity import match, np
    results = {name: analyze_segment(name, metrics['segments'][name], match, np, pins) for name in SEGMENTS}
    totals = dict(
        actual_actions={arm: dict(
            **{key: sum(r['actual_actions'][arm][key] for r in results.values()) for key in
               ('all_accepted_edges', 'same_pid_recertifications', 'changed_pid_actions')},
            physical={kind: sum(r['actual_actions'][arm]['physical'][kind] for r in results.values()) for kind in PHYSICAL})
            for arm in PID_ARMS},
        same_state_depth={key: sum(r['same_state_depth']['counts'][key] for r in results.values())
                          for key in next(iter(results.values()))['same_state_depth']['counts']},
        cross_arm_trajectory={key: sum(r['cross_arm_trajectory'][key] for r in results.values())
                              for key in ('divergent_frames', 'changed_source_frame_pairs')},
        switch_comparisons={label: {key: sum(r['switch_comparisons'][label][key] for r in results.values())
                                   for key in ('added_count', 'eliminated_count', 'common_count', 'net_idsw')}
                            for label in next(iter(results.values()))['switch_comparisons']},
    )
    for item in pins:
        verify_item(item)
    out = dict(schema='DS31_POSTSEAL_ANALYSIS_V1', status='POSTSEAL_LOGGED_MATRIX_AND_SCORED_EVIDENCE_ANALYSIS',
               helper=artifact(__file__), evidence_artifacts=pins, totals=totals, segments=results,
               totals_policy='Counts summed over independent segment ID domains; no cross-source metric average or physical-fish count.',
               example_policy='First by frame within each independent segment; no single cross-source chronological ordering.',
               boundaries=dict(new_GT_or_RGB_raster_read=False, predictions_read=False, tracker_replay=False,
                               science_or_parameter_edits=False, hypothetical_metrics=False),
               caveats=[
                   'Same-state matrix deltas include depth-induced rejection and indirect joint competition, not only accepted alternatives.',
                   'Replacement rows are a subset of both added and removed accepted edges; do not add these three counts together.',
                   'Same-state removed edges are unexecuted geometry alternatives; absent target references cannot be physically graded.',
                   'An unaccepted geometry target may still be published through continuity; rejection is not necessarily a PID change.',
                   'Cross-arm trajectory divergence includes propagated prior state differences and is separate from same-state cost effects.',
                   'Actual changed-action physical grade is against the recorded bank reference; initial public-origin semantics are separate.',
                   'Native-source grouping may combine source generations; these are handle-level counts, not certified physical fish counts.',
                   'Added or eliminated CLEAR switches are numeric events, not automatically wrong or correct physical associations.',
                   'Switch record identity uses complete scored records; changed endpoints can produce one added and one eliminated record.',
                   'L3/LW use weak unreviewed prediction-derived references; all sources are exposed diagnostics.',
                   'Actions cover accepted bank edges; allocation/collision PID changes without an accepted edge are not in ACTION_AUDIT.',
                   'Implementation-supported possible mechanism: an unaccepted unlocked observation retaining an established old bank sets source.risk and skips clean refresh; there is no separate reanchor escape after the 12-second bank search expiry. Matrices alone do not prove this is the unique cause without complete bank snapshots.',
                   'No causal mechanism is inferred from a nearby action or event; examples retain the recorded evidence and UNKNOWN.',
               ])
    write_new(HERE/'ANALYSIS.json', out)
    print(str(HERE/'ANALYSIS.json'), flush=True)


if __name__ == '__main__':
    main()
