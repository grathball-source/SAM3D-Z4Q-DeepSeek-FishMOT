"""End-to-end deterministic engineering checks. No API and no real-effect claims."""
from __future__ import annotations

import copy
import hashlib
import importlib
import json
import sys
from pathlib import Path

from bridge import P, read, save, sha
from policy import compile_view, state_for
from runner import (EpisodeBook, RepairedRunner, context_fingerprint, episode_key,
                    fixture_response)
from scoring import evaluate_transaction, full_timeline_harm_audit, sustained_recovery


def obj(n, z=700., x=0., neighbors=(), area=400, presence=.95):
    return dict(id=n, mask=f'n:{n}', box=[x, 0., x+20., 20.], area=area,
                score_birth=.95, presence=presence, neighbors=list(neighbors),
                depth=dict(n=400, valid_fraction=1., median=z, mad=2.))


def profiles(frame, row):
    result = {}
    for o in row:
        whole = dict(o['depth'], area=o['area'])
        core = dict(o['depth'], area=100, n=min(100, o['depth']['n']))
        result[o['id']] = dict(frame=frame, id=o['id'], mask=o['mask'], whole=whole, core=core)
    return result


def record(frame, row, now=None):
    return dict(frame=frame, global_frame=10000+frame, time=frame/30 if now is None else now,
                observations=row, native=[dict(id=o['id'], mask=o['mask']) for o in row])


def seed(runner, contact=True):
    for frame in range(1, 21):
        row = [obj(1), obj(2, 850., 40.)]
        runner.step(record(frame, row), profiles(frame, row))
    row = ([obj(1, 700., 0, [2]), obj(2, 850., 40., [1])] if contact
           else [obj(1), obj(2, 850., 40.)])
    runner.step(record(21, row), profiles(21, row))


def legal_single_reconnect(config):
    runner = RepairedRunner(config, 'B2', fixture_response)
    seed(runner)
    rows = []
    for frame in range(22, 28):
        row = [obj(9, 900., 3.), obj(2, 850., 40.)]
        ids, _, item = runner.step(record(frame, row), profiles(frame, row))
        rows.append(item)
    assert rows[0]['status'] == 'FIRST_CONFIRMATION'
    assert all(x['status'] == 'WAIT_NEW_OBSERVATION' for x in rows[1:5])
    assert rows[-1]['status'] == 'COMMIT' and rows[-1]['committed'] == {9: 1}
    assert rows[0]['response_kind'] == rows[-1]['response_kind'] == 'ENGINEERING_FIXTURE'
    assert ids == {9: 1, 2: 2}
    # The next frame reads the committed branch state.
    row = [obj(9, 900., 3.), obj(2, 850., 40.)]
    ids, _, follow = runner.step(record(28, row), profiles(28, row))
    assert ids == {9: 1, 2: 2}
    return runner, rows, follow


def legal_atomic_swap(config):
    runner = RepairedRunner(config, 'B2', fixture_response)
    seed(runner, contact=False)
    rows = []
    for frame in range(22, 28):
        area = 400 if frame == 27 else 1000  # freeze original history until final stage qualification
        row = [obj(1, 850., 40., area=area), obj(2, 700., 0., area=area)]
        ids, _, item = runner.step(record(frame, row), profiles(frame, row))
        rows.append(item)
    assert all(p['kind'] == 'REASSIGN_PAIR' for p in rows[0]['proposals'])
    assert rows[0]['native_trace']['native_return_checks'] == []
    assert rows[-1]['status'] == 'COMMIT' and rows[-1]['committed'] == {1: 2, 2: 1}
    assert ids == {1: 2, 2: 1}
    row = [obj(1, 850., 40.), obj(2, 700.)]
    ids, _, _ = runner.step(record(28, row), profiles(28, row))
    assert ids == {1: 2, 2: 1}
    return rows


def candidate_withdrawal_and_occupancy(config):
    runner = RepairedRunner(config, 'B2', fixture_response)
    seed(runner)
    row = [obj(9, 900., 3.), obj(2, 850., 40.)]
    _, _, first = runner.step(record(22, row), profiles(22, row))
    assert first['status'] == 'FIRST_CONFIRMATION'
    for frame in range(23, 27):
        row = [obj(9, 900., 3.), obj(1, 700.), obj(2, 850., 40.)]
        _, _, item = runner.step(record(frame, row), profiles(frame, row))
        assert item['status'] == 'NO_LEGAL_PROPOSAL'
    row = [obj(9, 900., 3.), obj(2, 850., 40.)]
    _, _, resumed = runner.step(record(27, row), profiles(27, row))
    assert resumed['status'] == 'FIRST_CONFIRMATION' and resumed['committed'] is None
    audit = next(iter(runner.episodes.episodes.values()))
    assert audit.checks == 2 and any(x['reason'] == 'candidate_withdrawn' for x in audit.invalidations)
    return resumed


