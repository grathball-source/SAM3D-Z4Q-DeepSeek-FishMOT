"""Identical-packet deterministic comparator, invariance and contract checks."""
from common import *
sys.addaudithook(guard)
import copy,itertools
def wait():return dict(state='UNRESOLVED',matches=[],merged_groups=[],unresolved_tracks=[],action='WAIT',evidence_refs=['/current'])
def decide(p):
 tracks=p['focal_tracks'];edges={(x['track'],x['observation']):(i,x) for i,x in enumerate(p['pairwise'])}
 candidates=[o['observation'] for o in p['current'] if o['area_px']>0];scores=[]
 for permutation in itertools.permutations(candidates,len(tracks)):
  ee=[edges[(t,o)] for t,o in zip(tracks,permutation)]
  if any(x['available_modalities']<2 or x['weighted_cost'] is None for _,x in ee):continue
  scores.append((sum(x['weighted_cost'] for _,x in ee)/len(ee),permutation,[i for i,_ in ee]))
 scores.sort(key=lambda x:x[0]);out=wait();out['unresolved_tracks']=list(tracks)
 if scores and scores[0][0]<=3 and (len(scores)==1 or scores[1][0]-scores[0][0]>=.15):
  best=scores[0];out=dict(state='MATCH',matches=[dict(track=t,observation=o) for t,o in zip(tracks,best[1])],
   merged_groups=[],unresolved_tracks=[],action='PROPOSE_MATCH',evidence_refs=['/pairwise/'+str(i) for i in best[2]])
 validate(p,out);return out
def transform(p):
 # Replace all opaque IDs, then reverse every unordered object list. Time remains time.
 names=set(p['focal_tracks'])|{x['observation'] for x in p['current']}
 names|={x['evidence_id'] for h in p['history'] for x in h['samples']}
 names|={x['observation'] for r in p['recent'] for x in r['observations']}
 names.add(p['query_id']);mapping={s:alias('X','permuted:'+s) for s in names}
 def change(x):
  if isinstance(x,str):return mapping.get(x,x)
  if isinstance(x,list):return [change(z) for z in x]
  if isinstance(x,dict):return {k:change(v) for k,v in x.items()}
  return x
 q=change(p)
 for k in ['focal_tracks','history','current','pairwise']:q[k].reverse()
 for r in q['recent']:r['observations'].reverse()
 return q,mapping
def physical(out,inverse=None):
 inv=inverse or {};tr=lambda x:inv.get(x,x)
 return dict(state=out['state'],action=out['action'],matches=sorted((tr(x['track']),tr(x['observation'])) for x in out['matches']),
  groups=sorted((tr(x['observation']),tuple(sorted(tr(t) for t in x['possible_members']))) for x in out['merged_groups']),
  unresolved=sorted(tr(t) for t in out['unresolved_tracks']))
def check_packet(p):
 forbidden={'global_frame','frame','native_id','public_id','true_choice','fish_pair','stable_correct','split','merge_start','merge_end'}
 def visit(x):
  if isinstance(x,dict):
   assert not forbidden.intersection(x)
   if 'time_s' in x:assert x['time_s']<=0
   for v in x.values():visit(v)
  elif isinstance(x,list):
   for v in x:visit(v)
  elif isinstance(x,float):
   import math
   assert math.isfinite(x)
 visit(p)
 assert len(p['focal_tracks'])==len(set(p['focal_tracks']))==2
 assert len({x['observation'] for x in p['current']})==len(p['current'])
 assert len(p['pairwise'])==len(p['focal_tracks'])*len(p['current'])
 assert all(x['history_age_s'] is None or x['history_age_s']>=0 for x in p['pairwise'])
