"""Check S0 response references against its own frozen request facts."""
import json
import re
from pathlib import Path

from prepare import HERE, SEGMENTS, write_new


def audit():
    records=[]
    for name in SEGMENTS:
        public=HERE/'run'/name/'public'
        for response_path in sorted((public/'responses').glob('*S0.json')):
            response=json.loads(response_path.read_text(encoding='utf-8'))
            request=json.loads((public/'requests'/response_path.name).read_text(encoding='utf-8'))
            content=json.loads(response['content'])
            refs=content.get('evidence_refs',[])
            cutoff=int(request['user'].split('当前证据截止：',1)[1].split('\n',1)[0])
            checks=[]
            for fact in refs:
                match=re.fullmatch(r'F(\d+):O\d+',fact) if isinstance(fact,str) else None
                checks.append(dict(fact_id=fact,in_request=fact in request['user'],
                                   at_or_before_cutoff=bool(match and int(match.group(1))<=cutoff)))
            records.append(dict(segment=name,tag=response['tag'],choice=response['choice'],
                                cutoff=cutoff,references=checks))
    count=sum(len(item['references']) for item in records)
    valid=sum(x['in_request'] and x['at_or_before_cutoff'] for item in records
              for x in item['references'])
    result=dict(status='POSTSEAL_RESPONSE_REFERENCE_AUDIT',split_responses=len(records),
                references=count,valid_references=valid,invalid_references=count-valid,
                records=records)
    write_new(HERE/'run/RESPONSE_REFERENCE_AUDIT.json',result)
    print(json.dumps(dict(split_responses=len(records),references=count,valid=valid)))


if __name__=='__main__':
    audit()
