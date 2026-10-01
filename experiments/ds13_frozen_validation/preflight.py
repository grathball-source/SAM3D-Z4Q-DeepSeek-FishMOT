"""Source metadata and old-artifact byte hashes; no source pixel/reference parsing or network."""
from pathlib import Path
import ast
import hashlib
import json
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
WORK = Path('E:/CAU/D-MOT')
DS12 = HERE.parent / 'ds12_contact_depth_admission'
BASE = '4a4c560d85f1e1ef07a497d6ece6bbc25a1931d4'
READS = {}


def artifact(path):
    path = Path(path).resolve()
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    return dict(path=str(path), bytes=path.stat().st_size, sha256=digest)


def metadata(path):
    """Explicit callers supply metadata/code paths, never pixel/reference paths."""
    path = Path(path).resolve()
    READS[str(path)] = artifact(path)
    return json.loads(path.read_text(encoding='utf-8'))


def write_new(name, value):
    with (HERE / name).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def intervals(numbers):
    result = []
    for number in sorted(set(numbers)):
        if result and number == result[-1][1] + 1:
            result[-1][1] = number
        else:
            result.append([number, number])
    return result


def overlap(recording, bounds, previous):
    """Frame numbers alone never identify a recording or a fresh source."""
    return any(recording == old_recording and bounds[0] <= stop and start <= bounds[1]
               for old_recording, start, stop in previous)


def frozen_segments():
    path = DS12 / 'common.py'
    READS[str(path.resolve())] = artifact(path)
    tree = ast.parse(path.read_text(encoding='utf-8'))
    assignment = next(node for node in tree.body if isinstance(node, ast.Assign)
                      and any(isinstance(t, ast.Name) and t.id == 'SEGMENTS' for t in node.targets))
    return ast.literal_eval(assignment.value)


def science_lock():
    sealed = metadata(DS12 / 'run/feeding_000000_000199/public/FREEZE.json')
    code = []
    for path, expected in sorted(sealed['code_sha256'].items()):
        item = artifact(path)
        assert item['sha256'] == expected, path
        code.append(item)
    actual = metadata(DS12 / 'EFFECTIVE_PARAMETERS.json')
    config = metadata(DS12 / 'CONFIG.json')
    assert actual['actual_config'] == config
    return dict(status='PREVIOUS_FORMAL_FREEZE_BYTES_VERIFIED', base_commit=BASE,
                code=code, actual_parameters=artifact(DS12 / 'EFFECTIVE_PARAMETERS.json'),
                config=artifact(DS12 / 'CONFIG.json'), scientific_changes=0,
                old_output_equivalence_on_adapted_runner='NOT_RUN_NO_ADAPTED_RUNNER')


def old_lock():
    entries = {}
    names = subprocess.check_output(['git', 'ls-files'], cwd=ROOT, text=True).splitlines()
    import re
    for name in names:
        if re.match(r'^experiments/ds(?:[1-9]|1[0-2])_', name):
            item = artifact(ROOT / name)
            entries[name] = {k: item[k] for k in ('bytes', 'sha256')}
    return dict(base_commit=BASE, count=len(entries), files=entries)


