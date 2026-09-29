"""Past, versioned co-visibility can exclude one identity edge.

This cache never asserts that an unexcluded pair is the same fish. It contains
no reference labels or future observations and is owned by one controller.
"""
import copy
import sys
from pathlib import Path

import cv2
import numpy as np
sys.path.insert(0, str(Path('E:/CAU/D-MOT/tools/jev_z4q_scene_v1_20260922/deps')))
from pycocotools import mask as coco


KERNEL = np.ones((7, 7), np.uint8)


def separate(a, b):
    """True only when actual masks have no intersection within a 7x7 window."""
    ax1, ay1, ax2, ay2 = a['box']
    bx1, by1, bx2, by2 = b['box']
    if ax2 + 3 < bx1 or bx2 + 3 < ax1 or ay2 + 3 < by1 or by2 + 3 < ay1:
        return True
    ra, rb = a.get('pairwise_rle'), b.get('pairwise_rle')
    if ra is None or rb is None:
        return False
    ma = coco.decode(dict(size=ra['size'], counts=ra['counts'].encode('ascii')))
    mb = coco.decode(dict(size=rb['size'], counts=rb['counts'].encode('ascii')))
    return not np.any(cv2.dilate(ma, KERNEL) & mb)


class CoVisibilityExclusion:
    def __init__(self, confirm, history_seconds=12):
        self.confirm = confirm
        self.history_seconds = history_seconds
        self.runs = {}
        self.public_lineage = {}
        self.pairs = {}
        self.current = {}
        self.frame = None
        self.now = None

    def prepare(self, frame, now, observations, engine):
        self.frame, self.now = frame, now
        self.current = {}
        by_id = {o['id']: o for o in observations}
        assert len(by_id) == len(observations)
        for n, o in by_id.items():
            h = engine.bank.get(n)
            areas = h.get('areas', []) if h else []
            area_ok = not areas or .5 * float(np.median(areas)) <= o['area'] <= 1.8 * float(np.median(areas))
            qualified = (o['area'] > 0 and engine.quality(o) and engine.depth_valid(o)
                         and not o.get('neighbors') and area_ok and o.get('pairwise_rle') is not None)
            self.current[n] = dict(qualified=qualified, generation=o.get('pairwise_generation'),
                                   observation=o, failure=None if qualified else 'quality_or_interaction')
        for n, entry in self.current.items():
            if not entry['qualified']:
                continue
            for m, other in by_id.items():
                if m != n and not separate(entry['observation'], other):
                    entry['qualified'] = False
                    entry['failure'] = 'group_duplicate_fragment_or_near_mask'
                    break

    def _continuing(self, native):
        entry, run = self.current.get(native), self.runs.get(native)
        return (run if entry and entry['qualified'] and run
                and run['last_frame'] == self.frame - 1
                and run['generation'] == entry['generation']
                and 0 < self.now - run['time'] <= self.history_seconds else None)

    def check(self, native, public, anchor, origin_rule):
        source = self._continuing(native)
        lineage = self.public_lineage.get(public)
        result = dict(origin_rule=origin_rule, native_id=native, public_id=public,
                      native_domain='source_native_segment', public_domain='target_bank_anchor',
                      source_version=None if source is None else source['version'],
                      target_version=None if lineage is None else lineage['version'],
                      anchor=copy.deepcopy(anchor), evidence_frames=[],
                      status='NO_EXCLUSION_EVIDENCE', veto=False)
        if not source:
            result['reason'] = 'source_segment_unqualified_or_no_continuous_history'
            return result
        if not anchor or not lineage or (anchor['frame'], anchor['native_id'], anchor['canonical_id']) != (
                lineage['anchor_frame'], lineage['native_id'], public):
            result['reason'] = 'target_anchor_lineage_unknown'
            return result
        if source['version'] == lineage['version']:
            result['reason'] = 'same_version_no_exclusion'
            return result
        key = tuple(sorted((source['version'], lineage['version'])))
        pair = self.pairs.get(key)
        if pair and pair['count'] >= self.confirm and 0 <= self.now - pair['time'] <= self.history_seconds:
            result.update(status='EXCLUDED', veto=True,
                          reason='qualified_versioned_past_co_visibility_7x7_separated',
                          evidence_frames=list(pair['frames']), evidence_count=pair['count'])
        else:
            result['reason'] = 'no_confirmed_pair_streak'
        return result

    def finish(self, frame, now, observations, mapping, engine):
        assert (frame, now) == (self.frame, self.now)
        for n, entry in self.current.items():
            k = mapping[n]
            anchor = engine.bank.get(k, {}).get('anchor')
            clean = (entry['qualified'] and k == n and n not in engine.alias and n not in engine.retired
                     and anchor and anchor['frame'] == frame and anchor['native_id'] == n
                     and anchor['canonical_id'] == n)
            if not clean:
                self.runs.pop(n, None)
                self.public_lineage.pop(k, None)
                self.public_lineage.pop(n, None)
                continue
            prior = self._continuing(n)
            version = prior['version'] if prior else f"native:{n}:start:{frame}:gen:{entry['generation']}"
            self.runs[n] = dict(version=version, last_frame=frame, time=now,
                                generation=entry['generation'])
            self.public_lineage[k] = dict(version=version, anchor_frame=frame,
                                          native_id=n)
        clean = [n for n, entry in self.current.items()
                 if entry['qualified'] and n in self.runs and mapping[n] == n]
        for i, n in enumerate(clean):
            for m in clean[i+1:]:
                if not separate(self.current[n]['observation'], self.current[m]['observation']):
                    continue
                key = tuple(sorted((self.runs[n]['version'], self.runs[m]['version'])))
                previous = self.pairs.get(key)
                continued = previous and previous['last_frame'] == frame-1
                count = previous['count']+1 if continued else 1
                frames = (previous['frames'] if continued else []) + [frame]
                self.pairs[key] = dict(count=count, frames=frames[-self.confirm:],
                                       last_frame=frame, time=now)
        self.pairs = {key: value for key, value in self.pairs.items()
                      if now-value['time'] <= self.history_seconds}
        self.current = {}
