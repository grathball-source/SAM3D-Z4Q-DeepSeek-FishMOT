"""Actual published before/group/q/after views; no RGB or GT raster."""
from common import *
from collections import defaultdict
from evidence import RawDepth,native_masks
import cv2,numpy as np
cv2.setNumThreads(1)
whole=read(RUN/'ALL_PREDICTIONS_SEALED.json');assert whole['frames']==20098
for n in SEGMENTS:verify_seal(n)
cases=defaultdict(list)
for c in rows(HERE/'FORMAL_JOINT_DECISIONS.jsonl.gz'):
    if c['arm']=='JOINT_DEPTH':cases[c['segment']].append(c)
records=[];private=HERE/'private';private.mkdir(exist_ok=True)
for name in SEGMENTS:
    events=read(RUN/name/'public/EVENTS.json')['JOINT_DEPTH']
    selected=[]
    # First q, first informative q, first changed-depth choice; no GT selection.
    for predicate in (lambda d:True,lambda d:d['detail']['depth_used'],lambda d:d['choice'] in ('H1','H2') and d['choice']!=d['detail'].get('geometry_choice')):
        case=next((c for c in cases[name] if predicate(c['decision'])),None)
        if case and case not in selected:selected.append(case)
    wrong=next((x for x in read(RUN/name/'public/JOINT_ACTION_AUDIT.json')['events']
        if x['arm']=='JOINT_DEPTH' and x['committed_actual_reference_physical']=='WRONG'),None)
    if wrong:
        case=next(c for c in cases[name] if c['decision']['frame']==wrong['frame'])
        if case not in selected:selected.append(case)
    if not selected and events:selected=[dict(segment=name,arm='JOINT_DEPTH',decision=None,event=events[0])]
    needs=set()
    for c in selected:
        d=c.get('decision');e=next(e for e in events if e['id']==d['event']) if d else c['event']
        f=d['frame'] if d else (e['end'] or SEGMENTS[name][1]-SEGMENTS[name][0]+1)
        c['event']=e;c['frames']=[max(1,e['suspect_frame']-1),e['confirm_frame'] or e['suspect_frame'],f,min(f+2,SEGMENTS[name][1]-SEGMENTS[name][0]+1)]
        needs.update(c['frames'])
    if not needs:continue
    assigned={r['frame']:r for r in rows(input_dir(name)/'assignments.jsonl.gz') if r['frame'] in needs}
    predictions={r['frame']:r for r in rows(RUN/name/'public/predictions.jsonl.gz') if r['frame'] in needs}
    depth=RawDepth(name)
    try:
        for index,c in enumerate(selected):
            e=c['event'];d=c.get('decision');canvas=np.full((850,1320,3),250,'u1');panels=[]
            title=f"{name} / {e['id']} / {d['choice'] if d else 'NO_SPLIT'} / {d['status'] if d else e['status']}"
            cv2.putText(canvas,title,(18,30),cv2.FONT_HERSHEY_SIMPLEX,.6,(20,20,20),1,cv2.LINE_AA)
            if d:
                text=f"pp={d['detail']['pre_probability']:.6f} pq={d['detail']['current_probability']:.6f} depth_used={d['detail']['depth_used']} post_velocity=UNKNOWN"
                cv2.putText(canvas,text,(18,57),cv2.FONT_HERSHEY_SIMPLEX,.5,(20,20,20),1,cv2.LINE_AA)
            else:cv2.putText(canvas,'No first split in this fixed segment; all masks remain published',(18,57),cv2.FONT_HERSHEY_SIMPLEX,.5,(20,20,20),1)
            for j,f in enumerate(c['frames']):
                a=assigned[f];p=predictions[f];masks=native_masks(a)
                depth.previous_frame=None  # Postseal display of separate cases, never causal runtime input.
                raw,_,_,binding=depth(p['global_frame'],p['time'])
                role_native=set(e['member_sources'])|set(int(n) for n in e['post_roles'])|{s['source'] for s in e['group']}
                boxes=[cv2.boundingRect(masks[n].astype('u1')) for n in role_native if n in masks and masks[n].any()]
                if not boxes:boxes=[(0,0,raw.shape[1],raw.shape[0])]
                x0=max(0,min(b[0] for b in boxes)-20);y0=max(0,min(b[1] for b in boxes)-20)
                x1=min(raw.shape[1],max(b[0]+b[2] for b in boxes)+20);y1=min(raw.shape[0],max(b[1]+b[3] for b in boxes)+20)
                valid=np.isfinite(raw)&(raw>0);lo,hi=(np.percentile(raw[valid],[5,95]) if valid.any() else [0,1]);hi=max(lo+1,hi)
                z=np.zeros(raw.shape,'u1');z[valid]=np.rint(np.clip((raw[valid]-lo)/(hi-lo),0,1)*255).astype('u1')
                image=cv2.applyColorMap(z,cv2.COLORMAP_TURBO);image[~valid]=0
                for n,m in masks.items():
                    color=(20,20,230) if n in role_native else (190,190,190)
                    contours,_=cv2.findContours(m.astype('u1'),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE);cv2.drawContours(image,contours,-1,color,1)
                ox=(j%2)*660;oy=85+(j//2)*375;crop=image[y0:y1,x0:x1]
                scale=min(630/crop.shape[1],230/crop.shape[0]);size=(max(1,round(crop.shape[1]*scale)),max(1,round(crop.shape[0]*scale)))
                resized=cv2.resize(crop,size,interpolation=cv2.INTER_NEAREST);canvas[oy:oy+size[1],ox+15:ox+15+size[0]]=resized
                cv2.putText(canvas,f"Actual global F{p['global_frame']} / local {f}",(ox+15,oy+255),cv2.FONT_HERSHEY_SIMPLEX,.5,(20,20,20),1)
                maps={arm:{int(x['mask'][2:]):x['id'] for x in p['variants'][arm]} for arm in ARMS}
                for rowi,arm in enumerate(ARMS):
                    txt=arm+': '+', '.join(f'n{n}->{maps[arm][n]}' for n in sorted(role_native) if n in maps[arm])
                    if len(txt)>105:txt=txt[:102]+'...'
                    cv2.putText(canvas,txt,(ox+15,oy+278+rowi*20),cv2.FONT_HERSHEY_SIMPLEX,.42,(20,20,20),1,cv2.LINE_AA)
                panels.append(dict(frame=f,global_frame=p['global_frame'],time=p['time'],roi_xyxy=[x0,y0,x1,y1],
                    output_offset_xy=[ox+15,oy],display_scale=scale,raw_source=binding,
                    all_actual_published_mapping=maps,depth_limits_mm=[float(lo),float(hi)],
                    after_q_is_postseal_display_only=f>(d['frame'] if d else f)))
            path=private/f'{name}_{e["id"]}_{index}.png';assert not path.exists();assert cv2.imwrite(str(path),canvas)
            records.append(dict(artifact(path),segment=name,event=e['id'],panels=panels,
                original_depth_only=True,RGB=False,GT_raster=False,all_branch_publications_actual=True))
    finally:depth.close()
write_new(HERE/'PRIVATE_VISUALS.json',dict(figures=records,selection='CHRONOLOGICAL_FIRST_Q_FIRST_INFORMATIVE_FIRST_DEPTH_CHOICE_CHANGE_PLUS_POSTSCORE_FIRST_WRONG_ELSE_FIRST_UNRESOLVED',private_pixels=True))
print('Actual publication/depth sheets',len(records),flush=True)
