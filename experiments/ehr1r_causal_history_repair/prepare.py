"""Build new causal event packets from predicted observations, without GT."""
from __future__ import annotations
import argparse
import gzip
import hashlib
import json
import math
import shutil
from pathlib import Path

import cv2

from contract import assert_packet_segments, reason, source_item, version_signature, dumps
from preflight import AO1, DEV_OBS, VAL, read, stream, put

M2 = Path('/home/xiongxiong/m2t_motion_first_20260924/full_run')
DEV_DEPTH = Path('/home/xiongxiong/dmot-experiments/sam3_depth_birth_inherit_20260917/features_r2/features_development.jsonl.gz')
DATA = Path('/home/data2/xiongxiong/d-mot/data/AlignedDataset_v1/rgb_original')
ASSIGN = {
 'development': Path('/home/data2/xiongxiong/d-mot/experiments/sam3_occlusion_identity_20260915/identity_cpu10_20260915/run_8400/assignments.jsonl.gz'),
 'validation': Path('/home/data2/xiongxiong/d-mot/experiments/sam3_i3_validation_cpu16_20260915/run_validation_2888/assignments.jsonl.gz')}
ARMS = ('E', 'H-2D', 'H-D', 'H-D-REPEAT', 'H-D-PERMUTE')


def digest(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1048576), b''):
            h.update(block)
    return h.hexdigest()


def measure(rows, depth_rows, masks, frame, native, role):
    src = source_item(rows, frame, native)
    if src is None:
        return None
    b = src['box']
    o = dict(fact_id=f'{role}-F{frame}', source_fact_ids=[f'SRC-F{frame}-N{native}'],
             source_frame=frame, source_time_seconds=rows[frame]['time'],
             source_mask_key=f'frame_local:n:{native}', source_mask_rle_sha256=masks.get((frame,native)), source_stream_frame=frame,
             coordinate_system='full_640x360_mask_px', unit='px',
             bbox_center_px=[round((b[0]+b[2])/2, 3), round((b[1]+b[3])/2, 3)],
             bbox_px=b, area_px=src['area'], neighbor_count=len(src.get('neighbors', [])),
             quality={'presence': src.get('presence'), 'risk': reason(src) or 'CLEAN'})
    drow = depth_rows.get(frame)
    dsrc = source_item(depth_rows, frame, native)
    if drow is None or dsrc is None:
        o['depth'] = {'epistemic_type': 'UNKNOWN', 'reason': 'NO_ALIGNED_PROFILE'}
    else:
        o['depth'] = dict(fact_id=f'D-{role}-F{frame}', source_fact_ids=[o['fact_id']],
                          epistemic_type='MEASUREMENT', source='raw_depth_profile_stream',
                          source_frame=frame, source_time_seconds=drow['time'],
                          raw_array_sha256=drow.get('raw_array_sha256'), sensor_available=drow.get('sensor_available'),
                          synchronized=drow['time']==rows[frame]['time'] and drow['frame']==frame,
                          unit='pipeline_mm_unverified_water_surface',
                          core={k:dsrc.get('core',{}).get(k) for k in ('median','mad','n','valid_fraction')},
                          whole={k:dsrc.get('whole',{}).get(k) for k in ('median','mad','n','valid_fraction')},
                          overlap_pixels=dsrc.get('overlap_pixels'), contact_risk=bool(src.get('neighbors')))
    return o


def clean_run(rows, native, start, stop, end_at):
    """Last contiguous clean island ending by stop, never joins across one bad frame."""
    runs, current = [], []
    prior_signature=None
    for f in range(start, stop+1):
        src=source_item(rows,f,native)
        valid = reason(src) is None
        signature=version_signature(rows[f],native,src) if valid else None
        if valid and current and (rows[f]['time']-rows[f-1]['time']>.2 or
                                  rows[f]['time']<=rows[f-1]['time'] or signature!=prior_signature):
            runs.append(current);current=[]
        if valid:
            current.append(f)
        elif current:
            runs.append(current)
            current = []
        prior_signature=signature
    if current:
        runs.append(current)
    return next((r for r in reversed(runs) if r[-1] <= end_at), [])


