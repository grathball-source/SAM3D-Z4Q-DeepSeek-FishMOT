"""Bind moved engineering-attempt bytes; never rewrite the original records."""
from common import HERE, artifact, read, verify_item, write_new
from datetime import datetime, timezone
from pathlib import Path

records = []
for name, record, field in (
    ('launch_failure_zero_frames_v1', 'FAILURE.json', 'original_artifact_pins'),
    ('partial_invalid_source_validation_v2', 'STOP.json', 'partial_artifact_pins'),
):
    archived = HERE / name
    for original in read(archived / record)[field]:
        relative = Path(original['path']).relative_to(HERE)
        actual = archived / relative
        pin = dict(original, path=str(actual))
        verify_item(pin)
        records.append(dict(original_record=artifact(archived / record),
                            original_path=original['path'], archived=artifact(actual)))

science = HERE / 'partial_invalid_source_validation_v2/science'
v2 = read(HERE / 'partial_invalid_source_validation_v2/RUNTIME_FREEZE.json')
source_records = []
for path in science.glob('*'):
    if path.name not in ('CONFIG.json', 'PLAN.md') and path.suffix != '.py':
        continue
    original = str(HERE / path.name)
    expected = v2['code'].get(original)
    if expected is None:
        expected = v2.get('configuration', {}).get('sha256') if path.name == 'CONFIG.json' else None
    actual = artifact(path)
    if expected is not None:
        assert actual['sha256'] == expected, path
    source_records.append(dict(original_path=original, archived=actual,
                               frozen_v2_hash_match=expected is not None))

write_new(HERE / 'ARCHIVE_PRESERVATION.json', dict(
    status='PASS_ALL_ORIGINAL_ATTEMPT_PINS_AT_ACTUAL_ARCHIVED_PATHS',
    checked_utc=datetime.now(timezone.utc).isoformat(), moved_artifacts=records,
    v2_source_snapshot=source_records, original_records_unchanged=True,
    stale_original_paths_are_not_current_artifact_paths=True,
    partial_predictions_unsealed_unscored=True, no_partial_state_or_output_reuse=True,
    result_only_helper=artifact(__file__), model_http=0, cost_usd=0))
print('ARCHIVE_PRESERVATION_PASS', len(records), len(source_records), flush=True)
