"""Own-state real prefixes, unchanged controls, current publication and local returns."""
from common import *
from concurrent.futures import ThreadPoolExecutor,as_completed
from execute import run
import argparse


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--tag',default='r1');args=parser.parse_args()
    directory='slice_'+args.tag
    stops={'L3':3030,'fishsa_development_8400':3970,'fishsa_validation_2888':2250,
           'feeding_000000_000199':200}
    results={}
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures={pool.submit(run,'guard.py','slice',name,str(stop),directory):name for name,stop in stops.items()}
        for future in as_completed(futures):
            result=future.result();results[futures[future]]=result
    assert all(x['exit_code']==0 for x in results.values()),results
    checks={}
    for name,stop in stops.items():
        public=HERE/directory/name/'public'
        old=iter(rows(DS18/'run'/name/'public/predictions.jsonl.gz'))
        count=0
        for actual in rows(public/'predictions.jsonl.gz'):
            previous=next(old);count+=1
            assert (actual['frame'],actual['global_frame'])==(previous['frame'],previous['global_frame'])
            for arm in ('SAM3_NATIVE','Z4Q_FROZEN','ACTIVITY_ORDER','MIXED_ORDER'):
                assert actual['variants'][arm]==previous['variants'][arm],(name,actual['frame'],arm)
            masks=[x['mask'] for x in actual['variants']['SAM3_NATIVE']]
            for arm in ARMS:
                assert [x['mask'] for x in actual['variants'][arm]]==masks
                assert len({x['id'] for x in actual['variants'][arm]})==len(masks)
        assert count==stop,(name,count,stop)
        returns=[]
        for tx in rows(public/'TRANSACTIONS.jsonl.gz'):
            record=tx.get('local_return')
            if record and record.get('status')=='EVENT_LOCAL_RETURN_COMMITTED':returns.append(record)
            trace=tx.get('controller_trace',{})
            event=trace.get('ds19_event_local_return')
            if event and event.get('status')=='EVENT_LOCAL_RETURN_COMMITTED' and event not in returns:returns.append(event)
        events=read(public/'EVENTS.json')
        for values in events.values():
            for event in values:
                if event['q'] is not None:
                    assert event['evidence_cutoff_frame']==event['q']
                    assert all(x['frame']==event['q'] for x in event['post_first_observations'].values())
        checks[name]=dict(frames=count,unchanged_native_Z4Q_and_two_controls=True,
            all_masks_unique_public_ids=True,current_source_transactions=returns,
            predictions=artifact(public/'predictions.jsonl.gz'),access=artifact(public/'ACCESS.json'),
            events=events)
    write_new(HERE/'PREFIX_CHECKS.json',dict(status='PASS',checks=checks,GT_read=False,model_http=0,
        source_logs=results,actual_test_sources={str(path):sha(path) for path in (
            HERE/'check_prefix.py',HERE/'runner.py',HERE/'controller.py',HERE/'common.py',HERE/'guard.py')}))
    print('PASS9450 actual prefixframes: four exact old controls and six publication contracts')


if __name__=='__main__':main()
