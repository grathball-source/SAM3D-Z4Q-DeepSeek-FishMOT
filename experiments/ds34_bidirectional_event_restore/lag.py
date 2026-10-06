"""Thirty-frame first-publication buffer; all identity decisions stay in the controller."""
from __future__ import annotations

import copy
import hashlib
import json
import math
from collections import deque


def _plain(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return ['dict', [[type(k).__name__, str(k), _plain(v)]
                         for k, v in sorted(value.items(), key=lambda item: (type(item[0]).__name__, str(item[0])))]]
    if isinstance(value, (list, tuple, set, frozenset)):
        items = list(value)
        if isinstance(value, (set, frozenset)):
            items.sort(key=repr)
        return [type(value).__name__, [_plain(v) for v in items]]
    if hasattr(value, 'tolist'):
        return ['array', str(getattr(value, 'dtype', '')), _plain(value.tolist())]
    if hasattr(value, '__dict__'):
        return [type(value).__module__ + '.' + type(value).__qualname__, _plain(vars(value))]
    raise TypeError('Unsupported state field: ' + type(value).__name__)


def state_hash(state):
    """Bind every supplied Bridge field, including its actual engine and publication state."""
    return hashlib.sha256(json.dumps(_plain(state), separators=(',', ':'),
                                    allow_nan=False).encode()).hexdigest()


def _fields(state):
    fields = state if isinstance(state, dict) else vars(state)
    assert {'engine', 'version', 'previous', 'epochs', 'provenance'} <= set(fields), 'full Bridge state required'
    assert type(fields['version']) is int and fields['version'] >= 0, 'invalid state version'
    return fields


def _validate(row, state):
    assert type(row['frame']) is int and row['frame'] > 0, 'invalid frame'
    assert type(row['global_frame']) is int and row['global_frame'] >= 0, 'invalid global frame'
    assert isinstance(row['time'], (int, float)) and not isinstance(row['time'], bool)
    assert math.isfinite(row['time']), 'invalid timestamp'
    native = row['native']
    mapping = row['mapping']
    assert isinstance(native, list) and isinstance(mapping, dict), 'native and mapping required'
    assert all(type(o['id']) is int and o['id'] >= 0 for o in native), 'invalid native ID'
    sources = [o['id'] for o in native]
    masks = [o['mask'] for o in native]
    assert len(sources) == len(set(sources)) == len(set(masks)), 'duplicate source or mask token'
    assert all(isinstance(token, str) and token for token in masks), 'invalid mask token'
    assert set(mapping) == set(sources), 'lost or added source/mask'
    assert all(type(n) is int and type(k) is int for n, k in mapping.items()), 'invalid public ID'
    assert len(mapping.values()) == len(set(mapping.values())), 'duplicate public ID'
    fields = _fields(state)
    assert fields['version'] == row['frame'], 'frame/state version mismatch'
    assert fields['previous'] == mapping, 'mapping was not selected in actual Bridge state'
    state_hash(state)


class LagBuffer:
    """Select complete own-branch replays before first publication, never edit its prefix."""

    def __init__(self, initial_state, delay_frames=30, initial_frame=0):
        assert type(delay_frames) is int and delay_frames == 30, 'DS33 freezes a 30-frame delay'
        assert type(initial_frame) is int and initial_frame >= 0
        assert _fields(initial_state)['version'] == initial_frame
        self.delay_frames = delay_frames
        self.published_frame = self.arrival_frame = initial_frame
        self._published_state = copy.deepcopy(initial_state)
        self._state = copy.deepcopy(initial_state)
        self._pending = deque()
        self._last_time = self._last_global_frame = None
        self._closed = False
        self.resolutions = []

    @property
    def state(self):
        return copy.deepcopy(self._state)

    @property
    def rows(self):
        return [copy.deepcopy(row) for row, state in self._pending]

    def checkpoint(self, frame):
        assert self.published_frame <= frame <= self.arrival_frame, 'checkpoint outside unpublished frontier'
        if frame == self.published_frame:
            return copy.deepcopy(self._published_state)
        return copy.deepcopy(next(state for row, state in self._pending if row['frame'] == frame))

    def buffer(self, row, state):
        assert not self._closed, 'buffer already flushed'
        _validate(row, state)
        assert row['frame'] == self.arrival_frame + 1, 'nonconsecutive or already published frame'
        assert self._last_time is None or row['time'] > self._last_time, 'nonincreasing time'
        assert self._last_global_frame is None or row['global_frame'] == self._last_global_frame + 1, 'nonconsecutive global frame'
        assert len(self._pending) <= self.delay_frames, 'release ready frames before next arrival'
        saved = copy.deepcopy((row, state))
        self._pending.append(saved)
        self.arrival_frame = row['frame']
        self._last_time = row['time']
        self._last_global_frame = row['global_frame']
        self._state = copy.deepcopy(saved[1])

    def resolve(self, checkpoint_frame, chosen_state, replayed_rows, evidence_max_frame):
        """Atomically replace a complete unissued suffix with actual (row, Bridge) replays."""
        assert not self._closed, 'buffer already flushed'
        assert type(checkpoint_frame) is int and self.published_frame <= checkpoint_frame < self.arrival_frame, 'published or empty suffix'
        assert type(evidence_max_frame) is int and checkpoint_frame < evidence_max_frame <= self.arrival_frame, 'future or empty evidence cutoff'
        original = list(self._pending)
        tail = [(row, state) for row, state in original if row['frame'] > checkpoint_frame]
        replayed = copy.deepcopy(list(replayed_rows))
        assert len(replayed) == len(tail), 'replay must cover complete unpublished suffix'
        for (old, old_state), entry in zip(tail, replayed, strict=True):
            assert isinstance(entry, (tuple, list)) and len(entry) == 2, 'each replay needs actual full state'
            row, state = entry
            _validate(row, state)
            for key in ('frame', 'global_frame', 'time', 'native', 'observations'):
                assert (key in row) == (key in old), 'changed source fields'
                if key in old:
                    assert row[key] == old[key], 'changed actual source row: ' + key
        selected = copy.deepcopy(chosen_state)
        assert state_hash(selected) == state_hash(replayed[-1][1]), 'chosen state differs from replay end'
        assert _fields(selected)['version'] == self.arrival_frame
        record = dict(checkpoint_frame=checkpoint_frame, evidence_max_frame=evidence_max_frame,
                      through_frame=self.arrival_frame, previous_state_sha256=state_hash(self._state),
                      selected_state_sha256=state_hash(selected),
                      replay_state_sha256=[dict(frame=row['frame'], sha256=state_hash(state)) for row, state in replayed])
        # No mutations above this line: rejected replay cannot damage this branch.
        self._pending = deque([(row, state) for row, state in original if row['frame'] <= checkpoint_frame] + replayed)
        self._state = selected
        self.resolutions.append(record)
        return copy.deepcopy(record)

    def pop_ready(self, arrival_frame, flush=False):
        assert type(arrival_frame) is int and arrival_frame == self.arrival_frame, 'fake future arrival'
        threshold = arrival_frame if flush else arrival_frame - self.delay_frames
        output = []
        while self._pending and self._pending[0][0]['frame'] <= threshold:
            row, state = self._pending.popleft()
            assert row['frame'] == self.published_frame + 1, 'duplicate or missing publication'
            self.published_frame = row['frame']
            self._published_state = state
            output.append(copy.deepcopy(row))
        if flush:
            self._closed = True
        return output
