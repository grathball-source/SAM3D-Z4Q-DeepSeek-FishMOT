"""Append-only actual contact publications: private depth, public numbers.

All decisions are already sealed. No GT, RGB, q+1 observation or model is read.
Selection is all actual birth commits plus the first eight source-qualified
contact noncommits per new branch, including active-group exclusions.
"""
from __future__ import annotations
import copy
import gzip
import hashlib
import importlib.util
import json
from itertools import islice
from collections import Counter
from functools import lru_cache
from pathlib import Path
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RUN = HERE/'run'
ARMS = ('SAM3_NATIVE','F9_RESTORED','R12_RAW','R12_RESTORED')
NEW_ARMS = ARMS[2:]
MAX_NONCOMMITS = 8


def read(path): return json.loads(Path(path).read_text(encoding='utf-8'))


def rows(path):
    opener = gzip.open if str(path).endswith('.gz') else open
    with opener(path,'rt',encoding='utf-8') as handle:
        yield from (json.loads(line) for line in handle)


@lru_cache(maxsize=None)
def artifact(path):
    path = Path(path).resolve()
    with path.open('rb') as handle: digest = hashlib.file_digest(handle,'sha256').hexdigest()
    return dict(path=str(path),bytes=path.stat().st_size,sha256=digest)


def verify(item):
    assert artifact(Path(item['path'])) == {k:item[k] for k in ('path','bytes','sha256')},item['path']


def write_new(path,value):
    path = Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8',newline='\n') as handle:
        json.dump(value,handle,ensure_ascii=False,indent=2,allow_nan=False);handle.write('\n')


def module(name,path):
    spec = importlib.util.spec_from_file_location(name,path)
    loaded = importlib.util.module_from_spec(spec);spec.loader.exec_module(loaded)
    return loaded


def mapping(prediction,arm):
    value = {int(item['mask'][2:]):item['id'] for item in prediction['variants'][arm]}
    assert len(value)==len(prediction['variants'][arm])
    return value


def select_cases(records):
    selected=[];counts={arm:Counter() for arm in NEW_ARMS}
    for segment,birth,query in sorted(records,key=lambda x:(x[1]['global_frame'],x[1]['arm'],x[2]['source'])):
        arm=birth['arm']
        if arm not in NEW_ARMS:continue
        certificate=query.get('contact_certificate')
        contact=bool(query['query_observation'].get('neighbors'))
        qualified=bool(contact and certificate and certificate['eligible'] and any(c['eligible'] for c in query['candidates']))
        counts[arm]['all_births']+=1
        counts[arm]['contact_births']+=contact
        counts[arm]['contact_certificate_and_legal_old']+=qualified
        committed=query['status']=='COMMIT'
        if committed:
            reason='ALL_ACTUAL_BIRTH_COMMITS';counts[arm]['commits']+=1
        elif qualified:
            counts[arm]['qualified_noncommits']+=1
            if counts[arm]['selected_noncommits']>=MAX_NONCOMMITS:continue
            reason='CHRONOLOGICAL_FIRST_8_CERTIFIED_CONTACT_NONCOMMITS_WITH_LEGAL_OLD'
            counts[arm]['selected_noncommits']+=1
        else:continue
        selected.append(dict(segment=segment,birth=birth,query=query,selection_reason=reason))
    return selected,{arm:dict(value) for arm,value in counts.items()}


def gate():
    all_path=RUN/'ALL_PREDICTIONS_SEALED.json';score_path=RUN/'SCORING_SEALED.json'
    assert all_path.is_file() and score_path.is_file(),'Wait for all predictions AND scoring seals'
    complete,score=read(all_path),read(score_path)
    assert complete['status']=='ALL_FOUR_BRANCHES_FOUR_SEGMENTS_SEALED' and complete['frames']==1471
    assert tuple(complete['arms'])==ARMS and score['status']=='ALL_SEGMENTS_AND_EVENTS_SCORED'
    assert score['all_prediction_seal_sha256']==artifact(all_path)['sha256']
    for name,digest in score['artifacts_sha256'].items(): assert artifact(RUN/name)['sha256']==digest,name
    access=read(RUN/'ACCESS_SEALED.json');verify(access['artifact'])
    assert access['prediction_all_seal']==artifact(all_path)
    return complete,dict(code=artifact(Path(__file__)),all_prediction_seal=artifact(all_path),
        scoring_seal=artifact(score_path),access_seal=artifact(RUN/'ACCESS_SEALED.json'),
        actual_access=access['artifact'],segments={})


