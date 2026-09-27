"""Poststop regression demonstrating the exact preflight gap without changing sent input."""
import argparse
import copy
import json
from pathlib import Path

from build import read, save


def stale(packet):
    return [(section,role,segment.get('anchor_frame'),segment['observations'][0]['source_frame'])
            for section,roles in (('PRE_HISTORY','AB'),('POST_HISTORY_TO_Q','XY'))
            for role in roles for segment in [packet[section][role]]
            if 'anchor_frame' in segment and segment['anchor_frame'] not in
                {o['source_frame'] for o in segment['observations']}]


def main(root):
    root=Path(root)
    requests=read(root/'public/REQUESTS_LOGICAL.json')['requests']
    failures=[]
    for request in requests:
        if request['arm']!='E':continue
        packet=json.loads(request['text']);actual=stale(packet)
        assert len(actual)==2 and {x[1] for x in actual}=={'X','Y'}
        failures.append(dict(case=request['case'],stale_role_count=len(actual)))
        fixture=copy.deepcopy(packet)
        for role in 'XY':fixture['POST_HISTORY_TO_Q'][role].pop('anchor_frame')
        assert not stale(fixture)
    assert len(failures)==5
    save(root/'public/POSTSTOP_REGRESSION.json',dict(status='FROZEN_INPUT_FAILS_ENDPOINT_ONLY',
        original_requests_unchanged=True,fixture='UNSENT_LOCAL_PROJECTION_ONLY',
        failed_E_requests=failures,stale_fields=10,
        correction='Remove anchor_frame from endpoint-only post segments in a separately frozen future run.'))
    print(dict(failed_E_requests=5,stale_fields=10,synthetic_correction_check='PASS'))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True)
    main(parser.parse_args().root)
