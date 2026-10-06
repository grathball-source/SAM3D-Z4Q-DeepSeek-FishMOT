"""Keep failed fixture; restore only homogeneous numeric-key dictionaries to memory form."""
from common import *
import unittest
previous=module('ds35_scoring_key_fixture_v1',HERE/'checks_scorer_serialization.py')

def integer_keys(value):
    if isinstance(value,dict):
        # depth_facts intentionally has A/B and frame-local string keys. It was
        # already string-keyed before publishing, so never convert that object.
        homogeneous=bool(value) and all(isinstance(k,str) and k.lstrip('-').isdigit() for k in value)
        return {(int(k) if homogeneous else k):integer_keys(v) for k,v in value.items()}
    if isinstance(value,list):return [integer_keys(v) for v in value]
    return value

previous.integer_keys=integer_keys
if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(previous.Checks)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    write_new(HERE/'CHECKS_SCORER_SERIALIZATION_V2.json',dict(status='PASS' if result.wasSuccessful() else 'FAIL',
        tests_run=result.testsRun,tests=[test.id() for test in unittest.defaultTestLoader.loadTestsFromTestCase(previous.Checks)],
        failed_fixture_preserved=artifact(HERE/'checks_scorer_serialization.py'),helper=artifact(__file__),
        real_sealed_decision_source=artifact(RUN/'LW/public/EVENTS.json'),GT_opened=False,
        choices_and_numeric_values_unchanged=True,new_model_http=0,cost_usd=0))
    assert result.wasSuccessful()