def _piece_totals(certificate,totals):
    totals['certificates']+=1;totals['eligible_certificates']+=certificate['eligible']
    totals['mask_area']+=certificate['mask_area'];totals['shared_mask_pixels_excluded']+=certificate['shared_mask_pixels_excluded']
    totals['original_exclusive_components']+=certificate['geometric_components']['component_count']
    totals['empty_geometry_components']+=sum(not p['samples'] for p in certificate['geometric_components']['pieces'])
    totals['actual_core_components']+=len(certificate['components'])
    totals['qualified_components']+=certificate['qualified_component_count']
    for piece in certificate['components']:
        for key in ('area','n','shared_source_pixels_excluded','duplicate_pixels_excluded',
                    'duplicate_within_piece_before_canonical','unmapped_pixels','invalid_native_source_pixels',
                    'inferred_pixels_excluded','aligned_above_5000_mm_diagnostic_n'):
            totals[key]+=piece[key]
        totals['native_above_5000_mm_diagnostic_n']+=piece['native_above_5000_mm_diagnostic_n'] or 0
        for reason in piece['exclusion_reasons']:totals['reason:'+reason]+=1


def source_review(complete,bindings,segments):
    from contact_measurement import check_certificate
    all_totals={mode:Counter() for mode in ('raw','restored')}
    born_totals={mode:Counter() for mode in ('raw','restored')}
    certificate_frames=0;birth_count=0;full_frames=0;full_objects=0;per_segment={}
    for segment,data in segments.items():
        frames=Counter();local={mode:Counter() for mode in ('raw','restored')}
        cache=data['measurements'];original=data['sources'];frozen=data['frozen']
        native_bindings={str(Path(x['path']).resolve()):x for x in frozen['native_depth_sources']}
        for frame,row in data['certificates'].items():
            full_frames+=1;full_objects+=len(cache[frame]['adaptive_raw'])
            born=row['born_sources'];birth_count+=len(born)
            actual=row['status']=='ACTUAL_CURRENT_BIRTH_FRAME_MEASUREMENTS'
            certificate_frames+=actual;frames[row['status']]+=1
            assert bool(row['raw'])==bool(row['restored'])==actual
            if not actual: assert not born;continue
            assert set(row['raw'])==set(row['restored'])==set(cache[frame]['adaptive_raw'])
            frames['births']+=len(born);frames['all_current_objects_at_birth_frames']+=len(row['raw'])
            source=original[frame-1];raw_binding=row['raw_source_binding'];v2_binding=row['restored_source_binding']
            assert (raw_binding['frame'],raw_binding['global_frame'],raw_binding['time'])==(frame,row['global_frame'],row['time'])
            assert raw_binding['raw_npz']['sha256']==source['depth_sha256'] and raw_binding['raw_npz']['bytes']==source['depth_bytes']
            verify(raw_binding['raw_npz']);verify(raw_binding['native_npy'])
            assert raw_binding['native_npy']==native_bindings[str(Path(raw_binding['native_npy']['path']).resolve())]
            assert v2_binding['native_h5']==frozen['restored_sources'][str(Path(v2_binding['native_h5']['path']).resolve())]
            verify(v2_binding['native_h5'])
            for mode in ('raw','restored'):
                for native,certificate in row[mode].items():
                    assert check_certificate(certificate,native=int(native),frame=frame,global_frame=row['global_frame'])
                    assert certificate['source_binding']==row[mode+'_source_binding']
                    _piece_totals(certificate,all_totals[mode]);_piece_totals(certificate,local[mode])
                    if int(native) in born:_piece_totals(certificate,born_totals[mode])
        per_segment[segment]=dict(coverage=dict(frames),all_current_certificate_totals={k:dict(v) for k,v in local.items()})
    assert full_frames==1471 and birth_count==105
    access=read(bindings['actual_access']['path'])
    return dict(status='PASS_POSTSEAL_SOURCE_BINDING_AND_EXHAUSTIVE_RECORDED_COVERAGE',bindings=bindings,
        complete_frames=full_frames,complete_cached_objects=full_objects,
        noninitial_first_ever_native_births=birth_count,actual_certificate_frames=certificate_frames,
        coverage_scope='Certificates reconstructed all current masks only on noninitial first-ever birth frames. Remaining frames retain exact DS10 measurements; not all 39208 objects were remeasured by contact producer.',
        all_current_birth_frame_certificate_totals={k:dict(v) for k,v in all_totals.items()},
        first_ever_born_source_certificate_totals={k:dict(v) for k,v in born_totals.items()},segments=per_segment,
        actual_npz_field_read_counts=dict(Counter(x['key'] for x in access['npz_field_reads'])),
        actual_source_access_status=access['status'],new_model_http=0,cost_usd=0,RGB_read=False,GT_read=False,
        source_policy='CROSS_ANY_MASK_SHARED_NATIVE_INDEX_EXCLUDED; SAME_MASK_ROW_MAJOR_CANONICAL_ONCE',
        inferred_admission='NONE; ONLY_PROVENANCE_1_RETAINED_NATIVE_V2',
        suspect_policy='>5000 diagnostic only; no new range exclusion',sensor_valid_range='UNKNOWN',
        physical_surface_identity='UNKNOWN',background_suspicion='UNKNOWN',calibration_accuracy='UNKNOWN',
        raw_native_z_vs_aligned_z='DIFFERENT_COORDINATES; NOT_ASSUMED_EQUAL',
        v2_boundary='UPSTREAM_RGB_AND_I_PLUS_1_CLEANING_OFFLINE; NO_CURRENT_RGB_OR_FUTURE_2D_READ',
        statistics_semantics='n from actually selected unique sensor-source pixels; fraction denominator actual geometric core-piece area; actual MAD, no inferred proxy MAD')