def audit_sources():
    feed = WORK / 'data/AlignedFeeding_v1'
    manifest = feed / 'manifest.jsonl'
    READS[str(manifest.resolve())] = artifact(manifest)
    rows = [json.loads(line) for line in manifest.read_text(encoding='utf-8').splitlines()]
    verification = metadata(feed / 'verification.json')
    segments = frozen_segments()
    used = [('FEEDING_20260918124300', a, b) for a, b in segments.values()]
    aligned = {row['frame'] for row in rows}
    assert aligned == {n for a, b in segments.values() for n in range(a, b + 1)}
    assert verification['frames'] == len(aligned) == 1471
    raw = WORK / 'data/AnnotationFeeding_20260924/ML/labels_raw'
    saved = {int(p.stem) for p in raw.glob('*.json')}
    assert saved == set(range(1907))
    cohort = metadata(HERE.parent / 'ds2_depth_transfer_validation/VALIDATION_COHORT.json')
    production = sorted(entry['production_support'] for category in ('selected', 'excluded')
                        for entry in cohort[category])
    feeding = dict(recording=used[0][0], aligned_frames=len(aligned), saved_prediction_frames=len(saved),
                   old_used_intervals=intervals(aligned), old_producer_support=production,
                   remaining_saved_intervals=intervals(saved - aligned),
                   remaining_saved_frames=len(saved - aligned),
                   approved_fresh_complete_segments=0,
                   blocker='ALL_COMPLETE_ALIGNED_SEGMENTS_USED_IN_DEVELOPMENT',
                   gaps='SAVED_PREDICTIONS_ONLY_NOT_IN_COMPLETE_ALIGNED_REFERENCE_PACKAGE')
    cameras = []
    refs = {'L3': 'labels_recovered_after2888_20260919_200202',
            'LW': 'labels_recovered_after1459_20260919_201837'}
    for camera in ('L3', 'LW'):
        base = WORK / 'data/AnnotationNewBags_20260919' / camera
        data = metadata(base / 'manifest.json')
        report = metadata(base / 'full_report.json')
        metadata(base / 'calibration.json')
        frames = data['frames']
        numbers = {row['frame'] for row in frames}
        prediction_numbers = {int(p.stem) for p in (base / 'labels_raw').glob('*.json')}
        reference_numbers = {int(p.stem) for p in (base / refs[camera]).glob('*.json')}
        assert numbers == prediction_numbers == reference_numbers == set(range(len(frames)))
        missing = [row['frame'] for row in frames if not Path(row['depth_source']).is_file()]
        assert not missing
        assert report['completed'] and report['frames'] == len(frames)
        assert report['depth_restored'] is False
        cameras.append(dict(recording=data['bag'], camera=camera, original_frames=[0, len(frames)-1],
            frames=len(frames), prediction_dir=str(base / 'labels_raw'),
            reference_dir=str(base / refs[camera]), prediction_names_complete=True,
            reference_names_complete=True, reference_content_opened=False,
            depth_source_paths_present=len(frames), depth_usable_declared=sum(row['depth_usable'] for row in frames),
            first_timestamp_us=min(row['rgb_timestamp_us'] for row in frames),
            last_timestamp_us=max(row['rgb_timestamp_us'] for row in frames),
            saved_v2_source='NOT_FOUND_IN_INSPECTED_INPUT_ENTRIES; report.depth_restored=false',
            prior_use='SOURCE_PRODUCTION_NATIVE_BASELINE_FROZEN_Z4Q_EVALUATION_POSTHOC_CASE_DIAGNOSIS',
            ds_tuning_evidence='NOT_FOUND_IN_BOUNDED_REPOSITORY_AND_TOOL_RECORD_SEARCH',
            exhaustive_external_tuning_history='UNKNOWN', explicit_DS13_development_split='UNKNOWN',
            reference_status='DEPENDENT_PREANNOTATION_NOT_INDEPENDENT_GT',
            reference_manual_acceptance='NOT_ESTABLISHED',
            blockers=['MISSING_F9_NATIVE_V2_SOURCE_CHAIN', 'FRESH_DEVELOPMENT_PURPOSE_NOT_EXPLICIT_IN_METADATA']))
    cameras.sort(key=lambda c: c['first_timestamp_us'])
    seconds = max(0, min(c['last_timestamp_us'] for c in cameras)
                  - max(c['first_timestamp_us'] for c in cameras)) / 1e6
    metadata(WORK / 'tools/z4q_new_bags_20260923/results/ACCEPTANCE.json')
    return dict(status='DS13_INPUT_BLOCKED', metadata_review='COMPLETED',
                selection_rule='EARLIEST_COMPLETE_APPROVED_UNTUNED_SAVED_COHORT; NO_OUTCOME_SELECTION',
                planned_arms=['SAM3_NATIVE', 'F9_RESTORED', 'R12_RAW'], feeding=feeding,
                alternative_raw_candidates=cameras, candidate_camera_time_overlap_seconds=seconds,
                selected=[], selected_frames=0,
                other_sources=dict(FishSA='OLD8400_DEVELOPMENT_AND2888_EXPOSED_VALIDATION; NO_FRESH_APPROVED_COHORT_ESTABLISHED',
                                   G10='RAW_SOURCE_METADATA_ONLY; NO_COMPATIBLE_SAVED_COHORT_ESTABLISHED',
                                   explicitly_test_named_inputs='EXCLUDED_WITHOUT_OPENING_CONTENTS'),
                prediction_execution='NOT_STARTED', source_pixel_semantic_checks='NOT_RUN',
                scientific_outcome='NOT_EVALUATED', metrics=None, target_success=None,
                new_model_http=0, api_smoke=0, training=0, sam3_inference=0,
                depth_service_calls=0, server_jobs=0, cost_usd=0)


def verify():
    for item in json.loads((HERE / 'SOURCE_METADATA_INVENTORY.json').read_text(encoding='utf-8'))['files']:
        assert artifact(item['path']) == item, item['path']
    lock = json.loads((HERE / 'OLD_READONLY_LOCK.json').read_text(encoding='utf-8'))
    for path, entry in lock['files'].items():
        item = artifact(ROOT / path)
        assert all(item[k] == entry[k] for k in ('bytes', 'sha256')), path
    frozen = json.loads((HERE / 'FROZEN_R12_LOCK.json').read_text(encoding='utf-8'))
    for item in frozen['code']:
        assert artifact(item['path']) == item, item['path']
    print(json.dumps(dict(status='READONLY_BYTES_REVERIFIED', old_files=lock['count'],
                         frozen_bindings=len(frozen['code']), no_prediction_run=True)))


if __name__ == '__main__':
    if '--verify' in sys.argv:
        verify()
    else:
        write_new('FROZEN_R12_LOCK.json', science_lock())
        write_new('OLD_READONLY_LOCK.json', old_lock())
        write_new('INPUT_AVAILABILITY.json', audit_sources())
        write_new('SOURCE_METADATA_INVENTORY.json', dict(files=list(READS.values()),
            scope='METADATA_AND_SCIENTIFIC_CODE_ONLY; NO_GT_OR_PIXEL_FILE_CONTENT',
            reproduction='python -B preflight.py in a new output copy; --verify is read-only'))
        print('Metadata audit complete; selected cohort=0; new predictions=0; no scientific outcome')
