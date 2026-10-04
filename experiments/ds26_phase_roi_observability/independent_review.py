"""Postseal DS26 task coverage and actual raw-source reproduction audit.

The semantic task set is rebuilt from COHORT without importing measure.tasks.
Every actual endpoint is then reproduced with the frozen DS25 producer. This
checks source bindings and reproducibility, not independent physical truth.
Raw-source intersections and depth-difference arithmetic are also reconstructed
directly. Only this new numeric review is written; no result, seal, tracking
state, candidate, reference, mask or old experiment is altered.
"""
from common import *
from collections import Counter, defaultdict
from datetime import datetime, timezone
import math
import runpy
import time
import numpy as np
from source import RawDepth, native_masks
import source
from measurement_adapter import summarize, pair_summary


def expected_tasks(cohort):
    """Construct each expected semantic record from its immutable references."""
    contexts = {c['context_id']: c for c in cohort['contexts']}
    logical = {p['pair_id']: p for p in cohort['logical_pairs']}
    assert len(contexts) == 15 and len(logical) == 532
    assert len(cohort['references']) == 540
    expected = {}
    for context_id, context in contexts.items():
        key = context['key']
        candidates = [p for p in logical.values() if p['context_id'] == context_id]
        assert candidates
        assert set(context['logical_pair_ids']) == {p['pair_id'] for p in candidates}
        first = next(p for p in cohort['logical_pairs'] if p['context_id'] == context_id)
        cutoff = min(p['q'] for p in candidates)
        for pair in candidates:
            assert pair['pre_frames'] == key['pre_frames']
            assert pair['target_anchor'] == key['anchor']
            assert pair['pre_versions']['A'] == key['target_anchor_version']
            assert pair['pre_versions']['B'] == key['partner_version']
            assert pair['partner_native'] == key['partner_native']
            assert pair['partner_public'] == key['partner_public']
            assert pair['current_partner_claim_version'] == key['partner_version']
            assert pair['seed_frame'] == key['seed_frame']
            assert [x['fact_id'] for x in pair['ds25_citations']['pre_pairs']] == key['pre_fact_ids']
            assert [x['frame'] for x in pair['ds25_citations']['pre_pairs']] == key['pre_frames']
            assert [x['frame'] for x in pair['ds25_citations']['anonymous_contact']] == list(range(key['anchor']['frame'] + 1, pair['q']))
            assert pair['ds25_citations']['current_pair']['frame'] == pair['q']
            assert key['anchor']['frame'] < pair['seed_frame'] < pair['q']
        for frame in key['pre_frames']:
            provenance = {p['role']: p for p in context['pre_source_checks'] if p['frame'] == frame}
            assert set(provenance) == {'A', 'B'}
            for role, native, public in (
                    ('A', key['anchor']['native_id'], key['anchor']['canonical_id']),
                    ('B', key['partner_native'], key['partner_public'])):
                p = provenance[role]
                assert (p['native'], p['public'], p['class_at_pre']) == (native, public, 'CLEAN_ACTUAL_BANK_ANCHOR')
                assert p['actual_publication_matches']
                assert p['actual_bank_anchor'] == dict(frame=frame, native_id=native, mask=f'n:{native}', canonical_id=public)
            cite = next(p for p in first['ds25_citations']['pre_pairs'] if p['frame'] == frame)
            task_id = f'{context_id}/pre/F{frame}'
            assert task_id not in expected
            expected[task_id] = dict(
                task_id=task_id, context_id=context_id, segment=key['segment'], frame=frame,
                phase='PRE_ACTUAL_CLEAN_ANCHORS',
                native_roles={'A': key['anchor']['native_id'], 'B': key['partner_native']},
                role_provenance=provenance, old_contact_roi_citation=cite,
                causal_query_limit=cutoff)
    for pair_id, pair in logical.items():
        task_id = pair_id + '/q'
        assert task_id not in expected
        assert pair['actual_published_mapping_at_q'][str(pair['current_native'])] == pair['current_actual_public']
        assert pair['actual_published_mapping_at_q'][str(pair['partner_native'])] == pair['partner_actual_public'] == pair['partner_public']
        expected[task_id] = dict(
            task_id=task_id, pair_id=pair_id, context_id=pair['context_id'],
            segment=pair['segment'], frame=pair['q'],
            phase='POST_ACTUAL_GEOMETRY_IDENTITY_UNKNOWN',
            native_roles={'A': pair['current_native'], 'B': pair['partner_native']},
            role_provenance=dict(
                actual_mapping=pair['actual_published_mapping_at_q'],
                original_transaction_sha256=pair['original_transaction_sha256'],
                pre_versions=pair['pre_versions'],
                current_partner_claim_version=pair['current_partner_claim_version'],
                candidate_target_public=pair['target_public'], candidate_mapping_is_hypothesis=True,
                current_source_is_actual_q_bank_anchor=pair['current_source_is_actual_q_bank_anchor'],
                partner_source_is_actual_q_bank_anchor=pair['partner_source_is_actual_q_bank_anchor'],
                post_geometry_and_quality_gate_passed=pair['post_geometry_and_quality_gate_passed']),
            old_contact_roi_citation=pair['ds25_citations']['current_pair'],
            causal_query_limit=pair['q'])
    assert Counter(t['phase'] for t in expected.values()) == {
        'PRE_ACTUAL_CLEAN_ANCHORS': 119,
        'POST_ACTUAL_GEOMETRY_IDENTITY_UNKNOWN': 532}
    assert len(expected) == 651
    return expected


