"""Postseal switch attribution using published IDs, action state writes, and GT matches."""
import json

from source import HERE, SEGMENTS, save, sha


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def lines(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]


def events_for(row, kind):
    return [event for event in row.get('trace', {}).get('events', []) if event.get('kind') == kind]


def matched_gt(match_row, arm, native):
    return [m['gt_id'] for m in match_row['matches'][arm] if m['native_id'] == native]


def last_related(ledger, frame, native, public):
    for prior in range(frame, min(ledger)-1, -1):
        row = ledger[prior]
        for event in row['trace'].get('events', []):
            if event.get('kind') not in ('reconnect', 'native_conflict_rollback',
                     'native_return_quarantine_begin', 'native_return_quarantine_end',
                     'empty_native_quarantine_begin', 'empty_native_quarantine_end',
                     'birth_inherit', 'birth_reconnect'):
                continue
            if (event.get('native_id') == native or event.get('canonical_id') == public
                    or event.get('public_id') == public):
                return dict(frame=prior, event=event)
    return None


def switch_attribution(source, segment, branch, event, ledgers):
    frame, native = event['frame'], event['native_id']
    ledger = ledgers[segment]
    row = ledger[frame]
    onefix = branch == 'Z4Q_ONEFIX'
    if onefix:
        candidate = row['onefix']
        public = candidate['published_public'].get(str(native))
        state_write = candidate['state_write']
        current_events = candidate['events']
        guard = candidate['guard']
    elif branch == 'Z4Q_FROZEN':
        candidate = row['frozen']
        public = candidate['published_public'].get(str(native))
        state_write = candidate['state_write']
        current_events = candidate['trace'].get('events', [])
        guard = []
    else:
        public = native
        state_write, current_events, guard = {}, [], []
    alias_write = state_write.get('alias', {}).get(str(native))
    recent = last_related({f: r['frozen'] for f, r in ledger.items()}, frame, native,
                          int(public) if public is not None else native)
    return dict(source=source, segment=segment, branch=branch, frame=frame,
        gt_id=event['gt_id'], native_id=native, native_mask=event['native_mask'],
        matched_iou=event['matched_iou'], from_public_id=event['from_public_id'],
        to_public_id=event['to_public_id'], current_public_for_native=public,
        current_alias_write=alias_write, current_state_write_fields=sorted(state_write),
        current_event_kinds=[item['kind'] for item in current_events],
        current_guard_native_ids=[item['native_id'] for item in guard],
        nearest_frozen_related_action=recent, nearest_is_causal_proof=False,
        current_public_equals_native=public == native,
        full_trace_ref=f'public/{source}/{segment}/B0_ACTION_LEDGER.jsonl#original_frame={frame}')


