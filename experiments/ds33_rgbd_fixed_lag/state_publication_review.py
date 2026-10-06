"""Late, read-only publication/state audit; never import or open GT scoring inputs."""
from common import *
from collections import Counter
from datetime import datetime, timezone
from statistics import median
from verify_inputs import verify_all


STATE_ARMS = ARMS[1:]
EVENT_ARMS = ARMS[2:]


def int_map(value):
    assert all(type(v) is int for v in value.values())
    return {int(k):v for k, v in value.items()}


def distribution(values):
    return dict(n=len(values), minimum=min(values) if values else None,
                median=median(values) if values else None,
                maximum=max(values) if values else None)


def action_keys(actions):
    return {(a['native_id'], a['canonical_id'],
             'BIRTH_REFINE' if a.get('phase') == 'birth' else 'D1_DELAYED')
            for a in actions}


def review_source(name, initial_state_hash):
    public = RUN / name / 'public'
    total = SEGMENTS[name][1] - SEGMENTS[name][0] + 1
    events, summary = read(public / 'EVENTS.json'), read(public / 'RUN_SUMMARY.json')
    assert set(events) == set(EVENT_ARMS)
    tx_rows = iter(rows(public / 'TRANSACTIONS.jsonl.gz'))
    ledgers = iter(rows(public / 'PUBLISH_LEDGER.jsonl'))
    hashes, publications, frame_reviews = {}, {}, []
    parity = {arm:Counter() for arm in EVENT_ARMS}
    for frame, prediction in enumerate(rows(public / 'predictions.jsonl.gz'), 1):
        ledger = next(ledgers)
        assert prediction['frame'] == ledger['frame'] == frame
        assert prediction['global_frame'] == ledger['global_frame'] == SEGMENTS[name][0] + frame - 1
        assert ledger['prediction_row_sha256'] == row_sha(prediction)
        arrival = ledger['first_publish_at_arrival_frame']
        assert arrival == min(frame + CFG['lag_frames'], total)
        assert not ledger['already_published_history_rewritten'] and ledger['actual_delay_frames'] == arrival - frame
        native = prediction['variants']['SAM3_NATIVE']
        native_by_token = {o['mask']:o['id'] for o in native}
        assert len(native_by_token) == len(native) == len({o['id'] for o in native})
        transactions = {}
        for arm in STATE_ARMS:
            transaction = next(tx_rows)
            assert (transaction['arm'], transaction['frame'], transaction['version']) == (arm, frame, frame)
            assert (transaction['global_frame'], transaction['time']) == (prediction['global_frame'], prediction['time'])
            assert ledger['transaction_row_sha256'][arm] == row_sha(transaction)
            assert transaction['decided_before_first_publish'] and not transaction['already_published_history_rewritten']
            objects = prediction['variants'][arm]
            assert [o['mask'] for o in objects] == [o['mask'] for o in native]
            assert all(type(o['id']) is int for o in objects) and len({o['id'] for o in objects}) == len(objects)
            mapping = {native_by_token[o['mask']]:o['id'] for o in objects}
            assert int_map(transaction['mapping']) == mapping
            for key in ('full_original_state_sha256', 'engine_state_sha256'):
                assert len(transaction[key]) == 64 and all(c in '0123456789abcdef' for c in transaction[key])
            transactions[arm] = transaction
        hashes[frame] = {arm:t['full_original_state_sha256'] for arm, t in transactions.items()}
        publications[frame] = dict(arrival=arrival, transactions={arm:{key:transaction[key]
            for key in ('mapping', 'actual_actions')} for arm, transaction in transactions.items()})
        per_frame = dict(frame=frame, global_frame=prediction['global_frame'],
            first_publish_at_arrival_frame=arrival,
            full_bridge_state_sha256=hashes[frame],
            engine_state_sha256={arm:t['engine_state_sha256'] for arm, t in transactions.items()},
            compared_with_Z4Q={})
        for arm in EVENT_ARMS:
            equality = dict(full_bridge_state=hashes[frame][arm] == hashes[frame]['Z4Q_FROZEN'],
                engine_state=transactions[arm]['engine_state_sha256'] == transactions['Z4Q_FROZEN']['engine_state_sha256'],
                mapping=int_map(transactions[arm]['mapping']) == int_map(transactions['Z4Q_FROZEN']['mapping']))
            per_frame['compared_with_Z4Q'][arm] = equality
            parity[arm].update({key + ('_equal' if same else '_different'):1 for key, same in equality.items()})
            parity[arm]['state_only_difference'] += not equality['full_bridge_state'] and equality['mapping']
        frame_reviews.append(per_frame)
    assert frame == total and next(tx_rows, None) is next(ledgers, None) is None
    assert summary['frames'] == summary['published_frames'] == total
    event_reviews, event_counts, evidence = {}, {}, {}
    for arm in EVENT_ARMS:
        counters = Counter({key:0 for key in ('requests', 'publication_changed_requests', 'UNKNOWN',
            'overlap', 'out_of_scope', 'raw_alternative_choices', 'invalid_candidate_fallbacks',
            'independent_window_replays', 'independent_changed_commits', 'q_minus_one_checkpoint_checks',
            'selected_state_cutoff_checks', 'independent_submitted_alternatives', 'shadow_checkpoint_differences',
            'all_request_q_minus_one_hash_comparisons', 'all_request_q_minus_one_hash_matches',
            'all_request_q_minus_one_hash_differences')})
        checks = []
        reasons, comparison_reasons, fractions, ages = Counter(), Counter(), [], []
        qualified = Counter({key:0 for key in ('windows_with_positive_common_depth_weight', 'samples',
            'clean_samples', 'comparisons', 'RGB_available_comparisons',
            'pre_anchor_depth_qualified_comparisons', 'local_3D_depth_qualified_comparisons')})
        for event in events[arm]:
            q, cutoff = event['request_frame'], event['evidence_max_frame']
            request = event['request']
            published = publications[q]
            actual = published['transactions'][arm]
            actual_mapping, original = int_map(actual['mapping']), int_map(request['original_mapping'])
            assert int_map(event['actual_first_mapping']) == int_map(event['first_published_mapping']) == actual_mapping
            changes = {str(n):dict(before=k, after=actual_mapping[n]) for n, k in original.items() if actual_mapping[n] != k}
            assert event['actual_changes'] == changes
            assert q <= cutoff <= min(q + CFG['lag_frames'], total) and cutoff <= published['arrival']
            assert event['first_publish_at_arrival_frame'] == published['arrival']
            assert event['actual_accepted_actions_at_first_publish'] == actual['actual_actions']
            previous_sha = initial_state_hash if q == 1 else hashes[q-1][arm]
            checkpoint_equal = request['checkpoint_sha256'] == previous_sha
            replay = event.get('replay')
            counters['requests'] += 1
            counters['all_request_q_minus_one_hash_comparisons'] += 1
            counters['all_request_q_minus_one_hash_matches'] += checkpoint_equal
            counters['all_request_q_minus_one_hash_differences'] += not checkpoint_equal
            counters['publication_changed_requests'] += bool(changes)
            counters['UNKNOWN'] += event.get('assessment', {}).get('status') == 'UNKNOWN_KEEP' or event['status'].startswith('UNKNOWN_')
            counters['overlap'] += event['status'] == 'ACTIVE_WINDOW_OVERLAP_KEEP'
            counters['out_of_scope'] += event['status'].startswith('OUT_OF_SCOPE') or event['status'] == 'OVERLAPPING_OR_MULTIPLE_COMPONENTS'
            counters['raw_alternative_choices'] += event['raw_selected_option'] != 'KEEP'
            counters['invalid_candidate_fallbacks'] += bool(event.get('invalid_candidate'))
            check = dict(id=event['id'], q=q, global_frame=event['global_frame'], evidence_cutoff=cutoff,
                first_publish_at_arrival_frame=published['arrival'], status=event['status'],
                raw_selected_option=event['raw_selected_option'], submitted_option=event['submitted_option'],
                actual_publication_changes=changes, checkpoint_frame=q-1,
                request_checkpoint_sha256=request['checkpoint_sha256'], actual_q_minus_one_state_sha256=previous_sha,
                checkpoint_matches_actual_selected_prefix=checkpoint_equal,
                original_trial_actions_missing_from_actual_publication=[list(key) for key in sorted(
                    action_keys(request['original_actions']) - action_keys(actual['actual_actions']))],
                shadow_request_not_an_independent_commit=replay is None,
                mapping_changed_by_earlier_active_window=event.get('mapping_changed_by_earlier_active_window', False))
            if replay is not None:
                assert checkpoint_equal and replay['checkpoint_sha256'] == previous_sha
                assert replay['selected_state_sha256'] == hashes[cutoff][arm]
                assert replay['frames'] == cutoff - q + 1 and replay['outside_mappings_preserved']
                assert replay['filtering_scope'] == 'UNPUBLISHED_WINDOW_ONLY' and not replay['direct_alias_writes']
                check.update(selected_state_sha256=replay['selected_state_sha256'],
                    actual_cutoff_transaction_state_sha256=hashes[cutoff][arm], selected_state_cutoff_match=True,
                    actual_replayed_frames=replay['frames'])
                counters['independent_window_replays'] += 1
                counters['independent_changed_commits'] += bool(changes)
                counters['q_minus_one_checkpoint_checks'] += 1
                counters['selected_state_cutoff_checks'] += 1
                counters['independent_submitted_alternatives'] += event['submitted_option'] != 'KEEP'
            else:
                counters['shadow_checkpoint_differences'] += not checkpoint_equal
            assessment = event.get('assessment', {})
            reasons[assessment.get('reason', event['status'])] += 1
            qualified['windows_with_positive_common_depth_weight'] += assessment.get('depth_common_component_weight', 0) > 0
            for sample in event.get('window_evidence', {}).get('samples', []):
                qualified['samples'] += 1
                qualified['clean_samples'] += sample['clean']
                for comparison in sample['comparisons'].values():
                    qualified['comparisons'] += 1
                    qualified['RGB_available_comparisons'] += comparison['status'] != 'UNKNOWN'
                    qualified['pre_anchor_depth_qualified_comparisons'] += bool(comparison.get('anchor_depth_usable'))
                    qualified['local_3D_depth_qualified_comparisons'] += bool(comparison.get('depth_available'))
                    comparison_reasons[comparison.get('reason') or 'AVAILABLE'] += 1
                    if 'reliable_fraction' in comparison: fractions.append(comparison['reliable_fraction'])
                    if 'actual_reference' in comparison: ages.append(sample['frame'] - comparison['actual_reference']['frame'])
            checks.append(check)
        actual_counts = summary['counts'][arm]
        for key, name_in_summary in (('requests', 'requests'), ('independent_window_replays', 'windows_resolved'),
                ('independent_changed_commits', 'changed_commits'), ('overlap', 'active_window_overlap'),
                ('out_of_scope', 'out_of_scope'), ('UNKNOWN', 'unknown_keep'),
                ('invalid_candidate_fallbacks', 'invalid_candidates')):
            assert counters[key] == actual_counts[name_in_summary], (name, arm, key)
        event_reviews[arm], event_counts[arm] = checks, dict(counters)
        evidence[arm] = dict(counts=dict(qualified), assessment_reasons=dict(reasons),
            comparison_reasons=dict(comparison_reasons), cumulative_reliable_contour_fraction=distribution(fractions),
            exact_bank_reference_age_frames=distribution(ages), physical_identity_not_certified=True)
    return dict(status='PASS', frames=total, source=name, GT_opened=False,
        artifacts={file:artifact(public / file) for file in ('PREDICTIONS_SEALED.json', 'ACCESS.json',
            'TRANSACTIONS.jsonl.gz', 'PUBLISH_LEDGER.jsonl', 'EVENTS.json', 'RUN_SUMMARY.json')},
        per_frame_state_hashes=frame_reviews, compared_with_Z4Q={a:dict(c) for a, c in parity.items()},
        event_counts=event_counts, request_state_publication_checks=event_reviews, evidence_availability=evidence)