def unique_rows(path):
    values = {}
    for row in rows(path):
        key = row['fact_id']
        assert key not in values, ('Duplicate sealed fact', key)
        values[key] = row
    return values


def all_old_citations(cohort, oldfacts):
    needed = {}
    references = 0
    for pair in cohort['logical_pairs']:
        citations = pair['ds25_citations']
        for citation in [*citations['pre_pairs'], *citations['anonymous_contact'], citations['current_pair']]:
            prior = needed.setdefault(citation['fact_id'], citation['measurement_sha256'])
            assert prior == citation['measurement_sha256']
            fact = oldfacts[citation['fact_id']]
            assert digest(fact) == citation['measurement_sha256']
            assert fact['segment'] == pair['segment']
            assert fact['frame'] == citation['frame'] <= pair['q']
            assert fact['time'] == citation['time'] <= pair['time']
            references += 1
    assert set(needed) == set(oldfacts)
    actual_old = {}
    for segment in {p['segment'] for p in cohort['logical_pairs']}:
        for fact in rows(DS25 / 'run' / segment / 'public/MEASUREMENTS.jsonl.gz'):
            if fact['fact_id'] in needed:
                assert digest(fact) == needed[fact['fact_id']]
                assert fact == oldfacts[fact['fact_id']]
                actual_old[fact['fact_id']] = fact
    assert set(actual_old) == set(needed)
    return references


def source_sets(fact, maps, index):
    """Reconstruct frame-local populations directly from the original raster."""
    roi = maps['roi']
    assert old_measurement.array_binding(roi) == fact['roi_binding']
    assert old_measurement.array_binding(index) == fact['actual_source_index_binding']
    canonical = np.sort(index[maps['mask_selected']])
    assert len(canonical) == fact['summary']['n']
    assert np.all(canonical >= 0) and len(np.unique(canonical)) == len(canonical)
    qualified = []
    layers = {layer['support_id']: layer for layer in fact['layers']}
    for support_id in fact['qualified_support_ids']:
        positions = maps['selected_positions'][support_id]
        layer = layers[support_id]
        assert layer['qualified'] and len(positions) == layer['independent_n']
        assert np.all(roi.ravel()[positions]) and np.all(maps['mask_selected'].ravel()[positions])
        assert np.all(maps['support_masks'][support_id].ravel()[positions])
        values = index.ravel()[positions]
        assert len(np.unique(values)) == len(values)
        assert old_measurement.array_binding(values) == layer['population_binding']['selected_source_index_binding']
        qualified.append(values)
    return dict(
        inclusive_raw_native_sources=np.unique(index[roi & (index >= 0)]),
        canonical_raw_native_sources=canonical,
        qualified_native_sources=np.unique(np.concatenate(qualified)) if qualified else np.array([], dtype=index.dtype))


