"""Score all frozen samples after seal against fixed silhouette/raw references.

These references are not physical depth ground truth. No extraction result
selects its matched silhouette or reference population.
"""
import gzip
import json
import time
from collections import Counter
from pathlib import Path

from bootstrap import (HERE, ROOT, DATA, DS3, SEGMENTS, ARMS, CONFIG, np, cv2,
    coco, KERNEL, verify, artifact, digest, records, decode, encoded, statistics,
    dump_line, write_new)
from score_helpers import summarize, classify_primary


def check_seal():
    seal=json.loads((HERE/'MEASUREMENTS_SEALED.json').read_text())
    assert seal['status']=='SEALED_BEFORE_NEW_REFERENCE_SCORING'
    for item in seal['artifacts']: verify(item)
    freeze=json.loads((HERE/'FREEZE.json').read_text())
    assert freeze['arms']=={k:list(v) for k,v in ARMS.items()}
    for item in freeze['code']+freeze['locked']+freeze['legacy_code']: verify(item)
    for key in ('source_inventory','old_readonly'): verify(freeze[key])
    for item in json.loads(Path(freeze['old_readonly']['path']).read_text()):
        assert digest(ROOT/item['path'])==item['sha256'],item
    inventory=json.loads(Path(freeze['source_inventory']['path']).read_text())
    for rows in inventory['original'].values():
        for row in rows:
            for kind in ('prediction','depth'):
                verify(dict(path=row[kind+'_path'],bytes=row[kind+'_bytes'],sha256=row[kind+'_sha256']))
    for item in inventory['native']+[inventory['calibration'],inventory['dataset_readme']]: verify(item)
    return seal,inventory


def truth_masks(path):
    document=json.loads(path.read_text(encoding='utf-8'))
    assert document['imageHeight']==360 and document['imageWidth']==640
    masks={}
    for shape in document['shapes']:
        assert shape['shape_type']=='polygon'
        region=masks.setdefault(int(shape['group_id']),np.zeros((360,640),'u1'))
        cv2.fillPoly(region,[np.rint(np.asarray(shape['points'],float)).astype('i4')],1)
    return {key:region.astype(bool) for key,region in masks.items()}


def counts(sample,matched,all_truth):
    fish=int((sample&matched).sum()); other=int((sample&all_truth&~matched).sum())
    background=int((sample&~all_truth).sum()); n=int(sample.sum())
    assert n==fish+other+background
    return dict(n=n,fish=fish,other_fish=other,background=background)


def usable(stat):
    scale=max(CONFIG['reference_scale_floor_mm'],1.4826*stat['mad']) if stat['n'] else None
    return bool(stat['n']>=CONFIG['reference_min_n'] and
        stat['valid_fraction']>=CONFIG['reference_min_fraction'] and
        scale<=CONFIG['reference_max_scale_mm']),scale


def matching(sources,truth):
    tokens=list(sources); identities=list(truth)
    if identities:
        matrix=coco.iou([encoded(sources[t]) for t in tokens],
                        [encoded(truth[i]) for i in identities],[0]*len(identities))
    else: matrix=np.zeros((len(tokens),0))
    candidates={}; proposed={}
    for index,token in enumerate(tokens):
        pairs=sorted(((float(matrix[index,j]),i) for j,i in enumerate(identities)),reverse=True)
        best=pairs[0] if pairs else (0,None)
        margin=best[0]-(pairs[1][0] if len(pairs)>1 else 0)
        candidates[token]=(best,margin)
        if best[0]>=CONFIG['reference_iou_min'] and margin>=CONFIG['reference_margin_min']:
            proposed[token]=best[1]
    claims=Counter(proposed.values())
    return {token:dict(best_iou=candidates[token][0][0],iou_margin=candidates[token][1],
        identity=candidates[token][0][1],status='NO_REFERENCE_POLYGON' if not truth else
        'LOW_OR_AMBIGUOUS_IOU' if token not in proposed else
        'DUPLICATE_REFERENCE_CLAIM' if claims[proposed[token]]!=1 else 'SCORABLE') for token in tokens}


def control_summary(rows,field):
    q=[r for r in rows if r['reference_status']=='SCORABLE']
    pooled={key:sum(r[field][key] for r in q) for key in ('n','fish','other_fish','background')}
    denom=sum(r['whole']['fish'] for r in q)
    return dict(q_n=len(q),selected_counts=pooled,micro_purity=pooled['fish']/pooled['n'] if pooled['n'] else None,
        fish_yield=pooled['fish']/denom if denom else None,
        nonfish_yield=(pooled['other_fish']+pooled['background'])/denom if denom else None)


