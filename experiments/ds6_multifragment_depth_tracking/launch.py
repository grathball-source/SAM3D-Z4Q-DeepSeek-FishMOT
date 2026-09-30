"""Local sequential CPU execution with input access audit; no services."""
import os
import sys
from pathlib import Path
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',
                  NUMEXPR_NUM_THREADS='1',CUDA_VISIBLE_DEVICES='')
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
mode=sys.argv[1] if len(sys.argv)>1 else 'full'
assert mode in ('slice','full')
blocked=('labels_640x360','labels_original','labels_source','depth_restored',
         'restored_v3','sealed_test','/rgb_640x360/','/rgb_original/','/rgb/')
seen=set()
npz_keys=set()
def guard(event,args):
    if event=='socket.connect':
        raise RuntimeError('network calls forbidden in depth-only prediction')
    if event!='open' or not isinstance(args[0],(str,bytes,os.PathLike)):
        return
    path=str(args[0]).replace('\\','/').lower()
    if any(token in path for token in blocked):
        raise RuntimeError('forbidden reference/restoration input before prediction seal: '+path)
    if '/data/' in path or '/private/' in path:
        seen.add(str(args[0]))
sys.addaudithook(guard)
from common import write_new,artifact
import numpy as np
original_getitem=np.lib.npyio.NpzFile.__getitem__
def sensor_getitem(sensor,key):
    if key not in ('depth_mm','source_index'):
        raise RuntimeError('non-sensor NPZ field forbidden: '+str(key))
    npz_keys.add((str(sensor.zip.filename),str(key)))
    return original_getitem(sensor,key)
np.lib.npyio.NpzFile.__getitem__=sensor_getitem
import runner
runner.main(mode)
target=HERE/('slice' if mode=='slice' else 'run')
write_new(target/'PREDICTION_ACCESS_AUDIT.json',dict(
    status='NO_REFERENCE_OR_RESTORED_FILE_OPEN_DURING_PREDICTION',
    audit_events='Python open/socket events and actual NumPy NPZ getitem keys',
    npz_field_reads=[dict(path=p,key=k) for p,k in sorted(npz_keys)],
    observed_data_paths=sorted(seen),forbidden_path_tokens=list(blocked),
    new_model_http=0,cost_usd=0))
write_new(target/'ACCESS_SEALED.json',dict(artifact=artifact(target/'PREDICTION_ACCESS_AUDIT.json'),
    prediction_all_seal=(artifact(target/'ALL_PREDICTIONS_SEALED.json') if mode=='full' else None)))

