"""Read-only depth contradiction at an exact original-Z4Q bank anchor.

Only the observer owns these records. It never writes an engine/bank/alias,
certifies equal identity from similar depth, or selects a favorable depth peak.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math

from common import ROOT, module

_depth = module('ds32_readonly_ds31_depth',
    ROOT / 'experiments/ds31_persistent_identity_depth/depth.py')


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
        allow_nan=False).encode()).hexdigest()


def _extract(extracts, native):
    return extracts.get(native, extracts.get(str(native)))


def _binding(extract):
    return {k: copy.deepcopy(extract.get(k)) for k in (
        'fact_id', 'certificate_fact_id', 'certificate_sha256', 'roi_binding',
        'selected_source_index_binding', 'quality', 'frame', 'time', 'native')}


class DepthEvidence:
    """Causal live fragments plus immutable exact-anchor reference registry.

    The registry survives loss/risk/weak current measurements; only the 12 s
    expiry removes a record. Current queries are issued before observe(q), so
    the current observation can never enter the target's fitted pre-history.
    """
    def __init__(self, namespace, cfg):
        self.namespace = namespace
        defaults = dict(history_frames=30, fit_observations=10,
            max_history_seconds=12., min_history_points=5,
            max_forecast_scale_mm=60., absolute_conflict_floor_mm=60.,
            conflict_scale_multiplier=3.)
        self.cfg = {k: cfg.get(k, v) for k, v in defaults.items()}
        assert self.cfg['history_frames'] == 30 and self.cfg['fit_observations'] == 10
        assert self.cfg['max_history_seconds'] == 12.
        assert self.cfg['min_history_points'] == 5
        assert self.cfg['max_forecast_scale_mm'] == self.cfg['absolute_conflict_floor_mm'] == 60.
        assert self.cfg['conflict_scale_multiplier'] == 3.
        self.previous, self.live, self.anchors = {}, {}, {}
        self.last_registered, self.last_eviction = {}, {}
        self.bank_anchors = {}
        self.frame = self.now = None

    def anchor_key(self, anchor):
        if not anchor or any(k not in anchor for k in ('frame', 'native_id', 'canonical_id', 'mask')):
            return None
        return (self.namespace, anchor['frame'], anchor['native_id'],
            anchor['canonical_id'], anchor['mask'])

    def __deepcopy__(self, memo):
        """Clone owned containers; historical records are internally immutable.

        observe() only replaces live records and registry entries; it never
        modifies a saved record/sample. query() and state() return detached
        data. Sharing those read-only values retains full history without
        copying the same 30-point fragment for each neighboring anchor.
        """
        result = type(self).__new__(type(self))
        memo[id(self)] = result
        for key, value in vars(self).items():
            setattr(result, key, dict(value) if isinstance(value, dict) else value)
        return result

    def state(self):
        """Lossless JSON state with complete sample content stored only once."""
        pool, identifiers = {}, {}
        def reference(sample):
            identity = id(sample)
            if identity not in identifiers:
                identifier = 'sample:' + str(len(identifiers))
                identifiers[identity] = identifier
                pool[identifier] = copy.deepcopy(sample)
            return identifiers[identity]
        live = {}
        for native, record in self.live.items():
            live[str(native)] = {k: copy.deepcopy(v) for k, v in record.items() if k != 'samples'}
            live[str(native)]['sample_refs'] = [reference(s) for s in record['samples']]
        anchors = {}
        for key, record in self.anchors.items():
            identifier = json.dumps(key, separators=(',', ':'))
            anchors[identifier] = {k: copy.deepcopy(v) for k, v in record.items() if k != 'samples'}
            anchors[identifier]['sample_refs'] = [reference(s) for s in record['samples']]
        return dict(namespace=self.namespace, cfg=copy.deepcopy(self.cfg),
            previous={str(k): copy.deepcopy(v) for k, v in self.previous.items()},
            live=live, anchors=anchors, sample_pool=pool,
            last_registered={str(k): list(v) for k, v in self.last_registered.items()},
            last_eviction={str(k): copy.deepcopy(v) for k, v in self.last_eviction.items()},
            bank_anchors={str(k): list(v) if v else None for k, v in self.bank_anchors.items()},
            frame=self.frame, now=self.now,
            encoding='LOSSLESS_ANCHOR_AND_LIVE_SAMPLE_POOL_REFERENCES')

    def _generation(self, native, frame):
        prior = self.previous.get(native)
        return (prior['generation'] if prior and prior['frame'] == frame - 1
            else prior['generation'] + 1 if prior else 1)

    def observe(self, row, mapping, epochs, engine, extracts, anonymous=()):
        """Record only the selected engine's genuine current clean bank write."""
        frame, now = row['frame'], row['time']
        assert self.frame is None or frame > self.frame
        assert math.isfinite(now) and (self.now is None or now > self.now)
        anonymous = set(anonymous)
        seen, output = set(), {}
        for observation in row['observations']:
            native = observation['id']; seen.add(native)
            public = mapping[native]
            generation = self._generation(native, frame)
            identity = [self.namespace, native, generation, public, epochs.get(native, 0)]
            extract = _extract(extracts, native)
            expected = dict(frame=frame, native_id=native, canonical_id=public,
                mask=observation['mask'])
            actual = engine.bank.get(public, {}).get('anchor')
            reasons = []
            if native in anonymous: reasons.append('ANONYMOUS_EVENT_RISK')
            if actual != expected: reasons.append('NO_ACTUAL_CURRENT_BANK_ANCHOR')
            if public < 0: reasons.append('NONPERSISTENT_PUBLIC_TOKEN')
            if not engine.quality(observation): reasons.append('ORIGINAL_QUALITY_FAILED')
            if observation.get('neighbors'): reasons.append('CURRENT_CONTACT_RISK')
            if native in engine.retired: reasons.append('RETIRED_SOURCE')
            if not extract or not extract.get('usable'): reasons.append('UNRELIABLE_CURRENT_DEPTH')
            if extract:
                assert (extract['frame'], extract['time'], extract['native']) == (frame, now, native)
            clean = not reasons
            prior = self.live.get(native)
            continuous = bool(clean and prior and prior['identity'] == identity and
                prior['samples'][-1]['frame'] == frame - 1 and
                prior['samples'][-1]['time'] < now)
            if clean:
                # A risk break starts a new fragment even if native/public integers
                # are unchanged. No filtering weak points and joining its ends.
                fragment_start = prior['fragment_start'] if continuous else frame
                version = identity + [fragment_start]
                source = _binding(extract)
                sample = dict(frame=frame, time=now, native=native, public=public,
                    version=version, z_mm=extract['z_mm'], mad_mm=extract['mad_mm'],
                    scale_mm=extract['scale_mm'], usable=True, fact_id=extract['fact_id'],
                    source_binding=source, source_binding_sha256=_digest(source),
                    anchor=copy.deepcopy(expected), observation_class='CLEAN_ACTUAL_BANK_ANCHOR')
                samples = ((prior['samples'] if continuous else ()) + (sample,))[-self.cfg['history_frames']:]
                self.live[native] = dict(identity=identity, fragment_start=fragment_start,
                    samples=samples)
                key = self.anchor_key(expected)
                record = dict(anchor=copy.deepcopy(expected), key=key, time=now,
                    version=version, identity=identity, fragment_start=fragment_start,
                    samples=samples)
                assert key not in self.anchors, 'Exact bank anchor already registered'
                # Internal sample dictionaries are never changed. Tuple references
                # share immutable points rather than duplicating 30 source packets.
                self.anchors[key] = record
                self.last_registered[public] = key
            else:
                self.live.pop(native, None)
                version, fragment_start, samples = identity + [None], None, ()
            self.previous[native] = dict(frame=frame, generation=generation)
            output[str(native)] = dict(native=native, public=public, source_version=version,
                source_generation=generation, public_epoch=epochs.get(native, 0),
                observation_class='CLEAN_ACTUAL_BANK_ANCHOR' if clean else 'ANONYMOUS_RISK_OBSERVATION',
                reasons=reasons, fragment_start=fragment_start,
                fragment_length=len(samples), fact_id=extract.get('fact_id') if extract else None,
                source_binding_sha256=_digest(_binding(extract)) if extract else None,
                actual_bank_anchor=copy.deepcopy(actual), registry_preserved_on_risk=True)
        for native in list(self.live):
            if native not in seen: self.live.pop(native)
        for key, record in list(self.anchors.items()):
            if now - record['time'] > self.cfg['max_history_seconds']:
                self.anchors.pop(key)
                self.last_eviction[record['anchor']['canonical_id']] = dict(
                    key=key, reason='EXPIRED', time=now)
        self.frame, self.now = frame, now
        self.bank_anchors = {public: self.anchor_key(bank.get('anchor'))
            for public, bank in engine.bank.items()}
        return output

    def query(self, frame, now, observation, public, anchor, extracts):
        """Return a single-edge veto or common-null without changing any state."""
        assert self.frame is None or frame > self.frame, 'q already entered pre-history'
        assert math.isfinite(now) and (self.now is None or now > self.now)
        native = observation['id']; key = self.anchor_key(anchor)
        extract = _extract(extracts, native)
        current = copy.deepcopy(extract)
        if extract:
            assert (extract['frame'], extract['time'], extract['native']) == (frame, now, native)
        record = self.anchors.get(key)
        lookup = 'REGISTERED' if record else 'NEVER_REGISTERED'
        if not anchor or anchor.get('canonical_id') != public:
            record, lookup = None, 'INVALID_OR_REBOUND_ANCHOR'
        elif key != self.bank_anchors.get(public):
            record, lookup = None, 'ANCHOR_CHANGED_OR_REBOUND'
        elif anchor.get('frame', frame) >= frame:
            record, lookup = None, 'NONCAUSAL_ANCHOR'
        elif record and not 0 < now - record['time'] <= self.cfg['max_history_seconds']:
            record, lookup = None, 'EXPIRED'
        elif not record:
            eviction = self.last_eviction.get(public)
            if eviction and eviction['key'] == key:
                lookup = eviction['reason']
            elif public in self.last_registered and self.last_registered[public] != key:
                lookup = 'ANCHOR_CHANGED_OR_UNREGISTERED_REFERENCE'
        result = dict(veto=False, conflict=False, reason='COMMON_NULL_NO_RELIABLE_CONTRADICTION',
            anchor=copy.deepcopy(anchor), anchor_key=list(key) if key else None,
            samples=[], forecast=None, current=current, threshold=None,
            source_contract=dict(namespace=self.namespace, query_frame=frame, query_time=now,
                source_native=native, current_source_generation=self._generation(native, frame),
                current_source_identity='UNKNOWN_BEFORE_ASSOCIATION', public_target=public,
                target_lookup=lookup, target_version=None,
                current_fact_binding=_binding(extract) if extract else None,
                exact_bank_anchor_only=True, public_integer_inheritance=False,
                current_in_pre_history=False, future_GT_network_used=False,
                physical_surface_identity='UNKNOWN'),
            depth_close_certifies_identity=False, background_reward_used=False)
        if record is None:
            return dict(result, reason='TARGET_' + lookup)
        samples = record['samples'][-self.cfg['fit_observations']:]
        result['samples'] = copy.deepcopy(list(samples))
        result['source_contract']['target_version'] = copy.deepcopy(record['version'])
        result['source_contract']['reference_binding_sha256'] = _digest(result['samples'])
        assert samples and samples[-1]['anchor'] == anchor
        assert samples[-1]['frame'] == anchor['frame']
        assert all(s['public'] == public and s['version'] == record['version'] for s in samples)
        assert all(s['frame'] < frame and s['time'] < now for s in samples)
        assert all(b['frame'] == a['frame'] + 1 and b['time'] > a['time']
            for a, b in zip(samples, samples[1:]))
        if len(samples) < self.cfg['min_history_points']:
            return dict(result, reason='TARGET_INSUFFICIENT_CONTIGUOUS_HISTORY')
        forecast = _depth.forecast(samples, now)
        result['forecast'] = forecast
        if not forecast.get('usable') or forecast.get('status') != 'WLS_LINEAR_TIME':
            return dict(result, reason='TARGET_WLS_UNAVAILABLE')
        if forecast['scale_mm'] > self.cfg['max_forecast_scale_mm']:
            return dict(result, reason='TARGET_FORECAST_TOO_BROAD')
        if not extract or not extract.get('usable'):
            return dict(result, reason='CURRENT_DEPTH_UNRELIABLE')
        if observation.get('neighbors') or observation.get('area', 0) <= 0:
            return dict(result, reason='CURRENT_OBSERVATION_RISK')
        # extract() independently fixes the actual core population, 15 mm floor,
        # 60 mm measurement cap, n/fraction gates and full-mask mixture veto.
        if (not all(isinstance(extract.get(k), (int, float)) and math.isfinite(extract[k])
                for k in ('z_mm', 'scale_mm')) or extract['z_mm'] <= 0 or
                not 0 < extract['scale_mm'] <= 60.):
            return dict(result, reason='CURRENT_DEPTH_UNRELIABLE')
        combined = math.hypot(forecast['scale_mm'], extract['scale_mm'])
        residual = abs(extract['z_mm'] - forecast['mu_mm'])
        threshold = max(self.cfg['absolute_conflict_floor_mm'],
            self.cfg['conflict_scale_multiplier'] * combined)
        veto = residual > threshold
        result.update(veto=veto, conflict=veto, reason='RELIABLE_DEPTH_CONFLICT' if veto else
            'NO_RELIABLE_DEPTH_CONFLICT_KEEP_ORIGINAL_EDGE', residual_mm=residual,
            combined_scale_mm=combined, threshold=threshold,
            threshold_is_uncalibrated_engineering_proxy=True)
        return result
