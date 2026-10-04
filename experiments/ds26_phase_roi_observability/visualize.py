"""Postseal private raw-depth sheets for every fixed context; no identity result."""
from common import *
from collections import defaultdict
import copy
import runpy
import cv2
import numpy as np
from source import RawDepth, native_masks
import source
from measure import saved_frames

cv2.setNumThreads(1)
CELL_W, IMAGE_H, HEADER_H = 480, 275, 96
COLORS = dict(qualified=(70, 180, 70), background=(165, 165, 165),
    weak=(35, 175, 245), missing=(15, 15, 15), A=(235, 160, 30),
    B=(30, 125, 235), old=(205, 35, 190), other=(115, 115, 115))


def _postseal():
    seal = read(RUN/'MEASUREMENTS_SEALED.json')
    review = read(HERE/'POSTSEAL_REVIEW.json')
    assert seal['status'] == 'SEALED_BEFORE_INDEPENDENT_REVIEW' and review['status'] == 'PASS'
    for item in seal['artifacts'].values(): verify_item(item)
    verify_item(seal['cohort']); verify_item(seal['runtime']); verify_item(review['seal'])
    for path, expected in read(HERE/'FREEZE.json')['code'].items(): assert sha(path) == expected, path
    return seal, review


def _wrap(text, width, scale=.44):
    words = str(text).split(); lines=[]; line=''
    for word in words:
        value=(line+' '+word).strip()
        if cv2.getTextSize(value, cv2.FONT_HERSHEY_SIMPLEX, scale, 1)[0][0] <= width:
            line=value; continue
        if line: lines.append(line); line=''
        while cv2.getTextSize(word, cv2.FONT_HERSHEY_SIMPLEX, scale, 1)[0][0] > width:
            cut=max(i for i in range(1,len(word))
                if cv2.getTextSize(word[:i],cv2.FONT_HERSHEY_SIMPLEX,scale,1)[0][0] <= width)
            lines.append(word[:cut]);word=word[cut:]
        line=word
    if line: lines.append(line)
    return lines or ['']


def _text(image, texts, x, y, width, scale=.44, spacing=19, color=(35,35,35)):
    for text in texts:
        for line in _wrap(text,width,scale):
            assert y < image.shape[0]-3, 'Figure text exceeds its allocated panel'
            cv2.putText(image,line,(x,y),cv2.FONT_HERSHEY_SIMPLEX,scale,color,1,cv2.LINE_AA)
            y+=spacing
    return y


