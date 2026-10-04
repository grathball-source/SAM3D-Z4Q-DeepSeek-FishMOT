"""Freeze actual runtime dependencies, old sources and scoring before full prediction."""
from common import *
import sys,subprocess
from datetime import datetime,timezone
import runner,score,measurement,association

assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip()==BASE
assert not subprocess.check_output(['git','diff','--name-only'],cwd=ROOT).decode().strip()
assert not RUN.exists()
checks=sorted((HERE/'checks').glob('*.json'));assert read(checks[-1])['status']=='PASS'
for slice_name in ('slice_disabled','slice_real'):
    s=read(HERE/slice_name/'feeding_000000_000199/public/RUN_SUMMARY.json')
    assert s['frames']==200 and s['every_original_Z4Q_publication_exact'] and s['changed_frames']==0
bounded=read(HERE/'slice_bounded_pair/feeding_000351_000555/public/RUN_SUMMARY.json')
assert bounded['frames']==82 and bounded['every_original_Z4Q_publication_exact'] and bounded['checks']>0
assert bounded['measured_objects']>0 and bounded['private_cache_limit_bytes']==384*1024**2
postseal_only={'visualize.py','report.py','delivery.py'}
files={p for p in HERE.glob('*.py') if p.name not in postseal_only}|{HERE/'CONFIG.json',HERE/'PLAN.md',HERE/'README.md',CONFIG_PATH}
for m in list(sys.modules.values()):
    p=getattr(m,'__file__',None)
    if p and str(p).endswith('.py') and (str(Path(p).resolve()).lower().startswith(str(ROOT).lower()) or
        str(Path(p).resolve()).lower().startswith(str(WORK/'tools').lower())):files.add(Path(p).resolve())
files.update([ROOT/'experiments/ds17_mixed_depth_activity_repair/mixed_depth.py',
    ROOT/'experiments/ds12_contact_depth_admission/contact_measurement.py',
    ROOT/'experiments/ds22_local_background_depth/measurement.py',
    ROOT/'experiments/ds3_depth_foreground_filter/CONFIG.json',
    ROOT/'experiments/ds20_pending_confirmation_isolation/guard.py',Path(score.reference._math.__file__)])
code={str(p.resolve()):sha(p) for p in files}
runtime=dict(base_commit=BASE,created_utc=datetime.now(timezone.utc).isoformat(),
    code=code,actual_original_config=read(CONFIG_PATH),new_config=read(HERE/'CONFIG.json'),
    actual_background_and_layer_parameters=measurement.PARAMETERS,actual_association_parameters=association.CFG,
    actual_private_cache_limit_bytes=bounded['private_cache_limit_bytes'],
    bounded_real_prefix=artifact(HERE/'slice_bounded_pair/feeding_000351_000555/public/RUN_SUMMARY.json'),
    local_patch='Original seed expanded20px, fixed shape translated from previous qualified anonymous support centres; never expanded recursively',
    postseal_reporting_producers_not_runtime_inputs=sorted(postseal_only),
    relative_mro=[dict(class_name=c.__name__,source=str(sys.modules[c.__module__].__file__)) for c in runner.new_class_mro] if hasattr(runner,'new_class_mro') else
        [dict(class_name=c.__name__,source=str(sys.modules[c.__module__].__file__)) for c in runner.OrderBridge(read(CONFIG_PATH)).engine.__class__.__mro__ if c is not object],
    co_visibility_strategy_instantiated=False,source_original_rows=20098,new_model_http=0,cost_usd=0)
write_new(HERE/'RUNTIME_FREEZE.json',runtime)
for name in SEGMENTS:
    chain=read(input_dir(name)/'SOURCE_MANIFEST.json')
    assert chain['no_GT'] and chain['no_RGB'] and chain['no_restored_values']
    for item in chain['derived_inputs'].values():verify_item(item)
    for key in ('scan','raw_sources','field_access'):verify_item(chain[key])
    original_seal=ROOT/'experiments/ds20_pending_confirmation_isolation/run'/name/'public/PREDICTIONS_SEALED.json'
    oldseal=read(original_seal);original_prediction=original_seal.parent/'predictions.jsonl.gz'
    assert sha(original_prediction)==oldseal['artifacts_sha256']['predictions.jsonl.gz']
    write_new(RUN/name/'public/FREEZE.json',dict(status='FROZEN_BEFORE_PREDICTION',segment=name,arms=ARMS,
        code=code,source_manifest=artifact(input_dir(name)/'SOURCE_MANIFEST.json'),source_chain=chain,
        original_prediction=artifact(original_prediction),original_prediction_seal=artifact(original_seal),
        runtime=artifact(HERE/'RUNTIME_FREEZE.json'),no_GT_before_seal=True,new_model_http=0,cost_usd=0))
print('Frozen 8 segments, 20098 frames, three arms and original scoring',flush=True)
