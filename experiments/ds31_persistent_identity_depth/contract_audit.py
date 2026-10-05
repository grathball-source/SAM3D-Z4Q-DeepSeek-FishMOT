"""Postseal source/trace audit; no controller replay, raster/GT or model calls."""
from common import *
from collections import Counter
import math
import time
import numpy as np
import depth
import identity

CFG = read(HERE/'CONFIG.json')


def close(a, b):
    assert math.isclose(float(a), float(b), rel_tol=1e-10, abs_tol=1e-10), (a, b)


def source_checks(name, row, measured, packet, source_ledger):
    f, g, now = row['frame'], row['global_frame'], row['time']
    assert (packet['segment'], packet['frame'], packet['global_frame'], packet['time']) == (name, f, g, now)
    assert (measured['segment'], measured['frame'], measured['global_frame'], measured['time']) == (name, f, g, now)
    assert source_ledger['frame'] == f and source_ledger['global_frame'] == g
    assert row_sha(packet) == source_ledger['mixed_row_sha256']
    assert packet['no_GT_RGB_future_or_restored_input'] and packet['no_sensor_completion']
    binding = packet['source_binding']
    assert binding == dict(measured['raw_source_binding'], frame=f)
    assert not any(binding.get(k, False) for k in ('GT_read', 'RGB_read', 'restored_read'))
    assert binding['global_frame'] == g and binding['time'] == now
    for outer, inner in (('actual_depth_binding', 'aligned_depth'),
                         ('actual_source_index_binding', 'aligned_source_index'),
                         ('native_depth_binding', 'native_depth')):
        assert packet[outer] == measured['raw_source_binding'][inner]
    shared = {k: packet[k] for k in ('segment', 'frame', 'global_frame', 'time', 'source_binding',
                                   'actual_depth_binding', 'actual_source_index_binding', 'native_depth_binding')}
    assert packet['frame_binding_sha256'] == digest(shared)
    allowed = {'depth_mm', 'source_index', 'current_native_depth_mm', 'frame_id',
               'aligned/raw_depth_mm', 'aligned/raw_source_index', 'native/original_depth_mm'}
    assert set(binding.get('actual_fields_read', ())) <= allowed
    assert set(binding.get('native_fields_read', ())) <= allowed
    return binding.get('actual_fields_read', ())


def check_samples(frames, versions, query, now, arm, records, pid=None):
    assert len(frames) == len(versions)
    assert all(1 <= f < query for f in frames), ('noncausal sample', query, frames)
    assert all(b == a + 1 for a, b in zip(frames, frames[1:])), ('fragment gap', frames)
    assert not versions or all(v == versions[-1] for v in versions), ('fragment version', versions)
    times = []
    for f, version in zip(frames, versions):
        n, generation, public = version
        record = records[f]
        assert n in record['extracts'] and record['generation'][n] == generation
        assert record['mapping'][arm][n] == public and (pid is None or public == pid)
        assert n not in record['risk'][arm], ('risk written to individual history', arm, f, n)
        assert record['time'] <= now
        times.append(record['time'])
    assert all(b > a for a, b in zip(times, times[1:])), ('nonmonotonic sample time', times)
    return times


def check_forecast(prediction, pid, arm, frame, now, records, facts, counters):
    counters['forecast_status/'+prediction['status']] += 1
    frames = prediction['sample_frames']
    assert all(1 <= f < frame for f in frames)
    assert prediction['query_time'] == now
    fact_ids = prediction.get('sample_fact_ids')
    if fact_ids is None:
        assert not prediction['usable']
        counters['null_forecasts_without_full_sample_provenance'] += bool(frames)
        return
    assert len(frames) == len(prediction['sample_times']) == len(fact_ids)
    samples, versions = [], []
    for f, t, fid in zip(frames, prediction['sample_times'], fact_ids):
        old_fact = facts[fid]
        assert old_fact['frame'] == f and old_fact['time'] == t
        measured = old_fact['extract']
        assert measured['usable'] and measured['fact_id'] == fid
        n = measured['native']; generation = records[f]['generation'][n]
        version = [n, generation, records[f]['mapping'][arm][n]]
        versions.append(version)
        samples.append(dict(frame=f, time=t, z_mm=measured['z_mm'], mad_mm=measured['mad_mm'],
                            fact_id=fid, version=version))
    assert check_samples(frames, versions, frame, now, arm, records, pid) == prediction['sample_times']
    assert depth.forecast(samples, now) == prediction
    counters['exact_DS1_forecasts_rebuilt'] += 1
    counters['depth_history_samples_source_and_PID_bound'] += len(samples)


