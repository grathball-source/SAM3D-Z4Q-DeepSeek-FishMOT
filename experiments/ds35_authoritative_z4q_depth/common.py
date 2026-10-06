"""Exact saved inputs and unchanged original Z4Q; DS35 owns only new outputs."""
from pathlib import Path
import os, sys, json, gzip, hashlib, importlib.util
os.environ.update(CUDA_VISIBLE_DEVICES='', OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1', NUMEXPR_NUM_THREADS='1')
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
spec = importlib.util.spec_from_file_location('ds35_saved_helpers', ROOT/'experiments/ds20_pending_confirmation_isolation/common.py')
old = importlib.util.module_from_spec(spec); spec.loader.exec_module(old)
WORK, DATA, DEPS, SEGMENTS = old.WORK, old.DATA, old.DEPS, old.SEGMENTS
DS14, DS18, DS1, OLD, S0P = old.DS14, old.DS18, old.DS1, old.OLD, old.S0P
read, rows, sha, artifact = old.read, old.rows, old.sha, old.artifact
verify_item, write_new, module, input_dir = old.verify_item, old.write_new, old.module, old.input_dir
BASE = '54b846a03ded8a8df355984e695f5ffbdf80475b'
RUN = HERE/'run'
PRIOR = ROOT/'experiments/ds34_bidirectional_event_restore'
ARMS = ('SAM3_NATIVE', 'Z4Q_FROZEN', 'DEPTH_OFF', 'DEPTH_OVERRIDE')
EVENT_ARMS = ARMS[2:]
CONFIG_PATH = ROOT/'online/closed_loop_2888/z4q_source/CONFIG.json'
CFG = read(HERE/'CONFIG.json')

def digest(value):
    def numeric(x):
        if isinstance(x, set): return sorted(x)
        if hasattr(x, 'tolist'): return x.tolist()
        raise TypeError(type(x).__name__)
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False, default=numeric).encode()).hexdigest()

def row_sha(value):
    return hashlib.sha256((json.dumps(value, separators=(',', ':'), allow_nan=False)+'\n').encode()).hexdigest()

def array_hash(value):
    import numpy as np
    a = np.ascontiguousarray(value)
    return dict(shape=list(a.shape), dtype=str(a.dtype), sha256=hashlib.sha256(a.tobytes()).hexdigest())
