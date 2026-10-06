"""Postseal failure tracing only; never writes predictions or tracking state."""
from collections import Counter
import copy
from common import *
from post_visuals import private_case, phases, selected_rows

ARM = 'EVENT_RGBD'
SOURCES = ('fishsa_development_8400', 'fishsa_validation_2888')


def mapping(prediction, arm):
    return {int(o['mask'][2:]): o['id'] for o in prediction['variants'][arm]}


def compact_action(action):
    keys = ('kind', 'accepted', 'native_id', 'canonical_id', 'phase', 'old_anchor',
            'source', 'cost', 'failures', 'survivor_witnesses', 'confirmations',
            'actual_qualified_return_natives', 'already_published_history_rewritten')
    return {k: action[k] for k in keys if k in action}


def compact_transaction(value):
    trace = value['controller_trace']
    return dict(arm=value['arm'], frame=value['frame'], global_frame=value['global_frame'],
        mapping=value['mapping'], actual_aliases=value['actual_aliases'],
        actual_epochs=value['actual_epochs'], actual_provenance=value['actual_provenance'],
        bank_anchors=value['bank_anchors'], version=value['version'],
        engine_state_sha256=value['engine_state_sha256'], full_state_sha256=value['full_state_sha256'],
        transaction_row_sha256=row_sha(value),
        actual_actions=[compact_action(a) for a in value['actual_actions']],
        conflict_actions=[compact_action(a) for a in trace.get('events', [])
                          if a.get('kind') in ('native_conflict_rollback', 'native_return')],
        event_write_set={k: trace[k] for k in ('merge_split_local_fallback', 'ds34_group_restore',
            'ds34_local_release', 'ds34_event_return_cascade') if k in trace})


def analyze_source(name):
    public = RUN / name / 'public'
    metric = read(public / 'METRICS.json')
    assert metric['segment'] == name and metric['no_mask_or_ID_exclusion']
    events = read(public / 'EVENTS.json')
    audit = read(public / 'EVENT_AUDIT.json')
    predictions = list(rows(public / 'predictions.jsonl.gz'))
    assert len(predictions) == metric['frames']
    matches = {r['frame']: r['matches'] for r in rows(public / 'REFERENCE_MATCHES.jsonl.gz')}
    assert len(matches) == len(predictions)
    active, runs, totals = {}, [], Counter()
    for pred in predictions:
        f = pred['frame']
        base, current = mapping(pred, 'Z4Q_FROZEN'), mapping(pred, ARM)
        assert set(base) == set(current) == set(mapping(pred, 'SAM3_NATIVE'))
        assert len(current) == len(set(current.values()))
        assert pred['variants']['EVENT_RGB'] == pred['variants']['EVENT_RGBD']
        different = {(n, base[n], k) for n, k in current.items() if base[n] != k}
        for key in set(active) - different:
            begin = active.pop(key)
            runs.append(dict(native=key[0], Z4Q_public=key[1], event_public=key[2],
                start=begin, end=f - 1, frames=f - begin))
        for key in different:
            active.setdefault(key, f)
            totals[key] += 1
    for key, begin in active.items():
        runs.append(dict(native=key[0], Z4Q_public=key[1], event_public=key[2],
            start=begin, end=f, frames=f - begin + 1))
    runs.sort(key=lambda r: (-r['frames'], r['start'], r['native']))
    return dict(name=name, public=public, metric=metric, events=events, audit=audit,
        predictions=predictions, matches=matches, runs=runs,
        differing_source_frame_counts=[dict(native=n, Z4Q_public=b, event_public=c, frames=v)
                                      for (n, b, c), v in totals.most_common()])


