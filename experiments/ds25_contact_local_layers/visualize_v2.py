"""Postseal private actual publications and bound anonymous local support rasters."""
from common import *
import copy, io, itertools, textwrap
import cv2, numpy as np
from source import RawDepth, native_masks
from history import Sources
import measurement
cv2.setNumThreads(1)


def _postseal():
    assert (RUN/'ALL_PREDICTIONS_SEALED.json').exists(), 'Seal all predictions before RGB diagnosis'
    assert read(RUN/'METRICS.json')['status']=='SCORED_AFTER_ALL_EIGHT_PREDICTION_AND_ACCESS_SEALS'


def rgb(sensor,g,now):
    _postseal()
    meta=sensor.metadata[g]
    if sensor.kind=='FEEDING':path=DATA/meta['rgb_original'];expected=meta['source_rgb_sha256'];timestamp=meta['rgb_timestamp_us']
    elif sensor.kind=='FISHSA':path=sensor.base/meta['rgb_original'];expected=meta['source_rgb_sha256'];timestamp=meta['color_timestamp_us']
    else:path=Path(meta['rgb_source']);expected=meta['rgb_sha256'];timestamp=meta['rgb_timestamp_us']
    pin=artifact(path);assert pin['sha256']==expected and abs(timestamp/1e6-now)<1e-6
    original=cv2.imread(str(path));assert original.shape==(1080,1920,3)
    return cv2.resize(original,(640,360),interpolation=cv2.INTER_AREA),pin


def _references(comparison):
    return [*comparison.get('pre_pairs',[]), *comparison.get('anonymous_contact',[]),
        *([comparison['current_pair']] if comparison.get('current_pair') else [])]


def _case(name,row,check,comparison=None):
    value=dict(segment=name,frame=row['frame'],global_frame=row['global_frame'],
        source=check['native_id'],target=check['public_id'],anchor=check['anchor'],
        reason=check['reason'],selection_tags=[],
        candidate_edge=dict(native_id=check['native_id'],public_id=check['public_id'],
            origin_rule=check['origin_rule'],veto=check['veto'],is_candidate_not_commit=True))
    if comparison is not None:
        value.update(partner=comparison['partner_native'],comparison=comparison,reason=comparison['reason'])
    return value


def _key(case):
    return (case['segment'],case['frame'],case['source'],case['target'],case.get('partner'))


