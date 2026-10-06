"""Independent actual-engine checks of the three already identified state repairs."""
import copy
import json
from datetime import datetime, timezone

from common import HERE, artifact, write_new
from checks_state import prepare, advance, packet, observation
from transaction import bridge_hash


def joint():
    branch, manager, assignments = prepare()
    advance(branch, manager, assignments, 8)
    advance(branch, manager, assignments, 9)
    row, profiles, assigned = packet(10, [observation(1), observation(3, 25, 1400.), observation(8, 70, 1700.)])
    assignments[10] = assigned
    manager.before(row, profiles)
    view = branch.preview(10, 1., row['observations'], profiles)
    tx, error = branch.stage_group_restore(view, manager.active, {1:2, 3:1})
    assert error is None
    branch.commit_once(view, tx)
    return branch


def step(branch, frame, objects):
    row, profiles, _ = packet(frame, objects)
    prior = bridge_hash(branch)
    view = branch.preview(frame, row['time'], objects, profiles)
    assert bridge_hash(branch) == prior, 'Preview modified authoritative state'
    ids, trace = branch.commit_once(view)
    assert len(ids) == len(set(ids.values()))
    return ids, trace


def owner_competition():
    branch = joint()
    for frame in (11, 12):
        step(branch, frame, [observation(1), observation(3, 25, 1400.), observation(8, 70, 1700.)])
    reconnects = []
    for frame in range(13, 18):
        ids, trace = step(branch, frame, [observation(4, z=1000.), observation(3, 25, 1400.), observation(8, 70, 1700.)])
        reconnects.extend(dict(event, frame=frame) for event in trace['events']
                          if event.get('kind') == 'reconnect' and event.get('native_id') == 4)
    accepted = [event for event in reconnects if event.get('accepted')]
    assert len(accepted) == 1 and accepted[0]['frame'] == 17
    assert accepted[0]['canonical_id'] == 2 and accepted[0]['confirmations'] == 5
    assert accepted[0]['cost'] == 0 and accepted[0].get('phase') != 'birth'
    assert branch.engine.alias[4]['target'] == 2
    outside = copy.deepcopy(branch.engine.alias[8])
    ids, trace = step(branch, 18, [observation(1), observation(4, z=1000.), observation(3, 25, 1400.), observation(8, 70, 1700.)])
    assert ids[4] == 2 and ids[8] == 7
    assert branch.engine.alias[8] == outside
    assert branch.engine.alias[4]['target'] == 2, 'Original accepted D1 alias was explicitly removed'
    cascade = trace['ds34_event_return_cascade']
    assert not cascade['actual_qualified_returns']
    assert cascade['event_aliases_revoked'] == [3]
    assert not cascade['bank_copied'] and not cascade['future_read']
    return dict(accepted_original_D1=reconnects, first_owner_return_frame=18,
                original_native2_absent=True, actual_mapping=ids, cascade=cascade,
                outside_original_alias_preserved=True)


def canonical_return():
    branch = joint()
    for frame in (11, 12):
        step(branch, frame, [observation(1), observation(3, 25, 1400.), observation(8, 70, 1700.)])
    row, profiles, _ = packet(13, [observation(1), observation(2, 25, 1400., area=0), observation(3, 25, 1400.), observation(8, 70, 1700.)])
    before = bridge_hash(branch)
    view = branch.preview(13, 1.3, row['observations'], profiles)
    assert bridge_hash(branch) == before
    assert view['mapping'] == {1:2, 2:-3, 3:1, 8:7}
    assert 'ds34_event_return_cascade' not in view['trace']
    ids, trace = step(branch, 13, [observation(1), observation(2, 25, 1400.), observation(3, 25, 1400.), observation(8, 70, 1700.)])
    assert ids == {1:1, 2:2, 3:3, 8:7}
    return dict(unqualified_mapping=view['mapping'], original_quarantine_unchanged=True,
                qualified_mapping=ids, cascade=trace['ds34_event_return_cascade'])


