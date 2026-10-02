from common import *
import unittest

def main():
    suite=unittest.TestSuite()
    for name,path in [('ds18_mixed_test',HERE/'test_mixed_depth.py'),('ds18_state_test',HERE/'test_controller.py'),('ds18_reused_order_test',DS16/'test_order.py'),('ds18_streaming_test',HERE/'test_streaming.py')]:
        test_module=module(name,path)
        suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(test_module))
        if hasattr(test_module,'checks'):suite.addTest(unittest.FunctionTestCase(test_module.checks))
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    assert result.wasSuccessful()
    target=HERE/('CHECKS_R3.json' if '--final3' in sys.argv else 'CHECKS_R2.json' if '--final' in sys.argv else 'CHECKS.json')
    write_new(target,dict(status='PASS',tests=result.testsRun,failures=0,errors=0,GT_read=False,model_http=0,cost_usd=0,
        actual_test_sources={str(p):sha(p) for p in (HERE/'tests.py',HERE/'test_mixed_depth.py',HERE/'test_controller.py',HERE/'test_streaming.py',HERE/'controller.py',HERE/'mixed_depth.py')}))
if __name__=='__main__':main()
