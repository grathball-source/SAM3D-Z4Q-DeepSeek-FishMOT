"""Matched-history scalar vs normalized multi-piece likelihood at the S0 cutoff."""
from __future__ import annotations
import math
import numpy as np
from common import HERE,read
from depth_state import predict
from depth_score import log_t4
from merge_split_manager import numeric_choice

CFG=read(HERE/'CONFIG.json')

def edge(forecast,measurement,background,multi):
    observed=[p for p in measurement['pieces'] if p['qualified']] if multi else [measurement['core']]
    logs=[]
    details=[]
    for value in observed:
        z=value['median']; sigma=max(15.,1.4826*value['mad'])
        scale=math.hypot(forecast['scale_mm'],sigma)
        log_ratio=log_t4(z,forecast['mu_mm'],scale)-log_t4(z,background['mu_mm'],background['scale_mm'])
        logs.append(log_ratio)
        details.append(dict(piece_id=value.get('piece_id',measurement['fact_id']+'/scalar'),
            median_mm=z,mad_mm=value['mad'],combined_scale_mm=scale,log_likelihood_ratio=log_ratio,
            prior_weight=1/len(observed)))
    # Equal normalized mixture, including the common 10% uninformative model.
    log_ratio=float(np.logaddexp.reduce(logs)-math.log(len(logs)))
    cost=-float(np.logaddexp(math.log(.9)+log_ratio,math.log(.1)))
    return dict(available=True,cost=cost,components=details,log_mixture_ratio=log_ratio,
                source_fact_id=measurement['fact_id'],predict=forecast)

def choose(episode,frozen,measured,full,multi):
    _,legacy=numeric_choice(episode)
    if not legacy.get('scores'):
        return 'UNRESOLVED',dict(reason='NO_NUMERIC_PAIR',used_edges=0)
    sources=list(episode['post_roles'])
    now=episode['post_roles'][sources[0]][0]['time']
    forecasts={role:predict(frozen[role],now) for role in ('A','B')}
    bg=dict(mu_mm=full['median'],scale_mm=max(60.,1.4826*full['mad'])) if full['n'] else None
    availability={str(n):bool(measured[n]['core_usable'] and measured[n]['qualified_piece_count']>0) for n in sources}
    joint=bool(bg and all(availability.values()) and
        all(p['mu_mm'] is not None and p['scale_mm'] is not None for p in forecasts.values()))
    edges={}
    for role in ('A','B'):
        for n in sources:
            value=(edge(forecasts[role],measured[n],bg,multi) if joint else
                   dict(available=False,cost=0.,components=[],source_fact_id=measured[n]['fact_id'],
                        predict=forecasts[role],reason='JOINT_COMMON_UNINFORMATIVE'))
            edges[f'{role}:{n}']=value
    candidates={}
    for choice in ('H1','H2'):
        old=next(item for item in legacy['scores'] if item['choice']==choice)
        geometry=sum(e['position']+.25*(e['motion'] if e['motion'] is not None else 0.)
                     for e in old['edges'])
        order=(0,1) if choice=='H1' else (1,0)
        pairs=[dict(role=role,post_source=sources[idx],edge=edges[f'{role}:{sources[idx]}'])
               for role,idx in zip(('A','B'),order)]
        depth=sum(pair['edge']['cost'] for pair in pairs)
        candidates[choice]=dict(geometry_cost=geometry,depth_cost=depth,
            total_cost=geometry+CFG['depth_weight']*depth,pairs=pairs)
    tie=abs(candidates['H1']['total_cost']-candidates['H2']['total_cost'])<=1e-9
    result=episode['temporary_choice'] if tie else min(candidates,key=lambda k:candidates[k]['total_cost'])
    return result,dict(candidates=candidates,edges=edges,background=bg,joint_available=joint,
        observation_availability=availability,used_edges=4 if joint else 0,
        depth_weight=CFG['depth_weight'],tie=tie,legacy_scores=legacy,
        evidence_max_frame=episode['q'],history_cutoff_frames={r:frozen[r]['cutoff_frame'] for r in ('A','B')},
        representation='EQUAL_WEIGHT_NORMALIZED_PIECE_MIXTURE' if multi else 'F6_SELECTED_SCALAR',
        physical_surface_identity='UNKNOWN')