def fit(role, values):
    if len(values) < 3 or len({x['source_time_seconds'] for x in values}) < 3:
        return dict(epistemic_type='UNKNOWN', reason='FEWER_THAN_THREE_DISTINCT_CLEAN_TIMES', count=len(values))
    tt = [x['source_time_seconds'] for x in values]
    if any(b-a <= 0 or b-a > .2 for a,b in zip(tt,tt[1:])):
        return dict(epistemic_type='UNKNOWN', reason='NONCONTIGUOUS_TIME')
    t0=sum(tt)/len(tt);den=sum((t-t0)**2 for t in tt)
    xy=[x['bbox_center_px'] for x in values]
    avg=[sum(x[k] for x in xy)/len(xy) for k in (0,1)]
    vv=[sum((t-t0)*(x[k]-avg[k]) for t,x in zip(tt,xy))/den for k in (0,1)]
    err=math.sqrt(sum(sum((x[k]-avg[k]-vv[k]*(t-t0))**2 for k in (0,1)) for t,x in zip(tt,xy))/len(xy))
    speed=math.hypot(*vv)
    return dict(fact_id=f'VELOCITY-{role}', source_fact_ids=[x['fact_id'] for x in values],
                epistemic_type='ESTIMATE', method='OLS_bbox_center', fit_interval_seconds=[tt[0],tt[-1]],
                velocity_px_per_s=[round(v,3) for v in vv], speed_px_per_s=round(speed,3),
                direction_radians=None if speed<2 else round(math.atan2(vv[1],vv[0]),4),
                direction_reason='LOW_SPEED' if speed<2 else None, residual_rms_px=round(err,3), samples=len(values))


def segment(role, frames, native, rows, depth_rows, masks):
    if not frames:
        return dict(role=role, status='UNKNOWN', reason='NO_CLEAN_SOURCE_FRAGMENT', observations=[],
                    velocity=dict(epistemic_type='UNKNOWN', reason='NO_CLEAN_SOURCE_FRAGMENT'))
    obs=[measure(rows,depth_rows,masks,f,native,role) for f in frames]
    fit_values=[x for x in obs if x['source_time_seconds'] >= obs[-1]['source_time_seconds']-.5]
    return dict(role=role, status='CLEAN_SOURCE_FRAGMENT', fragment_id=f'{role}-F{frames[0]}-{frames[-1]}',
                anchor_frame=frames[-1] if role in 'AB' else frames[0],
                observations=obs, velocity=fit(role,fit_values),
                last_position_fact_id=obs[-1]['fact_id'], first_position_fact_id=obs[0]['fact_id'],
                identity_scope='local_fragment_only')


def event_rows(rows, depth_rows, masks, lo, q, named):
    out=[]
    for f in range(lo,q+1):
        row=rows[f]
        obs=[]
        for source in row['observations']:
            n=source['id'];b=source['box'];key=(f,n)
            if key in named:
                continue
            d=source_item(depth_rows,f,n)
            core=(d or {}).get('core') or {}
            obs.append(dict(fact_id=f'EV-F{f}-O{len(obs)+1}', source_fact_ids=[f'SRC-F{f}-N{n}'],
                            local_token=f'F{f}:O{len(obs)+1}', source_mask_rle_sha256=masks.get((f,n)),
                            center_px=[round((b[0]+b[2])/2,1),round((b[1]+b[3])/2,1)],
                            area_px=source['area'], risk=reason(source) or 'ANONYMOUS_CLEAN_ISLAND',
                            neighbor_count=len(source.get('neighbors',[])),
                            depth_median_pipeline_mm=core.get('median'), depth_valid_fraction=core.get('valid_fraction'),
                            depth_sensor_available=None if depth_rows.get(f) is None else depth_rows[f].get('sensor_available'),
                            depth_synchronized=bool(depth_rows.get(f) and depth_rows[f]['frame']==f and depth_rows[f]['time']==row['time']),
                            depth_core_n=core.get('n'),depth_core_mad=core.get('mad'),
                            depth_whole_n=(d or {}).get('whole',{}).get('n'),
                            depth_whole_mad=(d or {}).get('whole',{}).get('mad'),
                            depth_overlap_pixels=None if d is None else d.get('overlap_pixels'),
                            depth_quality='UNKNOWN' if d is None else 'CONTACT_OR_MIXED_RISK' if reason(source) or (d.get('overlap_pixels') or 0)>0 else 'OBSERVED_PROFILE'))
        out.append(dict(fact_id=f'FRAME-F{f}', source_fact_ids=[x['fact_id'] for x in obs],
                        frame=f, time_seconds=row['time'], anonymous_observations=obs))
    return out


