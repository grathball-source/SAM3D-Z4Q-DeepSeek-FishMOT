"""Real source prefixes: old output equivalence, mask conservation and current publication."""
from common import *
from runner import run_segment


def main():
    checks={}
    for name in ('fishsa_development_8400','feeding_001201_001906','L3'):
        output=HERE/'slice'/name
        assert not output.exists(),output
        run_segment(name,output,stop_at=50)
        current=list(rows(output/name/'public/predictions.jsonl.gz'))
        old=rows(DS14/'run'/name/'public/predictions.jsonl.gz')
        for actual,previous in zip(current,old):
            for arm in ('SAM3_NATIVE','R12_RAW'):assert actual['variants'][arm]==previous['variants'][arm]
            keys=[x['mask'] for x in actual['variants']['SAM3_NATIVE']]
            for arm in ARMS:
                objects=actual['variants'][arm]
                assert [x['mask'] for x in objects]==keys
                assert len({x['id'] for x in objects})==len(keys)
        assert len(current)==50
        checks[name]=dict(frames=50,R12_and_native_exact=True,all_five_arms_masks_retained=True,
            observed_group_events={a:len(v) for a,v in read(output/name/'public/EVENTS.json').items()},
            prediction=artifact(output/name/'public/predictions.jsonl.gz'))
    write_new(HERE/'PREFIX_CHECKS.json',dict(status='PASS',checks=checks,GT_read=False,model_http=0))
    print('PASS:150 real prefix frames, five branches, old R12/native exact, masks and bijections retained.')

if __name__=='__main__':main()
