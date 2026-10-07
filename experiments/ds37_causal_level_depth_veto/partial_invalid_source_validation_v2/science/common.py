"""DS37 uses DS32's unchanged source, original hooks and same-source math."""
from pathlib import Path
import os, sys, json, gzip, hashlib, importlib.util
os.environ.update(CUDA_VISIBLE_DEVICES='', OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1',
                  MKL_NUM_THREADS='1', NUMEXPR_NUM_THREADS='1')
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
spec = importlib.util.spec_from_file_location('ds37_readonly_ds32_common',
    ROOT/'experiments/ds32_z4q_depth_conflict_veto/common.py')
OLD32 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(OLD32)
old = OLD32.old
WORK, DEPS, SEGMENTS, DS1, DS14, DS16, DATA = (getattr(OLD32, k) for k in
    ('WORK','DEPS','SEGMENTS','DS1','DS14','DS16','DATA'))
read, rows, sha, artifact, verify_item, write_new, module, input_dir, digest, row_sha = (
    getattr(OLD32, k) for k in ('read','rows','sha','artifact','verify_item','write_new',
        'module','input_dir','digest','row_sha'))
CONFIG_PATH = OLD32.CONFIG_PATH
CFG = read(HERE/'CONFIG.json')
RUN = HERE/'run'
BASE = 'ff45571a073cd660b812754a348b680e138ac7bf'
ARMS = ('SAM3_NATIVE','Z4Q_FROZEN','Z4Q_WLS_VETO','Z4Q_LEVEL_VETO')
VETO_ARMS = ARMS[2:]
verify_frozen_inputs = OLD32.verify_frozen_inputs

def verify_seal(name):
    p = RUN/name/'public'
    seal = read(p/'PREDICTIONS_SEALED.json')
    assert seal['frames'] == SEGMENTS[name][1]-SEGMENTS[name][0]+1
    assert tuple(seal['arms']) == ARMS
    for f, h in seal['artifacts_sha256'].items(): assert sha(p/f) == h, f
    frozen = read(p/'FREEZE.json')
    verify_frozen_inputs(frozen)
    for f, h in frozen['code'].items(): assert sha(f) == h, f
    return seal

def readonly_module(name, path, *, evidence=None):
    """Import an archived file with its own common; restore names even on error."""
    names = {'common': OLD32}
    if evidence is not None: names['evidence'] = evidence
    saved = {key: sys.modules.get(key) for key in names}
    try:
        sys.modules.update(names)
        return module(name, path)
    finally:
        for key, value in saved.items():
            if value is None: sys.modules.pop(key, None)
            else: sys.modules[key] = value
