"""Postseal coverage, forecast-to-observation diagnostics and real depth QA figures."""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import cv2

import score
from postseal import match_sources
from depth_measurement import decode,KERNEL
from depth_state import predict

HERE=Path(__file__).resolve().parent
RUN=HERE/'run'


def stats(values):
    return dict(n=len(values),median=float(np.median(values)) if values else None,
                p90=float(np.quantile(values,.9)) if values else None)


def load_segment(name):
    public=RUN/name/'public'
    return dict(
        measurements={x['frame']:x for x in score.records(public/'DEPTH_OBSERVATIONS.jsonl.gz')},
        states={(x['frame'],x['arm']):x for x in score.records(public/'DEPTH_STATES.jsonl.gz')},
        predictions=list(score.records(public/'predictions.jsonl.gz')),
        events=json.loads((public/'EVENTS.json').read_text(encoding='utf-8')),
        assignments={x['frame']:x for x in score.records(score.FEED/'private'/name/'assignments.jsonl.gz')},
        publish=list(map(json.loads,(public/'PUBLISH_LEDGER.jsonl').read_text(encoding='utf-8').splitlines())),
        summary=json.loads((public/'RUN_SUMMARY.json').read_text(encoding='utf-8')))


def forecast_diagnostics(data,audit):
    comparisons=[]
    exclusions=[]
    for name,(start,stop) in score.SEGMENTS.items():
        segment=data[name]
        labels={}
        def match(frame,sources):
            if frame not in labels:
                labels[frame]=json.loads((score.DATA/'labels_640x360'/f'{start+frame-1:06d}.json').read_text(encoding='utf-8'))
            return match_sources(segment['assignments'][frame],labels[frame],sources)
        for event in segment['events']['D2_DYNAMIC']:
            if event['q'] is None:
                continue
            physical=next(x for x in audit['events'] if x['segment']==name and x['arm']=='D2_DYNAMIC' and x['event']==event['id'])
            for role,frozen in event['depth_frozen'].items():
                base=dict(segment=name,event=event['id'],role=role)
                anchor=physical['anchor_matches'].get(str(frozen['public']))
                samples=frozen['samples'][-10:]
                if not samples or not anchor or anchor['status']!='UNIQUE_IOU_MATCH':
                    exclusions.append(dict(base,reason='NO_HISTORY_OR_UNSCORABLE_REFERENCE'))
                    continue
                gt=anchor['gt_id']
                source=frozen['source']
                checked=[match(s['frame'],[source])[source] for s in samples]
                if any(x['status']!='UNIQUE_IOU_MATCH' or x['gt_id']!=gt for x in checked):
                    exclusions.append(dict(base,reason='PRE_DEPTH_FRAGMENT_NOT_UNIQUE_SAME_PHYSICAL_ID'))
                    continue
                post=[int(n) for n,x in physical['post_matches'].items()
                      if x['status']=='UNIQUE_IOU_MATCH' and x['gt_id']==gt]
                if len(post)!=1:
                    exclusions.append(dict(base,reason='NO_UNIQUE_Q_SOURCE_FOR_REFERENCE'))
                    continue
                target=post[0]
                q_state=segment['states'][(event['q'],'D2_DYNAMIC')]['live'].get(str(target))
                if not q_state:
                    exclusions.append(dict(base,reason='Q_SOURCE_VERSION_NOT_BOUND'))
                    continue
                active_key=q_state['key']
                begun=False
                count=0
                for frame in range(event['q'],min(event['q']+30,stop-start+2)):
                    current=segment['states'][(frame,'D2_DYNAMIC')]['live'].get(str(target))
                    if current and current['key']!=active_key:
                        break
                    valid=bool(current and frame in current['sample_frames'])
                    if not valid:
                        if begun:
                            break
                        continue
                    matching=match(frame,[target])[target]
                    if matching['status']!='UNIQUE_IOU_MATCH' or matching['gt_id']!=gt:
                        if begun:
                            break
                        continue
                    begun=True
                    observed=segment['measurements'][frame]['objects'][str(target)]
                    prediction=predict(frozen,segment['measurements'][frame]['time'])
                    if prediction['mu_mm'] is None or not observed['core_usable']:
                        break
                    actual=observed['core']['median']
                    comparisons.append(dict(base,frame=frame,original_frame=start+frame-1,
                        target_source=target,gt_id=gt,version=active_key,
                        static_abs_mm=abs(actual-samples[-1]['z_mm']),
                        dynamic_abs_mm=abs(actual-prediction['mu_mm']),
                        delta_seconds=prediction['delta_seconds'],status=prediction['status'],
                        proxy_scale_mm=prediction['scale_mm'],
                        within_proxy_scale=abs(actual-prediction['mu_mm'])<=prediction['scale_mm']))
                    count+=1
                if not count:
                    exclusions.append(dict(base,reason='NO_CONTIGUOUS_CERTIFIED_POST_FRAGMENT_WITHIN_30_FRAMES'))
    bins=[]
    for low,high in ((0.,.1),(.1,.5),(.5,1.),(1.,2.),(2.,float('inf'))):
        selected=[x for x in comparisons if low<=x['delta_seconds']<high]
        bins.append(dict(interval_seconds=[low,high if np.isfinite(high) else None],
            static_absolute_mm=stats([x['static_abs_mm'] for x in selected]),
            dynamic_absolute_mm=stats([x['dynamic_abs_mm'] for x in selected]),
            within_proxy_scale=sum(x['within_proxy_scale'] for x in selected)))
    return dict(status='POSTHOC_UNIQUE_SAME_PHYSICAL_FRAGMENT_ONLY',
        interpretation='residual against later raw observations, not physical depth GT or calibrated coverage',
        selection='first certified contiguous same-version post fragment within 30 frames; stop at risk/nonunique match/version change',
        static_absolute_mm=stats([x['static_abs_mm'] for x in comparisons]),
        dynamic_absolute_mm=stats([x['dynamic_abs_mm'] for x in comparisons]),
        within_proxy_scale=sum(x['within_proxy_scale'] for x in comparisons),
        fitted_WLS_comparisons=sum(x['status']=='WLS_LINEAR_TIME' for x in comparisons),
        bins=bins,observations=comparisons,excluded_roles=exclusions)


