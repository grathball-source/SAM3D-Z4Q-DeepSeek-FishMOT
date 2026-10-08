"""Small read-only adapter to the original E-volume sources, F-volume outputs."""
from pathlib import Path
import os, sys, json, gzip, hashlib, importlib.util, subprocess
from datetime import datetime, timezone
os.environ.update(PYTHONDONTWRITEBYTECODE='1', CUDA_VISIBLE_DEVICES='',
                  OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1', NUMEXPR_NUM_THREADS='1')
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ORIGINAL = Path('E:/CAU/SAM3D-Z4Q-DeepSeek-FishMOT')
DS37 = ORIGINAL/'experiments/ds37_causal_level_depth_veto'
BASE = '4163d007d9a030999a6c1f027f0bf50943787061'

def module(name, path, common=None):
    saved = sys.modules.get('common')
    try:
        if common is not None: sys.modules['common'] = common
        spec = importlib.util.spec_from_file_location(name, path)
        result = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(result)
        return result
    finally:
        if saved is None: sys.modules.pop('common', None)
        else: sys.modules['common'] = saved

BOOTSTRAP = module('ds38_readonly_ds35', ORIGINAL/'experiments/ds35_authoritative_z4q_depth/common.py')
LEGACY = module('ds38_readonly_ds36', ORIGINAL/'experiments/ds36_local_depth_evidence_audit/common.py', BOOTSTRAP)
M = module('ds38_readonly_measurement', LEGACY.HERE/'measurement.py', LEGACY)
ARCHIVE = module('ds38_readonly_ds37', DS37/'common.py')
read, rows, sha, artifact, verify_item, write_new, input_dir = (
    getattr(LEGACY, x) for x in ('read','rows','sha','artifact','verify_item','write_new','input_dir'))
digest = ARCHIVE.digest  # Frozen engine state contains sets and numeric scalars.
SOURCE, MEASUREMENT = LEGACY.SOURCE, LEGACY.MEASUREMENT
SEGMENTS = {k:v for k,v in LEGACY.SEGMENTS.items() if k.startswith('feeding_')}
sys.path.insert(0, str(ORIGINAL/'online/closed_loop_2888/z4q_source'))
from bridge import Bridge, stream
CONFIG_PATH = ARCHIVE.CONFIG_PATH
ROLES = ('whole','core','patch1','patch2','patch3')

def utc(): return datetime.now(timezone.utc).isoformat()
def save(name, value): write_new(HERE/name, value)
def key(name, frame, native): return f'{name}/F{int(frame)}/n:{int(native)}'
def dump(handle, value): handle.write(json.dumps(value, separators=(',',':'), allow_nan=False)+'\n')
def git(*args):
    return subprocess.check_output(['git','-c','http.sslBackend=schannel','-c','http.sslVerify=true',
        '-c','http.proxy=','-c','http.version=HTTP/1.1','-c','gc.auto=0','-c','pack.threads=2',*args],cwd=ROOT)
def verified_freeze():
    frozen = read(HERE/'FREEZE.json')
    for p in frozen['files']: verify_item(p)
    return frozen
def relation(a,b):
    if a.get('status')!='UNIQUE_IOU_MATCH' or b.get('status')!='UNIQUE_IOU_MATCH': return 'UNKNOWN'
    return 'SAME' if a['gt_id']==b['gt_id'] else 'DIFFERENT'
