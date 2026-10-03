"""Resolve actual source/cache/ledger/commit/publication for the real prefixes."""
import guard
from common import *
from score import verify_publication_sources
from concurrent.futures import ThreadPoolExecutor


def main():
    proof = read(HERE/'PREFIX_CHECKS.json')
    assert proof['status'] == 'PASS'
    sources = (HERE/'check_prefix_sources.py', HERE/'score.py', HERE/'runner.py',
               HERE/'common.py', HERE/'controller.py', HERE/'guard.py')
    before = {str(path): sha(path) for path in sources}
    def check(item):
        name, record = item
        verify_item(record['predictions'])
        verify_item(record['access'])
        verify_item(record['events'])
        verify_item(record['source_manifest'])
        public = Path(record['predictions']['path']).parent
        chain = verify_publication_sources(public)
        assert chain['frames'] == record['frames'] and chain['status'] == 'PASS'
        return name, chain
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = dict(pool.map(check, proof['checks'].items()))
    stable = all(sha(p) == before[str(p)] for p in sources)
    assert stable, 'publication checker code changed during execution'
    write_new(HERE/'REAL_PREFIX_SOURCE_CHECKS.json', dict(status='PASS', checks=results,
        GT_read=False, metrics_read=False, model_http=0, cost_usd=0,
        actual_test_sources=before, source_stable_during_tests=stable,
        prefix_record=artifact(HERE/'PREFIX_CHECKS.json')))
    print('PASS actual prefix source→candidate→commit→unique publisher contracts')


if __name__ == '__main__':
    main()
