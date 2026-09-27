"""Hash every deliverable public file, excluding the manifest itself."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def main():
    files = [p for p in HERE.rglob('*') if p.is_file() and
             not any(x in ('private_api', 'dry_run', '__pycache__') for x in p.parts) and
             p.name != 'ARTIFACT_MANIFEST.json']
    files += [ROOT/'AGENTS.md', ROOT/'research/HANDOFF.md']
    rows = []
    for path in sorted(files):
        with path.open('rb') as source:
            digest = hashlib.file_digest(source, 'sha256').hexdigest()
        rows.append(dict(path=path.relative_to(ROOT).as_posix(), bytes=path.stat().st_size,
                         sha256=digest))
    target = HERE/'ARTIFACT_MANIFEST.json'
    target.write_text(json.dumps(dict(status='PUBLIC_DELIVERY', files=rows,
        count=len(rows), total_bytes=sum(x['bytes'] for x in rows)), indent=2)+'\n', encoding='utf-8')
    print(len(rows), 'files', sum(x['bytes'] for x in rows), 'bytes')


if __name__ == '__main__':
    main()
