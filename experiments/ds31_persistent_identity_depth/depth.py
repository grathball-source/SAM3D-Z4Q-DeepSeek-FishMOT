"""Reliable same-ROI raw depth and causal DS1 forecasts; no identity writes."""
from __future__ import annotations

import copy
import importlib.util
import math
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SPEC = importlib.util.spec_from_file_location(
    'ds31_unchanged_ds1_depth_state', _ROOT / 'experiments/ds1_depth_only/depth_state.py')
_DS1 = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_DS1)

DEPTH_WEIGHT = .25
HISTORY_SECONDS = 12.
SCALE_FLOOR_MM = 15.
MAX_MEASURED_SCALE_MM = 60.


def _multilayer(view):
    return bool(view.get('mixture_flag') or view.get('independent_mixture_flag') or
        view.get('inclusive_mixture_flag') or
        view.get('substantial_layer_count', 0) > 1 or
        view.get('inclusive_substantial_layer_count', 0) > 1)


def extract(fact):
    """Consume one validated DS18 object; keep its independent adaptive-core scalar.

    The caller validates the sealed cache's full source/ROI certificate. This
    module never selects a layer median, substitutes a whole-mask median, or
    certifies physical ownership. A whole-mask mixture also blocks individual
    history even when its exclusive core alone appears to have one layer.
    """
    if fact is None:
        return dict(usable=False, reason='MISSING_CERTIFICATE', fact_id=None,
                    z_mm=None, mad_mm=None, scale_mm=None, quality={})
    assert fact['schema'] == 'DS18_SAME_ROI_RAW_MEASUREMENT_V1'
    assert fact['no_cross_ROI_certification']
    core, whole = fact['core'], fact['whole']
    assert core['roi_definition'] == 'DS12_EXACT_L2_EXCLUSIVE_COMPONENT_ADAPTIVE_CORE'
    summary = copy.deepcopy(core['summary'])
    z, mad = summary['median'], summary['mad']
    finite = all(isinstance(v, (int, float)) and math.isfinite(v) for v in (z, mad))
    scale = max(SCALE_FLOOR_MM, 1.4826 * mad) if finite and mad >= 0 else None
    risk = _multilayer(core) or _multilayer(whole)
    usable = bool(core['eligible_single'] and core['quality_usable'] and
        core['source_ownership_exclusive'] and not core['source_population_unverified_n'] and
        not risk and summary['n'] >= 16 and summary['valid_fraction'] >= .2 and
        finite and z > 0 and mad >= 0 and scale <= MAX_MEASURED_SCALE_MM)
    quality = dict(core_status=core['status'], core_reason=core['reason'],
        core_eligible_single=core['eligible_single'], core_quality_usable=core['quality_usable'],
        exclusive_native_sources=core['source_ownership_exclusive'],
        unverified_source_n=core['source_population_unverified_n'],
        core_multilayer=_multilayer(core), whole_multilayer=_multilayer(whole),
        independent_source_n=summary['n'], fraction_of_original_core=summary['valid_fraction'],
        physical_surface_identity='UNKNOWN')
    return dict(usable=usable, reason='RELIABLE_INDEPENDENT_CORE' if usable else
        'MULTILAYER_INDIVIDUAL_HISTORY_BLOCKED' if risk else 'UNRELIABLE_INDEPENDENT_CORE',
        fact_id=core['fact_id'], certificate_fact_id=fact['fact_id'],
        certificate_sha256=fact['certificate_sha256'], native=fact['native'],
        frame=fact['frame'], time=fact['time'], z_mm=z, mad_mm=mad,
        scale_mm=scale, n=summary['n'], fraction=summary['valid_fraction'],
        summary=summary, quality=quality,
        roi_binding=copy.deepcopy(core['roi_binding']),
        selected_source_index_binding=copy.deepcopy(core['selected_source_index_binding']))


