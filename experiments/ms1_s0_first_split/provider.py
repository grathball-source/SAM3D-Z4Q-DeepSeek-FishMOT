"""Single-use official DeepSeek Files/chat route with bounded accounting."""
import hashlib
import json
import os
import time
import urllib.request
from pathlib import Path

HERE=Path(__file__).resolve().parent
PRICE_INPUT=.30
PRICE_OUTPUT=1.20
MAX_TOKENS=65536
INPUT_RESERVE=300000
PER_SLOT_USD=(INPUT_RESERVE*PRICE_INPUT+MAX_TOKENS*PRICE_OUTPUT)/1_000_000


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def write_new(path,value):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    raw=(json.dumps(value,ensure_ascii=False,separators=(',',':'))+'\n').encode()
    with path.open('xb') as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    return digest(raw)


def append(path,value):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('a',encoding='utf-8') as handle:
        handle.write(json.dumps(value,ensure_ascii=False,separators=(',',':'))+'\n')
        handle.flush()
        os.fsync(handle.fileno())


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        return None


def request(endpoint,payload,content_type):
    assert endpoint in ('/files','/chat/completions')
    req=urllib.request.Request('https://api.deepseek.com'+endpoint,data=payload,
        headers={'Authorization':'Bearer '+os.environ['DEEPSEEK_API_KEY'],
                 'Content-Type':content_type},method='POST')
    with urllib.request.build_opener(NoRedirect).open(req,timeout=900) as response:
        raw=response.read(16*1024*1024+1)
    assert len(raw)<=16*1024*1024
    return raw


def unique_object(pairs):
    out={}
    for key,value in pairs:
        if key in out:
            raise ValueError('duplicate_json_key')
        out[key]=value
    return out


def parse_split(content,finish_reason=None):
    if finish_reason!='stop' or not isinstance(content,str):
        return None,'TRUNCATED_OR_NON_TEXT'
    text=content.strip()
    if text.startswith('```') and text.endswith('```'):
        text=text.split('\n',1)[1].rsplit('```',1)[0].strip()
    try:
        obj=json.loads(text,object_pairs_hook=unique_object)
    except (ValueError,TypeError,IndexError):
        return None,'UNPARSEABLE'
    if not isinstance(obj,dict):
        return None,'NON_OBJECT'
    choices=[obj[k] for k in ('choice','preferred_hypothesis','selected_hypothesis') if k in obj]
    if not choices or any(x not in ('H1','H2','DEFER') for x in choices) or len(set(choices))!=1:
        return None,'AMBIGUOUS_CHOICE'
    choice=choices[0]
    if 'mapping' in obj:
        expected={'H1':{'A':'X','B':'Y'},'H2':{'A':'Y','B':'X'}}.get(choice)
        got=obj['mapping']
        if expected is None or not isinstance(got,dict) or any(got.get(k)!=v for k,v in expected.items()):
            return None,'CONFLICTING_MAPPING'
    return choice,'OK'


