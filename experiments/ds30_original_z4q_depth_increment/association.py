"""Marginalize every anonymous qualified support; no candidate-specific peak selection."""
from common import *
from evidence import t4_cdf
from history import anchor_key
from merge_split_manager import velocity
import math,copy,numpy as np
CFG=read(HERE/'CONFIG.json')

def endpoint(packet):
    f=packet['fact'];layers=[]
    agreed=f.get('inclusive_independent_partition_agreement') and f.get('inclusive_independent_support_agreement')
    for s in f['layers']:
        used=bool(agreed and s['qualified'])
        layers.append(dict(support_id=s['support_id'],used=used,
            weight=s['independent_n']/max(1,f['original_roi_area']) if used else 0.,
            z_mm=s.get('z_mm'),sigma_mm=s.get('sigma_mm'),reason='QUALIFIED_ANONYMOUS_SUPPORT' if used else 'COMMON_NULL_SUPPORT'))
    mass=sum(s['weight'] for s in layers);assert -1e-12<=mass<=1+1e-12
    return dict(fact_id=f['fact_id'],measurement_sha256=digest(f),frame=f['frame'],supports=layers,
        null_weight=max(0.,1-mass),foreground_identity='UNKNOWN',reason=f['reason'])

def pair(a,b):
    ea,eb=endpoint(a),endpoint(b);p=.5;details=[];information_mass=0.
    for x in ea['supports']:
        if not x['used']:continue
        for y in eb['supports']:
            if not y['used']:continue
            mass=x['weight']*y['weight'];sid,t=x['support_id'],y['support_id']
            ia=a['source_index'].ravel()[a['maps']['selected_positions'][sid]]
            ib=b['source_index'].ravel()[b['maps']['selected_positions'][t]]
            shared=int(np.intersect1d(ia,ib).size)
            assert shared==0,'Paired supports must be jointly deduplicated before scoring'
            prob=t4_cdf((y['z_mm']-x['z_mm'])/math.hypot(x['sigma_mm'],y['sigma_mm']))
            p+=mass*(prob-.5);information_mass+=mass if not shared else 0.
            details.append(dict(A_support=sid,B_support=t,weight=mass,probability_A_nearer=prob,
                shared_native_sources=shared,shared_support_common_null=bool(shared)))
    assert 0<=p<=1
    return dict(A=ea,B=eb,probability_A_nearer=p,combinations=details,
        common_null_weight=1-information_mass,physical_accuracy_mm='UNKNOWN',no_peak_selection=True)

def measured_pair(sources,arm,frame,a,b):
    first,second,source_check=sources.unique_pair(arm,frame,a,b)
    result=pair(first,second);result['joint_source_check']=source_check
    return result

def freeze_pre(history,episode):
    result={}
    for role,k in zip(('A','B'),episode['public_ids']):
        anchor=episode['bank_snapshot'][k].get('anchor');record=history.anchors.get(anchor_key(anchor))
        snapshot=history.frames.get(record['frame']) if record else None
        samples=list(snapshot['fragments'].get(record['native'],())) if snapshot else []
        valid=bool(record and samples and samples[-1]['frame']==anchor['frame'] and
            all(s['version']==record['version'] and s['public']==k and s['observation_class']=='CLEAN_ACTUAL_BANK_ANCHOR' for s in samples) and
            all(b['frame']==a['frame']+1 and b['time']>a['time'] for a,b in zip(samples,samples[1:])))
        result[role]=dict(status='EXACT_INDEPENDENT_VERSIONED_REFERENCE' if valid else 'UNKNOWN_REFERENCE',
            anchor=copy.deepcopy(anchor),version=copy.deepcopy(record['version']) if valid else None,
            public=k,samples=copy.deepcopy(samples) if valid else [])
    return result

def geometry(pre,query,now):
    if not pre:return None,dict(status='UNKNOWN_GEOMETRY')
    samples=[dict(frame=s['frame'],time=s['time'],center=[(s['box'][0]+s['box'][2])/2,(s['box'][1]+s['box'][3])/2],
        bbox=s['box'],source_generation=s['version'][1],public_epoch=s['version'][3]) for s in pre]
    fit=velocity(samples);gap=now-pre[-1]['time']
    if not 0<gap<=CFG['max_history_seconds']:return None,dict(status='EXPIRED_OR_NONCAUSAL_PRE',gap_seconds=gap)
    horizon=min(gap,1.);last=samples[-1]
    predicted=([fit['intercept_px'][i]+fit['px_per_second'][i]*(last['time']+horizon-fit['time_origin']) for i in (0,1)]
        if fit['status']!='UNKNOWN' else last['center'])
    target=[(query['box'][0]+query['box'][2])/2,(query['box'][1]+query['box'][3])/2]
    diag=max(1.,math.hypot(last['bbox'][2]-last['bbox'][0],last['bbox'][3]-last['bbox'][1]))
    cost=math.dist(predicted,target)/diag
    return cost,dict(position_cost=cost,pre_fit=fit,predicted_center_px=predicted,observed_center_px=target,
        prediction_horizon_s=horizon,gap_seconds=gap,post_velocity='UNKNOWN_ONE_CURRENT_OBSERVATION')

