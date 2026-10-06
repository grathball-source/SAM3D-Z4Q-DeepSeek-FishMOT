"""Postseal private pixels only; never imported by prediction or scoring code.

Selection uses first chronological events and first changed publication, not
reference labels or scores. Replayed contours must match sealed array hashes.
"""
from common import *
import copy


def guard():
    # No sensor constructor, RLE decoding, RGB or depth access precedes this gate.
    paths = RUN / 'ALL_PREDICTIONS_SEALED.json', RUN / 'SCORE_PROVENANCE.json'
    assert all(p.is_file() for p in paths), 'All predictions and independent scoring must finish first'
    all_seal, provenance = (read(p) for p in paths)
    assert all_seal['status'] == 'ALL_PREDICTIONS_AND_ACCESS_SEALED'
    assert all_seal['frames'] == 20098 and tuple(all_seal['arms']) == ARMS
    assert set(all_seal['seals']) == set(all_seal['access_seals']) == set(SEGMENTS)
    assert provenance['reference_opened_after_all_seals'] and not provenance['GT_used_for_prediction']
    assert provenance['original_controls_exact'] and provenance['ignored_public_ids'] == 0
    for key in ('scorer', 'scoring_freeze', 'prediction_parity'): verify_item(provenance[key])
    assert read(provenance['scoring_freeze']['path'])['all_seal'] == artifact(paths[0])
    runtime = read(HERE / 'RUNTIME_FREEZE.json')
    for filename in ('common.py', 'CONFIG.json', 'sensor.py', 'flow.py', 'evidence.py'):
        path = HERE / filename
        assert sha(path) == runtime['code'][str(path.resolve())], 'Changed frozen reconstruction dependency'
    for name in SEGMENTS:
        verify_item(all_seal['seals'][name]); verify_item(all_seal['access_seals'][name])
        public = RUN / name / 'public'
        sealed = read(public / 'PREDICTIONS_SEALED.json')
        for filename in ('EVENTS.json', 'predictions.jsonl.gz', 'FRAME_INPUTS_BINDINGS.jsonl.gz'):
            assert sha(public / filename) == sealed['artifacts_sha256'][filename]
    return dict(all_seal=artifact(paths[0]), score_provenance=artifact(paths[1]),
        runtime=artifact(HERE / 'RUNTIME_FREEZE.json'), helper=artifact(__file__),
        postseal_only=True, frozen_science_unchanged=True)


def select_cases():
    cases, every = [], []
    for name in SEGMENTS:
        events = read(RUN / name / 'public/EVENTS.json')
        candidates = [(event['request_frame'], ARMS.index(arm), arm, event)
            for arm in ARMS[2:] for event in events[arm]]
        candidates.sort(key=lambda x:x[:2])
        if candidates:
            _, _, arm, event = candidates[0]
            cases.append(dict(segment=name, arm=arm, event=event, selection='FIRST_EVENT_IN_SOURCE'))
        every.extend(dict(segment=name, arm=arm, event=event) for _, _, arm, event in candidates)
    # Only independent changed windows; an overlap is attributed to its earlier window.
    changed = [c for c in every if c['event']['status'] == 'COMMIT_CHANGED_WINDOW'
        and c['event'].get('actual_changes') and c['event'].get('submitted_option') != 'KEEP']
    if changed:
        chosen = min(changed, key=lambda c:(list(SEGMENTS).index(c['segment']), c['event']['request_frame'], ARMS.index(c['arm'])))
        if not any(c['segment']==chosen['segment'] and c['arm']==chosen['arm'] and c['event']['id']==chosen['event']['id'] for c in cases):
            cases.append(dict(chosen, selection='FIRST_INDEPENDENT_CHANGED_EVENT_FIXED_SOURCE_ORDER'))
    assert len(cases) <= 9
    return cases


