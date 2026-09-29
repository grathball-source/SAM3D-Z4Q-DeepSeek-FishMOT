"""Hash restricted dependencies and new private artifacts; publish no contents."""
import json
from pathlib import Path

from verify import HERE, FEED, SEGMENTS, digest


def item(path,kind):
    path=Path(path).resolve(strict=True)
    return dict(path=str(path),bytes=path.stat().st_size,sha256=digest(path),kind=kind)


def main():
    run=HERE/'run'
    assert (run/'METRICS.json').is_file() and (run/'VERIFICATION.json').is_file()
    source={}
    for name in SEGMENTS:
        parent=FEED/'private'/name
        source[name]=[item(parent/f'{kind}.jsonl.gz','REUSED_SOURCE_OLD_DERIVED')
                      for kind in ('observations','profiles','assignments')]
        source[name].extend([item(parent/'SOURCE_MANIFEST.json','SOURCE_MANIFEST'),
                             item(parent/'SCAN_MANIFEST.json','PREDICTION_ONLY_SCAN'),
                             item(parent/'scan_v4.json','PREDICTION_ONLY_SCAN')])
    base=HERE.parent/'b0_same_source_regression_repair/public/RESTRICTED_INVENTORY.json'
    restricted={}
    for name in SEGMENTS:
        private=[]
        for folder in ('private_api','private_source'):
            target=run/name/folder
            if target.exists():
                for path in sorted(target.rglob('*')):
                    if path.is_file():
                        private.append(item(path,'PROVIDER_FILE_ID_OR_RAW_RESPONSE' if folder=='private_api'
                                             else 'MASK_GEOMETRY_PNG'))
        restricted[name]=private
    preflight=[]
    for name in SEGMENTS:
        target=HERE/'preflight'/name/'private_source'
        if target.exists():
            preflight.extend(item(path,'PREFLIGHT_MASK_GEOMETRY_PNG')
                             for path in sorted(target.rglob('*')) if path.is_file())
    result=dict(status='HASHED_PATHS_ONLY_NO_PRIVATE_CONTENT',
        source_old=source,prior_source_inventory=item(base,'PRIOR_SOURCE_AND_REFERENCE_INVENTORY'),
        new_private_artifacts=restricted,preflight_private_artifacts=preflight,
        source_manifest_sha256={name:json.loads((run/name/'public/FREEZE.json').read_text(encoding='utf-8'))
                                ['source_manifest_sha256'] for name in SEGMENTS},
        reproduction='Use the listed exact bytes/hashes and SOURCE_OLD scanner in a fresh output directory. Execute test_ne.py, replay.py preflight/real, verify.py, score.py run, postseal.py and visualize.py in that order; real requires separate authorized official DeepSeek credentials. Never use v3 depth or old responses.')
    target=HERE/'RESTRICTED_INVENTORY.json'
    assert not target.exists()
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(source_files=sum(map(len,source.values())),
                          private_files=sum(map(len,restricted.values())),
                          preflight_files=len(preflight))))


if __name__=='__main__':
    main()
