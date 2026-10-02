"""Three local single-thread prediction jobs; all seals precede reference reads."""
from common import *
from concurrent.futures import ThreadPoolExecutor
from execute import run


def main():
    with ThreadPoolExecutor(max_workers=3) as pool:
        results=list(pool.map(lambda name:run('guard.py','run',name),SEGMENTS))
    assert all(r['exit_code']==0 for r in results),results
    for name,(a,b) in SEGMENTS.items():
        assert read(RUN/name/'public/RUN_SUMMARY.json')['frames']==b-a+1
    write_new(RUN/'ALL_PREDICTIONS_SEALED.json',dict(status='ALL_PREDICTIONS_AND_ACCESS_SEALED',
        frames=20098,arms=list(ARMS),seals={n:artifact(RUN/n/'public/PREDICTIONS_SEALED.json') for n in SEGMENTS},
        access_seals={n:artifact(RUN/n/'public/ACCESS.json') for n in SEGMENTS},model_http=0,cost_usd=0))
    print('ALL SIX ARMS20098 PREDICTIONS AND ACCESS SEALED')

if __name__=='__main__':main()
