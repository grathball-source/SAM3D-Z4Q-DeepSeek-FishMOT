"""Official same-source scoring only after every prediction/input/access seal."""
from common import *
from collections import Counter
import time
from bridge import stream

_saved_common = sys.modules['common']
try:
    sys.modules['common'] = old
    ref = module('ds33_official_ds20_adapter', ROOT / 'experiments/ds20_pending_confirmation_isolation/score.py')
finally:
    sys.modules['common'] = _saved_common
metrics, rle = ref.metrics, ref.rle
polygon_reference, unique_matches, clear_step, same = ref.polygon_reference, ref.unique_matches, ref.clear_step, ref.same
np, coco, FIELDS = ref.np, ref.coco, ref.FIELDS
STATE_ARMS = ARMS[1:]
EVENT_ARMS = ARMS[2:]
ARCHIVED = ROOT / 'experiments/ds32_z4q_depth_conflict_veto/run'
DEPTH = module('ds33_score_unchanged_ds31_depth', ROOT / 'experiments/ds31_persistent_identity_depth/depth.py')


def scoring_dependencies():
    """Explicitly pin dynamic adapter, AST math and actual installed metric code."""
    paths = {Path(__file__).resolve(), Path(ref.__file__).resolve(), Path(ref._math.__file__).resolve(),
        DS1 / 'postseal.py', DS1 / 'depth_state.py', Path(DEPTH.__file__).resolve(),
        old.OLD / 'score.py', DS14 / 'finish_scoring.py',
        WORK / 'tools/sam3_i1_validation_20260915/prepare_truth.py'}
    for name, value in tuple(sys.modules.items()):
        path = getattr(value, '__file__', None)
        if path and (name == 'trackeval' or name.startswith('trackeval.metrics')
                or name.startswith('pycocotools') or name == 'scipy.optimize._lsap'):
            paths.add(Path(path).resolve())
    return [artifact(path) for path in sorted(paths, key=str)]


def _mapping(row, arm):
    return {int(o['mask'].split(':')[1]): o['id'] for o in row['variants'][arm]}


def _int_map(value):
    return {int(k): int(v) for k, v in (value or {}).items()}


def _source_array_binding(array):
    header = json.dumps([array.dtype.str, list(array.shape)], separators=(',', ':')).encode()
    return dict(dtype=array.dtype.str, shape=list(array.shape),
        sha256=hashlib.sha256(header + b'\n' + array.tobytes(order='C')).hexdigest())


