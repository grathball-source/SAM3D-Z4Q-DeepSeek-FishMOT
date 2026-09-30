"""Private actual before/group/first-split publication; no RGB or GT raster."""
from common import *
import numpy as np

def main():
    assert (RUN/'SCORING_SEALED.json').exists()
    import matplotlib;matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from depth_measurement import decode
    cases=[]
    for name in SEGMENTS:
        for arm,events in read(RUN/name/'public/EVENTS.json').items():
            for e in events:
                if e['q'] is not None:
                    cases.append((e['restore']['status']!='COMMIT',SEGMENTS[name][0]+e['q']-1,name,arm,e))
    chosen=[];seen=set()
    for _,_,name,arm,e in sorted(cases,key=lambda x:(x[0],x[1],x[3])):
        key=(name,e['q'])
        if key in seen:continue
        seen.add(key);chosen.append((name,arm,e))
        if len(chosen)==3:break
    results=[]
    for name,arm,e in chosen:
        points=[max(1,e['suspect_frame']-1),e['confirm_frame'] or e['suspect_frame'],e['q']]
        assignments={r['frame']:r for r in rows(input_dir(name)/'assignments.jsonl.gz') if r['frame'] in points}
        predictions={r['frame']:r for r in rows(RUN/name/'public/predictions.jsonl.gz') if r['frame'] in points}
        original=read(input_dir(name)/'sources.json')
        fig,axes=plt.subplots(3,6,figsize=(24,11))
        for y,frame in enumerate(points):
            with np.load(original[frame-1]['depth_path']) as sensor:depth=sensor['depth_mm']
            masks={int(k[2:]):decode(v) for k,v in assignments[frame]['masks'].items()}
            for x,branch in enumerate(ARMS):
                ax=axes[y,x];ax.imshow(np.ma.masked_less_equal(depth,0),vmin=600,vmax=1500,cmap='viridis')
                mapping={int(z['mask'][2:]):z['id'] for z in predictions[frame]['variants'][branch]}
                for n,mask in masks.items():
                    ax.contour(mask,levels=[.5],colors='white',linewidths=.4)
                    yy,xx=np.nonzero(mask)
                    if len(xx):ax.text(float(xx.mean()),float(yy.mean()),str(mapping[n]),fontsize=6,color='white')
                ax.set_title(f'{branch}\nF{predictions[frame]["global_frame"]}: actual published IDs',fontsize=9);ax.axis('off')
        fig.suptitle(f'{name}/{e["id"]}: pre / merge / first split; one common RAW depth display; V2 arm still uses V2 measurement')
        fig.tight_layout();path=HERE/'private/visualizations'/f'{name}_q{e["q"]}.png'
        path.parent.mkdir(parents=True,exist_ok=True);fig.savefig(path,dpi=100);plt.close(fig)
        results.append(dict(artifact=artifact(path),frames=points,selected_without_GT='earliest actual COMMIT then earliest q',event=e['id']))
    write_new(HERE/'VISUALIZATION_INVENTORY.json',dict(private_figures=results,no_RGB_or_GT_pixels=True,not_for_Git=True))
    print('Actual before/group/first-publish private figures:',len(results))
if __name__=='__main__':main()