def _rebuild(name,case,public):
    """Call the sealed producer on acquired rows; capture its actual ROI arguments."""
    comparison=case.get('comparison')
    if not comparison or not comparison.get('pre_pairs'):
        return {},dict(status='NO_LOGGED_MEASUREMENT_CHAIN',new_scientific_rule=False)
    pre=comparison['pre_pairs'];q=case['frame']
    stages=[('FIRST_PRE',pre[0]['fact_id'])]
    contacts=comparison.get('anonymous_contact',[])
    selected_contact=next((x for x in contacts if x.get('contact_seed')),None)
    if selected_contact is None and contacts:selected_contact=contacts[0]
    if selected_contact is not None:stages.append(('ACTUAL_SEED' if selected_contact.get('contact_seed') else 'FIRST_ANONYMOUS',selected_contact['fact_id']))
    if comparison.get('current_pair'):stages.append(('QUERY',comparison['current_pair']['fact_id']))
    focus=case.get('focus_fact_id')
    if focus and focus not in [fid for _,fid in stages]:stages.append(('EXPLICIT_SEALED_FACT',focus))
    wanted={fid for _,fid in stages};captured={}
    provider=Sources(name,io.StringIO());original_packet=provider.packet
    def capture(frame,roi,roles=None,seed=False):
        packet=original_packet(frame,roi,roles,seed)
        if packet['fact']['fact_id'] in wanted:
            captured[packet['fact']['fact_id']]=dict(fact=copy.deepcopy(packet['fact']),roi=roi.copy())
        return packet
    provider.packet=capture
    try:
        base=input_dir(name)
        stream=zip(rows(base/'observations.jsonl.gz'),rows(base/'assignments.jsonl.gz'),rows(base/'DEPTH_OBSERVATIONS.jsonl.gz'))
        for row,assignment,saved in itertools.islice(stream,q):
            assert row['frame']<=q and (row['frame'],row['global_frame'],row['time'])==(
                saved['frame'],saved['global_frame'],saved['time'])
            provider.add(row,assignment,saved['raw_source_binding'])
        assert provider.cutoff==q
        result=provider.sequence([x['frame'] for x in pre],case['anchor']['native_id'],case['partner'],case['source'])
        assert all(result[key]==comparison[key] for key in result), 'Postseal sequence differs from sealed comparison'
        assert set(captured)==wanted, 'Requested actual ROI was not produced by the sealed sequence'
        sealed={x['fact_id']:x for x in rows(public/'MEASUREMENTS.jsonl.gz') if x['fact_id'] in wanted}
        assert set(sealed)==wanted
        nodes={}
        for label,fid in stages:
            packet=captured[fid];fact=packet['fact'];frame=fact['frame']
            assert frame<=q and fact==sealed[fid], 'Reconstructed fact differs from sealed measurement'
            depth,index,native,binding=provider.arrays_at(frame)
            expected=provider.frames[frame][2];masks=provider.masks(frame)
            full,maps=measurement.measure_region(depth,index,native,masks,packet['roi'],name,frame,
                fact['global_frame'],fact['time'],source_binding=binding,expected_source_binding=expected)
            assert full==fact and measurement.array_binding(maps['roi'])==fact['roi_binding']
            nodes[fid]=dict(label=label,fact=fact,maps=maps)
        return nodes,dict(status='EXACT_SEALED_SEQUENCE_AND_FACT_REPRODUCTION',
            sealed_comparison_sha256=digest(comparison),reconstructed_sequence_sha256=digest(result),
            query_cutoff_frame=q,source_reads=provider.reads,stage_fact_ids=stages,
            GT_RGB_restored_future_input=False,new_scientific_rule=False)
    finally:provider.close()


