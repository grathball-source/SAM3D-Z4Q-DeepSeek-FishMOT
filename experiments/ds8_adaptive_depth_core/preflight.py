"""Validate old immutable bytes and record actual local execution environment."""
import sys,platform,shutil
from common import *
import numpy as np,cv2,h5py,scipy
old=ROOT/'experiments/ds7_depth_native_recovery'
lock=read(old/'OLD_READONLY_LOCK.json')
for p,h in lock['files'].items():assert sha(ROOT/p)==h,p
frozen=read(old/'run/feeding_000000_000199/public/FREEZE.json')
for p,h in frozen['code_sha256'].items():assert sha(p)==h,p
write_new(HERE/'OLD_READONLY_LOCK.json',dict(files=lock['files'],count=lock['count'],
    ds7_frozen_code=frozen['code_sha256'],ds7_all_seal=artifact(old/'run/ALL_PREDICTIONS_SEALED.json'),
    ds7_scoring_seal=artifact(old/'run/SCORING_SEALED.json')))
write_new(HERE/'ENVIRONMENT.json',dict(python=sys.executable,platform=platform.platform(),
    numpy=np.__version__,opencv=cv2.__version__,h5py=h5py.__version__,scipy=scipy.__version__,
    local_cpu_only=True,new_model_http=0,cost_usd=0,disk_free_bytes=shutil.disk_usage(HERE).free,
    threads='OMP/OPENBLAS/MKL/NUMEXPR/OpenCV=1; CUDA empty'))
write_new(HERE/'REAL_INPUT_CHECKS.json',dict(status='PASS_SOURCE_REUSE',
    raw_masks_scanner_and_v2_sources='DS7 source seals unchanged; runtime revalidates actual bytes',
    first_q_selection='earliest actual automatic event, no GT',
    reference_scope='OFFLINE_EXPOSED_V2_FUTURE_RGB_SUPPORTED',new_http=0))
print('DS7 frozen code and old456 files unchanged; CPU only')