def case_record(source, event, selection, chain=None):
    name, public = source['name'], source['public']
    q, cutoff = event['q'], event['decision_cutoff']
    assert q is not None and q <= cutoff <= q + 30
    audit = next(a for a in source['audit']['event_arms'][ARM] if a['event'] == event['id'])
    important = {f for _, f in phases(event) if f is not None} | {q - 1, q + 1}
    if chain:
        important.update((chain['start'], chain['end']))
    transactions = {}
    for tx in rows(public / 'TRANSACTIONS.jsonl.gz'):
        if tx['frame'] in important:
            transactions.setdefault(tx['frame'], {})[tx['arm']] = compact_transaction(tx)
    selected_prediction = {f: source['predictions'][f - 1] for f in important}
    ledgers = selected_rows(public / 'PUBLISH_LEDGER.jsonl', important)
    selected_matches = {f: source['matches'][f] for f in important}
    for f in important:
        for arm in ARMS[1:]:
            assert {int(n): k for n, k in transactions[f][arm]['mapping'].items()} == mapping(selected_prediction[f], arm)
            assert transactions[f][arm]['transaction_row_sha256'] == ledgers[f]['transaction_row_sha256'][arm]
        assert row_sha(selected_prediction[f]) == ledgers[f]['prediction_row_sha256']
    qstate = transactions[q][ARM]
    assert qstate['version'] == q
    assert mapping(selected_prediction[q], ARM) == {int(n): k for n, k in event['first_published_mapping'].items()}
    assert ledgers[q]['first_publish_at_arrival_frame'] == event['first_publish_at_arrival_frame']
    assert event['lag_resolution']['replay_state_sha256'][0]['sha256'] == qstate['full_state_sha256']
    for arm in ARMS[2:]:
        peer = next(e for e in source['events'][arm] if e['id'] == event['id'])
        assert peer['first_published_mapping'] == event['first_published_mapping']
        assert peer['q'] == q and peer['decision_cutoff'] == cutoff
    d = event['joint_decision']
    compact_scores = []
    for candidate in d.get('scores', []):
        edges = []
        for edge in candidate['edges']:
            contours = edge['contour_samples']
            edges.append(dict(role=edge['role'], native=edge['native'], public=edge['public'],
                geometry=edge['geometry'], geometry_samples=edge['geometry_samples'],
                contour_cost=edge['contour_cost'], depth_cost=edge['depth_cost'],
                contour_pair_rows=len(contours), contour_available_rows=sum(bool(c['available']) for c in contours),
                contour_measurements=[{k: c[k] for k in ('available', 'status', 'symmetric_dice',
                    'forward_reliable_area', 'backward_reliable_area', 'forward_reliable_fraction',
                    'backward_reliable_fraction') if k in c} for c in contours], depth_rows=edge['depth_rows']))
        compact_scores.append(dict(choice=candidate['choice'], score=candidate['score'], mapping=candidate['mapping'], edges=edges))
    match_counts = None
    if chain:
        match_counts = dict(Counter(source['matches'][f].get(str(chain['native']), {}).get('gt_id', 'UNKNOWN')
                                    for f in range(chain['start'], chain['end'] + 1)))
        assert chain['start'] == q
        assert mapping(selected_prediction[q], 'Z4Q_FROZEN')[chain['native']] == chain['Z4Q_public']
        assert mapping(selected_prediction[q], ARM)[chain['native']] == chain['event_public']
    original_actions = [a for a in transactions[q]['Z4Q_FROZEN']['actual_actions']
                        if a.get('native_id') in set(map(int, event['post_roles']))]
    added_switches = read(public / 'SWITCH_CHANGES.json')['Z4Q_FROZEN_TO_' + ARM]
    start = SEGMENTS[name][0]
    affected = set(map(int, event['post_roles']))
    relevant_switches = {kind: [r for r in added_switches[kind]
        if r['native_id'] in affected and q <= r['frame'] - start + 1 <= (chain['end'] if chain else source['metric']['frames'])]
        for kind in ('occurrence_added', 'occurrence_eliminated')}
    pre = {role: dict(status=v['status'], public=v['public'], anchor=v.get('anchor'),
        version=v.get('version'), sample_frames=[s['frame'] for s in v.get('samples', [])])
        for role, v in event['joint_pre'].items()}
    return dict(segment=name, event_id=event['id'], arm=ARM, selection=selection,
        selected_after_prediction_seal_and_independent_score=True, diagnostic_case_not_new_experiment=True,
        suspect_frame=event['suspect_frame'], q=q, q_global_frame=start + q - 1,
        cutoff=cutoff, first_publish_at_arrival_frame=event['first_publish_at_arrival_frame'],
        decision_delay_frames=cutoff-q, publication_delay_frames=event['first_publish_at_arrival_frame']-q,
        status=event['status'], restored=bool(event['restore']['staged']), restore=event['restore'],
        raw_choice=d['choice'], reason=d['reason'], common_weights=d.get('common_weights'),
        winning_margin=d.get('winning_margin'), scores=compact_scores, pre=pre,
        frozen_bank_summary={str(k): {f: v.get(f) for f in ('anchor', 'last_frame', 'clean_count', 'clean_time')}
                             for k, v in event['bank_snapshot'].items()},
        post_confirm_frames={str(n): [s['frame'] for s in values] for n, values in event.get('confirmed_post_roles', {}).items()},
        longest_unchanged_mapping_difference_run=chain, chain_source_unique_match_counts=match_counts,
        original_q_recoveries=original_actions, physical_audit=audit, relevant_switch_occurrences=relevant_switches,
        actual_phase_frames=phases(event), selected_source_transactions=transactions,
        selected_first_publications={f: dict(frame=f, mappings={arm: mapping(p, arm) for arm in ARMS},
            ledger=ledgers[f], source_matches=selected_matches[f]) for f, p in selected_prediction.items()},
        lag_resolution=event['lag_resolution'],
        source_artifacts={file: artifact(public/file) for file in ('METRICS.json', 'EVENTS.json', 'EVENT_AUDIT.json',
            'SWITCHES.json', 'SWITCH_CHANGES.json', 'REFERENCE_MATCHES.jsonl.gz', 'TRANSACTIONS.jsonl.gz',
            'predictions.jsonl.gz', 'PUBLISH_LEDGER.jsonl', 'PREDICTIONS_SEALED.json')})


