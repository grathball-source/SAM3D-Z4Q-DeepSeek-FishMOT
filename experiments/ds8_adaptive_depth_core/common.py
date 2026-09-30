"""DS7 shared paths: same SOURCE_OLD masks and frozen scanner."""
from pathlib import Path
import sys, json, gzip, hashlib
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
DS1=ROOT/'experiments/ds1_depth_only'
DS2=ROOT/'experiments/ds2_depth_transfer_validation'
DS6=ROOT/'experiments/ds6_multifragment_depth_tracking'
FEED=ROOT/'experiments/feeding_first_two_s0p'
OLD=ROOT/'experiments/ms1_s0_development_8400'
S0P=ROOT/'experiments/s0p_identity_publication'
NE1=ROOT/'experiments/ne1_native_first_event_association'
DATA=Path('E:/CAU/D-MOT/data/AlignedFeeding_v1')
DEPS=Path('E:/CAU/D-MOT/tools/jev_z4q_scene_v1_20260922/deps')
RUN=HERE/'run'
ARMS=('SAM3_NATIVE','D2_CORE_FROZEN','P0_NATIVE_PRESERVE','P1_RAW_DEPTH','P2_RESTORED_DEPTH')
SEGMENTS={'feeding_000000_000199':(0,199),'feeding_000351_000555':(351,555),
          'feeding_000701_001060':(701,1060),'feeding_001201_001906':(1201,1906)}
for p in (DS1,FEED,OLD,S0P,NE1,ROOT/'online/closed_loop_2888/z4q_source',DEPS):
    if str(p) not in sys.path:sys.path.append(str(p))
def input_dir(name):return (FEED if SEGMENTS[name][0]<701 else DS2)/'private'/name
def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def rows(path):
    op=gzip.open if str(path).endswith('.gz') else open
    with op(path,'rt',encoding='utf-8') as f:
        yield from (json.loads(x) for x in f)
def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def artifact(path):
    p=Path(path).resolve()
    return dict(path=str(p),bytes=p.stat().st_size,sha256=sha(p))
def verify_item(item):
    p=Path(item['path']);assert p.stat().st_size==item['bytes'] and sha(p)==item['sha256'],p
def write_new(path,obj):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8',newline='\n') as f:
        json.dump(obj,f,ensure_ascii=False,indent=2,allow_nan=False,default=str);f.write('\n')
