"""Pre-freeze independent accepted-action verification on completed real prefixes."""
from common import *
from check_real_slices import CASES
from score import verify_automatic_sources,verify_order_sources


def main():
    cases={}
    for name,stop in CASES.items():
        public=Path(read(HERE/'REAL_SLICE_CHECKS.json')['cases'][name]['predictions']['path']).parent
        assert read(public/'RUN_SUMMARY.json')['frames']==stop
        cases[name]=dict(automatic=verify_automatic_sources(public),order=verify_order_sources(public),
            prediction_seal=artifact(public/'PREDICTIONS_SEALED.json'))
        print(name,'source-bound independent scorer PASS',flush=True)
    write_new(HERE/'REAL_SLICE_SOURCE_SCORER.json',dict(status='PASS',cases=cases,GT_read=False,
        actual_scoring_code_sha256=sha(HERE/'score.py'),model_http=0,cost_usd=0))

if __name__=='__main__':main()
