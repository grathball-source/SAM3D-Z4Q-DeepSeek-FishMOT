"""Hash public deliverables and restricted run artifacts without publishing their contents."""
import argparse
import hashlib
import json
from pathlib import Path


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as fh:
        for block in iter(lambda:fh.read(1<<20),b''):h.update(block)
    return h.hexdigest()


def item(path,relative=None):
    return dict(path=str(path.resolve()),repository_relative=relative,
                bytes=path.stat().st_size,sha256=digest(path))


def restricted(run,out):
    run=Path(run);selected=[]
    for folder in ('send/media','send/bodies','send/raw','send/errors','private'):
        base=run/folder
        if base.exists():selected.extend(x for x in base.rglob('*') if x.is_file())
    for name in ('send/UPLOAD_LEDGER.jsonl','send/BODY_RECORDS.json'):
        path=run/name
        if path.exists():selected.append(path)
    unique=sorted(set(selected))
    records=[item(x) for x in unique]
    value=dict(status='RESTRICTED_OFF_GIT',run=str(run.resolve()),file_count=len(records),
        total_bytes=sum(x['bytes'] for x in records),files=records,
        reproduction=('Use this run with its unchanged v6 corrected_unsent source, the M2 private token ledger, '
          'the original observation/depth feature streams, and the public frozen code. '
          'Provider IDs and raw wire are confined to this restricted tree; no key was saved.'))
    out=Path(out);assert not out.exists();out.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')
    print(dict(status=value['status'],files=value['file_count'],bytes=value['total_bytes']))


def public(root,out):
    root=Path(root);out=Path(out)
    files=sorted(x for x in root.rglob('*') if x.is_file() and x!=out
                 and not any(p in ('private','send','media','__pycache__','.git') for p in x.parts)
                 and x.suffix!='.pyc')
    records=[item(x,str(x.relative_to(root))) for x in files]
    value=dict(status='PUBLIC_FILES_HASHED_RESTRICTED_FILES_OFF_GIT',
        public_count=len(records),public=records)
    assert not out.exists();out.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')
    print(dict(status=value['status'],files=len(records)))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=('restricted','public'))
    parser.add_argument('--root',type=Path,required=True);parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();globals()[args.mode](args.root,args.out)
