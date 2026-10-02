"""Read-only prediction guard and actual array-field access inventory."""
import os,sys
BLOCKED=('labels_640x360','labels_original','labels_source','labels_recovered','restoration/v3/',
    'depth_restored_rgb_640x360/','sealed_test','/rgb_640x360/','/rgb_original/','/color/','/rgb/',
    'gt_grid','truth.jsonl','offline_matches','test_gt','full_v2')
SEEN=set();NPZ=set()
def guard(event,args):
    if event=='socket.connect':raise RuntimeError('No network in this experiment')
    if event!='open' or not isinstance(args[0],(str,bytes,os.PathLike)):return
    path=str(args[0]).replace('\\','/').lower()
    if any(token in path for token in BLOCKED):raise RuntimeError('Forbidden prediction read: '+path)
    if '/data/' in path or '/private/' in path:SEEN.add(str(args[0]))
sys.addaudithook(guard)
from common import *
import numpy as np
original=np.lib.npyio.NpzFile.__getitem__
def field(sensor,key):
    if key not in ('depth_mm','source_index'):raise RuntimeError('Forbidden NPZ field: '+key)
    NPZ.add((str(sensor.zip.filename),key));return original(sensor,key)
np.lib.npyio.NpzFile.__getitem__=field
import h5py
original_h5=h5py.Group.__getitem__
H5_KEYS={'/frame_id','/aligned/raw_depth_mm','/aligned/raw_source_index','/native/original_depth_mm'}
def h5_field(group,key):
    assert isinstance(key,str),'No indirect H5 object references'
    absolute=(key if key.startswith('/') else group.name.rstrip('/')+'/'+key)
    if absolute not in H5_KEYS:raise RuntimeError('Forbidden H5 field: '+absolute)
    return original_h5(group,key)
h5py.Group.__getitem__=h5_field

if __name__=='__main__':
    import source
    mode,name=sys.argv[1:3]
    if mode=='check':
        from adapter_checks import main
        main();target=HERE/'ADAPTER_ACCESS.json'
    elif mode=='prepare':
        from prepare_inputs import prepare
        prepare(name);target=HERE/'inputs'/f'{name}_access.json'
    elif mode=='slice':
        from runner import run_segment
        output=HERE/(sys.argv[4] if len(sys.argv)>4 else 'slice_real')
        assert output.parent==HERE and output.name.startswith('slice_')
        run_segment(name,output,stop_at=int(sys.argv[3]));target=output/name/'public/ACCESS.json'
    else:
        assert mode=='run'
        from runner import run_segment
        run_segment(name,RUN);target=RUN/name/'public/ACCESS.json'
    write_new(target,dict(status='NO_GT_RGB_RESTORED_NETWORK',blocked_tokens=list(BLOCKED),
        observed_data_paths=sorted(SEEN),npz_field_reads=[dict(path=p,key=k) for p,k in sorted(NPZ)],
        h5_or_array_field_reads=source.FIELD_READS,new_model_http=0,cost_usd=0))
