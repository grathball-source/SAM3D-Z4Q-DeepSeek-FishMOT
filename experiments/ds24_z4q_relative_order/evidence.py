"""One conditional pair-order refutation; no state or candidate cost writes."""
import math, statistics, copy
from common import *
CFG = read(HERE/'CONFIG.json')

def t4_cdf(value):
    u = value/math.hypot(value, 2.)
    return max(0., min(1., .5+.75*u-.25*u**3))

def representative(fact):
    """Do not choose between measured layers or label a support as a fish."""
    out = dict(status='UNKNOWN', fact_id=fact['fact_id'], reason=fact['reason'],
               measurement_sha256=digest(fact), foreground_identity='UNKNOWN')
    if fact['status'] != 'AVAILABLE': return out
    supports = [c for c in fact['components'] if c['qualified']]
    if len(supports) != 1: return dict(out, reason='MULTIPLE_QUALIFIED_SUPPORTS_NO_PEAK_SELECTION')
    c = supports[0]
    if c['independent_n']/max(1, fact['original_mask_area']) < CFG['minimum_support_over_original_mask']:
        return dict(out, reason='INSUFFICIENT_SUPPORT_OVER_ORIGINAL_MASK')
    # A second substantial sign is mixed evidence even when disconnected into small pieces.
    other_n = sum(x['independent_n'] for x in fact['components'] if x['sign'] != c['sign'])
    if other_n >= fact['parameters']['minimum_layer_n']:
        return dict(out, reason='OPPOSING_SIGN_SUPPORT_RETAINED_AS_MIXED')
    s = c['depth_summary']; plane = fact['plane']
    uncertainty = plane['mask_prediction_uncertainty_mm']['q90']
    if uncertainty is None or not math.isfinite(uncertainty):
        return dict(out, reason='PLANE_PREDICTION_UNCERTAINTY_MISSING')
    sigma = math.sqrt(s['scale_mm']**2 + plane['residual_scale_mm']**2 + uncertainty**2)
    if sigma > fact['parameters']['max_scale_mm']:
        return dict(out, reason='COMBINED_SUPPORT_UNCERTAINTY_TOO_BROAD')
    return dict(out, status='AVAILABLE_PROXY', reason='ONE_EXPLICIT_BACKGROUND_RELATIVE_SUPPORT',
        support_id=c['support_id'], z_mm=s['median'], sigma_mm=sigma, independent_n=c['independent_n'],
        support_fraction_of_original_mask=c['independent_n']/max(1,fact['original_mask_area']),
        background_scale_mm=plane['residual_scale_mm'], plane_q90_uncertainty_mm=uncertainty,
        support_sign=c['sign'], physical_depth_accuracy_mm='UNKNOWN')

