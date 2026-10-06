"""Saved masks -> RGB-D correspondence -> own-state fixed lag -> one publication."""
from common import *
import copy
import time
from collections import deque

from bridge import Bridge, stream
from pycocotools import mask as coco
from sensor import Sensor
from flow import PairMotion
from evidence import ContourMemory, WindowEvidence
from lag import LagBuffer
from verify_inputs import verify_frozen_inputs

C = module('ds33_candidate_controller', HERE / 'controller.py')
CandidateBridge = C.CandidateBridge
DEPTH = module('ds33_unchanged_ds31_extraction', ROOT / 'experiments/ds31_persistent_identity_depth/depth.py')


def emit(row, mapping):
    result = [dict(id=mapping[o['id']], mask=o['mask']) for o in row['native']]
    assert len(result) == len(row['native']) == len(set(o['id'] for o in result))
    assert set(mapping) == {o['id'] for o in row['native']}
    return result


def _numeric(value):
    if isinstance(value, set):
        return sorted(value)
    if hasattr(value, 'tolist'):
        return value.tolist()
    raise TypeError(type(value).__name__)


def _encoded_mask(encoded):
    return coco.decode(dict(size=encoded['size'], counts=encoded['counts'].encode('ascii'))).astype(bool)


def _source_array_binding(array):
    # Exact DS12/DS18 contract hashes the dtype/shape header and C-order bytes.
    header = json.dumps([array.dtype.str, list(array.shape)], separators=(',', ':')).encode()
    return dict(dtype=array.dtype.str, shape=list(array.shape),
                sha256=hashlib.sha256(header + b'\n' + array.tobytes(order='C')).hexdigest())


def transaction(row, bridge):
    actions = [copy.deepcopy(event) for event in row['trace'].get('events', [])
               if event.get('kind') == 'reconnect' and event.get('accepted')]
    return dict(frame=row['frame'], global_frame=row['global_frame'], time=row['time'],
        mapping=copy.deepcopy(row['mapping']), version=bridge.version,
        controller_trace=copy.deepcopy(row['trace']), actual_actions=actions,
        engine_state_sha256=digest(C.engine_state(bridge.engine)),
        full_original_state_sha256=C.bridge_hash(bridge),
        actual_aliases=copy.deepcopy(bridge.engine.alias),
        bank_anchors={str(k):copy.deepcopy(h.get('anchor')) for k, h in bridge.engine.bank.items()},
        source_row_sha256=row.get('source_row_sha256'),
        decided_before_first_publish=True, already_published_history_rewritten=False)


def _retained_runtime_row(row, mapping, trace, bridge):
    value = copy.deepcopy(row)
    value.update(mapping=copy.deepcopy(mapping), trace=copy.deepcopy(trace),
        engine_state_sha256=digest(C.engine_state(bridge.engine)),
        source_row_sha256=row_sha(row))
    value['transaction'] = transaction(value, bridge)
    return value


