"""Read actual cached mixture/quality records behind pre-pair window mismatch."""
import sys
from pathlib import Path
def _block(event,args):
    if event=='open' and isinstance(args[0],(str,bytes)):
        name=str(args[0]).replace('\\','/').lower()
        if any(x in name for x in ('/metrics','/gt/','/annotations/','/rgb/','instance_id','depth_mm_v3')):
            raise RuntimeError('Source-only audit prohibited input: '+name)
sys.addaudithook(_block)
from common import HERE,RUN,read,rows,artifact,sha,write_new

FOCUS={
 'feeding_001201_001906':[(557,563,(151,))],
 'LW':[(2866,2884,(3,))],
 'feeding_000351_000555':[(68,73,(1,24))],
 'fishsa_validation_2888':[(414,416,(3,4))],
}
out=[];sources=[]
for name,windows in FOCUS.items():
 public=RUN/name/'public';seal=read(public/'PREDICTIONS_SEALED.json')
 for filename in ('MIXED_DEPTH.jsonl.gz','DEPTH_OBSERVATIONS.jsonl.gz'):
  assert sha(public/filename)==seal['artifacts_sha256'][filename]
  sources.append(artifact(public/filename))
 end=max(w[1] for w in windows);raw={}
 for row in rows(public/'DEPTH_OBSERVATIONS.jsonl.gz'):
  if row['frame']>end:break
  for lo,hi,objects in windows:
   if lo<=row['frame']<=hi:
    for native in objects:raw[row['frame'],native]=row['adaptive_raw'].get(str(native))
 for row in rows(public/'MIXED_DEPTH.jsonl.gz'):
  if row['frame']>end:break
  for lo,hi,objects in windows:
   if not lo<=row['frame']<=hi:continue
   for native in objects:
    certificate=row['objects'].get(str(native));measurement=raw[row['frame'],native]
    if certificate is None:
     out.append(dict(segment=name,frame=row['frame'],native=native,presence=False));continue
    core=certificate['core']
    out.append(dict(segment=name,frame=row['frame'],global_frame=row['global_frame'],time=row['time'],native=native,
     raw_core=dict(measurement['core']),raw_core_usable=measurement['core_usable'],
     mixed_core={k:core.get(k) for k in ('fact_id','status','reason','eligible_single','mixture_flag','quality_usable','original_pixel_quality_usable','substantial_layer_count','qualified_layer_count','inclusive_summary','summary')},
     certificate_sha256=certificate.get('certificate_sha256'),frame_binding_sha256=row['frame_binding_sha256'],
     guard_raw_policy='ACTUAL_FROZEN_CODE: raw.core_usable AND binding.screened_eligible; NOT_NEW_ASSOCIATION'))
write_new(HERE/'PRE_PAIR_FOCUS_SOURCE_FACTS.json',dict(status='READONLY_ACTUAL_CACHE_FACTS',GT_read=False,new_association=False,new_model_http=0,helper=artifact(Path(__file__)),source_artifacts=sources,facts=out))
print('FOCUS_ROWS',len(out))