def group_summary(rows):
    arms={a:summarize(rows,a) for a in ARMS}
    for arm in arms:
        errors=[r['methods'][arm]['reference_abs_error_mm'] for r in rows
                if r['reference_usable'] and r['methods'][arm]['status']=='AVAILABLE']
        arms[arm]['conditional_reference_error']=dict(n=len(errors),
            median_mm=float(np.median(errors)) if errors else None,
            q90_mm=float(np.quantile(errors,.9)) if errors else None,
            mean_mm=float(np.mean(errors)) if errors else None)
    primary=CONFIG['primary_arm']; base='F2_DS3'
    paired=[r for r in rows if r['reference_status']=='SCORABLE' and
            all(r['methods'][a]['status']=='AVAILABLE' for a in (primary,base))]
    purity={}
    for arm in (base,primary):
        n=sum(r['methods'][arm]['occupancy']['n'] for r in paired)
        purity[arm]=sum(r['methods'][arm]['occupancy']['fish'] for r in paired)/n if n else None
    return dict(decision=classify_primary(arms[primary],arms[base]),arms=arms,
        raw_controls={field:control_summary(rows,field) for field in ('whole','core')},
        common_available_only=dict(objects=len(paired),micro_purity=purity,
            caveat='CONDITIONAL_DESCRIPTION_NOT_PRIMARY_POPULATION'),
        reference_reasons=dict(Counter(r['reference_status'] for r in rows)),
        range_suspect_reference_objects=sum((r['reference'].get('suspect_n') or 0)>0 for r in rows))


