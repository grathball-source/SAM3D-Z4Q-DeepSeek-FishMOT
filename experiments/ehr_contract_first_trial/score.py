"""Verify the frozen chain before opening the retrospective physical reference."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path

from build import read, save, sha
from contract import parse

REPO = Path(__file__).resolve().parents[2]
AO0 = REPO/'experiments/ao0_association_observability'
AO1 = REPO/'experiments/ao1_input_fidelity'
V6 = REPO/'experiments/ehr1r_causal_history_repair/corrected_unsent'
ARMS = ('E', 'H-2D', 'H-D', 'H-D-REPEAT', 'H-D-PERMUTE')


def canonical(mapping):
    assert isinstance(mapping, dict) and all(isinstance(k, str) and isinstance(v, str)
                                             for k, v in mapping.items())
    return tuple(sorted(mapping.items()))


def lines(path):
    return [json.loads(x) for x in Path(path).read_text(encoding='utf-8').splitlines()] if Path(path).exists() else []


def verify_chain(run):
    """This function opens no GT or identity answer."""
    from sender import body, wire
    from validate import checked_packet
    run = Path(run); public = run/'public'; send = run/'send'
    lock = read(public/'CODE_AND_INPUT_LOCK.json')
    for name, digest in lock['code_sha256'].items():
        assert sha(Path(__file__).parent/name) == digest, name
    for name, digest in lock['input_sha256'].items():
        assert sha(public/name) == digest, name
    assert read(public/'SOURCE_TO_BODY_AUDIT.json')['status'] == 'SOURCE_TO_LOGICAL_PASS'
    assert read(public/'UPSTREAM_SOURCE_RECHECK.json')['status'] == 'PASS'
    manifest = read(public/'REQUEST_MANIFEST.json')
    formal = read(public/'REQUESTS_LOGICAL.json')['requests']
    smoke = read(public/'SMOKE_REQUESTS.json')['requests']
    assert len(formal) == 25 and len(smoke) == 2
    assert manifest['schedule'] == [x['attempt_id'] for x in formal]
    old_public = Path(read(run/'private/SOURCE_LOCATION.json')['old_public'])
    assert sha(old_public/'REQUESTS_LOGICAL.json') == manifest['old_logical_sha256']
    assert sha(old_public/'REQUEST_MANIFEST.json') == manifest['old_request_manifest_sha256']
    assert sha(V6/'EPISODE_FACTS.json') == manifest['v6_episode_sha256']
    old = {x['attempt_id']: x for x in read(old_public/'REQUESTS_LOGICAL.json')['requests']}
    for request, record in zip(formal, manifest['requests'], strict=True):
        assert hashlib.sha256(request['text'].encode()).hexdigest() == record['text_sha256']
        assert [x['sha256'] for x in request['images']] == record['image_sha256']
        checked_packet(request, old[request['attempt_id']], old)
    seal = read(public/'REQUESTS_SEALED.json')
    assert seal['status'] == 'ALL_27_BODIES_FROZEN_BEFORE_INFERENCE'
    assert seal['lock_sha256'] == sha(public/'CODE_AND_INPUT_LOCK.json')
    assert seal['body_gate_sha256'] == sha(public/'BODY_GATE.json')
    assert seal['formal_logical_sha256'] == sha(public/'REQUESTS_LOGICAL.json')
    assert seal['smoke_logical_sha256'] == sha(public/'SMOKE_REQUESTS.json')
    records = {x['attempt_id']: x for x in seal['records']}
    assert set(records) == {x['attempt_id'] for x in formal+smoke} and len(records) == 27
    uploads = lines(send/'UPLOAD_LEDGER.jsonl')
    ids = {x['sha256']: x['file_id'] for x in uploads if x['phase'] == 'END'}
    for request in formal+smoke:
        attempt = request['attempt_id']
        payload = (send/'bodies'/(attempt+'.json')).read_bytes()
        assert payload == wire(body(request, ids))
        assert hashlib.sha256(payload).hexdigest() == records[attempt]['payload_sha256']
    events = lines(public/'CALL_LEDGER.jsonl')
    starts, ends = {}, {}
    for event in events:
        attempt = event['attempt_id']
        assert attempt in records
        if event['phase'] == 'START':
            assert attempt not in starts; starts[attempt] = event
            assert seal['at'] < event['at']
            assert event['payload_sha256'] == records[attempt]['payload_sha256']
        elif event['phase'] == 'END':
            assert attempt in starts and attempt not in ends
            assert starts[attempt]['at'] <= event['at']
            ends[attempt] = event
            if event['transport_valid']:
                response = public/'responses'/(attempt+'.json')
                assert response.exists() and sha(response) == event['response_sha256']
                assert read(response)['attempt_id'] == attempt
        else:
            raise AssertionError(event['phase'])
    assert len(starts) <= 27
    smoke_result_path = public/'API_PROTOCOL_SMOKE.json'
    if any(x['attempt_id'] in starts for x in formal):
        smoke_result = read(smoke_result_path)
        assert smoke_result['status'] == 'PASS'
        assert {x['attempt_id'] for x in smoke_result['results']} == {'S01', 'S02'}
        assert all(x['qualified'] for x in smoke_result['results'])
        assert all(x['attempt_id'] in ends and ends[x['attempt_id']]['transport_valid']
                   for x in smoke)
        for item in smoke_result['results']:
            assert item['response_sha256'] == sha(public/'responses'/(item['attempt_id']+'.json'))
    for attempt in records:
        if attempt not in starts:
            assert not (public/'responses'/(attempt+'.json')).exists()
    full_path = public/'RESPONSES_SEALED.json'
    full = full_path.exists()
    if full:
        response_seal = read(full_path)
        assert response_seal['status'] == 'ALL_25_FORMAL_RESPONSES_SEALED_BEFORE_SCORE'
        assert response_seal['request_seal_sha256'] == sha(public/'REQUESTS_SEALED.json')
        assert set(x['attempt_id'] for x in formal) <= set(ends)
        assert all(ends[x['attempt_id']]['transport_valid'] for x in formal)
        assert {x['attempt_id']: x['response_sha256'] for x in response_seal['records']} == {
            x['attempt_id']: sha(public/'responses'/(x['attempt_id']+'.json')) for x in formal}
        assert response_seal['at'] >= max(ends[x['attempt_id']]['at'] for x in formal)
    else:
        response_seal = read(public/'PARTIAL_RESPONSES_SEALED.json')
        assert response_seal['status'] == 'PARTIAL_STOP'
        assert response_seal['request_seal_sha256'] == sha(public/'REQUESTS_SEALED.json')
        assert response_seal['ledger_sha256'] == sha(public/'CALL_LEDGER.jsonl')
    return {'formal': formal, 'smoke': smoke, 'starts': starts, 'ends': ends, 'full': full,
            'seal_sha256': sha(full_path if full else public/'PARTIAL_RESPONSES_SEALED.json')}


def reference(case, episode, split):
    endpoints = {role: episode['PRE_HISTORY' if role in 'AB' else 'POST_HISTORY_TO_Q'][role]['observations'][-1]
                 for role in 'ABXY'}
    path = AO0/(split+'_rel_v2')/'RELATION_TIMELINE.jsonl.gz'
    frames = {x['source_frame'] for x in endpoints.values()}
    relations = {}
    with gzip.open(path, 'rt', encoding='utf-8') as fh:
        for line in fh:
            row = json.loads(line)
            if row['frame'] in frames:
                relations.setdefault((row['frame'], row['native_id']), []).append(row)
    roles = {}
    for role, obs in endpoints.items():
        frame = obs['source_frame']; native = int(obs['source_fact_ids'][0].split('-N')[1])
        matches = [x for x in relations.get((frame, native), []) if x['status'] == 'UNIQUE']
        roles[role] = {'frame': frame, 'status': 'UNIQUE' if len(matches) == 1 else 'NONUNIQUE',
                       'gt_id': matches[0]['gt_id'] if len(matches) == 1 else None,
                       'match_iou': matches[0]['match_iou'] if len(matches) == 1 else None}
    g = {r: roles[r]['gt_id'] for r in 'ABXY'}
    why, physical = None, None
    if None in g.values():
        why = 'NONUNIQUE_ENDPOINT_GT_BINDING'
    elif g['A'] == g['B'] or g['X'] == g['Y']:
        why = 'DUPLICATE_PHYSICAL_ROLE'
    elif {g['A'], g['B']} != {g['X'], g['Y']}:
        why = 'MAPPING_OUTSIDE_CANDIDATES'
    else:
        xy = {r: 'A' if g[r] == g['A'] else 'B' for r in 'XY'}
        candidates = [x['mapping'] for x in episode['hypotheses']
                      if all(x['mapping'][r] == xy[r] for r in 'XY')]
        if len(candidates) != 1:
            why = 'CANDIDATE_MISMATCH'
        else:
            physical = dict(canonical(candidates[0]))
    return {'case': case, 'roles': roles, 'correct_physical_mapping': physical,
            'reference_scoreable': physical is not None, 'unscorable_reason': why,
            'relation_timeline_sha256': sha(path), 'reference_from': 'POSTSEAL_GT_BINDING'}


def classify(response, packet, binding):
    empty = {'json_valid': False, 'decision_parseable': False, 'raw_choice': None,
             'strict_schema_valid': False, 'normalization_applied': [], 'normalized_schema_valid': False,
             'assessment_usable': False, 'fact_reference_valid': False, 'cited_fact_ids': [], 'errors': []}
    if response is None:
        return {'transport_valid': False, 'finish_reason': None, **empty,
                'reference_scoreable': binding['reference_scoreable'], 'raw_physical_choice': None,
                'official_identity_outcome': 'UNSENT', 'decision_eligible': False}
    if response.get('transport_valid') is not True:
        return {'transport_valid': False, 'finish_reason': None, **empty,
                'reference_scoreable': binding['reference_scoreable'], 'raw_physical_choice': None,
                'official_identity_outcome': 'HTTP_UNKNOWN', 'decision_eligible': False}
    parsed = parse(response.get('content'), packet)
    choice = parsed['raw_choice']; mapping = None
    if choice in ('H1', 'H2'):
        matches = [x['mapping'] for x in packet['hypotheses'] if x['id'] == choice]
        if len(matches) == 1:
            mapping = dict(canonical(matches[0]))
    if response.get('finish_reason') != 'stop':
        outcome = 'INVALID_FINISH'
    elif not parsed['assessment_usable']:
        outcome = 'INVALID_OUTPUT'
    elif not binding['reference_scoreable']:
        outcome = 'UNSCORABLE'
    elif choice == 'DEFER':
        outcome = 'DEFER'
    else:
        outcome = 'CORRECT' if mapping is not None and canonical(mapping) == canonical(binding['correct_physical_mapping']) else 'WRONG'
    return {'transport_valid': True, 'finish_reason': response.get('finish_reason'), **parsed,
            'reference_scoreable': binding['reference_scoreable'], 'raw_physical_choice': mapping,
            'official_identity_outcome': outcome,
            'decision_eligible': outcome in ('CORRECT', 'WRONG', 'DEFER')}


def summary(attempts, bindings, full):
    by = {(x['case'], x['arm']): x for x in attempts}
    valid = lambda x: x['decision_eligible'] and bindings[x['case']]['reference_scoreable']
    positives = [by['B01', arm] for arm in ('H-D', 'H-D-REPEAT', 'H-D-PERMUTE')]
    negatives = [by[case, arm] for case in ('B02', 'B03', 'B04', 'B05')
                 for arm in ('H-D', 'H-D-REPEAT', 'H-D-PERMUTE')]
    stable = all(valid(x) and x['official_identity_outcome'] == 'CORRECT' for x in positives)
    safe = all(valid(x) and x['official_identity_outcome'] in ('CORRECT', 'DEFER') for x in negatives)
    gain = any(valid(by[case, 'E']) and valid(by[case, 'H-2D']) and valid(by[case, 'H-D'])
               and by[case, 'E']['official_identity_outcome'] in ('WRONG', 'DEFER')
               and by[case, 'H-2D']['official_identity_outcome'] == 'CORRECT'
               and by[case, 'H-D']['official_identity_outcome'] == 'CORRECT'
               for case in bindings)
    technical = full and all(x['decision_eligible'] for x in attempts)
    return {'full_response_seal': full, 'formal_started': sum(x['official_identity_outcome'] != 'UNSENT' for x in attempts),
            'returned': sum(x['transport_valid'] for x in attempts),
            'strict_schema_valid': sum(x['strict_schema_valid'] for x in attempts),
            'normalized_schema_valid': sum(x['normalized_schema_valid'] for x in attempts),
            'decision_eligible': sum(x['decision_eligible'] for x in attempts),
            'technical_complete': technical, 'B01_HD_stable': stable, 'four_negative_HD_safe': safe,
            'E_to_history_gain': gain, 'limited_exposed_signal': technical and stable and safe and gain,
            'unscorable_cases': [c for c in bindings if not bindings[c]['reference_scoreable']],
            'VLM_necessity': 'NOT_TESTED_NO_FULL_SAME_INFORMATION_NUMERIC_COMPARATOR'}


def main(run):
    chain = verify_chain(run)  # GT is opened only below this line.
    cases = {x['case_alias']: x for x in read(AO1/'SOURCE_MANIFEST.json')['cases']}
    episodes = {x['request_id'].split('-')[-1]: x for x in read(V6/'EPISODE_FACTS.json')}
    bindings = {case: reference(case, episodes[case], cases[case]['split']) for case in sorted(episodes)}
    attempts = []
    for request in chain['formal']:
        attempt = request['attempt_id']; packet = json.loads(request['text'])
        if attempt not in chain['starts']:
            response = None
        elif attempt not in chain['ends'] or not chain['ends'][attempt]['transport_valid']:
            response = {'transport_valid': False}
        else:
            response = read(Path(run)/'public/responses'/(attempt+'.json'))
        item = classify(response, packet, bindings[request['case']])
        attempts.append({'attempt_id': attempt, 'case': request['case'], 'arm': request['arm'], **item,
                         'response_sha256': sha(Path(run)/'public/responses'/(attempt+'.json'))
                         if response and response.get('transport_valid') else None,
                         'usage': response.get('usage') if response else None,
                         'peak_upper_usd': response.get('charged_upper_usd') if response else None})
    events = [{'case': case, 'correct_physical_mapping': bindings[case]['correct_physical_mapping'],
               'arms': {x['arm']: {'raw_choice': x['raw_choice'],
                                   'raw_physical_choice': x['raw_physical_choice'],
                                   'strict_schema_valid': x['strict_schema_valid'],
                                   'normalized_schema_valid': x['normalized_schema_valid'],
                                   'decision_eligible': x['decision_eligible'],
                                   'official_identity_outcome': x['official_identity_outcome'],
                                   'errors': x['errors']}
                        for x in attempts if x['case'] == case}} for case in sorted(bindings)]
    public = Path(run)/'public'
    save(public/'REFERENCE_BINDING.json', bindings)
    save(public/'ATTEMPT_RESULTS.json', attempts)
    save(public/'EVENT_RESULTS.json', events)
    result = summary(attempts, bindings, chain['full'])
    result['response_seal_sha256'] = chain['seal_sha256']
    save(public/'SUMMARY.json', result)
    print({k: result[k] for k in ('returned', 'strict_schema_valid', 'normalized_schema_valid',
                                  'decision_eligible', 'limited_exposed_signal')})


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--run', type=Path, required=True)
    main(p.parse_args().run)
