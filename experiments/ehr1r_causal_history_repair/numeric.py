"""Transparent endpoint-history reference, with symmetric depth availability."""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path


def reliable_depth(o):
    d=o.get('depth') or {}
    c=d.get('core') or {}
    if (d.get('epistemic_type')=='MEASUREMENT' and d.get('sensor_available') and d.get('synchronized')
        and not d.get('contact_risk') and d.get('overlap_pixels')==0
        and (c.get('n') or 0)>=16 and (c.get('valid_fraction') or 0)>=.2
        and c.get('median') is not None and c.get('mad') is not None):
        return c
    return None


def edge(a,b,diagonal):
    if not a['observations'] or not b['observations']:
        return dict(status='UNKNOWN',reason='MISSING_SOURCE_FRAGMENT')
    x,y=a['observations'][-1],b['observations'][0]
    gap=y['source_time_seconds']-x['source_time_seconds']
    if gap<=0:return dict(status='UNKNOWN',reason='NONCAUSAL_TIME_ORDER')
    start,end=x['bbox_center_px'],y['bbox_center_px']
    parts=[];motion={}
    for name,s,origin,target,direction in [('forward',a,start,end,1),('backward',b,end,start,-1)]:
        v=s['velocity']
        if v.get('epistemic_type')=='ESTIMATE':
            projected=[origin[k]+direction*v['velocity_px_per_s'][k]*gap for k in (0,1)]
            error=math.dist(projected,target)
            scale=diagonal+v['residual_rms_px']*(1+gap/max(.1,v['fit_interval_seconds'][1]-v['fit_interval_seconds'][0]))
            parts.append(error/scale)
            motion[name]=dict(source_fact_ids=v['source_fact_ids'],predicted_px=[round(z,3) for z in projected],
                              error_px=round(error,3),normalized=round(error/scale,6))
        else:motion[name]=dict(status='UNKNOWN',reason=v.get('reason'))
    geometry=sum(parts)/len(parts) if parts else math.dist(start,end)/diagonal
    return dict(status='AVAILABLE',endpoint_fact_ids=[x['fact_id'],y['fact_id']],
                fragment_ids=[a['fragment_id'],b['fragment_id']],gap_seconds=round(gap,3),
                geometry_cost=round(geometry,6),geometry_mode='MOTION' if parts else 'POSITION_ONLY_FALLBACK',
                position_distance_px=round(math.dist(start,end),3),motion=motion,
                depth_available=bool(reliable_depth(x) and reliable_depth(y)),
                depth_fact_ids=[x.get('depth',{}).get('fact_id'),y.get('depth',{}).get('fact_id')])


def compare(packet,roi,use_depth):
    diagonal=math.hypot(roi[2]-roi[0],roi[3]-roi[1])
    edges={f'{a}-{b}':edge(packet['PRE_HISTORY'][a],packet['POST_HISTORY_TO_Q'][b],diagonal)
           for a in 'AB' for b in 'XY'}
    depth_mode='NOT_REQUESTED'
    if use_depth:
        depth_mode='ALL_FOUR_EDGES' if all(e.get('depth_available') for e in edges.values()) else 'DEPTH_UNAVAILABLE_FALLBACK'
    if depth_mode=='ALL_FOUR_EDGES':
        for a in 'AB':
            for b in 'XY':
                x=packet['PRE_HISTORY'][a]['observations'][-1]
                y=packet['POST_HISTORY_TO_Q'][b]['observations'][0]
                c1,c2=reliable_depth(x),reliable_depth(y)
                e=edges[f'{a}-{b}']
                e['depth_cost']=round(abs(c1['median']-c2['median'])/(15+c1['mad']+c2['mad']),6)
    totals={}
    for h in packet['hypotheses']:
        selected=[edges[f'{h["mapping"][b]}-{b}'] for b in 'XY']
        totals[h['id']]=None if any(e['status']!='AVAILABLE' for e in selected) else round(
            sum(e['geometry_cost']+(e['depth_cost'] if depth_mode=='ALL_FOUR_EDGES' else 0) for e in selected),6)
    values=list(totals.values())
    choice=min(totals,key=totals.get) if None not in values and values[0]!=values[1] else 'DEFER'
    return dict(choice=choice,candidate_costs=totals,edge_costs=edges,depth_mode=depth_mode,
                type='ENDPOINT_HISTORY_COMPARATOR',
                limitation='Consumes only qualified pre/post fragments; no same-information full-event numeric comparator or VLM necessity test.')


def main(run):
    packets=json.loads((run/'public/EPISODE_FACTS.json').read_text())
    out={}
    for p in packets:
        c=p['request_id'].split('-')[-1]
        roi=next(x['roi_full_mask_xyxy'] for x in p['IMAGE_INDEX'] if x['role_tokens'])
        out[c]=dict(N_H2D=compare(p,roi,False),N_HD=compare(p,roi,True))
    path=run/'public/NUMERIC_REFERENCE.json'
    assert not path.exists()
    path.write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n')
    print({k:(v['N_H2D']['choice'],v['N_HD']['choice'],v['N_HD']['depth_mode']) for k,v in out.items()})


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--run',type=Path,required=True)
    main(ap.parse_args().run)
