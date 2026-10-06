"""Direct fixed-lag state/publication contracts; synthetic, no pixels or GT."""
import copy
import json
from types import SimpleNamespace

from lag import LagBuffer, state_hash


def initial():
    return SimpleNamespace(version=0, engine=dict(alias={}, bank={7: 'outside repair', 1: 'prior repair'}),
                           previous={}, epochs={7: 4}, provenance={1: 'earlier own-branch repair'})


def advance(before, frame, choice='H1'):
    branch = copy.deepcopy(before)
    mapping = {20: 1, 21: 2, 7: 7} if choice == 'H1' else {20: 2, 21: 1, 7: 7}
    branch.version = frame
    branch.previous = mapping.copy()
    branch.engine['alias'] = {20: mapping[20], 21: mapping[21]}
    row = dict(frame=frame, global_frame=100 + frame, time=frame / 30,
               mapping=mapping, native=[dict(id=n, mask=f'n:{n}') for n in mapping])
    return row, branch


def reject(action):
    try:
        action()
    except (AssertionError, TypeError, KeyError, ValueError):
        return
    raise AssertionError('illegal operation was accepted')


def snapshot(buffer):
    return state_hash(dict(state=buffer.state, rows=buffer.rows,
                           resolutions=buffer.resolutions, published_frame=buffer.published_frame,
                           arrival_frame=buffer.arrival_frame))


def main():
    checks = []
    lag = LagBuffer(initial())
    branch = initial()
    for f in range(1, 4):
        row, branch = advance(branch, f)
        lag.buffer(row, branch)
        assert lag.pop_ready(f) == []
    rebuilt = lag.checkpoint(0)
    replay = []
    for f in range(1, 4):
        row, rebuilt = advance(rebuilt, f, 'H2')
        replay.append((row, copy.deepcopy(rebuilt)))
    lag.resolve(0, rebuilt, replay, 3)
    assert lag.state.engine['bank'][7] == 'outside repair'
    assert lag.state.provenance[1] == 'earlier own-branch repair'
    assert lag.checkpoint(1).engine['alias'][20] == 2
    checks.append('COMPLETE_OWN_STATE_AND_EVERY_REPLAY_CHECKPOINT_SELECTED')
    before = snapshot(lag)
    bad = copy.deepcopy(replay)
    bad[0][0]['mapping'] = {20: 1, 21: 2, 7: 7}
    reject(lambda: lag.resolve(0, rebuilt, bad, 3))
    assert snapshot(lag) == before
    reject(lambda: lag.resolve(0, initial(), replay, 3))
    reject(lambda: lag.resolve(0, rebuilt, replay, 4))
    assert snapshot(lag) == before
    checks.append('OUTPUT_ONLY_MAPPING_BAD_FINAL_STATE_AND_FUTURE_CUTOFF_REJECTED_ATOMICALLY')
    branch = lag.state
    emitted = []
    for f in range(4, 32):
        row, branch = advance(branch, f, 'H2')
        lag.buffer(row, branch)
        emitted += lag.pop_ready(f)
    assert len(emitted) == 1 and emitted[0]['frame'] == 1
    assert emitted[0]['mapping'][20] == 2
    assert len(lag.rows) == 30
    published_pin = state_hash(emitted)
    reject(lambda: lag.resolve(0, rebuilt, replay, 3))
    row, branch = advance(lag.state, 32, 'H1')
    lag.buffer(row, branch)
    emitted_after = lag.pop_ready(32)
    assert emitted_after[0]['frame'] == 2 and emitted_after[0]['mapping'][20] == 2
    assert state_hash(emitted) == published_pin
    checks.append('H1_PREVIEW_H2_CONFIRMED_ONCE_AND_PUBLISHED_PREFIX_IMMUTABLE')
    pending = lag.rows
    pending[0]['mapping'][20] = 99
    assert lag.rows[0]['mapping'][20] == 2
    checkpoint = lag.checkpoint(lag.published_frame)
    checkpoint.engine['bank'][7] = 'external modification'
    assert lag.checkpoint(lag.published_frame).engine['bank'][7] == 'outside repair'
    checks.append('CALLER_MUTATIONS_CANNOT_REWRITE_QUEUE_OR_CHECKPOINT')
    before = snapshot(lag)
    bad_row, bad_state = advance(lag.state, 33)
    bad_row['native'].pop()
    reject(lambda: lag.buffer(bad_row, bad_state))
    bad_row, bad_state = advance(lag.state, 33)
    bad_row['mapping'][20] = bad_row['mapping'][21]
    bad_state.previous = bad_row['mapping'].copy()
    reject(lambda: lag.buffer(bad_row, bad_state))
    bad_row, bad_state = advance(lag.state, 33)
    bad_row['mapping'][20] = 1.5
    bad_state.previous = bad_row['mapping'].copy()
    reject(lambda: lag.buffer(bad_row, bad_state))
    bad_row, bad_state = advance(lag.state, 33)
    bad_row['time'] = 32 / 30
    reject(lambda: lag.buffer(bad_row, bad_state))
    bad_row, bad_state = advance(lag.state, 33)
    bad_state.version = 32
    reject(lambda: lag.buffer(bad_row, bad_state))
    reject(lambda: lag.pop_ready(99))
    assert snapshot(lag) == before
    checks.append('MASK_ID_TIME_VERSION_AND_FAKE_FUTURE_BOUNDARIES')
    suffix = lag.pop_ready(32, flush=True)
    all_rows = emitted + emitted_after + suffix
    assert [r['frame'] for r in all_rows] == list(range(1, 33))
    assert lag.pop_ready(32, flush=True) == []
    reject(lambda: lag.buffer(*advance(lag.state, 33)))
    assert lag.checkpoint(32).version == 32
    assert lag.state.engine['bank'][7] == 'outside repair'
    checks.append('EVERY_FRAME_EXACTLY_ONCE_FINAL_FLUSH_AND_OUTSIDE_REPAIR_RETAINED')
    print(json.dumps(dict(status='PASS', checks=checks, count=len(checks), model_http=0,
                          delay_frames=30), indent=2))


if __name__ == '__main__':
    main()
