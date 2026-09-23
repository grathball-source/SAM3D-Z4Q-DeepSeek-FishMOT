"""Conservative numeric control, frozen before any SLR2 effect scoring."""
from common import *
import math

def decide(packet):
 wait=next(x['option_id'] for x in packet['options'] if x['state']=='UNRESOLVED')
 options=[x for x in packet['options'] if x['state']=='MATCH']
 edges={(x['track'],x['observation']):x for x in packet['pairwise']}
 currents={x['observation']:x for x in packet['current']}
 votes={};ties=[]
 for modality in ['D','A','M']:
  ranked=[]
  for option in options:
   selected=[edges[(x['track'],x['observation'])] for x in option['matches']]
   def usable(edge):
    if not edge['available'][modality] or edge[modality] is None or not math.isfinite(edge[modality]):return False
    if modality=='D':return edge['quality']['depth_valid_fraction_min'] is not None and edge['quality']['depth_valid_fraction_min']>=0.3
    if modality=='M':return edge['history_span_s'] is not None and edge['history_span_s']>=0.25 and edge['history_age_s']<=1 and not edge['quality']['motion_prediction_outside_image']
    return True
   if all(usable(e) for e in selected):ranked.append((sum(e[modality] for e in selected),option['option_id']))
  ranked.sort()
  if ranked:
   if len(ranked)>1 and math.isclose(ranked[0][0],ranked[1][0],rel_tol=1e-9,abs_tol=1e-12):ties.append(modality)
   else:votes[modality]=ranked[0][1]
 if ties or len(votes)<2 or len(set(votes.values()))!=1:return dict(query_id=packet['query_id'],option_id=wait,reason='insufficient_unique_modality_consensus',votes=votes,ties=ties)
 chosen=next(x for x in options if x['option_id']==next(iter(votes.values())))
 for match in chosen['matches']:
  edge=edges[(match['track'],match['observation'])];ob=currents[match['observation']]
  if not edge['quality']['history_geometry_independent'] or ob['area_px']<64 or ob['presence'] is None or ob['presence']<.5 or ob['largest_component_fraction']<.9:
   return dict(query_id=packet['query_id'],option_id=wait,reason='independent_geometry_quality_gate',votes=votes,ties=ties)
 return dict(query_id=packet['query_id'],option_id=chosen['option_id'],reason='unique_modality_consensus_and_quality',votes=votes,ties=ties)

def main():
 sys.addaudithook(guard);limit_cpu();acc=read(P/'PREPARATION_ACCEPTANCE.json');assert acc['exit_code']==0
 for name,h in acc['hashes'].items():assert sha(P/name)==h,name
 result=[decide(packet) for packet in read(P/'PACKETS.json')];save(P/'BASELINE_DECISIONS.json',result)
 save(P/'BASELINE_ACCEPTANCE.json',dict(at=now(),exit_code=0,GT_read=False,count=len(result),hashes={'BASELINE_DECISIONS.json':sha(P/'BASELINE_DECISIONS.json')}))
 print('B2 completed',len(result),flush=True)
if __name__=='__main__':main()
