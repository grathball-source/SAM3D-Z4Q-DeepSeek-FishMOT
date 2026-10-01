"""One final readable v2 publication detail; keep all prior images immutable."""
from pathlib import Path
import sys, hashlib
sys.dont_write_bytecode=True
from common import HERE,RUN,ARMS,read,rows,artifact,write_new


def main():
    zoom_path=HERE/'diagnosis/PUBLICATION_ZOOM_INVENTORY.json'
    zoom=read(zoom_path)
    assert all(artifact(Path(entry['path']))==entry for entry in
        [zoom['code'],zoom['original_inventory'],zoom['all_prediction_seal'],zoom['scoring_seal'],zoom['private_pixel_artifact']])
    original=read(zoom['original_inventory']['path'])
    segment=zoom['case']['segment'];public=RUN/segment/'public'
    bound=original['bindings']['segments'][segment]
    assert artifact(Path(bound['assignments']['path']))==bound['assignments']
    assert artifact(Path(bound['files']['predictions.jsonl.gz']['path']))==bound['files']['predictions.jsonl.gz']
    assert artifact(Path(bound['files']['EVENTS.json']['path']))==bound['files']['EVENTS.json']
    samples=zoom['source_and_row_bindings'];frames={sample['local_frame'] for sample in samples}
    assert {sample['global_frame'] for sample in samples}=={1024,1025,1027}
    predictions={row['frame']:row for row in rows(public/'predictions.jsonl.gz') if row['frame'] in frames}
    assignments={row['frame']:row for row in rows(Path(bound['assignments']['path'])) if row['frame'] in frames}
    event=next(e for e in read(public/'EVENTS.json')['F9_RESTORED'] if e['id']==zoom['case']['event'])
    focus=set(event['member_sources'])|set(map(int,event['post_first_observations']))
    focus.update(e['source'] for e in event['group_observations'] if e['frame']<=event['q'])
    assert focus=={95,137}
    import numpy as np
    import cv2
    cv2.setNumThreads(1)
    from depth_measurement import decode
    from restored_source import RestoredDepth
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.colors import LogNorm
    from matplotlib.cm import ScalarMappable
    reader=RestoredDepth();data={};union=np.zeros((360,640),bool)
    try:
        for sample in samples:
            masks={int(k[2:]):decode(value) for k,value in assignments[sample['local_frame']]['masks'].items()}
            prediction=predictions[sample['local_frame']]
            assert all({int(o['mask'][2:]):o['id'] for o in prediction['variants'][arm]}
                =={int(k):v for k,v in sample['published'][arm].items()} for arm in ARMS)
            depth,_,meta=reader(sample['global_frame'])
            assert meta['native_row']==sample['v2_row'] and artifact(Path(meta['native_path']))==sample['v2_native']
            assert hashlib.sha256(reader.current_source_index.astype('<i4').tobytes()).hexdigest()==sample['v2_source_index_sha256']
            for native in focus&set(masks):union|=masks[native]
            data[sample['role']]=(depth,masks,prediction,sample['global_frame'])
    finally:reader.close()
    yy,xx=np.nonzero(union);margin=24
    x0,x1=max(0,int(xx.min())-margin),min(640,int(xx.max())+margin+1)
    y0,y1=max(0,int(yy.min())-margin),min(360,int(yy.max())+margin+1)
    assert [y1-y0,x1-x0]==zoom['ROI_shape']
    region=np.s_[y0:y1,x0:x1]
    positive=np.concatenate([depth[region][np.isfinite(depth[region])&(depth[region]>0)] for depth,_,_,_ in data.values()])
    norm=LogNorm(vmin=float(positive.min()),vmax=float(positive.max()))
    path=HERE/'private/publication/F1027_ACTUAL_PUBLICATION_CALLOUT.png'
    out=HERE/'diagnosis/PUBLICATION_CALLOUT_INVENTORY.json'
    assert not path.exists() and not out.exists()
    fig,axes=plt.subplots(4,3,figsize=(16,15),constrained_layout=True)
    facts=[]
    for row,arm in enumerate(ARMS):
        for col,role in enumerate(('before','merge','q')):
            depth,masks,prediction,frame=data[role];ax=axes[row,col]
            actual={int(o['mask'][2:]):o['id'] for o in prediction['variants'][arm]}
            inside=[n for n,m in masks.items() if np.any(m[region])]
            ax.imshow(np.ma.masked_where(~np.isfinite(depth)|(depth<=0),depth),norm=norm,cmap='viridis')
            for native in inside:
                color='#00e5ff' if native==137 else '#ff8c00' if native==95 else '#eeeeee'
                contours,_=cv2.findContours(masks[native].astype('u1'),cv2.RETR_LIST,cv2.CHAIN_APPROX_SIMPLE)
                for contour in contours:
                    contour=contour[:,0,:]
                    if len(contour)>1:ax.plot(*contour.T,color=color,linewidth=1.8 if native in focus else .8)
                cy,cx=np.nonzero(masks[native][region]);center=(float(cx.mean())+x0,float(cy.mean())+y0)
                if native not in focus:
                    ax.text(*center,f'n{native}\nID {actual[native]}',color='white',fontsize=7,ha='center',va='center',
                        bbox=dict(facecolor='black',edgecolor='none',alpha=.6,pad=.4),zorder=3)
            for native in sorted(focus):
                cy,cx=np.nonzero(masks[native][region]);center=(float(cx.mean())+x0,float(cy.mean())+y0)
                top=native==95;color='#ff8c00' if top else '#00e5ff'
                ax.annotate(('post ' if role=='q' else 'source ')+str(native)+f'\npublic {actual[native]}',xy=center,
                    xytext=(x1-4,y0+5) if top else (x0+4,y1-5),ha='right' if top else 'left',va='top' if top else 'bottom',
                    fontsize=11,fontweight='bold',color=color,zorder=10,
                    bbox=dict(facecolor='black',edgecolor=color,alpha=.9,pad=2),
                    arrowprops=dict(arrowstyle='->',color=color,linewidth=1.4))
            ax.set_xlim(x0-.5,x1-.5);ax.set_ylim(y1-.5,y0-.5)
            ax.set_title(f'{arm} / {role} F{frame}',fontsize=11)
            ax.tick_params(labelsize=8)
            ax.set_xlabel(f'all local masks {len(inside)}; saved native V2',fontsize=9)
            facts.append(dict(arm=arm,role=role,global_frame=frame,all_local_masks=len(inside),
                source137_public=actual[137],source95_public=actual[95]))
    fig.colorbar(ScalarMappable(norm=norm,cmap='viridis'),ax=axes,shrink=.8,label='recorded camera-Z mm; full local positive value range')
    fig.suptitle('F1027 actual publication: q swaps IDs only in D10_RESTORED\n'
        'Before F1024 / recorded group F1025 / first split q F1027; actual predictions only, no relabeling.\n'
        'Source-mask union across these three <=q times + fixed 24 px margin; all local neighbors retained.\n'
        'No RGB / GT raster. V2 has upstream RGB + future support; surface ownership and calibration UNKNOWN.',fontsize=14)
    fig.savefig(path,dpi=160);plt.close(fig)
    write_new(out,dict(status='FINAL_READABLE_ACTUAL_PUBLICATION_DETAIL',code=artifact(Path(__file__)),
        original_zoom_inventory=artifact(zoom_path),original_full_inventory=zoom['original_inventory'],
        all_prediction_seal=zoom['all_prediction_seal'],scoring_seal=zoom['scoring_seal'],
        source_and_row_bindings=samples,pixel_artifact=artifact(path),private_pixels_not_for_Git=True,
        sample_checks=facts,ROI_shape=zoom['ROI_shape'],margin_px=24,ROI_rule=zoom['ROI_rule'],
        no_frame_after_q=True,no_reference_relabel=True,RGB_reads=0,GT_raster_reads=0,new_model_calls=0,new_replays=0))
    print('Final readable publication callout PASS: actual IDs at F1024/F1025/F1027; four branches; all local masks')


if __name__=='__main__':main()
