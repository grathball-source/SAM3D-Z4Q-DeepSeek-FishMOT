"""Read sealed DS9 facts and actual current depth; private pixels, public numbers.

Failure references select displays only. No GT raster, RGB, replay or model.
"""
from pathlib import Path
import sys, json, gzip, hashlib, math, collections, datetime
from functools import lru_cache
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
TRIAL = HERE.parent
DS9 = TRIAL.parent/'ds9_joint_h0_depth'
sys.path.insert(0, str(DS9))
from common import DATA, SEGMENTS, input_dir, read, rows, artifact, write_new
from restored_source import RestoredDepth
from depth_measurement import decode, statistics
from depth_score import log_t4
from measurement import measure_raw, measure_restored
from adaptive_core import adaptive_core
import numpy as np
import cv2
cv2.setNumThreads(1)
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm

PRIVATE = TRIAL/'private/diagnosis'
artifact = lru_cache(maxsize=None)(artifact)
RAW, V2, PERM = 'J1_RAW_DEPTH', 'J2_RESTORED_DEPTH', 'J2_DEPTH_PERMUTE'
COLORS = ['#00b7eb', '#f28e2b']


def finite_values(depth, region):
    z = depth[region].astype(float)
    return z[np.isfinite(z) & (z > 0)]


def public_measurement(item):
    return {k:item.get(k) for k in ('native','source','fact_id','core','core_usable',
        'cohort','cohorts','actual_selected_mad_mm','core_mad_semantics','roi_geometry',
        'uncertainty_floor_mm','provenance_counts')}


def decision(event, reference):
    d = event['numeric']['detail']; restore = event['restore']
    expected = {str(k):v for k,v in (reference.get('expected_mapping') or {}).items()}
    return dict(choice=restore['selected_choice'], status=restore['status'],
        first_public_reference=reference['first_public_physical'], reason=d['reason'],
        best=d['best'], runner_up=d['runner_up'], margin=d['margin'],
        post_pair_usable=d['post_pair_usable'], used_edges=d['used_edges'],
        stage_error=restore['stage_error'], visible_member_residual=restore['unassigned_member_residual'],
        depth_forecasts=d['depth_forecasts'], geometry_forecasts={r:{k:v.get(k) for k in
            ('samples','actual_gap_seconds','real_pre_span_seconds','growth_factor','mean_mode')}
            for r,v in d['geometry_forecasts'].items()},
        depth_assignment=d['depth_assignment'], candidates={k:dict(
            reference='UNSCORABLE' if not expected else 'CORRECT' if
                {str(n):v for n,v in c['mapping'].items()} == expected else 'WRONG',
            mapping=c['mapping'], geometry_log_lr=c['geometry_log_lr'],
            depth_log_lr=c['depth_log_lr'], log_score=c['log_score'], posterior=c['posterior'])
            for k,c in d['candidates'].items()})


def population(measurements):
    def spread(items):
        z=np.asarray(items,float)
        return dict(count=len(z),minimum=float(z.min()) if len(z) else None,
            maximum=float(z.max()) if len(z) else None,median=float(np.median(z)) if len(z) else None,
            q25=float(np.quantile(z,.25)) if len(z) else None,q75=float(np.quantile(z,.75)) if len(z) else None,
            IQR=float(np.quantile(z,.75)-np.quantile(z,.25)) if len(z) else None)
    allmed=[m['core']['median'] for m in measurements.values() if m['core']['median'] is not None and m['core']['median']>0]
    kernels=[dict(native=n,median_mm=m['core']['median'],scale_mm=max(15.,1.4826*m['core']['mad']),
        cohort=m.get('cohort','RAW'),fact_id=m['fact_id']) for n,m in measurements.items() if m['core_usable']]
    return dict(total_current_objects=len(measurements),all_nonmissing_core_medians=spread(allmed),
        all_usable_core_medians=spread([k['median_mm'] for k in kernels]),
        usable_cohorts=dict(collections.Counter(k['cohort'] for k in kernels)),kernels=kernels,
        rule='every current core_usable object once, equal object weight, query included; no GT or identity filter',
        interpretation='proposed diagnostic t4 KDE plug-in; not calibrated posterior or confirmed fish surface')


