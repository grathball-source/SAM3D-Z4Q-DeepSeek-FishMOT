"""Focused pending isolation checks, with immutable test-source hashes."""
from common import *
import argparse
import unittest


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',default='CHECKS.json');args=parser.parse_args()
    target=HERE/args.output
    assert target.parent.resolve()==HERE.resolve() and not target.exists()
    sources=(HERE/'checks.py',HERE/'test_pending_isolation.py',HERE/'controller.py',
        HERE/'common.py',DS19/'controller.py',DS19/'test_event_return.py',
        DS18/'controller.py',DS18/'test_controller.py',DS18/'mixed_depth.py')
    loaded={str(p):sha(p) for p in sources}
    test=module('ds20_pending_isolation_checks',HERE/'test_pending_isolation.py')
    suite=unittest.defaultTestLoader.loadTestsFromModule(test)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    stable=all(sha(p)==loaded[str(p)] for p in sources)
    write_new(target,dict(status='PASS' if result.wasSuccessful() and stable else 'FAIL',
        tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),
        failure_details=[dict(test=str(case),traceback=detail) for case,detail in result.failures+result.errors],
        GT_read=False,model_http=0,cost_usd=0,source_stable_during_tests=stable,actual_test_sources=loaded))
    assert result.wasSuccessful() and stable


if __name__=='__main__':main()
