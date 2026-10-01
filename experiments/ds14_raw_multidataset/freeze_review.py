"""Bind actual scientific bytes and preserve older experimental artifacts."""
from common import *
import subprocess
def main():
    assert read(HERE/'ADAPTER_CHECKS.json')['status']=='PASS'
    old={p:(v['sha256'] if isinstance(v,dict) else v) for p,v in read(HERE.parent/'ds13_frozen_validation/OLD_READONLY_LOCK.json')['files'].items()}
    paths=subprocess.check_output(['git','ls-files','experiments/ds13_frozen_validation'],cwd=ROOT,text=True).splitlines()
    old=dict(old,**{p:sha(ROOT/p) for p in paths})
    for p,h in old.items():assert sha(ROOT/p)==h,p
    write_new(HERE/'OLD_READONLY_LOCK.json',dict(base_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),count=len(old),files=old))
    prepared={}
    for name,(a,b) in SEGMENTS.items():
        m=read(input_dir(name)/'SOURCE_MANIFEST.json');assert m['frames']==b-a+1 and m['no_GT'] and m['no_RGB'] and m['no_restored_values']
        for i in m['derived_inputs'].values():verify_item(i)
        for n in ('scan','field_access','raw_sources'):verify_item(m[n])
        if name.startswith('feeding_'):
            assert m['coverage']['old_raw_cache_equal_frames']==b-a+1
            from source import original_sources
            original_scan=Path(original_sources(name)['observations']).parent/'scan_v4.json'
            assert read(original_scan)==read(input_dir(name)/'scan_v4.json'),name
        prepared[name]=dict(frames=b-a+1,coverage=m['coverage'],raw_profile_changed_objects=m['raw_profile_changed_objects'],suspects=len(read(input_dir(name)/'scan_v4.json')['suspects']))
    write_new(HERE/'EFFECTIVE_RUNTIME.json',dict(trial='DS14',arms=list(ARMS),segments=SEGMENTS,frames=20098,
        scientific_constants=read(HERE/'CONFIG.json'),scientific_kernel_equality=read(HERE/'ADAPTER_CHECKS.json')['kernel_byte_equality'],
        prepared=prepared,shared_group_policy='FROZEN_DS9',new_birth_policy='FROZEN_DS12',
        actual_max_local_parallel_processes=3,threads_per_process=1,GPU=False,server=False,
        new_model_http=0,cost_usd=0,reference_policy='ALL_EIGHT_SEALS_BEFORE_REFERENCE_ACCESS',
        prior_exposure='ALL_REQUESTED_DATA_PREVIOUSLY_EXPOSED; NOT_BLIND_GENERALIZATION'))
    import runner
    runner.freeze_inputs(RUN)
    print('FROZEN ALL8 20098 frames; old files unchanged',len(old),flush=True)
if __name__=='__main__':main()
