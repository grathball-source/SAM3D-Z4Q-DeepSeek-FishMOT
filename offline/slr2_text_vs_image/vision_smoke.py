"""One fixed synthetic transport/capability check; never reads research decisions."""
from common import *
sys.addaudithook(guard)
from model_client import credential, post, bound, charge
import base64, time
def main():
 limit_cpu();cfg=read(P/'MODEL_CONFIG.json');key=credential();assert key,'Missing configured credential'
 assert not (P/'SMOKE_STARTED.json').exists(),'Preserve existing smoke attempt; no implicit restart.'
 from PIL import Image, ImageDraw
 path=P/'smoke_stimulus.png';im=Image.new('RGB',(512,256),'white');d=ImageDraw.Draw(im)
 d.rectangle((30,30,225,225),fill=(255,0,0));d.rectangle((285,30,480,225),fill=(0,0,255));im.save(path)
 body=dict(model=cfg['model'],thinking=cfg['thinking'],reasoning_effort=cfg['reasoning_effort'],max_tokens=cfg['max_tokens'],response_format=cfg['response_format'],messages=[dict(role='user',content=[dict(type='text',text='Look at the attached picture. Return only JSON with keys left and right, each containing the basic English color name of the large filled square on that side. Do not infer colors from this text.'),dict(type='image_url',image_url=dict(url='data:image/png;base64,'+base64.b64encode(path.read_bytes()).decode('ascii')))])])
 reserve=bound(body,cfg);assert reserve<cfg['maximum_admitted_estimated_usd']
 save(P/'SMOKE_STARTED.json',dict(at=now(),pid=os.getpid(),reserve_usd=reserve,source_sha256=sha(Path(__file__)),image_sha256=sha(path)))
 start=time.monotonic()
 try:
  response,headers=post(body,key,cfg['timeout_seconds']);save(P/'SMOKE_RESPONSE.json',dict(response=response,headers=headers,seconds=time.monotonic()-start))
  used=charge(response,reserve,cfg);choice=response['choices'][0];out=json.loads(choice['message']['content'])
  passed=choice['finish_reason']=='stop' and out==dict(left='red',right='blue')
  save(P/'SMOKE_ACCEPTANCE.json',dict(at=now(),exit_code=0 if passed else 1,vision_content_verified=passed,output=out,usage=response.get('usage'),returned_model=response.get('model'),conservative_cost_usd=used,image_sha256=sha(path),response_sha256=sha(P/'SMOKE_RESPONSE.json'),seconds=time.monotonic()-start))
  assert passed,'Actual vision transport/content check failed; no text-only fallback.'
  print('Vision smoke passed',flush=True)
 except Exception as exc:
  if not (P/'SMOKE_ACCEPTANCE.json').exists():save(P/'SMOKE_FAILURE.json',dict(at=now(),type=type(exc).__name__,http_code=getattr(exc,'code',None),unknown_billing_reserve_usd=reserve))
  raise
if __name__=='__main__':main()