def _outline(image, mask, color, thickness=1):
    contours,_=cv2.findContours(mask.astype('u1'),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(image,contours,-1,color,thickness)


def _crop(masks, roi):
    union=roi.copy()
    for mask in masks.values(): union |= mask
    yy,xx=np.nonzero(union)
    if not len(xx): return [0,0,roi.shape[1],roi.shape[0]]
    return [max(0,int(xx.min())-12),max(0,int(yy.min())-12),
        min(roi.shape[1],int(xx.max())+13),min(roi.shape[0],int(yy.max())+13)]


def _fit(image, crop):
    x0,y0,x1,y1=crop;part=image[y0:y1,x0:x1]
    scale=min((CELL_W-20)/part.shape[1],(IMAGE_H-20)/part.shape[0])
    width=max(1,int(round(part.shape[1]*scale)));height=max(1,int(round(part.shape[0]*scale)))
    display=cv2.resize(part,(width,height),interpolation=cv2.INTER_NEAREST)
    out=np.full((IMAGE_H,CELL_W,3),248,'u1')
    ox=(CELL_W-width)//2;oy=(IMAGE_H-height)//2
    out[oy:oy+height,ox:ox+width]=display
    return out,dict(crop_xyxy=crop,output_pixels=[CELL_W,IMAGE_H],
        displayed_pixels=[width,height],offset_xy=[ox,oy],display_scale=scale,
        coordinate_transform='x_display=(x_raw-crop_x0)*scale+offset_x; same for y; nearest-neighbor display only')


def _depth_image(depth, limits):
    valid=np.isfinite(depth)&(depth>0);low,high=limits
    scaled=np.zeros(depth.shape,'u1')
    scaled[valid]=np.rint(np.clip((depth[valid]-low)/max(1.,high-low),0,1)*255).astype('u1')
    image=cv2.applyColorMap(scaled,cv2.COLORMAP_TURBO);image[~valid]=COLORS['missing']
    return image


def _supports(fact,maps):
    image=np.full((*maps['roi'].shape,3),248,'u1');image[maps['roi']]=(230,230,230)
    for layer in fact['layers']:
        if layer['kind']=='MISSING_DEPTH': name='missing'
        elif layer['qualified']: name='qualified'
        elif layer['background_compatibility']=='BACKGROUND_COMPATIBLE': name='background'
        else: name='weak'
        image[maps['support_masks'][layer['support_id']]]=COLORS[name]
    return image


def _description(fact):
    return [f"ROI {fact['original_roi_area']} px; independent N {fact['summary']['n']}; "
        f"declared Q {len(fact['qualified_support_ids'])}; missing {fact['original_roi_missing_n']}",
        fact['reason']]


def _selected_contexts(cohort):
    selected=[]
    for context in cohort['contexts']:
        candidates=[p for p in cohort['logical_pairs'] if p['context_id']==context['context_id']]
        first=min(candidates,key=lambda p:(p['q'],p['current_native'],p['pair_id']))
        selected.append((context,first))
    selected.sort(key=lambda value:(list(SEGMENTS).index(value[0]['key']['segment']),
        value[1]['q'],value[0]['context_id']))
    assert len(selected)==15 and len({c['context_id'] for c,p in selected})==15
    return selected


def _old_rois(context,pair,assignments,oldfacts):
    """Same fixed-window equation, driven by the unchanged preceding fact.

    Independent centroid_xy is the exact recorded mean of the canonical source
    positions used by DS25 Sources.sequence. The displayed nodes are additionally
    remeasured below and must equal the entire old fact, not only its ROI hash.
    """
    key=context['key'];a=key['anchor']['native_id'];b=key['partner_native']
    seed_frame=key['seed_frame'];masks=native_masks(assignments[seed_frame])
    seed=old_measurement.contact_seed(masks,a,b)
    assert old_measurement.array_binding(seed)==key['seed_binding']
    assert {str(n):old_measurement.array_binding(masks[n]) for n in (a,b)}==key['seed_original_mask_bindings']
    cfg=read(DS25/'CONFIG.json');margin=cfg['local_expansion_px']
    initial=cv2.dilate(seed.astype('u1'),np.ones((2*margin+1,)*2,'u1')).astype(bool)
    yy,xx=np.nonzero(seed);seed_center=np.array([xx.mean(),yy.mean()])
    wanted={key['pre_frames'][0],key['pre_frames'][-1],seed_frame,pair['q']}
    output={};window=initial.copy();transform=dict(dx=0.,dy=0.,driven_by_fact_id=None)
    for cite in pair['ds25_citations']['pre_pairs']:
        f=cite['frame'];fact=oldfacts[cite['fact_id']];assert digest(fact)==cite['measurement_sha256']
        if f in wanted:
            m=native_masks(assignments[f]);roi=window&(m[a]|m[b])
            assert old_measurement.array_binding(roi)==fact['roi_binding']
            output[f]=(roi,fact,copy.deepcopy(transform))
    previous=oldfacts[pair['ds25_citations']['pre_pairs'][-1]['fact_id']]
    contacts=pair['ds25_citations']['anonymous_contact']
    assert [c['frame'] for c in contacts]==list(range(key['anchor']['frame']+1,pair['q']))
    for cite in [*contacts,pair['ds25_citations']['current_pair']]:
        if previous['status']=='AVAILABLE_TWO_LAYERS':
            qualified=[x for x in previous['layers'] if x['support_id'] in previous['qualified_support_ids']]
            assert len(qualified)==2
            delta=np.mean([x['independent_spatial']['centroid_xy'] for x in qualified],axis=0)-seed_center
            dx,dy=map(float,delta)
            window=cv2.warpAffine(initial.astype('u1'),np.array([[1.,0.,dx],[0.,1.,dy]]),
                (initial.shape[1],initial.shape[0]),flags=cv2.INTER_NEAREST,
                borderMode=cv2.BORDER_CONSTANT,borderValue=0).astype(bool)
            assert window.sum()<=initial.sum()
            transform=dict(dx=dx,dy=dy,driven_by_fact_id=previous['fact_id'])
        f=cite['frame'];fact=oldfacts[cite['fact_id']]
        assert digest(fact)==cite['measurement_sha256'] and f<=pair['q']
        if f in wanted:
            m=native_masks(assignments[f]);union=np.zeros(initial.shape,bool)
            if f==pair['q']: union=m[pair['current_native']]|m[b]
            else:
                for mask in m.values(): union |= mask
            roi=window&union;assert old_measurement.array_binding(roi)==fact['roi_binding']
            output[f]=(roi,fact,copy.deepcopy(transform))
        previous=fact
    assert set(output)==wanted
    return output,dict(actual_seed_binding=old_measurement.array_binding(seed),
        initial_window_binding=old_measurement.array_binding(initial),initial_window_area=int(initial.sum()),
        local_expansion_px=margin,seed_center_xy=seed_center.tolist(),
        movement_policy='UNCHANGED_DS25_PREVIOUS_TWO_QUALIFIED_INDEPENDENT_CENTROIDS; FIXED_INITIAL_WINDOW',
        outside_q_reads=False)


def _render(context,pair,data,oldfacts,endpointfacts,pairings):
    key=context['key'];name=key['segment'];q=pair['q']
    stages=[('FIRST PRE',key['pre_frames'][0]),('LAST PRE',key['pre_frames'][-1]),
        ('ANONYMOUS SEED',key['seed_frame']),('EARLIEST q',q)]
    rois,reproduction=_old_rois(context,pair,data['assignments'],oldfacts)
    sensor=RawDepth(name);nodes=[]
    try:
        for label,f in stages:
            row=data['observations'][f];expected=data['depth'][f]['raw_source_binding']
            depth,index,native,binding=sensor(row['global_frame'],row['time']);assert binding==expected
            masks=native_masks(data['assignments'][f]);roi,oldfact,shift=rois[f]
            actual_old,oldmaps=old_measurement.measure_region(depth,index,native,masks,roi,name,f,
                row['global_frame'],row['time'],source_binding=binding,expected_source_binding=expected)
            assert actual_old==oldfact,'Displayed old source/body differs from sealed full fact'
            node=dict(label=label,frame=f,global_frame=row['global_frame'],time=row['time'],
                depth=depth,masks=masks,roi=roi,oldfact=oldfact,oldmaps=oldmaps,
                binding=binding,shift=shift,roles={},endpoints={})
            if label!='ANONYMOUS SEED':
                native_roles={'A':pair['current_native'] if f==q else key['anchor']['native_id'],
                    'B':key['partner_native']}
                matches=[p for p in pairings if p['context_id']==context['context_id'] and p['frame']==f and
                    (p.get('pair_id')==pair['pair_id'] if f==q else p['phase'].startswith('PRE'))]
                assert len(matches)==1;logged=matches[0]
                assert logged['native_roles']==native_roles
                for role,n in native_roles.items():
                    fact,maps=old_measurement.measure_region(depth,index,native,masks,masks[n],name,f,
                        row['global_frame'],row['time'],source_binding=binding,expected_source_binding=expected)
                    reference=logged['role_facts'][role]
                    assert fact==endpointfacts[reference['fact_id']] and digest(fact)==reference['measurement_sha256']
                    node['roles'][role]=masks[n];node['endpoints'][role]=(fact,maps)
                node['logged']=logged
            nodes.append(node)
    finally: sensor.close()
    values=np.concatenate([n['depth'][np.isfinite(n['depth'])&(n['depth']>0)] for n in nodes])
    limits=list(map(float,np.quantile(values,[.01,.99]))) if len(values) else [0.,1.]
    if limits[1]<=limits[0]: limits[1]=limits[0]+1.
    canvas=np.full((1450,CELL_W*4,3),255,'u1')
    _text(canvas,[f"DS26 {name} | {context['context_id']} | fixed earliest q={q}",
        'Only original measured camera-Z and masks. Anonymous proxy supports; physical identity UNKNOWN.',
        'Columns selected before viewing depth: first pre / last pre / actual contact seed / earliest q.'],
        16,24,canvas.shape[1]-32,.54,24)
    records=[]
    for col,node in enumerate(nodes):
        x=col*CELL_W;roles=node['roles'];focus=roles or {}
        if not focus:
            focus={str(n):node['masks'][n] for n in (key['anchor']['native_id'],key['partner_native'])}
        crop=_crop(focus,node['roi'])
        raw=_depth_image(node['depth'],limits)
        for mask in node['masks'].values():_outline(raw,mask,COLORS['other'])
        for role,mask in roles.items():_outline(raw,mask,COLORS[role],2)
        _outline(raw,node['roi'],COLORS['old'],2)
        raw,display=_fit(raw,crop)
        y=108
        _text(canvas,[f"{node['label']} | global F{node['global_frame']} / local F{node['frame']}",
            'Raw measured Z; old ROI=magenta; A/B geometric masks=blue/orange' if roles else
            'Contact is anonymous: grey original masks, magenta old ROI'],x+10,y+20,CELL_W-20)
        canvas[y+HEADER_H:y+HEADER_H+IMAGE_H,x:x+CELL_W]=raw
        y=500;oldimage=_supports(node['oldfact'],node['oldmaps'])
        _outline(oldimage,node['roi'],COLORS['old'],2)
        for role,mask in roles.items():_outline(oldimage,mask,COLORS[role],1)
        oldimage,old_display=_fit(oldimage,crop);assert old_display==display
        _text(canvas,['UNCHANGED anonymous local ROI',*_description(node['oldfact'])],
            x+10,y+20,CELL_W-20,.40,18)
        canvas[y+HEADER_H:y+HEADER_H+IMAGE_H,x:x+CELL_W]=oldimage
        y=894;endpointimage=np.full((360,640,3),248,'u1')
        endpoint_records={}
        if roles:
            description=['ACTUAL role masks; support identity remains UNKNOWN']
            for role,(fact,maps) in node['endpoints'].items():
                image=_supports(fact,maps);endpointimage[maps['roi']]=image[maps['roi']]
                _outline(endpointimage,roles[role],COLORS[role],2)
                description.append(f"{role}: area {fact['original_roi_area']}; N {fact['summary']['n']}; "
                    f"Q {len(fact['qualified_support_ids'])}; missing {fact['original_roi_missing_n']}")
                endpoint_records[role]=dict(fact_id=fact['fact_id'],fact_sha256=digest(fact),
                    original_status=fact['status'],original_reason=fact['reason'],roi_binding=fact['roi_binding'],
                    layers=copy.deepcopy(fact['layers']),exact_full_fact_reproduction=True)
            _outline(endpointimage,node['roi'],COLORS['old'],1)
        else:
            description=['NO A/B endpoint measurement for contact.',
                'All original measured / weak / background / missing supports remain in the anonymous panel above.']
            endpointimage=_supports(node['oldfact'],node['oldmaps'])
            _outline(endpointimage,node['roi'],COLORS['old'],2)
        endpointimage,endpoint_display=_fit(endpointimage,crop);assert endpoint_display==display
        _text(canvas,description,x+10,y+20,CELL_W-20,.40,18)
        canvas[y+HEADER_H:y+HEADER_H+IMAGE_H,x:x+CELL_W]=endpointimage
        records.append(dict(stage=node['label'],frame=node['frame'],global_frame=node['global_frame'],time=node['time'],
            query_limit=q,display_transform=display,window_translation=node['shift'],
            old_fact_id=node['oldfact']['fact_id'],old_fact_sha256=digest(node['oldfact']),
            old_status=node['oldfact']['status'],old_reason=node['oldfact']['reason'],
            old_roi_binding=node['oldfact']['roi_binding'],old_roi_area=node['oldfact']['original_roi_area'],
            actual_source_binding=copy.deepcopy(node['binding']),original_masks={str(n):old_measurement.array_binding(m) for n,m in node['masks'].items()},
            actual_role_mask_bindings={role:old_measurement.array_binding(m) for role,m in roles.items()},
            old_layers=copy.deepcopy(node['oldfact']['layers']),endpoint_facts=endpoint_records,
            exact_old_full_fact_reproduction=True,contact_identity_roles_assigned=False,
            RGB_GT_future_restored=False))
    legend_y=1287
    labels=[('qualified','Per-support qualified flag (original parent gates may still fail)'),
        ('background','Background-compatible proxy support retained'),('weak','Weak/noisy/unknown support retained'),
        ('missing','Missing actual depth retained'),('A','A geometric mask outline; not physical identity'),
        ('B','B geometric mask outline; not physical identity'),('old','Unchanged anonymous local ROI outline')]
    for i,(name,label) in enumerate(labels):
        lx=16+(i%2)*950;ly=legend_y+(i//2)*26
        cv2.rectangle(canvas,(lx,ly-12),(lx+16,ly+4),COLORS[name],-1)
        _text(canvas,[label],lx+26,ly+1,900,.43,19)
    _text(canvas,[f"Raw Z display limits {limits[0]:.1f}..{limits[1]:.1f} mm "
        '(pooled displayed frames 1%..99%; display clipping only). No completion, depth selection or identity decision.'],
        16,1411,canvas.shape[1]-32,.43,19)
    metadata=dict(context_id=context['context_id'],pair_id=pair['pair_id'],segment=pair['segment'],
        q=q,global_q=pair['global_frame'],reference=key,selection='ALL_15_CONTEXTS; ORIGINAL_SEGMENT_ORDER; '
        'MINIMUM_Q_THEN_CURRENT_NATIVE_AND_PAIR_ID; FIXED_FIRST_PRE_LAST_PRE_SEED_Q; NO_DEPTH_SELECTION',
        selected_reference=pair,depth_display_limits_mm=limits,reproduction=reproduction,nodes=records,
        original_public_mapping_at_q=pair['actual_published_mapping_at_q'],
        no_RGB_GT_future_restored=True,no_identity_state_write=True,new_model_http=0,cost_usd=0,
        figures_private=True,physical_identity='UNKNOWN',performance_claim='NONE')
    return canvas,metadata


def main():
    seal,review=_postseal();assert not (HERE/'PRIVATE_VISUALS.json').exists()
    seal_artifact=artifact(RUN/'MEASUREMENTS_SEALED.json')
    review_artifact=artifact(HERE/'POSTSEAL_REVIEW.json')
    guard=runpy.run_path(str(ROOT/'experiments/ds20_pending_confirmation_isolation/guard.py'),run_name='ds26_visual_guard')
    cohort=read(HERE/'COHORT.json');selected=_selected_contexts(cohort)
    selected_ids={p['pair_id'] for c,p in selected};context_ids={c['context_id'] for c,p in selected}
    pairings=[p for p in rows(RUN/'PAIRINGS.jsonl.gz') if p['context_id'] in context_ids and
        (p['phase'].startswith('PRE') or p.get('pair_id') in selected_ids)]
    old_needed={cite['fact_id'] for c,p in selected for stage in p['ds25_citations'].values()
        for cite in (stage if isinstance(stage,list) else [stage])}
    oldfacts={f['fact_id']:f for f in rows(RUN/'OLD_UNCHANGED_FACTS.jsonl.gz') if f['fact_id'] in old_needed}
    endpoint_needed={ref['fact_id'] for p in pairings for ref in p['role_facts'].values()}
    endpointfacts={f['fact_id']:f for f in rows(RUN/'ENDPOINT_FACTS.jsonl.gz') if f['fact_id'] in endpoint_needed}
    assert set(oldfacts)==old_needed and set(endpointfacts)==endpoint_needed
    bysegment=defaultdict(set)
    for c,p in selected:bysegment[p['segment']].update((c['first_pre_frame'],c['last_pre_frame'],p['seed_frame'],p['q']))
    data={name:saved_frames(name,wanted) for name,wanted in bysegment.items()}
    private=HERE/'private'/'v2';private.mkdir(parents=True,exist_ok=False);figures=[]
    for number,(context,pair) in enumerate(selected,1):
        canvas,metadata=_render(context,pair,data[pair['segment']],oldfacts,endpointfacts,pairings)
        base=private/f"phase_roi_{number:02d}_{context['context_id']}"
        image=base.with_suffix('.png');meta=base.with_suffix('.json')
        assert not image.exists() and not meta.exists()
        assert cv2.imwrite(str(image),canvas);write_new(meta,metadata)
        figures.append(dict(context_id=context['context_id'],pair_id=pair['pair_id'],segment=pair['segment'],
            earliest_q=pair['q'],image=artifact(image),metadata=artifact(meta),
            stages=[dict(stage=n['stage'],frame=n['frame'],global_frame=n['global_frame'],
                old_roi_area=n['old_roi_area'],actual_role_count=len(n['endpoint_facts']),
                old_full_fact_reproduced=n['exact_old_full_fact_reproduction'],
                endpoint_full_facts_reproduced=all(v['exact_full_fact_reproduction'] for v in n['endpoint_facts'].values()))
                for n in metadata['nodes']],physical_identity='UNKNOWN',used_for_prediction=False))
        print(number,pair['segment'],context['context_id'],'q',pair['q'],'four raw stages verified',flush=True)
    write_new(HERE/'PRIVATE_VISUALS.json',dict(status='POSTSEAL_PRIVATE_PHASE_MEASUREMENT_FIGURES_COMPLETE',
        producer=artifact(__file__),measurement_seal=seal_artifact,
        postseal_review=review_artifact,figures=figures,
        fixed_contexts=15,private_figure_count=len(figures),selected_stage_nodes=60,
        old_full_facts_reproduced=60,endpoint_full_facts_reproduced=90,
        selection='ALL15; ORIGINAL_SEGMENT_ORDER; EARLIEST_Q; FIRST_PRE_LAST_PRE_SEED_Q; NO_DEPTH_OR_GT_SELECTION',
        raw_only=True,RGB_GT_restored=False,no_identity_state_write=True,performance_claim='NONE',
        layers='ALL_MEASURED_WEAK_BACKGROUND_COMPATIBLE_MISSING_RETAINED; GEOMETRIC_ROLE_NOT_IDENTITY',
        access=dict(observed_data_paths=sorted(guard['SEEN']),
            npz_field_reads=[dict(path=p,key=k) for p,k in sorted(guard['NPZ'])],h5_or_array_fields=source.FIELD_READS),
        pixels_private=True,new_model_http=0,cost_usd=0))


if __name__=='__main__':main()
