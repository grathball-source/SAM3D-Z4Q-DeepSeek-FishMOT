"""Inventory the public S0-P deliverable before Git sync."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    target=HERE/'ARTIFACT_MANIFEST.json'
    files=[p for p in HERE.rglob('*') if p.is_file() and
           not any(part in ('private_source','private_api','__pycache__') for part in p.parts) and
           p.name not in ('ARTIFACT_MANIFEST.json','SYNC_VERIFICATION.json')]
    files.extend((ROOT/'research/HANDOFF.md',ROOT/'experiments/ms1_s0_development_8400/README.md'))
    records={str(p.relative_to(ROOT)).replace('\\','/'):dict(bytes=p.stat().st_size,sha256=sha(p))
             for p in sorted(files)}
    with target.open('w',encoding='utf-8') as handle:
        json.dump(dict(status='PUBLIC_DELIVERABLE_PRE_GIT_SYNC',files=records,
                       count=len(records),restricted_content_excluded=True),
                  handle,ensure_ascii=False,indent=2)
        handle.write('\n')
    print('PUBLIC_FILES',len(records))


if __name__=='__main__':
    main()
