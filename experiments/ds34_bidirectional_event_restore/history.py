"""DS29 exact, independently versioned pre fragments; group/post stay anonymous."""
from collections import OrderedDict
import copy

from common import CFG

DEPTH_REFERENCE_FIELDS = {
    'path', 'frame', 'global_frame', 'time', 'fact_id', 'certificate_sha256',
    'packet_sha256', 'source_row_sha256', 'row_sha256', 'measurement_sha256',
    'mask_sha256',
}


def anchor_key(anchor):
    return tuple(anchor[k] for k in ('frame', 'native_id', 'canonical_id', 'mask')) if anchor else None


class History:
    def __init__(self, name):
        self.name = name
        self.previous, self.live, self.anchors = {}, {}, {}
        self.frames = OrderedDict()
        self.last_frame = self.last_time = None

    def current_version(self, native, frame, mapping, epochs):
        prior = self.previous.get(native)
        generation = (prior['generation'] if prior and prior['frame'] == frame - 1
                      else prior['generation'] + 1 if prior else 1)
        return [native, generation, mapping[native], epochs.get(native, 0)]

    def observe(self, row, mapping, epochs, engine, classes=None, depth_refs=None):
        frame, now = row['frame'], row['time']
        assert self.last_frame is None or frame > self.last_frame, 'noncausal or duplicate history frame'
        assert self.last_time is None or now > self.last_time, 'nonincreasing history time'
        native = [o['id'] for o in row['observations']]
        assert len(native) == len(set(native)) and set(mapping) == set(native)
        assert len(set(mapping.values())) == len(mapping), 'public ID collision'
        classes, depth_refs = classes or {}, depth_refs or {}
        assert set(depth_refs) <= set(native)
        for n, reference in depth_refs.items():
            assert isinstance(reference, dict) and set(reference) <= DEPTH_REFERENCE_FIELDS, 'depth references only'
            assert all(isinstance(v, (str, int, float, type(None))) for v in reference.values()), 'no pixels in history'
            assert reference.get('frame', frame) == frame and reference.get('time', now) == now
        objects, fragments = {}, {}
        for o in row['observations']:
            n, k = o['id'], mapping[o['id']]
            version = self.current_version(n, frame, mapping, epochs)
            anchor = engine.bank.get(k, {}).get('anchor')
            source_class = classes.get(n, 'SOURCE_OBSERVATION')
            clean = bool(source_class == 'SOURCE_OBSERVATION' and k >= 0
                and anchor == dict(frame=frame, native_id=n, canonical_id=k, mask=o['mask'])
                and engine.quality(o) and not o.get('neighbors') and n not in engine.retired)
            previous = self.live.get(n)
            continuous = bool(clean and previous and previous[-1]['frame'] == frame - 1
                              and previous[-1]['version'] == version)
            item = dict(frame=frame, time=now, native=n, public=k, version=version,
                box=copy.deepcopy(o['box']), area=o['area'], neighbors=list(o.get('neighbors', [])),
                acquired_mask_depth=copy.deepcopy(o.get('depth')),
                raw_depth_reference=copy.deepcopy(depth_refs.get(n)), source_observation_class=source_class,
                measurement_origin='ORIGINAL_SAVED_OBSERVATION; MASK_MAY_BE_MIXED',
                observation_class='CLEAN_ACTUAL_BANK_ANCHOR' if clean else 'ANONYMOUS_RISK_OBSERVATION')
            objects[n] = item
            if clean:
                self.live[n] = ((previous if continuous else []) + [item])[-CFG['history_frames']:]
                fragments[n] = tuple(copy.deepcopy(self.live[n][-CFG['fit_observations']:]))
                record = dict(time=now, version=copy.deepcopy(version), frame=frame, native=n, public=k)
                key = anchor_key(anchor)
                assert key not in self.anchors or self.anchors[key] == record, 'immutable anchor changed'
                self.anchors.setdefault(key, record)
            else:
                self.live.pop(n, None)
            self.previous[n] = dict(frame=frame, generation=version[1])
        for n in list(self.live):
            if n not in objects:
                self.live.pop(n)
        self.frames[frame] = dict(time=now, objects=objects, fragments=fragments)
        while self.frames and now - next(iter(self.frames.values()))['time'] > CFG['max_history_seconds']:
            self.frames.popitem(last=False)
        for key, record in list(self.anchors.items()):
            if now - record['time'] > CFG['max_history_seconds']:
                self.anchors.pop(key)
        self.last_frame, self.last_time = frame, now
        return objects

    def freeze_pre(self, episode):
        result = {}
        before = episode['suspect_frame']
        for role, public in zip(('A', 'B'), episode['public_ids']):
            anchor = episode['bank_snapshot'][public].get('anchor')
            record = self.anchors.get(anchor_key(anchor))
            snapshot = self.frames.get(record['frame']) if record else None
            samples = list(snapshot['fragments'].get(record['native'], ())) if snapshot else []
            valid = bool(record and samples and samples[-1]['frame'] == anchor['frame'] < before
                and record['public'] == public and anchor['canonical_id'] == public
                and all(s['version'] == record['version'] and s['public'] == public
                        and s['observation_class'] == 'CLEAN_ACTUAL_BANK_ANCHOR' for s in samples)
                and all(b['frame'] == a['frame'] + 1 and b['time'] > a['time']
                        for a, b in zip(samples, samples[1:])))
            result[role] = dict(status='EXACT_INDEPENDENT_VERSIONED_REFERENCE' if valid else 'UNKNOWN_REFERENCE',
                public=public, anchor=copy.deepcopy(anchor),
                version=copy.deepcopy(record['version']) if valid else None,
                samples=copy.deepcopy(samples) if valid else [])
        return result
