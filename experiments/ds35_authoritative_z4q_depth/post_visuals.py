"""Postseal actual-source panels and public numeric figures; pixels stay private."""
from common import *
from html import escape
COLORS={'SAM3_NATIVE':'#6b7280','Z4Q_FROZEN':'#2563eb','DEPTH_OFF':'#b45309','DEPTH_OVERRIDE':'#15803d'}
NAMES={'SAM3_NATIVE':'Native','Z4Q_FROZEN':'Z4Q','DEPTH_OFF':'Depth off','DEPTH_OVERRIDE':'Depth override'}
RGB_PINS={name:{} for name in SEGMENTS}
for pin in rows(ROOT/'experiments/ds33_rgbd_fixed_lag/RGB_INPUT_PINS.jsonl'):RGB_PINS[pin['segment']][pin['global_frame']]=pin['rgb']

def text(x,y,value,size=12,fill='#111827'):
    return f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}">{escape(str(value))}</text>'


def svg(width,height,body):
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}"><rect width="100%" height="100%" fill="white"/><g font-family="Arial,sans-serif">'+''.join(body)+'</g></svg>\n'


def public_figures(metric,event_sets):
    sections=[('Feeding pooled temporal segments',metric['feeding_pooled']['metrics'])]+[
        (name,value['metrics']) for name,value in metric['segments'].items() if not name.startswith('feeding_')]
    assert len(sections)==5
    body=[text(20,28,'DS35 full-sequence tracking: all four actual state branches',20),
        text(20,50,'0–100 percent scale; L3/LW use weak preannotation. Fixed publication delay ≤30 frames. No added/deleted masks.')]
    y=88;numeric=[]
    for name,values in sections:
        body.append(text(20,y,name,15));y+=22
        for index,field in enumerate(('IDF1','HOTA','AssA')):
            x=30+index*410;body.append(text(x,y,field,13))
            for arm_index,arm in enumerate(ARMS):
                value=float(values[arm][field]);assert 0<=value<=100
                yy=y+20+arm_index*21
                body.append(text(x,yy,NAMES[arm],11,COLORS[arm]))
                body.append(f'<rect x="{x+92}" y="{yy-10}" width="{value*2.15:.6f}" height="12" fill="{COLORS[arm]}"/>')
                body.append(text(x+318,yy,f'{value:.4f}',11))
                numeric.append(dict(dataset=name,arm=arm,metric=field,value=value))
        y+=116
        body.append(text(30,y,'IDSW / FP / FN: '+' | '.join(f'{NAMES[arm]} {values[arm]["IDSW"]}/{values[arm]["FP"]}/{values[arm]["FN"]}' for arm in ARMS),11))
        y+=21
        body.append(text(30,y,'Depth − Z4Q: '+' / '.join(f'{field} {values["DEPTH_OVERRIDE"][field]-values["Z4Q_FROZEN"][field]:+.4f} pp' for field in ('IDF1','HOTA','AssA'))+
            ' | Depth − off: '+' / '.join(f'{values["DEPTH_OVERRIDE"][field]-values["DEPTH_OFF"][field]:+.4f}' for field in ('IDF1','HOTA','AssA')),11))
        y+=26;body.append(f'<path d="M20 {y-8} H1260" stroke="#e5e7eb"/>')
    directory=HERE/'visuals';directory.mkdir(exist_ok=True)
    path=directory/'FULL_METRICS.svg'
    with path.open('x',encoding='utf-8',newline='\n') as output:output.write(svg(1280,y+12,body))
    figures=[artifact(path)];timeline=[]
    body=[text(20,28,'Every automatic episode: decision and actual first publication',20),
        text(20,51,'No split, missing evidence, fallback and unchanged publications remain visible. Stage/choice is not physical correctness.'),
        text(20,73,'Coverage is conditional measurement support; it is not foreground, depth accuracy or identity accuracy.')];y=105
    for name in SEGMENTS:
        for arm in ARMS[2:]:
            audit={e['event']:e for e in metric['event_audits'][name]['event_arms'][arm]}
            for event in event_sets[name][arm]:
                decision=event.get('joint_decision',{});restore=event.get('restore',{});q=event.get('q')
                coverage=[]
                for candidate in decision.get('scores',[]):
                    for edge in candidate.get('edges',[]):
                        for sample in edge.get('contour_samples',[]):
                            if sample.get('available'):
                                coverage.extend(sample[key] for key in ('forward_reliable_fraction','backward_reliable_fraction') if sample.get(key) is not None)
                actual=audit.get(event['id'],{})
                value=dict(segment=name,arm=arm,event=event['id'],suspect=event['suspect_frame'],q=q,
                    cutoff=event.get('decision_cutoff'),first_publish=event.get('first_publish_at_arrival_frame'),
                    status=event['status'],choice=decision.get('choice','UNKNOWN'),staged=bool(restore.get('staged')),
                    fallback=restore.get('fallback'),depth_weight=decision.get('common_weights',{}).get('depth'),
                    reliable_fraction_samples=coverage,physical_preanchor=actual.get('physical_preanchor','UNSCORABLE'),
                    changes_real_publication=actual.get('changes_real_publication',False),
                    actual_changes_vs_Z4Q=actual.get('actual_changes_vs_Z4Q',{}))
                timeline.append(value)
                mean=sum(coverage)/len(coverage) if coverage else None
                body.append(text(20,y,f'{name} | {NAMES[arm]} | suspect {event["suspect_frame"]} → q {q if q is not None else "NONE"} → cutoff {value["cutoff"]} → first publish {value["first_publish"]}',12));y+=19
                body.append(text(34,y,f'{value["status"]} / choice {value["choice"]} / stage {value["staged"]} / depth weight {value["depth_weight"]} / mean reliable fraction {mean if mean is not None else "UNKNOWN"} / physical {value["physical_preanchor"]} / change vs Z4Q {value["changes_real_publication"]}',11));y+=28
    if not timeline:body.append(text(20,y,'No automatic episodes in the fixed eight sources.'));y+=24
    path=directory/'EVENT_TIMELINE.svg'
    with path.open('x',encoding='utf-8',newline='\n') as output:output.write(svg(1700,y+15,body))
    figures.append(artifact(path))
    write_new(HERE/'PUBLIC_VISUALS.json',dict(status='SCORED_NUMERIC_ONLY',metrics=artifact(RUN/'METRICS.json'),
        helper=artifact(__file__),figures=figures,figure_values=numeric,event_values=timeline,
        all_five_dataset_blocks=True,all_automatic_events=True,private_pixels=False,GT_rasters=False,
        correspondence_coverage_is_not_physical_accuracy=True))