def intervals(rows, native, start, stop, label):
    runs=[];prior=None
    for f in range(start,stop+1):
        state=reason(source_item(rows,f,native)) or 'CLEAN'
        if state!=prior:
            runs.append(dict(status=state, start_frame=f, end_frame=f));prior=state
        else:runs[-1]['end_frame']=f
    for i,r in enumerate(runs):
        r['fact_id']=f'INTERVAL-{label}-{i+1}'
        r['source_fact_ids']=[f'SRC-F{f}-N{native}' for f in range(r['start_frame'],r['end_frame']+1)]
        r['start_time_seconds']=rows[r['start_frame']]['time'];r['end_time_seconds']=rows[r['end_frame']]['time']
    return runs


def render_endpoint(case, frame, roles, rows, roi, out):
    source=DATA/f'{rows[frame]["global_frame"]-1:06d}.jpg'
    raw=cv2.imread(str(source))
    assert raw is not None and raw.shape[:2]==(1080,1920), source
    x0,y0,x1,y1=roi
    crop=raw[3*y0:3*y1,3*x0:3*x1]
    image=cv2.resize(crop,(x1-x0,y1-y0),interpolation=cv2.INTER_AREA)
    tokens=[]
    for role,native in roles.items():
        obj=source_item(rows,frame,native)
        assert obj is not None
        box=obj['box'];p=(round(box[0]-x0),round(box[1]-y0));z=(round(box[2]-x0),round(box[3]-y0))
        cv2.rectangle(image,p,z,(0,255,255),1)
        cv2.putText(image,role,(p[0],max(12,p[1]-3)),cv2.FONT_HERSHEY_SIMPLEX,.42,(0,255,255),1)
        tokens.append(dict(role=role,token=f'F{frame}:{role}',source_mask_key=f'frame_local:n:{native}',
                           bbox_full_px=box,bbox_image_px=[p[0],p[1],z[0],z[1]]))
    image_id=f'{case}-F{frame}'
    temp=out/'sender/media'/f'{image_id}.png'
    assert cv2.imwrite(str(temp),image)
    h=digest(temp);target=out/'sender/media'/f'{h}.png';temp.rename(target)
    return dict(image_id=image_id,frame=frame,time_seconds=rows[frame]['time'],width=x1-x0,height=y1-y0,
                roi_full_mask_xyxy=roi,full_to_image='x_image=x_full-roi_x0;y_image=y_full-roi_y0',
                pixel_source='original_rgb_crop_resized_3_to_1_with_endpoint_boxes',
                role_tokens=tokens,media_file=target.name,sha256=h,bytes=target.stat().st_size,
                source_rgb_sha256=digest(source))


