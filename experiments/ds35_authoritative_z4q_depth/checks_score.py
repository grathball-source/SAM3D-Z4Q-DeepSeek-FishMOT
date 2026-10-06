"""Real raw frame contract mutations remain invalid even with fresh logical hashes."""
from common import *
import copy,unittest
from bridge import stream
from association import DEPTH,gate
from checks import detail
from source_contract import verify_frame_contract

def actual():
    name='feeding_000351_000555';base=input_dir(name)
    row,_=next(stream(base/'observations.jsonl.gz',base/'profiles.jsonl.gz'))
    a=next(rows(base/'assignments.jsonl.gz'));m=next(rows(base/'DEPTH_OBSERVATIONS.jsonl.gz'))
    quality=next(rows(DS18/'run'/name/'public/MIXED_DEPTH.jsonl.gz'))
    p=dict(frame=1,global_frame=row['global_frame'],time=row['time'])
    bound=dict(p,source_row_sha256=row_sha(row),assignment_row_sha256=row_sha(a),measured_row_sha256=row_sha(m),
        DS18_packet_sha256=digest(quality),DS18_extracts={str(n):DEPTH.extract(c) for n,c in quality['objects'].items()},
        raw_source_binding=m['raw_source_binding'],actual_RGB_read=False,GT=False)
    return [name,p,a,row,m,quality,bound,dict(frame_inputs_row_sha256=row_sha(bound)),None]

def reseal(args):
    args[6]['DS18_packet_sha256']=digest(args[5]);args[6]['measured_row_sha256']=row_sha(args[4])
    args[6]['assignment_row_sha256']=row_sha(args[2]);args[6]['source_row_sha256']=row_sha(args[3])
    args[7]['frame_inputs_row_sha256']=row_sha(args[6])

class Checks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.frame=actual()
    def test_real_frame_pass(self):verify_frame_contract(*copy.deepcopy(self.frame))
    def test_depth_quality_mutation_self_consistent_hash_rejected(self):
        a=copy.deepcopy(self.frame);native=next(iter(a[5]['objects']));a[5]['objects'][native]['core']['inclusive_summary']['n']+=1
        cert=a[5]['objects'][native];cert['core']['inclusive_statistics_sha256']=digest(cert['core']['inclusive_summary'])
        cert['certificate_sha256']=digest({k:v for k,v in cert.items() if k!='certificate_sha256'})
        a[6]['DS18_extracts'][native]=DEPTH.extract(cert);reseal(a)
        with self.assertRaises(AssertionError):verify_frame_contract(*a)
    def test_endpoint_depth_fact_mutation_rejected(self):
        a=copy.deepcopy(self.frame);n=next(iter(a[6]['DS18_extracts']));a[6]['DS18_extracts'][n]['quality']['independent_source_n']+=1;reseal(a)
        with self.assertRaises(AssertionError):verify_frame_contract(*a)
    def test_future_frame_rejected_self_consistent_hash(self):
        a=copy.deepcopy(self.frame);a[3]['frame']=2;reseal(a)
        with self.assertRaises(AssertionError):verify_frame_contract(*a)
    def test_source_index_swapped_rejected(self):
        a=copy.deepcopy(self.frame);a[5]['actual_source_index_binding']=a[5]['actual_depth_binding'];reseal(a)
        with self.assertRaises(AssertionError):verify_frame_contract(*a)
    def test_candidate_container_order_no_effect(self):
        d=detail();prior=gate(d);d['scores']=d['scores'][::-1];self.assertEqual(gate(d),prior)

if __name__=='__main__':
    r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Checks));assert r.wasSuccessful()
    write_new(HERE/'CHECKS_SCORE.json',dict(status='PASS',tests=r.testsRun,real_input='SOURCE_OLD Feeding first saved frame',
        mutations_rehash_actual_logical_contract=True,GT_opened=False,new_model_http=0,cost_usd=0))
