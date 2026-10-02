"""Postseal real published mappings and full mask depth layers, local pixels only."""
from common import *
import collections
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from source import RawDepth,native_masks

def main():
    assert read(RUN/'SCORE_PROVENANCE.json')['reference_opened_after_all_seals']
    out=HERE/'private/visuals';out.mkdir(parents=True,exist_ok=True)
    cases=[]
    for name in SEGMENTS:
        first=next((x for x in rows(RUN/name/'public/MIXED_DEPTH.jsonl.gz') if any(c[role]['mixture_flag'] for c in x['objects'].values() for role in ('whole','birth_core','core'))),None)
        if first and (name.startswith('feeding_') or name=='L3'):cases.append((name,first['frame'],'FIRST_MEASURED_POTENTIAL_MIXTURE_NOT_IDENTITY_TRUTH'))
        previous=None
        for transaction in rows(RUN/name/'public/TRANSACTIONS.jsonl.gz'):
            if transaction['arm']=='ACTIVITY_ORDER':previous=transaction
            if transaction['arm']=='MIXED_ORDER':
                assert previous and previous['frame']==transaction['frame']
                if transaction['actual_published_mapping']!=previous['actual_published_mapping']:
                    cases.append((name,transaction['frame'],'FIRST_ACTUAL_MIXTURE_GUARD_MAPPING_DIFFERENCE'))
                    break
    cases.append(('L3',3025,'PREDECLARED_ACTIVITY_FAILURE_DIAGNOSTIC'))
    # Deterministic first occurrence per segment/reason; not best-case selection.
    inventory=[]
    for name,q,reason in cases:
        frames=sorted(set((max(1,q-5),max(1,q-1),q)))
        base=RUN/name/'public';pred={x['frame']:x for x in rows(base/'predictions.jsonl.gz') if x['frame'] in frames}
        assignments={x['frame']:x for x in rows(input_dir(name)/'assignments.jsonl.gz') if x['frame'] in frames}
        mixed={x['frame']:x for x in rows(base/'MIXED_DEPTH.jsonl.gz') if x['frame'] in frames}
        fig,axes=plt.subplots(len(ARMS),len(frames),figsize=(15,18),squeeze=False)
        sensor=RawDepth(name)
        for j,frame in enumerate(frames):
            row=pred[frame];depth,index,native,binding=sensor(row['global_frame'],row['time']);masks=native_masks(assignments[frame])
            vals=depth[np.isfinite(depth)&(depth>0)];lo,hi=np.quantile(vals,[.02,.98]) if len(vals) else (0,1)
            for i,arm in enumerate(ARMS):
                ax=axes[i,j];ax.imshow(np.where(depth>0,depth,np.nan),cmap='viridis',vmin=lo,vmax=hi)
                mapping={int(x['mask'][2:]):x['id'] for x in row['variants'][arm]}
                for n,mask in masks.items():
                    ax.contour(mask,levels=[.5],colors='white',linewidths=.4)
                    ys,xs=np.where(mask);ax.text(xs.mean(),ys.mean(),f'n{n}:p{mapping[n]}',fontsize=6,color='red',bbox=dict(facecolor='white',alpha=.65,pad=.3))
                ax.set_title(f'{arm} / F{row["global_frame"]}',fontsize=10);ax.axis('off')
        sensor.close();fig.suptitle(f'{name}: {reason}; actual first publication, no RGB/GT raster',fontsize=12)
        fig.tight_layout(rect=(0,0,1,.98));file=out/f'{name}_q{q}_actual.png';fig.savefig(file,dpi=130);plt.close(fig)
        inventory.append(dict(segment=name,frame=q,reason=reason,artifact=artifact(file),source_rows=[mixed[x]['source_binding'] for x in frames]))
        cert=mixed[q];objects=list(cert['objects'].items());fig,axes=plt.subplots(max(1,len(objects)),3,figsize=(16,max(3,2.5*len(objects))),squeeze=False)
        for i,(n,c) in enumerate(objects):
            for j,view in enumerate(('whole','birth_core','core')):
                rep=c[view];layers=rep['layers'];ax=axes[i,j]
                ax.bar(range(len(layers)),[x['measured_support_fraction'] for x in layers])
                ax.set_xticks(range(len(layers)),[f'{x["median"]:.1f}mm' for x in layers],rotation=35,fontsize=7)
                ax.set_title(f'n{n} {view}: {rep["status"]}; scalar ownership UNKNOWN',fontsize=9)
                ax.set_ylim(0,1);ax.set_ylabel('unique-source fraction')
        fig.tight_layout();file=out/f'{name}_q{q}_layers.png';fig.savefig(file,dpi=120);plt.close(fig)
        inventory.append(dict(segment=name,frame=q,reason='ALL_MEASURED_LAYERS_NO_SELECTED_PEAK',artifact=artifact(file),numeric_fact=artifact(base/'MIXED_DEPTH.jsonl.gz')))
    write_new(HERE/'PRIVATE_VISUALS.json',dict(status='ACTUAL_PUBLISHED_MAPS_AND_LAYER_DISTRIBUTIONS',selection_policy='First potential mixture/first guard mapping difference per predefined segment; predeclared L3 activity failure',figures=inventory,private_pixels=True,GT_raster=False,RGB=False))
    print('private visual figures',len(inventory))
if __name__=='__main__':main()
