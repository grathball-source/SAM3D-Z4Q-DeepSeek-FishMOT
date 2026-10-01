"""Append one readable actual-publication zoom; original full images stay bound."""
from pathlib import Path
import sys, json, hashlib
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
from common import ARMS, RUN, input_dir, rows, read, sha, artifact, write_new


def main():
    original_path=HERE/'diagnosis/PUBLICATION_INVENTORY.json'
    original=read(original_path)
    case=next(item for item in original['images'] if item['global_q']==1027)
    for key in ('all_prediction_seal','scoring_seal','code'):
        expected=original['bindings'][key]
        assert artifact(Path(expected['path']))==expected
    public=RUN/case['segment']/'public'
    bound=original['bindings']['segments'][case['segment']]
    for expected in [bound['prediction_seal'],*bound['files'].values(),bound['assignments']]:
        assert artifact(Path(expected['path']))==expected
    path=HERE/'private/publication/F1027_ACTUAL_PUBLICATION_ZOOM.png'
    inventory=HERE/'diagnosis/PUBLICATION_ZOOM_INVENTORY.json'
    assert not path.exists() and not inventory.exists()
    frames={sample['role']:sample['local_frame'] for sample in case['sample_frames']}
    assert tuple(frames)==('before','merge','q') and all(frame<=frames['q'] for frame in frames.values())
    wanted=set(frames.values())
    predictions={row['frame']:row for row in rows(public/'predictions.jsonl.gz') if row['frame'] in wanted}
    assignments={row['frame']:row for row in rows(Path(bound['assignments']['path'])) if row['frame'] in wanted}
    events=read(public/'EVENTS.json')
    episode=next(event for event in events['F9_RESTORED'] if event['id']==case['event'])
    sources=set(episode['member_sources'])|set(map(int,episode['post_first_observations']))
    sources.update(item['source'] for item in episode['group_observations'] if item['frame']<=episode['q'])
    for arm in ARMS[1:]:
        own=next(event for event in events[arm] if event['id']==case['event'])
        sources.update(own['restore']['unassigned_member_residual'])
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
    source_reader=RestoredDepth()
    data={};union=np.zeros((360,640),bool)
    try:
        for sample in case['sample_frames']:
            frame=sample['local_frame']
            assert all({int(obj['mask'][2:]):obj['id'] for obj in predictions[frame]['variants'][arm]}
                =={int(k):v for k,v in sample['published'][arm].items()} for arm in ARMS)
            assert artifact(Path(sample['raw_aligned']['path']))==sample['raw_aligned']
            with np.load(sample['raw_aligned']['path']) as raw_source:
                raw=raw_source['depth_mm'].copy()
                assert hashlib.sha256(raw_source['source_index'].astype('<i4').tobytes()).hexdigest()==sample['raw_source_index_sha256']
            v2,provenance,meta=source_reader(sample['global_frame'])
            assert meta['native_row']==sample['v2_row'] and meta['index']==sample['global_frame']
            assert artifact(Path(meta['native_path']))==sample['v2_native']
            assert hashlib.sha256(source_reader.current_source_index.astype('<i4').tobytes()).hexdigest()==sample['v2_source_index_sha256']
            masks={int(k[2:]):decode(value) for k,value in assignments[frame]['masks'].items()}
            assert all(set(masks)=={int(obj['mask'][2:]) for obj in predictions[frame]['variants'][arm]} for arm in ARMS)
            for native in sources&set(masks):union|=masks[native]
            data[sample['role']]=(raw,v2,masks,predictions[frame],sample['global_frame'])
    finally:
        source_reader.close()
    yy,xx=np.nonzero(union)
    assert len(xx)>0
    margin=24
    x0,x1=max(0,int(xx.min())-margin),min(640,int(xx.max())+margin+1)
    y0,y1=max(0,int(yy.min())-margin),min(360,int(yy.max())+margin+1)
    assert 0<=x0<x1<=640 and 0<=y0<y1<=360
    region=np.s_[y0:y1,x0:x1]
    values=np.concatenate([image[region][np.isfinite(image[region])&(image[region]>0)]
        for raw,v2,_,_,_ in data.values() for image in (raw,v2)])
    norm=LogNorm(vmin=float(values.min()),vmax=float(values.max()))
    fig,axes=plt.subplots(4,6,figsize=(27,14),constrained_layout=True)
    sample_checks=[]
    for row,arm in enumerate(ARMS):
        own=next(event for event in events[arm] if event['id']==case['event']) if arm!='SAM3_NATIVE' else None
        residual=set(own['restore']['unassigned_member_residual']) if own else set()
        for time_column,role in enumerate(('before','merge','q')):
            raw,v2,masks,prediction,global_frame=data[role]
            published={int(obj['mask'][2:]):obj['id'] for obj in prediction['variants'][arm]}
            inside=[native for native,mask in masks.items() if np.any(mask[region])]
            for modality,image in enumerate((raw,v2)):
                ax=axes[row,time_column*2+modality]
                ax.imshow(np.ma.masked_where(~np.isfinite(image)|(image<=0),image),cmap='viridis',norm=norm)
                high=np.argwhere(np.isfinite(image[region])&(image[region]>5000))
                if high.size:ax.scatter(high[:,1]+x0,high[:,0]+y0,c='red',s=8)
                for native in inside:
                    mask=masks[native]
                    focus=native in sources
                    color='#00e5ff' if native==137 else '#ff8c00' if native==95 else '#eeeeee'
                    if role=='q' and native in residual:color='magenta'
                    contours,_=cv2.findContours(mask.astype('u1'),cv2.RETR_LIST,cv2.CHAIN_APPROX_SIMPLE)
                    for contour in contours:
                        contour=contour[:,0,:]
                        if len(contour)>1:ax.plot(*contour.T,color=color,linewidth=1.7 if focus else .9)
                    cy,cx=np.nonzero(mask[region])
                    if len(cx):
                        label=(('post ' if role=='q' else 'source ')+str(native)+f'\npublic {published[native]}'
                               if focus else f'n{native}\nID {published[native]}')
                        ax.text(float(cx.mean())+x0,float(cy.mean())+y0,label,fontsize=9 if focus else 7,
                            fontweight='bold' if focus else 'normal',ha='center',va='center',color=color,
                            bbox=dict(boxstyle='square,pad=.12',facecolor='black',edgecolor='none',alpha=.72))
                ax.set_xlim(x0-.5,x1-.5);ax.set_ylim(y1-.5,y0-.5)
                ax.set_title(f'{arm}\n{role} F{global_frame} / '+('RAW' if modality==0 else 'native V2')+
                    f' / ROI >5000={len(high)}',fontsize=10)
                ax.tick_params(labelsize=7)
                if modality==0:
                    core=image[region];positive=core[np.isfinite(core)&(core>0)]
                    ax.set_xlabel(f'raw positive {len(positive)}/{core.size}; all local masks {len(inside)}',fontsize=8)
            sample_checks.append(dict(arm=arm,role=role,global_frame=global_frame,local_mask_count=len(inside),
                source137_public=published.get(137),source95_public=published.get(95)))
    fig.colorbar(ScalarMappable(norm=norm,cmap='viridis'),ax=axes,shrink=.7,
        label='recorded camera-Z mm; full actual local positive value range; >5000 red is diagnostic, not sensor limit')
    fig.suptitle('F1027 actual publication: source 137 cyan; source 95 orange; all local neighbors/residuals retained\n'
        'Four branches, before F1024 / recorded merge F1025 / q F1027; actual ID at that time only, no retroactive relabel.\n'
        'ROI = involved source-mask union across these three <=q frames + fixed 24 px margin. No GT/RGB.\n'
        'V2 is offline upstream RGB + future support; actual surface ownership and calibration accuracy UNKNOWN.',fontsize=14)
    fig.savefig(path,dpi=160)
    plt.close(fig)
    write_new(inventory,dict(status='SEALED_ACTUAL_PUBLICATION_LOCAL_ZOOM_COMPLETE',code=artifact(Path(__file__)),
        original_inventory=artifact(original_path),all_prediction_seal=original['bindings']['all_prediction_seal'],
        scoring_seal=original['bindings']['scoring_seal'],case=dict(segment=case['segment'],event=case['event'],global_q=1027),
        source_and_row_bindings=case['sample_frames'],private_pixel_artifact=artifact(path),private_pixels_not_for_Git=True,
        sample_checks=sample_checks,ROI_rule='INVOLVED_SOURCE_MASK_UNION_THREE_DISPLAYED_FRAMES_PLUS_FIXED_24PX_MARGIN',
        ROI_shape=[y1-y0,x1-x0],margin_px=margin,GT_ROI_selection=False,no_sample_after_q=True,
        RGB_reads=0,GT_raster_reads=0,new_replays=0,new_model_calls=0))
    print('Actual publication zoom PASS: F1024/F1025/F1027; four branches; actual IDs; all local masks; original 10 full images unchanged')


if __name__=='__main__':main()
