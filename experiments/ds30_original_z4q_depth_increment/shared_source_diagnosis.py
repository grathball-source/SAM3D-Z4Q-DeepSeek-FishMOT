"""Remeasure two old input failures; no outcome labels or new sample selection."""
from common import *
import runpy
guard=runpy.run_path(str(ROOT/'experiments/ds20_pending_confirmation_isolation/guard.py'),run_name='ds30_source_diagnostic_guard')
from evidence import Sources
from association import pair
from bridge import stream
out=HERE/'shared_source_diagnostic';out.mkdir()
records=[]
with gzip.open(out/'MEASUREMENTS.jsonl.gz','xt',encoding='utf-8') as handle:
    for name,frame in [('feeding_000351_000555',48),('L3',1421)]:
        old=next(x for x in rows(ROOT/'experiments/ds29_anonymous_pair_joint/run'/name/'public/ORDER_CHECKS.jsonl.gz') if x['frame']==frame)
        old_detail=old['checks']['JOINT_DEPTH'][0]['detail'];ns=old_detail['anonymous_current_sources']
        provider=Sources(name,handle);base=input_dir(name)
        try:
            assignment=next(x for x in rows(base/'assignments.jsonl.gz') if x['frame']==frame)
            measurement=next(x for x in rows(base/'DEPTH_OBSERVATIONS.jsonl.gz') if x['frame']==frame)
            row=next(r for r,p in stream(base/'observations.jsonl.gz',base/'profiles.jsonl.gz') if r['frame']==frame)
            provider.add(row,assignment,measurement['raw_source_binding'])
            first,second,check=provider.unique_pair('DEPTH_INCREMENT',frame,*ns)
            comparison=pair(first,second)
            assert check['shared_unique_sources']==(1 if name.startswith('feeding') else 20)
            records.append(dict(segment=name,frame=frame,global_frame=row['global_frame'],current_sources=ns,
                old_fact_only_source_fixture=True,not_current_trial_state_or_choice=True,
                source_check=check,comparison=comparison,actual_source_reads=provider.reads))
        finally:provider.close()
write_new(HERE/'SHARED_SOURCE_DIAGNOSIS.json',dict(status='PASS_ACTUAL_SHARED_SOURCE_REMEASUREMENT_CONTRACT',records=records,
    measurements=artifact(out/'MEASUREMENTS.jsonl.gz'),no_GT_or_RGB=True,actual_field_reads=guard['NPZ'] and [dict(path=p,key=k) for p,k in sorted(guard['NPZ'])],new_model_http=0,cost_usd=0))
print(json.dumps([dict(segment=r['segment'],shared=r['source_check']['shared_unique_sources'],probability=r['comparison']['probability_A_nearer']) for r in records]),flush=True)