class Provider:
    def __init__(self,output,config):
        self.output=Path(output)
        self.config=config
        self.uploaded={}
        self.attempts=0
        self.spent_upper=0.
        self.send_enabled=True

    def upload(self,image):
        sha=image['sha256']
        if sha in self.uploaded:
            return self.uploaded[sha]
        path=Path(image['path'])
        raw=path.read_bytes()
        assert digest(raw)==sha and raw[:8]==b'\x89PNG\r\n\x1a\n'
        boundary='ms1-'+sha[:30]
        header=(f'--{boundary}\r\nContent-Disposition: form-data; name="purpose"\r\n\r\nuser_data\r\n'
                f'--{boundary}\r\nContent-Disposition: form-data; name="expires_after[anchor]"\r\n\r\ncreated_at\r\n'
                f'--{boundary}\r\nContent-Disposition: form-data; name="expires_after[seconds]"\r\n\r\n2592000\r\n'
                f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="geometry.png"\r\n'
                'Content-Type: image/png\r\n\r\n').encode()
        append(self.output/'private_api/UPLOAD_LEDGER.jsonl',dict(phase='START',sha256=sha,bytes=len(raw),at=time.time()))
        try:
            reply=request('/files',header+raw+f'\r\n--{boundary}--\r\n'.encode(),
                          'multipart/form-data; boundary='+boundary)
            obj=json.loads(reply)
            assert obj['id'].startswith('file-api-') and obj['bytes']==len(raw)
            self.uploaded[sha]=obj['id']
            append(self.output/'private_api/UPLOAD_LEDGER.jsonl',
                   dict(phase='END',sha256=sha,file_id=obj['id'],response_sha256=digest(reply),at=time.time()))
            append(self.output/'public/MEDIA_LEDGER.jsonl',dict(phase='UPLOADED',sha256=sha,bytes=len(raw)))
            return obj['id']
        except Exception as exc:
            append(self.output/'private_api/UPLOAD_LEDGER.jsonl',
                   dict(phase='UNKNOWN',sha256=sha,error=type(exc).__name__,at=time.time()))
            self.send_enabled=False
            return None

    def infer(self,episode,stage,packet,images):
        tag=episode['id']+'-'+stage
        public=self.output/'public'
        write_new(public/'requests'/f'{tag}.json',packet)
        if not self.send_enabled:
            append(public/'CALL_LEDGER.jsonl',dict(phase='UNSENT',tag=tag,reason='send_disabled',at=time.time()))
            return None,'UNSENT',None
        assert self.attempts<self.config['max_inference_http']
        assert self.spent_upper+PER_SLOT_USD<=self.config['budget_usd']
        estimate=int(.6*(len(packet['system'])+len(packet['user'])))+16384*len(images)+1024
        assert estimate<=INPUT_RESERVE,(estimate,INPUT_RESERVE)
        file_ids=[]
        for image in images:
            file_id=self.upload(image)
            if file_id is None:
                append(public/'CALL_LEDGER.jsonl',dict(phase='UNSENT',tag=tag,reason='upload_unknown',at=time.time()))
                return None,'UPLOAD_UNKNOWN',None
            file_ids.append(file_id)
        body=dict(model='deepseek-flash',messages=[dict(role='system',content=packet['system']),
              dict(role='user',content=[dict(type='text',text=packet['user'])]+
                   [dict(type='file',file_id=f) for f in file_ids])],
              thinking=dict(type='enabled'),reasoning_effort='high',max_tokens=MAX_TOKENS,
              response_format=dict(type='json_object'),stream=False)
        payload=json.dumps(body,ensure_ascii=False,separators=(',',':')).encode()
        write_new(self.output/'private_api'/f'{tag}.body.json',body)
        body_sha=digest(payload)
        started=time.monotonic()
        append(public/'CALL_LEDGER.jsonl',dict(phase='START',tag=tag,at=time.time(),
            request_start_monotonic=started,
            body_sha256=body_sha,public_packet_sha256=digest(json.dumps(packet,ensure_ascii=False,separators=(',',':')).encode()),
            peak_reserve_usd=PER_SLOT_USD))
        self.attempts+=1
        try:
            raw=request('/chat/completions',payload,'application/json')
            private=self.output/'private_api'/f'{tag}.raw.json'
            with private.open('xb') as handle:
                handle.write(raw)
                handle.flush()
                os.fsync(handle.fileno())
            reply=json.loads(raw)
            answer=reply['choices'][0]
            content=answer['message'].get('content')
            finish=answer.get('finish_reason')
            if stage=='S0':
                choice,status=parse_split(content,finish)
            else:
                choice,status=None,('OK' if finish=='stop' and isinstance(content,str) else 'INVALID_M')
            usage=reply.get('usage') or {}
            prompt,completion=usage.get('prompt_tokens'),usage.get('completion_tokens')
            charge=((prompt*PRICE_INPUT+completion*PRICE_OUTPUT)/1_000_000
                    if type(prompt)==type(completion)==int else PER_SLOT_USD)
            self.spent_upper+=charge
            if isinstance(content,str) and any(x in content for x in ('file-api-','Bearer ','DEEPSEEK_API_KEY')):
                public_content='REDACTED_PRIVATE_TOKEN'
                status='PRIVATE_TOKEN_IN_RESPONSE'
                choice=None
            else:
                public_content=content
            ended=time.monotonic()
            record=dict(tag=tag,episode=episode['id'],stage=stage,content=public_content,
                choice=choice,parse_status=status,finish_reason=finish,returned_model=reply.get('model'),
                usage=usage,peak_charge_upper_usd=charge,latency_seconds=ended-started,
                request_start_monotonic=started,response_end_monotonic=ended,
                raw_private_sha256=digest(raw))
            response_sha=write_new(public/'responses'/f'{tag}.json',record)
            append(public/'CALL_LEDGER.jsonl',dict(phase='END',tag=tag,at=time.time(),
                response_end_monotonic=ended,
                response_sha256=response_sha,peak_charge_upper_usd=charge,parse_status=status))
            return choice,status,record
        except Exception as exc:
            self.spent_upper+=PER_SLOT_USD
            self.send_enabled=False
            append(public/'CALL_LEDGER.jsonl',dict(phase='HTTP_UNKNOWN',tag=tag,at=time.time(),
                response_end_monotonic=time.monotonic(),
                error=type(exc).__name__,http_code=getattr(exc,'code',None),
                latency_seconds=time.monotonic()-started,peak_reserve_usd=PER_SLOT_USD))
            return None,'HTTP_UNKNOWN',None