def verify_frame_contract(name, current, assignment, row, measured, quality, bound, flow, ledger,
                          rgb_pin, previous_sensor, source_metadata):
    """Semantic sensor/flow/fact bindings still matter with self-consistent hashes."""
    frame, global_frame, now = current['frame'], current['global_frame'], current['time']
    assert (row['frame'], row['global_frame'], row['time']) == (frame, global_frame, now)
    for packet in (measured, quality, bound):
        assert (packet['frame'], packet['global_frame'], packet['time']) == (frame, global_frame, now)
    assert measured['segment'] == quality['segment'] == name
    assert bound['source_row_sha256'] == row_sha(row)
    assert bound['assignment_row_sha256'] == row_sha(assignment)
    assert bound['DS18_packet_sha256'] == digest(quality)
    assert ledger['frame_inputs_row_sha256'] == row_sha(bound)
    assert ledger['flow_row_sha256'] == row_sha(flow)
    assert bound['no_future_sensor_lookup'] and bound['maximum_sensor_global_frame'] == global_frame
    sensor = bound['sensor']
    assert sensor['schema'] == 'DS33_SENSOR_FRAME_V1' and sensor['segment'] == name
    assert (sensor['global_frame'], sensor['time']) == (global_frame, now)
    assert sensor['RGB_read'] and not any(sensor[k] for k in ('GT_read', 'annotation_read', 'restored_read'))
    assert sensor['no_future_sensor_lookup'] and sensor['rgb'] == rgb_pin
    for field in ('rgb_timestamp_us', 'depth_timestamp_us', 'delta_us'):
        assert sensor[field] == source_metadata[field]
    assert sensor['rgb']['path'] == source_metadata['rgb_path']
    assert abs(sensor['rgb_timestamp_us'] / 1e6 - now) < 1e-6
    assert sensor['calibration_available'] and sensor['depth_difference_is_motion'] is False
    assert quality['source_binding'] == dict(measured['raw_source_binding'], frame=frame)
    shared = {key:quality[key] for key in ('segment', 'frame', 'global_frame', 'time', 'source_binding',
        'actual_depth_binding', 'actual_source_index_binding', 'native_depth_binding')}
    assert quality['frame_binding_sha256'] == digest(shared)
    for outer, inner, array_name in (('actual_depth_binding', 'aligned_depth', 'depth_mm'),
            ('actual_source_index_binding', 'aligned_source_index', 'source_index'),
            ('native_depth_binding', 'native_depth', 'native_depth')):
        actual = measured['raw_source_binding'][inner]
        assert quality[outer] == sensor[inner] == actual
        # Sensor writes both frozen raw-contract hashes and flow's bare-array hash.
        # Different header conventions are explicit; they must not be compared as one hash.
        bare = sensor['array_bindings'][array_name]
        assert bare['shape'] == actual['shape'] and np.dtype(bare['dtype']) == np.dtype(actual['dtype'])
    masks = {int(o['mask'][2:]):coco.decode(rle(assignment['masks'][o['mask']])).astype(bool)
        for o in assignment['variants']['N0']}
    assert set(masks) == {int(n) for n in quality['objects']} == {o['id'] for o in row['observations']}
    assert bound['current_mask_bindings'] == {str(n):array_hash(mask) for n, mask in masks.items()}
    assert bound['DS18_extracts'] == {n:DEPTH.extract(cert) for n, cert in quality['objects'].items()}
    raw = {int(n):v for n, v in measured['adaptive_raw'].items()}
    for native, cert in quality['objects'].items():
        assert cert['certificate_sha256'] == digest({k:v for k, v in cert.items() if k != 'certificate_sha256'})
        assert (cert['native'], cert['segment'], cert['frame'], cert['global_frame'], cert['time']) == (
            int(native), name, frame, global_frame, now)
        assert cert['frame_binding_sha256'] == quality['frame_binding_sha256']
        assert cert['mask_binding'] == _source_array_binding(masks[int(native)])
        for part in ('whole', 'core'):
            assert cert[part]['inclusive_statistics_sha256'] == digest(cert[part]['inclusive_summary'])
            assert cert[part]['source_quality_denominator'] == 'ORIGINAL_GEOMETRIC_ROI_AREA_INCLUDING_MISSING_SHARED_DUPLICATE_PIXELS'
            for field in ('n', 'area', 'valid_fraction', 'median', 'mad'):
                assert cert[part]['inclusive_summary'][field] == raw[int(native)][part][field]
        assert cert['whole']['roi_binding'] == cert['mask_binding']
        assert cert['core']['roi_binding'] == cert['core_binding']
    assert (flow['frame'], flow['global_frame']) == (frame, global_frame)
    if previous_sensor is None:
        assert frame == 1 and flow['status'] == 'FIRST_FRAME_NO_PREVIOUS_SENSOR' and flow['pair'] is None
    else:
        assert flow['status'] == 'ACTUAL_PAIR_COMPUTED_ONCE_SHARED'
        pair = flow['pair']
        assert pair['current_source_binding'] == sensor and pair['previous_source_binding'] == previous_sensor
        assert pair['previous_frame'] == global_frame - 1 and pair['current_frame'] == pair['maximum_read_global_frame'] == global_frame
        assert pair['current_gray'] == sensor['array_bindings']['gray']
        assert pair['previous_gray'] == previous_sensor['array_bindings']['gray']
        for role, binding in (('previous', previous_sensor), ('current', sensor)):
            assert pair[role + '_rgb_timestamp_us'] == binding['rgb_timestamp_us']
            assert pair[role + '_depth_timestamp_us'] == binding['depth_timestamp_us']
        assert abs(pair['rgb_dt_s'] - (sensor['rgb_timestamp_us'] - previous_sensor['rgb_timestamp_us']) / 1e6) < 1e-12
        if pair['depth_unknown_reasons']:
            assert pair['depth_status'] == 'UNKNOWN'
        else:
            assert pair['depth_status'] == 'AVAILABLE_RAW_SENSOR_PAIR' and pair['depth_dt_s'] > 0
            assert abs(pair['depth_dt_s'] - (sensor['depth_timestamp_us'] - previous_sensor['depth_timestamp_us']) / 1e6) < 1e-12
        if sensor['depth_timestamp_us'] == previous_sensor['depth_timestamp_us']:
            assert pair['depth_status'] == 'UNKNOWN'
        assert pair['physical_surface_identity'] == 'UNKNOWN' and pair['no_depth_completion']
        assert pair['no_ID_or_bank_write'] and pair['no_mean_depth_subtraction_as_flow']
    return sensor