def qualified_continuity():
    branch, manager, assignments = prepare()
    advance(branch, manager, assignments, 8)
    advance(branch, manager, assignments, 9, [observation(3, width=30), observation(2, 25, 1400., area=0), observation(8, 70, 1700.)])
    branch.engine.alias[99] = dict(target=2, anchor=copy.deepcopy(branch.engine.bank[2]['anchor']), commit_frame=9)
    bank = copy.deepcopy(branch.engine.bank[1])
    outside = {n:copy.deepcopy(branch.engine.alias[n]) for n in (8, 99)}
    row, profiles, assigned = packet(10, [observation(3), observation(4, 25, 1400.), observation(8, 70, 1700.)])
    assignments[10] = assigned
    manager.before(row, profiles)
    before = bridge_hash(branch)
    view = branch.preview(10, 1., row['observations'], profiles)
    tx, detail = branch.local_fallback(view, manager.active)
    assert detail['status'] == 'LOCAL_FALLBACK_UNRESOLVED'
    assert bridge_hash(branch) == before and tx['engine'].bank[1] == bank
    ids, _ = branch.commit_once(view, tx)
    assert ids == {8:7, 3:1, 4:4}
    alias = copy.deepcopy(branch.engine.alias[3])
    assert alias['target'] == 1 and alias['anchor'] == bank['anchor']
    assert {n:branch.engine.alias[n] for n in (8, 99)} == outside
    later, _ = step(branch, 11, [observation(3), observation(4, 25, 1400.), observation(8, 70, 1700.)])
    assert later == ids and {n:branch.engine.alias[n] for n in (8, 99)} == outside
    return dict(first_q_frame=10, next_frame=11, first_mapping=ids, next_mapping=later,
                actual_alias3=alias, unchanged_original_bank1_at_q=True,
                authoritative_state_unchanged_by_stage=True,
                outside_aliases8_to7_and99_to2_preserved_at_q_and_next=True)


def main():
    for name in ('NATIVE_RETURN_CASCADE_REVIEW_READY.json', 'QUALIFIED_CONTINUITY_REVIEW_CASCADE_READY.json'):
        assert not (HERE/name).exists(), 'Receipt is append-only'
    assert not (HERE/'RUNTIME_FREEZE.json').exists()
    owner = owner_competition()
    canonical = canonical_return()
    qualified = qualified_continuity()
    shared = dict(status='PASS', engineering_only=True, synthetic_only=True,
                  created_utc=datetime.now(timezone.utc).isoformat(),
                  transaction=artifact(HERE/'transaction.py'), checker=artifact(__file__),
                  science_code_modified=False, physical_identity_accuracy='UNKNOWN',
                  GT_opened=False, new_model_http=0, cost_usd=0)
    write_new(HERE/'NATIVE_RETURN_CASCADE_REVIEW_READY.json', dict(shared,
        schema='DS34_CURRENT_ORIGINAL_CONFLICT_INDEPENDENT_REVIEW_V1',
        scope='Only already reproduced current-frame event-related original-conflict cascades; no performance qualification.',
        return_after_publication_checked=True,
        correction='Current original single-pass conflict produces a duplicate inside an actual DS34 alias component; revoke only necessary DS34 aliases, then retain original arbitration and quarantine.',
        original_D1_owner_competition=owner, canonical_native_return=canonical))
    write_new(HERE/'QUALIFIED_CONTINUITY_REVIEW_CASCADE_READY.json', dict(shared,
        schema='DS34_QUALIFIED_CONTINUITY_INDEPENDENT_REVIEW_READY_V1',
        scope='Rechecked actual persistent qualified local fallback on the final current engine; no identity accuracy claim.',
        **qualified))
    print(json.dumps(dict(status='PASS', outputs=[artifact(HERE/name) for name in
        ('NATIVE_RETURN_CASCADE_REVIEW_READY.json', 'QUALIFIED_CONTINUITY_REVIEW_CASCADE_READY.json')],
        formal_trials_run=False, GT_opened=False)))


if __name__ == '__main__':
    main()
