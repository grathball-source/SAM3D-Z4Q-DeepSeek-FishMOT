"""Independent explanation of the stopped v5 depth-quality contract failure."""
import argparse
import json
from pathlib import Path

REQUIRED=('depth_sensor_available','depth_synchronized','depth_core_n','depth_core_mad',
          'depth_whole_n','depth_whole_mad','depth_overlap_pixels','depth_quality')


def main(run):
    requests=json.loads((run/'REQUESTS_LOGICAL.json').read_text())['requests']
    rows=[]
    for req in requests:
        p=json.loads(req['text']);t=p.get('INTERACTION_TABLE')
        if t is None:continue
        missing=[x for x in REQUIRED if x not in t['columns']]
        rows.append(dict(attempt_id=req['attempt_id'],arm=req['arm'],anonymous_depth_rows=len(t['rows']),
                         missing_required_fields=missing,
                         source_contract='FAIL' if req['arm'] in ('H-D','H-D-REPEAT','H-D-PERMUTE') and missing else 'DEPTH_NOT_SENT_OR_PASS'))
    assert sum(x['source_contract']=='FAIL' for x in rows)==15
    out=run/'SOURCE_FAILURE_AUDIT.json';assert not out.exists()
    out.write_text(json.dumps(dict(status='SOURCE_CONTRACT_FAILURE_AFTER_SEAL',
        root_cause='verbose anonymous records and compact H-D table both omitted required depth quality; preflight compared H2D/HD symmetry but did not validate quality completeness',
        cases=rows),ensure_ascii=False,indent=2)+'\n')
    print('invalid H-D logical packets',15)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True)
    main(p.parse_args().run)
