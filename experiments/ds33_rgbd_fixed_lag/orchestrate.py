"""Run all frozen sources with two independent, single-thread CPU workers."""
from common import *
from concurrent.futures import ThreadPoolExecutor
from verify_inputs import verify_seal
import subprocess
from datetime import datetime, timezone

def call(name):
    started = datetime.now(timezone.utc).isoformat()
    write_new(RUN / name / 'public/START.json', dict(started_utc=started,
        freeze=artifact(RUN / name / 'public/FREEZE.json'), command=[sys.executable, 'execute_unique.py', 'guard.py', 'run', name],
        new_model_http=0, cost_usd=0))
    value = subprocess.run([sys.executable, str(HERE / 'execute_unique.py'), 'guard.py', 'run', name],
        cwd=HERE, capture_output=True, text=True)
    print(name, value.returncode, value.stdout[-1500:], value.stderr[-1500:], flush=True)
    write_new(RUN / name / 'public/END.json', dict(ended_utc=datetime.now(timezone.utc).isoformat(),
        start=artifact(RUN / name / 'public/START.json'), exit_code=value.returncode,
        new_model_http=0, cost_usd=0))
    assert value.returncode == 0, name
    verify_seal(name)

schedule = ['fishsa_development_8400', 'LW', 'L3', 'fishsa_validation_2888',
            *[name for name in SEGMENTS if name.startswith('feeding_')]]
with ThreadPoolExecutor(max_workers=2) as pool:
    list(pool.map(call, schedule))
for name in SEGMENTS:
    verify_seal(name)
write_new(RUN / 'ALL_PREDICTIONS_SEALED.json', dict(status='ALL_PREDICTIONS_AND_ACCESS_SEALED',
    frames=20098, arms=ARMS, seals={name:artifact(RUN / name / 'public/PREDICTIONS_SEALED.json') for name in SEGMENTS},
    access_seals={name:artifact(RUN / name / 'public/ACCESS.json') for name in SEGMENTS},
    starts={name:artifact(RUN / name / 'public/START.json') for name in SEGMENTS},
    ends={name:artifact(RUN / name / 'public/END.json') for name in SEGMENTS},
    new_model_http=0, cost_usd=0))
print('ALL formal predictions sealed; independent scoring may now read exposed references.', flush=True)
