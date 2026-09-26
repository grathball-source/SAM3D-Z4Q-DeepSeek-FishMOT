"""Source contract and paired-input regressions; no provider calls or GT."""
import argparse
import copy
import json
from pathlib import Path

from contract import validate_segment
from numeric import compare
from prepare import fit, condition
from audit import validate_event_depth_table


def fake(f, risk=False):
    return dict(id=1,area=10,neighbors=[2] if risk else [],box=[f,0,f+2,2])


def packet_segment(frames):
    return dict(observations=[dict(source_frame=f,source_time_seconds=f/10,area_px=10,
                                    neighbor_count=0) for f in frames])


def run_tests(run):
    rows={f:dict(frame=f,time=f/10,observations=[fake(f,f==3)]) for f in range(1,7)}
    assert any(x.startswith('CONTACT_RISK') for x in validate_segment(packet_segment([1,2,3]),rows,1,2))
    tampered=packet_segment([1,2,3]);tampered['observations'][-1]['neighbor_count']=0
    assert any(x.startswith('CONTACT_RISK') for x in validate_segment(tampered,rows,1,2))
    assert 'GAP_F3' in validate_segment(packet_segment([1,2,4,5]),rows,1,5)
    assert any(x.startswith('CONTACT_RISK') for x in validate_segment(packet_segment([2,3,4]),rows,1,4))
    assert validate_segment(packet_segment([4,5,6]),rows,1,6)==[]
    version_rows=copy.deepcopy(rows)
    version_rows[5]['observations'][0]['generation']=2
    version_rows[6]['observations'][0]['generation']=3
    assert any(x.startswith('IDENTITY_VERSION_CHANGE') for x in validate_segment(packet_segment([5,6]),version_rows,1,6))
    time_rows=copy.deepcopy(rows);time_rows[6]['time']=2.0
    assert any(x.startswith('TIME_DISCONTINUITY') for x in validate_segment(packet_segment([5,6]),time_rows,1,6))
    two=[dict(fact_id=f'F{i}',source_time_seconds=i/10,bbox_center_px=[i,0]) for i in (4,5)]
    assert fit('T',two)['epistemic_type']=='UNKNOWN'
    episodes=json.loads((run/'public/EPISODE_FACTS.json').read_text())
    for p in episodes:
        assert condition(p,'H-D')==condition(p,'H-D-REPEAT')
        h=condition(p,'H-D');perm=condition(p,'H-D-PERMUTE')
        validate_event_depth_table(h['INTERACTION_TABLE'],p['INTERACTION_OBSERVATIONS'])
        broken=copy.deepcopy(h['INTERACTION_TABLE'])
        broken['columns'].remove('depth_core_mad')
        try:validate_event_depth_table(broken,p['INTERACTION_OBSERVATIONS'])
        except AssertionError:pass
        else:raise AssertionError('missing event depth quality passed')
        assert [x['mapping'] for x in perm['hypotheses']]==[x['mapping'] for x in reversed(h['hypotheses'])]
        assert all(x['source_frame']<=p['q_frame'] for part in ('PRE_HISTORY','POST_HISTORY_TO_Q')
                   for s in p[part].values() for x in s['observations'])
    b05=episodes[-1];roi=b05['IMAGE_INDEX'][0]['roi_full_mask_xyxy']
    baseline=compare(b05,roi,False);depth=compare(b05,roi,True)
    assert depth['depth_mode']=='DEPTH_UNAVAILABLE_FALLBACK'
    assert depth['candidate_costs']==baseline['candidate_costs']
    # A missing single edge cannot make that candidate cheaper.
    b02=copy.deepcopy(episodes[1]);roi=b02['IMAGE_INDEX'][0]['roi_full_mask_xyxy']
    b02['POST_HISTORY_TO_Q']['X']['observations'][0]['depth']={'epistemic_type':'UNKNOWN'}
    a=compare(b02,roi,False);b=compare(b02,roi,True)
    assert b['depth_mode']=='DEPTH_UNAVAILABLE_FALLBACK' and a['candidate_costs']==b['candidate_costs']
    assert episodes[0]['PRE_HISTORY']['A']['velocity']['epistemic_type']=='UNKNOWN'
    assert episodes[-1]['POST_HISTORY_TO_Q']['Y']['velocity']['epistemic_type']=='UNKNOWN'
    assert all('old_to_new_reference' not in condition(p,'E') for p in episodes)
    print('source, fragment, paired-condition and symmetric-depth regressions passed')


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--run',type=Path,required=True)
    run_tests(ap.parse_args().run)
