"""Actual sealed birth publications: private depth pixels, public numbers only."""
from pathlib import Path
from functools import lru_cache
import json,gzip,hashlib,sys,importlib.util
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
RUN=HERE/'run'
ARMS=('SAM3_NATIVE','F9_RESTORED','R11_RAW','R11_RESTORED')
R11=ARMS[2:]


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))


@lru_cache(maxsize=None)
def artifact(path):
    p=Path(path).resolve()
    with p.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
    return dict(path=str(p),bytes=p.stat().st_size,sha256=digest)


def verify(entry):assert artifact(Path(entry['path']))==entry,entry['path']


def rows(path):
    op=gzip.open if str(path).endswith('.gz') else open
    with op(path,'rt',encoding='utf-8') as stream:
        yield from (json.loads(line) for line in stream)


def mapping(prediction,arm):
    result={int(o['mask'][2:]):o['id'] for o in prediction['variants'][arm]}
    assert len(result)==len(prediction['variants'][arm]) and all(type(v) is int for v in result.values())
    return result


def qualified(birth,query,measurement):
    o=query['query_observation'];n=str(query['source']);raw=measurement['adaptive_raw'][n]
    current=o['quality'] and o['area']>=64 and not o['neighbors'] and raw['core_usable']
    if birth['arm']=='R11_RESTORED':
        v2=measurement['restored'][n];current=current and v2['core_usable'] and v2['cohort']=='retained'
    return bool(birth['frame']>1 and current and any(c['eligible'] for c in query['candidates']))


def choose_reference(query,upper):
    """Committed target, numerical best OLD, first eligible; never select by GT."""
    if query.get('selected_candidate'):
        return query['selected_candidate'],'ACTUAL_SELECTED_CANDIDATE'
    scores=(query.get('selection') or {}).get('candidates',{})
    old=sorted((c for c in scores.values() if not c['is_new']),key=lambda c:(-c['log_score'],c['public']))
    if old:return old[0]['qualification'],'HIGHEST_SCORED_OLD_CANDIDATE'
    available=sorted((c for c in query['candidates'] if c['eligible']),key=lambda c:(c['source'],c['public']))
    if available:return available[0],'FIRST_ELIGIBLE_SOURCE_ASCENDING_NO_NUMERIC_SELECTION'
    assert upper is not None and upper['source_candidates']
    # Fallback shows one deterministic source-bound history, not an invented branch version.
    c=next(c for c in upper['source_candidates'] if c['raw_branch_source_opportunity'])
    actual=next((a for a in query['candidates'] if a['source']==c['source_native'] and a.get('reference_anchor')),None)
    if actual:return actual,'INELIGIBLE_RUNTIME_CANDIDATE_NOT_ASSOCIATED'
    d=upper['_disappearances'][c['disappearance_evidence_index']]
    points=d['joint_fragment']
    return dict(source=d['source_native'],public=None,generation=d['source_generation'],epoch=None,
        reference_anchor=dict(d['reference_anchor']),last_seen_frame=d['last_appearance']['frame'],
        frozen_depth=dict(samples=[dict(frame=p['frame'],time=p['time'],z_mm=p['raw_median_mm'],
            mad_mm=p['raw_actual_mad_mm'],fact_id=p['raw_fact_id']) for p in points]),
        anonymous_risk_observations=d['risk_anonymous_source_observations'],eligible=False,
        reasons=['SOURCE_UPPER_BOUND_ONLY_BRANCH_VERSION_UNKNOWN'],anchor=None),'SOURCE_UPPER_BOUND_REFERENCE_NOT_ASSOCIATED'


def check():
    row=dict(variants={a:[dict(mask='n:3',id=3)] for a in ARMS})
    row['variants']['R11_RAW']=[dict(mask='n:3',id=1)]
    assert mapping(row,'R11_RAW')=={3:1} and mapping(row,'SAM3_NATIVE')=={3:3}
    measurement=dict(adaptive_raw={'3':dict(core_usable=True)},
        restored={'3':dict(core_usable=True,cohort='inferred')})
    q=dict(source=3,query_observation=dict(quality=True,area=64,neighbors=[]),candidates=[dict(eligible=True)])
    assert qualified(dict(frame=2,arm='R11_RAW'),q,measurement)
    assert not qualified(dict(frame=2,arm='R11_RESTORED'),q,measurement)
    assert not qualified(dict(frame=1,arm='R11_RAW'),q,measurement)
    print('Postseal visualization checks PASS: actual independent mappings, initial-frame exclusion, retained-only query qualification')