def pair_order(pairs, post, query_time):
    out = dict(status='UNKNOWN', veto=False, pre_pairs=pairs, current_pair=post)
    def unknown(reason): return dict(out, reason=reason)
    if len(pairs) < CFG['minimum_pre_pairs']: return unknown('TOO_FEW_CONTIGUOUS_PRE_PAIRS')
    if any(b['frame'] != a['frame']+1 or b['time'] <= a['time'] for a,b in zip(pairs,pairs[1:])):
        return unknown('PRE_GAP_OR_NONMONOTONIC_TIME')
    if any(x['status'] != 'AVAILABLE_PROXY' for p in pairs for x in (p['A'],p['B'])):
        return unknown('PRE_DEPTH_SUPPORT_UNKNOWN')
    if any(post[r]['status'] != 'AVAILABLE_PROXY' for r in ('A','B')):
        return unknown('CURRENT_DEPTH_SUPPORT_UNKNOWN')
    calculated=[]
    for p in pairs:
        delta = p['B']['z_mm']-p['A']['z_mm']
        scale = math.hypot(p['A']['sigma_mm'],p['B']['sigma_mm'])
        calculated.append(dict(frame=p['frame'],time=p['time'],delta_mm=delta,scale_mm=scale,p_A_nearer=t4_cdf(delta/scale)))
    low = 1/(1+CFG['minimum_joint_odds']); high=1-low
    if any(p['p_A_nearer']<=low for p in calculated) and any(p['p_A_nearer']>=high for p in calculated):
        return dict(out, reason='CONFIDENT_PRE_ORDER_REVERSAL', calculated_pre=calculated)
    last=calculated[-1]; gap=query_time-last['time']
    if not 0<gap<=CFG['max_history_seconds']: return unknown('EXPIRED_OR_NONCAUSAL_PAIR')
    dt=[b['time']-a['time'] for a,b in zip(calculated,calculated[1:])]
    span=max(last['time']-calculated[0]['time'],statistics.median(dt))
    floor2=2*CFG['raw_scale_floor_mm']**2
    original_process=floor2*(1+(gap/span)**2)
    increments=[dict(first_frame=a['frame'],second_frame=b['frame'],dt_seconds=b['time']-a['time'],
        delta_increment_mm=b['delta_mm']-a['delta_mm'],
        diffusion_mm2_per_second=max(0.,(b['delta_mm']-a['delta_mm'])**2-a['scale_mm']**2-b['scale_mm']**2)/(b['time']-a['time']))
        for a,b in zip(calculated,calculated[1:])]
    diffusion=statistics.median(x['diffusion_mm2_per_second'] for x in increments)
    process=max(original_process,diffusion*gap)
    pre_scale=math.sqrt(last['scale_mm']**2+process)
    p_pre=t4_cdf(last['delta_mm']/pre_scale)
    delta=post['B']['z_mm']-post['A']['z_mm']; scale=math.hypot(post['A']['sigma_mm'],post['B']['sigma_mm'])
    p_post=t4_cdf(delta/scale); same=p_pre*p_post+(1-p_pre)*(1-p_post)
    detail=dict(calculated_pre=calculated,pre_probability_A_nearer_at_q=p_pre,
        current_probability_A_nearer=p_post,current_delta_B_minus_A_mm=delta,current_scale_mm=scale,
        probability_same_order_proxy=same,pre_scale_at_q_mm=pre_scale,
        real_gap_seconds=gap,real_pre_span_seconds=span,process_variance_mm2=process,
        original_process_variance_mm2=original_process,diffusion_mm2_per_second=diffusion,increments=increments,
        probability_calibration='UNCALIBRATED_NOISE_CONTINUITY_PROXY; NO_PHYSICAL_INVARIANCE_PROOF')
    pre_strong=p_pre<=low or p_pre>=high; post_strong=p_post<=low or p_post>=high
    if not pre_strong or not post_strong:
        return dict(out,**detail,reason='WEAK_PROPAGATED_OR_CURRENT_ORDER')
    conflict=same<=low
    return dict(out,**detail,status='CONFLICT' if conflict else 'COMPATIBLE',veto=conflict,
        reason='RELIABLE_PROXY_ORDER_CONTRADICTS_THIS_JOINT_MAPPING' if conflict else 'NO_STRONG_ORDER_CONTRADICTION')

def combine(comparisons):
    reliable=[x for x in comparisons if x['status'] in ('CONFLICT','COMPATIBLE')]
    veto=bool(reliable and all(x['status']=='CONFLICT' for x in reliable))
    return dict(status='EXCLUDED' if veto else 'KEEP_ORIGINAL',veto=veto,
        reason='ALL_COMPARABLE_PARTNER_ORDERS_CONTRADICT' if veto else
               'COMPATIBLE_PARTNER_RETAINS_ORIGINAL' if any(x['status']=='COMPATIBLE' for x in reliable) else 'NO_RELIABLE_PAIR_ORDER',
        comparisons=comparisons,unknown_partner_count=sum(x['status']=='UNKNOWN' for x in comparisons))
