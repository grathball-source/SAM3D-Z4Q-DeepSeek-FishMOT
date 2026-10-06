"""Append-only diagnosis of a failed postseal decision reproduction, without GT."""
from common import *
from association import choose
from bridge import stream
from pycocotools import mask as coco
import copy

name = 'LW'
public = RUN/name/'public'
events = read(public/'EVENTS.json')
event_id = 'MS1-F2896'
prototype = next(e for e in events['DEPTH_OFF'] if e['id']==event_id)
needed = {s['frame'] for v in prototype['joint_pre'].values() for s in v['samples']}
needed |= set(range(prototype['q'], prototype['decision_cutoff']+1))
records = {}
for (row, profiles), assignment, measured, binding in zip(
    stream(input_dir(name)/'observations.jsonl.gz', input_dir(name)/'profiles.jsonl.gz'),
    rows(input_dir(name)/'assignments.jsonl.gz'), rows(input_dir(name)/'DEPTH_OBSERVATIONS.jsonl.gz'),
    rows(public/'FRAME_INPUTS_BINDINGS.jsonl.gz'), strict=True):
    f = row['frame']
    if f in needed:
        assert row_sha(row)==binding['source_row_sha256']
        assert row_sha(assignment)==binding['assignment_row_sha256']
        assert row_sha(measured)==binding['measured_row_sha256']
        records[f] = dict(row=row, assignment=assignment, measured=measured,
            extracts={int(n):v for n,v in binding['DS18_extracts'].items()},
            masks={o['id']:coco.decode(dict(size=assignment['masks'][o['mask']]['size'],
                counts=assignment['masks'][o['mask']]['counts'].encode('ascii'))).astype(bool)
                for o in row['native']})
    if f>=max(needed): break

def differences(a,b,path='$'):
    if type(a) is not type(b):
        return [dict(path=path,kind='type',sealed=str(type(a)),recomputed=str(type(b)),a=a,b=b)]
    if isinstance(a,dict):
        result=[]
        for key in a.keys() | b.keys():
            if key not in a or key not in b:
                result.append(dict(path=path+'.'+str(key),kind='missing',a=a.get(key),b=b.get(key)))
            else: result.extend(differences(a[key],b[key],path+'.'+str(key)))
        return result
    if isinstance(a,list):
        if len(a)!=len(b): return [dict(path=path,kind='length',a=len(a),b=len(b))]
        return [item for i,(x,y) in enumerate(zip(a,b)) for item in differences(x,y,path+f'[{i}]')]
    return [] if a==b else [dict(path=path,kind='value',a=a,b=b)]

result=[]
for arm in EVENT_ARMS:
    event=copy.deepcopy(next(e for e in events[arm] if e['id']==event_id))
    event['post_roles']={int(n):v for n,v in event['post_roles'].items()}
    event['post_generations']={int(n):v for n,v in event['post_generations'].items()}
    if event.get('confirmed_post_roles'):
        event['confirmed_post_roles']={int(n):v for n,v in event['confirmed_post_roles'].items()}
    recomputed=choose(event,event['joint_pre'],records,arm=='DEPTH_OVERRIDE')
    # Compare the actual serialized representation, retaining numeric values exactly.
    serialized=json.loads(json.dumps(recomputed,default=lambda x:x.tolist() if hasattr(x,'tolist') else sorted(x)))
    diff=differences(event['joint_decision'],serialized)
    result.append(dict(arm=arm,post_order=list(event['post_roles']),
        sealed_hash=digest(event['joint_decision']),recomputed_hash=digest(recomputed),differences=diff))
write_new(HERE/'DECISION_BINDING_DIAGNOSIS.json',dict(segment=name,event=event_id,
    GT_opened=False,predictions_and_scoring_code_unchanged=True,records=result))
for item in result:
    print(item['arm'],len(item['differences']),json.dumps(item['differences'][:20],ensure_ascii=False),flush=True)
