"""Freeze all science, source chains and independent scoring before full replay."""
from common import *
import runner,score,subprocess,sys,platform
from datetime import datetime,timezone
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip()==BASE
assert not subprocess.check_output(['git','diff','--name-only'],cwd=ROOT).decode().strip()
assert not RUN.exists()
check=HERE/'CHECKS_FINAL.json';assert read(check)['status']=='PASS'
accept=read(HERE/'REAL_ACCEPTANCE.json');assert accept['status']=='PASS_SOURCE_STATE_PUBLICATION_REGRESSIONS'
for pin in accept['artifacts']:verify_item(pin)
review=read(HERE/'CONTRACT_REVIEW_READY.json');assert review['status']=='PASS'
for pin in review['reviewed_artifacts'].values():verify_item(pin)
files={p for p in HERE.rglob('*.py') if not {'__pycache__','private'}&set(p.relative_to(HERE).parts)}
files|={HERE/'PLAN.md',HERE/'README.md',HERE/'CONFIG.json',CONFIG_PATH}
files|={old.HERE/'CONFIG.json',old.OLD/'score.py'}
for m in list(sys.modules.values()):
    path=getattr(m,'__file__',None)
    if path and path.endswith('.py') and any(str(Path(path).resolve()).lower().startswith(str(x).lower()) for x in (ROOT,WORK/'tools')):files.add(Path(path).resolve())
for path in ('ds1_depth_only/depth_state.py','ds20_pending_confirmation_isolation/common.py','ds20_pending_confirmation_isolation/guard.py',
    'ds31_persistent_identity_depth/depth.py','ds14_raw_multidataset/evaluate.py'):
    files.add(ROOT/'experiments'/path)
code={str(p.resolve()):sha(p) for p in sorted(files)}
write_new(HERE/'RUNTIME_FREEZE.json',dict(base_commit=BASE,created_utc=datetime.now(timezone.utc).isoformat(),code=code,
    effective_depth_config=CFG,original_Z4Q_config=read(CONFIG_PATH),effective_depth_math=artifact(DS1/'depth_state.py'),
    actual_hook_adaptation=artifact(HERE/'source/ADAPTATION.json'),preflight=artifact(check),acceptance=artifact(HERE/'REAL_ACCEPTANCE.json'),
    source_rows=20098,arms=ARMS,scoring_frozen_before_reference=True,no_late_parameter_adaptation=True,model_http=0,cost_usd=0))
for n in SEGMENTS:
    chain=read(input_dir(n)/'SOURCE_MANIFEST.json');assert chain['no_GT'] and chain['no_RGB'] and chain['no_restored_values']
    for pin in chain['derived_inputs'].values():verify_item(pin)
    for key in ('scan','raw_sources','field_access'):verify_item(chain[key])
    mixed=old.cache_reference(n);original=ROOT/'experiments/ds31_persistent_identity_depth/run'/n/'public'
    assert sha(original/'predictions.jsonl.gz')==read(original/'PREDICTIONS_SEALED.json')['artifacts_sha256']['predictions.jsonl.gz']
    write_new(RUN/n/'public/FREEZE.json',dict(status='FROZEN_BEFORE_PREDICTION',segment=n,arms=ARMS,code=code,
        source_chain=chain,source_manifest=artifact(input_dir(n)/'SOURCE_MANIFEST.json'),depth_cache=mixed,
        original_prediction=artifact(original/'predictions.jsonl.gz'),original_seal=artifact(original/'PREDICTIONS_SEALED.json'),
        runtime=artifact(HERE/'RUNTIME_FREEZE.json'),no_GT_before_seal=True,model_http=0,cost_usd=0))
write_new(HERE/'ENVIRONMENT.json',dict(python=sys.executable,version=sys.version,platform=platform.platform(),deps=str(DEPS),
    local_CPU_workers=2,threads_each=1,GPU=False,API=False,SAM3=False,training=False,completion=False))
print('Frozen eight sources, three branches,20098 frames; one source-selected counterfactual if available.',flush=True)
