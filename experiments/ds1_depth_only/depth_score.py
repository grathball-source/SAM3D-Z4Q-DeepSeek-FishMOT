"""Shared-background Student-t depth evidence on top of frozen 2D pair costs."""
from __future__ import annotations

import math

from depth_state import predict
from merge_split_manager import numeric_choice


def log_t4(z, mu, scale):
    assert scale > 0 and math.isfinite(scale)
    residual = (z-mu)/scale
    return (math.lgamma(2.5)-math.lgamma(2.)-.5*math.log(4*math.pi)
            -math.log(scale)-2.5*math.log1p(residual*residual/4))


def geometry_choice(episode):
    _, legacy = numeric_choice(episode)
    if 'scores' not in legacy:
        return 'UNRESOLVED', dict(reason=legacy.get('reason'))
    candidates = [dict(choice=item['choice'], geometry=sum(
        edge['position']+.25*(edge['motion'] if edge['motion'] is not None else 0.)
        for edge in item['edges'])) for item in legacy['scores']]
    tied = abs(candidates[0]['geometry']-candidates[1]['geometry'])<=1e-9
    choice = episode['temporary_choice'] if tied else min(candidates,key=lambda x:x['geometry'])['choice']
    return choice, dict(candidates=candidates, tie=tied)


def dynamic_choice(episode, frozen, measurements, full_frame, depth_weight=.25):
    """Retain numeric_choice geometry exactly; replace only its depth term."""
    _, legacy = numeric_choice(episode)
    if 'scores' not in legacy:
        return 'UNRESOLVED', dict(reason=legacy.get('reason'), legacy=legacy)
    sources = list(episode['post_roles'])
    predictions = {role: predict(frozen[role], episode['post_roles'][sources[0]][0]['time'])
                   for role in ('A', 'B')}
    full_ok = full_frame['n'] > 0 and full_frame['median'] is not None
    baseline = (dict(mu_mm=full_frame['median'], scale_mm=max(60., 1.4826*full_frame['mad']))
                if full_ok else None)
    edge = {}
    for role in ('A', 'B'):
        for source in sources:
            observed = measurements[source]
            forecast = predictions[role]
            available = (baseline is not None and observed['core_usable'] and
                         forecast['mu_mm'] is not None and forecast['scale_mm'] is not None)
            value = 0.
            if available:
                z = observed['core']['median']
                scale = math.hypot(forecast['scale_mm'],
                                   max(15., 1.4826*observed['core']['mad']))
                log_signal = log_t4(z, forecast['mu_mm'], scale)
                log_background = log_t4(z, baseline['mu_mm'], baseline['scale_mm'])
                relative = log_signal-log_background
                value = -_logaddexp(math.log(.9)+relative, math.log(.1))
            edge[(role,source)] = dict(used=bool(available), cost=value,
                measurement_fact_id=observed.get('fact_id'),
                observation_mm=observed['core']['median'], prediction=forecast,
                observation_scale_mm=(max(15., 1.4826*observed['core']['mad'])
                                      if observed['core_usable'] else None))
    candidates = []
    for item in legacy['scores']:
        order = (0,1) if item['choice']=='H1' else (1,0)
        pairs = [(role, sources[index]) for role,index in zip(('A','B'), order)]
        geometry = sum(x['position']+.25*(x['motion'] if x['motion'] is not None else 0.)
                       for x in item['edges'])
        depth = sum(edge[p]['cost'] for p in pairs)
        candidates.append(dict(choice=item['choice'], geometry=geometry, depth=depth,
                               total=geometry+depth_weight*depth,
                               pairs=[dict(role=role, source=source, **edge[(role,source)])
                                      for role,source in pairs]))
    choice = (episode['temporary_choice'] if abs(candidates[0]['total']-candidates[1]['total'])<=1e-9
              else min(candidates,key=lambda x:x['total'])['choice'])
    return choice, dict(candidates=candidates, background=baseline,
                        used_edges=sum(v['used'] for v in edge.values()),
                        depth_weight=depth_weight, tie=abs(candidates[0]['total']-candidates[1]['total'])<=1e-9,
                        legacy_scores=[dict(choice=x['choice'], total=x['score']) for x in legacy['scores']])


def _logaddexp(a, b):
    high = max(a, b)
    return high+math.log(math.exp(a-high)+math.exp(b-high))
