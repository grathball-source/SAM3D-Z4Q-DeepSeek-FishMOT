"""Two single-thread local processes; four branches with isolated identity state."""
from common import *
from concurrent.futures import ThreadPoolExecutor
import subprocess,sys
schedule=['LW','L3','fishsa_development_8400','fishsa_validation_2888',*[n for n in SEGMENTS if n.startswith('feeding_')]]
def run(name):
    p=subprocess.run([sys.executable,str(HERE/'execute_unique.py'),'guard.py','run',name],cwd=HERE,capture_output=True,text=True)
    print(name,p.returncode,p.stdout[-1800:],p.stderr[-1800:],flush=True)
    return p.returncode
with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(run,schedule))
assert all(x==0 for x in results),results
for name in SEGMENTS:verify_seal(name)
write_new(RUN/'ALL_PREDICTIONS_SEALED.json',dict(status='ALL_PREDICTIONS_AND_ACCESS_SEALED',frames=20098,arms=ARMS,
    seals={n:artifact(RUN/n/'public/PREDICTIONS_SEALED.json') for n in SEGMENTS},
    access_seals={n:artifact(RUN/n/'public/ACCESS.json') for n in SEGMENTS},new_model_http=0,cost_usd=0))
print('All predictions/access sealed; independent scoring now allowed',flush=True)
