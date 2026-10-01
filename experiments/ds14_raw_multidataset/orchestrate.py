"""Independent segments, up to three single-thread local CPU processes."""
from common import *
from concurrent.futures import ThreadPoolExecutor
from execute import run
def main(mode,names=None):
    assert mode in ('prepare','run')
    with ThreadPoolExecutor(max_workers=3) as pool:
        results=list(pool.map(lambda n:run('guard.py',mode,n),names or SEGMENTS))
    assert all(r['exit_code']==0 for r in results),results
    if mode=='run':
        for name in SEGMENTS:
            p=RUN/name/'public';assert read(p/'RUN_SUMMARY.json')['frames']==SEGMENTS[name][1]-SEGMENTS[name][0]+1
            verify_item(artifact(p/'ACCESS.json'))
        write_new(RUN/'ALL_PREDICTIONS_SEALED.json',dict(status='ALL_TWO_BRANCHES_EIGHT_SEGMENTS_SEALED',
            frames=sum(b-a+1 for a,b in SEGMENTS.values()),arms=list(ARMS),
            seals={n:artifact(RUN/n/'public/PREDICTIONS_SEALED.json') for n in SEGMENTS},
            access_seals={n:artifact(RUN/n/'public/ACCESS.json') for n in SEGMENTS},new_model_http=0,cost_usd=0))
if __name__=='__main__':main(sys.argv[1],sys.argv[2:])
