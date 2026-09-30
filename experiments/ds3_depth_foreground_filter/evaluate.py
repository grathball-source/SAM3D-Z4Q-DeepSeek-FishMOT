"""Postseal silhouette-occupancy audit, not physical depth or tracking accuracy."""
import csv
import gzip
import json
import time
from collections import Counter
from pathlib import Path

from common import (HERE, ROOT, DATA, SEGMENTS, CFG, verify, artifact, records, decode,
                    load_depth, KERNEL, cv2, np, dump_line, write_new, digest)


def check_seal():
    seal=json.loads((HERE/'MEASUREMENTS_SEALED.json').read_text())
    assert seal['status']=='SEALED_AWAITING_REFERENCE_OCCUPANCY_SCORING'
    for item in seal['artifacts']: verify(item)
    freeze=json.loads((HERE/'FREEZE.json').read_text())
    for item in freeze['code']+freeze['locked_sources']: verify(item)
    for key in ('source_inventory','old_readonly'): verify(freeze[key])
    for item in json.loads(Path(freeze['old_readonly']['path']).read_text()):
        assert digest(ROOT/item['path'])==item['sha256'],item
    inventory=json.loads(Path(freeze['source_inventory']['path']).read_text())
    for rows in inventory.values():
        for row in rows:
            for kind in ('prediction','depth'):
                verify(dict(path=row[kind+'_path'],bytes=row[kind+'_bytes'],sha256=row[kind+'_sha256']))
    return seal,inventory


def truth_masks(path):
    document=json.loads(path.read_text(encoding='utf-8'))
    assert document['imageHeight']==360 and document['imageWidth']==640
    masks={}
    for shape in document['shapes']:
        assert shape['shape_type']=='polygon'
        key=int(shape['group_id'])
        region=masks.setdefault(key,np.zeros((360,640),'u1'))
        cv2.fillPoly(region,[np.rint(np.asarray(shape['points'],float)).astype('i4')],1)
    return {key:region.astype(bool) for key,region in masks.items()}


def occupancy_counts(sample, matched, all_truth):
    fish=int((sample & matched).sum())
    other=int((sample & all_truth & ~matched).sum())
    background=int((sample & ~all_truth).sum())
    n=int(sample.sum())
    assert fish+other+background==n
    return dict(n=n,fish=fish,other_fish=other,background=background,
                purity=fish/n if n else None)


def pooled(rows, method):
    fields=('n','fish','other_fish','background')
    result={key:sum(row[method][key] for row in rows) for key in fields}
    result['purity']=result['fish']/result['n'] if result['n'] else None
    values=[r[method]['purity'] for r in rows if r[method]['purity'] is not None]
    result['objects_with_samples']=len(values)
    result['mean_object_purity']=float(np.mean(values)) if values else None
    return result


def summarize(rows):
    scored=[r for r in rows if r['reference_status']=='SCORABLE']
    available=[r for r in scored if r['filter_status']=='AVAILABLE']
    paired=[r for r in available if r['core']['n']>0 and r['whole']['fish']>0]
    core_usable=[r for r in rows if r['core_usable']]
    metrics={method:pooled(scored,method) for method in ('whole','core','foreground')}
    pair_metrics={method:pooled(paired,method) for method in ('whole','core','foreground')}
    gain=(100*(pair_metrics['foreground']['purity']-pair_metrics['core']['purity']) if paired else None)
    fish_denom=sum(r['whole']['fish'] for r in paired)
    retention=sum(r['foreground']['fish'] for r in paired)/fish_denom if fish_denom else None
    coverage=sum(r['filter_status']=='AVAILABLE' for r in core_usable)/len(core_usable) if core_usable else None
    deltas=[r['foreground']['purity']-r['core']['purity'] for r in paired]
    decision=('INCONCLUSIVE' if None in (gain,retention,coverage) else
              'PASS_MEASUREMENT_PROXY_ONLY' if gain>=CFG['primary_purity_gain_pp'] and
              retention>=CFG['primary_min_retention'] and coverage>=CFG['primary_min_core_usable_coverage']
              else 'FAIL_FROZEN_MEASUREMENT_HYPOTHESIS')
    return dict(objects=len(rows),scorable=len(scored),unscorable=len(rows)-len(scored),
        accepted=sum(r['filter_status']=='AVAILABLE' for r in rows),unknown=sum(r['filter_status']=='UNKNOWN' for r in rows),
        accepted_scorable=len(available),paired_accepted=len(paired),core_usable=len(core_usable),
        core_usable_acceptance=coverage,all_scorable=metrics,paired_accepted_metrics=pair_metrics,
        purity_gain_pp=gain,matched_foreground_retention=retention,
        paired_objects_improved=sum(d>1e-12 for d in deltas),
        paired_objects_worsened=sum(d< -1e-12 for d in deltas),
        paired_objects_equal=sum(abs(d)<=1e-12 for d in deltas),
        mean_paired_purity_delta_pp=100*float(np.mean(deltas)) if deltas else None,
        median_paired_retention=float(np.median([r['foreground']['fish']/r['whole']['fish'] for r in paired])) if paired else None,
        reference_reasons=dict(Counter(r['reference_status'] for r in rows)),
        filter_reasons=dict(Counter(r['filter_reason'] for r in rows)),decision=decision)


