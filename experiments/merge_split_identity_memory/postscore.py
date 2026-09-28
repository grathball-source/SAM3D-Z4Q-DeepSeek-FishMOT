"""After-seal mechanism counts and geometry-only three-branch contact sheet."""
import gzip
import hashlib
import json
import sys
from collections import Counter,defaultdict
from pathlib import Path

from PIL import Image,ImageDraw

from event_packet import token_map
from mask_geometry import mask
from replay import HERE,OBS,rows,read


def save(path,value):
    path=Path(path)
    assert not path.exists(),path
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def mechanism(public,predictions,matches,event):
    fixed={}
    maps={}
    for row in predictions.values():
        frame=row['frame']
        maps[frame]={arm:{int(x['mask'].split(':')[1]):x['id'] for x in row['variants'][arm]}
                     for arm in ('B0','B-HOLD','B-VLM')}
        for native,pid in maps[frame]['B0'].items():
            gt=matches[frame].get(str(native))
            if gt is not None and pid not in fixed:
                fixed[pid]=gt
    inverse=defaultdict(list)
    for pid,gt in fixed.items():
        inverse[gt].append(pid)
    counts=Counter()
    stages=defaultdict(Counter)
    for frame,variants in maps.items():
        stage=('before' if frame<event['suspect_frame'] else
               'group_or_pending' if frame<event['q'] else 'post_q')
        for native,before in variants['B0'].items():
            after=variants['B-VLM'][native]
            if before==after:
                continue
            counts['changed_detections']+=1
            stages[stage]['changed_detections']+=1
            gt=matches[frame].get(str(native))
            candidates=inverse.get(gt,[])
            if len(candidates)!=1:
                counts['unscorable_changed_detections']+=1
                stages[stage]['unscorable_changed_detections']+=1
                continue
            expected=candidates[0]
            name=('improved' if before!=expected and after==expected else
                  'harmed' if before==expected and after!=expected else 'changed_neither')
            counts[name]+=1
            stages[stage][name]+=1
    output=dict(status='POSTSEAL_OUTPUT_ID_AUDIT',fixed_public_first_matched_gt=fixed,
                nonunique_gt_to_public={str(gt):ids for gt,ids in inverse.items() if len(ids)!=1},
                counts=dict(counts),by_stage={k:dict(v) for k,v in stages.items()},
                interpretation='First-matched public-ID accounting is diagnostic; event physical truth is separately audited from fixed clean fragments.')
    save(public/'MECHANISM_AUDIT.json',output)
    return output