def selected_rows(path, wanted):
    result = {}; maximum = max(wanted)
    for row in rows(path):
        f = row['frame']
        if f in wanted: result[f] = row
        if f >= maximum: break
    assert set(result) == set(wanted), (str(path), sorted(set(wanted)-set(result)))
    return result


def decode_masks(assignment, coco):
    return {int(o['id']):coco.decode(dict(size=assignment['masks'][o['mask']]['size'],
        counts=assignment['masks'][o['mask']]['counts'].encode('ascii'))).astype(bool)
        for o in assignment['variants']['N0']}


def rebuild(case, sensor_type, motion_type, coco):
    event = case['event']; name = case['segment']; q = event['request_frame']
    end = event['evidence_max_frame']; assert q <= end <= q + CFG['lag_frames']
    samples = event.get('window_evidence', {}).get('samples', [])
    comparisons, anchors, anchor_depth = {}, {}, {}
    for sample in samples:
        assert q <= sample['frame'] <= end
        for c in sample['comparisons'].values():
            if 'predicted_mask_binding' not in c: continue
            f, k = sample['frame'], int(c['public'])
            assert c['frame'] == f and c['actual_current_observation']['time'] == sample['time']
            assert c['actual_reference'] == c['target_bank_anchor'], 'Action anchor must not replace the actual bank anchor'
            anchor = c['actual_reference']
            depth = dict(usable=c.get('anchor_depth_usable',False),
                quality=copy.deepcopy(c.get('anchor_depth_quality',{})),
                fact_binding=copy.deepcopy(c.get('anchor_depth_fact_binding')))
            if k in anchors:
                assert anchor == anchors[k] and depth == anchor_depth[k], 'Frozen reference changes inside a window'
            else:
                assert 1 <= anchor['frame'] < q and anchor['canonical_id'] == k
                anchors[k], anchor_depth[k] = copy.deepcopy(anchor), depth
            values = comparisons.setdefault((f,k), [])
            if values:
                for field in ('predicted_mask_binding', 'trusted_mask_binding', 'depth_support'):
                    assert c[field] == values[0][field], 'Same target must have one propagated hypothesis for all candidates'
            values.append(c)
    # No registered contour means no fabricated prediction. Still show the raw case.
    first = min((a['frame'] for a in anchors.values()), default=max(1, q-1))
    pre_label = 'PRE_ACTUAL_REFERENCE' if anchors else 'PRE_CONTEXT_NO_REGISTERED_REFERENCE'
    wanted = set(range(first, end+1)); phases = [(pre_label,first), ('Q_FIRST_PUBLICATION',q), ('CONFIRM_OR_STOP',end)]
    public = RUN / name / 'public'; base = input_dir(name)
    observations = selected_rows(base / 'observations.jsonl.gz', wanted)
    assignments = selected_rows(base / 'assignments.jsonl.gz', wanted)
    bindings = selected_rows(public / 'FRAME_INPUTS_BINDINGS.jsonl.gz', wanted)
    predictions = selected_rows(public / 'predictions.jsonl.gz', {f for _, f in phases})
    sensor = sensor_type(name); previous = None; tracks = {}; snapshots = {}; checks = []
    try:
        for f in sorted(wanted):
            source, assignment, bound = observations[f], assignments[f], bindings[f]
            stamp = (f, source['global_frame'], source['time'])
            assert source['global_frame'] == SEGMENTS[name][0] + f - 1
            assert (assignment['frame'],assignment['global_frame_id'],assignment['time']) == stamp
            assert (bound['frame'],bound['global_frame'],bound['time']) == stamp
            assert bound['source_row_sha256'] == row_sha(source) and bound['assignment_row_sha256'] == row_sha(assignment)
            assert source['native'] == assignment['variants']['N0']
            actual = sensor.read(source['global_frame'], source['time'])
            assert actual['binding'] == bindings[f]['sensor'], 'Postseal sensor differs from formal actual input'
            masks = decode_masks(assignment, coco)
            assert {str(n):array_hash(m) for n,m in masks.items()} == bindings[f]['current_mask_bindings']
            assert set(masks) == {o['id'] for o in source['observations']}
            pair = motion_type(previous, actual, CFG['flow']) if previous is not None else None
            for k, anchor in anchors.items():
                if f == anchor['frame']:
                    assert anchor['native_id'] in masks and anchor['mask'] == f"n:{anchor['native_id']}"
                    extract = bound['DS18_extracts'].get(str(anchor['native_id'])) or {}
                    assert anchor_depth[k]['quality'] == extract.get('quality', {})
                    assert anchor_depth[k]['fact_binding'] == depth_fact_binding(extract)
                    assert anchor_depth[k]['usable'] == endpoint_depth_usable(extract, source, anchor['native_id'])
                    tracks[k] = dict(mask=masks[anchor['native_id']].copy(), trusted=masks[anchor['native_id']].copy(),
                        support=np.zeros_like(actual['gray'],bool), support_summary=dict(status='UNKNOWN',reasons=['AT_REFERENCE_NO_PAIR']))
                elif f > anchor['frame']:
                    assert pair is not None and k in tracks
                    track = tracks[k]; old = track['mask']
                    track['support'], track['support_summary'] = pair.point_support(old)
                    track['mask'] = pair.warp_forward(old)
                    track['trusted'] = pair.warp_forward(track['trusted'],quality=True)
                for expected in comparisons.get((f,k), []):
                    assert array_hash(tracks[k]['mask']) == expected['predicted_mask_binding'], 'Rebuilt prediction mismatches sealed contour'
                    assert array_hash(tracks[k]['trusted']) == expected['trusted_mask_binding'], 'Rebuilt trusted support mismatches sealed contour'
                    assert tracks[k]['support_summary'] == expected['depth_support'], 'Rebuilt conditional point support differs from sealed evidence'
                    n = expected['native']; observed = next(o for o in source['observations'] if o['id'] == n)
                    assert expected['current_mask_binding'] == array_hash(masks[n])
                    assert expected['actual_current_observation']['mask'] == observed['mask']
                    assert expected['actual_current_observation']['neighbors'] == observed.get('neighbors', [])
                    extract = bound['DS18_extracts'].get(str(n)) or {}
                    assert expected['source_depth_quality'] == extract.get('quality', {})
                    assert expected['current_depth_fact_binding'] == depth_fact_binding(extract)
                    checks.append(dict(frame=f,native=n,public=k,predicted_mask_binding=expected['predicted_mask_binding'],
                        trusted_mask_binding=expected['trusted_mask_binding'],conditional_support_binding=expected['depth_support']['support_binding'],match=True))
            if f in {frame for _,frame in phases}:
                pred = predictions[f]
                assert (pred['frame'],pred['global_frame'],pred['time']) == stamp
                assert tuple(pred['variants']) == ARMS
                for arm in ARMS:
                    output = pred['variants'][arm]
                    assert len(output) == len(masks) == len({o['id'] for o in output})
                    assert {o['mask'] for o in output} == {f'n:{n}' for n in masks}
                assert pred['variants']['SAM3_NATIVE'] == source['native']
                if f == q:
                    actual_map = {int(o['mask'][2:]):int(o['id']) for o in pred['variants'][case['arm']]}
                    assert actual_map == {int(n):int(k) for n,k in event['actual_first_mapping'].items()}
                    assert actual_map == {int(n):int(k) for n,k in event['first_published_mapping'].items()}
                # Original RGB is read only for private diagnostics, from the exact pinned path.
                rgb = cv2.imread(actual['binding']['rgb']['path'],cv2.IMREAD_COLOR)
                assert rgb is not None
                if rgb.shape[:2] != (360,640):rgb=cv2.resize(rgb,(640,360),interpolation=cv2.INTER_AREA)
                assert np.array_equal(cv2.cvtColor(rgb,cv2.COLOR_BGR2GRAY),actual['gray'])
                snapshots[f] = dict(rgb=rgb,depth=actual['depth_mm'].copy(),masks=masks,
                    tracks=copy.deepcopy(tracks),prediction=pred,
                    sensor_binding=actual['binding'],extracts=bindings[f]['DS18_extracts'])
            previous = actual
    finally:sensor.close()
    if comparisons:assert checks, 'Bound contour case must have an exact match before drawing'
    return phases, snapshots, dict(status='EXACT_SEALED_CONTOUR_REPLAY_MATCH' if checks else 'UNKNOWN_NO_REGISTERED_BOUND_CONTOUR',
        comparison_count=len(checks),matches=checks,anchors=anchors,anchor_depth=anchor_depth,maximum_reconstruction_frame=end,
        selection_did_not_use_reference=True,physical_identity='UNKNOWN',depth_correspondences_are_conditional=True)


