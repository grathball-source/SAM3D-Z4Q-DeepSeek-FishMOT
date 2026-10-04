"""Freeze effective parameters, all runtime/source/scoring files before prediction."""
from common import *
from datetime import datetime,timezone
import subprocess,sys
import runner,score,measurement,evidence,soft_controller

assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip()==BASE
assert not subprocess.check_output(['git','diff','--name-only'],cwd=ROOT).decode().strip()
assert not RUN.exists()
check=read(sorted((HERE/'checks').glob('*.json'))[-1]);assert check['status']=='PASS'
disabled=read(HERE/'slice_disabled/feeding_000000_000199/public/RUN_SUMMARY.json')
real=read(HERE/'slice_real/feeding_000351_000555/public/RUN_SUMMARY.json')
assert disabled['frames']==200 and disabled['disabled_evidence'] and not any(disabled['changed_frames'].values())
assert real['frames']==205 and real['every_original_Z4Q_publication_exact']
postseal={'visualize.py','report.py','delivery.py','review.py'}
files={p for p in HERE.rglob('*.py') if p.name not in postseal}|{HERE/'CONFIG.json',HERE/'CALIBRATION.json',HERE/'PLAN.md',HERE/'README.md',CONFIG_PATH}
for m in list(sys.modules.values()):
    p=getattr(m,'__file__',None)
    if p and str(p).endswith('.py') and (str(Path(p).resolve()).lower().startswith(str(ROOT).lower()) or str(Path(p).resolve()).lower().startswith(str(WORK/'tools').lower())):
        files.add(Path(p).resolve())
for p in ['ds25_contact_local_layers/measurement.py','ds22_local_background_depth/measurement.py','ds17_mixed_depth_activity_repair/mixed_depth.py',
          'ds12_contact_depth_admission/contact_measurement.py','ds3_depth_foreground_filter/CONFIG.json','ds20_pending_confirmation_isolation/guard.py',
          'ds16_relative_depth_order/source.py']:
    files.add(ROOT/'experiments'/p)
files.add(Path(score.reference._math.__file__))
code={str(p.resolve()):sha(p) for p in sorted(files)}
write_new(HERE/'RUNTIME_FREEZE.json',dict(base_commit=BASE,created_utc=datetime.now(timezone.utc).isoformat(),code=code,
    new_config=read(HERE/'CONFIG.json'),original_effective_config=read(CONFIG_PATH),
    effective_measurement_parameters={a:measurement.Measurement(p).PARAMETERS for a,p in VARIANTS.items()},
    actual_soft_parameters=soft_controller.CFG,calibration=artifact(HERE/'CALIBRATION.json'),
    source_old_parameters_readonly=True,scoring_frozen_before_GT=True,source_rows=20098,arms=ARMS,
    controller_mro=[dict(class_name=c.__name__,file=str(sys.modules[c.__module__].__file__)) for c in runner.SoftBridge(read(CONFIG_PATH)).engine.__class__.__mro__ if c is not object],
    no_late_parameter_adaptation=True,new_model_http=0,cost_usd=0))
for name in SEGMENTS:
    chain=read(input_dir(name)/'SOURCE_MANIFEST.json');assert chain['no_GT'] and chain['no_RGB'] and chain['no_restored_values']
    for item in chain['derived_inputs'].values():verify_item(item)
    for key in ('scan','raw_sources','field_access'):verify_item(chain[key])
    original=ROOT/'experiments/ds20_pending_confirmation_isolation/run'/name/'public'
    assert sha(original/'predictions.jsonl.gz')==read(original/'PREDICTIONS_SEALED.json')['artifacts_sha256']['predictions.jsonl.gz']
    write_new(RUN/name/'public/FREEZE.json',dict(status='FROZEN_BEFORE_PREDICTION',segment=name,arms=ARMS,code=code,
        source_manifest=artifact(input_dir(name)/'SOURCE_MANIFEST.json'),source_chain=chain,
        original_prediction=artifact(original/'predictions.jsonl.gz'),original_prediction_seal=artifact(original/'PREDICTIONS_SEALED.json'),
        runtime=artifact(HERE/'RUNTIME_FREEZE.json'),no_GT_before_seal=True,new_model_http=0,cost_usd=0))
print('Frozen eight segments / six branches / 20098 frames before replay and scoring',flush=True)
