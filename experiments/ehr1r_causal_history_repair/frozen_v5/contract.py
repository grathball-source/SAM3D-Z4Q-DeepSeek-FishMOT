"""Source-backed identity-fragment contract. No GT or model output is read here."""
from __future__ import annotations

import json


def reason(observation):
    if observation is None:
        return 'MISSING_PREDICTED_MASK'
    if observation.get('area', 0) <= 0:
        return 'ZERO_AREA'
    if observation.get('neighbors'):
        return 'CONTACT_RISK'
    return None


def source_item(rows, frame, native):
    row = rows.get(frame)
    return None if row is None else next((x for x in row['observations'] if x['id'] == native), None)


def validate_segment(segment, rows, native, anchor=None):
    """Every included frame must be source-clean and connected to the anchor.

    Re-reading source rows means deleting a risk field from a packet cannot pass.
    """
    observations = segment.get('observations', [])
    failures = []
    frames = [x['source_frame'] for x in observations]
    if not frames:
        return ['EMPTY_IDENTITY_SEGMENT']
    if len(frames) != len(set(frames)) or frames != sorted(frames):
        failures.append('DUPLICATE_OR_UNSORTED_FRAME')
    if anchor is not None and anchor not in frames:
        failures.append('ANCHOR_NOT_INCLUDED')
    for f in range(min(frames), max(frames) + 1):
        if f not in frames:
            failures.append(f'GAP_F{f}')
    for x in observations:
        f = x['source_frame']
        src = source_item(rows, f, native)
        why = reason(src)
        if why:
            failures.append(f'{why}_F{f}')
        elif (x.get('area_px') != src['area'] or
              x.get('neighbor_count') != len(src.get('neighbors', [])) or
              x.get('source_time_seconds') != rows[f]['time']):
            failures.append(f'SOURCE_MISMATCH_F{f}')
    return sorted(set(failures))


def old_packet_regression(packets, cases, source_rows):
    output = {}
    for packet in packets:
        case = packet['request_id'].split('-')[-1]
        roles = cases[case]['V1']['roles']
        checks = {}
        for role in 'AB':
            old = max((x for x in roles if x['role'] == role), key=lambda x: x['frame'])
            native = int(old['native_mask_key'].split(':')[1])
            checks[role] = validate_segment(packet['PRE_HISTORY'][role], source_rows[case], native, old['frame'])
        output[case] = checks
    assert output['B01']['A'] and output['B01']['B']
    assert output['B02']['A'] and output['B02']['B']
    assert any(x.startswith('CONTACT_RISK_F') for x in output['B04']['A'])
    return output


def assert_packet_segments(packet, rows, native):
    for section, roles in (('PRE_HISTORY', 'AB'), ('POST_HISTORY_TO_Q', 'XY')):
        for role in roles:
            segment = packet[section][role]
            if segment.get('status') == 'UNKNOWN':
                continue
            failures = validate_segment(segment, rows, native[role], segment.get('anchor_frame'))
            if failures:
                raise ValueError(f'{packet["request_id"]} {role}: {failures}')


def dumps(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