def verify_publications(name):
    """Bind actual final state rows and unchanged controls before any GT access."""
    public = RUN / name / 'public'
    start, stop = SEGMENTS[name]
    original_seal = read(ARCHIVED / name / 'public/PREDICTIONS_SEALED.json')
    original_prediction = ARCHIVED / name / 'public/predictions.jsonl.gz'
    assert sha(original_prediction) == original_seal['artifacts_sha256']['predictions.jsonl.gz']
    tx = iter(rows(public / 'TRANSACTIONS.jsonl.gz'))
    ledgers = iter(rows(public / 'PUBLISH_LEDGER.jsonl'))
    bound_rows = iter(rows(public / 'FRAME_INPUTS_BINDINGS.jsonl.gz'))
    flow_rows = iter(rows(public / 'FLOW.jsonl.gz'))
    source_rows = iter(stream(input_dir(name) / 'observations.jsonl.gz', input_dir(name) / 'profiles.jsonl.gz'))
    measurements = iter(rows(input_dir(name) / 'DEPTH_OBSERVATIONS.jsonl.gz'))
    quality_rows = iter(rows(DS18 / 'run' / name / 'public/MIXED_DEPTH.jsonl.gz'))
    frozen = read(public / 'FREEZE.json')
    rgb_pins = {r['global_frame']:r['rgb'] for r in rows(frozen['rgb_pins']['path']) if r['segment'] == name}
    sensor_metadata = {r['global_frame']:r for s in read(frozen['sensor_audit']['path'])['segments']
        if s['segment'] == name for r in s['metadata']}
    previous_sensor = None
    first_public = {a: {} for a in ARMS}
    count = 0
    for count, (current, prior, assignment) in enumerate(zip(rows(public / 'predictions.jsonl.gz'),
            rows(original_prediction), rows(input_dir(name) / 'assignments.jsonl.gz'), strict=True), 1):
        assert current['frame'] == assignment['frame'] == count
        assert (current['frame'], current['global_frame'], current['time']) == (prior['frame'], prior['global_frame'], prior['time'])
        assert current['global_frame'] == start + count - 1 and current['time'] == assignment['time']
        assert set(current['variants']) == set(ARMS)
        assert current['variants']['SAM3_NATIVE'] == assignment['variants']['N0'] == prior['variants']['SAM3_NATIVE']
        assert current['variants']['Z4Q_FROZEN'] == prior['variants']['Z4Q_FROZEN']
        keys = [o['mask'] for o in assignment['variants']['N0']]
        assert len(keys) == len(set(keys))
        ledger = next(ledgers)
        assert ledger['frame'] == count and ledger['global_frame'] == current['global_frame']
        assert ledger['prediction_row_sha256'] == row_sha(current)
        row, profiles = next(source_rows)
        previous_sensor = verify_frame_contract(name, current, assignment, row, next(measurements),
            next(quality_rows), next(bound_rows), next(flow_rows), ledger, rgb_pins[current['global_frame']], previous_sensor,
            sensor_metadata[current['global_frame']])
        assert ledger['fixed_lag_frames'] == 30 and ledger['model_http'] == 0
        assert not ledger['already_published_history_rewritten']
        arrival = ledger['first_publish_at_arrival_frame']
        assert count <= arrival <= min(count + 30, stop - start + 1)
        assert ledger['actual_delay_frames'] == arrival - count
        assert ledger['EOF_flush'] or arrival == count + 30
        for arm in ARMS:
            objects = current['variants'][arm]
            assert [o['mask'] for o in objects] == keys
            assert all(type(o['id']) is int for o in objects)
            assert len({o['id'] for o in objects}) == len(keys)
            mapping = _mapping(current, arm)
            for source, target in mapping.items():
                first_public[arm].setdefault(target, dict(frame=count, global_frame=current['global_frame'], native_id=source))
            if arm == 'SAM3_NATIVE':
                continue
            transaction = next(tx)
            assert (transaction['arm'], transaction['frame'], transaction['global_frame'], transaction['version']) == (
                arm, count, current['global_frame'], count)
            assert transaction['time'] == current['time'] and transaction['decided_before_first_publish']
            assert transaction['source_row_sha256'] == row_sha(row)
            assert _int_map(transaction['mapping']) == mapping
            assert ledger['transaction_row_sha256'][arm] == row_sha(transaction)
    assert count == stop - start + 1
    assert all(next(values, None) is None for values in (tx, ledgers, source_rows, measurements, quality_rows, bound_rows, flow_rows))
    events = read(public / 'EVENTS.json')
    assert set(events) == set(EVENT_ARMS)
    event_q = {e['request_frame'] for arm in EVENT_ARMS for e in events[arm]}
    q_predictions = {p['frame']: p for p in rows(public / 'predictions.jsonl.gz') if p['frame'] in event_q}
    for arm in EVENT_ARMS:
        for event in events[arm]:
            q = event['request_frame']
            assert event['request']['frame'] == q and event['future_limit_frames'] == 30
            maximum = event['evidence_max_frame']
            assert q <= maximum <= min(q + 30, count)
            assert maximum <= event['first_publish_at_arrival_frame'] <= count
            actual = _mapping(q_predictions[q], arm)
            assert _int_map(event['actual_first_mapping']) == _int_map(event['first_published_mapping']) == actual
            for source, values in event['actual_changes'].items():
                assert actual[int(source)] == values['after']
                assert _int_map(event['request']['original_mapping'])[int(source)] == values['before']
    return dict(status='PASS', frames=count, original_native_and_Z4Q_every_frame_exact=True,
        masks_and_tokens_preserved=True, all_state_transactions_bound_to_first_publication=True,
        events_bound_to_actual_q_and_finite_evidence=True, GT_opened=False,
        actual_frame_source_mask_quality_and_flow_bound_before_GT=True,
        source_original_seal=artifact(ARCHIVED / name / 'public/PREDICTIONS_SEALED.json'),
        source_original_prediction=artifact(original_prediction)), first_public


