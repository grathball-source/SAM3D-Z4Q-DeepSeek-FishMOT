"""Postseal audit of real engine effects, separate from persistent publication."""
from common import *
from collections import Counter


def compact(event):
    keys = ('kind', 'accepted', 'native_id', 'canonical_id', 'confirmations',
            'assignment_margin', 'confirmation_span_s', 'old_anchor', 'phase', 'cost')
    return {key: event[key] for key in keys if key in event}


def main():
    from score import verify_all
    verify_all()
    assert read(RUN/'COMPLETE.json')['frames'] == 20098
    totals = {arm: Counter() for arm in VETO_ARMS}
    segments, deletions = {}, []
    for name in SEGMENTS:
        p = RUN/name/'public'
        counters = {arm: Counter() for arm in VETO_ARMS}
        tx = iter(rows(p/'TRANSACTIONS.jsonl.gz'))
        for ledger in rows(p/'PUBLISH_LEDGER.jsonl'):
            original = next(tx)
            assert (original['frame'], original['arm']) == (ledger['frame'], ARMS[1])
            assert row_sha(original) == ledger['transaction_row_sha256'][ARMS[1]]
            for arm in VETO_ARMS:
                actual = next(tx)
                assert (actual['frame'], actual['arm']) == (ledger['frame'], arm)
                assert row_sha(actual) == ledger['transaction_row_sha256'][arm]
                changed = actual['engine_state_sha256'] != actual['original_own_state_sha256']
                counters[arm]['frames'] += 1
                counters[arm]['same_prior_engine_hash_changed_frames'] += changed
                counters[arm]['independent_Z4Q_engine_hash_changed_frames'] += (
                    actual['engine_state_sha256'] != original['engine_state_sha256'])
                counters[arm]['same_prior_public_mapping_changed_frames'] += (
                    actual['mapping'] != actual['original_own_state_mapping'])
                counters[arm]['independent_Z4Q_public_mapping_changed_frames'] += (
                    actual['mapping'] != original['mapping'])
                own_events = [compact(e) for e in actual['original_own_state_trace']['events']]
                actual_events = [compact(e) for e in actual['controller_trace']['events']]
                counters[arm]['same_prior_proposal_or_event_trace_changed_frames'] += own_events != actual_events
                removed = [e for e in own_events if e not in actual_events]
                for check in actual['controller_trace']['depth_checks']:
                    if not check['veto']:
                        continue
                    match = lambda e: (e.get('native_id'), e.get('canonical_id')) == (
                        check['native_id'], check['canonical_id'])
                    deletions.append(dict(
                        segment=name, arm=arm, frame=actual['frame'], global_frame=actual['global_frame'],
                        phase=check['phase'], native=check['native_id'], target=check['canonical_id'],
                        anchor=check['anchor'], original_legal_cost=check['terms']['cost'],
                        residual_mm=check['residual_mm'], threshold_mm=check['threshold'],
                        source_fact_ids=[s['fact_id'] for s in check['samples']],
                        current_fact_id=check['current']['fact_id'],
                        same_prior_engine_hash_changed=changed,
                        own_original_engine_sha256=actual['original_own_state_sha256'],
                        actual_engine_sha256=actual['engine_state_sha256'],
                        mapping_unchanged=actual['mapping'] == actual['original_own_state_mapping'],
                        original_same_prior_proposals=[e for e in own_events if match(e)],
                        original_independent_proposals=[compact(e) for e in original['controller_trace']['events'] if match(e)],
                        actual_proposals=[e for e in actual_events if match(e)],
                        removed_same_prior_proposals=[e for e in removed if match(e)],
                        transaction_row_sha256=row_sha(actual), prediction_ledger_row_sha256=row_sha(ledger),
                        engine_hash_includes_original_pending_and_diagnostic_counters=True,
                        fieldwise_after_engine_snapshot_not_serialized=True))
        assert next(tx, None) is None
        segments[name] = {a: dict(counters[a]) for a in VETO_ARMS}
        for arm in VETO_ARMS:
            totals[arm].update(counters[arm])
    write_new(HERE/'STATE_EFFECT_REVIEW.json', dict(
        status='PASS_ENGINE_STATE_PROPOSAL_COMMIT_AND_PUBLICATION_EFFECTS_SEPARATED',
        totals={a: dict(totals[a]) for a in VETO_ARMS}, segments=segments,
        real_legal_deletions=deletions, result_only_code=artifact(__file__),
        inference_score_and_seal_bytes_unchanged=True, model_http=0, cost_usd=0))
    print(json.dumps({a: dict(totals[a]) for a in VETO_ARMS}), flush=True)


if __name__ == '__main__':
    main()
