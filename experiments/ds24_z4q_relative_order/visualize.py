"""Postseal only: draw actual published mappings on private same-frame RGB/depth."""
from common import *
import cv2,numpy as np
from source import RawDepth,native_masks
cv2.setNumThreads(1)

def rgb(sensor,g,now):
    meta=sensor.metadata[g]
    if sensor.kind=='FEEDING':path=DATA/meta['rgb_original'];expected=meta['source_rgb_sha256'];timestamp=meta['rgb_timestamp_us']
    elif sensor.kind=='FISHSA':path=sensor.base/meta['rgb_original'];expected=meta['source_rgb_sha256'];timestamp=meta['color_timestamp_us']
    else:path=Path(meta['rgb_source']);expected=meta['rgb_sha256'];timestamp=meta['rgb_timestamp_us']
    pin=artifact(path);assert pin['sha256']==expected and abs(timestamp/1e6-now)<1e-6
    original=cv2.imread(str(path));assert original.shape==(1080,1920,3)
    return cv2.resize(original,(640,360),interpolation=cv2.INTER_AREA),pin

def render(name,case):
    public=RUN/name/'public';verify_seal(name);q=case['frame'];anchor=case['anchor']['frame']
    middle=(case.get('comparison',{}).get('anonymous_risk_interval') or [{'frame':max(anchor,min(q-1,anchor+1))}])[0]['frame']
    frames=sorted(set((anchor,middle,q)))
    predictions={r['frame']:r for r in rows(public/'predictions.jsonl.gz') if r['frame'] in frames}
    assignments={r['frame']:r for r in rows(input_dir(name)/'assignments.jsonl.gz') if r['frame'] in frames}
    sensor=RawDepth(name);images={};depths={};masks={};pins=[];bindings=[]
    try:
        for f in frames:
            p=predictions[f];g=p['global_frame'];now=p['time']
            images[f],pin=rgb(sensor,g,now);pins.append(pin)
            arrays=sensor(g,now);depths[f]=arrays[0];masks[f]=native_masks(assignments[f]);bindings.append(arrays[3])
    finally:sensor.close()
    columns=(anchor,middle,q);canvas=np.full((3*405+445,3*640,3),248,'u1')
    mapping_records=[]
    for i,arm in enumerate(ARMS):
        for j,f in enumerate(columns):
            image=images[f].copy();mapping={int(x['mask'][2:]):x['id'] for x in predictions[f]['variants'][arm]}
            for n,mask in masks[f].items():
                k=mapping[n];color=(50+(k*67)%180,50+(k*97)%180,50+(k*137)%180)
                contours,_=cv2.findContours(mask.astype('u1'),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
                cv2.drawContours(image,contours,-1,color,1)
                yy,xx=np.nonzero(mask)
                if len(xx):cv2.putText(image,f'n{n}:p{k}',(int(np.mean(xx)),int(np.mean(yy))),cv2.FONT_HERSHEY_SIMPLEX,.36,color,1,cv2.LINE_AA)
            panel=cv2.copyMakeBorder(image,45,0,0,0,cv2.BORDER_CONSTANT,value=(248,248,248))
            label=f'{arm} | g{predictions[f]["global_frame"]} | '+('BANK REFERENCE' if j==0 else 'RISK' if j==1 else 'QUERY')
            cv2.putText(panel,label,(10,27),cv2.FONT_HERSHEY_SIMPLEX,.48,(20,20,20),1,cv2.LINE_AA)
            canvas[i*405:(i+1)*405,j*640:(j+1)*640]=panel
            mapping_records.append(dict(frame=f,global_frame=predictions[f]['global_frame'],arm=arm,actual_publication=mapping))
    z=depths[q];valid=np.isfinite(z)&(z>0);lo,hi=map(float,np.quantile(z[valid],[.01,.99])) if valid.any() else (0.,1.)
    heat=cv2.applyColorMap(np.clip((z-lo)/max(1.,hi-lo)*255,0,255).astype('u1'),cv2.COLORMAP_TURBO);heat[~valid]=255
    current=images[q].copy()
    for n in (case['source'],case.get('partner')):
        if n is None or n not in masks[q]:continue
        contours,_=cv2.findContours(masks[q][n].astype('u1'),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(current,contours,-1,(0,0,255),2);cv2.drawContours(heat,contours,-1,(0,0,0),2)
    canvas[3*405+45:3*405+405,:640]=current;canvas[3*405+45:3*405+405,640:1280]=heat
    cv2.putText(canvas,'Private RGB / actual raw camera-Z; labels are published claims, not GT',(10,3*405+29),cv2.FONT_HERSHEY_SIMPLEX,.65,(20,20,20),1,cv2.LINE_AA)
    note=[name,f'query global {predictions[q]["global_frame"]}, source {case["source"]} -> target {case["target"]}',
        case['reason'],f'raw Z display {lo:.0f}..{hi:.0f} mm','No GT raster / no fabricated layers','All three states are sealed publications']
    if 'comparison' in case:
        c=case['comparison'];note+= [f'pre p(A nearer) = {c.get("pre_probability_A_nearer_at_q",0):.4f}',f'post p(A nearer) = {c.get("current_probability_A_nearer",0):.4f}',f'reference gap = {c.get("real_gap_seconds",0):.3f} sec']
    for k,s in enumerate(note):cv2.putText(canvas,s[:67],(1290,3*405+80+k*29),cv2.FONT_HERSHEY_SIMPLEX,.45,(20,20,20),1,cv2.LINE_AA)
    path=HERE/'private'/f'{name}_g{predictions[q]["global_frame"]}_n{case["source"]}.png';path.parent.mkdir(exist_ok=True)
    assert not path.exists() and cv2.imwrite(str(path),canvas)
    return dict(case={k:v for k,v in case.items() if k!='comparison'},artifact=artifact(path),
        pixel_figures_private=True,actual_published_mappings=mapping_records,RGB_sources=pins,
        raw_source_bindings=bindings,GT_raster=False,used_for_prediction=False)

def main():
    assert read(RUN/'METRICS.json')['status']=='SCORED_AFTER_ALL_EIGHT_PREDICTION_AND_ACCESS_SEALS'
    selections={}
    for name in SEGMENTS:
        for r in rows(RUN/name/'public/ORDER_CHECKS.jsonl.gz'):
            for x in r['checks']:
                if name=='feeding_000000_000199' and r['global_frame']==159 and x['native_id']==26 and x['public_id']==16:
                    selections[name]=dict(frame=r['frame'],source=26,target=16,anchor=x['anchor'],reason=x['reason'])
                if name not in selections:
                    c=next((v for v in x['comparisons'] if v['reason']=='WEAK_PROPAGATED_OR_CURRENT_ORDER'),None)
                    if c:selections[name]=dict(frame=r['frame'],source=x['native_id'],target=x['public_id'],anchor=x['anchor'],
                        reason=c['reason'],partner=c['partner_native'],comparison=c)
    figures=[render(n,c) for n,c in selections.items()]
    write_new(HERE/'PRIVATE_VISUALS.json',dict(status='POSTSEAL_ACTUAL_PUBLICATIONS_RENDERED',figures=figures,
        selection='F159 specified input diagnostic and earliest numerically computed weak pair per source; no GT selection',
        actual_images_not_tracking_features=True,private_pixels_excluded_from_git=True))
    print('Private actual publication comparisons',len(figures),flush=True)

if __name__=='__main__':main()