def _verdict(relation):
    return 'CORRECT' if relation == 'SAME' else 'WRONG' if relation == 'DIFFERENT' else 'UNSCORABLE'


def physical_audit(name, matches, predictions, first_public):
    public = RUN / name / 'public'
    def match(frame, native):
        if frame is None or native is None:
            return dict(status='REFERENCE_MISSING')
        return matches.get(int(frame), {}).get(int(native), dict(status='SOURCE_OR_REFERENCE_MISSING'))
    def anchor_match(anchor):
        return match(anchor.get('frame'), anchor.get('native_id')) if isinstance(anchor, dict) else dict(status='REFERENCE_MISSING')
    def origin(arm, target, q):
        value = first_public[arm].get(target)
        # A just-created public label cannot certify its own identity at q.
        if not value or value['frame'] >= q:
            return value, dict(status='NO_PRIOR_PUBLIC_ORIGIN_REFERENCE')
        return value, anchor_match(value)
    automatic, actions_by_frame = [], {}
    for transaction in rows(public / 'TRANSACTIONS.jsonl.gz'):
        arm, frame = transaction['arm'], transaction['frame']
        actions = transaction.get('actual_actions', transaction['controller_trace'].get('events', []))
        actions_by_frame[arm, frame] = [a for a in actions if a.get('kind') == 'reconnect' and a.get('accepted')]
        for action in actions:
            if action.get('kind') != 'reconnect' or not action.get('accepted'):
                continue
            source, target = action['native_id'], action['canonical_id']
            anchor = action.get('old_anchor')
            assert isinstance(anchor, dict) and anchor['frame'] < frame
            query, past = match(frame, source), anchor_match(anchor)
            reference, public_match = origin(arm, target, frame)
            relation, public_relation = same(query, past), same(query, public_match)
            automatic.append(dict(arm=arm, frame=frame, global_frame=transaction['global_frame'],
                phase='BIRTH_REFINE' if action.get('phase') == 'birth' else 'D1_DELAYED',
                source=source, target=target, actual_action=action, actual_pre_reference=anchor,
                physical_preanchor=_verdict(relation), physical_preanchor_relation=relation,
                public_origin_reference=reference, public_origin_relation=public_relation,
                public_reference_correctness=_verdict(public_relation), query_match=query,
                preanchor_match=past, public_origin_match=public_match,
                incidental_public_reference_return=public_relation == 'SAME' and relation == 'DIFFERENT'))
    event_results = {a: [] for a in EVENT_ARMS}
    for arm, events in read(public / 'EVENTS.json').items():
        for event in events:
            q = event['request_frame']
            request = event['request']
            actual = _mapping(predictions[q], arm)
            source_ids = request.get('sources', sorted({a['native_id'] for a in request['original_actions']}))
            selected = []
            for source in source_ids:
                target = actual[source]
                candidates = [e for e in request['candidate_edges'] if e['native_id'] == source
                    and e['public_id'] == target and e['original_eligible']]
                query = match(q, source)
                public_reference, public_match = origin(arm, target, q)
                edges = []
                actual_actions = [a for a in actions_by_frame[arm, q] if a['native_id'] == source and a['canonical_id'] == target]
                for action in actual_actions:
                    anchor = action['old_anchor']
                    assert anchor['frame'] < q
                    candidate = next((c for c in candidates if c['action_reference_anchor'] == anchor), None)
                    bank = candidate['target_bank_anchor'] if candidate else None
                    past, bank_match = anchor_match(anchor), anchor_match(bank)
                    edges.append(dict(phase='BIRTH_REFINE' if action.get('phase') == 'birth' else 'D1_DELAYED',
                        actual_published_action=action, original_request_edge_binding=candidate,
                        actual_action_reference=anchor,
                        actual_bank_reference=bank, action_reference_match=past, bank_reference_match=bank_match,
                        physical_preanchor=_verdict(same(query, past)),
                        physical_bank_anchor=_verdict(same(query, bank_match))))
                labels = [e['physical_preanchor'] for e in edges]
                physical = ('NO_RECONNECT_REFERENCE' if not labels else 'WRONG' if 'WRONG' in labels
                    else 'UNSCORABLE' if 'UNSCORABLE' in labels else 'CORRECT')
                selected.append(dict(source=source, public_id=target, query_match=query,
                    selected_edge_references=edges, physical_preanchor=physical,
                    original_request_candidate_edges=candidates,
                    public_origin_reference=public_reference, public_origin_match=public_match,
                    public_origin_relation=same(query, public_match),
                    public_reference_correctness=_verdict(same(query, public_match))))
            original = []
            for action in request['original_actions']:
                query, past = match(q, action['native_id']), anchor_match(action.get('old_anchor'))
                original.append(dict(source=action['native_id'], target=action['canonical_id'],
                    phase='BIRTH_REFINE' if action.get('phase') == 'birth' else 'D1_DELAYED',
                    actual_pre_reference=action.get('old_anchor'), query_match=query, reference_match=past,
                    physical_preanchor=_verdict(same(query, past))))
            labels = [e['physical_preanchor'] for e in selected]
            verdict = ('WRONG' if 'WRONG' in labels else 'UNSCORABLE' if 'UNSCORABLE' in labels
                else 'NOT_ALL_SOURCES_RECONNECTED' if 'NO_RECONNECT_REFERENCE' in labels else 'CORRECT')
            event_results[arm].append(dict(event=event['id'], request_frame=q, global_frame=event['global_frame'],
                original_status=event['status'], submitted_option=event['submitted_option'],
                raw_selected_option=event['raw_selected_option'], actual_changes=event['actual_changes'],
                actual_first_published_mapping=actual, physical_preanchor=verdict,
                selection_changes_real_publication=bool(event['actual_changes']),
                submitted_alternative=event['submitted_option'] != 'KEEP' and bool(event['actual_changes']),
                outcome_role='SHADOW_REQUEST_NOT_INDEPENDENT_COMMIT' if event['status'] == 'ACTIVE_WINDOW_OVERLAP_KEEP' else
                    'BOUNDED_WINDOW_DECISION' if 'assessment' in event else 'OUT_OF_SCOPE_KEEP',
                physical_references_are_actual_published_actions=True,
                original_accepted_references=original, selected_sources=selected,
                evidence_max_frame=event['evidence_max_frame'],
                first_publish_at_arrival_frame=event['first_publish_at_arrival_frame'],
                decision_to_first_publication_delay_frames=event['first_publish_at_arrival_frame'] - q,
                public_reference_correctness_is_separate_from_physical_reconnect=True,
                dummy_new_label_is_not_certified_identity_recovery=True,
                prediction_case_selection_did_not_use_GT=True))
    result = dict(segment=name, automatic_actions=automatic, event_arms=event_results,
        automatic_counts={a: dict(Counter(e['physical_preanchor'] for e in automatic if e['arm'] == a)) for a in STATE_ARMS},
        event_counts={a: dict(Counter(e['physical_preanchor'] for e in values)) for a, values in event_results.items()},
        altered_event_counts={a: dict(Counter(e['physical_preanchor'] for e in values if e['submitted_alternative'])) for a, values in event_results.items()},
        UNKNOWN_unscorable_and_no_reference_not_correct=True,
        public_origin_definition='First actual publication with that public label strictly before query; not equality of public integer and GT integer.',
        physical_depth_accuracy='UNKNOWN', old_scores_unchanged=True, postseal_only=True)
    write_new(public / 'EVENT_AUDIT.json', result)
    return result


