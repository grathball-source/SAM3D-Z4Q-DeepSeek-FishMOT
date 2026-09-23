from common import *
from copy import deepcopy
from run_baseline import decide
from model_client import payload,bound,charge
from input_checks import canonical_option
from evaluation_checks import run_checks

def main():
 sys.addaudithook(guard);limit_cpu();checks=[]
 def ok(name,condition):
  assert condition,name;checks.append(name)
 def reject(name,fn):
  try:fn()
  except (ValueError,PermissionError):checks.append(name)
  else:raise AssertionError(name)
 requests=read(P/'REQUESTS.json');packet=requests[0]['packet'];e=next(iter(packet['evidence']))
 good=dict(option_id=packet['options'][0]['option_id'],evidence_ids=[e],reason_codes=['ambiguity'])
 ok('legal_catalog_selection',validate(packet,good))
 reject('unknown_option_rejected',lambda:validate(packet,dict(good,option_id='UNKNOWN')))
 reject('invented_evidence_rejected',lambda:validate(packet,dict(good,evidence_ids=['UNKNOWN'])))
 reject('duplicate_evidence_rejected',lambda:validate(packet,dict(good,evidence_ids=[e,e])))
 reject('arbitrary_reason_rejected',lambda:validate(packet,dict(good,reason_codes=['certain'])))
 reject('extra_output_field_rejected',lambda:validate(packet,dict(good,confidence=1)))
 reject('nonobject_output_rejected',lambda:validate(packet,[]))
 for name in ['data/labels/test.json','tools/E0/EVENTS_gap15.json','tools/audit_decisions/a.json','tools/SLR1/EVENT_RESULTS.json']:
  reject('GT_guard_'+name,lambda n=name:guard('open',(str(ROOT/n),'r',0)))
 # Complete synthetic association with independent quality and separate modality voting.
 fixture=dict(query_id='Q',current=[dict(observation=o,area_px=100,presence=.9,largest_component_fraction=1) for o in ['O1','O2']],options=[
  dict(option_id='H1',state='MATCH',matches=[dict(track='T1',observation='O1'),dict(track='T2',observation='O2')]),
  dict(option_id='H2',state='MATCH',matches=[dict(track='T1',observation='O2'),dict(track='T2',observation='O1')]),
  dict(option_id='HW',state='UNRESOLVED',matches=[])],pairwise=[])
 for t in ['T1','T2']:
  for o in ['O1','O2']:
   v=1.0 if t[-1]==o[-1] else 3.0
   fixture['pairwise'].append(dict(track=t,observation=o,D=v,A=v,M=v,available=dict(D=True,A=True,M=True),history_span_s=.5,history_age_s=.5,quality=dict(depth_valid_fraction_min=.9,motion_prediction_outside_image=False,history_geometry_independent=True)))
 ok('two_or_more_modalities_agree_accept',decide(fixture)['option_id']=='H1')
 risk=deepcopy(fixture)
 for edge in risk['pairwise']:edge['quality']['history_geometry_independent']=False
 ok('risk_gate_cannot_cancel_by_normalization',decide(risk)['option_id']=='HW')
 stale=deepcopy(fixture)
 for edge in stale['pairwise']:edge['history_age_s']=5;edge['D']=4-edge['D']
 ok('stale_motion_excluded_disagreeing_D_A_wait',decide(stale)['option_id']=='HW' and 'M' not in decide(stale)['votes'])
 tied=deepcopy(fixture)
 for edge in tied['pairwise']:edge['D']=1
 ok('nonunique_available_modality_forces_wait',decide(tied)['option_id']=='HW')
 poor=deepcopy(fixture);poor['current'][0]['largest_component_fraction']=.7
 ok('fragmented_mask_independent_gate',decide(poor)['option_id']=='HW')
 grouped={};maps=read(P/'REQUEST_MAPS.json');cfg=read(P/'MODEL_CONFIG.json');prompt=(P/'PROMPT.txt').read_text(encoding='utf-8')
 maxbytes=0;repeat_count=0;baseline_pairs=0;pair_count=0
 for r in requests:grouped.setdefault((r['query_id'],r['arm']),{})[r['view']]=r
 for (qid,arm),views in grouped.items():
  original=views['original'];body=payload(original,cfg,prompt);n=len(json.dumps(body,ensure_ascii=False).encode('utf-8'));maxbytes=max(maxbytes,n)
  ok_bound=bound(body,cfg)>charge(dict(usage=dict(prompt_tokens=100,completion_tokens=100)),0,cfg);assert ok_bound
  other=grouped[(qid,'V' if arm=='T' else 'T')]
  for view,r in views.items():assert r['packet']==other[view]['packet'];pair_count+=1
  if 'repeat' in views:
   assert body==payload(views['repeat'],cfg,prompt);repeat_count+=1
   d1=decide(original['packet']);d2=decide(views['permuted']['packet'])
   m1=maps[original['request_id']]['option_map'][d1['option_id']];m2=maps[views['permuted']['request_id']]['option_map'][d2['option_id']]
   assert m1==m2;baseline_pairs+=1
 ok('all_http_payloads_fit_48MiB',maxbytes<48*1024**2)
 ok('original_repeat_complete_payload_equality',repeat_count==36)
 ok('T_V_same_packets_for_every_view',pair_count==144)
 ok('B2_permutation_physical_invariance',baseline_pairs==36)
 save(P/'CONTRACT_CHECKS.json',dict(at=now(),exit_code=0,passed=len(checks),checks=checks,max_request_bytes=maxbytes,exact_repeat_full_payload_checks=repeat_count,GT_read=False))
 evaluation=run_checks();save(P/'EVALUATION_CHECKS.json',dict(at=now(),exit_code=0,**evaluation))
 print('Contract',len(checks),'Evaluation',evaluation['passed'],'PASS',flush=True)
if __name__=='__main__':main()
