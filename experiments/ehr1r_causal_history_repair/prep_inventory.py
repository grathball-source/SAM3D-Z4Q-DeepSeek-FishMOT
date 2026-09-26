"""Read-only inventory of superseded preparation versions, none sent."""
import argparse
import hashlib
import json
from pathlib import Path


def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()


def main(root,out):
    records=[]
    for v in range(1,5):
        run=root/f'run_v{v}'
        for p in sorted((run/'public').glob('*')):
            if p.is_file():records.append(dict(version=v,path=str(p),bytes=p.stat().st_size,sha256=sha(p)))
        plan=run/'sender/PLAN.json'
        if plan.is_file():records.append(dict(version=v,path=str(plan),bytes=plan.stat().st_size,sha256=sha(plan)))
    out=Path(out);assert not out.exists()
    out.write_text(json.dumps(dict(status='PREPARATION_ONLY_NO_MODEL_CALLS',records=records),indent=2)+'\n')
    print('prep files',len(records))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();main(a.root,a.out)