def build(case,m2,ledger,rows,depth_rows,masks,card,out):
    name=case['case_alias'];trigger=case['trigger_frame'];q=case['query_frame']
    old=case['V1']['roles'];native={r:int(max((x for x in old if x['role']==r),key=lambda x:x['frame'])['native_mask_key'].split(':')[1]) for r in 'ABXY'}
    old_anchor={r:max(x['frame'] for x in old if x['role']==r) for r in 'AB'}
    old_post_start=min(x['frame'] for x in old if x['role'] in 'XY')
    pre={};post={};relation={}
    for role in 'AB':
        anchor=old_anchor[role]
        clean=clean_run(rows,native[role],min(rows),trigger-1,trigger-1)
        # A later clean island is a new EHR-1R role; old role equivalence may be unknown.
        frames=clean[-31:]
        pre[role]=segment(role,frames,native[role],rows,depth_rows,masks)
        same=anchor in frames
        relation[role]=dict(old_anchor_frame=anchor,new_anchor_frame=frames[-1] if frames else None,
                            semantic_relation='SAME_CLEAN_FRAGMENT' if same else 'ORIGINAL_REFERENCE_UNRESOLVED',
                            source_basis='predicted_mask_clean_continuity_only_no_GT')
    for role in 'XY':
        clean=clean_run(rows,native[role],old_post_start,q,q)
        frames=[f for f in clean if f>=q-14]
        post[role]=segment(role,frames,native[role],rows,depth_rows,masks)
    assert_packet_segments(dict(request_id='EHR1R-'+name,PRE_HISTORY=pre,POST_HISTORY_TO_Q=post),rows,native)
    named={(x['source_frame'],native[r]) for part,roles in ((pre,'AB'),(post,'XY')) for r in roles for x in part[r]['observations']}
    first=min(min(s['observations'][0]['source_frame'] for s in pre.values() if s['observations']),trigger-30)
    timeline=event_rows(rows,depth_rows,masks,first,q,named)
    availability={r:intervals(rows,native[r],pre[r]['anchor_frame'],q,r) for r in 'AB'}
    reappearance={r:intervals(rows,native[r],trigger+1,q,r) for r in 'XY'}
    loss={}
    for r in 'AB':
        seq=availability[r]
        bad=next((s for s in seq if s['status']!='CLEAN'),None)
        if bad:
            last=bad['start_frame']-1
            loss[r]=dict(fact_id=f'LOSS-{r}',source_fact_ids=[f'SRC-F{last}-N{native[r]}',f'SRC-F{bad["start_frame"]}-N{native[r]}'],
                         last_usable_frame=last,first_unusable_frame=bad['start_frame'],reason=bad['status'],
                         interpretation='predicted_observation_usable_interval_not_physical_occlusion_time')
        else:loss[r]=dict(status='UNKNOWN',reason='NO_UNUSABLE_OBSERVATION_THROUGH_Q')
    return_intervals={}
    for r in 'XY':
        clean=next((s for s in reappearance[r] if s['status']=='CLEAN'),None)
        if clean:
            return_intervals[r]=dict(fact_id=f'RETURN-{r}',source_fact_ids=[f'SRC-F{clean["start_frame"]}-N{native[r]}'],
                                     first_clean_frame=clean['start_frame'],
                                     interpretation='handle_clean_availability_not_certified_identity_reappearance')
        else:return_intervals[r]=dict(status='UNKNOWN',reason='NO_CLEAN_OBSERVATION')
    first_loss='UNKNOWN'
    if all(loss[r].get('first_unusable_frame') is not None for r in 'AB'):
        if loss['A']['first_unusable_frame']<=loss['B']['last_usable_frame']:
            first_loss='A'
        elif loss['B']['first_unusable_frame']<=loss['A']['last_usable_frame']:
            first_loss='B'
    pair_clean=[]
    for f in range(trigger+1,q+1):
        if all(reason(source_item(rows,f,native[r])) is None for r in 'XY'):
            pair_clean.append(f)
    pair_streak=next(([f,f+2] for f in pair_clean if f+1 in pair_clean and f+2 in pair_clean),None)
    pair_fact=(dict(fact_id='PAIR-CLEAN-STREAK',source_fact_ids=[f'SRC-F{f}-N{native[r]}' for f in range(pair_streak[0],pair_streak[1]+1) for r in 'XY'],
                    frames=pair_streak,interpretation='two_handles_jointly_clean_only') if pair_streak else {'status':'UNKNOWN'})
    relative={'status':'UNKNOWN','reason':'UNALIGNED_OR_MISSING_VELOCITY'}
    if all(pre[r]['velocity'].get('epistemic_type')=='ESTIMATE' for r in 'AB'):
        ta=max(pre[r]['observations'][-1]['source_time_seconds'] for r in 'AB')
        projected=[]
        for r in 'AB':
            o=pre[r]['observations'][-1];v=pre[r]['velocity']['velocity_px_per_s'];dt=ta-o['source_time_seconds']
            projected.append([o['bbox_center_px'][k]+v[k]*dt for k in (0,1)])
        relative=dict(fact_id='RELATIVE-PRE',source_fact_ids=[pre[r]['observations'][-1]['fact_id'] for r in 'AB']+
                      [pre[r]['velocity']['fact_id'] for r in 'AB'],status='ESTIMATE',aligned_time_seconds=ta,
                      relative_position_B_minus_A_px=[round(projected[1][k]-projected[0][k],3) for k in (0,1)],
                      relative_velocity_B_minus_A_px_per_s=[round(pre['B']['velocity']['velocity_px_per_s'][k]-pre['A']['velocity']['velocity_px_per_s'][k],3) for k in (0,1)],
                      method='constant_velocity_projection_within_short_clean_fragments',
                      max_alignment_gap_seconds=max(ta-pre[r]['observations'][-1]['source_time_seconds'] for r in 'AB'))
    post_x,post_y=(post[r]['observations'][-1] for r in 'XY')
    post_relative=dict(fact_id='RELATIVE-POST-Q',source_fact_ids=[post_x['fact_id'],post_y['fact_id']],
                       status='OBSERVED_POSITION',time_seconds=rows[q]['time'],
                       relative_position_Y_minus_X_px=[round(post_y['bbox_center_px'][k]-post_x['bbox_center_px'][k],3) for k in (0,1)],
                       relative_velocity_Y_minus_X_px_per_s='UNKNOWN')
    if all(post[r]['velocity'].get('epistemic_type')=='ESTIMATE' for r in 'XY'):
        post_relative['source_fact_ids'] += [post[r]['velocity']['fact_id'] for r in 'XY']
        post_relative['relative_velocity_Y_minus_X_px_per_s']=[round(post['Y']['velocity']['velocity_px_per_s'][k]-post['X']['velocity']['velocity_px_per_s'][k],3) for k in (0,1)]
    candidates=[dict(id='H1' if c['choice']=='C1' else 'H2',mapping=c['mapping'],epistemic_type='HYPOTHESIS') for c in card['candidate_hypotheses']]
    assert {x['id'] for x in candidates}=={'H1','H2'}
    endpoints=[]
    by_frame={}
    for r in 'AB':by_frame.setdefault(pre[r]['anchor_frame'],{})[r]=native[r]
    for r in 'XY':by_frame.setdefault(q,{})[r]=native[r]
    for f,roles in sorted(by_frame.items()):endpoints.append(render_endpoint(name,f,roles,rows,m2['roi_mask_xyxy'],out))
    # Eight predeclared image samples; all unsent frame facts remain in the packet.
    middle=[(im,meta) for im,meta in zip(m2['g_images'],ledger,strict=True) if trigger<=meta['frame']<old_post_start]
    selected=[middle[round(i*(len(middle)-1)/7)] for i in range(8)] if middle else []
    images=endpoints[:]
    for im,meta in selected:
        src=M2/'sender/media'/im['media_file'];dst=out/'sender/media'/im['media_file']
        if not dst.exists():shutil.copyfile(src,dst)
        assert digest(dst)==im['sha256']
        images.append(dict(image_id=im['image_id'],frame=meta['frame'],time_seconds=meta['source_time'],
                           width=im['width'],height=im['height'],roi_full_mask_xyxy=m2['roi_mask_xyxy'],
                           full_to_image='x_image=x_full-roi_x0;y_image=y_full-roi_y0',
                           pixel_source='frozen_M2_original_rgb_mask_token_image',
                           role_tokens=[],anonymous_tokens=[dict(token=x['token'],bbox_norm=x['bbox_norm']) for x in meta['observations']],
                           media_file=im['media_file'],sha256=im['sha256'],bytes=im['bytes']))
    images.sort(key=lambda x:(x['frame'],x['image_id']))
    trigger_a=source_item(rows,trigger,native['A']);trigger_b=source_item(rows,trigger,native['B'])
    contact=bool(trigger_a and trigger_b and (native['B'] in trigger_a.get('neighbors',[]) or native['A'] in trigger_b.get('neighbors',[])))
    packet=dict(request_id='EHR1R-'+name,q_frame=q,q_time_seconds=rows[q]['time'],
                coordinate_system='full_640x360_mask_px;top_left;y_down',
                role_contract='A/B are new pre-risk source fragments, X/Y are q-local fragments; native handles across risk are anonymous evidence, never identity proof.',
                old_to_new_reference=relation,trigger=dict(frame=trigger,source='fixed_AO1_prediction_window',
                   pair_contact_predicted=contact,scope='PREDICTION_DRIVEN_CONTACT_PROXY' if contact else 'OFFLINE_DIAGNOSTIC_CONTROL'),
                PRE_HISTORY=pre,POST_HISTORY_TO_Q=post,INTERACTION_OBSERVATIONS=timeline,
                availability_intervals=availability,reappearance_intervals=reappearance,
                per_object_loss=loss,per_handle_clean_return=return_intervals,
                first_unusable_observation=first_loss,first_physical_entry='UNKNOWN',
                first_identity_reappearance='UNKNOWN',joint_clean_pair_streak=pair_fact,
                entry_side={r:{'status':'UNKNOWN','reason':'NO_OBSERVED_ROI_BOUNDARY_CROSSING',
                               'last_center_px':pre[r]['observations'][-1]['bbox_center_px']} for r in 'AB'},
                relative_motion=dict(pre=relative,post=post_relative),
                hypotheses=candidates,IMAGE_INDEX=images,
                unknowns=['identity across contact/loss','uncalibrated water-surface reference','original role equivalence where unresolved'])
    return packet,images


