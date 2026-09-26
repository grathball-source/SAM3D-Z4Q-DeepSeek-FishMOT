"""Final public evidence checks, independent of model scoring and GT."""
import argparse
import hashlib
import json
import re
from pathlib import Path


def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main(root):
    manifest=read(root/'REQUEST_MANIFEST.json');corrected=root/'corrected_unsent'
    plan=read(root/'REQUESTS_LOGICAL.json');new_plan=read(corrected/'REQUESTS_LOGICAL.json')
    req=read(root/'REQUESTS_SEALED.json');partial=read(root/'PARTIAL_RESPONSES_SEALED.json')
    assert len(plan['requests'])==len(new_plan['requests'])==len(manifest['schedule'])==25
    assert req['plan_sha256']==sha(root/'REQUESTS_LOGICAL.json')
    assert req['code_sha256']==sha(root/'frozen_v5/sender.py')
    assert partial['request_seal_sha256']==sha(root/'REQUESTS_SEALED.json')
    assert partial['call_ledger_sha256']==sha(root/'CALL_LEDGER.jsonl')
    assert [partial[k] for k in ('formal_returned','formal_http_unknown','formal_unsent')]==[7,1,17]
    assert not (root/'RESPONSES_SEALED.json').exists()
    assert read(corrected/'OFFLINE_REQUESTS_FROZEN.json')['actual_model_calls']==0
    assert read(root/'REPAIR_DIFF_AUDIT.json')['status']=='NO_CASE_REFERENCE_OR_IMAGE_CHANGE'
    assert read(root/'SOURCE_FAILURE_AUDIT.json')['status']=='SOURCE_CONTRACT_FAILURE_AFTER_SEAL'
    assert read(root/'TRIGGER_SCOPE_AUDIT.json')['status']=='PROXY_ONLY_ALL_FIVE'
    for record in partial['records']:
        p=root/'responses'/(record['attempt_id']+'.json')
        assert (p.is_file() and sha(p)==record['response_sha256']) if record['response_sha256'] else not p.exists()
    assert len(list(root.rglob('*.png')))==0
    checked=0
    for p in root.rglob('*'):
        if p.is_file() and p.suffix.lower() in ('.json','.jsonl','.md','.txt','.py','.sh'):
            text=p.read_text(encoding='utf-8',errors='replace')
            assert not re.search(r'file-api-[A-Za-z0-9_-]{8,}',text),p
            assert not re.search(r'sk-[A-Za-z0-9]{24,}',text),p
            checked+=1
    out=root/'FINAL_VERIFICATION.json';assert not out.exists()
    out.write_text(json.dumps(dict(status='PASS_PUBLIC_PARTIAL_SEAL_AND_PRIVACY',
        original_logical_requests=25,corrected_logical_requests_unsent=25,
        formal_returned=7,formal_http_unknown=1,formal_unsent=17,
        files_privacy_scanned=checked,no_private_png_in_repository=True,
        request_seal_sha256=sha(root/'REQUESTS_SEALED.json'),
        partial_response_seal_sha256=sha(root/'PARTIAL_RESPONSES_SEALED.json')),
        indent=2)+'\n')
    print('public verification pass',checked,'files scanned')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True)
    main(p.parse_args().root)
