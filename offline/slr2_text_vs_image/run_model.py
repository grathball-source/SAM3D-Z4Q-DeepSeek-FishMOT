"""Frozen paired experiment. Two concurrent calls, bounded costs, no semantic retries."""
from common import *
sys.addaudithook(guard)
from model_client import credential,payload,bound,perform
from concurrent.futures import ThreadPoolExecutor,wait,FIRST_COMPLETED
import time

def verify_freeze():
 frozen=read(P/'MODEL_FREEZE.json')
 for name,h in frozen.items():assert sha(name)==h,name
 return frozen

def main():
 cpu=limit_cpu();cfg=read(P/'MODEL_CONFIG.json');requests=read(P/'REQUESTS.json');assert len(requests)==cfg['formal_requests']==144
 assert len({r['request_id'] for r in requests})==144
 for name in ['INPUT_CHECKS.json','CONTRACT_CHECKS.json','BASELINE_ACCEPTANCE.json','EVALUATION_CHECKS.json','SMOKE_ACCEPTANCE.json']:
  assert read(P/name)['exit_code']==0,name
 verify_freeze();key=credential();assert key,'Credential missing'
 assert not (P/'MODEL_RUN_STARTED.json').exists(),'Existing formal run is immutable; no implicit restart.'
 prompt=(P/'PROMPT.txt').read_text(encoding='utf-8')
 reserves={r['request_id']:bound(payload(r,cfg,prompt),cfg) for r in requests}
 spent=read(P/'SMOKE_ACCEPTANCE.json')['conservative_cost_usd'];decisions=[];errors=[];started=time.monotonic();submitted=0
 cap=cfg['maximum_admitted_estimated_usd'];assert spent+sum(reserves[r['request_id']] for r in requests[:2])<=cap
 with (P/'MODEL_RUN_STARTED.json').open('x',encoding='utf-8') as f:
  json.dump(dict(at=now(),pid=os.getpid(),cpu=cpu,formal_requests=144,concurrency=2,budget_cap_usd=cap,smoke_cost_usd=spent,all_requests_maximum_reserve_usd=sum(reserves.values()),queue=[r['request_id'] for r in requests]),f)
 pending={};failure=None
 def status(stage):
  reserved=sum(reserves[r['request_id']] for r in pending.values())
  save(P/'COST_ADMISSION.json',dict(at=now(),conservative_used_usd=spent,inflight_reserve_usd=reserved,total_admitted_usd=spent+reserved,cap_usd=cap,network_attempts=submitted,unknown_failed_attempts=len(errors)))
  save(P/'STATUS.json',dict(at=now(),stage=stage,pid=os.getpid(),completed=len(decisions),valid=sum(x['valid'] for x in decisions),total=144,network_attempts=submitted,inflight=len(pending),conservative_cost_used_usd=spent,reserved_cost_usd=reserved,model=cfg['model']))
 try:
  with ThreadPoolExecutor(max_workers=2) as pool:
   def submit_one(r):
    nonlocal submitted
    reserve=reserves[r['request_id']]
    if spent+sum(reserves[x['request_id']] for x in pending.values())+reserve>cap:return False
    # Persist admission before sending; a crash makes this attempt unknown, never automatically retried.
    save(P/f"admissions/{r['request_id']}.json",dict(at=now(),request_id=r['request_id'],reserve_usd=reserve,request_ordinal=submitted))
    future=pool.submit(perform,r,cfg,prompt,key);pending[future]=r;submitted+=1;return True
   # The first T/V pair is a transport/contract pilot, already part of the 144 scheduled samples.
   assert requests[0]['arm']=='T' and requests[1]['arm']=='V' and requests[0]['query_id']==requests[1]['query_id']
   next_index=0;pilot_passed=False
   while pending or (next_index<144 and failure is None):
    ceiling=144 if pilot_passed else 2
    while failure is None and len(pending)<2 and next_index<ceiling:
     if not submit_one(requests[next_index]):failure='budget_admission_stop';break
     next_index+=1
    status('MODEL_PILOT' if not pilot_passed else 'MODEL_RUNNING')
    if not pending:break
    completed,_=wait(list(pending),timeout=30,return_when=FIRST_COMPLETED)
    for future in completed:
     r=pending.pop(future)
     try:result=future.result()
     except Exception as exc:result=dict(transport_ok=False,request_id=r['request_id'],exception_type=type(exc).__name__,charge_usd=reserves[r['request_id']])
     spent+=result['charge_usd']
     if not result['transport_ok']:
      errors.append(result);save(P/'API_ERRORS.json',errors);failure='transport_or_storage_failure'
     else:
      decisions.append(result);save(P/'MODEL_PROGRESS.json',decisions)
      print('completed',len(decisions),'/144',r['arm'],r['view'],'valid',result['valid'],flush=True)
      if not pilot_passed and not result['valid']:failure='technical_pilot_contract_failure'
    if not pilot_passed and next_index==2 and not pending and failure is None:
     assert len(decisions)==2 and all(x['valid'] for x in decisions)
     save(P/'PILOT_ACCEPTANCE.json',dict(at=now(),exit_code=0,requests=[r['request_id'] for r in requests[:2]],actual_image_call_verified=True,GT_read=False))
     pilot_passed=True
    if spent>cap:failure='usage_exceeds_reserved_cap'
   status('MODEL_DRAINED')
  if failure:raise RuntimeError(failure)
  assert len(decisions)==144 and not errors and submitted==144
  verify_freeze();byid={x['request_id']:x for x in decisions};ordered=[byid[x['request_id']] for x in requests]
  save(P/'MODEL_DECISIONS.json',ordered)
  seals=['MODEL_DECISIONS.json','MODEL_FREEZE.json','REQUESTS.json','COST_ADMISSION.json']+[f"raw_responses/{x['request_id']}.json" for x in requests]
  status('MODEL_SEALED_AWAITING_EVALUATION')
  save(P/'MODEL_ACCEPTANCE.json',dict(at=now(),exit_code=0,formal_requests=144,network_attempts=submitted,valid=sum(x['valid'] for x in ordered),seconds=time.monotonic()-started,conservative_cost_usd=spent,GT_read=False,opened_paths=sorted(set(OPENED)),hashes={name:sha(P/name) for name in seals}))
 except Exception as exc:
  save(P/'MODEL_FAILURE.json',dict(at=now(),type=type(exc).__name__,reason=failure or 'local_assertion_or_storage_failure',completed=len(decisions),attempts=submitted,policy='Preserve every admission/response; never restart from zero or score partial output for promotion.'))
  status('MODEL_FAILED');raise
if __name__=='__main__':main()
