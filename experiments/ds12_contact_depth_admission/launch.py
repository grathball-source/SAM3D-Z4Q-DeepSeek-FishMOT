"""Prediction process blocks GT, RGB, v3, networks; existing native v2 is authorized."""
import os,sys
from pathlib import Path
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1',CUDA_VISIBLE_DEVICES='')
sys.dont_write_bytecode=True
mode=sys.argv[1] if len(sys.argv)>1 else 'full'
blocked=('labels_640x360','labels_original','labels_source','restoration/v3/','depth_restored_rgb_640x360/',
         'sealed_test','/rgb_640x360/','/rgb_original/','/color/','/rgb/')
seen=set();npz_keys=set()
def guard(event,args):
    if event=='socket.connect':raise RuntimeError('no network during prediction')
    if event!='open' or not isinstance(args[0],(str,bytes,os.PathLike)):return
    normalized=str(args[0]).replace('\\','/').lower()
    if any(x in normalized for x in blocked):raise RuntimeError('forbidden prediction input: '+normalized)
    if '/data/' in normalized or '/private/' in normalized or '/full_v2/' in normalized:seen.add(str(args[0]))
sys.addaudithook(guard)
from common import *
import numpy as np
original=np.lib.npyio.NpzFile.__getitem__
def getitem(sensor,key):
    if key not in ('depth_mm','source_index'):raise RuntimeError('forbidden npz key '+key)
    npz_keys.add((str(sensor.zip.filename),key));return original(sensor,key)
np.lib.npyio.NpzFile.__getitem__=getitem
import runner
runner.main(mode)
target=HERE/('slice' if mode=='slice' else 'run')
write_new(target/'PREDICTION_ACCESS_AUDIT.json',dict(
    status='NO_DIRECT_GT_RGB_V3_OR_NETWORK_DURING_PREDICTION',
    restored_boundary='v2 was previously generated with RGB+future clean; offline exposed diagnostic',
    npz_field_reads=[dict(path=p,key=k) for p,k in sorted(npz_keys)],observed_data_paths=sorted(seen),
    forbidden_path_tokens=list(blocked),new_model_http=0,cost_usd=0))
write_new(target/'ACCESS_SEALED.json',dict(artifact=artifact(target/'PREDICTION_ACCESS_AUDIT.json'),
    prediction_all_seal=artifact(target/'ALL_PREDICTIONS_SEALED.json') if mode=='full' else None))
