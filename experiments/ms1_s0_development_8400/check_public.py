"""Fail if staged artifacts expose restricted files or common key/pixel forms."""
import re
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
patterns=[re.compile(rb'sk-[A-Za-z0-9_-]{16,}'),re.compile(rb'data:image/'),
          re.compile(rb'"file_id"\s*:'),re.compile(rb'"api_key"\s*:\s*"[^"]+"')]


def main():
    names=subprocess.check_output(['git','diff','--cached','--name-only'],cwd=ROOT).decode().splitlines()
    total=0
    for name in names:
        assert not any(part in ('private_source','private_api') for part in Path(name).parts),name
        assert Path(name).suffix.lower() not in ('.png','.jpg','.jpeg','.npy','.npz','.pt','.pth'),name
        content=subprocess.check_output(['git','show',':'+name],cwd=ROOT)
        total+=len(content)
        if name!=str(Path(__file__).relative_to(ROOT)).replace('\\','/'):
            assert not any(pattern.search(content) for pattern in patterns),name
    print(dict(status='PASS',staged_files=len(names),staged_bytes=total,
               restricted_files=0,credential_or_embedded_pixel_patterns=0))


if __name__=='__main__':
    main()
