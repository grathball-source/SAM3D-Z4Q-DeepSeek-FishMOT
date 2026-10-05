"""Pin effective science, source inventories and independent scoring before full replay."""
from common import *
import runner,score,measurement,association,increment_controller,subprocess,sys
from datetime import datetime,timezone
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip()==BASE
assert not subprocess.check_output(['git','diff','--name-only'],cwd=ROOT).decode().strip()
assert not RUN.exists()
assert read(sorted((HERE/'checks').glob('*.json'))[-1])['status']=='PASS'
for folder in ('slice_disabled','slice_real'):
    p=HERE/folder/'feeding_000000_000199/public';summary=read(p/'RUN_SUMMARY.json')
    assert summary['frames']==200 and summary['original_Z4Q_exact']
    assert read(p/'ACCESS.json')['status']=='NO_GT_RGB_RESTORED_NETWORK'
    if folder=='slice_disabled':assert summary['disabled'] and not any(summary['changed_frames'].values())
state=read(HERE/'slice_state_final/fishsa_development_8400/public/RUN_SUMMARY.json');assert state['frames']==4524 and state['original_Z4Q_exact']
assert read(HERE/'REAL_STATE_ACCEPTANCE.json')['status']=='PASS_ACTUAL_NULL_STATE_AND_PUBLICATION_CHECKS'
assert read(HERE/'SHARED_SOURCE_DIAGNOSIS.json')['status']=='PASS_ACTUAL_SHARED_SOURCE_REMEASUREMENT_CONTRACT'
files={p for p in HERE.glob('*.py')}|{HERE/'PLAN.md',HERE/'README.md',HERE/'CONFIG.json',CONFIG_PATH}
for m in list(sys.modules.values()):
    p=getattr(m,'__file__',None)
    if p and p.endswith('.py') and (str(Path(p).resolve()).lower().startswith(str(ROOT).lower()) or str(Path(p).resolve()).lower().startswith(str(WORK/'tools').lower())):files.add(Path(p).resolve())
for p in ['ds20_pending_confirmation_isolation/guard.py','ds25_contact_local_layers/measurement.py','ds22_local_background_depth/measurement.py',
    'ds17_mixed_depth_activity_repair/mixed_depth.py','ds12_contact_depth_admission/contact_measurement.py','ds3_depth_foreground_filter/CONFIG.json',
    'ds16_relative_depth_order/source.py','ms1_s0_development_8400/CONFIG_V7.json']:
    files.add(ROOT/'experiments'/p)
code={str(p.resolve()):sha(p) for p in sorted(files)}
write_new(HERE/'RUNTIME_FREEZE.json',dict(base_commit=BASE,created_utc=datetime.now(timezone.utc).isoformat(),code=code,
    actual_joint_parameters=association.CFG,original_effective_config=read(CONFIG_PATH),
    effective_measurement_parameters={a:measurement.Measurement(p).PARAMETERS for a,p in VARIANTS.items()},
    original_scanner_thresholds={n:read(input_dir(n)/'scan_v4.json')['thresholds'] for n in SEGMENTS},
    preflight_checks=artifact(sorted((HERE/'checks').glob('*.json'))[-1]),source_rows=20098,arms=ARMS,
    scoring_frozen_before_reference=True,no_late_parameter_adaptation=True,new_model_http=0,cost_usd=0))
for name in SEGMENTS:
    chain=read(input_dir(name)/'SOURCE_MANIFEST.json');assert chain['no_GT'] and chain['no_RGB'] and chain['no_restored_values']
    for item in chain['derived_inputs'].values():verify_item(item)
    for key in ('scan','raw_sources','field_access'):verify_item(chain[key])
    old=ROOT/'experiments/ds28_risk_driven_depth_entry/run'/name/'public'
    assert sha(old/'predictions.jsonl.gz')==read(old/'PREDICTIONS_SEALED.json')['artifacts_sha256']['predictions.jsonl.gz']
    write_new(RUN/name/'public/FREEZE.json',dict(status='FROZEN_BEFORE_PREDICTION',segment=name,arms=ARMS,code=code,
        source_manifest=artifact(input_dir(name)/'SOURCE_MANIFEST.json'),source_chain=chain,
        original_prediction=artifact(old/'predictions.jsonl.gz'),original_prediction_seal=artifact(old/'PREDICTIONS_SEALED.json'),
        runtime=artifact(HERE/'RUNTIME_FREEZE.json'),no_GT_before_seal=True,new_model_http=0,cost_usd=0))
print('Frozen eight segments, three branches, 20098 frames',flush=True)
