"""Freeze causal policy, actual constants, source chains and every scorer input."""
from common import *
import runner, score, visuals, postseal, subprocess, platform, shutil
from evidence import ADAPTATION
from datetime import datetime,timezone
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip()==BASE
changed=set(subprocess.check_output(['git','diff','--name-only'],cwd=ROOT).decode().splitlines())
assert changed<= {'.gitignore'},changed
assert not RUN.exists()
assert read(HERE/'CHECKS_FINAL_V2.json')['status']=='PASS'
accept=read(HERE/'REAL_ACCEPTANCE.json');assert accept['no_GT_read']
for pin in accept['artifacts']:verify_item(pin)
available=shutil.disk_usage(HERE).free;assert available>1_000_000_000,available
files={p for p in HERE.glob('*.py')}|{HERE/'PLAN.md',HERE/'README.md',HERE/'CONFIG.json',CONFIG_PATH,
    OLD32.HERE/'CONFIG.json',OLD32.HERE/'source/ADAPTATION.json',old.HERE/'CONFIG.json',old.OLD/'score.py',
    DS1/'postseal.py',DS1/'depth_state.py',DS14/'evaluate.py',old.HERE/'guard.py'}
for m in list(sys.modules.values()):
    path=getattr(m,'__file__',None)
    if path and path.endswith('.py') and any(str(Path(path).resolve()).lower().startswith(str(x).lower()) for x in (ROOT,WORK/'tools')):files.add(Path(path).resolve())
# importlib-loaded helpers do not always register in sys.modules.
for directory in (OLD32.HERE,old.HERE,DS14,ROOT/'experiments/ds31_persistent_identity_depth',
    ROOT/'experiments/ds34_bidirectional_event_restore'):
    files.update(directory.glob('*.py'))
files.update((OLD32.HERE/'source').glob('*.py'))
code={str(p.resolve()):sha(p) for p in sorted(files)}
write_new(HERE/'RUNTIME_FREEZE.json',dict(base_commit=BASE,created_utc=datetime.now(timezone.utc).isoformat(),code=code,
    effective_depth_config=CFG,original_Z4Q_config=read(CONFIG_PATH),query_adapter=ADAPTATION,
    original_hook_adaptation=artifact(OLD32.HERE/'source/ADAPTATION.json'),checks=artifact(HERE/'CHECKS_FINAL_V2.json'),
    real_acceptance=artifact(HERE/'REAL_ACCEPTANCE.json'),source_rows=20098,arms=ARMS,
    scoring_frozen_before_reference=True,dynamic_clear_math=artifact(DS1/'postseal.py'),
    no_late_parameter_adaptation=True,model_http=0,cost_usd=0))
for name in SEGMENTS:
    chain=read(input_dir(name)/'SOURCE_MANIFEST.json')
    assert chain['no_GT'] and chain['no_RGB'] and chain['no_restored_values']
    for pin in chain['derived_inputs'].values():verify_item(pin)
    for key in ('scan','raw_sources','field_access'):verify_item(chain[key])
    archived=ROOT/'experiments/ds31_persistent_identity_depth/run'/name/'public'
    mixed=old.cache_reference(name)
    write_new(RUN/name/'public/FREEZE.json',dict(status='FROZEN_BEFORE_PREDICTION',segment=name,arms=ARMS,code=code,
        source_chain=chain,source_manifest=artifact(input_dir(name)/'SOURCE_MANIFEST.json'),depth_cache=mixed,
        original_prediction=artifact(archived/'predictions.jsonl.gz'),original_seal=artifact(archived/'PREDICTIONS_SEALED.json'),
        archived_WLS_prediction=artifact(OLD32.RUN/name/'public/predictions.jsonl.gz'),
        archived_WLS_transaction=artifact(OLD32.RUN/name/'public/TRANSACTIONS.jsonl.gz'),
        archived_WLS_seal=artifact(OLD32.RUN/name/'public/PREDICTIONS_SEALED.json'),
        runtime=artifact(HERE/'RUNTIME_FREEZE.json'),no_GT_before_seal=True,model_http=0,cost_usd=0))
write_new(HERE/'ENVIRONMENT.json',dict(python=sys.executable,version=sys.version,platform=platform.platform(),deps=str(DEPS),
    local_CPU_workers=2,threads_each=1,disk_free_bytes_before_start=available,GPU=False,API=False,SAM3=False,
    training=False,completion=False,scope='Same eight already exposed segments; L3/LW weak references separately reported'))
print('FROZEN_FOUR_BRANCHES_EIGHT_SOURCES_20098_FRAMES',len(code),flush=True)