def visualization(selection, measurements, pixels):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    outputs=[]
    for label,row in selection.items():
        if row is None: continue
        key=(row['segment'],row['frame']); token=row['token']
        private=pixels[key]['objects'][token]; fact=measurements[key]['objects'][token]
        depth=load_depth(DATA/'depth_rgb_640x360'/f'{row["frame"]:06d}.npz')
        source=decode(private['source_mask'])
        own_masks=[decode(r['source_mask']) for r in pixels[key]['objects'].values()]
        occ=sum((m.astype('u2') for m in own_masks),np.zeros(depth.shape,'u2'))
        core=cv2.erode((source & (occ==1)).astype('u1'),KERNEL).astype(bool)
        x0,y0,x1,y1=private['crop']; local=depth[y0:y1,x0:x1]
        truth=truth_masks(DATA/'labels_640x360'/f'{row["frame"]:06d}.json')
        gt=sum((m.astype('u2') for m in truth.values()),np.zeros(depth.shape,'u2'))>0
        selected=decode(private['regions']['selected']); annulus=decode(private['regions']['annulus'])
        panels=[('Raw depth',None),('Whole valid samples',source[y0:y1,x0:x1]),
                ('Legacy core valid samples',core[y0:y1,x0:x1]),('Filtered raw samples',selected)]
        fig,axes=plt.subplots(1,4,figsize=(13,4),constrained_layout=True)
        for ax,(title,region) in zip(axes,panels):
            shown=np.ma.masked_where(~np.isfinite(local)|(local<=0),local)
            ax.imshow(shown,cmap='viridis',vmin=800,vmax=1300)
            ax.contour(source[y0:y1,x0:x1],levels=[.5],colors=['silver'],linewidths=.7)
            if gt[y0:y1,x0:x1].any(): ax.contour(gt[y0:y1,x0:x1],levels=[.5],colors=['orange'],linewidths=.6)
            if region is not None:
                overlay=np.zeros((*local.shape,4)); sampled=region & np.isfinite(local) & (local>0)
                overlay[sampled]=[1,0,1,.7]; ax.imshow(overlay)
            if title=='Filtered raw samples': ax.contour(annulus,levels=[.5],colors=['cyan'],linewidths=.6)
            ax.set_title(title); ax.axis('off')
        fig.suptitle(f'{label} F{row["frame"]} {token}: {fact["foreground"]["reason"]}\n'
                     'mm 800–1300; missing white; SAM3 silver / postseal manual orange / samples magenta / annulus cyan')
        path=HERE/'private'/f'{label}.png'; fig.savefig(path,dpi=160); plt.close(fig)
        outputs.append(dict(label=label,frame=row['frame'],token=token,artifact=artifact(path)))
    write_new(HERE/'VISUALIZATION_FILES.json',outputs)


