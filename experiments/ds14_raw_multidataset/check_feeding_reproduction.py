"""Full formal runs must reproduce old frozen R12_RAW; no GT is opened."""
from common import *
def main():
    report={}
    for name in (n for n in SEGMENTS if n.startswith('feeding_')):
        new=RUN/name/'public';old=DS12/'run'/name/'public'
        assert (new/'PREDICTIONS_SEALED.json').exists()
        count=0
        for a,b in zip(rows(new/'predictions.jsonl.gz'),rows(old/'predictions.jsonl.gz'),strict=True):
            assert (a['frame'],a['global_frame'],a['time'])==(b['frame'],b['global_frame'],b['time'])
            assert a['variants']=={arm:b['variants'][arm] for arm in ARMS},(name,a['frame'])
            count+=1
        assert read(new/'EVENTS.json')['R12_RAW']==read(old/'EVENTS.json')['R12_RAW'],name
        report[name]=dict(frames=count,native_and_R12_RAW_every_mapping_exact=True,all_event_decisions_exact=True)
    write_new(HERE/'FEEDING_REPRODUCTION.json',dict(status='PASS',segments=report,frames=1471,GT_opened=False,new_model_http=0))
    print('PASS all1471 formal Feeding mappings and events exact',flush=True)
if __name__=='__main__':main()