def forecast(samples, now):
    """Predict one contiguous clean version with DS1's actual last-ten-point WLS.

    Identity ownership, history writes and risk breaks belong to the controller.
    A gap/version break is rejected here too; no filtering and joining of ends.
    The unmodified DS1 fit retains its measured slope and extrapolation scale.
    """
    selected = list(samples)[-10:]
    reason = None
    if not selected:
        reason = 'NO_HISTORY'
    elif not math.isfinite(now):
        reason = 'INVALID_QUERY_TIME'
    elif any(not all(isinstance(s.get(k), (int, float)) and math.isfinite(s[k])
                    for k in ('frame', 'time', 'z_mm', 'mad_mm')) or
             s['frame'] < 1 or s['frame'] != int(s['frame']) or
             s['z_mm'] <= 0 or s['mad_mm'] < 0 or not s.get('usable', True)
             for s in selected):
        reason = 'INVALID_OR_UNRELIABLE_HISTORY'
    elif any(b['frame'] != a['frame'] + 1 or b['time'] <= a['time']
             for a, b in zip(selected, selected[1:])):
        reason = 'DISCONTINUOUS_HISTORY'
    elif any(s.get('version') != selected[-1].get('version') for s in selected):
        reason = 'HISTORY_VERSION_CHANGED'
    elif not 0 <= now - selected[-1]['time'] <= HISTORY_SECONDS:
        reason = 'EXPIRED_OR_NONCAUSAL_HISTORY'
    if reason:
        return dict(usable=False, status=reason, reason=reason, mu_mm=None,
                    slope_mm_s=None, scale_mm=None, samples=len(selected),
                    sample_frames=[s.get('frame') for s in selected], query_time=now)
    result = _DS1.predict(dict(samples=selected), now)
    usable = bool(result['mu_mm'] is not None and result['mu_mm'] > 0 and
        result['scale_mm'] is not None and math.isfinite(result['scale_mm']) and result['scale_mm'] > 0)
    return dict(result, usable=usable, reason=result['status'] if usable else 'INVALID_WLS_FORECAST')


def log_t4(z, mu, scale):
    """The normalized DS1 Student-t density, including its scale penalty."""
    assert scale > 0 and all(math.isfinite(v) for v in (z, mu, scale))
    residual = (z - mu) / scale
    return (math.lgamma(2.5) - math.lgamma(2.) - .5 * math.log(4 * math.pi)
            - math.log(scale) - 2.5 * math.log1p(residual * residual / 4))


def costs(samples_by_pid, current_extract, now, full_frame):
    """Return raw edge costs; unavailable evidence makes the entire row zero.

    Every candidate competes against the same current measurement and shared
    full-frame background. The controller adds these to its existing geometry
    costs at the external .25 weight without changing hard gates, the dummy
    cost, or candidate membership.
    """
    predictions = {pid: forecast(samples, now) for pid, samples in samples_by_pid.items()}
    values = {pid: 0. for pid in samples_by_pid}
    observed = current_extract or dict(usable=False)
    bg = full_frame or {}
    background_ok = bool(bg.get('n', 0) > 0 and
        all(isinstance(bg.get(k), (int, float)) and math.isfinite(bg[k]) for k in ('median', 'mad')) and
        bg['median'] > 0 and bg['mad'] >= 0)
    detail = dict(used=False, missing_model='COMMON_NULL_ENTIRE_CANDIDATE_ROW',
        external_depth_weight=DEPTH_WEIGHT, costs_are_weighted=False,
        measurement_fact_id=observed.get('fact_id'),
        forecasts=predictions, background=None, edges={}, no_peak_selection=True,
        no_hard_depth_gate=True, dummy_cost_change=0.)
    if observed.get('time') is not None:
        assert observed['time'] <= now, 'Future depth measurement'
    if not predictions or not observed.get('usable') or not background_ok or not all(
            p['usable'] for p in predictions.values()):
        return values, dict(detail, reason='INCOMPLETE_CURRENT_BACKGROUND_OR_CANDIDATE_HISTORY')
    background = dict(mu_mm=bg['median'], scale_mm=max(60., 1.4826 * bg['mad']))
    z = observed['z_mm']
    log_background = log_t4(z, background['mu_mm'], background['scale_mm'])
    for pid, prediction in predictions.items():
        scale = math.hypot(prediction['scale_mm'], observed['scale_mm'])
        log_signal = log_t4(z, prediction['mu_mm'], scale)
        a, b = math.log(.9) + log_signal - log_background, math.log(.1)
        high = max(a, b)
        raw = -(high + math.log(math.exp(a - high) + math.exp(b - high)))
        values[pid] = raw
        detail['edges'][pid] = dict(cost=values[pid], raw_cost=raw,
            observation_mm=z, observation_scale_mm=observed['scale_mm'],
            combined_scale_mm=scale, log_signal=log_signal, log_background=log_background)
    return values, dict(detail, used=True, reason='ALL_CANDIDATES_SHARE_AVAILABLE_DEPTH_ROW', background=background)
