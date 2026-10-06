"""Record necessary tests and actual unscored source/state/publication acceptance."""
from common import *
from datetime import datetime, timezone
import subprocess

records = list(rows(HERE / 'EXECUTION_LOG.jsonl'))
last = {}
for item in records:
    last[Path(item['command'][1]).name] = item
for script in ('flow_checks.py', 'lag_checks.py', 'controller.py', 'evidence_checks.py'):
    assert last[script]['exit_code'] == 0
    verify_item(last[script]['stdout']); verify_item(last[script]['stderr'])
review = read(HERE / 'RUNNER_CONTRACT_REVIEW.json')
assert review['status'].startswith('PASS')
score = read(HERE / 'SCORER_CONTRACT_CHECKS.json')
assert score['status'].startswith('PASS') and not score['GT_opened']
publication = read(HERE / 'PUBLICATION_ACCEPTANCE_B01.json')
assert publication['status'].startswith('PASS')
artifacts = [artifact(HERE / name) for name in ('NUMERIC_FLOW_CONTRACT_REVIEW.json',
    'RUNNER_CONTRACT_REVIEW.json', 'SCORER_CONTRACT_CHECKS.json', 'NUMERIC_VISUAL_CHECKS.json')]
for script in ('flow_checks.py', 'lag_checks.py', 'controller.py', 'evidence_checks.py'):
    artifacts.extend([artifact(HERE / script), last[script]['stdout'], last[script]['stderr']])
write_new(HERE / 'CHECKS_FINAL.json', dict(status='PASS', artifacts=artifacts,
    direct_check_counts=dict(flow=11, lag=6, real_engine=7, evidence=11,
        independent_numeric_flow=5, scorer_semantic_and_numeric=10),
    no_GT=True, tests_not_research_results=True, new_model_http=0, cost_usd=0))
accepted = [artifact(HERE / 'PUBLICATION_ACCEPTANCE_B01.json')]
details = {}
for name, frames in [('feeding_000000_000199', 200), ('feeding_000351_000555', 80)]:
    public = HERE / 'slice_real_acceptance_v6' / name / 'public'
    sealed = read(public / 'PREDICTIONS_SEALED.json')
    assert sealed['frames'] == frames and tuple(sealed['arms']) == ARMS
    for file, expected in sealed['artifacts_sha256'].items():
        assert sha(public / file) == expected
    prefix = read(public / 'PREFIX_FREEZE.json')
    for path, expected in prefix['code'].items():
        assert sha(path) == expected, 'source changed after accepted slice: ' + path
    access = read(public / 'ACCESS.json')
    assert access['status'] == 'RGB_RAW_DEPTH_FINITE_LAG_NO_GT_RESTORED_NETWORK'
    summary = read(public / 'RUN_SUMMARY.json')
    assert summary['original_Z4Q_exact'] and summary['all_masks_retained'] and summary['published_once']
    assert summary['published_frames'] == frames
    accepted.extend(artifact(public / file) for file in ('PREDICTIONS_SEALED.json', 'ACCESS.json',
        'PREFIX_FREEZE.json', 'RUN_SUMMARY.json', 'EVENTS.json'))
    details[name] = summary
write_new(HERE / 'REAL_ACCEPTANCE.json', dict(status='PASS_ACTUAL_RGB_RAW_DEPTH_STATE_PUBLICATION_SLICES',
    source_frames=280, details=details, artifacts=accepted, no_GT=True,
    minimum_method_improvement_required=False, unscored_prefixes_not_formal_results=True,
    new_model_http=0, cost_usd=0))
resource = json.loads(subprocess.check_output(['powershell', '-NoProfile', '-Command',
    "$ds33vol=Get-Volume -DriveLetter E; $ds33os=Get-CimInstance Win32_OperatingSystem; "
    "$ds33cpu=Get-CimInstance Win32_Processor; [ordered]@{disk_E_free_bytes=$ds33vol.SizeRemaining; "
    "memory_free_KiB=$ds33os.FreePhysicalMemory; CPU=$ds33cpu.Name; physical_cores=$ds33cpu.NumberOfCores; "
    "logical_processors=$ds33cpu.NumberOfLogicalProcessors} | ConvertTo-Json -Compress"], text=True))
assert resource['disk_E_free_bytes'] > 2*1024**3 and resource['memory_free_KiB'] > 4*1024**2
write_new(HERE / 'LOCAL_RESOURCE_PREFLIGHT.json', dict(utc=datetime.now(timezone.utc).isoformat(),
    host='LOCAL_WINDOWS', **resource,
    selected_CPU_workers=2, threads_per_worker=1,
    pixel_cache_frames_max=31, all_frame_RGB_copies_on_disk=False,
    unrelated_annotation_UI_processes_untouched=True, server_connection=False, GPU=False,
    new_model_http=0, cost_usd=0))
print('Necessary checks and 280 actual source frames accepted, without GT or scientific gate.', flush=True)
