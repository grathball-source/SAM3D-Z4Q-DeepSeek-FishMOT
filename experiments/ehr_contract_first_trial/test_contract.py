"""Real B01 slice plus independent, self-consistent semantic negative fixtures."""
import argparse
import copy
import hashlib
import json
import shutil
import tempfile
from pathlib import Path

import build
import contract
import score
import sender
import validate


def reject(fn):
    try:
        fn()
    except (AssertionError, ValueError, KeyError, TypeError):
        return
    raise AssertionError('negative fixture unexpectedly accepted')


def answer(packet, choice='H1'):
    fact = packet['PRE_HISTORY']['A']['observations'][-1]['fact_id']
    return {'request_id': packet['request_id'], 'preferred_hypothesis': choice,
            'hypothesis_assessments': [
                {'id': h, 'supporting_fact_ids': [fact] if h == choice else [],
                 'conflicting_fact_ids': [], 'unresolved_assumptions': []}
                for h in ('H1', 'H2')],
            'uncertainty_reason': 'Identity remains ambiguous.' if choice == 'DEFER' else ''}


def mutate_self_consistent(run, old_public, v6_source, media, attempt, change):
    with tempfile.TemporaryDirectory(prefix='ehrcf_fixture_') as dirname:
        tmp = Path(dirname); (tmp/'public').mkdir(); (tmp/'private').mkdir(); (tmp/'send/bodies').mkdir(parents=True)
        for name in ('REQUESTS_LOGICAL.json', 'REQUEST_MANIFEST.json', 'CONTRACT.json',
                     'CONTRACT_EXAMPLES.json', 'SMOKE_REQUESTS.json'):
            shutil.copyfile(run/'public'/name, tmp/'public'/name)
        shutil.copyfile(run/'private/SOURCE_LOCATION.json', tmp/'private/SOURCE_LOCATION.json')
        path = tmp/'public/REQUESTS_LOGICAL.json'
        obj = build.read(path)
        request = next(x for x in obj['requests'] if x['attempt_id'] == attempt)
        packet = json.loads(request['text']); change(packet)
        request['text'] = build.wire(packet)
        path.write_text(json.dumps(obj, ensure_ascii=False), encoding='utf-8')
        manifest_path = tmp/'public/REQUEST_MANIFEST.json'
        manifest = build.read(manifest_path)
        record = next(x for x in manifest['requests'] if x['attempt_id'] == attempt)
        record['text_sha256'] = hashlib.sha256(request['text'].encode()).hexdigest()
        manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
        assert record['text_sha256'] == hashlib.sha256(request['text'].encode()).hexdigest()
        all_requests = obj['requests']+build.read(tmp/'public/SMOKE_REQUESTS.json')['requests']
        digests = {image['sha256'] for item in all_requests for image in item['images']}
        ids = {digest: 'file-api-TEST-FIXTURE-'+str(i) for i, digest in enumerate(sorted(digests))}
        assert len(ids) == 59
        (tmp/'send/UPLOAD_LEDGER.jsonl').write_text(''.join(json.dumps(
            {'phase': 'END', 'sha256': digest, 'file_id': file_id})+'\n' for digest, file_id in ids.items()))
        original = {x['attempt_id']: x for x in build.read(run/'public/REQUESTS_LOGICAL.json')['requests']}
        body_records = []
        for item in all_requests:
            if item['attempt_id'] == attempt:
                payload = sender.body(original[attempt], ids)
                payload['messages'][1]['content'][0]['text'] = item['text']
            else:
                payload = sender.body(item, ids)
            raw = sender.wire(payload)
            (tmp/'send/bodies'/(item['attempt_id']+'.json')).write_bytes(raw)
            body_records.append({'attempt_id': item['attempt_id'], 'payload_sha256': hashlib.sha256(raw).hexdigest(),
                                 'payload_bytes': len(raw)})
        build.save(tmp/'public/BODY_GATE.json', {'status': 'BODY_GATE_PASS', 'records': body_records})
        assert all(hashlib.sha256((tmp/'send/bodies'/(x['attempt_id']+'.json')).read_bytes()).hexdigest() ==
                   x['payload_sha256'] for x in body_records)
        # Both manifest and final body hashes are internally consistent; only semantics may reject them.
        reject(lambda: validate.logical(tmp, old_public, v6_source, media))
        reject(lambda: validate.bodies(tmp))


