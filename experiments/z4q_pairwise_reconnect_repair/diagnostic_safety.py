"""Safe copy of the archived F159 whole-row diagnostic; never used by PX."""


def legacy_row_veto_preview(bridge, row, profiles, native):
    """Temporarily exclude the entire D1 source row, then restore on failure."""
    original = bridge.engine.first_eligible.get(native)
    assert original is not None
    try:
        bridge.engine.first_eligible[native] = row['time'] - 4.0
        view = bridge.preview(row['frame'], row['time'], row['observations'], profiles)
    finally:
        bridge.engine.first_eligible[native] = original
    view['engine'].first_eligible[native] = original
    assert not any(e.get('origin_rule', 'D1_DELAYED') == 'D1_DELAYED'
                   and e.get('kind') == 'reconnect' and e.get('accepted')
                   and e.get('native_id') == native for e in view['trace']['events'])
    return view
