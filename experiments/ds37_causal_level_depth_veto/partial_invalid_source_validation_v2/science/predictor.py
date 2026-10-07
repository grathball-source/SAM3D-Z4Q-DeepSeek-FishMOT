"""Causal constant level with a conservative past-innovation diffusion proxy."""
from common import ROOT, CFG, module
import math
import statistics

DEPTH = module('ds37_frozen_ds31_measurement',
    ROOT/'experiments/ds31_persistent_identity_depth/depth.py')

def predict(samples, now):
    selected = list(samples)[-CFG['fit_observations']:]
    wls = DEPTH.forecast(selected, now)
    common = dict(query_time=now, samples=len(selected),
        sample_frames=[s.get('frame') for s in selected],
        source_fact_ids=[s.get('fact_id') for s in selected],
        sample_times=[s.get('time') for s in selected],
        original_wls_diagnostic=wls, slope_mm_s=None,
        mean_drift_assumption='CONSTANT_LEVEL_NOT_MEASURED_ZERO_VELOCITY',
        physical_uncertainty_calibrated=False, target_current_or_future_used=False)
    if not wls['usable'] or len(selected) < CFG['min_history_points']:
        reason = wls['reason'] if not wls['usable'] else 'INSUFFICIENT_CONTIGUOUS_HISTORY'
        return dict(common, usable=False, status=reason, reason=reason,
                    mu_mm=None, scale_mm=None)
    floor = CFG['level_scale_floor_mm']
    z = [s['z_mm'] for s in selected]
    sigma2 = [max(floor, 1.4826*s['mad_mm'])**2 for s in selected]
    weight = [1/v for v in sigma2]
    weight_sum = math.fsum(weight)
    mu = math.fsum(w*v for w, v in zip(weight, z))/weight_sum
    temporal_variance = math.fsum(w*(v-mu)**2 for w, v in zip(weight, z))/weight_sum
    measurement_variance = statistics.median(sigma2)
    base = max(floor**2, measurement_variance, temporal_variance)
    innovations = [dict(from_frame=a['frame'], to_frame=b['frame'],
        from_fact_id=a.get('fact_id'), to_fact_id=b.get('fact_id'),
        dt_seconds=b['time']-a['time'], dz_mm=b['z_mm']-a['z_mm'],
        rate_mm2_s=(b['z_mm']-a['z_mm'])**2/(b['time']-a['time']))
        for a, b in zip(selected, selected[1:])]
    raw_rate = statistics.median(i['rate_mm2_s'] for i in innovations)
    rate = max(CFG['innovation_rate_floor_mm2_s'], raw_rate)
    delta = now-selected[-1]['time']
    scale = math.sqrt(base+rate*delta)
    assert all(math.isfinite(x) for x in (mu, scale, rate)) and delta >= 0
    return dict(common, usable=True, status='LOCAL_LEVEL_INNOVATION',
        reason='LOCAL_LEVEL_INNOVATION', mu_mm=mu, scale_mm=scale,
        delta_seconds=delta, history_span_seconds=selected[-1]['time']-selected[0]['time'],
        base_variance_mm2=base, temporal_variance_mm2=temporal_variance,
        measurement_variance_mm2=measurement_variance,
        raw_innovation_rate_mm2_s=raw_rate, innovation_rate_mm2_s=rate,
        innovation_floor_active=raw_rate < CFG['innovation_rate_floor_mm2_s'],
        drift_variance_mm2=rate*delta, innovations=innovations,
        scale_formula='sqrt(max(floor^2,median(sigma_i^2),weighted_level_variance)+max(rate_floor,median(dz_i^2/dt_i))*Delta)',
        no_division_by_sample_count=True, no_scale_cap_or_favorable_peak_selection=True)