def evaluate():
    seal,inventory=check_seal(); started=time.perf_counter()
    rows=[]; reference_inventory=[]; measurements={}; pixels={}; missing=0
    for name in SEGMENTS:
        streams=zip(records(HERE/f'{name}_measurements.jsonl.gz'),
                    records(HERE/'private'/f'{name}_pixels.jsonl.gz'),strict=True)
        for facts,private in streams:
            frame=facts['frame']; assert frame==private['frame'] and facts['evidence_max_frame']==frame
            reference=DATA/'labels_640x360'/f'{frame:06d}.json'
            reference_inventory.append(artifact(reference))
            truth=truth_masks(reference); all_truth=sum((m.astype('u2') for m in truth.values()),np.zeros((360,640),'u2'))>0
            depth=load_depth(DATA/'depth_rgb_640x360'/f'{frame:06d}.npz'); valid=np.isfinite(depth)&(depth>0)
            sources={t:decode(o['source_mask']) for t,o in private['objects'].items()}
            occ=sum((m.astype('u2') for m in sources.values()),np.zeros(depth.shape,'u2'))
            proposed={}; candidates={}
            for token,source in sources.items():
                comparisons=[]
                for identity,mask in truth.items():
                    union=int((source|mask).sum()); overlap=int((source&mask).sum())
                    comparisons.append((overlap/max(1,union),identity))
                comparisons.sort(reverse=True)
                best=comparisons[0] if comparisons else (0,None)
                margin=best[0]-(comparisons[1][0] if len(comparisons)>1 else 0)
                candidates[token]=(best,margin)
                if best[0]>=CFG['reference_iou_min'] and margin>=CFG['reference_margin_min']:
                    proposed[token]=best[1]
            claims=Counter(proposed.values())
            for token,source in sources.items():
                fact=facts['objects'][token]; pp=private['objects'][token]
                best,margin=candidates[token]
                status=('NO_REFERENCE_POLYGON' if not truth else 'LOW_OR_AMBIGUOUS_IOU' if token not in proposed else
                        'DUPLICATE_REFERENCE_CLAIM' if claims[proposed[token]]!=1 else 'SCORABLE')
                matched=truth[best[1]] if status=='SCORABLE' else np.zeros(depth.shape,bool)
                core=cv2.erode((source&(occ==1)).astype('u1'),KERNEL).astype(bool)
                filtered=np.zeros(depth.shape,bool); x0,y0,x1,y1=pp['crop']
                filtered[y0:y1,x0:x1]=decode(pp['regions']['selected'])
                assert np.all(~filtered|(source&valid&(occ==1)))
                assert int(filtered.sum())==fact['foreground']['selected']['n']
                row=dict(segment=name,frame=frame,token=token,fact_id=fact['fact_id'],
                    reference_status=status,best_iou=best[0],iou_margin=margin,core_usable=fact['core_usable'],
                    filter_status=fact['foreground']['status'],filter_reason=fact['foreground']['reason'],
                    significant_n=fact['foreground']['significant_n'],
                    whole=occupancy_counts(source&valid,matched,all_truth),
                    core=occupancy_counts(core&valid,matched,all_truth),
                    foreground=occupancy_counts(filtered,matched,all_truth),
                    original_missing_n=int((source&~valid).sum()),
                    median_delta_core_mm=(fact['foreground']['selected']['median']-fact['core']['median']
                        if fact['foreground']['status']=='AVAILABLE' and fact['core']['median'] is not None else None),
                    signed_contrast_mm=fact['foreground']['signed_contrast_median_mm'])
                rows.append(row)
            measurements[(name,frame)]=facts; pixels[(name,frame)]=private
        print(f'postseal occupancy scored {name}',flush=True)
    assert len(rows)==seal['objects']
    with gzip.open(HERE/'OCCUPANCY_AUDIT.jsonl.gz','xt',encoding='utf-8') as out:
        for row in rows: dump_line(out,row)
    summaries={name:summarize([r for r in rows if r['segment']==name]) for name in SEGMENTS}
    summaries['POOLED']=summarize(rows)
    write_new(HERE/'SUMMARY.json',dict(decision=summaries['POOLED']['decision'],groups=summaries,
        truth_kind='POSTSEAL_MANUAL_SILHOUETTE_OCCUPANCY_NOT_PHYSICAL_DEPTH_GT',
        frames=seal['frames'],scoring_seconds=time.perf_counter()-started,
        primary_thresholds={k:v for k,v in CFG.items() if k.startswith('primary_')},
        inference_http=0,cost_usd=0))
    write_new(HERE/'REFERENCE_INVENTORY_POSTSEAL.json',reference_inventory)
    accepted=next((r for r in rows if r['filter_status']=='AVAILABLE'),None)
    rejected=next((r for r in rows if r['filter_status']=='UNKNOWN' and r['significant_n']>0),None)
    paired=[r for r in rows if r['reference_status']=='SCORABLE' and r['filter_status']=='AVAILABLE' and r['core']['n']>0]
    worst=min(paired,key=lambda r:(r['foreground']['purity']-r['core']['purity'],r['frame'],r['token'])) if paired else None
    visualization(dict(earliest_accepted=accepted,earliest_significant_unknown=rejected,maximum_purity_decrease=worst),measurements,pixels)
    write_new(HERE/'SCORING_SEALED.json',dict(status='COMPLETE',measurement_seal=artifact(HERE/'MEASUREMENTS_SEALED.json'),
        artifacts=[artifact(HERE/p) for p in ('SUMMARY.json','OCCUPANCY_AUDIT.jsonl.gz','REFERENCE_INVENTORY_POSTSEAL.json','VISUALIZATION_FILES.json')],
        ended_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())))
    print(json.dumps(summaries['POOLED'],indent=2),flush=True)


if __name__=='__main__': evaluate()
