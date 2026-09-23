"""Read offline correspondences only after all actual model outputs are sealed."""
from common import *
import statistics
def physical(out,index):
 return {index['track_native_map'][x['track']]:index['observation_native_map'][x['observation']] for x in out['matches']}
def normalized(out,inverse):
 tr=lambda x:inverse.get(x,x)
 return dict(state=out['state'],matches=sorted((tr(x['track']),tr(x['observation'])) for x in out['matches']),
  groups=sorted((tr(x['observation']),tuple(sorted(tr(t) for t in x['possible_members']))) for x in out['merged_groups']),
  unresolved=sorted(tr(t) for t in out['unresolved_tracks']),action=out['action'])
def main():
 limit_cpu();ma=read(P/'MODEL_ACCEPTANCE.json');assert ma['exit_code']==0
 for n,h in ma['hashes'].items():assert sha(P/n)==h
 assert not (P/'EVALUATION_ACCEPTANCE.json').exists()
 for path,h in read(P/'MODEL_FREEZE.json').items():assert sha(path)==h
 models=read(P/'MODEL_DECISIONS.json');assert len(models)==72
 md={(x['query_id'],x['variant']):x for x in models};bd={x['query_id']:x['output'] for x in read(P/'BASELINE_DECISIONS.json')}
 packets={x['query_id']:x for x in read(P/'PACKETS.json')};ix=read(P/'PRIVATE_INDEX.json');indexes={x['query_id']:x for x in ix}
 # Deliberately separate evaluator; it is the only post-selection process to read E0 truth.
 epath=STAGE/'E0_event_audit/EVENTS_gap15.json';assert sha(epath)==read(P/'SELECTION_ACCEPTANCE.json')['source_sha256']
 events=read(epath);event_results=[];invariance=[]
 from copy import deepcopy
 for index in ix:
  qid=index['query_id'];p=packets[qid]
  # Same deterministic renaming algorithm, implemented here without importing guarded model code.
  names=set(p['focal_tracks'])|{x['observation'] for x in p['current']}|{x['evidence_id'] for h in p['history'] for x in h['samples']}|{x['observation'] for r in p['recent'] for x in r['observations']}|{p['query_id']}
  inverse={alias('X','permuted:'+s):s for s in names}
  orig=md[(qid,'original')];perm=md[(qid,'renamed_reversed')]
  inv=bool(orig['valid'] and perm['valid'] and normalized(orig['output'],{})==normalized(perm['output'],inverse))
  invariance.append(dict(query_id=qid,stage=index['stage'],consistent=inv))
  if index['stage']!='first_split':continue
  es=[e for e in events if e['eligible'] and e['merge_frames'] and e['split']==index['split'] and e['last_independent_frame']==index['pre'] and e['split_first_frame']==index['frame'] and sorted(e['pre_native_ids'])==sorted(index['track_native_map'].values())]
  assert len(es)==1;e=es[0];truth=dict(zip(e['pre_native_ids'],e['post_native_ids']));b0=bool(e['stable']['first_split_correct'])
  rr=dict(event=index['event'],query_id=qid,frame=index['frame'],split=index['split'],stable_correct=b0,variants={})
  for name,out,valid in [('B1',bd[qid],True),('L1',orig['output'],orig['valid'])]:
   proposed=bool(valid and out['state']=='MATCH');correct=bool(proposed and physical(out,index)==truth)
   rr['variants'][name]=dict(valid=valid,proposed=proposed,correct_assignment=correct,abstain=not proposed,
    correct_repair=correct and not b0,wrong_proposal=proposed and not correct,
    harms_stable_success=b0 and proposed and not correct,policy_correct=correct if proposed else b0,
    preserves_stable_success=b0 and (correct or not proposed))
  event_results.append(rr)
 assert len(event_results)==18
 sums={}
 for name in ['B1','L1']:
  keys=list(event_results[0]['variants'][name]);sums[name]={k:sum(r['variants'][name][k] for r in event_results) for k in keys}
 stable=sum(r['stable_correct'] for r in event_results)
 valid=sum(x['valid'] for x in models);invsum=sum(x['consistent'] for x in invariance);split_inv=sum(x['consistent'] for x in invariance if x['stage']=='first_split')
 H1=sums['L1']['correct_assignment']>max(stable,sums['B1']['correct_assignment']) and sums['L1']['correct_repair']>=2 and sums['L1']['harms_stable_success']==0
 # Gate uses explicit correct proposals; WAIT fallback is secondary, not LLM success.
 passed=H1 and split_inv==18 and invsum==36 and valid==72
 times=sorted(x['seconds'] for x in models);usage={k:sum((x['usage'] or {}).get(k,0) or 0 for x in models) for k in ['prompt_tokens','completion_tokens','total_tokens','prompt_cache_hit_tokens','prompt_cache_miss_tokens']}
 summary=dict(at=now(),decision='PASS_SHADOW_ONLY' if passed else 'STOP_SLR1',events=18,queries=36,model_responses=72,
  stable_correct=stable,variants=sums,valid_responses=valid,invariance_pass=invsum,split_invariance_pass=split_inv,
  latency_seconds=dict(mean=statistics.mean(times),p95=times[min(len(times)-1,int(.95*len(times)))],maximum=max(times)),usage=usage,
  returned_models=sorted(set(x['returned_model'] for x in models)),oracle_conditioned=True,independent_blind_test=False,
  continuous_tracking_modified=False,notes=['Events are correlated and previously exposed.','No IDF1/HOTA claim; no tracker integration.',
   'WAIT/invalid maintains frozen B0 for shadow policy; this is not a correct LLM repair.','Merge snapshot is offline selected, not physical occlusion truth.'])
 save(P/'EVENT_RESULTS.json',event_results);save(P/'INVARIANCE.json',invariance);save(P/'SUMMARY.json',summary)
 report=f'''# SLR-1 第一阶段结果\n\n判定：**{summary['decision']}**。DeepSeek V4.1 Flash，36原始包+36重排包，真实API结果已封存后评分。\n\n|指标|Z4Q_STABLE|同证据规则B1|LLM L1|\n|---|---:|---:|---:|\n|维持基线后的影子策略正确事件/18|{stable}|{sums['B1']['policy_correct']}|{sums['L1']['policy_correct']}|\n|明确正确匹配提案|—|{sums['B1']['correct_assignment']}|{sums['L1']['correct_assignment']}|\n|正确补救|—|{sums['B1']['correct_repair']}|{sums['L1']['correct_repair']}|\n|破坏原正确|—|{sums['B1']['harms_stable_success']}|{sums['L1']['harms_stable_success']}|\n|弃权/拒绝|—|{sums['B1']['abstain']}|{sums['L1']['abstain']}|\n\n有效输出{valid}/72，重排一致{invsum}/36（首分离{split_inv}/18）。平均延迟{statistics.mean(times):.2f}s，P95 {summary['latency_seconds']['p95']:.2f}s。完整token与逐事件明细见SUMMARY.json、EVENT_RESULTS.json。\n\n本轮事件边界及历史目标由离线oracle指定，事件已暴露且相关；不能宣称自动触发、独立泛化或连续跟踪指标提升。WAIT保留原Stable的结果单独计入影子策略，不当作模型修复。未改变SAM/Z4Q、未训练、未回填历史。即使通过也只允许设计下一阶段。\n'''
 (P/'RESULTS.md').write_text(report,encoding='utf-8')
 save(P/'EVALUATION_ACCEPTANCE.json',dict(at=now(),exit_code=0,model_seal_before_GT=True,model_decisions_sha256=sha(P/'MODEL_DECISIONS.json'),
  hashes={n:sha(P/n) for n in ['EVENT_RESULTS.json','INVARIANCE.json','SUMMARY.json','RESULTS.md']}))
 save(P/'STATUS.json',dict(stage='COMPLETED',at=now(),decision=summary['decision'],model_calls=72))
 print(summary['decision'],flush=True)
if __name__=='__main__':main()
