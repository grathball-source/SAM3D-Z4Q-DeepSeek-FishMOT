"""Postseal actual-mask/raw-depth sheets, selected chronologically without GT.

This producer never reads RGB or reference labels. Per source and policy, the
first nonzero matrix adjustment is selected; absent adjustments, the first
measured comparison is shown. Absent comparisons remain numeric-only records.
"""
from common import *
from measurement import Measurement
from evidence import endpoint
from collections import defaultdict
from functools import lru_cache
import cv2
import numpy as np

raw_source = module('ds27_visualization_raw_source',
    ROOT/'experiments/ds16_relative_depth_order/source.py')
RawDepth, native_masks = raw_source.RawDepth, raw_source.native_masks
cv2.setNumThreads(1)
W, IMAGE_H = 440, 240
COLORS = dict(qualified=(70,180,70), background=(155,155,155),
    weak=(35,175,245), missing=(15,15,15), A=(235,160,30), B=(30,125,235))

_saved_artifact=lru_cache(maxsize=None)(artifact)


def _postseal():
    path = RUN/'ALL_PREDICTIONS_SEALED.json'
    whole = read(path)
    assert whole['status'] == 'ALL_PREDICTIONS_AND_ACCESS_SEALED'
    assert whole['frames'] == 20098 and tuple(whole['arms']) == ARMS
    for name in SEGMENTS:
        verify_seal(name)
        verify_item(whole['seals'][name])
        verify_item(whole['access_seals'][name])
        frozen=read(RUN/name/'public/FREEZE.json')
        verify_item(frozen['source_manifest'])
        for item in frozen['source_chain']['derived_inputs'].values():verify_item(item)
        for key in ('scan','raw_sources','field_access'):verify_item(frozen['source_chain'][key])
    return path


def _wrap(value,width,scale=.44):
    words=str(value).split();lines=[];line=''
    for word in words:
        new=(line+' '+word).strip()
        if cv2.getTextSize(new,cv2.FONT_HERSHEY_SIMPLEX,scale,1)[0][0] <= width:
            line=new;continue
        if line:lines.append(line);line=''
        while cv2.getTextSize(word,cv2.FONT_HERSHEY_SIMPLEX,scale,1)[0][0] > width:
            cut=max(i for i in range(1,len(word))
                if cv2.getTextSize(word[:i],cv2.FONT_HERSHEY_SIMPLEX,scale,1)[0][0] <= width)
            lines.append(word[:cut]);word=word[cut:]
        line=word
    return lines+[line] if line else lines


def _text(canvas,lines,x,y,width,scale=.44,spacing=19):
    for line in lines:
        for value in _wrap(line,width,scale):
            assert y < canvas.shape[0]-3, 'Text allocation exceeded'
            cv2.putText(canvas,value,(x,y),cv2.FONT_HERSHEY_SIMPLEX,scale,(30,30,30),1,cv2.LINE_AA)
            y+=spacing
    return y


