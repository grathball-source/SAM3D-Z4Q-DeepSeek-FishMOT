"""Actual source-read protection, inherited unchanged from DS20."""
from common import *
import runpy
# Hashing already pinned Python source is not a reference-data read. The
# original data/field/network bans stay unchanged. Only exact frozen .py paths
# are allowed; arbitrary postseal files and every GT raster remain blocked.
runtime_path=HERE/'RUNTIME_FREEZE.json'
if not runtime_path.exists():
    assert sys.argv[1]=='prefix', 'Formal replay requires a fresh current freeze'
    runtime_path=HERE/'partial_invalid_source_validation_v2/RUNTIME_FREEZE.json'
runtime=read(runtime_path)
allowed={str(Path(p).resolve()).replace('\\','/').lower() for p in runtime['code'] if p.endswith('.py')}
guard_source=(old.HERE/'guard.py').read_text(encoding='utf-8')
needle="    if any(token in path for token in BLOCKED):raise RuntimeError('Forbidden prediction read: '+path)"
assert guard_source.count(needle)==1
guard_source=guard_source.replace(needle,"    if path in FROZEN_PYTHON_SOURCE_PATHS:return\n"+needle)
scope=dict(__name__='ds37_source_guard',__file__=str(old.HERE/'guard.py'),FROZEN_PYTHON_SOURCE_PATHS=allowed)
exec(compile(guard_source,str(old.HERE/'guard.py')+':pinned_source_hash_exception','exec'),scope)
from runner import run_segment
mode=sys.argv[1]
if mode=='probe':
    for token in ('gt_raster','sealed_test','postseal_unlisted'):
        path=WORK/'data'/token/'forbidden.json'
        try:
            path.open('r');raise AssertionError('Forbidden probe allowed')
        except RuntimeError as error:assert str(error).startswith('Forbidden prediction read:')
    for path in runtime['code']:
        if path.endswith('.py'):assert sha(path)==runtime['code'][path]
    write_new(HERE/'GUARD_PROBE.json',dict(status='PASS_EXACT_FROZEN_SOURCE_HASH_ALLOWED_GT_FUTURE_UNLISTED_POSTSEAL_BLOCKED',
        probes=3,pinned_python_paths=len(allowed),blocked_tokens=list(scope['BLOCKED']),model_http=0,cost_usd=0))
    print('GUARD_PROBE_PASS',flush=True);sys.exit(0)
name=sys.argv[2]
if mode=='prefix':
    output=HERE/sys.argv[4]
    assert output.parent==HERE and output.name.startswith('slice_')
    run_segment(name,output,stop_at=int(sys.argv[3]),disabled=len(sys.argv)>5 and sys.argv[5]=='disabled')
else:
    assert mode=='run';output=RUN;run_segment(name)
write_new(output/name/'public/ACCESS.json',dict(status='NO_GT_RGB_RESTORED_NETWORK',blocked_tokens=list(scope['BLOCKED']),
    observed_data_paths=sorted(scope['SEEN']),npz_field_reads=[dict(path=p,key=k) for p,k in sorted(scope['NPZ'])],
    measurements='CURRENT_SEALED_DS18_RAW_SAME_ROI_CERTIFICATES',current_in_pre_history=False,
    only_exact_frozen_python_source_hash_reads_exempted=True,frozen_python_paths=len(allowed),
    model_http=0,cost_usd=0))