def main():
    seal = verify_all()
    controller = module('ds33_postseal_state_review_controller', HERE / 'controller.py')
    initial_state_hash = controller.bridge_hash(controller.CandidateBridge(read(CONFIG_PATH)))
    sources = {name:review_source(name, initial_state_hash) for name in SEGMENTS}
    value = dict(status='PASS', created_utc=datetime.now(timezone.utc).isoformat(),
        review_role='LATE_READONLY_POST_SEAL_STATE_AND_FIRST_PUBLICATION_REVIEW',
        GT_opened=False, new_model_http=0, cost_usd=0,
        actual_full_state_hash_contract='engine/version/previous/epochs/provenance; transient added checks/policy excluded',
        limitation='Binds actual runtime state hashes and transaction/publication ledgers; not an independent rerun or physical identity score',
        all_source_seal=artifact(RUN / 'ALL_PREDICTIONS_SEALED.json'),
        review_code=artifact(Path(__file__)), frames=seal['frames'], sources=sources)
    destination = HERE / 'STATE_PUBLICATION_REVIEW.json'
    with destination.open('x', encoding='utf-8', newline='\n') as handle:
        json.dump(value, handle, separators=(',', ':'), allow_nan=False)
        handle.write('\n')
    print(json.dumps(dict(status='PASS', frames=seal['frames'], report=artifact(destination),
        sources={name:dict(frames=s['frames'], parity=s['compared_with_Z4Q'], events=s['event_counts'])
            for name, s in sources.items()}), separators=(',', ':')))


if __name__ == '__main__':
    main()
