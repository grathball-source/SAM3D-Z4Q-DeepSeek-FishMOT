"""Seal and describe the five B01 outputs after the prehistory contract stop."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from prepare import AO1, put, read, sha
from score import jsonl, parse, physical_choice


def main(run, b0_source):
    sender = run/'sender'
    plan = read(sender/'PLAN.json')
    assert [x['attempt_id'] for x in plan['requests'][:5]] == [f'B01-{arm}' for arm in
            ('E','H-2D','H-D','H-D-REPEAT','H-D-PERMUTE')]
    assert not (sender/'public/RESPONSES_SEALED.json').exists()
    assert read(run/'public/LINEAGE_AUDIT_V2.json')['status'] == 'POST_FREEZE_SOURCE_CONTRACT_FAILURE'
    request_seal = read(sender/'public/REQUESTS_SEALED.json')
    assert len(request_seal['records']) == 25
    assert request_seal['plan_sha256'] == sha(sender/'PLAN.json')
    for record in request_seal['records']:
        assert record['payload_sha256'] == sha(sender/'private/bodies'/(record['attempt_id']+'.json'))
    ledger = jsonl(sender/'public/CALL_LEDGER.jsonl')
    starts = {x['attempt_id']: x for x in ledger if x['phase'] == 'START'}
    ends = {x['attempt_id']: x for x in ledger if x['phase'] == 'END'}
    attempts = ['S001']+[x['attempt_id'] for x in plan['requests'][:5]]
    assert set(starts) == set(ends) == set(attempts) and len(ledger) == 12
    assert all(ends[x]['transport_valid'] for x in attempts)
    assert request_seal['at'] < starts[attempts[1]]['at']
    records = []
    for attempt in attempts:
        path = sender/'public/responses'/(attempt+'.json')
        assert path.is_file() and ends[attempt]['response_sha256'] == sha(path)
        records.append(dict(attempt_id=attempt, response_sha256=sha(path)))
    assert read(sender/'public/responses/S001.json')['smoke_ok'] is True
    seal_path = sender/'public/PARTIAL_RESPONSES_SEALED.json'
    put(seal_path, dict(status='FIVE_B01_FORMAL_RESPONSES_SEALED_ENGINEERING_STOP',
                        at=datetime.now(timezone.utc).isoformat(),
                        request_seal_sha256=sha(sender/'public/REQUESTS_SEALED.json'), records=records,
                        unsent=[x['attempt_id'] for x in plan['requests'][5:]],
                        reason='PRE_HISTORY_NATIVE_LINEAGE_NOT_ANCHOR_CONNECTED'))
    # No answer key or old response is opened until the partial seal above exists.
    key_path = AO1/'public/SCORE_KEY.json'
    key = next(x for x in read(key_path)['cases'] if x['case_alias'] == 'B01')
    b0 = next(x['b0'] for x in jsonl(b0_source) if x['case_alias'] == 'B01')
    outputs = []
    for request in plan['requests']:
        attempt = request['attempt_id']
        if request['case'] != 'B01':
            outputs.append(dict(attempt_id=attempt, case=request['case'], arm=request['arm'],
                                status='NOT_SENT_ENGINEERING_STOP', response=None))
            continue
        packet = json.loads(request['text'])
        response = read(sender/'public/responses'/(attempt+'.json'))
        parsed = parse(response.get('content'), packet)
        physical = physical_choice(packet, parsed['raw_preference'], key) if parsed['parseable'] else None
        outputs.append(dict(attempt_id=attempt, case='B01', arm=request['arm'],
                            status='UNSCORABLE_PROTOCOL_PRE_HISTORY_LINEAGE',
                            decision_parseable=parsed['parseable'], evidence_usable=parsed['usable'],
                            raw_choice=parsed['raw_preference'], physical_AO1_choice=physical,
                            posthoc_matches_exposed_answer=None if physical is None else physical == key['private_score_answer'],
                            exposed_answer=key['private_score_answer'], B0=b0,
                            evidence_errors=parsed['errors'],
                            latency_seconds=response['latency_seconds'], usage=response['usage'],
                            charge_upper_usd=response['charged_upper_usd'],
                            response_sha256=sha(sender/'public/responses'/(attempt+'.json'))))
    put(run/'public/ATTEMPT_RESULTS.json', outputs)
    spent = sum(read(sender/'public/responses'/(x+'.json'))['charged_upper_usd'] for x in attempts)
    put(run/'public/SUMMARY.json', dict(status='ENGINEERING_FAILURE_STOP',
        original_frozen_request_bodies=25, actual_formal_inference_requests=5,
        technical_smoke_requests=1, unsent_formal_requests=20,
        B01_parseable=sum(x.get('decision_parseable', False) for x in outputs),
        B01_evidence_usable=sum(x.get('evidence_usable', False) for x in outputs),
        scientific_score='UNSCORABLE_PROTOCOL_PRE_HISTORY_LINEAGE',
        peak_rate_upper_usd=spent, cap_usd=3.0,
        no_semantic_retry=True, no_GT_before_partial_seal=True,
        score_key_sha256=sha(key_path), b0_source_sha256=sha(b0_source),
        request_seal_sha256=sha(sender/'public/REQUESTS_SEALED.json'), partial_response_seal_sha256=sha(seal_path),
        VLM_event_history_value='INCONCLUSIVE', depth_increment='INCONCLUSIVE',
        VLM_necessity='NOT_TESTED_FULL_SAME_INFORMATION_NUMERIC_BASELINE_MISSING'))
    print(json.dumps(dict(status='ENGINEERING_FAILURE_STOP', requests=6, spent=spent)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--b0', type=Path, required=True)
    args = parser.parse_args()
    main(args.run, args.b0)
