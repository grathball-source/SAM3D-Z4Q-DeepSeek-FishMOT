"""Freeze science and independent scoring before any formal prediction starts."""
from common import *
import runner, score
import subprocess, platform
from datetime import datetime, timezone

assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT).decode().strip() == BASE
assert not subprocess.check_output(['git', 'diff', '--name-only'], cwd=ROOT).decode().strip()
assert not RUN.exists(), 'Never replace an old formal run'
checks = read(HERE / 'CHECKS_FINAL.json')
assert checks['status'] == 'PASS'
for item in checks['artifacts']:
    verify_item(item)
acceptance = read(HERE / 'REAL_ACCEPTANCE.json')
assert acceptance['status'] == 'PASS_ACTUAL_RGB_RAW_DEPTH_STATE_PUBLICATION_SLICES'
for item in acceptance['artifacts']:
    verify_item(item)
audit = read(HERE / 'SENSOR_AUDIT.json')
assert audit['status'].startswith('PASS') and audit['frames'] == 20098
for pin in audit['actual_rgb_inputs'] + audit['actual_raw_containers'] + audit['actual_calibrations']:
    verify_item(pin)
for section in audit['segments']:
    verify_item(section['source_observation_pin'])
    verify_item(section['source_sensor_binding_pin'])
for key in ('source_code', 'calling_common'):
    verify_item(audit[key])
files = {p for p in HERE.rglob('*.py') if not {'__pycache__', 'private'} & set(p.relative_to(HERE).parts)}
files |= {HERE / 'PLAN.md', HERE / 'README.md', HERE / 'CONFIG.json', CONFIG_PATH}
for mod in list(sys.modules.values()):
    value = getattr(mod, '__file__', None)
    if value and value.endswith('.py'):
        path = Path(value).resolve()
        if any(str(path).lower().startswith(str(root).lower()) for root in (ROOT, WORK / 'tools')):
            files.add(path)
# Unique module and AST loaders are intentionally not assumed present in sys.modules.
for relative in ('ds14_raw_multidataset/common.py', 'ds14_raw_multidataset/source.py',
    'ds12_contact_depth_admission/contact_measurement.py', 'ds31_persistent_identity_depth/depth.py',
    'ds1_depth_only/score.py', 'ds1_depth_only/postseal.py', 'ds14_raw_multidataset/evaluate.py',
    'ds20_pending_confirmation_isolation/common.py', 'ds20_pending_confirmation_isolation/score.py'):
    files.add(ROOT / 'experiments' / relative)
files |= set((ROOT / 'experiments/ds32_z4q_depth_conflict_veto/source').glob('*.py'))
files |= {WORK / 'tools/depth_restoration/geometry.py', WORK / 'tools/depth_restoration/build_aligned_dataset.py',
          WORK / 'tools/sam3_depth_birth_inherit_20260917/features.py'}
files |= {Path(pin['path']) for pin in score.scoring_dependencies()}
code = {str(p.resolve()): sha(p) for p in sorted(files)}
import cv2, numpy, h5py, scipy
write_new(HERE / 'ENVIRONMENT.json', dict(python=sys.executable, version=sys.version, platform=platform.platform(),
    installed_versions=dict(opencv=cv2.__version__, numpy=numpy.__version__, h5py=h5py.__version__, scipy=scipy.__version__),
    runtime_binaries=[artifact(sys.executable), *[artifact(p) for p in Path(cv2.__file__).parent.glob('*.pyd')]],
    dependencies=str(DEPS), local_CPU_workers=2, library_threads_each=1,
    GPU=False, API=False, SAM3=False, training=False, completion=False))
write_new(HERE / 'RUNTIME_FREEZE.json', dict(base_commit=BASE, created_utc=datetime.now(timezone.utc).isoformat(),
    code=code, effective_config=CFG, actual_original_Z4Q_config=read(CONFIG_PATH),
    environment=artifact(HERE / 'ENVIRONMENT.json'),
    sensor_audit=artifact(HERE / 'SENSOR_AUDIT.json'), rgb_pins=artifact(HERE / 'RGB_INPUT_PINS.jsonl'),
    contract_review=artifact(HERE / 'NUMERIC_FLOW_CONTRACT_REVIEW.json'), checks=artifact(HERE / 'CHECKS_FINAL.json'),
    real_acceptance=artifact(HERE / 'REAL_ACCEPTANCE.json'), frames=20098, arms=ARMS,
    scoring_frozen_before_reference=True, no_parameter_search_after_freeze=True,
    future_policy='ONLY_UNPUBLISHED_30_FRAME_CACHE', new_model_http=0, cost_usd=0))
for name, (start, stop) in SEGMENTS.items():
    source = read(input_dir(name) / 'SOURCE_MANIFEST.json')
    assert source['no_GT'] and source['no_restored_values']
    for pin in source['derived_inputs'].values():
        verify_item(pin)
    for key in ('scan', 'raw_sources', 'field_access'):
        verify_item(source[key])
    archive = ROOT / 'experiments/ds32_z4q_depth_conflict_veto/run' / name / 'public'
    original_seal = read(archive / 'PREDICTIONS_SEALED.json')
    assert sha(archive / 'predictions.jsonl.gz') == original_seal['artifacts_sha256']['predictions.jsonl.gz']
    write_new(RUN / name / 'public/FREEZE.json', dict(status='FROZEN_BEFORE_PREDICTION', segment=name,
        frames=stop-start+1, arms=ARMS, code=code, source_chain=source,
        source_manifest=artifact(input_dir(name) / 'SOURCE_MANIFEST.json'),
        depth_cache=old.cache_reference(name), sensor_audit=artifact(HERE / 'SENSOR_AUDIT.json'),
        rgb_pins=artifact(HERE / 'RGB_INPUT_PINS.jsonl'), original_prediction=artifact(archive / 'predictions.jsonl.gz'),
        original_seal=artifact(archive / 'PREDICTIONS_SEALED.json'), runtime=artifact(HERE / 'RUNTIME_FREEZE.json'),
        no_GT_before_seal=True, RGB_authorized=True, future_limit_frames=30,
        new_model_http=0, cost_usd=0))
print('Frozen 8 actual RGB/raw-depth sources,4 branches,20098 frames; all scoring code pinned.', flush=True)
