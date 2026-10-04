"""Freeze the full fixed cohort, real source and actual measurement/scoring code."""
from common import *
from datetime import datetime,timezone
import subprocess, measure, measurement_adapter, source

assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip()==BASE
assert not subprocess.check_output(['git','diff','--name-only'],cwd=ROOT).decode().strip()
assert not RUN.exists()
assert read(HERE/'TEST_RESULTS.json')['status']=='PASS'
slice_summary=read(HERE/'slice_real/SUMMARY.json')
assert slice_summary['contexts']==slice_summary['logical_pairs']==1 and slice_summary['post_pairs']==1
cohort=read(HERE/'COHORT.json');inputs=cohort['source_artifacts']+[artifact(HERE/'COHORT.json'),artifact(HERE/'COHORT_REVIEW.json'),artifact(HERE/'TEST_RESULTS.json'),artifact(HERE/'slice_real/MEASUREMENTS_SEALED.json')]
sources={}
for name in SEGMENTS:
    path=input_dir(name)/'SOURCE_MANIFEST.json';manifest=read(path)
    assert manifest['no_GT'] and manifest['no_RGB'] and manifest['no_restored_values']
    sources[name]=manifest;inputs.append(artifact(path))
    inputs.extend(manifest['derived_inputs'].values());inputs.append(manifest['raw_sources'])
for item in inputs:verify_item(item)
files={p for p in HERE.glob('*.py') if p.name not in {'visualize.py','delivery.py','report.py'}}|{HERE/'CONFIG.json',HERE/'PLAN.md',HERE/'README.md'}
for m in list(sys.modules.values()):
    path=getattr(m,'__file__',None)
    if path and str(path).endswith('.py'):
        p=Path(path).resolve()
        if p.is_relative_to(ROOT) or p.is_relative_to(WORK/'tools'):files.add(p)
files.update({DS25/'review.py',ROOT/'experiments/ds20_pending_confirmation_isolation/guard.py',ROOT/'experiments/ds3_depth_foreground_filter/CONFIG.json'})
write_new(HERE/'FREEZE.json',dict(base_commit=BASE,created_utc=datetime.now(timezone.utc).isoformat(),
    code={str(p.resolve()):sha(p) for p in sorted(files)},inputs=inputs,source_manifests=sources,
    actual_measurement_parameters=PARAMETERS,actual_config=read(HERE/'CONFIG.json'),
    cohort_selection=cohort['selection'],real_slice=artifact(HERE/'slice_real/SUMMARY.json'),
    frozen_judgment=artifact(HERE/'PLAN.md'),tracking_identity_transactions='NOT_EXECUTED',
    new_model_http=0,cost_usd=0))
print('Frozen actual measurement code, 15 contexts / 532 logical pairs, thresholds and raw sources')
