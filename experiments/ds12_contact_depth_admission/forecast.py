"""Same-version local level, with the old gap prior and past diffusion proxy."""
from __future__ import annotations

import math
import statistics
from common import HERE, read
from depth_state import predict as old_predict

CFG = read(HERE / 'CONFIG.json')


def predict(frozen, query_time):
    """Do not estimate a slope or manufacture history for short fragments."""
    legacy = old_predict(frozen, query_time)
    samples = frozen['samples'][-CFG['fit_observations']:]
    if len(samples) <= 2:
        return legacy
    if legacy['mu_mm'] is None or legacy['scale_mm'] is None:
        return legacy
    finite = all(math.isfinite(s[k]) for s in samples for k in ('time','z_mm','mad_mm'))
    contiguous = all(b['frame'] == a['frame'] + 1 and b['time'] > a['time']
                     for a,b in zip(samples,samples[1:]))
    version = frozen.get('key')
    same_version = version is not None and all(s.get('version_key',version) == version for s in samples)
    clean = all(s.get('observation_class','SOURCE_OBSERVATION') in
                ('SOURCE_OBSERVATION','RESTORED_POST') for s in samples)
    cutoff = frozen.get('cutoff_frame', samples[-1]['frame'])
    causal = math.isfinite(query_time) and all(s['frame'] <= cutoff and s['time'] <= query_time for s in samples)
    if not (finite and contiguous and same_version and clean and causal and
            all(s['mad_mm'] >= 0 for s in samples)):
        return dict(legacy,status='INVALID_LOCAL_LEVEL_FRAGMENT',mu_mm=None,scale_mm=None,
                    slope_mm_s=None,legacy_reference=legacy,
                    fallback='CONTIGUOUS_CLEAN_SAME_VERSION_CAUSAL_HISTORY_REQUIRED')
    floor = CFG['raw_scale_floor_mm']
    noise = [max(floor,1.4826*s['mad_mm']) for s in samples]
    increments=[]
    for a,b,sa,sb in zip(samples,samples[1:],noise,noise[1:]):
        dt=b['time']-a['time'];dz=b['z_mm']-a['z_mm']
        excess=max(0.,dz*dz-sa*sa-sb*sb)
        increments.append(dict(first_frame=a['frame'],second_frame=b['frame'],
            first_time=a['time'],second_time=b['time'],first_fact_id=a.get('fact_id'),second_fact_id=b.get('fact_id'),
            first_source=a.get('source'),second_source=b.get('source'),
            first_z_mm=a['z_mm'],second_z_mm=b['z_mm'],first_mad_mm=a['mad_mm'],second_mad_mm=b['mad_mm'],
            first_sigma_mm=sa,second_sigma_mm=sb,dt_seconds=dt,dz_mm=dz,
            excess_variance_mm2=excess,diffusion_rate_mm2_per_second=excess/dt))
    minimum=CFG['depth_diffusion_min_increments']
    rate=(statistics.median(x['diffusion_rate_mm2_per_second'] for x in increments)
          if len(increments)>=minimum else None)
    gap=query_time-samples[-1]['time']
    old_time_scale=legacy['time_scale_seconds']
    old_process=floor*floor*(1.+(gap/old_time_scale)**2)
    proposed=rate*gap if rate is not None else None
    process=max(old_process,proposed) if proposed is not None else old_process
    variance=noise[-1]**2+process
    return dict(legacy,status='ROBUST_LOCAL_LEVEL',mu_mm=samples[-1]['z_mm'],slope_mm_s=None,
        scale_mm=math.sqrt(variance),legacy_reference=legacy,
        mean_model='LAST_REAL_SAME_VERSION_OBSERVATION',velocity_status='UNKNOWN_NOT_ESTIMATED',
        calibration=dict(method='NONNEGATIVE_NOISE_CORRECTED_PAST_INCREMENT_MEDIAN_DIFFUSION_PROXY',
            version_key=version,cutoff_frame=cutoff,actual_gap_seconds=gap,
            old_time_scale_seconds=old_time_scale,old_process_variance_mm2=old_process,
            diffusion_min_increments=minimum,legal_increment_count=len(increments),
            diffusion_estimated=rate is not None,diffusion_rate_mm2_per_second=rate,
            diffusion_variance_at_query_mm2=proposed,selected_process_variance_mm2=process,
            last_measurement_sigma_mm=noise[-1],last_measurement_variance_mm2=noise[-1]**2,
            total_variance_mm2=variance,increments=increments,
            process_lower_bound='UNCHANGED_ORIGINAL_GAP_GROWTH_PRIOR',
            fallback_reason=None if rate is not None else 'TOO_FEW_LEGAL_INCREMENTS_USE_ORIGINAL_GAP_PRIOR',
            physical_accuracy_calibrated=False,physical_surface_identity='UNKNOWN',
            proxy_limit='Observed increments combine motion, noise and possible surface/source changes; not a calibrated diffusion law.'))