def check_trace(tx, extracts, now, records, facts, counters):
    arm, frame = tx['arm'], tx['frame']; trace = tx['controller_trace']
    assert trace['frame'] == frame and trace['future_frames_used'] == 0
    assert trace['all_masks_retained'] and trace['decided_before_first_publish']
    unlocked, candidates = trace['unlocked_sources'], trace['candidate_pids']
    protected = trace['protected_pids']; protected_pins = trace['protected_reference_pins']
    assert trace['protected_reference_unchanged']
    assert set(map(int, protected_pins)) == set(protected)
    assert all(isinstance(pin, str) and len(pin) == 64 for pin in protected_pins.values())
    assert not set(protected) & set(candidates)
    expected_protected = {pid for group in trace['group_records']
        if group['status'] in ('SUSPECT', 'GROUP') for pid in group['member_pids']}
    assert set(protected) == expected_protected
    if frame > 1:
        previous_pins = records[frame-1]['protected_pins'][arm]
        assert all(protected_pins[pid] == previous_pins[pid] for pid in protected_pins.keys() & previous_pins.keys())
    assert all(int(n) in trace['risk_sources'] for n, pid in tx['mapping'].items() if pid in protected)
    counters['protected_member_bank_frame_checks'] += len(protected)
    counters['protected_group_frames'] += bool(protected)
    shape = (len(unlocked), len(candidates))
    geometry = np.asarray(trace['geometry_cost'], dtype=float).reshape(shape)
    actual = np.asarray(trace['cost'], dtype=float).reshape(shape)
    feasible = np.asarray(trace['feasible'], dtype=bool).reshape(shape)
    assert np.all(np.isfinite(geometry)) and np.all(np.isfinite(actual))
    assert len(trace['depth_rows']) == len(unlocked)
    for i, d in enumerate(trace['depth_rows']):
        n = unlocked[i]; js = np.flatnonzero(feasible[i]); pids = [candidates[j] for j in js]
        assert d['source'] == n and d['candidate_pids'] == pids
        counters['depth_row_reason/'+d['reason']] += 1
        ranked = sorted([geometry[i, j] for j in js]+[CFG['dummy_cost']])
        ambiguous = len(ranked) >= 2 and ranked[1]-ranked[0] <= CFG['depth_ambiguity_margin']
        if d.get('forecasts') is not None:
            assert arm == 'PID_DEPTH' and ambiguous and pids
            assert set(map(int, d['forecasts'])) == set(pids)
            assert d['external_depth_weight'] == CFG['depth_weight'] == .25
            assert not d['costs_are_weighted'] and d['dummy_cost_change'] == 0.
            assert d['no_hard_depth_gate'] and d['no_peak_selection']
            assert d['missing_model'] == 'COMMON_NULL_ENTIRE_CANDIDATE_ROW'
            for pid, prediction in d['forecasts'].items():
                check_forecast(prediction, int(pid), arm, frame, now, records, facts, counters)
        if d.get('active'):
            counters['active_depth_rows'] += 1
            assert d['used'] and extracts[n]['usable'] and set(map(int, d['edges'])) == set(pids)
            assert all(v['usable'] for v in d['forecasts'].values())
            bg = d['background']; full = records[frame]['full_frame']
            assert bg == dict(mu_mm=full['median'], scale_mm=max(60., 1.4826*full['mad']))
            assert d['measurement_fact_id'] == extracts[n]['fact_id']
            for j in js:
                pid = candidates[j]; edge = d['edges'][str(pid)]; prediction = d['forecasts'][str(pid)]
                assert edge['observation_mm'] == extracts[n]['z_mm']
                assert edge['observation_scale_mm'] == extracts[n]['scale_mm']
                scale = math.hypot(prediction['scale_mm'], extracts[n]['scale_mm'])
                close(edge['combined_scale_mm'], scale)
                signal = depth.log_t4(extracts[n]['z_mm'], prediction['mu_mm'], scale)
                background = depth.log_t4(extracts[n]['z_mm'], bg['mu_mm'], bg['scale_mm'])
                close(edge['log_signal'], signal); close(edge['log_background'], background)
                a, b = math.log(.9)+signal-background, math.log(.1); high = max(a, b)
                raw = -(high+math.log(math.exp(a-high)+math.exp(b-high)))
                close(edge['raw_cost'], raw); close(edge['cost'], raw)
                close(actual[i, j], geometry[i, j]+CFG['depth_weight']*raw)
                counters['normalized_density_edges_and_single_weight_checked'] += 1
            assert np.array_equal(actual[i, ~feasible[i]], geometry[i, ~feasible[i]])
        else:
            counters['inactive_depth_rows_exact_geometry'] += 1
            assert not d.get('used') and np.array_equal(actual[i], geometry[i])
            if 'forecasts' in d:
                assert d['edges'] == {} and d['background'] is None
                counters['incomplete_rows_common_null'] += 1
    # Recompute only logged numerical assignments; never instantiate a tracker.
    selected, detail = identity.match(actual, feasible)
    geometric, _ = identity.match(geometry, feasible)
    assert detail == trace['global_assignment']
    if 'dummy_cost' in detail: assert detail['dummy_cost'] == CFG['dummy_cost'] == 1.
    assert len(selected) == len(trace['actions'])
    geo = {unlocked[i]: candidates[j] for i, j, _ in geometric}
    for (i, j, margin), action in zip(selected, trace['actions'], strict=True):
        n, pid = unlocked[i], candidates[j]
        assert (action['source'], action['target'], action['margin']) == (n, pid, margin)
        assert tx['mapping'][str(n)] == pid and action['first_publication_frame'] == frame
        assert action['depth_row'] == trace['depth_rows'][i]
        assert action['geometry_selected_target'] == geo.get(n)
        reference = action['reference']; assert reference['frame'] < frame and reference['pid'] == pid
        g = action['geometry']; sample_versions = g['sample_versions']
        check_samples(g['sample_frames'], sample_versions, frame, now, arm, records, pid)
        assert g['sample_frames'][-1] == reference['frame']
        assert sample_versions[-1] == [reference['native_id'], reference['source_generation'], pid]
        counters['action_motion_history_samples_bound'] += len(sample_versions)
        counters['actions'] += 1
        changed = action['previous_pid'] != pid
        counters['mapping_changed_actions'] += changed
        counters['same_PID_reassociation_actions'] += not changed
        counters['mapping_changed_from_none'] += changed and action['previous_pid'] is None
        counters['mapping_changed_from_existing_PID'] += changed and action['previous_pid'] is not None
        counters['active_depth_actions'] += bool(action['depth_row'].get('active'))
        counters['depth_changed_same_state_geometry_selection'] += bool(action['depth_row'].get('active')) and geo.get(n) != pid
    for group in trace['group_records']:
        assert not group['individual_history_updated']
        assert len(set(group['member_pids'])) == 2
        assert group['current_native'] == records[frame]['native_order']
        counters['group_frame_status/'+group['status']] += 1
        if group['q'] is not None: assert group['q'] == frame
    for item in trace['occupied_member_targets']:
        assert item['event'] in trace['first_split_events']
        assert item['pid'] not in candidates
        assert item['current_native'] and all(tx['mapping'][str(n)] == item['pid'] for n in item['current_native'])
        counters['first_split_occupied_member_targets'] += 1
    counters['first_split_events'] += len(trace['first_split_events'])
    return [dict(frame=frame, source=a['source'], target=a['target'], previous_pid=a['previous_pid'],
                 reference=a['reference'], active_depth=bool(a['depth_row'].get('active')),
                 same_state_geometry_selected_target=a['geometry_selected_target'],
                 depth_changed_same_state_selection=bool(a['depth_row'].get('active')) and a['geometry_selected_target'] != a['target'])
            for a in trace['actions'] if a['previous_pid'] != a['target'] or
            bool(a['depth_row'].get('active')) and a['geometry_selected_target'] != a['target']]


