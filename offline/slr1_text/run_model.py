"""Real official API calls only. No placeholder or local-agent substitution."""
from common import *
sys.addaudithook(guard)
import urllib.request,urllib.error,socket,argparse
from run_baseline import validate
def credential(path=None):
 if path:
  # User explicitly supplies this path. Content is used only in Authorization.
  return Path(path).read_text(encoding='utf-8-sig').strip()
 value=os.environ.get('DEEPSEEK_API_KEY','').strip()
 if not value and os.name=='nt':
  import winreg
  for root,path in [(winreg.HKEY_CURRENT_USER,'Environment'),(winreg.HKEY_LOCAL_MACHINE,r'SYSTEM\CurrentControlSet\Control\Session Manager\Environment')]:
   try:
    with winreg.OpenKey(root,path) as k:value=winreg.QueryValueEx(k,'DEEPSEEK_API_KEY')[0].strip()
   except FileNotFoundError:pass
   if value:break
 return value
def post(payload,key,timeout):
 req=urllib.request.Request('https://api.deepseek.com/chat/completions',data=json.dumps(payload,ensure_ascii=False).encode(),
  headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},method='POST')
 # Authorization is never logged. Redirects are rejected to avoid credential forwarding.
 class NoRedirect(urllib.request.HTTPRedirectHandler):
  def redirect_request(self,*args,**kwargs):return None
 with urllib.request.build_opener(NoRedirect).open(req,timeout=timeout) as response:
  return json.load(response),dict(request_id=response.headers.get('x-request-id'))
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--key-file');parser.add_argument('--credential-check',action='store_true');a=parser.parse_args()
 key=credential(a.key_file)
 if a.credential_check:
  print(json.dumps(dict(configured=bool(key))));return
 limit_cpu();cfg=read(P/'MODEL_CONFIG.json')
 if not key:
  save(P/'STATUS.json',dict(stage='AWAITING_API_KEY',at=now(),packets_ready=(P/'PACKETS_ACCEPTANCE.json').exists(),
   baseline_complete=(P/'BASELINE_ACCEPTANCE.json').exists(),model=cfg['model'],model_calls=0))
  print('API credential not configured; no network call made.',flush=True);return
 assert (P/'BASELINE_ACCEPTANCE.json').exists()
 assert read(P/'ADDITIONAL_INPUT_AUDIT.json')['exit_code']==0
 assert not (P/'MODEL_RUN_STARTED.json').exists(),'A formal run already exists; preserve it and do not restart from zero.'
 acc=read(P/'BASELINE_ACCEPTANCE.json')
 for n,h in acc['hashes'].items():assert sha(P/n)==h
 requests=read(P/'MODEL_REQUESTS.json');assert len(requests)==72
 prompt=(P/'PROMPT.txt').read_text(encoding='utf-8');freeze={str(p):sha(p) for p in P.iterdir() if p.suffix in ['.py','.md','.txt'] and p.name not in ['LAUNCH_STATUS.md','ENGINEERING_LOG.md','RESULTS.md','COMPLETION.md']}
 freeze.update({str(P/n):sha(P/n) for n in ['MODEL_CONFIG.json','PACKETS.json','MODEL_REQUESTS.json','BASELINE_DECISIONS.json']})
 save(P/'MODEL_FREEZE.json',freeze)
 # UTF-8 byte count is deliberately conservative for a token-budget admission bound.
 def bound(payload):
  b=len(json.dumps(payload,ensure_ascii=False).encode())+1024
  return b/1e6*cfg['peak_usd_per_million_input_tokens']+cfg['max_tokens']/1e6*cfg['peak_usd_per_million_output_tokens']
 payloads=[dict(model=cfg['model'],messages=[dict(role='system',content=prompt),dict(role='user',content=json.dumps(r['packet'],ensure_ascii=False,separators=(',',':')))],
  thinking=cfg['thinking'],reasoning_effort=cfg['reasoning_effort'],max_tokens=cfg['max_tokens'],response_format=cfg['response_format']) for r in requests]
 worst_all=sum(bound(p)*2 for p in payloads)
 spent=cfg['prior_engineering_calls_reserve_usd']
 assert spent+max(map(bound,payloads))<=cfg['maximum_admitted_estimated_usd']
 with (P/'MODEL_RUN_STARTED.json').open('x',encoding='utf-8') as f:json.dump(dict(at=now(),pid=os.getpid(),formal_requests=72,budget_cap_usd=cfg['maximum_admitted_estimated_usd'],prior_reserve_usd=spent,all_requests_all_retries_worst_case_usd=worst_all,budget_policy='per-attempt admission with actual usage accounting'),f)
 decisions=[];start=time.monotonic();calls=0
 try:
  for i,(r,payload) in enumerate(zip(requests,payloads)):
   save(P/'STATUS.json',dict(stage='MODEL_RUNNING',at=now(),pid=os.getpid(),completed=len(decisions),total=72,network_attempts=calls,model=cfg['model'],conservative_cost_used_usd=spent))
   response=None
   for attempt in range(2):
    reserve=bound(payload)
    if spent+reserve>cfg['maximum_admitted_estimated_usd']:raise RuntimeError('Budget cap would be exceeded; remaining requests stopped.')
    t=time.monotonic();calls+=1
    try:
     response,headers=post(payload,key,cfg['timeout_seconds']);elapsed=time.monotonic()-t
     usage=response.get('usage') or {}
     charge=(usage['prompt_tokens']*cfg['peak_usd_per_million_input_tokens']+usage['completion_tokens']*cfg['peak_usd_per_million_output_tokens'])/1e6 if 'prompt_tokens' in usage and 'completion_tokens' in usage else reserve
     spent+=charge
     save(P/'COST_ADMISSION.json',dict(at=now(),conservative_used_usd=spent,cap_usd=cfg['maximum_admitted_estimated_usd'],calls=calls,prior_reserve_usd=cfg['prior_engineering_calls_reserve_usd']))
     break
    except (urllib.error.URLError,TimeoutError,socket.timeout) as exc:
     spent+=reserve
     code=getattr(exc,'code',None)
     save(P/f'api_errors/request_{i:03d}_attempt_{attempt}.json',dict(at=now(),type=type(exc).__name__,http_code=code,seconds=time.monotonic()-t))
     if code in [400,401,402,403,404] or attempt==1:raise RuntimeError('API transport/authentication failure; inspect sanitized error record') from None
   save(P/f'raw_responses/{i:03d}.json',dict(query_id=r['query_id'],variant=r['variant'],response=response,headers=headers,seconds=elapsed,attempts=attempt+1))
   content=response['choices'][0]['message'].get('content','');out=None;valid=False;reason=None
   try:
    out=json.loads(content);validate(r['packet'],out);valid=response['choices'][0]['finish_reason']=='stop'
    if not valid:reason='generation_not_finished'
   except (ValueError,KeyError,TypeError,IndexError):reason='invalid_json_or_contract'
   decisions.append(dict(query_id=r['query_id'],variant=r['variant'],output=out,valid=valid,rejection_reason=reason,
    seconds=elapsed,usage=response.get('usage'),returned_model=response.get('model'),system_fingerprint=response.get('system_fingerprint')))
   save(P/'MODEL_PROGRESS.json',decisions)
   print('completed',len(decisions),'/ 72','valid',valid,flush=True)
   if i<2 and response['choices'][0]['finish_reason']=='length':
    raise RuntimeError('Technical pilot truncated; remaining API queue stopped before scoring.')
  for path,h in freeze.items():assert sha(path)==h
  save(P/'MODEL_DECISIONS.json',decisions)
  save(P/'MODEL_ACCEPTANCE.json',dict(at=now(),exit_code=0,formal_requests=72,network_attempts=calls,valid=sum(x['valid'] for x in decisions),
   seconds=time.monotonic()-start,conservative_cost_usd=spent,GT_read=False,opened_paths=sorted(set(OPENED)),hashes={n:sha(P/n) for n in ['MODEL_DECISIONS.json','MODEL_FREEZE.json','MODEL_REQUESTS.json']}))
  save(P/'STATUS.json',dict(stage='MODEL_SEALED_AWAITING_EVALUATION',at=now(),model_calls=72))
 except Exception as exc:
  save(P/'MODEL_FAILURE.json',dict(at=now(),type=type(exc).__name__,completed=len(decisions),network_attempts=calls,
   policy='Keep all attempts; do not delete MODEL_RUN_STARTED or restart from zero. No outcome-driven rerun.'))
  save(P/'STATUS.json',dict(stage='MODEL_FAILED',at=now(),completed=len(decisions),network_attempts=calls))
  raise
if __name__=='__main__':main()