def condition(base,arm):
    p=json.loads(dumps(base))
    if arm=='E':
        p['INTERACTION_OBSERVATIONS']=[]
        for k in ('trigger','old_to_new_reference','availability_intervals','reappearance_intervals','per_object_loss','per_handle_clean_return',
                  'first_unusable_observation','first_physical_entry','first_identity_reappearance','joint_clean_pair_streak',
                  'entry_side','relative_motion'):
            p.pop(k,None)
        for part in ('PRE_HISTORY','POST_HISTORY_TO_Q'):
            for s in p[part].values():
                s['observations']=s['observations'][-1:]
                s.pop('velocity',None)
        p['IMAGE_INDEX']=[x for x in p['IMAGE_INDEX'] if x.get('role_tokens')]
    if arm in ('E','H-2D'):
        for part in ('PRE_HISTORY','POST_HISTORY_TO_Q'):
            for s in p[part].values():
                for o in s['observations']:o.pop('depth',None)
        for row in p['INTERACTION_OBSERVATIONS']:
            for o in row['anonymous_observations']:
                for key in list(o):
                    if key.startswith('depth_'):o.pop(key)
    else:
        for part in ('PRE_HISTORY','POST_HISTORY_TO_Q'):
            for s in p[part].values():
                for o in s['observations']:
                    if 'depth' in o:o['depth'].pop('raw_array_sha256',None)
    if arm!='E':
        # Compact column encoding of every anonymous observation. The complete
        # source-backed records and mask hashes stay in EPISODE_FACTS.json.
        columns=['fact_id','frame','time_seconds','local_token','center_x_px','center_y_px',
                 'area_px','risk','neighbor_count']
        depth_columns=['depth_median_pipeline_mm','depth_valid_fraction','depth_sensor_available',
                       'depth_synchronized','depth_core_n','depth_core_mad','depth_whole_n',
                       'depth_whole_mad','depth_overlap_pixels','depth_quality']
        if arm!='H-2D':columns+=depth_columns
        table=[]
        for frame in p.pop('INTERACTION_OBSERVATIONS'):
            for o in frame['anonymous_observations']:
                row=[o['fact_id'],frame['frame'],frame['time_seconds'],o['local_token'],
                     *o['center_px'],o['area_px'],o['risk'],o['neighbor_count']]
                if arm!='H-2D':row += [o[key] for key in depth_columns]
                table.append(row)
        p['INTERACTION_TABLE']=dict(columns=columns,rows=table,scope='every_non_identity_observation_through_q',
             full_provenance='sealed_EPISODE_FACTS_and_source_manifest')
    if arm=='H-D-PERMUTE':
        for h in p['hypotheses']:h['id']='H2' if h['id']=='H1' else 'H1'
        p['hypotheses'].reverse()
    p['condition']='H-D' if arm in ('H-D-REPEAT','H-D-PERMUTE') else arm
    return p