def episode_invalidation_contract():
    key = ((9,), (1,))
    base = dict(participants=(9,), participant_epochs=((9, 1),), target_owners=((1, None),),
                reference_attribution=((1, (1, 1)),), candidate_signatures=(((9, 1),),))
    proposal = dict(changes={9: 1})
    book = EpisodeBook()
    book.synchronize({key: base}, 10)
    assert book.check_permission(key, 10) == (True, 'CHECK_ALLOWED')
    assert not book.record(key, 10, base, proposal)[0]
    assert book.check_permission(key, 10) == (False, 'SAME_FRAME_NOT_NEW_OBSERVATION')
    changed = copy.deepcopy(base); changed['target_owners'] = ((1, 7),)
    book.synchronize({key: changed}, 11)
    assert book.episodes[key].confirmation is None and book.episodes[key].checks == 1
    changed2 = copy.deepcopy(changed); changed2['reference_attribution'] = ((1, (1, 8)),)
    book.episodes[key].confirmation = dict(frame=11, signature=((9, 1),), fingerprint=changed)
    book.synchronize({key: changed2}, 12)
    assert book.episodes[key].confirmation is None and book.episodes[key].checks == 1
    changed3 = copy.deepcopy(changed2); changed3['participant_epochs'] = ((9, 2),)
    book.episodes[key].confirmation = dict(frame=12, signature=((9, 1),), fingerprint=changed2)
    book.synchronize({key: changed3}, 13)
    assert book.episodes[key].confirmation is None and book.episodes[key].checks == 1
    # Invalidation never refreshes the three-check budget.
    assert book.check_permission(key, 15)[0]
    book.record(key, 15, changed3, proposal)
    book.synchronize({}, 16)
    book.synchronize({key: changed3}, 20)
    assert book.check_permission(key, 20)[0]
    assert book.check_permission(key, 25) == (False, 'EPISODE_SEALED')
    reasons = [x['reason'] for x in book.episodes[key].invalidations]
    assert {'target_occupancy_changed','reference_attribution_changed','participant_epoch_changed','candidate_withdrawn'} <= set(reasons)
    return book.audit()


def native_return(config):
    runner, _, _ = legal_single_reconnect(config)
    row = [obj(9, 900., 3.), obj(1, 700.), obj(2, 850., 40.)]
    ids, trace, item = runner.step(record(29, row), profiles(29, row))
    assert ids[1] == 1 and ids[9] == 9 and 9 not in runner.bridge.provenance
    assert any(x['native_id'] == 1 and x['qualified'] for x in trace['native_return_checks'])
    return item


def input_contract(config):
    runner = RepairedRunner(config, 'B2', fixture_response)
    seed(runner, contact=False)
    row = [obj(1, 850., 40., area=1000), obj(2, 700., area=1000)]
    view = runner.bridge.preview(22, 22/30, row, profiles(22, row))
    compiled = compile_view(runner.bridge, view)
    assert compiled['proposals'][0]['kind'] == 'REASSIGN_PAIR'
    # RETURN_RESOLUTION requires an actual involved native-return trace.
    altered = copy.deepcopy(view)
    altered['trace']['native_return_checks'] = [dict(native_id=1, incumbent_native=2, public_id=1, qualified=False)]
    assert compile_view(runner.bridge, altered)['proposals'][0]['kind'] == 'RETURN_RESOLUTION'
    # Late reserved support changes the claim and is model-readable with both references.
    normal_row = [obj(1, 700.), obj(2, 850., 40.)]
    supported = runner.bridge.preview(22, 22/30, normal_row, profiles(22, normal_row))
    supported['trace']['edges'] = [dict(native_id=1, canonical_id=1, old_anchor=runner.bridge.engine.bank[1]['anchor'],
        rejection=None, cost=.1, history_depth=700., current_depth=700., residual_mm=0., tolerance_mm=60.,
        partner_margin_mm=20., required_partner_margin_mm=10., alternatives=[],
        reserved_partners=[dict(id=2, basis='native_continuity_plus_depth_compatibility',
                                own_history_depth=850., current_depth=850., candidate_residual_mm=150.)])]
    c = compile_view(runner.bridge, supported)
    assert c['claims'][2]['status'] == 'SUPPORTED_CURRENT'
    state = state_for(runner.bridge, supported, c)
    partner = state['native_decision_provenance'][0]['reserved_partners'][0]
    assert partner['identity'] and partner['observation'] and partner['basis'] == 'native_continuity_plus_depth_compatibility'
    return dict(ordinary_swap='REASSIGN_PAIR', real_return='RETURN_RESOLUTION', reserved_support=partner)