def switch_changes(switches):
    comparisons = {}
    key = lambda v: json.dumps(v, sort_keys=True, separators=(',', ':'))
    occurrence = lambda v: (v['segment'], v['frame'], v['gt_id'])
    for baseline in ('SAM3_NATIVE', 'Z4Q_FROZEN', 'RGB_LAG'):
        for arm in EVENT_ARMS:
            if arm == baseline:
                continue
            old_values = {key(v): v for v in switches[baseline]}
            new_values = {key(v): v for v in switches[arm]}
            before = {occurrence(v): v for v in switches[baseline]}
            after = {occurrence(v): v for v in switches[arm]}
            comparisons[baseline + '_TO_' + arm] = dict(
                added=[new_values[k] for k in sorted(new_values.keys() - old_values.keys())],
                eliminated=[old_values[k] for k in sorted(old_values.keys() - new_values.keys())],
                common_exact_records=len(old_values.keys() & new_values.keys()),
                occurrence_added=[after[k] for k in sorted(after.keys() - before.keys())],
                occurrence_eliminated=[before[k] for k in sorted(before.keys() - after.keys())],
                same_GT_frame_occurrences=[dict(before=before[k], after=after[k]) for k in sorted(after.keys() & before.keys())],
                net_IDSW=len(switches[arm]) - len(switches[baseline]))
    return comparisons


