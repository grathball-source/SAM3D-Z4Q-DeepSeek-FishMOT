"""DS26 read-only phase measurement on the immutable DS25 candidate cohort."""
from pathlib import Path
import sys, os, json, gzip, hashlib, importlib.util
os.environ.update(CUDA_VISIBLE_DEVICES='', OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1', NUMEXPR_NUM_THREADS='1')
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = 'e76a5184aafa9780a46c93f2128264291707c4d6'
DS25 = ROOT / 'experiments/ds25_contact_local_layers'
spec = importlib.util.spec_from_file_location('ds26_unchanged_helpers', DS25/'common.py')
old = importlib.util.module_from_spec(spec); spec.loader.exec_module(old)
WORK, DEPS, SEGMENTS, DATA = old.WORK, old.DEPS, old.SEGMENTS, old.DATA
read, rows, sha, artifact, verify_item, write_new, module = old.read, old.rows, old.sha, old.artifact, old.verify_item, old.write_new, old.module
digest, row_sha, input_dir = old.digest, old.row_sha, old.input_dir
old_measurement = module('ds26_unchanged_measurement', DS25/'measurement.py')
PARAMETERS = old_measurement.PARAMETERS
RUN = HERE/'run'

def check_freeze():
    freeze = read(HERE/'FREEZE.json')
    for path, expected in freeze['code'].items(): assert sha(path) == expected, path
    for item in freeze['inputs']: verify_item(item)
    return freeze

def write_rows(path, values):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, 'xt', encoding='utf-8', newline='\n') as handle:
        for value in values: handle.write(json.dumps(value, separators=(',', ':'), allow_nan=False)+'\n')
