"""Single-use, repository-free EHR-1 sender; mount only its sender tree at /work."""
from __future__ import annotations

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

ROOT = Path('/work')
API = 'https://api.deepseek.com'
SYSTEM = ('Compare the two complete physical identity hypotheses from the supplied causal event packet. '
          'A/B are frozen pre-event reference hypotheses; X/Y are current observed fragments. '
          'For each H, identify supporting_fact_ids, conflicting_fact_ids, and unresolved_assumptions. '
          'Return JSON with request_id, hypothesis_assessments array (id, supporting_fact_ids, '
          'conflicting_fact_ids, unresolved_assumptions), preferred_hypothesis H1 or H2 or DEFER, '
          'and uncertainty_reason. Use only supplied measurements and actually sent images. '
          'An anonymous observation or a native track handle during contact does not certify fish identity. '
          'A candidate path is a HYPOTHESIS, never an observed trajectory. Do not invent physical quantities, '
          'water-surface depth, fish heading from a mask axis, unseen frames, probabilities, or tracker edits. '
          'Prefer DEFER if evidence cannot distinguish candidates. Return JSON only.')


def now():
    return datetime.now(timezone.utc).isoformat()


def wire(x):
    return json.dumps(x, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()


def sha(x):
    return hashlib.sha256(x).hexdigest()


def read(p):
    return json.loads(p.read_text(encoding='utf-8'))


def save(p, x):
    assert not p.exists(), p
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('xb') as f:
        f.write(wire(x) + b'\n')
        f.flush()
        os.fsync(f.fileno())


def append(p, x):
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('ab') as f:
        f.write(wire(x) + b'\n')
        f.flush()
        os.fsync(f.fileno())


def lines(p):
    return [json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def post(endpoint, data, key, content_type):
    assert endpoint in ('/files', '/chat/completions')
    request = urllib.request.Request(API + endpoint, data=data, method='POST',
                   headers={'Authorization': 'Bearer ' + key, 'Content-Type': content_type})
    with urllib.request.build_opener(NoRedirect).open(request, timeout=900) as response:
        body = response.read(16 * 1024 * 1024 + 1)
        assert len(body) <= 16 * 1024 * 1024
        return body, response.headers.get('x-ds-trace-id') or response.headers.get('x-request-id')


def multipart(digest, raw):
    boundary = 'ehr1-' + digest[:30]
    header = (f'--{boundary}\r\nContent-Disposition: form-data; name="purpose"\r\n\r\nuser_data\r\n'
              f'--{boundary}\r\nContent-Disposition: form-data; name="expires_after[anchor]"\r\n\r\ncreated_at\r\n'
              f'--{boundary}\r\nContent-Disposition: form-data; name="expires_after[seconds]"\r\n\r\n2592000\r\n'
              f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="image_{digest[:24]}.png"\r\n'
              'Content-Type: image/png\r\n\r\n').encode()
    return header + raw + f'\r\n--{boundary}--\r\n'.encode(), boundary


def upload(digest, raw, key):
    ledger = ROOT / 'private/UPLOAD_LEDGER.jsonl'
    payload, boundary = multipart(digest, raw)
    append(ledger, dict(phase='START', at=now(), sha256=digest, bytes=len(raw)))
    try:
        body, _ = post('/files', payload, key, 'multipart/form-data; boundary=' + boundary)
        obj = json.loads(body)
        file_id = obj['id']
        assert file_id.startswith('file-api-') and obj['bytes'] == len(raw)
        append(ledger, dict(phase='END', at=now(), sha256=digest, file_id=file_id,
                            response_sha256=sha(body)))
        return file_id
    except Exception as e:
        append(ledger, dict(phase='ERROR', at=now(), sha256=digest,
                            error_type=type(e).__name__, http_code=getattr(e, 'code', None)))
        raise RuntimeError('upload failed; do not automatically retry') from None


def upload_all(plan, key):
    done = {x['sha256']: x['file_id'] for x in lines(ROOT / 'private/UPLOAD_LEDGER.jsonl') if x['phase'] == 'END'}
    for request in plan['requests']:
        for image in request['images']:
            digest = image['sha256']
            raw = (ROOT / 'media' / image['media_file']).read_bytes()
            assert sha(raw) == digest and len(raw) == image['bytes']
            if digest not in done:
                done[digest] = upload(digest, raw, key)
    return done


def body(request, uploaded):
    core = json.loads(request['text'])
    assert core['request_id'] == 'EHR1-' + request['case']
    assert [x['image_id'] for x in request['images']] == [x['image_id'] for x in core['IMAGE_INDEX']]
    text = SYSTEM + request['text']
    for forbidden in ('SCORE_KEY', 'GT2', 'GT6', '/home/', 'native_id', 'endpoint_roles', 'old_answer'):
        assert forbidden not in text, forbidden
    return dict(model='deepseek-flash', messages=[dict(role='system', content=SYSTEM),
           dict(role='user', content=[dict(type='text', text=request['text'])] +
                [dict(type='file', file_id=uploaded[x['sha256']]) for x in request['images']])],
           thinking=dict(type='enabled'), reasoning_effort='high', max_tokens=65536,
           response_format=dict(type='json_object'), stream=False)


def freeze(plan, uploaded):
    records = []
    for request in plan['requests']:
        payload = wire(body(request, uploaded))
        attempt = request['attempt_id']
        path = ROOT / 'private/bodies' / (attempt + '.json')
        assert not path.exists()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        records.append(dict(attempt_id=attempt, case=request['case'], arm=request['arm'],
                            payload_sha256=sha(payload), payload_bytes=len(payload),
                            image_count=len(request['images'])))
    for i in range(1, 6):
        a, b = [x for x in records if x['attempt_id'] in (f'B{i:02d}-H-D', f'B{i:02d}-H-D-REPEAT')]
        assert a['payload_sha256'] == b['payload_sha256']
    save(ROOT / 'public/REQUESTS_SEALED.json', dict(status='ALL_25_BODIES_FROZEN_BEFORE_FORMAL',
         at=now(), code_sha256=sha(Path(__file__).read_bytes()),
         plan_sha256=sha((ROOT / 'PLAN.json').read_bytes()),
         system_sha256=sha(SYSTEM.encode()), records=records))


def budget(plan):
    events = lines(ROOT / 'public/CALL_LEDGER.jsonl')
    starts = {x['attempt_id']: x for x in events if x['phase'] == 'START'}
    ends = {x['attempt_id']: x for x in events if x['phase'] == 'END'}
    assert len(starts) == sum(x['phase'] == 'START' for x in events)
    assert len(ends) == sum(x['phase'] == 'END' for x in events)
    assert starts.keys() == ends.keys(), 'unresolved inference must not retry'
    assert len(starts) <= 26
    spent = sum(x['charged_upper_usd'] for x in ends.values())
    remaining = len([x for x in (r['attempt_id'] for r in plan['requests']) if x not in starts]) * plan['reserve_each_usd']
    if 'S001' not in starts:
        remaining += plan['reserve_each_usd']
    assert spent + remaining <= plan['cap_usd'] + 1e-9, (spent, remaining)
    return starts, ends


def invoke(attempt, payload, key, plan, smoke=False):
    starts, _ = budget(plan)
    assert attempt not in starts and len(starts) < 26
    append(ROOT / 'public/CALL_LEDGER.jsonl', dict(phase='START', at=now(), attempt_id=attempt,
           payload_sha256=sha(payload), reserve_peak_usd=plan['reserve_each_usd']))
    began = time.monotonic()
    try:
        raw, trace = post('/chat/completions', payload, key, 'application/json')
        private = ROOT / 'private/raw' / (attempt + '.json')
        private.parent.mkdir(parents=True, exist_ok=True)
        assert not private.exists()
        private.write_bytes(raw)
        response = json.loads(raw)
        choice = response['choices'][0]
        usage = response.get('usage') or {}
        prompt, completion = usage.get('prompt_tokens'), usage.get('completion_tokens')
        charge = ((prompt * .30 + completion * 1.20) / 1e6
                  if type(prompt) is int and type(completion) is int else plan['reserve_each_usd'])
        content = choice['message'].get('content')
        smoke_ok = None
        if smoke:
            try:
                parsed = json.loads(content)
                smoke_ok = parsed.get('left_color', '').lower() == 'red' and parsed.get('right_color', '').lower() == 'blue' and choice.get('finish_reason') == 'stop'
            except (TypeError, ValueError, AttributeError):
                smoke_ok = False
        public = dict(attempt_id=attempt, at=now(), transport_valid=True, provider_trace_id=trace,
               response_id=response.get('id'), returned_model=response.get('model'),
               finish_reason=choice.get('finish_reason'), content=content, usage=usage,
               smoke_ok=smoke_ok, raw_private_sha256=sha(raw),
               reasoning_private_sha256=sha(str(choice['message'].get('reasoning_content') or '').encode()),
               latency_seconds=time.monotonic()-began, charged_upper_usd=charge,
               reserve_peak_usd=plan['reserve_each_usd'])
        path = ROOT / 'public/responses' / (attempt + '.json')
        save(path, public)
        append(ROOT / 'public/CALL_LEDGER.jsonl', dict(phase='END', at=now(), attempt_id=attempt,
               transport_valid=True, charged_upper_usd=charge, response_sha256=sha(path.read_bytes())))
        assert charge <= plan['reserve_each_usd'], 'budget reserve exceeded; stop'
        return public
    except Exception as e:
        if not (ROOT / 'public/responses' / (attempt + '.json')).exists():
            append(ROOT / 'public/CALL_LEDGER.jsonl', dict(phase='END', at=now(), attempt_id=attempt,
                   transport_valid=False, error_type=type(e).__name__, http_code=getattr(e, 'code', None),
                   charged_upper_usd=plan['reserve_each_usd'], latency_seconds=time.monotonic()-began))
        raise RuntimeError('inference failed; no automatic retry') from None


def smoke_png():
    def chunk(name, data):
        return struct.pack('>I', len(data)) + name + data + struct.pack('>I', zlib.crc32(name+data))
    rows = b''.join(b'\x00' + b'\xff\x00\x00'*128 + b'\x00\x00\xff'*128 for _ in range(256))
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 256, 256, 8, 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(rows)) + chunk(b'IEND', b'')


def main(phase):
    plan = read(ROOT / 'PLAN.json')
    schedule = [r['attempt_id'] for r in plan['requests']]
    assert len(schedule) == 25 and len(set(schedule)) == 25 and plan['max_tokens'] == 65536
    assert read(ROOT / 'public/PREFLIGHT.json')['reserve_usd'] <= plan['cap_usd']
    key = sys.stdin.readline().strip()
    assert key and len(key) < 512
    if phase == 'smoke':
        assert not (ROOT / 'public/REQUESTS_SEALED.json').exists()
        assert not lines(ROOT / 'public/CALL_LEDGER.jsonl')
        raw = smoke_png()
        file_id = upload(sha(raw), raw, key)
        payload = wire(dict(model='deepseek-flash', messages=[
            dict(role='system', content='Technical image routing check; answer JSON from the actual image.'),
            dict(role='user', content=[dict(type='text', text='Which color is the left half and right half? Return left_color and right_color. Do not guess if unseen.'),
                                       dict(type='file', file_id=file_id)])], thinking=dict(type='enabled'),
            reasoning_effort='high', max_tokens=65536, response_format=dict(type='json_object'), stream=False))
        result = invoke('S001', payload, key, plan, smoke=True)
        print(json.dumps(dict(smoke_ok=result['smoke_ok'], charge=result['charged_upper_usd'])), flush=True)
        assert result['smoke_ok'], 'smoke failed; no formal requests'
        return
    assert phase in ('b01', 'formal') and read(ROOT / 'public/responses/S001.json')['smoke_ok'] is True
    if not (ROOT / 'public/REQUESTS_SEALED.json').exists():
        freeze(plan, upload_all(plan, key))
    seal = read(ROOT / 'public/REQUESTS_SEALED.json')
    assert seal['code_sha256'] == sha(Path(__file__).read_bytes())
    assert seal['plan_sha256'] == sha((ROOT / 'PLAN.json').read_bytes())
    records = {x['attempt_id']: x for x in seal['records']}
    for attempt in (schedule[:5] if phase == 'b01' else schedule):
        _, ended = budget(plan)
        if attempt in ended:
            assert ended[attempt]['transport_valid']
            continue
        payload = (ROOT / 'private/bodies' / (attempt + '.json')).read_bytes()
        assert sha(payload) == records[attempt]['payload_sha256']
        result = invoke(attempt, payload, key, plan)
        print(json.dumps(dict(attempt_id=attempt, finish=result['finish_reason'],
              charge=result['charged_upper_usd'])), flush=True)
    if phase == 'b01':
        print('B01_FIVE_OUTCOMES_RECORDED; FULL_RESPONSE_SEAL_PENDING', flush=True)
        return
    _, ended = budget(plan)
    assert all(x in ended and ended[x]['transport_valid'] for x in schedule)
    save(ROOT / 'public/RESPONSES_SEALED.json', dict(status='ALL_25_RESPONSES_SEALED_BEFORE_SCORE',
         at=now(), request_seal_sha256=sha((ROOT / 'public/REQUESTS_SEALED.json').read_bytes()),
         records=[dict(attempt_id=x, response_sha256=sha((ROOT / 'public/responses' / (x + '.json')).read_bytes()))
                  for x in schedule]))
    print('ALL_25_RESPONSES_SEALED_BEFORE_SCORE', flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('phase', choices=('smoke', 'b01', 'formal'))
    main(p.parse_args().phase)
