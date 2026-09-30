"""Postseal performance, measurement coverage and actual raw-depth QA."""
from __future__ import annotations
from collections import Counter
import gzip
import json
import time
from common import HERE,ROOT,RUN,DATA,SEGMENTS,ARMS,input_dir,read,rows,write_new,artifact,verify_item,sha
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def main():
    started=time.perf_counter()
    scoring=read(RUN/'SCORING_SEALED.json')
    for filename,digest in scoring['artifacts_sha256'].items():
        assert sha(RUN/filename)==digest
    for item in read(HERE/'OLD_READONLY_LOCK.json')['artifacts']:
        verify_item(item)
    coverage={}
    f6_equivalent=0
    for name,(start,stop) in SEGMENTS.items():
        status=Counter();n=0
        old_rows=(rows(ROOT/'experiments/ds4_depth_quality_repair'/f'{name}_measurements.jsonl.gz')
                  if start>=701 else None)
        old_pixels=(rows(ROOT/'experiments/ds4_depth_quality_repair/private'/f'{name}_pixels.jsonl.gz')
                    if start>=701 else None)
        for row in rows(RUN/name/'public/DEPTH_OBSERVATIONS.jsonl.gz'):
            n+=len(row['objects'])
            for value in row['objects'].values():
                status['raw_core_available' if value['core_usable'] else 'raw_core_unknown']+=1
            for fact in row['f6'].values():
                status['f6_filter_'+fact['filter']['status']]+=1
                status['history_available' if fact['history_usable'] else 'history_unknown']+=1
                status['q_available' if fact['core_usable'] else 'q_unknown']+=1
                status['multi_qualified']+=fact['qualified_piece_count']>1
                status['no_qualified']+=fact['qualified_piece_count']==0
                status['original_selected_points']+=fact['filter']['selected']['n']
                status['qualified_selected_points']+=sum(p['n'] for p in fact['pieces'] if p['qualified'])
            if old_rows is not None:
                old=next(old_rows);pixel=next(old_pixels)
                assert old['frame']==pixel['frame']==row['global_frame']
                for token,fact in old['objects'].items():
                    native=str(pixel['objects'][token]['native'])
                    assert row['f6'][native]['filter']==fact['methods']['F6_BG_NOISE']['selector'],(name,row['frame'],native)
                    f6_equivalent+=1
        coverage[name]=dict(frames=stop-start+1,objects=n,counts=dict(status))
    shadow=[]
    for name in SEGMENTS:
        shadow+= [dict(segment=name,**x) for x in read(RUN/name/'public/COMMON_STATE_SHADOW.json')]
    events=read(RUN/'EVENT_AUDIT.json')
    timings={name:read(RUN/name/'public/RUN_SUMMARY.json') for name in SEGMENTS}
    measures=read(RUN/'METRICS.json')
    write_new(HERE/'SUMMARY.json',dict(
        status='TRACKING_TRIAL_COMPLETE',frames=1471,objects=sum(c['objects'] for c in coverage.values()),
        engineering='PASS',input_contract='PASS_RAW_SOURCE_BINDING',
        surface_identity='UNKNOWN',depth_increment=('SUPPORTED_ON_EXPOSED_DEVELOPMENT' if
            measures['frozen_support_rule_met'] else 'FROZEN_SUPPORT_RULE_NOT_MET'),
        pooled_metrics=measures['pooled_metrics'],pooled_delta=measures['pooled_delta'],
        coverage=coverage,f6_exact_old_objects=f6_equivalent,
        same_state_shadow=dict(events=len(shadow),joint_available=sum(x['multi'].get('joint_available',False) for x in shadow),
            scalar_vs_multi_choice_changes=sum(x['multi_choice']!=x['scalar_choice'] for x in shadow),
            rows=shadow),event_outcomes=events['summary'],first_public_outcomes=events['first_public_summary'],
        branch_independent_elapsed_seconds=sum(s['elapsed_seconds'] for s in timings.values()),
        per_segment_time=timings,no_gt_before_all_prediction_seals=True,
        old_public_files_verified=len(read(HERE/'OLD_READONLY_LOCK.json')['artifacts']),
        model_http=0,cost_usd=0,postrun_seconds=time.perf_counter()-started))
    # Pure numeric public visualization.
    arms=list(ARMS)
    fig,axes=plt.subplots(1,2,figsize=(13,4.5))
    x=np.arange(len(arms))
    for offset,key in ((-.24,'IDF1'),(0.,'HOTA'),(.24,'AssA')):
        axes[0].bar(x+offset,[measures['pooled_metrics'][a][key] for a in arms],width=.24,label=key)
    labels=['Native','Geometry','Core frozen','F6 scalar','Multi-fragment']
    axes[0].set_xticks(x,labels,rotation=15);axes[0].set_ylim(0,100)
    axes[0].set_ylabel('Percent');axes[0].legend()
    axes[1].bar(x,[measures['pooled_metrics'][a]['IDSW'] for a in arms],color='#315f84')
    axes[1].set_xticks(x,labels,rotation=15);axes[1].set_ylabel('Identity switches')
    fig.suptitle('DS6: 1471 exposed SOURCE_OLD frames | complete independent branches | no API')
    fig.tight_layout()
    fig.savefig(HERE/'PERFORMANCE.svg')
    plt.close(fig)
    # Actual source masks + unfilled selected raw points. No RGB or manual GT.
    from measurement import admission,f6_measure,pieces
    from depth_measurement import decode
    selected_cases=[]
    for name in SEGMENTS:
        for event in events['events']:
            if event['segment']==name and event['arm']=='D5_MULTIFRAGMENT' and event.get('q') is not None:
                selected_cases.append((name,event['q'],event['event']))
                break
    # Fixed prior mixed-surface failure is an exposed diagnosis, never input selection.
    selected_cases.append(('feeding_001201_001906',1821-1201+1,None))
    output=HERE/'private/visualizations';output.mkdir(parents=True,exist_ok=True)
    inventory=[]
    for name,local,event_id in selected_cases:
        global_frame=SEGMENTS[name][0]+local-1
        assignment=next(x for x in rows(input_dir(name)/'assignments.jsonl.gz') if x['frame']==local)
        masks={int(k[2:]):decode(v) for k,v in assignment['masks'].items()}
        occupancy=sum((m.astype('u2') for m in masks.values()),np.zeros((360,640),'u2'))
        with np.load(DATA/'depth_rgb_640x360'/f'{global_frame:06d}.npz') as sensor:
            depth=sensor['depth_mm']
        clean,_=admission(global_frame,depth)
        # Actual first-split sources; an exposed fixed mixed-surface failure is separate.
        original_events=read(RUN/name/'public/EVENTS.json')['D5_MULTIFRAGMENT']
        sources=([int(n) for n in next(e for e in original_events if e['id']==event_id)['post_first_observations']]
                 if event_id else sorted(masks)[:2])
        published=next(x for x in rows(RUN/name/'public/predictions.jsonl.gz') if x['frame']==local)
        public_ids={int(x['mask'][2:]):x['id'] for x in published['variants']['D5_MULTIFRAGMENT']}
        if global_frame==1821:
            source_pixel=next(x for x in rows(ROOT/'experiments/ds4_depth_quality_repair/private'/f'{name}_pixels.jsonl.gz')
                              if x['frame']==1821)
            sources=[int(source_pixel['objects']['o008']['native'])]
        fig,axes=plt.subplots(len(sources),2,figsize=(11,4*len(sources)),squeeze=False)
        for row_index,native in enumerate(sources):
            fact,pix=f6_measure(clean,masks[native],(occupancy-masks[native].astype('u2'))>0,1.)
            x0,y0,x1,y1=fact['crop']
            selected=pix['selected'];d=clean[y0:y1,x0:x1]
            graph=pieces(d,selected,f'{name}/F{local}/n:{native}/F6',fact['crop'])
            axis=axes[row_index,0]
            image=np.ma.masked_where(d<=0,d)
            axis.imshow(image,cmap='viridis',vmin=700,vmax=1300)
            axis.contour(masks[native][y0:y1,x0:x1],levels=[.5],colors='white',linewidths=.8)
            yy,xx=np.nonzero(selected);axis.scatter(xx,yy,s=3,c='red',alpha=.55)
            axis.set_title(f'F{global_frame} n:{native} public:{public_ids[native]} | white mask / red measured points\n{fact["reason"]}')
            axis.set_axis_off()
            axes[row_index,1].hist(d[selected],bins=40,color='#315f84')
            for p in graph:
                if p['qualified']:
                    axes[row_index,1].axvline(p['median'],color='#d77625',linewidth=1)
            axes[row_index,1].set_title(f'Anonymous depth pieces: {sum(p["qualified"] for p in graph)} qualified\nNo surface ownership labels; holes not measured')
            axes[row_index,1].set_xlabel('Original camera-Z (mm)')
        fig.tight_layout()
        path=output/f'F{global_frame:06d}.png'
        fig.savefig(path,dpi=140,bbox_inches='tight');plt.close(fig)
        inventory.append(dict(artifact=artifact(path),segment=name,frame=global_frame,
            source_masks='original saved SAM3',pixel_source='raw depth only; no RGB/GT',
            selection='first actual first-split post pair per segment plus fixed prior F1821'))
    write_new(HERE/'VISUALIZATION_INVENTORY.json',dict(
        public_numeric=artifact(HERE/'PERFORMANCE.svg'),private_raw_depth=inventory,
        actual_viewing='PENDING_ROOT_VIEW'))
    print(json.dumps(dict(coverage=coverage,old_f6_exact=f6_equivalent,
        same_state_events=len(shadow),joint=sum(x['multi'].get('joint_available',False) for x in shadow),
        changes=sum(x['multi_choice']!=x['scalar_choice'] for x in shadow),
        images=[x['artifact']['path'] for x in inventory]),ensure_ascii=False))
if __name__=='__main__':main()

