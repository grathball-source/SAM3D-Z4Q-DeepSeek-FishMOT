"""Post-seal numeric performance chart and restricted actual-depth case views."""
from common import *
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from depth_measurement import decode
from source import RawDepth

def main():
    result=read(RUN/'METRICS.json');assert result['status'].startswith('SCORED_AFTER_ALL')
    names=['fishsa_development_8400','fishsa_validation_2888','Feeding','L3','LW']
    items=[result['segments'][n] if n!='Feeding' else result['feeding_pooled'] for n in names]
    fig,axes=plt.subplots(1,3,figsize=(13,4),layout='constrained')
    for axis,key in zip(axes,('IDF1','HOTA','AssA')):
        y=np.arange(len(names));axis.barh(y-.16,[r['metrics']['SAM3_NATIVE'][key] for r in items],.3,label='SAM3 native',color='#6680a0')
        axis.barh(y+.16,[r['metrics']['R12_RAW'][key] for r in items],.3,label='Frozen R12 raw',color='#20a088')
        axis.set_yticks(y,['FishSA8400','FishSA2888','Feeding1471','L3 (weak ref)','LW (weak ref)']);axis.set_xlim(0,100);axis.set_title(key+' (%)');axis.invert_yaxis()
        for i,r in enumerate(items):axis.text(100.5,i,f"{r['delta'][key]:+.3f}",va='center',fontsize=9)
    axes[0].legend(loc='lower right',fontsize=8);fig.suptitle('All20098 frames; original raw depth; same-source native comparison')
    (HERE/'figures').mkdir(exist_ok=True);fig.savefig(HERE/'figures/PERFORMANCE.svg');plt.close(fig)
    inventory=[];chosen=[]
    for name in SEGMENTS:
        public=RUN/name/'public';audit=read(public/'EVENT_AUDIT.json');cases=[]
        # Diagnostic selection after scoring, never an input/event selection policy.
        outcomes=set()
        for e in audit['group_events']:
            if e.get('q') and e['physical'] not in outcomes:
                cases.append(('group',e['q'],e['physical']));outcomes.add(e['physical'])
        for e in audit['birth_commits']:
            if ('birth',e['physical']) not in outcomes:
                cases.append(('birth',e['frame'],e['physical']));outcomes.add(('birth',e['physical']))
        if not cases:continue
        assignment={r['frame']:r for r in rows(input_dir(name)/'assignments.jsonl.gz')}
        prediction={r['frame']:r for r in rows(public/'predictions.jsonl.gz')}
        for kind,q,outcome in cases:
            reader=RawDepth(name);frames=sorted(set((max(1,q-1),q,min(SEGMENTS[name][1]-SEGMENTS[name][0]+1,q+1))))
            fig,axes=plt.subplots(2,len(frames),figsize=(5*len(frames),6),squeeze=False,layout='constrained')
            bindings=[]
            for col,f in enumerate(frames):
                p=prediction[f];depth,index,native,binding=reader(p['global_frame'],p['time']);bindings.append(binding)
                valid=depth[np.isfinite(depth)&(depth>0)];lo,hi=np.quantile(valid,[.02,.98]) if len(valid) else (0,1)
                for row,arm in enumerate(ARMS):
                    ax=axes[row,col];ax.imshow(np.ma.masked_where(depth<=0,depth),vmin=lo,vmax=hi,cmap='viridis')
                    for obj in p['variants'][arm]:
                        mask=decode(assignment[f]['masks'][obj['mask']]);y,x=np.where(mask)
                        ax.contour(mask.astype('u1'),levels=[.5],colors=['white'],linewidths=.6)
                        ax.text(float(x.mean()),float(y.mean()),str(obj['id']),color='red',fontsize=8)
                    ax.set_title(f'{arm} original F{p["global_frame"]}');ax.set_xlim(0,640);ax.set_ylim(360,0);ax.axis('off')
            fig.suptitle(f'{name} {kind} q={q}: {outcome}; raw sensor/contours, no RGB; postseal q+1 diagnostic')
            path=HERE/'private/visuals'/f'{name}_{kind}_{q}_{outcome}.png';path.parent.mkdir(parents=True,exist_ok=True)
            fig.savefig(path,dpi=130);plt.close(fig);reader.close()
            chosen.append(dict(segment=name,kind=kind,q=q,outcome=outcome,frames=frames,artifact=artifact(path),source_bindings=bindings))
            inventory.append(artifact(path))
    write_new(HERE/'RESTRICTED_VISUALS.json',dict(selection='First each outcome per segment AFTER_ALL_SCORING; no predictor feedback',cases=chosen,
        restricted_artifacts=inventory,private_raw_pixels=True,RGB_read=False,GT_raster_read=False))
    print('Public numeric SVG; private true-depth cases',len(chosen),flush=True)
if __name__=='__main__':main()