def contract_tests(p):
 good=wait();good['unresolved_tracks']=p['focal_tracks'];assert validate(p,good)
 ts=p['focal_tracks'];oo=[x['observation'] for x in p['current'] if x['area_px']>0]
 mg=copy.deepcopy(good);mg.update(state='POSSIBLE_MERGE',merged_groups=[dict(observation=oo[0],possible_members=ts)])
 assert validate(p,mg)
 match=copy.deepcopy(good);match.update(state='MATCH',action='PROPOSE_MATCH',unresolved_tracks=[],matches=[dict(track=t,observation=o) for t,o in zip(ts,oo)])
 assert validate(p,match)
 bad=[]
 x=copy.deepcopy(match);x['matches'][1]['observation']=oo[0];bad.append(x)
 x=copy.deepcopy(match);x['matches'][1]['track']=ts[0];bad.append(x)
 x=copy.deepcopy(match);x['matches'][0]['observation']='UNKNOWN';bad.append(x)
 x=copy.deepcopy(match);x['evidence_refs']=['/nonexistent'];bad.append(x)
 x=copy.deepcopy(match);x['evidence_refs']=['/physical_size'];bad.append(x)
 x=copy.deepcopy(match);x['action']='WAIT';bad.append(x)
 x=copy.deepcopy(match);x['unresolved_tracks']=ts;bad.append(x)
 x=copy.deepcopy(mg);x['merged_groups'][0]['possible_members']=[ts[0]];bad.append(x)
 x=copy.deepcopy(good);x['evidence_refs']=[];bad.append(x)
 for x in bad:
  try:validate(p,x)
  except (ValueError,KeyError,IndexError,TypeError):pass
  else:raise AssertionError('invalid proposal accepted')
 dirty=copy.deepcopy(p);dirty['recent'][0]['time_s']=1
 try:check_packet(dirty)
 except AssertionError:pass
 else:raise AssertionError('future input accepted')
 try:read(ROOT/'data/AlignedDataset_v1/labels/000001.json')
 except PermissionError:pass
 else:raise AssertionError('GT access not blocked')
 return 14
def main():
 start=time.monotonic();limit_cpu();assert not (P/'BASELINE_ACCEPTANCE.json').exists()
 acceptance=read(P/'PACKETS_ACCEPTANCE.json');assert sha(P/'PACKETS.json')==acceptance['hashes']['PACKETS.json']
 packets=read(P/'PACKETS.json');assert len(packets)==36;checks=contract_tests(packets[0]);results=[];requests=[]
 for p in packets:
  check_packet(p);out=decide(p);q,mp=transform(p);check_packet(q);outq=decide(q)
  assert physical(out)==physical(outq,{v:k for k,v in mp.items()})
  results.append(dict(query_id=p['query_id'],output=out,permuted_output=outq,invariance=True))
  requests.extend([dict(query_id=p['query_id'],variant='original',packet=p),dict(query_id=p['query_id'],variant='renamed_reversed',packet=q)])
 save(P/'BASELINE_DECISIONS.json',results);save(P/'MODEL_REQUESTS.json',requests)
 save(P/'BASELINE_ACCEPTANCE.json',dict(at=now(),exit_code=0,count=len(results),semantic_checks=checks,packet_checks=36,
  invariance_pass=36,legality_pass=72,GT_read=False,opened_paths=sorted(set(OPENED)),seconds=time.monotonic()-start,
  match_count=sum(x['output']['state']=='MATCH' for x in results),wait_count=sum(x['output']['state']!='MATCH' for x in results),
  hashes={n:sha(P/n) for n in ['BASELINE_DECISIONS.json','MODEL_REQUESTS.json','PACKETS.json']}))
 save(P/'STATUS.json',dict(stage='AWAITING_API_KEY',at=now(),packets=36,baseline_complete=True,model='deepseek-flash',model_calls=0,
  missing='DEEPSEEK_API_KEY or user-specified credential file; Tracking ID is not authentication'))
 print('Same-evidence baseline sealed; 36/36 invariance, 72/72 legal outputs; model calls 0.',flush=True)
if __name__=='__main__':main()
