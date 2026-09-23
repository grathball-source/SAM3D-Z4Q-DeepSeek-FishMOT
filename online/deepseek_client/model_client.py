from common import *
import urllib.request, urllib.error, base64, time

def credential():
 value=os.environ.get('DEEPSEEK_API_KEY','').strip()
 if not value and os.name=='nt':
  import winreg
  for root,path in [(winreg.HKEY_CURRENT_USER,'Environment'),(winreg.HKEY_LOCAL_MACHINE,r'SYSTEM\CurrentControlSet\Control\Session Manager\Environment')]:
   try:
    with winreg.OpenKey(root,path) as key:value=winreg.QueryValueEx(key,'DEEPSEEK_API_KEY')[0].strip()
   except FileNotFoundError:pass
   if value:break
 return value

def payload(request,cfg,prompt):
 content=[dict(type='text',text=json.dumps(request['packet'],ensure_ascii=False,separators=(',',':'),allow_nan=False))]
 assert len(request['image_paths'])==len(request['image_sha256'])
 if request['arm']=='T':assert not request['image_paths']
 for name,expected in zip(request['image_paths'],request['image_sha256']):
  path=(P/name).resolve();assert path.is_relative_to(P.resolve()) and sha(path)==expected
  mime='image/png' if path.suffix.lower()=='.png' else 'image/jpeg'
  encoded=base64.b64encode(path.read_bytes()).decode('ascii')
  content.append(dict(type='image_url',image_url=dict(url=f'data:{mime};base64,{encoded}')))
 return dict(model=cfg['model'],messages=[dict(role='system',content=prompt),dict(role='user',content=content)],
  thinking=cfg['thinking'],reasoning_effort=cfg['reasoning_effort'],max_tokens=cfg['max_tokens'],response_format=cfg['response_format'])

def bound(body,cfg):
 return (len(json.dumps(body,ensure_ascii=False).encode('utf-8'))+1024)/1e6*cfg['peak_usd_per_million_input_tokens']+cfg['max_tokens']/1e6*cfg['peak_usd_per_million_output_tokens']
def charge(response,reserve,cfg):
 usage=response.get('usage') or {}
 if not all(isinstance(usage.get(x),int) and usage[x]>=0 for x in ['prompt_tokens','completion_tokens']):return reserve
 return (usage['prompt_tokens']*cfg['peak_usd_per_million_input_tokens']+usage['completion_tokens']*cfg['peak_usd_per_million_output_tokens'])/1e6
def post(body,key,timeout):
 class NoRedirect(urllib.request.HTTPRedirectHandler):
  def redirect_request(self,*args,**kwargs):return None
 req=urllib.request.Request('https://api.deepseek.com/chat/completions',data=json.dumps(body,ensure_ascii=False).encode('utf-8'),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},method='POST')
 with urllib.request.build_opener(NoRedirect).open(req,timeout=timeout) as response:
  return json.load(response),dict(request_id=response.headers.get('x-request-id'))

def perform(request,cfg,prompt,key):
 body=payload(request,cfg,prompt);reserve=bound(body,cfg);start=time.monotonic()
 try:
  response,headers=post(body,key,cfg['timeout_seconds']);seconds=time.monotonic()-start
  save(P/f"raw_responses/{request['request_id']}.json",dict(response=response,headers=headers,seconds=seconds,request_id=request['request_id']))
 except Exception as exc:
  # Do not serialize exception text or request objects: they may contain sensitive headers.
  return dict(transport_ok=False,request_id=request['request_id'],exception_type=type(exc).__name__,http_code=getattr(exc,'code',None),seconds=time.monotonic()-start,charge_usd=reserve)
 output=None;valid=False;reason=None;finish=None
 try:
  choice=response['choices'][0];finish=choice['finish_reason'];output=json.loads(choice['message']['content'])
  validate(request['packet'],output);valid=finish=='stop'
  if not valid:reason='generation_not_finished'
 except (KeyError,TypeError,ValueError,IndexError):reason='invalid_json_or_contract'
 return dict(transport_ok=True,request_id=request['request_id'],query_id=request['query_id'],arm=request['arm'],view=request['view'],output=output,valid=valid,rejection_reason=reason,finish_reason=finish,
  seconds=seconds,usage=response.get('usage'),returned_model=response.get('model'),system_fingerprint=response.get('system_fingerprint'),charge_usd=charge(response,reserve,cfg))