def sealed_inputs():
    # Gate before importing pixel readers or reading new prediction/birth rows.
    all_path=RUN/'ALL_PREDICTIONS_SEALED.json';score_path=RUN/'SCORING_SEALED.json'
    assert all_path.is_file() and score_path.is_file(),'Wait for ALL prediction AND scoring seals'
    complete,score=read(all_path),read(score_path)
    assert complete['status']=='ALL_FOUR_BRANCHES_FOUR_SEGMENTS_SEALED' and complete['frames']==1471
    assert tuple(complete['arms'])==ARMS and score['status']=='ALL_SEGMENTS_AND_EVENTS_SCORED'
    assert score['all_prediction_seal_sha256']==artifact(all_path)['sha256']
    for name,digest in score['artifacts_sha256'].items():assert artifact(RUN/name)['sha256']==digest,name
    return complete,dict(all_prediction_seal=artifact(all_path),scoring_seal=artifact(score_path),
        code=artifact(Path(__file__)),endpoint_contract=artifact(HERE/'ENDPOINT_CONTRACT.json'),
        source_upper_bound=artifact(HERE/'RISK_PRE_FRAGMENT_CENSUS.json'),segments={})


def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m);return m


def main():
    complete,bindings=sealed_inputs()
    from common import SEGMENTS,input_dir,DS1
    upper=read(HERE/'RISK_PRE_FRAGMENT_CENSUS.json')
    upper_by={s['segment']:s for s in upper['segments']}
    cases=[];selection_summary={};datasets={}
    for segment,(start,stop) in SEGMENTS.items():
        public=RUN/segment/'public';seal=read(public/'PREDICTIONS_SEALED.json')
        assert artifact(public/'PREDICTIONS_SEALED.json')['sha256']==complete['seals'][segment]
        assert seal['frames']==stop-start+1 and tuple(seal['arms'])==ARMS
        frozen=read(public/'FREEZE.json');files={}
        for name in ('FREEZE.json','predictions.jsonl.gz','BIRTHS.jsonl.gz','PUBLISH_LEDGER.jsonl','DEPTH_OBSERVATIONS.jsonl.gz'):
            files[name]=artifact(public/name);assert files[name]['sha256']==seal['artifacts_sha256'][name]
        assignment=frozen['derived_inputs']['assignments'];verify(assignment)
        source_path=input_dir(segment)/'sources.json'
        assert artifact(source_path)['sha256']==frozen['source_list_sha256']
        chain=frozen['measurement_cache_source_chain']
        for name in ('restored_source.py','adaptive_core.py','legacy_depth_measurement.py'):
            verify(chain['measurement_producer'][name])
        for entry in frozen['restored_sources'].values():verify(entry)
        bindings['segments'][segment]=dict(prediction_seal=artifact(public/'PREDICTIONS_SEALED.json'),
            files=files,assignments=assignment,source_list=artifact(source_path),
            restored_sources=frozen['restored_sources'],pixel_reader_producer=chain['measurement_producer'])
        measured={r['frame']:r for r in rows(public/'DEPTH_OBSERVATIONS.jsonl.gz')}
        births={(b['frame'],b['arm']):b for b in rows(public/'BIRTHS.jsonl.gz')}
        u=upper_by[segment]
        upper_queries={q['native']:dict(q,_disappearances=u['disappearances']) for q in u['births'] if q['raw_source_opportunity_count']}
        for arm in R11:
            selected={}
            for (frame,a),b in births.items():
                if a!=arm:continue
                for q in b['queries']:
                    reasons=[]
                    if qualified(b,q,measured[frame]):reasons.append('ACTUAL_BRANCH_SOURCE_QUALIFIED_BIRTH')
                    if q['status']=='COMMIT':reasons.append('ALL_ACTUAL_COMMITS')
                    if reasons:selected[(frame,q['source'])]=(b,q,reasons)
            selection_summary[(segment,arm)]=dict(actual_source_qualified_or_commit=len(selected),source_upper_bound_added=0)
            datasets[(segment,arm)]=(births,measured,upper_queries,selected)
    # Retain all four common raw-source opportunities, including active-group exclusions.
    for arm in R11:
        for segment,(start,stop) in SEGMENTS.items():
            births,measured,upper_queries,selected=datasets[(segment,arm)]
            for native,u in upper_queries.items():
                if (u['frame'],native) in selected:
                    selected[(u['frame'],native)][2].append('ALL_FOUR_COMMON_RAW_SOURCE_UPPER_BOUND_QUERIES')
                    continue
                b=births[(u['frame'],arm)];q=next(q for q in b['queries'] if q['source']==native)
                selected[(u['frame'],native)]=(b,q,['SOURCE_UPPER_BOUND_EXCLUDED_NOT_ASSOCIATED'])
                selection_summary[(segment,arm)]['source_upper_bound_added']+=1
            for (frame,native),(b,q,reasons) in selected.items():
                ref,ref_rule=choose_reference(q,upper_queries.get(native))
                assert ref['reference_anchor'] is not None and ref['last_seen_frame'] is not None
                sample_frames=dict(joint_reference=ref['reference_anchor']['frame'],risk_last_appearance=ref['last_seen_frame'],query=frame)
                assert all(1<=f<=frame for f in sample_frames.values())
                cases.append(dict(segment=segment,start=start,arm=arm,birth=b,query=q,candidate=ref,
                    reference_rule=ref_rule,selection_reasons=reasons,sample_frames=sample_frames))
    destination=HERE/'private/birth_visualizations';public_dir=HERE/'diagnosis'
    inventory_path=public_dir/'BIRTH_VISUALIZATION_INVENTORY.json'
    assert not destination.exists() and not inventory_path.exists(),'Exclusive postseal output already exists'
    destination.mkdir(parents=True);public_dir.mkdir(exist_ok=True)
    import numpy as np
    import cv2
    cv2.setNumThreads(1)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.colors import LogNorm
    from matplotlib.cm import ScalarMappable
    decode=module('ds11_plot_decode',DS1/'depth_measurement.py').decode
    ds10=HERE.parent/'ds10_depth_failure_repair'
    RestoredDepth=module('ds11_plot_restored',ds10/'restored_source.py').RestoredDepth
    adaptive_core=module('ds11_plot_core',ds10/'adaptive_core.py').adaptive_core
    artifacts=[];reader=RestoredDepth()
    try:
        for case in cases:
            segment,arm,start=case['segment'],case['arm'],case['start'];q=case['query'];candidate=case['candidate']
            public=RUN/segment/'public';required=set(case['sample_frames'].values())
            prediction={r['frame']:r for r in rows(public/'predictions.jsonl.gz') if r['frame'] in required}
            assignments={r['frame']:r for r in rows(bindings['segments'][segment]['assignments']['path']) if r['frame'] in required}
            ledger={r['frame']:r for r in rows(public/'PUBLISH_LEDGER.jsonl') if r['frame'] in required}
            line_hashes={};disk_hashes={}
            with gzip.open(public/'predictions.jsonl.gz','rt',encoding='utf-8',newline='') as stream:
                for line in stream:
                    r=json.loads(line)
                    if r['frame'] in required:
                        prewrite=line[:-2]+'\n' if line.endswith('\r\n') else line
                        line_hashes[r['frame']]=hashlib.sha256(prewrite.encode()).hexdigest()
                        disk_hashes[r['frame']]=hashlib.sha256(line.encode()).hexdigest()
            assert all(ledger[f]['prediction_row_sha256']==line_hashes[f] for f in required)
            sources=read(bindings['segments'][segment]['source_list']['path'])
            data={};samples=[];union=np.zeros((360,640),bool);focus={candidate['source'],q['source']}
            for role,frame in case['sample_frames'].items():
                original=sources[frame-1];raw_path=Path(original['depth_path']);raw_binding=artifact(raw_path)
                assert raw_binding['sha256']==original['depth_sha256'] and raw_binding['bytes']==original['depth_bytes']
                with np.load(raw_path) as values:
                    raw=values['depth_mm'].copy();index_sha=hashlib.sha256(values['source_index'].astype('<i4').tobytes()).hexdigest()
                v2,provenance,meta=reader(start+frame-1)
                masks={int(k[2:]):decode(rle) for k,rle in assignments[frame]['masks'].items()}
                assert raw.shape==v2.shape==(360,640)
                assert all(set(mapping(prediction[frame],a))==set(masks) for a in ARMS)
                for n in focus&set(masks):union|=masks[n]
                occupancy=sum((m.astype('u2') for m in masks.values()),np.zeros((360,640),'u2'))
                cores={n:adaptive_core(masks[n],occupancy)[0] for n in focus&set(masks)}
                data[role]=(raw,v2,masks,cores,prediction[frame])
                samples.append(dict(role=role,frame=frame,global_frame=start+frame-1,time=prediction[frame]['time'],
                    raw_aligned=raw_binding,raw_source_index_sha256=index_sha,v2_native=artifact(Path(meta['native_path'])),
                    v2_row=meta['native_row'],v2_source_index_sha256=hashlib.sha256(reader.current_source_index.astype('<i4').tobytes()).hexdigest(),
                    v2_future_support=meta['future_support'],prediction_prewrite_LF_sha256=line_hashes[frame],
                    prediction_disk_line_sha256=disk_hashes[frame],actual_published={a:mapping(prediction[frame],a) for a in ARMS},
                    all_frame_masks=len(masks)))
            yy,xx=np.nonzero(union);assert yy.size
            x0,x1=max(0,int(xx.min())-24),min(640,int(xx.max())+25)
            y0,y1=max(0,int(yy.min())-24),min(360,int(yy.max())+25);region=np.s_[y0:y1,x0:x1]
            positive=np.concatenate([d[region][np.isfinite(d[region])&(d[region]>0)] for r in data.values() for d in r[:2]])
            norm=LogNorm(vmin=float(positive.min()),vmax=max(float(positive.max()),float(positive.min())+1))
            name=f'F{start+q["query_observation"]["frame"]-1:06d}_n{q["source"]}_{arm}'
            private_path=destination/(name+'.png');svg_path=public_dir/(name+'_NUMERIC.svg')
            fig,axes=plt.subplots(2,3,figsize=(21,12),constrained_layout=True);local_counts=[]
            for col,role in enumerate(case['sample_frames']):
                raw,v2,masks,cores,pred=data[role];actual=mapping(pred,arm)
                inside=[n for n,m in masks.items() if np.any(m[region])]
                for row,d in enumerate((raw,v2)):
                    ax=axes[row,col];ax.imshow(np.ma.masked_where(~np.isfinite(d)|(d<=0),d),cmap='viridis',norm=norm)
                    suspect=np.isfinite(d)&(d>5000);cy,cx=np.nonzero(suspect[region])
                    if cy.size:ax.scatter(cx+x0,cy+y0,c='red',s=4,alpha=.8,label='>5000 SUSPECT diagnostic')
                    for n in inside:
                        color='#00e5ff' if n==candidate['source'] else '#ff8c00' if n==q['source'] else '#eeeeee'
                        contours,_=cv2.findContours(masks[n].astype('u1'),cv2.RETR_LIST,cv2.CHAIN_APPROX_SIMPLE)
                        for c in contours:
                            c=c[:,0,:]
                            if len(c)>1:ax.plot(*c.T,color=color,lw=1.7 if n in focus else .7)
                        cy,cx=np.nonzero(masks[n][region]);center=(float(cx.mean())+x0,float(cy.mean())+y0)
                        if n in focus:
                            core_contours,_=cv2.findContours(cores[n].astype('u1'),cv2.RETR_LIST,cv2.CHAIN_APPROX_SIMPLE)
                            for c in core_contours:
                                c=c[:,0,:]
                                if len(c)>1:ax.plot(*c.T,color='#ff66cc',lw=1.,ls=':')
                            ax.annotate(f'source n{n}\nACTUAL public {actual[n]}',xy=center,xytext=(x1-3,y0+4) if n==q['source'] else (x0+3,y1-4),
                                ha='right' if n==q['source'] else 'left',va='top' if n==q['source'] else 'bottom',fontsize=11,color=color,
                                bbox=dict(facecolor='black',alpha=.9,pad=2),arrowprops=dict(arrowstyle='->',color=color,lw=1.5))
                        else:ax.text(*center,f'n{n}/ID{actual[n]}',fontsize=7,color='white',ha='center',va='center',bbox=dict(facecolor='black',alpha=.6,pad=.5))
                    ax.set_xlim(x0-.5,x1-.5);ax.set_ylim(y1-.5,y0-.5)
                    ax.set_title(f'{role} F{pred["global_frame"]} / '+('raw' if row==0 else 'native v2 offline'),fontsize=12)
                    values=d[region];good=values[np.isfinite(values)&(values>0)]
                    maximum=f'{good.max():.2f}' if good.size else 'NONE'
                    ax.set_xlabel(f'all local masks {len(inside)} | positive {good.size}/{values.size} | max {maximum} mm | >5000 {int((values>5000).sum())}',fontsize=9)
                local_counts.append(dict(role=role,local_masks=len(inside),source_ids=inside))
            actual=mapping(data['query'][4],arm)[q['source']];assert actual==q['actual_first_public_id']
            not_associated='NOT_ASSOCIATED / ' if q['status']!='COMMIT' else ''
            fig.suptitle(f'{arm} first birth F{start+q["query_observation"]["frame"]-1}, n{q["source"]}: {not_associated}{q["status"]}; ACTUAL first public {actual}\n'
                f'{case["reference_rule"]}; source-mask union of these three <=query times + fixed 24 px; all local neighbors retained.\n'
                'Pink dotted = geometric adaptive core. Risk source observations are anonymous; ownership/calibration UNKNOWN. No RGB / GT raster.',fontsize=13)
            fig.colorbar(ScalarMappable(norm=norm,cmap='viridis'),ax=axes,shrink=.8,label='recorded camera-Z mm; full local positive range, no high-value clipping')
            fig.savefig(private_path,dpi=140);plt.close(fig)
            measured=datasets[(segment,arm)][1];query_frame=q['query_observation']['frame'];old=candidate['source']
            past=candidate['frozen_depth']['samples'];query_time=q['query_observation']['time']
            fig,axes=plt.subplots(1,3,figsize=(19,6),constrained_layout=True)
            ax=axes[0];ax.plot([p['time']-query_time for p in past],[p['z_mm'] for p in past],'o-',label='actual joint clean raw history',ms=4)
            risk=[]
            for f in range(past[-1]['frame']+1,candidate['last_seen_frame']+1):
                fact=measured[f]['adaptive_raw'].get(str(old))
                if fact and fact['core']['median'] is not None:risk.append((measured[f]['time']-query_time,fact['core']['median']))
            if risk:ax.scatter(*zip(*risk),facecolors='none',edgecolors='#f08000',s=30,label='anonymous risk raw medians; never fit')
            current=measured[query_frame]
            for key,color,label in (('adaptive_raw','#00aabb','current raw'),('restored','#aa55cc','current v2 '+current['restored'][str(q['source'])]['cohort'])):
                fact=current[key][str(q['source'])]
                if fact['core']['median'] is not None:ax.scatter([0],[fact['core']['median']],marker='D',s=65,color=color,label=label)
            ax.axvspan(past[-1]['time']-query_time,0,color='#ffcc66',alpha=.15,label='full last-clean -> query gap')
            last_time=measured[candidate['last_seen_frame']]['time']
            ax.axvspan(last_time-query_time,0,color='gray',alpha=.2,label='source absent; no interpolated path')
            ax.set_xlabel('seconds relative to first birth (query = 0)');ax.set_ylabel('actual measured camera-Z mm')
            ax.set_title(f'full clean gap {query_time-past[-1]["time"]:.6f}s');ax.legend(fontsize=7)
            selection=q.get('selection') or {};scores=selection.get('candidates',{});ax=axes[1]
            labels=list(scores);x=np.arange(len(labels))
            if labels:
                ax.bar(x-.25,[scores[k]['geometry_log_lr'] for k in labels],.25,label='geometry log LR')
                ax.bar(x,[scores[k]['depth_log_lr'] for k in labels],.25,label='depth log LR')
                ax.bar(x+.25,[scores[k]['geometry_log_lr']+scores[k]['depth_log_lr'] for k in labels],.25,label='joint log LR')
                ax.set_xticks(x,labels,rotation=45,ha='right');ax.axhline(0,color='black',lw=.8)
                ax.legend(fontsize=8)
            else:ax.text(.5,.5,'No numeric association\n'+q['status'],ha='center',va='center',transform=ax.transAxes)
            ax.set_ylabel('dimensionless log contrast (not posterior accuracy)')
            ax.set_title('actual scored candidates incl. NEW\nreason: '+selection.get('reason',q['status']),fontsize=10)
            ax=axes[2];ax.axis('off');table=[]
            for role in case['sample_frames']:
                pred=data[role][4];n=q['source'] if role=='query' else old
                table.append([role,f'n{n}',*[str(mapping(pred,a).get(n,'absent')) for a in ARMS]])
            t=ax.table(cellText=table,colLabels=['time','source','native','F9','R11 raw','R11 v2'],loc='center',cellLoc='center')
            t.auto_set_font_size(False);t.set_fontsize(9);t.scale(1,2)
            ax.set_title('actual publication at each sampled time\nNo current ID copied backward / no GT relabeling',fontsize=10)
            fig.suptitle(f'{name}: {not_associated}{q["status"]}; first actual public {actual}\n'
                f'Joint margin {selection.get("margin")}; best-vs-NEW {selection.get("best_vs_new_margin")}; frozen threshold log(9).\n'
                'Recorded numeric measurements only. V2 upstream RGB + future support; physical surface ownership UNKNOWN.',fontsize=12)
            assert not any(a.images for a in axes)
            fig.savefig(svg_path);plt.close(fig);assert '<image' not in svg_path.read_text(encoding='utf-8')
            artifacts.append(dict(segment=segment,arm=arm,query_global_frame=start+query_frame-1,query_native=q['source'],
                selection_reasons=case['selection_reasons'],status=q['status'],actual_first_public_id=actual,
                reference_source=old,reference_rule=case['reference_rule'],reference_anchor=candidate['reference_anchor'],
                mechanical_bank_anchor=candidate.get('anchor'),runtime_candidate_eligible=candidate.get('eligible'),
                runtime_reasons=candidate.get('reasons'),numeric_selection_reason=selection.get('reason'),
                active_group_blocked=case['birth']['group_blocked'],stage_error=q.get('stage_error'),
                sample_frames=case['sample_frames'],sample_bindings=samples,local_mask_checks=local_counts,
                roi_xyxy=[x0,y0,x1,y1],private_pixel_artifact=artifact(private_path),public_numeric_svg=artifact(svg_path),
                no_frame_after_query=True,GT_raster_reads=0,RGB_reads=0,unverified_QA='PENDING_ACTUAL_PIXEL_VIEW'))
    finally:reader.close()
    summary=[dict(segment=s,arm=a,**value) for (s,a),value in selection_summary.items()]
    value=dict(status='POSTSEAL_ACTUAL_BIRTH_VISUALIZATION; PIXEL_QA_PENDING',bindings=bindings,
        selection_policy='ALL_R11_SOURCE_QUALIFIED_BIRTHS_AND_ALL_COMMITS_AND_ALL_FOUR_COMMON_RAW_SOURCE_UPPER_BOUND_QUERIES; EXCLUDED_CASES_NOT_ASSOCIATED',
        reference_policy='COMMITTED_TARGET_ELSE_HIGHEST_SCORED_OLD_ELSE_FIRST_ELIGIBLE_SOURCE_ASCENDING_ELSE_SOURCE_UPPER_BOUND',
        segment_selection=summary,case_count=len(artifacts),cases=artifacts,private_pixels_not_for_Git=True,
        GT_selection=False,GT_raster_reads=0,RGB_reads=0,new_model_calls=0,new_replays=0)
    with inventory_path.open('x',encoding='utf-8',newline='\n') as stream:json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write('\n')
    print(json.dumps(dict(cases=len(artifacts),inventory=artifact(inventory_path),selection=summary),ensure_ascii=False))


if __name__=='__main__':
    if sys.argv[1:]==['--self-check']:check()
    else:
        assert not sys.argv[1:]
        main()
