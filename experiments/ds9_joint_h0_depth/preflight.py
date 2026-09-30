"""Capture real environment and immutable old tracked artifacts before replay."""
from common import *
import subprocess,platform,os,importlib.metadata

def main():
    paths=subprocess.check_output(['git','ls-files','experiments/ds1_*','experiments/ds2_*',
        'experiments/ds3_*','experiments/ds4_*','experiments/ds5_*','experiments/ds6_*',
        'experiments/ds7_*','experiments/ds8_*'],cwd=ROOT,text=True,encoding='utf-8').splitlines()
    write_new(HERE/'OLD_READONLY_LOCK.json',dict(count=len(paths),files={p:sha(ROOT/p) for p in paths},
        base_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()))
    write_new(HERE/'ENVIRONMENT.json',dict(interpreter=sys.executable,python=sys.version,
        platform=platform.platform(),cpu_count=os.cpu_count(),threads=1,cuda_visible_devices='',
        versions={n:importlib.metadata.version(n) for n in ('numpy','scipy','opencv-python','h5py')},
        execution='local CPU, no server jobs, no package installation',new_model_http=0,cost_usd=0))
    print('Old artifacts locked:',len(paths))
if __name__=='__main__':main()