def visual(public,predictions,observations,assignments,event,scan):
    sources=scan['sources']
    suspect=event['suspect_frame']
    pre=max(f for f in range(max(1,suspect-30),suspect)
            if all(any(o['id']==n and o['area']>=64 and not o['neighbors']
                       for o in observations[f]['observations']) for n in sources))
    frames=[pre,suspect,(suspect+event['post_start'])//2,event['post_start'],event['q'],
            min(2888,event['q']+3)]
    phases=['PRE','FIRST_SUSPECT','MERGED','SPLIT_PENDING','RESTORE_Q','AFTER_Q']
    arms=['B0','B-HOLD','B-VLM']
    width,height=640,410
    sheet=Image.new('RGB',(width*3,height*len(frames)),'#101820')
    index=[]
    for ri,(frame,phase) in enumerate(zip(frames,phases)):
        row=observations[frame]
        tokens=token_map([row])
        by_native={o['id']:o for o in row['observations']}
        assignment=assignments[frame]
        for ci,arm in enumerate(arms):
            panel=Image.new('RGB',(width,height),'#101820')
            variants=predictions[frame]['variants'][arm]
            draw=ImageDraw.Draw(panel)
            labels=[]
            for item in variants:
                native=int(item['mask'].split(':')[1])
                key=item['mask']
                if key not in assignment['masks']:
                    continue
                fill=('#ad70d0' if native==scan['group'] and phase in ('FIRST_SUSPECT','MERGED') else
                      '#31b494' if native==sources[0] else '#e7a74b' if native==sources[1] else '#46535d')
                panel.paste(fill,mask=Image.fromarray((mask(assignment['masks'][key])*255).astype('uint8')))
                o=by_native.get(native)
                if o and o['area']>=64:
                    cx=(o['box'][0]+o['box'][2])/2
                    cy=(o['box'][1]+o['box'][3])/2
                    labels.append((min(500,cx+3),max(25,cy-11),f'{tokens[(frame,native)]} ID {item["id"]}'))
            draw=ImageDraw.Draw(panel)
            for x,y,label in labels:
                draw.rectangle((x-2,y-1,x+len(label)*7+2,y+12),fill='#101820')
                draw.text((x,y),label,fill='white')
            draw.rectangle((0,360,639,409),fill='#202e36')
            draw.text((8,6),f'{arm} | {phase} | F{frame}',fill='white')
            mapping={int(x['mask'].split(':')[1]):x['id'] for x in variants}
            member_line=' | '.join(f'{tokens.get((frame,n),"ABSENT")} -> {mapping.get(n,"LATENT")}' for n in sources)
            draw.text((8,369),'Two saved members: '+member_line,fill='white')
            draw.text((8,388),'Measured mask pixels only; no RGB or GT',fill='#bdd5dc')
            sheet.paste(panel,(ci*width,ri*height))
        index.append(dict(frame=frame,phase=phase))
    path=public/'MS1_THREE_BRANCH_CONTACT_SHEET.png'
    assert not path.exists()
    sheet.save(path)
    raw=path.read_bytes()
    manifest=dict(status='POSTSEAL_GEOMETRY_ONLY',file=path.name,bytes=len(raw),
                  sha256=hashlib.sha256(raw).hexdigest(),frames=index,arms=arms,
                  source='actual prediction-mask RLE and sealed public ID outputs; no RGB or GT raster')
    save(public/'VISUAL_MANIFEST.json',manifest)
    return manifest


def main():
    public=HERE/'run_ms1_20260928/public'
    seal=read(public/'PREDICTIONS_SEALED.json')
    assert seal['status']=='SEALED_AWAITING_INDEPENDENT_SCORING'
    assert hashlib.sha256((public/'predictions_validation.jsonl.gz').read_bytes()).hexdigest()==seal['predictions_sha256']
    assert read(public/'METRICS.json')['source_prediction_sha256']==seal['predictions_sha256']
    pred={x['frame']:x for x in rows(public/'predictions_validation.jsonl.gz')}
    obs={x['frame']:x for x in rows(OBS)}
    assign={x['frame']:x for x in rows(HERE/'private_source/assignments.jsonl.gz')}
    matches={x['frame']:x['native_to_gt'] for x in rows(HERE/'private_source/offline_matches_validation.jsonl.gz')}
    event=read(public/'EVENTS.json')['B-VLM'][0]
    scan=read(HERE/'private_source/scan.json')['suspects'][0]
    m=mechanism(public,pred,matches,event)
    v=visual(public,pred,obs,assign,event,scan)
    print(json.dumps(dict(mechanism=m['counts'],visual=v),ensure_ascii=False))


def other_fish_audit():
    public=HERE/'run_ms1_20260928/public'
    members=set(read(HERE/'private_source/scan.json')['suspects'][0]['sources'])
    counts=Counter()
    for row in rows(public/'predictions_validation.jsonl.gz'):
        before={x['mask']:x['id'] for x in row['variants']['B0']}
        after={x['mask']:x['id'] for x in row['variants']['B-HOLD']}
        for key in before:
            if before[key]!=after[key]:
                counts[int(key.split(':')[1])]+=1
    assert set(counts).issubset(members)
    output=dict(status='POSTSEAL_OTHER_OBJECT_INVARIANCE',
                changed_detections_by_private_source={str(k):v for k,v in sorted(counts.items())},
                nonmember_changed_detections=0,
                source='sealed B0/B-HOLD predictions and fixed source-scan member set')
    save(public/'OTHER_FISH_AUDIT.json',output)
    print(json.dumps(output))


if __name__=='__main__':
    if sys.argv[1:]==['--other']:
        other_fish_audit()
    elif not sys.argv[1:]:
        main()
    else:
        raise SystemExit('usage: postscore.py [--other]')
