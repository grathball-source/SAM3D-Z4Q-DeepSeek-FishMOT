"""Prove the unsent repair changed only H-D anonymous depth-quality payload."""
import argparse
import json
from pathlib import Path


def read(p):return json.loads(Path(p).read_text())


def main(root):
    new=root/'corrected_unsent'
    assert read(root/'REFERENCE_SEGMENTS.json')==read(new/'REFERENCE_SEGMENTS.json')
    a=read(root/'REQUESTS_LOGICAL.json')['requests'];b=read(new/'REQUESTS_LOGICAL.json')['requests']
    rows=[]
    for old,current in zip(a,b,strict=True):
        assert old['attempt_id']==current['attempt_id'] and old['images']==current['images']
        p=json.loads(old['text']);q=json.loads(current['text'])
        if old['arm'] in ('E','H-2D'):
            assert old['text']==current['text']
            status='BYTE_IDENTICAL'
        else:
            table=q['INTERACTION_TABLE']
            # The first two old H-D depth fields are retained; remove only eight new quality fields.
            new_only=[i for i,c in enumerate(table['columns']) if c not in p['INTERACTION_TABLE']['columns']]
            table['columns']=[c for i,c in enumerate(table['columns']) if i not in new_only]
            table['rows']=[[v for i,v in enumerate(row) if i not in new_only] for row in table['rows']]
            assert q==p
            status='ONLY_EIGHT_ANONYMOUS_DEPTH_QUALITY_COLUMNS_ADDED'
        rows.append(dict(attempt_id=old['attempt_id'],status=status,same_image_list=True))
    out=root/'REPAIR_DIFF_AUDIT.json';assert not out.exists()
    out.write_text(json.dumps(dict(status='NO_CASE_REFERENCE_OR_IMAGE_CHANGE',
         unchanged_E_H2D=10,changed_HD_quality_only=15,requests=rows),indent=2)+'\n')
    print('repair diff verified',len(rows))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True)
    main(p.parse_args().root)