def main():
    frozen = read(HERE / 'public/BASELINE_SWITCH_DECOMPOSITION.json')
    fixed = read(HERE / 'public/ONEFIX_SWITCH_LEDGER.json')
    result = {}
    for source in ('SOURCE_OLD', 'SOURCE_BASELINE'):
        all_matches = lines(HERE / 'public' / source / 'GT_MATCHED_LEDGER.jsonl')
        matches = {(row['segment'], row['local_frame']): row for row in all_matches}
        ledgers = {}
        action_checks = []
        for segment, (start, stop) in SEGMENTS.items():
            path = HERE / 'public' / source / segment
            b0 = {row['original_frame']: row for row in lines(path / 'B0_ACTION_LEDGER.jsonl')}
            one = {row['original_frame']: row for row in lines(path / 'onefix/ACTION_LEDGER.jsonl')}
            assert set(b0) == set(one) == set(range(start, stop+1))
            ledgers[segment] = {frame: dict(frozen=b0[frame], onefix=one[frame]) for frame in b0}
            for frame, row in b0.items():
                for event in events_for(row, 'reconnect'):
                    if not event.get('accepted'):
                        continue
                    anchor = event['old_anchor']
                    native = event['native_id']
                    current_gt = matched_gt(matches[segment, row['frame']], 'NATIVE', native)
                    anchor_gt = matched_gt(matches[segment, anchor['frame']], 'NATIVE',
                                           anchor['native_id'])
                    assert len(current_gt) <= 1 and len(anchor_gt) <= 1
                    native_write = row['state_write'].get('native_runs', {}).get(str(native), {})
                    count_before = native_write.get('before', {}).get('count') if native_write.get('before') else None
                    onefix_frame = one[frame]
                    first_eligible = [r['original_frame'] for r in b0.values()
                        if str(native) in r['state_write'].get('first_eligible', {})
                        and r['state_write']['first_eligible'][str(native)]['before'] is None]
                    action_checks.append(dict(source=source, segment=segment, original_frame=frame,
                        native_id=native, old_public_id=event['canonical_id'],
                        birth_frame=event['birth_frame'], native_run_count_before=count_before,
                        first_eligible_original_frame=first_eligible[0] if first_eligible else None,
                        anchor=anchor, anchor_gt=anchor_gt, current_gt=current_gt,
                        physical_relation=('SAME_GT' if current_gt and anchor_gt and current_gt == anchor_gt else
                                           'DIFFERENT_GT' if current_gt and anchor_gt else 'UNKNOWN'),
                        frozen_published_public=row['published_public'].get(str(native)),
                        onefix_published_public=onefix_frame['published_public'].get(str(native)),
                        frozen_alias_write=row['state_write'].get('alias', {}).get(str(native)),
                        onefix_alias_write=onefix_frame['state_write'].get('alias', {}).get(str(native)),
                        onefix_guard_at_action=[g for g in onefix_frame['guard'] if g['native_id'] == native],
                        note='GT consulted only after all prediction seals'))
        switches = {
            'NATIVE': frozen['source'][source]['switches']['NATIVE'],
            'Z4Q_FROZEN': frozen['source'][source]['switches']['Z4Q_FROZEN'],
            'Z4Q_ONEFIX': fixed['source'][source]}
        event_key = lambda event: (event['segment'], event['frame'], event['gt_id'])
        exact_key = lambda event: (*event_key(event), event['from_public_id'], event['to_public_id'])
        occurrences = {arm: {event_key(event) for event in events} for arm, events in switches.items()}
        exact = {arm: {exact_key(event) for event in events} for arm, events in switches.items()}
        classified = []
        for arm, events in switches.items():
            classified.extend(switch_attribution(source, event['segment'], arm, event, ledgers)
                              for event in events)
        differences = {}
        for segment in SEGMENTS:
            rows = ledgers[segment]
            changed = [frame for frame, arms in rows.items()
                       if arms['frozen']['published_public'] != arms['onefix']['published_public']]
            differences[segment] = dict(frames_changed=len(changed), original_frames=changed)
        result[source] = dict(
            switch_occurrences={arm: len(events) for arm, events in occurrences.items()},
            occurrence_frozen_only_vs_native=sorted(occurrences['Z4Q_FROZEN']-occurrences['NATIVE']),
            occurrence_native_only_vs_frozen=sorted(occurrences['NATIVE']-occurrences['Z4Q_FROZEN']),
            occurrence_onefix_only_vs_native=sorted(occurrences['Z4Q_ONEFIX']-occurrences['NATIVE']),
            occurrence_native_only_vs_onefix=sorted(occurrences['NATIVE']-occurrences['Z4Q_ONEFIX']),
            exact_frozen_only_vs_native=sorted(exact['Z4Q_FROZEN']-exact['NATIVE']),
            exact_native_only_vs_frozen=sorted(exact['NATIVE']-exact['Z4Q_FROZEN']),
            accepted_frozen_reconnects=action_checks, switch_action_ledger=classified,
            onefix_vs_frozen_publication_difference=differences)
    save(HERE / 'public/POSTSEAL_CAUSE_REVIEW.json', dict(status='POSTSEAL_GT_DIAGNOSTIC',
        source=result, frozen_decomposition_sha256=sha(HERE / 'public/BASELINE_SWITCH_DECOMPOSITION.json'),
        onefix_switch_sha256=sha(HERE / 'public/ONEFIX_SWITCH_LEDGER.json'), model_http=0))
    print(json.dumps({source: {key: result[source][key] for key in (
        'switch_occurrences', 'occurrence_frozen_only_vs_native',
        'occurrence_onefix_only_vs_native', 'occurrence_native_only_vs_onefix',
        'accepted_frozen_reconnects')} for source in result}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
