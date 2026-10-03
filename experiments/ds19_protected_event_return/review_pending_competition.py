"""Read frozen ordinary/event confirmation competition, without a new replay."""
import sys
from pathlib import Path
def _block(event,args):
    if event=='open' and isinstance(args[0],(str,bytes)):
        name=str(args[0]).replace('\\','/').lower()
        if any(x in name for x in ('/metrics','/gt/','/annotations/','/rgb/','instance_id','depth_mm_v3')):
            raise RuntimeError('Source-only audit prohibited input: '+name)
sys.addaudithook(_block)
from common import HERE,RUN,read,rows,sha,artifact,write_new
CASES=(('feeding_000000_000199',190,200,38,('ACTIVITY_ORDER','ACTIVITY_RETURN')),
       ('LW',947,965,32,('MIXED_ORDER','MIXED_RETURN')))
result=[];artifacts=[]
for name,start,stop,native,arms in CASES:
 public=RUN/name/'public';seal=read(public/'PREDICTIONS_SEALED.json')
 path=public/'TRANSACTIONS.jsonl.gz';assert sha(path)==seal['artifacts_sha256'][path.name]
 artifacts.append(artifact(path));selected=[]
 for row in rows(path):
  if row['frame']>stop:break
  if row['frame']<start or row['arm'] not in arms:continue
  trace=row['controller_trace'];proposal=trace.get('ds19_event_return_proposals') or {}
  events=[e for e in trace.get('events',[]) if e.get('native_id')==native]
  carry=(proposal.get('carried_original_confirmations') or {}).get(str(native))
  checks=[e for e in proposal.get('checks',[]) if e.get('native_id')==native]
  selected.append(dict(frame=row['frame'],original_frame=row['global_frame'],arm=row['arm'],
   event=row['active_event'],ordinary_events=events,carried_pending=carry,proposal_checks=checks,
   accepted_protected_proposals=[e for e in proposal.get('accepted',[]) if e.get('native_id')==native],
   local_return_stage=row.get('local_return_stage'),return_record=row.get('return_record'),
   actual_public=row['actual_published_mapping'].get(str(native)),
   actual_alias=row['actual_alias_targets'].get(str(native)),
   durable_automatic_commits=[e for e in row['durable_automatic_commits'] if e['event'].get('native_id')==native]))
 collisions=[]
 for row in selected:
  if not row['carried_pending']:continue
  for event in row['ordinary_events']:
   if event.get('kind')=='reconnect' and not event['accepted'] and event['canonical_id'] != row['carried_pending']['target']:
    collisions.append(dict(frame=row['frame'],original_frame=row['original_frame'],arm=row['arm'],event=row['event'],
     ordinary_target=event['canonical_id'],ordinary_confirmations=event['confirmations'],
     transported_target=row['carried_pending']['target'],transported_count=row['carried_pending']['count'],
     source_native=native,actual_public=row['actual_public']))
 result.append(dict(segment=name,native=native,frames=[start,stop],arms=list(arms),actual_trace_rows=selected,collisions=collisions))
write_new(HERE/'PENDING_COMPETITION_BOUNDARY.json',dict(status='READONLY_SOURCE_KEY_PENDING_COMPETITION_CONFIRMED',
 GT_read=False,metrics_read=False,new_association=False,new_model_http=0,
 method_source=artifact(HERE/'controller.py'),helper=artifact(Path(__file__)),source_artifacts=artifacts,cases=result,
 scope='Source-key isolation holds; a shared source pending slot can overwrite a target outside event member_public',
 zero_return_is_zero_side_effect=False))
for case in result:print(case['segment'],'collisions',case['collisions'])