def segment(name, metrics):
    p = RUN/name/'public'; frozen = read(p/'FREEZE.json'); verify_seal(name)
    verify_item(frozen['original_prediction']); verify_item(frozen['original_seal'])
    chain = frozen['source_chain']
    assert chain['no_GT'] and chain['no_RGB'] and chain['no_restored_values']
    verify_item(frozen['source_manifest'])
    for item in chain['derived_inputs'].values(): verify_item(item)
    for key in ('scan', 'raw_sources', 'field_access'): verify_item(chain[key])
    reference = frozen['depth_cache']
    for key in ('source', 'source_seal', 'source_freeze', 'source_ledger'): verify_item(reference[key])
    access = read(p/'ACCESS.json')
    assert access['status'] == 'NO_GT_RGB_RESTORED_NETWORK' and access['new_model_http'] == 0
    for path in access['observed_data_paths']:
        assert not any(token in path.replace('\\', '/').lower() for token in access['blocked_tokens'])
    assert all(x['key'] in ('depth_mm', 'source_index') for x in access['npz_field_reads'])
    counts = Counter(); branches = {arm: Counter() for arm in ARMS[2:]}
    changed = {arm: [] for arm in ARMS[2:]}; depth_divergence = []; divergent_objects = 0
    changes = {arm: [] for arm in ARMS[2:]}; state_pins = {}; generations = {}; last_frames = {}
    facts, records = {}, {}; source_fields = Counter(); txs = iter(rows(p/'TRANSACTIONS.jsonl.gz'))
    streams = (rows(p/'predictions.jsonl.gz'), rows(p/'PUBLISH_LEDGER.jsonl'), rows(p/'DEPTH_EXTRACTS.jsonl.gz'),
        rows(input_dir(name)/'observations.jsonl.gz'), rows(input_dir(name)/'assignments.jsonl.gz'),
        rows(input_dir(name)/'DEPTH_OBSERVATIONS.jsonl.gz'), rows(reference['source']['path']), rows(reference['source_ledger']['path']),
        rows(frozen['original_prediction']['path']))
    start, stop = SEGMENTS[name]
    for f, (prediction, ledger, extracted, row, assignment, measured, packet, old_ledger, archived) in enumerate(zip(*streams, strict=True), 1):
        now, g = row['time'], row['global_frame']
        assert f == prediction['frame'] == ledger['frame'] == extracted['frame'] == row['frame'] == assignment['frame']
        assert g == start+f-1 == prediction['global_frame'] == ledger['global_frame'] == extracted['global_frame']
        assert prediction['time'] == now and ledger['model_http'] == 0
        assert (archived['frame'], archived['global_frame']) == (f, g)
        assert all(prediction['variants'][arm] == archived['variants'][arm] for arm in ARMS[:2])
        assert row_sha(prediction) == ledger['prediction_row_sha256']
        assert row_sha(extracted) == ledger['depth_extract_row_sha256']
        source_fields.update(source_checks(name, row, measured, packet, old_ledger))
        keys = [o['mask'] for o in assignment['variants']['N0']]
        natives = [int(k[2:]) for k in keys]
        assert row['native'] == assignment['variants']['N0'] == prediction['variants']['SAM3_NATIVE']
        assert set(natives) == {o['id'] for o in row['observations']} == set(map(int, packet['objects']))
        rebuilt = {}
        for n in natives:
            c = packet['objects'][str(n)]
            assert c['certificate_sha256'] == digest({k:v for k,v in c.items() if k != 'certificate_sha256'})
            assert (c['native'], c['segment'], c['frame'], c['global_frame'], c['time']) == (n, name, f, g, now)
            assert c['frame_binding_sha256'] == packet['frame_binding_sha256']
            for part, binding_key in (('whole', 'mask_binding'), ('core', 'core_binding')):
                view = c[part]; summary = view['summary']
                assert view['roi_binding'] == c[binding_key]
                assert view['inclusive_statistics_sha256'] == digest(view['inclusive_summary'])
                assert view['source_quality_denominator'] == 'ORIGINAL_GEOMETRIC_ROI_AREA_INCLUDING_MISSING_SHARED_DUPLICATE_PIXELS'
                assert summary['n'] == view['selected_independent_native_source_n'] == view['selected_source_index_binding']['shape'][0]
                assert summary['valid_fraction'] == summary['n']/max(1, summary['area'])
            rebuilt[n] = depth.extract(c)
            assert rebuilt[n] == extracted['extracts'][str(n)]
            counts['objects'] += 1; counts['usable_independent_core'] += rebuilt[n]['usable']
            counts['extract_reason/'+rebuilt[n]['reason']] += 1
            counts['whole_multilayer'] += rebuilt[n]['quality']['whole_multilayer']
            counts['core_multilayer'] += rebuilt[n]['quality']['core_multilayer']
            if last_frames.get(n) != f-1: generations[n] = generations.get(n, -1)+1
            last_frames[n] = f
        assert set(map(int, extracted['extracts'])) == set(natives)
        assert extracted['source_packet'] == reference['source']['path']
        assert extracted['full_frame'] == measured['adaptive_full']
        packet['full_frame'] = measured['adaptive_full']
        assert extracted['source_packet_sha256'] == digest(packet)
        mappings = {}
        frame_txs = {}
        for arm in ARMS:
            objects = prediction['variants'][arm]
            assert [x['mask'] for x in objects] == keys and len({x['id'] for x in objects}) == len(natives)
            mappings[arm] = dict(zip(natives, [x['id'] for x in objects]))
            if arm == 'SAM3_NATIVE': continue
            tx = next(txs); frame_txs[arm] = tx
            assert (tx['arm'], tx['frame'], tx['global_frame'], tx['version'], tx['time']) == (arm, f, g, f, now)
            assert tx['decided_before_first_publish'] and row_sha(tx) == ledger['transaction_row_sha256'][arm]
            assert {int(n): k for n,k in tx['mapping'].items()} == mappings[arm]
            if arm in ARMS[2:]:
                assert tx['source_row_sha256'] == row_sha(row) and tx['depth_packet_sha256'] == digest(packet)
                assert tx['actual_actions'] == tx['controller_trace']['actions']
                if f > 1: assert tx['controller_trace']['state_before_sha256'] == state_pins[arm]
                state_pins[arm] = tx['state_sha256']
        assert set(ledger['transaction_row_sha256']) == set(ARMS[1:])
        records[f] = dict(time=now, extracts=rebuilt, generation={n:generations[n] for n in natives}, mapping=mappings,
            full_frame=extracted['full_frame'], native_order=[o['id'] for o in row['observations']],
            risk={arm:set(frame_txs[arm]['controller_trace']['risk_sources']) for arm in ARMS[2:]},
            protected_pins={arm:frame_txs[arm]['controller_trace']['protected_reference_pins'] for arm in ARMS[2:]})
        for arm in ARMS[2:]:
            changes[arm].extend(check_trace(frame_txs[arm], rebuilt, now, records, facts, branches[arm]))
            if prediction['variants'][arm] != prediction['variants']['Z4Q_FROZEN']: changed[arm].append(g)
        if prediction['variants']['PID_DEPTH'] != prediction['variants']['PID_MOTION']:
            depth_divergence.append(g)
            divergent_objects += sum(mappings['PID_DEPTH'][n] != mappings['PID_MOTION'][n] for n in natives)
        for n, ex in rebuilt.items(): facts[ex['fact_id']] = dict(frame=f, time=now, extract=ex)
        counts['frames'] += 1; counts['mask_publications_verified'] += len(natives)*len(ARMS)
    assert next(txs, None) is None and f == stop-start+1
    assert changed == metrics['changed_frames_vs_z4q'] and depth_divergence == metrics['depth_vs_motion_changed_frames']
    summary = read(p/'RUN_SUMMARY.json'); assert summary['objects'] == counts['objects'] and summary['frames'] == f
    events = read(p/'EVENTS.json'); event_summary = {}
    for arm in ARMS[2:]:
        assert len({e['id'] for e in events[arm]}) == len(events[arm])
        ec = Counter(e['status'] for e in events[arm])
        for e in events[arm]:
            assert len(set(e['pids'])) == 2 and all(a['frame'] < e['start'] for a in e['anchors'].values())
            if e['q'] is not None: assert e['start'] < e['q'] <= f and e['status'] == 'FIRST_SPLIT_ASSOCIATION'
        event_summary[arm] = dict(total=len(events[arm]), final_status=dict(ec), events=events[arm])
        assert branches[arm]['actions'] == summary['counts'][arm]['commits']
        assert branches[arm]['active_depth_rows'] == summary['counts'][arm]['depth_rows']
        assert branches[arm]['depth_changed_same_state_geometry_selection'] == summary['counts'][arm]['depth_changed_choice']
    return dict(status='PASS', counts=dict(counts), source_fields=dict(source_fields), branches={k:dict(v) for k,v in branches.items()},
        mapping_changes_and_same_state_depth_changes=changes, groups=event_summary,
        changed_frames_vs_original_Z4Q=changed, independent_depth_vs_motion_divergent_frames=depth_divergence,
        independent_depth_vs_motion_divergent_objects=divergent_objects,
        sources_and_result_seal=artifact(p/'PREDICTIONS_SEALED.json'), access_seal=artifact(p/'ACCESS.json'))


