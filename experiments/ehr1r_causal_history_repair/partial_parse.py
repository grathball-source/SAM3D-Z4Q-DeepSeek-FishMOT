"""Post-partial-seal raw choices and citation legality; never opens GT."""
import argparse
import json
from pathlib import Path

from score import parse,sha,read,save


def main(run):
    seal=read(run/'PARTIAL_RESPONSES_SEALED.json')
    assert seal['status']=='PARTIAL_SOURCE_CONTRACT_FAILURE_STOP'
    assert seal['request_seal_sha256']==sha(run/'REQUESTS_SEALED.json')
    assert seal['call_ledger_sha256']==sha(run/'CALL_LEDGER.jsonl')
    logical={x['attempt_id']:x for x in read(run/'REQUESTS_LOGICAL.json')['requests']}
    rows=[]
    for record in seal['records']:
        a=record['attempt_id'];req=logical[a]
        if record['response_sha256']:
            response=read(run/'responses'/(a+'.json'))
            assert sha(run/'responses'/(a+'.json'))==record['response_sha256']
            parsed=parse(response.get('content'),json.loads(req['text']))
            rows.append(dict(attempt_id=a,case=req['case'],arm=req['arm'],status='RETURNED_UNSCORED',
                raw_choice=parsed['raw_choice'],parseable=parsed['parseable'],citation_legal=parsed['usable'],
                evidence_errors=parsed['errors'],finish_reason=response['finish_reason'],
                usage=response['usage'],latency_seconds=response['latency_seconds'],
                charge_upper_usd=response['charged_upper_usd']))
        else:
            rows.append(dict(attempt_id=a,case=req['case'],arm=req['arm'],status=record['status'],
                             raw_choice=None,parseable=None,citation_legal=None,evidence_errors=[]))
    save(run/'RAW_RESPONSE_AUDIT.json',rows)
    print('returned',sum(x['status']=='RETURNED_UNSCORED' for x in rows),
          'parseable',sum(x['parseable'] is True for x in rows),
          'citation_legal',sum(x['citation_legal'] is True for x in rows))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True)
    main(p.parse_args().run)