def deltas(summary):
    return {base: {arm: {key: summary[arm][key] - summary[base][key] for key in FIELDS}
        for arm in EVENT_ARMS if arm != base} for base in ('SAM3_NATIVE', 'Z4Q_FROZEN', 'RGB_LAG')}


def score_segment(name, dev_pin, first_public):
    public = RUN / name / 'public'
    start, stop = SEGMENTS[name]
    gt, sims, predictions = [], [], {}
    pred = {a: [] for a in ARMS}
    previous, step, switches = ({a: {} for a in ARMS}, {a: {} for a in ARMS}, {a: [] for a in ARMS})
    matches = {}
    for frame, (prediction, assignment, truth) in enumerate(zip(rows(public / 'predictions.jsonl.gz'),
            rows(input_dir(name) / 'assignments.jsonl.gz'), ref.reference_rows(name, dev_pin), strict=True), 1):
        global_frame, ids, reference = truth
        assert prediction['frame'] == frame and prediction['global_frame'] == global_frame == start + frame - 1
        keys = [o['mask'] for o in assignment['variants']['N0']]
        sources = [int(key[2:]) for key in keys]
        encoded = [rle(assignment['masks'][key]) for key in keys]
        if name in ('L3', 'LW'):
            label = read(WORK / 'data/AnnotationNewBags_20260919' / name / 'labels_raw' / f'{global_frame:06d}.json')
            native_ids, encoded = polygon_reference(label['shapes'], 1080, 1920)
            assert native_ids == sources
        similarity = (np.asarray(coco.iou(reference, encoded, [0] * len(encoded)), float).reshape(len(ids), len(encoded))
            if ids and encoded else np.zeros((len(ids), len(encoded))))
        gt.append(ids); sims.append(similarity)
        matches[frame] = unique_matches(ids, sources, similarity)
        predictions[frame] = prediction
        for arm in ARMS:
            public_ids = [o['id'] for o in prediction['variants'][arm]]
            pred[arm].append(public_ids)
            step[arm], added = clear_step(ids, keys, public_ids, similarity, previous[arm], step[arm], global_frame)
            switches[arm].extend(dict(value, segment=name) for value in added)
        if frame % 1000 == 0:
            print('DS33 SCORE', name, frame, flush=True)
    assert len(gt) == stop - start + 1
    summary = {arm: metrics(gt, pred[arm], sims)[0] for arm in ARMS}
    archived = read(ARCHIVED / name / 'public/METRICS.json')['metrics']
    for arm in ARMS[:2]:
        assert summary[arm] == archived[arm], (name, arm, 'official same-source control mismatch')
    for arm in ARMS:
        assert len(switches[arm]) == summary[arm]['IDSW']
        assert summary[arm]['predictions'] == summary['SAM3_NATIVE']['predictions']
    result = dict(segment=name, frames=len(gt), metrics=summary, deltas=deltas(summary),
        reference_status='WEAK_UNREVIEWED_PREDICTION_DERIVED_PREANNOTATION' if name in ('L3', 'LW') else 'EXPOSED_EXISTING_ANNOTATION',
        score_protocol='Unchanged DS14/DS20 official mask CLEAR.5 Identity.5 HOTA19alphas; FishSA original raster/annotation version; L3/LW1080; Feeding640.',
        no_mask_or_ID_exclusion=True, physical_depth_accuracy='UNKNOWN')
    write_new(public / 'METRICS.json', result)
    write_new(public / 'SWITCHES.json', switches)
    write_new(public / 'SWITCH_CHANGES.json', switch_changes(switches))
    with gzip.open(public / 'REFERENCE_MATCHES.jsonl.gz', 'xt', encoding='utf-8') as output:
        for frame, values in matches.items():
            output.write(json.dumps(dict(frame=frame, matches=values), separators=(',', ':'), allow_nan=False) + '\n')
    audit = physical_audit(name, matches, predictions, first_public)
    print(name, json.dumps(summary), flush=True)
    return result, (gt, pred, sims), audit


