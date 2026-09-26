"""Read-only inventory of current-run restricted files; never opens content as text."""
import argparse
import hashlib
import json
from pathlib import Path


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1048576),b''):h.update(block)
    return h.hexdigest()


def main(root,out):
    assert root.resolve()==Path('/home/xiongxiong/ehr1r_causal_history_20260926').resolve()
    records=[]
    for run in sorted(root.glob('run_v*')):
        if not run.is_dir():continue
        for path in sorted((run/'sender').rglob('*')):
            if not path.is_file():continue
            private=('media' in path.parts or 'private' in path.parts)
            if not private:continue
            records.append(dict(path=str(path),bytes=path.stat().st_size,sha256=sha(path),
                                class_='restricted_pixels_or_provider_wire'))
    out=Path(out);assert not out.exists()
    out.write_text(json.dumps(dict(status='RESTRICTED_FILES_OFF_GIT',records=records,
             reproduction='Read source-host paths under original account; rerun prepare/audit with documented source streams. New API calls require separate authorization.'),
             ensure_ascii=False,indent=2)+'\n')
    print('restricted files',len(records),'bytes',sum(x['bytes'] for x in records))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();main(a.root,a.out)
