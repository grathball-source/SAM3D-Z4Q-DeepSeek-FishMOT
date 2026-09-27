"""Hash unsent preparation drafts kept on the source host; publish only metadata."""
import argparse
import json
from pathlib import Path

from artifact import item


def main(parent,out):
    parent,out=Path(parent),Path(out)
    drafts=[]
    for name in ('run','run_c2','run_c3'):
        path=parent/name
        files=sorted(x for x in path.rglob('*') if x.is_file())
        records=[item(x) for x in files]
        drafts.append(dict(name=name,status='UNSENT_PREPARATION_DRAFT',path=str(path.resolve()),
            file_count=len(records),total_bytes=sum(x['bytes'] for x in records),files=records))
    assert not out.exists()
    out.write_text(json.dumps(dict(status='RESTRICTED_DRAFTS_OFF_GIT',drafts=drafts),
        indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print([(x['name'],x['file_count'],x['total_bytes']) for x in drafts])


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--parent',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True);args=parser.parse_args()
    main(args.parent,args.out)