def contract_checks(prefix_public):
    """Small real source-to-ledger slice and synthetic scoring boundaries; no GT."""
    import copy
    from itertools import islice
    prefix_public = Path(prefix_public)
    sealed = read(prefix_public / 'PREDICTIONS_SEALED.json')
    for file, expected in sealed['artifacts_sha256'].items():
        assert sha(prefix_public / file) == expected
    name = sealed['segment']
    base = input_dir(name)
    metadata = {r['global_frame']:r for s in read(HERE / 'SENSOR_AUDIT.json')['segments']
        if s['segment'] == name for r in s['metadata']}
    rgb_pins = {r['global_frame']:r['rgb'] for r in rows(HERE / 'RGB_INPUT_PINS.jsonl') if r['segment'] == name}
    records = []
    inputs = zip(rows(prefix_public / 'predictions.jsonl.gz'), rows(base / 'assignments.jsonl.gz'),
        stream(base / 'observations.jsonl.gz', base / 'profiles.jsonl.gz'),
        rows(base / 'DEPTH_OBSERVATIONS.jsonl.gz'), rows(DS18 / 'run' / name / 'public/MIXED_DEPTH.jsonl.gz'),
        rows(prefix_public / 'FRAME_INPUTS_BINDINGS.jsonl.gz'), rows(prefix_public / 'FLOW.jsonl.gz'),
        rows(prefix_public / 'PUBLISH_LEDGER.jsonl'))
    previous = None
    for values in islice(inputs, 2):
        current, assignment, (row, profiles), measured, quality, bound, flow, ledger = values
        arguments = [name, current, assignment, row, measured, quality, bound, flow, ledger,
            rgb_pins[current['global_frame']], previous, metadata[current['global_frame']]]
        previous = verify_frame_contract(*arguments)
        records.append(arguments)
    assert len(records) == 2
    checks = [dict(name='TWO_ACTUAL_SENSOR_MASK_DS18_FLOW_SOURCE_LEDGER_ROWS', status='PASS', frames=[1, 2])]
    for label, mutate in (
            ('SELF_CONSISTENT_FUTURE_SENSOR_BINDING', lambda a:a[6].__setitem__('maximum_sensor_global_frame', a[1]['global_frame'] + 1)),
            ('SELF_CONSISTENT_WRONG_CURRENT_FLOW_SOURCE', lambda a:a[7]['pair'].__setitem__('current_source_binding', a[10])),
            ('SELF_CONSISTENT_WRONG_DEPTH_QUALITY_EXTRACT', lambda a:a[6].__setitem__('DS18_extracts', {})),
            ('SELF_CONSISTENT_WRONG_MASK_BINDING', lambda a:a[6].__setitem__('current_mask_bindings', {})),
            ('SELF_CONSISTENT_WRONG_SENSOR_TIMESTAMP', lambda a:a[6]['sensor'].__setitem__('depth_timestamp_us', 0))):
        bad = copy.deepcopy(records[1]); mutate(bad)
        bad[8]['frame_inputs_row_sha256'] = row_sha(bad[6])
        bad[8]['flow_row_sha256'] = row_sha(bad[7])
        try:
            verify_frame_contract(*bad)
        except AssertionError:
            checks.append(dict(name=label, status='PASS_REJECTED_AFTER_RECOMPUTING_BINDING_HASHES'))
        else:
            raise AssertionError('semantic tamper accepted: ' + label)
    assert _verdict('UNKNOWN') == 'UNSCORABLE' and _verdict('DIFFERENT') == 'WRONG'
    assert same(dict(status='NO_PRIOR_PUBLIC_ORIGIN_REFERENCE'), dict(status='UNIQUE_IOU_MATCH', gt_id=1)) == 'UNKNOWN'
    checks.append(dict(name='UNKNOWN_AND_NEW_PUBLIC_ORIGIN_CANNOT_CERTIFY_IDENTITY', status='PASS'))
    assert unique_matches([1, 2], [7], np.array([[.7], [.65]]))[7]['status'].startswith('UNSCORABLE')
    checks.append(dict(name='AMBIGUOUS_PHYSICAL_REFERENCE_IS_UNSCORABLE', status='PASS'))
    g, p, sims = [[1], [1], [1]], [[11], [11], [22]], [np.ones((1, 1))] * 3
    official = metrics(g, p, sims)[0]
    previous, step, switches = {}, {}, []
    for frame, (gi, pi, si) in enumerate(zip(g, p, sims), 1):
        step, added = clear_step(gi, ['n:7'], pi, si, previous, step, frame)
        switches.extend(added)
    assert official['IDSW'] == len(switches) == 1 and official['predictions'] == 3
    checks.append(dict(name='OFFICIAL_CLEAR_SWITCH_AND_COUNT_SYNTHETIC_PARITY', status='PASS', official=official))
    old_switch = dict(switches[0], segment='synthetic')
    new_switch = dict(old_switch, from_public_id=101, to_public_id=202, public_id=202)
    values = {a:[] for a in ARMS}
    values['SAM3_NATIVE'] = values['Z4Q_FROZEN'] = [old_switch]
    values['RGB_LAG'] = values['RGBD_LAG'] = [new_switch]
    change = switch_changes(values)['Z4Q_FROZEN_TO_RGBD_LAG']
    assert len(change['added']) == len(change['eliminated']) == 1 and change['net_IDSW'] == 0
    assert not change['occurrence_added'] and not change['occurrence_eliminated']
    checks.append(dict(name='NET_ZERO_SWITCHES_CAN_CONTAIN_ADDED_AND_ELIMINATED_RECORDS', status='PASS'))
    return dict(status='PASS_SCORER_ACTUAL_SOURCE_PROTOCOL_AND_SYNTHETIC_NUMERICS', checks=checks,
        scoring_code_dependencies=scoring_dependencies(), prefix_prediction_seal=artifact(prefix_public / 'PREDICTIONS_SEALED.json'),
        GT_opened=False, annotations_opened=False, new_model_http=0,
        scope='No method performance claim; complete formal prediction/access seals are still mandatory before GT scoring.')