def hist(ax, depth, rois, label, full, pop, provenance=None, ring=None):
    collected = [finite_values(depth, roi) for roi in rois.values()]
    values = np.concatenate([z for z in collected if z.size])
    background_scale=max(60.,1.4826*full['mad'])
    landmarks=[k['median_mm'] for k in pop['kernels']]+[max(1.,full['median']-3*background_scale),full['median']+3*background_scale]
    lo,hi = min(float(values.min()),min(landmarks)),max(float(values.max()),max(landmarks))
    edges = np.geomspace(max(1.,lo*.97),max(lo*1.01,hi*1.03),50)
    for i,(n,roi) in enumerate(rois.items()):
        cohorts = [('all',roi)] if provenance is None else [('retained',roi&(provenance==1)),('inferred',roi&np.isin(provenance,[2,3]))]
        for name,selection in cohorts:
            z = finite_values(depth,selection)
            if z.size:ax.hist(z,bins=edges,histtype='step',density=True,color=COLORS[i],
                linestyle='-' if name!='inferred' else '--',label=f'n{n} {name} n={len(z)}')
    grid=np.geomspace(edges[0],edges[-1],400)
    null=np.exp([log_t4(z,full['median'],max(60.,1.4826*full['mad'])) for z in grid])
    ax.plot(grid,null,color='black',linestyle=':',label='DS9 whole-pixel t4 null')
    if len(pop['kernels'])>=3:
        kde=np.mean([np.exp([log_t4(z,k['median_mm'],k['scale_mm']) for z in grid]) for k in pop['kernels']],axis=0)
        ax.plot(grid,kde,color='#9c27b0',label=f'proposed object-equal t4 null K={len(pop["kernels"])}')
    if ring is not None:
        z = finite_values(depth,ring)
        if z.size:ax.axvline(float(np.median(z)),color='gray',linestyle=':',label='outside-mask local median')
    ax.set_xscale('log');ax.set_xlabel('actual depth mm (log axis, full core value range)')
    ax.set_ylabel('normalized density 1/mm');ax.set_title(label+'\nROI-pixel histogram vs object-equal KDE');ax.legend(fontsize=6)


