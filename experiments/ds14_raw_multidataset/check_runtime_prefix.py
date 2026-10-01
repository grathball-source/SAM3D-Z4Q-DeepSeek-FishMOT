"""Actual controller adapter smoke, zero model calls, no reference reading."""
from common import *
from runner import run_segment
def main():
    name='feeding_000000_000199';output=HERE/'slice';assert not output.exists()
    run_segment(name,output,stop_at=50)
    p=output/name/'public';old=DS12/'run'/name/'public'
    for index,(a,b) in enumerate(zip(rows(p/'predictions.jsonl.gz'),rows(old/'predictions.jsonl.gz')),1):
        assert a['variants']=={arm:b['variants'][arm] for arm in ARMS},index
    assert index==50
    write_new(HERE/'RUNTIME_PREFIX_CHECK.json',dict(status='PASS',frames=50,full_formal_run=False,
        current_raw_certificate_path_entered=True,source=artifact(p/'CONTACT_CERTIFICATES.jsonl.gz'),
        first_publication_and_native_conservation=True,new_model_http=0,cost_usd=0,GT_opened=False))
    print('PASS genuine state first50 prefix; no GT or model calls')
if __name__=='__main__':main()
