"""Record hashes for local restricted inputs and outputs without their contents."""
import hashlib
import json
from pathlib import Path

from postseal_event import MATCHES
from replay_v6 import ARCHIVED, PROFILES
from score import GT
from source_scan import ASSIGN, OBS

HERE=Path(__file__).resolve().parent


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda:handle.read(1<<20),b''):
            h.update(block)
    return h.hexdigest()


def main():
    originals=[OBS,ASSIGN,PROFILES,ARCHIVED,GT,MATCHES]
    restricted=sorted(p for p in HERE.rglob('*') if p.is_file() and
                      any(part in ('private_source','private_api') for part in p.parts))
    files=[]
    for path in originals+restricted:
        files.append(dict(path=str(path.resolve()),bytes=path.stat().st_size,
                          sha256=digest(path),kind='external_input' if path in originals else
                          'local_restricted_artifact'))
    result=dict(status='LOCAL_RESTRICTED_ARTIFACT_INVENTORY',files=files,
                count=len(files),private_pixels_or_gt_raster_committed=False,
                reproduction='Use the listed exact-hash local inputs and the commands in README.md; private mask images and GT stay local.')
    output=HERE/'RESTRICTED_INVENTORY.json'
    with output.open('x',encoding='utf-8') as handle:
        json.dump(result,handle,ensure_ascii=False,indent=2)
        handle.write('\n')
    print(json.dumps(dict(count=len(files),output=str(output)),ensure_ascii=False))


if __name__=='__main__':
    main()
