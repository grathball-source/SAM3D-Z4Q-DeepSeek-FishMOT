"""Versioned, risk-separated individual depth history and causal WLS forecast."""
from __future__ import annotations

from collections import deque
import math

import numpy as np


class DepthState:
    def __init__(self, segment, arm):
        self.segment, self.arm = segment, arm
        self.live = {}
        self.groups = []
        self.pending = []
        self.breaks = 0
        self.updates = 0

    def freeze(self, episode, frame, epochs=None, generations=None):
        result = {}
        for role, native, public in zip(('A', 'B'), episode['member_sources'], episode['public_ids']):
            record = self.live.get(native)
            same_version = (record and record['key'][3] == public and
                (epochs is None or record['key'][4] == epochs.get(native)) and
                (generations is None or record['key'][2] == generations.get(native)))
            # A completed valid fragment survives missing/risk observations.
            # Select that one fragment, never filter risk points then join its ends.
            samples = ([s.copy() for s in record['latest_fragment'] if s['frame'] >= frame-30]
                       if same_version else [])
            acquired = [item['time'] for item in record['cache']] if same_version else []
            intervals = [b-a for a,b in zip(acquired,acquired[1:]) if b>a]
            result[role] = dict(key=record['key'] if samples else None, samples=samples,
                                acquired_interval_seconds=intervals[-1] if intervals else None,
                                cutoff_frame=frame-1, source=native, public=public)
        return result

    def break_source(self, native):
        record = self.live.get(native)
        if record and record['samples']:
            record['samples'].clear()
            self.breaks += 1

    def record_pending(self,native,measurement,frame):
        if not any(x['frame']==frame and x['native']==native for x in self.pending):
            self.pending.append(dict(frame=frame,native=native,measurement=measurement))

    def update(self, native, measurement, frame, now, public, epoch, generation, observation_class):
        if observation_class == 'GROUP_MEASUREMENT':
            self.groups.append(dict(frame=frame, native=native, measurement=measurement))
            self.break_source(native)
            return
        if observation_class == 'POST_UNASSIGNED':
            self.record_pending(native,measurement,frame)
            self.break_source(native)
            return
        key = (self.segment, self.arm, generation, public, epoch)
        record = self.live.get(native)
        if record and record['key'] != key:
            self.break_source(native)
            record = None
        if record is None:
            record = dict(key=key, samples=deque(maxlen=30), cache=deque(maxlen=30),
                          latest_fragment=[], last_frame=None, last_time=None)
            self.live[native] = record
        record['cache'].append(dict(frame=frame,time=now,observation_class=observation_class,
                                    core_usable=measurement['core_usable'],measurement=measurement))
        if record['last_frame'] is not None and (record['last_frame'] != frame-1 or now <= record['last_time']):
            self.break_source(native)
        record['last_frame'], record['last_time'] = frame, now
        if observation_class not in ('SOURCE_OBSERVATION', 'RESTORED_POST') or not measurement['core_usable']:
            self.break_source(native)
            return
        record['samples'].append(dict(frame=frame, time=now, z_mm=measurement['core']['median'],
                                     mad_mm=measurement['core']['mad'], source=measurement['source'],
                                     fact_id=measurement.get('fact_id')))
        record['latest_fragment'] = list(record['samples'])
        self.updates += 1


def predict(frozen, query_time):
    samples = frozen['samples'][-10:]
    base = dict(status='NO_HISTORY', mu_mm=None, slope_mm_s=None, scale_mm=None,
                samples=len(samples), sample_frames=[s['frame'] for s in samples],
                sample_times=[s['time'] for s in samples], residual_mm=[],
                delta_seconds=None, time_scale_seconds=None, fallback=None)
    base.update(query_time=query_time,sample_fact_ids=[s.get('fact_id') for s in samples])
    if not samples:
        return base
    times = np.asarray([s['time'] for s in samples], float)
    z = np.asarray([s['z_mm'] for s in samples], float)
    if (not np.all(np.isfinite(times)) or not np.all(np.isfinite(z)) or
            query_time < times[-1] or (len(times) > 1 and np.any(np.diff(times) <= 0))):
        return dict(base, status='INVALID_TIME_OR_VALUE')
    delta = float(query_time-times[-1])
    sigma = np.maximum(15., 1.4826*np.asarray([s['mad_mm'] for s in samples], float))
    if not np.all(np.isfinite(sigma)):
        return dict(base, status='INVALID_SCALE')
    positive_dt = np.diff(times)
    acquired = frozen.get('acquired_interval_seconds')
    nominal = acquired if acquired is not None and acquired>0 else 1/30
    span = float(times[-1]-times[0])
    t0 = max(span, float(np.median(positive_dt))) if len(times) > 1 else nominal
    last_scale2 = sigma[-1]**2 + 15.**2*(1+(delta/t0)**2)
    last = dict(base, status='NO_SLOPE_LAST_VALUE', mu_mm=float(z[-1]),
                scale_mm=float(math.sqrt(last_scale2)), delta_seconds=delta,
                time_scale_seconds=t0, fallback=('NOMINAL_TIME_FALLBACK' if acquired is None else
                    'OBSERVED_ACQUISITION_INTERVAL') if len(times)==1 else None)
    if len(samples) < 3 or span <= 0:
        return last
    tau = times-times[-1]
    design = np.stack((np.ones(len(times)), tau), axis=1)
    weighted = design/sigma[:, None]
    gram = weighted.T@weighted
    rhs = weighted.T@(z/sigma)
    try:
        beta = np.linalg.solve(gram, rhs)
        inverse = np.linalg.solve(gram, np.eye(2))
        residual = z-design@beta
        gamma = max(1., float(np.sum((residual/sigma)**2)/max(len(z)-2, 1)))
        h = np.array([1., delta])
        scale2 = float(gamma*h@inverse@h + 15.**2*(1+(delta/t0)**2))
        mu = float(h@beta)
        if not all(math.isfinite(v) for v in (mu, scale2, beta[1])) or scale2 <= 0:
            return dict(last, fallback='NONFINITE_WLS')
        return dict(base, status='WLS_LINEAR_TIME', mu_mm=mu, slope_mm_s=float(beta[1]),
                    scale_mm=math.sqrt(scale2), samples=len(samples),
                    residual_mm=[float(v) for v in residual], gamma=gamma,
                    delta_seconds=delta, time_scale_seconds=t0,
                    beta_intercept_mm=float(beta[0]),covariance_proxy=(gamma*inverse).tolist())
    except np.linalg.LinAlgError:
        return dict(last, fallback='DEGENERATE_WLS')