def evaluate():
    seal,inventory=check_seal(); started=time.perf_counter(); rows=[]; reference_inventory=[]
    old={(r['frame'],r['token']):r for r in records(DS3/'OCCUPANCY_AUDIT.jsonl.gz')}
    for name,(start,stop) in SEGMENTS.items():
        with gzip.open(HERE/f'{name}_occupancy.jsonl.gz','xt',encoding='utf-8') as out:
            streams=zip(records(HERE/f'{name}_measurements.jsonl.gz'),
                records(HERE/'private'/f'{name}_pixels.jsonl.gz'),inventory['original'][name],strict=True)
            for facts,private,source in streams:
                frame=facts['frame']; assert frame==private['frame']==source['frame']
                assert facts['evidence_max_frame']==frame
                assert facts['source_depth_sha256']==source['depth_sha256']
                assert facts['source_prediction_sha256']==source['prediction_sha256']
                path=DATA/'labels_640x360'/f'{frame:06d}.json'
                reference_inventory.append(artifact(path)); truth=truth_masks(path)
                truth_occ=sum((m.astype('u2') for m in truth.values()),np.zeros((360,640),'u2'))
                all_truth=truth_occ>0
                with np.load(Path(source['depth_path'])) as sensor: depth=sensor['depth_mm'].copy()
                valid=np.isfinite(depth)&(depth>0); suspect=decode(private['suspect'])
                sources={t:decode(o['source_mask']) for t,o in private['objects'].items()}
                occ=sum((m.astype('u2') for m in sources.values()),np.zeros(depth.shape,'u2'))
                matches=matching(sources,truth)
                for token,region in sources.items():
                    fact=facts['objects'][token]; pix=private['objects'][token]; match=matches[token]
                    previous=old[(frame,token)]
                    assert match['status']==previous['reference_status']
                    assert match['best_iou']==previous['best_iou'] and match['iou_margin']==previous['iou_margin']
                    scorable=match['status']=='SCORABLE'
                    matched=truth[match['identity']] if scorable else None
                    core=cv2.erode((region&(occ==1)).astype('u1'),KERNEL).astype(bool)
                    reference=dict(status='UNSCORABLE',usable=False,statistics=None,scale_mm=None,
                                   median_mm=None,tolerance_mm=None,suspect_n=None)
                    if scorable:
                        refmask=cv2.erode((matched&(truth_occ==1)).astype('u1'),KERNEL).astype(bool)
                        stat=statistics(depth,refmask); good,scale=usable(stat)
                        reference=dict(status='RAW_SILHOUETTE_CORE_QUALIFIED' if good else 'RAW_REFERENCE_UNAVAILABLE',
                            usable=good,statistics=stat,scale_mm=scale,median_mm=stat['median'],
                            tolerance_mm=max(CONFIG['reference_tolerance_floor_mm'],
                                CONFIG['reference_tolerance_scale_factor']*scale) if good else None,
                            suspect_n=int((refmask&suspect&valid).sum()))
                    methods={}
                    for arm,item in fact['methods'].items():
                        selected=np.zeros(depth.shape,bool); x0,y0,x1,y1=item['selector']['crop']
                        selected[y0:y1,x0:x1]=decode(pix['methods'][arm]['regions']['selected'])
                        assert np.all(~selected|(region&valid&(occ==1)))
                        computed=statistics(depth,selected)
                        assert computed==item['selector']['selected'],(frame,token,arm,'raw facts binding')
                        assert not ARMS[arm][0] or not np.any(selected&suspect)
                        available=item['selector']['status']=='AVAILABLE'
                        assert available==bool(computed['n'])
                        error=abs(computed['median']-reference['median_mm']) if available and reference['usable'] else None
                        methods[arm]=dict(status=item['selector']['status'],reason=item['selector']['reason'],
                            selected_n=computed['n'],median_mm=computed['median'],
                            occupancy=counts(selected,matched,all_truth) if scorable else None,
                            reference_abs_error_mm=error,
                            reference_compatible=bool(error<=reference['tolerance_mm']) if error is not None else None,
                            selected_sign=item['selector'].get('selected_sign'),
                            contrast_mm=item['selector']['signed_contrast_median_mm'],
                            background_noise_mm=(item['selector']['plane']['residual_scale_mm'] if item['selector']['plane'] else None))
                    row=dict(segment=name,frame=frame,token=token,fact_id=fact['fact_id'],
                        reference_status=match['status'],best_iou=match['best_iou'],iou_margin=match['iou_margin'],
                        reference_usable=reference['usable'],reference=reference,
                        whole=counts(region&valid,matched,all_truth) if scorable else None,
                        core=counts(core&valid,matched,all_truth) if scorable else None,
                        raw_core_usable=fact['core_usable'],methods=methods)
                    if scorable:
                        assert row['whole']=={k:previous['whole'][k] for k in row['whole']}
                        assert row['core']=={k:previous['core'][k] for k in row['core']}
                        assert methods['F2_DS3']['occupancy']=={k:previous['foreground'][k] for k in row['whole']}
                    rows.append(row); dump_line(out,row)
                if (frame-start+1)%200==0 or frame==stop:
                    print(f'postseal scored {name} {frame-start+1}/{stop-start+1}; Q exactly unchanged',flush=True)
    assert len(rows)==seal['objects']==28382
    assert sum(r['reference_status']=='SCORABLE' for r in rows)==28088
    groups={n:group_summary([r for r in rows if r['segment']==n]) for n in SEGMENTS}
    groups['POOLED']=group_summary(rows)
    known=[r for r in rows if (r['frame'],r['token']) in ((704,'o013'),(766,'o012'),(1319,'o007'),(1673,'o022'))]
    primary=CONFIG['primary_arm']; base='F2_DS3'
    new_available=next((r for r in rows if r['methods'][primary]['status']=='AVAILABLE' and
        r['methods'][base]['status']=='UNKNOWN'),None)
    new_discordant=next((r for r in rows if r['methods'][primary]['reference_compatible'] is False and
        r['methods'][base]['reference_compatible'] is not False),None)
    transitions=Counter((r['methods'][base]['status'],r['methods'][primary]['status']) for r in rows)
    write_new(HERE/'SUMMARY.json',dict(decision=groups['POOLED']['decision'],groups=groups,
        reference_kind='POSTSEAL_RAW_MANUAL_SILHOUETTE_CONSENSUS_NOT_PHYSICAL_DEPTH_GT',
        frames=seal['frames'],objects=len(rows),scoring_seconds=time.perf_counter()-started,
        primary_arm=primary,actual_arms={a:list(v) for a,v in ARMS.items()},
        primary_status_transitions=[dict(old=a,new=b,n=n) for (a,b),n in sorted(transitions.items())],
        inference_http=0,smoke=0,cost_usd=0,tracking_run=False,
        physical_depth_accuracy='UNKNOWN',blind_validation=False,upstream_sam3_lookahead='UNKNOWN'))
    write_new(HERE/'CASES_POSTSEAL.json',dict(exposed_regressions=known,
        earliest_new_primary_available=new_available,earliest_new_primary_discordant=new_discordant))
    write_new(HERE/'REFERENCE_INVENTORY_POSTSEAL.json',reference_inventory)
    outputs=[artifact(HERE/f'{n}_occupancy.jsonl.gz') for n in SEGMENTS]+[
        artifact(HERE/p) for p in ('SUMMARY.json','CASES_POSTSEAL.json','REFERENCE_INVENTORY_POSTSEAL.json')]
    write_new(HERE/'SCORING_SEALED.json',dict(status='COMPLETE',
        measurement_seal=artifact(HERE/'MEASUREMENTS_SEALED.json'),artifacts=outputs,
        ended_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())))
    print(json.dumps(dict(decision=groups['POOLED']['decision'],
        fixed_R={a:v['fixed_R'] for a,v in groups['POOLED']['arms'].items()}),indent=2),flush=True)


if __name__=='__main__': evaluate()
