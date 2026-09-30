"""Preserve commands, stdout, exit status and times for this one trial."""
from common import *
import subprocess,os,time
from datetime import datetime,timezone

def run(script,*args):
    env=dict(os.environ,PYTHONUTF8='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',
        MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1',CUDA_VISIBLE_DEVICES='')
    target=HERE/'logs'/('_'.join((Path(script).stem,*args)).replace('--','')+'.txt')
    target.parent.mkdir(exist_ok=True)
    begin=time.perf_counter()
    command=[sys.executable,str(HERE/script),*args]
    with target.open('x',encoding='utf-8') as f:
        process=subprocess.run(command,cwd=HERE,env=env,stdout=f,stderr=subprocess.STDOUT)
    record=dict(command=command,exit_code=process.returncode,elapsed_seconds=time.perf_counter()-begin,
        finished_utc=datetime.now(timezone.utc).isoformat(),log=artifact(target))
    with (HERE/'EXECUTION_LOG.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(record)+'\n')
    print(json.dumps(record),flush=True)
    assert process.returncode==0,target
    return record

if __name__=='__main__':run(*sys.argv[1:])