def main():
    assert (RUN/'ALL_PREDICTIONS_SEALED.json').is_file() and (RUN/'METRICS.json').is_file(), 'All prediction seals and completed metrics are required'
    assert not (RUN/'MECHANISM_ANALYSIS.json').exists(), 'Audit outputs are exclusive-create'
    sealed = read(RUN/'ALL_PREDICTIONS_SEALED.json'); metrics = read(RUN/'METRICS.json')
    assert sealed['frames'] == metrics['frames'] == 20098 and tuple(sealed['arms']) == ARMS
    assert metrics['status'] == 'SCORED_AFTER_ALL_EIGHT_PREDICTION_AND_ACCESS_SEALS'
    assert depth.DEPTH_WEIGHT == CFG['depth_weight'] == .25
    assert depth.SCALE_FLOOR_MM == 15. and depth.MAX_MEASURED_SCALE_MM == 60.
    assert depth.HISTORY_SECONDS == CFG['identity_search_seconds'] == 12.
    began = time.perf_counter(); results = {}
    for name in SEGMENTS:
        verify_item(sealed['seals'][name]); verify_item(sealed['access_seals'][name])
        results[name] = segment(name, metrics['segments'][name])
        print('CONTRACT PASS', name, results[name]['counts']['frames'], flush=True)
    total = Counter(); arms = {a:Counter() for a in ARMS[2:]}
    for result in results.values():
        total.update(result['counts'])
        for arm in ARMS[2:]: arms[arm].update(result['branches'][arm])
    write_new(RUN/'MECHANISM_ANALYSIS.json', dict(status='PASS', audit='SEALED_NUMERIC_SOURCE_TRACE_CONTRACT',
        frames=total['frames'], totals=dict(total), branches={k:dict(v) for k,v in arms.items()}, segments=results,
        elapsed_seconds=time.perf_counter()-began, all_predictions=artifact(RUN/'ALL_PREDICTIONS_SEALED.json'),
        metrics=artifact(RUN/'METRICS.json'), auditor=artifact(__file__),
        checks=dict(all_ledger_rows=True, public_one_to_one_and_all_masks=True, exact_DS18_core_scalar_and_ROI=True,
            active_forecasts_exact_DS1=True, used_history_versions_times_and_continuity=True,
            missing_rows_exact_common_null=True, normalized_scale_density=True, depth_weight_applied_once=True,
            fixed_dummy_and_geometry_feasibility=True, numerical_Hungarian_assignment_verified=True,
            state_hash_chain_verified=True, protected_member_references_held=True,
            original_SAM3_and_Z4Q_frame_exact=True, source_access_no_GT_RGB_restored_network=True),
        limitations=[
            'This audit reads sealed numeric observations/certificates/logs and existing metrics; it performs no controller replay or GT/raster/model access.',
            'Complete bank snapshots and unused motion edges are not logged. State hashes bind that internal state but do not independently reconstruct every unused history or write.',
            'Usable depth forecasts are rebound to prior actual extracts, source generations and this branch public mappings; recorded accepted-motion sample versions are checked. Null forecasts lacking sample provenance are counted separately.',
            'Mapping changes use recorded source previous_PID and actual committed publications. Accepted same-PID reassociations are counted separately from identity changes.',
            'Same-state geometry selections are numerical counterfactuals on logged matrices. Independent PID_DEPTH/PID_MOTION divergence includes their continued different states and is reported separately.',
            'Source/ROI/single-layer quality is not physical identity truth or sensor calibration. Existing exposed data and weak L3/LW annotations do not establish blind or cross-dataset generalization.'
        ], new_model_http=0, cost_usd=0))
    print('MECHANISM_ANALYSIS PASS', dict(total), flush=True)


if __name__ == '__main__':
    main()
