"""Direct source/projection/score checks; no research success prerequisite."""
from common import *
import importlib.metadata
import numpy as np
from source import RawDepth,original_sources,native_masks,FIELD_READS
from evaluate import metrics,data_for

def main():
    kernels={n:dict(new=sha(HERE/n),old=sha(DS12/n)) for n in
        ('CONFIG.json','controller.py','birth_memory.py','forecast.py','reconnect.py','contact_measurement.py')}
    kernels.update({n:dict(new=sha(HERE/n),old=sha(HERE.parent/'ds10_depth_failure_repair'/n)) for n in ('measurement.py','adaptive_core.py')})
    assert all(x['new']==x['old'] for x in kernels.values())
    tested=[]
    reader=RawDepth('fishsa_development_8400');stream=rows(original_sources('fishsa_development_8400')['observations'])
    a=next(stream);b=next(stream)
    z,idx,native,binding=reader(a['global_frame'],a['time'])
    assert a['global_frame']==1 and not binding['sensor_available'] and not z.any() and np.all(idx==-1)
    z,idx,native,binding=reader(b['global_frame'],b['time'])
    assert b['global_frame']==2 and binding['aligned_frame_id']==1 and binding['source_color_index']==1 and binding['sensor_available']
    if 'guard' in sys.modules or '__main__' in sys.modules and getattr(sys.modules['__main__'],'H5_KEYS',None):
        try:next(iter(reader.files.values()))['aligned/depth_mm']
        except RuntimeError:tested.append('Restored/GT H5 field rejected before data access')
        else:raise AssertionError('H5 field whitelist missing')
    reader.close();tested.extend(('FishSA first source remains missing','FishSA global2 matches aligned1'))
    reader=RawDepth('fishsa_validation_2888');a=next(rows(original_sources('fishsa_validation_2888')['observations']))
    z,idx,native,binding=reader(a['global_frame'],a['time'])
    assert a['global_frame']==9301 and binding['aligned_frame_id']==9300 and binding['source_color_index']==9300
    reader.close();tested.append('Validation source time and row binding')
    original=original_sources('fishsa_validation_2888')
    for o,a in zip(rows(original['observations']),rows(original['assignments']),strict=True):
        if o['frame']==53:
            assert len(a['masks'])>len(o['native']) and set(native_masks(a))=={x['id'] for x in o['observations']}
            break
    tested.append('Archive auxiliary proposals never enter native occupancy; all N0 masks retained')
    camera_results={}
    for name in ('L3','LW'):
        reader=RawDepth(name);first=reader.metadata[0]
        z,idx,native,binding=reader(0,first['rgb_timestamp_us']/1e6)
        original=reader.geo.align(native) if first['depth_usable'] else np.zeros(z.shape,'f4')
        assert np.array_equal(z,original),(name,'projection changed')
        assert np.array_equal(idx>=0,z>0)
        invalid=next(row for row in reader.metadata.values() if not row['depth_usable'])
        z,idx,native,binding=reader(invalid['frame'],invalid['rgb_timestamp_us']/1e6)
        assert not z.any() and np.all(idx==-1) and not binding['sensor_available']
        camera_results[name]=dict(first_frame_exact_original_projection=True,missing_frame=invalid['frame'],missing_common_zero=True)
        reader.close()
    tested.extend(('Recorded original camera projection exact','Missing timestamp common no-information'))
    gt=[[1,2]]*4;native=[[10,20]]*4;sims=[np.eye(2)]*4
    perfect,_=metrics(gt,native,sims);switched,_=metrics(gt,[[10,20],[20,10],[10,20],[10,20]],sims)
    assert all(abs(perfect[k]-100)<1e-8 for k in ('IDF1','HOTA','AssA')) and perfect['IDSW']==0
    assert switched['IDSW']==4 and switched['IDF1']<100
    tested.append('Official scoring detects actual public ID switches')
    versions={p:importlib.metadata.version(p) for p in ('numpy','opencv-python','scipy','h5py','pycocotools')}
    write_new(HERE/'ADAPTER_CHECKS.json',dict(status='PASS',checks=tested,kernel_byte_equality=kernels,
        cameras=camera_results,score_sanity=perfect,switch_sanity=switched,actual_array_field_reads=FIELD_READS,
        versions=versions,python=sys.version,passed_engineering_only=True,new_model_http=0,cost_usd=0))
    print('PASS',tested,flush=True)
if __name__=='__main__':main()
