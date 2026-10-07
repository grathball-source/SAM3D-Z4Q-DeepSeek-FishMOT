"""Published numeric summaries plus private actual raw-depth/mask comparisons."""
from common import *
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
SENSOR=module('ds37_frozen_raw_sensor',ROOT/'experiments/ds34_bidirectional_event_restore/sensor.py')
SOURCE=SENSOR._source()

def main():
    from score import verify_all
    verify_all();result=read(RUN/'METRICS.json');audit=read(RUN/'MECHANISM_AUDIT.json')
    public=HERE/'visuals';private=HERE/'private/cases'
    public.mkdir(exist_ok=True);private.mkdir(parents=True,exist_ok=False)
    fig,axes=plt.subplots(2,1,figsize=(11,7),layout='constrained');names=list(SEGMENTS)
    for offset,arm in enumerate(ARMS):
        x=np.arange(len(names))+(offset-1.5)*.19
        axes[0].bar(x,[result['segments'][n]['metrics'][arm]['IDF1'] for n in names],width=.19,label=arm)
        axes[1].bar(x,[result['segments'][n]['metrics'][arm]['IDSW'] for n in names],width=.19,label=arm)
    for ax in axes:ax.set_xticks(np.arange(len(names)),names,rotation=25,ha='right');ax.grid(axis='y',alpha=.2)
    axes[0].set_ylabel('IDF1 (%)');axes[1].set_ylabel('ID switches (all public IDs)');axes[0].legend(fontsize=8,ncol=2)
    fig.suptitle('DS37 same saved source / raw depth — L3 and LW references are weak')
    fig.savefig(public/'METRICS.svg');plt.close(fig)
    q=list(rows(RUN/'EDGE_AUDIT.jsonl.gz'));fig,axes=plt.subplots(1,2,figsize=(11,5),layout='constrained')
    for arm,ax in zip(VETO_ARMS,axes,strict=True):
        chosen=[v for v in q if v['arm']==arm and v['eligible'] and v['residual_mm'] is not None]
        for grade,color in [('SAME','tab:blue'),('DIFFERENT','tab:red'),('UNSCORABLE','gray')]:
            points=[v for v in chosen if v['physical_bank_relation']==grade]
            ax.scatter([v['threshold_mm'] for v in points],[v['residual_mm'] for v in points],s=15,alpha=.6,c=color,label=f'{grade} n={len(points)}')
        limit=max([v['residual_mm'] for v in chosen]+[v['threshold_mm'] for v in chosen]+[60.])
        ax.plot([0,limit],[0,limit],ls='--',c='black');ax.set(title=arm,xlabel='Frozen veto threshold mm',ylabel='Actual core / predicted level residual mm')
        ax.legend(fontsize=8);ax.grid(alpha=.2)
    fig.suptitle('Only original eligible edges; labels read after prediction seal; correlated queries')
    fig.savefig(public/'ELIGIBLE_CONFLICTS.svg');plt.close(fig)
    cases=read(HERE/'VISUAL_CASES.json')['cases'];inventory=[]
    for name in SEGMENTS:
        selected=[c for c in cases if c['segment']==name]
        if not selected:continue
        wanted={f for c in selected for f in (c['anchor']['frame'],max(1,c['frame']-1),c['frame'],min(SEGMENTS[name][1]-SEGMENTS[name][0]+1,c['frame']+1))}
        assignments={r['frame']:r for r in rows(input_dir(name)/'assignments.jsonl.gz') if r['frame'] in wanted}
        published={r['frame']:r for r in rows(RUN/name/'public/predictions.jsonl.gz') if r['frame'] in wanted}
        sensor=SOURCE.RawDepth(name)
        try:
            for case in selected:
                frames=[case['anchor']['frame'],max(1,case['frame']-1),case['frame'],min(SEGMENTS[name][1]-SEGMENTS[name][0]+1,case['frame']+1)]
                fig,axes=plt.subplots(3,4,figsize=(16,10),layout='constrained');source=[]
                for col,f in enumerate(frames):
                    pr=published[f];g=pr['global_frame'];d,ix,nat,b=sensor(g,pr['time'])
                    masks=SOURCE.native_masks(assignments[f]);target=case['anchor']['native_id'] if col==0 else case['native']
                    relevant=masks.get(target);yy,xx=np.nonzero(relevant) if relevant is not None else (np.array([]),np.array([]))
                    if len(xx):x0,x1=max(0,int(xx.min())-35),min(640,int(xx.max())+36);y0,y1=max(0,int(yy.min())-35),min(360,int(yy.max())+36)
                    else:x0,x1,y0,y1=0,640,0,360
                    cut=d[y0:y1,x0:x1];valid=cut[cut>0];lo,hi=np.quantile(valid,[.02,.98]) if len(valid) else (0,1)
                    source.append(dict(frame=f,global_frame=g,source_binding=b,assignment_row_sha256=row_sha(assignments[f]),prediction_row_sha256=row_sha(pr)))
                    for row,arm in enumerate(ARMS[1:]):
                        ax=axes[row,col];ax.imshow(np.where(cut>0,cut,np.nan),cmap='viridis',vmin=lo,vmax=max(hi,lo+1),extent=(x0,x1,y1,y0))
                        ids={int(o['mask'][2:]):o['id'] for o in pr['variants'][arm]}
                        for native,mask in masks.items():
                            if not mask[y0:y1,x0:x1].any():continue
                            ax.contour(mask.astype(float),levels=[.5],colors=['red' if native==target else 'white'],linewidths=.8)
                            my,mx=np.nonzero(mask)
                            ax.text(float(np.median(mx)),float(np.median(my)),f'n{native}→p{ids[native]}',fontsize=6,color='black',bbox=dict(facecolor='white',alpha=.7,pad=.5),clip_on=True)
                        ax.set_xlim(x0,x1);ax.set_ylim(y1,y0);ax.set_title(f'{arm}\nF{g} ({"anchor" if col==0 else "before" if col==1 else "decision" if col==2 else "after"})',fontsize=9)
                fig.suptitle(f'{name} / F{case["frame"]} / {case["grade"]}\nActual raw depth mm and published IDs; no RGB or GT raster; later frame shown only postseal',fontsize=11)
                path=private/f'{len(inventory)+1:03d}.png';fig.savefig(path,dpi=110);plt.close(fig)
                inventory.append(dict(case=case,artifact=artifact(path),source_frames=source))
                print('PRIVATE_VISUAL',len(inventory),name,case['frame'],flush=True)
        finally:sensor.close()
    write_new(HERE/'PRIVATE_VISUALS.json',dict(cases=inventory,pixels_private=True,RGB=False,GT_raster=False,
        reproduction='execute.py visuals.py after seals/scoring, using pinned DS14 saved masks and original RawDepth dependencies'))
    write_new(HERE/'PUBLIC_VISUALS.json',dict(files=[artifact(p) for p in sorted(public.glob('*.svg'))],private_cases=len(inventory)))

if __name__=='__main__':main()
