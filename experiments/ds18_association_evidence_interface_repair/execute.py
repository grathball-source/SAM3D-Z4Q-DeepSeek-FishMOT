"""Exact local commands, complete logs, exits and elapsed time."""
from common import *
import subprocess,time,threading
from datetime import datetime,timezone
LOCK=threading.Lock()
def run(script,*args):
    target=HERE/'logs'/('_'.join((Path(script).stem,*args))+'.txt');target.parent.mkdir(exist_ok=True)
    env=dict(os.environ,PYTHONUTF8='1');command=[sys.executable,'-B',str(HERE/script),*args]
    begin=time.perf_counter();started=datetime.now(timezone.utc).isoformat()
    with target.open('x',encoding='utf-8') as f:
        process=subprocess.run(command,cwd=HERE,env=env,stdout=f,stderr=subprocess.STDOUT)
    record=dict(command=command,exit_code=process.returncode,elapsed_seconds=time.perf_counter()-begin,
        started_utc=started,finished_utc=datetime.now(timezone.utc).isoformat(),log=artifact(target))
    with LOCK:
        with (HERE/'EXECUTION_LOG.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(record)+'\n')
    print(json.dumps(record),flush=True)
    return record
if __name__=='__main__':assert run(*sys.argv[1:])['exit_code']==0
