"""Actual commit-to-publisher source contracts, before any reference reads."""
import guard
from common import *
from score import verify_publication_sources
from concurrent.futures import ThreadPoolExecutor


def main():
    proof=read(HERE/'PREFIX_CHECKS.json');assert proof['status']=='PASS'
    def check(item):
        name,record=item
        public=Path(record['predictions']['path']).parent
        return name,verify_publication_sources(public)
    with ThreadPoolExecutor(max_workers=3) as pool:
        results=dict(pool.map(check,proof['checks'].items()))
    write_new(HERE/'REAL_PREFIX_SOURCE_CHECKS.json',dict(status='PASS',checks=results,
        GT_read=False,model_http=0,cost_usd=0,actual_test_sources={str(p):sha(p) for p in (
            HERE/'check_prefix_sources.py',HERE/'score.py',HERE/'common.py',HERE/'controller.py',HERE/'guard.py')}))
    print('PASS actual prefix source→candidate→commit→unique publisher contracts')


if __name__=='__main__':main()
