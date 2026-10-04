"""Finish only the manifest after the seven preserved runs and first L3 run."""
from common import *
recovery=read(HERE/'TECHNICAL_RECOVERY.json')
for pin in recovery['completed_seven_seals_preserved'].values():verify_item(pin)
for p,h in read(HERE/'RUNTIME_FREEZE.json')['code'].items():assert sha(p)==h,p
for name in SEGMENTS:verify_seal(name)
write_new(RUN/'ALL_PREDICTIONS_SEALED.json',dict(status='ALL_PREDICTIONS_AND_ACCESS_SEALED',frames=20098,arms=ARMS,
    seals={n:artifact(RUN/n/'public/PREDICTIONS_SEALED.json') for n in SEGMENTS},
    access_seals={n:artifact(RUN/n/'public/ACCESS.json') for n in SEGMENTS},
    log_collision_recovery=artifact(HERE/'TECHNICAL_RECOVERY.json'),
    frozen_runtime_unchanged=True,seven_seals_unchanged=True,new_model_http=0,cost_usd=0))
print('All eight predictions/access sealed; L3 first launch recovered; frozen runtime unchanged')
