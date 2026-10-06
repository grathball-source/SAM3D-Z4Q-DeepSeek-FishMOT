"""Unchanged measured geometry/WLS; new writes require explicit reliable depth support."""
from common import *
import copy
E = module('ds35_short_endpoint_cost', PRIOR/'evidence.py')
DEPTH = E.DEPTH

def gate(detail, enabled=True):
    result = dict(eligible=False, reason='DEPTH_DISABLED' if not enabled else 'NO_COMPLETE_ENDPOINTS',
        weighted_depth_margin=None, depth_winner=None, per_post_depth_winners=[], geometry_only_choice=None)
    if not enabled or not detail.get('scores'): return result
    if detail['common_weights']['depth'] != CFG['depth_weight']:
        return dict(result, reason='COMMON_DEPTH_UNAVAILABLE')
    if any(len(v) < CFG['minimum_pre_depth_observations'] for v in detail['pre_frames'].values()):
        return dict(result, reason='TOO_FEW_CONTIGUOUS_PRE_DEPTH_OBSERVATIONS')
    # Extrapolated uncertainty is checked too; a good current ROI cannot certify an old broad forecast.
    for candidate in detail['scores']:
        for edge in candidate['edges']:
            for row in edge['depth_rows']:
                if not row['detail']['used']: return dict(result, reason='COMMON_DEPTH_UNAVAILABLE')
                if any(p['scale_mm'] > CFG['maximum_depth_forecast_scale_mm']
                       for p in row['detail']['forecasts'].values()):
                    return dict(result, reason='DEPTH_FORECAST_TOO_UNCERTAIN')
    depth_scores = {c['choice']:sum(e['depth_cost'] for e in c['edges']) for c in detail['scores']}
    geometry_scores = {c['choice']:sum(e['geometry'] for e in c['edges']) for c in detail['scores']}
    ranked = sorted(depth_scores, key=lambda k:(depth_scores[k], k))
    winner = ranked[0]
    margin = CFG['depth_weight']*(depth_scores[ranked[1]]-depth_scores[winner])
    per_post = []
    for index in range(CFG['confirmation_clean_frames']):
        values = {c['choice']:sum(e['depth_rows'][index]['costs'][e['public']] for e in c['edges']) for c in detail['scores']}
        order = sorted(values, key=lambda k:(values[k], k))
        per_post.append(order[0] if values[order[0]] < values[order[1]] else 'UNKNOWN_TIE')
    result.update(depth_scores=depth_scores, geometry_scores=geometry_scores, depth_winner=winner,
        weighted_depth_margin=float(margin), per_post_depth_winners=per_post,
        geometry_only_choice=min(geometry_scores,key=lambda k:(geometry_scores[k],k)))
    if margin < CFG['min_weighted_depth_margin']: return dict(result, reason='INSUFFICIENT_DEPTH_MARGIN')
    if CFG['require_each_post_depth_same_winner'] and any(k != winner for k in per_post):
        return dict(result, reason='INCONSISTENT_POST_DEPTH_SUPPORT')
    if detail.get('status') != 'CHOOSE' or detail['choice'] != winner:
        return dict(result, reason='DEPTH_AND_JOINT_WINNER_DISAGREE_OR_JOINT_DEFER')
    return dict(result, eligible=True, reason='RELIABLE_COMMON_DEPTH_SUPPORTS_JOINT_MAPPING')

def choose(episode, pre, packets, enabled=True):
    detail = E.choose(episode, pre, packets, enabled, motion_provider=None)
    detail['depth_gate'] = gate(detail, enabled)
    detail['proposal_mapping'] = copy.deepcopy(detail.get('mapping'))
    if not detail['depth_gate']['eligible']:
        detail.update(status='DEFER', choice='DEFER', mapping=None,
            reason=detail['depth_gate']['reason'], original_evidence_reason=detail.get('reason'))
    detail.update(contour_policy='NOT_USED_THIS_DEPTH_ONLY_OVERRIDE', authoritative_Z4Q_unchanged_until_success=True)
    return detail
