"""One immutable science freeze before all eight real trials and reference scoring."""
from common import *
import runner,score,subprocess,platform
from datetime import datetime,timezone

assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip()==BASE
assert not subprocess.check_output(['git','diff','--name-only'],cwd=ROOT).decode().strip()
assert not RUN.exists(),'Do not replace any formal output'
checks=read(HERE/'CHECKS_FINAL.json');assert checks['status']=='PASS'
for pin in checks['artifacts']:verify_item(pin)
acceptance=read(HERE/'REAL_ACCEPTANCE.json');assert acceptance['status']=='PASS'
for pin in acceptance['artifacts']:verify_item(pin)
prior=ROOT/'experiments/ds33_rgbd_fixed_lag'
audit=read(prior/'SENSOR_AUDIT.json');assert audit['frames']==20098
for item in audit['actual_rgb_inputs']+audit['actual_raw_containers']+audit['actual_calibrations']:verify_item(item)
files=set(HERE.glob('*.py'))|{HERE/'CONFIG.json',HERE/'PLAN.md',HERE/'README.md',HERE/'DATA_CONTRACT.md',CONFIG_PATH}
for m in list(sys.modules.values()):
    path=getattr(m,'__file__',None)
    if path and path.endswith('.py') and any(str(Path(path).resolve()).lower().startswith(str(r).lower()) for r in (ROOT,WORK/'tools')):files.add(Path(path))
for relative in ('ds14_raw_multidataset/common.py','ds14_raw_multidataset/source.py','ds12_contact_depth_admission/contact_measurement.py',
    'ds31_persistent_identity_depth/depth.py','ds33_rgbd_fixed_lag/evidence.py','ds1_depth_only/depth_state.py',
    'ds20_pending_confirmation_isolation/common.py','ds1_depth_only/postseal.py','ds14_raw_multidataset/evaluate.py'):
    files.add(ROOT/'experiments'/relative)
files|={WORK/'tools/depth_restoration/geometry.py',WORK/'tools/depth_restoration/build_aligned_dataset.py',
    WORK/'tools/sam3_depth_birth_inherit_20260917/features.py'}
files|={Path(p['path']) for p in score.scoring_dependencies()}
code={str(p.resolve()):sha(p) for p in sorted(files)}
import cv2,numpy,h5py,scipy
write_new(HERE/'ENVIRONMENT.json',dict(python=sys.executable,version=sys.version,platform=platform.platform(),
    installed_versions=dict(opencv=cv2.__version__,numpy=numpy.__version__,h5py=h5py.__version__,scipy=scipy.__version__),
    runtime_binaries=[artifact(sys.executable),*[artifact(p) for p in Path(cv2.__file__).parent.glob('*.pyd')]],
    dependencies=str(DEPS),local_CPU_workers=2,library_threads_each=1,GPU=False,API=False,training=False,SAM3=False,completion=False))
write_new(HERE/'RUNTIME_FREEZE.json',dict(base_commit=BASE,created_utc=datetime.now(timezone.utc).isoformat(),code=code,
    effective_config=CFG,actual_original_Z4Q_config=read(CONFIG_PATH),environment=artifact(HERE/'ENVIRONMENT.json'),
    actual_safety_constants=dict(fallback_continuity_min_clean_count=5,reference_mask_min_area=64,
        original_merge_confirmation_frames=2,original_split_mask_coverage=0.15,original_split_area_fraction=0.6),
    checks=artifact(HERE/'CHECKS_FINAL.json'),real_acceptance=artifact(HERE/'REAL_ACCEPTANCE.json'),
    reused_sensor_audit=artifact(prior/'SENSOR_AUDIT.json'),reused_rgb_pins=artifact(prior/'RGB_INPUT_PINS.jsonl'),
    sparse_RGB_access='FIXED_PRE_POST_ENDPOINTS_ONLY_WITH_ACQUIRED_PAST_BOUND',frames=20098,arms=ARMS,
    scoring_frozen_before_reference=True,no_parameter_search_after_freeze=True,new_model_http=0,cost_usd=0))
for name,(start,stop) in SEGMENTS.items():
    source=read(input_dir(name)/'SOURCE_MANIFEST.json');assert source['no_GT'] and source['no_restored_values']
    for pin in source['derived_inputs'].values():verify_item(pin)
    for key in ('scan','raw_sources','field_access'):verify_item(source[key])
    archive=prior/'run'/name/'public';seal=read(archive/'PREDICTIONS_SEALED.json')
    assert sha(archive/'predictions.jsonl.gz')==seal['artifacts_sha256']['predictions.jsonl.gz']
    write_new(RUN/name/'public/FREEZE.json',dict(status='FROZEN_BEFORE_PREDICTION',segment=name,frames=stop-start+1,
        arms=ARMS,code=code,source_chain=source,source_manifest=artifact(input_dir(name)/'SOURCE_MANIFEST.json'),
        depth_cache=old.cache_reference(name),sensor_audit=artifact(prior/'SENSOR_AUDIT.json'),rgb_pins=artifact(prior/'RGB_INPUT_PINS.jsonl'),
        original_prediction=artifact(archive/'predictions.jsonl.gz'),original_seal=artifact(archive/'PREDICTIONS_SEALED.json'),
        runtime=artifact(HERE/'RUNTIME_FREEZE.json'),no_GT_before_seal=True,RGB_authorized=True,future_limit_frames=30,
        new_model_http=0,cost_usd=0))
print('DS34 all 8 sources / 4 branches / 20098 frames frozen before prediction',flush=True)