def _outline(image,mask,color,thickness=1):
    contours,_=cv2.findContours(mask.astype('u1'),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(image,contours,-1,color,thickness)


def _fit(image,crop):
    x0,y0,x1,y1=crop;part=image[y0:y1,x0:x1]
    scale=min((W-20)/part.shape[1],(IMAGE_H-20)/part.shape[0])
    shape=[max(1,int(round(part.shape[1]*scale))),max(1,int(round(part.shape[0]*scale)))]
    display=cv2.resize(part,tuple(shape),interpolation=cv2.INTER_NEAREST)
    out=np.full((IMAGE_H,W,3),248,'u1');ox=(W-shape[0])//2;oy=(IMAGE_H-shape[1])//2
    out[oy:oy+shape[1],ox:ox+shape[0]]=display
    return out,dict(crop_xyxy=crop,output_pixels=[W,IMAGE_H],displayed_pixels=shape,
        offset_xy=[ox,oy],display_scale=scale,
        coordinate_transform='display=(raw-crop_origin)*scale+offset; nearest-neighbor display only')


def _depth(depth,limits):
    valid=np.isfinite(depth)&(depth>0);lo,hi=limits
    z=np.zeros(depth.shape,'u1');z[valid]=np.rint(np.clip((depth[valid]-lo)/(hi-lo),0,1)*255).astype('u1')
    result=cv2.applyColorMap(z,cv2.COLORMAP_TURBO);result[~valid]=COLORS['missing']
    return result


def _supports(fact,maps):
    result=np.full((*maps['roi'].shape,3),248,'u1');drawn=np.zeros(maps['roi'].shape,bool)
    for layer in fact['layers']:
        name=('missing' if layer['kind']=='MISSING_DEPTH' else 'qualified' if layer['qualified']
            else 'background' if layer['background_compatibility']=='BACKGROUND_COMPATIBLE' else 'weak')
        region=maps['support_masks'][layer['support_id']]
        assert not np.any(region&~maps['roi'])
        drawn|=region;result[region]=COLORS[name]
    assert np.array_equal(drawn,maps['roi']), 'A measured or missing ROI pixel was hidden'
    return result


def _case(name,arm,row,check,ordinal,comparison=None,selection=None):
    return dict(segment=name,arm=arm,q=row['frame'],global_frame=row['global_frame'],time=row['time'],
        check_ordinal=ordinal,check=check,comparison=comparison,selection=selection,
        check_sha256=digest(check),comparison_sha256=digest(comparison) if comparison else None)


def select_cases():
    chosen=[]
    for name in SEGMENTS:
        first={}; comparable={}; updates={};counts={a:dict(checks=0,comparisons=0,nonzero_updates=0) for a in ARMS[2:]}
        for row in rows(RUN/name/'public/ORDER_CHECKS.jsonl.gz'):
            for arm in ARMS[2:]:
                for ordinal,check in enumerate(row['checks'][arm]):
                    counts[arm]['checks']+=1
                    first.setdefault(arm,_case(name,arm,row,check,ordinal))
                    matches=[c for c in check.get('comparisons',[]) if c.get('pre_pairs') and c.get('current_pair')]
                    counts[arm]['comparisons']+=len(matches)
                    if matches:comparable.setdefault(arm,_case(name,arm,row,check,ordinal,matches[0]))
                    if check.get('applied_delta_cost',0):
                        counts[arm]['nonzero_updates']+=1
                        assert matches, 'Actual depth cost lacks its complete measured comparison'
                        active=next((c for c in matches if c.get('delta_cost',0)),None)
                        assert active is not None
                        updates.setdefault(arm,_case(name,arm,row,check,ordinal,active))
        for arm in ARMS[2:]:
            if arm in updates:case=dict(updates[arm],selection='EARLIEST_NONZERO_APPLIED_DEPTH_COST')
            elif arm in comparable:case=dict(comparable[arm],selection='EARLIEST_COMPARABLE_PRE_Q_PAIR_NO_COST_UPDATE')
            elif arm in first:case=dict(first[arm],selection='EARLIEST_CHECK_NUMERIC_ONLY_NO_COMPARABLE_PAIR')
            else:case=dict(segment=name,arm=arm,selection='NO_COMPETITIVE_CHECK_NUMERIC_ONLY',check=None,comparison=None)
            case['source_arm_counts']=counts[arm];chosen.append(case)
    assert len(chosen)==len(SEGMENTS)*len(VARIANTS)
    return chosen


def _loaded(name,wanted):
    base=input_dir(name)
    values={k:{r['frame']:r for r in rows(base/path) if r['frame'] in wanted}
        for k,path in [('observations','observations.jsonl.gz'),('assignments','assignments.jsonl.gz'),
            ('depth','DEPTH_OBSERVATIONS.jsonl.gz')]}
    assert all(set(v)==wanted for v in values.values())
    return values


def _fact_references(case):
    comparison=case['comparison'];before=comparison['pre_pairs'][-1];after=comparison['current_pair']
    assert comparison['pre_frames'][-1]==case['check']['anchor']['frame']
    return {'PRE':before,'q':after}


def _render(case,logged_facts):
    name,arm,q=case['segment'],case['arm'],case['q'];check=case['check'];comp=case['comparison']
    refs=_fact_references(case);pre_frame=check['anchor']['frame'];wanted={pre_frame,q}
    data=_loaded(name,wanted);producer=Measurement(arm);nodes=[];source_pins=[]
    sensor=RawDepth(name)
    try:
        for stage,f in [('PRE',pre_frame),('q',q)]:
            row=data['observations'][f];saved=data['depth'][f]
            assert f<=q and row['time']<=case['time']
            assert (row['frame'],row['global_frame'],row['time'])==(saved['frame'],saved['global_frame'],saved['time'])
            depth,index,native,binding=sensor(row['global_frame'],row['time']);assert binding==saved['raw_source_binding']
            assert not any(binding.get(k,False) for k in ('GT_read','RGB_read','restored_read'))
            masks=native_masks(data['assignments'][f])
            roles={'A':check['anchor']['native_id'] if stage=='PRE' else check['native_id'], 'B':comp['partner_native']}
            assert roles['A']!=roles['B']
            observations={o['id']:o for o in row['observations']}
            for role,n in roles.items():
                assert n in masks and n in observations and int(masks[n].sum())==observations[n]['area']
                fact,maps=producer.measure_region(depth,index,native,masks,masks[n],name,f,
                    row['global_frame'],row['time'],source_binding=binding,expected_source_binding=saved['raw_source_binding'])
                ref=refs[stage][role];key=(arm,ref['fact_id'],ref['measurement_sha256'])
                assert key in logged_facts and fact==logged_facts[key] and digest(fact)==ref['measurement_sha256'], \
                    'Displayed source/body differs from frozen trace and actual measurement'
                packet=dict(fact=fact,maps=dict(selected_positions={s:maps['selected_positions'][s]
                    for s in fact['qualified_support_ids']}),source_index=index)
                assert endpoint(packet)==ref, 'Displayed endpoint conditional/null status differs from sealed evidence'
                nodes.append(dict(stage=stage,role=role,native=n,frame=f,global_frame=row['global_frame'],
                    time=row['time'],fact=fact,maps=maps,depth=depth,masks=masks,reference=ref,
                    source_binding=binding))
            source_pins.append(dict(frame=f,source_binding=binding,
                saved_observation_row_sha256=row_sha(row),saved_assignment_row_sha256=row_sha(data['assignments'][f]),
                saved_depth_row_sha256=row_sha(saved)))
    finally:sensor.close()
    assert len(nodes)==4
    # Only already-selected PRE/q source pixels set a display color scale; it is
    # not a measurement threshold, source selection, or physical calibration.
    values=np.concatenate([n['depth'][n['maps']['roi']&np.isfinite(n['depth'])&(n['depth']>0)] for n in nodes])
    limits=list(map(float,np.quantile(values,[.01,.99]))) if len(values) else [0.,1.]
    if limits[1]<=limits[0]:limits[1]=limits[0]+1.
    headers=[];legends=[];crops=[];panels=[]
    for node in nodes:
        f=node['fact'];plane=f['plane'];role=node['role'];version=(comp['pre_versions'][role] if node['stage']=='PRE'
            else comp['current_partner_claim_version'] if role=='B' else 'CURRENT_NATIVE; IDENTITY_UNKNOWN')
        hs=[f"{node['stage']} {role}: native {node['native']}, F{node['frame']} / global {node['global_frame']}",
            f"version/reference {version}",node['reference']['status'],node['reference']['reason'],
            f"independent N {f['summary']['n']} / mask area {f['original_roi_area']}; missing {f['original_roi_missing_n']}",
            'background plane UNKNOWN' if plane is None else
                f"background sigma {plane['residual_scale_mm']:.2f} mm; contrast gate {plane['contrast_threshold_mm']:.2f} mm"]
        headers.append([line for text in hs for line in _wrap(text,W-28)])
        lines=[]
        for i,l in enumerate(f['layers'],1):
            z='UNKNOWN' if l.get('z_mm') is None else f"{l['z_mm']:.2f}"
            sig='UNKNOWN' if l.get('sigma_mm') is None else f"{l['sigma_mm']:.2f}"
            lines += _wrap(f"S{i} {l['kind']}; Q flag {int(l['qualified'])}; N {l['independent_n']} / inclusive {l['inclusive_n']}; z {z}; sigma {sig} mm; {l['background_compatibility']}",W-28)
        legends.append(lines)
        yy,xx=np.nonzero(node['maps']['roi']);assert len(xx)
        crops.append([max(0,int(xx.min())-22),max(0,int(yy.min())-22),
            min(node['depth'].shape[1],int(xx.max())+23),min(node['depth'].shape[0],int(yy.max())+23)])
    header_h=max(map(len,headers))*19+14;legend_h=max(map(len,legends))*19+20
    top=115;raw_y=top+header_h;support_y=raw_y+IMAGE_H+27;legend_y=support_y+IMAGE_H+25
    canvas=np.full((legend_y+legend_h+82,W*4,3),255,'u1')
    _text(canvas,[f"DS27 {name} | {arm} | earliest q={q} | {case['selection']}",
        f"Candidate native {check['native_id']} -> public {check['public_id']} is a hypothesis. Applied cost {check['applied_delta_cost']:.8f}.",
        'Original raw depth + original masks; all supports retained. Physical identity/accuracy UNKNOWN; no RGB/GT.',
        'Green = qualified flag; grey = background-compatible; orange = weak/unresolved; black = missing. Parent null status shown above.'],
        14,24,canvas.shape[1]-28,.49,22)
    for col,(node,crop) in enumerate(zip(nodes,crops,strict=True)):
        x=col*W;_text(canvas,headers[col],x+14,top+20,W-28)
        raw=_depth(node['depth'],limits);supports=_supports(node['fact'],node['maps'])
        for n,mask in node['masks'].items():
            if n!=node['native']:_outline(raw,mask,(145,145,145))
        _outline(raw,node['maps']['roi'],COLORS[node['role']],2)
        _outline(supports,node['maps']['annulus'],(195,195,195))
        _outline(supports,node['maps']['roi'],COLORS[node['role']],1)
        raw_cell,transform=_fit(raw,crop);support_cell,support_transform=_fit(supports,crop)
        canvas[raw_y:raw_y+IMAGE_H,x:x+W]=raw_cell
        canvas[support_y:support_y+IMAGE_H,x:x+W]=support_cell
        _text(canvas,['Original measured camera-Z + actual mask'],x+14,raw_y-5,W-28)
        _text(canvas,['All measured/weak/background/missing supports'],x+14,support_y-5,W-28)
        _text(canvas,legends[col],x+14,legend_y+20,W-28)
        panels.append(dict(stage=node['stage'],role=node['role'],native=node['native'],frame=node['frame'],
            global_frame=node['global_frame'],time=node['time'],role_identity='UNKNOWN',
            version_reference=comp['pre_versions'][node['role']] if node['stage']=='PRE' else
                comp['current_partner_claim_version'] if node['role']=='B' else 'CURRENT_NATIVE_IDENTITY_UNKNOWN',
            actual_mask_binding=producer.array_binding(node['maps']['roi']),
            fact_id=node['fact']['fact_id'],fact_sha256=digest(node['fact']),endpoint=node['reference'],
            depth_binding=producer.array_binding(node['depth']),
            source_binding_sha256=digest(node['source_binding']),transform=transform,support_transform=support_transform,
            all_layers=[{k:l.get(k) for k in ('support_id','kind','qualified','inclusive_qualified','substantial',
                'independent_n','inclusive_n','z_mm','sigma_mm','median_residual_mm','background_compatibility',
                'geometric_component_binding','population_binding')} for l in node['fact']['layers']],
            all_original_ROI_pixels_measured_or_missing_drawn=True,no_text_obscures_support_pixels=True))
    _text(canvas,[f"Display Z limits {limits[0]:.2f} .. {limits[1]:.2f} mm (1st/99th percentiles of selected PRE/q masks; display only).",
        f"Logged pre median probability {comp['pre_probability_median']:.6f}; q probability {comp['current_probability']:.6f}; common-null weight remains in the original calculation."],
        14,canvas.shape[0]-48,canvas.shape[1]-28,.47,22)
    return canvas,dict(panels=panels,actual_source_pins=source_pins,
        display_depth_limits_mm=limits,pre_versions=comp['pre_versions'],
        conditional_mapping_hypothesis=comp['complete_mapping_hypothesis'],
        identity='UNKNOWN',physical_accuracy_mm='UNKNOWN',GT_read=False,RGB_read=False,used_for_prediction=False)


def _render_diagnostic(case,transaction,handle):
    """Measure blocked geometry after seal; never masquerade as formal evidence."""
    name,arm,q=case['segment'],case['arm'],case['q'];check=case['check']
    anchor=check.get('anchor');pre=anchor.get('frame') if anchor else None
    assert pre is None or 1<=pre<=q
    listed=next((c for c in check.get('comparisons',[]) if 'partner_native' in c),None)
    partner=listed['partner_native'] if listed else None
    wanted={q}|({pre} if pre is not None else set());data=_loaded(name,wanted)
    producer=Measurement(arm);nodes=[];source_pins=[];sensor=RawDepth(name)
    try:
        for stage,f in [('PRE',pre),('q',q)]:
            if f is None:
                nodes.extend(dict(stage=stage,role=role,native=None,frame=None,
                    unavailable='NO_LOGGED_TARGET_ANCHOR') for role in ('A','B'));continue
            row=data['observations'][f];saved=data['depth'][f]
            assert row['time']<=case['time'] and f<=q
            assert (row['frame'],row['global_frame'],row['time'])==(saved['frame'],saved['global_frame'],saved['time'])
            depth,index,native,binding=sensor(row['global_frame'],row['time'])
            assert binding==saved['raw_source_binding']
            assert not any(binding.get(k,False) for k in ('GT_read','RGB_read','restored_read'))
            masks=native_masks(data['assignments'][f]);obs={o['id']:o for o in row['observations']}
            roles={'A':anchor['native_id'] if stage=='PRE' else check['native_id'], 'B':partner}
            source_pins.append(dict(frame=f,source_binding=binding,
                saved_observation_row_sha256=row_sha(row),saved_assignment_row_sha256=row_sha(data['assignments'][f]),
                saved_depth_row_sha256=row_sha(saved)))
            for role,n in roles.items():
                if n is None or n not in masks:
                    nodes.append(dict(stage=stage,role=role,native=n,frame=f,
                        unavailable='NO_LOGGED_PARTNER' if n is None else 'LOGGED_PARTNER_NOT_PRESENT_IN_ACTUAL_PRE_MASKS'))
                    continue
                assert n in obs and int(masks[n].sum())==obs[n]['area']
                fact,maps=producer.measure_region(depth,index,native,masks,masks[n],name,f,
                    row['global_frame'],row['time'],source_binding=binding,expected_source_binding=saved['raw_source_binding'])
                packet=dict(fact=fact,maps=dict(selected_positions={s:maps['selected_positions'][s]
                    for s in fact['qualified_support_ids']}),source_index=index)
                measured=endpoint(packet)
                provenance=dict(case_segment=name,arm=arm,query_frame=q,check_sha256=case['check_sha256'],
                    stage=stage,role=role,actual_native=n,observed_neighbors=obs[n].get('neighbors',[]),
                    original_formal_block_reason=check.get('reason'),
                    first_listed_partner_block_reason=listed.get('reason') if listed else None,
                    source_binding_sha256=digest(binding),actual_mask_binding=producer.array_binding(masks[n]),
                    observation_row_sha256=row_sha(row),assignment_row_sha256=row_sha(data['assignments'][f]),
                    expected_raw_depth_row_sha256=row_sha(saved),
                    source_saved_files={k:_saved_artifact(input_dir(name)/v) for k,v in
                        [('observations','observations.jsonl.gz'),('assignments','assignments.jsonl.gz'),
                         ('depth','DEPTH_OBSERVATIONS.jsonl.gz')]},
                    scope='POSTSEAL_DIAGNOSTIC_NOT_FORMAL_INPUT_NOT_USED_FOR_ASSOCIATION',
                    source_identity_qualification='NOT_PERFORMED',physical_identity='UNKNOWN')
                record=dict(provenance=provenance,measurement=fact,measurement_sha256=digest(fact),
                    calculated_endpoint_diagnostic=measured,new_model_http=0,cost_usd=0)
                handle.write(json.dumps(record,separators=(',',':'),allow_nan=False)+'\n')
                nodes.append(dict(stage=stage,role=role,native=n,frame=f,global_frame=row['global_frame'],
                    time=row['time'],fact=fact,maps=maps,depth=depth,masks=masks,reference=measured,
                    source_binding=binding,provenance=provenance))
    finally:sensor.close()
    assert len(nodes)==4 and any('fact' in n for n in nodes)
    values=np.concatenate([n['depth'][n['maps']['roi']&np.isfinite(n['depth'])&(n['depth']>0)]
        for n in nodes if 'fact' in n])
    limits=list(map(float,np.quantile(values,[.01,.99]))) if len(values) else [0.,1.]
    if limits[1]<=limits[0]:limits[1]=limits[0]+1.
    headers=[];legends=[]
    for node in nodes:
        hs=[f"{node['stage']} {node['role']}: native {node['native']}, F{node['frame']}",
            'DIAGNOSTIC ONLY; NOT FORMAL ASSOCIATION INPUT', 'Source identity/clean-reference UNKNOWN']
        ls=[]
        if 'fact' not in node:hs += ['UNKNOWN',node['unavailable']]
        else:
            f=node['fact'];plane=f['plane'];hs += [node['reference']['status'],node['reference']['reason'],
                f"observed neighbors {node['provenance']['observed_neighbors']}; independent N {f['summary']['n']}; mask area {f['original_roi_area']}",
                'background plane UNKNOWN' if plane is None else
                    f"background sigma {plane['residual_scale_mm']:.2f}; contrast gate {plane['contrast_threshold_mm']:.2f} mm"]
            for i,l in enumerate(f['layers'],1):
                z='UNKNOWN' if l.get('z_mm') is None else f"{l['z_mm']:.2f}"
                sig='UNKNOWN' if l.get('sigma_mm') is None else f"{l['sigma_mm']:.2f}"
                ls += _wrap(f"S{i} {l['kind']}; Q flag {int(l['qualified'])}; N {l['independent_n']} / inclusive {l['inclusive_n']}; z {z}; sigma {sig} mm; {l['background_compatibility']}",W-28)
        headers.append([line for text in hs for line in _wrap(text,W-28)]);legends.append(ls)
    titles=[f"DS27 {name} | {arm} | earliest blocked q={q}",
        'POSTSEAL DIAGNOSTIC ONLY: measured now; not sent to the frozen association and not a new tracking result.',
        f"Actual formal gate: {check.get('reason','UNKNOWN')}; matrix delta {check.get('applied_delta_cost',0):.8f}.",
        f"First logged partner gate: {listed.get('reason','NONE') if listed else 'NO_LOGGED_PARTNER'}.",
        'Original raw depth/masks only; missing roles remain UNKNOWN. Physical identity/accuracy UNKNOWN; no RGB/GT.',
        'Green = Q flag; grey = background-compatible; orange = weak; black = missing. Flags do not certify source identity.']
    footers=[f"Display Z limits {limits[0]:.2f} .. {limits[1]:.2f} mm (selected PRE/q only; display scale, not accuracy).",
        f"Actual first-publish mapping at q: {transaction['actual_published_mapping']}",
        'New diagnostic measurements cannot replace null formal evidence or certify a rejected source/version.']
    top=sum(len(_wrap(t,W*4-28,.48)) for t in titles)*22+32
    footer_h=sum(len(_wrap(t,W*4-28,.46)) for t in footers)*22+28
    header_h=max(map(len,headers))*19+14;raw_y=top+header_h
    support_y=raw_y+IMAGE_H+27;legend_y=support_y+IMAGE_H+25;legend_h=max(map(len,legends))*19+20
    canvas=np.full((legend_y+legend_h+footer_h,W*4,3),255,'u1');panels=[]
    _text(canvas,titles,14,24,canvas.shape[1]-28,.48,22)
    for col,node in enumerate(nodes):
        x=col*W;_text(canvas,headers[col],x+14,top+20,W-28)
        if 'fact' not in node:
            _text(canvas,['UNKNOWN - no actual bound role'],x+14,raw_y+45,W-28,.52)
            panels.append({k:node[k] for k in ('stage','role','native','frame','unavailable')});continue
        yy,xx=np.nonzero(node['maps']['roi']);assert len(xx)
        crop=[max(0,int(xx.min())-22),max(0,int(yy.min())-22),
            min(node['depth'].shape[1],int(xx.max())+23),min(node['depth'].shape[0],int(yy.max())+23)]
        raw=_depth(node['depth'],limits);supports=_supports(node['fact'],node['maps'])
        for n,mask in node['masks'].items():
            if n!=node['native']:_outline(raw,mask,(145,145,145))
        _outline(raw,node['maps']['roi'],COLORS[node['role']],2)
        _outline(supports,node['maps']['annulus'],(195,195,195));_outline(supports,node['maps']['roi'],COLORS[node['role']],1)
        raw_cell,transform=_fit(raw,crop);support_cell,support_transform=_fit(supports,crop)
        canvas[raw_y:raw_y+IMAGE_H,x:x+W]=raw_cell;canvas[support_y:support_y+IMAGE_H,x:x+W]=support_cell
        _text(canvas,['Original measured camera-Z + actual mask'],x+14,raw_y-5,W-28)
        _text(canvas,['All measured/weak/background/missing supports'],x+14,support_y-5,W-28)
        _text(canvas,legends[col],x+14,legend_y+20,W-28)
        panels.append(dict(stage=node['stage'],role=node['role'],native=node['native'],frame=node['frame'],
            global_frame=node['global_frame'],time=node['time'],fact_id=node['fact']['fact_id'],
            fact_sha256=digest(node['fact']),endpoint_diagnostic=node['reference'],provenance=node['provenance'],
            transform=transform,support_transform=support_transform,
            all_original_ROI_pixels_measured_or_missing_drawn=True,no_text_obscures_support_pixels=True))
    _text(canvas,footers,14,legend_y+legend_h+20,canvas.shape[1]-28,.46,22)
    return canvas,dict(panels=panels,actual_source_pins=source_pins,display_depth_limits_mm=limits,
        scope='POSTSEAL_DIAGNOSTIC_NOT_FORMAL_INPUT_NOT_USED_FOR_ASSOCIATION',
        gate_repair_attempted=False,tracking_score_claim='NONE',identity='UNKNOWN',physical_accuracy_mm='UNKNOWN',
        GT_read=False,RGB_read=False,used_for_prediction=False)


def main():
    seal_path=_postseal();target=HERE/'PRIVATE_VISUALS.json';assert not target.exists()
    cases=select_cases();needed=defaultdict(set)
    for case in cases:
        if case['comparison']:
            for p in _fact_references(case).values():
                for role in ('A','B'):needed[case['segment']].add((case['arm'],p[role]['fact_id'],p[role]['measurement_sha256']))
    logged={}
    for name,keys in needed.items():
        for r in rows(RUN/name/'public/MEASUREMENTS.jsonl.gz'):
            f=r['measurement'];key=(r['arm'],f['fact_id'],digest(f))
            if key in keys:logged[(name,*key)]=f
        assert all((name,*key) in logged for key in keys)
    transactions={}
    for name in SEGMENTS:
        wanted={(case['arm'],case['q']) for case in cases if case['segment']==name and case.get('check')}
        for t in rows(RUN/name/'public/TRANSACTIONS.jsonl.gz'):
            if (t['arm'],t['frame']) in wanted:transactions[(name,t['arm'],t['frame'])]=t
    private=HERE/'private';private.mkdir(exist_ok=True);records=[];figures=[]
    diagnostic_path=HERE/'DIAGNOSTIC_ENDPOINTS.jsonl.gz'
    assert not diagnostic_path.exists()
    diagnostic_handle=gzip.open(diagnostic_path,'xt',encoding='utf-8')
    try:
      for case in cases:
        record={k:v for k,v in case.items() if k not in ('check','comparison')}
        record['check']=case['check']
        if case['comparison']:
            subset={key[1:]:fact for key,fact in logged.items() if key[0]==case['segment']}
            canvas,detail=_render(case,subset)
            path=private/f"{case['segment']}_{case['arm']}_F{case['q']:05d}.png"
            assert not path.exists() and cv2.imwrite(str(path),canvas)
            tx=transactions[(case['segment'],case['arm'],case['q'])]
            record.update(detail,figure=artifact(path),query_transaction_sha256=digest(tx),
                actual_query_published_mapping=tx['actual_published_mapping'],
                actual_query_actions=tx['actual_actions'],pixel_figure_private=True)
            figures.append(artifact(path))
        elif case.get('check'):
            tx=transactions[(case['segment'],case['arm'],case['q'])]
            canvas,detail=_render_diagnostic(case,tx,diagnostic_handle)
            path=private/f"{case['segment']}_{case['arm']}_blocked_F{case['q']:05d}.png"
            assert not path.exists() and cv2.imwrite(str(path),canvas)
            record.update(detail,figure=artifact(path),query_transaction_sha256=digest(tx),
                actual_query_published_mapping=tx['actual_published_mapping'],
                actual_query_actions=tx['actual_actions'],pixel_figure_private=True)
            figures.append(artifact(path))
        else:
            record.update(figure=None,reason='NO_ACTUAL_PRE_Q_COMPARISON; NUMERIC_ONLY_NO_FABRICATED_PIXELS')
        records.append(record)
    finally:diagnostic_handle.close()
    write_new(target,dict(status='POSTSEAL_PRIVATE_RAW_DEPTH_AND_ALL_SUPPORTS_RENDERED',
        producer=artifact(Path(__file__)),all_prediction_seal=artifact(seal_path),
        figure_count=len(figures),source_arm_case_count=len(records),figures=figures,cases=records,
        postseal_diagnostic_measurements=artifact(diagnostic_path),
        selection='Per source+arm earliest actual nonzero applied cost; else earliest measured comparison; else earliest blocked check with separate postseal diagnostic measurements.',
        no_reference_or_score_used_for_selection=True,all_qualified_weak_background_missing_retained=True,
        comparable_formal_facts_reconstructed_and_exactly_bound_to_measurement_and_comparison=True,
        blocked_diagnostic_facts_are_new_postseal_only_never_formal_evidence=True,
        private_pixels_excluded_from_publication=True,GT_raster=False,RGB_read=False,
        new_model_http=0,cost_usd=0))
    print(json.dumps(dict(private_figures=len(figures),source_arm_cases=len(records),GT_read=False,RGB_read=False)))


if __name__=='__main__':main()
