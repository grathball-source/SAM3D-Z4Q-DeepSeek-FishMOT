"""Capture real environment and immutable old tracked artifacts before replay."""
from common import *
import subprocess,platform,os,importlib.metadata

def main():
    assert not RUN.exists(),'environment/preflight is fixed before prediction'
    lock=read(HERE/'OLD_READONLY_LOCK.json')
    for p,h in lock['files'].items():assert sha(ROOT/p)==h,p
    environment=dict(interpreter=sys.executable,python=sys.version,
        platform=platform.platform(),cpu_count=os.cpu_count(),threads=1,cuda_visible_devices='',
        versions={n:importlib.metadata.version(n) for n in ('numpy','scipy','opencv-python','h5py')},
        execution='local CPU, no server jobs, no package installation',new_model_http=0,cost_usd=0)
    (HERE/'ENVIRONMENT.json').write_text(json.dumps(environment,indent=2)+'\n',encoding='utf-8')
    print('Old artifacts locked:',lock['count'])
if __name__=='__main__':main()
