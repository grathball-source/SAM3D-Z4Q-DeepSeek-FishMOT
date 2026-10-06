"""Verify actual source, complete prediction and scoring contracts, not a hash alone."""
from common import *


def verify_frozen_inputs(frozen):
    name = frozen['segment']
    assert name in SEGMENTS and tuple(frozen['arms']) == ARMS
    assert frozen['status'] == 'FROZEN_BEFORE_PREDICTION'
    assert frozen['no_GT_before_seal'] and frozen['RGB_authorized']
    assert frozen['future_limit_frames'] == CFG['lag_frames'] == 30
    for path, expected in frozen['code'].items():
        assert sha(path) == expected, path
    for key in ('source_manifest', 'runtime', 'sensor_audit', 'rgb_pins',
                'original_prediction', 'original_seal'):
        verify_item(frozen[key])
    runtime = read(frozen['runtime']['path'])
    verify_item(runtime['environment'])
    for pin in read(runtime['environment']['path'])['runtime_binaries']:
        verify_item(pin)
    source = read(frozen['source_manifest']['path'])
    assert source == frozen['source_chain'] and source['no_GT'] and source['no_restored_values']
    # This old no_RGB flag describes how the saved measurements were produced.
    # The new DS33 sensor reader's RGB authority is independently bound above.
    for pin in source['derived_inputs'].values():
        verify_item(pin)
    for key in ('scan', 'raw_sources', 'field_access'):
        verify_item(source[key])
    old.verify_cache_reference(frozen['depth_cache'])
    original = read(frozen['original_seal']['path'])
    assert original['artifacts_sha256']['predictions.jsonl.gz'] == frozen['original_prediction']['sha256']
    start, stop = SEGMENTS[name]
    pins = [r for r in rows(frozen['rgb_pins']['path']) if r['segment'] == name]
    assert [r['global_frame'] for r in pins] == list(range(start, stop + 1))
    assert len(pins) == frozen['frames'] == stop - start + 1
    for pin in pins:
        verify_item(pin['rgb'])
    return True


def verify_seal(name):
    public = RUN / name / 'public'
    frozen = read(public / 'FREEZE.json')
    verify_frozen_inputs(frozen)
    sealed = read(public / 'PREDICTIONS_SEALED.json')
    assert sealed['status'] == 'SEALED_AWAITING_INDEPENDENT_SCORING'
    assert tuple(sealed['arms']) == ARMS and sealed['frames'] == frozen['frames']
    assert 'FREEZE.json' in sealed['artifacts_sha256']
    for file, expected in sealed['artifacts_sha256'].items():
        path = public / file
        assert path.resolve().parent == public.resolve()
        assert sha(path) == expected, path
    return sealed


def verify_all():
    sealed = read(RUN / 'ALL_PREDICTIONS_SEALED.json')
    assert sealed['frames'] == 20098 and tuple(sealed['arms']) == ARMS
    assert set(sealed['seals']) == set(sealed['access_seals']) == set(SEGMENTS)
    for name in SEGMENTS:
        verify_item(sealed['seals'][name])
        verify_item(sealed['access_seals'][name])
        verify_seal(name)
        access = read(sealed['access_seals'][name]['path'])
        assert access['status'] == 'RGB_RAW_DEPTH_FINITE_LAG_NO_GT_RESTORED_NETWORK'
        assert access['new_model_http'] == 0 and access['future_limit_frames'] == 30
    return sealed
