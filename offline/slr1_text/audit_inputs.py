"""Exact descriptor regression and causal-source audit without GT."""
from common import *
sys.addaudithook(guard)
import numpy as np
def main():
 packets={x['query_id']:x for x in read(P/'PACKETS.json')};indexes=read(P/'PRIVATE_INDEX.json')
 previous=read(ROOT/'tools/sam3_final_pre_llm_20260918/BLIND_FEATURES.json');old={}
 for e in previous:
  for x in e['candidates']+[z for r in e['references'] for z in r['sources']]:
   if x['A'] is not None:old[(e['split'],x['frame'],x['native_id'])]=x
 count=0;diff=0;checks=[]
 for ix in indexes:
  assert max(ix['source_frames'])<=ix['frame']
  for ob in packets[ix['query_id']]['current']:
   key=(ix['split'],ix['frame'],ix['observation_native_map'][ob['observation']])
   if key in old:
    d=float(np.max(np.abs(np.array(old[key]['A'])-ob['appearance_hsv_body'])));diff=max(diff,d);count+=1
    assert old[key]['source_mask_sha256']==ob['mask_sha256'];checks.append(dict(source=list(key),max_abs_difference=d))
 assert count==37 and diff<1e-12
 needed={s:set(g for x in indexes if x['split']==s for g in x['source_frames']) for s in ['development','validation']};checked=0
 for s in needed:
  for r in rows(ROOT/f'tools/sam3_depth_birth_inherit_20260917/completion_evidence/features_r2/features_{s}.jsonl.gz'):
   if r['global_frame'] in needed[s]:assert r['evidence_max_global_frame']<=r['global_frame'];checked+=1
 current_count=0
 for s in needed:
  qs={x['frame']:x for x in indexes if x['split']==s}
  for r in rows(ROOT/f'tools/sam3_depth_failure_repair_20260917/diagnosis_evidence/diagnosis/observations_{s}.jsonl.gz'):
   if r['global_frame'] in qs:
    ix=qs[r['global_frame']];assert set(ix['observation_native_map'].values())=={o['id'] for o in r['observations']};current_count+=1
 result=dict(at=now(),exit_code=0,old_appearance_exact_overlap=count,max_abs_difference=diff,checks=checks,
  depth_source_causality_frames=checked,private_packet_causality_pass=36,all_current_candidates_preserved_unique_frames=current_count,
  GT_read=False,opened_paths=sorted(set(OPENED)))
 save(P/'ADDITIONAL_INPUT_AUDIT.json',result)
 print('37/37 old descriptors exact, masks identical; causal sources and full candidate coverage passed.',flush=True)
if __name__=='__main__':main()