def audit_cross(pair, cache, index):
    roles = pair['native_roles']
    actual = pair['cross_role']
    A, mapsA = cache[roles['A']]
    B, mapsB = cache[roles['B']]
    # Frozen helper reproduction and separately reconstructed source arithmetic
    # are reported distinctly from independent physical evidence.
    assert digest(actual) == digest(pair_summary(A, mapsA, B, mapsB, index))
    populations = {'A': source_sets(A, mapsA, index), 'B': source_sets(B, mapsB, index)}
    overlaps = {}
    for role in ('A', 'B'):
        for name, values in populations[role].items():
            recorded = actual['populations'][role][name]
            assert recorded == dict(n=int(len(values)), binding=old_measurement.array_binding(values))
    for name in populations['A']:
        values = np.intersect1d(populations['A'][name], populations['B'][name])
        recorded = actual['source_overlaps'][name]
        assert recorded == dict(n=int(len(values)), binding=old_measurement.array_binding(values))
        overlaps[name] = int(len(values))
    summaries = [pair['role_facts'][r]['summary'] for r in ('A', 'B')]
    eligible = all(s['sole_proxy_eligible'] for s in summaries) and not overlaps['qualified_native_sources']
    assert actual['pair_proxy_eligible'] == eligible
    assert actual['identity_independence'] == actual['physical_identity'] == actual['foreground_identity'] == 'UNKNOWN'
    assert actual['no_identity_veto'] and actual['no_state_write']
    assert not actual['source_index_temporal_correspondence']
    if eligible:
        supports = [next(layer for layer in s['layers'] if layer['support_id'] == s['sole_proxy_support_id']) for s in summaries]
        delta = supports[1]['z_mm'] - supports[0]['z_mm']
        sigma = math.sqrt(supports[0]['sigma_mm'] ** 2 + supports[1]['sigma_mm'] ** 2)
        assert math.isclose(actual['measured_depth_difference_mm'], delta, abs_tol=1e-10)
        assert math.isclose(actual['propagated_sigma_mm'], sigma, abs_tol=1e-10)
        assert math.isclose(actual['standardized_difference'], delta / sigma, abs_tol=1e-12)
        order = 'A_PROXY_NEARER' if delta > 0 else 'B_PROXY_NEARER' if delta < 0 else 'EQUAL_PROXY_MEDIANS'
        assert actual['measured_order'] == order
    else:
        assert actual['measured_depth_difference_mm'] is None
        assert actual['propagated_sigma_mm'] is None and actual['standardized_difference'] is None
        assert actual['measured_order'] == 'UNKNOWN'