def selected_rows(path,wanted):
    if not wanted:return {}
    result={}
    for row in rows(path):
        if row['frame'] in wanted:result[row['frame']]=row
        if row['frame']>=max(wanted):break
    assert set(result)==wanted,(str(path),wanted-set(result));return result


def phases(event):
    result=[]
    for role in ('A','B'):
        reference=event.get('joint_pre',{}).get(role,{});anchor=reference.get('anchor')
        result.append((f'PRE_{role} / {reference.get("status","UNKNOWN")}',anchor['frame'] if anchor else None))
    result.append(('FIRST_SUSPECT',event['suspect_frame']))
    group=event.get('group',[]);result.append(('GROUP_LAST_ACTUAL',group[-1]['frame'] if group else None))
    result.append(('Q_FIRST_SPLIT' if event.get('q') is not None else 'NO_SPLIT_Q_UNKNOWN',event.get('q')))
    result.append(('DECISION_OR_END',event.get('decision_cutoff') or event.get('end')))
    return result


def private_case(name,event,arm,destination):
    import cv2,numpy as np
    from pycocotools import mask as coco
    from sensor import Sensor
    cv2.setNumThreads(1)
    selected=phases(event);wanted={f for _,f in selected if f is not None};start,stop=SEGMENTS[name]
    assert all(1<=f<=stop-start+1 for f in wanted)
    base=input_dir(name);public=RUN/name/'public'
    observation=selected_rows(base/'observations.jsonl.gz',wanted);assignment=selected_rows(base/'assignments.jsonl.gz',wanted)
    prediction=selected_rows(public/'predictions.jsonl.gz',wanted);binding=selected_rows(public/'FRAME_INPUTS_BINDINGS.jsonl.gz',wanted)
    snapshots={};source_proofs=[];sensor=Sensor(name)
    try:
        for f in sorted(wanted):
            row=observation[f];saved=assignment[f];bound=binding[f];pred=prediction[f]
            assert row['global_frame']==saved['global_frame_id']==pred['global_frame']==bound['global_frame']==start+f-1
            assert row['time']==saved['time']==pred['time']==bound['time']
            assert row_sha(row)==bound['source_row_sha256'] and row_sha(saved)==bound['assignment_row_sha256']
            assert saved['variants']['N0']==row['native']==pred['variants']['SAM3_NATIVE']
            actual=sensor.read(row['global_frame'],row['time'])
            assert actual['binding']['rgb']==RGB_PINS[name][row['global_frame']]
            verify_item(actual['binding']['rgb'])
            for key in ('aligned_depth','aligned_source_index','native_depth'):assert actual['binding'][key]==bound['raw_source_binding'][key]
            rgb=cv2.imread(actual['binding']['rgb']['path']);assert rgb is not None
            if rgb.shape[:2]!=(360,640):rgb=cv2.resize(rgb,(640,360),interpolation=cv2.INTER_AREA)
            assert np.array_equal(cv2.cvtColor(rgb,cv2.COLOR_BGR2GRAY),actual['gray'])
            masks={o['id']:coco.decode(dict(size=saved['masks'][o['mask']]['size'],counts=saved['masks'][o['mask']]['counts'].encode('ascii'))).astype(bool) for o in row['native']}
            for branch in ARMS:
                assert len(pred['variants'][branch])==len(masks)==len({o['id'] for o in pred['variants'][branch]})
                assert {o['mask'] for o in pred['variants'][branch]}=={f'n:{n}' for n in masks}
            if f==event.get('q'):
                mapping={int(o['mask'][2:]):o['id'] for o in pred['variants'][arm]}
                assert mapping=={int(n):k for n,k in event['first_published_mapping'].items()}
            snapshots[f]=dict(rgb=rgb,depth=actual['depth_mm'].copy(),masks=masks,pred=pred)
            source_proofs.append(dict(frame=f,global_frame=row['global_frame'],sensor=actual['binding'],
                actual_mask_bindings={str(n):array_hash(mask) for n,mask in masks.items()},
                source_row_sha256=row_sha(row),assignment_row_sha256=row_sha(saved),prediction_row_sha256=row_sha(pred)))
    finally:sensor.close()
    panels=[]
    relevant=set(event['member_sources'])|set(map(int,event.get('post_roles',{})))|{event['group_source']}
    for branch in ARMS:
        columns=[]
        for phase,f in selected:
            header=np.full((60,640,3),24,'u1')
            lines=[f'{NAMES[branch]} | {phase}',f'local F{f} / global F{start+f-1 if f else "UNKNOWN"}',
                'WHITE=all actual SAM3 masks; YELLOW=event context; raw depth 0..3000 mm']
            for index,line in enumerate(lines):cv2.putText(header,line[:125],(5,16+index*18),cv2.FONT_HERSHEY_SIMPLEX,.36,(240,240,240),1,cv2.LINE_AA)
            if f is None:body=np.full((180,640,3),16,'u1');cv2.putText(body,'UNKNOWN: no invented reference/frame',(18,90),cv2.FONT_HERSHEY_SIMPLEX,.5,(200,200,200),1)
            else:
                shot=snapshots[f];rgb=shot['rgb'].copy();z=shot['depth'];lut=np.nan_to_num(np.clip(z/3000.*255,0,255)).astype('u1')
                depth=cv2.applyColorMap(lut,cv2.COLORMAP_TURBO);depth[~np.isfinite(z)|(z<=0)]=0
                mapping={int(o['mask'][2:]):o['id'] for o in shot['pred']['variants'][branch]}
                for n,mask in shot['masks'].items():
                    contours,_=cv2.findContours(mask.astype('u1'),cv2.RETR_LIST,cv2.CHAIN_APPROX_SIMPLE)
                    color=(0,255,255) if n in relevant else (255,255,255)
                    for image in (rgb,depth):cv2.drawContours(image,contours,-1,color,2 if n in relevant else 1)
                    yy,xx=np.nonzero(mask)
                    if len(xx):
                        center=(int(np.mean(xx)),int(np.mean(yy)))
                        for image in (rgb,depth):cv2.putText(image,f'n{n}->p{mapping[n]}',center,cv2.FONT_HERSHEY_SIMPLEX,.35,color,1,cv2.LINE_AA)
                body=np.hstack((cv2.resize(rgb,(320,180),interpolation=cv2.INTER_AREA),cv2.resize(depth,(320,180),interpolation=cv2.INTER_AREA)))
            columns.append(np.vstack((header,body)))
        panels.append(np.hstack(columns))
    canvas=np.vstack(panels);ok,encoded=cv2.imencode('.png',canvas);assert ok
    path=destination/f'{name}_{event["id"]}_{arm}.png'
    with path.open('xb') as output:output.write(encoded.tobytes())
    return dict(segment=name,selected_event_arm=arm,event_id=event['id'],selection='FIRST_AUTOMATIC_EPISODE_IN_SOURCE_THEN_FIXED_ARM_ORDER',
        phases=selected,image=artifact(path),source_bindings=source_proofs,all_four_published_branches=True,
        no_GT_raster_or_annotation_read=True,all_masks_residuals_preserved=True,unknown_reference_not_replaced=True)