def draw(case, arrays, events):
    raw,v2,prov,masks,occupancy,rois,ring = arrays
    nlist = list(rois);posts = set(nlist);residual=set(case['branches'][V2]['visible_member_residual'])
    fig,axes=plt.subplots(3,3,figsize=(19,14),constrained_layout=True)
    positive=np.concatenate([raw[raw>0],v2[v2>0]])
    norm=LogNorm(vmin=float(positive.min()),vmax=float(positive.max()))
    for ax,depth,label in zip(axes[0,:2],(raw,v2),('actual RAW camera-Z','saved native V2 reprojected')):
        image=ax.imshow(np.ma.masked_less_equal(depth,0),norm=norm,cmap='viridis')
        for n,mask in masks.items():
            c=COLORS[nlist.index(n)] if n in posts else 'magenta' if n in residual else 'white'
            ax.contour(mask,levels=[.5],colors=c,linewidths=1. if n in posts|residual else .35)
            if n in posts|residual:
                yy,xx=np.nonzero(mask);ax.text(xx.mean(),yy.mean(),f'n{n}',color=c,fontsize=8)
        high=depth>5000
        if high.any():
            overlay=np.zeros((*depth.shape,4));overlay[high]=[1,0,0,.9];ax.imshow(overlay)
        ax.set_title(f'{label}\nmax={depth.max():.3f} mm; >5000 SUSPECT={high.sum()} (red, not a sensor limit)')
        fig.colorbar(image,ax=ax,label='mm, full actual range');ax.set_xlabel('RGB-grid x');ax.set_ylabel('RGB-grid y')
    ax=axes[0,2];context=np.zeros((*raw.shape,3))
    context[occupancy>0]=.15;context[ring]=[.24,.24,.24]
    for i,(n,roi) in enumerate(rois.items()):
        context[masks[n]]=[.08,.28,.4] if i==0 else [.4,.2,.08]
        context[roi&(prov==1)]=[0,.8,1] if i==0 else [1,.6,0]
        context[roi&np.isin(prov,[2,3])]=[1,0,1]
    ax.imshow(context)
    for n,mask in masks.items():ax.contour(mask,levels=[.5],colors='red' if n in residual else 'white',linewidths=.6)
    area=np.logical_or.reduce([masks[n] for n in posts|residual]);yy,xx=np.nonzero(area)
    ax.set_xlim(max(0,xx.min()-25),min(639,xx.max()+25));ax.set_ylim(min(359,yy.max()+25),max(0,yy.min()-25))
    ax.set_title('Current prediction masks / actual exclusive core\ncyan-orange: retained; magenta: inferred; gray: unlabeled local ring\nred contour: visible member residual; all neighbor contours retained')
    hist(axes[1,0],raw,rois,'RAW core distribution',case['full_raw'],case['object_population_raw'],ring=ring)
    hist(axes[1,1],v2,rois,'V2 cohorts stay separate',case['full_v2'],case['object_population_v2'],provenance=prov,ring=ring)
    ax=axes[1,2];ax.axis('off');lines=[]
    for n in nlist:
        item=case['posts'][str(n)]
        for label,key in [('RAW','raw'),('V2','v2')]:
            m=item[key];c=m['core'];lines.append(f'n{n} {label}: ROI={c["area"]} n={c["n"]} fraction={c["valid_fraction"]:.3f}')
            actual=m.get('actual_selected_mad_mm') if label=='V2' else c['mad']
            lines.append(f'  median={c["median"]:.3f} actualMAD={actual:.3f} adapterMAD={c["mad"]:.3f}' if c['median'] is not None else '  median/MAD missing')
            lines.append(f'  usable={m["core_usable"]} cohort={m.get("cohort") or "RAW"}')
        lines.append(f'  ring median raw/v2: {item["ring_raw"]["median"]} / {item["ring_v2"]["median"]}')
        lines.append(f'  raw/v2 winner native-source equality={item["source_binding"]["same_native_winner_on_shared_valid"]}/{item["source_binding"]["shared_valid_roi_pixels"]}')
    ax.text(0,1,'\n'.join(lines),va='top',fontsize=8,family='monospace');ax.set_title('Actual facts; surface identity UNKNOWN')
    ax=axes[2,0]
    for arm,style in [(RAW,':'),(V2,'-')]:
        e=events[arm]
        for i,role in enumerate(('A','B')):
            samples=e['depth_frozen'][role]['samples'][-10:]
            if samples:
                ax.plot([s['time']-case['time'] for s in samples],[s['z_mm'] for s in samples],style,marker='.',color=COLORS[i],label=f'pre {role} {arm}')
        for i,n in enumerate(nlist):
            m=case['posts'][str(n)]['raw' if arm==RAW else 'v2']['core']
            if m['median'] is not None:ax.scatter([0],[m['median']],marker='o' if arm==RAW else 's',facecolors='none',edgecolors=COLORS[i],s=65,label=f'post n{n} {arm}')
    ax.axvline(0,color='black',linewidth=.5);ax.axhline(case['full_v2']['median'],color='gray',linestyle='--',label='current whole median proxy')
    ax.set_xlabel('seconds relative to first split q (gap left unfilled)');ax.set_ylabel('measured / selected depth mm')
    ax.set_title('Frozen same-version pre facts + actual current facts\nNo assumed post-to-pre ownership connection');ax.legend(fontsize=6)
    ax=axes[2,1];candidates=list(case['branches'][V2]['candidates']);x=np.arange(len(candidates))
    for offset,arm,c in [(-.24,V2,'#4169e1'),(0,PERM,'#e15759'),(.24,RAW,'#59a14f')]:
        vals=case['branches'][arm]['candidates'];ax.bar(x+offset,[vals.get(k,{}).get('depth_log_lr',np.nan) for k in candidates],width=.23,label=arm,color=c)
    ax.set_xticks(x,[f'{k}\n{case["branches"][V2]["candidates"][k]["reference"]}' for k in candidates])
    ax.axhline(0,color='black',linewidth=.5);ax.set_ylabel('normalized depth log-LR vs common background')
    ax.set_title('Depth contribution only (no geometry eligibility gate)\nreference labels select display; never select pixels');ax.legend(fontsize=7)
    ax=axes[2,2];ax.axis('off');lines=[f'F{case["global_q"]} / {case["event"]}',f'First-public V2: {case["branches"][V2]["first_public_reference"]}']
    for arm in (RAW,V2,PERM):
        d=case['branches'][arm];lines.extend([f'{arm}: {d["choice"]} {d["status"]}',f'  margin={d["margin"]:.6f}; {d["reason"]}',f'  pre n/scale: '+str({r:(v['samples'],v['scale_mm']) for r,v in d['depth_forecasts'].items()})])
    lines.extend(['RAW NPZ SHA '+case['sources']['raw_aligned']['sha256'][:16],
        'V2 H5 SHA '+case['sources']['v2_native']['sha256'][:16],
        'V2 native row/index '+str(case['sources']['v2_row'])+'/'+str(case['global_q']),
        'calibration SHA '+case['sources']['calibration']['sha256'][:16],
        'V2 upstream RGB + I+1 OFFLINE; no RGB/GT pixels shown',
        'Physical sensor range / surface ownership / accuracy UNKNOWN'])
    ax.text(0,1,'\n'.join(lines),va='top',fontsize=7.4,family='monospace')
    fig.suptitle(f'DS10 actual depth diagnosis F{case["global_q"]} — {case["selection_reason"]}',fontsize=14)
    path=PRIVATE/f'F{case["global_q"]}_{case["event"]}.png';assert not path.exists()
    fig.savefig(path,dpi=115,metadata={'Description':'Actual depth/masks; no RGB or GT raster; diagnostic only'});plt.close(fig)
    return artifact(path)


