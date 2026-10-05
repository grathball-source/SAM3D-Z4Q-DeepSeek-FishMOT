"""Immutable code/effective constants/source/metric plan before full prediction."""
from common import *
import runner,score,identity,depth,subprocess,sys,platform
from datetime import datetime,timezone
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip()==BASE
assert not subprocess.check_output(['git','diff','--name-only'],cwd=ROOT).decode().strip()
assert not RUN.exists()
check=sorted((HERE/'checks').glob('CHECKS_*.json'))[-1];assert read(check)['status']=='PASS'
slice_path=HERE/'slice_acceptance/feeding_000000_000199/public';summary=read(slice_path/'RUN_SUMMARY.json')
assert summary['frames']==200 and summary['original_Z4Q_exact']
assert read(slice_path/'ACCESS.json')['status']=='NO_GT_RGB_RESTORED_NETWORK'
files={p for p in HERE.glob('*.py')}|{HERE/'PLAN.md',HERE/'README.md',HERE/'CONFIG.json',CONFIG_PATH}
for m in list(sys.modules.values()):
    p=getattr(m,'__file__',None)
    if p and p.endswith('.py') and any(str(Path(p).resolve()).lower().startswith(str(x).lower()) for x in (ROOT,WORK/'tools')):files.add(Path(p).resolve())
files.add(DS1/'depth_state.py');files.add(ROOT/'experiments/ds20_pending_confirmation_isolation/guard.py')
files.add(ROOT/'experiments/ds18_association_evidence_interface_repair/mixed_depth.py')
code={str(p.resolve()):sha(p) for p in sorted(files)}
write_new(HERE/'RUNTIME_FREEZE.json',dict(base_commit=BASE,created_utc=datetime.now(timezone.utc).isoformat(),code=code,
    effective_identity_config=identity.CFG,effective_depth=dict(weight=depth.DEPTH_WEIGHT,history_seconds=depth.HISTORY_SECONDS,
        scale_floor_mm=depth.SCALE_FLOOR_MM,max_measured_scale_mm=depth.MAX_MEASURED_SCALE_MM,predict_unchanged_DS1=artifact(DS1/'depth_state.py')),
    original_Z4Q_config=read(CONFIG_PATH),preflight=artifact(check),real_slice=artifact(slice_path/'RUN_SUMMARY.json'),
    source_rows=20098,arms=ARMS,scoring_frozen_before_reference=True,no_late_parameter_adaptation=True,model_http=0,cost_usd=0))
for name in SEGMENTS:
    chain=read(input_dir(name)/'SOURCE_MANIFEST.json');assert chain['no_GT'] and chain['no_RGB'] and chain['no_restored_values']
    for item in chain['derived_inputs'].values():verify_item(item)
    for key in ('scan','raw_sources','field_access'):verify_item(chain[key])
    mixed=old.cache_reference(name);original=ROOT/'experiments/ds30_original_z4q_depth_increment/run'/name/'public'
    assert sha(original/'predictions.jsonl.gz')==read(original/'PREDICTIONS_SEALED.json')['artifacts_sha256']['predictions.jsonl.gz']
    write_new(RUN/name/'public/FREEZE.json',dict(status='FROZEN_BEFORE_PREDICTION',segment=name,arms=ARMS,code=code,
        source_chain=chain,source_manifest=artifact(input_dir(name)/'SOURCE_MANIFEST.json'),depth_cache=mixed,
        original_prediction=artifact(original/'predictions.jsonl.gz'),original_seal=artifact(original/'PREDICTIONS_SEALED.json'),
        runtime=artifact(HERE/'RUNTIME_FREEZE.json'),no_GT_before_seal=True,model_http=0,cost_usd=0))
write_new(HERE/'ENVIRONMENT.json',dict(python=sys.executable,version=sys.version,platform=platform.platform(),deps=str(DEPS),
    local_CPU_workers=2,threads_each=1,GPU=False,API=False,SAM3=False,training=False,completion=False))
print('Frozen eight sources, four branches,20098 frames',flush=True)
