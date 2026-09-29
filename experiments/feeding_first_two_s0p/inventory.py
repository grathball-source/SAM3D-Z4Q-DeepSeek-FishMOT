"""List restricted reproduction inputs by path, byte count and SHA, never content."""
import json
from pathlib import Path

from prepare import DATA, HERE, SEGMENTS, digest, write_new


def inventory():
    entries=[]
    for name in SEGMENTS:
        for base,role in ((HERE/'private'/name,'derived_source_and_masks'),
                          (HERE/'run'/name/'private_api','provider_wire_and_ids'),
                          (HERE/'run'/name/'private_source','geometry_images')):
            if base.exists():
                for path in sorted(base.rglob('*')):
                    if path.is_file():
                        entries.append(dict(segment=name,role=role,path=str(path.resolve()),
                                            bytes=path.stat().st_size,sha256=digest(path)))
    scored=json.loads((HERE/'run/METRICS.json').read_text(encoding='utf-8'))
    labels=DATA/'labels_640x360'
    for name,(start,stop) in SEGMENTS.items():
        entries.append(dict(segment=name,role='edited_reference_polygon_directory',
                            path=str(labels.resolve()),files=stop-start+1,
                            ordered_file_bytes_sha256=scored['reference'][name]['ordered_file_bytes_sha256'],
                            reproduction='read 000000-style JSON for original frame range in order'))
    result=dict(status='RESTRICTED_LOCAL_ONLY',entries=entries,
                reproduction=('Use exact source files and source manifest SHA values, run prepare.py, '
                              'scan.py, replay.py real, then score.py run and postseal audits. '
                              'Reproduction of model choices requires a new paid API batch; '
                              'sealed responses are not reused as fresh model evidence.'),
                no_private_contents_published=True)
    write_new(HERE/'run/RESTRICTED_INVENTORY.json',result)
    print(json.dumps(dict(entries=len(entries),roles=sorted({x['role'] for x in entries})),ensure_ascii=False))


if __name__=='__main__':
    inventory()
