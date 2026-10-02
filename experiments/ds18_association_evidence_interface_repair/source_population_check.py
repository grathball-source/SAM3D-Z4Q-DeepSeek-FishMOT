"""Prespecified actual source/ROI checks, including semantically invalid re-signed copies."""
import guard  # Installs no-GT/RGB/restored/network and array-field audit before source access.
from common import *
import copy
from mixed_depth import (SCALAR_FIELDS, _digest, _seal, bind_measurement, guard_inputs,
                         guard_raw, measure_mixed, validate_bound_measurement, validate_certificate)
import source

CASES = {'fishsa_development_8400': [3902], 'fishsa_validation_2888': [2188], 'LW': [3064],
         'feeding_000000_000199': [191], 'feeding_001201_001906': [264, 274]}


def actual_anchors(name, frames):
    """All actual proposal/assessment anchors at the chosen source-only frames, no GT selection."""
    references = set()

    def inspect(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key in ('anchor', 'old_anchor') and isinstance(child, dict) and all(
                        k in child for k in ('frame', 'native_id', 'mask')):
                    references.add((child['frame'], child['native_id'], child['mask']))
                inspect(child)
        elif isinstance(value, list):
            for child in value:
                inspect(child)

    path = DS17 / 'run' / name / 'public/TRANSACTIONS.jsonl.gz'
    for row in rows(path):
        if row['frame'] in frames:
            trace = row['controller_trace']
            inspect(dict(events=trace['events'], birth_checks=trace.get('birth_checks', [])))
    assert all(frame < max(frames) and token == f'n:{native}' for frame, native, token in references)
    return sorted(references), artifact(path)


def select(path, frames):
    result = {row['frame']: row for row in rows(path) if row['frame'] in frames}
    assert set(result) == set(frames), (path, frames, result.keys())
    return result


def signed_test_copy(payload):
    manifest = dict(payload=payload, payload_sha256=_digest(payload))
    assert manifest['payload_sha256'] == _digest(manifest['payload'])
    return manifest


def expect_reject(action):
    try:
        action()
    except (AssertionError, ValueError, KeyError):
        return True
    return False


def negative_checks(row, profiles, raw, certificates):
    """Fresh hashes are valid; wrong population/native/version/cutoff remains invalid."""
    native = next(n for n in certificates if certificates[n]['birth_core']['inclusive_summary']['area'] !=
                  certificates[n]['core']['inclusive_summary']['area'])
    c = certificates[native]
    wrong_roi = copy.deepcopy(profiles)
    wrong_roi[native]['core'] = copy.deepcopy(raw[native]['core'])
    manifest = signed_test_copy(wrong_roi)
    roi = expect_reject(lambda: guard_inputs(row, manifest['payload'], certificates))
    assert roi, 'Self-consistent new profile manifest must not legalize the other ROI'
    # JSON payloads are untrusted mutable inputs, never the producer's immutable cache.
    wrong_source = {n: json.loads(json.dumps(c)) for n, c in certificates.items()}
    wrong_source[native]['native'] = native + 1000000
    _seal(wrong_source[native])
    assert validate_certificate(wrong_source[native])  # Producer hash alone is intentionally insufficient.
    manifest = signed_test_copy(wrong_source)
    source_rejection = expect_reject(lambda: guard_inputs(row, profiles, manifest['payload']))
    assert source_rejection, 'Current observation/native binding must reject re-signed other source'
    version = [row.get('segment', c['segment']), 'SOURCE_POPULATION_CHECK', native, 'SOURCE_VERSION_UNSPECIFIED']
    # This is a version-policy negative control, not a fabricated real generation claim.
    binding = bind_measurement(c, 'BIRTH_CORE', profiles[native]['core'], source_version=version)
    forged = bind_measurement(c, 'BIRTH_CORE', profiles[native]['core'], source_version=version[:-1] + ['CHANGED'])
    manifest = signed_test_copy(forged)
    version_rejection = not validate_bound_measurement(manifest['payload'], profiles[native]['core'],
        'BIRTH_CORE', c, source_version=version, native=native, frame=row['frame'])
    assert version_rejection
    future_rejection = not validate_bound_measurement(binding, profiles[native]['core'], 'BIRTH_CORE', c,
        before_frame=row['frame'])
    assert future_rejection
    return dict(actual_test_native=native, current_frame=row['frame'], new_manifests_self_consistent=True,
        wrong_ROI_rejected=roi, rehashed_wrong_native_rejected=source_rejection,
        fresh_binding_wrong_source_version_rejected=version_rejection, current_not_past_anchor_rejected=future_rejection,
        version_control='SYNTHETIC_SOURCE_VERSION_CONTRADICTION; REAL_GENERATION_NOT_INVENTED',
        physical_correct_id_not_required=True)


def main():
    assert not (HERE / 'SOURCE_POPULATION_CHECKS.json').exists()
    results, total_frames, total_objects = {}, 0, 0
    for name, query_frames in CASES.items():
        anchors, anchor_origin = actual_anchors(name, query_frames)
        requested = sorted(set(query_frames) | {frame for frame, _, _ in anchors})
        base = input_dir(name)
        inputs = {filename: select(base / filename, requested) for filename in (
            'observations.jsonl.gz', 'profiles.jsonl.gz', 'assignments.jsonl.gz', 'DEPTH_OBSERVATIONS.jsonl.gz')}
        sensor = source.RawDepth(name)
        checked, negative, by_frame = [], [], {}
        try:
            for frame in requested:
                row = inputs['observations.jsonl.gz'][frame]
                profiles = {p['id']: dict(p, frame=frame) for p in inputs['profiles.jsonl.gz'][frame]['observations']}
                measured = inputs['DEPTH_OBSERVATIONS.jsonl.gz'][frame]
                raw = {int(n): v for n, v in measured['adaptive_raw'].items()}
                depth, index, native_depth, source_binding = sensor(row['global_frame'], row['time'])
                source_binding['frame'] = frame
                packet = measure_mixed(depth, index, source.native_masks(inputs['assignments.jsonl.gz'][frame]),
                    name, frame, row['global_frame'], source_binding=source_binding, native_depth=native_depth)
                for outer, original in (('actual_depth_binding', 'aligned_depth'),
                                        ('actual_source_index_binding', 'aligned_source_index'),
                                        ('native_depth_binding', 'native_depth')):
                    assert packet[outer] == measured['raw_source_binding'][original]
                certificates = packet['objects']
                for n, c in certificates.items():
                    for part in ('whole', 'core'):
                        for key in SCALAR_FIELDS:
                            if key in raw[n][part]:
                                assert c[part]['inclusive_summary'][key] == raw[n][part][key], (name, frame, n, part, key)
                    for part, actual in (('whole', profiles[n]['whole']), ('birth_core', profiles[n]['core'])):
                        for key in SCALAR_FIELDS:
                            if key in actual:
                                assert c[part]['inclusive_summary'][key] == actual[key], (name, frame, n, part, key)
                for screen in (False, True):
                    guard_inputs(row, profiles, certificates, screen=screen)
                    guard_raw(raw, certificates, screen=screen)
                checked.append(dict(frame=frame, global_frame=row['global_frame'], objects=len(certificates),
                    prescribed_query=frame in query_frames, exact_all_original_scalar_statistics=True,
                    raw_source_array_hashes_match=True, raw_source_binding=measured['raw_source_binding'],
                    frame_binding_sha256=packet['frame_binding_sha256'],
                    actual_ROIs={str(n): dict(whole=c['mask_binding'], birth_fixed=c['birth_core_binding'],
                        s0_adaptive=c['core_binding']) for n, c in certificates.items()}))
                by_frame[frame] = (certificates, profiles)
                total_objects += len(certificates)
                if frame in query_frames:
                    negative.append(negative_checks(row, profiles, raw, certificates))
            verified_anchors = []
            for frame, native, token in anchors:
                certificates, profiles = by_frame[frame]
                assert native in certificates and token == f'n:{native}'
                c = certificates[native]
                binding = bind_measurement(c, 'BIRTH_CORE', profiles[native]['core'])
                assert validate_bound_measurement(binding, profiles[native]['core'], 'BIRTH_CORE', c,
                    native=native, frame=frame, before_frame=max(query_frames))
                verified_anchors.append(dict(frame=frame, source_native=native, mask_token=token,
                    binding=binding, source_generation='UNKNOWN_NOT_INVENTED_FROM_PUBLIC_ID',
                    actual_legacy_reference_ROI_bound=True, identity_truth='UNKNOWN'))
        finally:
            sensor.close()
        total_frames += len(requested)
        results[name] = dict(query_frames=query_frames, actual_old_anchor_origin=anchor_origin,
            frame_checks=checked, actual_old_anchor_bindings=verified_anchors, semantic_negative_controls=negative,
            saved_input_bindings={filename: artifact(base / filename) for filename in inputs})
        print(name, 'same-ROI actual sources PASS', len(requested), flush=True)
    access = dict(status='NO_GT_RGB_RESTORED_NETWORK', blocked_tokens=list(guard.BLOCKED),
        observed_data_paths=sorted(guard.SEEN), npz_field_reads=[dict(path=p, key=k) for p, k in sorted(guard.NPZ)],
        h5_or_array_field_reads=source.FIELD_READS, new_model_http=0, cost_usd=0)
    write_new(HERE / 'SOURCE_POPULATION_ACCESS.json', access)
    write_new(HERE / 'SOURCE_POPULATION_CHECKS.json', dict(status='PASS', checked_source_frames=total_frames,
        checked_objects=total_objects, real_query_frames=sum(map(len, CASES.values())), cases=results,
        access=artifact(HERE / 'SOURCE_POPULATION_ACCESS.json'), GT_read=False, RGB_read=False, restored_read=False,
        actual_id_correctness_not_required=True, no_predictions_or_threshold_changes=True,
        source_generation_control_scope='REAL_PIXEL_SOURCE_BOUND; SYNTHETIC_GENERATION_CONTRADICTION_TEST_ONLY',
        model_http=0, cost_usd=0))


if __name__ == '__main__':
    main()
