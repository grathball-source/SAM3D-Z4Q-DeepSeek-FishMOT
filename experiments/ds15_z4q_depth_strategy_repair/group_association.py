"""The frozen DS9 score, local-level depth, and symmetric extra-edit admission."""
from __future__ import annotations

import importlib.util
import math

from common import ROOT,HERE,read
from forecast import predict as local_predict

_spec = importlib.util.spec_from_file_location(
    'ds15_isolated_group_score', ROOT / 'experiments/ds9_joint_h0_depth/association.py')
_joint = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_joint)
MAX_REFERENCE_AGE=read(HERE/'CONFIG.json')['birth_max_gap_seconds']


def predict(frozen, query_time):
    """Validate short fragments too; the unchanged forecast owns mean and scale."""
    samples = frozen.get('samples', [])[-_joint.CFG['fit_observations']:]
    key = frozen.get('key')
    reason = None
    if not samples:
        reason = 'NO_HISTORY'
    elif not key or len(key) != 5 or key[3] != frozen.get('public'):
        reason = 'MISSING_OR_MISMATCHED_PUBLIC_VERSION'
    else:
        try:
            cutoff = frozen.get('cutoff_frame', samples[-1]['frame'])
            legal = (math.isfinite(query_time) and
                0 < query_time - samples[-1]['time'] <= MAX_REFERENCE_AGE and
                all(math.isfinite(s[k]) for s in samples for k in ('time', 'z_mm', 'mad_mm')) and
                all(s['z_mm'] > 0 and s['mad_mm'] >= 0 and
                    s['frame'] <= cutoff and s['time'] < query_time and
                    s.get('version_key', key) == key and
                    s.get('observation_class', 'SOURCE_OBSERVATION') in
                    ('SOURCE_OBSERVATION', 'RESTORED_POST') for s in samples) and
                all(b['frame'] == a['frame'] + 1 and b['time'] > a['time']
                    for a, b in zip(samples, samples[1:])))
        except (KeyError, TypeError, ValueError):
            legal = False
        if not legal:
            reason = 'INVALID_CAUSAL_SAME_VERSION_CLEAN_FRAGMENT'
    if reason:
        return dict(status=reason, mu_mm=None, scale_mm=None, slope_mm_s=None,
                    samples=len(samples), sample_frames=[s.get('frame') for s in samples],
                    sample_fact_ids=[s.get('fact_id') for s in samples],
                    history_eligible=False, velocity_status='UNKNOWN_NOT_ESTIMATED')
    return dict(local_predict(frozen, query_time), history_eligible=True)


# Only this private module instance changes; the frozen R12 module is untouched.
_joint.predict = predict


def admission(episode, detail, choice):
    """Every changed protected public must prefer its chosen measured source."""
    selected = detail['candidates'][choice]
    baseline = detail['candidates']['H0']
    depth_delta = selected['depth_log_lr'] - baseline['depth_log_lr']
    audit = dict(joint_selected_choice=choice, joint_accepted=detail['accepted'],
                 depth_delta_vs_h0=depth_delta, changed_roles=[], accepted=False)
    if choice == 'H0':
        return dict(audit, reason='H0_NO_EXTRA_GROUP_EDIT')
    if not detail['post_pair_usable'] or not detail['background']['depth']:
        return dict(audit, reason='GROUP_DEPTH_PAIR_UNINFORMATIVE')
    for role, public in zip(('A', 'B'), episode['public_ids']):
        source = next((n for n, k in selected['mapping'].items() if k == public), None)
        previous = next((n for n, k in baseline['mapping'].items() if k == public), None)
        if source == previous:
            continue
        alternatives = [previous] if previous is not None else sorted(
            n for n in episode['post_roles'] if n != source)
        forecast = detail['depth_forecasts'][role]
        edge = detail['edges'][f'{role}:{source}']['depth']
        checks = [dict(source=n, used=detail['edges'][f'{role}:{n}']['depth']['used'],
            measurement_fact_id=detail['edges'][f'{role}:{n}']['depth']['measurement_fact_id'],
            log_lr=detail['edges'][f'{role}:{n}']['depth']['log_lr'],
            preference=edge['log_lr'] - detail['edges'][f'{role}:{n}']['depth']['log_lr'])
            for n in alternatives]
        check = dict(role=role, public=public, selected_source=source,
            baseline_source=previous, history_eligible=forecast.get('history_eligible', False),
            forecast_status=forecast['status'], version_key=forecast.get('version_key'),
            sample_fact_ids=forecast.get('sample_fact_ids', []), selected_used=edge['used'],
            selected_measurement_fact_id=edge['measurement_fact_id'],
            selected_depth_log_lr=edge['log_lr'], alternatives=checks)
        audit['changed_roles'].append(check)
        if not check['history_eligible'] or forecast.get('public') != public:
            return dict(audit, reason='GROUP_CHANGED_IDENTITY_HISTORY_UNKNOWN')
        if not edge['used'] or not checks or not all(c['used'] for c in checks):
            return dict(audit, reason='GROUP_CHANGED_IDENTITY_DEPTH_UNINFORMATIVE')
        if edge['log_lr'] <= 0:
            return dict(audit, reason='GROUP_CHANGED_IDENTITY_NONPOSITIVE_DEPTH_SUPPORT')
        if not all(c['preference'] > 0 for c in checks):
            return dict(audit, reason='GROUP_CHANGED_IDENTITY_NONPOSITIVE_DEPTH_PREFERENCE')
    if not audit['changed_roles'] or depth_delta <= 0:
        return dict(audit, reason='GROUP_NONPOSITIVE_DEPTH_DELTA_VS_H0')
    return dict(audit, accepted=True, reason='GROUP_CHANGED_IDENTITIES_DEPTH_ADMITTED')


def choose(episode, frozen_depth, measurements, full, baseline_mapping, mode, segment):
    choice, detail = _joint.choose(episode, frozen_depth, measurements, full,
                                 baseline_mapping, mode, segment)
    audit = admission(episode, detail, choice)
    detail['group_depth_admission'] = audit
    if choice != 'H0' and not audit['accepted']:
        detail.update(reason=audit['reason'], accepted=False,
                      selected_mapping=detail['baseline_mapping'])
        choice = 'H0'
    return choice, detail