def main(guard):
    started = time.perf_counter()
    output = HERE / 'INDEPENDENT_REVIEW.json'
    assert not output.exists(), 'Do not overwrite an independent review'
    check_freeze()
    seal_path = RUN / 'MEASUREMENTS_SEALED.json'
    seal = read(seal_path)
    assert seal['status'] == 'SEALED_BEFORE_INDEPENDENT_REVIEW'
    assert seal['no_tracking_or_identity_state_write'] and seal['new_model_http'] == seal['cost_usd'] == 0
    for pin in seal['artifacts'].values():
        verify_item(pin)
    verify_item(seal['cohort'])
    verify_item(seal['runtime'])
    cohort = read(HERE / 'COHORT.json')
    expected = expected_tasks(cohort)
    recorded = list(rows(RUN / 'PAIRINGS.jsonl.gz'))
    actual = {p['task_id']: p for p in recorded}
    assert len(actual) == len(recorded) and set(actual) == set(expected)
    logical = list(rows(RUN / 'LOGICAL_PAIR_REFERENCES.jsonl.gz'))
    assert logical == cohort['logical_pairs']
    endpoint_facts = unique_rows(RUN / 'ENDPOINT_FACTS.jsonl.gz')
    oldfacts = unique_rows(RUN / 'OLD_UNCHANGED_FACTS.jsonl.gz')
    citations = all_old_citations(cohort, oldfacts)
    referenced_endpoint_facts = set()
    grouped = defaultdict(lambda: defaultdict(list))
    for task_id, task in expected.items():
        pair = actual[task_id]
        for key, value in task.items():
            assert pair[key] == value, ('Task semantic mismatch', task_id, key)
        assert pair['identity_recovery'] == 'NOT_PERFORMED'
        assert not pair['state_write'] and not pair['GT_RGB_future']
        assert pair['frame'] <= pair['causal_query_limit']
        cite = task['old_contact_roi_citation']
        assert pair['old_contact_roi_summary'] == summarize(oldfacts[cite['fact_id']])
        assert set(pair['role_facts']) == set(pair['actual_masks']) == {'A', 'B'}
        for role in ('A', 'B'):
            ref = pair['role_facts'][role]
            fact = endpoint_facts[ref['fact_id']]
            assert digest(fact) == ref['measurement_sha256']
            assert summarize(fact) == ref['summary']
            assert fact['frame'] == pair['frame'] and fact['segment'] == pair['segment']
            assert fact['global_frame'] == pair['global_frame'] and fact['time'] == pair['time']
            assert fact['roi_binding'] == pair['actual_masks'][role]
            assert digest(fact['source_binding']) == pair['source_binding_sha256']
            referenced_endpoint_facts.add(ref['fact_id'])
        grouped[pair['segment']][pair['frame']].append(pair)
    assert referenced_endpoint_facts == set(endpoint_facts)

    reads = []
    reproduced = set()
    masks_measured = 0
    source_paths = []
    for segment in SEGMENTS:
        if segment not in grouped:
            continue
        frames = set(grouped[segment])
        base = input_dir(segment)
        data = {}
        for field, filename in [('observations', 'observations.jsonl.gz'),
                                ('assignments', 'assignments.jsonl.gz'),
                                ('depth', 'DEPTH_OBSERVATIONS.jsonl.gz')]:
            path = base / filename
            data[field] = {row['frame']: row for row in rows(path) if row['frame'] in frames}
            assert set(data[field]) == frames
            source_paths.append(artifact(path))
        sensor = RawDepth(segment)
        try:
            for frame in sorted(frames):
                observation = data['observations'][frame]
                assignment = data['assignments'][frame]
                depth_record = data['depth'][frame]
                assert (observation['frame'], observation['global_frame'], observation['time']) == (assignment['frame'], assignment['global_frame_id'], assignment['time']) == (depth_record['frame'], depth_record['global_frame'], depth_record['time'])
                depth, index, native, binding = sensor(observation['global_frame'], observation['time'])
                assert binding == depth_record['raw_source_binding']
                masks = native_masks(assignment)
                objects = {o['id']: o for o in observation['observations']}
                cache = {}
                for pair in grouped[segment][frame]:
                    assert pair['global_frame'] == observation['global_frame'] and pair['time'] == observation['time']
                    assert pair['source_binding_sha256'] == digest(binding)
                    for role, native_id in pair['native_roles'].items():
                        assert native_id in masks and native_id in objects
                        assert int(masks[native_id].sum()) == objects[native_id]['area']
                        assert not objects[native_id].get('neighbors')
                        assert pair['actual_masks'][role] == old_measurement.array_binding(masks[native_id])
                        if native_id not in cache:
                            fact, maps = old_measurement.measure_region(
                                depth, index, native, masks, masks[native_id], segment, frame,
                                observation['global_frame'], observation['time'],
                                source_binding=binding, expected_source_binding=depth_record['raw_source_binding'])
                            cache[native_id] = fact, maps
                            masks_measured += 1
                        fact, maps = cache[native_id]
                        ref = pair['role_facts'][role]
                        assert fact['fact_id'] == ref['fact_id'] and digest(fact) == ref['measurement_sha256']
                        assert fact == endpoint_facts[ref['fact_id']]
                        reproduced.add(fact['fact_id'])
                    audit_cross(pair, cache, index)
                reads.append(dict(segment=segment, frame=frame, global_frame=observation['global_frame'],
                                  time=observation['time'], source_binding_sha256=digest(binding),
                                  actual_mask_measurements=len(cache), paired_tasks=len(grouped[segment][frame])))
        finally:
            sensor.close()
        print(segment, len(frames), 'raw frames independently reproduced', flush=True)
    assert reproduced == set(endpoint_facts)

    summary = read(RUN / 'SUMMARY.json')
    assert summary['contexts'] == 15 and summary['logical_pairs'] == 532
    assert summary['paired_endpoints'] == 651 and summary['pre_pairs'] == 119 and summary['post_pairs'] == 532
    assert summary['unique_endpoint_facts'] == len(endpoint_facts)
    assert summary['unchanged_old_facts'] == len(oldfacts)
    assert summary['unique_actual_mask_measurements'] == masks_measured
    assert summary['raw_frames'] == len(reads)
    for key in ('state_commits', 'new_tracking_predictions', 'new_model_http', 'cost_usd'):
        assert summary[key] == 0
    optional_result_reviewed = False
    if (HERE / 'RESULTS.json').exists():
        result = read(HERE / 'RESULTS.json')
        assert result['cohort_selection'] == cohort['selection']
        assert len(result['contexts']) == 15
        assert result['stages']['PRE_ACTUAL_CLEAN_ANCHORS']['paired_frames'] == 119
        assert result['stages']['POST_ACTUAL_GEOMETRY_IDENTITY_UNKNOWN']['paired_frames'] == 532
        assert result['physical_identity'] == result['physical_depth_accuracy'] == 'UNKNOWN'
        for key in ('state_commits', 'new_tracking_predictions', 'new_model_http', 'cost_usd'):
            assert result[key] == 0
        assert sum(len(c['per_query']) for c in result['contexts']) == 532
        assert all(not c['identity_certified'] for c in result['contexts'])
        optional_result_reviewed = True
    write_new(output, dict(
        status='PASS_FULL_SEMANTIC_COHORT_AND_ACTUAL_SOURCE_REPRODUCTION',
        created_utc=datetime.now(timezone.utc).isoformat(), elapsed_seconds=time.perf_counter() - started,
        independently_reconstructed_tasks=len(expected), pre_tasks=119, post_semantic_pairs=532,
        original_path_references=540, reference_contexts=15,
        complete_task_id_and_semantic_sets_match=True,
        context_frame_roles_versions_actual_publications_match=True,
        unique_endpoint_facts_reproduced=len(reproduced), actual_mask_measurements=masks_measured,
        raw_frames_reproduced=len(reads), paired_cross_role_reproductions=len(recorded),
        unchanged_old_contact_endpoint_facts=len(oldfacts), old_fact_citation_occurrences=citations,
        every_old_fact_value_matches_original_DS25=True,
        frame_local_population_and_intersection_bindings_independently_reconstructed=True,
        depth_delta_and_RSS_arithmetic_recomputed=True, optional_result_boundary_reviewed=optional_result_reviewed,
        seal=artifact(seal_path), cohort=artifact(HERE / 'COHORT.json'), code=artifact(Path(__file__)),
        source_paths=source_paths, raw_source_reads=reads, actual_fields_read=source.FIELD_READS,
        access_guard=dict(status='NO_GT_RGB_RESTORED_NETWORK', blocked_tokens=list(guard['BLOCKED']),
                          observed_data_paths=sorted(guard['SEEN']),
                          npz_field_reads=[dict(path=p, key=k) for p, k in sorted(guard['NPZ'])]),
        GT_read=False, RGB_read=False, restored_depth_read=False, future_data_used=False,
        new_model_http=0, cost_usd=0, state_commits=0, new_tracking_predictions=0,
        physical_identity='UNKNOWN', physical_depth_accuracy='UNKNOWN',
        limitations=[
            'Raw measurements are reproduced with the same frozen DS25 producer; this is source/reproducibility validation, not an independent sensor accuracy estimator.',
            'Task construction does not call measure.tasks. Shared measurement helper formulas remain the frozen scientific definition.',
            'Canonical raw source populations are compared only within each actual frame, never across time.',
            'Source independence does not certify independent fish identities; no post role becomes an old-identity clean anchor.',
            'Saved JSONL metadata is scanned for the fixed wanted frames; only the selected actual raw depth and masks contribute to measurement.',
            'No new tracking metric or identity recovery is inferred from this review.']))
    print('PASS: all 119 pre tasks, 532 semantic post pairs, actual source facts and cross-role arithmetic')


if __name__ == '__main__':
    guard = runpy.run_path(str(ROOT / 'experiments/ds20_pending_confirmation_isolation/guard.py'), run_name='ds26_independent_guard')
    main(guard)
