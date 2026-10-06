"""Real failed-decision serialization plus factual/choice tamper rejection; no GT."""
from common import *
from score_serialized_v2 import serialized
import copy,unittest

def integer_keys(value):
    if isinstance(value,dict):
        return {(int(k) if isinstance(k,str) and k.lstrip('-').isdigit() else k):integer_keys(v)
            for k,v in value.items()}
    if isinstance(value,list):return [integer_keys(v) for v in value]
    return value

events=read(RUN/'LW/public/EVENTS.json')
real={a:next(e['joint_decision'] for e in events[a] if e['id']=='MS1-F2896') for a in EVENT_ARMS}

class Checks(unittest.TestCase):
    def test_real_multidigit_decision_matches_actual_json(self):
        for decision in real.values():
            original=copy.deepcopy(decision);memory=integer_keys(decision)
            self.assertNotEqual(digest(memory),digest(decision))
            self.assertEqual(digest(serialized(memory)),digest(decision))
            self.assertEqual(decision,original)
    def test_choice_and_candidate_list_not_reordered(self):
        for d in real.values():
            result=serialized(integer_keys(d))
            self.assertEqual(result['choice'],d['choice'])
            self.assertEqual(result['scores'],d['scores'])
            wrong=copy.deepcopy(result);wrong['scores'].reverse()
            self.assertNotEqual(digest(wrong),digest(d))
    def test_physical_mapping_tamper_still_fails(self):
        for d in real.values():
            wrong=copy.deepcopy(d);wrong['scores'][0]['mapping']['106']=999
            self.assertNotEqual(digest(serialized(wrong)),digest(d))
    def test_measured_fact_tamper_still_fails(self):
        for d in real.values():
            wrong=copy.deepcopy(d)
            wrong['scores'][0]['edges'][0]['geometry_samples'][0]['actual_gap_seconds']+=.001
            self.assertNotEqual(digest(serialized(wrong)),digest(d))
    def test_top_level_choice_tamper_still_fails(self):
        for d in real.values():
            wrong=copy.deepcopy(d);wrong['choice']='H2'
            self.assertNotEqual(digest(serialized(wrong)),digest(d))

if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Checks)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    write_new(HERE/'CHECKS_SCORER_SERIALIZATION.json',dict(status='PASS' if result.wasSuccessful() else 'FAIL',
        tests_run=result.testsRun,tests=[test.id() for test in unittest.defaultTestLoader.loadTestsFromTestCase(Checks)],
        real_sealed_decision_source=artifact(RUN/'LW/public/EVENTS.json'),helper=artifact(__file__),GT_opened=False,
        choices_and_numeric_values_unchanged=True,new_model_http=0,cost_usd=0))
    assert result.wasSuccessful()
