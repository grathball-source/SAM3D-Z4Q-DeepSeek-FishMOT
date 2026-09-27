"""Single-use Files API sender; this directory contains only frozen inputs and media."""
import argparse
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from contract import parse, schema, system
from score import classify

ROOT = Path(__file__).resolve().parent
API = 'https://api.deepseek.com'
INPUT_RATE = .30
OUTPUT_RATE = 1.20


def now():
    return datetime.now(timezone.utc).isoformat()


def wire(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')


def sha(value):
    return hashlib.sha256(value).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def lines(path):
    return [json.loads(x) for x in Path(path).read_text(encoding='utf-8').splitlines()] if Path(path).exists() else []


def save(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as fh:
        fh.write(wire(value)+b'\n'); fh.flush(); os.fsync(fh.fileno())


def append(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('ab') as fh:
        fh.write(wire(value)+b'\n'); fh.flush(); os.fsync(fh.fileno())


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def post(endpoint, payload, key, content_type):
    assert endpoint in ('/files', '/chat/completions')
    req = urllib.request.Request(API+endpoint, data=payload, method='POST', headers={
        'Authorization': 'Bearer '+key, 'Content-Type': content_type})
    with urllib.request.build_opener(NoRedirect).open(req, timeout=900) as response:
        raw = response.read(16*1024*1024+1)
        assert len(raw) <= 16*1024*1024
        return raw


def multipart(digest, raw):
    boundary = 'ehrcf-'+digest[:30]
    head = (f'--{boundary}\r\nContent-Disposition: form-data; name="purpose"\r\n\r\nuser_data\r\n'
            f'--{boundary}\r\nContent-Disposition: form-data; name="expires_after[anchor]"\r\n\r\ncreated_at\r\n'
            f'--{boundary}\r\nContent-Disposition: form-data; name="expires_after[seconds]"\r\n\r\n2592000\r\n'
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="image_{digest[:24]}.png"\r\n'
            'Content-Type: image/png\r\n\r\n').encode()
    return head+raw+f'\r\n--{boundary}--\r\n'.encode(), boundary


def upload(digest, raw, key):
    ledger = ROOT/'UPLOAD_LEDGER.jsonl'
    payload, boundary = multipart(digest, raw)
    append(ledger, {'phase': 'START', 'at': now(), 'sha256': digest, 'bytes': len(raw)})
    try:
        response = post('/files', payload, key, 'multipart/form-data; boundary='+boundary)
        obj = json.loads(response); file_id = obj['id']
        assert file_id.startswith('file-api-') and obj['bytes'] == len(raw)
        append(ledger, {'phase': 'END', 'at': now(), 'sha256': digest,
                        'file_id': file_id, 'response_sha256': sha(response)})
        return file_id
    except Exception as exc:
        append(ledger, {'phase': 'ERROR', 'at': now(), 'sha256': digest,
                        'error_type': type(exc).__name__, 'http_code': getattr(exc, 'code', None)})
        raise RuntimeError('upload uncertain; no automatic retry') from None


def uploaded():
    events = lines(ROOT/'UPLOAD_LEDGER.jsonl')
    starts = {x['sha256'] for x in events if x['phase'] == 'START'}
    done = {x['sha256']: x['file_id'] for x in events if x['phase'] == 'END'}
    assert starts == set(done), 'uncertain upload; do not retry'
    return done


def body(request, ids):
    packet = json.loads(request['text'])
    assert read(ROOT/'CONTRACT.json') == schema() if (ROOT/'CONTRACT.json').exists() else True
    assert packet['request_id'] == ('EHR-CF-'+request['case'] if request['case'].startswith('B')
                                    else 'SYNTHETIC_TEST_ONLY-'+request['case'])
    assert [x['image_id'] for x in packet['IMAGE_INDEX']] == [x['image_id'] for x in request['images']]
    for forbidden in ('SRC-F', 'frame_local:n:', 'native_mask_key', 'SCORE_KEY', 'GT2', 'GT6', '/home/'):
        assert forbidden not in request['text'], forbidden
    return {'model': 'deepseek-flash', 'messages': [
        {'role': 'system', 'content': system()},
        {'role': 'user', 'content': [{'type': 'text', 'text': request['text']}]+
         [{'type': 'file', 'file_id': ids[x['sha256']]} for x in request['images']]}],
        'thinking': {'type': 'enabled'}, 'reasoning_effort': 'high', 'max_tokens': 65536,
        'response_format': {'type': 'json_object'}, 'stream': False}


def plan():
    p = read(ROOT/'PLAN.json')
    assert p['model'] == 'deepseek-flash' and p['max_tokens'] == 65536 and p['cap_usd'] <= 4
    formal = read(ROOT/'REQUESTS_LOGICAL.json')['requests']
    smoke = read(ROOT/'SMOKE_REQUESTS.json')['requests']
    assert len(formal) == 25 and len(smoke) == 2
    assert [x['attempt_id'] for x in formal] == p['formal_schedule']
    assert [x['attempt_id'] for x in smoke] == p['smoke_schedule'] == ['S01', 'S02']
    return p, formal, smoke


def reserve():
    gate = read(ROOT/'SENDER_GATE.json')
    assert gate['status'] == 'PASS' and gate['request_count'] == 27 and gate['cap_usd'] <= 4
    assert gate['plan_sha256'] == sha((ROOT/'PLAN.json').read_bytes())
    rates = {x['attempt_id']: x['reserve_usd'] for x in gate['request_budget']}
    assert len(rates) == 27 and sum(rates.values()) <= gate['cap_usd']+1e-9
    return rates


def ready():
    p, formal, smoke = plan(); rates = reserve()
    lock = read(ROOT/'CODE_AND_INPUT_LOCK.json')
    for name, digest in lock['code_sha256'].items():
        if (ROOT/name).exists():
            assert sha((ROOT/name).read_bytes()) == digest, name
    for name, digest in lock['input_sha256'].items():
        assert sha((ROOT/name).read_bytes()) == digest, name
    seal = read(ROOT/'public/REQUESTS_SEALED.json')
    assert seal['status'] == 'ALL_27_BODIES_FROZEN_BEFORE_INFERENCE'
    assert seal['lock_sha256'] == sha((ROOT/'CODE_AND_INPUT_LOCK.json').read_bytes())
    assert seal['body_gate_sha256'] == sha((ROOT/'BODY_GATE.json').read_bytes())
    assert seal['formal_logical_sha256'] == sha((ROOT/'REQUESTS_LOGICAL.json').read_bytes())
    assert seal['smoke_logical_sha256'] == sha((ROOT/'SMOKE_REQUESTS.json').read_bytes())
    records = {x['attempt_id']: x for x in seal['records']}
    assert set(records) == set(rates)
    return p, formal, smoke, rates, records


def budget(rates, cap):
    events = lines(ROOT/'public/CALL_LEDGER.jsonl')
    starts, ends = {}, {}
    for event in events:
        attempt = event['attempt_id']
        if event['phase'] == 'START':
            assert attempt not in starts; starts[attempt] = event
        elif event['phase'] == 'END':
            assert attempt in starts and attempt not in ends; ends[attempt] = event
        else:
            raise AssertionError(event['phase'])
    assert set(starts) == set(ends), 'unresolved inference HTTP; stop'
    assert len(starts) <= 27
    spent = sum(x['charged_upper_usd'] for x in ends.values())
    remaining = sum(v for a, v in rates.items() if a not in starts)
    assert spent+remaining <= cap+1e-9
    return starts


def invoke(attempt, payload, key, rates, cap):
    starts = budget(rates, cap)
    assert attempt not in starts and len(starts) < 27
    reserve_usd = rates[attempt]
    append(ROOT/'public/CALL_LEDGER.jsonl', {'phase': 'START', 'at': now(), 'attempt_id': attempt,
        'payload_sha256': sha(payload), 'reserve_peak_usd': reserve_usd})
    started = time.monotonic()
    try:
        raw = post('/chat/completions', payload, key, 'application/json')
        raw_path = ROOT/'raw'/(attempt+'.json'); raw_path.parent.mkdir(parents=True, exist_ok=True)
        with raw_path.open('xb') as fh:
            fh.write(raw); fh.flush(); os.fsync(fh.fileno())
        obj = json.loads(raw); choice = obj['choices'][0]; usage = obj.get('usage') or {}
        prompt, completion = usage.get('prompt_tokens'), usage.get('completion_tokens')
        charge = ((prompt*INPUT_RATE+completion*OUTPUT_RATE)/1_000_000
                  if type(prompt) is int and type(completion) is int else reserve_usd)
        response = {'attempt_id': attempt, 'at': now(), 'transport_valid': True,
                    'returned_model': obj.get('model'), 'finish_reason': choice.get('finish_reason'),
                    'content': choice['message'].get('content'), 'usage': usage,
                    'raw_private_sha256': sha(raw),
                    'reasoning_private_sha256': sha(str(choice['message'].get('reasoning_content') or '').encode()),
                    'latency_seconds': time.monotonic()-started,
                    'charged_upper_usd': charge, 'reserve_peak_usd': reserve_usd}
        path = ROOT/'public/responses'/(attempt+'.json'); save(path, response)
        append(ROOT/'public/CALL_LEDGER.jsonl', {'phase': 'END', 'at': now(), 'attempt_id': attempt,
            'transport_valid': True, 'charged_upper_usd': charge,
            'response_sha256': sha(path.read_bytes())})
    except Exception as exc:
        save(ROOT/'errors'/(attempt+'.json'), {'at': now(), 'attempt_id': attempt,
            'error_type': type(exc).__name__, 'http_code': getattr(exc, 'code', None),
            'elapsed_seconds': time.monotonic()-started})
        raise RuntimeError('inference outcome uncertain; no new START') from None
    assert charge <= reserve_usd, 'known response exceeded reserve; stop new START'
    return response


def partial(reason):
    path = ROOT/'public/PARTIAL_RESPONSES_SEALED.json'
    if path.exists():
        return
    _, formal, smoke = plan()
    events = lines(ROOT/'public/CALL_LEDGER.jsonl')
    starts = {x['attempt_id'] for x in events if x['phase'] == 'START'}
    ends = {x['attempt_id'] for x in events if x['phase'] == 'END'}
    save(path, {'status': 'PARTIAL_STOP', 'reason': reason, 'at': now(),
        'request_seal_sha256': sha((ROOT/'public/REQUESTS_SEALED.json').read_bytes()),
        'ledger_sha256': sha((ROOT/'public/CALL_LEDGER.jsonl').read_bytes()),
        'attempts': [{'attempt_id': x['attempt_id'],
                      'state': 'UNSENT' if x['attempt_id'] not in starts else
                               'HTTP_UNKNOWN' if x['attempt_id'] not in ends else 'RETURNED'}
                     for x in smoke+formal]})


def main(phase):
    p, formal, smoke = plan()
    if phase == 'upload':
        frozen = read(ROOT/'PREUPLOAD_LOCK.json')
        assert frozen['status'] == 'CODE_LOGICAL_REQUEST_BUDGET_FROZEN_BEFORE_UPLOAD'
        for name, digest in frozen['input_sha256'].items():
            assert sha((ROOT/name).read_bytes()) == digest, name
        for name, digest in frozen['code_sha256'].items():
            if (ROOT/name).exists():
                assert sha((ROOT/name).read_bytes()) == digest, name
    if phase in ('upload', 'smoke', 'formal'):
        key = os.environ.get('DEEPSEEK_API_KEY', '').strip()
        assert key and len(key) < 512, 'DeepSeek credential unavailable'
    if phase == 'upload':
        assert not (ROOT/'public/CALL_LEDGER.jsonl').exists()
        done = uploaded()
        for request in formal+smoke:
            for image in request['images']:
                digest = image['sha256']; raw = (ROOT/'media'/image['media_file']).read_bytes()
                assert sha(raw) == digest and len(raw) == image['bytes']
                if digest not in done:
                    done[digest] = upload(digest, raw, key)
        assert len(done) == 59
        print('UPLOADS_59_COMPLETE', flush=True); return
    if phase == 'freeze':
        assert not (ROOT/'public/CALL_LEDGER.jsonl').exists()
        ids = uploaded(); assert len(ids) == 59
        records = []
        for request in formal+smoke:
            attempt = request['attempt_id']; payload = wire(body(request, ids))
            path = ROOT/'bodies'/(attempt+'.json'); path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('xb') as fh:
                fh.write(payload); fh.flush(); os.fsync(fh.fileno())
            records.append({'attempt_id': attempt, 'payload_sha256': sha(payload),
                            'payload_bytes': len(payload)})
        save(ROOT/'BODY_RECORDS.json', records)
        print('BODIES_27_FROZEN', flush=True); return
    if phase == 'seal':
        assert not (ROOT/'public/CALL_LEDGER.jsonl').exists()
        gate = read(ROOT/'BODY_GATE.json'); lock = read(ROOT/'CODE_AND_INPUT_LOCK.json')
        assert gate['status'] == 'BODY_GATE_PASS'
        assert lock['input_sha256']['BODY_GATE.json'] == sha((ROOT/'BODY_GATE.json').read_bytes())
        records = read(ROOT/'BODY_RECORDS.json'); assert records == gate['records']
        with (ROOT/'public/CALL_LEDGER.jsonl').open('xb') as fh:
            fh.flush(); os.fsync(fh.fileno())
        save(ROOT/'public/REQUESTS_SEALED.json', {'status': 'ALL_27_BODIES_FROZEN_BEFORE_INFERENCE',
            'at': now(), 'formal_logical_sha256': sha((ROOT/'REQUESTS_LOGICAL.json').read_bytes()),
            'smoke_logical_sha256': sha((ROOT/'SMOKE_REQUESTS.json').read_bytes()),
            'body_gate_sha256': sha((ROOT/'BODY_GATE.json').read_bytes()),
            'lock_sha256': sha((ROOT/'CODE_AND_INPUT_LOCK.json').read_bytes()), 'records': records})
        print('REQUESTS_SEALED', flush=True); return
    p, formal, smoke, rates, records = ready()
    if phase == 'smoke':
        results = []
        try:
            for request in smoke:
                if (ROOT/'STOP_NEW_START').exists():
                    partial('PREDECLARED_STOP_NEW_START'); return
                attempt = request['attempt_id']; payload = (ROOT/'bodies'/(attempt+'.json')).read_bytes()
                assert sha(payload) == records[attempt]['payload_sha256']
                response = invoke(attempt, payload, key, rates, p['cap_usd'])
                packet = json.loads(request['text'])
                parsed = parse(response['content'], packet)
                expectation = read(ROOT/'SMOKE_REQUESTS.json')['expectations'][attempt]
                binding = {'reference_scoreable': expectation['correct_physical_mapping'] is not None,
                           'correct_physical_mapping': expectation['correct_physical_mapping']}
                scored = classify(response, packet, binding)
                assert scored['raw_choice'] == parsed['raw_choice']
                ok = response['finish_reason'] == 'stop' and parsed['assessment_usable']
                results.append({'attempt_id': attempt, 'qualified': ok, **parsed,
                                'synthetic_physical_diagnostic_only': scored['official_identity_outcome'],
                                'expected_choice_diagnostic_only': expectation['expected_choice_diagnostic_only'],
                                'response_sha256': sha((ROOT/'public/responses'/(attempt+'.json')).read_bytes())})
                print({'smoke': attempt, 'qualified': ok, 'raw_choice': parsed['raw_choice']}, flush=True)
                if not ok:
                    save(ROOT/'public/API_PROTOCOL_SMOKE.json', {'status': 'INTERFACE_QUALIFICATION_FAILURE',
                        'results': results, 'frozen_template_unchanged': True})
                    partial('INTERFACE_QUALIFICATION_FAILURE'); return
        except Exception:
            partial('SMOKE_TRANSPORT_OR_BUDGET_STOP'); raise
        save(ROOT/'public/API_PROTOCOL_SMOKE.json', {'status': 'PASS', 'results': results,
            'frozen_template_unchanged': True})
        return
    assert phase == 'formal'
    assert read(ROOT/'public/API_PROTOCOL_SMOKE.json')['status'] == 'PASS'
    try:
        for request in formal:
            if (ROOT/'STOP_NEW_START').exists():
                partial('PREDECLARED_STOP_NEW_START'); return
            attempt = request['attempt_id']; payload = (ROOT/'bodies'/(attempt+'.json')).read_bytes()
            assert sha(payload) == records[attempt]['payload_sha256']
            response = invoke(attempt, payload, key, rates, p['cap_usd'])
            print({'formal': attempt, 'finish': response['finish_reason'],
                   'peak_upper_usd': response['charged_upper_usd']}, flush=True)
        save(ROOT/'public/RESPONSES_SEALED.json', {
            'status': 'ALL_25_FORMAL_RESPONSES_SEALED_BEFORE_SCORE', 'at': now(),
            'request_seal_sha256': sha((ROOT/'public/REQUESTS_SEALED.json').read_bytes()),
            'records': [{'attempt_id': x['attempt_id'],
                         'response_sha256': sha((ROOT/'public/responses'/(x['attempt_id']+'.json')).read_bytes())}
                        for x in formal]})
        print('ALL_25_FORMAL_RESPONSES_SEALED_BEFORE_SCORE', flush=True)
    except Exception:
        partial('TECHNICAL_OR_BUDGET_STOP'); raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('phase', choices=('upload', 'freeze', 'seal', 'smoke', 'formal'))
    main(parser.parse_args().phase)
