"""Summarize sealed observational results; RGB QA stays private."""
import json
from collections import Counter
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from audit import (HERE,ROOT,DS4,DATA,SEGMENTS,ARMS,CFG,np,cv2,records,decode,artifact,verify,
                   write_new,check_old,load_old,selected_region,truth_masks,matching)


def aggregate(census, oldrows):
    out={}
    for arm in ARMS:
        entries=[r['methods'][arm] for r in census]
        available=[e for e in entries if e['selected_n']]
        summary=dict(objects=len(entries),available=len(available),unknown=len(entries)-len(available),
            selected_fragments_more_than_one=sum(e['selected_spatial_components']>1 for e in available),
            closing_connects_real_fragments=sum(e['selected_spatial_components']>1 and e['support_spatial_components']==1 for e in available),
            depth_graphs={})
        for gap in CFG['depth_edge_gaps_mm']:
            graphs=[e['graphs'][str(gap)] for e in available]
            changed=0; statuses=Counter(); original_statuses=Counter()
            for row in census:
                old=oldrows[(row['frame'],row['token'])]; ref=old['reference']; m=old['methods'][arm]
                g=row['methods'][arm]['graphs'][str(gap)]
                if ref['usable']:
                    original_statuses['U' if m['reference_compatible'] is None else 'C' if m['reference_compatible'] else 'D']+=1
                    qualified=g['largest_median_mm'] is not None and g['largest_n']>=CFG['piece_min_n'] and g['largest_n']/max(1,g['n'])>=CFG['piece_min_fraction']
                    status='U' if not qualified else 'C' if abs(g['largest_median_mm']-ref['median_mm'])<=ref['tolerance_mm'] else 'D'
                    statuses[status]+=1
                    changed+=qualified and g['largest_median_mm']!=m['median_mm']
            summary['depth_graphs'][str(gap)]=dict(
                multiple_pieces=sum(len(g['pieces'])>1 for g in graphs),
                multiple_qualified_pieces=sum(g['qualified_pieces']>=2 for g in graphs),
                old_fixed_R_reference_status=dict(original_statuses),
                largest_piece_shadow_R_reference_status=dict(statuses),
                shadow_changed_median_on_R=int(changed),
                interpretation='ANONYMOUS_DEPTH_PIECE_SHADOW_NOT_NEW_EXTRACTOR_OR_SURFACE_ACCURACY')
        out[arm]=summary
    return out


def grid_summary(rows):
    out={}
    for arm in ARMS:
        totals={}
        for row in rows:
            shifts=row['methods'][arm]['shifts']
            if shifts is None: continue
            assert len(shifts)==49
            for s in shifts:
                key=(s['dx'],s['dy']); value=totals.setdefault(key,Counter())
                value.update(s['counts'])
        curves=[dict(dx=x,dy=y,counts=dict(c),fish_fraction=c['fish']/c['n'] if c['n'] else None) for (x,y),c in sorted(totals.items())]
        nonzero=[r['fish_fraction'] for r in curves if (r['dx'] or r['dy']) and r['fish_fraction'] is not None]
        out[arm]=dict(objects=len(rows),scorable=sum(r['methods'][arm]['shifts'] is not None for r in rows),
            curves=curves,zero=next((r for r in curves if r['dx']==r['dy']==0),None),
            nonzero_fraction_range=[min(nonzero),max(nonzero)] if nonzero else None,
            chosen_transform=None,interpretation='FIXED_COORDINATE_SENSITIVITY_NOT_CALIBRATION_OR_SURFACE_GT')
    return out


