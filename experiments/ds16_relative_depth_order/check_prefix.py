"""Actual raw prefixes, causal q and source/public identity conservation."""
from common import *
from runner import run_segment

def main():
    checks={}
    for name in ('fishsa_development_8400','feeding_001201_001906','L3'):
        output=HERE/'slice'/name
        assert not output.exists()
        run_segment(name,output,stop_at=50)
        current=list(rows(output/name/'public/predictions.jsonl.gz'))
        for actual,previous in zip(current,rows(DS15/'run'/name/'public/predictions.jsonl.gz')):
            for arm in ('SAM3_NATIVE','Z4Q_FROZEN'):
                assert actual['variants'][arm]==previous['variants'][arm],(name,actual['frame'],arm)
            masks=[x['mask'] for x in actual['variants']['SAM3_NATIVE']]
            for arm in ARMS:
                assert [x['mask'] for x in actual['variants'][arm]]==masks
                assert len({x['id'] for x in actual['variants'][arm]})==len(masks)
        assert len(current)==50
        for event_rows in read(output/name/'public/EVENTS.json').values():
            for event in event_rows:
                if event['q'] is not None:
                    assert event['evidence_cutoff_frame']==event['q']
                    assert all(x['frame']==event['q'] for x in event['post_first_observations'].values())
        checks[name]=dict(frames=50,native_and_original_Z4Q_exact=True,all_masks_and_bijections_retained=True,
            events=read(output/name/'public/EVENTS.json'),prediction=artifact(output/name/'public/predictions.jsonl.gz'))
    write_new(HERE/'PREFIX_CHECKS.json',dict(status='PASS',checks=checks,GT_read=False,model_http=0))
    print('PASS150 actual raw prefix frames and six branch publication contracts')

if __name__=='__main__':main()