def contour(image, mask, color, dashed=False):
    found,_=cv2.findContours(mask.astype('u1'),cv2.RETR_LIST,cv2.CHAIN_APPROX_SIMPLE)
    if not dashed:cv2.drawContours(image,found,-1,color,1);return
    for shape in found:
        points=shape.reshape(-1,2)
        for i in range(len(points)):
            if i%4<2:cv2.line(image,tuple(points[i]),tuple(points[(i+1)%len(points)]),color,1)


def text(image, lines, height=112):
    header=np.full((height,image.shape[1],3),24,'u1')
    for i,line in enumerate(lines):cv2.putText(header,str(line)[:170],(8,18+i*18),cv2.FONT_HERSHEY_SIMPLEX,.43,(240,240,240),1,cv2.LINE_AA)
    return np.vstack((header,image))


def render(case, phases, snapshots, proof):
    event=case['event']; chosen=case['arm']; panels=[]
    for arm in ARMS:
        columns=[]
        for phase,f in phases:
            shot=snapshots[f]; rgb=shot['rgb'].copy(); z=shot['depth']
            # Shared fixed display scale, never a foreground extraction or a prediction.
            lut=np.clip(z/3000.*255,0,255).astype('u1');depth=cv2.applyColorMap(lut,cv2.COLORMAP_TURBO);depth[~np.isfinite(z)|(z<=0)]=0
            mapping={int(o['mask'][2:]):int(o['id']) for o in shot['prediction']['variants'][arm]}
            for n,mask in shot['masks'].items():
                for image in (rgb,depth):contour(image,mask,(255,255,255))
                yy,xx=np.nonzero(mask)
                if len(xx):
                    center=(int(np.mean(xx)),int(np.mean(yy)))
                    for image in (rgb,depth):cv2.putText(image,f'n{n}->p{mapping[n]}',center,cv2.FONT_HERSHEY_SIMPLEX,.43,(255,255,255),1,cv2.LINE_AA)
            if arm==chosen:
                for k,track in shot['tracks'].items():
                    for image in (rgb,depth):
                        contour(image,track['mask'],(0,160,255),dashed=True)
                        contour(image,track['trusted'],(255,0,255))
                    color = (80,255,80) if track['support_summary']['status'] == 'AVAILABLE_CONDITIONAL_3D_SUPPORT' else (128,128,128)
                    depth[track['support']] = color
            extracts=shot['extracts']
            relevant=set(event['request'].get('sources', []))|{a['native_id'] for a in proof['anchors'].values()}
            quality_line='; '.join(f"n{n}:current DS18={bool(v.get('usable'))}/{v.get('reason')}"
                for n,v in extracts.items() if int(n) in relevant) or 'Relevant current DS18 observation UNKNOWN/missing'
            support_line='; '.join(f"p{k}:conditional support {t['support_summary']['status']} n={int(t['support'].sum())}"
                for k,t in shot['tracks'].items()) if arm==chosen else 'No propagated overlay used by this control panel'
            global_frame=shot['prediction']['global_frame']
            heading=[f'{arm} | {phase} | global F{global_frame}, local F{f}',
                'WHITE=actual raw contours and first-published n->p mapping; raw depth LUT 0..3000 mm',
                f'ORANGE dashed=hypothesis; MAGENTA=RGB-trusted; GREEN=conditional XYZ; GRAY=insufficient/UNKNOWN (event {chosen} only)',
                quality_line, support_line,
                f"Event status={event['status']}; selected={event.get('submitted_option','KEEP')}; depth weight={event.get('assessment',{}).get('depth_common_component_weight','UNKNOWN')}" ]
            columns.append(text(np.hstack((rgb,depth)),heading,130))
        panels.append(np.hstack(columns))
    canvas=np.vstack(panels)
    source_refs='; '.join(f"p{k}: actual pre n{a['native_id']}@local F{a['frame']}" for k,a in proof['anchors'].items()) or 'Actual registered pre contour UNKNOWN; no invented prediction overlay'
    pre_quality='; '.join(f"p{k}:actual pre DS18 usable={v['usable']}, whole mixed={v['quality'].get('whole_multilayer','UNKNOWN')}" for k,v in proof['anchor_depth'].items()) or 'Pre depth quality UNKNOWN'
    return text(canvas,[f"PRIVATE / NO GT PIXELS OR LABELS / {case['segment']} / {event['id']}",
        source_refs,pre_quality,f"Reconstruction={proof['status']}; exact matching sealed mask samples={proof['comparison_count']}",
        'All propagated contours are hypotheses. 3D support does not certify foreground, identity, physical accuracy or occlusion.'],106)