def main():
    from verify_inputs import verify_all
    verify_all();metric=read(RUN/'METRICS.json');events={n:read(RUN/n/'public/EVENTS.json') for n in SEGMENTS}
    public_figures(metric,events)
    destination=HERE/'private/visuals';destination.mkdir(parents=True,exist_ok=False);inventory=[]
    for name in SEGMENTS:
        candidates=events[name]['DEPTH_OVERRIDE']
        chosen=[candidates[0]] if candidates else []
        chosen += [e for e in candidates if e.get('restore',{}).get('staged') or (name=='fishsa_development_8400' and e.get('q')==3902) or (name=='fishsa_validation_2888' and e.get('q') in (2188,2689))]
        unique={e['id']:e for e in chosen}
        for event in unique.values():
            value=private_case(name,event,'DEPTH_OVERRIDE',destination)
            value['selection']='FIRST_AUTOMATIC_EPISODE_OR_ALL_NEW_STAGES_OR_PRIOR_ENGINEERING_FAILURE_POSTSEAL_CASES'
            inventory.append(value)
    write_new(HERE/'PRIVATE_VISUALS_INVENTORY.json',dict(status='POSTSEAL_PRIVATE_ACTUAL_SOURCE_CONTACT_SHEETS',helper=artifact(__file__),
        all_seal=artifact(RUN/'ALL_PREDICTIONS_SEALED.json'),cases=inventory,private_pixels_not_for_git=True,
        exact_old_RGB_pins=artifact(ROOT/'experiments/ds33_rgbd_fixed_lag/RGB_INPUT_PINS.jsonl'),
        reproduction='After all predictions sealed and official scoring, provide exact private raw RGB/depth/masks and run this helper. No GT raster read.',new_model_http=0,cost_usd=0))
    print('Private actual source contact sheets and public numeric metrics/timeline complete',flush=True)
if __name__=='__main__':main()
