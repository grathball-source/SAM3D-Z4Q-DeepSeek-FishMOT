"""Four fixed historical events in a genuine 2,888-frame Z4Q state replay.

The inference process never opens GT. Scoring runs separately after the seal.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OLD = ROOT / 'experiments/ehr_contract_first_trial/run'
SOURCE = ROOT / 'experiments/ehr1r_causal_history_repair/corrected_unsent'
Z4Q = ROOT / 'online/closed_loop_2888'
sys.path.insert(0, str(Z4Q / 'z4q_source'))
sys.path.insert(0, str(Z4Q))
from bridge import Bridge, read, rows, sha, stream  # noqa: E402
from preflight import OBS, PROFILES, ARCHIVED  # noqa: E402


def wire(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()


def store(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as out:
        out.write(wire(value) + b'\n')
        out.flush()
        os.fsync(out.fileno())


def append(path, value):
    with Path(path).open('ab') as out:
        out.write(wire(value) + b'\n')
        out.flush()
        os.fsync(out.fileno())


def digest(value):
    return hashlib.sha256(value).hexdigest()


def unique(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError('DUPLICATE_KEY')
        obj[key] = value
    return obj


def parse_choice(content, finish_reason):
    if finish_reason != 'stop' or not isinstance(content, str):
        return None, 'TRUNCATED_OR_MISSING'
    try:
        obj = json.loads(content, object_pairs_hook=unique)
    except (ValueError, TypeError):
        return None, 'UNPARSEABLE'
    if not isinstance(obj, dict):
        return None, 'NOT_OBJECT'
    choices = [obj[k] for k in ('preferred_hypothesis', 'choice', 'selected_hypothesis') if k in obj]
    if not choices or any(type(c) is not str or c not in ('H1', 'H2', 'DEFER') for c in choices):
        return None, 'INVALID_CHOICE'
    if len(set(choices)) != 1:
        return None, 'CONFLICTING_CHOICE'
    return choices[0], 'VALID'


def source_native(facts, case, role, frame):
    ns = {int(x['source_fact_id'].rsplit('-N', 1)[1]) for x in facts
          if x['case'] == case and x['observed_fact_id'] == f'{role}-F{frame}'}
    assert len(ns) == 1, (case, role, frame, ns)
    return ns.pop()


def cases():
    assert read(OLD / 'public/SOURCE_TO_BODY_AUDIT.json')['status'] == 'SOURCE_TO_LOGICAL_PASS'
    assert read(SOURCE / 'PREFLIGHT.json')['status'] == 'PASS'
    manifest = read(OLD / 'public/REQUEST_MANIFEST.json')
    assert sha(OLD / 'public/REQUESTS_LOGICAL.json') == read(OLD / 'public/SOURCE_TO_BODY_AUDIT.json')['logical_sha256']
    locked = {x['attempt_id']: x for x in manifest['requests']}
    facts = read(SOURCE / 'SOURCE_FACT_MANIFEST.json')['facts']
    config = read(HERE / 'CONFIG.json')
    out = {}
    for item in read(OLD / 'public/REQUESTS_LOGICAL.json')['requests']:
        case = item['case']
        if case not in config['cases_by_q'] or item['arm'] != 'H-D':
            continue
        packet = json.loads(item['text'])
        assert digest(item['text'].encode()) == locked[item['attempt_id']]['text_sha256']
        q = packet['q_frame']
        assert packet['condition'] == 'H-D'
        assert all(x['source_frame'] <= q for part in ('PRE_HISTORY', 'POST_HISTORY_TO_Q')
                   for segment in packet[part].values() for x in segment['observations'])
        assert all(x['frame'] <= q for x in packet['IMAGE_INDEX'])
        assert max(x[1] for x in packet['INTERACTION_TABLE']['rows']) <= q
        native = {r: source_native(facts, case, r,
                  packet['PRE_HISTORY'][r]['anchor_frame'] if r in 'AB' else q) for r in 'ABXY'}
        assert native['X'] != native['Y'] and native['A'] != native['B']
        for image in item['images']:
            media = OLD / 'private/media' / image['media_file']
            assert sha(media) == image['sha256'] and media.stat().st_size == image['bytes']
        out[case] = dict(packet=packet, images=item['images'], native=native, q=q,
                         anchors={r: packet['PRE_HISTORY'][r]['anchor_frame'] for r in 'AB'})
    assert list(sorted(out, key=lambda c: out[c]['q'])) == config['cases_by_q']
    assert len(out) == config['max_inference_http'] == 4
    return out


def hypotheses(packet, refs, view, native):
    physical = {}
    for hypothesis in packet['hypotheses']:
        target = {native[r]: refs[hypothesis['mapping'][r]]['public_id'] for r in 'XY'}
        full = dict(view['mapping'])
        full.update(target)
        physical[hypothesis['id']] = dict(targets=target, full=full,
            one_to_one=len(set(full.values())) == len(full))
    assert set(physical) == {'H1', 'H2'} and physical['H1']['full'] != physical['H2']['full']
    return physical


def changes(choice, physical, current):
    target = physical[choice]['targets']
    return {n: k for n, k in target.items() if current[n] != k}


def file_ids():
    ledger = OLD / 'send/UPLOAD_LEDGER.jsonl'
    done = {}
    starts = set()
    for x in map(json.loads, ledger.read_text(encoding='utf-8').splitlines()):
        if x['phase'] == 'START':
            starts.add(x['sha256'])
        elif x['phase'] == 'END':
            assert x['file_id'].startswith('file-api-')
            done[x['sha256']] = x['file_id']
    assert starts == set(done), 'prior image upload ledger incomplete'
    return done


SYSTEM = ('Compare the two complete physical identity hypotheses for the observed event history. '
          'A/B are qualified pre-risk reference fragments; X/Y are q-local fragments. '
          'Use measured positions, motion, raw depth with its quality, anonymous interaction evidence, and sent images. '
          'Do not treat native handles across contact as identity proof or invent an unobserved path or physical quantity. '
          'If one complete mapping explains the evidence better, select it; if indistinguishable, DEFER. '
          'Return JSON with preferred_hypothesis H1, H2, or DEFER and optional brief reason.')


def make_body(case, item, refs, view, ids, config):
    packet = json.loads(json.dumps(item['packet']))
    packet['request_id'] = 'DIRECT-2888-' + case
    packet['role_contract'] = ('A/B are qualified pre-risk local reference fragments frozen in this replay; '
        'X/Y are q-local fragments. Anonymous observations during risk do not certify identity. '
        'The two hypotheses cover all current fish; unchanged U roles retain their current assignment. '
        'Candidate mappings are explanations, not observations or tracker commands.')
    # Only X/Y-to-A/B is inherited from the frozen hypothesis. Rebind all
    # unaffected current fish from B1 at q; old K labels are never carried over.
    assert {x['id'] for x in packet['hypotheses']} == {'H1', 'H2'}
    other = sorted(n for n in view['mapping'] if n not in (item['native']['X'], item['native']['Y']))
    assert len(other) == 4
    packet['CURRENT_OTHER_ROLES'] = []
    for i, native in enumerate(other, 1):
        fact = next(x for x in read(SOURCE/'SOURCE_FACT_MANIFEST.json')['facts']
                    if x['case'] == case and x['frame'] == item['q'] and
                    x['source_fact_id'] == f'SRC-F{item["q"]}-N{native}')
        packet['CURRENT_OTHER_ROLES'].append(dict(role=f'U{i}',
            observed_fact_id=fact['observed_fact_id'], assignment_token=f'K{i}',
            identity_scope='current_B1_assignment_only'))
    for h in packet['hypotheses']:
        h['mapping'] = {r: h['mapping'][r] for r in 'XY'} | {f'U{i}': f'K{i}' for i in range(1, 5)}
    for role in 'AB':
        assert refs[role]['anchor_frame'] == item['anchors'][role]
    packet['reference_binding'] = {r: {'anchor_frame': refs[r]['anchor_frame'],
        'identity_scope': 'branch_frozen_reference_at_anchor'} for r in 'AB'}
    physical = hypotheses(packet, refs, view, item['native'])
    text = json.dumps(packet, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
    for forbidden in ('SRC-F', 'frame_local:n:', 'native_mask_key', 'SCORE_KEY', 'GT2', 'GT6', '/home/'):
        assert forbidden not in text, forbidden
    body = dict(model=config['model'], messages=[dict(role='system', content=SYSTEM),
        dict(role='user', content=[dict(type='text', text=text)] +
            [dict(type='file', file_id=ids[x['sha256']]) for x in item['images']])],
        thinking=dict(type='enabled'), reasoning_effort='high',
        max_tokens=config['max_tokens'], response_format=dict(type='json_object'), stream=False)
    return packet, physical, body


def reserve(body, config):
    # Conservative peak no-cache budget, matching the prior Files API run.
    chars = len(body['messages'][0]['content']) + len(body['messages'][1]['content'][0]['text'])
    images = len(body['messages'][1]['content']) - 1
    tokens = int(chars * .6) + images * 1024 + 1024
    return (tokens * config['peak_input_usd_per_million'] +
            config['max_tokens'] * config['peak_output_usd_per_million']) / 1_000_000


def infer(case, packet, physical, body, config, spent):
    public = HERE / 'public'
    private = HERE / 'private_api'
    payload = wire(body)
    estimate = reserve(body, config)
    assert spent + estimate <= config['max_usd']
    store(public / 'requests' / (case + '.json'), packet)
    store(public / 'request_bindings' / (case + '.json'), dict(q=packet['q_frame'],
        body_sha256=digest(payload), text_sha256=digest(wire(packet)),
        media_sha256=[x['sha256'] for x in packet['IMAGE_INDEX']],
        physical=physical, reserve_peak_usd=estimate))
    store(private / (case + '.body.json'), body)
    assert sha(private / (case + '.body.json')) == digest(payload + b'\n')
    append(public / 'CALL_LEDGER.jsonl', dict(phase='START', case=case, at=time.time(),
        body_sha256=digest(payload), reserve_peak_usd=estimate))
    started = time.monotonic()
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None
    req = urllib.request.Request('https://api.deepseek.com/chat/completions', data=payload,
        headers={'Authorization': 'Bearer ' + os.environ['DEEPSEEK_API_KEY'],
                 'Content-Type': 'application/json'}, method='POST')
    try:
        with urllib.request.build_opener(NoRedirect).open(req, timeout=900) as response:
            raw = response.read(16 * 1024 * 1024 + 1)
        assert len(raw) <= 16 * 1024 * 1024
        response = json.loads(raw)
        with (private / (case + '.raw.json')).open('xb') as out:
            out.write(raw)
            out.flush()
            os.fsync(out.fileno())
        result = response['choices'][0]
        usage = response.get('usage') or {}
        prompt_tokens, output_tokens = usage.get('prompt_tokens'), usage.get('completion_tokens')
        charged = ((prompt_tokens * config['peak_input_usd_per_million'] +
                    output_tokens * config['peak_output_usd_per_million']) / 1_000_000
                   if type(prompt_tokens) is int and type(output_tokens) is int else estimate)
        content = result['message'].get('content')
        choice, parse_status = parse_choice(content, result.get('finish_reason'))
        record = dict(case=case, at=time.time(), returned_model=response.get('model'),
            finish_reason=result.get('finish_reason'), content=content, usage=usage,
            choice=choice, parse_status=parse_status, latency_seconds=time.monotonic()-started,
            charge_peak_upper_usd=charged, raw_private_sha256=digest(raw),
            reasoning_private_sha256=digest(str(result['message'].get('reasoning_content') or '').encode()))
        store(public / 'responses' / (case + '.json'), record)
        append(public / 'CALL_LEDGER.jsonl', dict(phase='END', case=case, at=time.time(),
            response_sha256=sha(public / 'responses' / (case + '.json')),
            charge_peak_upper_usd=charged, parse_status=parse_status))
        return choice, parse_status, charged
    except Exception as exc:
        append(public / 'CALL_LEDGER.jsonl', dict(phase='ERROR', case=case, at=time.time(),
            exception_type=type(exc).__name__, http_code=getattr(exc, 'code', None),
            latency_seconds=time.monotonic()-started, charge_reserved_usd=estimate))
        return None, 'HTTP_OR_STORAGE_ERROR', estimate


def no_truth(event, args):
    if event == 'open' and args and isinstance(args[0], (str, bytes)):
        path = os.fsdecode(args[0]).replace('\\', '/').lower()
        if any(word in path for word in ('offline_matches', 'gt_grid', '/truth', '/labels/', '/metrics', '/evaluation')):
            raise PermissionError('inference cannot open GT or scoring inputs')


def run(dry_run=False):
    config = read(HERE / 'CONFIG.json')
    fixed = cases()
    assert all(sha(path) == expected for path, expected in
        ((OBS, '3fc24d623ca3af22520dc7333ba07ad1479bc766425a2c548b1a13aa922a2e87'),
         (PROFILES, '91a154246748146896ac846f0bdd934bb67be874fe823124263650e88ad62f0e')))
    public = HERE / ('dry_run' if dry_run else 'public')
    if not dry_run:
        assert not public.exists(), 'single-use experiment directory'
        assert os.environ.get('DEEPSEEK_API_KEY'), 'key unavailable'
        ids = file_ids()
        assert all(x['sha256'] in ids for v in fixed.values() for x in v['images'])
    else:
        ids = {}
    public.mkdir(parents=True, exist_ok=False)
    refs = {case: {} for case in fixed}
    anchor_schedule = {}
    for case, item in fixed.items():
        for role, frame in item['anchors'].items():
            anchor_schedule.setdefault(frame, []).append((case, role, item['native'][role]))
    if not dry_run:
        store(public / 'FREEZE.json', dict(at=time.time(), config_sha256=sha(HERE/'CONFIG.json'),
            code_sha256=sha(HERE/'replay.py'), old_logical_sha256=sha(OLD/'public/REQUESTS_LOGICAL.json'),
            input_sha256={str(p): sha(p) for p in (OBS, PROFILES, ARCHIVED)},
            schedule=[dict(case=c, q=fixed[c]['q']) for c in config['cases_by_q']],
            max_http=4, max_usd=4, peak_reserve_usd=sum(
                (int((len(SYSTEM)+len(wire(x['packet']))) * .6) + len(x['images'])*1024 + 1024)*.3/1e6
                + config['max_tokens']*1.2/1e6 for x in fixed.values())))
    b0, b1 = Bridge(read(Z4Q/'z4q_source/CONFIG.json')), Bridge(read(Z4Q/'z4q_source/CONFIG.json'))
    sys.addaudithook(no_truth)
    spent = 0.0
    attempts = 0
    count = 0
    event_log = []
    started = time.monotonic()
    pred = gzip.open(public/'predictions_validation.jsonl.gz', 'wt', encoding='utf-8')
    traces = gzip.open(public/'transactions_validation.jsonl.gz', 'wt', encoding='utf-8')
    try:
        for (row, profiles), old in zip(stream(OBS, PROFILES, 2888, 9301), rows(ARCHIVED), strict=True):
            f = row['frame']
            v0 = b0.preview(f, row['time'], row['observations'], profiles)
            ids0, trace0 = b0.commit_once(v0)
            v1 = b1.preview(f, row['time'], row['observations'], profiles)
            transaction = None
            record = dict(frame=f, status='NATIVE', committed=None)
            for case in config['cases_by_q']:
                item = fixed[case]
                if f != item['q']:
                    continue
                assert len(refs[case]) == 2
                packet, physical, body = make_body(case, item, refs[case], v1, ids, config) if not dry_run else (None, None, None)
                if dry_run:
                    choice, parse_status, charge = None, 'MODEL_OFF', 0.0
                else:
                    assert attempts < 4
                    choice, parse_status, charge = infer(case, packet, physical, body, config, spent)
                    attempts += 1
                    spent += charge
                event = dict(case=case, frame=f, references=refs[case],
                    q_native={r: item['native'][r] for r in 'XY'},
                    before=v1['mapping'], choice=choice, parse_status=parse_status,
                    proposal=None, status='FALLBACK', first_reject_reason=None)
                if choice in ('H1', 'H2'):
                    wanted = physical[choice]
                    delta = changes(choice, physical, v1['mapping'])
                    event['proposal'] = wanted
                    event['changes'] = delta
                    if not delta:
                        event['status'] = 'KEEP'
                    elif not wanted['one_to_one']:
                        event['first_reject_reason'] = 'occupied_target'
                    else:
                        transaction, reason = b1.stage(v1, delta)
                        event['status'] = 'COMMIT' if transaction else 'STAGE_REJECTED'
                        event['first_reject_reason'] = reason
                elif choice == 'DEFER':
                    event['status'] = 'DEFER'
                event_log.append(event)
                record.update(status=event['status'], case=case, choice=choice,
                    selected_proposal=dict(displaced=[]),
                    stage_error=event['first_reject_reason'])
            ids1, trace1 = b1.commit_once(v1, transaction)
            for case, role, native in anchor_schedule.get(f, []):
                refs[case][role] = dict(anchor_frame=f, native=native,
                    public_id=ids1[native], epoch=b1.epochs[native], branch_version=b1.version)
            if record.get('status') == 'COMMIT':
                record['committed'] = transaction['changes']
                record['commit_provenance'] = {str(n): b1.provenance.get(n) for n in transaction['changes']}
                event_log[-1]['after'] = ids1
                event_log[-1]['bridge_version_after'] = b1.version
            out0 = [dict(id=ids0[x['id']], mask=x['mask']) for x in row['native']]
            out1 = [dict(id=ids1[x['id']], mask=x['mask']) for x in row['native']]
            assert out0 == old['variants']['Z4Q_STABLE'], f
            assert len({x['id'] for x in out1}) == len(out1)
            assert not dry_run or out0 == out1
            meta = dict(frame=f, global_frame=row['global_frame'], time=row['time'])
            pred.write(json.dumps(dict(meta, variants=dict(B0=out0, B1=out1)), separators=(',', ':'))+'\n')
            traces.write(json.dumps(dict(meta, variants=dict(B0=dict(status='NATIVE'), B1=record)), separators=(',', ':'))+'\n')
            count += 1
            if count % 200 == 0:
                print('FRAME', count, 'HTTP', attempts, 'USD_UPPER', round(spent, 6), flush=True)
        assert count == 2888
    finally:
        pred.close()
        traces.close()
    store(public/'EVENTS.json', event_log)
    store(public/'PREDICTIONS_SEALED.json', dict(status='SEALED_AWAITING_INDEPENDENT_SCORING',
        frames=count, HTTP_attempts=attempts, peak_no_cache_upper_usd=spent,
        wall_seconds=time.monotonic()-started, predictions_sha256=sha(public/'predictions_validation.jsonl.gz'),
        transactions_sha256=sha(public/'transactions_validation.jsonl.gz'),
        call_ledger_sha256=sha(public/'CALL_LEDGER.jsonl') if not dry_run else None))
    print('SEALED', count, 'HTTP', attempts, 'USD_UPPER', spent, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    run(args.dry_run)
