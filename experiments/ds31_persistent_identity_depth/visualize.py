"""Postseal raw depth and actual four-branch before/current/after publication."""
from common import *
from collections import defaultdict
import cv2,numpy as np
cv2.setNumThreads(1)
import score
score.verify_all();assert (RUN/'METRICS.json').is_file()
raw_module=module('ds31_postseal_raw_adapter',DS16/'source.py');RawDepth,native_masks=raw_module.RawDepth,raw_module.native_masks
private=HERE/'private';private.mkdir(exist_ok=True);records=[]
for name in SEGMENTS:
    p=RUN/name/'public';audit=read(p/'ACTION_AUDIT.json')['actions'];selected=[]
    for predicate in (lambda a:a['mapping_changed'],lambda a:a['depth_changed_same_state_selection'],lambda a:a['mapping_changed'] and a['physical']=='WRONG'):
        a=next((a for a in audit if a['arm']=='PID_DEPTH' and predicate(a)),None)
        if a and a not in selected:selected.append(a)
    if not selected:continue
    wanted={max(1,a['reference']['frame']) for a in selected}|{a['frame'] for a in selected}|{min(a['frame']+2,SEGMENTS[name][1]-SEGMENTS[name][0]+1) for a in selected}
    assigned={r['frame']:r for r in rows(input_dir(name)/'assignments.jsonl.gz') if r['frame'] in wanted}
    predictions={r['frame']:r for r in rows(p/'predictions.jsonl.gz') if r['frame'] in wanted}
    raw=RawDepth(name)
    try:
        for i,a in enumerate(selected):
            canvas=np.full((760,1350,3),250,'u1');frames=[a['reference']['frame'],a['frame'],min(a['frame']+2,SEGMENTS[name][1]-SEGMENTS[name][0]+1)]
            cv2.putText(canvas,f"{name} / n{a['source']} -> PID{a['target']} / {a['physical']} / depthchanged={a['depth_changed_same_state_selection']}",
                (15,30),cv2.FONT_HERSHEY_SIMPLEX,.55,(20,20,20),1,cv2.LINE_AA)
            panels=[];roi_boxes=[];masks_by={f:native_masks(assigned[f]) for f in frames}
            roles={a['source'],a['reference']['native_id']}
            for f,masks in masks_by.items():
                for n in roles:
                    if n in masks:roi_boxes.append(cv2.boundingRect(masks[n].astype('u1')))
            if not roi_boxes:roi_boxes=[(0,0,640,360)]
            x0=max(0,min(b[0] for b in roi_boxes)-30);y0=max(0,min(b[1] for b in roi_boxes)-30)
            x1=min(640,max(b[0]+b[2] for b in roi_boxes)+30);y1=min(360,max(b[1]+b[3] for b in roi_boxes)+30)
            for j,f in enumerate(frames):
                pr=predictions[f];raw.previous_frame=None;depth,_,_,binding=raw(pr['global_frame'],pr['time'])
                valid=np.isfinite(depth)&(depth>0);lo,hi=np.percentile(depth[valid],[5,95]) if valid.any() else (0,1);hi=max(lo+1,hi)
                z=np.zeros(depth.shape,'u1');z[valid]=np.rint(np.clip((depth[valid]-lo)/(hi-lo),0,1)*255).astype('u1')
                image=cv2.applyColorMap(z,cv2.COLORMAP_TURBO);image[~valid]=0
                masks=masks_by[f]
                for n,m in masks.items():
                    contours,_=cv2.findContours(m.astype('u1'),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
                    cv2.drawContours(image,contours,-1,(0,0,255) if n in roles else (200,200,200),1)
                    if n in roles:
                        yy,xx=np.where(m);cv2.putText(image,f'n{n}',(int(xx.mean()),int(yy.mean())),cv2.FONT_HERSHEY_SIMPLEX,.33,(0,0,0),1)
                crop=image[y0:y1,x0:x1];scale=min(425/crop.shape[1],410/crop.shape[0]);size=(max(1,round(crop.shape[1]*scale)),max(1,round(crop.shape[0]*scale)))
                ox=15+450*j;oy=65;canvas[oy:oy+size[1],ox:ox+size[0]]=cv2.resize(crop,size,interpolation=cv2.INTER_NEAREST)
                cv2.putText(canvas,f"globalF{pr['global_frame']} local{f}",(ox,500),cv2.FONT_HERSHEY_SIMPLEX,.48,(20,20,20),1)
                maps={arm:{int(x['mask'][2:]):x['id'] for x in pr['variants'][arm]} for arm in ARMS}
                for ri,arm in enumerate(ARMS):
                    relevant=[n for n,m in masks.items() if m[y0:y1,x0:x1].any()]
                    text=arm+': '+','.join(f'{n}>{maps[arm][n]}' for n in relevant)
                    chunks=[text[k:k+65] for k in range(0,len(text),65)]
                    for ci,chunk in enumerate(chunks[:2]):cv2.putText(canvas,chunk,(ox,535+ri*45+ci*16),cv2.FONT_HERSHEY_SIMPLEX,.35,(20,20,20),1)
                panels.append(dict(frame=f,global_frame=pr['global_frame'],roi_xyxy=[x0,y0,x1,y1],scale=scale,
                    actual_publication=maps,raw_binding=binding,postseal_display_only=f>a['frame']))
            path=private/f'{name}_F{a["frame"]}_{i}.png';assert not path.exists();assert cv2.imwrite(str(path),canvas)
            records.append(dict(artifact(path),segment=name,action=a,panels=panels,RGB=False,GT_raster=False))
    finally:raw.close()
write_new(HERE/'PRIVATE_VISUALS.json',dict(figures=records,selection='FIRST_CHANGED_MAPPING_FIRST_LOCAL_DEPTH_CHANGE_AND_FIRST_POSTSCORE_WRONG_PER_SOURCE',
    private_pixels=True,all_publication_actual=True,new_model_http=0,cost_usd=0))
print('Rendered actual publication sheets',len(records),flush=True)
