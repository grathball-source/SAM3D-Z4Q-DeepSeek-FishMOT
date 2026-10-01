"""One explicit GT-posthoc reference; never numeric selection or prediction input."""
from pathlib import Path
import json,hashlib,gzip
import postseal_visualize as v
HERE=v.HERE
SEGMENT='feeding_001201_001906'
ARM='R11_RESTORED'


def main():
    _,bindings=v.sealed_inputs()
    original_path=HERE/'diagnosis/BIRTH_VISUALIZATION_INVENTORY.json';original=v.read(original_path)
    qa=v.read(HERE/'diagnosis/BIRTH_VISUALIZATION_QA.json')
    assert v.artifact(original_path)==qa['inventory']
    for case in original['cases']:
        v.verify(case['private_pixel_artifact']);v.verify(case['public_numeric_svg'])
    bound=original['bindings']['segments'][SEGMENT]
    for entry in bound['files'].values():v.verify(entry)
    public=HERE/'run'/SEGMENT/'public'
    birth=next(b for b in v.rows(public/'BIRTHS.jsonl.gz') if b['global_frame']==1805 and b['arm']==ARM)
    query=next(q for q in birth['queries'] if q['source']==194)
    candidate=next(c for c in query['candidates'] if c['source']==149)
    audit_path=HERE/'run/BIRTH_AUDIT.json'
    assert v.artifact(audit_path)['sha256']==v.read(HERE/'run/SCORING_SEALED.json')['artifacts_sha256']['BIRTH_AUDIT.json']
    audit=next(q for q in v.read(audit_path)['queries'] if q['global_frame']==1805 and q['arm']==ARM and q['source']==194)
    reference=next(c for c in audit['candidate_references'] if c['source']==149)
    assert reference['current_vs_anchor']=='SAME' and reference['pre_total']==16
    assert candidate['reasons']==['GROUP_PUBLIC_RESERVED'] and not candidate['eligible']
    assert query['selection'] is None and query['status']=='ACTIVE_GROUP_FRAME_BLOCKED' and not birth['changes']
    samples=candidate['frozen_depth']['samples'];risk=candidate['anonymous_risk_observations']
    assert len(samples)==16 and len(risk)==11
    frames=dict(joint_reference=candidate['reference_anchor']['frame'],first_anonymous_risk=risk[0]['frame'],
        latest_appearance=candidate['last_seen_frame'],first_birth=query['query_observation']['frame'])
    assert frames==dict(joint_reference=563,first_anonymous_risk=564,latest_appearance=574,first_birth=605)
    assert all(f<=birth['frame'] for f in frames.values())
    predictions={r['frame']:r for r in v.rows(public/'predictions.jsonl.gz') if r['frame'] in frames.values()}
    assignments={r['frame']:r for r in v.rows(bound['assignments']['path']) if r['frame'] in frames.values()}
    measured={r['frame']:r for r in v.rows(public/'DEPTH_OBSERVATIONS.jsonl.gz')}
    ledger={r['frame']:r for r in v.rows(public/'PUBLISH_LEDGER.jsonl') if r['frame'] in frames.values()}
    hashes={}
    with gzip.open(public/'predictions.jsonl.gz','rt',encoding='utf8',newline='') as stream:
        for line in stream:
            p=json.loads(line)
            if p['frame'] in frames.values():
                normalized=line[:-2]+'\n' if line.endswith('\r\n') else line
                hashes[p['frame']]=hashlib.sha256(normalized.encode()).hexdigest()
    assert all(ledger[f]['prediction_row_sha256']==hashes[f] for f in frames.values())
    source_list=v.read(bound['source_list']['path'])
    from common import DS1
    import numpy as np
    import cv2
    cv2.setNumThreads(1)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.colors import LogNorm
    from matplotlib.cm import ScalarMappable
    ds10=HERE.parent/'ds10_depth_failure_repair'
    decode=v.module('posthoc149_decode',DS1/'depth_measurement.py').decode
    adaptive_core=v.module('posthoc149_core',ds10/'adaptive_core.py').adaptive_core
    RestoredDepth=v.module('posthoc149_v2',ds10/'restored_source.py').RestoredDepth
    for entry in bound['restored_sources'].values():v.verify(entry)
    private_path=HERE/'private/birth_visualizations/F001805_n194_old149_POSTHOC_GT_REFERENCE_DIAGNOSTIC.png'
    numeric_path=HERE/'diagnosis/F001805_n194_old149_POSTHOC_GT_REFERENCE_NUMERIC.svg'
    inventory_path=HERE/'diagnosis/POSTHOC_REFERENCE_INVENTORY.json'
    assert not any(p.exists() for p in (private_path,numeric_path,inventory_path))
    reader=RestoredDepth();data={};sample_bindings=[];union=np.zeros((360,640),bool)
    try:
        for role,f in frames.items():
            source=source_list[f-1];path=Path(source['depth_path']);entry=v.artifact(path)
            assert entry['sha256']==source['depth_sha256'] and entry['bytes']==source['depth_bytes']
            with np.load(path) as arrays:
                raw=arrays['depth_mm'].copy();index_hash=hashlib.sha256(arrays['source_index'].astype('<i4').tobytes()).hexdigest()
            restored,provenance,meta=reader(1200+f)
            masks={int(k[2:]):decode(rle) for k,rle in assignments[f]['masks'].items()}
            assert set(masks)==set(v.mapping(predictions[f],ARM))
            for n in {149,194}&set(masks):union|=masks[n]
            occupancy=sum((m.astype('u2') for m in masks.values()),np.zeros((360,640),'u2'))
            cores={n:adaptive_core(masks[n],occupancy)[0] for n in {149,194}&set(masks)}
            data[role]=(raw,restored,masks,cores,predictions[f])
            sample_bindings.append(dict(role=role,local_frame=f,global_frame=1200+f,
                prediction_prewrite_LF_sha256=hashes[f],raw_aligned=entry,raw_source_index_sha256=index_hash,
                v2_native=v.artifact(Path(meta['native_path'])),v2_row=meta['native_row'],v2_future_support=meta['future_support'],
                v2_source_index_sha256=hashlib.sha256(reader.current_source_index.astype('<i4').tobytes()).hexdigest(),
                actual_published={a:v.mapping(predictions[f],a) for a in v.ARMS}))
    finally:reader.close()
    yy,xx=np.nonzero(union);x0,x1=max(0,int(xx.min())-24),min(640,int(xx.max())+25)
    y0,y1=max(0,int(yy.min())-24),min(360,int(yy.max())+25);region=np.s_[y0:y1,x0:x1]
    positive=np.concatenate([d[region][np.isfinite(d[region])&(d[region]>0)] for r in data.values() for d in r[:2]])
    norm=LogNorm(vmin=float(positive.min()),vmax=float(positive.max()))
    fig,axes=plt.subplots(2,4,figsize=(26,12),constrained_layout=True);local=[]
    for column,(role,f) in enumerate(frames.items()):
        raw,restored,masks,cores,prediction=data[role];actual=v.mapping(prediction,ARM)
        inside=[n for n,m in masks.items() if np.any(m[region])]
        for row,depth in enumerate((raw,restored)):
            ax=axes[row,column];ax.imshow(np.ma.masked_where(~np.isfinite(depth)|(depth<=0),depth),cmap='viridis',norm=norm)
            for n in inside:
                color='#00e5ff' if n==149 else '#ff8c00' if n==194 else '#eeeeee'
                for mask,style in [(masks[n],'-')]+([(cores[n],':')] if n in cores else []):
                    contours,_=cv2.findContours(mask.astype('u1'),cv2.RETR_LIST,cv2.CHAIN_APPROX_SIMPLE)
                    for c in contours:
                        c=c[:,0,:]
                        if len(c)>1:ax.plot(*c.T,color=color if style=='-' else '#ff66cc',lw=1.6 if n in cores else .7,ls=style)
                cy,cx=np.nonzero(masks[n][region]);center=(float(cx.mean())+x0,float(cy.mean())+y0)
                if n in {149,194}:
                    ax.annotate(f'native {n}\nACTUAL public {actual[n]}',xy=center,xytext=(x1-3,y0+4),ha='right',va='top',fontsize=13,
                        color=color,bbox=dict(facecolor='black',alpha=.9,pad=2),arrowprops=dict(arrowstyle='->',color=color,lw=1.4))
                else:ax.text(*center,f'n{n}/ID{actual[n]}',fontsize=7,color='white',ha='center',va='center',bbox=dict(facecolor='black',alpha=.6,pad=.5))
            ax.set_xlim(x0-.5,x1-.5);ax.set_ylim(y1-.5,y0-.5)
            ax.set_title(f'{role}\nF{1200+f} / '+('raw' if row==0 else 'native v2 offline'),fontsize=12)
            local_positive=depth[region][np.isfinite(depth[region])&(depth[region]>0)]
            ax.set_xlabel(f'all local masks {len(inside)}; max {local_positive.max():.2f} mm',fontsize=10)
        local.append(dict(role=role,source_ids=inside,all_local_masks=len(inside)))
    fig.colorbar(ScalarMappable(norm=norm,cmap='viridis'),ax=axes,shrink=.8,label='recorded camera-Z mm; full local positive range, no high-value clipping')
    fig.suptitle('POSTHOC_GT_REFERENCE_DIAGNOSTIC: F1805 n194 vs old149 / NOT NUMERIC SELECTION / NO COMMIT\n'
        'Sealed RGB-polygon endpoint reference: SAME. Runtime old149 excluded by GROUP_PUBLIC_RESERVED; entire birth stage ACTIVE_GROUP_FRAME_BLOCKED.\n'
        'Actual clean endpoint F1763; anonymous risk F1764..1774; source absent F1775..1804; first actual public remains 194.\n'
        'GT used only for this posthoc explanation; no GT raster/RGB texture. No identity copied backward; physical surface ownership UNKNOWN.',fontsize=14)
    fig.savefig(private_path,dpi=140);plt.close(fig)
    fig,axes=plt.subplots(1,3,figsize=(19,6),constrained_layout=True);query_time=birth['time'];ax=axes[0]
    ax.plot([p['time']-query_time for p in samples],[p['z_mm'] for p in samples],'o-',label='16 actual joint raw samples')
    anonymous=[]
    for p in risk:
        fact=measured[p['frame']]['adaptive_raw']['149']
        if fact['core']['median'] is not None:anonymous.append((p['time']-query_time,fact['core']['median']))
    if anonymous:ax.scatter(*zip(*anonymous),facecolors='none',edgecolors='#f08000',label='anonymous risk medians; no fit')
    for key,color,label in (('adaptive_raw','#0088bb','query raw'),('restored','#aa44bb','query v2 retained')):
        fact=measured[birth['frame']][key]['194'];ax.scatter([0],[fact['core']['median']],marker='D',s=80,color=color,label=label)
    ax.axvspan(samples[-1]['time']-query_time,0,color='#ffcc66',alpha=.15,label='full last-clean gap')
    ax.axvspan(candidate['last_seen_time']-query_time,0,color='gray',alpha=.2,label='source absent; no interpolated path')
    ax.axvline(measured[candidate['anchor']['frame']]['time']-query_time,color='purple',ls=':',label='separate mechanical bank anchor')
    ax.set_xlabel('seconds relative to first birth');ax.set_ylabel('actual camera-Z median mm');ax.legend(fontsize=7)
    ax.set_title(f'full gap {candidate["risk_interval"]["full_gap_seconds"]:.6f}s; raw actual MAD, not inferred proxy')
    axes[1].axis('off');axes[1].text(.5,.5,'POSTHOC endpoint identity: SAME\n\nold149 runtime eligible: FALSE\nGROUP_PUBLIC_RESERVED\n\nEntire birth stage blocked\nNo LR evaluated / no numerical selection\nNO COMMIT',ha='center',va='center',fontsize=13,transform=axes[1].transAxes)
    axes[2].axis('off');table=[]
    for role,f in frames.items():
        native=194 if role=='first_birth' else 149
        table.append([role,f'F{1200+f}',native,*[v.mapping(predictions[f],a).get(native,'absent') for a in v.ARMS]])
    t=axes[2].table(cellText=table,colLabels=['time','frame','native','N0','F9','raw','v2'],cellLoc='center',loc='center')
    t.auto_set_font_size(False);t.set_fontsize(8);t.scale(1,2)
    axes[2].set_title('ACTUAL publications, not GT-renamed IDs')
    fig.suptitle('POSTHOC_GT_REFERENCE_DIAGNOSTIC: n194 vs old149; SAME reference is explanatory only\n'
        'F1805 actual first public 194; original numeric selection and all original eight plots preserved.\n'
        'Recorded numeric depths; V2 upstream RGB/future offline; physical surface ownership and calibration UNKNOWN.',fontsize=12)
    assert not any(a.images for a in axes);fig.savefig(numeric_path);plt.close(fig)
    assert '<image' not in numeric_path.read_text(encoding='utf8')
    for case in original['cases']:
        v.verify(case['private_pixel_artifact']);v.verify(case['public_numeric_svg'])
    result=dict(status='APPENDED_POSTHOC_GT_REFERENCE_DIAGNOSTIC; PIXEL_QA_PENDING',code=v.artifact(Path(__file__)),
        original_inventory=v.artifact(original_path),original_QA=v.artifact(HERE/'diagnosis/BIRTH_VISUALIZATION_QA.json'),
        all_prediction_seal=bindings['all_prediction_seal'],scoring_seal=bindings['scoring_seal'],birth_audit=v.artifact(audit_path),
        sealed_segment_binding=bound,source='HUMAN_REQUEST_FIXED_F1805_N194_OLD149_AND_SEALED_POSTHOC_ENDPOINT_REFERENCE',
        original_case_selection_unchanged=True,original_eight_plots_unchanged=True,
        private_pixel_artifact=v.artifact(private_path),public_numeric_svg=v.artifact(numeric_path),sample_bindings=sample_bindings,
        reference_anchor=candidate['reference_anchor'],mechanical_bank_anchor=candidate['anchor'],runtime_reasons=candidate['reasons'],
        raw_joint_fact_ids=[p['fact_id'] for p in samples],joint_sample_count=16,anonymous_risk_count=11,full_gap_seconds=candidate['risk_interval']['full_gap_seconds'],
        posthoc_endpoint_relation=reference['current_vs_anchor'],posthoc_pre_all_vs_anchor=reference['pre_all_vs_anchor'],
        runtime_status=query['status'],actual_first_public_id=query['actual_first_public_id'],numeric_selection=None,committed=False,
        local_mask_checks=local,roi_xyxy=[x0,y0,x1,y1],GT_used_only_for_posthoc_explanation=True,GT_raster_reads=0,RGB_reads=0,
        physical_surface_identity='UNKNOWN',physical_depth_GT=False,new_model_calls=0,new_replays=0,no_frame_after_query=True)
    with inventory_path.open('x',encoding='utf8',newline='\n') as f:json.dump(result,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps(dict(inventory=v.artifact(inventory_path),private_plot=result['private_pixel_artifact'],public_numeric_svg=result['public_numeric_svg']),ensure_ascii=False))


if __name__=='__main__':main()