def scoring_contract():
    gt = {1:{1:'A'}, 2:{9:'A'}, 3:{9:'A'}, 4:{9:'A'}, 5:{9:'A'}}
    fixed = {'A':1, 'B':2}
    local_anchor_but_wrong_public = dict(frame=2, changes={9:2}, displaced=[9], anchors={9:dict(frame=1,native_id=1)})
    verdict = evaluate_transaction(local_anchor_but_wrong_public, gt, fixed)
    assert verdict['edges'][0]['anchor_consistent'] is True
    assert verdict['edges'][0]['target_public_correct'] is False and verdict['verdict'] == 'wrong'
    unscorable = evaluate_transaction(dict(frame=2,changes={9:1},displaced=[9],anchors={9:dict(frame=1,native_id=7)}),gt,fixed)
    assert unscorable['verdict'] == 'unscorable'
    b0={f:{9:1} for f in range(2,42)};branch=copy.deepcopy(b0);branch[20][9]=2
    gt_long={f:{9:'A'} for f in range(2,42)}
    harm=full_timeline_harm_audit(b0,branch,gt_long,fixed)
    assert harm['harms']==[dict(frame=20,native=9,gt='A',expected=1,B0=1,branch=2)]
    sustained=sustained_recovery(2,'A',1,branch,gt_long,horizon=40,minimum=30)
    assert not sustained['stable'] and sustained['errors']
    return dict(wrong_public=verdict, unscorable=unscorable, harm=harm, sustained=sustained)


def imported_modules():
    modules = [importlib.import_module(x) for x in ['bridge','policy','runner','scoring']]
    result = {}
    for module in modules:
        path = Path(module.__file__).resolve()
        assert path.parent == P.resolve(), (module.__name__, path)
        result[module.__name__] = dict(file=str(path), sha256=sha(path))
    assert Path(sys.modules['controller_return'].__file__).resolve().is_relative_to((P/'source').resolve())
    result['controller_return'] = dict(file=str(Path(sys.modules['controller_return'].__file__).resolve()),
                                       sha256=sha(sys.modules['controller_return'].__file__))
    return result


def main():
    config = read(P/'CONFIG.json')
    single, single_rows, follow = legal_single_reconnect(config)
    swap_rows = legal_atomic_swap(config)
    withdrawal = candidate_withdrawal_and_occupancy(config)
    episodes = episode_invalidation_contract()
    returned = native_return(config)
    contract = input_contract(config)
    scoring = scoring_contract()
    imports = imported_modules()
    result = dict(
        status='PASS_ENGINEERING_FIXTURES',
        evidence_class='ENGINEERING_FIXTURE',
        API_calls=0,
        checks=[
            'legal_single_reconnect_full_runner_chain', 'legal_atomic_swap_full_runner_chain',
            'two_new_observations_five_frames_apart', 'same_frame_not_confirmation',
            'candidate_withdrawal_clears_confirmation', 'target_occupancy_change_clears_confirmation',
            'reference_attribution_change_clears_confirmation', 'participant_epoch_change_clears_confirmation',
            'invalidation_does_not_refresh_three_check_budget', 'ordinary_measurement_does_not_change_epoch',
            'qualified_native_return', 'ordinary_swap_vs_real_return_classification',
            'late_reserved_partner_claim_and_model_references', 'anchor_consistency_and_public_identity_both_scored',
            'unscorable_transaction_separate', 'full_timeline_harm_not_filtered',
            'sustained_recovery_rejects_intermediate_wrong_occupancy', 'local_import_paths_and_hashes'
        ],
        single_commit=single_rows[-1], swap_commit=swap_rows[-1], withdrawal=withdrawal,
        episode_audit=episodes, native_return=returned, input_contract=contract,
        scoring=scoring, imported_modules=imports,
    )
    save(P/'END_TO_END_FIXTURE_RESULTS.json', result)
    print(result['status'], len(result['checks']), 'checks')


if __name__ == '__main__':
    main()