def event_plot(name,event,segment,target):
    q=event['q']
    time_q=segment['measurements'][q]['time']
    figure,axes=plt.subplots(3,1,figsize=(10,10),layout='constrained')
    for role,axis in zip(('A','B'),axes[:2]):
        frozen=event['depth_frozen'][role]
        samples=frozen['samples'][-10:]
        if samples:
            x=[s['time']-time_q for s in samples]
            axis.scatter(x,[s['z_mm'] for s in samples],label=f'{role} raw qualified pre',s=25)
            grid=np.linspace(samples[-1]['time'],time_q,80)
            fitted=[predict(frozen,float(t)) for t in grid]
            mu=np.array([x['mu_mm'] for x in fitted]); scale=np.array([x['scale_mm'] for x in fitted])
            axis.plot(grid-time_q,mu,'--',label=f"forecast {fitted[-1]['status']}")
            axis.fill_between(grid-time_q,mu-scale,mu+scale,alpha=.15,label='heuristic scale, not 95% interval')
        else:
            axis.text(.1,.5,'NO_HISTORY',transform=axis.transAxes)
        for native in event['post_first_observations']:
            obs=segment['measurements'][q]['objects'][native]
            z=obs['core']['median']
            if z is not None:
                public=next(x['id'] for x in segment['predictions'][q-1]['variants']['D2_DYNAMIC'] if x['mask']==f'n:{native}')
                axis.scatter([0],[z],marker='x',s=70,label=f'q n:{native} → public {public}; usable={obs["core_usable"]}')
        axis.axvline(0,color='black',linewidth=.8)
        axis.set(ylabel='APPARENT_CAMERA_Z_MM',xlabel='seconds relative to q; input cutoff = 0')
        axis.legend(fontsize=8)
    group=event['group_observations']
    times=[segment['measurements'][x['frame']]['time']-time_q for x in group]
    values=[segment['measurements'][x['frame']]['objects'][str(x['source'])]['core']['median'] for x in group]
    axes[2].plot(times,values,'o-',color='orange',label='GROUP only; never A/B history')
    axes[2].axvline(0,color='black',linewidth=.8)
    axes[2].set(xlabel='seconds relative to q',ylabel='GROUP core Z mm')
    axes[2].legend(fontsize=8)
    detail=event['numeric']['detail']
    score_text='; '.join(f"{x['choice']}: geom={x['geometry']:.4f}, depth={x['depth']:.4f}, total={x['total']:.4f}"
                        for x in detail.get('candidates',[]))
    figure.suptitle(f"{name} {event['id']} original q={score.SEGMENTS[name][0]+q-1}\n"
                   f"{event['numeric']['choice']} / {event['restore']['status']}\n{score_text}",fontsize=10)
    figure.savefig(target)
    plt.close(figure)