def main():
    assert not (HERE/'CASE_STATS.json').exists()
    PRIVATE.mkdir(parents=True,exist_ok=True)
    score=read(DS9/'run/SCORING_SEALED.json')
    for name in ('METRICS.json','EVENT_AUDIT.json'):
        assert artifact(DS9/'run'/name)['sha256']==score['artifacts_sha256'][name]
    refs={(x['segment'],x['arm'],x['event']):x for x in read(DS9/'run/EVENT_AUDIT.json')['events']}
    source_reader=RestoredDepth();cases=[];figures=[];bindings={}
    for name,(start,stop) in SEGMENTS.items():
        public=DS9/'run'/name/'public';sealed=read(public/'PREDICTIONS_SEALED.json')
        events=read(public/'EVENTS.json');qualified=[e for e in events[V2] if e['q'] is not None]
        qset={e['q'] for e in qualified}
        measurements={r['frame']:r for r in rows(public/'DEPTH_OBSERVATIONS.jsonl.gz') if r['frame'] in qset}
        assignments={r['frame']:r for r in rows(input_dir(name)/'assignments.jsonl.gz') if r['frame'] in qset}
        originals=read(input_dir(name)/'sources.json')
        for f in ['EVENTS.json','DEPTH_OBSERVATIONS.jsonl.gz']:
            entry=artifact(public/f);assert entry['sha256']==sealed['artifacts_sha256'][f];bindings[str(public/f)]=entry
        for e in qualified:
            f=e['q'];global_q=start+f-1;old=measurements[f]
            rawpath=Path(originals[f-1]['depth_path']);rawbinding=artifact(rawpath);assert rawbinding['sha256']==originals[f-1]['depth_sha256']
            with np.load(rawpath) as sensor:raw=sensor['depth_mm'];rawindex=sensor['source_index']
            v2,prov,meta=source_reader(global_q);v2index=source_reader.current_source_index
            masks={int(k[2:]):decode(v) for k,v in assignments[f]['masks'].items()}
            occupancy=np.zeros(raw.shape,'u2')
            for mask in masks.values():occupancy+=mask
            rawfull,rawmeasured=measure_raw(raw,masks,occupancy,name,f)
            v2full,v2measured=measure_restored(v2,prov,masks,occupancy,name,f)
            assert rawfull==old['adaptive_full'] and v2full==old['restored_full']
            for n in masks:
                for now,prior in [(rawmeasured[n],old['adaptive_raw'][str(n)]),(v2measured[n],old['restored'][str(n)])]:
                    assert now['core']==prior['core'] and now['core_usable']==prior['core_usable']
            branch_events={arm:next(x for x in events[arm] if x['id']==e['id']) for arm in (RAW,V2,PERM)}
            branch={arm:decision(x,refs[(name,arm,e['id'])]) for arm,x in branch_events.items()}
            postids=list(map(int,e['post_first_observations']));rois={n:adaptive_core(masks[n],occupancy)[0] for n in postids}
            union=np.logical_or.reduce([masks[n] for n in postids])
            ring=cv2.dilate(union.astype('u1'),np.ones((41,41),'u1')).astype(bool)&(occupancy==0)
            v2bind=artifact(Path(meta['native_path']))
            nativepath=DATA/'depth_native_mm'/f'{global_q:06d}.npy';native=np.load(nativepath).ravel()
            posts={}
            for n,roi in rois.items():
                shared=roi&(raw>0)&(v2>0);rawpoints=rawindex[roi&(raw>0)];v2points=v2index[roi&(v2>0)]
                assert np.all(rawpoints>=0) and np.all(v2points>=0)
                expectedz=source_reader.geom.rc.reshape(-1,3)[rawpoints,2]*native[rawpoints]+source_reader.geom.t[2]
                error=float(np.max(np.abs(raw[roi&(raw>0)].astype(float)-expectedz))) if len(rawpoints) else 0.
                assert error<.002
                posts[str(n)]=dict(raw=public_measurement(rawmeasured[n]),v2=public_measurement(v2measured[n]),
                    ring_raw=statistics(raw,ring),ring_v2=statistics(v2,ring),
                    raw_mask=statistics(raw,masks[n]),v2_mask=statistics(v2,masks[n]),
                    source_binding=dict(shared_valid_roi_pixels=int(shared.sum()),same_native_winner_on_shared_valid=int(((rawindex==v2index)&shared).sum()),
                        raw_native_z_median_mm=float(np.median(native[rawpoints])) if len(rawpoints) else None,
                        raw_recorded_reprojection_max_error_mm=error,
                        raw_source_index_sha256=hashlib.sha256(rawpoints.astype('<i4').tobytes()).hexdigest(),
                        v2_source_index_sha256=hashlib.sha256(v2points.astype('<i4').tobytes()).hexdigest()),
                    raw_core_suspect_gt5000=int((roi&(raw>5000)).sum()),v2_core_suspect_gt5000=int((roi&(v2>5000)).sum()))
            reasons=[]
            if branch[V2]['first_public_reference']=='WRONG':reasons.append('all remaining WRONG first publications')
            if branch[V2]['visible_member_residual']:reasons.append('all visible-member residual restrictions')
            if global_q in (519,1027):reasons.append('correct-depth vs harmful actual permutation')
            case=dict(segment=name,event=e['id'],local_q=f,global_q=global_q,time=old['time'],
                selection_reason='; '.join(reasons),branches=branch,posts=posts,full_raw=rawfull,full_v2=v2full,
                object_population_raw=population(rawmeasured),object_population_v2=population(v2measured),
                source_context=dict(current_prediction_masks=len(masks),post_sources=postids,
                    visible_residual_sources=branch[V2]['visible_member_residual'],other_mask_sources=sorted(set(masks)-set(postids)),
                    local_ring_rule='41x41 dilation of both current post masks, excluding every current predicted mask; unlabeled proxy, not certified background'),
                sources=dict(raw_aligned=rawbinding,native_raw=artifact(nativepath),v2_native=v2bind,v2_row=meta['native_row'],
                    calibration=artifact(DATA/'calibration.json'),timing=old['timing'],restored_metadata=meta),
                physical_surface_identity='UNKNOWN',gt_used_for_display_selection_only=True)
            cases.append(case)
            if reasons:figures.append(dict(global_q=global_q,event=e['id'],selection_reason=case['selection_reason'],artifact=draw(case,(raw,v2,prov,masks,occupancy,rois,ring),branch_events)))
    r=source_reader.geom.r
    source_reader.close()
    assert len(cases)==19 and len(figures)==10
    assert {c['global_q'] for c in cases if c['branches'][V2]['first_public_reference']=='WRONG'}=={470,764,1390,1805}
    stats=dict(status='ACTUAL_DS9_ALL_Q_DEPTH_DIAGNOSIS',created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        q_events=19,private_figures=10,source_bindings=bindings,scoring=artifact(DS9/'run/SCORING_SEALED.json'),
        source_reader=artifact(DS9/'restored_source.py'),measurement=artifact(DS9/'measurement.py'),
        diagnostic_code=artifact(Path(__file__)),cases=cases,
        calibration_summary=dict(recorded_rotation_det=float(np.linalg.det(r)),singular_values=np.linalg.svd(r,compute_uv=False).tolist(),
            orthogonality_error=float(np.linalg.norm(r.T@r-np.eye(3))),changed=False,physical_calibration_accuracy='UNKNOWN'),
        semantics=dict(actual_MAD='cohort statistic',inferred_adapter='max(actualMAD,60/1.4826), assumed noise, not measured MAD',
            source_index_binding='recorded camera-Z exact numerical reprojection; not physical depth certification',
            background_proxy='whole/ring statistics, not GT-certified tank surface',SUSPECT_5000='display diagnostic, not sensor maximum or pixel exclusion'),
        RGB_reads=0,GT_raster_reads=0,new_model_calls=0,new_replays=0)
    write_new(HERE/'CASE_STATS.json',stats)
    write_new(HERE/'PRIVATE_INVENTORY.json',dict(private_figures=figures,not_for_Git=True,no_RGB_or_GT_raster=True))
    fig,ax=plt.subplots(figsize=(13,5));x=np.arange(len(cases))
    for off,arm,color in [(-.25,RAW,'#59a14f'),(0,V2,'#4169e1'),(.25,PERM,'#e15759')]:
        ax.bar(x+off,[c['branches'][arm]['margin'] for c in cases],width=.25,label=arm,color=color)
    ax.set_xticks(x,[str(c['global_q']) for c in cases],rotation=45);ax.axhline(math.log(9),color='black',linestyle='--',label='old frozen joint margin log9')
    ax.set_xlabel('All 19 original DS9 first-split frames');ax.set_ylabel('logged margin (H0-best is KEEP, not restore)')
    ax.set_title('DS9 complete q coverage; public numbers only, no pixel geometry');ax.legend(fontsize=8);fig.tight_layout()
    assert not (HERE/'DECISION_SUMMARY.svg').exists();fig.savefig(HERE/'DECISION_SUMMARY.svg');plt.close(fig)
    print('Actual all-q diagnostics PASS:',len(cases),'events,',len(figures),'private figures')


if __name__=='__main__':main()
