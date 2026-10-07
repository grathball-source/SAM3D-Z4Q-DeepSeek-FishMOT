"""Two source workers; all seals first; then independent score and explanation."""
from common import *
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import subprocess,time

def run(name):
    began=time.perf_counter()
    process=subprocess.run([sys.executable,str(HERE/'execute.py'),'guard.py','run',name],cwd=HERE,
        capture_output=True,text=True)
    print(name,process.returncode,process.stdout[-1600:],process.stderr[-2000:],flush=True)
    assert process.returncode==0,name
    verify_seal(name)
    write_new(RUN/name/'JOB_COMPLETE.json',dict(segment=name,exit_code=process.returncode,
        elapsed_seconds=time.perf_counter()-began,completed_utc=datetime.now(timezone.utc).isoformat()))

if __name__=='__main__':
    schedule=['fishsa_development_8400','LW','fishsa_validation_2888','L3',*[n for n in SEGMENTS if n.startswith('feeding_')]]
    write_new(RUN/'START.json',dict(started_utc=datetime.now(timezone.utc).isoformat(),schedule=schedule,
        workers=4,threads_each=1,frozen_policy=artifact(HERE/'RUNTIME_FREEZE.json'),model_http=0,cost_usd=0))
    with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(run,schedule))
    for name in SEGMENTS:verify_seal(name)
    write_new(RUN/'ALL_PREDICTIONS_SEALED.json',dict(status='ALL_FOUR_BRANCHES_EIGHT_SEGMENTS_AND_ACCESS_SEALED',frames=20098,arms=ARMS,
        seals={n:artifact(RUN/n/'public/PREDICTIONS_SEALED.json') for n in SEGMENTS},
        access_seals={n:artifact(RUN/n/'public/ACCESS.json') for n in SEGMENTS},model_http=0,cost_usd=0))
    print('ALL_PREDICTIONS_SEALED; reference scoring starts now',flush=True)
    for file in ('score.py','postseal.py','visuals.py'):
        result=subprocess.run([sys.executable,str(HERE/'execute.py'),file],cwd=HERE)
        assert result.returncode==0,file
    write_new(RUN/'COMPLETE.json',dict(status='FULL_REPLAY_SCORE_MECHANISM_AND_VISUALS_COMPLETE',frames=20098,
        completed_utc=datetime.now(timezone.utc).isoformat(),model_http=0,cost_usd=0))