def main():
    seal = read(RUN/'ALL_PREDICTIONS_SEALED.json')
    checked = read(RUN/'SCORING_FREEZE.json')
    assert seal['status'] == 'ALL_PREDICTIONS_AND_ACCESS_SEALED'
    assert checked['status'] == 'ALL_PREDICTION_INPUT_ACCESS_AND_PUBLICATION_BINDINGS_VERIFIED'
    verify_item(checked['all_seal'])
    data = {name: analyze_source(name) for name in SOURCES}
    cases, visual_cases = [], []
    for name in SOURCES:
        source = data[name]
        chain = source['runs'][0]
        event = next(e for e in source['events'][ARM] if e.get('q') == chain['start'] and
            chain['native'] in set(map(int, e['post_roles'])))
        assert not event['restore']['staged']
        record = case_record(source, event, 'POSTHOC_LONGEST_CONTIGUOUS_POSITIVE_PUBLIC_DIFFERENCE_RUN_VS_Z4Q', chain)
        record['causal_boundary'] = 'Direct event-local q fallback writes the differing mapping and actual alias state; later rows show persistence. No new ALLOW/VETO counterfactual or exact per-event IDF1 attribution was run.'
        cases.append(record);visual_cases.append((name,event))
    val = data['fishsa_validation_2888']
    wrong = [a for a in val['audit']['event_arms'][ARM] if a['staged'] and
             a['physical_preanchor'] == 'WRONG' and a['physical_prefragment'] == 'WRONG']
    chosen = min(wrong, key=lambda a: a['q'])
    event = next(e for e in val['events'][ARM] if e['id'] == chosen['event'])
    record = case_record(val, event, 'POSTHOC_EARLIEST_STAGED_WRONG_PREANCHOR_AND_PREFRAGMENT_IN_VALIDATION')
    assert record['common_weights'] == dict(motion=0.0, contour=0.0, depth=0.0)
    assert record['selected_source_transactions'][record['q']][ARM]['event_write_set']['ds34_group_restore']['selected'] == event['joint_decision']['mapping']
    record['causal_boundary'] = 'Actual joint q stage installs both swapped aliases; independent fixed endpoint audit is WRONG. All motion/contour/depth weights are zero, so this is a geometry-only erroneous stage, not an adverse depth decision.'
    cases.append(record);visual_cases.append((val['name'],event))
    result = dict(status='POSTSEAL_FAILURE_TRACE_COMPLETE', reporting_only=True,
        prediction_or_score_mutation=False, new_model_http=0, cost_usd=0,
        all_seals=artifact(RUN/'ALL_PREDICTIONS_SEALED.json'), scoring_freeze=artifact(RUN/'SCORING_FREEZE.json'),
        analysis_code=artifact(HERE/'postseal_extra_visuals.py'), frozen_transaction=artifact(HERE/'transaction.py'),
        frozen_visual_helper=artifact(HERE/'post_visuals.py'),
        sources={name:dict(metrics=v['metric'], longest_mapping_difference_runs=v['runs'][:20],
            differing_source_frame_counts=v['differing_source_frame_counts'], EVENT_RGB_equals_EVENT_RGBD_all_frames=True)
                 for name,v in data.items()}, cases=cases,
        boundaries=['Public integers are not physical GT IDs.', 'Fallback UNSCORABLE remains UNSCORABLE.',
            'Long mapping difference duration is not an official error count or per-event IDF1 decomposition.',
            'A lost correct Z4Q recovery fragments identity without requiring more IDSW.',
            'Static protection/fallback flow suggests interference with original birth recovery; exact missing candidate-edge reason is UNKNOWN because fallback candidate checks were not sealed.',
            'Case selection uses postseal failures only for diagnosis and did not alter any trial input or decision.'])
    write_new(HERE/'POSTSEAL_FAILURE_CASES.json', result)
    destination = HERE/'private/postseal_extra_cases'
    destination.mkdir(parents=True, exist_ok=False)
    pictures = []
    for name,event in visual_cases:
        value = private_case(name,event,ARM,destination)
        value['selection'] = next(c['selection'] for c in cases if c['segment']==name and c['event_id']==event['id'])
        value['postseal_diagnostic_selection_only'] = True
        pictures.append(value)
    write_new(HERE/'POSTSEAL_EXTRA_PRIVATE_VISUALS.json', dict(status='POSTSEAL_PRIVATE_ACTUAL_SOURCE_CASES',
        images_are_private=True, public_pixel_release=False, no_GT_raster_or_annotation_reader=True,
        uses_only_already_scored_numeric_reference_matches=True, analysis=artifact(HERE/'POSTSEAL_FAILURE_CASES.json'),
        images=pictures, reproduction='Run postseal_extra_visuals.py once after the same all-source SCORING_FREEZE and independent scores; original RGB/raw depth and immutable saved masks required.'))
    print(json.dumps(dict(status=result['status'], cases=len(cases), private_images=len(pictures),
        longest_mapping_difference_frames=[c['longest_unchanged_mapping_difference_run']['frames'] for c in cases if c['longest_unchanged_mapping_difference_run']],
        new_model_http=0, cost_usd=0)))


if __name__ == '__main__':
    main()