def main(out):
    assert (out/'public/OLD_PACKET_REJECTION.json').is_file(), 'old real-packet rejection is mandatory'
    assert read(out/'public/OLD_PACKET_REJECTION.json')['status']=='OLD_REAL_PACKETS_REJECTED'
    ao=read(AO1/'public/SOURCE_MANIFEST.json')['cases']
    m2={x['case_alias']:x for x in read(M2/'public/SOURCE_MANIFEST.json')['cases']}
    ledger=read(M2/'private/TOKEN_LEDGER.json')
    (out/'sender/media').mkdir(parents=True,exist_ok=True)
    episodes=[];requests=[];reference=[]
    for case in ao:
        name=case['case_alias'];lo=min(x['frame'] for x in case['V1']['roles'])-40;hi=case['query_frame']
        op=DEV_OBS if case['split']=='development' else VAL/'observations_validation.jsonl.gz'
        dp=DEV_DEPTH if case['split']=='development' else VAL/'features_validation.jsonl.gz'
        rows=stream(op,lo,hi);depth_rows=stream(dp,lo,hi)
        masks={}
        with gzip.open(ASSIGN[case['split']],'rt',encoding='utf-8') as fh:
            for line in fh:
                ar=json.loads(line);f=ar['frame']
                if lo<=f<=hi:
                    masks.update({(f,int(k.split(':')[1])):hashlib.sha256(dumps(v).encode()).hexdigest()
                                  for k,v in ar['masks'].items()})
        card=read(AO1/'blind'/name/'P1/card.json')
        packet,images=build(case,m2[name],ledger[name],rows,depth_rows,masks,card,out)
        episodes.append(packet);reference.append(dict(case=name,old_to_new=packet['old_to_new_reference'],
                                                     pre={r:[x['source_frame'] for x in packet['PRE_HISTORY'][r]['observations']] for r in 'AB'},
                                                     post={r:[x['source_frame'] for x in packet['POST_HISTORY_TO_Q'][r]['observations']] for r in 'XY'}))
        for arm in ARMS:
            text=condition(packet,arm)
            wanted={x['image_id'] for x in text['IMAGE_INDEX']}
            selected=[x for x in images if x['image_id'] in wanted]
            requests.append(dict(attempt_id=f'{name}-{arm}',case=name,arm=arm,text=dumps(text),
                                 images=[{k:x[k] for k in ('image_id','media_file','sha256','bytes')} for x in selected]))
    assert len(requests)==25
    put(out/'public/REFERENCE_SEGMENTS.json',reference)
    put(out/'public/EPISODE_FACTS.json',episodes)
    put(out/'public/REQUEST_MANIFEST.json',dict(base='869d9812a6549307e8e4502d1ee17d6881494626',
        schedule=[r['attempt_id'] for r in requests],requests=[dict(attempt_id=r['attempt_id'],
        text_sha256=hashlib.sha256(r['text'].encode()).hexdigest(),image_sha256=[x['sha256'] for x in r['images']]) for r in requests]))
    put(out/'sender/PLAN.json',dict(model='deepseek-flash',max_tokens=65536,cap_usd=3,smoke_max=1,requests=requests))
    print(dumps(dict(cases=5,requests=25,images=len(list((out/'sender/media').iterdir())))))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True)
    main(p.parse_args().out)
