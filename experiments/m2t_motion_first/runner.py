"""Single-use isolated DeepSeek sender. Mount only the new sender directory at /work."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import struct
import sys
import time
import urllib.request
import zlib
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('/work')
API = 'https://api.deepseek.com'
CAP = 65536
PRICE_IN, PRICE_OUT = .30, 1.20
LIMIT = 3.0
SYSTEM = ("You are evaluating four anonymous identity-association edges from real temporal observations. "
          "Return one JSON object only. Assess A-X, A-Y, B-X, B-Y jointly; the two complete "
          "hypotheses are A-X+B-Y and A-Y+B-X. For each edge return relation SUPPORT, "
          "CONTRADICT, or UNRESOLVED; cue OBSERVED_CONTINUITY, ENTRY_EXIT_COMPATIBILITY, "
          "RELATIVE_MOTION, TEMPORAL_TURNING, or UNRESOLVED; evidence as an array of objects "
          "with image_id, observation_tokens (array of local f###:o## tokens on that image), "
          "relative_seconds, observation; gaps_or_assumptions as text; competing_explanation "
          "as text. Top-level keys: request_id, edges. The edges value must be a JSON object "
          "with exactly four named keys A-X, A-Y, B-X, B-Y (not an array). Each value is an "
          "edge object with the fields just specified. Copy the input request_id exactly. "
          "For directional SUPPORT/CONTRADICT cite at least two distinct real G image times. "
          "Cite an intermediate G observation if claiming interaction evidence. Image tokens reset "
          "every frame and are not persistent identities. Do not infer continuous visibility across "
          "missing observations. Static color, spot, single-frame bend, size, or neighbor alone "
          "cannot support identity. If observations allow both hypotheses, use UNRESOLVED. "
          "No fabricated probability or tracker identity edit.")


def now():
    return datetime.now(timezone.utc).isoformat()


def wire(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path, value):
    assert not path.exists(), path
    with path.open('xb') as stream:
        stream.write(wire(value) + b'\n')
        stream.flush()
        os.fsync(stream.fileno())


def append(path, value):
    with path.open('ab') as stream:
        stream.write(wire(value) + b'\n')
        stream.flush()
        os.fsync(stream.fileno())


def lines(path):
    return [json.loads(row) for row in path.read_text(encoding='utf-8').splitlines()] if path.exists() else []


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def post(endpoint, payload, key, content_type, timeout):
    assert endpoint in ('/files', '/chat/completions')
    req = urllib.request.Request(API + endpoint, data=payload, method='POST',
                                 headers={'Authorization': 'Bearer ' + key,
                                          'Content-Type': content_type})
    with urllib.request.build_opener(NoRedirect).open(req, timeout=timeout) as response:
        raw = response.read(16 * 1024 * 1024 + 1)
        assert len(raw) <= 16 * 1024 * 1024
        return raw, response.headers.get('x-ds-trace-id') or response.headers.get('x-request-id')


def key():
    value = sys.stdin.readline().strip()
    assert value and len(value) < 512 and '\n' not in value
    return value


def multipart(digest, raw):
    boundary = 'm2t-' + digest[:30]
    head = (f'--{boundary}\r\nContent-Disposition: form-data; name="purpose"\r\n\r\nuser_data\r\n'
            f'--{boundary}\r\nContent-Disposition: form-data; name="expires_after[anchor]"\r\n\r\ncreated_at\r\n'
            f'--{boundary}\r\nContent-Disposition: form-data; name="expires_after[seconds]"\r\n\r\n2592000\r\n'
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="image_{digest[:24]}.png"\r\n'
            'Content-Type: image/png\r\n\r\n').encode()
    return head + raw + f'\r\n--{boundary}--\r\n'.encode(), boundary


def upload_one(digest, raw, api_key, ledger):
    payload, boundary = multipart(digest, raw)
    append(ledger, dict(phase='UPLOAD_START', at=now(), sha256=digest, bytes=len(raw), payload_sha256=sha(payload)))
    try:
        response_raw, _ = post('/files', payload, api_key, 'multipart/form-data; boundary=' + boundary, 600)
        response = json.loads(response_raw)
        file_id = response['id']
        assert file_id.startswith('file-api-') and response['bytes'] == len(raw)
        append(ledger, dict(phase='UPLOAD_END', at=now(), sha256=digest, bytes=len(raw),
                            file_id=file_id, response_sha256=sha(response_raw)))
        return file_id
    except Exception as exc:
        append(ledger, dict(phase='UPLOAD_ERROR', at=now(), sha256=digest,
                            exception_type=type(exc).__name__, http_code=getattr(exc, 'code', None)))
        raise RuntimeError('upload failed; no automatic retry') from None


def upload_all(plan, api_key):
    ledger = ROOT / 'private/UPLOAD_LEDGER.jsonl'
    done = {x['sha256']: x['file_id'] for x in lines(ledger) if x['phase'] == 'UPLOAD_END'}
    wanted = {image['sha256']: image for req in plan['requests'] for image in req['images']}
    for number, (digest, image) in enumerate(wanted.items(), 1):
        raw = (ROOT / 'media' / image['media_file']).read_bytes()
        assert sha(raw) == digest and len(raw) == image['bytes']
        if digest not in done:
            done[digest] = upload_one(digest, raw, api_key, ledger)
        if number % 40 == 0 or number == len(wanted):
            print(json.dumps(dict(uploaded=len(set(done) & set(wanted)), total=len(wanted))), flush=True)
    assert set(wanted) <= set(done)  # The same ledger also contains the one smoke image.
    return done


def smoke_png():
    def chunk(name, data):
        return struct.pack('>I', len(data)) + name + data + struct.pack('>I', zlib.crc32(name + data))
    rows = b''.join(b'\x00' + b'\xff\x00\x00' * 128 + b'\x00\x00\xff' * 128 for _ in range(256))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 256, 256, 8, 2, 0, 0, 0)) +
            chunk(b'IDAT', zlib.compress(rows)) + chunk(b'IEND', b''))


def request_body(req, uploaded):
    core = json.loads(req['core_text'])
    assert core['request_id'] == req['request_id']
    content = [dict(type='text', text=req['core_text'])]
    content += [dict(type='file', file_id=uploaded[image['sha256']])
                for image in req['images'] if image['kind'] == 'G']
    if req['ap_text']:
        content.append(dict(type='text', text=req['ap_text']))
        content += [dict(type='file', file_id=uploaded[image['sha256']])
                    for image in req['images'] if image['kind'] == 'AP']
    result = dict(model='deepseek-flash', messages=[dict(role='system', content=SYSTEM),
              dict(role='user', content=content)], thinking=dict(type='enabled'),
              reasoning_effort='high', max_tokens=CAP, response_format=dict(type='json_object'), stream=False)
    sent_text = SYSTEM + req['core_text'] + (req['ap_text'] or '')
    for forbidden in ('SCORE_KEY', 'GT2', 'GT6', 'SWAP', 'KEEP', '/home/', 'api_key', 'P4218132'):
        assert forbidden not in sent_text, forbidden
    assert re.search(r'(?<![A-Za-z0-9])B0(?![A-Za-z0-9])', sent_text) is None
    return result


def freeze(plan, uploaded):
    assert not (ROOT / 'public/REQUESTS_SEALED.json').exists()
    bodies = ROOT / 'private/bodies'
    bodies.mkdir(exist_ok=True)
    assert not any(bodies.iterdir()), 'partial unsealed bodies require audit before restart'
    records = []
    by_attempt = {}
    for req in plan['requests']:
        payload = wire(request_body(req, uploaded))
        assert len(payload) < 48 * 1024 * 1024
        (bodies / (req['attempt_id'] + '.json')).write_bytes(payload)
        records.append(dict(attempt_id=req['attempt_id'], case_alias=req['case_alias'], arm=req['arm'],
                            payload_sha256=sha(payload), payload_bytes=len(payload),
                            image_count=len(req['images']), reserve_peak_usd=req['reserve_peak_usd']))
        by_attempt[req['attempt_id']] = payload
    assert len(records) == 25
    for case in {x['case_alias'] for x in plan['requests']}:
        assert by_attempt[case + '-G-SEQ'] == by_attempt[case + '-G-SEQ-REPEAT']
        assert by_attempt[case + '-G+AP'] == by_attempt[case + '-G+AP-REPEAT']
    save(ROOT / 'public/REQUESTS_SEALED.json', dict(status='ALL_25_BODIES_FROZEN_BEFORE_FORMAL_CALL',
         at=now(), code_sha256=sha(Path(__file__).read_bytes()),
         plan_sha256=sha((ROOT / 'PLAN.json').read_bytes()),
         system_sha256=sha(SYSTEM.encode()), records=records))


def budget(plan):
    events = lines(ROOT / 'public/CALL_LEDGER.jsonl')
    starts = {x['attempt_id']: x for x in events if x['phase'] == 'START'}
    ends = {x['attempt_id']: x for x in events if x['phase'] == 'END'}
    assert len(starts) == sum(x['phase'] == 'START' for x in events)
    assert len(ends) == sum(x['phase'] == 'END' for x in events)
    assert set(starts) == set(ends), 'unresolved inference; no retry'
    assert len(starts) <= 26
    charged = sum(x['charged_upper_usd'] for x in ends.values())
    pending = sum(x['reserve_peak_usd'] for x in plan['requests'] if x['attempt_id'] not in starts)
    return charged, pending, starts, ends


def invoke(attempt, body, reserve, api_key, smoke=False):
    ledger = ROOT / 'public/CALL_LEDGER.jsonl'
    _, _, starts, _ = budget(read(ROOT / 'PLAN.json'))
    assert attempt not in starts and len(starts) < 26
    append(ledger, dict(phase='START', at=now(), attempt_id=attempt,
                        payload_sha256=sha(body), reserve_peak_usd=reserve))
    started = time.monotonic()
    try:
        raw, trace = post('/chat/completions', body, api_key, 'application/json', 900)
        private_raw = ROOT / 'private/raw'
        private_raw.mkdir(exist_ok=True)
        path = private_raw / (attempt + '.json')
        assert not path.exists()
        path.write_bytes(raw)
        response = json.loads(raw)
        selected = response['choices'][0]
        content = selected['message'].get('content')
        usage = response.get('usage') or {}
        prompt, completion = usage.get('prompt_tokens'), usage.get('completion_tokens')
        charge = ((prompt * PRICE_IN + completion * PRICE_OUT) / 1e6
                  if type(prompt) is int and type(completion) is int and prompt >= 0 and completion >= 0
                  else reserve)
        parsed = None
        try:
            parsed = json.loads(content) if isinstance(content, str) else None
        except json.JSONDecodeError:
            pass
        smoke_ok = (isinstance(parsed, dict) and parsed.get('left_color', '').lower() == 'red' and
                    parsed.get('right_color', '').lower() == 'blue' and selected.get('finish_reason') == 'stop') if smoke else None
        public = dict(attempt_id=attempt, at=now(), transport_valid=True, provider_trace_id=trace,
                      response_id=response.get('id'), returned_model=response.get('model'),
                      finish_reason=selected.get('finish_reason'), content=content, usage=usage,
                      smoke_ok=smoke_ok, raw_private_sha256=sha(raw),
                      reasoning_private_sha256=sha(str(selected['message'].get('reasoning_content') or '').encode()),
                      latency_seconds=time.monotonic() - started, charged_upper_usd=charge,
                      reserve_peak_usd=reserve)
        responses = ROOT / 'public/responses'
        responses.mkdir(exist_ok=True)
        save(responses / (attempt + '.json'), public)
        append(ledger, dict(phase='END', at=now(), attempt_id=attempt, transport_valid=True,
                            charged_upper_usd=charge, reserve_peak_usd=reserve,
                            response_sha256=sha((responses / (attempt + '.json')).read_bytes())))
        assert charge <= reserve + 1e-6, 'reserve overrun; stop'
        return public
    except Exception as exc:
        if not (ROOT / 'public/responses' / (attempt + '.json')).exists():
            append(ledger, dict(phase='END', at=now(), attempt_id=attempt, transport_valid=False,
                                exception_type=type(exc).__name__, http_code=getattr(exc, 'code', None),
                                charged_upper_usd=reserve, reserve_peak_usd=reserve,
                                latency_seconds=time.monotonic() - started))
        raise RuntimeError('inference failed; no automatic retry') from None


def main(phase):
    plan = read(ROOT / 'PLAN.json')
    assert plan['model'] == 'deepseek-flash' and plan['max_tokens'] == CAP and len(plan['requests']) == 25
    assert read(ROOT / 'public/PREFLIGHT.json')['reserve_usd'] <= LIMIT
    api_key = key()
    if phase == 'smoke':
        assert not (ROOT / 'public/REQUESTS_SEALED.json').exists()
        _, _, starts, _ = budget(plan)
        assert not starts
        picture = smoke_png()
        digest = sha(picture)
        file_id = upload_one(digest, picture, api_key, ROOT / 'private/UPLOAD_LEDGER.jsonl')
        smoke_body = dict(model='deepseek-flash', messages=[
            dict(role='system', content='Technical image-routing check. Read the actual image; return only JSON.'),
            dict(role='user', content=[dict(type='text', text='A synthetic rectangle has two colored halves. Report the observed left_color and right_color in JSON; do not guess if not visible.'),
                                       dict(type='file', file_id=file_id)])],
            thinking=dict(type='enabled'), reasoning_effort='high', max_tokens=CAP,
            response_format=dict(type='json_object'), stream=False)
        value = wire(smoke_body)
        reserve = ((len(value) + 4096 + 1024) * PRICE_IN + CAP * PRICE_OUT) / 1e6
        assert reserve <= read(ROOT / 'public/PREFLIGHT.json')['smoke_reserve_usd']
        result = invoke('S001', value, reserve, api_key, smoke=True)
        print(json.dumps(dict(smoke_ok=result['smoke_ok'], cost=result['charged_upper_usd'])), flush=True)
        assert result['smoke_ok'], 'smoke failed; no formal requests'
        return
    assert phase == 'formal'
    assert read(ROOT / 'public/responses/S001.json')['smoke_ok'] is True
    if not (ROOT / 'public/REQUESTS_SEALED.json').exists():
        freeze(plan, upload_all(plan, api_key))
    sealed = read(ROOT / 'public/REQUESTS_SEALED.json')
    assert sealed['code_sha256'] == sha(Path(__file__).read_bytes())
    assert sealed['plan_sha256'] == sha((ROOT / 'PLAN.json').read_bytes())
    lookup = {x['attempt_id']: x for x in sealed['records']}
    for item in plan['requests']:
        charged, pending, _, ended = budget(plan)
        assert charged + pending <= LIMIT + 1e-9, (charged, pending)
        attempt = item['attempt_id']
        if attempt in ended:
            assert ended[attempt]['transport_valid'], 'failed attempt; no retry'
            continue
        payload = (ROOT / 'private/bodies' / (attempt + '.json')).read_bytes()
        assert sha(payload) == lookup[attempt]['payload_sha256']
        result = invoke(attempt, payload, item['reserve_peak_usd'], api_key)
        print(json.dumps(dict(attempt_id=attempt, finish=result['finish_reason'],
                              cost=result['charged_upper_usd'])), flush=True)
    _, _, _, ended = budget(plan)
    assert all(x['attempt_id'] in ended and ended[x['attempt_id']]['transport_valid'] for x in plan['requests'])
    save(ROOT / 'public/RESPONSES_SEALED.json', dict(status='ALL_25_RESPONSES_SEALED_BEFORE_SCORE',
         at=now(), requests_seal_sha256=sha((ROOT / 'public/REQUESTS_SEALED.json').read_bytes()),
         records=[dict(attempt_id=x['attempt_id'],
                       response_sha256=sha((ROOT / 'public/responses' / (x['attempt_id'] + '.json')).read_bytes()))
                  for x in plan['requests']]))
    print('ALL_25_RESPONSES_SEALED_BEFORE_SCORE', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=('smoke', 'formal'))
    main(parser.parse_args().phase)
