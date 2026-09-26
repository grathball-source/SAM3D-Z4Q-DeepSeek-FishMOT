"""Inventory committed public artifacts and restricted copies without leaking them."""
import argparse
import hashlib
import json
import re
from pathlib import Path


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()


def main(root):
    assert root.is_dir()
    public=[]
    for p in sorted(root.rglob('*')):
        if not p.is_file() or p.name=='ARTIFACT_MANIFEST.json' or '__pycache__' in p.parts:continue
        if p.suffix.lower() in ('.json','.jsonl','.md','.txt','.py','.sh'):
            content=p.read_text(encoding='utf-8',errors='replace')
            assert not re.search(r'file-api-[A-Za-z0-9_-]{8,}',content),p
            assert not re.search(r'sk-[A-Za-z0-9]{24,}',content),p
        public.append(dict(path=str(p.resolve()),repository_relative=str(p.relative_to(root)),
                           bytes=p.stat().st_size,sha256=sha(p)))
    preview=Path('C:/Users/19430/AppData/Local/Temp/ehr1r_b01_visual_20260926')
    local_previews=[dict(path=str(p),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(preview.glob('*.png'))] if preview.is_dir() else []
    remote=json.loads((root/'RESTRICTED_INVENTORY.json').read_text())['records']
    artifact=dict(status='PUBLIC_FILES_HASHED_RESTRICTED_FILES_OFF_GIT',
        public_count=len(public),public=public,restricted_count=len(remote),
        restricted_inventory='RESTRICTED_INVENTORY.json',local_private_previews=local_previews,
        reproduction='Use the documented AO1/M2 observation, assignment and raw HDF5 source hashes on the authorized host. Rebuild v5 only for historical audit; corrected_unsent is the unsent quality-complete package. New inference requires a fresh authorization and fresh response seal.')
    out=root/'ARTIFACT_MANIFEST.json';assert not out.exists(),out
    out.write_text(json.dumps(artifact,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print('public',len(public),'restricted',len(remote),'local previews',len(local_previews))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True)
    main(p.parse_args().root)