def main():
    complete,bindings=gate()
    from common import SEGMENTS,input_dir
    legacy=module('ds12_visual_reference_helper',HERE.parent/'ds11_depth_birth_reconnect/postseal_visualize.py')
    segments={};records=[]
    for segment,(start,stop) in SEGMENTS.items():
        public=RUN/segment/'public';seal_path=public/'PREDICTIONS_SEALED.json';seal=read(seal_path)
        assert artifact(seal_path)['sha256']==complete['seals'][segment]
        assert seal['frames']==stop-start+1 and tuple(seal['arms'])==ARMS
        files={}
        for name in ('FREEZE.json','predictions.jsonl.gz','BIRTHS.jsonl.gz','CONTACT_CERTIFICATES.jsonl.gz','PUBLISH_LEDGER.jsonl','DEPTH_OBSERVATIONS.jsonl.gz'):
            files[name]=artifact(public/name);assert files[name]['sha256']==seal['artifacts_sha256'][name]
        frozen=read(public/'FREEZE.json');assignment=frozen['derived_inputs']['assignments'];verify(assignment)
        source_path=input_dir(segment)/'sources.json'
        assert artifact(source_path)['sha256']==frozen['source_list_sha256']
        bindings['segments'][segment]=dict(prediction_seal=artifact(seal_path),files=files,assignments=assignment,
            source_list=artifact(source_path),restored_sources=frozen['restored_sources'])
        for path in (HERE/'contact_measurement.py',HERE.parent/'ds10_depth_failure_repair/adaptive_core.py',HERE.parent/'ds10_depth_failure_repair/restored_source.py'):
            assert artifact(path)['sha256']==frozen['code_sha256'][str(path.resolve())]
        measurements={r['frame']:r for r in rows(public/'DEPTH_OBSERVATIONS.jsonl.gz')}
        certificates={r['frame']:r for r in rows(public/'CONTACT_CERTIFICATES.jsonl.gz')}
        assert len(measurements)==len(certificates)==stop-start+1
        segments[segment]=dict(start=start,public=public,frozen=frozen,measurements=measurements,
            certificates=certificates,sources=read(source_path))
        for birth in rows(public/'BIRTHS.jsonl.gz'):
            for query in birth['queries']:
                if birth['arm'] in NEW_ARMS:records.append((segment,birth,query))
    cases,selection_summary=select_cases(records)
    review=source_review(complete,bindings,segments)
    review['case_selection_summary']=selection_summary
    private=HERE/'private/contact_visualizations';diagnosis=HERE/'diagnosis'
    assert not private.exists(),'Do not overwrite existing postseal pixels'
    private.mkdir(parents=True);diagnosis.mkdir(exist_ok=True)
    import numpy as np
    import cv2
    cv2.setNumThreads(1)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.colors import LogNorm
    from matplotlib.cm import ScalarMappable
    from contact_measurement import load_raw_frame,array_binding,adaptive_core
    from depth_measurement import decode
    RestoredDepth=module('ds12_visual_native_v2',HERE.parent/'ds10_depth_failure_repair/restored_source.py').RestoredDepth
    reader=RestoredDepth();items=[]
    try:
        for number,case in enumerate(cases,1):
            segment=case['segment'];birth=case['birth'];q=case['query'];arm=birth['arm'];data=segments[segment]
            candidate,reference_rule=legacy.choose_reference(q,None)
            qframe=birth['frame'];reference=candidate['reference_anchor']['frame'];last=candidate['last_seen_frame']
            risk=candidate['anonymous_risk_observations'];first_risk=min((r['frame'] for r in risk),default=None)
            times=dict(joint_reference=reference,first_anonymous_risk=first_risk,last_appearance=last,first_birth=qframe)
            required={f for f in times.values() if f is not None};assert all(1<=f<=qframe for f in required)
            assert all(p['frame']<=qframe for p in candidate['frozen_depth']['samples'])
            predictions={r['frame']:r for r in islice(rows(data['public']/'predictions.jsonl.gz'),qframe) if r['frame'] in required}
            assignments={r['frame']:r for r in islice(rows(bindings['segments'][segment]['assignments']['path']),qframe) if r['frame'] in required}
            ledger={r['frame']:r for r in islice(rows(data['public']/'PUBLISH_LEDGER.jsonl'),qframe) if r['frame'] in required}
            line_hashes={};disk_hashes={}
            with gzip.open(data['public']/'predictions.jsonl.gz','rt',encoding='utf-8',newline='') as handle:
                for line in islice(handle,qframe):
                    row=json.loads(line)
                    if row['frame'] in required:
                        normalized=line[:-2]+'\n' if line.endswith('\r\n') else line
                        line_hashes[row['frame']]=hashlib.sha256(normalized.encode()).hexdigest()
                        disk_hashes[row['frame']]=hashlib.sha256(line.encode()).hexdigest()
            assert all(ledger[f]['prediction_row_sha256']==line_hashes[f] for f in required)
            images={};sample_bindings=[];union=np.zeros((360,640),bool);focus={candidate['source'],q['source']}
            for role,frame in times.items():
                if frame is None:continue
                raw,index,native,raw_binding=load_raw_frame(data['start']+frame-1,data['sources'][frame-1])
                v2,provenance,metadata=reader(data['start']+frame-1)
                masks={int(k[2:]):decode(rle) for k,rle in assignments[frame]['masks'].items()}
                for source in focus&set(masks):union|=masks[source]
                assert all(set(mapping(predictions[frame],a))==set(masks) for a in ARMS)
                occupancy=sum((m.astype('u2') for m in masks.values()),np.zeros((360,640),'u2'))
                core={n:adaptive_core(masks[n],occupancy)[0] for n in focus&set(masks)}
                images[role]=(raw,v2,masks,core,predictions[frame])
                sample_bindings.append(dict(role=role,frame=frame,global_frame=data['start']+frame-1,time=predictions[frame]['time'],
                    raw_source_binding=raw_binding,native_v2_source=data['frozen']['restored_sources'][str(Path(metadata['native_path']).resolve())],
                    native_v2_metadata=metadata,v2_source_index=array_binding(reader.current_source_index),
                    publisher_prewrite_LF_sha256=line_hashes[frame],disk_prediction_line_sha256=disk_hashes[frame],
                    actual_public_ids={a:mapping(predictions[frame],a) for a in ARMS},all_actual_masks=len(masks)))
            yy,xx=np.nonzero(union);assert yy.size
            x0,x1=max(0,int(xx.min())-24),min(640,int(xx.max())+25)
            y0,y1=max(0,int(yy.min())-24),min(360,int(yy.max())+25);crop=np.s_[y0:y1,x0:x1]
            positive=np.concatenate([d[crop][np.isfinite(d[crop])&(d[crop]>0)] for image in images.values() for d in image[:2]])
            norm=LogNorm(vmin=float(positive.min()) if positive.size else 1.,vmax=max(float(positive.max()),float(positive.min())+1) if positive.size else 2.)
            certificate=q.get('contact_certificate');pieces=certificate['components'] if certificate else []
            query_core=images['first_birth'][3][q['source']]
            if certificate:assert array_binding(query_core)==certificate['core_binding']
            _,query_labels=cv2.connectedComponents(query_core.astype('u1'),connectivity=8)
            name=f'postseal_F{birth["global_frame"]:06d}_n{q["source"]}_{arm}'
            png=private/(name+'.png');svg=diagnosis/(name+'_NUMERIC.svg')
            actual=mapping(predictions[qframe],arm)[q['source']]
            assert actual==q['actual_first_public_id']
            fig,axes=plt.subplots(2,4,figsize=(26,12),constrained_layout=True);local_counts=[]
            for col,(role,frame) in enumerate(times.items()):
                if frame is None:
                    for ax in axes[:,col]:ax.axis('off');ax.text(.5,.5,'NO OBSERVED RISK FRAME\nNo synthetic reference inserted',ha='center',va='center',transform=ax.transAxes)
                    continue
                raw,v2,masks,cores,pred=images[role];published=mapping(pred,arm)
                inside=[n for n,m in masks.items() if np.any(m[crop])]
                for row,depth in enumerate((raw,v2)):
                    ax=axes[row,col];ax.imshow(np.ma.masked_where(~np.isfinite(depth)|(depth<=0),depth),cmap='viridis',norm=norm)
                    sy,sx=np.nonzero(np.isfinite(depth[crop])&(depth[crop]>5000))
                    if sy.size:ax.scatter(sx+x0,sy+y0,c='red',s=5,alpha=.8)
                    for n in inside:
                        color='#00e5ff' if n==candidate['source'] else '#ff8c00' if n==q['source'] else '#eeeeee'
                        contours,_=cv2.findContours(masks[n].astype('u1'),cv2.RETR_LIST,cv2.CHAIN_APPROX_SIMPLE)
                        for contour in contours:
                            points=contour[:,0,:]
                            if len(points)>1:ax.plot(*points.T,color=color,lw=1.8 if n in focus else .8)
                        my,mx=np.nonzero(masks[n][crop]);center=(float(mx.mean())+x0,float(my.mean())+y0)
                        if n in focus:
                            ax.annotate(f'native {n}\nACTUAL public {published[n]}',xy=center,
                                xytext=(x1-3,y0+4) if n==q['source'] else (x0+3,y1-4),
                                ha='right' if n==q['source'] else 'left',va='top' if n==q['source'] else 'bottom',
                                fontsize=11,color=color,bbox=dict(facecolor='black',alpha=.9,pad=2),
                                arrowprops=dict(arrowstyle='->',color=color,lw=1.3))
                        else:ax.text(*center,f'n{n}/ID{published[n]}',fontsize=7,color='white',ha='center',bbox=dict(facecolor='black',alpha=.65,pad=.5))
                        if n in cores and role!='first_birth':
                            contours,_=cv2.findContours(cores[n].astype('u1'),cv2.RETR_LIST,cv2.CHAIN_APPROX_SIMPLE)
                            for contour in contours:
                                points=contour[:,0,:]
                                if len(points)>1:ax.plot(*points.T,color='#ff66cc',ls=':',lw=1.)
                    if role=='first_birth':
                        for piece in pieces:
                            region=query_labels==piece['core_label'];color='#00ff77' if piece['qualified'] else '#ff3333'
                            contours,_=cv2.findContours(region.astype('u1'),cv2.RETR_LIST,cv2.CHAIN_APPROX_SIMPLE)
                            for contour in contours:
                                points=contour[:,0,:]
                                if len(points)>1:ax.plot(*points.T,color=color,lw=1.4,ls=':')
                            py,px=np.nonzero(region)
                            ax.text(float(px.mean()),float(py.mean()),f'c{piece["core_label"]}: n{piece["n"]}',fontsize=9,color=color,
                                bbox=dict(facecolor='black',alpha=.8,pad=1))
                    ax.set_xlim(x0-.5,x1-.5);ax.set_ylim(y1-.5,y0-.5)
                    ax.set_title(f'{role} F{pred["global_frame"]} / '+('raw' if row==0 else 'native-v2 offline'),fontsize=12)
                    values=depth[crop];good=values[np.isfinite(values)&(values>0)]
                    ax.set_xlabel(f'all local masks {len(inside)}; max {good.max():.2f} mm; >5000 SUSPECT {sy.size}' if good.size else 'all depth missing',fontsize=9)
                local_counts.append(dict(role=role,all_local_masks=len(inside),native_sources=inside))
            fig.suptitle(f'{arm} F{birth["global_frame"]} n{q["source"]}: {q["status"]}; ACTUAL FIRST PUBLIC {actual}\n'
                f'Reference source {candidate["source"]}: {reference_rule}; reference is NOT certified correct target. No selected ID copied backward.\n'
                f'Current green/red dotted core = qualified/rejected {certificate["mode"] if certificate else "NO CERTIFICATE"} pieces; historical pink = geometry only.\n'
                'All four sampled times <= query; full local depth range. No RGB/GT raster. Fish/background ownership and calibration UNKNOWN.',fontsize=12)
            fig.colorbar(ScalarMappable(norm=norm,cmap='viridis'),ax=axes,shrink=.8,label='recorded camera-Z mm; no high-value clipping')
            fig.savefig(png,dpi=140);plt.close(fig)
            selection=q.get('selection') or {};scored=selection.get('candidates',{})
            fig,axes=plt.subplots(2,2,figsize=(20,12),constrained_layout=True)
            ax=axes[0,0];past=candidate['frozen_depth']['samples'];now=q['query_observation']['time']
            ax.errorbar([p['time']-now for p in past],[p['z_mm'] for p in past],
                yerr=[p['mad_mm'] for p in past],fmt='o-',ms=4,label='complete actual joint-clean raw history +/- actual MAD')
            risk_numeric=[]
            for r in risk:
                fact=data['measurements'][r['frame']]['adaptive_raw'].get(str(candidate['source']))
                median=fact['core']['median'] if fact else None
                risk_numeric.append(dict(frame=r['frame'],time=r['time'],class_name=r.get('observation_class',r.get('class')),median_mm=median,
                    actual_mad_mm=fact['core']['mad'] if fact else None,neighbors=r.get('neighbors'),identity='UNKNOWN'))
            visible=[(r['time']-now,r['median_mm']) for r in risk_numeric if r['median_mm'] is not None]
            if visible:ax.scatter(*zip(*visible),facecolors='none',edgecolors='#f08000',s=32,label='anonymous risk medians; never fitted')
            ax.axvspan(past[-1]['time']-now,0,color='#ffcc66',alpha=.2,label='full last-clean -> query gap')
            last_time=data['measurements'][last]['time'];ax.axvspan(last_time-now,0,color='gray',alpha=.2,label='absent source interval')
            if candidate.get('anchor'):ax.axvline(data['measurements'][candidate['anchor']['frame']]['time']-now,color='gray',ls=':',label='actual mechanical bank anchor')
            for p in pieces:
                if p['median_mm'] is not None:ax.scatter([0],[p['median_mm']],marker='D',color='#00aa66' if p['qualified'] else '#dd3333',s=45)
            ax.set_xlabel('seconds relative to actual first birth');ax.set_ylabel('recorded measured camera-Z mm')
            ax.set_title(f'History {len(past)}; anonymous risk {len(risk)}; full gap {now-past[-1]["time"]:.6f}s');ax.legend(fontsize=8)
            ax=axes[0,1];weights={p['component_id']:p['weight'] for p in certificate['qualified_components']} if certificate else {}
            for index,piece in enumerate(pieces):
                if piece['median_mm'] is not None:ax.errorbar(piece['median_mm'],index,xerr=piece['scale_mm'],fmt='o',color='#00aa66' if piece['qualified'] else '#dd3333')
            ax.set_yticks(range(len(pieces)),[f'c{p["core_label"]} n={p["n"]}/{p["area"]} frac={p["valid_fraction"]:.3f}\nMAD={p["actual_mad_mm"]} w={weights.get(p["component_id"],0)} '+('QUAL' if p['qualified'] else 'REJECT') for p in pieces],fontsize=8)
            ax.set_xlabel('current actual median +/- frozen scale (mm)');ax.set_title('ALL current core pieces; weights fixed before candidates\nInferred pixels never certified; ownership/background UNKNOWN',fontsize=11)
            ax=axes[1,0];labels=list(scored);y=np.arange(len(labels))
            if labels:
                ax.barh(y-.25,[scored[k]['geometry_log_lr'] for k in labels],.25,label='geometry log LR')
                ax.barh(y,[scored[k]['depth_log_lr'] for k in labels],.25,label='depth log LR')
                ax.barh(y+.25,[scored[k]['geometry_log_lr']+scored[k]['depth_log_lr'] for k in labels],.25,label='joint log LR')
                ax.set_yticks(y,labels,fontsize=8);ax.axvline(0,color='black',lw=.8);ax.legend(fontsize=8)
            else:ax.text(.5,.5,'NUMERIC LR NOT EVALUATED\n'+q['status'],ha='center',va='center',transform=ax.transAxes)
            unevaluated=[dict(source=c['source'],public=c['public'],eligible=c['eligible'],reasons=c['reasons']) for c in q['candidates'] if f'OLD:{c["public"]}' not in scored]
            ax.set_xlabel('dimensionless log contrast; not calibrated posterior accuracy')
            ax.set_title(f'All evaluated OLD + NEW LR; {len(unevaluated)} other recorded candidates have no LR\nreason {selection.get("reason",q["status"])}',fontsize=10)
            ax=axes[1,1];ax.axis('off');table=[]
            for role,frame in times.items():
                source=q['source'] if role=='first_birth' else candidate['source']
                table.append([role,'NONE' if frame is None else str(data['start']+frame-1),f'n{source}',
                    *['NONE' if frame is None else str(mapping(predictions[frame],a).get(source,'ABSENT')) for a in ARMS]])
            tab=ax.table(cellText=table,colLabels=['time','global F','source','native','F9','R12 raw','R12 v2'],loc='upper center',cellLoc='center')
            tab.auto_set_font_size(False);tab.set_fontsize(9);tab.scale(1,1.8)
            excluded='\n'.join(f'n{c["source"]}/public{c["public"]}: '+','.join(c['reasons']) for c in unevaluated)
            ax.text(0,.58,'All recorded unevaluated candidate reasons:\n'+(excluded or 'NONE'),va='top',fontsize=7,transform=ax.transAxes)
            ax.set_title('Actual publisher IDs at each time; never relabeled by reference',fontsize=11)
            fig.suptitle(f'{name}: {q["status"]}; actual first public {actual}; selected_target={q.get("selected_target")}\n'
                f'Joint margin={selection.get("margin")}; best vs NEW={selection.get("best_vs_new_margin")}; frozen log(9). Group blocked={birth["group_blocked"]}.\n'
                'Raw causal; native-v2 upstream RGB/future diagnostic. Physical ownership/accuracy UNKNOWN. No GT used for case selection.',fontsize=12)
            assert not any(ax.images for ax in axes.flat)
            fig.savefig(svg);plt.close(fig);assert '<image' not in svg.read_text(encoding='utf-8').lower()
            items.append(dict(segment=segment,arm=arm,query_global_frame=birth['global_frame'],query_native=q['source'],
                selection_reason=case['selection_reason'],status=q['status'],actual_first_public_id=actual,
                selected_target=q.get('selected_target'),stage_error=q.get('stage_error'),group_blocked=birth['group_blocked'],
                numeric_reason=selection.get('reason'),reference_source=candidate['source'],reference_rule=reference_rule,
                reference_anchor=candidate['reference_anchor'],actual_mechanical_bank_anchor=candidate.get('anchor'),
                sample_frames=times,sample_bindings=sample_bindings,roi_xyxy=[x0,y0,x1,y1],all_local_mask_checks=local_counts,
                complete_joint_history=past,complete_anonymous_risk=risk_numeric,current_certificate=certificate,
                all_evaluated_candidate_LR={k:dict(source=c.get('source',q['source'] if c['is_new'] else None),
                    **{f:c[f] for f in ('public','geometry_log_lr','depth_log_lr','log_score')}) for k,c in scored.items()},
                all_recorded_candidates=[dict(source=c['source'],public=c['public'],eligible=c['eligible'],reasons=c['reasons'],
                    geometry_frames=[p['frame'] for p in c.get('geometry_history',[])],
                    reference_anchor=c.get('reference_anchor'),bank_anchor=c.get('anchor')) for c in q['candidates']],
                all_unevaluated_candidates=unevaluated,private_pixel_artifact=artifact(png),public_numeric_svg=artifact(svg),
                no_frame_after_query=True,GT_used=False,GT_raster_reads=0,RGB_reads=0,pixel_QA='PENDING_ACTUAL_VIEW'))
            print(f'private/public case {number}/{len(cases)} {name} {q["status"]}',flush=True)
    finally:reader.close()
    inventory=dict(status='POSTSEAL_ACTUAL_CONTACT_VISUALIZATION; PIXEL_QA_PENDING',bindings=bindings,
        selection_policy='ALL_ACTUAL_BIRTH_COMMITS_PLUS_FIRST_8_CERTIFIED_CONTACT_NONCOMMITS_WITH_LEGAL_OLD_PER_BRANCH; NO_GT',
        selection_summary=selection_summary,case_count=len(items),cases=items,private_pixels_not_for_Git=True,
        GT_used=False,GT_raster_reads=0,RGB_reads=0,new_model_calls=0,new_replays=0)
    inventory_path=diagnosis/'postseal_VISUALIZATION_INVENTORY.json'
    review_path=HERE/'postseal_SOURCE_REVIEW.json'
    write_new(inventory_path,inventory);review['visualization_inventory']=artifact(inventory_path);write_new(review_path,review)
    print(json.dumps(dict(case_count=len(items),inventory=artifact(inventory_path),source_review=artifact(review_path)),ensure_ascii=False))


if __name__=='__main__':
    assert sys.argv[1:] in ([],['--axes-repair'])
    main()
