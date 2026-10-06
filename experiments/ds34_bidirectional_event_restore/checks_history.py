"""Small history contract checks; synthetic only, no GT or scientific trial."""
import copy
from types import SimpleNamespace

from common import HERE, artifact, write_new
from history import History, anchor_key


def observation(n):
    return dict(id=n, mask=f'n:{n}', box=[0, 0, 10, 10], area=100, neighbors=[],
                depth=dict(n=20, valid_fraction=.5, median=1000., mad=5.))


def frame(f, ns=(1, 2), now=None):
    return dict(frame=f, time=f / 30 if now is None else now, observations=[observation(n) for n in ns])


def engine(f, mapping):
    return SimpleNamespace(bank={k:dict(anchor=dict(frame=f, native_id=n, canonical_id=k, mask=f'n:{n}'))
                                 for n, k in mapping.items()}, retired=set(), quality=lambda o: True)


def episode(f, banks, publics=(1, 2)):
    return dict(suspect_frame=f, public_ids=list(publics), bank_snapshot=copy.deepcopy(banks))


def main():
    checks = []
    h = History('SYNTHETIC')
    for f in range(1, 13):
        h.observe(frame(f), {1:1, 2:2}, {1:1, 2:1}, engine(f, {1:1, 2:2}),
                  depth_refs={1:dict(frame=f, time=f / 30, fact_id=f'd:{f}:1', packet_sha256='synthetic')})
    frozen = h.freeze_pre(episode(13, engine(12, {1:1, 2:2}).bank))
    assert [s['frame'] for s in frozen['A']['samples']] == list(range(3, 13))
    checks.append('LATEST_TEN_CONTIGUOUS_SAME_VERSION_WITH_REFERENCES')
    old = copy.deepcopy(h.anchors)
    h.observe(frame(13), {1:1, 2:2}, {1:1, 2:1}, engine(13, {1:1, 2:2}),
              classes={1:'GROUP_MEASUREMENT', 2:'POST_UNASSIGNED'})
    assert not h.live and h.anchors == old
    assert all(o['observation_class'] == 'ANONYMOUS_RISK_OBSERVATION' for o in h.frames[13]['objects'].values())
    assert h.freeze_pre(episode(14, engine(12, {1:1, 2:2}).bank)) == frozen
    checks.append('GROUP_EMPTY_NEIGHBORS_AND_PENDING_POST_NEVER_PRE_OLD_ANCHORS_RETAINED')
    h.observe(frame(14), {1:1, 2:2}, {1:1, 2:1}, engine(14, {1:1, 2:2}))
    assert [s['frame'] for s in h.live[1]] == [14]
    checks.append('RISK_REENTRY_STARTS_NEW_FRAGMENT')
    h.observe(frame(15), {1:3, 2:2}, {1:2, 2:1}, engine(15, {1:3, 2:2}))
    assert h.live[1][0]['version'] == [1, 1, 3, 2] and len(h.live[1]) == 1
    h.observe(frame(16, (2,)), {2:2}, {2:1}, engine(16, {2:2}))
    h.observe(frame(17), {1:3, 2:2}, {1:2, 2:1}, engine(17, {1:3, 2:2}))
    assert h.live[1][0]['version'] == [1, 2, 3, 2] and len(h.live[1]) == 1
    h.observe(frame(18), {1:3, 2:2}, {1:3, 2:1}, engine(18, {1:3, 2:2}))
    assert len(h.live[1]) == 1 and h.live[1][0]['version'][-1] == 3
    checks.append('PUBLIC_MAPPING_EPOCH_AND_GAP_GENERATION_BREAK_HISTORY')
    missing = engine(18, {1:3, 2:2}).bank
    missing[3]['anchor']['native_id'] = 99
    assert h.freeze_pre(episode(19, missing, (3, 2)))['A']['status'] == 'UNKNOWN_REFERENCE'
    checks.append('NO_OTHER_NATIVE_OR_OLDER_REFERENCE_BY_PUBLIC_FALLBACK')
    assert h.freeze_pre(episode(18, engine(18, {1:3, 2:2}).bank, (3, 2)))['A']['status'] == 'UNKNOWN_REFERENCE'
    checks.append('SAME_FRAME_OR_FUTURE_REFERENCE_UNKNOWN')
    before = copy.deepcopy(dict(previous=h.previous, live=h.live, anchors=h.anchors, frames=h.frames))
    for row, refs in ((frame(18), None), (frame(19, now=.1), None),
                      (frame(19), {1:dict(frame=19, depth_mm=[[1]])})):
        try:
            h.observe(row, {1:3, 2:2}, {1:3, 2:1}, engine(19, {1:3, 2:2}), depth_refs=refs)
        except AssertionError:
            pass
        else:
            raise AssertionError('invalid history input accepted')
        assert dict(previous=h.previous, live=h.live, anchors=h.anchors, frames=h.frames) == before
    checks.append('DUPLICATE_TIME_REGRESSION_AND_PIXEL_INPUT_REJECTED_BEFORE_MUTATION')
    h.observe(frame(19, now=20.), {1:3, 2:2}, {1:3, 2:1}, engine(19, {1:3, 2:2}))
    assert set(h.frames) == {19} and anchor_key(engine(12, {1:1, 2:2}).bank[1]['anchor']) not in h.anchors
    assert h.freeze_pre(episode(20, engine(12, {1:1, 2:2}).bank))['A']['status'] == 'UNKNOWN_REFERENCE'
    checks.append('TRUE_TIME_TWELVE_SECOND_REGISTRY_AND_FRAME_EXPIRY')
    saved = h.freeze_pre(episode(20, engine(19, {1:3, 2:2}).bank, (3, 2)))
    saved['A']['samples'][0]['box'][0] = 999
    assert h.frames[19]['objects'][1]['box'][0] == 0
    checks.append('FROZEN_SAMPLES_ARE_INDEPENDENT_COPIES')
    write_new(HERE/'HISTORY_CHECKS.json', dict(status='PASS', checks=checks, synthetic_only=True,
        GT_opened=False, new_model_http=0, cost_usd=0, code=artifact(HERE/'history.py'), checker=artifact(__file__)))
    print('PASS', len(checks), 'history checks; 0 GT/API', flush=True)


if __name__ == '__main__':
    main()