def raster_figure(name,frames,sources,segment,target,title,roles=None):
    images=[]
    decoded=[]
    bounds=[]
    for frame,selected in zip(frames,sources):
        with np.load(segment['measurements'][frame]['depth_path']) as sensor:
            raw=sensor['depth_mm']
        assignment=segment['assignments'][frame]
        masks={int(k[2:]):decode(v) for k,v in assignment['masks'].items()}
        occupancy=np.zeros(raw.shape,np.uint16)
        for region in masks.values(): occupancy+=region
        core={n:cv2.erode((region & (occupancy==1)).astype('u1'),KERNEL).astype(bool) for n,region in masks.items()}
        for native in selected:
            ys,xs=np.nonzero(masks[native])
            bounds.append((xs.min(),ys.min(),xs.max()+1,ys.max()+1))
        images.append(raw); decoded.append((masks,core))
    x0=max(0,min(x[0] for x in bounds)-30); y0=max(0,min(x[1] for x in bounds)-30)
    x1=min(640,max(x[2] for x in bounds)+30); y1=min(360,max(x[3] for x in bounds)+30)
    finite=np.concatenate([raw[y0:y1,x0:x1][np.isfinite(raw[y0:y1,x0:x1]) & (raw[y0:y1,x0:x1]>0)] for raw in images])
    low,high=np.quantile(finite,[.02,.98]) if len(finite) else (0,1)
    figure,axes=plt.subplots(len(frames),2,figsize=(13,4*len(frames)),squeeze=False,layout='constrained')
    for index,(frame,selected,raw,(masks,cores)) in enumerate(zip(frames,sources,images,decoded)):
        depth_axis,valid_axis=axes[index]
        view=np.where(np.isfinite(raw)&(raw>0),raw,np.nan)
        im=depth_axis.imshow(view[y0:y1,x0:x1],extent=(x0,x1,y1,y0),vmin=low,vmax=high,cmap='viridis')
        ay,ax=np.where(np.isfinite(raw)&(raw>5000))
        depth_axis.scatter(ax,ay,s=8,c='magenta',marker='+',label='raw >5000mm; display marker only')
        valid_axis.imshow((np.isfinite(raw)&(raw>0))[y0:y1,x0:x1],extent=(x0,x1,y1,y0),vmin=0,vmax=1,cmap='gray')
        for native,region in masks.items():
            if np.any(region[y0:y1,x0:x1]):
                for axis in (depth_axis,valid_axis):
                    axis.contour(region.astype(float),levels=[.5],colors=['#bbbbbb'],linewidths=.5)
        for native,color in zip(selected,('red','cyan')):
            for axis in (depth_axis,valid_axis):
                axis.contour(masks[native].astype(float),levels=[.5],colors=[color],linewidths=1.3)
                if cores[native].any(): axis.contour(cores[native].astype(float),levels=[.5],colors=[color],linewidths=.8,linestyles='--')
            obs=segment['measurements'][frame]['objects'][str(native)]
            zs=np.argwhere(masks[native])
            valid_axis.text(float(zs[:,1].mean()),float(zs[:,0].mean()),f'n:{native}',color=color,fontsize=9)
            def number(value): return 'UNKNOWN' if value is None else f'{value:.1f}'
            depth_axis.text(.01,.03+.09*list(selected).index(native),
                f"n:{native}: whole={number(obs['whole']['median'])}, core={number(obs['core']['median'])} mm\n"
                f"core n={obs['core']['n']}, fraction={obs['core']['valid_fraction']:.2f}, usable={obs['core_usable']}",
                transform=depth_axis.transAxes,fontsize=8,color='white',bbox=dict(facecolor='black',alpha=.6))
        for axis in (depth_axis,valid_axis):
            axis.set(xlim=(x0,x1),ylim=(y1,y0),xlabel='RGB-grid x px',ylabel='RGB-grid y px')
        role=roles[index] if roles else 'RAW QUALITY DIAGNOSTIC'
        depth_axis.set_title(f'{role}\noriginal F{score.SEGMENTS[name][0]+frame-1}',fontsize=10)
        valid_axis.set_title('valid raw pixels\nsolid prediction mask / dashed exclusive core',fontsize=10)
        if len(ax): depth_axis.legend(fontsize=7,loc='upper left')
        figure.colorbar(im,ax=depth_axis,label='APPARENT_CAMERA_Z_MM')
    figure.suptitle(title,fontsize=11)
    figure.savefig(target,dpi=150,bbox_inches='tight')
    plt.close(figure)
    return dict(path=str(target),bytes=target.stat().st_size,sha256=score.digest(target),
        segment=name,local_frames=frames,selected_sources=sources,
        crop_rgb_grid=[int(x0),int(y0),int(x1),int(y1)],display_depth_range_mm=[float(low),float(high)],
        transform='crop only in shared640x360 RGB grid; axes preserve original pixel coordinates',
        data='only raw depth_mm and predicted masks; no RGB or GT raster')