def main():
    provenance=guard()
    global cv2,np,endpoint_depth_usable,depth_fact_binding
    import cv2
    import numpy as np
    from pycocotools import mask as coco
    from sensor import Sensor
    from flow import PairMotion
    from evidence import endpoint_depth_usable, depth_fact_binding
    cv2.setNumThreads(1)
    private_root=HERE/'private'; destination=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else private_root/'visuals'
    assert destination.resolve().is_relative_to(private_root.resolve()), 'Pixel output must stay in this experiment private directory'
    destination.mkdir(parents=True,exist_ok=False)
    inventory=[]
    for index,case in enumerate(select_cases(),1):
        phases,snapshots,proof=rebuild(case,Sensor,PairMotion,coco)
        image=render(case,phases,snapshots,proof);ok,encoded=cv2.imencode('.png',image);assert ok
        path=destination/f"{index:02d}_{case['segment']}_Q{case['event']['request_frame']}_{case['arm']}.png"
        with path.open('xb') as output:output.write(encoded.tobytes())
        inventory.append(dict(segment=case['segment'],arm=case['arm'],event_id=case['event']['id'],
            selection=case['selection'],request_frame=case['event']['request_frame'],phases=phases,
            image=artifact(path),reconstruction=proof,private_pixels=True,GT_used=False,
            actual_first_mapping=case['event'].get('actual_first_mapping'),
            original_trial_mapping=case['event']['request']['original_mapping']))
        print('PRIVATE VISUAL',path.name,proof['status'],proof['comparison_count'],flush=True)
    write_new(destination/'CASE_INVENTORY.json',dict(status='POSTSEAL_PRIVATE_ACTUAL_RGB_DEPTH_CONTOUR_DIAGNOSTICS',
        provenance=provenance,cases=inventory,selection='Each source first event; one additional first independent changed event; fixed source/arm order; no GT/metric selection',
        no_GT_raster_or_label_read=True,all_pixels_private=True,new_model_http=0,cost_usd=0))
    write_new(RUN/'PRIVATE_VISUALS_INVENTORY.json',dict(private_inventory=artifact(destination/'CASE_INVENTORY.json'),
        helper=provenance['helper'],images=[c['image'] for c in inventory],private_pixels_not_published=True,
        exact_contour_reconstruction_matches=sum(c['reconstruction']['comparison_count'] for c in inventory),
        cases=len(inventory),no_GT_raster_or_label_read=True,new_model_http=0,cost_usd=0))


if __name__=='__main__':main()