def main(run):
    run = Path(run)
    location = build.read(run/'private/SOURCE_LOCATION.json')
    old_public, v6_source = Path(location['old_public']), Path(location['v6_source'])
    media = run/'private/media'
    old = build.read(old_public/'REQUESTS_LOGICAL.json')['requests']
    prior = {x['attempt_id']: x for x in old}
    new = build.read(run/'public/REQUESTS_LOGICAL.json')['requests']
    current = {x['attempt_id']: x for x in new}
    assert build.read(run/'public/CONTRACT.json') == contract.schema()
    assert build.read(run/'public/CONTRACT_EXAMPLES.json')['examples'] == [contract.example(c) for c in contract.CHOICES]
    assert json.dumps(contract.schema(), separators=(',', ':')) in contract.system()
    assert all(json.dumps(contract.example(c), separators=(',', ':')) in contract.system()
               for c in contract.CHOICES)
    checks = ['ONE_SCHEMA_PROMPT_EXAMPLES_PARSER']
    leaks = []
    for case in (f'B{i:02d}' for i in range(1, 6)):
        old_e = json.loads(prior[case+'-E']['text'])
        new_e = json.loads(current[case+'-E']['text'])
        for role in 'XY':
            old_seg = old_e['POST_HISTORY_TO_Q'][role]
            assert old_seg['anchor_frame'] != old_seg['observations'][0]['source_frame']
            assert 'anchor_frame' not in new_e['POST_HISTORY_TO_Q'][role]
            leaks.append((case, role))
        assert all('anchor_frame' not in new_e[part][role] for part, roles in
                   (('PRE_HISTORY', 'AB'), ('POST_HISTORY_TO_Q', 'XY')) for role in roles)
    assert len(leaks) == 10
    checks.append('OLD_10_STALE_ANCHORS_DETECTED_NEW_E_WHITELIST_CLEAN')
    h = json.loads(prior['B01-H-D']['text']); e = current['B01-E']
    ids = {x['sha256']: 'file-api-TEST-FIXTURE-'+str(i) for i, x in enumerate(e['images'])}
    images = json.loads(prior['B01-E']['text'])['IMAGE_INDEX']
    first = build.project_e(h, images); first['request_id'] = 'EHR-CF-B01'
    changed = copy.deepcopy(h)
    changed['PRE_HISTORY']['B']['observations'] = changed['PRE_HISTORY']['B']['observations'][-1:]
    changed['PRE_HISTORY']['B']['anchor_frame'] = -999
    changed['PRE_HISTORY']['B']['velocity'] = {'not_a_measurement': 12345}
    changed['POST_HISTORY_TO_Q']['X']['observations'] = changed['POST_HISTORY_TO_Q']['X']['observations'][-1:]
    changed['POST_HISTORY_TO_Q']['X']['anchor_frame'] = -999
    changed['trigger'] = {'secret_history_event': True}
    changed['future_history_field'] = {'unapproved': 'MUST_NOT_LEAK'}
    second = build.project_e(changed, images); second['request_id'] = 'EHR-CF-B01'
    assert build.wire(first) == build.wire(second) == e['text']
    altered_request = dict(e, text=build.wire(second))
    assert sender.wire(sender.body(e, ids)) == sender.wire(sender.body(altered_request, ids))
    checks.append('E_ACTUAL_MESSAGE_NONINTERFERENCE_HIDDEN_HISTORY_AND_NOVEL_FIELD')
    mutations = [
        ('B01-E', lambda p: p['POST_HISTORY_TO_Q']['X'].update(anchor_frame=1484)),
        ('B01-E', lambda p: p.update(future_history_field={'leak': True})),
        ('B01-E', lambda p: p['PRE_HISTORY']['A']['observations'][0].update(source_fact_ids=['NATIVE'])),
        ('B01-H-D', lambda p: p['INTERACTION_TABLE']['columns'].remove('depth_quality')),
        ('B01-H-D', lambda p: p['INTERACTION_TABLE']['rows'][0].__setitem__(
            p['INTERACTION_TABLE']['columns'].index('depth_median_pipeline_mm'), 123456.0)),
        ('B01-H-D', lambda p: p['IMAGE_INDEX'][2]['anonymous_tokens'][0].update(fact_id='NONEXISTENT')),
        ('B01-H-D', lambda p: p['IMAGE_INDEX'][0].update(frame=p['q_frame']+1)),
        ('B01-H-D', lambda p: p['INTERACTION_TABLE']['rows'][0].__setitem__(
            p['INTERACTION_TABLE']['columns'].index('fact_id'), 'SRC-F1-N1'))]
    for attempt, change in mutations:
        mutate_self_consistent(run, old_public, v6_source, media, attempt, change)
    checks.append('EIGHT_SELF_CONSISTENT_SEMANTIC_MUTATIONS_REJECTED')
    request = current['B01-H-D']; packet = json.loads(request['text'])
    fake_ids = {x['sha256']: 'file-api-TEST-FIXTURE-'+str(i) for i, x in enumerate(request['images'])}
    actual_body = sender.body(request, fake_ids)
    assert actual_body['messages'][1]['content'][0]['text'] == request['text']
    binding = {'reference_scoreable': True, 'correct_physical_mapping': packet['hypotheses'][0]['mapping']}
    response = {'transport_valid': True, 'finish_reason': 'stop', 'content': json.dumps(answer(packet))}
    assert score.classify(response, packet, binding)['official_identity_outcome'] == 'CORRECT'
    assert score.classify({'transport_valid': True, 'finish_reason': 'stop',
                           'content': json.dumps(answer(packet, 'H2'))}, packet, binding)['official_identity_outcome'] == 'WRONG'
    assert score.classify({'transport_valid': True, 'finish_reason': 'stop',
                           'content': json.dumps(answer(packet, 'DEFER'))}, packet, binding)['official_identity_outcome'] == 'DEFER'
    swapped = copy.deepcopy(packet)
    for candidate in swapped['hypotheses']:
        candidate['id'] = 'H2' if candidate['id'] == 'H1' else 'H1'
    swapped['hypotheses'].reverse()
    assert score.classify({'transport_valid': True, 'finish_reason': 'stop',
                           'content': json.dumps(answer(swapped, 'H2'))}, swapped, binding)['official_identity_outcome'] == 'CORRECT'
    occupied = copy.deepcopy(packet); occupied['hypotheses'][0]['mapping']['U1'] = 'B'
    assert score.classify(response, occupied, binding)['official_identity_outcome'] == 'WRONG'
    checks.append('REAL_B01_SOURCE_PROJECTION_BODY_PARSER_PHYSICAL_SCORER_H1_H2_DEFER_PERMUTE_U')
    obj = answer(packet)
    alias = copy.deepcopy(obj)
    for row in alias['hypothesis_assessments']:
        row['hypothesis_id'] = row.pop('id')
    parsed = contract.parse(json.dumps(alias), packet)
    assert not parsed['strict_schema_valid'] and parsed['normalized_schema_valid']
    assert parsed['normalization_applied'] == ['single_label_alias_to_id']
    keyed = copy.deepcopy(obj)
    keyed['hypothesis_assessments'] = {x.pop('id'): x for x in keyed['hypothesis_assessments']}
    parsed = contract.parse(json.dumps(keyed), packet)
    assert not parsed['strict_schema_valid'] and parsed['normalized_schema_valid']
    assert parsed['normalization_applied'] == ['H1_H2_dictionary_to_list']
    reversed_rows = copy.deepcopy(obj); reversed_rows['hypothesis_assessments'].reverse()
    parsed = contract.parse(json.dumps(reversed_rows), packet)
    assert parsed['strict_schema_valid'] and parsed['normalization_applied'] == ['assessment_order_H1_H2']
    checks.append('STRICT_AND_THREE_FROZEN_LOSSLESS_NORMALIZATIONS')
    bad = copy.deepcopy(obj); bad['hypothesis_assessments'][0]['supporting_fact_ids'] = ['NONEXISTENT']
    assert contract.parse(json.dumps(bad), packet)['errors'] == ['UNKNOWN_FACT_ID']
    bad = copy.deepcopy(obj); bad['hypothesis_assessments'][0]['hypothesis_id'] = 'H2'
    assert not contract.parse(json.dumps(bad), packet)['normalized_schema_valid']
    bad = copy.deepcopy(obj); bad['hypothesis_assessments'][1]['id'] = 'H1'
    assert not contract.parse(json.dumps(bad), packet)['normalized_schema_valid']
    bad = copy.deepcopy(obj); bad['physical_mapping'] = packet['hypotheses'][1]['mapping']
    parsed = contract.parse(json.dumps(bad), packet)
    assert parsed['raw_choice'] == 'H1' and not parsed['normalized_schema_valid']
    raw = json.dumps(obj).replace('"request_id":', '"request_id":"DUP", "request_id":', 1)
    assert not contract.parse(raw, packet)['json_valid']
    bad = copy.deepcopy(obj); bad['hypothesis_assessments'] = []
    assert not contract.parse(json.dumps(bad), packet)['normalized_schema_valid']
    bad = copy.deepcopy(obj); bad['hypothesis_assessments'][0]['unresolved_assumptions'] = 'wrong type'
    assert not contract.parse(json.dumps(bad), packet)['normalized_schema_valid']
    checks.append('UNKNOWN_CITATION_CONFLICT_DUPLICATE_JSON_EXTRA_MAPPING_MISSING_ASSESSMENT_REJECTED')
    assert score.classify(None, packet, binding)['official_identity_outcome'] == 'UNSENT'
    assert score.classify({'transport_valid': False}, packet, binding)['official_identity_outcome'] == 'HTTP_UNKNOWN'
    assert score.classify(response, packet, {'reference_scoreable': False,
           'correct_physical_mapping': None})['official_identity_outcome'] == 'UNSCORABLE'
    assert score.classify(dict(response, finish_reason='length'), packet, binding)['official_identity_outcome'] == 'INVALID_FINISH'
    assert score.classify(dict(response, content=json.dumps(bad)), packet, binding)['official_identity_outcome'] == 'INVALID_OUTPUT'
    attempts = [{'case': f'B{i:02d}', 'arm': arm, 'decision_eligible': True,
                 'official_identity_outcome': 'CORRECT', 'transport_valid': True,
                 'strict_schema_valid': True, 'normalized_schema_valid': True}
                for i in range(1, 6) for arm in build.ARMS]
    next(x for x in attempts if x['case'] == 'B01' and x['arm'] == 'E')['official_identity_outcome'] = 'DEFER'
    bindings = {f'B{i:02d}': {'reference_scoreable': True} for i in range(1, 6)}
    assert score.summary(attempts, bindings, True)['limited_exposed_signal']
    for outcome in ('UNSENT', 'HTTP_UNKNOWN', 'UNSCORABLE', 'INVALID_OUTPUT', 'INVALID_FINISH'):
        altered = copy.deepcopy(attempts)
        row = next(x for x in altered if x['case'] == 'B03' and x['arm'] == 'H-D')
        row.update(decision_eligible=False, official_identity_outcome=outcome)
        assert not score.summary(altered, bindings, True)['four_negative_HD_safe']
    checks.append('INVALID_NEGATIVES_UNSENT_UNKNOWN_UNSCORABLE_NEVER_COUNT_SAFE')
    for case in (f'B{i:02d}' for i in range(1, 6)):
        left, right = current[case+'-H-D'], current[case+'-H-D-REPEAT']
        assert sender.wire(sender.body(left, {x['sha256']: 'file-api-TEST-'+x['sha256'][:8]
                                                for x in left['images']})) == sender.wire(sender.body(
            right, {x['sha256']: 'file-api-TEST-'+x['sha256'][:8] for x in right['images']}))
    checks.append('REPEAT_ACTUAL_BODY_IDENTICAL')
    tests = {'status': 'PASS', 'fixture': 'TEST_FIXTURE_NO_MODEL_CALL', 'checks': checks,
             'self_consistent_semantic_mutations': len(mutations), 'old_stale_post_anchors': len(leaks)}
    build.save(run/'public/CONTRACT_TESTS.json', tests)
    acceptance = {'status': 'PASS', 'fixture': 'TEST_FIXTURE_NO_MODEL_CALL',
                  'B01': {'q': 1498, 'A_velocity': 'UNKNOWN', 'real_source_recheck': 'PASS',
                          'source_to_body_to_scorer': 'PASS'},
                  'cases': 5, 'formal_requests': 25, 'synthetic_smoke_templates': 2,
                  'source_recheck_sha256': build.sha(run/'public/UPSTREAM_SOURCE_RECHECK.json'),
                  'logical_audit_sha256': build.sha(run/'public/SOURCE_TO_BODY_AUDIT.json'),
                  'tests_sha256': build.sha(run/'public/CONTRACT_TESTS.json')}
    build.save(run/'public/END_TO_END_ACCEPTANCE.json', acceptance)
    print({'acceptance': 'PASS', 'checks': len(checks), 'semantic_mutations': len(mutations)})


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--run', type=Path, required=True)
    main(p.parse_args().run)