def figure(case, facts, pixels):
    frame,token=case['frame'],case['token']
    source=decode(pixels['objects'][token]['source_mask'])
    y,x=np.nonzero(source); x0,x1=max(0,x.min()-20),min(640,x.max()+21); y0,y1=max(0,y.min()-20),min(360,y.max()+21)
    with np.load(DATA/'depth_rgb_640x360'/f'{frame:06d}.npz') as sensor: depth=sensor['depth_mm'].copy(); index=sensor['source_index'].copy()
    native=np.load(DATA/'depth_native_mm'/f'{frame:06d}.npy'); valid=depth>0
    suspect=np.zeros(depth.shape,bool); suspect[valid]=native.ravel()[index[valid]]>5000
    rgb=cv2.cvtColor(cv2.imread(str(DATA/'rgb_640x360'/f'{frame:06d}.png')),cv2.COLOR_BGR2RGB)
    truth=truth_masks(DATA/'labels_640x360'/f'{frame:06d}.json')
    sources={t:decode(o['source_mask']) for t,o in pixels['objects'].items()}
    match=matching(sources,truth)[token]
    matched=truth[match['identity']] if match['status']=='SCORABLE' else None
    regular=depth[y0:y1,x0:x1][valid[y0:y1,x0:x1]&~suspect[y0:y1,x0:x1]]
    lo,hi=(float(regular.min()),float(regular.max())) if regular.size else (0.,1.)
    fig,axes=plt.subplots(2,4,figsize=(18,10),constrained_layout=True)
    ax=axes[0,0]; ax.imshow(rgb[y0:y1,x0:x1]); ax.contour(source[y0:y1,x0:x1],levels=[.5],colors='white',linewidths=1)
    if matched is not None: ax.contour(matched[y0:y1,x0:x1],levels=[.5],colors='gold',linewidths=1)
    ax.set_title('Current RGB: source white, manual RGB gold\nNeither contour certifies measured surface')
    crop=depth[y0:y1,x0:x1]; show=np.ma.masked_where(crop<=0,crop)
    ax=axes[0,1]; im=ax.imshow(show,vmin=lo,vmax=hi,cmap='viridis')
    ys,xs=np.nonzero(suspect[y0:y1,x0:x1]); ax.scatter(xs,ys,c='red',s=8)
    fig.colorbar(im,ax=ax,label='Raw RGB-camera Z mm; red native>5m')
    ax.set_title(f'Original raw depth, max {crop.max():.1f} mm\nMissing unfilled; anomalies shown red')
    selecteds={}
    for j,arm in enumerate(ARMS):
        full,_,_,_=selected_region(pixels['objects'][token],arm,depth); selecteds[arm]=full
        ax=axes[0,2+j]; ax.imshow(show,vmin=lo,vmax=hi,cmap='viridis')
        yy,xx=np.nonzero(full[y0:y1,x0:x1]); ax.scatter(xx,yy,c='lime',s=8)
        stat=facts['objects'][token]['methods'][arm]['selector']['selected']
        med=f'{stat["median"]:.2f}' if stat['median'] is not None else 'UNKNOWN'
        ax.set_title(f'{arm}: {stat["n"]} actual raw points\nmedian {med} mm; green selection')
    ax=axes[1,0]
    ax.imshow(rgb[y0:y1,x0:x1]); ys,xs=np.nonzero(selecteds[ARMS[1]][y0:y1,x0:x1]); values=crop[ys,xs]
    sc=ax.scatter(xs,ys,c=values,cmap='plasma',s=15,vmin=lo,vmax=hi); fig.colorbar(sc,ax=ax,label='Selected raw mm')
    ax.set_title('F6 spatial location vs raw value\nDepth layers remain anonymous')
    ax=axes[1,1]
    all_values=np.concatenate([depth[s] for s in selecteds.values()])
    bins=np.linspace(all_values.min()-1,all_values.max()+1,31) if all_values.size else np.linspace(0,1,31)
    for arm,s in selecteds.items(): ax.hist(depth[s],bins=bins,histtype='step',label=arm,linewidth=2)
    ax.legend(fontsize=8); ax.set_xlabel('Original selected RGB-camera Z mm'); ax.set_ylabel('Measured points')
    ax.set_title('Same histogram bins; no filled samples')
    ax=axes[1,2]
    if matched is not None and selecteds[ARMS[1]].any():
        from audit import shift_counts
        grid=CFG['shift_grid_px']; image=np.array([[shift_counts(selecteds[ARMS[1]],matched,np.logical_or.reduce(list(truth.values())),dx,dy)['fish']/int(selecteds[ARMS[1]].sum()) for dx in grid] for dy in grid])
        im=ax.imshow(image,vmin=0,vmax=1,cmap='magma'); ax.set_xticks(range(7),grid); ax.set_yticks(range(7),grid)
        ax.set_xlabel('dx px'); ax.set_ylabel('dy px'); fig.colorbar(im,ax=ax,label='Matched RGB contour fraction, fixed n')
    else: ax.text(.1,.5,'UNKNOWN / zero selected points',transform=ax.transAxes)
    ax.set_title('Complete 49-cell coordinate sensitivity\nNo transform selected or applied')
    axes[1,3].axis('off'); axes[1,3].text(0,.95,'Evidence boundary\n\nCurrent frame only.\nOriginal depth/source indices.\nOriginal selections unchanged.\nRGB silhouette is not depth truth.\nFish/background physical surface: UNKNOWN.\nNo tracking, model or correction.\n\n'+ '\n'.join(case['reasons']),va='top',wrap=True,fontsize=10)
    for ax in axes[0,:]: ax.axis('off')
    axes[1,0].axis('off')
    fig.suptitle(f'DS5 frozen diagnostic F{frame}/{token} — private original pixels, physical surface UNKNOWN',fontsize=14)
    output=HERE/'private/visualizations'/f'F{frame}_{token}.png'; output.parent.mkdir(parents=True,exist_ok=True)
    assert not output.exists(); fig.savefig(output,dpi=130); plt.close(fig)
    return dict(frame=frame,token=token,artifact=artifact(output),RGB_read=True,manual_RGB_contour=True,physical_surface='UNKNOWN')


