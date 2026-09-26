"""Independent postseal scoring of exposed EHR-1 cases; never edits model output."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from prepare import AO1, put, read, sha


def jsonl(path):
    return [json.loads(x) for x in Path(path).read_text(encoding='utf-8').splitlines()]


def verify(run):
    sender = run/'sender'
    plan = read(sender/'PLAN.json')
    requests = read(sender/'public/REQUESTS_SEALED.json')
    responses = read(sender/'public/RESPONSES_SEALED.json')
    schedule = [x['attempt_id'] for x in plan['requests']]
    assert len(schedule) == len(set(schedule)) == 25
    assert len(requests['records']) == len(responses['records']) == 25
    assert responses['request_seal_sha256'] == sha(sender/'public/REQUESTS_SEALED.json')
    assert requests['plan_sha256'] == sha(sender/'PLAN.json')
    reqs = {x['attempt_id']: x for x in requests['records']}
    resps = {x['attempt_id']: x for x in responses['records']}
    assert set(reqs) == set(resps) == set(schedule)
    for attempt in schedule:
        assert sha(sender/'private/bodies'/(attempt+'.json')) == reqs[attempt]['payload_sha256']
        assert sha(sender/'public/responses'/(attempt+'.json')) == resps[attempt]['response_sha256']
    ledger = jsonl(sender/'public/CALL_LEDGER.jsonl')
    starts = {x['attempt_id']: x for x in ledger if x['phase'] == 'START'}
    ends = {x['attempt_id']: x for x in ledger if x['phase'] == 'END'}
    assert len(starts) == len(ends) == len(ledger)//2 == 26
    assert set(starts) == set(ends) == set(schedule)|{'S001'}
    assert all(ends[x]['transport_valid'] for x in schedule)
    assert requests['at'] < min(starts[x]['at'] for x in schedule)
    assert responses['at'] >= max(ends[x]['at'] for x in schedule)
    assert all(ends[x]['response_sha256'] == resps[x]['response_sha256'] for x in schedule)
    assert read(sender/'public/responses/S001.json')['smoke_ok'] is True
    return plan, requests, responses, starts, ends


def facts(packet):
    ids = {o['fact_id'] for part in ('PRE_HISTORY','POST_HISTORY_TO_Q')
           for segment in packet[part].values() for o in segment['observations']}
    ids.update(o['fact_id'] for row in packet['INTERACTION_OBSERVATIONS'] for o in row['observations'])
    return ids


def physical_choice(packet, chosen, key):
    if chosen == 'DEFER':
        return None
    candidate = next(x for x in packet['hypotheses'] if x['id'] == chosen)
    matches = [x['choice'] for x in key['candidate_mapping'] if x['mapping'] == candidate['mapping']]
    assert len(matches) == 1
    return matches[0]


def parse(content, packet):
    try:
        value = json.loads(content)
    except (TypeError, ValueError):
        return dict(parseable=False, raw_preference=None, usable=False, errors=['NOT_JSON'])
    if not isinstance(value, dict):
        return dict(parseable=False, raw_preference=None, usable=False, errors=['NOT_OBJECT'])
    choice = value.get('preferred_hypothesis')
    structural = value.get('request_id') == packet['request_id'] and choice in ('H1','H2','DEFER')
    errors = [] if structural else ['INVALID_DECISION_STRUCTURE']
    if not structural:
        return dict(parseable=False, raw_preference=choice, usable=False, errors=errors)
    assessments = value.get('hypothesis_assessments')
    if not isinstance(assessments, list) or len(assessments) != 2 or {x.get('id') for x in assessments if isinstance(x, dict)} != {'H1','H2'}:
        errors.append('MISSING_OR_DUPLICATE_HYPOTHESIS_ASSESSMENT')
    else:
        allowed = facts(packet)
        for a in assessments:
            for field in ('supporting_fact_ids','conflicting_fact_ids'):
                cited = a.get(field)
                if not isinstance(cited, list) or any(not isinstance(x, str) or x not in allowed for x in cited):
                    errors.append(f'INVALID_{field.upper()}_{a["id"]}')
            assumptions = a.get('unresolved_assumptions')
            if not isinstance(assumptions, list) or any(not isinstance(x, str) for x in assumptions):
                errors.append(f'INVALID_UNRESOLVED_ASSUMPTIONS_{a["id"]}')
    if not isinstance(value.get('uncertainty_reason'), str):
        errors.append('INVALID_UNCERTAINTY_REASON')
    return dict(parseable=True, raw_preference=choice, usable=not errors, errors=errors,
                assessments=assessments if isinstance(assessments, list) else None,
                uncertainty_reason=value.get('uncertainty_reason'))


def main(run, b0_path):
    plan, req_seal, resp_seal, starts, ends = verify(run)
    # Deliberately opened only after the complete response and ledger seal passed.
    key_path = AO1/'public/SCORE_KEY.json'
    key = {x['case_alias']: x for x in read(key_path)['cases']}
    b0 = {x['case_alias']: x['b0'] for x in jsonl(b0_path)}
    numeric = read(run/'public/NUMERIC_REFERENCE.json')
    triggers = {x['case']: x for x in read(run/'public/TRIGGER_AUDIT.json')}
    rows = []
    for req in plan['requests']:
        attempt, case = req['attempt_id'], req['case']
        packet = json.loads(req['text'])
        response = read(run/'sender/public/responses'/(attempt+'.json'))
        result = parse(response.get('content'), packet)
        physical = physical_choice(packet, result['raw_preference'], key[case]) if result['parseable'] else None
        if not result['parseable']:
            status = 'UNSCORABLE'
        elif physical is None:
            status = 'DEFER'
        elif physical == key[case]['private_score_answer']:
            status = 'CORRECT'
        else:
            status = 'WRONG'
        rows.append(dict(attempt_id=attempt, case=case, arm=req['arm'], trigger=triggers[case]['deployment_status'],
                         raw_choice=result['raw_preference'], physical_AO1_choice=physical,
                         answer=key[case]['private_score_answer'], answer_origin=key[case]['answer_origin'],
                         b0=b0[case], status=status, decision_parseable=result['parseable'], usable=result['usable'],
                         evidence_errors=result['errors'], uncertainty_reason=result.get('uncertainty_reason'),
                         response_sha256=sha(run/'sender/public/responses'/(attempt+'.json')),
                         request_body_sha256=sha(run/'sender/private/bodies'/(attempt+'.json')),
                         finish_reason=response['finish_reason'], returned_model=response['returned_model'],
                         latency_seconds=response['latency_seconds'], usage=response['usage'],
                         charge_upper_usd=response['charged_upper_usd']))
    put(run/'public/ATTEMPT_RESULTS.json', rows)
    events = []
    for case in key:
        rr = {x['arm']: x for x in rows if x['case'] == case}
        events.append(dict(case=case, exposure='EXPOSED_DEVELOPMENT_DIAGNOSTIC',
                           would_trigger=triggers[case]['would_trigger'], trigger_type=triggers[case]['trigger_type'],
                           answer=key[case]['private_score_answer'], b0=b0[case],
                           N_H2D=numeric[case]['N_H2D']['choice'], N_HD=numeric[case]['N_HD']['choice'],
                           arms={arm: dict(status=x['status'], raw_choice=x['raw_choice'],
                                           physical_choice=x['physical_AO1_choice'], usable=x['usable'],
                                           evidence_errors=x['evidence_errors']) for arm, x in rr.items()}))
    put(run/'public/EVENT_RESULTS.json', events)
    b01 = next(x for x in events if x['case'] == 'B01')
    stable_b01 = all(b01['arms'][a]['status'] == 'CORRECT' and b01['arms'][a]['usable'] for a in ('H-D','H-D-REPEAT','H-D-PERMUTE'))
    negative_safe = all(x['arms'][a]['status'] != 'WRONG' for x in events[1:] for a in ('H-D','H-D-REPEAT','H-D-PERMUTE'))
    history_gain = any(x['arms']['E']['status'] != 'CORRECT' and x['arms']['H-2D']['status'] == 'CORRECT'
                       and x['arms']['H-D']['status'] == 'CORRECT' for x in events)
    spent = sum(x['charged_upper_usd'] for x in [read(run/'sender/public/responses'/(a+'.json')) for a in ['S001']+[r['attempt_id'] for r in plan['requests']]])
    summary = dict(status='SCORED_AFTER_ALL_25_SEALED', inference_calls=26, formal_requests=25,
                   parseable=sum(x['decision_parseable'] for x in rows), usable=sum(x['usable'] for x in rows),
                   peak_rate_upper_usd=spent, cap_usd=3, total_formal_latency_seconds=sum(x['latency_seconds'] for x in rows),
                   B01_H_D_stable=stable_b01, negative_H_D_safe=negative_safe, E_to_history_change=history_gain,
                   technical_gate=sum(x['decision_parseable'] for x in rows) >= 24 and all(
                       r['decision_parseable'] for r in rows if r['case'] == 'B01'),
                   limited_exposed_case_signal=stable_b01 and negative_safe and history_gain,
                   VLM_necessity='NOT_ESTABLISHED_NO_FULL_SAME_INFORMATION_NUMERIC_COMPARATOR',
                   score_key_sha256=sha(key_path), b0_source_sha256=sha(b0_path),
                   request_seal_sha256=sha(run/'sender/public/REQUESTS_SEALED.json'),
                   response_seal_sha256=sha(run/'sender/public/RESPONSES_SEALED.json'))
    put(run/'public/SUMMARY.json', summary)
    print(json.dumps({k: summary[k] for k in ('parseable','usable','peak_rate_upper_usd','limited_exposed_case_signal')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--b0', type=Path, required=True)
    args = parser.parse_args()
    main(args.run, args.b0)
