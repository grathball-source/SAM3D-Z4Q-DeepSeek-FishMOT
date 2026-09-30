"""Balanced row comparisons and an explicit cost for changing native identity."""
import math
from common import HERE,read
from depth_state import predict
from depth_score import log_t4
from merge_split_manager import numeric_choice
CFG=read(HERE/'CONFIG.json')
def choose(episode,frozen,measurements,full):
    _,legacy=numeric_choice(episode)
    sources=list(episode['post_roles'])
    if not legacy.get('scores'):
        return 'UNRESOLVED',dict(reason='NO_NUMERIC_PAIR',used_edges=0)
    now=episode['post_roles'][sources[0]][0]['time']
    forecasts={role:predict(frozen[role],now) for role in ('A','B')}
    bg=(dict(mu_mm=full['median'],scale_mm=max(60.,1.4826*full['mad'])) if full['n'] else None)
    post_ok=all(measurements[n]['core_usable'] for n in sources)
    edges={}
    for role in ('A','B'):
        pred=forecasts[role]
        eligible=bool(bg and post_ok and pred['mu_mm'] is not None and pred['scale_mm'] is not None)
        for n in sources:
            m=measurements[n];cost=0.
            if eligible:
                obs=m['core']
                scale=math.hypot(pred['scale_mm'],max(15.,1.4826*obs['mad']))
                lr=log_t4(obs['median'],pred['mu_mm'],scale)-log_t4(obs['median'],bg['mu_mm'],bg['scale_mm'])
                cost=-float(__import__('numpy').logaddexp(math.log(.9)+lr,math.log(.1)))
            edges[f'{role}:{n}']=dict(used=eligible,cost=cost,predict=pred,
                measurement_fact_id=m['fact_id'],observation_mm=m['core']['median'],
                observation_cohort=m.get('cohort','RAW'),missing_model='COMMON_UNINFORMATIVE_ROW')
    candidates={}
    for choice in ('H1','H2'):
        old=next(x for x in legacy['scores'] if x['choice']==choice)
        geometry=sum(e['position']+.25*(e['motion'] if e['motion'] is not None else 0.) for e in old['edges'])
        order=(0,1) if choice=='H1' else (1,0)
        pairs=[dict(role=r,source=sources[i],**edges[f'{r}:{sources[i]}']) for r,i in zip(('A','B'),order)]
        depth=sum(p['cost'] for p in pairs)
        candidates[choice]=dict(geometry=geometry,depth=depth,total=geometry+.25*depth,pairs=pairs)
    depth_best=min(candidates,key=lambda k:candidates[k]['depth'])
    total_best=min(candidates,key=lambda k:candidates[k]['total'])
    gap=abs(candidates['H1']['depth']-candidates['H2']['depth'])
    accepted=(depth_best==total_best and gap>=math.log(CFG['minimum_depth_odds']))
    return (total_best if accepted else 'UNRESOLVED'),dict(
        reason='DEPTH_AND_TOTAL_AGREE_WITH_PRESET_ODDS' if accepted else 'INSUFFICIENT_OR_CONFLICTING_DEPTH',
        candidates=candidates,edges=edges,forecasts=forecasts,background=bg,
        used_edges=sum(x['used'] for x in edges.values()),post_pair_usable=post_ok,
        depth_best=depth_best,total_best=total_best,depth_log_odds_gap=gap,
        minimum_log_odds=math.log(CFG['minimum_depth_odds']),accepted=accepted,
        evidence_max_frame=episode['q'],physical_identity='UNKNOWN_UNTIL_POSTSEAL_REFERENCE_AUDIT')
