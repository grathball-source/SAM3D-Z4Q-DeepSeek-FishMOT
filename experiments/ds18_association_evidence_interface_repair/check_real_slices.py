"""Real causal source prefixes through prespecified engineering failure frames; no GT."""
from common import *
from concurrent.futures import ThreadPoolExecutor
from execute import run
from mixed_depth import validate_certificate
from score import verify_automatic_sources,verify_order_sources
import time

CASES={'fishsa_development_8400':3902,'fishsa_validation_2888':2188,
       'LW':3064,'feeding_000000_000199':191,'feeding_001201_001906':274}

def main():
    finishing='--finish-completed-prefixes' in sys.argv
    if not finishing:
        with ThreadPoolExecutor(max_workers=3) as pool:
            results=list(pool.map(lambda item:run('guard.py','slice',item[0],str(item[1]),'slice_real_immutable'),CASES.items()))
        assert all(x['exit_code']==0 for x in results),results
    checks={}
    for name,stop in sorted(CASES.items(),key=lambda item:item[0]=='LW'):
        folder='slice_real_records' if finishing and name=='LW' else 'slice_real_immutable'
        public=HERE/folder/name/'public'
        if finishing and name=='LW':
            deadline=time.monotonic()+3600
            while not (public/'ACCESS.json').exists():
                assert time.monotonic()<deadline,'Unfinished actual LW source prefix; no acceptance synthesized'
                time.sleep(1)
        assert read(public/'RUN_SUMMARY.json')['frames']==stop
        predictions=list(rows(public/'predictions.jsonl.gz'))
        assert len(predictions)==stop
        for current,old in zip(predictions,rows(DS16/'run'/name/'public/predictions.jsonl.gz')):
            assert all(current['variants'][a]==old['variants'][a] for a in ('SAM3_NATIVE','Z4Q_FROZEN'))
            assert current['variants']['DS16_ORDER']==old['variants']['DEPTH_ORDER']
        certs=list(rows(public/'MIXED_DEPTH.jsonl.gz'))
        assert all(validate_certificate(c) for row in certs for c in row['objects'].values())
        trace=[x for x in rows(public/'TRANSACTIONS.jsonl.gz') if x['frame']==stop]
        assert len(trace)==5
        checks[name]=dict(stop_frame=stop,global_frame=predictions[-1]['global_frame'],
            actual_prediction=predictions[-1],actual_certs=certs[-1],
            actual_controller_transactions=trace,baseline_parity=True,
            predictions=artifact(public/'predictions.jsonl.gz'),access=artifact(public/'ACCESS.json'),
            independent_actual_automatic_sources=verify_automatic_sources(public),
            independent_actual_order_sources=verify_order_sources(public),
            all_same_roi_certificates_valid=True,GT_expected_mapping_not_required=True)
        print(name,'actual source/scorer acceptance PASS',flush=True)
    write_new(HERE/'REAL_SLICE_CHECKS.json',dict(status='PASS',frames=sum(CASES.values()),cases=checks,
        original_references_not_replaced=True,GT_read=False,model_http=0,cost_usd=0))
    write_new(HERE/'REAL_SLICE_SOURCE_SCORER.json',dict(status='PASS',cases={name:dict(
        automatic=c['independent_actual_automatic_sources'],order=c['independent_actual_order_sources'],
        prediction= c['predictions']) for name,c in checks.items()},
        actual_scoring_code_sha256=sha(HERE/'score.py'),GT_read=False,model_http=0,cost_usd=0,
        note='Independent source scorer executes inside real-slice acceptance; not counted as two separate replications'))
    print('Real source-to-controller prefixes PASS',sum(CASES.values()),flush=True)

if __name__=='__main__':main()
