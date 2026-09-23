"""Read-only post-hoc SLR-1 decision audit. No API or credential access."""
from pathlib import Path
import json, hashlib, importlib.util, collections, gzip

P=Path(__file__).resolve().parent
ROOT=next(x for x in P.parents if (x/'AGENTS.md').exists())
SRC=ROOT/'tools/sam3_spatial_llm_stage1_20260920/engineering_r3'
def read(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def save(n,x): (P/n).write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
def alias(x): return 'X'+hashlib.sha256(('SLR1:permuted:'+x).encode()).hexdigest()[:8]
spec=importlib.util.spec_from_file_location('slr1_common',SRC/'common.py')
common=importlib.util.module_from_spec(spec); spec.loader.exec_module(common)
ix={x['query_id']:x for x in read(SRC/'PRIVATE_INDEX.json')}
pk={x['query_id']:x for x in read(SRC/'PACKETS.json')}
requests={(x['query_id'],x['variant']):x['packet'] for x in read(SRC/'MODEL_REQUESTS.json')}
md={(x['query_id'],x['variant']):x for x in read(SRC/'MODEL_DECISIONS.json')}
events=read(ROOT/'tools/sam3_interaction_stage_20260918/E0_event_audit/EVENTS_gap15.json')
old={x['query_id']:x for x in read(SRC/'EVENT_RESULTS.json')}
def inverse(q):
 p=pk[q]
 names=set(p['focal_tracks'])|{x['observation'] for x in p['current']}|{x['evidence_id'] for h in p['history'] for x in h['samples']}|{x['observation'] for r in p['recent'] for x in r['observations']}|{q}
 return {alias(s):s for s in names}
def norm(o,inv=None):
 inv=inv or {};tr=lambda x:inv.get(x,x)
 return dict(state=o['state'],action=o['action'],matches=sorted([tr(x['track']),tr(x['observation'])] for x in o['matches']),
  groups=sorted([tr(x['observation']),sorted(tr(t) for t in x['possible_members'])] for x in o['merged_groups']),
  unresolved=sorted(tr(t) for t in o['unresolved_tracks']))
def native_match(q,normed):
 idx=ix[q]
 return sorted([idx['track_native_map'][t],idx['observation_native_map'][o]] for t,o in normed['matches'])

invalid=[];invariance=[];split_details=[]
for (q,v),r in md.items():
 if r['valid']: continue
 packet=requests[q,v];bad=[]
 for ref in r['output']['evidence_refs']:
  try:
   val=common.pointer(packet,ref)
   if val is None: bad.append(dict(ref=ref,error='null'))
  except Exception as e:bad.append(dict(ref=ref,error=type(e).__name__+': '+str(e)))
 out=dict(r['output']);out['evidence_refs']=['/current']
 try:common.validate(packet,out);nonref_valid=True
 except Exception as e:nonref_valid=str(e)
 invalid.append(dict(query_id=q,variant=v,frame=ix[q]['frame'],stage=ix[q]['stage'],bad_refs=bad,
  non_reference_contract_pass=nonref_valid,normalized=norm(r['output'],inverse(q) if v!='original' else {})))
for q,idx in ix.items():
 a,b=md[q,'original'],md[q,'renamed_reversed'];na=norm(a['output']);nb=norm(b['output'],inverse(q))
 strict=a['valid'] and b['valid'] and na==nb
 if not strict:
  if na==nb: category='reference_validity_only_same_physical_decision'
  elif na['action']==nb['action']=='WAIT':category='WAIT_group_hypothesis_difference_no_assignment'
  elif na['action']==nb['action']=='PROPOSE_MATCH':category='different_physical_assignment'
  else:category='MATCH_vs_WAIT'
  invariance.append(dict(query_id=q,frame=idx['frame'],stage=idx['stage'],category=category,
   original_valid=a['valid'],permuted_valid=b['valid'],original=na,permuted=nb,
   original_native_matches=native_match(q,na),permuted_native_matches=native_match(q,nb)))
 if idx['stage']!='first_split':continue
 es=[e for e in events if e['eligible'] and e['merge_frames'] and e['split']==idx['split'] and e['last_independent_frame']==idx['pre'] and e['split_first_frame']==idx['frame'] and sorted(e['pre_native_ids'])==sorted(idx['track_native_map'].values())]
 assert len(es)==1;e=es[0]
 truth=dict(zip(e['pre_native_ids'],e['post_native_ids']))
 prepublic=dict(zip(e['pre_native_ids'],e['pre_public_ids']))
 postpub=dict(zip(e['post_native_ids'],e['post_public_ids']))
 local_pub_correct=e['pre_public_ids']==e['post_public_ids']
 assert local_pub_correct==e['stable']['first_split_correct']
 na_native=dict(native_match(q,na));nb_native=dict(native_match(q,nb))
 record=dict(query_id=q,event_id=e['event_id'],frame=idx['frame'],pre=idx['pre'],fish_pair=e['fish_pair'],
  truth_native_mapping=truth,pre_public_by_native=prepublic,post_public_by_native=postpub,
  public_ids_unique=len(set(e['pre_public_ids']))==2,
  stable_local_continuity=local_pub_correct,stable_original_flag=e['stable']['first_split_correct'],
  original_valid=a['valid'],permuted_valid=b['valid'],original_state=na['state'],permuted_state=nb['state'],
  original_native_matches=na_native,permuted_native_matches=nb_native,
  original_payload_correspondence_correct=(na['state']=='MATCH' and na_native==truth),
  permuted_payload_correspondence_correct=(nb['state']=='MATCH' and nb_native==truth),
  previous_metrics=old[q]['variants']['L1'],history_summary=[])
 for h in pk[q]['history']:
  record['history_summary'].append(dict(native_id=idx['track_native_map'][h['track']],geometry_independent_reference=h['geometry_independent_reference'],
   history_age_s=[-s['time_s'] for s in h['samples']],velocity_px_s=h['velocity_px_s']))
 record['selected_edge_details']={}
 for label,mapping in [('original',na_native),('truth',truth)]:
  selected=[]
  for t,o in mapping.items():
   tid=next(k for k,v in idx['track_native_map'].items() if v==t);oid=next(k for k,v in idx['observation_native_map'].items() if v==o)
   edge=next(x for x in pk[q]['pairwise'] if x['track']==tid and x['observation']==oid)
   ob=next(x for x in pk[q]['current'] if x['observation']==oid)
   selected.append(dict(track_native=t,observation_native=o,edge=edge,current_quality={k:ob[k] for k in ['area_px','presence','largest_component_fraction','neighbor_count','center_px']}))
  record['selected_edge_details'][label]=selected
 split_details.append(record)
save('INVALID_DETAILS.json',invalid)
save('INVARIANCE_FAILURE_DETAILS.json',invariance)
save('FIRST_SPLIT_DETAILS.json',split_details)
history_ownership=[]
for split in ['development','validation']:
 mp=ROOT/f'tools/sam3_depth_return_guard_20260918/completion_evidence/experiment/offline_matches_{split}.jsonl.gz'
 with gzip.open(mp,'rt',encoding='utf-8') as f: mm=[json.loads(l) for l in f]
 bytime={round(x['time']*1000):x for x in mm};byframe={x['global_frame']:x for x in mm}
 for r in split_details:
  idx=ix[r['query_id']]
  if idx['split']!=split:continue
  qtime=byframe[r['frame']]['time'];base=byframe[r['pre']]['native_to_gt'];samples=[]
  for h in pk[r['query_id']]['history']:
   n=idx['track_native_map'][h['track']];expected=base[str(n)]
   for s in h['samples']:
    rr=bytime[round((qtime+s['time_s'])*1000)];actual=rr['native_to_gt'].get(str(n))
    samples.append(dict(native_id=n,frame=rr['global_frame'],expected_gt_at_pre=expected,actual_gt=actual,
     status='unknown' if actual is None else 'consistent' if actual==expected else 'contradicted'))
  history_ownership.append(dict(query_id=r['query_id'],decision_frame=r['frame'],samples=samples,
   all_known_consistent=all(s['status']=='consistent' for s in samples)))
save('POSTHOC_HISTORY_OWNERSHIP.json',history_ownership)
summary=dict(posthoc_only=True,source_evaluator_unchanged=True,invalid_count=len(invalid),
 invalid_all_reference_only=all(x['non_reference_contract_pass'] is True for x in invalid),
 invariance_failure_categories=dict(collections.Counter(x['category'] for x in invariance)),
 split_invariance_failure_categories=dict(collections.Counter(x['category'] for x in invariance if x['stage']=='first_split')),
 stable_metric_is_local_continuity=True,all_18_stable_local_flags_reproduced=True,
 all_18_pre_public_ids_unique=all(x['public_ids_unique'] for x in split_details),
 wrong_proposal_frames=[x['frame'] for x in split_details if x['previous_metrics']['wrong_proposal']],
 harm_frames=[x['frame'] for x in split_details if x['previous_metrics']['harms_stable_success']],
 repair_frames=[x['frame'] for x in split_details if x['previous_metrics']['correct_repair']],
 ignoring_reference_contract_original_correct=sum(x['original_payload_correspondence_correct'] for x in split_details),
 ignoring_reference_contract_permuted_correct=sum(x['permuted_payload_correspondence_correct'] for x in split_details))
summary['posthoc_history_ownership_counts']=dict(collections.Counter(s['status'] for r in history_ownership for s in r['samples']))
summary['posthoc_history_events_with_unknown_or_contradicted']=[r['decision_frame'] for r in history_ownership if not r['all_known_consistent']]
save('SUMMARY.json',summary)
print(json.dumps(summary,indent=2))