def choose(episode,pre,row,sources,arm):
    queries={o['id']:o for o in row['observations']};ns=list(episode['post_roles']);targets=episode['public_ids']
    result=dict(pre=pre,anonymous_current_sources=ns,query_frame=row['frame'],post_count=1,
        current_roles='IDENTITY_UNKNOWN_UNTIL_MAPPING_COMMIT',candidates={},pre_pairs=[],current_pair=None,
        pre_probability=.5,attenuated_pre_probability=.5,current_probability=.5,depth_used=False)
    if len(ns)!=2 or any(not pre[r]['samples'] for r in ('A','B')):return 'DEFER',dict(result,reason='UNKNOWN_REFERENCE')
    costs={}
    for role in ('A','B'):
        for n in ns:
            cost,detail=geometry(pre[role]['samples'],queries[n],row['time']);costs[role,n]=(cost,detail)
    if any(c is None for c,_ in costs.values()):return 'DEFER',dict(result,reason='UNKNOWN_GEOMETRY')
    c=.5
    if arm=='DEPTH_INCREMENT':
        a={s['frame']:s for s in pre['A']['samples']};b={s['frame']:s for s in pre['B']['samples']}
        shared=sorted(set(a)&set(b))[-CFG['fit_observations']:]
        if hasattr(sources,'frames') and any(g not in sources.frames for g in shared):
            result['depth_reason']='FROZEN_PRE_RAW_WINDOW_EXPIRED_COMMON_NULL';shared=[]
        if shared:
            before=[measured_pair(sources,arm,g,a[g]['native'],b[g]['native']) for g in shared]
            after=measured_pair(sources,arm,row['frame'],ns[0],ns[1])
            pp=float(np.median([p['probability_A_nearer'] for p in before]));pq=after['probability_A_nearer']
            age=row['time']-a[shared[-1]]['time'];attenuation=max(0.,1-age/CFG['age_attenuation_s'])
            pa=.5+attenuation*(pp-.5);c=pa*pq+(1-pa)*(1-pq)
            result.update(pre_pairs=before,current_pair=after,pre_frames=shared,pre_probability=pp,
                attenuated_pre_probability=pa,current_probability=pq,age_attenuation=attenuation,
                depth_used=abs(c-.5)>1e-12,order_assumption='LOCAL_ORDER_MAY_PERSIST_NOT_IDENTITY_CERTIFICATE')
        else:result['depth_reason']='NO_SAME_FRAME_IN_INDEPENDENT_PRE_COMMON_NULL'
    for name,order,compat in [('H1',ns,c),('H2',ns[::-1],1-c)]:
        edges=[costs[role,n][1] for role,n in zip(('A','B'),order)]
        geometry_cost=sum(costs[role,n][0] for role,n in zip(('A','B'),order))
        depth_cost=-CFG['depth_weight']*math.log(max(1e-12,2*compat)) if c!=.5 else 0.
        result['candidates'][name]=dict(mapping=dict(zip(order,targets)),geometry_cost=geometry_cost,
            depth_cost=depth_cost,total_cost=geometry_cost+depth_cost,order_compatibility=compat,edges=edges)
    ordered=sorted(result['candidates'],key=lambda k:result['candidates'][k]['total_cost'])
    margin=result['candidates'][ordered[1]]['total_cost']-result['candidates'][ordered[0]]['total_cost']
    if not result['depth_used']:
        return 'DEFER',dict(result,margin=margin,reason='NO_DEPTH_INCREMENT_KEEP_COMPLETE_ORIGINAL_STATE',
            geometry_choice=min(result['candidates'],key=lambda k:result['candidates'][k]['geometry_cost']))
    depth_preference=min(result['candidates'],key=lambda k:result['candidates'][k]['depth_cost'])
    depth_margin=abs(result['candidates']['H1']['depth_cost']-result['candidates']['H2']['depth_cost'])
    result.update(depth_preference=depth_preference,depth_only_margin=depth_margin)
    if depth_margin<CFG['joint_margin'] or ordered[0]!=depth_preference:
        return 'DEFER',dict(result,margin=margin,reason='DEPTH_NOT_DECISIVE_OR_OPPOSES_SELECTED_KEEP_ORIGINAL',
            geometry_choice=min(result['candidates'],key=lambda k:result['candidates'][k]['geometry_cost']))
    return (ordered[0] if margin>=CFG['joint_margin'] else 'DEFER'),dict(result,margin=margin,
        reason='JOINT_MARGIN_PASSED' if margin>=CFG['joint_margin'] else 'AMBIGUOUS_COMPLETE_MAPPING',
        geometry_choice=min(result['candidates'],key=lambda k:result['candidates'][k]['geometry_cost']))
