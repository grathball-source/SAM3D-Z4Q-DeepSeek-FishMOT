"""Postscore failure figures: actual depth and published IDs, no new predictions."""
from common import *
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from source import RawDepth,native_masks

def main():
    assert read(RUN/'SCORE_PROVENANCE.json')['reference_opened_after_all_seals']
    cases=[('fishsa_development_8400',3902,7,'ORIGINAL_BIRTH_BLOCKED_BY_IDENTITY_UNKNOWN'),
           ('fishsa_validation_2888',2188,8,'ORIGINAL_BIRTH_DELAYED_49_FRAMES'),
           ('feeding_001201_001906',264,176,'WRONG_TARGET_MIGRATION_AT_GLOBAL1464')]
    out=HERE/'private/visuals';out.mkdir(parents=True,exist_ok=True);inventory=[]
    for name,q,subject,reason in cases:
        public=RUN/name/'public';seal=read(public/'PREDICTIONS_SEALED.json')
        assert sha(public/'predictions.jsonl.gz')==seal['artifacts_sha256']['predictions.jsonl.gz']
        selected=[q-5,q-1,q]
        predictions={r['frame']:r for r in rows(public/'predictions.jsonl.gz') if r['frame'] in selected}
        assignments={r['frame']:r for r in rows(input_dir(name)/'assignments.jsonl.gz') if r['frame'] in selected}
        fig,axes=plt.subplots(len(ARMS),3,figsize=(16,18),squeeze=False);sensor=RawDepth(name)
        facts=[]
        try:
            for j,frame in enumerate(selected):
                row=predictions[frame];depth,index,native,binding=sensor(row['global_frame'],row['time'])
                facts.append(binding);masks=native_masks(assignments[frame])
                values=depth[np.isfinite(depth)&(depth>0)]
                lo,hi=np.quantile(values,[.02,.98]) if len(values) else (0,1)
                for i,arm in enumerate(ARMS):
                    ax=axes[i,j];ax.imshow(np.where(depth>0,depth,np.nan),cmap='viridis',vmin=lo,vmax=hi)
                    mapping={int(x['mask'][2:]):x['id'] for x in row['variants'][arm]}
                    for n,mask in masks.items():
                        ys,xs=np.where(mask)
                        if not len(xs):continue
                        ax.contour(mask,levels=[.5],colors='red' if n==subject else 'white',linewidths=1.2 if n==subject else .5)
                        ax.text(xs.mean(),ys.mean(),f'n{n}:p{mapping[n]}',fontsize=8 if n==subject else 6,
                            color='red',bbox=dict(facecolor='white',alpha=.75,pad=.4))
                    ax.set_title(f'{arm} / F{row["global_frame"]}',fontsize=10);ax.axis('off')
        finally:sensor.close()
        fig.suptitle(f'{name}: {reason}; highlighted source n{subject}; actual first publication',fontsize=12)
        fig.tight_layout(rect=(0,0,1,.98));file=out/f'{name}_failure_q{q}.png'
        fig.savefig(file,dpi=140);plt.close(fig)
        inventory.append(dict(segment=name,local_q=q,subject_source=subject,reason=reason,
            artifact=artifact(file),raw_bindings=facts,prediction=artifact(public/'predictions.jsonl.gz'),
            current_published={arm:{int(x['mask'][2:]):x['id'] for x in predictions[q]['variants'][arm]} for arm in ARMS}))
    write_new(HERE/'FAILURE_VISUALS.json',dict(status='POSTSCORE_ACTUAL_FAILURE_MAPS',figures=inventory,
        selection_policy='Two source-state failures plus score-diagnosed Feeding candidate migration; diagnostic only, no GT selection for predictions',
        RGB=False,GT_raster=False,private_pixels=True,new_predictions=0,new_model_http=0))
    print('3 additional actual failure figures')

if __name__=='__main__':main()