def report():
    assert not (HERE/'SUMMARY.json').exists(),'refuse overwrite'
    check_old(); seal=json.loads((HERE/'AUDIT_SEALED.json').read_text(encoding='utf-8'))
    for item in seal['artifacts']: verify(item)
    census=list(records(HERE/'CENSUS.jsonl.gz')); registration=list(records(HERE/'REGISTRATION.jsonl.gz'))
    cohort=json.loads((HERE/'COHORT.json').read_text(encoding='utf-8'))['cases']
    assert len(census)==28382 and len(registration)==len(cohort)==seal['cohort_n']
    old,facts=load_old(); oldrows={(r['frame'],r['token']):r for r in old}
    keys={(c['frame'],c['token']):c for c in cohort}
    cases=[r for r in registration if keys[(r['frame'],r['token'])]['reasons']!=['NEAREST_STABLE_DIAGNOSTIC_CONTROL']]
    controls=[r for r in registration if keys[(r['frame'],r['token'])]['reasons']==['NEAREST_STABLE_DIAGNOSTIC_CONTROL']]
    groups={name:aggregate([r for r in census if r['segment']==name],oldrows) for name in SEGMENTS}
    groups['POOLED']=aggregate(census,oldrows)
    new=[r for r in census if 'ALL_NEW_REFERENCE_CONFLICTS' in keys.get((r['frame'],r['token']),{}).get('reasons',[])]
    assert len(new)==44
    selected_cases=[c for c in cohort if 'SEALED_KNOWN_CASE' in c['reasons']]
    known=[dict(case=c,census=next(r for r in census if (r['frame'],r['token'])==(c['frame'],c['token'])),
                old_reference=oldrows[(c['frame'],c['token'])]['reference'],old_methods=oldrows[(c['frame'],c['token'])]['methods'],
                registration=next(r for r in registration if (r['frame'],r['token'])==(c['frame'],c['token']))) for c in selected_cases]
    write_new(HERE/'KNOWN_CASES.json',known)
    new_conflicts=aggregate(new,oldrows)
    summary=dict(status='AUDIT_COMPLETE',main_scientific_status='SURFACE_AND_PHYSICAL_REGISTRATION_UNRESOLVED',
        base=CFG['base'],fixed_S=28382,fixed_Q=28088,fixed_R=21817,groups=groups,
        new_conflicts_all_44=new_conflicts,cohort=dict(n=len(cohort),cases=len(cases),unique_controls=len(controls),
            reasons=dict(Counter(reason for c in cohort for reason in c['reasons'])),cases_without_stable_control=sum(c['control'] is None for c in cohort if c['reasons']!=['NEAREST_STABLE_DIAGNOSTIC_CONTROL'])),
        registration_cases=grid_summary(cases),registration_controls=grid_summary(controls),
        calibration=json.loads((HERE/'CALIBRATION_STRUCTURE.json').read_text(encoding='utf-8')),
        runtime_seconds=seal['seconds'],model_http=0,cost_usd=0,tracker_runs=0,new_measurement_accuracy='NOT_MEASURED',
        physical_surface_labels='UNAVAILABLE_UNKNOWN',blind_validation=False,no_transform_applied=True)
    write_new(HERE/'SUMMARY.json',summary)
    required={c['frame'] for c in selected_cases}
    pixels={}; measured={}
    for name in SEGMENTS:
        for r in records(DS4/'private'/f'{name}_pixels.jsonl.gz'):
            if r['frame'] in required: pixels[r['frame']]=r
        for r in records(DS4/f'{name}_measurements.jsonl.gz'):
            if r['frame'] in required: measured[r['frame']]=r
    figures=[figure(c,measured[c['frame']],pixels[c['frame']]) for c in selected_cases]
    write_new(HERE/'VISUALIZATION_FILES.json',figures)
    # Public chart contains sealed counts only, never image/raster pixels.
    fig,ax=plt.subplots(figsize=(9,4)); width=.35
    for i,arm in enumerate(ARMS):
        v=groups['POOLED'][arm]; vals=[v['selected_fragments_more_than_one'],v['closing_connects_real_fragments'],v['depth_graphs']['30']['multiple_qualified_pieces'],v['depth_graphs']['60']['multiple_qualified_pieces']]
        ax.bar(np.arange(4)+i*width,vals,width,label=arm)
    ax.set_xticks(np.arange(4)+width/2,['Real point\ncomponents >1','Closed support\nconnects fragments','Depth parts >=2\n30 mm edges','Depth parts >=2\n60 mm edges'])
    ax.set_ylabel('Objects among fixed S=28382'); ax.legend(); fig.tight_layout()
    output=HERE/'CONNECTIVITY_SUMMARY.svg'; assert not output.exists(); fig.savefig(output); plt.close(fig)
    write_new(HERE/'REPORT_SEALED.json',dict(status='SEALED_POSTAUDIT_SUMMARY',audit_seal=artifact(HERE/'AUDIT_SEALED.json'),
        artifacts=[artifact(HERE/p) for p in ('SUMMARY.json','KNOWN_CASES.json','VISUALIZATION_FILES.json','CONNECTIVITY_SUMMARY.svg')]))
    print(json.dumps(dict(status=summary['status'],cohort=summary['cohort'],pooled=groups['POOLED'],new44=new_conflicts),indent=2))


if __name__=='__main__': report()
