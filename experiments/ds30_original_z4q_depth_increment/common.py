"""DS30 anonymous pair branches on unchanged DS14 saved masks and raw depth."""
from pathlib import Path
import sys, importlib.util, json, hashlib, gzip, os
os.environ.update(CUDA_VISIBLE_DEVICES='', OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1', NUMEXPR_NUM_THREADS='1')
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
spec = importlib.util.spec_from_file_location('ds25_readonly_helpers', ROOT/'experiments/ds20_pending_confirmation_isolation/common.py')
old = importlib.util.module_from_spec(spec); spec.loader.exec_module(old)
WORK, DEPS, SEGMENTS = old.WORK, old.DEPS, old.SEGMENTS
DS1, DS2, DS14, DS16, OLD, DATA = old.DS1, old.DS2, old.DS14, old.DS16, old.OLD, old.DATA
RUN = HERE/'run'
BASE = 'ecde37dfada0c9d19bc187b0fac108db48a3a661'
ARMS = ('SAM3_NATIVE', 'Z4Q_FROZEN', 'DEPTH_INCREMENT')
VARIANTS = {arm: dict(contrast=(10., 2.), scale_floor_mm=5.) for arm in ARMS[2:]}
DS27 = ROOT/'experiments/ds27_depth_threshold_soft_association'
CONFIG_PATH = ROOT/'online/closed_loop_2888/z4q_source/CONFIG.json'
read, rows, sha, artifact, verify_item, write_new, module = old.read, old.rows, old.sha, old.artifact, old.verify_item, old.write_new, old.module
input_dir = old.input_dir
sys.path.append(str(ROOT/'experiments/z4q_anchor_evidence_retention/source'))

def digest(value):
    def numeric(x):
        if isinstance(x,set):return sorted(x)
        if hasattr(x,'tolist'):return x.tolist()
        raise TypeError(type(x).__name__)
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False, default=numeric).encode()).hexdigest()

def row_sha(value):
    return hashlib.sha256((json.dumps(value, separators=(',', ':'), allow_nan=False)+'\n').encode()).hexdigest()

def verify_seal(name):
    public = RUN/name/'public'; seal = read(public/'PREDICTIONS_SEALED.json')
    assert seal['frames'] == SEGMENTS[name][1]-SEGMENTS[name][0]+1
    for f, expected in seal['artifacts_sha256'].items(): assert sha(public/f) == expected, f
    frozen = read(public/'FREEZE.json')
    for p, expected in frozen['code'].items(): assert sha(p) == expected, p
    return seal
