"""Read-only DS35 sources; DS36 writes only its own diagnostic artifacts."""
from pathlib import Path
import os, sys, json, gzip, hashlib, subprocess, importlib.util
os.environ.update(CUDA_VISIBLE_DEVICES='', OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1',
                  MKL_NUM_THREADS='1', NUMEXPR_NUM_THREADS='1')
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = '543731028dc94bdade1c1860246e4e649586487b'

def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec); spec.loader.exec_module(result)
    return result

old = module('ds36_saved_ds35_helpers', ROOT/'experiments/ds35_authoritative_z4q_depth/common.py')
WORK, DATA, DEPS, SEGMENTS = old.WORK, old.DATA, old.DEPS, old.SEGMENTS
DS14, DS18, DS1, OLD, S0P = old.DS14, old.DS18, old.DS1, old.OLD, old.S0P
read, rows, sha, artifact = old.read, old.rows, old.sha, old.artifact
verify_item, write_new, input_dir = old.verify_item, old.write_new, old.input_dir
DS35 = ROOT/'experiments/ds35_authoritative_z4q_depth'
DS21 = ROOT/'experiments/ds21_z4q_depth_discriminability_audit'
CFG = dict(neighbor_radius_px=20, patches=3, minimum_n=16, minimum_fraction=.2,
           scale_floor_mm=15., maximum_measured_scale_mm=60., horizons_seconds=[1/30,.1,.3,1.,3.,6.],
           calibration_anchor_stride=30, history_samples=10, maximum_history_seconds=12.)
DEPTH = module('ds36_frozen_depth', ROOT/'experiments/ds31_persistent_identity_depth/depth.py')
SENSOR = module('ds36_existing_raw_adapter', ROOT/'experiments/ds34_bidirectional_event_restore/sensor.py')
SOURCE = SENSOR._source()  # Only RawDepth and saved N0 masks; never Sensor.read/RGB.
sys.path.insert(0, str(DS18))
_calling_common = sys.modules.get('common')
try:
    # Legacy measurement imports use their frozen DS20 configuration namespace.
    sys.modules['common'] = old.old
    MEASUREMENT = module('ds36_existing_local_background', ROOT/'experiments/ds22_local_background_depth/measurement.py')
finally:
    if _calling_common is None:sys.modules.pop('common',None)
    else:sys.modules['common'] = _calling_common

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    ensure_ascii=False, allow_nan=False).encode()).hexdigest()

def line_hash(value):
    return hashlib.sha256((json.dumps(value,separators=(',',':'),allow_nan=False)+'\n').encode()).hexdigest()

def verify_freeze():
    frozen = read(HERE/'FREEZE.json')
    for pin in frozen['files']: verify_item(pin)
    return frozen

def save(name, value): write_new(HERE/name, value)

def git(*args):
    env = os.environ.copy()
    options = {'http.sslBackend':'schannel','http.sslVerify':'true','http.proxy':'',
               'http.version':'HTTP/1.1','gc.auto':'0','pack.threads':'2'}
    env['GIT_CONFIG_COUNT']=str(len(options))
    for i,(key,value) in enumerate(options.items()):
        env[f'GIT_CONFIG_KEY_{i}'],env[f'GIT_CONFIG_VALUE_{i}']=key,value
    return subprocess.check_output(['git',*args],cwd=ROOT,env=env)