def main():
    from verify_inputs import verify_all
    assert not (RUN / 'METRICS.json').exists(), 'No rescore or sealed-output overwrite'
    began = time.perf_counter()
    seal = verify_all()
    parity, origins = {}, {}
    for name in SEGMENTS:
        parity[name], origins[name] = verify_publications(name)
    # Reference byte hashing and raster access begin only after all guards above.
    dev_pin = ref.authoritative_development_pin()
    assert sha(ref.GT_DEV) == dev_pin
    write_new(RUN / 'SCORING_FREEZE.json', dict(status='ALL_PREDICTION_INPUT_ACCESS_AND_PUBLICATION_BINDINGS_VERIFIED',
        all_seal=artifact(RUN / 'ALL_PREDICTIONS_SEALED.json'), scoring_sources=scoring_dependencies(),
        development_reference=artifact(ref.GT_DEV), development_reference_authority=artifact(old.OLD / 'score.py'),
        validation_original_archive=artifact(ref.ARCHIVE), development_pin=dev_pin,
        reference_not_substituted_by_aligned_package=True, verified_before_reference_raster_read=True,
        prediction_parity=parity, new_model_http=0, cost_usd=0))
    write_new(RUN / 'PREDICTION_PARITY.json', dict(status='PASS', segments=parity, GT_opened=False))
    results, audits = {}, {}
    pool_gt, pool_sims = [], []
    pool_pred = {a: [] for a in ARMS}
    for name in SEGMENTS:
        result, (gt, pred, sims), audit = score_segment(name, dev_pin, origins[name])
        results[name], audits[name] = result, audit
        if name.startswith('feeding_'):
            pool_gt.extend([[(name, identity) for identity in ids] for ids in gt]); pool_sims.extend(sims)
            for arm in ARMS:
                pool_pred[arm].extend([[(name, identity) for identity in ids] for ids in pred[arm]])
    pooled = {a: metrics(pool_gt, pool_pred[a], pool_sims)[0] for a in ARMS}
    original_pool = read(ARCHIVED / 'METRICS.json')['feeding_pooled']['metrics']
    assert all(pooled[a] == original_pool[a] for a in ARMS[:2])
    write_new(RUN / 'METRICS.json', dict(status='SCORED_AFTER_ALL_EIGHT_FORMAL_PREDICTION_AND_ACCESS_SEALS',
        frames=20098, arms=ARMS, segments=results,
        feeding_pooled=dict(frames=1471, metrics=pooled, deltas=deltas(pooled)), event_audits=audits,
        all_seal=artifact(RUN / 'ALL_PREDICTIONS_SEALED.json'), score_seconds=time.perf_counter() - began,
        no_cross_dataset_pooled_headline=True, future_prediction_authority='FINITE_UNPUBLISHED_30FRAME_LAG_NOT_S0_OR_REALTIME',
        depth_increment_comparison='RGBD_LAG_MINUS_RGB_LAG', new_model_http=0, cost_usd=0))
    write_new(RUN / 'SCORE_PROVENANCE.json', dict(scorer=artifact(__file__),
        scoring_freeze=artifact(RUN / 'SCORING_FREEZE.json'), prediction_parity=artifact(RUN / 'PREDICTION_PARITY.json'),
        reference_opened_after_all_seals=True, official_metric_math_unchanged=True,
        ignored_public_ids=0, GT_used_for_prediction=False, original_controls_exact=True))


if __name__ == '__main__':
    main()