def run_segment(name, output=RUN, stop_at=None):
    start, stop = SEGMENTS[name]
    total = stop - start + 1
    limit = total if stop_at is None else stop_at
    assert isinstance(limit, int) and 1 <= limit <= total
    base = input_dir(name)
    public = output / name / 'public'
    public.mkdir(parents=True, exist_ok=True)
    if stop_at is None:
        frozen = read(public / 'FREEZE.json')
        verify_frozen_inputs(frozen)
        pin_path = frozen['rgb_pins']['path']
    else:
        pin_path = HERE / 'RGB_INPUT_PINS.jsonl'
        assert Path(pin_path).exists(), 'RGB input pins must precede prefix execution'
        write_new(public / 'PREFIX_FREEZE.json', dict(status='FROZEN_PREFIX_BEFORE_SOURCE_READ',
            segment=name, frames=limit, review_base=BASE,
            rgb_pins=artifact(pin_path), source_manifest=artifact(base / 'SOURCE_MANIFEST.json'),
            code={str(path):sha(path) for path in (HERE / file for file in
                  ('common.py', 'CONFIG.json', 'runner.py', 'controller.py', 'lag.py', 'evidence.py', 'sensor.py', 'flow.py'))},
            no_GT=True, model_http=0, cost_usd=0))
    selected_pins = {pin['global_frame']:pin['rgb'] for pin in rows(pin_path)
                     if pin['segment'] == name}
    assert set(range(start, start + limit)) <= set(selected_pins)
    sensor = Sensor(name)
    previous_sensor = None
    original = Bridge(read(CONFIG_PATH))
    branches = {}
    for arm in ARMS[2:]:
        bridge = CandidateBridge(read(CONFIG_PATH))
        branches[arm] = dict(bridge=bridge, lag=LagBuffer(bridge),
            memory=ContourMemory(name + '/' + arm), active=None,
            events=[], event_by_frame={}, counts=dict(requests=0, changed_commits=0,
                out_of_scope=0, active_window_overlap=0, invalid_candidates=0,
                unknown_keep=0, windows_resolved=0), published=0)
    cached = DS18 / 'run' / name / 'public/MIXED_DEPTH.jsonl.gz'
    archived = ROOT / 'experiments/ds32_z4q_depth_conflict_veto/run' / name / 'public/predictions.jsonl.gz'
    source = zip(stream(base / 'observations.jsonl.gz', base / 'profiles.jsonl.gz'),
        rows(base / 'assignments.jsonl.gz'), rows(base / 'DEPTH_OBSERVATIONS.jsonl.gz'),
        rows(cached), rows(archived), strict=True)
    packets = deque()
    packet_by_frame = {}
    handles = {file:gzip.open(public / file, 'xt', encoding='utf-8', newline='\n') for file in
               ('predictions.jsonl.gz', 'TRANSACTIONS.jsonl.gz', 'FRAME_INPUTS_BINDINGS.jsonl.gz', 'FLOW.jsonl.gz')}
    ledger = (public / 'PUBLISH_LEDGER.jsonl').open('x', encoding='utf-8', newline='\n')
    objects = published = 0
    began = time.perf_counter()

    def dump(file, value):
        line = json.dumps(value, separators=(',', ':'), allow_nan=False, default=_numeric) + '\n'
        handles[file].write(line)
        return hashlib.sha256(line.encode()).hexdigest()

    def finish_window(arm, active, assessment, forced_reason=None):
        owner = branches[arm]
        request = active['plan']['request']
        raw_option = assessment.get('selected_option', 'KEEP') if forced_reason is None else 'KEEP'
        option = next(o for o in active['plan']['options'] if o['id'] == raw_option)
        frames = [(packet_by_frame[f]['row'], packet_by_frame[f]['profiles'])
                  for f in range(request['frame'], active['evidence'].previous_frame + 1)]
        result = C.replay_option(active['checkpoint'], frames, request, option)
        invalid = None
        if result['status'] != 'VALID_CANDIDATE':
            owner['counts']['invalid_candidates'] += 1
            invalid = result['trace']
            option = active['plan']['options'][0]
            result = C.replay_option(active['checkpoint'], frames, request, option)
        assert result['status'] == 'VALID_CANDIDATE', 'own original KEEP replay failed'
        new_memory = copy.deepcopy(active['memory_checkpoint'])
        runtime_rows = []
        for replay_row, state in result['replayed_rows']:
            packet = packet_by_frame[replay_row['frame']]
            new_memory.advance(packet['row'], packet['pair'])
            new_memory.observe(packet['row'], packet['masks'], state, packet['extracts'])
            final = _retained_runtime_row(packet['row'], replay_row['mapping'], replay_row['trace'], state)
            runtime_rows.append((final, state))
        selected_state = result['state']
        if option['id'] == 'KEEP':
            assert C.bridge_hash(selected_state) == C.bridge_hash(owner['bridge']), 'KEEP changed tentative own state'
        owner['lag'].resolve(request['checkpoint_frame'], selected_state, runtime_rows,
                             active['evidence'].previous_frame)
        owner['bridge'], owner['memory'] = selected_state, new_memory
        first_mapping = runtime_rows[0][0]['mapping']
        changed = {n:dict(before=k, after=first_mapping[n]) for n, k in request['original_mapping'].items()
                   if first_mapping[n] != k}
        owner['counts']['changed_commits'] += bool(changed)
        owner['counts']['windows_resolved'] += 1
        if forced_reason or assessment['status'] == 'UNKNOWN_KEEP':
            owner['counts']['unknown_keep'] += 1
        event = active['event']
        event.update(status=forced_reason or ('COMMIT_CHANGED_WINDOW' if changed else 'RESOLVED_KEEP'),
            assessment=copy.deepcopy(assessment), raw_selected_option=raw_option,
            submitted_option=option['id'], invalid_candidate=invalid, actual_changes=changed,
            actual_first_mapping=copy.deepcopy(first_mapping), replay=copy.deepcopy(result['trace']),
            evidence_max_frame=active['evidence'].previous_frame,
            window_evidence=active['evidence'].numeric())
        owner['active'] = None

    def publish(arrival_frame, flush=False):
        nonlocal published
        ready = {arm:owner['lag'].pop_ready(arrival_frame, flush) for arm, owner in branches.items()}
        assert [r['frame'] for r in ready[ARMS[2]]] == [r['frame'] for r in ready[ARMS[3]]]
        for index, first in enumerate(ready[ARMS[2]]):
            frame = first['frame']
            assert frame == published + 1
            packet = packet_by_frame[frame]
            values = copy.deepcopy(packet['baseline_values'])
            transactions = {'Z4Q_FROZEN':packet['baseline_transaction']}
            transaction_pins = {}
            for arm, owner in branches.items():
                chosen = ready[arm][index]
                assert chosen['native'] == packet['row']['native']
                values[arm] = emit(chosen, chosen['mapping'])
                transactions[arm] = chosen['transaction']
                event = owner['event_by_frame'].get(frame)
                if event is not None:
                    assert event['evidence_max_frame'] <= arrival_frame
                    assert event['evidence_max_frame'] <= event['request_frame'] + CFG['lag_frames']
                    event['original_trial_first_mapping'] = copy.deepcopy(event['request']['original_mapping'])
                    event['actual_first_mapping'] = copy.deepcopy(chosen['mapping'])
                    final_changes = {n:dict(before=k, after=chosen['mapping'][n])
                                     for n, k in event['request']['original_mapping'].items()
                                     if chosen['mapping'][n] != k}
                    event['mapping_changed_by_earlier_active_window'] = (
                        event['status'] == 'ACTIVE_WINDOW_OVERLAP_KEEP' and bool(final_changes))
                    event['actual_changes'] = final_changes
                    event['actual_accepted_actions_at_first_publish'] = copy.deepcopy(chosen['transaction']['actual_actions'])
                    original_keys = {(action['native_id'], action['canonical_id'], C.phase(action))
                                     for action in event['request']['original_actions']}
                    actual_keys = {(action['native_id'], action['canonical_id'], C.phase(action))
                                   for action in chosen['transaction']['actual_actions']}
                    event['original_trial_action_not_in_selected_replay'] = not bool(original_keys & actual_keys)
                    event.update(first_publish_at_arrival_frame=arrival_frame,
                                 first_published_mapping=copy.deepcopy(chosen['mapping']))
                owner['published'] += 1
            for arm, txn in transactions.items():
                transaction_pins[arm] = dump('TRANSACTIONS.jsonl.gz', dict(arm=arm, **txn))
            pred = dict(frame=frame, global_frame=packet['row']['global_frame'],
                        time=packet['row']['time'], variants=values)
            prediction_pin = dump('predictions.jsonl.gz', pred)
            ledger.write(json.dumps(dict(frame=frame, global_frame=pred['global_frame'],
                prediction_row_sha256=prediction_pin, transaction_row_sha256=transaction_pins,
                frame_inputs_row_sha256=packet['input_pin'], flow_row_sha256=packet['flow_pin'],
                first_publish_at_arrival_frame=arrival_frame, fixed_lag_frames=CFG['lag_frames'],
                actual_delay_frames=arrival_frame-frame, EOF_flush=flush,
                receive_to_first_publish_seconds=time.perf_counter()-packet['received'],
                model_http=0, already_published_history_rewritten=False), separators=(',', ':')) + '\n')
            published += 1
        # Shared flow, raw arrays and masks are released with the oldest published
        # frame; no full-sequence private pixel copy is retained or written.
        while packets and packets[0]['row']['frame'] <= published:
            packet_by_frame.pop(packets.popleft()['row']['frame'])
        assert len(packets) <= CFG['lag_frames']

    try:
        for frame, ((row, profiles), assignment, measured, quality_packet, archive) in enumerate(source, 1):
            received = time.perf_counter()
            assert frame == row['frame'] == assignment['frame'] == measured['frame'] == quality_packet['frame'] == archive['frame']
            assert row['global_frame'] == start + frame - 1 == assignment['global_frame_id'] == measured['global_frame'] == quality_packet['global_frame'] == archive['global_frame']
            assert row['time'] == assignment['time'] == measured['time'] == quality_packet['time'] == archive['time']
            assert quality_packet['actual_depth_binding'] == measured['raw_source_binding']['aligned_depth']
            assert quality_packet['actual_source_index_binding'] == measured['raw_source_binding']['aligned_source_index']
            assert {int(n) for n in quality_packet['objects']} == {o['id'] for o in row['observations']}
            for cert in quality_packet['objects'].values():
                assert cert['certificate_sha256'] == digest({k:v for k, v in cert.items() if k != 'certificate_sha256'})
                assert (cert['frame'], cert['global_frame'], cert['time']) == (frame, row['global_frame'], row['time'])
                assert cert['frame_binding_sha256'] == quality_packet['frame_binding_sha256']
                for part in ('whole', 'core'):
                    assert cert[part]['inclusive_statistics_sha256'] == digest(cert[part]['inclusive_summary'])
                    assert cert[part]['source_quality_denominator'] == 'ORIGINAL_GEOMETRIC_ROI_AREA_INCLUDING_MISSING_SHARED_DUPLICATE_PIXELS'
            extracts = {int(n):DEPTH.extract(cert) for n, cert in quality_packet['objects'].items()}
            masks = {o['id']:_encoded_mask(assignment['masks'][o['mask']]) for o in row['native']}
            for native, cert in quality_packet['objects'].items():
                assert cert['mask_binding'] == _source_array_binding(masks[int(native)])
                assert cert['whole']['roi_binding'] == cert['mask_binding']
                assert cert['core']['roi_binding'] == cert['core_binding']
            actual_sensor = sensor.read(row['global_frame'], row['time'])
            assert actual_sensor['binding']['rgb'] == selected_pins[row['global_frame']], 'RGB differs from preselected input'
            for source_field in ('aligned_depth', 'aligned_source_index', 'native_depth'):
                assert actual_sensor['binding'][source_field] == measured['raw_source_binding'][source_field], 'actual sensor differs from saved measured source'
            pair = PairMotion(previous_sensor, actual_sensor, CFG['flow']) if previous_sensor is not None else None
            previous_sensor = actual_sensor
            input_pin = dump('FRAME_INPUTS_BINDINGS.jsonl.gz', dict(frame=frame, global_frame=row['global_frame'],
                time=row['time'], sensor=actual_sensor['binding'], source_row_sha256=row_sha(row),
                assignment_row_sha256=row_sha(assignment), DS18_packet_sha256=digest(quality_packet),
                DS18_extracts=extracts, current_mask_bindings={str(n):array_hash(mask) for n, mask in masks.items()},
                no_future_sensor_lookup=True, maximum_sensor_global_frame=row['global_frame']))
            flow_pin = dump('FLOW.jsonl.gz', dict(frame=frame, global_frame=row['global_frame'],
                status='FIRST_FRAME_NO_PREVIOUS_SENSOR' if pair is None else 'ACTUAL_PAIR_COMPUTED_ONCE_SHARED',
                pair=None if pair is None else pair.numeric_summary))
            native_ids, native_trace = original.commit_once(original.preview(frame, row['time'], row['observations'], profiles))
            baseline_values = {'SAM3_NATIVE':copy.deepcopy(row['native']), 'Z4Q_FROZEN':emit(row, native_ids)}
            assert baseline_values['SAM3_NATIVE'] == assignment['variants']['N0'] == archive['variants']['SAM3_NATIVE']
            assert baseline_values['Z4Q_FROZEN'] == archive['variants']['Z4Q_FROZEN']
            baseline_row = _retained_runtime_row(row, native_ids, native_trace, original)
            packet = dict(row=row, profiles=profiles, masks=masks, pair=pair, extracts=extracts,
                baseline_values=baseline_values, baseline_transaction=baseline_row['transaction'],
                input_pin=input_pin, flow_pin=flow_pin, received=received)
            packets.append(packet)
            packet_by_frame[frame] = packet
            for arm, owner in branches.items():
                branch, memory = owner['bridge'], owner['memory']
                view = branch.preview(frame, row['time'], row['observations'], profiles)
                plan = C.enumerate_options(view)
                new_active = plan['status'] == 'REQUEST' and owner['active'] is None
                memory_before = copy.deepcopy(memory) if new_active else None
                checkpoint = owner['lag'].checkpoint(frame-1) if new_active else None
                if new_active:
                    assert C.bridge_hash(checkpoint) == plan['request']['checkpoint_sha256']
                memory.advance(row, pair)
                if plan['status'] != 'NO_ACCEPTED_ACTION':
                    event = dict(id=name + '/' + arm + '/Q' + str(frame), request_frame=frame,
                        global_frame=row['global_frame'], request=copy.deepcopy(plan['request']),
                        future_limit_frames=CFG['lag_frames'], status=plan['status'],
                        raw_selected_option='KEEP', submitted_option='KEEP', actual_changes={},
                        actual_first_mapping=copy.deepcopy(view['mapping']), evidence_max_frame=frame)
                    owner['events'].append(event)
                    owner['event_by_frame'][frame] = event
                    owner['counts']['requests'] += 1
                    if new_active:
                        targets = memory.capture(plan['request'], checkpoint, pair)
                        owner['active'] = dict(plan=plan, checkpoint=checkpoint,
                            memory_checkpoint=memory_before, event=event,
                            evidence=WindowEvidence(plan['request'], targets, arm == 'RGBD_LAG'))
                    elif owner['active'] is not None:
                        event['status'] = 'ACTIVE_WINDOW_OVERLAP_KEEP'
                        owner['counts']['active_window_overlap'] += 1
                    else:
                        owner['counts']['out_of_scope'] += 1
                mapping, trace = branch.commit_once(view)
                owner['lag'].buffer(_retained_runtime_row(row, mapping, trace, branch), branch)
                memory.observe(row, masks, branch, extracts)
                active = owner['active']
                if active is not None:
                    active['evidence'].update(row, masks, profiles, pair, extracts, branch.engine.quality)
                    assessment = active['evidence'].assess(active['plan']['options'])
                    if assessment['status'] in ('DECIDED', 'UNKNOWN_KEEP'):
                        finish_window(arm, active, assessment)
                    elif frame >= active['plan']['request']['frame'] + CFG['lag_frames']:
                        finish_window(arm, active, assessment, 'UNKNOWN_DEADLINE_KEEP')
            publish(frame)
            objects += len(row['native'])
            if frame % 500 == 0:
                print(name, frame, '/', limit, {arm:owner['counts'] for arm, owner in branches.items()}, flush=True)
            if frame == limit:
                break
        for arm, owner in branches.items():
            active = owner['active']
            if active is not None:
                finish_window(arm, active, active['evidence'].assess(active['plan']['options']), 'UNKNOWN_EOF_KEEP')
        publish(frame, flush=True)
        assert published == frame == limit and not packets
        assert all(owner['published'] == limit for owner in branches.values())
    finally:
        for handle in handles.values():
            handle.close()
        ledger.close()
        sensor.close()
    write_new(public / 'EVENTS.json', {arm:owner['events'] for arm, owner in branches.items()})
    write_new(public / 'RUN_SUMMARY.json', dict(segment=name, frames=limit, objects=objects,
        published_frames=published, counts={arm:owner['counts'] for arm, owner in branches.items()},
        elapsed_seconds=time.perf_counter()-began, all_masks_retained=True, original_Z4Q_exact=True,
        published_once=True, fixed_lag_frames=30, corrected_only_unpublished_cache=True,
        no_mask_inpainting=True, model_http=0, cost_usd=0))
    sealed = tuple(handles) + ('PUBLISH_LEDGER.jsonl', 'EVENTS.json', 'RUN_SUMMARY.json')
    sealed += ('FREEZE.json',) if stop_at is None else ('PREFIX_FREEZE.json',)
    write_new(public / 'PREDICTIONS_SEALED.json', dict(status='SEALED_AWAITING_INDEPENDENT_SCORING',
        segment=name, frames=limit, arms=ARMS, artifacts_sha256={file:sha(public / file) for file in sealed},
        model_http=0, cost_usd=0, fixed_lag_frames=30))
    print(name, 'SEALED', limit, {arm:owner['counts'] for arm, owner in branches.items()}, flush=True)


if __name__ == '__main__':
    mode, name = sys.argv[1:3]
    if mode == 'prefix':
        destination = HERE / sys.argv[4]
        assert destination.parent == HERE and destination.name.startswith('slice_')
        run_segment(name, destination, int(sys.argv[3]))
    else:
        assert mode == 'run'
        run_segment(name)
