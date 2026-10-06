"""Freeze code, actual constants, source and scoring before formal predictions."""
from common import *
import runner,score,subprocess,platform
from datetime import datetime,timezone
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip()==BASE
assert not subprocess.check_output(['git','diff','--name-only'],cwd=ROOT).decode().strip()
assert not RUN.exists(),'No output replacement'
for file in ('CHECKS_FINAL.json','CHECKS_SCORE.json','CHECKS_EMPTY.json','CHECKS_ORIGINAL.json','REAL_ACCEPTANCE.json'):assert read(HERE/file)['status']=='PASS'
for p in read(HERE/'REAL_ACCEPTANCE.json')['artifacts']:verify_item(p)
files=set(HERE.glob('*.py'))|{HERE/'CONFIG.json',HERE/'PLAN.md',HERE/'README.md',HERE/'DATA_CONTRACT.md',CONFIG_PATH}
for m in list(sys.modules.values()):
    path=getattr(m,'__file__',None)
    if path and path.endswith('.py') and any(str(Path(path).resolve()).lower().startswith(str(r).lower()) for r in (ROOT,WORK/'tools')):files.add(Path(path))
files|={PRIOR/f for f in ('common.py','history.py','manager.py','lag.py','evidence.py','score.py')}
files|={Path(p['path']) for p in score.scoring_dependencies()}
code={str(p.resolve()):sha(p) for p in sorted(files)}
import cv2,numpy,h5py,scipy
write_new(HERE/'ENVIRONMENT.json',dict(python=sys.executable,version=sys.version,platform=platform.platform(),
    installed_versions=dict(opencv=cv2.__version__,numpy=numpy.__version__,h5py=h5py.__version__,scipy=scipy.__version__),
    runtime_binaries=[artifact(sys.executable),*[artifact(p) for p in Path(cv2.__file__).parent.glob('*.pyd')]],
    dependencies=str(DEPS),local_CPU_workers=2,library_threads_each=1,GPU=False,API=False,training=False,SAM3=False,completion=False))
write_new(HERE/'RUNTIME_FREEZE.json',dict(base_commit=BASE,created_utc=datetime.now(timezone.utc).isoformat(),code=code,
    effective_config=CFG,actual_original_Z4Q_config=read(CONFIG_PATH),environment=artifact(HERE/'ENVIRONMENT.json'),
    checks=[artifact(HERE/f) for f in ('CHECKS_FINAL.json','CHECKS_SCORE.json','CHECKS_EMPTY.json','CHECKS_ORIGINAL.json','REAL_ACCEPTANCE.json')],
    actual_original_event_constants=dict(merge_confirm_frames=2,split_mask_coverage=.15,split_area_fraction=.6,emerging_tolerance_px=8),
    actual_depth_constants=dict(weight=.25,sample_min=16,fraction_min=.2,measurement_scale_floor_mm=15.,measurement_scale_cap_mm=60.,forecast_min_history=3,forecast_scale_cap_mm=60.),
    frames=20098,arms=ARMS,scoring_frozen_before_reference=True,no_parameter_search_after_freeze=True,new_model_http=0,cost_usd=0))
for name,(start,stop) in SEGMENTS.items():
    source=read(input_dir(name)/'SOURCE_MANIFEST.json');assert source['no_GT'] and source['no_restored_values']
    for pin in source['derived_inputs'].values():verify_item(pin)
    for key in ('scan','raw_sources','field_access'):verify_item(source[key])
    archive=PRIOR/'run'/name/'public';seal=read(archive/'PREDICTIONS_SEALED.json')
    assert sha(archive/'predictions.jsonl.gz')==seal['artifacts_sha256']['predictions.jsonl.gz']
    old.verify_cache_reference(old.cache_reference(name))
    write_new(RUN/name/'public/FREEZE.json',dict(status='FROZEN_BEFORE_PREDICTION',segment=name,frames=stop-start+1,arms=ARMS,
        code=code,source_chain=source,source_manifest=artifact(input_dir(name)/'SOURCE_MANIFEST.json'),depth_cache=old.cache_reference(name),
        original_prediction=artifact(archive/'predictions.jsonl.gz'),original_seal=artifact(archive/'PREDICTIONS_SEALED.json'),
        original_transactions=artifact(archive/'TRANSACTIONS.jsonl.gz'),
        runtime=artifact(HERE/'RUNTIME_FREEZE.json'),no_GT_before_seal=True,RGB_for_association=False,future_limit_frames=30,new_model_http=0,cost_usd=0))
print('DS35 eight exact sources / 20098 frames frozen before formal prediction.',flush=True)
