from common import *
import unittest

def main():
    suite=unittest.TestSuite()
    for name,path in [('ds17_mixed_test',HERE/'test_mixed_depth.py'),('ds17_state_test',HERE/'test_controller.py'),('ds17_reused_order_test',DS16/'test_order.py')]:
        test_module=module(name,path)
        suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(test_module))
        if hasattr(test_module,'checks'):suite.addTest(unittest.FunctionTestCase(test_module.checks))
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    assert result.wasSuccessful()
    write_new(HERE/'CHECKS.json',dict(status='PASS',tests=result.testsRun,failures=0,errors=0,GT_read=False,model_http=0,cost_usd=0))
if __name__=='__main__':main()
