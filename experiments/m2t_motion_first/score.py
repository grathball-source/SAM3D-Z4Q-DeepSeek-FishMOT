"""Independent post-seal M2-T parser, evidence validator, deterministic decoder and scorer."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

EDGES = ('A-X', 'A-Y', 'B-X', 'B-Y')
RELATIONS = ('SUPPORT', 'CONTRADICT', 'UNRESOLVED')
CUES = ('OBSERVED_CONTINUITY', 'ENTRY_EXIT_COMPATIBILITY', 'RELATIVE_MOTION',
        'TEMPORAL_TURNING', 'UNRESOLVED')
CANDIDATES = {'STRAIGHT': ('A-X', 'B-Y'), 'CROSSED': ('A-Y', 'B-X')}


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    assert not path.exists()
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf-8')


def evidence_status(evidence, sent):
    if not isinstance(evidence, list):
        return 'EVIDENCE_NOT_ARRAY', [], False
    by_id = {image['image_id']: image for image in sent}
    seen = set()
    for cite in evidence:
        if not isinstance(cite, dict) or not all(k in cite for k in
               ('image_id', 'observation_tokens', 'relative_seconds', 'observation')):
            return 'MALFORMED_CITATION', sorted(seen)
        image = by_id.get(cite['image_id'])
        if image is None or image['kind'] != 'G':
            return 'UNSENT_OR_NON_GEOMETRY_IMAGE', sorted(seen)
        tokens = cite['observation_tokens']
        if not isinstance(tokens, list) or not tokens or not all(isinstance(x, str) for x in tokens):
            return 'MISSING_OBSERVATION_TOKENS', sorted(seen)
        if not set(tokens) <= set(image['observation_tokens']):
            return 'UNSENT_OBSERVATION_TOKEN', sorted(seen)
        when = cite['relative_seconds']
        if type(when) not in (int, float) or abs(when - image['relative_seconds']) > .002:
            return 'UNSENT_TIME', sorted(seen)
        if not isinstance(cite['observation'], str) or not cite['observation'].strip():
            return 'EMPTY_OBSERVATION', sorted(seen)
        seen.add((cite['image_id'], image['relative_seconds']))
    return None, sorted(seen)


def parse(content, request_id, sent, endpoint_ids):
    try:
        payload = json.loads(content) if isinstance(content, str) else None
    except json.JSONDecodeError:
        payload = None
    if not isinstance(payload, dict) or payload.get('request_id') != request_id or not isinstance(payload.get('edges'), dict):
        return dict(schema_valid=False, schema_reason='MISSING_BOUND_OBJECT', edges={}, choice='ABSTAIN')
    edges = payload['edges']
    if set(edges) != set(EDGES):
        return dict(schema_valid=False, schema_reason='NOT_EXACTLY_FOUR_EDGES', edges={}, choice='ABSTAIN')
    parsed = {}
    schema_valid = True
    for name in EDGES:
        row = edges[name]
        if not isinstance(row, dict) or row.get('relation') not in RELATIONS or row.get('cue') not in CUES or not all(
            isinstance(row.get(k), str) for k in ('gaps_or_assumptions', 'competing_explanation')):
            schema_valid = False
            parsed[name] = dict(status='INVALID_SCHEMA', relation=None, cue=None,
                                evidence_reason='MALFORMED_EDGE', cited_times=[], middle_cited=False)
            continue
        relation = row['relation']
        reason, times = evidence_status(row.get('evidence'), sent)
        middle = any(image_id not in endpoint_ids for image_id, _ in times)
        if relation != 'UNRESOLVED' and reason is None and len({x[1] for x in times}) < 2:
            reason = 'FEWER_THAN_TWO_DISTINCT_G_TIMES'
        status = 'INVALID_EVIDENCE' if reason else 'VALID'
        parsed[name] = dict(status=status, relation=relation, cue=row['cue'],
                            evidence_reason=reason, cited_times=times, middle_cited=middle,
                            evidence=row.get('evidence'), gaps_or_assumptions=row['gaps_or_assumptions'],
                            competing_explanation=row['competing_explanation'])
    return dict(schema_valid=schema_valid, schema_reason=None if schema_valid else 'MALFORMED_EDGE',
                edges=parsed, choice=decode(parsed) if schema_valid else 'ABSTAIN')


def decode(edges):
    """Unknown or invalid edges cannot be used as a zero-score rival."""
    if set(edges) != set(EDGES) or any(edges[x]['status'] != 'VALID' for x in EDGES):
        return 'ABSTAIN'
    score = {'SUPPORT': 1, 'CONTRADICT': -1, 'UNRESOLVED': 0}
    eligible = []
    for name, selected in CANDIDATES.items():
        rival = CANDIDATES['CROSSED' if name == 'STRAIGHT' else 'STRAIGHT']
        if all(edges[x]['relation'] == 'SUPPORT' for x in selected) and sum(score[edges[x]['relation']] for x in rival) <= 0:
            eligible.append(name)
    return eligible[0] if len(eligible) == 1 else 'ABSTAIN'


def verify_seal(run, manifest):
    sent = run / 'sender/public'
    seal = read(sent / 'RESPONSES_SEALED.json')
    assert seal['status'] == 'ALL_25_RESPONSES_SEALED_BEFORE_SCORE'
    assert digest(sent / 'REQUESTS_SEALED.json') == seal['requests_seal_sha256']
    req_seal = read(sent / 'REQUESTS_SEALED.json')
    assert req_seal['status'] == 'ALL_25_BODIES_FROZEN_BEFORE_FORMAL_CALL'
    req_map = {x['attempt_id']: x for x in req_seal['records']}
    assert len(req_map) == len(seal['records']) == len(manifest['requests']) == 25
    response_map = {x['attempt_id']: x for x in seal['records']}
    assert set(req_map) == set(response_map) == {x['attempt_id'] for x in manifest['requests']}
    for request in manifest['requests']:
        ident = request['attempt_id']
        assert req_map[ident]['case_alias'] == request['case_alias'] and req_map[ident]['arm'] == request['arm']
        assert digest(run / 'sender/private/bodies' / (ident + '.json')) == req_map[ident]['payload_sha256']
        assert digest(sent / 'responses' / (ident + '.json')) == response_map[ident]['response_sha256']
        response = read(sent / 'responses' / (ident + '.json'))
        assert response['attempt_id'] == ident and response['transport_valid']
    events = [json.loads(x) for x in (sent / 'CALL_LEDGER.jsonl').read_text().splitlines()]
    starts = [x for x in events if x['phase'] == 'START']
    ends = [x for x in events if x['phase'] == 'END']
    assert len(starts) == len(ends) == 26
    assert len({x['attempt_id'] for x in starts}) == 26
    for event in starts:
        if event['attempt_id'] != 'S001':
            assert event['payload_sha256'] == req_map[event['attempt_id']]['payload_sha256']
    for event in ends:
        assert event['transport_valid']
        if event['attempt_id'] != 'S001':
            assert event['response_sha256'] == digest(sent / 'responses' / (event['attempt_id'] + '.json'))
    return ends


def main(args):
    run = args.run
    manifest = read(run / 'public/REQUEST_MANIFEST.json')
    ends = verify_seal(run, manifest)  # No key opened before this point.
    source = read(run / 'public/SOURCE_MANIFEST.json')
    cases = {x['case_alias']: x for x in source['cases']}
    answer_key = read(args.score_key)
    answers = {x['case_alias']: x['private_score_answer'] for x in answer_key['cases']}
    assert set(cases) == set(answers) == {'B01', 'B02', 'B03', 'B04', 'B05'}
    output = []
    for request in manifest['requests']:
        ident, alias = request['attempt_id'], request['case_alias']
        response = read(run / 'sender/public/responses' / (ident + '.json'))
        endpoint_frames = set(cases[alias]['endpoint_frames'])
        frame_to_id = dict(zip(cases[alias]['all_frames'],
                               [x['image_id'] for x in cases[alias]['g_images']], strict=True))
        endpoint_ids = {frame_to_id[x] for x in endpoint_frames}
        parsed = parse(response['content'], request['request_id'], request['images'], endpoint_ids)
        if response['finish_reason'] != 'stop':
            parsed['choice'] = 'ABSTAIN'
        ao1_choice = cases[alias]['candidate_to_AO1_choice'].get(parsed['choice'])
        correct = answers[alias]
        status = ('INVALID_SCHEMA' if not parsed['schema_valid'] else
                  'ABSTAIN' if parsed['choice'] == 'ABSTAIN' else
                  'CORRECT' if ao1_choice == correct else 'WRONG')
        b0 = correct if alias != 'B01' else ('C2' if correct == 'C1' else 'C1')
        output.append(dict(attempt_id=ident, case_alias=alias, arm=request['arm'],
                           schema_valid=parsed['schema_valid'], schema_reason=parsed['schema_reason'],
                           edges=parsed['edges'], decoded_relation=parsed['choice'],
                           ao1_choice=ao1_choice, identity_status=status,
                           answer_canonical=correct, b0_canonical=b0,
                           b0_fallback_simulated=b0 if ao1_choice is None else ao1_choice,
                           finish_reason=response['finish_reason'], returned_model=response['returned_model'],
                           latency_seconds=response['latency_seconds'], charged_upper_usd=response['charged_upper_usd'],
                           semantic_visual_support='UNKNOWN_PENDING_POST_SCORE_PIXEL_REVIEW'))
    assert not args.out.exists()
    args.out.mkdir(parents=True)
    (args.out / 'ATTEMPT_RESULTS.jsonl').write_text(''.join(json.dumps(x, ensure_ascii=False, allow_nan=False) + '\n' for x in output), encoding='utf-8')
    events = []
    for alias in sorted(cases):
        arm = {x['arm']: x for x in output if x['case_alias'] == alias}
        assert set(arm) == {'G-SEQ', 'G-SEQ-REPEAT', 'G+AP', 'G+AP-REPEAT', 'G-END'}
        events.append(dict(case_alias=alias, original_case_id=cases[alias]['original_case_id'],
                           case_role='AO0_POSITIVE' if alias == 'B01' else 'OLD_HARM_NEGATIVE',
                           answer=answers[alias], b0=arm['G-SEQ']['b0_canonical'],
                           numeric_motion=cases[alias]['numeric_motion'],
                           arms={name: dict(identity_status=row['identity_status'],
                                            relation=row['decoded_relation'], ao1_choice=row['ao1_choice'],
                                            schema_valid=row['schema_valid'],
                                            invalid_edges=[e for e, v in row['edges'].items() if v['status'] != 'VALID'],
                                            middle_cited=any(v['middle_cited'] for v in row['edges'].values()))
                                 for name, row in arm.items()},
                           g_repeat_same=arm['G-SEQ']['decoded_relation'] == arm['G-SEQ-REPEAT']['decoded_relation'],
                           gap_repeat_same=arm['G+AP']['decoded_relation'] == arm['G+AP-REPEAT']['decoded_relation']))
    (args.out / 'EVENT_RESULTS.jsonl').write_text(''.join(json.dumps(x, ensure_ascii=False, allow_nan=False) + '\n' for x in events), encoding='utf-8')
    schema_count = sum(x['schema_valid'] for x in output)
    g_positive = [x for x in output if x['case_alias'] == 'B01' and x['arm'] in ('G-SEQ', 'G-SEQ-REPEAT')]
    negative_g = [x for x in output if x['case_alias'] != 'B01' and x['arm'] in ('G-SEQ', 'G-SEQ-REPEAT')]
    technical = schema_count >= 24 and all(x['schema_valid'] for x in g_positive)
    motion = (technical and all(x['identity_status'] == 'CORRECT' for x in g_positive) and
              all(x['identity_status'] in ('CORRECT', 'ABSTAIN') for x in negative_g) and
              any(any(v['middle_cited'] and v['status'] == 'VALID' and v['relation'] != 'UNRESOLVED'
                      for v in x['edges'].values()) for x in output if x['arm'] == 'G-SEQ'))
    verdict = ('ENGINEERING_FAILURE' if not technical else
               'TENTATIVE_MOTION_FIRST_SIGNAL_ON_EXPOSED_CASES' if motion else
               'FAIL_STOP_FROZEN_M2T')
    summary = dict(verdict=verdict, technical_complete=technical, schema_valid=schema_count,
                   formal_attempts=len(output), inference_http_attempts=len(ends),
                   per_arm={name: dict(Counter(x['identity_status'] for x in output if x['arm'] == name))
                            for name in ('G-SEQ', 'G-SEQ-REPEAT', 'G+AP', 'G+AP-REPEAT', 'G-END')},
                   g_repeat_agreement=sum(x['g_repeat_same'] for x in events),
                   gap_repeat_agreement=sum(x['gap_repeat_same'] for x in events),
                   total_charged_upper_usd=sum(x['charged_upper_usd'] for x in ends),
                   total_latency_seconds=sum(x['latency_seconds'] for x in output),
                   visual_semantics='UNKNOWN_PENDING_POST_SCORE_PIXEL_REVIEW',
                   new_idf1_hota_computed=False)
    save(args.out / 'SUMMARY.json', summary)
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--score-key', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    main(parser.parse_args())
