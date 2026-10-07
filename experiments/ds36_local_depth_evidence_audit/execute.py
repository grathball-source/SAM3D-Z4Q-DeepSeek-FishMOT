"""Record actual exits with fresh log files, including failed attempts."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,subprocess,sys,time,uuid
HERE=Path(__file__).resolve().parent
sys.dont_write_bytecode=True

def main():
    script=(HERE/sys.argv[1]).resolve();assert script.parent==HERE and script.suffix=='.py' and script.name not in ('execute.py','delivery.py')
    logdir=HERE/'logs';logdir.mkdir(exist_ok=True)
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'_'+uuid.uuid4().hex
    stdout=logdir/(stamp+'.stdout.txt');stderr=logdir/(stamp+'.stderr.txt')
    command=[sys.executable,str(script),*sys.argv[2:]];started=datetime.now(timezone.utc).isoformat();began=time.perf_counter()
    env=dict(os.environ,PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1',CUDA_VISIBLE_DEVICES='',
             OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1')
    with stdout.open('xb') as out,stderr.open('xb') as err:result=subprocess.run(command,cwd=HERE,env=env,stdout=out,stderr=err)
    def pin(p):
        with p.open('rb') as f:s=hashlib.file_digest(f,'sha256').hexdigest()
        return dict(path=str(p),bytes=p.stat().st_size,sha256=s)
    record=dict(command=command,started_utc=started,ended_utc=datetime.now(timezone.utc).isoformat(),
                elapsed_seconds=time.perf_counter()-began,exit_code=result.returncode,stdout=pin(stdout),stderr=pin(stderr),model_http=0,cost_usd=0)
    with (HERE/'EXECUTION_LOG.jsonl').open('a',encoding='utf-8',newline='\n') as f:f.write(json.dumps(record,separators=(',',':'))+'\n')
    print(json.dumps(record,separators=(',',':')),flush=True)
    if result.returncode:print(stderr.read_text(encoding='utf-8',errors='replace')[-7000:],flush=True)
    sys.exit(result.returncode)
if __name__=='__main__':main()
