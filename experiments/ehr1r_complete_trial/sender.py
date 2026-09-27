"""Isolated, single-use DeepSeek sender. Its /work mount contains no GT or native map."""
import argparse
import hashlib
import json
import os
import struct
import sys
import time
import urllib.request
import zlib
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path('/work')
API='https://api.deepseek.com'
SYSTEM=('Compare the two complete physical identity hypotheses in this causal event packet. '
 'A/B are qualified pre-risk fragments; X/Y are current q-local fragments. '
 'For each H return supporting_fact_ids, conflicting_fact_ids, and unresolved_assumptions. '
 'Return JSON with request_id, hypothesis_assessments, preferred_hypothesis H1/H2/DEFER, and uncertainty_reason. '
 'Use supplied measurements and actually sent images only. Anonymous observations or track handles during contact '
 'do not certify fish identity. A candidate path is a HYPOTHESIS, never an observed trajectory. '
 'Do not invent physical quantities, water-surface depth, fish heading from mask axis, unseen frames, probabilities, '
 'or tracker edits. Prefer DEFER if evidence cannot distinguish candidates. Return JSON only.')
INPUT_RATE=.30
OUTPUT_RATE=1.20


def now():return datetime.now(timezone.utc).isoformat()
def wire(x):return json.dumps(x,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
def sha(x):return hashlib.sha256(x).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def lines(p):return [json.loads(x) for x in Path(p).read_text().splitlines()] if Path(p).exists() else []
def save(p,x):
    p=Path(p);assert not p.exists(),p;p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('xb') as fh:
        fh.write(wire(x)+b'\n');fh.flush();os.fsync(fh.fileno())
def append(p,x):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('ab') as fh:
        fh.write(wire(x)+b'\n');fh.flush();os.fsync(fh.fileno())


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None


def post(endpoint,data,key,content_type):
    assert endpoint in ('/files','/chat/completions')
    req=urllib.request.Request(API+endpoint,data=data,method='POST',headers={
        'Authorization':'Bearer '+key,'Content-Type':content_type})
    with urllib.request.build_opener(NoRedirect).open(req,timeout=900) as response:
        result=response.read(16*1024*1024+1)
        assert len(result)<=16*1024*1024
        return result


def multipart(digest,raw):
    boundary='ehr1rc-'+digest[:30]
    head=(f'--{boundary}\r\nContent-Disposition: form-data; name="purpose"\r\n\r\nuser_data\r\n'
          f'--{boundary}\r\nContent-Disposition: form-data; name="expires_after[anchor]"\r\n\r\ncreated_at\r\n'
          f'--{boundary}\r\nContent-Disposition: form-data; name="expires_after[seconds]"\r\n\r\n2592000\r\n'
          f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="image_{digest[:24]}.png"\r\n'
          'Content-Type: image/png\r\n\r\n').encode()
    return head+raw+f'\r\n--{boundary}--\r\n'.encode(),boundary


def upload(digest,raw,key):
    ledger=ROOT/'UPLOAD_LEDGER.jsonl';payload,boundary=multipart(digest,raw)
    append(ledger,dict(phase='START',at=now(),sha256=digest,bytes=len(raw)))
    try:
        result=post('/files',payload,key,'multipart/form-data; boundary='+boundary)
        obj=json.loads(result);file_id=obj['id']
        assert file_id.startswith('file-api-') and obj['bytes']==len(raw)
        append(ledger,dict(phase='END',at=now(),sha256=digest,file_id=file_id,response_sha256=sha(result)))
        return file_id
    except Exception as exc:
        append(ledger,dict(phase='ERROR',at=now(),sha256=digest,error_type=type(exc).__name__,
                           http_code=getattr(exc,'code',None)))
        raise RuntimeError('upload failed; no automatic retry') from None


def uploaded():
    events=lines(ROOT/'UPLOAD_LEDGER.jsonl')
    starts={x['sha256'] for x in events if x['phase']=='START'}
    done={x['sha256']:x['file_id'] for x in events if x['phase']=='END'}
    assert starts==set(done),'uncertain upload; stop rather than automatically retry'
    return done


def body(request,ids):
    core=json.loads(request['text'])
    assert core['request_id']=='EHR1R-C-'+request['case']
    assert [x['image_id'] for x in core['IMAGE_INDEX']]==[x['image_id'] for x in request['images']]
    for forbidden in ('SRC-F','frame_local:n:','native_mask_key','SCORE_KEY','GT2','GT6','/home/'):
        assert forbidden not in request['text'],forbidden
    return dict(model='deepseek-flash',messages=[dict(role='system',content=SYSTEM),
        dict(role='user',content=[dict(type='text',text=request['text'])]+
             [dict(type='file',file_id=ids[x['sha256']]) for x in request['images']])],
        thinking=dict(type='enabled'),reasoning_effort='high',max_tokens=65536,
        response_format=dict(type='json_object'),stream=False)


def plan():
    p=read(ROOT/'PLAN.json');requests=p['requests']
    assert len(requests)==25 and len({x['attempt_id'] for x in requests})==25
    assert p['model']=='deepseek-flash' and p['max_tokens']==65536 and p['cap_usd']<=3
    return p


def reserve():
    gate=read(ROOT/'SENDER_GATE.json')
    assert gate['status']=='PASS' and gate['request_count']==25 and gate['cap_usd']<=3
    assert gate['plan_sha256']==sha((ROOT/'PLAN.json').read_bytes())
    rates={x['attempt_id']:x['reserve_usd'] for x in gate['request_budget']}
    rates['S001']=gate['smoke_reserve_usd']
    assert len(rates)==26 and sum(rates.values())<=gate['cap_usd']+1e-9
    return rates


def verify_ready():
    p=plan();rates=reserve();seal=read(ROOT/'public/REQUESTS_SEALED.json')
    assert seal['status']=='ALL_25_BODIES_FROZEN_BEFORE_FORMAL'
    assert seal['logical_sha256']==sha((ROOT/'REQUESTS_LOGICAL.json').read_bytes())
    assert seal['manifest_sha256']==sha((ROOT/'REQUEST_MANIFEST.json').read_bytes())
    assert seal['lock_sha256']==sha((ROOT/'CODE_AND_INPUT_LOCK.json').read_bytes())
    assert seal['body_gate_sha256']==sha((ROOT/'BODY_GATE.json').read_bytes())
    assert sha(Path(__file__).read_bytes())==read(ROOT/'CODE_AND_INPUT_LOCK.json')['code_sha256']['sender.py']
    assert len(seal['records'])==25
    return p,rates,{x['attempt_id']:x for x in seal['records']}


def budget(rates,cap):
    events=lines(ROOT/'public/CALL_LEDGER.jsonl')
    starts={};ends={}
    for x in events:
        if x['phase']=='START':
            assert x['attempt_id'] not in starts;starts[x['attempt_id']]=x
        elif x['phase']=='END':
            assert x['attempt_id'] in starts and x['attempt_id'] not in ends;ends[x['attempt_id']]=x
        else:raise AssertionError(x['phase'])
    assert set(starts)==set(ends),'unresolved HTTP; do not retry or start another request'
    assert len(starts)<=26
    spent=sum(x['charged_upper_usd'] for x in ends.values())
    remaining=sum(value for key,value in rates.items() if key not in starts)
    assert spent+remaining<=cap+1e-9,(spent,remaining,cap)
    return starts,ends


def invoke(attempt,payload,key,rates,cap,smoke=False):
    starts,_=budget(rates,cap)
    assert attempt not in starts and len(starts)<26
    reserve_usd=rates[attempt]
    append(ROOT/'public/CALL_LEDGER.jsonl',dict(phase='START',at=now(),attempt_id=attempt,
        payload_sha256=sha(payload),reserve_peak_usd=reserve_usd))
    began=time.monotonic()
    try:
        raw=post('/chat/completions',payload,key,'application/json')
        raw_path=ROOT/'raw'/(attempt+'.json');raw_path.parent.mkdir(parents=True,exist_ok=True)
        assert not raw_path.exists();raw_path.write_bytes(raw)
        obj=json.loads(raw);choice=obj['choices'][0];usage=obj.get('usage') or {}
        prompt,completion=usage.get('prompt_tokens'),usage.get('completion_tokens')
        charge=((prompt*INPUT_RATE+completion*OUTPUT_RATE)/1e6
                if type(prompt) is int and type(completion) is int else reserve_usd)
        content=choice['message'].get('content');finish=choice.get('finish_reason')
        smoke_ok=None
        if smoke:
            try:
                parsed=json.loads(content)
                smoke_ok=(parsed.get('left_color','').lower()=='red' and
                          parsed.get('right_color','').lower()=='blue' and finish=='stop')
            except (ValueError,TypeError,AttributeError):smoke_ok=False
        public=dict(attempt_id=attempt,at=now(),transport_valid=True,response_id=obj.get('id'),
            returned_model=obj.get('model'),finish_reason=finish,content=content,usage=usage,
            smoke_ok=smoke_ok,raw_private_sha256=sha(raw),
            reasoning_private_sha256=sha(str(choice['message'].get('reasoning_content') or '').encode()),
            latency_seconds=time.monotonic()-began,charged_upper_usd=charge,reserve_peak_usd=reserve_usd)
        path=ROOT/'public/responses'/(attempt+'.json');save(path,public)
        append(ROOT/'public/CALL_LEDGER.jsonl',dict(phase='END',at=now(),attempt_id=attempt,
            transport_valid=True,charged_upper_usd=charge,response_sha256=sha(path.read_bytes())))
        assert charge<=reserve_usd,'actual charge exceeded frozen reserve'
        return public
    except Exception as exc:
        # A START without END is genuinely unknown; do not invent a transport outcome.
        save(ROOT/'errors'/(attempt+'.json'),dict(at=now(),attempt_id=attempt,
            error_type=type(exc).__name__,http_code=getattr(exc,'code',None),
            elapsed_seconds=time.monotonic()-began))
        raise RuntimeError('inference outcome uncertain; stop new START') from None


def smoke_png():
    def chunk(name,data):return struct.pack('>I',len(data))+name+data+struct.pack('>I',zlib.crc32(name+data))
    rows=b''.join(b'\x00'+b'\xff\x00\x00'*128+b'\x00\x00\xff'*128 for _ in range(256))
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',256,256,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(rows))+chunk(b'IEND',b'')


def partial(reason):
    path=ROOT/'public/PARTIAL_RESPONSES_SEALED.json'
    if path.exists():return
    requests=plan()['requests'];events=lines(ROOT/'public/CALL_LEDGER.jsonl')
    starts={x['attempt_id'] for x in events if x['phase']=='START'}
    ends={x['attempt_id'] for x in events if x['phase']=='END'}
    save(path,dict(status='PARTIAL_STOP',reason=reason,at=now(),
        request_seal_sha256=sha((ROOT/'public/REQUESTS_SEALED.json').read_bytes()),
        ledger_sha256=sha((ROOT/'public/CALL_LEDGER.jsonl').read_bytes()),
        attempts=[dict(attempt_id=x['attempt_id'],state='UNSENT' if x['attempt_id'] not in starts else
            'HTTP_UNKNOWN' if x['attempt_id'] not in ends else 'RETURNED') for x in requests]))


def main(phase):
    p=plan();key=None
    if phase=='upload':
        frozen=read(ROOT/'PREUPLOAD_LOCK.json')
        assert frozen['status']=='CODE_LOGICAL_REQUEST_BUDGET_SCORER_GATES_FROZEN_BEFORE_UPLOAD'
        assert frozen['code_sha256']['sender.py']==sha(Path(__file__).read_bytes())
        for name in ('REQUESTS_LOGICAL.json','REQUEST_MANIFEST.json','PLAN.json','SENDER_GATE.json'):
            assert frozen['input_sha256'][name]==sha((ROOT/name).read_bytes()),name
    if phase in ('upload','smoke','formal'):
        key=sys.stdin.readline().strip();assert key and len(key)<512
    if phase=='upload':
        assert not (ROOT/'public/CALL_LEDGER.jsonl').exists()
        done=uploaded()
        for request in p['requests']:
            for image in request['images']:
                digest=image['sha256'];raw=(ROOT/'media'/image['media_file']).read_bytes()
                assert sha(raw)==digest and len(raw)==image['bytes']
                if digest not in done:done[digest]=upload(digest,raw,key)
        assert len(done)==55
        print('UPLOADS_55_COMPLETE',flush=True);return
    if phase=='freeze':
        assert not (ROOT/'public/CALL_LEDGER.jsonl').exists()
        done=uploaded();assert len(done)==55
        records=[]
        for request in p['requests']:
            attempt=request['attempt_id'];data=wire(body(request,done))
            path=ROOT/'bodies'/(attempt+'.json');path.parent.mkdir(parents=True,exist_ok=True)
            assert not path.exists();path.write_bytes(data)
            records.append(dict(attempt_id=attempt,payload_sha256=sha(data),payload_bytes=len(data)))
        save(ROOT/'BODY_RECORDS.json',records)
        print('BODIES_25_FROZEN',flush=True);return
    if phase=='seal':
        assert not (ROOT/'public/CALL_LEDGER.jsonl').exists()
        gate=read(ROOT/'BODY_GATE.json');assert gate['bodies']['status']=='BODY_GATE_PASS'
        assert read(ROOT/'CODE_AND_INPUT_LOCK.json')['input_sha256']['BODY_GATE.json']==sha((ROOT/'BODY_GATE.json').read_bytes())
        records=read(ROOT/'BODY_RECORDS.json')
        assert records==gate['bodies']['records']
        save(ROOT/'public/REQUESTS_SEALED.json',dict(status='ALL_25_BODIES_FROZEN_BEFORE_FORMAL',
            at=now(),logical_sha256=sha((ROOT/'REQUESTS_LOGICAL.json').read_bytes()),
            manifest_sha256=sha((ROOT/'REQUEST_MANIFEST.json').read_bytes()),
            body_gate_sha256=sha((ROOT/'BODY_GATE.json').read_bytes()),
            lock_sha256=sha((ROOT/'CODE_AND_INPUT_LOCK.json').read_bytes()),records=records))
        print('REQUESTS_SEALED',flush=True);return
    p,rates,records=verify_ready()
    if phase=='smoke':
        assert not (ROOT/'public/CALL_LEDGER.jsonl').exists()
        raw=smoke_png();file_id=upload(sha(raw),raw,key)
        payload=wire(dict(model='deepseek-flash',messages=[
            dict(role='system',content='Technical image routing check; answer JSON from the actual image.'),
            dict(role='user',content=[dict(type='text',text='Which color is the left half and right half? Return left_color and right_color. Do not guess if unseen.'),
                                      dict(type='file',file_id=file_id)])],thinking=dict(type='enabled'),
            reasoning_effort='high',max_tokens=65536,response_format=dict(type='json_object'),stream=False))
        result=invoke('S001',payload,key,rates,p['cap_usd'],smoke=True)
        print(dict(smoke_ok=result['smoke_ok'],charge=result['charged_upper_usd']),flush=True)
        assert result['smoke_ok'],'smoke failed, no formal calls'
        return
    assert phase=='formal'
    assert read(ROOT/'public/responses/S001.json')['smoke_ok'] is True
    try:
        for request in p['requests']:
            if (ROOT/'STOP_NEW_START').exists():
                partial('PREDECLARED_STOP_NEW_START');return
            attempt=request['attempt_id']
            events=lines(ROOT/'public/CALL_LEDGER.jsonl')
            assert attempt not in {x['attempt_id'] for x in events if x['phase']=='START'}
            payload=(ROOT/'bodies'/(attempt+'.json')).read_bytes()
            assert sha(payload)==records[attempt]['payload_sha256']
            result=invoke(attempt,payload,key,rates,p['cap_usd'])
            print(dict(attempt=attempt,finish_reason=result['finish_reason'],
                       charged_upper_usd=result['charged_upper_usd']),flush=True)
        responses=[dict(attempt_id=x['attempt_id'],response_sha256=sha((ROOT/'public/responses'/(x['attempt_id']+'.json')).read_bytes())) for x in p['requests']]
        save(ROOT/'public/RESPONSES_SEALED.json',dict(status='ALL_25_RESPONSES_SEALED_BEFORE_SCORE',
            at=now(),request_seal_sha256=sha((ROOT/'public/REQUESTS_SEALED.json').read_bytes()),records=responses))
        print('ALL_25_RESPONSES_SEALED_BEFORE_SCORE',flush=True)
    except Exception:
        partial('TECHNICAL_OR_BUDGET_STOP')
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=('upload','freeze','seal','smoke','formal'))
    main(parser.parse_args().phase)
