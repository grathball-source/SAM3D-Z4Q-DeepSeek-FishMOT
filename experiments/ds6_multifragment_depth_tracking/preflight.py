"""Freeze old public bytes and effective runtime/dependency provenance."""
import os
import platform
import subprocess
import sys
from common import HERE,ROOT,DATA,DEPS,write_new,artifact,sha,read
import numpy as np
import cv2
cv2.setNumThreads(1)
import scipy
from measurement import CFG,FILTER_CFG
from depth_measurement import KERNEL
from merge_split_manager import numeric_choice

def main():
    paths=subprocess.check_output(['git','ls-files','experiments/ds1_depth_only',
        'experiments/ds2_depth_transfer_validation','experiments/ds3_depth_foreground_filter',
        'experiments/ds4_depth_quality_repair','experiments/ds5_surface_registration_audit'],
        cwd=ROOT,text=True).splitlines()
    old_lock=dict(base=subprocess.check_output(
        ['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        artifacts=[artifact(ROOT/p) for p in paths],
        policy='all tracked DS1-DS5 bytes preserved; no legacy rerun writes')
    if (HERE/'OLD_READONLY_LOCK.json').exists():
        assert read(HERE/'OLD_READONLY_LOCK.json')==old_lock
    else:
        write_new(HERE/'OLD_READONLY_LOCK.json',old_lock)
    depfiles=sorted([*DEPS.glob('pycocotools/*.py'),*DEPS.glob('pycocotools/*.pyd'),
        *DEPS.glob('trackeval/*.py'),*DEPS.glob('trackeval/metrics/*.py')])
    write_new(HERE/'ENVIRONMENT.json',dict(
        interpreter=sys.executable,python=platform.python_version(),numpy=np.__version__,
        cv2=cv2.__version__,scipy=scipy.__version__,cv2_threads=cv2.getNumThreads(),
        native_math_threads={k:os.environ.get(k) for k in (
            'OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','CUDA_VISIBLE_DEVICES')},
        dependency_root=str(DEPS),external_dependency_files=[artifact(p) for p in depfiles],
        server_used=False,new_installation=False,model_http=0,cost_usd=0,
        runtime_policy='single native math thread; CPU only; no tracemalloc slowdown'))
    settings=dict(new_depth=CFG,f6_filter=FILTER_CFG,
        eroded_core_kernel=KERNEL.tolist(),f6_background_floor_mm=CFG['background_floor_mm'],
        f6_native_quality_policy_mm=CFG['native_suspect_above_mm'],
        history_cache=30,wls_max_points=10,wls_sigma_floor_mm=15,
        wls_process_scale_mm=15,depth_weight=.25,t4_df=4,common_uninformative_weight=.1,
        role_post_mapping='H1=A:first,B:second; H2=A:second,B:first, original numeric_choice',
        controller_config=read(ROOT/'online/closed_loop_2888/z4q_source/CONFIG.json'),
        event_max_seconds=read(ROOT/'experiments/ms1_s0_development_8400/CONFIG_V7.json')['max_episode_seconds'],
        verified_by='actual imported constants/functions and source SHA frozen, not explanatory CONFIG alone')
    if (HERE/'EFFECTIVE_SETTINGS.json').exists():
        assert read(HERE/'EFFECTIVE_SETTINGS.json')==settings
    else:
        write_new(HERE/'EFFECTIVE_SETTINGS.json',settings)
    print('old files',len(paths),'external dependency files',len(depfiles),flush=True)

if __name__=='__main__': main()

