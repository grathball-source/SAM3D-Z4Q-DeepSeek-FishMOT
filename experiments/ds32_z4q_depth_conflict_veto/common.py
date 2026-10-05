"""DS32: original Z4Q with a causal per-edge depth conflict veto."""
from pathlib import Path
import sys,os,json,hashlib,gzip,importlib.util
os.environ.update(CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1')
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
spec=importlib.util.spec_from_file_location('ds32_saved_helpers',ROOT/'experiments/ds20_pending_confirmation_isolation/common.py')
old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
WORK,DEPS,SEGMENTS,DS1,DS14,DS16,DATA=old.WORK,old.DEPS,old.SEGMENTS,old.DS1,old.DS14,old.DS16,old.DATA
read,rows,sha,artifact,verify_item,write_new,module,input_dir=old.read,old.rows,old.sha,old.artifact,old.verify_item,old.write_new,old.module,old.input_dir
RUN=HERE/'run';BASE='511958fc27893da3f389bc3fe89d7f6bfb5995c4'
ARMS=('SAM3_NATIVE','Z4Q_FROZEN','Z4Q_DEPTH_VETO')
CONFIG_PATH=ROOT/'online/closed_loop_2888/z4q_source/CONFIG.json'
CFG=read(HERE/'CONFIG.json')
def digest(value):
    def numeric(x):
        if isinstance(x,set):return sorted(x)
        if hasattr(x,'tolist'):return x.tolist()
        raise TypeError(type(x).__name__)
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False,default=numeric).encode()).hexdigest()
def row_sha(value):return hashlib.sha256((json.dumps(value,separators=(',',':'),allow_nan=False)+'\n').encode()).hexdigest()
def verify_frozen_inputs(frozen):
    verify_item(frozen['source_manifest'])
    chain=frozen['source_chain'];assert read(frozen['source_manifest']['path'])==chain
    assert chain['no_GT'] and chain['no_RGB'] and chain['no_restored_values']
    for pin in chain['derived_inputs'].values():verify_item(pin)
    for key in ('scan','raw_sources','field_access'):verify_item(chain[key])
    old.verify_cache_reference(frozen['depth_cache'])
    for key in ('original_prediction','original_seal','runtime'):verify_item(frozen[key])
    assert frozen['original_prediction']['sha256']==read(frozen['original_seal']['path'])['artifacts_sha256']['predictions.jsonl.gz']
    assert read(frozen['runtime']['path'])['code']==frozen['code']

def verify_seal(name):
    p=RUN/name/'public';s=read(p/'PREDICTIONS_SEALED.json')
    assert s['frames']==SEGMENTS[name][1]-SEGMENTS[name][0]+1
    for f,h in s['artifacts_sha256'].items():assert sha(p/f)==h,f
    frozen=read(p/'FREEZE.json');verify_frozen_inputs(frozen)
    for f,h in frozen['code'].items():assert sha(f)==h,f
    return s
