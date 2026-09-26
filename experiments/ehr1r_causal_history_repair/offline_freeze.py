"""Seal corrected logical requests as unsent; never creates provider bodies."""
import argparse
import hashlib
import json
from pathlib import Path


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main(run):
    plan=json.loads((run/'REQUESTS_LOGICAL.json').read_text())
    gate=json.loads((run/'SENDER_GATE.json').read_text())
    assert gate['status']=='PASS' and gate['request_count']==25
    assert gate['plan_sha256']==sha(run/'REQUESTS_LOGICAL.json')
    records=[dict(attempt_id=x['attempt_id'],text_sha256=hashlib.sha256(x['text'].encode()).hexdigest(),
                  image_sha256=[im['sha256'] for im in x['images']],status='UNSENT') for x in plan['requests']]
    assert len(records)==25
    out=run/'OFFLINE_REQUESTS_FROZEN.json';assert not out.exists()
    out.write_text(json.dumps(dict(status='CORRECTED_LOGICAL_REQUESTS_ONLY_NO_INFERENCE',
      reason='same EHR-1R authorized request ceiling already consumed by interrupted v5 batch; no response reuse',
      plan_sha256=sha(run/'REQUESTS_LOGICAL.json'),gate_sha256=sha(run/'SENDER_GATE.json'),
      reserve_usd=gate['total_reserve_usd'],request_count=25,actual_model_calls=0,
      records=records),indent=2,ensure_ascii=False)+'\n')
    print('corrected logical requests frozen unsent',25)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True)
    main(p.parse_args().run)
