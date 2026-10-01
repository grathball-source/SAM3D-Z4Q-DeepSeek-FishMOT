"""DS14 data adapters; frozen DS12 scientific kernels use unchanged CONFIG."""
from pathlib import Path
import os, sys, json, gzip, hashlib, importlib.util
os.environ.update(CUDA_VISIBLE_DEVICES='', OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1',
                  MKL_NUM_THREADS='1', NUMEXPR_NUM_THREADS='1')
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
WORK=Path('E:/CAU/D-MOT')
DS1=ROOT/'experiments/ds1_depth_only'
DS2=ROOT/'experiments/ds2_depth_transfer_validation'
DS6=ROOT/'experiments/ds6_multifragment_depth_tracking'
DS12=ROOT/'experiments/ds12_contact_depth_admission'
FEED=ROOT/'experiments/feeding_first_two_s0p'
OLD=ROOT/'experiments/ms1_s0_development_8400'
S0P=ROOT/'experiments/s0p_identity_publication'
NE1=ROOT/'experiments/ne1_native_first_event_association'
DATA=WORK/'data/AlignedFeeding_v1'
DEPS=WORK/'tools/jev_z4q_scene_v1_20260922/deps'
RUN=HERE/'run'
ARMS=('SAM3_NATIVE','R12_RAW')
SEGMENTS={'feeding_000000_000199':(0,199),'feeding_000351_000555':(351,555),
          'feeding_000701_001060':(701,1060),'feeding_001201_001906':(1201,1906),
          'fishsa_development_8400':(1,8400),'fishsa_validation_2888':(9301,12188),
          'L3':(0,3709),'LW':(0,3628)}
for p in (DS1,FEED,OLD,S0P,NE1,ROOT/'online/closed_loop_2888/z4q_source',DEPS,
          WORK/'tools/depth_restoration',WORK/'tools/sam3_depth_birth_inherit_20260917'):
    if str(p) not in sys.path:sys.path.append(str(p))
def input_dir(name):return HERE/'private'/name
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def rows(p):
    opener=gzip.open if str(p).endswith('.gz') else open
    with opener(p,'rt',encoding='utf-8') as f:yield from (json.loads(x) for x in f)
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def artifact(p):
    p=Path(p).resolve();return dict(path=str(p),bytes=p.stat().st_size,sha256=sha(p))
def verify_item(i):assert artifact(i['path'])=={k:i[k] for k in ('path','bytes','sha256')},i['path']
def write_new(p,value):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8',newline='\n') as f:
        json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False,default=str);f.write('\n')
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m);return m
