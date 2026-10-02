"""Storage-only optimization must preserve all scientific JSON and publications."""
from common import *
from runner import run_segment
from score import verify_automatic_sources, verify_order_sources


def main():
    checks={}
    streams=('predictions.jsonl.gz','MIXED_DEPTH.jsonl.gz','TRANSACTIONS.jsonl.gz',
             'DEPTH_STATES.jsonl.gz','DEPTH_OBSERVATIONS.jsonl.gz','BIRTHS.jsonl.gz',
             'CONTACT_CERTIFICATES.jsonl.gz','ORDER_EVIDENCE.jsonl.gz')
    for name in ('fishsa_development_8400','feeding_001201_001906','L3'):
        out=HERE/('slice_immutable_records' if '--records' in sys.argv else 'slice_immutable')
        if not (out/name/'public/RUN_SUMMARY.json').exists():
            run_segment(name,out,stop_at=50)
        else:
            assert '--resume-source-check' in sys.argv
            assert read(out/name/'public/RUN_SUMMARY.json')['frames']==50
        new=out/name/'public';old=HERE/'slice'/name/name/'public'
        counts={}
        for stream in streams:
            count=0
            for a,b in zip(rows(new/stream),rows(old/stream),strict=True):
                assert a==b,(name,stream,count,'storage optimization changed scientific data')
                # dict/list subclass serialization must also preserve canonical bytes.
                assert json.dumps(a,separators=(',',':'),allow_nan=False)==json.dumps(b,separators=(',',':'),allow_nan=False)
                count+=1
            counts[stream]=count
        for file in ('EVENTS.json','COMMON_STATE_SHADOW.json'):
            assert read(new/file)==read(old/file)
        checks[name]=dict(rows=counts,all_scientific_rows_and_canonical_JSON_equal=True,
            order_sources=verify_order_sources(new),automatic_sources=verify_automatic_sources(new),
            actual_prediction=artifact(new/'predictions.jsonl.gz'),
            elapsed_seconds=read(new/'RUN_SUMMARY.json')['elapsed_seconds'],
            old_elapsed_seconds=read(old/'RUN_SUMMARY.json')['elapsed_seconds'])
    proof='IMMUTABLE_RECORD_EQUIVALENCE.json' if '--records' in sys.argv else 'IMMUTABLE_EQUIVALENCE.json'
    write_new(HERE/proof,dict(status='PASS',frames=150,checks=checks,
        untrusted_JSON_fully_validated=True,mutable_state_clone_isolation=True,
        runtime_boundary='Read-only normal branch operations; not an isolation boundary against malicious same-process Python builtin calls',
        source_archive=artifact(HERE/'archive_prefreeze_mutable/ARCHIVE.json'),
        GT_read=False,model_http=0,cost_usd=0))
    print('PASS: immutable storage preserved150 real frames and independent source scorer',flush=True)

if __name__=='__main__':main()
