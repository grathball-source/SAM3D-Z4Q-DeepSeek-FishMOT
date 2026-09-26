"""Seal interruption without treating unknown HTTP or unsent requests as answers."""
import argparse
import hashlib
import json
from datetime import datetime,timezone
from pathlib import Path


def sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for block in iter(lambda:f.read(1048576),b''):h.update(block)
    return h.hexdigest()


def put(path,value):
    path=Path(path);assert not path.exists(),path
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def main(run):
    sender=run/'sender'
    assert not (sender/'public/RESPONSES_SEALED.json').exists()
    assert (sender/'public/REQUESTS_SEALED.json').is_file()
    plan=json.loads((sender/'PLAN.json').read_text())
    gate=json.loads((sender/'SENDER_GATE.json').read_text())
    reserve={x['attempt_id']:x['reserve_usd'] for x in gate['request_budget']}
    ledger=[json.loads(line) for line in (sender/'public/CALL_LEDGER.jsonl').read_text().splitlines()]
    starts={x['attempt_id']:x for x in ledger if x['phase']=='START'}
    ends={x['attempt_id']:x for x in ledger if x['phase']=='END'}
    unknown=set(starts)-set(ends)
    assert unknown=={'B02-H-D'},unknown
    assert starts.keys()>=ends.keys()
    records=[]
    for req in plan['requests']:
        a=req['attempt_id'];response=sender/'public/responses'/(a+'.json')
        if a in ends:
            assert response.is_file() and ends[a]['transport_valid']
            status='RETURNED_UNSCORED_SOURCE_CONTRACT_FAILURE'
        elif a in unknown:
            assert not response.exists();status='HTTP_OUTCOME_UNKNOWN_INTERRUPTED'
        else:
            assert a not in starts and not response.exists();status='UNSENT'
        records.append(dict(attempt_id=a,case=req['case'],arm=req['arm'],status=status,
                            response_sha256=sha(response) if response.exists() else None,
                            charged_or_reserved_upper_usd=ends[a]['charged_upper_usd'] if a in ends else reserve[a] if a in unknown else 0))
    assert [sum(x['status']==s for x in records) for s in
        ('RETURNED_UNSCORED_SOURCE_CONTRACT_FAILURE','HTTP_OUTCOME_UNKNOWN_INTERRUPTED','UNSENT')]==[7,1,17]
    smoke=sender/'public/responses/S001.json';assert smoke.is_file()
    charged=json.loads(smoke.read_text())['charged_upper_usd']+sum(x['charged_or_reserved_upper_usd'] for x in records)
    seal=dict(status='PARTIAL_SOURCE_CONTRACT_FAILURE_STOP',at=datetime.now(timezone.utc).isoformat(),
        reason='H-D anonymous event depths lack sensor_available, synchronized, core_n and core_MAD in model-visible table',
        request_seal_sha256=sha(sender/'public/REQUESTS_SEALED.json'),
        call_ledger_sha256=sha(sender/'public/CALL_LEDGER.jsonl'),
        smoke_response_sha256=sha(smoke),formal_returned=7,formal_http_unknown=1,formal_unsent=17,
        inference_http_attempts_upper=9,charged_or_reserved_peak_upper_usd=charged,
        records=records)
    put(run/'public/PARTIAL_RESPONSES_SEALED.json',seal)
    put(run/'public/ATTEMPT_RESULTS.json',records)
    print(json.dumps({k:seal[k] for k in ('status','formal_returned','formal_http_unknown','formal_unsent','charged_or_reserved_peak_upper_usd')}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True)
    main(p.parse_args().run)
