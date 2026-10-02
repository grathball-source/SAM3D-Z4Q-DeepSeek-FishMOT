"""All-frame read-only archive equivalence; no references or new predictions."""
from common import *

def main():
    assert read(RUN/'SCORE_PROVENANCE.json')['reference_opened_after_all_seals']
    result={}
    for name,(a,b) in SEGMENTS.items():
        old=DS16/'run'/name/'public';new=RUN/name/'public'
        assert sha(old/'predictions.jsonl.gz')==read(old/'PREDICTIONS_SEALED.json')['artifacts_sha256']['predictions.jsonl.gz']
        assert sha(new/'predictions.jsonl.gz')==read(new/'PREDICTIONS_SEALED.json')['artifacts_sha256']['predictions.jsonl.gz']
        count=0
        for count,(current,prior) in enumerate(zip(rows(new/'predictions.jsonl.gz'),rows(old/'predictions.jsonl.gz'),strict=True),1):
            assert current['frame']==prior['frame']==count
            assert current['global_frame']==prior['global_frame']==a+count-1
            assert current['time']==prior['time']
            assert current['variants']['DS16_ORDER']==prior['variants']['DEPTH_ORDER'],(name,count)
        assert count==b-a+1
        result[name]=dict(frames=count,status='EVERY_DS16_ORDER_MASK_PUBLIC_ID_TIME_EXACT',
            new_prediction=artifact(new/'predictions.jsonl.gz'),old_prediction=artifact(old/'predictions.jsonl.gz'))
    write_new(RUN/'DS16_PARITY.json',dict(status='PASS',frames=20098,segments=result,GT_read=False,new_predictions=0))
    print('DS16_ORDER full 20098 frame parity PASS')

if __name__=='__main__':main()
