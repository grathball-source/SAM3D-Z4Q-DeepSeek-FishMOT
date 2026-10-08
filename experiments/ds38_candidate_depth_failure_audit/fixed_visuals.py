"""Postseal real-depth views: missing is magenta, fixed 900-1400 mm display scale."""
from common import *
from collections import defaultdict
import numpy as np,cv2
from PIL import Image,ImageDraw

def main():
    actions=read(HERE/'RESULTS.json')['actions'];requested=defaultdict(set)
    for a in actions:
        r=a['action'];requested[r['segment']].update((r['frame'],r['actual_reference']['frame']))
    images={};views=[]
    for name,frames in requested.items():
        assignments={r['frame']:r for r in rows(input_dir(name)/'assignments.jsonl.gz') if r['frame'] in frames}
        observed={r['frame']:r for r in rows(input_dir(name)/'DEPTH_OBSERVATIONS.jsonl.gz') if r['frame'] in frames}
        sensor=SOURCE.RawDepth(name)
        try:
            for f in sorted(frames):
                row=observed[f];depth,index,native,binding=sensor(row['global_frame'],row['time'])
                assert binding==row['raw_source_binding']
                missing=~np.isfinite(depth)|(depth<=0);v=np.clip((np.nan_to_num(depth)-900)/500,0,1)
                rgb=np.repeat((v*255).astype('u1')[:,:,None],3,axis=2);rgb[missing]=(255,0,255)
                masks=SOURCE.native_masks(assignments[f]);palette=((255,70,70),(70,255,70),(70,130,255),(255,200,50))
                for n,m in masks.items():
                    contours,_=cv2.findContours(m.astype('u1'),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
                    cv2.drawContours(rgb,contours,-1,palette[n%4],1)
                im=Image.fromarray(rgb).resize((1280,720));draw=ImageDraw.Draw(im)
                for n,m in masks.items():
                    yy,xx=np.nonzero(m)
                    if len(xx):draw.text((2*float(xx.mean()),2*float(yy.mean())),f'n{n}',fill='white',stroke_width=1,stroke_fill='black')
                draw.text((6,6),f'{name} local F{f}; black=900mm or nearer, white=1400mm or farther, MAGENTA=MISSING',fill='white',stroke_width=1,stroke_fill='black')
                path=HERE/'private'/f'FIXED_SCALE_{name}_F{f}.png';im.save(path);images[name,f]=im
                views.append(dict(file=artifact(path),source_binding=binding,missing_pixels=int(missing.sum()),
                    display_scale_mm=[900,1400],contour_color_not_identity_evidence=True))
        finally:sensor.close()
    cases=[]
    for a in actions:
        r=a['action'];name=r['segment'];q=r['frame'];ref=r['actual_reference']
        im=Image.new('RGB',(1280,1470),'white');im.paste(images[name,ref['frame']],(0,30));im.paste(images[name,q],(0,750))
        ImageDraw.Draw(im).text((6,6),f'Global F{r["global_frame"]} {a["physical"]}; actual old n{ref["native_id"]}/p{r["target"]} -> q n{r["native"]}; colors label observations only',fill='black')
        path=HERE/'private'/f'FIXED_CASE_global{r["global_frame"]}_n{r["native"]}.png';im.save(path)
        cases.append(dict(action_id=r['action_id'],physical=a['physical'],figure=artifact(path)))
    sheets=[]
    for physical in ('WRONG','CORRECT','UNSCORABLE'):
        group=[c for c in cases if c['physical']==physical]
        for offset in range(0,len(group),4):
            im=Image.new('RGB',(1280,1510),'white');draw=ImageDraw.Draw(im)
            draw.text((6,6),f'{physical}: cases {offset+1}-{min(offset+4,len(group))}; all cases retained; raw original depth; magenta=MISSING',fill='black')
            for i,c in enumerate(group[offset:offset+4]):
                panel=Image.open(c['figure']['path']).resize((640,735));im.paste(panel,((i%2)*640,30+(i//2)*735))
            path=HERE/'private'/f'CONTACT_{physical}_{offset//4+1}.png';im.save(path);sheets.append(dict(physical=physical,file=artifact(path),cases=[c['action_id'] for c in group[offset:offset+4]]))
    save('FIXED_SCALE_PRIVATE_VISUALS.json',dict(views=views,cases=cases,contact_sheets=sheets,
        legacy_gray_views_preserved=True,old_gray_black_was_ambiguous_missing_vs_low_depth=True,
        all_new_figures_postseal_diagnostic=True,RGB=False,GT_raster=False))
    print('FIXED VISUALS',len(views),len(cases),len(sheets),flush=True)

if __name__=='__main__': main()