def main():
    metrics=json.loads((RUN/'METRICS.json').read_text(encoding='utf-8'))
    audit=json.loads((RUN/'EVENT_AUDIT.json').read_text(encoding='utf-8'))
    data={name:load_segment(name) for name in score.SEGMENTS}
    coverage={}
    event_scores=[]
    changes=[]
    conflict=None
    for name,(start,stop) in score.SEGMENTS.items():
        segment=data[name]
        all_objects=[x for frame in segment['measurements'].values() for x in frame['objects'].values()]
        coverage[name]=dict(total_observations=len(all_objects),core_usable=sum(x['core_usable'] for x in all_objects),
            core_empty=sum(x['core']['n']==0 for x in all_objects),
            measurement_extract_seconds=stats([x['extraction_seconds'] for x in segment['publish']]),
            receive_to_publish_seconds=stats([x['receive_to_publish_seconds'] for x in segment['publish']]),
            runtime=segment['summary'])
        for frame,item in segment['measurements'].items():
            for native,obs in item['objects'].items():
                delta=obs['core_whole_median_delta_mm']
                if delta is not None and (conflict is None or abs(delta)>abs(conflict['delta_mm'])):
                    conflict=dict(segment=name,frame=frame,original_frame=start+frame-1,native=int(native),
                                  delta_mm=delta,whole=obs['whole'],core=obs['core'],core_usable=obs['core_usable'])
        reference={e['q']:e for e in segment['events']['D0_GEOMETRY'] if e['q'] is not None}
        for event in segment['events']['D2_DYNAMIC']:
            if event['q'] is None: continue
            detail=event['numeric']['detail']
            candidates=detail.get('candidates',[])
            geom=(min(candidates,key=lambda x:x['geometry'])['choice'] if candidates else 'UNRESOLVED')
            event_scores.append(dict(segment=name,event=event['id'],original_q=start+event['q']-1,
                selected=event['numeric']['choice'],geometry_common_state_choice=geom,
                used_edges=detail.get('used_edges',0),status=event['restore']['status'],
                forecast_by_role={r:predict(f,event['post_first_observations'][next(iter(event['post_first_observations']))]['time'])
                                  for r,f in event['depth_frozen'].items()},
                candidates=[{k:x[k] for k in ('choice','geometry','depth','total')} for x in candidates],
                post_depth_usable={n:segment['measurements'][event['q']]['objects'][n]['core_usable'] for n in event['post_first_observations']}))
            old=reference.get(event['q'])
            if old:
                pub=segment['publish'][event['q']-1]['event_publish']
                if pub['D2_DYNAMIC']['first_public_pair']!=pub['D0_GEOMETRY']['first_public_pair']:
                    physical=next(x for x in audit['events'] if x['segment']==name and x['arm']=='D2_DYNAMIC' and x['event']==event['id'])
                    changes.append(dict(segment=name,event=event['id'],original_q=start+event['q']-1,
                        first_public_D0=pub['D0_GEOMETRY']['first_public_pair'],
                        first_public_D2=pub['D2_DYNAMIC']['first_public_pair'],physical=physical['first_public_physical']))
    forecast=forecast_diagnostics(data,audit)
    diagnostics=dict(status='POSTSEAL_DIAGNOSTICS',coverage=coverage,event_scores=event_scores,
        changed_first_publications=changes,forecast_observation_comparison=forecast,
        quality_conflict_selection=conflict,
        source_policy='maximum absolute finite core-whole median difference, all masks and frames; no GT selection',
        measurement_failures=0,new_model_http=0,model_cost_usd=0)
    score.write_new(RUN/'DEPTH_DIAGNOSTICS.json',diagnostics)
    public_figures=RUN/'visualizations'; public_figures.mkdir()
    private=HERE/'private_visualizations'; private.mkdir()
    first=json.loads((RUN/'SELECTION.json').read_text(encoding='utf-8'))['first_complete_event']
    name=first['segment']; segment=data[name]
    e=next(x for x in segment['events']['D2_DYNAMIC'] if x['id']==first['event'])
    selected=[]; frames=[]
    for role,frozen in e['depth_frozen'].items():
        if frozen['samples']:
            frames.append(frozen['samples'][-1]['frame']); selected.append([frozen['source']])
    frames.extend([e['suspect_frame'],e['q']])
    selected.extend([[e['group_observations'][0]['source']],[int(n) for n in e['post_first_observations']]])
    inventories=[raster_figure(name,frames,selected,segment,private/'first_complete_depth.png',
        f"First complete automatic event {e['id']}: actual pre / GROUP / q; first public {first['first_public_pair']}")]
    inventories.append(raster_figure(conflict['segment'],[conflict['frame']],[[conflict['native']]],data[conflict['segment']],
        private/'maximum_quality_conflict.png',f"Candidate-independent maximum core/whole conflict; Δ={conflict['delta_mm']:.1f}mm"))
    for name,segment in data.items():
        for event in segment['events']['D2_DYNAMIC']:
            if event['q'] and (event['id']==first['event'] or any(x['segment']==name and x['event']==event['id'] for x in changes)):
                event_plot(name,event,segment,public_figures/f'{name}_{event["id"]}.svg')
    score.write_new(RUN/'VISUALIZATION_INVENTORY.json',dict(private= inventories,
        public=[dict(path=str(p),bytes=p.stat().st_size,sha256=score.digest(p)) for p in public_figures.iterdir()],
        reproduction='python experiments/ds1_depth_only/analyze.py; requires original raw depth, prepared prediction RLE, matplotlib/cv2/numpy/pycocotools; fresh output directories',
        no_private_raster_committed=True))
    print(json.dumps(dict(coverage={name:{k:v for k,v in value.items() if k in ('total_observations','core_usable','core_empty')} for name,value in coverage.items()},
        changes=changes,forecast={k:v for k,v in forecast.items() if k in ('static_absolute_mm','dynamic_absolute_mm','fitted_WLS_comparisons','within_proxy_scale')},conflict=conflict)))


if __name__=='__main__':
    main()