def _outline(image,mask,color,thickness=1):
    contours,_=cv2.findContours(mask.astype('u1'),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(image,contours,-1,color,thickness)


def _depth_image(depth):
    valid=np.isfinite(depth)&(depth>0)
    lo,hi=map(float,np.quantile(depth[valid],[.01,.99])) if valid.any() else (0.,1.)
    values=np.nan_to_num(depth,nan=0.,posinf=0.,neginf=0.)
    heat=cv2.applyColorMap(np.clip((values-lo)/max(1.,hi-lo)*255,0,255).astype('u1'),cv2.COLORMAP_TURBO)
    heat[~valid]=255
    return heat,[lo,hi]


def _panel(image,title):
    panel=cv2.copyMakeBorder(image,45,0,0,0,cv2.BORDER_CONSTANT,value=(248,248,248))
    cv2.putText(panel,title[:94],(10,27),cv2.FONT_HERSHEY_SIMPLEX,.44,(20,20,20),1,cv2.LINE_AA)
    return panel


def _local_view(image,roi):
    yy,xx=np.nonzero(roi)
    if len(xx):
        x0,x1=max(0,int(xx.min())-20),min(640,int(xx.max())+21)
        y0,y1=max(0,int(yy.min())-20),min(360,int(yy.max())+21)
    else:x0,y0,x1,y1=0,0,640,360
    scale=min(640/(x1-x0),360/(y1-y0))
    width,height=round((x1-x0)*scale),round((y1-y0)*scale)
    shown=cv2.resize(image[y0:y1,x0:x1],(width,height),interpolation=cv2.INTER_NEAREST)
    output=np.full((360,640,3),238,'u1');dx,dy=(640-width)//2,(360-height)//2
    output[dy:dy+height,dx:dx+width]=shown
    return output,dict(original_xyxy=[x0,y0,x1,y1],display_xyxy=[dx,dy,dx+width,dy+height],
        interpolation='NEAREST_DISPLAY_ONLY; NUMERICAL_MASKS_AND_DEPTH_NOT_RESAMPLED')


def render(name,case):
    _postseal();public=RUN/name/'public';verify_seal(name)
    q=case['frame'];anchor=case['anchor']['frame'];comparison=case.get('comparison',{})
    middle=comparison.get('actual_contact_seed_frame');middle_label='ACTUAL CONTACT SEED'
    if middle is None:
        risk=comparison.get('anonymous_risk_interval') or []
        middle=risk[0]['frame'] if risk else max(anchor,min(q-1,anchor+1))
        middle_label='LOGGED RISK' if risk else 'PAST SNAPSHOT; NO MEASURED SEED'
    nodes,reproduction=_rebuild(name,case,public)
    node_list=list(nodes.values());focus=case.get('focus_fact_id')
    if focus in nodes:node_list=[nodes[focus]]+[n for n in node_list if n['fact']['fact_id']!=focus]
    shown=node_list[:3]
    frames=sorted({anchor,middle,q,*[n['fact']['frame'] for n in shown]})
    assert all(f<=q for f in frames)
    predictions={r['frame']:r for r in rows(public/'predictions.jsonl.gz') if r['frame'] in frames}
    assignments={r['frame']:r for r in rows(input_dir(name)/'assignments.jsonl.gz') if r['frame'] in frames}
    saved={r['frame']:r for r in rows(input_dir(name)/'DEPTH_OBSERVATIONS.jsonl.gz') if r['frame'] in frames}
    transactions={r['arm']:r for r in rows(public/'TRANSACTIONS.jsonl.gz') if r['frame']==q}
    actual_commits={arm:[a for a in t['actual_actions'] if a['action']['native_id']==case['source']
        and a['action']['canonical_id']==case['target']] for arm,t in transactions.items()}
    if 'FIXED_F159_ACTUAL_N26_TO_P16_DIAGNOSTIC' in case['selection_tags']:
        assert any(x['actual_published'] for x in actual_commits['Z4Q_FROZEN']), 'Fixed F159 action is not an actual sealed baseline commit'
    sensor=RawDepth(name);images={};depths={};masks={};pins=[];bindings=[]
    try:
        for f in frames:
            p=predictions[f];g=p['global_frame'];now=p['time']
            arrays=sensor(g,now);assert arrays[3]==saved[f]['raw_source_binding']
            images[f],pin=rgb(sensor,g,now);pins.append(pin)
            depths[f]=arrays[0];masks[f]=native_masks(assignments[f]);bindings.append(arrays[3])
    finally:sensor.close()
    columns=(anchor,middle,q)
    footer=110+26*max((len(n['fact']['layers']) for n in shown),default=0)
    canvas=np.full((3*405+445+(2*405+footer if shown else 0),3*640,3),248,'u1')
    mapping_records=[]
    for i,arm in enumerate(ARMS):
        for j,f in enumerate(columns):
            image=images[f].copy();mapping={int(x['mask'][2:]):x['id'] for x in predictions[f]['variants'][arm]}
            assert set(mapping)==set(masks[f])
            for n,mask in masks[f].items():
                k=mapping[n];color=(50+(k*67)%180,50+(k*97)%180,50+(k*137)%180)
                _outline(image,mask,color)
                yy,xx=np.nonzero(mask)
                if len(xx):cv2.putText(image,f'n{n}:p{k}',(int(np.mean(xx)),int(np.mean(yy))),cv2.FONT_HERSHEY_SIMPLEX,.36,color,1,cv2.LINE_AA)
            label=f'{arm} | g{predictions[f]["global_frame"]} | '+('BANK REFERENCE' if j==0 else middle_label if j==1 else 'QUERY')
            canvas[i*405:(i+1)*405,j*640:(j+1)*640]=_panel(image,label)
            mapping_records.append(dict(segment=name,frame=f,global_frame=predictions[f]['global_frame'],arm=arm,actual_publication=mapping))
    heat,limits=_depth_image(depths[q]);current=images[q].copy()
    for n in (case['source'],case.get('partner')):
        if n is not None and n in masks[q]:_outline(current,masks[q][n],(0,0,255),2);_outline(heat,masks[q][n],(0,0,0),2)
    canvas[3*405+45:3*405+405,:640]=current;canvas[3*405+45:3*405+405,640:1280]=heat
    cv2.putText(canvas,'Private RGB / original camera-Z; public labels are claims, not GT',(10,3*405+29),cv2.FONT_HERSHEY_SIMPLEX,.61,(20,20,20),1,cv2.LINE_AA)
    note=[name,f'query g{case["global_frame"]}; candidate n{case["source"]} -> p{case["target"]}',
        case['reason'],f'raw Z display {limits[0]:.0f}..{limits[1]:.0f} mm',
        f'logged pre={len(comparison.get("pre_pairs",[]))}; anonymous={len(comparison.get("anonymous_contact",[]))}',
        f'local facts shown={len(shown)}; support ownership UNKNOWN']
    calculated=comparison.get('calculated_order',[])
    if calculated:
        for label,item in (('first',calculated[0]),('last',calculated[-1])):
            probability=item.get('probability_A_nearer')
            note.append(f'{label} measured p(A nearer): {probability:.4f}' if probability is not None else f'{label} order probability: NOT MEASURED')
    else:note.append('Order probabilities NOT CALCULATED; never drawn as zero')
    if not shown:note.append('No logged local measurement chain; no ROI or layers invented')
    for k,text in enumerate(note):cv2.putText(canvas,text[:84],(1290,3*405+77+k*32),cv2.FONT_HERSHEY_SIMPLEX,.42,(20,20,20),1,cv2.LINE_AA)
    node_records=[];start=3*405+445
    for j in range(3 if shown else 0):
        if j>=len(shown):
            blank=np.full((360,640,3),248,'u1')
            cv2.putText(blank,'NO SEALED LOCAL FACT FOR THIS PANEL',(20,175),cv2.FONT_HERSHEY_SIMPLEX,.58,(45,45,45),1,cv2.LINE_AA)
            for offset in (0,405):canvas[start+offset:start+offset+405,j*640:(j+1)*640]=_panel(blank,'No invented ROI, layers or depth')
            continue
        node=shown[j];fact=node['fact'];maps=node['maps'];f=fact['frame'];roi=maps['roi']
        local,local_limits=_depth_image(depths[f]);local[~roi]=(238,238,238)
        _outline(local,roi,(0,0,0),1)
        support=np.full((360,640,3),238,'u1');support[roi]=(255,255,255)
        legend=[];records=[]
        for ordinal,layer in enumerate(fact['layers'],1):
            sid=layer['support_id'];mask=maps['support_masks'][sid]
            color=(0,0,0) if layer['kind']=='MISSING_DEPTH' else (40+(ordinal*71)%190,40+(ordinal*113)%190,40+(ordinal*151)%190)
            support[mask]=color
            qualified='Q' if layer['qualified'] else 'unqualified'
            bg=layer['background_compatibility']
            short_bg={'BACKGROUND_COMPATIBLE':'BG_PROXY_COMPATIBLE',
                'DIFFERENT_FROM_LOCAL_ANNULUS_PROXY':'DIFFERENT_FROM_BG_PROXY',
                'UNKNOWN_NO_MEASURED_DEPTH':'MISSING_DEPTH'}.get(bg,bg)
            z=layer.get('z_mm');sigma=layer.get('sigma_mm')
            numbers='z=NA sigma=NA' if z is None else f'z={z:.1f} sigma={sigma:.1f}mm'
            legend.append((color,f'S{ordinal} {qualified} N={layer["independent_n"]} {numbers} {short_bg}'))
            records.append(dict(display_label=f'S{ordinal}',display_color_bgr=list(color),**layer))
        _outline(support,roi,(0,0,255),1)
        local,display_crop=_local_view(local,roi);support,support_crop=_local_view(support,roi)
        assert display_crop==support_crop
        if not roi.any():
            for image in (local,support):
                cv2.putText(image,'EMPTY ORIGINAL CONTACT ROI',(100,180),cv2.FONT_HERSHEY_SIMPLEX,.65,(45,45,45),1,cv2.LINE_AA)
        title=f'{node["label"]} g{fact["global_frame"]} ROI={fact["original_roi_area"]}px; raw Z'
        canvas[start:start+405,j*640:(j+1)*640]=_panel(local,title)
        title=f'{fact["status"]}; all {len(fact["layers"])} anonymous supports'
        canvas[start+405:start+810,j*640:(j+1)*640]=_panel(support,title)
        text=textwrap.wrap(fact['reason'],82)+[f'independentN={fact["summary"]["n"]}; missing={fact["original_roi_missing_n"]}; qualified={len(fact["qualified_support_ids"])}',
            'BG is the local annulus proxy; physical support ownership UNKNOWN']
        for k,value in enumerate(text):cv2.putText(canvas,value,(j*640+10,start+810+22+k*24),cv2.FONT_HERSHEY_SIMPLEX,.38,(20,20,20),1,cv2.LINE_AA)
        for k,(color,value) in enumerate(legend):
            y=start+810+22+(len(text)+k)*24
            cv2.rectangle(canvas,(j*640+10,y-12),(j*640+25,y),color,-1)
            cv2.putText(canvas,value,(j*640+33,y),cv2.FONT_HERSHEY_SIMPLEX,.38,(20,20,20),1,cv2.LINE_AA)
        node_records.append(dict(stage=node['label'],fact_id=fact['fact_id'],frame=f,
            global_frame=fact['global_frame'],status=fact['status'],reason=fact['reason'],
            sealed_fact_sha256=digest(fact),roi_binding=fact['roi_binding'],roi_area=fact['original_roi_area'],
            display_depth_limits_mm=local_limits,display_crop=display_crop,original_source_binding=fact['source_binding'],
            layers=records,all_measured_background_weak_and_missing_supports_drawn=True,
            all_support_legend_rows_visible=True,no_text_obscures_support_pixels=True))
    return canvas,dict(case={k:v for k,v in case.items() if k!='comparison'},
        pixel_figures_private=True,actual_published_mappings=mapping_records,
        candidate_edge=case['candidate_edge'],candidate_actual_commits=actual_commits,
        query_transaction_bindings={arm:digest(t) for arm,t in transactions.items()},
        RGB_sources=pins,raw_source_bindings=bindings,local_support_panels=node_records,reproduction=reproduction,
        comparison_sha256=digest(comparison) if comparison else None,
        GT_raster=False,used_for_prediction=False,absent_probability_is_not_zero=True)


def main():
    _postseal();manifest=HERE/'PRIVATE_VISUALS_V2.json';assert not manifest.exists()
    candidates={};fixed=None;references={};available=None;available_by_source={};source_status={}
    for name in SEGMENTS:
        verify_seal(name);first=None
        for row in rows(RUN/name/'public/ORDER_CHECKS.jsonl.gz'):
            for check in row['checks']:
                if name=='feeding_000000_000199' and row['global_frame']==159 and check['native_id']==26 and check['public_id']==16:
                    fixed=_case(name,row,check);fixed['selection_tags']=['FIXED_F159_ACTUAL_N26_TO_P16_DIAGNOSTIC']
                for comparison in check.get('comparisons',[]):
                    if not comparison.get('pre_pairs'):continue
                    case=_case(name,row,check,comparison)
                    if first is None:first=case
                    for fact in _references(comparison):references.setdefault(fact['fact_id'],case)
        source_status[name]='EARLIEST_MEASURED_CHAIN_SELECTED' if first else 'NO_ACTUAL_MEASURED_CHAIN'
        if first:
            first['selection_tags']=['EARLIEST_ACTUAL_MEASUREMENT_CHAIN_IN_SOURCE'];candidates[_key(first)]=first
        first_available=None
        for fact in rows(RUN/name/'public/MEASUREMENTS.jsonl.gz'):
            if fact['status']=='AVAILABLE_TWO_LAYERS' and (first_available is None or
                (fact['frame'],fact['fact_id'])<(first_available['frame'],first_available['fact_id'])):first_available=fact
        if first_available is not None:
            available_by_source[name]=first_available
            if available is None:available=first_available
    assert fixed is not None
    selections=[fixed,*candidates.values()]
    for available_fact in available_by_source.values():
        assert available_fact['fact_id'] in references, 'Available fact lacks a sealed logged comparison'
        case=references[available_fact['fact_id']];existing=next((x for x in selections if _key(x)==_key(case)),None)
        if existing is None:existing=copy.deepcopy(case);selections.append(existing)
        existing['focus_fact_id']=available_fact['fact_id'];existing['selection_tags'].append('EARLIEST_AVAILABLE_TWO_LAYERS_FACT_IN_SOURCE')
    # A source without a measured chain stays explicit. Additional panels are
    # first/seed/query facts of the same selected chain, never manufactured data.
    if len(selections)<4:
        for case in list(selections):
            for fact in _references(case.get('comparison',{})):
                if len(selections)>=4:break
                if any(x.get('focus_fact_id')==fact['fact_id'] for x in selections):continue
                extra=copy.deepcopy(case);extra['focus_fact_id']=fact['fact_id'];extra['selection_tags'].append('EARLIEST_ADDITIONAL_SEALED_FACT_IN_SELECTED_CHAIN')
                selections.append(extra)
            if len(selections)>=4:break
    assert len(selections)>=4, 'Fewer than four actual selected publication/support diagnostics exist'
    count=min(6,len(selections));groups=[[x] for x in selections[:count]]
    for index,case in enumerate(selections[count:]):groups[index%count].append(case)
    figures=[];private=HERE/'private'/'v2';private.mkdir(exist_ok=True)
    for index,group in enumerate(groups,1):
        sections=[];canvases=[]
        for case in group:
            canvas,record=render(case['segment'],case);canvases.append(canvas);sections.append(record)
        combined=np.concatenate(canvases,axis=0);path=private/f'actual_publications_local_supports_{index:02d}.png'
        assert not path.exists() and cv2.imwrite(str(path),combined)
        figure=dict(artifact=artifact(path),sections=sections,pixel_figures_private=True,GT_raster=False,used_for_prediction=False)
        if len(sections)==1:figure.update(sections[0])
        figures.append(figure)
    write_new(manifest,dict(status='POSTSEAL_ACTUAL_PUBLICATIONS_AND_ANONYMOUS_LOCAL_SUPPORTS_RENDERED',
        layout_revision=2,previous_attempt=artifact(HERE/'PRIVATE_VISUALS.json'),
        producer=artifact(__file__),all_prediction_seal=artifact(RUN/'ALL_PREDICTIONS_SEALED.json'),score=artifact(RUN/'METRICS.json'),
        figures=figures,private_figure_count=len(figures),selected_case_count=len(selections),source_selection_status=source_status,
        earliest_available_fact=None if available is None else dict(fact_id=available['fact_id'],segment=available['segment'],frame=available['frame'],status=available['status']),
        available_fact_diagnostics=[dict(fact_id=f['fact_id'],segment=f['segment'],frame=f['frame'],status=f['status']) for f in available_by_source.values()],
        available_two_layers_selection='NONE_EXISTS_IN_SEALED_MEASUREMENTS' if available is None else 'EARLIEST_RECORDED_FRAME_IN_ORIGINAL_SOURCE_ORDER',
        selection='Fixed F159 actual n26->p16 diagnostic; first actual measurement chain per source; earliest AVAILABLE fact per source only if present. At most6 private contact sheets preserve every selected case; no GT selection.',
        probabilities='Only logged calculated_order probabilities; absent is NOT_CALCULATED, never0.',
        all_layers='Every observed measured/background-compatible/weak/missing support retained; no invented fish ownership.',
        actual_images_not_tracking_features=True,private_pixels_excluded_from_git=True,new_model_http=0,cost_usd=0))
    print('Private actual publication/local support figures',len(figures),'cases',len(selections),flush=True)


if __name__=='__main__':main()
